"""T4 (docs/TEST_ALL.md §9): injection per arm, no model call. Run in venv-aw with APPWORLD_ROOT=root_opt:

  . examples/appworld/test_all/env.sh && APPWORLD_ROOT=$AW_HOME/build/root_opt $VENV_AW/bin/python -I \
      examples/appworld/test_all/check_t4.py

For each of the 13 scored copies, render the agent's first request for one **dev** task through aw_agent.py's own
prompt-building path (CapReActAgent.initialize inside an AppWorld world, as scripts/check_injection.py does), with the
memory block the episode runner would pass (adapter._memory_block). Records per arm: messages, prompt tokens
(o200k_harmony on the contents), memory block present and placed before 'My name is:', helpers defined (the setup
snippet ran and the notice is in the prompt), notes appended (a wrapped API-doc lookup carries a note). Expected:
seed and harnesslens byte-identical to the stock first request (23 messages); every arm with M has its block before
'My name is:'; every arm with T has its helpers/notes. altk: retrieval.json has 168 keys and, for one key, the runner's
_memory_block returns a non-empty string; only its length is printed (the key is never printed). Writes
AW_STATE/acceptance/t4.json; prints flags and counts only.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "scripts"))
sys.path.insert(0, str(EX / "adapters"))
import awrest as P  # noqa: E402

P.setup_env()
os.environ.setdefault("OPENAI_API_KEY", "unused")
os.environ.setdefault("MODEL_SERVER_URL", "http://unused")
os.environ.setdefault(os.environ.get("AW_KEY_ENV", "RITS_API_KEY"), "unused")

import aw_agent  # noqa: E402
from adapter import Adapter  # noqa: E402
from appworld import AppWorld, load_task_ids  # noqa: E402
from appworld_agents.code.simplified.react_code_agent import SimplifiedReActCodeAgent  # noqa: E402

ART = P.AW_STATE / "final" / "artifacts"
STOCK = P.APPWORLD_SRC / "experiments/prompts/react_code_agent/instructions.txt"


def kwargs(prompt_path: str) -> dict:
    return dict(prompt_file_path=prompt_path, model_config=dict(aw_agent.MODEL_CONFIG),
                appworld_config={"random_seed": 7000}, logger_config={"color": False, "verbose": False},
                max_output_length=aw_agent.MAX_OUTPUT_LENGTH, max_steps=50)


def main() -> int:
    import tiktoken
    enc = tiktoken.get_encoding("o200k_harmony")
    tok = lambda t: len(enc.encode(t, disallowed_special=()))  # noqa: E731
    tid = load_task_ids("dev")[0]
    ad = Adapter()
    with AppWorld(task_id=tid, experiment_name="probes/t4_stock") as world:
        stock = SimplifiedReActCodeAgent(**kwargs(str(STOCK)))
        stock.initialize(world)
        m_stock = [dict(m) for m in stock.messages]
    Cap = aw_agent.build_agent_class()
    res, ok = {"stock_messages": len(m_stock)}, True
    for arm in P.ARMS:
        cdir = ART / arm
        cand = aw_agent.read_candidate(cdir)
        mem = ad._memory_block(cdir, tid)
        agent = Cap(candidate=cand, memory_block=mem, **kwargs(str(cdir / "policy" / "instructions.txt")))
        with AppWorld(task_id=tid, experiment_name=f"probes/t4_{arm}") as world:
            agent.initialize(world)
            msgs = [dict(m) for m in agent.messages]
            noted = None
            if cand["notes"]:
                key = next(iter(cand["notes"]))
                app, _, api = key.partition(".")
                probe = (f"print(apis.api_docs.show_api_doc(app_name={app!r}, api_name={api!r}))" if api else
                         f"print(apis.api_docs.show_api_descriptions(app_name={app!r}))")
                out = world.execute(probe)
                noted = '"note"' in out or "'note'" in out
        last = msgs[-1]["content"]
        has_mem = aw_agent.MEMORY_HEADING.rstrip(":") in last
        placed = has_mem and last.index(aw_agent.MEMORY_HEADING.rstrip(":")) < last.rindex("My name is:")
        helpers = aw_agent.has_code(cand["helpers"])
        notice = bool(aw_agent.helper_notice(cand["helpers"])) and aw_agent.helper_notice(cand["helpers"]) in last
        r = {"messages": len(msgs), "prompt_tokens_o200k": sum(tok(m["content"]) for m in msgs),
             "memory_block_present": has_mem, "memory_before_my_name_is": placed, "memory_chars": len(mem),
             "helpers_defined": helpers and agent.setup_output is not None and "Execution failed" not in (agent.setup_output or ""),
             "helper_notice_in_prompt": notice, "notes": len(cand["notes"]), "note_appended": noted,
             "byte_identical_to_stock": json.dumps(msgs) == json.dumps(m_stock)}
        changed = P.SURFACES_CHANGED[arm]
        exp = []
        if changed == "none":
            exp.append(r["byte_identical_to_stock"] and r["messages"] == 23)
        if arm in ("ace", "skillopt", "wikiskill", "evoskill", "trace2skill"):
            exp.append(placed)
        if arm == "altk":
            exp.append(not has_mem)    # retrieval.json is keyed by test ids: no block for a dev id (checked below)
        if "T" in changed:
            exp.append((not helpers or (r["helpers_defined"] and notice)) and (not cand["notes"] or bool(noted)))
        r["expected_ok"] = all(exp)
        ok &= r["expected_ok"]
        res[arm] = r
        print(json.dumps({"arm": arm, **r}))
    # altk: the lookup works for the keys it has (inside this trusted script; only counts and a length are printed)
    rj = json.loads((ART / "altk" / "memory" / "retrieval.json").read_text())
    k0 = sorted(rj)[0]
    blk = ad._memory_block(ART / "altk", k0)
    res["altk_retrieval"] = {"keys": len(rj), "block_len_for_one_key": len(blk), "ok": len(rj) == 168 and len(blk) > 0}
    ok &= res["altk_retrieval"]["ok"]
    res["seed_harnesslens_identical"] = res["seed"]["byte_identical_to_stock"] and res["harnesslens"]["byte_identical_to_stock"]
    res["ok"] = ok and res["seed_harnesslens_identical"]
    import shutil
    shutil.rmtree(P.ROOT_OPT / "experiments" / "outputs" / "probes", ignore_errors=True)
    P.write_json(P.AW_STATE / "acceptance" / "t4.json", res)
    print(json.dumps({"altk_retrieval": res["altk_retrieval"], "ok": res["ok"]}))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
