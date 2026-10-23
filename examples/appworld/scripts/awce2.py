"""Eval CE2 constants (docs/EVAL_APPWORLD_CE2.md §6.2 B1): the values of awrest.py that are not environment-driven.

Loaded by awrest.py when AW_PROFILE=ce2 (set by examples/appworld/ce2/env.sh), so every module that does
``import awrest as P`` (status_doc, evaluator, sandbox, autopost, post, scan, window, ...) sees the CE2 values in
every process of the run. Paths come from the environment (AW_HOME, AW_STATE, AW_SCRATCH_ROOT, AW_LEDGER_NAME,
AW_BRANCH), all set by env.sh. Kept unchanged from REST (plan §6.2 B1): BUDGET_ROLLOUTS, BUDGET_OPT_TOKENS,
SEARCH_SEED_BASE, FINAL_SEED_BASE, the prices, OPT_MODEL, AGENT_MODEL, GLOBAL_SLOTS_DEFAULT/MAX, SPLIT_COUNTS,
APPWORLD_COMMIT.
"""

from pathlib import Path

CANDIDATES = ("ce2_k1", "ce2_k2")
ARMS = ("seed",) + CANDIDATES
ISSUES = {"ce2_k1": 909, "ce2_k2": 910}
METHOD_NAMES = {"ce2_k1": "Cap-Evolve-impr2 K=1", "ce2_k2": "Cap-Evolve-impr2 K=2"}
K_SE = {"ce2_k1": 1, "ce2_k2": 2}
RUN_ROOTS = {"ce2_k1": Path("/workspace/aw_ce2/run_k1"), "ce2_k2": Path("/workspace/aw_ce2/run_k2")}
RUN_TS = {"ce2_k1": "ce2_k1_s0", "ce2_k2": "ce2_k2_s0"}
CAPE_COMMIT = "3db96a08ef77d7701f21771d389c6471a5d88344"   # 8194578 + two Self-check wording fixes (user decisions 2026-10-23)
CAPE_TREE = Path("/workspace/worktrees/cape-impr2")
PINS = {c: ("https://github.com/erezh16/cap-evolve/tree/cap-evolve-impr2", CAPE_COMMIT) for c in CANDIDATES}
# REST's names for the pinned cap-evolve checkout, re-pointed so shared code (sandbox deny list, A9) uses the CE2 pin
CAPE_IMPROVE_COMMIT = CAPE_COMMIT
CAPE_IMPROVE_TREE = CAPE_TREE
SEED_BASELINE_PHASE = "P3-reused"          # the seed baseline is REST's P3 records, reused (plan §7.4, D5)
LEDGER_PREFIX = "CE2"
EVAL_NAME = "eval CE2"
REST_HOME = Path("/workspace/aw_rest")     # sealed for every agent (R1); only seed_reuse.py copies from it
