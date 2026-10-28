#!/usr/bin/env python3
"""TEST_ABL §8, §11, §12.3: the rest of the run as one nohup chain, resumable (AW_STATE/chain.json).

  . examples/appworld/test_abl/env.sh && nohup python3 -I examples/appworld/test_abl/chain.py &

Steps, each recorded once: (1) wait for window 1's launcher (launch_when_clear.py --window 1) and its runner to finish
with all cells recorded; (2) analysis of window 1 and its RESULTS drafts; (3) results comments on window 1's issues
plus a pointer on each arm's search issue; (4) once the gate arms have joined (gate_join.py), launch_when_clear.py
--window 2, then the same analysis and posts for window 2. Never two windows at once. A failure is an `error` entry
and the chain stops; resume by starting it again (finished steps are skipped).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EX = HERE.parent
sys.path.insert(0, str(EX / "scripts"))
import awrest as P  # noqa: E402
import status_doc as S  # noqa: E402

ST = P.AW_STATE / "chain.json"
LOG = P.PROGRESS / "chain.log"


def log(msg: str) -> None:
    with open(LOG, "a") as f:
        f.write(f"{P.utcnow()} {msg}\n")


def done() -> set:
    return set((P.read_json(ST, {}) or {}).get("done", []))


def mark(step: str) -> None:
    d = done() | {step}
    P.write_json(ST, {"done": sorted(d)})
    log(f"done {step}")


def pid_alive(name: str) -> bool:
    try:
        return S.pid_alive(int((P.AW_STATE / name).read_text().split()[0]))
    except (FileNotFoundError, ValueError, IndexError):
        return False


def n_records(d: str) -> int:
    rec = P.AW_STATE / d / "records"
    return len(list(rec.glob("*.json"))) if rec.exists() else 0


def run(cmd: list[str], env: dict, step: str) -> int:
    with open(P.PROGRESS / f"chain_{step}.out", "a") as f:
        f.write(f"== {P.utcnow()} {' '.join(cmd)}\n")
        f.flush()
        return subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, env=env, cwd=str(P.REPO)).returncode


def fail(step: str, rc: int) -> int:
    S.append("error", "P4", f"chain step {step} failed", f"Chain step `{step}` exited {rc}; the chain stopped. See "
             f"AW_STATE/progress/chain_{step}.out. It is resumed by starting chain.py again.", subject=f"chain {step}")
    return rc or 1


def window(win: str, cells: int) -> int:
    d = "final" if win == "1" else "final2"
    env = dict(os.environ, AW_WINDOW=win)
    if f"w{win}_window" not in done():
        while True:                                  # a launcher (ours) waits for the machine, then runs the window
            if not pid_alive("LAUNCHER.pid") and not pid_alive("RUNNING.pid"):
                if n_records(d) >= cells:
                    break
                log(f"window {win}: no launcher and {n_records(d)}/{cells} records: starting launch_when_clear")
                subprocess.Popen(["nohup", sys.executable, "-I", str(HERE / "launch_when_clear.py"), "--window", win],
                                 stdout=open(P.PROGRESS / "launcher.out", "a"), stderr=subprocess.STDOUT,
                                 start_new_session=True, cwd=str(P.REPO), env=env)
                time.sleep(30)
            time.sleep(60)
        mark(f"w{win}_window")
    if f"w{win}_analysis" not in done():
        rc = run([str(P.VENV_PY), "-I", str(EX / "test_all" / "analyze_all.py")], dict(env, AW_RELOCK="1"),
                 f"w{win}_analysis")
        if rc:
            return fail(f"w{win}_analysis", rc)
        rc = run([sys.executable, "-I", str(EX / "test_all" / "report_all.py")], env, f"w{win}_report")
        if rc:
            return fail(f"w{win}_report", rc)
        S.append("phase_done", "P4" if win == "1" else "P7", f"analysis window {win}",
                 f"Analysis of window {win} done: docs/TEST_ABL_STATE/{d}/analysis.json and RESULTS.md, and one "
                 "RESULTS.md draft per arm (aggregates only).", artifacts=[f"STATE/{d}/analysis.json"],
                 next_unit=f"P5/results window {win}", subject=f"analysis window {win}")
        mark(f"w{win}_analysis")
    if f"w{win}_posts" not in done():
        rc = run([sys.executable, "-I", str(EX / "test_all" / "report_all.py"), "--post"], env, f"w{win}_posts")
        if rc:
            return fail(f"w{win}_posts", rc)
        import post
        arms = [a for a in P.WINDOW_ARMS if a in P.SEARCH_ISSUES] if win == "1" else list(P.GATE_ARMS)
        issues = (P.read_json(P.PUSHED / "manifest.json", {}) or {}).get("issues", {})
        for a in arms:
            body = (f"Pointer: this arm's champion was scored **test-only** in AppWorld TEST_ABL (`test_normal` × 5 "
                    f"trials, gpt-oss-120b). Results: skillberry-ai/cap-evolve#{issues.get(a)}.")
            try:
                post._comment_raw(P.SEARCH_ISSUES[a], body) if hasattr(post, "_comment_raw") else subprocess.run(
                    ["gh", "issue", "comment", str(P.SEARCH_ISSUES[a]), "-R", P.ISSUE_REPO, "--body", body],
                    capture_output=True, text=True, check=True)
            except Exception as e:  # noqa: BLE001 — a courtesy pointer never stops the chain
                log(f"pointer on #{P.SEARCH_ISSUES[a]} failed: {e}"[:300])
            time.sleep(3)
        S.append("phase_done", "P5" if win == "1" else "P7", f"results posted window {win}",
                 f"Results comments posted on the issues of window {win}'s arms, and a pointer on each arm's search "
                 "issue.", next_unit="window 2" if win == "1" else "done", subject=f"results window {win}")
        mark(f"w{win}_posts")
    return 0


def main() -> int:
    (P.AW_STATE / "CHAIN.pid").write_text(f"{os.getpid()}\n")
    rc = window("1", 168 * 7 * 5)
    if rc:
        return rc
    while "w2_ready" not in done():                  # gate_join.py writes window2_arms once both gate arms are ready
        if (P.read_json(P.PUSHED / "manifest.json", {}) or {}).get("window2_arms"):
            mark("w2_ready")
            break
        if not pid_alive("GATE_JOIN.pid"):
            subprocess.Popen(["nohup", sys.executable, "-I", str(HERE / "gate_join.py")],
                             stdout=open(P.PROGRESS / "gate_join.out", "a"), stderr=subprocess.STDOUT,
                             start_new_session=True, cwd=str(P.REPO), env=dict(os.environ))
        time.sleep(120)
    # a fresh interpreter, so the profile sees window2_arms from the manifest
    return subprocess.run([sys.executable, "-I", str(HERE / "chain_w2.py")], env=dict(os.environ, AW_WINDOW="2"),
                          cwd=str(P.REPO)).returncode


if __name__ == "__main__":
    raise SystemExit(main())
