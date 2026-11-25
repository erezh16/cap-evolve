# Seed baselines with glm-5-3, part 2: spreadsheetbench, swe_bench, skillsbench on a Docker host

**For:** a coding agent running these three evaluations on a Linux host that has a Docker engine
(with DinD available) and no cluster image policy.

**Goal:** for each benchmark below, measure its **stock seed capability** on its **test split**,
5 trials per task, with `glm-5-3` in every model role. Report each one on the GitHub issue that
already exists for it.

This plan narrows [baseline.md](baseline.md) to three benchmarks. Read baseline.md as well: its
§1.1–1.2 (environment, model), §2 (procedure, what to record), §4 (tracking) and §5 (final
report) apply here unchanged, except where this document says otherwise. This document adds
what the first attempt learned. That attempt ran on an OpenShift context and was stopped
(see §0).

| Benchmark | Issue | Example / adapter | Test split | Primary score |
|---|---|---|---|---|
| spreadsheetbench (verified_400) | [#1001](https://github.com/skillberry-ai/cap-evolve/issues/1001) | `benchmarks/spreadsheetbench/template` | 280 tasks (`ci/benchmarks/spreadsheetbench/full_verified/split_ids.json`) | `hard_no_recalc` (`hard_restriction` secondary) |
| skillsbench | [#1002](https://github.com/skillberry-ai/cap-evolve/issues/1002) | `benchmarks/skillsbench/template` (+ `examples/shared_skills/` for config, split and seed) | 3 tasks | mean binary verifier reward |
| swe_bench (Verified) | [#1003](https://github.com/skillberry-ai/cap-evolve/issues/1003) | Harbor: `benchmarks/generic/harbor/template` | 100 tasks (`ci/benchmarks/swebench/full/split_ids.json`) | resolved rate |

Each benchmark has its own score, scale and test size. Never average or rank across benchmarks.

---

## 0. Where things stand (read before starting)

The first attempt (2026-11-19) ran on OpenShift context `erezh-sa@erezh-ocp-int-2`. **None of
these three benchmarks has a test score. All three are restarted from scratch on the new host.**

- **spreadsheetbench (#1001)** used a project-local Kubernetes backend. Mid-run, the cluster
  started enforcing image policies ("Block images older than 1 year", "Block Critical CVE older
  than 180 days") that reject `docker.io/xingyaoww/codeact-executor`. 88 of the 200 val episodes
  were denied. The run was stopped before any test rollout was written.
  - **Do not reuse that run's val number.** It is 0.696 over 112 of 200 episodes, biased by which
    episodes happened to run before enforcement.
  - On a Docker host the Kubernetes backend is **not needed**: use the stock adapter.
- **swe_bench (#1003)** ran through Harbor on OpenShift (`-e openshift`, with three patches to
  Harbor). The same image policy rejected the `sweb.eval.*` task images, and builds also hit
  Docker Hub's anonymous pull limit and the namespace ConfigMap quota. It was stopped during val
  trial 0, before any test rollout.
  - On a Docker host, use Harbor's **default `docker` environment**. None of the OpenShift
    patches apply.
- **skillsbench (#1002)** was recorded as **infeasible** on that context: BenchFlow needs a Docker
  engine, and DinD needed a privileged pod, which the cluster's security constraints denied.
  Nothing ran. It is now feasible on a host with Docker.

**First action on each issue:** post a "context change" comment. Say that the evaluation moves
to a Docker host, give the host description (OS, Docker version, CPU, memory, disk), say that
the earlier OpenShift results are void and no score from them will be reported, and say that
the run restarts in a fresh run dir. For #1002, say that the infeasible verdict is superseded.

---

## 1. Common rules (deltas from baseline.md §1)

### 1.1 Environment

- **CA bundle, memory, long jobs, credentials:** as in baseline.md §1.1. In a devagent
  workspace, run `memcheck` (docs/CONTAINER_AGENT.md §2.3). On a plain host, size from the real
  memory and CPU limits. Either way: stop starting new episodes at 85% memory, resume below 75%.
- **Write each job's own PID** from inside its launcher (`echo $$ > <base>.pid` as the first line
  of the run script). Do not use `$!` from a wrapper shell: it captured the wrong PID twice in the
  first attempt.
- **Never kill by name pattern.** Kill by PID or process group only.
- **Container restarts kill everything.** In the first attempt, a workspace container restart
  killed a running benchmark and the agent session with it, and nothing was posted for 15 h. After
  any restart: find out why if you can, relaunch with **fewer** workers, and say so on the issue.
- **Disk:** the executor image is 13.7 GB. SWE-bench task images are 1–4 GB each, about 150
  distinct images for val + test. Check `docker system df` and free disk before starting, and
  keep Harbor's jobs dir and `TMPDIR` off a small root filesystem.
- **Docker Hub rate limit:** anonymous pulls hit `toomanyrequests` in the first attempt. Run
  `docker login` with a Docker Hub account before starting, or pre-pull images with retries. A
  pull failure is an **infrastructure** error: retry it, never score it.

### 1.2 The model

As in baseline.md §1.2. The gateway is `https://litellm.cb.ete.res.ibm.com`, and the repo-root
`.env` holds `OPENAI_BASE_URL`, `OPENAI_API_KEY` and `OPENAI_MODEL_NAME=rits/zai-org/glm-5-3`.

- **Check the key first.** It was valid on 2026-11-19.
- **Check from inside a container too.** For skillsbench and swe_bench the agent runs **inside**
  the task container, so it must reach the gateway from there. Test with `docker run --rm curlimages/curl …`.
- The gateway accepts both `Authorization: Bearer` and `x-api-key` on `/v1/messages`.
- **Claude Code agents:** set **every** model slot to `rits/zai-org/glm-5-3`
  (`ANTHROPIC_MODEL`, `ANTHROPIC_SMALL_FAST_MODEL`, `ANTHROPIC_DEFAULT_{OPUS,SONNET,HAIKU}_MODEL`,
  `CLAUDE_CODE_SUBAGENT_MODEL`). Check that each run's `modelUsage` / `model_usage` shows only
  glm-5-3.
- **Isolate from the operator's own Claude settings.** A harness that forwards `HOME` lets the
  agent CLI read the operator's `~/.claude/settings.json`, whose `env` block overrides the
  gateway and key. That produced a 403 in the first attempt. Give agent processes a private `HOME`
  or `CLAUDE_CONFIG_DIR`.

### 1.3 Seeds, splits and the baseline phase

- Use `split_seed=0` for all three benchmarks. Trials are seeds 0..4.
- The stock `phases/baseline` scores the seed on **val and on train** (it skips train only when
  the train ids equal the val ids). The plan asks for val + test only. To skip the train
  evaluation, give the run a split file with `train := val`; keep val and test exactly as
  committed. Record this as a deviation. skillsbench's committed split already has train == val.
- `phases/finalize` scores the sealed test split **once**. A crash after test rollouts exist
  means a fresh run dir. Rollouts are written when an evaluation **completes**, not per episode,
  for adapters that pool their own trials (all three here). So:
  - partial scores are not visible mid-grid;
  - track live progress from the benchmark's native artifacts (§2–§4 say which);
  - **if most episodes are failing as infra, stop the run before finalize writes test rollouts.**
    Never seal a test result that is mostly infra errors.

---

## 2. spreadsheetbench (verified_400)

**Setup**
- **Data:** `SPREADSHEETBENCH_VARIANT=verified_400 ci/benchmarks/spreadsheetbench/fetch_data.sh <dest>`.
  This downloads from GitHub `main`. The first attempt verified that tree to be **file-for-file
  identical** to HF `KAKA22/SpreadsheetBench` @ `ab0b742b0fc95b946f212d80ac7771b5531272e4`.
  Re-check with `diff -rq` against
  `https://huggingface.co/datasets/KAKA22/SpreadsheetBench/resolve/ab0b742b…/spreadsheetbench_verified_400.tar.gz`,
  and record the result.
- **Project:** scaffold with `skills/phases/intake/scripts/run.py --base <dir> --workdir <dir> --force`,
  in a **private** base, not the repo's shared `.capevolve/`. Then:
  - copy `adapter.py` and `benchmarks/_shared/model_config.py` into `<project>/adapters/`;
  - copy `seed_capability/` (`prompt.md`, `task_template.md`);
  - write a `capevolve.yaml` with `capabilities: [system-prompt]`, `capability_path: seed_capability`,
    `split_ids_file`, `split_seed: 0`, `max_iterations: 0`.
- **Packages:** `pip install pandas openpyxl docker tornado requests litellm` and `-e core`.
- **LibreOffice is required for `hard_restriction`.** With root, use the distro package. Without
  root: extract the LibreOffice AppImage (`--appimage-extract`), `apt-get download` the missing X11/
  NSS/cairo/glib libraries (with private `Dir::State::Lists`/`Dir::Cache`), unpack them with
  `dpkg-deb -x`, and use a wrapper script that sets `LD_LIBRARY_PATH`. Point
  `SPREADSHEETBENCH_LIBREOFFICE_BIN` at it. Test one headless `--convert-to xlsx`.
- **Containers:** the stock Docker backend, one `codeact-executor` container per rollout
  (8 GB / 2 CPU caps, uid 1000), with the gold-free agent view bind-mounted at `/mnt/data`.
  - Pre-pull the image (`docker pull docker.io/xingyaoww/codeact-executor`, 13.7 GB) before the
    smoke test, so the first episodes don't spend minutes on the pull.
  - The adapter runs `_preflight_mount` before any LLM call. Make sure it passes.

**Settings** (baseline.md §3.3):
- `MODEL=litellm_proxy/rits/zai-org/glm-5-3`, `LITELLM_PROXY_API_BASE=$OPENAI_BASE_URL`,
  `API_KEY=$OPENAI_API_KEY`.
- Leave `API_BASE` and `OPENAI_API_BASE` **unset**: `model_config.py` prefers them over
  `LITELLM_PROXY_API_BASE`.
- `MAX_TOKENS=8000`, `TEMPERATURE=0.0`, `SPREADSHEETBENCH_MAX_TURNS=30`,
  `SPREADSHEETBENCH_SCORING=hard`, `SPREADSHEETBENCH_AGENT_VIEW=1`.
- Pin `SPREADSHEETBENCH_AGENT_VIEW_DIR` to an empty, per-run dir.
- `SPREADSHEETBENCH_CONCURRENCY`: 3–4 per 32 GiB / 8 CPU. Size from the host.

**Smoke:** 2 train tasks, 1 trial. The first attempt scored 2/2 (tasks `10452` and `105-24`) with
5 and 4 LLM calls and 16k and 35k tokens. Check per rollout: no `metadata.error_kind="infra"`,
non-zero tokens, the output file exists, and a sensible LLM-call count.

**Run:** baseline (val 40 × 5), then finalize (test 280 × 5): 1,600 episodes. The first attempt
measured about 1.2–1.4 episodes/min at concurrency 6, so plan for about 20 h at 4–6. Report ETAs
from measured rates.

**What to record:**
- The stock adapter stores **total** tokens only, and no per-episode time. Add, in a
  **project-local copy** of the adapter (recorded as a deviation):
  - a wrapper around `run_target` that stamps `episode_start`, `episode_end` and
    `episode_seconds` into `Rollout.metadata`;
  - prompt and completion token sums, plus the number of LLM calls, accumulated where the
    adapter adds `usage.total_tokens`.
- A patch that did exactly this (alongside the Kubernetes backend, which you do **not** need) is
  in the first attempt's notes; see §6.
- **Live progress:** the adapter pools its own trials, so there is no per-episode harness event.
  Count the per-rollout output dirs under `<agent_view>/outputs/` (one per started episode) and
  running `docker ps` containers.

**Score:**
- Primary: `hard_no_recalc`. Secondary: `hard_restriction`, which needs LibreOffice.
- Report `n_scored` and the infra count. If more than half the rollouts are infra, the run is not
  a measurement.

---

## 3. skillsbench

**Setup**
- **Clone:** `GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/benchflow-ai/skillsbench`, then
  `git checkout bf3793e9ec20e9682e6f18dbf4de3c69163dc9c7` (the pin; it is reachable in a full
  clone).
- **Runner:** `uv tool install benchflow==0.6.4`, which provides the `bench` CLI. Set
  `SKILLSBENCH_TASKS_DIR=<clone>/tasks` (offline).
- **Seed:** copy, don't symlink (symlinked skills are skipped), into `<project>/seed_capability/`:
  - `docx` from `tasks/offer-letter-generator/environment/skills/docx`;
  - `pptx` and `xlsx` from `tasks/exceltable-in-ppt/environment/skills/`;
  - `pdf` from `tasks/pdf-excel-diff/environment/skills/pdf`.
- **Config:** take `capevolve.yaml` (set `max_iterations: 0`) and `split_ids.json` from
  `benchmarks/skillsbench/examples/shared_skills/`. The adapter is `benchmarks/skillsbench/template/adapter.py`.
- **Split:** train = val (7 tasks); **test = 3 tasks**: `pdf-excel-diff`,
  `pptx-reference-formatting`, `reserves-at-risk-calc`.

**Containers:**
- `SKILLSBENCH_SANDBOX=docker`. BenchFlow builds each task's `environment/Dockerfile`
  (ubuntu:24.04 plus LibreOffice and similar) and runs Claude Code inside it.
- Check the sandbox can reach the gateway (§1.2).
- If the host's Docker is DinD, check that BenchFlow's LiteLLM usage proxy and the bridge-gateway
  address it binds are reachable from the task containers. This path is **not yet exercised**;
  verify it in the smoke test.

**Agent model:**
- `SKILLSBENCH_MODEL=rits/zai-org/glm-5-3`, `SKILLSBENCH_AGENT_BASE_URL=$OPENAI_BASE_URL`,
  `SKILLSBENCH_AGENT_API_KEY=$OPENAI_API_KEY`.
- The template adapter's `_gateway_env()` passes only `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN`
  (plus an OpenAI mirror) as `--agent-env`. Check whether BenchFlow sets the other Claude Code
  model slots from `--model`. If not, add them as extra `--agent-env` entries in a
  **project-local** adapter copy (deviation).
- Probe `/v1/messages` with glm-5-3 first, then confirm the smoke run's agent usage shows only
  glm-5-3.

**Concurrency / timeouts:** `SKILLSBENCH_CONCURRENCY` (default 7); measure memory.
`SKILLSBENCH_TASK_TIMEOUT` (2400 s).

**Smoke:** 1 train task, 1 trial. Check four things:
- a verifier reward exists;
- the agent ran on glm-5-3 only;
- tokens come from BenchFlow's per-trial `result.json` under `<run>/bench_jobs/…` (the adapter
  stores 0);
- there are no infra errors.

**Score:** mean over the 3 test tasks of each task's trial-mean binary reward, plus pass^k.
- Report **per-task** results: one task moves the mean by 0.33.
- `reserves-at-risk-calc` has a known broken oracle that caps it.

---

## 4. swe_bench (Verified), via Harbor on Docker

**Path:** Harbor (`benchmarks/generic/harbor/template`), Claude Code as the agent, Harbor's
default `docker` environment.
- This is CI's only swebench path (`ci/benchmarks/lib/run_suite.sh`). The litellm single-shot
  path is not used in CI.
- baseline.md also allows `benchmarks/swe_bench/template` with a Docker engine. If you choose
  that instead, say why on #1003.
- Use **one path for all 5 trials**.
- The seed is the template's `seed_capability/`. The adapter passes the first non-empty of
  `prompt.md`/`SKILL.md` as `--extra-instruction-path`, which here is `prompt.md`.

**Setup**
- `uv tool install harbor` (0.26.0 in the first attempt; record the version).
- Copy the adapter to `<project>/adapters/`. Put the repo root on `PYTHONPATH` for
  `capevolve_harbor`.
- **Project-local adapter fix (deviation):** `_build_agent_env()` sets only
  `ANTHROPIC_MODEL` and `ANTHROPIC_DEFAULT_{SONNET,HAIKU,OPUS}_MODEL`. Add
  `ANTHROPIC_SMALL_FAST_MODEL` and `CLAUDE_CODE_SUBAGENT_MODEL` set to `HARBOR_MODEL`.
- **Env:**
  - `HARBOR_DATASET=swe-bench/swe-bench-verified`, `HARBOR_AGENT=claude-code`,
    `HARBOR_MODEL=rits/zai-org/glm-5-3`;
  - `HARBOR_AGENT_BASE_URL=$OPENAI_BASE_URL`, `HARBOR_AGENT_API_KEY=$OPENAI_API_KEY`;
  - unset any ambient `ANTHROPIC_*`;
  - `HARBOR_EXTRA_FLAGS="--agent-setup-timeout-multiplier 3"`, `HARBOR_TIMEOUT=3600`;
  - `HARBOR_JOBS_DIR` and `TMPDIR` on a large disk.
- **`HARBOR_TASK_IDS` must list every id of the run's split.** The adapter's `tasks()` returns
  exactly that list.
- Pre-fetch the task definitions with `harbor download swe-bench/swe-bench-verified --cache`
  (500 tasks, one version each).
- Each task's Dockerfile is `FROM swebench/sweb.eval.x86_64.<id>:latest` plus `uv` and `/logs`.
  **Pre-pulling the ~150 base images** (val + test), with retries, before the run avoids pull
  failures and long first trials. With `docker login` this is easy.

**Settings:**
- `HARBOR_PARALLEL`: CI uses 6 on a 32-core host (16 overloaded it). Each task container runs a
  real test suite (task.toml: 1 CPU, 4 GB, 10 GB storage). Size from the host.
- The task instruction is the issue's problem statement only. **`hints_text` is not included**
  (checked for `astropy__astropy-12907`, 1,246 bytes). `SWEBENCH_ORACLE` does not apply. Say both
  on #1003.

**Smoke:** 1 train task, 1 trial. The first attempt on OpenShift **resolved**
`astropy__astropy-12907`:
- `model_usage` showed only glm-5-3;
- tokens were 275,532 in (251,904 cached) and 2,669 out;
- phase times: environment 5m27s, agent setup 1m41s, agent 2m02s, verifier 1m27s.

The smoke must show at least one valid, applicable patch.

**What to record:**
- The adapter stores tokens as 0 and has no per-episode time. Take both from Harbor's per-trial
  `result.json`:
  - `agent_result.n_input_tokens`, `n_cache_tokens`, `n_output_tokens`, `model_usage`;
  - `started_at`/`finished_at` and the per-phase `environment_setup`, `agent_setup`,
    `agent_execution` and `verifier` timestamps.
- `exception_info` non-null means infra (excluded); count it.
- `harbor_reward` / `verifier_result.rewards.reward` is the per-instance resolved flag.
- **Live progress:** the adapter's `run_trials` runs one full `harbor run` per trial,
  sequentially, so there are no harness events mid-grid. Count the per-trial `result.json` files
  under `HARBOR_JOBS_DIR` written since the run started.

**Run:** baseline (val 50 × 5), then finalize (test 100 × 5). In the first attempt a trial took
about 10–45 min including the in-trial image build; pre-pulled images make that much shorter.
Report ETAs from measured rates.

**Score:** resolved rate. "Patch Apply Failed", empty and non-diff outputs score 0. Exceptions,
missing reports and timeouts are infra: excluded, and counted.

---

## 5. Tracking (deltas from baseline.md §4)

- **Issues:** use the existing ones: #1001 (spreadsheetbench), #1002 (skillsbench), #1003
  (swe_bench). **Do not open new issues.**
  - Post the setup as actually run (provenance, mapping, settings, deviations) on each issue
    before the real run.
  - When all three are done, post a connecting update on **#975**: a table mapping each
    benchmark to its issue and result, saying scores are per benchmark and not comparable.
- **Hourly, on every issue whose final report is not yet posted**, use a **durable** recurring
  job (one that survives a session or container restart). A session-only job died with the
  workspace in the first attempt.
- **Each hourly comment states the run's STATE explicitly:**
  - running;
  - terminated, with the reason and time (crash, container restart, infra block, operator
    stop);
  - blocked, and on what;
  - completed.
- **For a running benchmark, each comment also gives:**
  - a **stall verdict** with its basis: minutes since the last activity of any kind (rollout
    files, harness `eval_progress` events, or the native artifacts named above). More than 30 min
    with episodes expected means **stalled**;
  - process alive (PID file), infra-error count, memory %, and a restart check;
  - progress (episodes done / total) and partial per-trial scores where visible;
  - an **ETA in UTC with its basis** (measured episodes/min × remaining).
- **Fix and relaunch** anything stalled or dead: a fresh run dir if test rollouts exist, and
  fewer workers after a restart. Say what you did on the issue.
- Watch each run's end directly (a background wait on its PID or status file), so the final
  report is posted when the run ends, not at the next hourly tick.

## 6. Final report (per issue)

As baseline.md §5:
- the headline as mean ± std over the 5 trials;
- tokens and serial time;
- coverage and the errored-trial count;
- a per-trial table;
- per-episode mean ± std;
- provenance (SHAs, dataset revision, package versions, Docker version, host);
- deviations.

Every number must come from the run's own files. For an infeasible or blocked benchmark, give
the failing check and no score.

**Material from the first attempt** (on the original workspace, for reference; it may not be
reachable from the new host): `/workspace/seedbase/` holds per-benchmark setup, env
templates (no keys committed), `ssb/k8s_patch.py` (which includes the per-episode
timing and token stamping for the spreadsheetbench adapter), `swe/harbor_openshift.patch` (not
needed on Docker), `swe/prebuild.py` and `status.py` (the hourly status and stall collector). The
issue threads #1001–#1003 record every finding listed above.
