"""P4 (docs/TEST_ALL.md §11): analysis of the one TEST_ALL window. Run in venv-aw (a trusted script, rule R1):

  . examples/appworld/test_all/env.sh && AW_RELOCK=1 $VENV_AW/bin/python -I examples/appworld/test_all/analyze_all.py

Reads AW_STATE/final/{order.json,records/} (counters and flags only) and each test task's difficulty; writes
docs/TEST_ALL_STATE/final/analysis.json and RESULTS.md, aggregates only (no task id, no per-task outcome).

Definitions follow scripts/analyze.py (REST), extended to 13 arms and 5 trials:
  TGC = mean over the 168 tasks of the mean success over the trials; SGC = per trial the share of the 56 scenarios
  whose tasks all pass, averaged over trials; both overall and by difficulty. An infra-failed cell scores 0 (primary)
  and is dropped in the sensitivity rows. Every arm − seed and all 78 pairs: Δ TGC and Δ SGC with a scenario-clustered
  paired bootstrap (resample the 56 scenarios, 10,000 resamples, random.Random(0)), 95% percentile CI; the pairwise
  Δ TGC also carry a Holm correction over the 78 pairs (bootstrap two-sided p = 2·min(P(Δ*≤0), P(Δ*≥0))). §11.3:
  per-task pass-count distribution, stable/flaky shares, pass@k and pass^k (k = 1..5, averaged over trial orders),
  within-task variance and its share of total variance, trial-count sensitivity (first 1..5 trials, with CIs), and
  each arm's earlier test_normal TGC from its own evaluation (context, "other window").
"""

from __future__ import annotations

import itertools
import json
import math
import os
import random
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "scripts"))
import awrest as P  # noqa: E402

ARMS = tuple(P.ARMS)
K = P.FINAL_TRIALS
DIFF = {1: "Easy", 2: "Medium", 3: "Hard"}
B = int(os.environ.get("AW_BOOTSTRAP", 10000))
FINAL = P.AW_STATE / "final"
OUT = P.PUSHED / "final"


# ---------------------------------------------------------------- data

def load(ids: list[str]) -> dict:
    """succ[arm][task] = list of K values in trial order: 1.0, 0.0, or None for an infra-failed / missing cell."""
    order = P.read_json(FINAL / "order.json")
    recs = {}
    for p in (FINAL / "records").glob("*.json"):
        recs[int(p.stem)] = json.loads(p.read_text())
    succ = {a: {t: [None] * K for t in ids} for a in ARMS}
    raw = defaultdict(list)
    for c in order:
        r = recs.get(c["idx"])
        if r is not None and not r.get("infra_error"):
            succ[c["arm"]][c["task_id"]][c["trial"]] = 1.0 if r.get("success") else 0.0
        raw[c["arm"]].append(r if r is not None else {"infra_error": "never ran"})
    return {"order": order, "succ": succ, "raw": raw, "n_records": len(recs)}


def vals(succ, arm, t, trials, drop):
    v = [succ[arm][t][k] for k in trials]
    return [x for x in v if x is not None] if drop else [0.0 if x is None else x for x in v]


def tgc(succ, arm, tasks, trials=range(K), drop=False):
    per = [sum(v) / len(v) for t in tasks if (v := vals(succ, arm, t, trials, drop))]
    return sum(per) / len(per) if per else float("nan")


def sgc(succ, arm, scen: dict, trials=range(K), drop=False):
    out = []
    for k in trials:
        for ts in scen.values():
            v = [succ[arm][t][k] for t in ts]
            if drop and any(x is None for x in v):
                continue
            out.append(1.0 if all(x == 1.0 for x in v) else 0.0)
    return sum(out) / len(out) if out else float("nan")


# ---------------------------------------------------------------- bootstrap

def resamples(scen: dict) -> list[list[str]]:
    rng = random.Random(0)
    keys = sorted(scen)
    return [[rng.choice(keys) for _ in keys] for _ in range(B)]


