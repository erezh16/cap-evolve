# Environment of the abl_cc REMOTE run (docs/ABLATIONS.md §10.2; ledger ABL-0361). Edit the two marked lines, then
# source it instead of abl/env.sh. Same profile and layout as the main run, under the host's own AW_HOME.
export AW_PROFILE=abl
export AW_HOME=/workspace/aw_abl                        # EDIT if needed: durable dir on the remote host
export AW_STATE=$AW_HOME/state
export AW_SCRATCH_ROOT=/tmp/aw_abl
export AW_LEDGER_NAME=ABLATION_STATUS.md
export AW_LEDGER_ID=ABL
export AW_BRANCH=eval-abl-cc-remote                     # the remote session commits ONLY to this branch
export AW_REMOTE=fork
export AW_REPO=/workspace/worktrees/eval-abl            # EDIT if needed: the eval-abl checkout on the remote host
export AW_ENV_FILE=/workspace/secrets/rits.env          # EDIT: KEY=VALUE file with RITS_URL and RITS_API_KET (never print it)
export AW_SESSION_IDS=                                  # the remote orchestrating session appends its own id here
