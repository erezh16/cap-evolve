"""P3 ACE start (plan §8.2, §10): record the train order (sha256 only is pushed), pb_000 = ACE's initial
playbook, next_global_id, and M_cap; then the checkpoint whose `next` is ace/step/001/episode.

  venv-aw/bin/python -I p3_start.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "scripts"))
sys.path.insert(0, str(EX / "adapters"))
sys.path.insert(0, str(EX))
import awpaths as P  # noqa: E402
import adapter  # noqa: E402
import lints  # noqa: E402
import status_doc  # noqa: E402
from ace.vendor.playbook import get_next_global_id  # noqa: E402


def main() -> int:
    ids = adapter.tasks("train")
    order_sha = P.sha256_bytes(json.dumps(ids).encode())
    P.write_json(P.AW_STATE / "ace" / "train_order.json", ids)
    pb0 = (EX / "ace" / "vendor" / "playbooks" / "appworld_initial_playbook.txt").read_text()
    m_cap = int(P.manifest()["m_cap"]["value"])
    ml = lints.memory_lint(pb0, m_cap)
    if not ml["ok"]:
        raise SystemExit(f"pb_000 fails the memory lint: {ml}")
    P.atomic_write(P.AW_STATE / "ace" / "playbooks" / "pb_000.txt", pb0)
    nid = get_next_global_id(pb0)
    P.update_manifest(train_order={"source": "load_task_ids('train')", "n": len(ids), "sha256": order_sha})
    prog = {"last_applied_step": 0, "next_global_id": nid, "rows": [], "spend": {}, "rollouts": 0,
            "soft_cap_reached": False, "hard_stop": False, "m_cap": m_cap}
    P.write_json(P.PUSHED / "ace" / "progress.json", prog)
    P.atomic_write(P.PUSHED / "ace" / "playbook.txt", pb0)
    status_doc.append(
        "phase_done", "P3", "ACE start",
        f"P3 done: train order = `load_task_ids(\"train\")` ({len(ids)} tasks, no shuffle), sha256 {order_sha[:16]}… "
        f"(ids not pushed); pb_000 = ACE's initial playbook ({ml['bullets']} bullets, {ml['chars']:,} chars, "
        f"{ml['tokens']} tokens; lint passed), next_global_id {nid}; M_cap = {m_cap:,} tokens (A8).\n"
        f"Next: P4 ace/step/001/episode.",
        done_through="P3/start", next_unit="ace/step/001/episode",
        extra={"counts": {"rollouts_counted": 0, "ace_steps": 0}},
        artifacts=["STATE/manifest.json", "STATE/ace/playbook.txt", "STATE/ace/progress.json",
                   "local/ace/playbooks/pb_000.txt"], subject="P3 ACE start")
    return 0


if __name__ == "__main__":
    sys.exit(main())
