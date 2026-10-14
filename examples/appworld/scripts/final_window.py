"""P8 final window (plan §12): 168 test_normal tasks × {seed, ace} × 2 trials = 672 cells, one random
order with a recorded seed, AW_ALLOW_SEALED=final-eval-only, root_full (unlocked here, logged),
48 workers, trial seeds 5000 + trial, infra errors retried up to 3 times with new seeds.
Only counts are pushed (final/progress.json); per-cell records stay in AW_STATE/final/records.

  venv-aw/bin/python -I final_window.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "adapters"))
import awpaths as P  # noqa: E402

ORDER_SEED = 804008


def main() -> int:
    os.environ["AW_ALLOW_SEALED"] = "final-eval-only"
    if (os.stat(P.ROOT_FULL).st_mode & 0o777) == 0:
        os.chmod(P.ROOT_FULL, 0o755)
        P.progress_log("final", "P8", "root_full unlocked for the final window")
    import adapter  # noqa: E402
    import window  # noqa: E402
    ids = adapter.tasks("test_normal")
    order = window.make_order(ids, ["seed", "ace"], 2, ORDER_SEED)
    sha = window.order_sha(order)
    m = P.manifest()
    if m.get("final_order", {}).get("sha256") not in (None, sha):
        raise SystemExit("regenerated final order differs from the recorded sha256")
    P.write_json(P.AW_STATE / "final" / "order.json", order)
    P.update_manifest(final_order={"seed": ORDER_SEED, "sha256": sha, "cells": len(order)})
    art = P.AW_STATE / "final" / "artifacts"
    for arm in ("seed", "ace"):
        if P.sha256_tree(art / arm) != m["freeze"]["tree_sha256"][arm]:
            raise SystemExit(f"frozen artifact {arm} changed since P5")
    own = not os.environ.get("AW_UNDER_PIPELINE")
    if own:
        (P.AW_STATE / "RUNNING.pid").write_text(f"{os.getpid()} final_window\n")
    try:
        w = window.Window("p8final", "P8", "final window", order, {"seed": art / "seed", "ace": art / "ace"},
                          P.AW_STATE / "final" / "records", seed_base=5000, final=True,
                          workers=int(os.environ.get("AW_WORKERS", 48)), max_infra_retries=3,
                          coalesce_s=int(os.environ.get("AW_COALESCE_S", 300)),
                          pushed_counts=P.PUSHED / "final" / "progress.json", next_unit_done="P9/analysis",
                          trial_name="final")
        return w.run()
    finally:
        if own:
            (P.AW_STATE / "RUNNING.pid").unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
