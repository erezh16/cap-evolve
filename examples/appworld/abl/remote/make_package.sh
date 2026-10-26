#!/usr/bin/env bash
# Builds the abl_cc remote package (ledger ABL-0361) on the ORIGINAL pod: the arm's state, its workdir and config dirs,
# the cache records it needs, the reference build manifest, the deny rules and the two documents. Trusted script (R1):
# copies bytes, prints counts and hashes only. Run after sourcing abl/env.sh, with no abl_cc ticket running.
#   bash examples/appworld/abl/remote/make_package.sh OUT_DIR
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ABL="$(cd "$HERE/.." && pwd)"
[ "${AW_LEDGER_ID:-}" = ABL ] || { echo "make_package.sh: source abl/env.sh first" >&2; exit 2; }
OUT="$1"; [ ! -e "$OUT" ] || { echo "make_package.sh: $OUT exists" >&2; exit 2; }
S="$AW_STATE/abl_cc"; R="$AW_HOME/arms/abl_cc"
[ -z "$(ls "$R/work/.eval/requests/"*.json 2>/dev/null)" ] || { echo "make_package.sh: a ticket is still open" >&2; exit 3; }
[ -z "$(ls -A "$S/inflight" 2>/dev/null)" ] || { echo "make_package.sh: episodes still in flight" >&2; exit 3; }
VC="$AW_HOME/build/venvs/venv-abl/bin/python"
mkdir -p "$OUT"/{state_abl_cc,arm_abl_cc,state_root,launch}
"$VC" -I "$ABL/cc/export_cache.py" "$OUT" > "$OUT/.export_cache.json"
# the arm state without what is superseded or host-specific: the inert first freeze and its reset check, A9/A13
# acceptance leftovers, pid files and in-flight markers
for f in evals.jsonl rollouts.jsonl cache_hits.jsonl optimizer_usage.jsonl session_result.json session2_result.json \
         SESSION_STARTED SESSION2_STARTED check_config.json; do
  [ -e "$S/$f" ] && cp -p "$S/$f" "$OUT/state_abl_cc/$f"
done
cp -rp "$S/cands" "$S/claude_calls" "$OUT/state_abl_cc/"
cp -rp "$R/work" "$OUT/arm_abl_cc/work"
for d in "$R"/config*; do cp -rp "$d" "$OUT/arm_abl_cc/"; done
cp -p "$AW_STATE/SEED_BASELINE_DONE" "$OUT/state_root/"
cp -p "$AW_REPO/docs/ABLATION_STATUS_STATE/manifest.json" "$OUT/reference_manifest.json"
cp -p "$AW_HOME/launch/exec-settings.json" "$OUT/launch/"
cp -p "$HERE/ABL_CC_REMOTE.md" "$OUT/"
[ -e "$AW_HOME/export/DEVAGENT_BWRAP_ISSUES.md" ] && cp -p "$AW_HOME/export/DEVAGENT_BWRAP_ISSUES.md" "$OUT/"
chmod -R u+w "$OUT"
"$VC" -I - "$OUT" <<'EOF'
import hashlib, json, subprocess, sys, datetime as dt
from pathlib import Path
out = Path(sys.argv[1])
ev = [json.loads(l) for l in (out / "state_abl_cc" / "evals.jsonl").read_text().splitlines() if l.strip()]
used = sum(1 for l in (out / "state_abl_cc" / "rollouts.jsonl").read_text().splitlines() if l.strip())
done = [e for e in ev if e.get("state") == "done"]
repo = subprocess.run(["git", "-C", "/workspace/worktrees/eval-abl", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
files = {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in sorted(out.rglob("*")) if p.is_file() and not p.is_symlink() and p.name != ".export_cache.json"}
man = {"arm": "abl_cc", "snapshot_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
       "code_commit": repo, "code_branch": "eval-abl", "remote_branch": "eval-abl-cc-remote",
       "export_cache": json.loads((out / ".export_cache.json").read_text()),
       "arm_status": {"evaluations_done": len(done), "evaluations_logged": len(ev),
                      "mean_rewards_done": [e.get("mean_reward") for e in done],
                      "rollouts_used": used, "rollouts_left": 882 - used, "budget": 882,
                      "sessions_started": sorted(p.name for p in (out / "state_abl_cc").glob("SESSION*_STARTED")),
                      "next_session": 3},
       "files": files}
(out / "PACKAGE_MANIFEST.json").write_text(json.dumps(man, indent=1))
(out / ".export_cache.json").unlink()
print(json.dumps({k: man[k] for k in ("snapshot_utc", "code_commit", "export_cache", "arm_status")} | {"files": len(files)}))
EOF
