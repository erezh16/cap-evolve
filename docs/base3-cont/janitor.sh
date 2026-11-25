#!/bin/bash
# base3 disk janitor for swe_bench (as deployed at ~/b3/swe/janitor.sh). Started with LOW=26 HIGH=36.
# When / has < LOW GB free: prune BuildKit cache unused for 30 min (swebench base images live in the build
# cache, NOT as named images), then remove idle swebench/sweb.eval.* named images oldest-pull-first with plain
# `docker rmi` (never -f) until HIGH GB free. Touches nothing else.
# Launch: LOW=26 HIGH=36 setsid nohup ~/b3/swe/janitor.sh >> ~/b3/swe/janitor.log 2>&1 < /dev/null &
echo $$ > /home/erezh/b3/swe/janitor.pid
LOW=${LOW:-22}; HIGH=${HIGH:-32}
free_gb(){ df --output=avail -B1G / | tail -1 | tr -d " "; }
while true; do
  if [ "$(free_gb)" -lt "$LOW" ]; then
    echo "$(date -u +%FT%TZ) free=$(free_gb)G < $LOW: pruning"
    docker builder prune -af --filter unused-for=30m 2>&1 | tail -1
    for img in $(for i in $(docker images --format "{{.Repository}}:{{.Tag}}" | grep "^swebench/sweb\.eval\."); do printf "%s\t%s\n" "$(docker image inspect --format "{{.Metadata.LastTagTime}}" $i)" "$i"; done | sort | cut -f2); do
      [ "$(free_gb)" -ge "$HIGH" ] && break
      docker rmi "$img" >/dev/null 2>&1 && echo "  removed $img (free=$(free_gb)G)"
    done
  fi
  sleep 120
done
