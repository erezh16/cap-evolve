"""P8: analysis of the one final window of eval REST (docs/EVAL_APPWORLD_REST.md §14, §5.2).

  venv-aw/bin/python -I analyze.py      # reads AW_STATE/final/{order.json,records/}; writes final/analysis.json
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
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import awrest as P  # noqa: E402
sys.path.insert(0, str(HERE.parent / "common"))
import opt_llm  # noqa: E402

ARMS = (tuple(P.REUSED_WINDOW_ARMS) + tuple(P.CANDIDATES)) if getattr(P, "REUSED_WINDOW_ARMS", None) else P.ARMS
TRIALS = 2
DIFF = {1: "Easy", 2: "Medium", 3: "Hard"}
B = int(os.environ.get("AW_BOOTSTRAP", 10000))


def _cells_of(state: Path, arms=None) -> tuple[list, dict]:
    order = P.read_json(state / "final" / "order.json")
    recs = {}
    for p in (state / "final" / "records").glob("*.json"):
        recs[int(p.stem)] = json.loads(p.read_text())
    cells = {}
    for c in order:
        if arms and c["arm"] not in arms:
            continue
        r = recs.get(c["idx"])
        cells[(c["arm"], c["task_id"], c["trial"])] = r if r is not None else {"infra_error": "never ran"}
    return order, cells


def load():
    order, cells = _cells_of(P.AW_STATE)
    if getattr(P, "REUSED_WINDOW_ARMS", None):
        # CE3 §2: the seed, ce2_k1 and ce2_k2 test_normal cells of CE2's window, reused (trusted script; counters and
        # flags only), keyed (arm, task, trial) like this window's cells, so every per-task pairing lines up
        o2, c2 = _cells_of(P.CE2_HOME / "state", set(P.REUSED_WINDOW_ARMS))
        cells.update(c2)
        order = order + [c for c in o2 if c["arm"] in P.REUSED_WINDOW_ARMS]
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


def bootstrap_p(cells, a, b, scen, rng):
    """ABLATIONS §15: the same scenario-clustered paired bootstrap, with a two-sided percentile p-value for TGC
    (p = 2·min(P(Δ* ≤ 0), P(Δ* ≥ 0)), capped at 1)."""
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
    p = min(1.0, 2 * min(sum(1 for x in dt if x <= 0), sum(1 for x in dt if x >= 0)) / B)
    return ci(dt), ci(ds), p


def holm(ps: dict) -> dict:
    """Holm step-down adjusted p-values over one family."""
    order = sorted(ps, key=lambda k: ps[k])
    m, out, run = len(order), {}, 0.0
    for i, k in enumerate(order):
        run = max(run, min(1.0, (m - i) * ps[k]))
        out[k] = run
    return out


def by_difficulty(cells, arm, ids, scen, diff, d) -> dict:
    """TGC over the tasks of difficulty d; SGC over the scenarios whose tasks are all of difficulty d."""
    ts = [t for t in ids if diff[t] == d]
    sc = {s: v for s, v in scen.items() if all(diff[t] == d for t in v)}
    return {"n": len(ts), "tgc": tgc(cells, arm, ts), "n_scenarios": len(sc), "sgc": sgc(cells, arm, sc) if sc else None}


def _q(xs: list[float], q: float):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def _dist(rows: list[dict], k: str) -> dict:
    v = [float(r[k]) for r in rows if r.get(k) is not None]
    return {"mean": round(statistics.mean(v), 1) if v else None, "p50": _q(v, 0.5), "p90": _q(v, 0.9)}


def search_side(c: str) -> dict:
    """§5.2 search-phase rows, from shared code only: the evaluator's rollouts/cache/lint logs and the usage log."""
    u = P.read_jsonl(P.AW_STATE / c / "optimizer_usage.jsonl")
    ro = P.read_jsonl(P.AW_STATE / c / "rollouts.jsonl")
    t = opt_llm.totals(c)
    models = sorted({r.get("model") for r in u if r.get("model")})
    roles: dict = defaultdict(lambda: {"calls": 0, "in": 0, "out": 0, "cache_read": 0, "cache_write": 0})
    for r in u:
        x = roles[r.get("role") or "?"]
        x["calls"] += 1
        x["in"] += int(r.get("prompt_tokens") or 0)
        x["out"] += int(r.get("completion_tokens") or 0)
        x["cache_read"] += int(r.get("cache_read") or 0)
        x["cache_write"] += int(r.get("cache_write") or 0)
    secs = [float(r.get("seconds") or 0) for r in u]
    fz = P.read_json(P.PUSHED / c / "artifact" / "FREEZE.json", {}) or {}
    extra = {}
    if P.LEDGER_PREFIX == "CE2":
        pr = P.read_json(P.PUSHED / c / "progress.json", {}) or {}
        mu: dict = defaultdict(lambda: {"in": 0, "out": 0, "cache_read": 0, "cache_write": 0, "results": 0})
        for f in sorted((P.AW_STATE / c / "claude_calls").glob("*.json")):
            d = json.loads(f.read_text())
            for m, v in (d.get("modelUsage") or {}).items():
                x = mu[m]
                x["results"] += 1
                x["in"] += int(v.get("inputTokens") or 0)
                x["out"] += int(v.get("outputTokens") or 0)
                x["cache_read"] += int(v.get("cacheReadInputTokens") or 0)
                x["cache_write"] += int(v.get("cacheCreationInputTokens") or 0)
        extra = {"iterations": pr.get("iterations"), "iterations_done": pr.get("iterations_done"),
                 "iterations_consumed": pr.get("iterations_consumed"), "accepted": pr.get("accepted"),
                 "best_search_score": pr.get("best_search_score"), "metric_calls": pr.get("metric_calls"),
                 "capevolve_optimizer_usd": pr.get("capevolve_optimizer_usd"), "model_usage_by_model": dict(mu),
                 "k_se": P.K_SE.get(c)}                    # abl_cc has no gate (None)
        if c == "abl_cc":                                  # ABLATIONS §10.2 report: evaluations, not iterations
            extra.update({k: pr.get(k) for k in ("evaluations_done", "evaluation_requests", "refused", "lint_rejects",
                                                 "evaluations", "max_turns")})
    return {"optimizer": {"calls": len(u), "errors": sum(1 for r in u if r.get("error")), "models": models,
                          "input_tokens": t["prompt_tokens"], "output_tokens": t["completion_tokens"],
                          "cache_read_tokens": t["cache_read"], "cache_write_tokens": t["cache_write"],
                          "proxy_usd": opt_llm.proxy_usd(t),
                          "cli_reported_usd": round(sum(float(r.get("total_cost_usd") or 0) for r in u), 2) or None,
                          "per_role": dict(roles), "call_seconds_mean": round(statistics.mean(secs), 1) if secs else None,
                          "call_seconds_p90": _q(secs, 0.9), "optimizer_seconds_total": round(sum(secs))},
            "rollouts": {"counted": len(ro), "cache_hits": len(P.read_jsonl(P.AW_STATE / c / "cache_hits.jsonl")),
                         "lint_reject_batches": len(P.read_jsonl(P.AW_STATE / c / "lint_rejects.jsonl")),
                         "infra": sum(1 for r in ro if r.get("infra")),
                         "mean_reward_counted": round(statistics.mean([r["reward"] for r in ro]), 4) if ro else None,
                         "prompt_tokens": _dist(ro, "prompt_tokens"), "completion_tokens": _dist(ro, "completion_tokens"),
                         "max_prompt_tokens": max((int(r.get("max_prompt_tokens") or 0) for r in ro), default=0),
                         "steps": _dist(ro, "steps"), "episode_seconds": _dist(ro, "seconds"),
                         "step_cap_hits": sum(1 for r in ro if r.get("termination") == "max_steps"),
                         "token_cap_hits": sum(1 for r in ro if r.get("termination") == "token_cap"),
                         "context_exceeded": sum(1 for r in ro if r.get("termination") == "context_exceeded"),
                         "search_wall": [ro[0]["t"], ro[-1]["t"]] if ro else None},
            "champion_search_score": fz.get("search_score"), "champion_search_label": fz.get("search_label"),
            "time_to_champion": fz.get("time_to_champion"), "freeze": fz, **extra}


