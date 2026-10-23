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
PHASE_NAMES = {"P0": "decisions", "P1": "build", "P2": "acceptance checks",
               "P3": "seed baseline (reused from REST P3)" if P.LEDGER_PREFIX == "CE2" else "shared seed baseline",
               "P4": "searches", "P5": "dev diagnostic", "P6": "isolation scan",
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
    if P.LEDGER_PREFIX == "CE2":
        nx = str(last.get("next") or "")
        ph = nx.split("/")[0] if nx[:2] in {f"P{i}" for i in range(10)} else ph
        return {"P1": f"build ({nx})", "P2": f"acceptance checks ({nx})",
                "P4": "searches (both arms launched together)", "P5": "dev diagnostic",
                "P6": "isolation scan", "P7": "final window", "P8": "analysis", "P9": "results posts"}.get(
                    ph, f"phase {ph}")
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
             *([f"- iterations scored: {pr.get('iterations_done', 0)} of 6, accepted {pr.get('accepted', 0)}"
                + (f" (gate K = {P.K_SE[c]})" if hasattr(P, "K_SE") else "")] if P.LEDGER_PREFIX == "CE2" else []),
             f"- counted search rollouts: {counted} of B = {P.BUDGET_ROLLOUTS}"
             + (f" (cache hits {pr['cache_hits']})" if pr.get("cache_hits") is not None else ""),
             f"- optimizer ({P.OPT_MODEL}): {u['calls']} calls, {u['in'] / 1e6:.2f}M in / {u['out'] / 1e6:.2f}M out / "
             f"{u['cache_read'] / 1e6:.2f}M cache-read tokens; proxy ${u['usd']} at Sonnet 5.5 list price",
             "- best search-time score so far: " + (f"{best} ({pr.get('best_search_label', 'selection-biased')})"
                                                    if best is not None else "n/a"),
             f"- memory: {mem.get('used_pct')}% of {mem.get('limit_MB')} MB (peak {mem.get('peak_pct')}%), "
             f"guard {mem.get('state')}"
             + (" (guard sample stale)" if mem.get("stale") else ""),
             f"- last ledger checkpoint: {P.LEDGER_PREFIX}-{int(last.get('cp', 0)):04d} ({last.get('utc')}), "
             f"phase {last.get('phase')}, next `{last.get('next')}`",
             f"- ETA: {pr.get('eta') or ('plan §18 projection: about 12–16 h in total; per-iteration ETA once the search runs' if P.LEDGER_PREFIX == 'CE2' else 'see the plan projection (§16); updated once the search runs')}",
             *window_lines(c), "",
             "Counts and aggregates only. No test-set score of any arm is posted before the final window completes."]
    return "\n".join(lines)


def window_lines(c: str) -> list[str]:
    """Final-window progress, counts only (§8: no test score of any arm before the analysis)."""
    rec_dir = P.AW_STATE / "final" / "records"
    order = P.read_json(P.AW_STATE / "final" / "order.json")
    if not order or not rec_dir.exists():
        return []
    recs = list(rec_dir.glob("*.json"))
    arm_of = {x["idx"]: x["arm"] for x in order}
    mine = sum(1 for p in recs if p.stem.isdigit() and arm_of.get(int(p.stem)) == c)
    recent = [p.stat().st_mtime for p in recs if p.stat().st_mtime > time.time() - 3600]
    left = len(order) - len(recs)
    started = min((p.stat().st_mtime for p in recs), default=time.time())
    eta = (f"; about {left / max(1, len(recent)):.1f} h left at the last hour's rate"
           if recent and left and time.time() - started >= 3600 else "")
    return [f"- final window (168 test_normal × {len(P.ARMS)} arms × 2 trials): {len(recs)}/{len(order)} cells done{eta}; "
            f"this arm {mine}/336. No test score is shown before the window completes."]


def _last_post_age(c: str) -> float:
    st = P.read_json(STATE, {}) or {}
    t = (st.get("last_post") or {}).get(c)
    return time.time() - t if t else 1e12


