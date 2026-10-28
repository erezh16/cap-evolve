"""P8 of the gate arms (docs/ABLATIONS_GATE.md G7): reads AW_STATE/final_gate/{order.json,records/} and the FIRST window's
seed and abl_ref cells (AW_STATE/final, reused, D16); writes final_gate/analysis.json. Counts and rewards only.

  venv-aw/bin/python -I analyze_gate.py

The statistics are analyze.py's own functions, unchanged (scenario-clustered paired bootstrap, 56 clusters, B resamples,
two-sided percentile p, Holm). Cells are keyed (arm, task, trial) in both windows, so every per-task pairing lines up.
Every contrast that involves seed or abl_ref is cross-window and labelled so; abl_nogate − abl_naivegate is in-window.
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
import analyze as A  # noqa: E402
import awrest as P  # noqa: E402

GATE = tuple(P.GATE_ARMS)
REUSED = ("seed", "abl_ref")
FIRST_PRIMARY = ("abl_cc", "abl_prompt", "abl_tools", "abl_notrace", "abl_tracescore")   # the first window's family


def _cells(window: str, arms: set) -> tuple[list, dict]:
    order = P.read_json(P.AW_STATE / window / "order.json")
    recs = {int(p.stem): json.loads(p.read_text()) for p in (P.AW_STATE / window / "records").glob("*.json")}
    cells = {}
    for c in order:
        if c["arm"] in arms:
            r = recs.get(c["idx"])
            cells[(c["arm"], c["task_id"], c["trial"])] = r if r is not None else {"infra_error": "never ran"}
    return [c for c in order if c["arm"] in arms], cells


def _arm_row(cells, arm, ids, scen, diff) -> dict:
    rs = [r for (a, _, _), r in cells.items() if a == arm and not r.get("infra_error")]

    def mean(k):
        v = [float(r.get(k) or 0) for r in rs]
        return statistics.mean(v) if v else float("nan")
    return {"tgc": A.tgc(cells, arm, ids), "sgc": A.sgc(cells, arm, scen),
            "tgc_drop_missing": A.tgc(cells, arm, ids, True), "sgc_drop_missing": A.sgc(cells, arm, scen, True),
            "by_difficulty": {n: A.by_difficulty(cells, arm, ids, scen, diff, d) for d, n in A.DIFF.items()},
            "episodes": len(rs),
            "missing": sum(1 for (a, _, _), r in cells.items() if a == arm and r.get("infra_error")),
            "infra_retries": sum(int(r.get("attempt") or 0) for r in rs),
            "context_exceeded": sum(1 for r in rs if r.get("termination") == "context_exceeded"),
            "prompt_tokens_per_task": mean("prompt_tokens"), "completion_tokens_per_task": mean("completion_tokens"),
            "steps_per_task": mean("n_steps"), "episode_seconds": mean("episode_seconds"),
            "trials_agree_share": sum(1 for t in ids if A.succ(cells, arm, t, 0) == A.succ(cells, arm, t, 1)) / len(ids),
            "pass_fraction": (sum(int(r.get("pass_count") or 0) for r in rs)
                              / max(1, sum(int(r.get("num_tests") or 0) for r in rs)))}


def main() -> int:
    os.chmod(P.ROOT_FULL, 0o755) if (os.stat(P.ROOT_FULL).st_mode & 0o777) == 0 else None
    try:
        ids = P.read_split("test_normal", P.ROOT_FULL)
        diff = {t: json.loads((P.ROOT_FULL / "data/tasks" / t / "ground_truth/metadata.json").read_text())["difficulty"]
                for t in ids}
    finally:
        os.chmod(P.ROOT_FULL, 0o000)
    scen = defaultdict(list)
    for t in ids:
        scen[t.split("_")[0]].append(t)
    og, cg = _cells("final_gate", set(GATE))
    o1, c1 = _cells("final", set(REUSED))
    if len(og) != len(ids) * len(GATE) * A.TRIALS or len(o1) != len(ids) * len(REUSED) * A.TRIALS:
        raise SystemExit(f"cell counts: gate {len(og)}, reused {len(o1)}")
    cells = {**c1, **cg}
    rng = random.Random(0)
    res: dict = {"n_tasks": len(ids), "n_scenarios": len(scen), "trials": A.TRIALS, "bootstrap_resamples": A.B,
                 "windows": {"gate window (2026-10-28)": list(GATE),
                             "reused from the first window (2026-10-27)": list(REUSED)},
                 "cells": {"gate": len(og), "reused": len(o1)}, "arms": {}}
    for arm in REUSED + GATE:
        res["arms"][arm] = _arm_row(cells, arm, ids, scen, diff)
    prim = {}
    for c in GATE:
        ct, cs, pv = A.bootstrap_p(cells, c, "abl_ref", scen, rng)
        prim[c] = {"d_tgc": res["arms"][c]["tgc"] - res["arms"]["abl_ref"]["tgc"], "ci_tgc": ct,
                   "d_sgc": res["arms"][c]["sgc"] - res["arms"]["abl_ref"]["sgc"], "ci_sgc": cs, "p_raw": pv,
                   "cross_window": True}
    for c, ph in A.holm({c: v["p_raw"] for c, v in prim.items()}).items():
        prim[c]["p_holm"] = ph
    res["vs_ref"] = prim
    res["vs_seed"] = {}
    for c in GATE:
        ct, cs = A.bootstrap(cells, c, "seed", scen, rng)
        res["vs_seed"][c] = {"d_tgc": res["arms"][c]["tgc"] - res["arms"]["seed"]["tgc"], "ci_tgc": ct,
                             "d_sgc": res["arms"][c]["sgc"] - res["arms"]["seed"]["sgc"], "ci_sgc": cs,
                             "cross_window": True}
    ct, cs = A.bootstrap(cells, GATE[0], GATE[1], scen, rng)
    res["pairs"] = {f"{GATE[0]} − {GATE[1]}": {"d_tgc": res["arms"][GATE[0]]["tgc"] - res["arms"][GATE[1]]["tgc"],
                                               "ci_tgc": ct, "d_sgc": res["arms"][GATE[0]]["sgc"] - res["arms"][GATE[1]]["sgc"],
                                               "ci_sgc": cs, "cross_window": False,
                                               "label": "in-window; one search seed each"}}
    # G7: the joint Holm family over all 7 primary contrasts, a labelled secondary (the first five are not re-adjusted)
    first = (P.read_json(P.PUSHED / "final" / "analysis.json", {}) or {}).get("vs_ref") or {}
    joint = {c: first[c]["p_raw"] for c in FIRST_PRIMARY if c in first and first[c].get("p_raw") is not None}
    joint.update({c: prim[c]["p_raw"] for c in GATE})
    res["joint_holm_7"] = {"p_holm": A.holm(joint), "label": "secondary: Holm over the 5 first-wave and 2 gate contrasts"}
    # G7 drift check: a 2x difference in infra-retry or context-exceeded rate between windows is flagged
    ref_rate = {k: (res["arms"]["abl_ref"][k] + res["arms"]["seed"][k]) / max(1, res["arms"]["abl_ref"]["episodes"]
                                                                               + res["arms"]["seed"]["episodes"])
                for k in ("infra_retries", "context_exceeded")}
    gate_rate = {k: sum(res["arms"][c][k] for c in GATE) / max(1, sum(res["arms"][c]["episodes"] for c in GATE))
                 for k in ("infra_retries", "context_exceeded")}
    res["drift_check"] = {"first_window_rate": ref_rate, "gate_window_rate": gate_rate,
                          "flag": [k for k in ref_rate if max(ref_rate[k], gate_rate[k]) > 0
                                   and max(ref_rate[k], gate_rate[k]) > 2 * max(1e-9, min(ref_rate[k], gate_rate[k]))
                                   and abs(ref_rate[k] - gate_rate[k]) * 336 >= 3]}
    res["search"] = {c: A.search_side(c) for c in GATE}
    for c in GATE:   # G2.1: the champion is the last accepted candidate; best_search_score is the best val SEEN
        fz = P.read_json(P.PUSHED / c / "artifact" / "FREEZE.json", {}) or {}
        res["search"][c]["champion_search_score"] = fz.get("champion_val")
        res["search"][c]["champion_search_label"] = "the champion's (last accepted candidate's) val on train ∪ dev"
    P.write_json(P.AW_STATE / "final_gate" / "analysis.json", res)
    P.write_json(P.PUSHED / "final_gate" / "analysis.json", res)
    print(json.dumps({"arms": {a: round(v["tgc"], 4) for a, v in res["arms"].items()},
                      "vs_ref": {c: {k: v[k] for k in ("d_tgc", "ci_tgc", "p_raw", "p_holm")} for c, v in prim.items()},
                      "drift_flag": res["drift_check"]["flag"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
