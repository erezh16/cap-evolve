"""The detached phase runner (plan §10): runs P4 → P9 from the ledger's `next` unit, one phase at a time.

  nohup venv-aw/bin/python -I pipeline.py > AW_STATE/progress/pipeline.out 2>&1 &
It owns AW_STATE/RUNNING.pid (the resume lock); each phase runs as a child process; SIGTERM is
forwarded to the child (which finishes its current unit) and the pipeline exits. A failing phase
writes an `error` entry and stops the pipeline. P10 (the report) is not automatic.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "scripts"))
import awpaths as P  # noqa: E402
import status_doc  # noqa: E402

PY = str(P.VENV_PY)
child: subprocess.Popen | None = None
stopping = False


def _term(*_):
    global stopping
    stopping = True
    if child and child.poll() is None:
        child.send_signal(signal.SIGTERM)


def phase_of(nxt: str) -> str | None:
    if nxt.startswith("ace/step/") or nxt == "P4/start":
        return "P4"
    return {"P5/freeze": "P5", "P6/dev": "P6", "p6dev/cells": "P6", "P7/scan": "P7", "P8/final": "P8",
            "p8final/cells": "P8", "P9/analysis": "P9"}.get(nxt)


CMDS = {
    "P4": [PY, "-I", str(EX / "ace" / "run_ace.py"), "--post-every", "15"],
    "P5": [PY, "-I", str(EX / "scripts" / "freeze.py")],
    "P6": [PY, "-I", str(EX / "scripts" / "dev_diag.py")],
    "P7": [PY, "-I", str(EX / "scripts" / "scan_isolation.py"), "--checkpoint"],
    "P8": [PY, "-I", str(EX / "scripts" / "final_window.py")],
    "P9": [PY, "-I", str(EX / "scripts" / "analyze.py"), "--checkpoint"],
}
STARTS = {"ace/step/001/episode": ("P4", "ACE adaptation", "90 sequential steps (episode, Reflector, Curator, apply)"),
          "P6/dev": ("P6", "dev diagnostic", "114 cells (57 dev × seed, ace × 1 trial), 24 workers"),
          "P8/final": ("P8", "final window", "672 cells (168 test_normal × seed, ace × 2 trials), 48 workers")}


def main() -> int:
    global child
    signal.signal(signal.SIGTERM, _term)
    (P.AW_STATE / "RUNNING.pid").write_text(f"{os.getpid()} pipeline\n")
    env = {**os.environ, "AW_UNDER_PIPELINE": "1", "HF_HOME": str(P.HF_HOME), "HF_HUB_OFFLINE": "1"}
    try:
        while not stopping:
            nxt = status_doc.last_entry().get("next") or ""
            ph = phase_of(nxt)
            if ph is None:
                P.progress_log("pipeline", "-", f"nothing to run for next={nxt}; exiting")
                return 0
            if nxt in STARTS:
                p, label, what = STARTS[nxt]
                status_doc.append("phase_start", p, label, f"Phase start: {what}. Runner pid {os.getpid()}.",
                                  subject=f"{p} start")
            P.progress_log("pipeline", ph, f"running {ph} (next={nxt})")
            log = open(P.PROGRESS / f"{ph.lower()}.out", "a")
            child = subprocess.Popen(CMDS[ph], env=env, stdout=log, stderr=subprocess.STDOUT, cwd=str(P.AW_STATE))
            rc = child.wait()
            log.close()
            if stopping:
                P.progress_log("pipeline", ph, "stopped by SIGTERM")
                return 0
            if rc != 0:
                tail = (P.PROGRESS / f"{ph.lower()}.out").read_text()[-800:]
                prose = f"Phase {ph} runner exited with code {rc}. The pipeline stopped; see the local log " \
                        f"`progress/{ph.lower()}.out`. Resume with `resume.py` after the cause is fixed."
                try:
                    status_doc.append("error", ph, "runner error", prose + f"\nLog tail:\n```\n{tail}\n```",
                                      extra={"rc": rc}, subject=f"{ph} error")
                except status_doc.Refused:
                    status_doc.append("error", ph, "runner error", prose + " (log tail withheld by the content filter)",
                                      extra={"rc": rc}, subject=f"{ph} error")
                return rc
            if status_doc.last_entry().get("next") == nxt:
                P.progress_log("pipeline", ph, f"{ph} exited without progress (next still {nxt}); stopping")
                return 1
        return 0
    finally:
        pf = P.AW_STATE / "RUNNING.pid"
        if pf.exists() and pf.read_text().split()[0] == str(os.getpid()):
            pf.unlink()


if __name__ == "__main__":
    sys.exit(main())
