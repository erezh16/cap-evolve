#!/usr/bin/env python3
"""TEST_ABL §11 (window 2): cross-window contrasts of the gate arms with window 1's arms. Trusted script (rule R1).

  . examples/appworld/test_abl/env.sh && $VENV_AW/bin/python -I examples/appworld/test_abl/analyze_cross.py [--post]

Both windows ran every (task, trial) with the same trial seed (7000 + k), so each gate arm is paired with `abl_ref`
and the seed on the same (task, trial) cells and compared with the same scenario-clustered paired bootstrap as
analyze_all.py (56 scenarios, 10,000 resamples, random.Random(0)). Primary: abl_nogate − abl_ref and
abl_naivegate − abl_ref, Holm over the 2. Secondary: each gate arm − seed. Labelled cross-window throughout, with
each window's infra-retry rate as a drift check (a rate differing by more than 2x is flagged). Context: the gate
run's own window (2 trials, seeds 5000 + k). Reads the two windows' orders and records (counters only); writes
docs/TEST_ABL_STATE/final2/cross_window.json and CROSS_WINDOW.md, aggregates only. --post comments on #948 and #949.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(EX / "scripts"), str(EX / "test_all")]
import awrest as P  # noqa: E402
import analyze_all as AA  # noqa: E402

K = 5
REF, SEED = "abl_ref", "seed"
GATE = ("abl_nogate", "abl_naivegate")


def load(d: str) -> tuple[dict, dict, set]:
    """succ[arm][task] = K values (1.0 / 0.0 / None for infra-missing); per-arm infra retry rate; task ids."""
    order = P.read_json(P.AW_STATE / d / "order.json")
    recs = {int(p.stem): json.loads(p.read_text()) for p in (P.AW_STATE / d / "records").glob("*.json")}
    succ = defaultdict(lambda: defaultdict(lambda: [None] * K))
    retries, n = defaultdict(int), defaultdict(int)
    for c in order:
        r = recs.get(c["idx"])
        n[c["arm"]] += 1
        if r is None:
            continue
        retries[c["arm"]] += int(r.get("attempt") or 0)
        if not r.get("infra_error"):
            succ[c["arm"]][c["task_id"]][c["trial"]] = 1.0 if r.get("success") else 0.0
    return succ, {a: retries[a] / max(1, n[a]) for a in n}, {c["task_id"] for c in order}


def main() -> int:
    s1, rate1, ids1 = load("final")
    s2, rate2, ids2 = load("final2")
    if ids1 != ids2:
        raise SystemExit("the two windows do not cover the same test tasks")
    ids = sorted(ids1)
    succ = {a: dict(s1[a]) for a in (REF, SEED)} | {a: dict(s2[a]) for a in GATE}
    for a in succ:
        for t in ids:
            succ[a].setdefault(t, [None] * K)
    scen = defaultdict(list)
    for t in ids:
        scen[t.split("_")[0]].append(t)
    scen = dict(scen)
    picks = AA.resamples(scen)
    pc = lambda x: None if x is None else round(x, 4)  # noqa: E731
    res = {"label": "cross-window: gate arms from window 2 (2026-11-01), abl_ref and seed from window 1 "
                    "(2026-10-28/30); same tasks and trial seeds 7000 + k",
           "n_tasks": len(ids), "n_scenarios": len(scen), "trials": K, "bootstrap_resamples": AA.B,
           "tgc": {a: pc(AA.tgc(succ, a, ids)) for a in succ}, "sgc": {a: pc(AA.sgc(succ, a, scen)) for a in succ},
           "vs_ref": {}, "vs_seed": {}}
    for a in GATE:
        for b, key in ((REF, "vs_ref"), (SEED, "vs_seed")):
            dt, ds = AA.boot_pair(succ, a, b, scen, picks)
            res[key][a] = {"d_tgc": AA.tgc(succ, a, ids) - AA.tgc(succ, b, ids), "ci_tgc": AA.ci(dt),
                           "p_tgc": AA.p_two_sided(dt),
                           "d_sgc": AA.sgc(succ, a, scen) - AA.sgc(succ, b, scen), "ci_sgc": AA.ci(ds)}
    hk = AA.holm({a: v["p_tgc"] for a, v in res["vs_ref"].items()})
    for a, v in res["vs_ref"].items():
        v["holm_significant_tgc"] = hk[a]
    r1, r2 = (rate1.get(REF, 0) + rate1.get(SEED, 0)) / 2, sum(rate2.get(a, 0) for a in GATE) / 2
    res["drift_check"] = {"infra_retries_per_cell_window1_ref_seed": round(r1, 4),
                          "infra_retries_per_cell_window2_gate": round(r2, 4),
                          "flag_more_than_2x": bool(max(r1, r2) > 2 * max(min(r1, r2), 1e-9) and max(r1, r2) > 0.01)}
    g = subprocess.run(["git", "-C", str(P.REPO), "show",
                        "fork/eval-abl:docs/ABLATION_STATUS_STATE/final_gate/analysis.json"],
                       capture_output=True, text=True)
    ga = (json.loads(g.stdout).get("arms") if g.returncode == 0 else {}) or {}
    res["gate_run_window_context"] = {a: (ga.get(a) or {}).get("tgc") for a in GATE + (REF, SEED)}
    out = P.PUSHED / "final2"
    P.write_json(out / "cross_window.json", res)
    md = report(res)
    P.atomic_write(out / "CROSS_WINDOW.md", md)
    print(json.dumps({"tgc": res["tgc"], "vs_ref": {a: (round(v["d_tgc"], 4), [round(c, 4) for c in v["ci_tgc"]],
                                                        v["holm_significant_tgc"]) for a, v in res["vs_ref"].items()},
                      "drift": res["drift_check"]}))
    if "--post" in sys.argv:
        import post
        print(json.dumps(post.post_all("results_cross", "{NAME}: cross-window comparison with abl_ref and the seed",
                                       lambda a: arm_body(res, a), arms=list(GATE))))
    return 0


def _p(x):
    return "n/a" if x is None else f"{100 * x:.1f}"


def _ci(c):
    return f"[{_p(c[0])}, {_p(c[1])}]"


def table(res: dict) -> str:
    L = ["| arm | window | TGC | SGC | Δ TGC vs `abl_ref` [95% CI] | Holm (2 primary) | Δ TGC vs seed [95% CI] | gate run's own window (2 trials) |",
         "|---|---|---|---|---|---|---|---|"]
    for a in (REF, SEED) + GATE:
        v, s = res["vs_ref"].get(a), res["vs_seed"].get(a)
        L.append(f"| `{a}` | {'2' if a in GATE else '1'} | {_p(res['tgc'][a])} | {_p(res['sgc'][a])} | "
                 + (f"{_p(v['d_tgc'])} {_ci(v['ci_tgc'])} | {'significant' if v['holm_significant_tgc'] else 'not significant'}"
                    if v else "— | —") + " | " + (f"{_p(s['d_tgc'])} {_ci(s['ci_tgc'])}" if s else "—")
                 + f" | {_p(res['gate_run_window_context'].get(a))} |")
    return "\n".join(L)


def caveat(res: dict) -> str:
    d = res["drift_check"]
    return ("**Cross-window caveat.** `abl_ref` and the seed were scored in window 1 (2026-10-28 to 10-30) and the gate "
            "arms in window 2 (2026-11-01), on the same 168 tasks with the same trial seeds (7000 + k), so the "
            "comparison is paired by (task, trial). Any drift in the RITS serving between the two windows is mixed "
            f"into each Δ. Drift check: infra retries per cell, window 1 (`abl_ref`, seed) {d['infra_retries_per_cell_window1_ref_seed']}, "
            f"window 2 (gate arms) {d['infra_retries_per_cell_window2_gate']}; differing by more than 2×: "
            f"**{'yes' if d['flag_more_than_2x'] else 'no'}**. One search seed per arm; differences of a few points are "
            "not resolved.")


def report(res: dict) -> str:
    return "\n\n".join(["# AppWorld TEST_ABL: the gate arms vs `abl_ref` and the seed (cross-window)", table(res),
                        caveat(res)]) + "\n"


def arm_body(res: dict, a: str) -> str:
    v, s = res["vs_ref"][a], res["vs_seed"][a]
    return "\n\n".join([
        f"**{P.METHOD_NAMES[a]} (`{a}`): the primary comparison, vs the reference `abl_ref` (cross-window).** "
        "This completes the results comment above, which covered window 2 alone.",
        f"**Δ TGC vs `abl_ref`: {_p(v['d_tgc'])} points** {_ci(v['ci_tgc'])} (bootstrap p {v['p_tgc']:.4f}; Holm over "
        f"the 2 gate arms: **{'significant' if v['holm_significant_tgc'] else 'not significant'}**); Δ SGC "
        f"{_p(v['d_sgc'])} {_ci(v['ci_sgc'])}. Δ TGC vs the seed: {_p(s['d_tgc'])} {_ci(s['ci_tgc'])}.",
        table(res), caveat(res),
        "Full table: [`docs/TEST_ABL_STATE/final2/CROSS_WINDOW.md`](https://github.com/erezh16/cap-evolve/blob/test-abl/"
        "docs/TEST_ABL_STATE/final2/CROSS_WINDOW.md). Counts and aggregates only."])


if __name__ == "__main__":
    raise SystemExit(main())
