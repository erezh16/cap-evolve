"""P9: analysis of the one final window of eval 5 (docs/EVAL_APPWORLD_5.md §12).

  venv-aw/bin/python -I analyze5.py     # reads AW_STATE/p8final/{order.json,records/}; writes final/analysis.json
                                        # + final/RESULTS.md (pushed; aggregates only) and per-candidate drafts

ARMS = seed + the five candidates. TGC = mean over tasks of the mean over trials of success; SGC = a scenario
passes in trial k iff all its tasks pass in trial k, averaged over k and scenarios; both by difficulty (Easy /
Medium / Hard). For each candidate, the paired difference `<cand> − seed` with a scenario-clustered paired
bootstrap (56 clusters, 10,000 resamples) 95% percentile CI, unadjusted. An infra-failed cell is scored 0
(primary) and dropped in the sensitivity analysis. Only rewards, counters and infra flags are read; no test
trajectory is opened. Cost/tokens/latency per arm come from the window's own records (agent side) and from
each candidate's optimizer_usage.jsonl and rollouts.jsonl (optimizer side, search).
"""

from __future__ import annotations

import json
import os
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import aw5 as P  # noqa: E402

ARMS = P.ARMS
TRIALS = 2
DIFF = {1: "Easy", 2: "Medium", 3: "Hard"}
B = int(os.environ.get("AW_BOOTSTRAP", 10000))


def load():
    order = P.read_json(P.AW_STATE / "p8final" / "order.json")
    recs = {}
    for p in (P.AW_STATE / "p8final" / "records").glob("*.json"):
        recs[int(p.stem)] = json.loads(p.read_text())
    cells = {}
    for c in order:
        r = recs.get(c["idx"])
        cells[(c["arm"], c["task_id"], c["trial"])] = r if r is not None else {"infra_error": "never ran"}
    return order, cells


def succ(cells, arm, t, k, drop=False):
    r = cells.get((arm, t, k))
    if r is None or r.get("infra_error"):
        return None if drop else 0.0
    return 1.0 if r.get("success") else 0.0


def tgc(cells, arm, tasks, drop=False):
    per = []
    for t in tasks:
        v = [x for k in range(TRIALS) if (x := succ(cells, arm, t, k, drop)) is not None]
        if v:
            per.append(sum(v) / len(v))
    return sum(per) / len(per) if per else float("nan")


def sgc(cells, arm, scen, drop=False):
    vals = []
    for k in range(TRIALS):
        for s, ts in scen.items():
            v = [succ(cells, arm, t, k, drop) for t in ts]
            if drop and any(x is None for x in v):
                continue
            vals.append(1.0 if all(x == 1.0 for x in v) else 0.0)
    return sum(vals) / len(vals) if vals else float("nan")


def bootstrap(cells, a, b, scen, rng):
    scens = sorted(scen)
    dt, ds = [], []
    for _ in range(B):
        pick = [rng.choice(scens) for _ in scens]
        tasks = [t for s in pick for t in scen[s]]
        st = {f"{s}#{i}": scen[s] for i, s in enumerate(pick)}
        dt.append(tgc(cells, a, tasks) - tgc(cells, b, tasks))
        ds.append(sgc(cells, a, st) - sgc(cells, b, st))

    def ci(xs):
        xs = sorted(xs)
        return [xs[int(0.025 * B)], xs[int(0.975 * B) - 1]]
    return ci(dt), ci(ds)


def by_difficulty(cells, arm, ids, scen, diff, d) -> dict:
    """TGC over the tasks of difficulty d; SGC over the scenarios whose tasks are all of difficulty d."""
    ts = [t for t in ids if diff[t] == d]
    sc = {s: v for s, v in scen.items() if all(diff[t] == d for t in v)}
    return {"n": len(ts), "tgc": tgc(cells, arm, ts), "n_scenarios": len(sc), "sgc": sgc(cells, arm, sc) if sc else None}


