# Launcher scripts as deployed on fed-ws-1 (for reconstruction if ~/b3 is lost)

All launchers write their own PID as the first line, run in their own session (`setsid nohup … &`),
and log `START` / `BASELINE_EXIT` / `FINALIZE_EXIT` / `RUN_END` / `TEST_MOSTLY_INFRA` / `WATCHDOG_*` / `HOLD*`
lines into `~/b3/<bench>/run.log`.

## ~/b3/ssb/env.sh  (usage: `. env.sh <split_ids.json> <agent_view_dir>`)
```bash
set -a; . ~/ce.env; set +a
unset API_BASE OPENAI_API_BASE ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN ANTHROPIC_API_KEY
export MODEL=litellm_proxy/rits/zai-org/glm-5-3
export LITELLM_PROXY_API_BASE="$OPENAI_BASE_URL" API_KEY="$OPENAI_API_KEY"
export MAX_TOKENS=8000 TEMPERATURE=0.0
export SPREADSHEETBENCH_MAX_TURNS=30 SPREADSHEETBENCH_SCORING=hard SPREADSHEETBENCH_AGENT_VIEW=1
export SPREADSHEETBENCH_HARNESS_DIR=~/b3/repo/benchmarks/spreadsheetbench/harness
export SPREADSHEETBENCH_DATA_DIR=~/b3/data/ssb/spreadsheetbench_verified_400
export SPREADSHEETBENCH_LIBREOFFICE_BIN=/usr/bin/soffice
export SPREADSHEETBENCH_AGENT_VIEW_DIR="$2"
export SPREADSHEETBENCH_TASK_IDS=$(~/b3/venv/bin/python -c "import json,sys;s=json.load(open(sys.argv[1]));print(','.join(dict.fromkeys(s['train']+s['val']+s['test'])))" "$1")
export SPREADSHEETBENCH_CONCURRENCY=${SPREADSHEETBENCH_CONCURRENCY:-2}
export CAPEVOLVE_ERRORED_TRIAL_POLICY=drop
export TMPDIR=~/b3/tmp PYTHONUNBUFFERED=1
. ~/b3/venv/bin/activate
```

## ~/b3/ssb/run3.sh  (finalize retry on run_real2; the latest spreadsheetbench launcher)
```bash
#!/bin/bash
echo $$ > /home/erezh/b3/ssb/run.pid
P=/home/erezh/b3/ssb/base/project; S=$P/inputs/split_ids.json
V=/home/erezh/b3/ssb/view_real3; mkdir -p $V          # use a NEW empty view dir for each relaunch
. /home/erezh/b3/ssb/env.sh $S $V
cd /home/erezh/b3/ssb; R=/home/erezh/b3/ssb/run_base/run_real2
echo "START $(date -u +%FT%TZ) concurrency=$SPREADSHEETBENCH_CONCURRENCY run=real2 finalize retry"
[ -z "$(ls -A $R/rollouts/test 2>/dev/null)" ] || { echo "RUN_END refused: test rollouts exist"; exit 4; }
echo "BASELINE_EXIT 0 reused $(date -u +%FT%TZ)"
python /home/erezh/b3/repo/skills/phases/finalize/scripts/run.py --run-dir $R --project $P --n-trials 5
rc=$?; echo "FINALIZE_EXIT $rc $(date -u +%FT%TZ)"
python /home/erezh/b3/infra_gate.py $R/rollouts/test || echo "TEST_MOSTLY_INFRA $(date -u +%FT%TZ)"
echo "RUN_END done rc=$rc"
```

