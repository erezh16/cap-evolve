#!/usr/bin/env bash
# The ONLY way the abl_cc arm runs (docs/ABLATIONS.md §10.2): starts evald.py (pid file) and ONE plain Claude Code
# session through the same PATH shim as every arm (sandbox_cc/claude: --setting-sources '' and the sandbox settings).
#   bash examples/appworld/abl/cc/launch_cc.sh            # the counted session (never re-prompted, §13.4)
# Refuses to start if the config dir is not empty, the prompt hash differs, a session already ran, or memok-abl fails.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ABL="$(cd "$HERE/.." && pwd)"; EX="$(cd "$ABL/.." && pwd)"
. "$ABL/env.sh"
for v in $(compgen -e); do case "$v" in CAPEVOLVE_*|AW_ABL_*|AW_CC_*) unset "$v";; esac; done
unset RITS_API_KET RITS_API_KEY CLAUDECODE || true
ARM=abl_cc
VC="$AW_HOME/build/venvs/venv-abl"
ROOT="$AW_HOME/arms/$ARM"; WORK="$ROOT/work"; CONF="$ROOT/config"
export AW_CAPE_ARM=$ARM AW_EXAMPLE="$EX" AW_ABL_FEEDBACK=full AW_KEY_ENV=RITS_API_KET \
       APPWORLD_ROOT="$AW_HOME/build/root_opt" AW_EXPERIMENT="aw_${ARM}_s0"
mkdir -p "$AW_STATE/$ARM" "$AW_STATE/progress"
[ ! -e "$AW_STATE/$ARM/SESSION_STARTED" ] || { echo "launch_cc.sh: a session already ran; no re-prompting (§13.4)" >&2; exit 3; }
"$VC/bin/python" -I "$HERE/run_cc.py" setup > /dev/null
"$VC/bin/python" -I "$HERE/run_cc.py" check-config > "$AW_STATE/$ARM/check_config.json" \
  || { echo "launch_cc.sh: config dir not empty or prompt hash differs" >&2; exit 3; }
until /home/dev/bin/memok-abl >/dev/null 2>&1; do sleep 30; done
# the daemon: trusted, unsandboxed, outside the session's process tree
if ! { [ -f "$AW_STATE/$ARM/EVALD.pid" ] && kill -0 "$(cat "$AW_STATE/$ARM/EVALD.pid")" 2>/dev/null; }; then
  nohup "$VC/bin/python" -I "$HERE/evald.py" loop "$WORK" >> "$AW_STATE/progress/abl_cc_evald.out" 2>&1 < /dev/null &
  sleep 2
fi
export PATH="$ABL/sandbox_cc:$PATH" CLAUDE_CONFIG_DIR="$CONF"
[ "$(command -v claude)" = "$ABL/sandbox_cc/claude" ] || { echo "launch_cc.sh: shim not first on PATH" >&2; exit 3; }
date -u +%FT%TZ > "$AW_STATE/$ARM/SESSION_STARTED"
echo $$ > "$AW_STATE/$ARM/session.pid"
cd "$WORK"
exec claude -p "$(cat "$HERE/PROMPT.txt")" --permission-mode acceptEdits --allowedTools Bash --disallowedTools Monitor \
  --model aws/claude-sonnet-5-5 --output-format json --max-turns 1200 \
  > "$AW_STATE/$ARM/session_result.json" 2> >(tee -a "$AW_STATE/progress/$ARM.log" >&2)
