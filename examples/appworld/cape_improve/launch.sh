#!/usr/bin/env bash
# The ONLY way the cape_improve cap-evolve run is started or resumed (docs/EVAL_APPWORLD_REST.md §9.5 Deploy).
#   bash launch.sh PROJECT_DIR RUN_TS [extra cap-evolve run args, e.g. --resume --max-iterations 7]
# Uses venv-cape's cap-evolve (core from /workspace/worktrees/cape-improve @ 470f3fa) with
# CAPEVOLVE_SKILLS_DIR = the pinned skills, puts the sandbox shim first on PATH, re-runs IMP checks 1-3
# and refuses to start if any fails. A9 must have passed with the shim before a counted run.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EX="$(cd "$HERE/.." && pwd)"
PIN=/workspace/worktrees/cape-improve
VC=/workspace/aw_rest/build/venvs/venv-cape
PROJ="${1:?project dir}"; TS="${2:?run ts}"; shift 2
export CAPEVOLVE_SKILLS_DIR="$PIN/skills"
export PATH="$HERE/sandbox_cc:$VC/bin:$PATH"
export AW_EXAMPLE="$EX" AW_CAPE_PHASE="${AW_CAPE_PHASE:-search}" AW_EXPERIMENT="awrest_cape_improve_$TS"
export AW_CAPE_EXTRA_DENY="${AW_CAPE_EXTRA_DENY:-$PROJ/adapters}"
export APPWORLD_ROOT=/workspace/aw_rest/build/root_opt AW_KEY_ENV=RITS_API_KET
unset RITS_API_KET RITS_API_KEY CLAUDECODE || true
# rule R2: nothing new starts while the memory guard is PAUSED or stale
until /home/dev/bin/memok >/dev/null 2>&1; do sleep 30; done
# IMP checks 1, 2, 3 (code pin, skills pin, spec k = 0.5): refuse to start on any failure
"$VC/bin/python" -I "$HERE/run_cape_improve.py" imp-check --level launch --project "$PROJ" \
  > "/workspace/aw_rest/state/cape_improve/imp_launch_$TS.json" \
  || { echo "launch.sh: IMP launch checks failed; see imp_launch_$TS.json" >&2; exit 3; }
[ "$(command -v claude)" = "$HERE/sandbox_cc/claude" ] || { echo "launch.sh: shim not first on PATH" >&2; exit 3; }
cd "$PROJ/../.."
exec "$VC/bin/cap-evolve" run --spec "$PROJ/capevolve.yaml" --project "$PROJ" --run-ts "$TS" \
  --dashboard off --follow "$@"
