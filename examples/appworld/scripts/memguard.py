"""Memory guard, rule R2 of docs/EVAL_APPWORLD_REST.md §4.2 (adapted from eval 5's memguard5.py).

  python3 -I memguard.py loop [--high 90] [--low 85] [--every 5]
  python3 -I memguard.py once

Every `every` s (5 s; never more than 10 s): used = anon + shmem of this container's cgroup (what the
kernel cannot reclaim; the page cache is not counted) over memory.max, or memory.high if lower. It writes
AW_STATE/MEMSTATE.json = {t, used_pct, used_MB, limit_MB, state, peak_pct} atomically on every sample.
At used_pct >= HIGH (90) it sets state PAUSED and creates AW_STATE/PAUSE; it clears both only when
used_pct < LOW (85). Everything that starts work (the evaluator's slot pool, the windows, opt_llm.py, the
claude-code wrappers, the executing agent's spawn check) waits while PAUSE exists. One line per transition
and one sample line per minute go to AW_STATE/progress/memguard.log.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import awrest as P  # noqa: E402

CG = Path("/sys/fs/cgroup")


def sample() -> dict:
    lim = (CG / "memory.max").read_text().strip()
    high = (CG / "memory.high").read_text().strip() if (CG / "memory.high").exists() else "max"
    if high != "max" and (lim == "max" or int(high) < int(lim)):
        lim = high
    used = 0
    for line in (CG / "memory.stat").read_text().splitlines():
        k, v = line.split()
        if k in ("anon", "shmem"):
            used += int(v)
    if lim == "max":
        avail = int(next(x for x in Path("/proc/meminfo").read_text().splitlines()
                         if x.startswith("MemAvailable")).split()[1]) * 1024
        lim_b = used + avail // 2
    else:
        lim_b = int(lim)
    return {"used_pct": round(100.0 * used / lim_b, 2), "used_MB": used // 1048576, "limit_MB": lim_b // 1048576}


def main() -> int:
    a = sys.argv
    high = float(a[a.index("--high") + 1]) if "--high" in a else 90.0
    low = float(a[a.index("--low") + 1]) if "--low" in a else 85.0
    every = min(10.0, float(a[a.index("--every") + 1]) if "--every" in a else 5.0)
    if a[1] == "once":
        print(sample())
        return 0
    P.AW_STATE.mkdir(parents=True, exist_ok=True)
    (P.AW_STATE / "MEMGUARD.pid").write_text(str(os.getpid()))
    state = "PAUSED" if P.PAUSE_FILE.exists() else "OK"
    peak, last_line = 0.0, 0.0
    s = sample()
    P.progress_log("memguard", "-", f"start pid {os.getpid()}: high {high}%, low {low}%, every {every}s, "
                                    f"now {s['used_pct']}% of {s['limit_MB']} MB, state {state}")
    while True:
        s = sample()
        u = s["used_pct"]
        peak = max(peak, u)
        if u >= high and state != "PAUSED":
            state = "PAUSED"
            P.atomic_write(P.PAUSE_FILE, f"memguard {P.utcnow()} used {u}%\n")
            P.progress_log("memguard", "-", f"PAUSED: {u}% >= {high}% ({s['used_MB']} MB)")
        elif u < low and state == "PAUSED":
            state = "OK"
            P.PAUSE_FILE.unlink(missing_ok=True)
            P.progress_log("memguard", "-", f"RESUMED: {u}% < {low}%")
        P.write_json(P.MEMSTATE, {"t": P.utcnow(), **s, "state": state, "peak_pct": round(peak, 2),
                                  "high": high, "low": low, "every_s": every, "pid": os.getpid()})
        if time.time() - last_line >= 60:
            P.progress_log("memguard", "-", f"sample {u}% ({s['used_MB']} MB) state {state} peak {peak:.1f}%")
            last_line = time.time()
        time.sleep(every)


if __name__ == "__main__":
    raise SystemExit(main())
