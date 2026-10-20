"""Hourly status and milestone posts on the five tracking issues (docs/EVAL_APPWORLD_REST.md §8).

  python3 -I autopost.py loop [--every 3600]     # nohup loop, relaunched by resume.py
  python3 -I autopost.py once [--force]

Every 60 s it checks the ledger. Milestones (§8) are posted by the code that reaches them, through
post.post(). This loop guarantees the hourly floor: when the last post on a candidate's issue is older than
`every` seconds (default 3600; the plan requires at least one post per hour per issue), it posts that
candidate's status. Each status says: the stage, counted rollouts of B, optimizer tokens and proxy USD,
the best search-time score so far (labelled), memory state, the last ledger checkpoint and the ETA. Bodies
are built only from pushed state and local counters (counts and aggregates), pass the content filter in
post.post, and are keyed so nothing is posted twice. No test-set score of any arm is posted before P8.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import awrest as P  # noqa: E402
import post  # noqa: E402
import status_doc as S  # noqa: E402

STATE = P.AW_STATE / "autopost.json"
PHASE_NAMES = {"P0": "decisions", "P1": "build", "P2": "acceptance checks", "P3": "shared seed baseline",
               "P4": "candidate searches", "P5": "dev diagnostic", "P6": "isolation scan",
               "P7": "final window", "P8": "analysis", "P9": "results posts"}


def _usage(c: str) -> dict:
    rows = P.read_jsonl(P.AW_STATE / c / "optimizer_usage.jsonl")
    t = {"calls": len(rows), "in": 0, "out": 0, "cache_read": 0, "cache_write": 0}
    for r in rows:
        t["in"] += int(r.get("prompt_tokens") or 0)
        t["out"] += int(r.get("completion_tokens") or 0)
        t["cache_read"] += int(r.get("cache_read") or 0)
        t["cache_write"] += int(r.get("cache_write") or 0)
    t["usd"] = round((t["in"] * P.PRICE_IN + t["out"] * P.PRICE_OUT + t["cache_read"] * P.PRICE_CACHE_READ
                      + t["cache_write"] * P.PRICE_CACHE_WRITE) / 1e6, 2)
    return t


def stage(c: str, last: dict) -> str:
    pr = P.read_json(P.PUSHED / c / "progress.json", {}) or {}
    if pr.get("stage"):
        return pr["stage"]
    ph = last.get("phase", "P0")
    if ph in ("P0", "P1", "P2"):
        return f"queued; common phase {ph} ({PHASE_NAMES.get(ph, '')}) in progress"
    if ph == "P3":
        return "waiting for the shared seed baseline (P3)"
    return f"common phase {ph} ({PHASE_NAMES.get(ph, '')})"


def status_body(c: str) -> str:
    last = S.last_entry()
    pr = P.read_json(P.PUSHED / c / "progress.json", {}) or {}
    u = _usage(c)
    mem = P.memstate()
    counted = len(P.read_jsonl(P.AW_STATE / c / "rollouts.jsonl"))
    best = pr.get("best_search_score")
    lines = [f"**Hourly status — {P.METHOD_NAMES[c]}** ({P.utcnow()}).", "",
             f"- stage: {stage(c, last)}",
             f"- counted search rollouts: {counted} of B = {P.BUDGET_ROLLOUTS}"
             + (f" (cache hits {pr['cache_hits']})" if pr.get("cache_hits") is not None else ""),
             f"- optimizer ({P.OPT_MODEL}): {u['calls']} calls, {u['in'] / 1e6:.2f}M in / {u['out'] / 1e6:.2f}M out / "
             f"{u['cache_read'] / 1e6:.2f}M cache-read tokens; proxy ${u['usd']} at Sonnet 5.5 list price",
             "- best search-time score so far: " + (f"{best} ({pr.get('best_search_label', 'selection-biased')})"
                                                    if best is not None else "n/a"),
             f"- memory: {mem.get('used_pct')}% of {mem.get('limit_MB')} MB, guard {mem.get('state')}"
             + (" (guard sample stale)" if mem.get("stale") else ""),
             f"- last ledger checkpoint: CP-{int(last.get('cp', 0)):04d} ({last.get('utc')}), "
             f"phase {last.get('phase')}, next `{last.get('next')}`",
             f"- ETA: {pr.get('eta') or 'see the plan projection (§16); updated once the search runs'}", "",
             "Counts and aggregates only. No test-set score of any arm is posted before the final window completes."]
    return "\n".join(lines)


def _last_post_age(c: str) -> float:
    st = P.read_json(STATE, {}) or {}
    t = (st.get("last_post") or {}).get(c)
    return time.time() - t if t else 1e12


def mark_posted(c: str) -> None:
    st = P.read_json(STATE, {}) or {}
    st.setdefault("last_post", {})[c] = time.time()
    P.write_json(STATE, st)


def once(every: int, force: bool = False) -> list[str]:
    out = []
    posts = P.read_json(post.POSTS, {}) or {}
    for c in P.CANDIDATES:
        if f"{c}/results" in posts:
            continue
        if force or _last_post_age(c) >= every - 90:
            k = dt.datetime.now(dt.timezone.utc).strftime("status_%Y%m%dT%H%M")
            url = post.post(c, k, f"{P.METHOD_NAMES[c]} hourly status", status_body(c))
            mark_posted(c)
            out.append(f"{c} {url}")
    return out


def check_ages(every: int) -> list[str]:
    """For the heartbeat: candidates whose last post is older than `every` (an error entry, §8)."""
    posts = P.read_json(post.POSTS, {}) or {}
    return [c for c in P.CANDIDATES if f"{c}/results" not in posts and _last_post_age(c) > every + 300]


def main() -> int:
    every = int(sys.argv[sys.argv.index("--every") + 1]) if "--every" in sys.argv else 3600
    if sys.argv[1] == "once":
        print("\n".join(once(every, "--force" in sys.argv)))
        return 0
    (P.AW_STATE / "AUTOPOST.pid").write_text(str(os.getpid()))
    while True:
        try:
            once(every)
        except Exception as e:  # noqa: BLE001 — keep the loop alive; the failure is in the local log
            P.progress_log("autopost", "-", f"error {type(e).__name__}: {e}"[:300])
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
