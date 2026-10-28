"""T3 (docs/TEST_ALL.md §9): the window order. Run in venv-aw (a trusted script; root_full unlocked only for the read):

  . examples/appworld/test_all/env.sh && $VENV_AW/bin/python -I examples/appworld/test_all/check_t3.py

Regenerating the order from its seed twice gives the same sha256; 10,920 cells; every (arm, task, trial) exactly
once; indices 0..10,919. Records the seed and the sha256 in manifest.json `final_order` in advance (the order itself
holds task ids and is never written here). Prints counts and the hash only.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "scripts"))
import awrest as P  # noqa: E402
import window as W  # noqa: E402


def main() -> int:
    os.chmod(P.ROOT_FULL, 0o755)
    try:
        ids = P.read_split("test_normal", P.ROOT_FULL)
    finally:
        os.chmod(P.ROOT_FULL, 0o000)
    o1 = W.make_order(ids, list(W.WINDOW_ARMS), W.FINAL_TRIALS, W.FINAL_ORDER_SEED)
    o2 = W.make_order(list(ids), list(W.WINDOW_ARMS), W.FINAL_TRIALS, W.FINAL_ORDER_SEED)
    trip = Counter((c["arm"], c["task_id"], c["trial"]) for c in o1)
    res = {"seed": W.FINAL_ORDER_SEED, "trials": W.FINAL_TRIALS, "arms": len(W.WINDOW_ARMS), "tasks": len(set(ids)),
           "cells": len(o1), "sha256": W.order_sha(o1), "reproducible": W.order_sha(o1) == W.order_sha(o2),
           "each_cell_once": len(trip) == len(o1) == 168 * len(W.WINDOW_ARMS) * W.FINAL_TRIALS and set(trip.values()) == {1},
           "idx_ok": [c["idx"] for c in o1] == list(range(len(o1))),
           "per_arm": sorted(set(Counter(c["arm"] for c in o1).values())),
           "root_full_relocked": (os.stat(P.ROOT_FULL).st_mode & 0o777) == 0}
    key = getattr(P, "ORDER_KEY", "final_order")
    m = P.manifest().get(key) or {}
    if m.get("sha256") not in (None, res["sha256"]):
        res["matches_manifest"] = False
    else:
        P.update_manifest(**{key: {"seed": W.FINAL_ORDER_SEED, "sha256": res["sha256"], "cells": len(o1),
                                   "trials": W.FINAL_TRIALS, "trial_seeds": f"{P.FINAL_SEED_BASE} + trial",
                                   "infra_retries": 3}})
        res["matches_manifest"] = True
    res["ok"] = all(res[k] for k in ("reproducible", "each_cell_once", "idx_ok", "root_full_relocked",
                                     "matches_manifest")) and res["cells"] == P.FINAL_CELLS and res["per_arm"] == [168 * W.FINAL_TRIALS]
    P.write_json(P.AW_STATE / "acceptance" / ("t3_w2.json" if getattr(P, "WINDOW", "1") == "2" else "t3.json"), res)
    print(json.dumps(res))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
