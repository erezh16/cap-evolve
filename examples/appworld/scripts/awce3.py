"""Eval CE3 constants (docs/EVAL_APPWORLD_CE3.md): CE2's profile (awce2.py) with one arm, ce3_k02 (K = 0.2).

Loaded by awrest.py when AW_PROFILE=ce3 (set by examples/appworld/ce3/env.sh). Everything not set here is CE2's
(awce2.py), including the candidate pin 3db96a0, the ledger prefix logic and the CE2 code paths, which key on
P.LEDGER_PREFIX == "CE2" (CE3 is a CE2 arm). The ledger entries are numbered CE3-NNNN through LEDGER_ID.
Differences from CE2 (plan section 2): one arm; no money or token cap; a 336-cell window of this arm only, joined
with CE2's reused window records for the analysis.
"""

from pathlib import Path

from awce2 import *  # noqa: F401,F403

CANDIDATES = ("ce3_k02",)
ARMS = ("seed",) + CANDIDATES
ISSUES = {"ce3_k02": 913}
METHOD_NAMES = {"ce3_k02": "Cap-Evolve-impr2 K=0.2"}
K_SE = {"ce3_k02": 0.2}
RUN_ROOTS = {"ce3_k02": Path("/workspace/aw_ce3/run_k02")}
RUN_TS = {"ce3_k02": "ce3_k02_s0"}
PINS = {"ce3_k02": ("https://github.com/erezh16/cap-evolve/tree/cap-evolve-impr2", CAPE_COMMIT)}  # noqa: F405
LEDGER_ID = "CE3"                          # the visible ledger id; LEDGER_PREFIX stays "CE2" for the shared code paths
EVAL_NAME = "eval CE3"
BUDGET_OPT_TOKENS = 10 ** 15               # plan section 2: no optimizer token cap (the shim compares against this)
# CE2's run roots and frozen artifacts: hidden from the CE3 optimizer (plan section 2, A9)
CE2_HOME = Path("/workspace/aw_ce2")
CE2_RUN_ROOTS = (CE2_HOME / "run_k1", CE2_HOME / "run_k2")
CE2_PUSHED = Path("/workspace/worktrees/eval-ce2/docs/EVAL_APPWORLD_CE2_STATUS_STATE")
FINAL_ARMS_RUN = ("ce3_k02",)              # the window runs only this arm (plan section 2)
REUSED_WINDOW_ARMS = ("seed", "ce2_k1", "ce2_k2")
