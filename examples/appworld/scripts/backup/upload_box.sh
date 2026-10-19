#!/usr/bin/env bash
# Copy each assembled run folder to Box as a plain folder tree, verify it, and time it (docs/BACKUP_BOX.md §6).
#   bash upload_box.sh BACKUP_DIR [REMOTE]     REMOTE defaults to eval-data:appworld
# Uses `rclone copy`, never `sync`, so nothing already on Box is deleted. Adds T2 to BACKUP_DIR/timing.json.
set -euo pipefail
SRC="${1:?backup dir}"
REMOTE="${2:-eval-data:appworld}"
RCLONE="${RCLONE:-$HOME/.local/bin/rclone}"
LOGS="$SRC/_upload_logs"
mkdir -p "$LOGS"

t_start=$(date +%s.%N)
declare -A secs
for d in "$SRC"/20*/; do
  run="$(basename "$d")"
  t0=$(date +%s.%N)
  "$RCLONE" copy "$d" "$REMOTE/$run" --transfers 8 --checkers 16 --stats 60s --stats-one-line \
    --log-file "$LOGS/$run.copy.log" --log-level INFO
  t1=$(date +%s.%N)
  secs[$run]=$(python3 -c "print(round($t1 - $t0, 2))")
  echo "$(date -u +%FT%TZ) copied $run in ${secs[$run]} s"
done
t_end=$(date +%s.%N)

# verify: Box keeps SHA-1 per file, so this compares content, not just names and sizes
check_rc=0
for d in "$SRC"/20*/; do
  run="$(basename "$d")"
  if "$RCLONE" check "$d" "$REMOTE/$run" --one-way --checkers 16 \
       --combined "$LOGS/$run.check.txt" --log-file "$LOGS/$run.check.log" --log-level INFO; then
    echo "$(date -u +%FT%TZ) check $run: 0 differences"
  else
    echo "$(date -u +%FT%TZ) check $run: DIFFERENCES (see $LOGS/$run.check.txt)"; check_rc=1
  fi
done
t_verified=$(date +%s.%N)

python3 - "$SRC/timing.json" "$t_start" "$t_end" "$t_verified" "$REMOTE" "$check_rc" \
  "$(for k in "${!secs[@]}"; do printf '%s=%s;' "$k" "${secs[$k]}"; done)" <<'EOF'
import json, sys
from datetime import datetime, timezone
path, ts, te, tv, remote, rc, per = sys.argv[1:8]
t = json.load(open(path))
ts, te, tv = float(ts), float(te), float(tv)
t["t2_transfer_start_utc"] = datetime.fromtimestamp(ts, timezone.utc).isoformat()
t["t2_transfer_end_utc"] = datetime.fromtimestamp(te, timezone.utc).isoformat()
t["transfer_seconds"] = round(te - ts, 2)
t["verify_on_box_seconds"] = round(tv - te, 2)
t["transfer_per_run_seconds"] = {kv.split("=")[0]: float(kv.split("=")[1]) for kv in per.split(";") if kv}
t["remote"] = remote
t["remote_check_ok"] = rc == "0"
t["total_seconds_capture_plus_transfer"] = round(t["capture_seconds"] + t["transfer_seconds"], 2)
json.dump(t, open(path, "w"), indent=1)
print(json.dumps({k: t[k] for k in ("capture_seconds", "transfer_seconds", "verify_on_box_seconds",
                                    "total_seconds_capture_plus_transfer", "remote_check_ok")}, indent=1))
EOF
exit $check_rc