def mark_posted(c: str) -> None:
    st = P.read_json(STATE, {}) or {}
    st.setdefault("last_post", {})[c] = time.time()
    P.write_json(STATE, st)


def milestones(c: str) -> list[tuple[str, str, str]]:
    """§8 search milestones, derived uniformly for every candidate from its pushed progress.json and its counted
    rollouts: search started, every 25% of B, a new best search-time score (an accepted candidate), search ended,
    frozen. Each milestone has a stable key so it is posted once. Drivers that post their own milestones use
    different keys; a duplicate message is possible but harmless."""
    pr = P.read_json(P.PUSHED / c / "progress.json", {}) or {}
    counted = len(P.read_jsonl(P.AW_STATE / c / "rollouts.jsonl"))
    stage = str(pr.get("stage") or "")
    chain = P.read_json(P.AW_STATE / "p4" / f"{c}.json", {}) or {}     # the P4 runner's record of the chain
    done = set(chain.get("done") or [])
    out = []
    if counted > 0:
        out.append(("m4_search_start", "search started",
                    f"**{P.METHOD_NAMES[c]}: counted search started.** Settings as plan §9 for this candidate; "
                    f"B = {P.BUDGET_ROLLOUTS} counted rollouts and 10M optimizer tokens; gold-free F1 feedback; "
                    f"baseline = the seed run (P3{', reused from REST' if P.LEDGER_PREFIX == 'CE2' else ''}). Hourly status posts follow."))
    for q in (1, 2, 3, 4):
        if counted >= q * P.BUDGET_ROLLOUTS // 4:
            out.append((f"m4_budget_{25 * q}", f"{25 * q}% of B",
                        f"**{P.METHOD_NAMES[c]}: {25 * q}% of the search budget used** ({counted} of "
                        f"{P.BUDGET_ROLLOUTS} counted rollouts).\n\n" + status_body(c).split("\n", 2)[2]))
    best = pr.get("best_search_score")
    if best is not None:
        out.append((f"m4_best_{best}", "new best search-time score",
                    f"**{P.METHOD_NAMES[c]}: new best search-time score {best}** "
                    f"({pr.get('best_search_label', 'selection-biased')}; a search-set number, not a test result)."))
    if "search" in done:
        out.append(("m4_search_done", "search ended", f"**{P.METHOD_NAMES[c]}: search ended** ({stage}).\n\n"
                    + status_body(c).split("\n", 2)[2]))
    fz = P.read_json(P.PUSHED / c / "artifact" / "FREEZE.json", {}) or {}
    if fz and "freeze" in done:
        keep = {k: v for k, v in fz.items() if isinstance(v, (int, float, bool, str)) and len(str(v)) <= 80}
        out.append(("m4_frozen", "champion frozen", f"**{P.METHOD_NAMES[c]}: champion frozen** (lint-clean, "
                    f"published in `docs/{P.PUSHED.name}/{c}/artifact/`).\n\n"
                    + "\n".join(f"- {k}: {v}" for k, v in keep.items())))
    scan = (P.read_json(P.PUSHED / "isolation_scan.json", {}) or {}).get(c)
    if scan and "scan" in done:
        out.append(("m4_scanned", "isolation scan", f"**{P.METHOD_NAMES[c]}: isolation scan done.** Test-id hits in "
                    f"every optimizer-side record and workspace: {scan.get('test_id_hits')}"
                    + (" — ISOLATION BREACH" if scan.get("isolation_breach") else "") + ". Literal-string counts are "
                    f"in `docs/{P.PUSHED.name}/isolation_scan.json`."))
    return out


def once(every: int, force: bool = False) -> list[str]:
    out = []
    posts = P.read_json(post.POSTS, {}) or {}
    for c in P.CANDIDATES:
        for key, title, body in milestones(c):
            if f"{c}/{key}" not in posts:
                url = post.post(c, key, f"{P.METHOD_NAMES[c]} {title}", body)
                mark_posted(c)
                out.append(f"{c} {key} {url}")
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