def seed_baseline() -> dict:
    if P.LEDGER_PREFIX == "CE2":   # reused from REST P3 (plan 7.4): its pushed aggregates, labelled
        r = subprocess.run(["git", "-C", str(P.REPO), "show",
                            "origin/eval-rest:docs/EVAL_APPWORLD_REST_STATE/seed/baseline.json"],
                           capture_output=True, text=True)
        return {"label": "reused from REST P3 (2026-10-20), not re-run, not counted",
                **(json.loads(r.stdout) if r.returncode == 0 else {}), "reuse_check": P.read_json(P.AW_STATE / "seed_reuse.json", {})}
    ro = P.read_jsonl(P.AW_STATE / "seed" / "rollouts.jsonl")
    tr, dv = set(P.read_split("train")), set(P.read_split("dev"))
    return {"rollouts": len(ro), "prompt_tokens": _dist(ro, "prompt_tokens"), "episode_seconds": _dist(ro, "seconds"),
            **(P.read_json(P.PUSHED / "seed" / "baseline.json", {}) or {})}


def dev_diag() -> dict:
    prog = P.read_json(P.PUSHED / "p5dev" / "progress.json", {}) or {}
    return {a: v.get("tgc") for a, v in (prog.get("per_arm") or {}).items()}


def usd(o: dict) -> str:
    """The list-price proxy (Sonnet 5.5: $2 in, $10 out, $0.20 cache read, $2.50 cache write per MTok), plus the
    CLI-reported total where a CLI was used (labelled)."""
    return f"${o['proxy_usd']} (proxy)" + (f"; ${o['cli_reported_usd']} (CLI-reported)" if o.get("cli_reported_usd") else "")


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

        def q(k, x):
            return _q([float(r.get(k) or 0) for r in rs], x)
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
            "prompt_tokens_p50": q("prompt_tokens", 0.5), "prompt_tokens_p90": q("prompt_tokens", 0.9),
            "completion_tokens_p50": q("completion_tokens", 0.5), "completion_tokens_p90": q("completion_tokens", 0.9),
            "episode_seconds_p50": q("episode_seconds", 0.5), "episode_seconds_p90": q("episode_seconds", 0.9),
            "pass_fraction": (sum(int(r.get("pass_count") or 0) for r in rs) / max(1, sum(int(r.get("num_tests") or 0) for r in rs))),
            "infra_retries": sum(int(r.get("attempt") or 0) for r in rs)}
    cross = bool(getattr(P, "REUSED_WINDOW_ARMS", None))
    for c in P.CANDIDATES:
        ct, cs = bootstrap(cells, c, "seed", scen, rng)
        res["vs_seed"][c] = {"d_tgc": res["arms"][c]["tgc"] - res["arms"]["seed"]["tgc"], "ci_tgc": ct,
                             "d_sgc": res["arms"][c]["sgc"] - res["arms"]["seed"]["sgc"], "ci_sgc": cs,
                             "cross_window": cross}
    if cross:   # CE3 §2: the new arm against the reused CE2 champions, same bootstrap, labelled cross-window
        res["pairs"] = {}
        for c in P.CANDIDATES:
            for o in P.REUSED_WINDOW_ARMS:
                if o == "seed":
                    continue
                ct, cs = bootstrap(cells, c, o, scen, rng)
                res["pairs"][f"{c} − {o}"] = {"d_tgc": res["arms"][c]["tgc"] - res["arms"][o]["tgc"], "ci_tgc": ct,
                                               "d_sgc": res["arms"][c]["sgc"] - res["arms"][o]["sgc"], "ci_sgc": cs,
                                               "cross_window": True,
                                               "label": "cross-window: the reused arm ran in CE2's window (2026-10-23)"}
        res["windows"] = {"this window": list(P.CANDIDATES), "reused from CE2's window (2026-10-23)": list(P.REUSED_WINDOW_ARMS)}
    if P.LEDGER_ID == "ABL":    # ABLATIONS §15: primary 5 (each ablation − abl_ref, raw and Holm p), two secondary pairs
        prim = {}
        for c in [x for x in P.CANDIDATES if x != "abl_ref"]:
            ct, cs, pv = bootstrap_p(cells, c, "abl_ref", scen, rng)
            prim[c] = {"d_tgc": res["arms"][c]["tgc"] - res["arms"]["abl_ref"]["tgc"], "ci_tgc": ct,
                       "d_sgc": res["arms"][c]["sgc"] - res["arms"]["abl_ref"]["sgc"], "ci_sgc": cs, "p_raw": pv}
        for c, ph in holm({c: v["p_raw"] for c, v in prim.items()}).items():
            prim[c]["p_holm"] = ph
        res["vs_ref"] = prim
        res["pairs"] = {}
        for a1, a2 in (("abl_prompt", "abl_tools"), ("abl_notrace", "abl_tracescore")):
            ct, cs = bootstrap(cells, a1, a2, scen, rng)
            res["pairs"][f"{a1} − {a2}"] = {"d_tgc": res["arms"][a1]["tgc"] - res["arms"][a2]["tgc"], "ci_tgc": ct,
                                             "d_sgc": res["arms"][a1]["sgc"] - res["arms"][a2]["sgc"], "ci_sgc": cs,
                                             "label": "secondary; one search seed each"}
    if P.LEDGER_ID == "CE2" and not cross:   # CE2 §16: ce2_k2 − ce2_k1, same bootstrap (confounds K with search randomness)
        a2, a1 = P.CANDIDATES[1], P.CANDIDATES[0]
        ct, cs = bootstrap(cells, a2, a1, scen, rng)
        res["k2_vs_k1"] = {"d_tgc": res["arms"][a2]["tgc"] - res["arms"][a1]["tgc"], "ci_tgc": ct,
                           "d_sgc": res["arms"][a2]["sgc"] - res["arms"][a1]["sgc"], "ci_sgc": cs,
                           "label": "ce2_k2 − ce2_k1; one search seed each: K is confounded with search randomness"}
    for x in getattr(P, "EXTRA_WINDOW_ARMS", ()):   # ABL-0485: window-only arm, secondary; not in the Holm family
        ct, cs = bootstrap(cells, x, "seed", scen, rng)
        res["vs_seed"][x] = {"d_tgc": res["arms"][x]["tgc"] - res["arms"]["seed"]["tgc"], "ci_tgc": ct,
                             "d_sgc": res["arms"][x]["sgc"] - res["arms"]["seed"]["sgc"], "ci_sgc": cs}
        for other in ("abl_ref", "abl_cc"):
            ct, cs = bootstrap(cells, x, other, scen, rng)
            res.setdefault("pairs", {})[f"{x} − {other}"] = {
                "d_tgc": res["arms"][x]["tgc"] - res["arms"][other]["tgc"], "ci_tgc": ct,
                "d_sgc": res["arms"][x]["sgc"] - res["arms"][other]["sgc"], "ci_sgc": cs,
                "label": "secondary (ABL-0485): abl_cc's best-evaluated candidate, chosen after its search"}
    res["search"] = {c: search_side(c) for c in P.CANDIDATES}
    if cross:   # the reused arms' search-side rows, from CE2's pushed analysis (aggregates only)
        ce2a = P.read_json(P.CE2_PUSHED / "final" / "analysis.json", {}) or {}
        res["search_reused_ce2"] = {k: v for k, v in (ce2a.get("search") or {}).items() if k in P.REUSED_WINDOW_ARMS}
    res["seed_baseline"] = seed_baseline()
    res["spend_per_provider"] = {"RITS (agent, unpriced)": "n/a (unpriced); tokens in the arm tables",
                                 "gateway (optimizer)": {c: res["search"][c]["optimizer"]["proxy_usd"] for c in P.CANDIDATES}}
    rec = sorted((P.AW_STATE / "final" / "records").glob("*.json"), key=lambda p: p.stat().st_mtime)
    res["window_wall"] = [P._dt.datetime.utcfromtimestamp(rec[0].stat().st_mtime).isoformat() + "Z",
                          P._dt.datetime.utcfromtimestamp(rec[-1].stat().st_mtime).isoformat() + "Z"] if rec else None
    res["dev_diagnostic_tgc"] = dev_diag()
    m = P.manifest()
    res["manifest"] = {k: m.get(k) for k in ("appworld", "candidates", "m_cap", "final_order", "freeze", "opt_model",
                                             "agent_model", "budget", "trials", "prices_usd_per_mtok")}
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
        tag = " (reused, CE2 window)" if a in getattr(P, "REUSED_WINDOW_ARMS", ()) else ""
        L.append(f"| {a}{tag} | {pct(r['tgc'])} | {pct(r['sgc'])} | {dt} | {ds} | {r['missing']} |")
    for lab, v in (res.get("pairs") or {}).items() if "vs_ref" not in res else ():   # ABL: printed with vs_ref below
        L += ["", f"{lab}: Δ TGC {pct(v['d_tgc'])} [{pct(v['ci_tgc'][0])}, {pct(v['ci_tgc'][1])}], "
                  f"Δ SGC {pct(v['d_sgc'])} [{pct(v['ci_sgc'][0])}, {pct(v['ci_sgc'][1])}] ({v['label']})."]
    if getattr(P, "REUSED_WINDOW_ARMS", ()):
        L += ["", "Every Δ in this table compares an arm of this window with an arm of CE2's window (2026-10-23): "
                  "cross-window, so it includes window-to-window drift (CE2's predecessors measured 4–6 TGC points for "
                  "identical artifacts)."]
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
    O = ["| candidate | counted rollouts (of 900) | cache hits | lint rejects | optimizer calls | input tok | output tok | cache-read tok | cache-write tok | USD | optimizer s |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in P.CANDIDATES:
        o, rr = res["search"][c]["optimizer"], res["search"][c]["rollouts"]
        O.append(f"| {c} | {rr['counted']} | {rr['cache_hits']} | {rr['lint_reject_batches']} | {o['calls']} | {o['input_tokens']:,} | "
                 f"{o['output_tokens']:,} | {o['cache_read_tokens']:,} | {o['cache_write_tokens']:,} | {usd(o)} | {o['optimizer_seconds_total']:,} |")
    if "vs_ref" in res:   # ABLATIONS §15: the five primary contrasts, raw and Holm p; the secondary pairs
        L += ["", "| ablation − abl_ref (primary) | Δ TGC [95% CI] | Δ SGC [95% CI] | p raw | p Holm |", "|---|---|---|---|---|"]
        for c, v in res["vs_ref"].items():
            L.append(f"| {c} | {pct(v['d_tgc'])} [{pct(v['ci_tgc'][0])}, {pct(v['ci_tgc'][1])}] | {pct(v['d_sgc'])} "
                     f"[{pct(v['ci_sgc'][0])}, {pct(v['ci_sgc'][1])}] | {v['p_raw']:.4f} | {v['p_holm']:.4f} |")
        for lab, v in res.get("pairs", {}).items():
            L.append(f"\n{lab} (secondary): Δ TGC {pct(v['d_tgc'])} [{pct(v['ci_tgc'][0])}, {pct(v['ci_tgc'][1])}], "
                     f"Δ SGC {pct(v['d_sgc'])} [{pct(v['ci_sgc'][0])}, {pct(v['ci_sgc'][1])}].")
    if "k2_vs_k1" in res:
        v = res["k2_vs_k1"]
        L.append("")
        L.append(f"ce2_k2 − ce2_k1: Δ TGC {pct(v['d_tgc'])} [{pct(v['ci_tgc'][0])}, {pct(v['ci_tgc'][1])}], "
                 f"Δ SGC {pct(v['d_sgc'])} [{pct(v['ci_sgc'][0])}, {pct(v['ci_sgc'][1])}] ({v['label']}).")
    head = (f"## Final window(s): test_normal, 168 tasks / 56 scenarios × 2 trials; {', '.join(P.CANDIDATES)} run in this "
            f"window, {', '.join(P.REUSED_WINDOW_ARMS)} reused from CE2's window" if getattr(P, "REUSED_WINDOW_ARMS", ()) else
            f"## Final window: test_normal, 168 tasks / 56 scenarios × 2 trials × {len(ARMS)} arms")
    md = (head + "\n\n" + "\n".join(L)
          + "\n\n## TGC by difficulty\n\n" + "\n".join(D) + "\n\n## Agent cost, tokens and latency per episode (final window)\n\n"
          + "\n".join(C) + ("\n\n## Optimizer side (search; seed baseline reused from REST P3, not counted)\n\n" if P.LEDGER_PREFIX == "CE2" else "\n\n## Optimizer side (search; shared seed baseline of 147 rollouts counted once, not charged)\n\n") + "\n".join(O) + "\n")
    P.atomic_write(P.PUSHED / "final" / "RESULTS.md", md)
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
