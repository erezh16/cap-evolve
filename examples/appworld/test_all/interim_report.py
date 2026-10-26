"""Interim per-arm report (user decision, TA ledger 2026-10-26): status, interim test score, per-arm ETA.

  . examples/appworld/test_all/env.sh && python3 -I examples/appworld/test_all/interim_report.py OUT.md

A trusted script (rule R1): it reads the window's order and cell records and writes aggregates only (per arm: cells
done of 840, successes over finished episodes, interim TGC over the tasks with at least one finished trial, infra
counts, its ETA from its own rate over the last 3 hours). No task id, task text or per-task outcome is written.
The output is NOT committed, pushed or posted (it overrides plan sections 4.1 / 12.2 for one look only).
"""

from __future__ import annotations

import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "scripts"))
import awrest as P  # noqa: E402

FINAL = P.AW_STATE / "final"
PER_ARM = P.FINAL_CELLS // len(P.ARMS)
WINDOW_H = 3


def wilson(k: int, n: int) -> tuple[float, float]:
    if not n:
        return (float("nan"), float("nan"))
    z, p = 1.96, k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def main(out: Path) -> int:
    order = {c["idx"]: c for c in P.read_json(FINAL / "order.json")}
    now = time.time()
    per = defaultdict(lambda: {"done": 0, "ok": 0, "succ": 0, "infra": 0, "retries": 0, "recent": 0,
                               "tasks": defaultdict(list)})
    for p in (FINAL / "records").glob("*.json"):
        r = json.loads(p.read_text())
        c = order[int(p.stem)]
        a = per[c["arm"]]
        a["done"] += 1
        a["retries"] += int(r.get("attempt") or 0)
        a["recent"] += int(p.stat().st_mtime > now - WINDOW_H * 3600)
        if r.get("infra_error"):
            a["infra"] += 1
            a["tasks"][c["task_id"]].append(0.0)
            continue
        a["ok"] += 1
        s = 1.0 if r.get("success") else 0.0
        a["succ"] += int(s)
        a["tasks"][c["task_id"]].append(s)
    prog = P.read_json(P.PUSHED / "final" / "progress.json", {}) or {}
    alive = False
    try:
        import os
        os.kill(int((P.AW_STATE / "RUNNING.pid").read_text().split()[0]), 0)
        alive = True
    except Exception:  # noqa: BLE001
        pass
    total_done = sum(v["done"] for v in per.values())
    total_recent = sum(v["recent"] for v in per.values())
    rows = []
    for arm in P.ARMS:
        a = per[arm]
        left = PER_ARM - a["done"]
        rate = a["recent"] / WINDOW_H
        eta_h = left / rate if rate else None
        tgc = sum(sum(v) / len(v) for v in a["tasks"].values()) / len(a["tasks"]) if a["tasks"] else None
        lo, hi = wilson(a["succ"], a["ok"])
        status = ("complete" if left <= 0 else f"running ({a['done']}/{PER_ARM} cells, {100 * a['done'] / PER_ARM:.0f}%)"
                  if alive else f"stopped ({a['done']}/{PER_ARM} cells)")
        eta = ("done" if left <= 0 else
               time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(now + eta_h * 3600)) + f" (≈{eta_h:.1f} h, {left} cells left at {rate:.1f}/h)"
               if eta_h else "n/a")
        rows.append((arm, status, a, tgc, lo, hi, eta, eta_h))
    rank = sorted((r for r in rows if r[3] is not None), key=lambda r: -r[3])
    L = ["# AppWorld TEST_ALL: interim report (not final)", "",
         f"Generated {P.utcnow()} by `examples/appworld/test_all/interim_report.py` (a trusted script; aggregates only). "
         "**Local file: not committed, pushed or posted.** An interim look requested by the user (ledger decision, "
         "2026-10-26), overriding plan §4.1 / §12.2 once; it changes nothing in the window.", "",
         f"**Window:** {total_done:,} / {P.FINAL_CELLS:,} cells ({100 * total_done / P.FINAL_CELLS:.1f}%); runner "
         f"{'alive' if alive else 'NOT running'}; {total_recent / WINDOW_H:.0f} cells/h over the last {WINDOW_H} h; "
         f"18 global slots. Whole-window ETA: "
         + (time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(now + (P.FINAL_CELLS - total_done) / (total_recent / WINDOW_H) * 3600))
            if total_recent else "n/a") + ". Analysis and results posts follow in about 1 h.", "",
         "| # | competitor | arm | status | interim score: TGC (tasks with ≥1 finished trial) | success rate over finished episodes [95% Wilson CI] | infra (missing / retries) | ETA for this competitor |",
         "|---|---|---|---|---|---|---|---|"]
    for i, (arm, status, a, tgc, lo, hi, eta, _) in enumerate(sorted(rows, key=lambda r: -(r[3] or -1)), 1):
        L.append(f"| {i} | {P.METHOD_NAMES[arm]} | `{arm}` | {status} | "
                 + (f"**{100 * tgc:.1f}%** over {len(a['tasks'])} tasks" if tgc is not None else "n/a")
                 + f" | {100 * a['succ'] / max(1, a['ok']):.1f}% ({a['succ']}/{a['ok']}) [{100 * lo:.1f}, {100 * hi:.1f}] | "
                   f"{a['infra']} / {a['retries']} | {eta} |")
    top = rank[0]
    L += ["", f"**Best interim score so far:** {P.METHOD_NAMES[top[0]]} (`{top[0]}`), TGC {100 * top[3]:.1f}%.", "",
          f"**Noise check:** `harnesslens` is byte-identical to `seed`; their interim gap is "
          f"{100 * ((dict((r[0], r[3]) for r in rows)['harnesslens'] or 0) - (dict((r[0], r[3]) for r in rows)['seed'] or 0)):+.1f} "
          "TGC points, a direct read of this window's noise at this point.", "",
          "**How to read this (caveats):**",
          f"- Interim, {100 * total_done / P.FINAL_CELLS:.1f}% of cells. The order is shuffled, so each arm's finished cells are a near-random sample "
          "of its 840, but the remaining cells are on average the slower episodes (long or hard tasks finish late), so "
          "interim scores are likely biased upward, and possibly more for some arms than others.",
          "- The interim TGC averages over the tasks that have at least one finished trial, with whatever trials are "
          "finished; the final TGC averages all 5 trials of all 168 tasks. The Wilson CI is per episode and ignores "
          "task and scenario clustering, so it is too narrow; the final analysis uses a scenario-clustered paired "
          "bootstrap, 78 pairs with Holm.",
          "- Artifact-level only: one search seed per method; methods differ in surfaces and budget (plan §3, §12.3).",
          "- Per-competitor ETA = its remaining cells / its own rate over the last 3 h; with 30-60 cells left per arm "
          "each estimate is rough (about ±1 h). The arms are interleaved in one order, so they finish within a few "
          "hours of each other; the last arm sets the window's end, and no arm's score is final until then.",
          "- Incidents so far: queue drain at the first memory pause (2026-10-25 10:05, about 15 min lost, TA-0349); "
          "pod OOM restart (2026-10-26 03:09, about 3 h lost, TA-0835); slots 24 → 18 (TA-0847)."]
    out.write_text("\n".join(L) + "\n")
    print(f"wrote {out} ({len(L)} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1])))
