#!/usr/bin/env bash
# The ONLY way a cap-evolve ablation search is started or resumed (docs/ABLATIONS.md §9.2).
#   bash examples/appworld/abl/launch_abl.sh ARM PROJECT_DIR RUN_TS [extra cap-evolve run args, e.g. --resume]
# 1 sources abl/env.sh, exports CAPEVOLVE_SKILLS_DIR, puts abl/sandbox_cc then venv-abl/bin first on PATH;
# 2 APPWORLD_ROOT=root_opt, AW_CAPE_ARM, AW_KEY_ENV; 3 the arm's switches and nothing else; 4 AW_CAPE_EXTRA_DENY;
# 5 unsets the RITS key variables, CLAUDECODE and every CAPEVOLVE_* / AW_ABL_* it does not set itself;
# 6 waits on memok-abl; 7 IMP launch checks 1-3 and the switch check, exit 3 on failure; 8 claude is the shim;
# 9 execs cap-evolve run under the caller's nohup, stderr teed to AW_STATE/progress/<arm>.log.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EX="$(cd "$HERE/.." && pwd)"
ARM="${1:?arm}"; PROJ="${2:?project dir}"; TS="${3:?run ts}"; shift 3
case "$ARM" in
  abl_ref) SW=(AW_ABL_FEEDBACK=full);;
  abl_prompt) SW=(AW_ABL_FEEDBACK=full);;
  abl_tools) SW=(AW_ABL_FEEDBACK=full AW_ABL_TOOLS_LINT=1);;
  abl_notrace) SW=(AW_ABL_FEEDBACK=eval_only);;
  abl_tracescore) SW=(AW_ABL_FEEDBACK=trace_score);;
  *) echo "launch_abl.sh: unknown arm $ARM (abl_cc uses abl/cc/launch_cc.sh)" >&2; exit 2;;
esac
. "$HERE/env.sh"
for v in $(compgen -e); do case "$v" in CAPEVOLVE_*|AW_ABL_*) unset "$v";; esac; done
unset RITS_API_KET RITS_API_KEY CLAUDECODE || true
PIN=/workspace/worktrees/abl-main
VC="$AW_HOME/build/venvs/venv-abl"
export CAPEVOLVE_SKILLS_DIR="$PIN/skills"
export PATH="$HERE/sandbox_cc:$VC/bin:$PATH"
export AW_CAPE_ARM="$ARM" AW_EXAMPLE="$EX" AW_CAPE_PHASE="${AW_CAPE_PHASE:-search}" AW_EXPERIMENT="aw_${ARM}_$TS"
export AW_CAPE_EXTRA_DENY="${AW_CAPE_EXTRA_DENY:-$PROJ/adapters}"
export APPWORLD_ROOT="$AW_HOME/build/root_opt" AW_KEY_ENV=RITS_API_KET
export "${SW[@]}"
# acceptance dry runs only (optimizer_skill mock): never in a counted search
if [ "$AW_CAPE_PHASE" = accept ] && [ -n "${AW_MOCK_SCRIPT:-}" ]; then export CAPEVOLVE_MOCK_SCRIPT="$AW_MOCK_SCRIPT"; fi
unset AW_MOCK_SCRIPT
mkdir -p "$AW_STATE/$ARM" "$AW_STATE/progress"
until "$HOME/bin/memok-abl" >/dev/null 2>&1; do sleep 30; done
"$VC/bin/python" -I "$HERE/run_abl.py" imp-check --arm "$ARM" --level launch --project "$PROJ" \
  > "$AW_STATE/$ARM/imp_launch_$TS.json" \
  || { echo "launch_abl.sh: IMP launch / switch checks failed; see imp_launch_$TS.json" >&2; exit 3; }
[ "$(command -v claude)" = "$HERE/sandbox_cc/claude" ] || { echo "launch_abl.sh: shim not first on PATH" >&2; exit 3; }
cd "$PROJ/../.."
echo $$ > "$AW_STATE/$ARM/search.pid"
exec "$VC/bin/cap-evolve" run --spec "$PROJ/capevolve.yaml" --project "$PROJ" --run-ts "$TS" \
  --dashboard off --follow "$@" 2> >(tee -a "$AW_STATE/progress/$ARM.log" >&2)
