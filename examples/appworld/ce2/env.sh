# Environment of every eval CE2 command (docs/EVAL_APPWORLD_CE2.md §6.2 B1). Source it: . examples/appworld/ce2/env.sh
# awrest.py reads these; AW_PROFILE=ce2 loads the CE2 constants (scripts/awce2.py) in every process.
export AW_PROFILE=ce2
export AW_HOME=/workspace/aw_ce2
export AW_STATE=/workspace/aw_ce2/state
export AW_SCRATCH_ROOT=/tmp/aw_ce2
export AW_LEDGER_NAME=EVAL_APPWORLD_CE2_STATUS.md
export AW_BRANCH=eval-ce2
export AW_REPO=/workspace/worktrees/eval-ce2
# the RITS key stays in the base worktree's .env; it is read by the episode worker only, never copied (R1)
export AW_ENV_FILE=/workspace/worktrees/base/.env
export AW_SESSION_IDS=959232f1-5a88-467f-b986-718636481ff3   # this run's orchestrating session (CE2-0087)