## ~/b3/swe/env.sh  (usage: `. env.sh <split_ids.json>`)
```bash
set -a; . /home/erezh/ce.env; set +a
for v in $(env | grep -o "^ANTHROPIC_[A-Z_]*"); do unset $v; done
export HARBOR_DATASET=swe-bench/swe-bench-verified HARBOR_AGENT=claude-code HARBOR_MODEL=rits/zai-org/glm-5-3
export HARBOR_AGENT_BASE_URL="$OPENAI_BASE_URL" HARBOR_AGENT_API_KEY="$OPENAI_API_KEY"
export HARBOR_EXTRA_FLAGS="--agent-setup-timeout-multiplier 3 --max-retries 2" HARBOR_TIMEOUT=3600
export HARBOR_PARALLEL=${HARBOR_PARALLEL:-2}
export HARBOR_JOBS_DIR=/home/erezh/b3/swe/jobs TMPDIR=/home/erezh/b3/swe/tmp
export HARBOR_TASK_IDS=$(/home/erezh/b3/venv/bin/python -c "import json,sys;s=json.load(open(sys.argv[1]));print(','.join(dict.fromkeys(s['train']+s['val']+s['test'])))" "$1")
export PYTHONPATH=/home/erezh/b3/repo:/home/erezh/b3/swe/base/project/adapters
export CAPEVOLVE_ERRORED_TRIAL_POLICY=drop PYTHONUNBUFFERED=1
export PATH=/home/erezh/.local/bin:$PATH
. /home/erezh/b3/venv/bin/activate
export HOME=/home/erezh/b3/home-swe CLAUDE_CONFIG_DIR=/home/erezh/b3/home-swe/.claude   # isolates ~/.claude/settings.json
```
NB: after `HOME` is changed, `~` means the private home — use absolute paths in launchers.

## ~/b3/swe/run3.sh  (fresh run dir run_real3; the latest swe_bench launcher)
```bash
#!/bin/bash
echo $$ > /home/erezh/b3/swe/run.pid
P=/home/erezh/b3/swe/base/project; S=$P/inputs/split_ids.json
. /home/erezh/b3/swe/env.sh $S
cd /home/erezh/b3/swe
echo "START $(date -u +%FT%TZ) parallel=$HARBOR_PARALLEL n_ids=$(echo $HARBOR_TASK_IDS | tr , "\n" | wc -l)"
python /home/erezh/b3/repo/skills/phases/baseline/scripts/run.py --base /home/erezh/b3/swe/run_base --project $P --capability $P/seed_capability --seed 0 --split-ids $S --n-trials 5 --max-iterations 0 --spec $P/capevolve.yaml --run-ts real3
rc=$?; echo "BASELINE_EXIT $rc $(date -u +%FT%TZ)"
[ $rc -eq 0 ] || { echo "RUN_END failed-baseline"; exit $rc; }
python /home/erezh/b3/infra_gate.py /home/erezh/b3/swe/run_base/run_real3/rollouts/val || { echo "RUN_END infra-gate-stop $(date -u +%FT%TZ)"; exit 3; }
python /home/erezh/b3/repo/skills/phases/finalize/scripts/run.py --run-dir /home/erezh/b3/swe/run_base/run_real3 --project $P --n-trials 5
rc=$?; python /home/erezh/b3/infra_gate.py /home/erezh/b3/swe/run_base/run_real3/rollouts/test || echo "TEST_MOSTLY_INFRA $(date -u +%FT%TZ)"; (exit $rc)
rc=$?; echo "FINALIZE_EXIT $rc $(date -u +%FT%TZ)"; echo "RUN_END done rc=$rc"
```
A finalize-only retry for swe_bench (if `run_real3` has no test rollouts) is the same as the ssb run3.sh pattern:
skip baseline, refuse if `rollouts/test` is non-empty, run finalize, run the test infra gate.

## ~/b3/sb/env.sh (skillsbench — COMPLETED, kept for reference)
SKILLSBENCH_MODEL=rits/zai-org/glm-5-3, SANDBOX=docker, AGENT_BASE_URL=$OPENAI_BASE_URL (no /v1),
OPENAI_BASE_URL=$OPENAI_BASE_URL/v1, TASKS_DIR=~/b3/skillsbench/tasks, TASK_TIMEOUT=2400, CONCURRENCY=2,
BENCH_CWD=~/b3/sb/bench_cwd, SKILLSBENCH_BENCH_BIN=/home/erezh/.local/bin/bench, private HOME=~/b3/home-sb.
