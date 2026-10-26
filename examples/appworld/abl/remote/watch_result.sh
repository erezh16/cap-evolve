#!/usr/bin/env bash
# Watches the user's Box folder for the abl_cc REMOTE result (ledger ABL-0361) and, once it is complete, downloads,
# checks and installs it, then lets the P4 runner run abl_cc's freeze, isolation scan and reset (the chain is resumed
# with its search step marked done: the search ran on the remote host). Trusted script (R1): prints counts and hashes.
#   nohup bash examples/appworld/abl/remote/watch_result.sh >> $AW_STATE/progress/abl_cc_watch.out 2>&1 &
# Expected in box:claude-code-ablation/result/: abl_cc_return.tar.gz, abl_cc_return.tar.gz.sha256 and the marker
# UPLOAD_COMPLETE (written last by the remote agent). Poll every 5 min (AW_WATCH_EVERY). Exits after one import.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ABL="$(cd "$HERE/.." && pwd)"
. "$ABL/env.sh"
VC="$AW_HOME/build/venvs/venv-abl/bin/python"
SRC="${AW_RESULT_REMOTE:-box:claude-code-ablation/result}"
EVERY="${AW_WATCH_EVERY:-300}"
DL="$AW_HOME/import/abl_cc_result"
LOG() { echo "$(date -u +%FT%TZ) watch_result: $*"; }
ledger() { "$VC" -I "$AW_REPO/examples/appworld/scripts/status_doc.py" append --arm abl_cc "$@" > /dev/null || LOG "ledger append failed"; }
echo $$ > "$AW_STATE/abl_cc_watch.pid"
LOG "start pid $$, polling $SRC every ${EVERY}s"
last_err=""
while true; do
  out=$(rclone lsf "$SRC" 2>&1); rc=$?
  if [ $rc -ne 0 ]; then
    err=$(echo "$out" | tail -1 | cut -c1-160)
    if [ "$err" != "$last_err" ]; then LOG "rclone lsf failed: $err"; last_err="$err"; fi
    case "$out" in *invalid_grant*|*"token expired"*)
      [ -e "$AW_STATE/abl_cc_watch.tokenwarn" ] || { touch "$AW_STATE/abl_cc_watch.tokenwarn"
        ledger --kind error --phase P4 --label "abl_cc result watch: Box token" --subject "Box token expired" \
          --prose "The watcher of the abl_cc remote result cannot list the Box folder: the rclone token for box: has expired (invalid_grant). It keeps polling; the user must run rclone config reconnect box: on this pod."; } ;;
    esac
    sleep "$EVERY"; continue
  fi
  rm -f "$AW_STATE/abl_cc_watch.tokenwarn"; last_err=""
  if echo "$out" | grep -qx "UPLOAD_COMPLETE" && echo "$out" | grep -qx "abl_cc_return.tar.gz" \
     && echo "$out" | grep -qx "abl_cc_return.tar.gz.sha256"; then
    LOG "result complete in $SRC; downloading"
    mkdir -p "$DL"
    if ! rclone copy "$SRC" "$DL" --include "abl_cc_return.tar.gz*" --include "UPLOAD_COMPLETE" --include "REMOTE_REPORT.md"; then
      LOG "download failed; retrying next poll"; sleep "$EVERY"; continue
    fi
    until "$HOME/bin/memok-abl" >/dev/null 2>&1; do sleep 30; done
    chk=$("$VC" -I "$HERE/import_result.py" check "$DL/abl_cc_return.tar.gz" "$DL/abl_cc_return.tar.gz.sha256" 2>&1 | tail -1)
    LOG "check: $(echo "$chk" | cut -c1-600)"
    if ! echo "$chk" | grep -q '"ok": true'; then
      ledger --kind abort --phase P4 --label "abl_cc result rejected" --subject "abl_cc result check failed" \
        --prose "The abl_cc remote result arrived in the Box folder but failed its checks (import_result.py check; counts and booleans in AW_STATE/progress/abl_cc_watch.out). Nothing was installed; the local abl_cc state is unchanged. The user is asked (R5)."
      exit 3
    fi
    ins=$("$VC" -I "$HERE/import_result.py" install "$DL/abl_cc_return.tar.gz" 2>&1 | tail -1)
    if ! echo "$ins" | grep -q '"installed": true'; then
      LOG "install failed: $(echo "$ins" | cut -c1-300)"
      ledger --kind abort --phase P4 --label "abl_cc result install failed" --subject "abl_cc result install failed" \
        --prose "The abl_cc remote result passed its checks but its install failed (AW_STATE/progress/abl_cc_watch.out). The user is asked (R5)."
      exit 3
    fi
    LOG "installed: $(echo "$ins" | cut -c1-600)"
    sum=$("$VC" -I -c "import json,sys;d=json.loads(sys.argv[1]);s=d.get('status') or {};print('evaluations done %s (mean val %s), rollouts %s of 882, sessions %s; remote checks: A9 ok %s, long-command probe pass %s; %s cache records added' % (s.get('evaluations_done'), s.get('mean_rewards_done'), s.get('rollouts_used'), s.get('sessions_started'), d.get('a9_ok'), d.get('probe_pass'), d.get('cache_records_added')))" "$ins")
    ledger --kind result --phase P4 --label "abl_cc remote result imported" --subject "abl_cc remote result imported" \
      --prose "abl_cc remote result (ABL-0361) downloaded from the Box folder claude-code-ablation/result, checked (tarball sha256, every bundle file hash, cache listing, the remote logs extend this pod's own, session 3 present, within B) and installed; this pod's previous abl_cc state is kept under AW_STATE/archive/. $sum. Next: abl_cc's freeze, isolation scan and reset check on this pod (P4 chain), then P5."
    # the chain resumes at freeze: search is done (remote), the earlier freeze and scan are superseded
    "$VC" -I - <<'EOF'
import json, os
from pathlib import Path
p = Path(os.environ["AW_STATE"]) / "p4" / "abl_cc.json"
d = json.loads(p.read_text())
d["done"] = ["search"]
for k in ("stopped_by_decision", "failed", "interrupted"):
    d.pop(k, None)
d.setdefault("notes", []).append("search ran on the remote host (ABL-0361); imported; freeze, scan, reset run here")
d["remote_import"] = True
t = p.with_name(p.name + ".tmp"); t.write_text(json.dumps(d, indent=1)); os.replace(t, p)
EOF
    # the P4 runner starts the chain (freeze, scan, reset); when every arm is finished it writes P4 done and starts P5
    if ! { [ -f "$AW_STATE/p4/RUNNER.pid" ] && kill -0 "$(cat "$AW_STATE/p4/RUNNER.pid")" 2>/dev/null; }; then
      nohup "$VC" -I "$ABL/p4_abl.py" loop >> "$AW_STATE/progress/p4_runner.out" 2>&1 < /dev/null &
      LOG "P4 runner started pid $!"
    fi
    rm -f "$AW_STATE/abl_cc_watch.pid"
    exit 0
  fi
  sleep "$EVERY"
done