def boot_pair(succ, a, b, scen, picks, trials=range(K)):
    dt, ds = [], []
    for pick in picks:
        tasks = [t for s in pick for t in scen[s]]
        st = {f"{s}#{i}": scen[s] for i, s in enumerate(pick)}
        dt.append(tgc(succ, a, tasks, trials) - tgc(succ, b, tasks, trials))
        ds.append(sgc(succ, a, st, trials) - sgc(succ, b, st, trials))
    return dt, ds


def ci(xs):
    xs = sorted(xs)
    return [xs[int(0.025 * len(xs))], xs[int(0.975 * len(xs)) - 1]]


def p_two_sided(xs):
    n = len(xs)
    return min(1.0, 2 * min(sum(1 for x in xs if x <= 0) / n, sum(1 for x in xs if x >= 0) / n))


def holm(pvals: dict[str, float], alpha=0.05) -> dict[str, bool]:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m, out, stop = len(items), {}, False
    for i, (k, p) in enumerate(items):
        if stop or p > alpha / (m - i):
            stop = True
            out[k] = False
        else:
            out[k] = True
    return out


# ---------------------------------------------------------------- §11.3 stochasticity

def stochastic(succ, arm, ids) -> dict:
    counts = [int(sum(vals(succ, arm, t, range(K), False))) for t in ids]
    dist = {str(i): counts.count(i) for i in range(K + 1)}
    perms = list(itertools.permutations(range(K)))
    pass_at, pass_hat = {}, {}
    for k in range(1, K + 1):
        at = hat = 0.0
        for perm in perms:
            sub = perm[:k]
            for t in ids:
                v = vals(succ, arm, t, sub, False)
                at += 1.0 if any(x == 1.0 for x in v) else 0.0
                hat += 1.0 if all(x == 1.0 for x in v) else 0.0
        pass_at[str(k)] = at / (len(perms) * len(ids))
        pass_hat[str(k)] = hat / (len(perms) * len(ids))
    means = [c / K for c in counts]
    within = statistics.mean(m * (1 - m) for m in means)          # per-task Bernoulli variance over its trials
    allv = [x for t in ids for x in vals(succ, arm, t, range(K), False)]
    total = statistics.pvariance(allv) if allv else float("nan")
    return {"pass_count_distribution": dist, "stable_share": (dist["0"] + dist[str(K)]) / len(ids),
            "flaky_share": 1 - (dist["0"] + dist[str(K)]) / len(ids), "pass_at_k": pass_at, "pass_hat_k": pass_hat,
            "within_task_variance_mean": within, "total_variance": total,
            "within_share_of_variance": (within / total) if total else None}


# ---------------------------------------------------------------- earlier windows (context only)

