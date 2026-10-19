"""Periodic per-candidate progress posts (user decision D9, docs/EVAL_APPWORLD_5.md §5).

  python3 -I autopost5.py loop [--every 7200]     # nohup loop
  python3 -I autopost5.py once

Every 60 s: if the ledger's `next` names a new phase of a candidate (search started, search finished →
freeze, frozen → scan, scanned → next candidate), post a milestone comment on that candidate's issue at
once; otherwise, while a candidate's search runs, post a progress comment every `--every` seconds. Bodies are
built only from the pushed progress.json / FREEZE.json / isolation_scan.json (counts and aggregates), pass
the content filter in post5.post, and each is keyed so nothing is posted twice.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aw5 as P  # noqa: E402
import post5  # noqa: E402
import status_doc as S  # noqa: E402

STATE = P.AW_STATE / "autopost.json"


def _opt(pr: dict) -> str:
    o = pr.get("optimizer") or {}
    usd = o.get("proxy_usd")
    usd = f"${usd} proxy at list price" if usd is not None else f"${o.get('cost_usd', 0)} CLI/SDK-reported"
    return (f"{o.get('calls', 0)} calls, {o.get('prompt_tokens', 0) / 1e6:.2f}M in / "
            f"{o.get('completion_tokens', 0) / 1e6:.2f}M out tokens ({usd})")


def progress_body(c: str) -> str:
    pr = P.read_json(P.PUSHED / c / "progress.json", {}) or {}
    rows = pr.get("rows") or pr.get("iterations") or []
    lines = [f"**{c} search in progress** (counted, automatic update).", "",
             f"- counted rollouts: {pr.get('counted_rollouts', 0)} of B = {P.BUDGET_ROLLOUTS}",
             f"- optimizer (aws/claude-sonnet-5-5): {_opt(pr)}"]
    if c == "gepa" and rows:
        r = rows[-1]
        lines += [f"- iterations: {r.get('iteration')}, accepted children: {sum(1 for x in rows if x.get('accepted'))}, "
                  f"candidates: {r.get('n_candidates')}", f"- best dev TGC: {r.get('best_dev')} (seed 0.421)"]
    elif c == "skillopt":
        acc = [x for x in rows if x.get("accepted") or str(x.get("action", "")).startswith("accept")]
        lines += [f"- steps on record: {len(rows)}, accepted by the gate: {len(acc)}",
                  f"- best skill so far: {pr.get('best_skill_chars', 0):,} chars"]
    elif c == "wikiskill":
        lines += [f"- iterations done: {len(rows)} of {pr.get('K')}; R_best (dev): {pr.get('r_best')}",
                  f"- accepted skills: {pr.get('skills')}, playbook {pr.get('playbook_chars', 0):,} chars"]
    elif c == "evoskill":
        ev = [x for x in rows if x.get("event") == "eval_result"]
        base = next((x for x in rows if x.get("event") == "baseline"), {})
        lines += [f"- children scored: {len(ev)} (admitted to the frontier: {sum(1 for x in ev if x.get('added'))})",
                  f"- base val-subset score: {base.get('score')}; best child: "
                  f"{max((x.get('score') or 0) for x in ev) if ev else None}"]
    elif c == "metaharness":
        lines += [f"- iterations on record: {max((x.get('iteration') or 0) for x in rows) if rows else 0}; "
                  f"best search-set TGC: {(pr.get('best') or {}).get('avg_pass_rate')}"]
    lines += ["", "Search-time scores come from train/dev (selection sets) and are optimistic. Only the final "
                  "test_normal window counts as a result."]
    return "\n".join(lines)


def _window_line(c: str) -> str:
    """Counts only (plan §10.2: no per-cell test outcome is published before P9)."""
    prog = P.read_json(P.PUSHED / "p8final" / "progress.json", {}) or {}
    if not prog:
        return "- final window: not started"
    recs = sorted((P.AW_STATE / "p8final" / "records").glob("*.json"), key=lambda q: q.stat().st_mtime)
    eta = ""
    recent = [q.stat().st_mtime for q in recs if q.stat().st_mtime > time.time() - 3600]
    left = prog["cells_total"] - prog["cells_done"]
    if len(recent) >= 10 and left > 0:
        rate = len(recent) / max(60.0, time.time() - min(recent))
        eta = f"; at the last hour's rate ({3600 * rate:.0f} cells/h) about {left / rate / 3600:.1f} h left"
    arm = (prog.get("per_arm") or {}).get(c, {})
    return (f"- **final window** (168 test_normal × 6 arms × 2 trials, one shuffled order): "
            f"{prog['cells_done']}/{prog['cells_total']} cells done{eta}. This arm: {arm.get('done', 0)}/336 cells, "
            f"infra still failed {arm.get('infra_missing', 0)}. Test scores are not shown until the window completes "
            f"and the analysis runs.")


def status_body(c: str) -> str:
    """Hourly per-candidate status, any phase (user instruction 2026-10-19)."""
    nxt = (S.last_entry().get("next") or "")
    fz = P.read_json(P.PUSHED / c / "artifact" / "FREEZE.json", {}) or {}
    pr = P.read_json(P.PUSHED / c / "progress.json", {}) or {}
    dev = ((P.read_json(P.PUSHED / "p6dev" / "progress.json", {}) or {}).get("per_arm") or {})
    scan = (P.read_json(P.PUSHED / "isolation_scan.json", {}) or {}).get(c, {})
    stage = ("search running" if nxt.startswith(f"{c}/search") else
             "final window running" if nxt.startswith("p8final") or nxt.startswith("P8") else
             "analysis" if nxt.startswith("P9") else "results posting" if nxt.startswith("P10") else nxt)
    lines = [f"**Hourly status — {c}** ({P.utcnow()}). Evaluation stage: {stage}.", "",
             f"- search: {'finished; champion frozen' if fz else 'in progress'}"
             + (f" ({pr.get('counted_rollouts')} of {P.BUDGET_ROLLOUTS} counted rollouts)" if pr else ""),
             f"- optimizer spend for this arm: {_opt(pr)}" if pr else "- optimizer spend: n/a"]
    if dev.get(c):
        lines.append(f"- dev diagnostic (57 dev tasks, 1 trial; selection-biased): {c} {dev[c].get('tgc')} vs seed "
                     f"{(dev.get('seed') or {}).get('tgc')}")
    if scan:
        lines.append(f"- isolation scan: {scan.get('test_id_hits')} test-id hits")
    lines.append(_window_line(c))
    return "\n".join(lines)


def milestone_body(c: str, what: str) -> str:
    if what == "search":
        return (f"**{c}: counted search started.** Settings follow plan §7 for this candidate. The cap is "
                f"B = {P.BUDGET_ROLLOUTS} counted rollouts and 10M optimizer tokens, with gold-free F1 feedback; "
                f"root_full stays locked. Progress posts follow every few hours.")
    if what == "freeze":
        return f"**{c}: search finished.**\n\n" + progress_body(c).split("\n", 2)[2] + ("\n\nThis ends the **search only**. The champion's test_normal score comes from the one common final "
               "window (6 arms × 168 tasks × 2 trials), which runs after all five searches. Next: freeze the champion.")
    if what == "scan":
        fz = P.read_json(P.PUSHED / c / "artifact" / "FREEZE.json", {}) or {}
        keep = {k: v for k, v in fz.items() if k not in ("tree_sha256",) and not isinstance(v, (list, dict))}
        return (f"**{c}: champion frozen** (lint-clean; published in `docs/EVAL_APPWORLD_5_STATE/{c}/artifact/`).\n\n"
                + "\n".join(f"- {k}: {v}" for k, v in keep.items()) + "\n\nNext: the per-candidate isolation scan.")
    if what == "scanned":
        sc = (P.read_json(P.PUSHED / "isolation_scan.json", {}) or {}).get(c, {})
        return (f"**{c}: isolation scan done.** Test-id hits in every optimizer-side record and workspace: "
                f"{sc.get('test_id_hits')}{' — ISOLATION BREACH' if sc.get('isolation_breach') else ''}. "
                f"Literal-string counts (ground_truth, root_full, …) are in `docs/EVAL_APPWORLD_5_STATE/isolation_scan.json`.\n\n"
                f"Next: this candidate waits for the common dev diagnostic and the final test_normal window (6 arms, "
                f"run once all five searches are done).")
    raise ValueError(what)


def _milestones_since(cp: int) -> list[tuple[int, str]]:
    """Every (cp, next) of ledger entries after `cp` whose `next` names a candidate phase."""
    out = []
    for n, chunk in S.entries():
        if n <= cp:
            continue
        m = S.JSON_RE.search(chunk)
        nxt = (json.loads(m.group(1)).get("next") or "") if m else ""
        out.append((n, nxt))
    return out


def once(every: int) -> None:
    st = P.read_json(STATE, {"last_cp": -1, "last_progress": {}}) or {}
    st.setdefault("last_cp", -1)
    seen_next = st.get("last_next")
    for cp, nxt in _milestones_since(st["last_cp"]):
        st["last_cp"] = cp
        if nxt == seen_next:
            continue
        parts, prev = nxt.split("/"), (seen_next or "").split("/")
        if len(parts) >= 2 and parts[0] in P.CANDIDATES and parts[1] in ("search", "freeze", "scan"):
            post5.post(parts[0], f"m_{parts[1]}", f"{parts[0]} {parts[1]}", milestone_body(parts[0], parts[1]))
        if len(prev) >= 2 and prev[0] in P.CANDIDATES and prev[1] == "scan" and parts[0] != prev[0]:
            post5.post(prev[0], "m_scanned", f"{prev[0]} scanned", milestone_body(prev[0], "scanned"))
        seen_next = nxt
    st["last_next"] = seen_next
    # hourly status on every candidate's issue, in every phase, until the results are posted
    last = st.setdefault("last_status", 0)
    done_all = all(f"{c}/results" in (P.read_json(post5.POSTS, {}) or {}) for c in P.CANDIDATES)
    if not done_all and time.time() - last >= every:
        k = int(time.time() // every)
        for c in P.CANDIDATES:
            post5.post(c, f"status_{k}", f"{c} hourly status", status_body(c))
        st["last_status"] = time.time()
    P.write_json(STATE, st)


def main() -> int:
    every = int(sys.argv[sys.argv.index("--every") + 1]) if "--every" in sys.argv else 7200
    if sys.argv[1] == "once":
        once(every)
        return 0
    (P.AW_STATE / "AUTOPOST.pid").write_text(str(__import__("os").getpid()))
    while True:
        try:
            once(every)
        except Exception as e:  # noqa: BLE001 — keep the loop alive; the failure is in the local log
            P.progress_log("autopost", "-", f"error {type(e).__name__}: {e}"[:300])
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
