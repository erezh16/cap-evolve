"""A7: the ACE loop acceptance (plan §11), on dev ids per rule S1. Nothing here is counted.

  check_a7_ace.py offline           prompt byte-identity with ACE's own code, validation semantics,
                                    per-bullet lint, D5 rule on a synthetic 1.3·M_cap playbook
  check_a7_ace.py loop              run_ace.py on the first 4 dev tasks into a throwaway dir, then
                                    the gateway-filter check and the transcript scan on those calls
Prints a JSON summary (counts and flags only).
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "scripts"))
sys.path.insert(0, str(EX / "ace"))
sys.path.insert(0, str(EX / "adapters"))
sys.path.insert(0, str(EX))
import awpaths as P  # noqa: E402

A7_DIR = P.AW_STATE / "acceptance" / "a7"
os.environ.setdefault("ACE_CALLS_LOG", str(A7_DIR / "llm_calls.jsonl"))
import ace_llm  # noqa: E402
ace_llm.CALLS_LOG = Path(os.environ["ACE_CALLS_LOG"])
import run_ace  # noqa: E402
import lints  # noqa: E402
from ace.vendor import playbook as vpb  # noqa: E402

ACE_SRC_FILE = P.ACE_SRC / "ace-appworld" / "experiments" / "code" / "ace" / "adaptation_react.py"

FIXED = [
    {"role": "system", "content": "You are a helpful assistant.\n\n"},
    {"role": "user", "content": "Using these APIs, now generate code to solve the actual task:\n\nTask: count {braces} and $dollars\n\n"},
    {"role": "assistant", "content": "```python\nprint({'a': 1})\n```\n\n"},
    {"role": "user", "content": "Output:\n```\n{'a': 1}\n```\n\n"},
]


def ace_methods():
    """Compile ACE's own reflector_call and curator_call from the pinned source."""
    tree = ast.parse(ACE_SRC_FILE.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "SimplifiedReActStarAgent")
    fns = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in ("reflector_call", "curator_call")]
    mod = ast.Module(body=fns, type_ignores=[])
    g = {"json": json, "apply_curator_operations": vpb.apply_curator_operations,
         "extract_json_from_text": vpb.extract_json_from_text, "get_next_global_id": vpb.get_next_global_id}
    exec(compile(mod, str(ACE_SRC_FILE), "exec"), g)
    return g["reflector_call"], g["curator_call"]


class Capture:
    def __init__(self, reply):
        self.reply = reply
        self.sent = []

    def generate(self, messages, **_):
        self.sent.append(messages[0]["content"])
        return {"content": self.reply}


def fake_agent(template_r, template_c, playbook, reply_r, reply_c, tmp):
    a = types.SimpleNamespace()
    a.reflector_prompt, a.curator_prompt = template_r, template_c
    a.world_gt_code, a.test_report = None, "TEST REPORT THAT MUST NOT APPEAR"
    a.playbook, a.trimmed_messages = playbook, FIXED
    a.reflector_model, a.curator_model = Capture(reply_r), Capture(reply_c)
    a.logger = types.SimpleNamespace(show_message=lambda **k: None)
    a.step_number, a.use_reflector = 1, True
    a.world = types.SimpleNamespace(task=types.SimpleNamespace(instruction="count {braces} and $dollars"))
    a.next_global_id = vpb.get_next_global_id(playbook)
    a.trained_playbook_file_path = str(Path(tmp) / "pb.txt")
    rc, cc = ace_methods()
    a.reflector_call = types.MethodType(rc, a)
    return a, cc


