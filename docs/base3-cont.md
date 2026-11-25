# base3 continuation: finishing the three glm-5-3 seed baselines

**For:** the agent that picks up [base3.md](base3.md) after the first Docker-host agent stopped.
Read base3.md first; it is the plan. This document records what has already been done, what state
everything was last seen in, what is broken, and exactly what is left. Written 2026-11-25 19:40 UTC.

Helper scripts used so far are in [base3-cont/](base3-cont/). They are copies of what runs on the host,
in case the host's `~/b3` is lost.

---

## 0. Status at handoff

| Benchmark | Issue | State | What is left |
|---|---|---|---|
| skillsbench | [#1002](https://github.com/skillberry-ai/cap-evolve/issues/1002) | **COMPLETED**, final report posted | nothing (only the #975 summary row) |
| spreadsheetbench (verified_400) | [#1001](https://github.com/skillberry-ai/cap-evolve/issues/1001) | **unknown**: last seen ON HOLD (SIGSTOPped) mid-test, awaiting an operator decision | a clean test grid, then the final report |
| swe_bench Verified (Harbor) | [#1003](https://github.com/skillberry-ai/cap-evolve/issues/1003) | **unknown**: last seen RUNNING the test grid (67 / 500) | test grid, then the final report |

**The Docker host `fed-ws-1` (192.168.122.154) has refused SSH** (`Connection refused` on port 22) at every
check from **2026-11-24 10:16 UTC** to 2026-11-25 19:38 UTC. The VM answers at the IP, but sshd does not, so it
is probably down, rebooting or wedged. **Nothing can continue until the operator restores it.** Both issues
already say "blocked, host unreachable".

Other open items:
- **Pending operator decision (spreadsheetbench):** see §3.2. Ask the operator again; do not decide alone.
- **Pending operator approval:** remove 3 idle leftover containers on the host:
  - `django__django-13410__mnzwr8z__env-main-1`
  - `conv-capevolve-341-14_4_3a5aa5d7`
  - `conv-capevolve-341-14_3_a8840a10`

  The permission classifier blocked `kill -KILL` and `docker rm -f` as "interfering with workloads". If the host
  rebooted, they may be gone anyway.
- **Monitoring is gone.** The previous agent's hourly job was session-only and died with its session. You must
  set up your own (see §5).

---

## 1. First thing to do when the host is reachable

```bash
ssh fed-ws-1 'uptime -s; systemctl show docker --property=ActiveEnterTimestamp --value'
# Previous boot was 2026-11-17 14:31 UTC. A newer boot time means every run process is dead.
ssh fed-ws-1 '~/b3/venv/bin/python ~/b3/status.py'      # status collector (copy in base3-cont/status.py)
ssh fed-ws-1 'for b in ssb swe; do echo "$b pid=$(cat ~/b3/$b/run.pid) stat=$(ps -o stat= -p $(cat ~/b3/$b/run.pid))"; \
  ls ~/b3/$b/HOLD 2>/dev/null; grep -E "^(START|BASELINE_EXIT|FINALIZE_EXIT|RUN_END|TEST_MOSTLY|HOLD|WATCHDOG)" ~/b3/$b/run.log | tail -5; done'
ssh fed-ws-1 'ls ~/b3/ssb/run_base/run_real2/rollouts/test | wc -l; ls ~/b3/swe/run_base/run_real3/rollouts/test | wc -l'
ssh fed-ws-1 'cat ~/b3/gw_watchdog.pid; kill -0 $(cat ~/b3/gw_watchdog.pid) && echo watchdog-alive; \
  kill -0 $(cat ~/b3/swe/janitor.pid) && echo janitor-alive; tail -5 ~/b3/gw_watchdog.log'
```

- **Test rollouts empty (expected for both):** the seal is unused, and `finalize` can be re-run in the **same**
  run dir. Rollouts are written only when a whole grid completes; ssb was frozen, and swe was about 13% through test.
- **Test rollouts present:** do **not** re-score. Read `final.json` / the test rollouts. If they are mostly infra,
  report that and use a fresh run dir per base3 §1.3.

Then post a status comment on #1001 and #1003 (reboot or not, process state, what you will do) **before** acting.

---

## 2. Host layout (fed-ws-1, user erezh)

| Path | What |
|---|---|
| `~/ce.env` | **Model credentials** (`OPENAI_BASE_URL=https://litellm.cb.ete.res.ibm.com`, `OPENAI_API_KEY`, `OPENAI_MODEL_NAME`). The operator put it there. Never copy the workspace `.env` to the host: that was blocked as credential leakage. |
| `~/b3/repo` | cap-evolve clone @ `af0ce486c79d5fc12aacf073fb867d84a1fe253f` |
| `~/b3/venv` | Python 3.12.16 venv: litellm 1.110.2, pandas 3.1.1, openpyxl 3.1.5, tornado 6.6.1, docker 7.2.0, `-e repo/core` |
| `~/.local/bin/{bench,harbor}` | benchflow 0.6.4, harbor 0.26.0 (uv tools) |
| `~/b3/data/ssb/spreadsheetbench_verified_400` | data; `diff -rq`-identical to HF `KAKA22/SpreadsheetBench@ab0b742b…` |
| `~/b3/skillsbench` | SkillsBench clone @ `bf3793e9ec20e9682e6f18dbf4de3c69163dc9c7` |
| `~/b3/{ssb,sb,swe}/base/project` | intake-scaffolded projects (project-local adapters with the deviations in §6) |
| `~/b3/{ssb,swe}/env.sh`, `run*.sh`, `run.pid`, `run.log` | env and launchers (copies in `base3-cont/launchers.md`) |
| `~/b3/ssb/run_base/run_real2` | **current spreadsheetbench run dir** (val reused from `run_real`; test not sealed) |
| `~/b3/swe/run_base/run_real3` | **current swe_bench run dir** (val complete; test in progress) |
| `~/b3/swe/jobs/` | Harbor job dirs, one per `harbor run` = one trial; per-trial `result.json` |
| `~/b3/home-swe`, `~/b3/home-sb` | private HOME for Harbor / BenchFlow (the host's `~/.claude/settings.json` has an `env` block that overrides gateway/model) |
| `~/b3/gw_watchdog2.sh`, `.pid`, `.log` | gateway watchdog, pause mode (`base3-cont/gw_watchdog2.sh`) |
| `~/b3/swe/janitor.sh` | disk janitor, `LOW=26 HIGH=36` (`base3-cont/janitor.sh`) |
| `~/b3/infra_gate.py` | the "> half errored" gate |
| `~/b3/status.py` | status collector; `~/b3/status_history.jsonl` gets an hourly snapshot from the host crontab |
| `~/b3/ssb/adapter.retry.py` | **prepared, not yet active**: spreadsheetbench adapter with the LLM-retry patch (§4.1) |

Run status quirks:
- **Run dirs:** `status.py` picks the newest `run_*` dir by mtime, and the newest `view_real*` dir for ssb.
- **ssb `episodes_started`** counts per-rollout output dirs, and includes burned (instantly failed) episodes. ssb
  rollouts and errors are only visible once a grid completes.
- **Timestamps:** BenchFlow/Harbor `result.json` times are in host-local time for job dir names (+02:00), but
  `started_at`/`finished_at` are UTC in Harbor.

---

## 3. Per-benchmark state and what is left

### 3.1 skillsbench (#1002): DONE
- Final report: [comment 7056956964](https://github.com/skillberry-ai/cap-evolve/issues/1002#issuecomment-7056956964).
- **Test: 0.467 ± 0.183** (5 trials, 15 / 15 scored, 0 errored).
  - Per task: `pdf-excel-diff` 1.0, `pptx-reference-formatting` 0.4, `reserves-at-risk-calc` 0.0.
  - pass^k: 0.467 / 0.367 / 0.333 / 0.333 / 0.333.
- **Val:** 0.400 with errors excluded (`financial-modeling-qa` errored 5/5: glm-5-3 is text-only and Claude Code's PDF read sends a document block → `400 … not a multimodal model`), or 0.343 with errors counted as 0.
- **Only remaining use:** its row in the #975 table.

### 3.2 spreadsheetbench (#1001): needs a clean test grid
- **Val (final, reused):** `run_real` val, 200 / 200 scored, 0 infra.

  | trial | 0 | 1 | 2 | 3 | 4 | mean ± std |
  |---|---|---|---|---|---|---|
  | `hard_no_recalc` | 0.725 | 0.700 | 0.725 | 0.650 | 0.725 | **0.705 ± 0.033** |
  | `hard_restriction` | | | | | | 0.700 ± 0.035 |

  9,339,574 tokens; 211.6 ± 142.9 s per episode.
- **Test history:**
  1. **`run_real` (void):** gateway 403 from 2026-11-21 08:50; finalize sealed 1,289 / 1,400 infra. Declared void on #1001; do not report it.
  2. **`run_real2`, first finalize:** stopped by the old stop-mode watchdog 2026-11-22 03:27; 0 test rollouts.
  3. **`run_real2`, second finalize (`run3.sh`, started 2026-11-22 09:30):** two short key-refusal blips each burned hundreds of episodes in a minute before the watchdog could pause. Every episode failed on its first LLM call, at about 180/min:
     - **2026-11-23 08:55–08:56:** 367 burned;
     - **17:18:** 216 burned.

     At 1,302 / 1,400 started, about **583 were burned**, so the grid would end about 42% infra, non-random. The previous agent **held** it at 2026-11-23 17:29:35 (SIGSTOP of the process group, `~/b3/ssb/HOLD` present) to keep the seal unused.
- **Operator decision pending** (asked on #1001 at 09:35 and 17:30 UTC on 11-23):
  1. **Lift the hold** and let this grid finish (about 42%+ infra, non-random).
  2. **Recommended: stop it** and re-run `finalize` in `run_real2` with the **retry patch** (§4.1) active. The grid restarts from zero, about 50 h at about 0.47 episodes/min, concurrency 2.

  **If the host rebooted, option 1 is gone: the held process is dead.** Re-run finalize with the retry patch, after telling the operator.
- **How to do option 2:**
  1. Confirm `run_real2/rollouts/test` is empty.
  2. Stop the held process group, if alive (operator approval needed: the classifier blocks kills).
  3. Run `cp ~/b3/ssb/adapter.retry.py ~/b3/ssb/base/project/adapters/adapter.py` (or re-apply `ssb_patch.py` and then `ssb_retry_patch.py` to the stock adapter).
  4. Remove `~/b3/ssb/HOLD`.
  5. Launch a `run3.sh` copy with a **new empty** view dir (`view_real4`) via `setsid nohup`.
  6. Post the relaunch on #1001, naming the retry patch as a deviation.

### 3.3 swe_bench Verified (#1003): test grid in progress
- **Val (final):** `run_real3`, `BASELINE_EXIT 0` at 2026-11-23 07:38, `infra_gate: 0/250`.
  - Resolved per trial: **0.92 / 0.94 / 0.92 / 0.92 / 0.96**, as scored by cap-evolve.
  - Harbor's own view of trial 2 is 45 / 49 + 1 exception (see the scoring note below).
- **Test:** `finalize` was running (PID 2312713). At 2026-11-23 17:28: **67 / 500** results.
  - Test trial 0 at 67 / 100: 55 / 56 graded resolved, plus 12 Harbor exceptions (1 graded).
  - Test is 100 tasks per trial, 5 trials, one `harbor run` per trial, sequential, parallel 2, about 0.21 episodes/min, about 40 h for the whole grid.
- **If the run died (reboot):**
  1. Confirm `run_real3/rollouts/test` is empty (almost certainly).
  2. Re-run **finalize only** on `run_real3`: same pattern as ssb `run3.sh`, val reused, seal unused.
  3. Before launching, verify container networking: `docker run --rm curlimages/curl:8.11.1 curl -4 -s -m 15 -o /dev/null -w "%{http_code}\n" http://archive.ubuntu.com/ubuntu/` must give 200 repeatedly. Every trial installs Node and Claude Code via `apt` in the task image.
- **Scoring note (must go in the final report):** `capevolve_harbor`'s parser takes the verifier reward and ignores `exception_info`. Trials with a Harbor exception but a verifier reward are therefore **scored, not infra**:
  - `django-10554` val t2: `AgentTimeoutError` caused by a watchdog pause, reward 1.0;
  - `matplotlib-22865` test: `UnknownApiError`, reward 1.0.

  base3 §4 says `exception_info` non-null means infra. **Report both:** the cap-evolve score, and the score with exception trials excluded, with counts.

---

## 4. Known failure modes and the mitigations in place

**Gateway refusals (HTTP 403 on this key).** The key gets refused for a while, then works again with no change on our side:

| window (UTC) | length |
|---|---|
| 11-21 08:50 → 17:20 | 8.5 h |
| 11-22 03:23 → 07:50 | 4.5 h |
| 11-22 17:49 → 18:15 | 25 min |
| 11-23 04:15 → 06:58 | 2.7 h |
| 11-23 08:55 → 09:09 | 14 min |
| 11-23 17:18 | about 1 min |

`/key/info` is not allowed for this key, so the cause is unknown. Ask the gateway owners.

**Pause-mode watchdog** (`gw_watchdog2.sh`, PID file `~/b3/gw_watchdog.pid`):
- probes every 60 s;
- after 2 failures, SIGSTOPs each live run's process group and `docker pause`s running containers; after 2 OKs, resumes;
- skips runs with a `HOLD` file.

This saves Harbor (slow failures) but **not spreadsheetbench**, which burns about 180 episodes/min before the pause.

### 4.1 spreadsheetbench retry patch
`base3-cont/ssb_retry_patch.py` wraps the adapter's `litellm.completion` call in `_b3_wait_completion`:
- retries the same request every 60 s for up to 12 h on 401/403/429/5xx/connection/timeout;
- other errors fail as before.

It must be applied on top of `ssb_patch.py` (timing and token stamping). The patched file already exists as `~/b3/ssb/adapter.retry.py`. It is a deviation: infra robustness only; prompts and scoring are unchanged.

**Host network trouble (11-23 09:00–12:00 UTC).**
- **Full loss:** the VM lost outbound connectivity, then flapped.
- **Partial loss:** some Canonical archive IPs timed out from the host and from containers, while the gateway, npm and GitHub worked.
- **Effect:** swe_bench trials failed in agent setup (`AgentSetupTimeoutError`, `NonZeroAgentExitCodeError: Unable to locate package nodejs`, uv installer failures) with no verifier reward, so infra.
- **What the previous agent did:** held swe_bench (`~/b3/swe/HOLD`, SIGSTOP + `docker pause`) until a container could reach the archives 15 / 15 times, then lifted the hold.

**Disk** (98 GB, about 30 GB free):
- swebench base images land in the **BuildKit build cache**, not as named images;
- the janitor prunes cache unused for 30 min below 26 GB free;
- the codeact executor image (21.4 GB on disk) must stay.

**Process control:**
- **Never kill by name pattern;** use PID or process group only.
- **Runs start under `setsid`,** so each run has its own process group.
- **SIGTERM to the swe group did not stop `baseline/run.py`.** It survived and kept launching trials, so use SIGKILL on the group if a real stop is needed.
- **The permission classifier blocked** `kill -KILL -- -<pgid>` and `docker rm -f` of run containers. Get explicit operator approval for those.

**Your own process:**
- **Local files vanish.** The previous session restarted once and lost its `/tmp` background waits.
- **Stale comment files.** A blocked command once left a stale comment file that was then posted. Always write a fresh file (the Write tool), check its header line, then post.

---

## 5. Monitoring you must set up

- **Hourly status:** base3 §5 asks for a **durable** hourly job. The previous agent's CronCreate with `durable: true` still came back session-only, and recurring jobs expire after 7 days. Re-create the job in your session and tell the operator it is session-only if that happens again. The host cannot post to GitHub (`gh` there has no github.com auth), so posting must come from your session.
- **Every hourly comment** states STATE explicitly (running / terminated / blocked / completed), plus:
  - the stall verdict with its basis;
  - PID alive;
  - infra count;
  - memory %;
  - the restart check (boot `2026-11-17 14:31 UTC` and Docker start; compare after any reboot);
  - progress;
  - partial per-trial scores where visible;
  - an ETA from the measured rate.
- **Skip duplicates:** when blocked and nothing changes, post at most every few hours.
- **End-of-run waits:** a background wait on each run's PID, so final reports are posted promptly. Background tasks have a time limit; re-arm them each hourly tick.

---

## 6. Deviations already disclosed on the issues (repeat in the final reports)

- **All three:** private project bases (intake `--force`, not the shared `.capevolve/`).
- **All three:** `CAPEVOLVE_ERRORED_TRIAL_POLICY=drop`.
- **All three:** concurrency 2, sized to this 4-vCPU / 15 GiB host.
- **ssb and swe:** split files with `train := val`.
- **All three:** an infra gate before finalize; a test infra gate after.
- **ssb:** `ssb_patch.py`, the project-local wrapper stamping `episode_start/end/seconds`, `prompt_tokens`, `completion_tokens` and `llm_calls`.
- **ssb:** val reused via `--reuse-baseline` from `run_real`, with `reused_seed_test.json` **discarded**, so test is re-scored.
- **ssb, if applied:** the retry patch.
- **sb:** model slots set to the BenchFlow proxy alias (`sb_patch.py`).
- **sb:** `_task_jobs_dir` picks the newest attempt, applied before finalize.
- **sb:** private HOME.
- **swe:** `ANTHROPIC_SMALL_FAST_MODEL` and `CLAUDE_CODE_SUBAGENT_MODEL` added (`swe_patch.py`).
- **swe:** `--max-retries 2`.
- **swe:** private HOME.
- **swe:** no full image pre-pull, with the disk janitor instead.
- **swe:** no Docker Hub login (operator's choice).
- **Watchdog:** pause mode; the paused time inflates the wall time of in-flight episodes, and one swe trial timed out because of it.
- **Holds:** swe_bench held 11-23 11:33:59 → 12:28:57; spreadsheetbench held from 11-23 17:29:35.

`docs/baseline.md`, referenced by base3.md, **does not exist** anywhere. The previous agent followed base3.md
plus the conventions recorded in the earlier #1001–#1003 comments.

---

## 7. Final reports and closing

For each of #1001 and #1003, per base3 §6:
- the headline as mean ± std over the 5 trial means;
- tokens and serial time;
- coverage (`n_scored`) and the errored count;
- a per-trial table;
- per-episode mean ± std;
- provenance (SHAs, dataset revision, package versions, Docker 29.10.0, host);
- deviations (§6 above).

Every number must come from the run's own files. For skillsbench, `base3-cont/sb_report.py` shows how the
numbers were computed. Adapt it for swe_bench (Harbor `result.json`: `agent_result.n_input_tokens`,
`n_cache_tokens`, `n_output_tokens`, `model_usage`, and the phase timestamps).
- **spreadsheetbench:** report `hard_no_recalc` (primary) and `hard_restriction`, plus `n_scored` and the infra count.
- **swe_bench:** report the resolved rate both ways (§3.3).

When all three are done:
1. Post a connecting comment on **#975**: a table of benchmark → issue → result, saying the scores are per benchmark and not comparable.
2. Delete your hourly job.
3. Ask the operator about cleanup on the host: leftover containers, the `~/b3` dirs, the crontab line writing `status_history.jsonl`, and the watchdog/janitor processes.
