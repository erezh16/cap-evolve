# Environment of every ablation command (docs/ABLATIONS.md §6.2 B1). Source it: . examples/appworld/abl/env.sh
export AW_PROFILE=abl
export AW_HOME=/workspace/aw_abl
export AW_STATE=/workspace/aw_abl/state
export AW_SCRATCH_ROOT=/tmp/aw_abl
export AW_LEDGER_NAME=ABLATION_STATUS.md
export AW_LEDGER_ID=ABL
export AW_BRANCH=eval-abl
export AW_REMOTE=fork                      # branches go to erezh16/cap-evolve; origin (skillberry-ai) is issues only
export AW_REPO=/workspace/worktrees/eval-abl
# the RITS key stays in the base worktree's .env; it is read by the episode worker only, never copied (R1)
export AW_ENV_FILE=/workspace/worktrees/base/.env
export AW_SESSION_IDS=12194466-3ee6-4d3d-afab-8ab8118a33cc,5cbfcce5-92a4-4a7f-931d-8014e8ce1e92   # orchestrating sessions (B0 session; relaunched session appended)
# another host (ABL-0361, abl_cc remote run): remote/env.remote.sh sets AW_HOST_ENV to itself, so every launcher that
# sources this file gets that host's values back. Unset on the original pod.
if [ -n "${AW_HOST_ENV:-}" ]; then . "$AW_HOST_ENV"; fi
