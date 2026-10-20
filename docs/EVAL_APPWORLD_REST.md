# AppWorld eval "REST": five optimization candidates vs one shared seed run

Status: **PLAN**, written 2026-10-20. Nothing in sections 6 to 16 has run yet. This document is
**both the plan and the status ledger**: sections 0 to 17 are the plan; the execution ledger is
appended to section 18 during the run, under an exclusive file lock (rule R3, section 4.3).

The plan evaluates **five optimization candidates** on AppWorld. Each is scored against the **same
unmodified seed agent**, whose baseline is **run exactly once** and shared by every candidate (rule Q4,
section 5.4). The candidates are:

| arm id | method | reference implementation | pin studied (2026-10-20) |
|---|---|---|---|
| `harnesslens` | HarnessLens (behavior-aware harness evolution) | https://github.com/jhxu5214/HarnessLens | `369a5c8` (single commit, 2026-08-27), paper arXiv 2608.27311 |
| `miprov2` | MIPROv2 (DSPy instruction + demo optimization) | https://github.com/stanfordnlp/dspy (`docs/docs/api/optimizers/MIPROv2.md`) | PyPI `dspy==3.4.1` (tag `3.4.1`), paper arXiv 2406.11695 |
| `trace2skill` | Trace2Skill (trajectory → skill distillation) | https://github.com/Qwen-Applications/Trace2Skill | `3d0b52a` (2026-05-02), paper arXiv 2603.25158 |
| `gepa_full` | GEPA, **full mode**: prompt **and** tool descriptions | https://github.com/gepa-ai/gepa | PyPI `gepa==0.1.4` (`8b0ce6c`), paper arXiv 2507.19457 |
| `cape_improve` | cap-evolve, improved version (`cap-evolve-improve`) | https://github.com/erezh16/cap-evolve/tree/cap-evolve-improve | `470f3fa` (the branch's last code commit; later commits on the branch are docs only, such as this plan) |

It reuses the harness, splits, feedback tier, isolation rules and final-window machinery of the base
plans. **The executing agent must read these in full before doing anything else:**

- `docs/EVAL_SMOKE_TEST.md` ("the base plan"): sections 0 to 15 and Appendices A (findings F1 to F20),
  B and C.
- `docs/EVAL_SMOKE_TEST_FIX.md` ("the fix doc"): what was re-run and why; optimizer isolation.
- `docs/CONTAINER_AGENT.md` ("the container guide"): sub-agent isolation and memory in this pod.
- `docs/EVAL_APPWORLD_5.md` on branch `origin/eval5` ("eval 5"): the most recent sibling, executed
  2026-10-17 to 2026-10-20 in this same kind of pod, with the same models and the same final window
  for five other candidates (GEPA 0.1.4 prompt-mostly, SkillOpt, WikiSkill, EvoSkill, Meta-Harness).
  Its code under `examples/appworld/` (shared evaluator, gateway shim, sandbox settings, ledger writer,
  resume, memory guard, auto-poster, windows, scan, analysis) is the starting point of this plan's
  code, and its ledger (its section 15) records the failures this plan is written to avoid. Read its
  sections 0 to 14 and every ledger entry of kind `error`, `repair`, `decision`, `resume` or `restore`.

Every rule of the base plan and of eval 5 is kept unless this document says otherwise. Section 15 lists
every deviation. Where a candidate's paper and its code disagree, follow the **code at the pinned
commit** and record the choice in the ledger.

The deliverables of the execution are: one results comment per candidate on that candidate's tracking
issue (section 8); the five frozen artifacts; and this ledger. Issues live on
**`skillberry-ai/cap-evolve`** (the `origin` fork `erezh16/cap-evolve` has issues disabled).

---

## 0. Scope and the non-negotiable rules at a glance

| item | this evaluation |
|---|---|
| methods | `harnesslens`, `miprov2`, `trace2skill`, `gepa_full`, `cape_improve`, each against the **same** seed. Candidates are **not ranked** against each other (one search seed each; section 14). |
| **the seed** | the official AppWorld simplified ReAct code agent, stock prompt, no helpers, notes or memory. **Run once** on train (90) and dev (57), 1 trial each, in phase P3. Every candidate reads those records as its baseline. The seed is one arm of the final window, run there once. **No candidate driver ever re-runs the seed** (rule Q4). |
| optimizer model, every candidate | `aws/claude-sonnet-5-5` via the gateway in `~/.claude/settings.json` (rule Q3) |
| agent under test, every arm | `openai/gpt-oss-120b-a100` on RITS, `hosted_vllm/` route, reasoning effort `medium`, temperature 0 (rule Q3) |
| benchmark | AppWorld at `42b5bcf`, **official splits only**. Search uses `train` (90) and `dev` (57). Results come from `test_normal` (168). `test_challenge` is not used. |
| trials | **search: 1 trial per task (trial seed 100); final window: 2 trials per task (trial seeds 5000+k); 1 search seed per candidate**, identical for all (rule Q1) |
| budget per candidate | **B = 900 counted (fresh) search rollouts**, and **≤ 10M optimizer non-cache-read tokens**. The shared seed baseline (147) is counted once, separately, and is not charged to any candidate. |
| final window | `test_normal` 168 tasks × **6 arms** (seed + 5 champions) × 2 trials = **2,016 episodes**, in **one** interleaved shuffled order |
| metrics | reward, cost, tokens, latency, at **both** the search (train) and the test phase, identically for every arm (rule Q2) |
| isolation | no agent of any kind, executing or optimizing, may see gold, ground truth, solutions, task generators, sealed splits or test outcomes (rule R1) |
| memory | sampled every **5 s** by a guard service; at ≥ 90% of the container limit nothing new starts (no sub-agent, episode or optimizer call) until it is back below 85% (rule R2) |
| resumability | this document is the status ledger, appended under `flock`; one command resumes; only the in-flight step may be lost (rule R3) |
| parallelism | as parallel as rule R2 allows: shared episode-slot pool, up to 3 candidate searches at once, parallel sub-agents for the build (rule R4) |

---

## 1. What was read and verified (2026-10-20)

### 1.1 Sources read
The base plan with Appendices A to C; the fix doc; the container guide; eval 5's plan, ledger, state,
results and code (`origin/eval5:examples/appworld/`, `docs/EVAL_APPWORLD_5_STATE/`); the AppWorld
example of branch `origin/appworld-example`; `origin/capevolve-impr:docs/CAPEVOLVE_IMPR.md`; issues
#875 to #878, #867, #868 and eval 5's #881 to #885; `CLAUDE.md`. For each candidate, its repository
was cloned read-only under `/tmp/plan_ref/clones/` and its code and paper read. Nothing was executed.
Per-candidate findings are in section 9.

### 1.2 Facts about this host (probed 2026-10-20)
- `memcheck` (container guide §2.3): `limit_MB=32768`, `cpu_limit=8`, `swap_max=0`,
  `memory.oom.group=1`. An OOM kills **the whole container** and restarts it. `nproc` is not the CPU
  limit.
- `/workspace`: 20 GB volume, about 17 GB free, **persists across restarts**. `/tmp`: 295 GB, about
  99 GB free, an `emptyDir` that does **not** survive a pod restart. Durable state must live on
  `/workspace`.
- `/workspace/aw_eval5` (eval 5's build and local state) is **gone**. Everything is rebuilt from scratch.
- `unshare -rm` fails with `ENOSYS`, so the base plan's namespace wrapper (`examples/appworld/sandbox/claude`)
  cannot run. Claude Code's sandbox works through `devagent-bwrap` (tier: landrun + proot, Landlock
  ABI 5; network open by default, `DEVAGENT_BWRAP_NETWORK=restrict` closes it). Managed setting:
  `/etc/claude-code/managed-settings.json` = `{"sandbox":{"bwrapPath":"/usr/local/bin/devagent-bwrap"}}`.
  `/usr/bin/bwrap` and `socat` are present. Claude Code CLI 2.1.270.
- `.env` in the repo root holds `RITS_URL` and `RITS_API_KET` (typo kept, base plan §1.1). The gateway
  is `ANTHROPIC_BASE_URL` (ContextGuru) with `x-context-guru-token` in `ANTHROPIC_CUSTOM_HEADERS`.
  `CLAUDE_CODE_SUBAGENT_MODEL` and `ANTHROPIC_DEFAULT_SONNET_MODEL` are `aws/claude-sonnet-5-5`.
- `gh` is logged in as `erezh16` (ssh). `uv` is `/usr/local/bin/uv`; `python3` is 3.11.2.
- `CLAUDE.md`'s provider order (RITS, then ETE-INT, then ETE) governs `benchmarks.yml` CI runs. This
  run does not use CI: the agent is on RITS (unpriced) and the optimizer on the gateway, as in the base
  plan (D1). Spend is reported **per provider** anyway (section 5.2).

### 1.3 Facts carried from the base plan and eval 5 that this plan depends on
- Gateway (eval 5 G1 to G3): the gateway **rejects `temperature`** for `aws/claude-sonnet-5-5`, and
  rejects forced `tool_choice` (`tool`/`any`). A deterministic 4xx other than 429 is not retried. The
  gateway's `[cyber]` classifier refuses exfiltration-styled prompts, so the isolation check (A9) uses
  a neutral framing ("which files are visible in this workspace").
- Episode worker `aw_agent.py` (base F1, F2): one AppWorld episode per subprocess. It removes `os`,
  `pathlib`, `io`, `shutil` and `glob` from AppWorld's import allowlist, drops the RITS key from the
  environment before the world starts, enforces the 100,000 completion-token cap, records `fs_probe`,
  `wall_seconds`, tokens, steps and termination, and drops the gold-bearing `trace` before anything is
  written.
- `M_cap` (eval 5): `min(30,000 chars, 34,000 − P_max − H_max tokens)` = **13,500 tokens / 30,000
  chars** with the stock prompt. Recompute it in A8, because candidates that change P change `P_max`.
- Temperature 0 is **not** deterministic at scale (base F10): the two trials of a task disagreed on
  24–38% of tasks, and identical artifacts drifted by 4–6 TGC points between windows. So arms are
  compared only inside one window.
- Eval 5 ledger lessons, each turned into a rule below: lint must run in `venv-aw` (it needs jinja2);
  driver crashes on lint-rejected records; `claude -p` print mode ends background sub-agents after
  600 s unless `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS` is raised; a `pgrep -f` pattern that matched its
  own command line stalled the final window for 10 h; 48 final-window workers plus the session
  OOM-restarted the pod (peak about 25 GB of 32 GB), and 24 workers ran at about 44%.

---

## 2. Decisions

| id | decision | source |
|---|---|---|
| D1 | optimizer `aws/claude-sonnet-5-5` for every candidate and every optimizer role (proposer, analyst, editor, sub-agent) | base D1; guideline 6.3 |
| D2 | AppWorld core and agents from source at `42b5bcf`, pydantic 2.12.x | base D2 |
| D3 | 1 trial per task in search, 2 trials per task in the final window, 1 search seed | base D3; guideline 6.1 |
| D4 | candidate pins as in the table at the top | section 9 |
| D5 | **one shared seed run** (P3): train 90 + dev 57, 1 trial, trial seed 100; reused by every candidate through the evaluator cache; the seed is one arm of the final window | user instruction 2026-10-20 |
| D6 | surfaces: `harnesslens` P+T+M, `miprov2` P, `trace2skill` M, `gepa_full` P+T (per-app tool-description components), `cape_improve` P+T | section 9 |
| D7 | isolation: Claude Code's sandbox (not the namespace wrapper) for every optimizer role that has file or shell tools; plain-chat roles need no sandbox but get only gold-free inputs | sections 1.2, 10 |
| D8 | memory guard at 90% (pause) / 85% (resume), sampled every 5 s, enforced on sub-agents, episodes and optimizer calls | user guideline 7.2 |
| D9 | ledger = this document; branch `eval-rest`; one tracking issue per candidate; progress posted at least hourly per candidate | user guidelines 5, 7.3 |

If the executing agent meets a question these decisions do not answer, it asks the user (one
`AskUserQuestion`, with a recommended option) and records the answer as a `decision` ledger entry. It
never decides silently where the choice could favour one arm.

---

## 3. Arms

| arm id | learned artifact | surface |
|---|---|---|
| `seed` | none: `examples/appworld/seed_capability/` verbatim (byte-identical to stock) | none |
| `harnesslens` | edited `policy/instructions.txt`, `tools/helpers.py`, `tools/api_notes.json`, `memory/playbook.md` | P + T + M |
| `miprov2` | an instruction block and up to 3 compact demos rendered into `policy/instructions.txt` | P |
| `trace2skill` | a distilled skill document as `memory/playbook.md` | M (static) |
| `gepa_full` | evolved `policy/instructions.txt`, `tools/helpers.py`, and `tools/api_notes.json` assembled from per-app components | P + T |
| `cape_improve` | edited `policy/instructions.txt`, `tools/helpers.py`, `tools/api_notes.json` | P + T |

All six arms use the same harness, model client, decoding parameters, step cap, token cap and evaluator.
Only each arm's own surface files differ. This holds by construction: every arm's agent runs through the
one unmodified `aw_agent.py` worker.

---

## 4. MANDATORY EXECUTION RULES (read before any action; they override convenience)

> These five rules are **not optional**. A step that would break one of them is not taken; the agent
> stops, records an `abort` or `decision` entry, and asks the user. Every sub-agent the executing agent
> spawns receives the text of this section **verbatim** in its prompt.

### 4.1 Rule R1: no agent ever sees what it must not see (guideline 7.1)

**Forbidden content** (the "sealed set"):
- `ground_truth/` of any task, `answer.json`, `private_data.json`, `evaluation.py`, `solution.py`,
  `compiled_solution.py`, the evaluator's failure `trace`, AppWorld's native per-episode output dirs
  (they hold evaluation reports with gold);
