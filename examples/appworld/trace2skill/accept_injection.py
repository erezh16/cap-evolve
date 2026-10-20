"""A-trace2skill packaging check (venv-aw, no model call): the candidate's playbook lands in the final USER
message, under the memory heading, before 'My name is:'; every earlier message equals the seed's.

  venv-aw/bin/python -I accept_injection.py CANDIDATE_DIR      # prints one JSON line {ok, ...} (booleans/counts only)

Modelled on scripts/check_injection.py. AppWorld loads the dev task itself; nothing here prints task content.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(EX / "adapters"), str(EX / "scripts")]
import awrest as P  # noqa: E402

P.setup_env()
os.environ.setdefault("OPENAI_API_KEY", "unused")
os.environ.setdefault("MODEL_SERVER_URL", "http://unused")
os.environ.setdefault(os.environ.get("AW_KEY_ENV", "RITS_API_KEY"), "unused")
os.environ["APPWORLD_ROOT"] = str(P.ROOT_OPT)

import aw_agent  # noqa: E402
from appworld import AppWorld  # noqa: E402


def kwargs(prompt_path: Path) -> dict:
    return dict(prompt_file_path=str(prompt_path), model_config=dict(aw_agent.MODEL_CONFIG),
                appworld_config={"random_seed": 100}, logger_config={"color": False, "verbose": False},
                max_output_length=aw_agent.MAX_OUTPUT_LENGTH, max_steps=50)


def first(agent, tid: str, exp: str) -> list[dict]:
    with AppWorld(task_id=tid, experiment_name=exp) as world:
        agent.initialize(world)
        return [dict(m) for m in agent.messages]


def main() -> int:
    import shutil
    cdir = Path(sys.argv[1])
    tid = P.read_split("dev")[0]
    Cap = aw_agent.build_agent_class()
    seed = P.SEED_CAP
    block = (cdir / "memory" / "playbook.md").read_text(encoding="utf-8")
    m_seed = first(Cap(candidate=aw_agent.read_candidate(seed), **kwargs(seed / "policy/instructions.txt")),
                   tid, "probes/t2s_seed")
    m_pb = first(Cap(candidate=aw_agent.read_candidate(cdir), memory_block=block,
                     **kwargs(cdir / "policy/instructions.txt")), tid, "probes/t2s_pb")
    for e in ("probes/t2s_seed", "probes/t2s_pb"):
        shutil.rmtree(P.ROOT_OPT / "experiments" / "outputs" / e, ignore_errors=True)
    last = m_pb[-1]["content"]
    h = last.find(aw_agent.MEMORY_HEADING)
    probe = block.strip().splitlines()[0] if block.strip() else ""
    ok = (len(m_pb) == len(m_seed) and m_pb[:-1] == m_seed[:-1] and 0 <= h < last.find(probe) < last.rfind("My name is:")
          < last.rfind("Task:"))
    print(json.dumps({"ok": bool(ok), "messages": len(m_pb), "same_prefix_messages": m_pb[:-1] == m_seed[:-1],
                      "heading_before_my_name_is": 0 <= h < last.rfind("My name is:"), "block_chars": len(block)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
