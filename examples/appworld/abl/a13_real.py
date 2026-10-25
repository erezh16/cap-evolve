"""A13 on the REAL cache after P3 (docs/ABLATIONS.md §14 A13; CE2-0009: before any path swap). Source abl/env.sh; run
in venv-abl. Counts only.

For each cap-evolve arm (with its own switches) a candidate dir identical to the seed is evaluated on all 147 ids
through the shared evaluator, phase search, under a throwaway name ``acc_a13_<arm>``: every record must be a cache hit
of the P3 baseline and nothing counted. For abl_cc the eval daemon itself evaluates a byte copy of the seed in a
throwaway workdir (real mode, B = 882): 0 rollouts used; its log lines are then moved to AW_STATE/abl_cc/accept/, so
abl_cc's search starts with an empty log. Finally a fresh seed episode (a seed value with no record) must raise
SeedRerunRefused.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EX = HERE.parent
sys.path[:0] = [str(EX / "scripts"), str(EX / "common")]
import awrest as P  # noqa: E402

P.setup_env()
import evaluator as E  # noqa: E402

SWITCH = {"abl_tools": {"AW_ABL_TOOLS_LINT": "1"}}


def main() -> int:
    if not E.SEED_DONE.exists():
        raise SystemExit("a13_real: P3 is not done")
    ids = E.split_ids("train") + E.split_ids("dev")
    res = {"arms": {}}
    for arm in ("abl_ref", "abl_prompt", "abl_tools", "abl_notrace", "abl_tracescore"):
        saved = {k: os.environ.get(k) for k in ("AW_ABL_TOOLS_LINT",)}
        os.environ.update(SWITCH.get(arm, {}))
        try:
            name = f"acc_a13_{arm}"
            same = E.materialize(name, {})
            before = E.counted(name)
            recs = E.evaluate(name, same, ids, phase="search", tag="a13-real")
            res["arms"][arm] = {"same_tree_is_seed": E.tree_hash(same) == E.seed_hash(), "records": len(recs),
                                "all_cache_hits": all(r.get("cache_hit") for r in recs),
                                "counted": E.counted(name) - before,
                                "tgc_from_cache": round(sum(r["reward"] for r in recs) / len(recs), 4)}
        finally:
            for k, v in saved.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
    # abl_cc: the daemon in real mode on a throwaway workdir
    st = P.AW_STATE / "abl_cc"
    work = st / "accept" / "a13_work"
    shutil.rmtree(work, ignore_errors=True)
    py = str(P.VENVS / "venv-abl" / "bin" / "python")
    env = {k: v for k, v in os.environ.items() if k not in ("AW_CC_DRY", "AW_ABL_TOOLS_LINT")}
    env["AW_ABL_FEEDBACK"] = "full"
    subprocess.run([py, "-I", str(HERE / "cc" / "run_cc.py"), "setup", "--root", str(work.parent / "a13_root")],
                   check=True, capture_output=True, env=env)
    w = work.parent / "a13_root" / "work"
    (w / "seedcopy").mkdir()
    for d in ("policy", "tools"):
        shutil.copytree(w / d, w / "seedcopy" / d)
    subprocess.run([str(w / "eval_candidate"), "seedcopy"], check=True, capture_output=True, cwd=str(w))
    lines_before = len(P.read_jsonl(st / "evals.jsonl"))
    r = subprocess.run([py, "-I", str(HERE / "cc" / "evald.py"), "once", str(w)], capture_output=True, text=True, env=env)
    log = json.loads(r.stdout.strip().splitlines()[-1])
    res["abl_cc_daemon"] = {"state": log.get("state"), "fresh": log.get("fresh"), "cache_hits": log.get("cache_hits"),
                            "rollouts_used": log.get("rollouts_used"), "mean_reward": log.get("mean_reward")}
    acc = st / "accept"
    for f in ("evals.jsonl", "cache_hits.jsonl"):           # the arm's search logs start empty (as A9, REST CP-0041)
        if (st / f).exists():
            os.replace(st / f, acc / f"a13_{f}")
    shutil.rmtree(st / "cands", ignore_errors=True)
    res["abl_cc_logs_moved"] = lines_before >= 0
    try:
        E.evaluate("acc_a13_fresh", E.materialize("acc_a13_fresh", {}), ids[:1], phase="search", tag="a13-fresh", seed=101)
        res["seed_rerun_refused"] = False
    except E.SeedRerunRefused:
        res["seed_rerun_refused"] = True
    a = res["arms"].values()
    res["ok"] = (all(v["same_tree_is_seed"] and v["records"] == 147 and v["all_cache_hits"] and v["counted"] == 0
                     for v in a)
                 and res["abl_cc_daemon"]["state"] == "done" and res["abl_cc_daemon"]["fresh"] == 0
                 and res["abl_cc_daemon"]["rollouts_used"] == 0 and res["seed_rerun_refused"])
    P.write_json(P.AW_STATE / "acceptance" / "a13_real.json", res)
    print(json.dumps(res))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