- AppWorld's task generators (`appworld/generate/`, base F19) and AppWorld's app implementation source
  (`src/appworld/apps/`, base F20);
- all `test_normal` and `test_challenge` task data and ids, `root_full`, and every final-window record
  until the analysis step reads counts from it;
- `.env`, the gateway token, other sessions' transcripts (`~/.claude/projects/*`, `/tmp/claude-*/*`),
  `~/.config/gh`.

**Who may touch it:** only named trusted scripts running as separate unsandboxed processes: the episode
worker (`aw_agent.py`), the windows (`window*.py`), the build steps, the lint-cache builder and the
isolation scan. No LLM, sub-agent or person reads it.

**How it is enforced (all layers apply; none is enough alone):**
1. **Data roots.** Search-time episodes use `root_opt` (train + dev tasks only, no test file; a grep
   of every test id must find 0 hits). `root_full` is `chmod 000` from the end of B3 until the start of
   P7, and again after P7.
2. **Gold-free feedback (tier F1).** The only evaluator output any optimizer sees is: reward 0/1, the
   pass fraction, the **texts** of failed requirements, the collateral-damage flag, whether
   `complete_task` was called, steps, API-error count, and termination. Never the gold answer, the
   `trace`, a solution or a reference value. Every candidate whose native design feeds gold (Trace2Skill's
   agentic analyst, MIPROv2's labeled demos) is de-fanged (section 9).
3. **Optimizer sandbox.** Every optimizer role with file or shell tools (`harnesslens` Editor,
   `cape_improve` proposer and its sub-agents) runs under Claude Code's sandbox with `failIfUnavailable`
   and `allowUnsandboxedCommands: false`, `filesystem.denyRead` plus `permissions.deny Read(...)` and
   `Edit(...)` on the sealed set **and** on AppWorld itself, the evaluator code, `AW_STATE`, the venvs,
   the clones and every repo checkout, a restricted network (gateway host only), and no `WebFetch`/
   `WebSearch` (section 10). It must pass check A9 before any counted rollout.
4. **Plain-chat roles** (MIPROv2's proposer, Trace2Skill's analysts and merger, GEPA's reflector,
   HarnessLens's analysis roles) get only the gold-free text the driver builds. They have no tools.
5. **Executing agent and its sub-agents.** The orchestrating sessions (the main session and every
   sub-agent it spawns) **never** open a sealed-set file with any tool (`Read`, `Grep`, `Glob`, `cat`,
   `head`, `python -c open(...)`, ...), never print a test record, and never read a test trajectory.
   Before P1, write `.claude/settings.local.json` in the `eval-rest` worktree with
   `permissions.deny` rules `Read(//<path>/**)` for: `AW_BUILD/root_full`, `AW_BUILD/root_opt/data/tasks`,
   `AW_BUILD/appworld/generate`, `AW_BUILD/appworld/src/appworld/apps`, `AW_BUILD/appworld/data`,
   `AW_STATE/final`, `AW_SCRATCH`, and the repo's `.env`. Spawn sub-agents only with prompts that
   repeat this section; give a sub-agent that writes code a dedicated workspace and tell it to test
   against **dev ids only** with a mock or the shared evaluator, never by reading task files. Code
   that must handle task data is run, never read, by the agent.
6. **Detection.** After each search (P4 per candidate) and once more before the final window (P6), the
   isolation scan greps every optimizer transcript, prompt/response log, workspace, frozen artifact **and
   the orchestrating sessions' own transcripts** for: every test id, `test_normal`, `test_challenge`,
   `root_full`, `ground_truth`, `answer.json`, `compiled_solution`, `solution.py`, `generate/tasks`,
   `src/appworld/apps`. Counts only are published. A test-id hit labels the arm "isolation breach" in
   every result (base F14). A train/dev gold read is reported and labelled the same way.
7. **Nothing is ever published** that contains a task id, task or supervisor text, a train/dev 8-gram, a
   trajectory, a secret or a per-task test outcome (AppWorld redistribution rule; content filter in
   section 12.2).

### 4.2 Rule R2: memory is watched every 5 s, and nothing new starts above 90% (guideline 7.2)

Follow `docs/CONTAINER_AGENT.md` §2 in full. In addition:
- **Guard service** `memguard.py` (adapt eval 5's `memguard5.py`): a `nohup` loop started in P1 before
  anything heavy, relaunched by `resume.py`. Every **5 s** (never more than 10 s) it reads this
  container's cgroup: `used = anon + shmem` of `memory.stat` over `memory.max` (or `memory.high` if
  lower). It atomically writes `AW_STATE/MEMSTATE.json` = `{t, used_pct, used_MB, limit_MB, state}`.
- **Watermarks:** at `used_pct ≥ 90` it sets `state = PAUSED` and creates `AW_STATE/PAUSE`. It clears both
  only when `used_pct < 85`. One line per transition, and one sample line per minute, go to
  `AW_STATE/progress/memguard.log`.
- **Who honours it:**
  - the shared evaluator and the windows: no new episode starts while PAUSED; in-flight episodes finish;
  - every candidate driver: no new optimizer call or proposer session starts while PAUSED;
  - the executing agent: before **every** sub-agent spawn and every launch of a process, read
    `MEMSTATE.json`. Spawn nothing if `state == PAUSED`, if the file is older than 30 s (the guard is
    dead: restart it first), or if `memcheck`'s `subagents_that_fit` is 0. Wait and re-check every 30 s.
- **Escalation:** if the state stays PAUSED for more than 10 minutes, the agent shrinks what it started,
  most recent first: lower the global episode slots by 25%, then stop the most recently started candidate
  search gracefully (it resumes later from its state). It records a `decision` entry each time.
- **Sizing:** size every pool from `cpu_limit` (8) and measured memory, never from `nproc`. Episode
  workers: about 0.5 GB each (eval 5: 24 workers ≈ 44% with one session). Start with **24 global episode
  slots** (section 7.3). Raise by 4 at most, and only after 30 minutes with peak `used_pct` < 65%.
  Never above 32.
- **After a restart** (`container_age_s` shorter than the session; `oom.group=1` resets the counters),
  treat the work launched just before as the cause. Resume (section 12.4) and relaunch **smaller**, never
  unchanged: −25% slots and one fewer concurrent search.

### 4.3 Rule R3: this document is the status ledger; the run can resume at any time (guideline 7.3)

- The ledger is section 18 of **this file**, `docs/EVAL_APPWORLD_REST.md`. It is append-only. Every
  append happens under **`flock(AW_STATE/ledger.lock)`**, through the one writer `status_doc.py`
  (adapted from eval 5). Concurrent drivers and sub-agents never edit the file directly, so no update
  overwrites another.
- Every append: write the pushed state files atomically, append the entry, `fsync`, run the content
  filter, `git commit -- <pathspec>`, `git push origin eval-rest` (never `--force`). Section 12.2 gives
  the entry format and cadence.
- Resolution: a checkpoint at every phase boundary and search milestone, coalesced results at most every
  5 minutes, and a heartbeat after 25 silent minutes. The only acceptable loss on a crash is the step in
  flight.
- One command, `resume.py`, continues from the last entry (section 12.4).

### 4.4 Rule R4: parallelize as much as rule R2 allows (guideline 7.4)

- **Build (P1):** after the common code (section 6.2) exists, write the five candidate drivers in
  **parallel sub-agents** (one per candidate, each in its own directory `examples/appworld/<cand>/`, each
  with rule R1's text), subject to `memcheck` and rule R2.
- **Search (P4):** up to **3 candidate searches at once**, sharing one global pool of episode slots
  (section 7.3), so total agent concurrency never exceeds the pool however many searches run. Optimizer
  time of one candidate overlaps rollouts of another.
- **Inside a candidate:** episodes are the parallel unit (`batch_evaluate`, thread pools), always
  through the global pool.
- **Watchers:** detached `nohup` processes do the long work; at most one watcher sub-agent per running
  search plus one for the guard and posting. Nothing depends on a sub-agent staying alive.
- **Never nest:** sub-agents must not spawn sub-agents (container guide §2.5 rule 5). The optimizers'
  own sub-agents (`cape_improve`'s claude-code) run inside the sandboxed optimizer process and count
  against memory like any other process.

### 4.5 Rule R5: quality over speed (guideline 8)

Take the time to read every source named here before writing code. Check every number against its
source. Prefer a correct pause to a fast wrong step. Before any counted rollout, every acceptance check
of section 13 passes and its result is in the ledger. When something is unclear or a result looks
surprising, stop and investigate (and ask the user if needed) before continuing. Report failures and
deviations plainly in the ledger and on the issue.

---

## 5. Quality rules for valid results (guideline 6)

### 5.1 Rule Q1: the same number of trials everywhere (guideline 6.1)

Verified against the base plan: §0 "search seeds: 1 per method"; §7.2 `num_trials: 1`; decision D3 "2
trials per task" in the final window; Appendix C kept them. Eval 5 used the same. So:

| level | value | applies to |
|---|---|---|
| search seeds per candidate | **1** | every candidate (one search run, seed 0 or the method's seed parameter fixed in section 9) |
| trials per task during search | **1**, trial seed **100** | every search-time episode of every arm, including the shared seed run |
| trials per task in the final window | **2**, trial seeds **5000 + k**, k ∈ {0, 1} | all 6 arms |
| dev diagnostic (P5) | **1**, trial seed 100 | all 6 arms |

**One (candidate tree, task, trial seed) is run at most once.** The shared evaluator caches each record
by `(sha256 tree hash of the candidate dir, task id, trial seed)`. A repeat request returns the cached
record and is not counted. So a method that re-evaluates the same candidate on the same task (MIPROv2's
full evals, GEPA's parent minibatches, HarnessLens's parent re-runs) gets the one recorded trial, never a
second sample. An infrastructure failure (`Rollout.error`) is not cached and is retried once with the
same seed (base §7.1).

### 5.2 Rule Q2: the same metrics for every arm, at search and at test (guideline 6.2)

Collected by shared code only (the evaluator, the gateway shim, the windows and `analyze.py`), never by
a candidate driver's own counters, so the definitions cannot differ. **Every** arm reports **every** row.

| metric | search phase (train/dev) | test phase (final window) | source |
|---|---|---|---|
| **reward** | champion's search-time score (labelled with its set and "selection-biased"); mean reward of counted rollouts; dev diagnostic TGC (P5, same 57 tasks for all arms); seed train and dev TGC | TGC, SGC, by difficulty; Δ vs seed with 95% CI; pass fraction (`pass_count/num_tests`) as a secondary | evaluator records; window records |
| **tokens, agent** | prompt and completion tokens per episode (mean, p50, p90), max prompt tokens, steps, step-cap hits, token-cap hits, context-exceeded | the same | `aw_agent.py` record fields |
| **tokens, optimizer** | input, output, cache-read and cache-write tokens; number of calls; per role | n/a (no optimizer at test) | `optimizer_usage.jsonl` per candidate |
| **cost** | optimizer USD, **proxy** at list price for Claude Sonnet 5.5: $2.00 / MTok input, $10.00 / MTok output, $0.20 / MTok cache read, $2.50 / MTok 5-min cache write (1.25× input); plus the CLI-reported `total_cost_usd` where a CLI is used, labelled. Agent cost: RITS is unpriced, so it is "n/a (unpriced)", **never $0**; agent tokens stand in for it | agent: "n/a (unpriced)" plus tokens | shim, CLI JSON |
| **latency** | per-episode wall seconds (mean, p50, p90); per optimizer call seconds (mean, p90) and total optimizer wall time; search wall time; time to champion | per-episode wall seconds (mean, p50, p90); window wall time | `wall_seconds`; shim `seconds`; ledger timestamps |
| **budget** | counted search rollouts (of B = 900), cache hits, lint rejects, infra retries | infra retries, missing cells | evaluator |
| **stability** | n/a | share of tasks whose 2 trials agree | window records |

Spend is also reported **per provider**: RITS (agent, unpriced: tokens only) and the gateway (optimizer:
tokens and proxy USD). Note: eval 5 priced the proxy at $3/$15, which is not Sonnet 5.5's list price; do
not reuse that constant.

**Wiring (verify in A12):** every optimizer LLM call of every candidate goes through
`common/opt_llm.py` (plain chat) or is a `claude -p --output-format json` call whose usage JSON is
appended to the same `optimizer_usage.jsonl` with the same fields: `{t, seconds, model, role,
prompt_tokens, completion_tokens, cache_read, cache_write, error, finish_reason}`. A library that calls
an LLM by itself (DSPy, Trace2Skill's clients) is given a client object that routes into `opt_llm.py`.

### 5.3 Rule Q3: the same models for every arm (guideline 6.3)

- **Optimizer:** `aws/claude-sonnet-5-5`, through the gateway, for **every** optimizer role of **every**
  candidate: proposers, reflectors, analysts, mergers, editors, condensers, and the sub-agents of
  `cape_improve`'s claude-code optimizer. `claude_env()` sets `ANTHROPIC_MODEL`,
  `ANTHROPIC_DEFAULT_{OPUS,SONNET,HAIKU}_MODEL`, `ANTHROPIC_SMALL_FAST_MODEL` and
  `CLAUDE_CODE_SUBAGENT_MODEL` all to that id. No `temperature`, `top_p`, `top_k` or `seed` is sent
  (G1). A1 checks it per candidate, and the post-search scan checks the `model` field of every usage line
  (any other model id is an error entry).
- **Agent under test:** `openai/gpt-oss-120b-a100` on RITS, with the base plan §5.1 model config
  unchanged (reasoning effort `medium`, temperature 0, `max_completion_tokens` 6000,
  `drop_reasoning_content`, `use_cache: false`, `max_output_length` 60000 chars, `max_steps` 50, 100,000
  completion tokens per task). No candidate may change the agent model, its decoding parameters or the
  step and token caps.

### 5.4 Rule Q4: the seed is run once, and every candidate starts from it

The seed run is independent of every candidate, so it is run **exactly once**:
- **P3 (shared seed baseline):** the seed (`seed_capability`, tree hash `SEED_HASH` recorded in
  `manifest.json`) is run on all 90 train and 57 dev tasks, 1 trial, trial seed 100, through the shared
  evaluator. Its 147 records are the baseline of **every** candidate. They are counted once, as
  "shared seed baseline: 147 rollouts", and not charged to any candidate's B.
- **Every candidate starts from the seed artifact** and reads the seed's records instead of producing its
  own baseline:
  - `cape_improve`: its baseline (train = val = 147) is served from the cache (0 fresh). The seed's
    tree hash does not depend on the gate or the instructions, so the cache hit holds with k = 0.5;
  - `gepa_full`: its seed full-val eval on dev is served from the cache;
  - `miprov2`: its default-program full eval on dev is served from the cache, and its demo pool comes
    from the seed's successful train records;
  - `trace2skill`: the trajectories it analyses are the seed's 90 train records;
  - `harnesslens`: its v0 baseline on train is the seed's 90 records, and every "parent = v0" rollout is
    a cache hit.
- **Guard:** after P3 is done, the evaluator refuses any **fresh** episode of `SEED_HASH` in search
  (`SeedRerunRefused`); only cache hits are allowed. A driver that hits this guard has a bug.
- **Final window:** the seed is **one** arm (168 × 2), run once in the one window, next to the five
  champions. **Dev diagnostic (P5):** the seed's dev numbers are the P3 records; only the five champions
  are scored there (most will already be cache hits).

---

## 6. Environment and code

### 6.1 Layout

```
/workspace/worktrees/eval-rest/            # NEW worktree, branch eval-rest (from origin/eval5); all commits and pushes go here
  docs/EVAL_APPWORLD_REST.md               # THIS DOCUMENT: plan (0–17) + ledger (18)
  docs/EVAL_APPWORLD_REST_STATE/           # pushed, publishable state (manifest, per-candidate progress, artifacts, final counts)
  examples/appworld/                       # shared harness (from eval 5) + five new candidate drivers
/workspace/worktrees/cape-improve/         # NEW worktree, DETACHED at 470f3fa: the cap-evolve-improve code under test. Read-only: never commit here
/workspace/aw_rest/                        # AW_HOME, durable, outside git, never pushed
  state/                                   # AW_STATE: ledger.lock, MEMSTATE.json, PAUSE, RUNNING.pid, records, logs, caches
  build/                                   # AW_BUILD: appworld/, venvs/, root_full/ (chmod 000), root_opt/, reference/, hf/, clones/
/tmp/aw_rest/                              # AW_SCRATCH: AppWorld native outputs (deleted after each record), optimizer workspaces
```

Do **not** commit to `cap-evolve-improve`: it holds the pinned code of a candidate. The candidate is the
commit `470f3fa`, never the branch tip, which also carries this plan and its source docs. Do not touch the
`/workspace/worktrees/base` worktree, except to copy this file from it. Never use bare `git stash`.

### 6.2 Build steps (each idempotent, each one ledger checkpoint)

- **B0.** `git worktree add -b eval-rest /workspace/worktrees/eval-rest origin/eval5`; copy this document
  in and commit it. `git worktree add --detach /workspace/worktrees/cape-improve 470f3fa`. Write the
  executing session's deny rules (rule R1.5). Start `memguard.py` (rule R2).
- **B1 to B4** as eval 5 §4 (AppWorld clone at `42b5bcf` + `git lfs pull` + the extra-headers patch;
  `venv-aw`; `appworld download data`; count checks 90/57/168/417, scenarios 30/19/56/139, difficulties;
  `make_roots.py`, `make_splits.py`, `make_reference.py`; `chmod 000 root_full`; the lint cache). Paths
  under `/workspace/aw_rest`.
- **B5.** Per-candidate environments (section 9 gives each install). Clone each candidate repo at its pin
  into `AW_BUILD/clones/<cand>` (read-only); vendor only what a driver imports, with a `VENDORED.md`
  (source path, commit, sha256). `venv-cape`: like `venv-aw`, but with
  `-e /workspace/worktrees/cape-improve/core` instead of the eval-rest core, and every cap-evolve command
  run with `CAPEVOLVE_SKILLS_DIR=/workspace/worktrees/cape-improve/skills` (section 9.5, I1 to I6).
- **B6. Common code** (adapt from `origin/eval5`, then generalize): `scripts/awrest.py` (paths, constants,
  `CANDIDATES`, `ARMS`, issues, pins, B, prices), `common/evaluator.py` (with the cache, the seed guard,
  the global slot pool, the PAUSE check and the hard budget cap), `common/opt_llm.py` (no temperature,
  usage logging, the 10M cap, PAUSE check), `common/sandbox.py` (settings and env, section 10),
  `scripts/{status_doc,resume,build,memguard,autopost,post,scan,window,analyze}.py`. Fix eval 5's known
  bugs: lint in `venv-aw` only; never `pgrep -f` on a pattern that matches the caller (use pid files);
  lint-reject records carry the same fields as normal records.
- **B7. Candidate drivers**, in parallel sub-agents (rule R4), each `examples/appworld/<cand>/run_<cand>.py`
  with sub-commands `accept`, `search`, `freeze`; each committed after its offline unit test passes.

---

## 7. Shared harness, evaluator, cache and budget

### 7.1 The harness (unchanged from the base plan and eval 5)
Seed capability, injection through `CapReActAgent` (P from `policy/instructions.txt`; T from
`tools/helpers.py` and `tools/api_notes.json`; M before the final `My name is: … Task:` block), and the
lints (prompt keeps its three Jinja variables, `USER:`/`ASSISTANT:` structure and final block, ≤ 8,000
tokens; helper AST lint; notes ≤ 400 chars each and ≤ 20,000 tokens; memory ≤ `M_cap`; no 8-gram of a
train/dev instruction; no supervisor contact). The lint runs at materialization; a violating candidate
gets no episode (`lint_reject`), and the driver gets the violations as feedback.

### 7.2 The evaluator (`common/evaluator.py`), the only path to an episode
`evaluate(cand, cdir, task_ids, *, phase, tag)` returns gold-free records. It:
1. lints the candidate (in `venv-aw`) and returns lint-reject records without running anything;
2. returns cached records for `(tree hash, task, seed)` already on disk (not counted);
3. refuses a fresh seed episode after P3 (rule Q4) and any id outside train ∪ dev unless
   `AW_ALLOW_SEALED=final-eval-only` (set only by the final window);
4. raises `BudgetExceeded` **before** starting a batch that would take the candidate's fresh count past
   B = 900;
5. acquires one global slot per episode (7.3), waits while `AW_STATE/PAUSE` exists, runs `aw_agent.py` as
   a subprocess with `APPWORLD_ROOT=root_opt` and a 30-minute wall cap, retries an infra failure once;
6. appends every fresh record to `AW_STATE/<cand>/rollouts.jsonl` (counted) and every cache hit to
   `cache_hits.jsonl`.

`cape_improve`'s cap-evolve adapter (`adapters/adapter.py`) must call this evaluator inside its
`run_trials`, so the cache, the seed reuse, the slots, the guard and the cap apply to it too.

### 7.3 The global episode-slot pool
`AW_GLOBAL_SLOTS` (start 24, section 4.2) slots, implemented as `flock` on files
`AW_STATE/slots/<i>.lock`, shared by every process. All episode-running code (evaluator, windows) takes a
slot per episode. RITS handled 48 concurrent requests without errors (base §1.1), so RITS is not the
bottleneck; memory is.

### 7.4 Budget accounting
- **Counted** = fresh search episodes of a candidate (cache hits, the shared seed baseline and acceptance
  probes are not counted). Hard cap B = 900 in the evaluator. Each candidate's driver also sets the
  method's own budget parameter so the method ends naturally within B (section 9). If the hard cap fires
  first, the driver freezes the method's best state saved before the abandoned step (as eval 5's GEPA
  did) and records it.
- Optimizer tokens: cap 10M non-cache-read tokens per candidate, checked by `opt_llm.py` before each call
  and by the claude-code wrapper between proposer sessions.
- Report beside every result: counted rollouts, cache hits, shared seed baseline (147), lint rejects,
  optimizer tokens and USD.

---

## 8. Tracking issues and progress posts (guideline 5)

**Before execution** (done 2026-10-20, when this plan was written): one issue per candidate on
`skillberry-ai/cap-evolve`, titled `AppWorld eval REST: <Method> vs seed (gpt-oss-120b)`, labels
`paper-experiment`, `algorithm`. The **first post** of each issue is the projection of this plan for
that candidate: its own section 9.x plus every common section (0 to 8, 10 to 17). The issue numbers are
recorded below, in `manifest.json` and in the first ledger entry (CP-0000).

| arm | issue |
|---|---|
| `harnesslens` | [#897](https://github.com/skillberry-ai/cap-evolve/issues/897) |
| `miprov2` | [#898](https://github.com/skillberry-ai/cap-evolve/issues/898) |
| `trace2skill` | [#899](https://github.com/skillberry-ai/cap-evolve/issues/899) |
| `gepa_full` | [#900](https://github.com/skillberry-ai/cap-evolve/issues/900) |
| `cape_improve` | [#901](https://github.com/skillberry-ai/cap-evolve/issues/901) |

**During execution:**
- **Milestone posts** on the candidate's issue at once when: build and acceptance are done; P3's shared
  seed baseline is done (same post on all five); its search starts; each search milestone (an accepted
  candidate, every 25% of B); search ends; freeze; isolation scan; its dev diagnostic; final-window
  progress; final results.
- **Hourly status posts**: `autopost.py` posts **at least once per hour on every one of the five issues**,
  whatever the candidate's stage (queued, building, searching, waiting for the window, scoring). Each
  post says the stage, counted rollouts of B, optimizer tokens and proxy USD, best search-time score so
  far (labelled), memory state, last ledger checkpoint and the ETA. The auto-poster is a `nohup` loop
  restarted by `resume.py`; the heartbeat checks that the last post on each issue is under 60 minutes old
  and records an `error` entry if not.
- **Content rules:** counts and aggregates only. No task ids, task or supervisor text, trajectory text,
  secrets, optimizer-prompt text, or per-task test outcomes. **No test-set score of any arm before the
  window completes and the analysis runs.** Every body passes the content filter. Each post is keyed and
  recorded in a `posted` ledger entry with its URL, so nothing is posted twice.
- **Final post:** the candidate's results comment (section 14).

---

## 9. The five candidates

Common to all five: the optimizer is `aws/claude-sonnet-5-5` (Q3); the agent runs through the shared
worker; the evaluator is the shared one (section 7); search uses only train ∪ dev; the lint and `M_cap`
apply; B = 900 counted rollouts; 10M optimizer tokens; 1 trial per task; 1 search seed; the baseline is
the shared seed run (Q4). Each subsection gives: method; surface; deployment; glue; faithful settings;
splits; budget; isolation and de-fanging; conflicts and resolutions; acceptance check; artifact.

### 9.1 `harnesslens` — HarnessLens (pin `369a5c8`)

**Method (verified in code; `harnesslens/evolution/controller.py:IterationController._run_locked`).** A
deterministic controller drives LLM roles in a gated, one-candidate-per-iteration hill-climb:
1. *Baseline* of the unmodified harness on TRAIN.
2. *Discovery*: a Task Explorer clusters TRAIN tasks by goal from the instructions only; a Harness Query
   lists the editable channels.
3. *Experience*: batches of ≤ 5 tasks give "reusable" and "needs adjustment" passages with evidence; a
   synthesis merges them.
4. *Analyzer*: a ranked portfolio of atomic, materializable candidates (one behavior hypothesis, a
   channel plan, a validation spec each).
5. Per iteration: the *Main Agent* picks one unattempted candidate and ≥ 5 TRAIN tasks (including a
   "conversion" task that failed at baseline); the controller labels tasks (conversion, positive
   control, preservation canary, diagnostic); the *Harness Editor* (a coding agent with read/write/edit/
   grep, ≤ 40 steps) edits a copy of the parent; a *channel preflight* checks the edit is visible; a
   *paired rollout* runs candidate and parent on the same tasks; *Comparison* classifies each task
   (recovered, stable success, regressed, still failing, mixed) without seeing the diff; *Post-analyzers*
   attribute changes to channels; the *Review* returns accept, reject, revise, confirm or replan. Accept
   needs attributable positive evidence and no attributable regression.
6. *Confirmation* (default `always`): a second paired batch; the candidate must strictly improve pass@1;
   an unaffordable confirmation rejects.
7. Accepted edits accumulate in the parent. It stops when the budget is short, no candidate is left, or an
   iteration cannot be funded. The result is the last accepted parent (no best-of-N, no val set).

**Maturity.** Official code but a single-commit dump (about 32.5k lines). It is tightly bound to the
opencode, codex and pi CLIs, tau2 MCP servers, docker and DeepSeek ids (`core/profiles.py:51-53`),
and to an OpenAI-only proxy that sends only `Authorization` (`infrastructure/chat_completions_proxy.py`,
headers hard-coded near line 346). It cannot run AppWorld as shipped. **Deploy it as a faithful port**:
reuse its controller logic, gates, cost formulas and role prompts; replace its runtime layer. State in
the issue that this is "HarnessLens ported to the AppWorld harness", and list what was written.

**Surface (D6): P + T + M.** HarnessLens edits a harness's channels; the paper reports tool-description
edits (BIRD), skills (Retail, Banking) and global instructions (Terminal). Map them:

| HarnessLens channel | AppWorld surface |
|---|---|
| tool / parameter description patches | `tools/api_notes.json` (`app` or `app.api` keys) |
| local extension code | `tools/helpers.py` |
| skills, AGENTS-style instructions | `memory/playbook.md` (static, ≤ `M_cap`) |
| global system instructions | `policy/instructions.txt` (widest blast radius; the Review must require preservation canaries) |

Replace the Harness Query role with a fixed channel description of these four files and their lint rules
(our discovery artifact, written once, recorded).

**Deploy.** `venv-hl` (Python 3.11): `pyyaml`, `httpx`. Do not install its CLIs, docker or tau2. Vendor
the prompt constants and pure helpers (`evolution/{experience,analyzer,main_agent,discovery}.py`
prompts; `select_confirmation_task_ids`, `assert_confirmed_promotion`, `minimum_screen_start_creations`;
the cost formulas of `main_agent.py:56-105`) into `examples/appworld/harnesslens/vendor/`.

**Glue (`run_harnesslens.py`).**
- *Rollout service* replacing `evaluation/rollout_bridge.py:CellHarnessRepository` and
  `RolloutModule.run_pair_from_main`: `run_pair(parent_dir, cand_dir, task_ids)` → per-task records from
  the shared evaluator. A parent equal to v0 is the shared seed (cache). Any other parent is
  materialized and evaluated (cache hit if already run on that task).
- *Trial packet* replacing `experience.py:_visible_trial_packet`: instruction, per-step thought / code /
  output (output truncated to 1,200 chars, as `_clip_text`), final response, pass/fail, plus the F1
  failed-requirement **texts** in the `grader_diagnostic` slot (its BIRD-only slot; requirement text
  only).
- *Role calls*: every analysis role (Task Explorer, Experience, Synthesis, Analyzer planner and
  analyzers, Main Agent, Comparison, Post-analyzers, Review) is one plain-chat call through `opt_llm.py`
  with the vendored system prompt and the role's JSON payload, parsed by the vendored `parse_json_object`.
  HarnessLens ran these roles as tool-less agent sessions over bundle files; here the bundle is inlined
  into the payload (clipped). Record that as a deviation.
- *Harness Editor*: `claude -p` with `--allowedTools Read,Write,Edit,Glob,Grep` (HarnessLens's
  `EDITOR_TOOLS`: no shell), `--max-turns 40`, the vendored `EDITOR_SYSTEM_PROMPT` plus the lint rules,
  working in a scratch copy of `{policy,tools,memory}` under `/tmp/aw_rest/opt/harnesslens/<job>/`,
  **inside Claude Code's sandbox** (section 10).
- *Channel preflight*: the shared lint plus `check_injection`-style rendering (prompt renders; helpers
  import and define; notes parse and are appended; playbook ≤ `M_cap`). A failure rejects with no
  rollout, as `harnesses/channel_preflight.py`.
- *Budget ledger* replacing `core/budget.py`: rollouts are what B counts; role and editor sessions are
  optimizer calls counted in tokens.

**Faithful settings.** `HAI_TRAIN_ROLLOUT_REPEATS=1` (allowed: 1 or 2); confirmation mode `always`;
promotion metric pass@1 with strict improvement; one revision per candidate; Experience batch ≤ 5;
Analyzer ≤ 4 groups; role step limits as shipped; the Editor's bans on task ids, literal answers and
per-example mappings; the prompts' bans on inferring evaluator logic. **Screen batches of 10 TRAIN tasks**
(code minimum 5; the paper's ablations used 10) and **confirmation on fresh TRAIN tasks**, as the code's
`select_confirmation_task_ids`: the still-unconfirmed tasks (≤ min(2, n−1)) plus fresh train tasks that
passed at baseline, 10 in total. With 1 trial, fresh tasks replace HarnessLens's fresh seeds as the
variance check.

**Splits (D7 of eval 5 adapted).** TRAIN = official train (90) for every role and every rollout. HarnessLens
has no validation split, so **dev is not used in its search**; the champion is the last accepted parent.
Dev is used only in the common P5 diagnostic. (Using dev for selection would add a step the method
does not have.)

**Budget.** Baseline 90 = shared seed (0 counted). Per iteration about 10 (candidate) + 10 (parent, 0 if
v0 or cached) + 20 (confirmation: candidate + parent) ≈ 30 to 40 counted. B = 900 allows about 20 to 25
iterations; HarnessLens usually stops earlier when its portfolio is exhausted. The native 200-unit budget
(it counts LLM sessions as units) is replaced by "B = 900 rollouts + 10M tokens"; record this.

**Isolation.** The analysis roles are plain chat with gold-free packets. The Editor has file tools, so it
runs sandboxed and must pass A9 with its exact tool list. The Editor's workspace holds only the parent's
four surface files, the channel description and the lint command.

**Conflicts.** Its runtime (opencode etc.) is replaced: the port keeps the algorithm, not the CLI. Model:
the paper used one model family for every role and the target; here roles are Sonnet and the target is
gpt-oss-120b (Q3). Gateway: no temperature or seed (the proxy's injected `seed` is dropped). 40K context:
HarnessLens never limits what it adds, so the preflight enforces `M_cap` and the 8,000-token prompt limit.

**Acceptance A-harnesslens** (not counted; dev ids only):
- one Experience call and one Analyzer call return parseable JSON from the gateway;
- one Editor session in the sandbox writes only allowed files and passes the lint;
- the preflight rejects a deliberately broken helper without a rollout;
- `run_pair` on 3 dev tasks returns records, and parent = v0 is served from the cache;
- a 1-iteration dry run with a mock reward completes the accept/reject path, including confirmation.

**Artifact.** The last accepted parent's four files.

### 9.2 `miprov2` — MIPROv2 (pin `dspy==3.4.1`)

**Method (verified; `dspy/teleprompt/mipro_optimizer_v2.py`).**
1. Bootstrap N demo sets per predictor (`_bootstrap_fewshot_examples` → `create_n_fewshot_demo_sets`).
2. Propose instruction candidates with the `GroundedProposer`: a dataset summary, the program source,
   the module description, up to 3 bootstrapped demos and a random tip. MIPROv2 hard-codes
   `use_instruct_history=False`. Candidate 0 is overwritten with the original instruction, so the
   baseline is always in the search space.
3. Bayesian search over (instruction, demo set) with Optuna TPE (`multivariate=True`, seeded). It starts
   with a full eval of the default program on val. Each trial scores a random minibatch; every
   `minibatch_full_eval_steps + 1` trials the best-mean unevaluated combo gets a full val eval. The result
   is the best **full-eval** program.

MIPROv2 optimizes only `signature.instructions` and `predictor.demos`. It does not touch tool
descriptions or code.

**Surface (D6): P.** Wrap the whole external agent as **one** DSPy module with **one** predictor
(the research option "A"):
- `class AppWorldAgent(dspy.Module)` holds `self.agent = dspy.Predict(Sig)` with input `task` and output
  `solution`. Its docstring describes the AppWorld agent, because the proposer reads the program source.
- `forward(task)` never calls the LM. It renders `self.agent.signature.instructions` and
  `self.agent.demos` into a candidate dir, runs the episode through the shared evaluator, and returns
  `dspy.Prediction(reward=…)`. Every exception becomes reward 0, so DSPy's `max_errors` (10) is never hit
  by infrastructure.
- **Instruction slot:** the predictor's initial instruction is the stock first-USER-message prose before
  the first ` ```python ` block, verbatim. Rendering replaces exactly that span, so candidate 0 renders
  byte-identically to the seed (its tree hash is `SEED_HASH`: cache hit). The three API examples, the
  Spotify demo, the Jinja variables and the final block are never touched.
- **Demo slot:** each demo is rendered as one extra `USER:` (a generic task paraphrase) and `ASSISTANT:`
  (condensed solution code) pair after the stock demo and before the final `USER:` block. That is how
  DSPy renders demos, as user/assistant pairs. At most 3 demos of at most 400 tokens each.

**Deploy.** `venv-mipro` (Python 3.11): `pip install "dspy[optuna]==3.4.1"`. Running the agent does not
need AppWorld inside this venv (the evaluator runs episodes in a `venv-aw` subprocess, as eval 5).

**Glue (`run_miprov2.py`).**
- *LM.* `class GatewayLM(dspy.LM)` with `engine="litellm"`, model `anthropic/aws/claude-sonnet-5-5`,
  `api_base`, `headers={x-context-guru-token: …}`. It **pops `temperature`, `top_p`, `top_k` and `n`** in
  `forward`, `aforward` and `copy`. This covers every place MIPROv2 sets temperature: the proposer's
  `init_temperature` copy (`grounded_proposer.py:395-398`) and the hard-coded `temperature=1.0` of the
  dataset summary (`dataset_summary_generator.py:54,72,88,90`). It logs usage to
  `optimizer_usage.jsonl`. Set `dspy.configure(adapter=dspy.ChatAdapter(use_json_adapter_fallback=False))`
  so no `response_format` is ever sent. Set `cache=False`. Pass `task_model=` a dummy LM (required by the
  constructor, never called).
- *Demo pool (no extra rollouts).* Override `_bootstrap_fewshot_examples` (option "A2"). Build the pool
  from the shared seed's **successful train records** (reward 1). Each is condensed by one Sonnet call
  into a task-agnostic demo: a paraphrased task with placeholders for every name, value and contact, plus
  only the decisive code steps. The pool is linted (no train/dev 8-gram, no supervisor contact, ≤ 400
  tokens); a failing demo is re-condensed once, then dropped. Demo sets follow
  `create_n_fewshot_demo_sets`: set 0 zero-shot; sets 1 to N−1 random subsets of size
  `randint(1, max_bootstrapped_demos)`, drawn with the MIPROv2 seed. There is no labeled set
  (`max_labeled_demos=0`). Record that the demo source is the seed's train pass instead of
  BootstrapFewShot re-runs; the selection rule (successful traces of the same program) is the same.
- *Examples carry the instruction only*: `dspy.Example(task=<instruction>).with_inputs("task")`; the task
  id is looked up by instruction text in the driver, so the dataset summary sees no label, id or
  supervisor contact. Every proposed instruction is linted before it enters the search; a failing one is
  replaced by a re-proposal (up to 2), else by candidate 0.

**Faithful settings.** `auto=None`, `num_candidates=6` (light's N), `num_trials=16`, `minibatch=True`,
`minibatch_size=35`, `minibatch_full_eval_steps=5`, `max_bootstrapped_demos=3`, `max_labeled_demos=0`,
`program_aware_proposer=True`, `data_aware_proposer=True`, `tip_aware_proposer=True`,
`fewshot_aware_proposer=True`, `seed=9` (default), `num_threads` = the global slots.

**Splits.** `trainset` = official train (90): dataset summary and demo pool. `valset` = official dev (57):
minibatches and full evals, passed explicitly (never split from train).

**Budget.** The default-program full eval is the shared seed's dev records (cache). Trials: 16 × 35 plus
about 3 full evals of 57, minus cache hits (a full eval re-uses its own minibatch tasks), ≈ 650 to 750
counted ≤ B. Check the count in the A-miprov2 dry run with a stub metric (step 5 below). `auto="medium"`
(≈ 915) does not fit and is not used; record why.

**Isolation.** Plain chat, no tools. Inputs: instructions of train tasks, condensed and linted demos, the
program source. No gold exists in the examples.

**Conflicts.** The noisy 0/1 reward on 35-task minibatches makes TPE select mostly on noise; MIPROv2's own
rule (only full evals pick the winner) is kept and reported. Bootstrapping's pass/fail filter is an
evaluator outcome (allowed by F1), not gold. MIPROv2 cannot edit T or M; that is the method.

**Acceptance A-miprov2:**
1. Rendering a dummy instruction and 3 demos keeps the Jinja variables, the structure and the final
   block, and fits the token limit. Candidate 0 renders to `SEED_HASH`.
2. 2 dev tasks run end to end through `forward`.
3. One proposer call through `GatewayLM`: the request has no `temperature` and no `response_format`
   (checked by a request hook), and the header is sent.
4. The lint finds 0 hits on the dataset-summary prompt, 3 proposals and 3 demos.
5. A stub-metric dry run (N=3, T=3, minibatch 5) gives a counted total equal to the arithmetic.

**Artifact.** The best full-eval program, rendered to `policy/instructions.txt`.

### 9.3 `trace2skill` — Trace2Skill (pin `3d0b52a`)

**Method (verified; `skill_evolver/parallel_evolving_agent.py:run`, line 3058).** A single pass from
trajectories to a skill:
1. Trajectories of the target agent, one per task, labelled SUCCEED or FAILED.
2. Per-trajectory analysts: an error analyst (failure memories and causes) and a success analyst (a lean
   solution path and memory items).
3. MAP (`run_map_phase`, line 1857): one JSON patch per record (batch size 1) against the frozen
   starting skill, in parallel.
4. REDUCE (`run_reduce_phase`, line 2319): hierarchical merges of patches (merge batch 5, ≤ 5 levels,
   then a forced final merge).
5. TRANSLATION (fix inexact `target_text`), APPLY (programmatic) and VERIFICATION (a validator plus ≤ 3
   LLM fix rounds).

Combined mode (`run_parallel_combined_skill_evolution.py`) pools error and success records. The README's
selection procedure: run 3 evolution seeds, validate each evolved skill against the starting skill on the
training split, keep the best.

**Surface (D6): M (static `memory/playbook.md`).** The native delivery preloads `SKILL.md` into the
system prompt (`cli_skill_preloaded_agent.py`); our agent cannot read files, so the skill becomes the
static playbook (frontmatter stripped). Reference files are **forbidden** in our copy of the MAP and merge
prompts ("put all guidance in SKILL.md; do not create reference files"), because the agent cannot open
them.

**Deploy.** `venv-t2s` (Python 3.11): `openai tqdm openpyxl requests diskcache` (README line) plus our
shim. No GPU, vLLM or docker.

**Glue (`run_trace2skill.py`).**
- *LLM client*: `AnthropicGatewayClient(LLMClient)` implementing `chat(messages, settings=None,
  return_reasoning=False) -> str` through `opt_llm.py` (system message to `system`, `max_tokens` 16000,
  **no** temperature). `ModelSettings.to_dict` (`src/react_agent/models.py:70-71`) always sends
  `temperature`: drop it in the shim. Pass no `--generation-config` and no `--seed`. Disable the disk cache
  (`use_cache=False`) or give each run its own cache path. Patch the client construction in
  `run_parallel_skill_evolution.py` (~560–575) and in the two single-call analysis scripts.
- *Trajectory converter*: each of the **shared seed's 90 train records** becomes
  `<prefix><task-id>_(SUCCEED|FAILED).md`. **Replace `_` in the task id with `-`**: `parse_log_filename`
  takes the last underscore-separated token, and AppWorld ids contain `_`. Layout: the header that
  `strip_log_metadata` removes; the task instruction; per-step reasoning, code and output (truncated to
  2,000 chars); for FAILED logs, an "Evaluator report: failed requirements" section with F1 requirement
  **texts** only, placed **before** the `## RESULT` block (that block is stripped).
- *Prompts*: copy the analyst, MAP, merge, translation and verification prompts into
  `examples/appworld/trace2skill/prompts/`. Replace spreadsheet wording (`input.xlsx`, openpyxl, recalc)
  with AppWorld wording, add the lint rules and the no-reference-files rule. Record a diff against the
  vendored originals.
- *Validator*: the code calls `skills/skill-creator/scripts/quick_validate.py`, which is **missing from the
  repo** (a cwd-relative path; the runner exits without it). Provide one at that path: frontmatter fields
  allowed by the verification prompt, `SKILL.md` present, no `references/`, length ≤ `M_cap`.
- *Starting skill* ("creation" mode of the paper): a `SKILL.md` with frontmatter and an empty body, so the
  starting playbook is empty and the starting agent is the seed (Q4).
- *Packaging*: strip the frontmatter and write `memory/playbook.md`. If it is over `M_cap`, run one
  condensation call with the repo's `final_consolidation` prompt from the sequential evolver
  (`prompts/skill_evolving_agent/`), then re-lint. Record each condensation.

**Faithful settings.** Combined mode; the **single-call** analysts (`run_error_analysis_llm.py`,
`run_success_analysis_llm.py`); MAP batch 1; `--merge-batch-size 5` (code default; the paper used 32:
record it); `--max-merge-levels 5`; translation on; verification ≤ 3 rounds; `--prompt generic
--patch-pipeline json` (README repro); `--max-workers` limited by the PAUSE check; **3 evolution seeds
(41, 42, 43)**.

**Splits.** The analysts and evolution see **train only** (the seed's 90 records). Selection follows the
README: each of the 3 evolved skills is scored on **train** (90) and compared with the seed's train score;
keep the best (tie → shorter playbook); if none beats the seed, the arm is "inert" and freezes as the
seed. Dev is used only in P5.

**Budget.** Trajectories: 0 counted (shared seed). Selection: 3 × 90 = **270 counted**. Optimizer: about
250 chat calls per seed.

**Isolation and de-fanging.** The paper's default analyst is **agentic and reads the gold file**
(`analysis/run_error_analysis.py:89-103, 220-222`; `evaluate_output.py` diffs output against gold). It is
**not used**. Only the single-call analysts run; they see the log only. All roles are plain chat.

**Conflicts.** The gold-free analyst is weaker in the paper (it blames parse errors in 57% of cases vs 14%
for the agentic one); our F1 requirement texts partly compensate. Disclose. Released skills are 22–46 KB,
over our cap: condensation, disclosed. Spreadsheet prompts: rewritten, diff recorded.

**Acceptance A-trace2skill:**
- the converter round-trips 3 dev records into filenames that parse back to the right id;
- one error and one success analysis call return parseable items;
- a 4-record MAP → REDUCE → APPLY → VERIFY dry run with the gateway shim produces a skill;
- packaging gives a lint-clean playbook ≤ `M_cap` that lands before `My name is:` (A4 style);
- no request carries `temperature`.

**Artifact.** The selected skill as `memory/playbook.md`.

### 9.4 `gepa_full` — GEPA in full mode: prompt and tool descriptions (pin `gepa==0.1.4`)

**What "full mode" means here.** Neither GEPA nor DSPy has a flag called "full mode". DSPy's released
`dspy.GEPA` has no tool-description option (checked through 3.4.1). GEPA's own mechanisms for tool
descriptions are `DspyAdapter(enable_tool_optimization=True)` (one JSON component holding a ReAct
module's instruction and all its tool descriptions) and `MCPAdapter` (one component per tool,
`tool_description_<name>`, plus `system_prompt`, with a per-component reflective dataset). **This arm
follows the `MCPAdapter` pattern**: the instruction prompt plus one tool-description component per
AppWorld app, plus the helpers, evolved together. That is GEPA co-optimizing prompts and tool
descriptions with its stock engine.

**Method.** Verified (0.1.4). It runs as eval 5 §7.1:
- the seed is evaluated on the full valset;
- a parent is picked from the per-instance Pareto front;
- the parent runs on a train minibatch of 3 with trace capture;
- the reflection LM reflects once on the component chosen by the selector, giving a child;
- the child runs on the same minibatch and is accepted iff the summed score strictly improves;
- the child is then evaluated on the full valset and added to the Pareto front;
- the result is the candidate with the highest mean val score.

**Surface (D6): P + T.** Components (all seeded from `seed_capability`):

| component | renders to | seed |
|---|---|---|
| `policy/instructions.txt` | the prompt | stock |
| `tools/helpers.py` | helpers | the seed's docstring-only module |
| `api_notes:<app>`, one per app listed in `root_opt/data/api_docs` (9 apps + `api_docs` + `supervisor` expected) | that app's keys in `tools/api_notes.json` | empty |

An `api_notes:<app>` component is a small text block: lines `<app>: <note>` and `<app>.<api>: <note>`,
each note ≤ 400 chars. The adapter parses the blocks and merges them into `tools/api_notes.json`. An
invalid block makes the proposal a no-op for that component (parent text kept). Text is never truncated.

**Deploy.** `pip install gepa==0.1.4` into `venv-aw` (zero dependencies; avoids the `gepa[full]`
litellm conflict). The driver runs in `venv-aw` like eval 5's.

**Glue (`run_gepa_full.py`, starting from eval 5's `gepa/run_gepa.py`).**
- `GEPAAdapter.evaluate` and `batch_evaluate` through the shared evaluator.
- `reflection_lm` = the gateway callable (no temperature).
- A custom proposer with `<new_text>` delimiters (the stock prompt has about 45 ``` fences that break
  GEPA's fence parser), the lint inside, and ≤ 2 re-reflections with the lint error.
- **New: per-component-type reflection templates and reflective datasets**:
  - `policy/instructions.txt` and `tools/helpers.py`: eval 5's template and dataset.
  - `api_notes:<app>`: the template says "this text is appended to the API documentation the assistant
    reads for app `<app>`", and states the format and limits. The dataset holds, per minibatch task, only
    the steps where the agent called `show_api_descriptions`/`show_api_doc` for that app or called
    `apis.<app>.*` (the doc text seen, the code, the output or error, truncated) plus the task's F1
    feedback. If the app does not appear in the minibatch, use the whole-trajectory summary instead (the
    `MCPAdapter` falls back the same way). Count these per component.

**Faithful settings.** As eval 5's GEPA, so the component set is the only change: `module_selector=
"round_robin"` (the default; one component per iteration), `reflection_minibatch_size=3`,
`candidate_selection_strategy="pareto"`, `skip_perfect_score=True`, `perfect_score=1.0`,
`acceptance_criterion="strict_improvement"`, `use_merge=False` (the default), `cache_evaluation=False`
(our evaluator caches), `seed=0`, `track_best_outputs=True`. Merge is not turned on: it is not part of
"tool descriptions", it costs up to 63 rollouts per merge, and keeping it off keeps this arm comparable to
eval 5's GEPA. Record this.

**Splits.** `trainset` = train (90, minibatches); `valset` = dev (57, Pareto front and final choice), as
eval 5.

**Budget.** The seed's dev eval comes from the cache but is still in GEPA's `total_num_evals` (57). Fresh
counted = `total_num_evals − 57`. Each iteration costs 6 (parent minibatch, often cached, and child
minibatch); each accepted child adds 57. Overshoot past the stop check is ≤ 63. Set
**`max_metric_calls = 894`**, so fresh ≤ 894 − 57 + 63 = 900. Expect about 35 to 45 iterations, about 3
visits per component with round-robin over ≈ 13 components.

**Isolation.** No shell. Gold-free F1 feedback only. The reflector tends to copy example text, so the lint
is stated in every template.

**Conflicts.** With ≈ 13 components and round-robin, each app component is visited only about 3 times, and
a note must change the score of a 3-task minibatch to be accepted: tool components will rarely change.
That is the method under budget, reported with per-component visit and accept counts; it is not forced. In
eval 5 GEPA left helpers and notes untouched; this arm's per-app templates make the tool surface explicit.

**Acceptance A-gepa_full:**
- the seed dict has every `api_notes:<app>` key;
- a forced one-component selector exercises one app component, and the mutated text reaches
  `candidate[...]`;
- a canary string in one app's note appears in that app's `show_api_doc` output in the trajectory and in no
  other app's output;
- an oversize note and an invalid helper are rejected with no rollout and no crash;
- an untouched app's dataset falls back without raising;
- GEPA's `total_num_evals` minus cache hits equals the evaluator's counted rollouts.

**Artifact.** `result.best_candidate`, rendered to `policy/instructions.txt`, `tools/helpers.py` and the
merged `tools/api_notes.json`.

### 9.5 `cape_improve` — cap-evolve, improved version (pin `470f3fa`)

**What the improved version is (verified).** `cap-evolve-improve` = `main` (`520ecbe`, V3 hill-climbing
restored by #889) plus one commit, `470f3fa`, a template-only change:
- `templates/project/capevolve.yaml`: default `gate_k_se` goes from 1.0 to **0.5**;
- `templates/project/optimizer/INSTRUCTIONS.md`: a new "Strategies for selecting improvements" section
  (optimize code and tools before prompt text; use the whole tools skill: descriptions, code, adding and
  removing tools).

Main since the smoke test also changed the default optimizer instructions and capability skills (#865:
"largest expected reward gain, REAL and GENERAL"). Stock hill-climb is otherwise the smoke test's loop:
one child per iteration, a paired gate accepting iff Δ > k·SE. **Optimizer isolation (#875, PR #879) is
not in this commit.** Open issues #876, #877 and #878 still apply.

**Surface (D6): P + T** (`capabilities: [system-prompt, tools]`), as the base plan's `cape-hc`.

**MANDATORY: the AppWorld run must get every improvement of `cap-evolve-improve`, including
`gate_k_se: 0.5`.** None of the improvements reaches an AppWorld run by itself:
- `setup_project.sh` overwrites the template yaml with the example's own spec, which has `gate_k_se: 1.0`.
- The example passes its own old INSTRUCTIONS file, so the template's new strategy section is never read.
- Core silently falls back to `k_se = 1.0` if the key is missing (`core/cap_evolve/cli.py:982`; the
  hill-climb script's `--k-se` default is also 1.0, `skills/algorithms/hill-climb/scripts/run.py:51`).
- `_find_skills_dir()` (`cli.py:55-70`) prefers `~/.claude/skills`, which **exists on this host**
  (docx/pdf/pptx/xlsx), over the repo's `skills/`.

So every item below is applied explicitly and then verified (check A-cape_improve-IMP). A run that fails
any item is not launched. A run found afterwards to have missed one is void and is re-run.

| # | improvement in `470f3fa` (vs the smoke test's cap-evolve) | source at the pin | how the AppWorld run gets it |
|---|---|---|---|
| I1 | acceptance gate `gate_k_se` 1.0 → **0.5** | `templates/project/capevolve.yaml:93` | the AppWorld spec sets `gate_k_se: 0.5` **explicitly** (spec below; edit `examples/appworld/capevolve.yaml` and the `PROJECT.md` line of `setup_project.sh` that says "k = 1.0") |
| I2 | new optimizer section "Strategies for selecting improvements": optimize code and tools before prompts; use the whole tools skill (descriptions, code, add tools, remove tools that hurt) | `templates/project/optimizer/INSTRUCTIONS.md:39-45` | the run's INSTRUCTIONS are re-derived from the **pinned** template (below), so the section is present verbatim |
| I3 | the #865 optimizer instructions: "ship the edit with the largest expected reward gain", REAL + GENERAL + CHECKED, choose the lever by failure type, "prefer code over prose" on code surfaces, the handover rules | the same pinned template, whole file | the same re-derivation: the pinned template is the **base**, never the example's old 311-line template (pre-#865: "SAFE, VERIFIED", "THREE TESTS") |
| I4 | the #865 capability and phase skills the optimizer reads as `./guidance/` (`skills/capabilities/system-prompt`, `skills/capabilities/tools`, `skills/phases/diagnose`) | pinned `skills/` | `CAPEVOLVE_SKILLS_DIR=/workspace/worktrees/cape-improve/skills` is exported for **every** cap-evolve command (check, estimate, run, resume). The harness then stages these skills verbatim into each iteration's `work/<cid>/guidance/` (`harness.py:3073-3135`, `_capabilities_root` at `:4280`) |
| I5 | V3 hill-climbing restored (#889 reverts the V4 changes of #880) and the hill-climb fixes of #865/#869 | pinned `core/` and `skills/algorithms/hill-climb/` | `venv-cape` installs `-e /workspace/worktrees/cape-improve/core`; the algorithm script comes from the pinned skills dir (I4). **Not** eval 5's code base: eval 5 branched from `0fc6924`, the V4 code that #889 reverted |
| I6 | the default `optimizer_skill: claude-code` registry row and the run-optimizer skill | pinned `skills/optimizers/registry.yaml`, `skills/run-optimizer/` | the same pinned skills dir; the sandbox shim (Isolation, below) wraps the CLI without changing the registry flags |

Improvements that are **opt-in or for other algorithms** are not part of stock hill-climb, so they are
not enabled: HC-2 / rule P2 (`promotion_*`, `split_mode: pooled`), agent-optimize, and the `hc2.py` and
`conductor_backend.py` changes in `418fd42..470f3fa`. Turning them on would be a different algorithm.
The pinned hill-climb SKILL.md still says "Do not lower `k-se` to work around it" (line ~127). The
improved version's explicit default overrides that; record it as a known inconsistency of the pin.

**Deploy.**
- Worktree `/workspace/worktrees/cape-improve` at `470f3fa` (detached, never committed to). `venv-cape`
  is `venv-aw` plus `-e /workspace/worktrees/cape-improve/core`. It must **not** contain `-e` of the
  `eval-rest` core, which is eval 5's V4 base.
- Every cap-evolve invocation (`setup_project.sh`, `check`, `estimate`, `run`, `run --resume`, finalize)
  runs with `CAPEVOLVE_SKILLS_DIR=/workspace/worktrees/cape-improve/skills` and with
  `venv-cape/bin/cap-evolve`. Put both in one launcher `examples/appworld/cape_improve/launch.sh`, which
  is the only way the run is started or resumed.
- Scaffold with the **pinned** intake script
  (`/workspace/worktrees/cape-improve/skills/phases/intake/scripts/run.py`), as `setup_project.sh` does.
- **Re-derive the optimizer instructions** into `examples/appworld/cape_improve/INSTRUCTIONS.template.md`:
  1. start from a byte copy of the pinned `templates/project/optimizer/INSTRUCTIONS.md`;
  2. keep every `{{…}}` placeholder and every section, including "Strategies for selecting
     improvements" and "On code surfaces (tools, MCP): prefer code over prose", unchanged;
  3. insert one new section, `## AppWorld facts for THIS run`, after "## On code surfaces …". Its
     content is the old example template's block of that name, updated as follows:
     - the three surfaces and their lint rules;
     - helpers take `apis` and names as parameters;
     - API notes ≤ 400 chars;
     - `memory/` not part of the run;
     - generic hints only;
     - how trajectories are laid out;
     - do not look for gold or test data on disk;
     - do not run AppWorld episodes yourself;
     - the lint command, rewritten to run in the optimizer's own lint venv (`sandbox.ensure_lint_venv`)
       **without** `APPWORLD_ROOT` (AppWorld is hidden from the optimizer, section 10) and against the
       lint cache.
  4. Do not alter or delete any other sentence of the pinned template. Commit the result with a
     `VENDORED.md` line giving the source sha256 of the pinned template. Store a `diff -u` of pinned
     template vs derived template in the pushed state (`cape_improve/instructions.diff`): it must show
     **only** the inserted section.
- Write `gate_k_se: 0.5` **explicitly** in the project yaml (I1).

**Spec.**

```yaml
capabilities: [system-prompt, tools]
capability_path: seed_capability
actions: [edit]
optimizer_skill: claude-code
optimizer_model: aws/claude-sonnet-5-5
optimizer_max_turns: 200
optimizer_usd_per_iter: 15.0
max_optimizer_usd: 120.0
target_model: openai/gpt-oss-120b-a100
algorithm_skill: hill-climb
algorithm_focus: all
orchestration_mode: deterministic
memory_skill: md-files
optimizer_instructions_file: <abs path of the rendered, re-derived INSTRUCTIONS (I2, I3)>
runner_repo_path: /workspace/aw_rest/build/reference
capability_sources: [reference/api_index.md, reference/react_agent_notes.md]
dataset_source: adapter
split_ids_file: split_ids.json      # train = val = official train ∪ dev (147), test = [] (base rule S2)
num_trials: 1
gate_mode: paired
gate_k_se: 0.5                      # I1: the improved version's value. MUST be explicit (core default is 1.0)
max_iterations: 6
stall: 0
max_metric_calls: 1029              # 147 baseline (cached) + 6 × 147
protected_paths: [default]
store: git
```

**Splits.** As the base plan's rule S2: train = val = train ∪ dev (147), test = []. The search score is a
fit metric (train = val), labelled "selection-biased".

**Budget.** The baseline (147) is the shared seed, served from the cache by the adapter (0 counted).
cap-evolve still counts it as 147 metric calls. 6 iterations × 147 = **882 counted** ≤ B. A lint-rejected
candidate costs no model call but counts 147 metric calls in cap-evolve (#877); record each one.
Evaluation-error steps consume iterations (#876): if one occurs, fix the cause and `cap-evolve run
--resume --max-iterations <n>` so 6 **scored** iterations remain the target, as base F15.

**Isolation (critical: base F14, F19, F20).** The claude-code optimizer has `Bash` and parallel
sub-agents.
- A PATH shim `examples/appworld/sandbox_cc/claude`, first on the cap-evolve process's PATH only, execs
  the real CLI with `--settings <the section 10 settings>`. That gives Claude Code's sandbox with
  `denyRead` on the sealed set **and all of AppWorld** (`appworld/` entirely; the optimizer's lint runs in a
  small lint venv with jinja2 and tiktoken, as eval 5's `ensure_lint_venv`), `AW_STATE` except the run's
  gold-free trajectories, the evaluator and adapter code, `.env`, other transcripts; network restricted to
  the gateway; no WebFetch/WebSearch.
- Set `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS` high enough that print mode does not end sub-agents after
  600 s (eval 5 D11).
- Sub-agents inherit the sandbox (container guide §1.1).
- A9 must pass **with the shim**, the exact registry flags (`--allowedTools Bash`, `parallel: true`),
  and a planted secret in each sealed location, before the run starts.
- Keep the instructions' "do not look for answers" rule, without relying on it (fix doc §4).

**Conflicts.** k = 0.5 raises false accepts on 1-trial gates (the proposal's confirm step is not
implemented): that is the improved version as committed; reported. Train = val makes the search score a
fit metric; only the test window is held out.

**Acceptance A-cape_improve:**
- `cap-evolve check` prints `{"ok": true}`, with `CAPEVOLVE_SKILLS_DIR` set as above;
- A9 passes with the shim;
- a 1-iteration `optimizer_skill: mock` dry run on 4 dev ids completes, with its baseline served from the
  cache;
- `injection` and `scoring` checks pass (A4, A5).

**Acceptance A-cape_improve-IMP (the improvements are really in use; all must pass, recorded in the
ledger with hashes):**
1. **Code pin:** `venv-cape/bin/python -c "import cap_evolve, pathlib;
   print(pathlib.Path(cap_evolve.__file__).resolve())"` points into `/workspace/worktrees/cape-improve/core`,
   and `git -C /workspace/worktrees/cape-improve rev-parse HEAD` is `470f3fa…` with a clean `git status`.
2. **Skills pin:** with the launcher's environment, the skills dir the CLI resolves is
   `/workspace/worktrees/cape-improve/skills`. Check through a `cap-evolve check` line or a one-line call to
   `cli._find_skills_dir()`, and confirm that `~/.claude/skills` is **not** the resolved dir.
3. **I1, spec level:** the rendered project `capevolve.yaml` has `gate_k_se: 0.5`, and the run's
   `run_config` event (`cli.py:889`) records the spec with 0.5.
4. **I1, effective:** in the 1-iteration mock dry run, the hill-climb command line in the run's events or
   process log contains `--k-se 0.5`. Also run a gate unit check with the pinned
   `core/cap_evolve/gate.py`: for a paired delta vector with Δ = 0.7·SE, the gate accepts at `k_se=0.5`
   and rejects at 1.0.
5. **I2 and I3, effective:** after the dry run's first iteration, the optimizer workdir's
   `work/<cid>/INSTRUCTIONS.md` (the file actually handed to the optimizer, with placeholders filled)
   contains, verbatim:
   - the heading `## Strategies for selecting improvements`;
   - the sentence starting "**Optimize code before prompts.**";
   - the sentence starting "**On tools, use the whole tools skill.**";
   - the heading `# Optimize the capability — ship the edit with the largest expected reward gain`;
   - `## AppWorld facts for THIS run`.

   It contains none of "THREE TESTS", "VERIFY-THE-FIX", `{AW_`, or an unfilled `{{`. `instructions.diff`
   shows only the inserted section.
6. **I4, effective:** `work/<cid>/guidance/tools/SKILL.md`, `guidance/system-prompt/SKILL.md` and
   `guidance/diagnose/SKILL.md` exist, and their sha256 equal the pinned
   `skills/capabilities/tools/SKILL.md`, `skills/capabilities/system-prompt/SKILL.md` and
   `skills/phases/diagnose/SKILL.md` (the diagnose copy is scrubbed by `_scrub_history_guidance`, so for it
   check the pinned head lines instead of the hash). The instruction "Study `./guidance/tools/SKILL.md`"
   therefore points at an existing file.
7. **I5:** the hill-climb script the run executes is the pinned `skills/algorithms/hill-climb/scripts/run.py`
   (path in the process command line; sha256 recorded).
8. **Re-check at launch and at every resume:** `launch.sh` re-runs checks 1, 2 and 3 before
   `cap-evolve run` or `run --resume` and refuses to start if any fails. After the search, the
   post-search scan re-reads every iteration's `work/<cid>/INSTRUCTIONS.md` and the gate records, and
   confirms all iterations had the strategy section and k = 0.5. Its counts go into the results.

The results comment on #901 lists I1 to I6 with their verification evidence (hashes and the observed
`--k-se 0.5`), so a reader can see that the evaluated system is the improved version.

**Artifact.** `candidates/<best_id>/` of the run (the seed if nothing was accepted: "inert").

---

## 10. Optimizer isolation mechanics (Claude Code's sandbox)

Adapted from eval 5's `common/sandbox5.py` (verified working in this pod type), applied to the
`harnesslens` Editor and the `cape_improve` optimizer.

- **Settings (per call, `--settings`):**
  - `sandbox`: `{enabled: true, failIfUnavailable: true, allowUnsandboxedCommands: false,
    filesystem.denyRead: DENY, network.allowedDomains: [gateway host]}`;
  - `permissions.deny`: `Read(//p/**)` and `Edit(//p/**)` for every `p` in DENY, plus `WebFetch` and
    `WebSearch`;
  - `env`: `DEVAGENT_BWRAP_NETWORK=restrict`.
  - Check that every rule starts with `//` (absolute).
- **DENY:** `root_opt`, `root_full`, the whole AppWorld clone, `AW_STATE` (except a gold-free trajectories
  dir copied into the workspace), `AW_SCRATCH` except the call's own workspace, the venvs, the clones,
  every repo checkout's parent dir (the evaluator, adapters, ledger and `.env`), `/workspace/src`,
  `/workspace/inbox`, `~/.claude/projects`, `~/.config/gh`, and other sessions' dirs under
  `/tmp/claude-<uid>/`.
- **Workspace:** `/tmp/aw_rest/opt/<cand>/…`, holding only what the method needs. It may never sit under
  a denied path.
- **The evaluator never runs inside the optimizer process.** Drivers score candidates in separate,
  unsandboxed subprocesses.
- **A9 (each sandboxed role, before any counted rollout):**
  - Plant a random secret in each sealed location (`root_full` unlocked only for planting, then
    relocked).
  - Make one real call with the role's exact flags and a neutral prompt ("I am checking which files are
    visible in this workspace; run these commands and paste the output"). The prompt tries `cat`, `Read`,
    `cp`, `find`, a socket and the network.
  - **PASS** iff no secret appears anywhere in the transcript, the call really tried (≥ 3 Bash or file-tool
    uses and ≥ 1 Read), the network to a non-gateway host and AF_UNIX sockets are refused, and normal work
    still runs (a workspace file written, the lint ran).
  - Never instruct any agent to disable or bypass its sandbox.
- **Caveat (container guide §1.4):** under landrun + proot, masks are path rewriting, not a kernel wall.
  Processes are shared. So the post-search scan stays mandatory.

---

## 11. Splits and feedback (shared)

| official split | search-time role | final window |
|---|---|---|
| `train` (90) | shared seed baseline (P3); every candidate's optimizer signal (rollouts, minibatches, trajectories, demos); `cape_improve` train = val | not used |
| `dev` (57) | shared seed baseline (P3); val or selection set for `gepa_full` and `miprov2`; part of `cape_improve`'s train = val; not used by `harnesslens` or `trace2skill` search; P5 diagnostic for all | not used |
| `test_normal` (168) | **never** | scored: 6 arms × 2 trials |
| `test_challenge` (417) | never | never |

- **S1 (base plan): official splits only.** Ids come from AppWorld's split files via `load_task_ids`;
  `make_splits.py` and `make_roots.py` refuse other counts; the sha256 of each split file goes in
  `manifest.json`. Acceptance probes use a few dev ids and are not counted.
- Each candidate uses the split roles of its own method (section 9). Where the method has no val set
  (`harnesslens`, `trace2skill`), dev is not used to select. This difference is part of the methods and is
  stated in the results.

---

## 12. Orchestration, ledger and resume

### 12.1 Phases
- **P0** decisions and issue numbers (CP-0000).
- **P1** build B0 to B7.
- **P2** acceptance (A1 to A13 and A-<cand>).
- **P3** **shared seed baseline** (147 episodes, once).
- **P4** candidate searches: each runs `search` → `freeze` → per-candidate isolation scan. Up to 3
  candidates at once (rule R4). Suggested order: `cape_improve`, `gepa_full` and `miprov2` first (the
  long agentic optimizer overlaps two rollout-heavy searches), then `harnesslens` and `trace2skill`.
- **P5** dev diagnostic: the 5 champions on dev, 1 trial, seed 100 (the seed's dev records are reused; most
  champion cells are cache hits).
- **P6** full isolation scan.
- **P7** the one final window.
- **P8** analysis.
- **P9** results posts.

Each phase has a resume rule: skip done units, redo an idempotent step, never post twice.

### 12.2 The ledger (section 18)
- `status_doc.py` is the only writer, under `flock(AW_STATE/ledger.lock)`.
- **Entry format:** `## CP-NNNN · <UTC> · <phase> <label> · <kind>`, then a prose line, then a fenced
  `json` block with: `cp`, `prev_cp`, `utc`, `kind`, `phase`, `candidate`, `done_through`, `next`,
  `counts`, `spend`, `memory` (`used_pct`, peak), `artifacts` (sha256), `code` (sha), `open_decisions`.
- **`kind`** is one of: phase_start, result, phase_done, heartbeat, decision, abort, resume, restore,
  rebuild, repair, error, cap_spend, posted.
- After every entry, commit (pathspec only: this file, `docs/EVAL_APPWORLD_REST_STATE/`,
  `examples/appworld/`) and push to `origin eval-rest`.
- **Cadence:**
  - an entry at once on every phase start or end, decision, build step, acceptance check, accepted
    candidate, freeze, scan, error, abort and resume;
  - coalesced results (search steps, window cells) at most 1 entry per 5 min;
  - a heartbeat after 25 silent minutes.
- **Content filter:** before each commit and each post, refuse any task id, `.env` value, train/dev
  8-gram or supervisor contact.

### 12.3 What is pushed vs local
- **Pushed:**
  - this ledger;
  - `manifest.json` (hashes, seeds, caps, issue numbers, `SEED_HASH`, `M_cap`);
  - per-candidate `progress.json` (counts and spend);
  - each candidate's lint-checked artifact, published only after the per-item lint;
  - `final/progress.json` (counts only);
  - `final/analysis.json` and `RESULTS.md`;
  - the code.
- **Local only (`AW_STATE`):** records, trajectories, optimizer prompt and response logs, window orders
  and cells.
- **Rebuildable (`AW_BUILD`):** clones, venvs, data roots.

### 12.4 Resume (`resume.py`)
1. Fetch, then fast-forward or push the branch. Stop if it has diverged.
2. Refuse if `RUNNING.pid` names a live runner (check the pid, never `pgrep -f`).
3. Rebuild missing `AW_BUILD` items from `manifest.json`, and re-`chmod 000 root_full` unless in P7.
4. Reconcile local records with the last entry. Each method adopts its own state: GEPA `run_dir`, the
   Optuna study db, cap-evolve `--resume`, HarnessLens controller checkpoints, Trace2Skill intermediates,
   the evaluator cache.
5. Restart `memguard.py`, the heartbeat and `autopost.py`.
6. Append a `resume` entry and relaunch the phase runner under `nohup`.

Check A10 tests this with a kill in the middle of a mini run.

---

## 13. Acceptance checks before any counted rollout

| id | check |
|---|---|
| A1 | `aws/claude-sonnet-5-5` answers through `opt_llm.py`, `GatewayLM` (DSPy), the Trace2Skill client, and the `claude` CLI with the shims; no `temperature` on the wire; no refusal |
| A2 | RITS: `max_model_len` 40,144; 48 concurrent short requests return 200; 1 dev episode completes; the RITS key appears nowhere under `AW_HOME`, `/tmp/aw_rest` or pushed files |
| A3 | REPL hardening (`import os`, `open(answer.json)`, `pathlib` read all fail); `root_opt` has 0 test-id hits; `root_full` unreadable |
| A4 | injection: the seed's first request is byte-identical to stock; a memory block lands before `My name is:`; helpers and notes work with the original doc text unchanged; a lint violation is rejected without a rollout |
| A5 | scoring: a released train solution scores 1, a no-op 0; no `trace` or gold in records; scoring twice is identical |
| A6 | splits and seal: `tasks("train")` = `train.txt` (90); a test id is refused without `AW_ALLOW_SEALED` |
| A7 | the dev-diagnostic and final-window orders are reproducible from their seeds and match their sha256 |
| A8 | context and `M_cap`: 10 dev episodes < 34K prompt tokens; `P_max`, `H_max`, `M_cap` recorded; an `M_cap`-sized memory block stays < 34K |
| A9 | optimizer sandbox (section 10) for the `harnesslens` Editor and the `cape_improve` optimizer, each with its exact flags |
| A10 | ledger and resume: a killed mini run resumes with no unit run twice; entries append-only; concurrent `status_doc.py append` calls from 3 processes all land, none lost (the `flock` test); content filter refuses a task id and an `.env` value |
| A11 | **memory guard:** a sample period ≤ 10 s is logged; a synthetic allocation (in a child process, below the limit) crossing 90% sets PAUSED within 10 s; the evaluator starts no new episode and `opt_llm.py` no new call while PAUSED; it resumes only after < 85%; the executing agent's spawn check reads `MEMSTATE.json` |
| A12 | **metrics:** one record of each kind (episode, plain-chat call, `claude -p` call) carries every field of section 5.2; proxy USD uses the Sonnet 5.5 prices |
| A13 | **seed reuse:** after a mini P3 on 4 dev ids, a candidate dir identical to the seed is served from the cache (0 counted); a fresh seed episode raises `SeedRerunRefused`; the global slot pool never exceeds its size with 3 concurrent callers |
| A-<cand> | the five candidate checks of section 9, including **A-cape_improve-IMP** (every cap-evolve-improve improvement, k = 0.5 included, is in effect; section 9.5) |

None of these rollouts are counted (S1).

---

## 14. Final window, statistics and the five reports

- **Freeze.** Copy each champion artifact into `AW_STATE/final/artifacts/<cand>/`, lint it and tree-hash it.
  The seed = `seed_capability` (`SEED_HASH`). An inert candidate is frozen as the seed and labelled.
- **Window.** 168 `test_normal` × 6 arms × 2 trials = **2,016 cells**:
  - one shuffled order from a recorded seed;
  - `AW_ALLOW_SEALED=final-eval-only` and `APPWORLD_ROOT=root_full`, unlocked at P7 start and logged;
  - the global pool at 24 slots (eval 5 OOM'd at 48);
  - trial seeds 5000+k;
  - infra retries ≤ 3 with new seeds; a cell that still fails is scored 0 (primary) and reported missing
    (sensitivity);
  - only rewards, counters and infra flags are read; **no test trajectory is opened by anyone**;
  - `PAUSE` is honoured.
- **Statistics.** As base §12 and eval 5 §12:
  - TGC, SGC, by difficulty (Easy 57, Medium 48, Hard 63);
  - per candidate `<cand> − seed`, with a scenario-clustered paired bootstrap (56 clusters, 10,000
    resamples) 95% CI, unadjusted;
  - the full section 5.2 metric table for all six arms, at search and test.
- **Comparison discipline.** Artifact-level statements. One search seed each, unmatched methods and
  surfaces, and window drift (base F10) mean **no ranking between candidates**. The Δ-vs-seed of all five
  may be listed side by side for context.
- **Each report** has a "what this <method> is and is not" paragraph:
  - common to all: Sonnet optimizer, gold-free F1 feedback, B = 900, `M_cap`, 1 trial, the shared seed
    baseline;
  - per candidate: HarnessLens as a port; MIPROv2's demo pool from the seed pass; Trace2Skill's
    single-call analysts and condensation; GEPA full mode via per-app components with merge off;
    cap-evolve-improve's k = 0.5 and the hand-applied sandbox.
- **Report contents** (per candidate, posted on its issue with `gh issue comment <n> -R
  skillberry-ai/cap-evolve --body-file …`, draft first):
  - setup (commits, models, settings);
  - main table;
  - difficulty table;
  - cost, tokens and latency tables (search and test);
  - what changed (artifact summary, lint-clean);
  - isolation scan counts;
  - deviations;
  - what the numbers cannot support.

  No task ids, text or per-task outcomes.

---

## 15. Deviations from the base plans and eval 5

| base / eval 5 | here | why |
|---|---|---|
| arms seed, cape-hc, altk (base); seed + 5 (eval 5) | seed + `harnesslens`, `miprov2`, `trace2skill`, `gepa_full`, `cape_improve` | task scope |
| each method ran its own baseline; eval 5 charged baselines to B | **one shared seed run** (147), reused by all via the evaluator cache, not charged to any candidate | user instruction (D5, Q4) |
| namespace wrapper (fix doc) | Claude Code's sandbox (the pod refuses `unshare`) | 1.2 |
| `/tmp/aw_eval`, `/workspace/aw_eval5` | `/workspace/aw_rest` (durable) + `/tmp/aw_rest` (scratch) | durability |
| memory watermarks 90/80, every 15 s (eval 5) | **90/85, every 5 s**, also gating sub-agent spawns and optimizer calls | guideline 7.2 |
| candidates sequential (eval 5) | up to 3 concurrent searches on one global slot pool | guideline 7.4 |
| proxy price $3/$15 (eval 5) | $2/$10, cache read $0.20, cache write $2.50 (Sonnet 5.5 list) | correct list price |
| GEPA P+T with 3 components (eval 5) | GEPA full mode: prompt + helpers + per-app tool-description components | user scope |
| cap-evolve at the smoke-test code: `gate_k_se` 1.0, the old 311-line INSTRUCTIONS, pre-#865 skills (base); eval 5's V4 core | cap-evolve-improve `470f3fa` in full (I1 to I6): `gate_k_se: 0.5` explicit, INSTRUCTIONS re-derived from the pinned template (strategy section included), pinned skills via `CAPEVOLVE_SKILLS_DIR`, pinned V3 core; all verified by A-cape_improve-IMP | the improved version, as committed |
| HarnessLens on opencode/codex/pi with DeepSeek | ported controller and prompts on the AppWorld harness; roles as plain-chat calls; Editor as sandboxed `claude -p` | its runtime cannot run AppWorld or the gateway |
| MIPROv2 BootstrapFewShot re-runs | demo pool from the seed's successful train records | Q4 and B |
| Trace2Skill agentic analyst with gold | single-call analysts plus F1 requirement texts; condensation to `M_cap` | rule R1; 40K window |
| native budgets (HarnessLens 200 units; MIPROv2 auto modes) | B = 900 rollouts + 10M tokens for all | common budget |

Per-candidate conflicts and their resolutions are in section 9.

---

## 16. Budget and timeline (projection)

| phase | counted rollouts | wall (estimate) |
|---|---|---|
| P1 build + P2 acceptance | ≈ 80 (not counted) | 5–8 h (five drivers in parallel) |
| P3 shared seed baseline | 147 | 0.5–1 h |
| P4 five searches, ≤ 3 at once, ≤ 900 each | ≤ 4,500 (expected ≈ 3,000–3,800: trace2skill 270, others ≤ 900) | 15–25 h |
| P5 dev diagnostic | ≤ 285 (mostly cache hits) | ≤ 1 h |
| P6 scan | 0 | < 0.5 h |
| P7 final window | 2,016 | 6–7 h at 24 slots (eval 5: about 330 cells/h) |
| P8 analysis + P9 posts | 0 | 1 h |
| **total** | **≈ 5,500–7,000** | **≈ 30–45 h** after the build |

Optimizer spend:
- plain-chat arms: about 1–8M tokens each, roughly $5–$25 at proxy prices;
- `cape_improve`: ≤ $120 (`max_optimizer_usd`), with large cache-read volumes;
- `harnesslens`: many role calls plus Editor sessions.

All usage is recorded exactly.

## 17. Risks

| risk | mitigation |
|---|---|
| OOM restart from concurrent searches | rule R2 guard at 5 s; 24 slots; relaunch smaller; durable records on `/workspace` |
| an optimizer reads gold (base F14, F19, F20) | sandbox + deny rules + whole-AppWorld deny; A9; scans; label any breach |
| gateway throttling or refusals | `opt_llm.py` retries 429/5xx; neutral framing; G2 phrase fixes only in our prompt copies, logged |
| a driver bug ends a search (eval 5 evoskill) | lint-reject records carry all fields; resume from the method's own state |
| HarnessLens port drifts from the method | vendored prompts and gates; port deviations listed in the issue |
| the window stalls (eval 5: 10 h) | pid files, not `pgrep -f`; the heartbeat flags a window with no new cell for 15 min |
| hourly posts stop | the heartbeat checks post age per issue (section 8) |
| RITS drift between windows | one window for all six arms |
| cap-evolve eval errors burn iterations (#876) | stable roots, cached tasks; `--resume --max-iterations` to keep 6 scored |

---

## 18. Execution ledger (appended during the run)

> Appended during execution, newest last, under `flock(AW_STATE/ledger.lock)`, only by `status_doc.py`.
> Nothing below the marker is ever edited. The first entry (CP-0000) records the five issue numbers and
> the decisions. Content rules: section 12.2.

<!-- CHECKPOINTS BELOW THIS LINE -->

## CP-0000 · 2026-10-20T20:36Z · P0 decisions · decision

Execution of the eval REST plan starts. Decisions D1 to D9 (section 2) are taken as written; no open decision. Tracking issues (skillberry-ai/cap-evolve): harnesslens #897, miprov2 #898, trace2skill #899, gepa_full #900, cape_improve #901; each already carries its plan projection as the first post. Host: memcheck limit 32,768 MB, cpu_limit 8, oom.group 1, container_age 9.6 ks. B0 done: worktree eval-rest (from origin/eval5, pushed as origin/eval-rest), worktree cape-improve detached at 470f3fa, session deny rules written (R1.5, .claude/settings.local.json in both worktrees, git-excluded), memguard.py running (5 s, 90/85). Next: P1 build B1 to B4.

```json
{"cp": 0, "prev_cp": null, "prev_commit": "ffe35e9149aba2b68df193a8e67560b7b8144782", "utc": "2026-10-20T20:36:50Z", "kind": "decision", "phase": "P0", "done_through": "P0/decisions", "next": "P1/b1", "candidate": null, "counts": {}, "spend": {}, "artifacts": {"STATE/manifest.json": "58456826314cff9c47963871419539afdb51819a027c5f3f3de467998ae7313f"}, "code": "0b33760c3e12190eb1854ec0ca4604ac1392fc17", "open_decisions": [], "issues": {"harnesslens": 897, "miprov2": 898, "trace2skill": 899, "gepa_full": 900, "cape_improve": 901}}
```

## CP-0001 · 2026-10-20T20:38Z · P1 build B1-B4 · result

B1 to B4 done as eval 5 section 4, under /workspace/aw_rest. B1: AppWorld at 42b5bcf with git lfs and the extra-headers patch (git diff sha256 755de8b8...). B2: venv-aw, 123 packages, pydantic 2.12.5, gepa 0.1.4 (core is the eval-rest core: only the shared Rollout type; cap_improve gets its own venv-cape in B5). B3: data downloaded; split counts 90/57/168/417, scenario counts 30/19/56/139 and difficulty counts all match; publishing cache built (732 ids, 1,528 8-grams, 249 contacts). B4: root_opt with 148 task dirs (train + dev + _base_), 0 test-id hits; lint cache and reference dir built; root_full chmod 000. Code added: awrest.py (constants), memguard.py, build.py, post.py, autopost.py; status_doc.py switched to this ledger. Next: B5 per-candidate clones and venvs.

```json
{"cp": 1, "prev_cp": 0, "prev_commit": "b6442f3497e35f54953973f97fe9af0cd399462b", "utc": "2026-10-20T20:38:18Z", "kind": "result", "phase": "P1", "done_through": "P1/b4", "next": "P1/b5", "candidate": null, "counts": {}, "spend": {}, "artifacts": {"STATE/manifest.json": "9f4a017e248bf85af70443328e9c5872f6e3fda4859f1d3a055460439919acde"}, "code": "b6442f3497e35f54953973f97fe9af0cd399462b", "open_decisions": []}
```

## CP-0002 · 2026-10-20T20:38Z · P1 posted harnesslens · posted

Posted 'HarnessLens hourly status' on #897 (harnesslens): https://github.com/skillberry-ai/cap-evolve/issues/897#issuecomment-6300961668

```json
{"cp": 2, "prev_cp": 1, "prev_commit": "b922eb7ebac986f29904ae152b1d32fa49362943", "utc": "2026-10-20T20:38:40Z", "kind": "posted", "phase": "P1", "done_through": "P1/b4", "next": "P1/b5", "candidate": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "b922eb7ebac986f29904ae152b1d32fa49362943", "open_decisions": [], "post": "harnesslens/status_20261020T2038", "url": "https://github.com/skillberry-ai/cap-evolve/issues/897#issuecomment-6300961668"}
```

## CP-0003 · 2026-10-20T20:38Z · P1 posted miprov2 · posted

Posted 'MIPROv2 hourly status' on #898 (miprov2): https://github.com/skillberry-ai/cap-evolve/issues/898#issuecomment-6300962742

```json
{"cp": 3, "prev_cp": 2, "prev_commit": "a9d53c3ba0510067f36a8b6f802a1c94d39920e9", "utc": "2026-10-20T20:38:43Z", "kind": "posted", "phase": "P1", "done_through": "P1/b4", "next": "P1/b5", "candidate": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "b922eb7ebac986f29904ae152b1d32fa49362943", "open_decisions": [], "post": "miprov2/status_20261020T2038", "url": "https://github.com/skillberry-ai/cap-evolve/issues/898#issuecomment-6300962742"}
```

## CP-0004 · 2026-10-20T20:38Z · P1 posted trace2skill · posted

Posted 'Trace2Skill hourly status' on #899 (trace2skill): https://github.com/skillberry-ai/cap-evolve/issues/899#issuecomment-6300963657

```json
{"cp": 4, "prev_cp": 3, "prev_commit": "06c1b92ef503fea9e8bbf53cfa129f3819bc23d4", "utc": "2026-10-20T20:38:46Z", "kind": "posted", "phase": "P1", "done_through": "P1/b4", "next": "P1/b5", "candidate": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "b922eb7ebac986f29904ae152b1d32fa49362943", "open_decisions": [], "post": "trace2skill/status_20261020T2038", "url": "https://github.com/skillberry-ai/cap-evolve/issues/899#issuecomment-6300963657"}
```

## CP-0005 · 2026-10-20T20:38Z · P1 posted gepa_full · posted

Posted 'GEPA-Full hourly status' on #900 (gepa_full): https://github.com/skillberry-ai/cap-evolve/issues/900#issuecomment-6300964540

```json
{"cp": 5, "prev_cp": 4, "prev_commit": "8f789624cc4d9788429a317d3e5ba8148d9df454", "utc": "2026-10-20T20:38:49Z", "kind": "posted", "phase": "P1", "done_through": "P1/b4", "next": "P1/b5", "candidate": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "b922eb7ebac986f29904ae152b1d32fa49362943", "open_decisions": [], "post": "gepa_full/status_20261020T2038", "url": "https://github.com/skillberry-ai/cap-evolve/issues/900#issuecomment-6300964540"}
```

## CP-0006 · 2026-10-20T20:38Z · P1 posted cape_improve · posted

Posted 'Cap-Evolve-improve hourly status' on #901 (cape_improve): https://github.com/skillberry-ai/cap-evolve/issues/901#issuecomment-6300965337

```json
{"cp": 6, "prev_cp": 5, "prev_commit": "681c76f03774c50211de8b51139c886d1946ba63", "utc": "2026-10-20T20:38:52Z", "kind": "posted", "phase": "P1", "done_through": "P1/b4", "next": "P1/b5", "candidate": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "b922eb7ebac986f29904ae152b1d32fa49362943", "open_decisions": [], "post": "cape_improve/status_20261020T2038", "url": "https://github.com/skillberry-ai/cap-evolve/issues/901#issuecomment-6300965337"}
```

## CP-0007 · 2026-10-20T20:40Z · P1 build B5 · result

B5 done. Clones (read-only, chmod a-w) under AW_BUILD/clones at the plan pins: HarnessLens 369a5c8, Trace2Skill 3d0b52a, GEPA 8b0ce6c (v0.1.4), DSPy tag 3.4.1 (099982b). Venvs: venv-hl (pyyaml, httpx), venv-mipro (dspy[optuna]==3.4.1, optuna 5.0.0), venv-t2s (openai, tqdm, openpyxl, requests, diskcache), venv-cape (venv-aw's packages with cap-evolve core installed editable from the cape-improve worktree at 470f3fa; import resolves there, worktree git status clean). GEPA runs in venv-aw. Freeze hashes in manifest.json. Hourly autoposter started; first status posted on #897 to #901. Next: B6 common code.

```json
{"cp": 7, "prev_cp": 6, "prev_commit": "90153e2554dd700aa54442ca19903a4b007cde61", "utc": "2026-10-20T20:40:26Z", "kind": "result", "phase": "P1", "done_through": "P1/b5", "next": "P1/b6", "candidate": null, "counts": {}, "spend": {}, "artifacts": {"STATE/manifest.json": "fbeb7d2135f7fd133de188a49c3e35ea1d9894f424a105385a1f7c8ef0bea0ce"}, "code": "b922eb7ebac986f29904ae152b1d32fa49362943", "open_decisions": []}
```

## CP-0008 · 2026-10-20T20:50Z · P1 fastapi pin · repair

Repair: the fresh B2 resolve installed fastapi 0.156.2. AppWorld 42b5bcf calls fastapi Path(embed=...), which 0.156 rejects, so every world failed to start (caught by the first evaluator smoke test; nothing counted). Pinned fastapi==0.143.0 (the version of the base run, base A.1) in venv-aw and venv-cape and in build.py b2. After the pin, one dev episode ran end to end through the new common/evaluator.py: reward 1, 2 steps, 70 s, max prompt 4,179 tokens. A second identical request was served from the cache. Also: .env is read from the base worktree (the RITS key is never copied); common/evaluator.py, opt_llm.py (cache_write field, PAUSE wait, Sonnet 5.5 proxy prices) and sandbox.py (section 10 settings + claude_call usage logging) written. Next: rest of B6.

```json
{"cp": 8, "prev_cp": 7, "prev_commit": "ae20bffd7300fea7e5f782124cd6736fee97b016", "utc": "2026-10-20T20:50:46Z", "kind": "repair", "phase": "P1", "done_through": "P1/b6-evaluator", "next": "P1/b6", "candidate": null, "counts": {}, "spend": {}, "artifacts": {"STATE/manifest.json": "e1026a88766bba532defe449843a44b33f3c7394dbc9c39b3b82d6610fa516c6"}, "code": "b922eb7ebac986f29904ae152b1d32fa49362943", "open_decisions": []}
```

## CP-0009 · 2026-10-20T20:53Z · P1 build B6 common · result

B6 common code written: scripts/awrest.py (constants, global slot pool with flock, PAUSE wait, memstate), scripts/memguard.py (5 s, 90/85, MEMSTATE.json), common/evaluator.py (tree-hash cache keyed by (tree, task, seed), seed guard SeedRerunRefused after P3, sealed ids refused, hard cap B checked and reserved under flock before a batch, one global slot per episode, lint-reject records with every field), common/opt_llm.py, common/sandbox.py (section 10 settings, claude_call with usage logging), common/API.md (the contract for drivers), scripts/post.py, scripts/autopost.py. Eval 5's evaluator kept as common/evaluator5.py for reference only. Next: B7, five candidate drivers in parallel sub-agents (rule R4); in parallel the A9 check, windows, scan, analysis and resume code.

```json
{"cp": 9, "prev_cp": 8, "prev_commit": "71778190de84f60b6a61943a0aaf83df875aa7d9", "utc": "2026-10-20T20:53:04Z", "kind": "result", "phase": "P1", "done_through": "P1/b6-common", "next": "P1/b7", "candidate": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "71778190de84f60b6a61943a0aaf83df875aa7d9", "open_decisions": []}
```

## CP-0010 · 2026-10-20T20:56Z · P1 B7 drivers · phase_start

B7 started: five candidate drivers are being written in parallel sub-agents (rule R4), one per candidate, each in examples/appworld/<cand>/, each given section 4 verbatim, dev ids only, acceptance-namespace episodes only (not counted). memcheck before the spawn: 1.7% used, 32 sub-agents fit. In parallel the main session writes the common A-checks, the windows, the scan, the analysis and resume. Next: P2 common acceptance checks.

```json
{"cp": 10, "prev_cp": 9, "prev_commit": "b25b5b6bd8ae9a8fdc06e90ea3dc06b4105ec9d0", "utc": "2026-10-20T20:56:25Z", "kind": "phase_start", "phase": "P1", "done_through": "P1/b6", "next": "P1/b7", "candidate": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "b25b5b6bd8ae9a8fdc06e90ea3dc06b4105ec9d0", "open_decisions": []}
```

## CP-0011 · 2026-10-20T21:20Z · P2 acceptance common · result

Common acceptance checks, all pass (results in STATE/acceptance/; none counted): A1 gateway via opt_llm.py and claude CLI, no temperature, model aws/claude-sonnet-5-5. A2 RITS max_model_len 40,144, 48/48 concurrent 200 (0 x 429), 1 dev episode completed (15 steps), RITS key hits 0. A3+A5 REPL hardening blocks os/open/pathlib, root_opt has no test data, root_full locked; released solution scores 1, no-op 0, scoring deterministic, no trace or gold persisted. A4 seed first request byte-identical (23 messages), memory before My name is:, helpers and notes work, lint-rejected helper costs no rollout. A6 train order = load_task_ids (90), test id and test split refused. A7 final order (2,016 cells) reproducible from seed 2026102007, sha256 in manifest. A8 10 dev episodes max prompt 10,937 tokens; P_max 3,230, H_max 16,625, M_cap = 14,000 tokens (30,000 chars); 3 episodes with a max-size memory stay under 13.7K prompt tokens, tiktoken = vLLM. A11 guard period 5 s; PAUSE set within 5 s of crossing; no slot or optimizer call starts while paused; resumed below low mark; spawn check reads MEMSTATE. (A11 and memok first failed: memcheck's awk printed large byte counts in e-notation; fixed with printf %.0f, and the A11 test margins were widened over background swings.) A12 episode, chat and claude -p usage records carry every section 5.2 field; proxy 1M in + 1M out + 1M cache read = USD 12.20 (Sonnet 5.5 prices). A13 mini P3 on 4 dev ids, an identical candidate served from the cache with 0 counted, a fresh seed episode refused, slot pool peak = size with 3 callers. Remaining: A9 (sandbox), A10 (ledger/resume), A-<cand>.

```json
{"cp": 11, "prev_cp": 10, "prev_commit": "7f1e252637fe91da7a76e5857705d6cf47e56f9e", "utc": "2026-10-20T21:20:41Z", "kind": "result", "phase": "P2", "done_through": "P2/common", "next": "P2/a9-a10", "candidate": null, "counts": {}, "spend": {}, "artifacts": {"STATE/manifest.json": "d9bb008fc42a6f09bfb8573abe283118a519cb7c6b942f9be2cd0c60e65236de"}, "code": "b25b5b6bd8ae9a8fdc06e90ea3dc06b4105ec9d0", "open_decisions": []}
```
