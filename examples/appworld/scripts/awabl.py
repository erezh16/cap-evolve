"""Ablation constants (docs/ABLATIONS.md §6.2 B1): CE3's profile (awce3.py -> awce2.py) with the six ablation arms.

Loaded by awrest.py when AW_PROFILE=abl (set by examples/appworld/abl/env.sh). LEDGER_PREFIX stays "CE2" so the
shared CE2 code paths (memory field in every entry, `arm` key) apply; the visible ledger id is ABL. Code under test:
cap-evolve main 75b3bcd, core and skills unmodified (D4). No money or token cap (D12).
"""

from pathlib import Path

from awce3 import *  # noqa: F401,F403

CANDIDATES = ("abl_ref", "abl_cc", "abl_prompt", "abl_tools", "abl_notrace", "abl_tracescore")
ARMS = ("seed",) + CANDIDATES
ISSUES = {"abl_ref": 930, "abl_cc": 931, "abl_prompt": 932, "abl_tools": 933, "abl_notrace": 934,
          "abl_tracescore": 935}
METHOD_NAMES = {"abl_ref": "Cap-evolve full (reference)", "abl_cc": "Claude code (plain Claude Code)",
                "abl_prompt": "Cap evolve prompt only", "abl_tools": "Cap evolve tools only",
                "abl_notrace": "Cap evolve no traces", "abl_tracescore": "Cap evolve traces and score only"}
CAPE_ARMS = ("abl_ref", "abl_prompt", "abl_tools", "abl_notrace", "abl_tracescore")
K_SE = {c: 0.2 for c in CAPE_ARMS}         # D7: gate_k_se 0.2, written explicitly (cap-evolve arms only)
ARMS_HOME = Path("/workspace/aw_abl/arms")
RUN_ROOTS = {c: ARMS_HOME / c for c in CANDIDATES}
RUN_TS = {c: f"{c}_s0" for c in CANDIDATES}
CAPE_COMMIT = "75b3bcdd0fc7292f9717f2b6dcb720f147452df9"   # cap-evolve main (D4)
CAPE_TREE = Path("/workspace/worktrees/abl-main")
CAPE_IMPROVE_COMMIT = CAPE_COMMIT
CAPE_IMPROVE_TREE = CAPE_TREE
PINS = {c: ("https://github.com/skillberry-ai/cap-evolve/tree/main", CAPE_COMMIT) for c in CANDIDATES}
TEMPLATE_SHA256 = "84de4f00a5254c47f0627a9e753129375ce12d20ecdcbeeb0e266d6106de2fce"
BUDGET_ROLLOUTS = 882                      # B = 6 x 147 counted (fresh) search rollouts per arm
BUDGET_OPT_TOKENS = None                   # off (D12)
SEED_BASELINE_PHASE = "P3"                 # one fresh shared seed run (D8)
LEDGER_ID = "ABL"
EVAL_NAME = "AppWorld ablations"
FINAL_ARMS_RUN = ARMS                      # one window: seed + 6 champions
REUSED_WINDOW_ARMS = ()
# earlier evaluations' homes: sealed for every optimizer (R1)
EARLIER_HOMES = (Path("/workspace/aw_rest"), Path("/workspace/aw_ce2"), Path("/workspace/aw_ce3"))