def optimizer_side(c: str) -> dict:
    u = P.read_jsonl(P.AW_STATE / c / "optimizer_usage.jsonl")
    ro = P.read_jsonl(P.AW_STATE / c / "rollouts.jsonl")
    pin = sum(int(r.get("prompt_tokens") or 0) for r in u)
    pout = sum(int(r.get("completion_tokens") or 0) for r in u)
    fz = P.read_json(P.PUSHED / c / "artifact" / "FREEZE.json", {}) or {}
    return {"calls": len(u), "errors": sum(1 for r in u if r.get("error")), "input_tokens": pin, "output_tokens": pout,
            "cache_read_tokens": sum(int(r.get("cache_read") or 0) for r in u),
            "proxy_usd": round(pin / 1e6 * P.PRICE_IN + pout / 1e6 * P.PRICE_OUT, 2),
            "reported_usd": round(sum(float(r.get("cost_usd") or 0) for r in u), 2) or None,
            "optimizer_seconds": round(sum(float(r.get("seconds") or 0) for r in u)),
            "counted_search_rollouts": len(ro), "search_infra_errors": sum(1 for r in ro if r.get("infra")),
            "search_episode_seconds_mean": round(statistics.mean([r["seconds"] for r in ro if r.get("seconds")]), 1) if ro else None,
            "search_wall": [ro[0]["t"], ro[-1]["t"]] if ro else None, "freeze": fz}


def dev_diag() -> dict:
    prog = P.read_json(P.PUSHED / "p6dev" / "progress.json", {}) or {}
    return {a: v.get("tgc") for a, v in (prog.get("per_arm") or {}).items()}


def usd(o: dict) -> str:
    """The cost the tool itself reported (Agent SDK / claude CLI: includes cache writes and reads) when there is
    one; otherwise the list-price proxy over input + output tokens (chat-API arms have no cache)."""
    return f"${o['reported_usd']} (reported)" if o.get("reported_usd") else f"${o['proxy_usd']} (proxy)"


def pct(x):
    return f"{100 * x:.1f}"