def _git_json(spec: str) -> dict:
    r = subprocess.run(["git", "-C", str(P.REPO), "show", spec], capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 else {}


def earlier() -> dict:
    out = {}
    rest = _git_json("origin/eval-rest:docs/EVAL_APPWORLD_REST_STATE/final/analysis.json").get("arms", {})
    ev5 = _git_json("origin/eval5:docs/EVAL_APPWORLD_5_STATE/final/analysis.json").get("arms", {})
    ce3 = _git_json("origin/eval-ce3:docs/EVAL_APPWORLD_CE3_STATUS_STATE/final/analysis.json").get("arms", {})
    sm = P.read_json(P.AW_STATE / "earlier" / "smoke" / "results.json", {}) or {}
    ace = P.read_json(P.AW_STATE / "earlier" / "ace" / "pushed_final__analysis.json", {}) or {}
    src = {"altk": (sm.get("arms", {}).get("altk"), "smoke test window (2026-10-15)"),
           "ace": (ace.get("arms", {}).get("ace"), "ACE window (2026-10-14)"),
           "harnesslens": (rest.get("harnesslens"), "REST window (2026-10-21)"),
           "miprov2": (rest.get("miprov2"), "REST window (2026-10-21)"),
           "trace2skill": (rest.get("trace2skill"), "REST window (2026-10-21)"),
           "gepa_full": (rest.get("gepa_full"), "REST window (2026-10-21)"),
           "cape_k02": (ce3.get("ce3_k02"), "CE3 window (2026-10-24)")}
    for a in ("gepa", "skillopt", "wikiskill", "evoskill", "metaharness"):
        src[a] = (ev5.get(a), "eval 5 window (2026-10-19)")
    src["seed"] = (rest.get("seed"), "REST window (2026-10-21); the seed also ran in every other window")
    for a, (v, lab) in src.items():
        out[a] = {"tgc": (v or {}).get("tgc"), "trials": 2, "label": f"other window: {lab}"}
    out["_seed_in_other_windows"] = {"REST": (rest.get("seed") or {}).get("tgc"), "eval 5": (ev5.get("seed") or {}).get("tgc"),
                                     "CE3": (ce3.get("seed") or {}).get("tgc"),
                                     "smoke": (sm.get("arms", {}).get("seed") or {}).get("tgc"),
                                     "ACE": (ace.get("arms", {}).get("seed") or {}).get("tgc")}
    return out


# ---------------------------------------------------------------- main

def _q(xs, q):
    xs = sorted(x for x in xs if x is not None)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else None


def per_arm(succ, raw, arm, ids, scen, diff) -> dict:
    rs = [r for r in raw[arm] if not r.get("infra_error")]

    def dist(k):
        v = [float(r.get(k) or 0) for r in rs]
        return {"mean": statistics.mean(v) if v else None, "p50": _q(v, 0.5), "p90": _q(v, 0.9)}

    byd = {}
    for d, n in DIFF.items():
        ts = [t for t in ids if diff[t] == d]
        sc = {s: v for s, v in scen.items() if all(diff[t] == d for t in v)}
        byd[n] = {"n": len(ts), "tgc": tgc(succ, arm, ts), "n_scenarios": len(sc), "sgc": sgc(succ, arm, sc) if sc else None}
    return {"tgc": tgc(succ, arm, ids), "sgc": sgc(succ, arm, scen),
            "tgc_drop_missing": tgc(succ, arm, ids, drop=True), "sgc_drop_missing": sgc(succ, arm, scen, drop=True),
            "by_difficulty": byd, "episodes": len(rs), "missing": len(raw[arm]) - len(rs),
            "pass_fraction": sum(int(r.get("pass_count") or 0) for r in rs) / max(1, sum(int(r.get("num_tests") or 0) for r in rs)),
            "prompt_tokens": dist("prompt_tokens"), "completion_tokens": dist("completion_tokens"),
            "steps": dist("n_steps"), "episode_seconds": dist("episode_seconds"),
            "max_prompt_tokens": max((int(r.get("max_prompt_tokens") or 0) for r in rs), default=0),
            "step_cap_hits": sum(1 for r in rs if r.get("termination") == "max_steps"),
            "token_cap_hits": sum(1 for r in rs if r.get("termination") == "token_cap"),
            "context_exceeded": sum(1 for r in rs if r.get("termination") == "context_exceeded"),
            "collateral_damage": sum(1 for r in rs if r.get("collateral_damage")),
            "complete_task_not_called": sum(1 for r in rs if not r.get("complete_task_called")),
            "fs_probe": sum(1 for r in rs if r.get("fs_probe")),
            "infra_retries": sum(int(r.get("attempt") or 0) for r in rs),
            "agent_cost_usd": "n/a (unpriced)"}


def main() -> int:
    if (os.stat(P.ROOT_FULL).st_mode & 0o777) == 0:
        os.chmod(P.ROOT_FULL, 0o755)
    try:
        ids = P.read_split("test_normal", P.ROOT_FULL)
        diff = {t: json.loads((P.ROOT_FULL / "data/tasks" / t / "ground_truth/metadata.json").read_text())["difficulty"]
                for t in ids}
    finally:
        if os.environ.get("AW_RELOCK") == "1":
            os.chmod(P.ROOT_FULL, 0o000)
    scen = defaultdict(list)
    for t in ids:
        scen[t.split("_")[0]].append(t)
    scen = dict(scen)
    d = load(ids)
    succ, raw = d["succ"], d["raw"]
    picks = resamples(scen)
    res: dict = {"n_tasks": len(ids), "n_scenarios": len(scen), "trials": K, "cells": len(d["order"]),
                 "records": d["n_records"], "bootstrap_resamples": B, "arms": {}, "vs_seed": {}, "pairs": {},
                 "stochastic": {}, "trial_sensitivity": {}}
    for a in ARMS:
        res["arms"][a] = per_arm(succ, raw, a, ids, scen, diff)
        res["stochastic"][a] = stochastic(succ, a, ids)
    boots = {}
    for a, b in itertools.combinations(ARMS, 2):
        dt, ds = boot_pair(succ, a, b, scen, picks)
        boots[(a, b)] = dt
        res["pairs"][f"{a} − {b}"] = {"a": a, "b": b, "d_tgc": res["arms"][a]["tgc"] - res["arms"][b]["tgc"],
                                     "ci_tgc": ci(dt), "p_tgc": p_two_sided(dt),
                                     "d_sgc": res["arms"][a]["sgc"] - res["arms"][b]["sgc"], "ci_sgc": ci(ds)}
    hk = holm({k: v["p_tgc"] for k, v in res["pairs"].items()})
    for k, v in res["pairs"].items():
        v["holm_significant_tgc"] = hk[k]
    for a in ARMS[1:]:
        v = res["pairs"][f"seed − {a}"]
        res["vs_seed"][a] = {"d_tgc": -v["d_tgc"], "ci_tgc": [-v["ci_tgc"][1], -v["ci_tgc"][0]],
                             "d_sgc": -v["d_sgc"], "ci_sgc": [-v["ci_sgc"][1], -v["ci_sgc"][0]],
                             "holm_significant_tgc": v["holm_significant_tgc"]}
    # ranking with uncertainty: arms by TGC, each with a bootstrap CI of its own TGC; arms not separable from the top
    rank = sorted(ARMS, key=lambda a: -res["arms"][a]["tgc"])
    own_ci = {}
    for a in ARMS:
        xs = [tgc(succ, a, [t for s in pick for t in scen[s]]) for pick in picks]
        own_ci[a] = ci(xs)
    top = rank[0]

    def diff_ci(a, b):
        key = f"{a} − {b}" if f"{a} − {b}" in res["pairs"] else f"{b} − {a}"
        c = res["pairs"][key]["ci_tgc"]
        return c if key.startswith(a + " ") else [-c[1], -c[0]]
    res["ranking"] = [{"rank": i + 1, "arm": a, "tgc": res["arms"][a]["tgc"], "ci_tgc": own_ci[a],
                       "not_separable_from_top": a == top or (lambda c: c[0] <= 0 <= c[1])(diff_ci(top, a))}
                      for i, a in enumerate(rank)]
    res["noise_check"] = {"harnesslens − seed": {k: v for k, v in res["pairs"]["seed − harnesslens"].items()
                                                 if k not in ("a", "b")} | {
        "d_tgc": res["arms"]["harnesslens"]["tgc"] - res["arms"]["seed"]["tgc"],
        "ci_tgc": [-res["pairs"]["seed − harnesslens"]["ci_tgc"][1], -res["pairs"]["seed − harnesslens"]["ci_tgc"][0]],
        "d_sgc": res["arms"]["harnesslens"]["sgc"] - res["arms"]["seed"]["sgc"],
        "ci_sgc": [-res["pairs"]["seed − harnesslens"]["ci_sgc"][1], -res["pairs"]["seed − harnesslens"]["ci_sgc"][0]],
        "label": "two byte-identical artifacts in one window: a direct measure of within-window noise"}}
    for n in range(1, K + 1):
        tr = range(n)
        row = {"tgc": {a: tgc(succ, a, ids, tr) for a in ARMS}, "vs_seed": {}}
        for a in ARMS[1:]:
            dt, _ = boot_pair(succ, a, "seed", scen, picks[:2000], tr)
            row["vs_seed"][a] = {"d_tgc": row["tgc"][a] - row["tgc"]["seed"], "ci_tgc": ci(dt),
                                 "bootstrap_resamples": 2000}
        res["trial_sensitivity"][str(n)] = row
    # flakiness vs TGC, difficulty and surface types (across arms)
    fl = {a: res["stochastic"][a]["flaky_share"] for a in ARMS}
    tg = {a: res["arms"][a]["tgc"] for a in ARMS}
    mx, my = statistics.mean(tg.values()), statistics.mean(fl.values())
    cov = sum((tg[a] - mx) * (fl[a] - my) for a in ARMS)
    sx = math.sqrt(sum((tg[a] - mx) ** 2 for a in ARMS))
    sy = math.sqrt(sum((fl[a] - my) ** 2 for a in ARMS))
    by_diff_flaky = {}
    for d_, n in DIFF.items():
        ts = [t for t in ids if diff[t] == d_]
        by_diff_flaky[n] = {a: sum(1 for t in ts if 0 < sum(vals(succ, a, t, range(K), False)) < K) / len(ts)
                            for a in ARMS}
    surf = defaultdict(list)
    for a in ARMS:
        for s in ("P", "T", "M"):
            if s in P.SURFACES_CHANGED[a]:
                surf[s].append(fl[a])
        if P.SURFACES_CHANGED[a] == "none":
            surf["none"].append(fl[a])
    res["flakiness_across_arms"] = {"pearson_tgc_vs_flaky_share": cov / (sx * sy) if sx and sy else None,
                                    "flaky_share_by_difficulty": by_diff_flaky,
                                    "mean_flaky_share_by_surface_changed": {k: statistics.mean(v) for k, v in surf.items()},
                                    "n_arms_by_surface_changed": {k: len(v) for k, v in surf.items()}}
    res["earlier_windows"] = earlier()
    rec = sorted((FINAL / "records").glob("*.json"), key=lambda p: p.stat().st_mtime)
    res["window_wall"] = [P._dt.datetime.utcfromtimestamp(rec[0].stat().st_mtime).isoformat() + "Z",
                          P._dt.datetime.utcfromtimestamp(rec[-1].stat().st_mtime).isoformat() + "Z"] if rec else None
    m = P.manifest()
    res["manifest"] = {k: m.get(k) for k in ("final_order", "issues", "hourly_offset_s", "seed_equals_harnesslens_bytewise")}
    res["artifacts"] = {a: {"rule": v["rule"], "expected": v["expected"], "computed": v["computed"], "source": v["source"],
                            "surfaces_searched": P.SURFACES_OF[a], "surfaces_changed": P.SURFACES_CHANGED[a]}
                        for a, v in (m.get("artifacts") or {}).items()}
    res["lint"] = {a: {"pass": v["pass"], "violations": v["violations"]} for a, v in (m.get("lint") or {}).items()}
    res["spend_per_provider"] = {"RITS (agent, unpriced)": "n/a (unpriced); agent tokens per arm in `arms`",
                                 "optimizer": "none (no optimizer in this plan)"}
    P.write_json(OUT / "analysis.json", res)
    import report
    md = report.combined(res)
    P.atomic_write(OUT / "RESULTS.md", md)
    print(json.dumps({"written": [str(OUT / "analysis.json"), str(OUT / "RESULTS.md")], "records": d["n_records"],
                      "missing": {a: res["arms"][a]["missing"] for a in ARMS}}))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
