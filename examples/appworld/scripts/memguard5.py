"""Memory guard with simple watermarks (user instruction 2026-10-19; CONTAINER_AGENT.md §2).

  python3 -I memguard5.py loop [--high 90] [--low 80] [--every 15]

Every `every` s: used = anon + shmem of this container's cgroup (what the kernel cannot reclaim; the page
cache is not counted), as a share of memory.max (or memory.high if lower). At or above the HIGH watermark
(90%) it creates the PAUSE file of every window (AW_STATE/<window>/PAUSE): in-flight episodes finish, no
new one starts. Once used falls below the LOW watermark (80%) it removes the PAUSE files it created. Each
transition goes to AW_STATE/progress/memguard.log. It never touches a PAUSE file it did not create.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aw5 as P  # noqa: E402

CG = Path("/sys/fs/cgroup")
WINDOWS = ("p6dev", "p8final")


def used_pct() -> float:
    lim = (CG / "memory.max").read_text().strip()
    high = (CG / "memory.high").read_text().strip() if (CG / "memory.high").exists() else "max"
    if high != "max" and (lim == "max" or int(high) < int(lim)):
        lim = high
    if lim == "max":
        return 0.0
    used = 0
    for line in (CG / "memory.stat").read_text().splitlines():
        k, v = line.split()
        if k in ("anon", "shmem"):
            used += int(v)
    return 100.0 * used / int(lim)


def main() -> int:
    a = sys.argv
    high = float(a[a.index("--high") + 1]) if "--high" in a else 90.0
    low = float(a[a.index("--low") + 1]) if "--low" in a else 80.0
    every = float(a[a.index("--every") + 1]) if "--every" in a else 15.0
    (P.AW_STATE / "MEMGUARD.pid").write_text(str(os.getpid()))
    mine: set[Path] = set()
    P.progress_log("memguard", "-", f"start: high {high}%, low {low}%, every {every}s, now {used_pct():.1f}%")
    while True:
        u = used_pct()
        if u >= high and not mine:
            for w in WINDOWS:
                pf = P.AW_STATE / w / "PAUSE"
                if (P.AW_STATE / w).exists() and not pf.exists():
                    pf.write_text(f"memguard {P.utcnow()} used {u:.1f}%\n")
                    mine.add(pf)
            P.progress_log("memguard", "-", f"HIGH {u:.1f}% >= {high}%: paused new episodes ({len(mine)} window(s))")
        elif u < low and mine:
            for pf in mine:
                pf.unlink(missing_ok=True)
            P.progress_log("memguard", "-", f"LOW {u:.1f}% < {low}%: resumed")
            mine.clear()
        time.sleep(every)


if __name__ == "__main__":
    raise SystemExit(main())
