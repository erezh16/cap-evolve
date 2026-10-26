#!/usr/bin/env bash
# Long-command probe (ABL-0361): through the arm's own shim and sandbox, a 90 s sleep and a background wait must
# finish. On the original pod both were killed after ~5 s (landrun + proot). Prints PASS/FAIL lines only.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ABL="$(cd "$HERE/.." && pwd)"
P=$(mktemp -d "$AW_HOME/arms/abl_cc/probe_XXXX"); mkdir -p "$P/cfg"; cd "$P"
unset RITS_API_KET RITS_API_KEY CLAUDECODE
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
rm -rf "$P"