def offline() -> dict:
    res = {}
    pb = run_ace.INITIAL_PLAYBOOK
    reply_c = json.dumps({"reasoning": "r", "operations": [
        {"type": "ADD", "section": "verification_checklist", "content": "Check the answer type."},
        {"type": "ADD", "section": "not_a_section", "content": "skipped"}]})
    with tempfile.TemporaryDirectory() as tmp:
        for name, tr, tc in [("vendor", (EX / "ace/vendor/prompts/appworld_react_reflector_no_gt_prompt.txt").read_text(),
                              (EX / "ace/vendor/prompts/appworld_react_curator_prompt.txt").read_text()),
                             ("ours", run_ace.REFLECTOR_PROMPT, run_ace.CURATOR_PROMPT)]:
            a, cc = fake_agent(tr, tc, pb, "REFLECTION", reply_c, tmp)
            cc(a)
            r_ace, c_ace = a.reflector_model.sent[0], a.curator_model.sent[0]
            saved = run_ace.REFLECTOR_PROMPT, run_ace.CURATOR_PROMPT
            run_ace.REFLECTOR_PROMPT, run_ace.CURATOR_PROMPT = tr, tc
            r_port = run_ace.render_reflector(pb, FIXED)
            c_port = run_ace.render_curator(pb, "REFLECTION", "count {braces} and $dollars", FIXED)
            run_ace.REFLECTOR_PROMPT, run_ace.CURATOR_PROMPT = saved
            ops, skipped, err = run_ace.validate_curator(reply_c)
            port_pb, port_next = vpb.apply_curator_operations(pb, ops, vpb.get_next_global_id(pb))
            res[f"byte_identical_{name}"] = {"reflector": r_ace == r_port, "curator": c_ace == c_port,
                                             "playbook_after_ops": a.playbook == port_pb,
                                             "next_id": a.next_global_id == port_next,
                                             "test_report_absent": "TEST REPORT" not in r_port}
    # validation semantics: a non-ADD op skips the whole update; off-whitelist skips the op only
    bad = json.dumps({"reasoning": "r", "operations": [
        {"type": "ADD", "section": "others", "content": "fine"}, {"type": "UPDATE", "section": "others", "content": "x"}]})
    ops, _, err = run_ace.validate_curator(bad)
    res["non_add_skips_update"] = ops is None and "invalid type" in (err or "")
    ops, skipped, err = run_ace.validate_curator(reply_c)
    res["off_whitelist_skipped"] = len(ops) == 1 and len(skipped) == 1
    res["invalid_json_skips"] = run_ace.validate_curator("no json here")[0] is None
    new_pb, new_next = vpb.apply_curator_operations(pb, ops, vpb.get_next_global_id(pb))
    added = [b for b in lints.bullets(new_pb) if b not in lints.bullets(pb)]
    res["fresh_id"] = [b[0] for b in added] == [f"vc-{vpb.get_next_global_id(pb):05d}"]
    # planted bullet with a train 8-gram is lint_dropped (the planted text is not printed)
    cache = json.loads(P.LINT_CACHE.read_text())
    gram = sorted(cache["instruction_8grams"])[0]
    planted = [{"type": "ADD", "section": "others", "content": f"Remember: {gram}."},
               {"type": "ADD", "section": "others", "content": "Always paginate until an empty page."}]
    m_cap = int(P.manifest().get("m_cap", {}).get("value", 13500))
    out, nxt, info = run_ace.apply_with_rules(pb, vpb.get_next_global_id(pb), planted, m_cap, "A7-lint")
    res["planted_lint_drop"] = len(info["lint_drop"]) == 1 and info["lint_drop"][0]["rules"] == ["instruction_8gram"] \
        and info["applied"] == 1
    # D5 on a synthetic playbook of 1.3·M_cap tokens: near-duplicate generic bullets in 6 groups
    base = ["Always call apis.api_docs.show_api_doc before using an API, to check its parameters",
            "Loop over page_index until an API returns an empty page, so that no item is missed",
            "Return answers as minimal values: a number, a name or a title, never a sentence",
            "Log in to each app once with the supervisor's account password and reuse the access token",
            "Print intermediate results in small code chunks before any irreversible change",
            "Call apis.supervisor.complete_task at the end, with the answer only when one is asked for"]
    lines, k = ["## OTHERS"], 1
    while lints.count_tokens("\n".join(lines)) < 1.3 * m_cap:
        b = base[k % len(base)]
        lines.append(f"[misc-{k:05d}] {b} (variant {k // len(base)}).")
        k += 1
    synth = "\n".join(lines)
    stok = lints.count_tokens(synth)
    one = [{"type": "ADD", "section": "others", "content": "Check the output schema of an API on its first call."}]
    out, nxt, info = run_ace.apply_with_rules(synth, k, one, m_cap, "A7-d5",
                                              merge_cache=A7_DIR / "d5_merge_cache.json")
    res["d5"] = {"synthetic_tokens": stok, "m_cap": m_cap, "dedup": info["dedup"], "cap_drop": info["cap_drop"],
                 "applied": info["applied"], "result_tokens": lints.count_tokens(out),
                 "merge_calls": len(info["merge_usage"]), "lint_drop": len(info["lint_drop"])}
    res["d5_triggered"] = info["dedup"] is not None and lints.count_tokens(out) <= m_cap
    flags = [res["byte_identical_vendor"]["reflector"], res["byte_identical_vendor"]["curator"],
             res["byte_identical_vendor"]["playbook_after_ops"], res["byte_identical_ours"]["reflector"],
             res["byte_identical_ours"]["curator"], res["non_add_skips_update"], res["off_whitelist_skipped"],
             res["invalid_json_skips"], res["fresh_id"], res["planted_lint_drop"], res["d5_triggered"]]
    res["ok"] = all(flags)
    return res


