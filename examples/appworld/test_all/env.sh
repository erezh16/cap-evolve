# Environment of every TEST_ALL command (docs/TEST_ALL.md §7 B1). Source it: . examples/appworld/test_all/env.sh
# awrest.py reads these; AW_PROFILE=testall loads the TEST_ALL constants (scripts/awtestall.py) in every process.
export AW_PROFILE=testall
export AW_HOME=/workspace/aw_testall
export AW_STATE=/workspace/aw_testall/state
export AW_SCRATCH_ROOT=/tmp/aw_testall
export AW_LEDGER_NAME=TEST_ALL_STATUS.md
export AW_BRANCH=test-all
export AW_REPO=/workspace/worktrees/test-all
# the RITS key stays in the base worktree's .env; it is read by the episode worker only, never copied (R1)
export AW_ENV_FILE=/workspace/worktrees/base/.env
export AW_SESSION_IDS=64d72acb-bfc9-4bbd-93a4-f80e9242b4f0   # this run's orchestrating session
