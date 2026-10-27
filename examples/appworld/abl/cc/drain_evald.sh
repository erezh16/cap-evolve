#!/usr/bin/env bash
# After the abl_cc session ends (docs/ABLATIONS.md §10.2): every evaluation the session requested still counts, so
# wait until the daemon has taken every request and no episode is in flight, then stop it. Prints counts only.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ABL="$(cd "$HERE/.." && pwd)"
. "$ABL/env.sh"
S="$AW_STATE/abl_cc"; W="$AW_HOME/arms/abl_cc/work"
pending() { ls "$W/.eval/requests/"*.json 2>/dev/null | wc -l; }
inflight() { ls -A "$S/inflight" 2>/dev/null | wc -l; }
alive() { [ -f "$S/EVALD.pid" ] && kill -0 "$(cat "$S/EVALD.pid")" 2>/dev/null; }
echo "drain_evald: $(date -u +%FT%TZ) pending $(pending), in flight $(inflight)"
while alive && { [ "$(pending)" -gt 0 ] || [ "$(inflight)" -gt 0 ]; }; do sleep 30; done
# a ticket being handled has already left the queue: wait for its result to be logged (the request file is renamed last)
while alive && ls "$W/.eval/results/"*/status.json >/dev/null 2>&1 \
      && grep -lq '"state": "\(running\|queued_to_run\)"' "$W/.eval/results/"*/status.json 2>/dev/null; do sleep 30; done
if alive; then kill "$(cat "$S/EVALD.pid")"; sleep 3; fi
alive && { echo "drain_evald: evald did not stop" >&2; exit 1; }
echo "drain_evald: $(date -u +%FT%TZ) done; evaluations logged $(wc -l < "$S/evals.jsonl"), rollouts $(wc -l < "$S/rollouts.jsonl") of 882"
