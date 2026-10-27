#!/usr/bin/env bash
# Long-command probe (ABL-0361): through the arm's own shim and sandbox, a 90 s sleep and a background wait must
# finish. It moves only its own usage lines and call files out of abl_cc's logs. On the original pod both were killed after ~5 s (landrun + proot). Prints PASS/FAIL lines only.
set -uo pipefail
# the tier line is informational (ABL-0462: the fixed sandbox need not be bubblewrap; only the three PASS lines count)
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ABL="$(cd "$HERE/.." && pwd)"
[ "${AW_LEDGER_ID:-}" = ABL ] || { echo "probe: source abl/env.sh first" >&2; exit 2; }
mkdir -p "$AW_HOME/arms/probe_abl_cc"; P=$(mktemp -d "$AW_HOME/arms/probe_abl_cc/run_XXXX"); mkdir -p "$P/cfg"; cd "$P"
unset RITS_API_KET RITS_API_KEY CLAUDECODE
TS=$(date -u +%Y%m%dT%H%M%SZ)
U0=$( [ -e "$AW_STATE/abl_cc/optimizer_usage.jsonl" ] && wc -l < "$AW_STATE/abl_cc/optimizer_usage.jsonl" || echo 0)
C0=$(mktemp); ls "$AW_STATE/abl_cc/claude_calls" 2>/dev/null > "$C0"
run() {
  AW_CAPE_ARM=abl_cc AW_ABL_FEEDBACK=full CLAUDE_CONFIG_DIR="$P/cfg" PATH="$ABL/sandbox_cc:$PATH" \
    timeout 900 claude -p "Run exactly this one Bash command and then report its exit code and output verbatim: $1" \
    --permission-mode acceptEdits --allowedTools Bash --disallowedTools Monitor --model aws/claude-sonnet-5-5 \
    --output-format json 2>/dev/null | python3 -c "import json,sys
d=json.load(sys.stdin); r=d.get('result','')
print('PASS' if 'waited-ok' in r and '137' not in r else 'FAIL (killed, 137)' if '137' in r else 'FAIL: '+r[:200])"
}
echo "sleep 12:  $(run 'sleep 12; echo waited-ok')"
echo "sleep 90:  $(run 'sleep 90; echo waited-ok')"
echo "loop 100s: $(run 'for i in $(seq 1 10); do sleep 10; done; echo waited-ok')"
echo "tier:      $(devagent-bwrap --devagent-tier --unshare-net --ro-bind / / --dev /dev --proc /proc -- true 2>&1 | head -1 || echo 'devagent-bwrap absent: Claude Code uses its own bwrap')"
rm -rf "$P"; rmdir "$AW_HOME/arms/probe_abl_cc" 2>/dev/null
# the shim logged these calls as abl_cc's: move only the probe's own lines and call files out of the arm's logs
# (as A9 does, CE2 CP-0041); sessions 1 and 2 stay in place
A="$AW_STATE/abl_cc/accept"; mkdir -p "$A/probe_claude_calls_$TS"
U="$AW_STATE/abl_cc/optimizer_usage.jsonl"
if [ -e "$U" ]; then
  tail -n +$((U0+1)) "$U" > "$A/probe_usage_$TS.jsonl"; head -n "$U0" "$U" > "$U.tmp" && mv "$U.tmp" "$U"
  [ "$U0" -eq 0 ] && rm -f "$U"
fi
if [ -d "$AW_STATE/abl_cc/claude_calls" ]; then
  for f in "$AW_STATE/abl_cc/claude_calls"/*; do [ -e "$f" ] || continue
    grep -qxF "$(basename "$f")" "$C0" || mv "$f" "$A/probe_claude_calls_$TS/"; done
fi
rm -f "$C0"; true