def main() -> int:
    os.chmod(P.ROOT_FULL, 0o755) if (os.stat(P.ROOT_FULL).st_mode & 0o777) == 0 else None
    ids = P.read_split("test_normal", P.ROOT_FULL)
    diff = {t: json.loads((P.ROOT_FULL / "data/tasks" / t / "ground_truth/metadata.json").read_text())["difficulty"]
            for t in ids}
    scen = defaultdict(list)
    for t in ids:
        scen[t.split("_")[0]].append(t)
    order, cells = load()
    rng = random.Random(0)
    res: dict = {"n_tasks": len(ids), "n_scenarios": len(scen), "trials": TRIALS, "cells": len(order),
                 "bootstrap_resamples": B, "arms": {}, "vs_seed": {}}
    for arm in ARMS:
        rs = [r for (a, _, _), r in cells.items() if a == arm and not r.get("infra_error")]
        agree = sum(1 for t in ids if succ(cells, arm, t, 0) == succ(cells, arm, t, 1))

        def mean(k):
            v = [float(r.get(k) or 0) for r in rs]
            return statistics.mean(v) if v else float("nan")
        res["arms"][arm] = {
            "tgc": tgc(cells, arm, ids), "sgc": sgc(cells, arm, scen),
            "tgc_drop_missing": tgc(cells, arm, ids, True), "sgc_drop_missing": sgc(cells, arm, scen, True),
            "by_difficulty": {n: by_difficulty(cells, arm, ids, scen, diff, d) for d, n in DIFF.items()},
            "episodes": len(rs), "missing": sum(1 for (a, _, _), r in cells.items() if a == arm and r.get("infra_error")),
            "prompt_tokens_per_task": mean("prompt_tokens"), "completion_tokens_per_task": mean("completion_tokens"),
            "steps_per_task": mean("n_steps"), "episode_seconds": mean("episode_seconds"),
            "step_cap_hits": sum(1 for r in rs if r.get("termination") == "max_steps"),
            "token_cap_hits": sum(1 for r in rs if r.get("termination") == "token_cap"),
            "context_exceeded": sum(1 for r in rs if r.get("termination") == "context_exceeded"),
            "collateral_damage": sum(1 for r in rs if r.get("collateral_damage")),
            "complete_task_not_called": sum(1 for r in rs if not r.get("complete_task_called")),
            "fs_probe": sum(1 for r in rs if r.get("fs_probe")),
            "max_prompt_tokens": max((int(r.get("max_prompt_tokens") or 0) for r in rs), default=0),
            "trials_agree_share": agree / len(ids),
            "infra_retries": sum(int(r.get("attempt") or 0) for r in rs)}
    for c in P.CANDIDATES:
        ct, cs = bootstrap(cells, c, "seed", scen, rng)
        res["vs_seed"][c] = {"d_tgc": res["arms"][c]["tgc"] - res["arms"]["seed"]["tgc"], "ci_tgc": ct,
                             "d_sgc": res["arms"][c]["sgc"] - res["arms"]["seed"]["sgc"], "ci_sgc": cs}
    res["optimizer"] = {c: optimizer_side(c) for c in P.CANDIDATES}
    res["dev_diagnostic_tgc"] = dev_diag()
    m = P.manifest()
    res["manifest"] = {k: m.get(k) for k in ("appworld", "candidates", "m_cap", "final_order", "freeze", "models")}
    scan = P.read_json(P.PUSHED / "isolation_scan.json", {}) or {}
    res["isolation"] = {c: {"test_id_hits": (scan.get(c) or {}).get("test_id_hits"),
                            "breach": (scan.get(c) or {}).get("isolation_breach")} for c in P.CANDIDATES}
    os.chmod(P.ROOT_FULL, 0o000) if os.environ.get("AW_RELOCK") == "1" else None
    P.write_json(P.PUSHED / "final" / "analysis.json", res)

    L = ["| arm | TGC | SGC | Δ TGC vs seed [95% CI] | Δ SGC vs seed [95% CI] | missing |", "|---|---|---|---|---|---|"]
    for a in ARMS:
        r = res["arms"][a]
        v = res["vs_seed"].get(a)
        dt = f"{pct(v['d_tgc'])} [{pct(v['ci_tgc'][0])}, {pct(v['ci_tgc'][1])}]" if v else "—"
        ds = f"{pct(v['d_sgc'])} [{pct(v['ci_sgc'][0])}, {pct(v['ci_sgc'][1])}]" if v else "—"
        L.append(f"| {a} | {pct(r['tgc'])} | {pct(r['sgc'])} | {dt} | {ds} | {r['missing']} |")
    D = ["| arm | " + " | ".join(f"{n} (n={res['arms']['seed']['by_difficulty'][n]['n']})" for n in DIFF.values()) + " |",
         "|---|---|---|---|"]
    for a in ARMS:
        D.append(f"| {a} | " + " | ".join(pct(res["arms"][a]["by_difficulty"][n]["tgc"]) for n in DIFF.values()) + " |")
    C = ["| arm | prompt tok/ep | completion tok/ep | steps/ep | s/ep | step-cap | ctx-exceeded | collateral | max prompt | trials agree |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for a in ARMS:
        r = res["arms"][a]
        C.append(f"| {a} | {r['prompt_tokens_per_task']:,.0f} | {r['completion_tokens_per_task']:,.0f} | {r['steps_per_task']:.1f} | "
                 f"{r['episode_seconds']:.0f} | {r['step_cap_hits']} | {r['context_exceeded']} | {r['collateral_damage']} | "
                 f"{r['max_prompt_tokens']:,} | {100 * r['trials_agree_share']:.0f}% |")
    O = ["| candidate | counted search rollouts | optimizer calls | input tok | output tok | cache-read tok | USD | optimizer wall s |",
         "|---|---|---|---|---|---|---|---|"]
    for c in P.CANDIDATES:
        o = res["optimizer"][c]
        O.append(f"| {c} | {o['counted_search_rollouts']} | {o['calls']} | {o['input_tokens']:,} | {o['output_tokens']:,} | "
                 f"{o['cache_read_tokens']:,} | {usd(o)} | {o['optimizer_seconds']:,} |")
    md = ("## Final window: test_normal, 168 tasks / 56 scenarios × 2 trials × 6 arms\n\n" + "\n".join(L)
          + "\n\n## TGC by difficulty\n\n" + "\n".join(D) + "\n\n## Agent cost, tokens and latency per episode (final window)\n\n"
          + "\n".join(C) + "\n\n## Optimizer side (search)\n\n" + "\n".join(O) + "\n")
    P.atomic_write(P.PUSHED / "final" / "RESULTS.md", md)
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
