#!/bin/bash
# base3 gateway watchdog, PAUSE mode (as deployed on fed-ws-1 at ~/b3/gw_watchdog2.sh).
# Probe glm-5-3 every 60 s (1-token completion). After 2 consecutive non-200s, freeze every live base3 run:
# SIGSTOP its PROCESS GROUP and `docker pause` the containers running at that moment. After 2 consecutive
# 200s, unpause exactly those containers and SIGCONT the groups. Runs with a ~/b3/<bench>/HOLD file are skipped
# (operator/agent hold). Every transition is logged into the run's run.log.
# Launch: setsid nohup ~/b3/gw_watchdog2.sh >> ~/b3/gw_watchdog.log 2>&1 < /dev/null &
echo $$ > /home/erezh/b3/gw_watchdog.pid
set -a; . /home/erezh/ce.env; set +a
S=/home/erezh/b3/gw_paused.state; fails=0; oks=0
while true; do
  code=$(curl -s -m 60 -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $OPENAI_API_KEY" -H "content-type: application/json" \
    "$OPENAI_BASE_URL/v1/chat/completions" -d "{\"model\":\"rits/zai-org/glm-5-3\",\"max_tokens\":1,\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}")
  if [ "$code" = "200" ]; then fails=0; oks=$((oks+1)); else oks=0; fails=$((fails+1)); echo "$(date -u +%FT%TZ) probe http=$code fails=$fails"; fi
  if [ $fails -ge 2 ] && [ ! -f $S ]; then
    : > $S
    for c in $(docker ps -q --filter status=running); do docker pause $c >/dev/null 2>&1 && echo "container $c" >> $S; done
    for b in ssb swe; do
      pf=/home/erezh/b3/$b/run.pid; [ -f $pf ] || continue; p=$(cat $pf)
      [ -f /home/erezh/b3/$b/HOLD ] && continue   # operator/agent hold: never touched by the watchdog
      if kill -0 $p 2>/dev/null; then g=$(ps -o pgid= -p $p | tr -d " "); kill -STOP -- -$g && echo "group $g $b" >> $S
        echo "WATCHDOG_PAUSE $(date -u +%FT%TZ) http=$code pgid=$g containers=$(grep -c ^container $S)" | tee -a /home/erezh/b3/$b/run.log; fi
    done
  fi
  if [ $oks -ge 2 ] && [ -f $S ]; then
    for c in $(awk '/^container/{print $2}' $S); do docker unpause $c >/dev/null 2>&1; done
    while read -r kind g b; do [ "$kind" = group ] || continue; kill -CONT -- -$g
      echo "WATCHDOG_RESUME $(date -u +%FT%TZ) pgid=$g" | tee -a /home/erezh/b3/$b/run.log; done < $S
    mv $S $S.$(date -u +%Y%m%dT%H%M%SZ)
  fi
  sleep 60
done
