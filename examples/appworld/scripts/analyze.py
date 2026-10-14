"""P9 analysis (plan §12): TGC, SGC, by difficulty, paired Δ (ace − seed) with a scenario-clustered
paired bootstrap 95% CI (10,000 resamples), trial agreement, cost table. Reads only rewards, counters
and infra flags from the final records. Writes the pushed analysis.json (aggregates only).
"""

from __future__ import annotations

import json
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "scripts"))
import awpaths as P  # noqa: E402

ARMS = ("seed", "ace")
B = 10_000
SEED = 804009


def load(records_dir: Path, order: list[dict]):
    cells = {}
    for c in order:
        p = records_dir / f"{c['idx']}.json"
        r = json.loads(p.read_text()) if p.exists() else None
        cells[(c["arm"], c["task_id"], c["trial"])] = r
    return cells


def metrics(cells, tasks, trials, arm, missing_as_zero=True):
    """TGC = mean over tasks of the mean over trials of success; SGC per trial over scenarios, averaged."""
    def s(t, k):
        r = cells[(arm, t, k)]
        if r is None or r.get("infra_error"):
            return 0.0 if missing_as_zero else None
        return 1.0 if r.get("success") else 0.0
    per_task = []
    for t in tasks:
        v = [s(t, k) for k in range(trials)]
        v = [x for x in v if x is not None]
        if v:
            per_task.append(sum(v) / len(v))
    tgc = 100 * statistics.mean(per_task) if per_task else float("nan")
    scen = defaultdict(list)
    for t in tasks:
        scen[t.split("_")[0]].append(t)
    sgc_k = []
    for k in range(trials):
        sgc_k.append(statistics.mean(1.0 if all(s(t, k) == 1.0 for t in ts) else 0.0 for ts in scen.values()))
    return tgc, 100 * statistics.mean(sgc_k)


def bootstrap(cells, tasks, trials):
    scen = defaultdict(list)
    for t in tasks:
        scen[t.split("_")[0]].append(t)
    keys = sorted(scen)
    rng = random.Random(SEED)
    d_t, d_s = [], []
    for _ in range(B):
        pick = [rng.choice(keys) for _ in keys]  # resampled scenarios may repeat
        tg, sg = {}, {}
        for arm in ARMS:
            per_task, sgc_k = [], [[] for _ in range(trials)]
            for k in pick:
                tv = []
                for t in scen[k]:
                    v = [1.0 if (cells[(arm, t, j)] or {}).get("success") and not (cells[(arm, t, j)] or {}).get("infra_error") else 0.0
                         for j in range(trials)]
                    per_task.append(sum(v) / trials)
                    tv.append(v)
                for j in range(trials):
                    sgc_k[j].append(1.0 if all(v[j] == 1.0 for v in tv) else 0.0)
            tg[arm] = 100 * statistics.mean(per_task)
            sg[arm] = 100 * statistics.mean(statistics.mean(x) for x in sgc_k)
        d_t.append(tg["ace"] - tg["seed"])
        d_s.append(sg["ace"] - sg["seed"])
    q = lambda xs, p: sorted(xs)[int(p * (len(xs) - 1))]  # noqa: E731
    return {"tgc": [q(d_t, 0.025), q(d_t, 0.975)], "sgc": [q(d_s, 0.025), q(d_s, 0.975)], "resamples": B,
            "clusters": len(keys)}


