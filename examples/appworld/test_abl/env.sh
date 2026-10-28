# Environment of every TEST_ABL command (docs/TEST_ABL.md §2, §7 B1). Source it: . examples/appworld/test_abl/env.sh
# awrest.py reads these; AW_PROFILE=testabl loads the TEST_ABL constants (scripts/awtestabl.py) in every process.
export AW_PROFILE=testabl
export AW_HOME=/workspace/aw_abl                       # the ablation run's build, used in place (never modified)
export AW_STATE=/workspace/aw_abl/state/testabl        # inside the ablation AW_STATE: denied to every gate optimizer
export AW_SCRATCH_ROOT=/tmp/aw_abl/testabl
export AW_LEDGER_NAME=TEST_ABL_STATUS.md
export AW_BRANCH=test-abl
export AW_REMOTE=fork                                  # branches go to erezh16/cap-evolve; origin is issues only
export AW_REPO=/workspace/worktrees/test-abl
# the RITS key stays in the base worktree's .env; it is read by the episode worker only, never copied (R1)
export AW_ENV_FILE=/workspace/worktrees/base/.env
export AW_SESSION_IDS=31c436f4-7310-4c8b-81cc-5b90e0bd3c20   # this run's orchestrating session
export VENV_AW=/workspace/aw_abl/build/venvs/venv-aw
unset AW_ABL_FEEDBACK AW_ABL_TOOLS_LINT AW_CAPE_ARM    # search-time switches; never set in this run (plan §5)
