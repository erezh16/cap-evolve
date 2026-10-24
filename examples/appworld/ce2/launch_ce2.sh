#!/usr/bin/env bash
# The ONLY way a CE2 cap-evolve search is started or resumed (docs/EVAL_APPWORLD_CE2.md §9.2).
#   bash examples/appworld/ce2/launch_ce2.sh ARM PROJECT_DIR RUN_TS [extra cap-evolve run args, e.g. --resume]
# Sources ce2/env.sh; venv-ce2's cap-evolve (core from /workspace/worktrees/cape-impr2 @ 8194578) with
# CAPEVOLVE_SKILLS_DIR = the pinned skills; the sandbox shim first on PATH; the arm's extra deny paths (the other arm's
# project root is in sandbox.py's CE2 deny list); RITS key variables and CLAUDECODE unset; waits on memok-ce2;
# re-runs IMP checks 1-3 and exits 3 on any failure; checks that `command -v claude` is the shim.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EX="$(cd "$HERE/.." && pwd)"
ARM="${1:?arm ce2_k1|ce2_k2|ce3_k02}"; PROJ="${2:?project dir}"; TS="${3:?run ts}"; shift 3
case "$ARM" in
  ce2_k1|ce2_k2) . "$HERE/env.sh"; MEMOK=/home/dev/bin/memok-ce2;;
  ce3_k02) . "$HERE/../ce3/env.sh"; MEMOK=/home/dev/bin/memok-ce3;;     # CE3: one more CE2 arm (EVAL_APPWORLD_CE3.md)
  *) echo "launch_ce2.sh: unknown arm $ARM" >&2; exit 2;;
esac
PIN=/workspace/worktrees/cape-impr2
VC=/workspace/aw_ce2/build/venvs/venv-ce2
export CAPEVOLVE_SKILLS_DIR="$PIN/skills"
export PATH="$HERE/sandbox_cc:$VC/bin:$PATH"
export AW_CAPE_ARM="$ARM" AW_EXAMPLE="$EX" AW_CAPE_PHASE="${AW_CAPE_PHASE:-search}" AW_EXPERIMENT="aw_${ARM}_$TS"
export AW_CAPE_EXTRA_DENY="${AW_CAPE_EXTRA_DENY:-$PROJ/adapters}"
export APPWORLD_ROOT="$AW_HOME/build/root_opt" AW_KEY_ENV=RITS_API_KET
unset RITS_API_KET RITS_API_KEY CLAUDECODE || true
mkdir -p "$AW_STATE/$ARM" "$AW_STATE/progress"
# rule R2: nothing new starts while the memory guard is PAUSED or stale
until "$MEMOK" >/dev/null 2>&1; do sleep 30; done
# IMP checks 1, 2, 3 (code pin, skills pin, spec K): refuse to start on any failure
"$VC/bin/python" -I "$HERE/run_ce2.py" imp-check --arm "$ARM" --level launch --project "$PROJ" \
  > "$AW_STATE/$ARM/imp_launch_$TS.json" \
  || { echo "launch_ce2.sh: IMP launch checks failed; see imp_launch_$TS.json" >&2; exit 3; }
[ "$(command -v claude)" = "$HERE/sandbox_cc/claude" ] || { echo "launch_ce2.sh: shim not first on PATH" >&2; exit 3; }
cd "$PROJ/../.."
exec "$VC/bin/cap-evolve" run --spec "$PROJ/capevolve.yaml" --project "$PROJ" --run-ts "$TS" \
  --dashboard off --follow "$@" 2> >(tee -a "$AW_STATE/progress/$ARM.log" >&2)