def main() -> int:
    order = json.loads((P.AW_STATE / "final" / "order.json").read_text())
    cells = load(P.AW_STATE / "final" / "records", order)
    tasks = sorted({c["task_id"] for c in order})
    trials = 1 + max(c["trial"] for c in order)
    out = {"n_tasks": len(tasks), "n_scenarios": len({t.split('_')[0] for t in tasks}), "trials": trials, "arms": {}}
    diff = {}
    for t in tasks:
        r = cells[("seed", t, 0)] or cells[("ace", t, 0)] or {}
        diff[t] = r.get("difficulty")
    for arm in ARMS:
        tgc, sgc = metrics(cells, tasks, trials, arm)
        tgc_s, sgc_s = metrics(cells, tasks, trials, arm, missing_as_zero=False)
        recs = [cells[(arm, t, k)] for t in tasks for k in range(trials)]
        ok = [r for r in recs if r]
        by = {}
        for lvl, name in ((1, "easy"), (2, "medium"), (3, "hard")):
            ts = [t for t in tasks if diff.get(t) == lvl]
            if ts:
                a, b = metrics(cells, ts, trials, arm)
                by[name] = {"n": len(ts), "tgc": round(a, 1), "sgc": round(b, 1)}
        agree = statistics.mean(
            1.0 if len({bool((cells[(arm, t, k)] or {}).get("success")) for k in range(trials)}) == 1 else 0.0 for t in tasks)
        out["arms"][arm] = {
            "tgc": round(tgc, 1), "sgc": round(sgc, 1), "tgc_missing_excluded": round(tgc_s, 1),
            "sgc_missing_excluded": round(sgc_s, 1), "by_difficulty": by,
            "cells": len(recs), "missing_infra": sum(1 for r in recs if not r or r.get("infra_error")),
            "infra_retries": sum((r or {}).get("infra_retries", 0) for r in recs),
            "context_exceeded": sum(1 for r in ok if r.get("termination") == "context_exceeded"),
            "step_cap": sum(1 for r in ok if r.get("termination") == "step_cap"),
            "token_cap": sum(1 for r in ok if r.get("termination") == "token_cap"),
            "mean_steps": round(statistics.mean(r.get("steps") or 0 for r in ok), 2),
            "mean_prompt_tokens_per_task": round(statistics.mean(r.get("prompt_tokens_sum") or 0 for r in ok)),
            "mean_completion_tokens_per_task": round(statistics.mean(r.get("completion_tokens") or 0 for r in ok)),
            "max_prompt_tokens": max((r.get("prompt_tokens_max") or 0) for r in ok),
            "fs_probe_hits": sum(1 for r in ok if r.get("fs_probe")),
            "trial_agreement": round(100 * agree, 1),
        }
    a, s = out["arms"]["ace"], out["arms"]["seed"]
    out["delta"] = {"tgc": round(a["tgc"] - s["tgc"], 1), "sgc": round(a["sgc"] - s["sgc"], 1),
                    "ci95": {k: [round(x, 1) for x in v] if isinstance(v, list) else v
                             for k, v in bootstrap(cells, tasks, trials).items()}}
    prog = P.read_json(P.PUSHED / "ace" / "progress.json")
    out["optimizer"] = {"spend": prog["spend"], "rows": len(prog["rows"])}
    P.write_json(P.PUSHED / "final" / "analysis.json", out)
    print(json.dumps(out, indent=1))
    if "--checkpoint" in sys.argv:
        import status_doc
        status_doc.append(
            "phase_done", "P9", "analysis",
            f"Analysis done (held-out test_normal, {out['n_tasks']} tasks / {out['n_scenarios']} scenarios × {trials} trials):\n"
            f"| arm | TGC | SGC |\n|---|---|---|\n| seed | {s['tgc']} | {s['sgc']} |\n| ace | {a['tgc']} | {a['sgc']} |\n"
            f"Δ ace − seed: TGC {out['delta']['tgc']:+} [{out['delta']['ci95']['tgc'][0]:+}, {out['delta']['ci95']['tgc'][1]:+}], "
            f"SGC {out['delta']['sgc']:+} [{out['delta']['ci95']['sgc'][0]:+}, {out['delta']['ci95']['sgc'][1]:+}] "
            f"(scenario-clustered paired bootstrap, 95%).\nNext: P10 report.",
            done_through="P9/analysis", next_unit="P10/report", extra={"results": {"seed": [s["tgc"], s["sgc"]],
            "ace": [a["tgc"], a["sgc"]], "delta": out["delta"]}}, artifacts=["STATE/final/analysis.json"],
            subject="analysis")
    return 0


if __name__ == "__main__":
    sys.exit(main())
