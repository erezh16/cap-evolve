"""P6 dev diagnostic (plan §8.5): seed and ace on the 57 dev tasks, 1 trial each, root_opt, 24 workers.
No decision depends on it. Pushed rows (no ids): docs/EVAL_SMOKE_TEST_ACE_STATE/dev/cells.csv.

  venv-aw/bin/python -I dev_diag.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "adapters"))
import awpaths as P  # noqa: E402
import adapter  # noqa: E402
import window  # noqa: E402

ORDER_SEED = 804006


def main() -> int:
    ids = adapter.tasks("dev")
    order = window.make_order(ids, ["seed", "ace"], 1, ORDER_SEED)
    P.write_json(P.AW_STATE / "dev" / "order.json", order)
    m = P.manifest()
    sha = window.order_sha(order)
    if m.get("dev_order", {}).get("sha256") not in (None, sha):
        raise SystemExit("regenerated dev order differs from the recorded sha256")
    P.update_manifest(dev_order={"seed": ORDER_SEED, "sha256": sha, "cells": len(order)})
    art = P.AW_STATE / "final" / "artifacts"
    own = not os.environ.get("AW_UNDER_PIPELINE")
    if own:
        (P.AW_STATE / "RUNNING.pid").write_text(f"{os.getpid()} dev_diag\n")
    try:
        w = window.Window("p6dev", "P6", "dev diagnostic", order, {"seed": art / "seed", "ace": art / "ace"},
                          P.AW_STATE / "dev" / "records", seed_base=100, final=False,
                          workers=int(os.environ.get("AW_WORKERS", 24)), max_infra_retries=1,
                          coalesce_s=int(os.environ.get("AW_COALESCE_S", 300)),
                          pushed_rows_csv=P.PUSHED / "dev" / "cells.csv", next_unit_done="P7/scan",
                          trial_name="dev")
        return w.run()
    finally:
        if own:
            (P.AW_STATE / "RUNNING.pid").unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
