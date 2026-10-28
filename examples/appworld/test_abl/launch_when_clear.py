#!/usr/bin/env python3
"""TEST_ABL §8.1: wait until the machine is clear of the gate run, then T3 and window 1 (or window 2). nohup.

  . examples/appworld/test_abl/env.sh && nohup python3 -I examples/appworld/test_abl/launch_when_clear.py [--window 2] &

"Clear" (plan §8.1, addendum A5): no gate search process alive (its pid files, never pgrep -f); the ablation ledger
has the gate searches' P4 `phase_done`; no gate-run window or P5-P9 process alive (AW_STATE/RUNNING.pid and
AFTER_P4.pid of the ablation run); and either the gate run's own P7 has completed (a P7 `phase_done` after the gate
P4 entry), or 30 minutes have passed since the gate P4 entry with no gate P5/P6/P7 entry (then window 1 goes first
and the gate run's P7 waits for it; addendum A5). root_full must be mode 000 and both memory guards OK. Then: T3 (the
order check, which unlocks root_full only for its read), a ledger entry, and window.py final under nohup with this
run's 24 slots. Every wait is logged to AW_STATE/progress/launch.log; a ledger heartbeat-style note every 30 minutes.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EX = HERE.parent
sys.path.insert(0, str(EX / "scripts"))
import awrest as P  # noqa: E402
import status_doc as S  # noqa: E402

ABL = Path("/workspace/aw_abl/state")
GATE = ("abl_nogate", "abl_naivegate")
GRACE_S = 1800
LOG = P.PROGRESS / "launch.log"


def log(msg: str) -> None:
    P.PROGRESS.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(f"{P.utcnow()} {msg}\n")


def pid_of(p: Path) -> int | None:
    try:
        return int(p.read_text().split()[0])
    except (FileNotFoundError, ValueError, IndexError):
        return None


def abl_ledger() -> list[tuple[int, str, str, str]]:
    """(id, utc, phase+label, kind) of every ablation ledger entry, from fork/eval-abl (headings only)."""
    subprocess.run(["git", "-C", str(P.REPO), "fetch", "-q", "fork", "eval-abl"], capture_output=True)
    txt = subprocess.run(["git", "-C", str(P.REPO), "show", "fork/eval-abl:docs/ABLATION_STATUS.md"],
                         capture_output=True, text=True).stdout
    out = []
    for m in re.finditer(r"(?m)^## ABL-(\d{4}) · (\S+) · (.+?) · (\w+)$", txt):
        out.append((int(m.group(1)), m.group(2), m.group(3), m.group(4)))
    return out


def ts(utc: str) -> float:
    return time.mktime(time.strptime(utc, "%Y-%m-%dT%H:%MZ")) - time.timezone


def state() -> dict:
    gate_alive = [a for a in GATE if S.pid_alive(pid_of(ABL / "p4" / f"{a}.pid"))]
    runner = S.pid_alive(pid_of(ABL / "p4" / "RUNNER.pid"))
    window = S.pid_alive(pid_of(ABL / "RUNNING.pid"))
    after = S.pid_alive(pid_of(ABL / "AFTER_P4.pid"))
    led = abl_ledger()
    p4 = [e for e in led if e[3] == "phase_done" and "gate searches done" in e[2]]
    later = [e for e in led if p4 and e[0] > p4[-1][0]]
    p567 = [e for e in later if re.match(r"P[567] ", e[2]) and e[3] in ("phase_start", "result", "phase_done")]
    p7done = [e for e in later if e[2].startswith("P7") and e[3] == "phase_done"]
    aborted = [e for e in later if e[3] == "abort"]
    return {"gate_alive": gate_alive, "runner": runner, "abl_window": window, "after_p4": after,
            "p4_done_utc": p4[-1][1] if p4 else None, "gate_p567_entries": len(p567), "gate_p7_done": bool(p7done),
            "gate_abort": bool(aborted), "root_full_mode": oct(os.stat(P.ROOT_FULL).st_mode & 0o777),
            "mem_ok": P.memstate().get("state") == "OK" and not P.memstate().get("stale")
            and (P.read_json(ABL / "MEMSTATE.json", {}) or {}).get("state") == "OK"}


def clear(st: dict) -> tuple[bool, str]:
    if st["gate_alive"] or st["runner"]:
        return False, f"gate searches running ({', '.join(st['gate_alive']) or 'runner'})"
    if not st["p4_done_utc"]:
        return False, "gate P4 phase_done not in the ablation ledger yet"
    if st["abl_window"] or st["after_p4"]:
        return False, "a gate-run window or P5-P9 chain is alive"
    if st["root_full_mode"] != "0o0":
        return False, f"root_full mode {st['root_full_mode']} (another window may be running)"
    if not st["mem_ok"]:
        return False, "a memory guard is not OK"
    if st["gate_p7_done"]:
        return True, "the gate run's P7 window has completed"
    if st["gate_p567_entries"]:
        return False, "the gate run's P5-P7 are in progress"
    age = time.time() - ts(st["p4_done_utc"])
    if age >= GRACE_S:
        return True, (f"no gate P5-P7 started within {GRACE_S // 60} min of the gate P4 phase_done "
                      f"({st['p4_done_utc']}); window 1 goes first (addendum A5)")
    return False, f"grace: {int((GRACE_S - age) // 60)} min left for a gate P5-P7 to start"


def main() -> int:
    win = sys.argv[sys.argv.index("--window") + 1] if "--window" in sys.argv else "1"
    (P.AW_STATE / "LAUNCHER.pid").write_text(f"{os.getpid()} window{win}\n")
    last_note, last_why = 0.0, None
    while True:
        st = state()
        ok, why = clear(st)
        if why != last_why:
            log(f"window {win}: {'CLEAR' if ok else 'wait'}: {why} | {json.dumps(st)}")
            last_why = why
        if st["gate_abort"]:
            log("the gate run recorded an abort; window 1 does not depend on it, continuing")
        if ok:
            break
        if time.time() - last_note > 1800:
            prev = S.last_entry()
            S.append("result", "W", f"waiting for the gate run (window {win})",
                     f"Window {win} waits for the gate run (plan §8.1): {why}.", next_unit=f"P3/window{win}",
                     subject=f"wait window {win}")
            last_note = time.time()
        time.sleep(60)
    env = dict(os.environ, AW_WINDOW=win)
    r = subprocess.run([str(P.VENV_PY), "-I", str(HERE.parent / "test_all" / "check_t3.py")], env=env,
                       capture_output=True, text=True, cwd=str(P.REPO))
    t3 = json.loads((r.stdout.strip().splitlines() or ["{}"])[-1])
    S.append("result" if t3.get("ok") else "error", "P2", f"T3 order (window {win})",
             f"T3 (window {win} order): seed {t3.get('seed')}, cells {t3.get('cells')}, per arm {t3.get('per_arm')}, "
             f"sha256 {str(t3.get('sha256'))[:16]}…, reproducible {t3.get('reproducible')}, each cell once "
             f"{t3.get('each_cell_once')}, root_full relocked {t3.get('root_full_relocked')}: "
             f"{'PASS' if t3.get('ok') else 'FAIL'}.", extra={"t3": {k: v for k, v in t3.items()}},
             subject=f"T3 window {win}")
    if not t3.get("ok"):
        log(f"T3 failed: {t3}")
        return 1
    st = state()
    ok, why = clear(st)
    if not ok:                                   # re-check right before the launch: never overlap the gate run
        log(f"not clear any more after T3 ({why}); restarting the wait")
        return main()
    S.append("phase_start", "P3" if win == "1" else "P6", f"window {win} start",
             f"Window {win} starts: {why}. {P.FINAL_CELLS if win == '1' else 168 * 2 * 5:,} cells, "
             f"{P.global_slots()} global slots in this run's own pool, trial seeds {P.FINAL_SEED_BASE} + k; "
             "root_full is unlocked by window.py for the window and relocked at its end.",
             next_unit=f"P3/window{win}" if win == "1" else "P6/window2", subject=f"window {win} start")
    out = open(P.PROGRESS / f"window{win}.out", "a")
    p = subprocess.Popen(["nohup", str(P.VENV_PY), "-I", str(EX / "scripts" / "window.py"), "final"],
                         stdout=out, stderr=subprocess.STDOUT, start_new_session=True, cwd=str(P.REPO),
                         env=P.setup_env(env))
    log(f"window {win} launched pid {p.pid}")
    # addendum A7: if another process relocks root_full while this window runs (a gate-run window ending), this
    # watcher never unlocks it. It stops this window (SIGTERM: no new cell) and records an error; the window is
    # resumed later through the same wait, which skips every cell that has a record.
    while p.poll() is None:
        time.sleep(30)
        if p.poll() is None and (os.stat(P.ROOT_FULL).st_mode & 0o777) == 0:
            p.terminate()
            log(f"window {win}: root_full relocked from outside while the window runs; window stopped (SIGTERM)")
            S.append("error", "P3" if win == "1" else "P6", "root_full relocked from outside",
                     f"root_full was set to 000 by another process while window {win} was running (addendum A7). "
                     "The window was stopped (no new cell); it resumes through the launch wait once the machine is "
                     "clear again. Cells that failed on it are counted as infra failures.", subject="root_full relock")
            p.wait()
            return main()
    log(f"window {win} runner exited rc {p.returncode}; root_full mode {oct(os.stat(P.ROOT_FULL).st_mode & 0o777)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