def loop() -> dict:
    ace_dir = A7_DIR / "loop"
    if ace_dir.exists() and "--fresh" in sys.argv:
        shutil.rmtree(ace_dir)
    cmd = [str(P.VENV_PY), "-I", str(EX / "ace" / "run_ace.py"), "--split", "dev", "--limit", "4", "--no-ledger",
           "--ace-dir", str(ace_dir), "--pushed-dir", str(ace_dir / "pushed"), "--exp-prefix", "a7",
           "--trial-name", "a7"]
    env = {**os.environ, "ACE_CALLS_LOG": str(ace_dir / "llm_calls.jsonl"), "HF_HOME": str(P.HF_HOME)}
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    prog = P.read_json(ace_dir / "pushed" / "progress.json") or {}
    rows = prog.get("rows", [])
    calls = [json.loads(x) for x in (ace_dir / "llm_calls.jsonl").read_text().splitlines()] \
        if (ace_dir / "llm_calls.jsonl").exists() else []
    refusals = sum(1 for c in calls if c["finish_reason"] == "refusal")
    empty = 0
    from ace.vendor.playbook import extract_json_from_text
    for c in calls:
        j = extract_json_from_text(c["response"] or "") if c["role"] == "reflector" else None
        if isinstance(j, dict):
            empty += sum(1 for v in j.values() if isinstance(v, str) and not v.strip())
    scan = run_ace.scan_counts([json.dumps(c["messages"]) + (c["response"] or "") for c in calls])
    pb_final = (ace_dir / "playbooks" / f"pb_{len(rows):03d}.txt")
    added = 0
    if pb_final.exists():
        init = set(lints.bullets(run_ace.INITIAL_PLAYBOOK))
        added = len([b for b in lints.bullets(pb_final.read_text()) if b not in init])
    res = {"returncode": r.returncode, "steps_done": len(rows), "curated": sum(1 for x in rows if x.get("curated")),
           "terminations": [x.get("termination") for x in rows], "successes": sum(1 for x in rows if x.get("success")),
           "calls": len(calls), "refusals": refusals, "empty_reflector_fields": empty,
           "bullets_added": added, "pb_tokens": [x.get("pb_tokens") for x in rows],
           "scan": scan, "stderr_tail": r.stderr[-600:] if r.returncode else ""}
    res["ok"] = r.returncode == 0 and len(rows) == 4 and refusals == 0 and empty == 0 and added >= 1 \
        and scan["test_id"] == 0 and scan["root_full"] == 0 and scan["answer.json"] == 0 and scan["ground_truth"] == 0
    return res


def main() -> int:
    A7_DIR.mkdir(parents=True, exist_ok=True)
    res = offline() if sys.argv[1] == "offline" else loop()
    print(json.dumps(res))
    P.write_json(A7_DIR / f"result_{sys.argv[1]}.json", res)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
