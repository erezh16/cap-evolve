# AppWorld ablations of cap-evolve `main`: plan

Status: **PLAN**, written 2026-10-25. Nothing in sections 6 to 17 has run yet. The status ledger is a separate file,
**`docs/ABLATION_STATUS.md`**, appended during the run under an exclusive file lock (rule R3, section 4.3). This plan is
not edited during execution; findings, repairs and user decisions go into the ledger.

The plan measures what each part of cap-evolve contributes on AppWorld. It runs **five ablation arms** and **one
reference arm** (full cap-evolve, user decision 2026-10-25). All six start from the **same unmodified seed agent**.
The ablations are the five that the user listed; their design follows issue
[#908](https://github.com/skillberry-ai/cap-evolve/issues/908), with the deviations of section 16.

| arm id | name | what differs from the reference (the ablated factor) | issue |
|---|---|---|---|
| `abl_ref` | **Cap-evolve full (reference)** | nothing: cap-evolve `main` with every part on | [#930](https://github.com/skillberry-ai/cap-evolve/issues/930) |
| `abl_cc` | **Claude code** | no cap-evolve at all: plain Claude Code, one session, a 3-line prompt, the same eval tool, feedback and budget | [#931](https://github.com/skillberry-ai/cap-evolve/issues/931) |
| `abl_prompt` | **Cap evolve prompt only** | edit surface = the system prompt only (`tools/` sealed) | [#932](https://github.com/skillberry-ai/cap-evolve/issues/932) |
| `abl_tools` | **Cap evolve tools only** | edit surface = the tools only (`policy/` sealed) | [#933](https://github.com/skillberry-ai/cap-evolve/issues/933) |
| `abl_notrace` | **Cap evolve no traces** | the optimizer gets no conversation traces: reward plus evaluation feedback only | [#934](https://github.com/skillberry-ai/cap-evolve/issues/934) |
| `abl_tracescore` | **Cap evolve traces and score only** | the optimizer gets the full traces plus the reward only: no evaluation feedback | [#935](https://github.com/skillberry-ai/cap-evolve/issues/935) |

Issues are on **`skillberry-ai/cap-evolve`** (remote `origin` of this repo). Code and ledger go to the fork
**`erezh16/cap-evolve`** (remote `fork`). Never push an evaluation branch to `origin` (section 6.1).

**The executing agent must read these in full before doing anything else** (rule R5):
- `docs/CONTAINER_AGENT.md` ("the container guide"): sub-agent isolation and memory in this pod. Its procedure is
  mandatory (rule R2).
- `docs/EVAL_APPWORLD_REST.md` ("REST"): **its core rules apply here, with the six arms of this plan as the
  competitors** in place of REST's five. Those are rules R1 to R5 (section 4), Q1 to Q4 (section 5), the
  shared-evaluator, cache and seed-reuse machinery (section 7), sandbox isolation (section 10), the final window
  (section 14) and acceptance A1 to A13 (section 13).
- `docs/EVAL_APPWORLD_CE2.md` and `docs/EVAL_APPWORLD_CE3.md`: the most recent siblings (2026-10-22 to 10-24, same pod
  type, same models). CE3 ran cap-evolve with exactly this plan's base settings (K = 0.2 and the Improvement 2
  instructions, which are now on `main`, PR #914). Their code on branch **`fork/eval-ce3`** is the starting point of this
  run's code. Read their ledgers (`docs/EVAL_APPWORLD_CE2_STATUS.md` and `docs/EVAL_APPWORLD_CE3_STATUS.md` on
  `fork/eval-ce3`), every entry of kind `error`, `repair`, `decision` or `abort` (Appendix A summarizes them).
- `docs/EVAL_SMOKE_TEST.md` (Appendix A, findings F1 to F20) and `docs/EVAL_SMOKE_TEST_FIX.md`: why isolation is built
  the way it is.
- `examples/appworld/README.md`: the benchmark harness.
- Issue #908: the ablation design.

Where a source and this plan disagree on a fact, stop, record it in the ledger and ask the user (rule R5).

Deliverables of the execution:
- one results comment per arm on that arm's issue (section 15);
- the six frozen artifacts;
- the ledger;
- a progress post on every issue at least once an hour (section 12).

---

## 0. Scope and the non-negotiable rules at a glance

| item | this evaluation |
|---|---|
| code under test | cap-evolve **`main` at `75b3bcd`** (`75b3bcdd0fc7292f9717f2b6dcb720f147452df9`): V3 hill-climb (#889), optimizer instructions "Improvement 2" and default `gate_k_se: 0.2` (#914). Core and skills are not modified for any arm (decision D4) |
| base configuration (every cap-evolve arm) | stock hill-climb `--focus all`, deterministic orchestration, paired gate with **`gate_k_se: 0.2`** written explicitly, the **current `templates/project/optimizer/INSTRUCTIONS.md`** of `main` (sha256 `84de4f00…`) plus one AppWorld facts section (9.4), 6 scored iterations (user guideline 10) |
| **the seed** | AppWorld's official simplified ReAct code agent, with the stock prompt and no helpers, notes or memory (`examples/appworld/seed_capability/`). It is run **once** on train ∪ dev (147 tasks, 1 trial, trial seed 100) in phase P3, and every arm reads those records as its baseline (rule Q4). The seed is also one arm of the final window |
| agent under test, every arm | `openai/gpt-oss-120b-a100` on RITS, `hosted_vllm/` route, reasoning effort `medium`, temperature 0 (section 7.1) |
| optimizer, every arm and role | `aws/claude-sonnet-5-5` through the gateway in `~/.claude/settings.json`, for the main loop **and** every sub-agent (section 7.2) |
| benchmark | AppWorld at `42b5bcf`, official splits only. Search: train = val = train ∪ dev (147). Results: `test_normal` (168). `test_challenge` is not used |
| trials | search: 1 trial per task, trial seed 100. Final window: 2 trials per task, trial seeds 5000 + k. 1 search seed per arm (rule Q1) |
| budget per arm | **B = 882 counted (fresh) search rollouts** (6 × 147). The cap-evolve arms also have `max_metric_calls: 1029` (147 cached baseline + 6 × 147) and **no money or token cap**, as in CE3. Spend is recorded exactly |
| final window | `test_normal` 168 × **7 arms** (seed + 6 champions) × 2 trials = **2,352 episodes**, in **one** interleaved, shuffled order |
| metrics | reward, cost, tokens and latency, at **both** the search and the test phase, with the same definitions for every arm (rule Q2) |
| isolation | no agent of any kind, executing or optimizing, sees gold, ground truth, solutions, task generators, app source, sealed splits, test outcomes, another arm's run, or any earlier evaluation's results (rule R1, section 11) |
| memory | sampled every **5 s** by a guard service. At ≥ 90% of the container limit nothing new starts (no sub-agent, episode or optimizer session) until it is back below 85% (rule R2) |
| resumability | `docs/ABLATION_STATUS.md` is the ledger, appended under `flock` and pushed after every entry. One command resumes. Only the step in flight may be lost (rule R3) |
| parallelism | up to **3 searches at once** on one shared pool of episode slots, and parallel sub-agents for the build and checks, all within rule R2 (rule R4) |

---

## 1. What was read and verified (2026-10-25)

### 1.1 Sources read
- All the documents listed at the top, `CLAUDE.md` and issue #908.
- The CE2 and CE3 ledgers and code on `fork/eval-ce3`.
- On `main`: `core/cap_evolve/{cli,harness,optimizer_config,integrity,gate,specfile}.py`,
  `skills/optimizers/registry.yaml`, `templates/project/{capevolve.yaml,optimizer/INSTRUCTIONS.md}`.
- The unmerged branch `origin/ablation-lead/ablation-switches`.

Only read-only probes ran, plus one trial merge in a throwaway worktree that was then deleted.

### 1.2 The version under test
- `main` = `75b3bcd`. `git diff 3db96a0 75b3bcd -- core skills` changes only the `gate_k_se` / `--k-se` default, from
  1.0 to 0.2. That is the cli.py fallback (`core/cap_evolve/cli.py:982`), the hill-climb, gepa, skillopt,
  agent-optimize and gate scripts, and the docs that state the default. So `main` is CE3's code with CE3's K as its
  default.
- `templates/project/optimizer/INSTRUCTIONS.md` on `main` is **byte-identical** to the CE2/CE3 pin `3db96a0`
  (sha256 `84de4f00a5254c47f0627a9e753129375ce12d20ecdcbeeb0e266d6106de2fce`). Its headings are
  `# Optimize the capability — ship the edit with the largest expected objective score gain`, `## PREPARATION:`,
  `### 1. Understand the objective score`, `## Strategies for constructing edits:` (items 1 to 6). Its placeholders
  are `TARGET_READER`, `FOCUS_SUMMARY`, `EMPTY_SEED`, `FAILURES`, `PASSING`, `BENCH_REPO`, `PARALLEL_NOTE`,
  `CAP_BRIEF`, `ALGO_BRIEF`.
- **Watch out:** `examples/appworld/capevolve.yaml` still says `gate_k_se: 1.0`, and `setup_project.sh` writes
  "k = 1.0" into `PROJECT.md`. `_find_skills_dir()` prefers `~/.claude/skills`, which exists on this host. So K and the
  skills dir are set explicitly and verified (9.6), as in REST §9.5 and CE2 §9.

### 1.3 Where the ablation settings are (user guideline 2)

| ablation | built-in setting on `main` | what this plan uses |
|---|---|---|
| Claude code | none. `optimizer_skill: claude-code` is cap-evolve's normal optimizer, run inside the loop with the instructions, guidance, history and gate. There is no "plain Claude Code" mode | its own driver (10.2), as in #908 NAIVE-CC: the `claude` CLI, one session, no cap-evolve code |
| prompt only | `capabilities: [system-prompt]` selects the capability brief, guidance and validation, but **does not block writes** (`ci/benchmarks/lib/run_suite.sh:303-308`). The hard block is `protected_paths:` (`harness.parse_protected_paths`, `integrity.py`): the files are hashed, made read-only, and any change makes the step **indecisive before any rollout** (`harness.py:3629`) | `capabilities: [system-prompt]` + `protected_paths: [default, "tools/*", "memory/*"]` (10.3) |
| tools only | the same keys | `capabilities: [tools]` + `protected_paths: [default, "policy/*", "memory/*"]` + an anti-smuggling lint (10.4) |
| no traces | `optimizer.ablation.history: false` / `CAPEVOLVE_HISTORY=0` hides only the cross-iteration history. `./trajectories/` is always copied (`harness.py:2996`). There is **no switch** for removing traces | an adapter-side feedback filter, `AW_ABL_FEEDBACK=eval_only` (10.5) |
| traces and score only | none. The proposer sees whatever the adapter's `score()` returns (tier F1: failed requirement texts and more, `examples/appworld/adapters/adapter.py:234-265`) | the same filter, `AW_ABL_FEEDBACK=trace_score` (10.6) |

The purpose-built switches `abl_capability` (P/TD/TC), `abl_info` (reward/eval/fail), `abl_history` and `abl_gate` exist only on the **unmerged** branch `origin/ablation-lead/ablation-switches` (`8079e39`). It merges cleanly onto `main` and its 58 tests pass on the merge. But its paths are hard-coded to the tau2 layout (`policy/policy.md`, `tools/tools.py`, `tau2_reward_info`), so using it would mean changing the core of the version under test. **User decision 2026-10-25 (D4): core stays exactly `main`.** The ablations are made from `main`'s own keys plus a filter in the AppWorld adapter.

The adapter filter works at the one place every proposer-visible file comes from. cap-evolve builds every file it shows the
optimizer from the adapter's `Rollout` and `Score`: the rollout JSONs in `./trajectories/`, the `{{FAILURES}}` block,
`baseline.json`, `state.json`, the LEDGER, the JOURNAL and the rejected reasons. The full records live only in the
evaluator's state (`AW_STATE`, denied to the optimizer). Filtering in the adapter therefore filters all of these, not only
the trajectories (#908 §5, ablation 3).

### 1.4 Facts about this host (probed 2026-10-25)
- `memcheck`: `limit_MB=32768`, `cpu_limit=8`, `swap_max=0`, `oom_kills_whole_container=1` (an OOM restarts the **whole
  pod**), used 3%. `nproc` is not the CPU limit.
- `/workspace`: 20 GB, 18 GB free, survives restarts. `/tmp`: 590 GB, 180 GB free, an `emptyDir` that is lost on a pod
  restart. Durable state lives on `/workspace`.
- **No earlier build exists**: there is no `/workspace/aw_rest`, `aw_ce2` or `aw_ce3`. AppWorld, the data roots, the venvs
  and the seed baseline are built fresh (B1 to B4, P3).
- `unshare -rm` fails (`ENOSYS`), so the namespace wrapper `examples/appworld/sandbox/claude` cannot run. Claude Code's
  sandbox runs through `devagent-bwrap` (managed setting `/etc/claude-code/managed-settings.json` =
  `{"sandbox":{"bwrapPath":"/usr/local/bin/devagent-bwrap"}}`). Claude Code CLI 2.1.270. `uv`, `gh` (logged in as
  `erezh16`) and python3 3.11 are present.
- The repo's `.env` (`/workspace/worktrees/base/.env`) holds `RITS_URL` and `RITS_API_KET` (the typo is real and is
  kept). Its values are never printed, copied or committed.

### 1.5 Model access (probed 2026-10-25; how-to in section 7)
- RITS: `GET $RITS_URL/gpt-oss-120b-a100/v1/models` → 200, model `openai/gpt-oss-120b-a100`, `max_model_len` 40,144. A
  chat request with header `RITS_API_KEY: <key>`, `temperature 0` and `reasoning_effort medium` → 200.
- Optimizer: `claude -p … --model aws/claude-sonnet-5-5 --output-format json` → a normal result. `modelUsage` shows only
  `aws/claude-sonnet-5-5`. A harmless stderr line `[claude-code:unrecognized_model]` comes from the session-title call.

---

## 2. Decisions

| id | decision | source |
|---|---|---|
| D1 | optimizer `aws/claude-sonnet-5-5` for every arm and every role (main loop, sub-agents, helper calls) | user guideline 8 |
| D2 | agent `openai/gpt-oss-120b-a100` on RITS, the base plan §5.1 config | user guideline 5 |
| D3 | 1 search trial, 2 final trials, 1 search seed per arm | REST Q1 |
| D4 | code under test: cap-evolve `main` `75b3bcd`, **core and skills unmodified**. Ablations are made from `main`'s keys and an AppWorld-adapter filter, **not** from the `abl_*` branch | user decision 2026-10-25 |
| D5 | a **fresh reference arm** `abl_ref` (full cap-evolve), searched under this plan and scored in the same window | user decision 2026-10-25 |
| D6 | "Claude code" = **plain Claude Code** (#908 NAIVE-CC); #908's CC-CAPEVOLVE is not run | user decision 2026-10-25 |
| D7 | base config of every cap-evolve arm: `gate_k_se: 0.2` explicit, the current `main` INSTRUCTIONS template | user guideline 10 |
| D8 | **one shared seed run** (P3), reused by every arm through the evaluator cache | REST D5 / Q4 |
| D9 | isolation: Claude Code's sandbox through the PATH shim, with `--setting-sources ''` forced, for every optimizer session (section 11) | user guideline 9; CE2 D8 |
| D10 | memory guard 90% pause / 85% resume, sampled every 5 s, gating sub-agents, episodes and optimizer sessions | user guideline 6 |
| D11 | ledger = `docs/ABLATION_STATUS.md` on branch `eval-abl` (fork), one issue per arm, a post on every issue at least hourly | user guidelines 4, 7 |
| D12 | no money or token cap on any arm (CE3 §2); `optimizer_max_turns: 200` per cap-evolve session; spend recorded exactly | CE3 decision 2026-10-24 (CE2-0021: a USD cap truncated sessions unevenly) |
| D13 | `memory/*` is sealed (`protected_paths`) in **every** cap-evolve arm, the reference included; `memory/` is not part of these runs | consistency: otherwise a tools-only arm could put prompt text in `memory/playbook.md` |

If the executing agent meets a question these decisions do not answer, it asks the user (one `AskUserQuestion`, with the
recommended option first) and records the answer as a `decision` entry. It never decides silently where a choice could
favour one arm.

---

## 3. Arms and surfaces

| arm | optimizer | editable surface (enforced) | proposer feedback | gate |
|---|---|---|---|---|
| `seed` | none | none | n/a | n/a |
| `abl_ref` | cap-evolve hill-climb + claude-code | `policy/instructions.txt`, `tools/helpers.py`, `tools/api_notes.json` | full F1 tier: traces + reward + evaluation feedback | paired, K = 0.2 |
| `abl_cc` | plain Claude Code, one session | the same three files | the same F1 content as `abl_ref`, returned by its eval tool | none (Claude decides) |
| `abl_prompt` | as `abl_ref` | `policy/instructions.txt` only | as `abl_ref` | as `abl_ref` |
| `abl_tools` | as `abl_ref` | `tools/helpers.py`, `tools/api_notes.json` only | as `abl_ref` | as `abl_ref` |
| `abl_notrace` | as `abl_ref` | as `abl_ref` | reward + evaluation feedback, **no conversation trace** | as `abl_ref` |
| `abl_tracescore` | as `abl_ref` | as `abl_ref` | full conversation trace + **reward only** | as `abl_ref` |

All seven arms use the same harness, model client, decoding parameters, step cap, token cap and evaluator. Every arm's
agent runs through the one unmodified `adapters/aw_agent.py` worker. Only each arm's own surface files differ. An arm that
accepts nothing is frozen as the seed and labelled **inert**. "F1 tier" means: reward 0/1, the pass fraction, the
**texts** of failed requirements, the collateral-damage flag, whether `complete_task` was called, steps, API-error count
and termination. It never includes a gold value.

---

## 4. MANDATORY EXECUTION RULES (read before any action; they override convenience)

> **These five rules are not optional.** A step that would break one of them is not taken: the agent stops, records an
> `abort` or `decision` entry, and asks the user. **Every sub-agent the executing agent spawns receives the text of this
> section verbatim in its prompt.**

### 4.1 Rule R1: no agent ever sees what it must not see (user guideline 9)

**Forbidden content (the "sealed set"):**
- `ground_truth/` of any task, `answer.json`, `private_data.json`, `evaluation.py`, `solution.py`,
  `compiled_solution.py`, the evaluator's failure `trace`, AppWorld's native per-episode output dirs;
- AppWorld's task generators (`appworld/generate/`, F19) and app implementation source (`src/appworld/apps/`, F20);
- all `test_normal` and `test_challenge` task data and ids, `root_full`, and every final-window record until the analysis
  step reads counts from it;
- **another arm's run**: no arm's optimizer sees another arm's project root, run dir, workdir, usage log or artifact;
- **earlier evaluations' results** (REST, CE2, CE3, #804): their plans, ledgers, pushed state, champions and issues.
  Optimizers never see them. The executing agent may read the plans, ledgers and code, as this plan requires;
- `.env`, the gateway token, other sessions' transcripts (`~/.claude/projects/*`, `/tmp/claude-*/*`), `~/.config/gh`.

**Who may touch it:** only named trusted scripts, running as separate unsandboxed processes: the episode worker
(`aw_agent.py`), the window (`window.py`), the build steps, the lint-cache builder, the `abl_cc` eval daemon (10.2) and
the isolation scan. No LLM, sub-agent or person reads it.

**How it is enforced (all layers apply; none is enough alone):**
1. **Data roots.** Search-time episodes use `root_opt` (train + dev only; a grep of every test id finds 0 hits).
   `root_full` stays `chmod 000` from the end of B4 until P7 starts, and again after P7.
2. **Gold-free feedback.** No arm's optimizer gets more than the F1 tier (section 3). Two arms get less (10.5, 10.6).
3. **Optimizer sandbox** (section 11): every optimizer session of every arm, `abl_cc` included, runs under Claude Code's
   sandbox. The settings are `failIfUnavailable: true`, `allowUnsandboxedCommands: false`, `filesystem.denyRead` plus
   `permissions.deny Read(...)`/`Edit(...)` on the deny list, a network restricted to the gateway host, no
   `WebFetch`/`WebSearch`, and user settings **not** loaded (`--setting-sources ''`). **Check A9 must pass for each
   arm's exact launch configuration before any counted rollout.**
4. **Executing agent and its sub-agents.** The orchestrating sessions never open a sealed-set file with any tool
   (`Read`, `Grep`, `Glob`, `cat`, `head`, `python -c open(...)`, …). They never print a test record and never read a test
   trajectory. Launch the session with `--settings /workspace/aw_abl/launch/exec-settings.json` (deny rules for the
   sealed set) and copy the same rules into `/workspace/worktrees/eval-abl/.claude/settings.local.json` (git-excluded) in
   B0. Spawn sub-agents only with prompts that repeat this section. Give a code-writing sub-agent its own worktree
   (`isolation: "worktree"`), and have it test against **dev ids only**, with a mock or the shared evaluator, never by
   reading task files. Code that must handle task data is **run, never read**.
5. **Detection.** After each search (P4) and again before the window (P6), the isolation scan greps every location below
   for the patterns below:
   - locations: every optimizer transcript (sub-agents included), workdir, eval-daemon spool, frozen artifact, **and the
     orchestrating sessions' own transcripts**;
   - patterns: every test id, `test_normal`, `test_challenge`, `root_full`, `ground_truth`, `answer.json`,
     `compiled_solution`, `solution.py`, `generate/tasks`, `src/appworld/apps`, the other arms' run roots, and
     `aw_rest`/`aw_ce2`/`aw_ce3`.

   Read the **tool calls** of each hit, not only the text (`docs/VERIFICATION_SCAN.md` §A1). Publish counts only. A real
   hit labels the arm "isolation breach" in every result. Hits from sessions outside this run are counted and disclosed
   as out of scope (CE2-0087).
6. **Nothing is ever published** that contains a task id, task or supervisor text, a train/dev 8-gram, a trajectory, a
   secret or a per-task test outcome (AppWorld redistribution rule; content filter, 13.2).

### 4.2 Rule R2: memory is watched every 5 s, and nothing new starts above 90% (user guideline 6)

Follow `docs/CONTAINER_AGENT.md` §2 in full. Save its `memcheck` script as `~/bin/memcheck`. In addition:
- **Guard service** `memguard.py` (CE2's, with `AW_STATE=/workspace/aw_abl/state`). It is a `nohup` process started in B0
  **before anything heavy**, and relaunched by `resume.py` and by the heartbeat whenever its `MEMSTATE.json` is older than
  30 s. Every **5 s** it reads this container's cgroup: `used = anon + shmem` of `memory.stat` over `memory.max` (or
  `memory.high` if lower). It atomically writes `AW_STATE/MEMSTATE.json` = `{t, used_pct, used_MB, limit_MB, state,
  peak_pct}`.
- **Watermarks:** at `used_pct ≥ 90` it sets `state = PAUSED` and creates `AW_STATE/PAUSE`. It clears both only when
  `used_pct < 85`. One line per transition, plus one sample line per minute, goes to `AW_STATE/progress/memguard.log`.
- **`~/bin/memok-abl`** (a copy of CE2's `memok`, reading `/workspace/aw_abl/state/MEMSTATE.json`) exits 0 only if
  `state == OK` and the file is under 30 s old.
- **Who honours it:**
  - the evaluator and the window: no new episode starts while PAUSED; in-flight episodes finish;
  - the claude shim and the `abl_cc` driver: no new optimizer session starts while PAUSED;
  - **the executing agent, before every sub-agent spawn and every process launch:** run `memok-abl` and `memcheck`.
    **Spawn nothing** if the state is PAUSED, if `MEMSTATE.json` is older than 30 s (restart the guard first), or if
    `subagents_that_fit` is 0. Wait and re-check every 30 s. Sub-agents are memory consumers: none is started above 90%
    until use is back below 85%.
- **Escalation:** if PAUSED for more than 10 minutes, shrink what was started, most recent first:
  1. lower the global episode slots by 25%;
  2. after 20 minutes, ask the most recently launched search to stop at its next iteration boundary (it resumes later
     with `--resume`).

  Record a `decision` entry each time. Every arm must still end with 6 scored iterations (or, for `abl_cc`, its full
  session).
- **Sizing:** size pools from `cpu_limit` (8) and measured memory, never from `nproc`. An episode worker is about 0.5 GB,
  and a claude-code optimizer session with sub-agents is budgeted at 2 GB.
  - **24 global slots** (REST peak 47.8% with three searches at 24; eval 5 OOM-restarted at 48). Raise by 4 only after
    30 minutes with peak `used_pct` < 65%, and never above 32.
  - At most 3 optimizer sessions at once.
- **After a restart** (`container_age_s` shorter than the session; counters reset by `oom.group=1`): treat the work
  launched just before as the cause. Resume (13.4) and relaunch **smaller**: 25% fewer slots and one search fewer.

### 4.3 Rule R3: the status ledger; the run can resume at any time (user guideline 7)

- The ledger is **`docs/ABLATION_STATUS.md`** on branch `eval-abl`. It is append-only. Every append happens under
  **`flock(/workspace/aw_abl/state/ledger.lock)`**, through the one writer `status_doc.py` (CE2's, with
  `AW_LEDGER_NAME=ABLATION_STATUS.md`, `AW_LEDGER_ID=ABL`, `AW_BRANCH=eval-abl`). No driver, sub-agent or session edits the
  file directly, so concurrent updates never overwrite each other.
- Every append:
  1. write the pushed state files atomically;
  2. append the entry and `fsync`;
  3. run the content filter;
  4. `git commit -- <pathspec>`;
  5. `git push fork HEAD:eval-abl` (explicit refspec, never `--force`; CE2-0001).

  A failed push keeps the commit locally and is retried by the heartbeat. A crash therefore loses at most the entries
  since the last push, and the durable local state on `/workspace` keeps them.
- Resolution:
  - an entry at every phase boundary, build step, acceptance check, iteration verdict, `abl_cc` evaluation, freeze,
    scan, error and resume;
  - coalesced results at most every 5 minutes;
  - a heartbeat after 25 silent minutes.

  The only acceptable loss on a crash is the step in flight (one optimizer session or one batch of episodes), which is
  redone on resume.
- Durable state lives on `/workspace/aw_abl` (never `/tmp`, which a pod restart wipes): records, caches, run dirs, pid
  files and the posting keys.
- One command, `resume.py`, continues from the last entry (13.4).

### 4.4 Rule R4: parallelize as much as rule R2 allows

- **Build and checks:** independent steps run in parallel sub-agents, each given rule R1's text and each subject to the
  R2 spawn check. Examples: the per-arm instruction variants, the `abl_cc` driver and daemon, A9 for each arm.
- **Search:** up to **3 searches at once**, on one global pool of episode slots, so total agent concurrency never
  exceeds the pool. Waves: `abl_ref`, `abl_prompt`, `abl_tools` first (launched within the same minute), then `abl_notrace`,
  `abl_tracescore`, `abl_cc`. Any slot that frees up starts the next arm.
- **Watchers:** detached `nohup` processes do the long work. At most one watcher sub-agent per running search, plus one
  for the guard and posting. Nothing depends on a sub-agent staying alive.
- **Never nest:** the executing agent's sub-agents must not spawn sub-agents (container guide §2.5). The optimizers' own
  sub-agents run inside their sandboxed process and count against memory.

### 4.5 Rule R5: quality over speed

Read every source named here before writing code. Check every number against its source. Prefer a correct pause to a
fast wrong step. Before any counted rollout, every acceptance check of section 14 must pass, with its result in the
ledger. When something is unclear or a result looks surprising, stop and investigate (and ask the user if needed) before
continuing. Report failures and deviations plainly in the ledger and on the issues.

---

## 5. Quality rules for valid results

### 5.1 Rule Q1: the same number of trials everywhere

| level | value | applies to |
|---|---|---|
| search seeds per arm | **1** | all six arms |
| trials per task during search | **1**, trial seed **100** | every search episode of every arm, and the shared seed run |
| trials per task in the final window | **2**, trial seeds **5000 + k**, k ∈ {0, 1} | all 7 arms |
| dev diagnostic (P5) | **1**, trial seed 100 | all 6 champions (cache hits: dev ⊂ val) |

**One (candidate tree, task, trial seed, phase) is run at most once.** The evaluator caches every record under that key,
and a repeat returns the cached record, uncounted. An infrastructure failure is not cached and is retried once with the
same seed.

### 5.2 Rule Q2: the same metrics for every arm, at search and at test

Shared code collects all metrics: the evaluator, the shim's usage logger, the `abl_cc` driver's usage logger (the same
function), the window and `analyze.py`. **Every** arm reports **every** row.

| metric | search phase (train = val = 147) | test phase (final window) | source |
|---|---|---|---|
| **reward** | per iteration (cap-evolve arms): val, paired Δ̄, SE, K·SE, verdict. Per evaluation (`abl_cc`): mean val. The champion's search score (labelled "fit metric, train = val, selection-biased"). The seed baseline. TGC and pass fraction of counted rollouts | TGC, SGC, by difficulty (Easy 57, Medium 48, Hard 63); Δ vs `abl_ref` and Δ vs seed with 95% CI; pass fraction as a secondary | evaluator records, cap-evolve `events.jsonl`, window records |
| **tokens, agent** | prompt and completion tokens per episode (mean, p50, p90, total); max prompt tokens; steps; step-cap, token-cap and context-exceeded hits | the same | `aw_agent.py` record fields |
| **tokens, optimizer** | input, output, cache-read and cache-write tokens; sessions; per iteration; by model and role (main loop vs sub-agents), from the CLI's **`modelUsage`** (CE2: the top-level `usage` misses sub-agents) | n/a | `optimizer_usage.jsonl` per arm |
| **cost** | optimizer USD **proxy** at Claude Sonnet 5.5 list price: $2.00 / MTok input, $10.00 output, $0.20 cache read, $2.50 5-min cache write. Also the CLI-reported `total_cost_usd`, labelled. Agent: RITS is unpriced, so "n/a (unpriced)", **never $0**; agent tokens stand in. #908's gpt-oss proxy ($0.15 / $0.60 per MTok) is reported as a labelled secondary | agent: "n/a (unpriced)" plus tokens | shim, CLI JSON |
| **latency** | per-episode wall seconds (mean, p50, p90); per optimizer session seconds and total; per-iteration wall time; search wall time; time to champion | per-episode wall seconds; window wall time | `wall_seconds`, shim timing, ledger timestamps |
| **budget** | counted rollouts (of B = 882); metric calls; cache hits; lint rejects; surface-voided steps; infra retries; iterations scored vs consumed; optimizer turn-cap hits per session (#908 §6) | infra retries, missing cells | evaluator, cap-evolve state, CLI JSON |
| **stability** | n/a | share of tasks whose 2 trials agree, per arm | window records |
| **artifact** | per champion: chars and tokens of `instructions.txt`; helper count and lines; note count and chars; edit types used (add/remove/composite helper, docstring, code, note, prompt) | the same artifact | freeze |

Spend is reported **per provider**: RITS (agent: tokens, unpriced) and the gateway (optimizer: tokens, proxy USD, CLI
USD). `CLAUDE.md`'s provider order (RITS → ETE-INT → ETE) governs `benchmarks.yml` CI runs. This run uses no CI: the agent
runs on RITS and the optimizer on the `~/.claude/settings.json` gateway.

### 5.3 Rule Q3: the same models for every arm

- **Optimizer:** `aws/claude-sonnet-5-5` for every optimizer call of every arm, sub-agents and helper calls included
  (section 7.2). After each search the scan counts every `modelUsage` key: any other model id is an `error` entry.
- **Agent under test:** section 7.1, unchanged for every arm. No arm changes the agent model, its decoding or its caps.

### 5.4 Rule Q4: one seed, run once, and arms that differ only in their factor

- **P3** runs `seed_capability` (tree hash `SEED_HASH`, recorded in `manifest.json`; expected
  `85a0da9cec2206a7…` as in REST and CE2, recompute it) on the 147 train ∪ dev tasks, 1 trial, seed 100. Those 147 records
  are every arm's baseline. They are counted once, as "shared seed baseline: 147", and charged to no arm. After P3 the
  evaluator refuses a fresh `SEED_HASH` episode in search (`SeedRerunRefused`).
- **A-ABL-SAME** (14): the five cap-evolve arms' rendered `capevolve.yaml`, rendered `INSTRUCTIONS.md`, launcher
  environment and sandbox settings are compared with `abl_ref`'s. They may differ **only** in the rows of the table below
  (plus run dir, run ts, issue number, the arm's own deny entry, and the arm's other-arm deny list):

  | arm | the only allowed differences from `abl_ref` |
  |---|---|
  | `abl_prompt` | `capabilities`, `protected_paths`, the AppWorld facts section |
  | `abl_tools` | `capabilities`, `protected_paths`, the AppWorld facts section, `AW_ABL_TOOLS_LINT=1` |
  | `abl_notrace` | `AW_ABL_FEEDBACK`, the AppWorld facts section |
  | `abl_tracescore` | `AW_ABL_FEEDBACK`, the AppWorld facts section |

  The stored `diff` must show nothing else.

---

## 6. Environment and build

### 6.1 Layout

```
/workspace/worktrees/eval-abl/        # NEW worktree, branch eval-abl from fork/eval-ce3; every commit and push goes here (remote fork)
  docs/ABLATIONS.md                   # this plan (copied from the ablations branch, never edited after)
  docs/ABLATION_STATUS.md             # THE STATUS LEDGER (rule R3)
  docs/ABLATION_STATUS_STATE/         # pushed, publishable state (manifest, per-arm progress, artifacts, final counts)
  examples/appworld/                  # CE3's harness + examples/appworld/abl/ (this run's drivers)
/workspace/worktrees/abl-main/        # NEW worktree, DETACHED at 75b3bcd: the code under test. Read-only: never commit here
/workspace/aw_abl/                    # AW_HOME, durable, outside git, never pushed
  launch/exec-settings.json           # the executing session's deny rules (R1.4)
  state/                              # AW_STATE: ledger.lock, MEMSTATE.json, PAUSE, pid files, cache/, slots/, per-arm state, logs
  build/                              # AW_BUILD: appworld/, venvs/{venv-aw,venv-abl,venv-lint}, root_full/ (mode 000), root_opt/, reference/
  arms/<arm>/                         # each arm's project root (.capevolve/project + run dir), or abl_cc's session dir
/tmp/aw_abl/                          # AW_SCRATCH: AppWorld native outputs (deleted after each record)
```

- Remotes in this repo: `origin` = `skillberry-ai/cap-evolve` (issues only), `fork` = `erezh16/cap-evolve` (branches).
  Create `eval-abl` with `git worktree add --no-track -b eval-abl /workspace/worktrees/eval-abl fork/eval-ce3`. Then push
  it with `git push -u fork HEAD:eval-abl`, so its upstream is `fork/eval-abl` and never `eval-ce3` (CE2-0001).
- Do not commit to `main` or to `abl-main`. Do not touch `/workspace/worktrees/base` except to copy this plan from it.
  Never use bare `git stash`.

### 6.2 Build steps (each idempotent, each one ledger entry)

- **B0.**
  1. Create the worktree (6.1); copy this plan in; create `docs/ABLATION_STATUS.md` with a header and the marker
     `<!-- CHECKPOINTS BELOW THIS LINE -->`; commit; push.
  2. `git -C /workspace/worktrees/base worktree add --detach /workspace/worktrees/abl-main 75b3bcd`.
  3. Write the executing-session deny rules (R1.4).
  4. Install `~/bin/memcheck` and `~/bin/memok-abl`.
  5. Start `memguard.py` (R2) and verify a fresh `MEMSTATE.json` within 10 s.

  First ledger entry ABL-0000 records: decisions D1 to D13, the six issue numbers, the host facts, the executing session
  id (`AW_SESSION_IDS`).
- **B1. Configuration profile.** `scripts/awabl.py` (profile `abl`), on top of CE3's `awce3.py`:
  - `CANDIDATES = ("abl_ref", "abl_cc", "abl_prompt", "abl_tools", "abl_notrace", "abl_tracescore")`, `ARMS` = seed + those;
  - `ISSUES`, `METHOD_NAMES` (section 10 headings), `CAPE_COMMIT = 75b3bcd…`, `CAPE_TREE = /workspace/worktrees/abl-main`;
  - `BUDGET_ROLLOUTS = 882`; `BUDGET_OPT_TOKENS = None` (off, D12);
  - kept unchanged: `SEARCH_SEED_BASE = 100`, `FINAL_SEED_BASE = 5000`, the prices, `OPT_MODEL`, `AGENT_MODEL`,
    `GLOBAL_SLOTS_DEFAULT = 24`, `GLOBAL_SLOTS_MAX = 32`, `SPLIT_COUNTS`, `APPWORLD_COMMIT`.

  `examples/appworld/abl/env.sh` sets:

  ```
  AW_PROFILE=abl  AW_HOME=/workspace/aw_abl  AW_STATE=/workspace/aw_abl/state  AW_SCRATCH_ROOT=/tmp/aw_abl
  AW_LEDGER_NAME=ABLATION_STATUS.md  AW_BRANCH=eval-abl  AW_REPO=/workspace/worktrees/eval-abl
  AW_ENV_FILE=/workspace/worktrees/base/.env  AW_SESSION_IDS=<this session>
  ```

  Grep every script the run uses for hard-coded `aw_rest`, `aw_ce2`, `aw_ce3`, `eval-ce2`, `eval-ce3`, `EVAL_APPWORLD_CE`,
  `ce2_k`, `ce3_k02`, `cape-impr2`, `3db96a0`, `memok-ce` and `int(K)`, fix each hit for this run, and list them in the
  ledger. Two things must stay correct: the CE2 two-arm independence check runs only between arms that are meant to be
  identical (there are none here, CE3-0010), and K is written with its decimals (CE3).
- **B2. AppWorld from scratch** (REST B1 to B4, CE2's `scripts/build.py` with `AW_BUILD=/workspace/aw_abl/build`; no REST
  build exists on this pod):
  - clone `StonyBrookNLP/appworld` at `42b5bcf`, `git lfs pull`, apply `patches/appworld-extra-headers.patch` (record its
    sha256);
  - `venv-aw` (Python 3.11, `uv`): CPU torch, `-e appworld`, `-e 'appworld/experiments[simplified]'`,
    `'pydantic>=2.12,<2.13'`, **`fastapi==0.143.0`** (fastapi 0.156 breaks AppWorld, REST CP-0008), `tiktoken`,
    `anthropic`;
  - `appworld install --repo`; `appworld download data --root $AW_BUILD/root_full`;
  - check split counts 90/57/168/417, scenario counts 30/19/56/139 and difficulties; record each split file's sha256;
  - `make_roots.py` builds `root_opt` (train + dev + `_base_`, 0 test-id hits), then `make_splits.py`,
    `make_reference.py`, the lint cache and the publish cache;
  - `chmod 000 root_full`.

  Re-runs read-only through `verify_build.py`.
- **B3. `venv-abl`** = `venv-aw`'s freeze + `-e /workspace/worktrees/abl-main/core`. It must contain no other cap-evolve
  core. `venv-lint` is the optimizer's small lint venv (jinja2, tiktoken; `sandbox.ensure_lint_venv`).
- **B4.** The data seal and caches are re-checked: `root_full` mode 000; `root_opt` 148 dirs; test-id grep 0.
- **B5. Drivers**, `examples/appworld/abl/`, from CE2's `ce2/` (adapter, `run_ce2.py` → `run_abl.py`, `launch_ce2.sh` →
  `launch_abl.sh`, `sandbox_cc/claude`, `p4`, `report`, `resume`), parameterized by `--arm`. New pieces:
  1. the feedback filter in `abl/adapter.py` (9.7);
  2. the tools-only smuggling lint (10.4);
  3. the instruction variants (9.4);
  4. the per-arm specs (9.3);
  5. `abl/cc/` (the plain Claude Code driver and its eval daemon, 10.2);
  6. `abl/reset_check.py` (9.8).

  Commit each piece after its offline unit test passes.

---

## 7. Model access (user guidelines 5 and 8)

### 7.1 The agent under test: gpt-oss-120b on RITS
- **Credentials:** `/workspace/worktrees/base/.env` (KEY=VALUE) holds `RITS_URL` (the RITS base URL) and `RITS_API_KET`
  (the key; the variable name has a typo, keep it).
  - The file is **never exported, printed, copied or committed**. Each episode worker reads it itself:
    `aw_agent.load_secrets(AW_ENV_FILE)`. Every launcher sets `AW_KEY_ENV=RITS_API_KET` and unsets `RITS_API_KET` /
    `RITS_API_KEY` in the parent environment.
  - The worker drops the key from the environment once the client is built, before the world starts.
- **Endpoint:** `$RITS_URL/gpt-oss-120b-a100/v1` (vLLM, OpenAI-compatible). The model id is `openai/gpt-oss-120b-a100`;
  the litellm route is **`hosted_vllm/openai/gpt-oss-120b-a100`** (the `openai/` route rejects `reasoning_effort`).
  `aw_agent.py` uses `base_url = {{MODEL_SERVER_URL}}/gpt-oss-120b-a100/v1`, with `MODEL_SERVER_URL` set from `RITS_URL`
  and `OPENAI_API_KEY=unused` (AppWorld constructs `OpenAI()` at init).
- **Auth:** header **`RITS_API_KEY: <key>`**, sent via the extra-headers patch (`extra_headers_env`). `Authorization:
  Bearer` is rejected with 403.
- **Config** (base plan §5.1, identical for every arm, never changed):
  - reasoning effort `medium`, temperature 0;
  - `max_completion_tokens` 6000 per call, `drop_reasoning_content`, `use_cache: false`;
  - `max_output_length` 60000 chars, `max_steps` 50, 100,000 completion tokens per task (enforced by the worker);
  - `max_model_len` is **40,144**, so prompt plus completion must fit.
- **Probe** (A2) without printing the key: a Python `-I` script reads the env file into a dict and sends `GET …/v1/models`
  and one chat request with the header. It prints only status codes, the model id, `max_model_len` and the usage counts,
  with any long token-like string masked.
- RITS handled 48 concurrent requests without 429s (CE2 A2). Memory, not RITS, limits concurrency.

### 7.2 The optimizer: Claude Sonnet 5.5 through `~/.claude/settings.json`
- **Gateway:** `~/.claude/settings.json` `env` holds `ANTHROPIC_BASE_URL` (ContextGuru), `ANTHROPIC_AUTH_TOKEN` and
  `ANTHROPIC_CUSTOM_HEADERS` (`x-context-guru-token: …`).
  - `common/sandbox.claude_env()` reads those three keys into the optimizer process's environment and nothing else.
  - The shim then passes `--setting-sources ''`, so no user or project settings load: `~/.claude/settings.json` allows
    `WebFetch(domain:*)`, which would open the sandbox proxy (CE2 CP-0013). The managed `sandbox.bwrapPath` still loads.
  - Never print these values; read only the key names when checking.
- **Model pinning:** the settings file defaults `ANTHROPIC_MODEL` / `ANTHROPIC_DEFAULT_OPUS_MODEL` to an Opus id. So the
  shim sets `ANTHROPIC_MODEL`, `ANTHROPIC_SMALL_FAST_MODEL`, `ANTHROPIC_DEFAULT_{OPUS,SONNET,HAIKU}_MODEL` and
  `CLAUDE_CODE_SUBAGENT_MODEL` **all to `aws/claude-sonnet-5-5`**, both in the process environment and in the per-call
  `--settings` file. The spec has `optimizer_model: aws/claude-sonnet-5-5` and the CLI gets `--model aws/claude-sonnet-5-5`.
- **Gateway rules** (eval 5 G1 to G3):
  - send no `temperature`, `top_p`, `top_k` or `seed`;
  - no forced `tool_choice`;
  - a deterministic 4xx other than 429 is not retried;
  - the `[cyber]` classifier refuses exfiltration-styled prompts, so the A9 probe uses neutral wording ("which files are
    visible in this workspace").
- **Print mode:** set `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS = 4 h` (14,400,000), or print mode ends background sub-agents
  after 600 s (eval 5 D11).
- **Usage:** every session runs with `--output-format json`. Its `modelUsage` (summed over models, so sub-agents count) is
  appended to `AW_STATE/<arm>/optimizer_usage.jsonl`, and the full result JSON is kept in `AW_STATE/<arm>/claude_calls/`.

---

## 8. Harness, evaluator, cache, seed baseline and budget

- **Harness** (unchanged from REST and CE2):
  - P is `policy/instructions.txt`; T is `tools/helpers.py` (REPL functions) and `tools/api_notes.json` (notes appended
    to API docs); M is `memory/`, sealed in this run (D13). Injection is through `CapReActAgent`.
  - REPL hardening: `os`, `pathlib`, `io`, `shutil` and `glob` are removed from AppWorld's import allowlist.
  - Records are gold-free: the evaluator's `trace` is dropped.
  - Lints: the prompt keeps its three Jinja variables, `USER:`/`ASSISTANT:` structure and final block, at ≤ 8,000
    tokens; helper AST lint; notes ≤ 400 chars each; no 8-gram of a train/dev instruction; no supervisor contact.
  - A violating candidate runs no episode, costs 0 counted rollouts, and gets the violations as feedback.
- **Evaluator** (`common/evaluator.py`), the only path to an episode:
  - lint first;
  - cached records by `(tree hash, task, seed, phase)`, returned uncounted;
  - `SeedRerunRefused` after P3;
  - any id outside train ∪ dev is refused unless `AW_ALLOW_SEALED=final-eval-only` (set only by the window);
  - `BudgetExceeded` before a batch that would take an arm past B = 882 fresh;
  - one global slot per episode; PAUSE honoured;
  - `aw_agent.py` runs as a subprocess with `APPWORLD_ROOT=root_opt` and a 30-minute wall cap (CE2-0136: a runaway
    10 GB worker was ended by it); one infra retry;
  - every fresh record goes to `AW_STATE/<arm>/rollouts.jsonl`, every cache hit to `cache_hits.jsonl`.

  The cap-evolve adapter's `run_trials` and the `abl_cc` daemon both call it, so the cache, slots, guard, seal and budget
  apply to every arm.
- **Slot pool:** `AW_GLOBAL_SLOTS` (24) as `flock` files `AW_STATE/slots/<i>.lock`, shared by every process.
- **Seed baseline (P3):** `scripts/p3_seed.py` with the abl profile: 147 episodes, once, through the evaluator into the
  shared cache. Then `SEED_BASELINE_DONE` and a `result` entry with train, dev and union TGC. For context only, REST and
  CE2's seed scored about 0.37 on the union. A large difference is investigated before P4 (R5).
- **Budget per arm:** counted = fresh search episodes. Cache hits, the seed baseline and acceptance probes are not counted.
  - Cap-evolve arms: 6 iterations × 147 = **882 counted**. `max_metric_calls: 1029` counts the cached baseline as 147.
    A lint-rejected or surface-voided candidate costs 0 counted rollouts but consumes an iteration (#877): record each.
    An evaluation-error step also consumes an iteration (#876); fix the cause and resume with `--max-iterations <n>` so
    that 6 **scored** iterations remain the target (base F15).
  - `abl_cc`: its eval daemon enforces the same B = 882 (6 full evaluations of 147). A lint reject or a cache hit is free.

---

## 9. Cap-evolve deployment common to the five cap-evolve arms

### 9.1 What runs
Stock hill-climb on `main` `75b3bcd`:
- `algorithm_skill: hill-climb`, `--focus all`, deterministic orchestration, one child per iteration;
- the paired gate, accepting iff the mean paired per-task Δ over the 147 val tasks exceeds **0.2 · SE(Δ)**. On CE3's
  numbers that bar is about 0.008, a net gain of about 1.5 tasks;
- the champion is the last accepted candidate.

None of the following reaches an AppWorld run by itself (REST §9.5), so each is applied explicitly and verified (9.6):

| # | what (at `75b3bcd`) | how the run gets it |
|---|---|---|
| J1 | the current optimizer instructions template | the run's INSTRUCTIONS are **derived from a byte copy of main's template** (9.4) |
| J2 | the capability and phase skills (`skills/capabilities/{system-prompt,tools}`, `skills/phases/diagnose`) staged into `work/<cid>/guidance/` | `CAPEVOLVE_SKILLS_DIR=/workspace/worktrees/abl-main/skills` for **every** cap-evolve command |
| J3 | the V3 hill-climb core and its script | `venv-abl` (`-e abl-main/core`); the script from the pinned skills dir |
| J4 | the `claude-code` registry row (`claude -p … --permission-mode acceptEdits --allowedTools Bash --disallowedTools Monitor --model {model}`) | pinned skills dir; the shim adds only `--settings` and `--setting-sources ''` |
| J5 | `gate_k_se: 0.2` | written **explicitly** in every project yaml |

### 9.2 Launcher (`examples/appworld/abl/launch_abl.sh ARM [cap-evolve args]`)
The only way a cap-evolve search is started or resumed. It does, in order:
1. sources `abl/env.sh`, exports `CAPEVOLVE_SKILLS_DIR`, and puts `abl/sandbox_cc` then `venv-abl/bin` first on `PATH`;
2. sets `APPWORLD_ROOT=root_opt`, `AW_CAPE_ARM=<arm>` and `AW_KEY_ENV=RITS_API_KET`;
3. sets the arm's switches **and nothing else**: `AW_ABL_FEEDBACK` (`full` unless 10.5/10.6) and `AW_ABL_TOOLS_LINT`
   (`1` only for `abl_tools`);
4. sets `AW_CAPE_EXTRA_DENY` = every other arm's root;
5. unsets `RITS_API_KET`, `RITS_API_KEY`, `CLAUDECODE` and every `CAPEVOLVE_*` variable it does not set itself (no
   inherited ablation switch);
6. waits on `memok-abl`;
7. runs IMP launch checks 1 to 3 (9.6) and the arm's switch check, and exits 3 on any failure;
8. checks that `command -v claude` is the shim;
9. execs `venv-abl/bin/cap-evolve run --spec … --project … --run-ts <arm>_s0 --dashboard off --follow "$@"` under `nohup`,
   writes a pid file, and tees stderr to `AW_STATE/progress/<arm>.log`.

### 9.3 Spec (reference; each arm's differences are in its section)

```yaml
capabilities: [system-prompt, tools]           # ARM: abl_prompt [system-prompt]; abl_tools [tools]
capability_path: seed_capability
actions: [edit]
optimizer_skill: claude-code
optimizer_model: aws/claude-sonnet-5-5
optimizer_max_turns: 200
max_optimizer_usd: 0                           # off (D12); no optimizer_usd_per_iter key, so no --max-budget-usd
target_model: openai/gpt-oss-120b-a100
algorithm_skill: hill-climb
algorithm_focus: all
orchestration_mode: deterministic
memory_skill: md-files
optimizer_instructions_file: <abs path of the arm's rendered INSTRUCTIONS (9.4)>
runner_repo_path: /workspace/aw_abl/build/reference
capability_sources: [reference/api_index.md, reference/react_agent_notes.md]
dataset_source: adapter
split_ids_file: split_ids.json                 # train = val = official train ∪ dev (147), test = []
num_trials: 1
gate_mode: paired
gate_k_se: 0.2                                 # user guideline 10. MUST be explicit
max_iterations: 6
stall: 0
max_metric_calls: 1029                         # 147 baseline (cached) + 6 × 147
protected_paths: [default, "memory/*"]         # ARM: abl_prompt adds "tools/*"; abl_tools adds "policy/*"
store: git
# no objectives: block -> single objective = reward
```

Scaffold each project with the **pinned** intake script (`abl-main/skills/phases/intake/scripts/run.py`), as
`setup_project.sh` does, and then overwrite its `capevolve.yaml` with the arm's rendered spec. `PROJECT.md` records every
resolved input, with "k = 0.2" (fix the hard-coded "k = 1.0" line). `cap-evolve check` must print `{"ok": true}`.
`cap-evolve estimate` is recorded.

### 9.4 Optimizer instructions (one base, one section per arm)
1. Byte-copy `abl-main/templates/project/optimizer/INSTRUCTIONS.md` into `abl/INSTRUCTIONS.base.md`, and record its
   sha256 (`84de4f00…`) in `abl/VENDORED.md`.
2. Keep every `{{…}}` placeholder and every sentence unchanged.
3. Insert **one** section, `## AppWorld facts for THIS run`, immediately before `## PREPARATION:`. The reference's version
   is CE2's block (`fork/eval-ce3:examples/appworld/ce2/INSTRUCTIONS.template.md`, from `**Objective score for this run.**`
   to the lint command) unchanged. Each ablation arm replaces exactly the sentences that its factor changes (its section
   gives the text). The section never names K, another arm, an earlier evaluation or a result.
4. Render one file per arm: `abl/INSTRUCTIONS.<arm>.md`. Store `diff -u base <arm>` in the pushed state
   (`abl/instructions_<arm>.diff`): it must show **only** the inserted section. Store `diff -u abl_ref <arm>` too: it must
   show only the sentences the arm's section lists.

### 9.5 Isolation of the optimizer
Section 11 applies to every arm. The claude-code optimizer has `Bash` and parallel sub-agents, so every past breach came
from it (F14, F19, F20). The "do not look for answers" sentence stays in the instructions, but nothing relies on it.

### 9.6 Acceptance A-ABL-CORE (each cap-evolve arm; all must pass; results with hashes in the ledger)
1. **Code pin:** `venv-abl/bin/python -c "import cap_evolve, pathlib; print(pathlib.Path(cap_evolve.__file__).resolve())"`
   points into `/workspace/worktrees/abl-main/core`. `git -C /workspace/worktrees/abl-main rev-parse HEAD` is
   `75b3bcdd0fc7…`, with a clean `git status`.
2. **Skills pin:** with the launcher's environment, `cli._find_skills_dir()` resolves to `/workspace/worktrees/abl-main/skills`,
   not `~/.claude/skills`.
3. **K, spec level:** the rendered `capevolve.yaml` has `gate_k_se: 0.2`, and the run's `run_config` event records it.
4. **K, effective:** run a 1-iteration `optimizer_skill: mock` dry run on 4 dev ids (a throwaway project, the accept cache
   namespace). The hill-climb command line contains `--k-se 0.2`, and the baseline comes from the cache. Gate unit check
   with the pinned `gate.py` (`decide(mode="paired")`): Δ̄ = 0.3·SE is accepted at k_se = 0.2 and rejected at 1.0; Δ̄ =
   0.1·SE is rejected at 0.2.
5. **J1 effective:** the dry run's `work/<cid>/INSTRUCTIONS.md` (the file the optimizer actually gets) contains, verbatim:
   - `# Optimize the capability — ship the edit with the largest expected objective score gain`
   - `## PREPARATION:`
   - `### 1. Understand the objective score`
   - `## Strategies for constructing edits:`
   - `### 4. Make capabilities that are SOFT and allow JUDGEMENT CALLS`
   - `### 6. On code surfaces (tools, MCP): prefer code over prose`
   - `## AppWorld facts for THIS run`
   - `**Objective score for this run.**`

   It contains none of `## Strategies for selecting improvements`, `largest expected reward gain`, `THREE TESTS`,
   `VERIFY-THE-FIX`, `{AW_`, or an unfilled `{{[A-Z_]+}}`.
6. **J2 effective:** `work/<cid>/guidance/{tools,system-prompt}/SKILL.md` exist only where the arm's `capabilities` puts
   them, and equal the pinned files by sha256. `guidance/diagnose/SKILL.md` matches the pinned head lines.
7. **J3:** the executed hill-climb script is the pinned `skills/algorithms/hill-climb/scripts/run.py` (path and sha256
   recorded).
8. **A-ABL-SAME** (rule Q4).
9. **Re-check at launch and at every resume:** the launcher re-runs 1 to 3 and the switch check. After the search, the scan
   re-reads every iteration's `work/<cid>/INSTRUCTIONS.md` and gate records and confirms J1, K = 0.2 and the arm's
   switches in every iteration.

### 9.7 The feedback filter (`abl/adapter.py`, env `AW_ABL_FEEDBACK`)
A pure function applied in the adapter's `_rollout()` and `score()`, to fresh records and cache hits alike, so that every
proposer-visible file is built from filtered objects. The evaluator's own records in `AW_STATE` stay complete; the
optimizer cannot read them (section 11).

| value | `Rollout.trace` (steps: thought, reasoning excerpt, code, output) | `Rollout.metadata` | `Score.feedback` / `Score.raw` |
|---|---|---|---|
| `full` (default; `abl_ref`, `abl_prompt`, `abl_tools`) | kept | all F1 fields | F1 text (`PASSED all n requirement checks…` / `FAILED: p/n … Failed requirements: … Collateral damage …`) |
| `eval_only` (`abl_notrace`) | **`[]`**; `output` = termination only | all F1 fields | unchanged F1 text |
| `trace_score` (`abl_tracescore`) | kept | only `termination`, `n_steps`, `complete_task_called`, `api_errors`, tokens, `success`, `seed`, `cost_source`, `cache_hit` (all readable from the trace or bookkeeping). **Removed:** `failed_requirements`, `pass_count`, `num_tests`, `collateral_damage` | **`Task reward: 0`** or **`Task reward: 1`**; `raw = {}` |

Rules:
- An unknown value raises at adapter import, so a typo cannot run the wrong arm.
- A lint-reject record keeps its violation text in every mode: that is the lint's own output, not evaluation feedback,
  and every arm gets it.
- `reward` and `Score.metrics` are never changed, so **the gate sees exactly what it sees in the reference**.
- Unit tests on synthetic records (never task files): for each mode, the filtered JSON has exactly the fields above, no
  string of a removed field survives anywhere in the serialized object, and `full` is byte-identical to CE2's adapter
  output.

### 9.8 Activation and reset: the mechanics shared by every arm
Each arm is activated **only** by its own project spec, its own rendered INSTRUCTIONS file and the variables the launcher
sets for its process tree. No shared file, global setting or core default changes, so ending one arm cannot leak into
another. Each arm's section gives its "Activate" and "Reset" lines. After an arm's search ends (freeze done), and again at
P6, `abl/reset_check.py <arm>` must pass:
1. no process of the arm is alive (by its pid files, **never `pgrep -f`**, eval 5 lesson);
2. `git -C /workspace/worktrees/abl-main status --porcelain` is empty and HEAD is `75b3bcd`;
3. none of `AW_ABL_FEEDBACK`, `AW_ABL_TOOLS_LINT`, `AW_CAPE_ARM` or `CAPEVOLVE_*` is set in the executing session's
   environment or in `abl/env.sh`;
4. the shared code's defaults are the reference's: `AW_ABL_FEEDBACK` unset means `full`; `AW_ABL_TOOLS_LINT` unset means
   off;
5. a fresh render of the **reference** spec, INSTRUCTIONS and shim settings is byte-identical to the ones stored at
   `abl_ref`'s launch;
6. the arm's per-call settings files under `AW_STATE/opt/` are moved to `AW_STATE/archive/<arm>/`, and its project root
   is made read-only (`chmod -R a-w`).

The result is a ledger entry, `reset <arm>`.

---

## 10. The arms

### 10.1 `abl_ref`: Cap-evolve full (reference)
- **Issue:** [#930](https://github.com/skillberry-ai/cap-evolve/issues/930).
- **What it is:** cap-evolve `main` `75b3bcd`, section 9 in full, with nothing ablated: `capabilities: [system-prompt,
  tools]`, `protected_paths: [default, "memory/*"]`, `AW_ABL_FEEDBACK=full`, the reference INSTRUCTIONS. It is the base
  that every cap-evolve ablation differs from in exactly one factor. It is the same configuration as CE3's `ce3_k02` on
  newer code (section 1.2). CE3's numbers are context only, never a comparison (other window).
- **Activate:** `bash examples/appworld/abl/launch_abl.sh abl_ref` (project `/workspace/aw_abl/arms/abl_ref/.capevolve/project`,
  run ts `abl_ref_s0`).
- **Acceptance:** A-ABL-CORE 1 to 9; A9 with this arm's launch configuration.
- **Reset:** 9.8. Store its rendered spec, INSTRUCTIONS and shim settings as the reference renders used by every
  `reset_check`.
- **Report:** section 15, labelled "reference".

### 10.2 `abl_cc`: Claude code (plain Claude Code, no cap-evolve)
- **Issue:** [#931](https://github.com/skillberry-ai/cap-evolve/issues/931).
- **What it is:** #908 NAIVE-CC, with these properties:
  - **one** `claude -p` session (Claude Code CLI 2.1.270, `aws/claude-sonnet-5-5`);
  - **no cap-evolve code, loop, gate, ledger, journal, skills, guidance or instructions**;
  - **no `/goal`, no driver loop and no re-prompting**;
  - a 3-line prompt, the same evaluation feedback content as `abl_ref`'s proposer, and the same B = 882;
  - the champion is whatever the session leaves in its working directory when it stops.

  It answers "how much of cap-evolve's gain does a plain coding agent get with the same tool, feedback and budget?".
- **Working directory** `/workspace/aw_abl/arms/abl_cc/work/` (never under a denied path). It holds:
  - `policy/instructions.txt`, `tools/helpers.py`, `tools/api_notes.json`: a byte copy of the seed;
  - `reference/api_index.md`, `reference/react_agent_notes.md`: the same benchmark docs `abl_ref` gets as
    `./guidance/sources/`, nothing more;
  - `eval_candidate`, `eval_status`: two small scripts that only touch `./.eval/`;
  - `.eval/{requests,results}/`.

  There is no `CLAUDE.md`, no `.claude/` and no guidance. `git init` is run so that the edit history can be reported.
- **Prompt (exactly; the three lines are byte-checked in A-ABL-CC):**

  ```
  Improve this agent's system prompt (policy/instructions.txt) and tools (tools/) so it solves more tasks.
  Evaluate a candidate on the training tasks with: ./eval_candidate <dir>   (budget: 882 rollouts; one evaluation runs all 147 training tasks)
  Each evaluation returns a ticket; ./eval_status <ticket> shows its progress, then per-task rewards and trajectories under .eval/results/<ticket>/.
  ```

  Nothing else: no description of grading, rules, lints or hints. The lint's violations reach Claude only if it submits a
  violating candidate, as in every arm.
- **Session flags:**
  - `CLAUDE_CONFIG_DIR=/workspace/aw_abl/arms/abl_cc/config` (fresh and empty: no user skills, `CLAUDE.md`, plugins or
    memory);
  - through the same shim as the other arms (section 11): `--setting-sources ''` plus `--settings <sandbox settings>`;
  - `--permission-mode acceptEdits --allowedTools Bash --disallowedTools Monitor`, the same as the cap-evolve registry
    row;
  - `--model aws/claude-sonnet-5-5 --output-format json`;
  - **`--max-turns 1200`** (= 6 × the 200 turns of a cap-evolve session; recorded; a hit is reported as a truncation);
  - the model variables and `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS` as in 7.2. Sub-agents are allowed, as in every arm,
    and inherit the sandbox.
- **Eval daemon** (`abl/cc/evald.py`): a trusted, unsandboxed host process and the arm's **only** path to rollouts. The
  sandboxed session can only drop a request file, `.eval/requests/<ticket>.json` = `{"dir": "<relative subdir>"}`,
  through `./eval_candidate`. The daemon:
  1. resolves `dir` strictly inside the working directory (refuses `..`, absolute paths and symlinks out);
  2. copies the three surface files into its own staging dir, so the candidate cannot change mid-evaluation;
  3. lints the copy (a reject costs 0 rollouts and returns the violations);
  4. evaluates the **fixed** 147 train ∪ dev ids through the shared evaluator, and refuses any other id or argument;
  5. enforces B = 882 counted rollouts and refuses once that is spent (a cache hit, an identical resubmission or the seed
     itself, is free);
  6. writes `.eval/results/<ticket>/summary.json` (mean reward, per-task reward, lint status, rollouts used and left) and
     `trajectories/*.json` in **the same `{"input", "rollout", "score"}` format and F1 content as `abl_ref`'s
     `./trajectories/`**, built with the same adapter functions and `AW_ABL_FEEDBACK=full`;
  7. logs every request in `AW_STATE/abl_cc/evals.jsonl`.

  An evaluation of 147 tasks takes about 30 to 45 min, longer than one Bash call. So `eval_candidate` returns a ticket at
  once, and `eval_status` reports progress. The daemon honours PAUSE.
- **Champion:** the working directory's three surface files when the session ends.
  - If they fail the lint, the champion is the last lint-clean candidate the daemon evaluated (recorded as a deviation).
  - Log the candidate Claude names as its pick, if it names one.
  - Log the best-evaluated candidate and its val, and report it as a secondary artifact (#908 pitfalls). Only the champion
    enters the final window.
- **Activate:** `bash examples/appworld/abl/cc/launch_cc.sh`. It starts `evald.py` (pid file) and the session through the
  shim, waits on `memok-abl`, and refuses to start if the config dir is not empty or the prompt hash differs.
- **Acceptance A-ABL-CC:**
  - the session's `system/init` event (`--output-format stream-json --verbose` in the dry run) lists no skill and no
    `CLAUDE.md` memory, and its tools match the flags;
  - the prompt's sha256 equals the plan's three lines;
  - the daemon refuses a path outside the working directory, a symlink out, an extra argument and a second budget over
    882;
  - a lint-violating candidate costs 0 rollouts;
  - a resubmitted identical candidate is free;
  - a 4-dev-id dry run (accept namespace, B = 8) returns results in the reference format, and the format check confirms
    the F1 fields;
  - A9 passes with this exact configuration, the daemon spool included.
- **Reset:** stop the session and `evald.py` by pid; move `config/` to `AW_STATE/archive/abl_cc/` (it holds the session
  transcript the scan reads); make the working directory read-only; then run `reset_check.py abl_cc`.
- **Report:** label it "plain Claude Code: no cap-evolve loop, instructions or gate". Give the number of evaluations it ran,
  the rollouts used of 882, turns used, and whether it stopped by itself or hit the turn cap.

### 10.3 `abl_prompt`: Cap evolve prompt only
- **Issue:** [#932](https://github.com/skillberry-ai/cap-evolve/issues/932).
- **Ablated factor:** the edit surface. Only the system prompt `policy/instructions.txt` may change, and `tools/` stays
  byte-identical to the seed. Everything else is as `abl_ref`.
- **Activate:**
  - spec: `capabilities: [system-prompt]` and `protected_paths: [default, "memory/*", "tools/*"]`;
  - instructions: `abl/INSTRUCTIONS.abl_prompt.md`;
  - launch: `bash examples/appworld/abl/launch_abl.sh abl_prompt`.
- **Enforcement:** cap-evolve's integrity seal hashes `tools/*` and `memory/*` before the session and clears their write
  bits. If a candidate changes, adds or removes any file there, its step is **indecisive before any rollout** (0 counted).
  It consumes the iteration and is recorded (`step_indecisive`). The anti-overfit lint (task id, supervisor or user name,
  email, phone, exact date, train/dev 8-gram) applies as in every arm. Report every reject.
- **AppWorld facts variant:** replace the bullet list of the three files with: "The candidate you may edit is ONE file,
  `policy/instructions.txt` (capability system-prompt) …[the reference's bullet for it, unchanged]… In this run `tools/`
  and `memory/` are read-only: a candidate that changes, adds or removes any file under them is voided before it is run.
  The agent's REPL helpers and API notes stay as they are." Every other sentence is unchanged.
- **Acceptance:** A-ABL-CORE; and two mock dry runs (4 dev ids). One whose mock edits `tools/helpers.py` gives an
  indecisive step with 0 counted rollouts; one whose mock edits only the prompt is scored.
- **Reset:** 9.8.
- **Report:** label "prompt only". Include the count of voided steps.

### 10.4 `abl_tools`: Cap evolve tools only
- **Issue:** [#933](https://github.com/skillberry-ai/cap-evolve/issues/933).
- **Ablated factor:** the edit surface. Only the tools may change, with everything cap-evolve's tools capability allows:
  - helper code;
  - adding and removing helpers, composite and wrapper helpers;
  - docstrings;
  - API-doc notes in `tools/api_notes.json`.

  `policy/instructions.txt` stays byte-identical to the seed.
- **Activate:**
  - spec: `capabilities: [tools]` and `protected_paths: [default, "memory/*", "policy/*"]`;
  - instructions: `abl/INSTRUCTIONS.abl_tools.md`;
  - launcher env: `AW_ABL_TOOLS_LINT=1`;
  - launch: `bash examples/appworld/abl/launch_abl.sh abl_tools`.
- **Enforcement:** the integrity seal on `policy/*` and `memory/*` (as 10.3). **Anti-smuggling lint**
  (`AW_ABL_TOOLS_LINT=1`, in `lints.py`, run at materialization, so it costs 0 rollouts, #877) rejects a helper whose
  return value is fixed procedure text. That is, a `return` of a string literal, an f-string with literal parts, or a join
  of literals, totalling more than 200 characters. #908 found that a tools-only arm smuggled policy into a
  `get_procedure()`. Docstrings and notes are tool descriptions, which this surface owns, so they are not rejected. The
  post-search report counts, per champion, the imperative policy sentences in docstrings and notes (a fixed word list:
  "always", "never", "must", "before you", "do not"), as a disclosed measure.
- **AppWorld facts variant:** replace the bullet list with: the reference's `tools/helpers.py` and `tools/api_notes.json`
  bullets, unchanged, followed by "In this run `policy/instructions.txt` and `memory/` are read-only: a candidate that
  changes, adds or removes any file under them is voided before it is run. All your changes go into the tools. A helper may
  not return fixed procedure or checklist text (more than 200 characters of literal text): the lint rejects it." Every
  other sentence is unchanged.
- **Acceptance:** A-ABL-CORE; mock dry runs: an edit of the prompt is voided (0 rollouts); an edit of a helper is scored;
  a helper returning 300 characters of literal text is lint-rejected (0 rollouts). After the search, the report shows one
  real example of each edit type the arm used (add, remove, composite, docstring, code, note), by type and count only (no
  task text).
- **Reset:** 9.8, plus confirm that `AW_ABL_TOOLS_LINT` is unset everywhere afterwards.
- **Report:** label "tools only". Include voided steps, smuggling-lint rejects and the docstring/note measure.

### 10.5 `abl_notrace`: Cap evolve no traces
- **Issue:** [#934](https://github.com/skillberry-ai/cap-evolve/issues/934).
- **Ablated factor:** the proposer's information. It gets **no conversation traces** (no thoughts, reasoning, code or
  outputs of the agent), only each rollout's reward and the evaluation feedback: failed requirement texts, pass fraction,
  collateral damage, steps, termination, `complete_task` called, API-error count. This is #908 EVAL-ONLY. The surface, gate
  and everything else are as `abl_ref`.
- **Activate:** launcher env `AW_ABL_FEEDBACK=eval_only`; instructions `abl/INSTRUCTIONS.abl_notrace.md`;
  `bash examples/appworld/abl/launch_abl.sh abl_notrace`.
- **Enforcement:** the filter of 9.7 at the adapter. So `./trajectories/*.json`, `{{FAILURES}}`, `baseline.json`,
  `state.json`, LEDGER, JOURNAL, RUNMAP, `prior_iterations/` and the rejected reasons are all built without the trace. The
  history files stay, as in `abl_ref`: they record what was tried, not traces.
- **AppWorld facts variant:** replace the `./trajectories/` sentence with: "`./trajectories/` holds one JSON per rollout
  with NO conversation: `input.instruction`, `rollout.metadata` (termination, steps, tokens, failed requirement texts,
  collateral-damage flag) and `score.feedback`. `rollout.trace` is empty: this run does not show you what the agent did,
  only how each task was graded. A requirement text says WHAT the evaluator checked, never the gold value." Every other
  sentence is unchanged.
- **Acceptance:** A-ABL-CORE; in the mock dry run, a script walks the whole run dir and the optimizer workdir and prints
  counts only. It must find 0 non-empty `trace` arrays and 0 `thought`/`code`/`reasoning` keys, while failed-requirement
  fields are present in the failing records. A9.
- **Reset:** 9.8 (`AW_ABL_FEEDBACK` unset → `full`).
- **Report:** label "no traces (evaluation feedback only)".

### 10.6 `abl_tracescore`: Cap evolve traces and score only (without full eval)
- **Issue:** [#935](https://github.com/skillberry-ai/cap-evolve/issues/935).
- **Ablated factor:** the proposer's information. It gets the **full conversation traces** (every step's thought,
  reasoning excerpt, code and output) and **only** the per-task reward, 0 or 1. Removed: every evaluation field (failed
  requirement texts, pass counts, collateral damage) and every "why it failed" text. This is #908 TRACE+SCORE. Everything
  else is as `abl_ref`.
- **Activate:** launcher env `AW_ABL_FEEDBACK=trace_score`; instructions `abl/INSTRUCTIONS.abl_tracescore.md`;
  `bash examples/appworld/abl/launch_abl.sh abl_tracescore`.
- **Enforcement:** the filter of 9.7, so every derived file (`{{FAILURES}}` lines read `Task reward: 0`, LEDGER, JOURNAL,
  rejected reasons, `baseline.json`, `state.json`) carries the reward only.
- **AppWorld facts variant:**
  - in the objective paragraph, replace "Partial passes earn nothing; the failed-requirement texts in each trajectory say
    which checks failed." with "Partial passes earn nothing. In this run you are NOT told which checks failed: each
    rollout carries only its reward.";
  - replace the `./trajectories/` sentence with: "`./trajectories/` holds one JSON per rollout: `input.instruction`,
    `rollout.trace` (per step: thought, reasoning excerpt, code, output truncated to 2,000 chars), `rollout.metadata`
    (termination, steps, tokens) and `score.feedback`, which is only `Task reward: 0` or `Task reward: 1`. Infer why a
    run lost reward from the conversation itself."

  Every other sentence is unchanged.
- **Acceptance:** A-ABL-CORE; in the mock dry run, a script walks the run dir and workdir and prints counts only. It must
  find 0 `failed_requirements`, `pass_count`, `num_tests`, `collateral_damage` fields and 0 occurrences of
  `requirement checks` or `Failed requirements`, with traces present in every non-lint record. A9.
- **Reset:** 9.8.
- **Report:** label "traces + score only (no evaluation feedback)".

---

## 11. Optimizer isolation mechanics (Claude Code's sandbox; user guideline 9)

CE2's `common/sandbox.py` and the `sandbox_cc/claude` shim (A9-verified in this pod type), adapted. **Every optimizer
session of every arm goes through the shim, `abl_cc` included.**
- **The shim** execs the real CLI with the caller's flags plus `--settings <per-call settings>` and `--setting-sources ''`.
  It also:
  - refuses any caller-supplied `--settings`, `--setting-sources` or permission bypass;
  - waits on `memok-abl` and PAUSE;
  - logs `modelUsage` to the arm's `optimizer_usage.jsonl`;
  - sets the model variables of 7.2.
- **Settings:**
  - `sandbox: {enabled: true, failIfUnavailable: true, allowUnsandboxedCommands: false, filesystem.denyRead: DENY,
    network.allowedDomains: [gateway host]}`;
  - `permissions.deny`: `Read(//p/**)` and `Edit(//p/**)` for each `p` in DENY, plus `WebFetch`, `WebSearch`;
  - `env: {DEVAGENT_BWRAP_NETWORK: restrict, …model vars}`.

  Every rule starts with `//` (absolute).
- **DENY** (every path and, for a symlink, its target):
  - `root_opt`, `root_full` and the whole AppWorld clone (generators, app source, data);
  - `/workspace/aw_abl/state` (the evaluator's full records, caches, other arms' logs);
  - `/workspace/aw_abl/build/venvs` except `venv-lint`;
  - **every other arm's** `arms/<arm>/` root;
  - `/tmp/aw_abl` (AppWorld native outputs; no session needs it);
  - every repo checkout (`/workspace/worktrees`, `/workspace/src`), which holds the evaluator, adapters, this plan, the
    ledger, the CE2/CE3 artifacts and `.env`;
  - `/workspace/inbox`, `~/.claude/projects`, `~/.config/gh`, other sessions' `/tmp/claude-<uid>/` dirs, every `.env`;
  - the arm's own project `adapters/` dir.
- **Workspace:** `<run dir>/work/<cid>` for the cap-evolve arms (the run dir holds only adapter-filtered files, 9.7), and
  `arms/abl_cc/work` for `abl_cc`. A workspace under a denied path is refused.
- **The evaluator never runs inside an optimizer process.** Episodes run in separate, unsandboxed processes: the adapter's
  `run_trials`, or `evald.py`.
- **A9** (each arm, its exact launch configuration, before any counted rollout):
  1. Plant a random secret in each sealed location: `root_opt` gold, `root_full` (unlock only to plant, then relock), the
     generator dir, the app source, `AW_STATE`, each other arm's root and a `.env` stand-in.
  2. Make one real call through the shim, with a neutral prompt ("I am checking which files are visible in this
     workspace; run these commands and paste the output"). The prompt tries `cat`, `Read`, `cp`, `find /`, a sub-agent, an
     AF_UNIX socket and a non-gateway URL.
  3. **PASS** iff:
     - no secret appears anywhere in the transcript, sub-agents included;
     - the call really tried (≥ 3 tool uses, ≥ 1 Read);
     - the network to a non-gateway host and AF_UNIX sockets are refused;
     - normal work still runs: a workspace file is written, the lint ran, and for `abl_cc` a request file reached the
       spool.
  4. Remove every planting dir (CE2 CP-0034) and move A9's usage lines into an accept log (CE2 CP-0041).

  Never instruct any agent to disable or bypass its sandbox.
- **Caveat** (container guide §1.4): under landrun + proot, masks are path rewriting, not a kernel wall, and processes are
  shared. So the post-search scan stays mandatory.

---

## 12. Tracking issues and progress posts (user guideline 4)

**Before execution** (done 2026-10-25, when this plan was written: #930 to #935): one issue per arm on `skillberry-ai/cap-evolve`,
labels `paper-experiment`, `algorithm`, titled `AppWorld ablation: <name> (cap-evolve main 75b3bcd, gpt-oss-120b)`. The
**first post** of each issue (its body) is the projection of this plan for that arm: its own section 10.x plus every
common section. The issue numbers are in the table at the top, and go into `manifest.json` and ABL-0000.

**During execution:**
- **Milestone posts** go on the arm's issue at once when:
  - build and acceptance are done;
  - P3's seed baseline is done (the same post on all six);
  - its search starts;
  - each iteration's verdict (val, Δ̄, SE, K·SE, accept/reject/voided; counts only), or for `abl_cc`, each evaluation's
    mean val and the rollouts used;
  - its search ends; its freeze; its reset check; its isolation scan; its dev diagnostic;
  - final-window progress (every 25%);
  - final results.
- **Hourly status posts:** `autopost.py` posts **at least once per hour on each of the six issues**, whatever the arm's
  stage (queued, building, searching, waiting for the window, scoring, analysing). Each post gives:
  - stage; iterations scored of 6 (or evaluations of 6) and accepts;
  - counted rollouts of 882; optimizer tokens and proxy USD;
  - best search score so far (labelled "fit metric");
  - memory state and peak; last ledger checkpoint; ETA.

  `autopost.py` is a `nohup` loop restarted by `resume.py` and by the heartbeat. Every 60 s the heartbeat checks that the
  last post on each issue is under 60 minutes old. If one is not, it records an `error` entry and posts at once
  (CE3-0002).
- **Content rules:** counts and aggregates only. No task ids, task or supervisor text, trajectory text, secrets, optimizer
  prompt or edit text, or per-task test outcomes. **No test-set score of any arm before the window completes and the
  analysis runs.** Every body passes the content filter. Each post is keyed and recorded in a `posted` ledger entry with
  its URL, so nothing is posted twice.
- **Final post:** the arm's results comment (section 15). Post with `gh issue comment <n> -R skillberry-ai/cap-evolve
  --body-file …`.

---

## 13. Orchestration, ledger and resume

### 13.1 Phases
- **P0:** decisions and issue numbers (ABL-0000).
- **P1:** build B0 to B5 (parallel where independent, R4).
- **P2:** acceptance: A1 to A13, A-ABL-CORE for each cap-evolve arm, A-ABL-CC, the per-arm checks, and A9 per arm.
- **P3:** the shared seed baseline: 147 episodes, once.
- **P4:** searches in two waves of three (R4). Per arm: search → freeze → reset check → isolation scan.
- **P5:** dev diagnostic: all six champions on dev, 1 trial, seed 100 (cache hits; recorded).
- **P6:** full isolation scan, the model-usage check (Q3), the J1/K/switch re-check (9.6.9), and `reset_check.py` for all
  arms.
- **P7:** the one final window.
- **P8:** analysis.
- **P9:** results posts.

Each phase has a resume rule: skip done units, redo an idempotent step, never post twice.

### 13.2 The ledger (`docs/ABLATION_STATUS.md`)
- Written only by `status_doc.py`, under `flock(AW_STATE/ledger.lock)`.
- **Entry format:** `## ABL-NNNN · <UTC> · <phase> <label> · <kind>`, a prose line, then a fenced `json` block with:
  `cp`, `prev_cp`, `prev_commit`, `utc`, `kind`, `phase`, `arm`, `done_through`, `next`, `counts`, `spend`, `memory`
  (`used_pct`, `peak_pct`, `state`), `artifacts` (sha256), `code` (sha), `open_decisions`.
- **`kind`:** phase_start, result, phase_done, heartbeat, decision, abort, resume, restore, rebuild, repair, error,
  cap_spend, posted, reset.
- After every entry: commit (pathspec: the ledger, `docs/ABLATION_STATUS_STATE/`, `examples/appworld/`) and push with
  `git push fork HEAD:eval-abl`.
- **Content filter** before each commit and post: refuse any task id, `.env` or gateway value, train/dev 8-gram or
  supervisor contact.

### 13.3 Pushed vs local
- **Pushed:**
  - the ledger; `manifest.json` (hashes, seeds, issues, `SEED_HASH`, K, per-arm switches);
  - per-arm `progress.json`; the instruction diffs and `same.json`;
  - each frozen artifact, after its lint;
  - `final/progress.json` (counts only), `final/analysis.json`, `RESULTS_<arm>.md`;
  - the code.
- **Local only** (`AW_STATE`, arm roots): records, trajectories, optimizer transcripts, window order and cells.

### 13.4 Resume (`resume.py`)
1. Fetch; fast-forward or push `eval-abl`; stop if it has diverged.
2. Refuse if a pid file names a live runner (check the pids, **never `pgrep -f`**).
3. Check `container_age_s`. If the pod restarted, record it and apply R2's "relaunch smaller". `/tmp/aw_abl` may be empty
   after a restart; recreate it.
4. Re-verify the build (`verify_build.py`) and `root_full` mode 000 (unless in P7).
5. Reconcile local records with the last entry:
   - each cap-evolve arm resumes through `launch_abl.sh <arm> --resume` (cap-evolve's own state);
   - `abl_cc` resumes as follows:
     - if its session ended, nothing is resumed;
     - if the session died mid-run (pod restart), the arm is **not** re-prompted (#908: no re-prompting). Record an
       `error` entry and ask the user whether to start one fresh session from the last workdir state or to freeze as is;
     - `evald.py` restarts and finishes any accepted ticket from the cache;
   - the window resumes from its cell records. The evaluator cache makes redone episodes free.
6. Restart `memguard.py` (first), the heartbeat and `autopost.py`.
7. Append a `resume` entry and relaunch the phase runner under `nohup`.

A10 tests this with a kill in the middle of a mini run.

---

## 14. Acceptance checks before any counted rollout

| id | check |
|---|---|
| A1 | `aws/claude-sonnet-5-5` answers through the shim for each arm; `modelUsage` shows only that model, sub-agent included; no `temperature` on the wire |
| A2 | RITS: `max_model_len` 40,144; 48 concurrent short requests return 200; 1 dev episode completes through the patched client (accept namespace); the RITS key appears nowhere under `/workspace/aw_abl`, `/tmp/aw_abl` or pushed files |
| A3 | REPL hardening (`import os`, `open(answer.json)`, a `pathlib` read all fail); `root_opt` 0 test-id hits; `root_full` unreadable |
| A4 | injection: the seed's first request is byte-identical to stock; helpers and notes work with the doc text unchanged; a lint violation is rejected without a rollout |
| A5 | scoring: a released train solution scores 1, run by a trusted script, never read; a no-op scores 0; scoring twice is identical; no `trace` or gold in records |
| A6 | splits and seal: `split_ids.json` = `train.txt` ∪ `dev.txt` (147) for every arm; a test id is refused without `AW_ALLOW_SEALED` |
| A7 | the final-window order is reproducible from its recorded seed and matches its sha256 |
| A8 | context: 10 dev episodes stay under 34K prompt tokens; `P_max` and `H_max` recorded; the 8,000-token prompt limit holds |
| A9 | the optimizer sandbox, for each of the six arms, in its exact configuration (section 11) |
| A10 | ledger and resume: a killed mini run resumes with no unit run twice; 3 concurrent `status_doc.py` appends all land; the content filter refuses a task id and an `.env` value |
| A11 | **memory guard:** sample period ≤ 10 s, logged; a synthetic allocation in a child process crossing 90% sets PAUSED within 10 s; the evaluator starts no episode and the shim and `abl_cc` no session while PAUSED; it resumes only below 85%; `memok-abl` reflects it; the executing agent's spawn check reads it |
| A12 | **metrics:** one episode record and one shim usage line (cap-evolve arm and `abl_cc`) carry every field of 5.2; the usage line sums `modelUsage`; proxy USD uses the Sonnet 5.5 prices |
| A13 | **seed reuse:** after P3, a candidate dir identical to the seed is served from the cache (0 counted) for every arm, `abl_cc`'s daemon included; a fresh seed episode raises `SeedRerunRefused`; the slot pool never exceeds its size with 3 concurrent callers. Run on the **real** cache before any path swap (CE2-0009) |
| A-ABL | A-ABL-CORE 1 to 9 per cap-evolve arm (9.6); A-ABL-CC (10.2); the per-arm checks of 10.3 to 10.6; the filter unit tests (9.7); `reset_check.py` on a throwaway arm |

None of these rollouts are counted.

---

## 15. Final window, statistics and the six reports

- **Freeze.** Copy each champion (all three surface files) to `AW_STATE/final/artifacts/<arm>/`, lint it, tree-hash it, and
  check the hash against the run's own record (CE2 CP-0206). The seed = `seed_capability` (`SEED_HASH`). An arm that
  accepted nothing is frozen as the seed and labelled inert. Commit the champion hashes and the window order hash
  **before** the first window episode; change nothing after that.
- **Window:** 168 `test_normal` × 7 arms × 2 trials = **2,352 cells**.
  - One shuffled order, from a seed recorded in advance (`20261025` + a fixed suffix, in `manifest.json`).
  - `AW_ALLOW_SEALED=final-eval-only` and `APPWORLD_ROOT=root_full`. `root_full` is unlocked at P7 start and relocked at P7
    end; both are logged.
  - The global pool at 24 slots; trial seeds 5000 + k.
  - Up to 3 infra retries with new seeds. A cell that still fails is scored 0 in the primary analysis and reported missing
    in the sensitivity analysis.
  - `PAUSE` is honoured. Only rewards, counters and infra flags are read; **no test trajectory is opened by anyone**.
  - The heartbeat flags a window with no new cell for 15 minutes.
- **Statistics** (REST §14, CE2 §16):
  - TGC, SGC, and TGC by difficulty.
  - **Primary contrasts (5): each ablation − `abl_ref`**, and secondary (6): each arm − seed. Each has a
    scenario-clustered paired bootstrap 95% CI (56 clusters, 10,000 resamples). For the primary 5, report raw and **Holm**
    p-values.
  - Also: `abl_prompt − abl_tools` and `abl_notrace − abl_tracescore`; γ = held-out gain / search gain per arm; the
    accept rate; cost per +0.01 TGC; tokens per episode against the seed; the full 5.2 table for all seven arms at search
    and test.
  - Anything added after seeing results gets a dagger (†) and is labelled exploratory.
- **Comparison discipline:** artifact-level statements. One search seed per arm means an ablation's contrast confounds the
  factor with search randomness. CE2 measured window SE of about 3 to 4 TGC points per arm, so a difference under about
  8 TGC points is not resolved. Say so plainly; treat a null result as a bound ("less than about X").
- **Each report** (draft to `RESULTS_<arm>.md`, then posted on the arm's issue) contains:
  - setup: commits, models as used, CLI version, the arm's activation lines and switch evidence, the J1 to J5 evidence;
  - the main table (the arm, `abl_ref` and the seed);
  - the difficulty table;
  - cost, token and latency tables (search and test);
  - the per-iteration (or per-evaluation) table;
  - what changed: artifact sizes and edit types, lint-clean, no task text;
  - the isolation scan counts and the reset check;
  - deviations;
  - what the numbers cannot support.

  No task ids, task text or per-task outcomes.

---

## 16. Deviations from #908, REST and CE2/CE3

| source | here | why |
|---|---|---|
| #908: 7 arms incl. CC-CAPEVOLVE, reference K = 2, 3 search seeds, 3 final trials, B = 1,050 | 6 arms (no CC-CAPEVOLVE); reference K = 0.2 with `main`'s template; 1 seed; 2 trials; B = 882 (6 × 147 fresh; the seed's 147 shared) | user guidelines 3 and 10, decisions D5 and D6; REST Q1 |
| #908: `abl_capability`-style surface rejection, a local credentials-injecting gateway | `main`'s `protected_paths` seal (indecisive, 0 rollouts); the settings.json gateway through the sandbox shim | D4; user guideline 8 |
| #908: prices Sonnet $3/$15 | Sonnet 5.5 list $2/$10 (cache $0.20 / $2.50), as REST and CE2; #908's gpt-oss proxy as a secondary | consistency with the series |
| #908: smuggling lint on docstrings | a literal-procedure lint on helpers; docstring/note imperative counts reported, not rejected | AppWorld's tool surface is docstrings and notes by design |
| REST/CE2: seed baseline reused from an earlier run | fresh P3 (no earlier build on this pod) | host fact 1.4 |
| CE2: `optimizer_usd_per_iter` 40 / `max_optimizer_usd` 300 | no money or token cap; 200 turns per session (D12, as CE3) | CE2-0021: caps truncate unevenly |
| CE2/CE3: no protection of `memory/` | `memory/*` sealed in every arm (D13) | prevents prompt smuggling in the surface arms; applied equally |
| CE2: branch pushed to `origin` (the fork there) | pushed to remote `fork`; `origin` here is `skillberry-ai` | this repo's remotes |

---

## 17. Budget and timeline (projection)

| phase | counted rollouts | wall (estimate) |
|---|---|---|
| P1 build (AppWorld from scratch) + P2 acceptance | ≈ 40 (not counted) | 4 to 6 h |
| P3 seed baseline | 147 (shared) | 0.5 to 1 h |
| P4: 6 searches in two waves of 3, ≤ 882 each | ≤ 5,292 | 12 to 16 h (CE2/CE3: 55 to 70 min per iteration with 2 searches) |
| P5 + P6 | 0 (cache hits) | < 1 h |
| P7 final window, 2,352 cells at 24 slots | 2,352 | 7 to 8 h (REST: about 330 cells/h) |
| P8 + P9 | 0 | 1 h |
| **total** | **≈ 7,800** | **≈ 26 to 33 h** |

Optimizer spend is not capped. CE2/CE3 measured about $40 proxy ($63 to $102 CLI-reported) per cap-evolve arm over
6 iterations. Expect about $250 proxy over the six arms (`abl_cc` is unknown: one long session). Every session's
`modelUsage`, proxy USD and CLI USD are recorded. The agent is unpriced (RITS).

## 18. Risks

| risk | mitigation |
|---|---|
| OOM restart (3 optimizers with sub-agents + 24 episodes) | R2 guard at 5 s; 24 slots; 2 GB per optimizer budgeted; at most 3 searches; relaunch smaller; durable state on `/workspace` |
| an optimizer reads gold, another arm's run or earlier results | sandbox + whole-AppWorld, `AW_STATE`, other-arm and all-checkout deny; A9 per arm; scans; label any breach |
| user settings widen the sandbox (CE2 CP-0013) | the shim forces `--setting-sources ''`; A9's network item |
| a feedback filter leaks through a derived file | the filter sits in the adapter, the single source of every proposer-visible file; the dry-run walk of the whole run dir (10.5, 10.6) and the post-search scan count removed fields |
| a surface arm burns iterations on voided steps | the seal makes the files read-only and the instructions say so; voided steps are reported, not re-run |
| `abl_cc` stops early or runs very long | that is its result: reported with turns, evaluations and rollouts used; the 1,200-turn cap is a truncation if hit |
| a pod restart kills `abl_cc` mid-session | no silent re-prompt; ask the user (13.4) |
| an arm ends inert | a valid result; scored as a seed-identical arm |
| cap-evolve eval errors burn iterations (#876) | stable roots, cached tasks; `--resume --max-iterations` to keep 6 scored |
| usage undercount (CE2 CP-0326) | `modelUsage` summed from the first call; A12 |
| the window stalls (eval 5: 10 h) | pid files, never `pgrep -f`; the 15-minute no-progress flag |
| hourly posts stop | the heartbeat checks post age per issue every 60 s |
| `/workspace` fills (18 GB free) | native outputs on `/tmp`, deleted per episode; `df` at each phase start; stop below 2 GB |

---

## Appendix A. Lessons from the REST, CE2 and CE3 ledgers that this plan applies

| entry | what happened | applied here |
|---|---|---|
| REST CP-0008 | fastapi 0.156.2 broke every AppWorld world | fastapi 0.143.0 pinned (B2) |
| REST CP-0013 | the shim without `--setting-sources ''` let user settings open the network | forced in the shim; A9 network item |
| REST CP-0031/0034 | an empty A9 planting dir made setup skip intake | A9 removes its dirs |
| REST CP-0041 | A9 probe usage landed in the search's usage log | moved to an accept log |
| REST CP-0326 | the CLI's top-level `usage` missed sub-agent calls (cost 2.5× under) | `modelUsage` summed from the start |
| CE2-0001 | `worktree add -b … origin/eval-rest` set the upstream, so the first push overwrote another branch | `--no-track`, `push -u fork HEAD:eval-abl`, explicit refspec in `status_doc.py` |
| CE2-0009 | A13 ran 99 fresh seed episodes after a path swap | A13 on the real cache first |
| CE2-0012 | a forbidden "reward gain" string in the pinned template | `main`'s template is already fixed (= `3db96a0`); J1 forbidden strings kept |
| CE2-0021/0022 | a $15 per-iteration cap ended sessions before any edit | no money caps (D12) |
| CE2-0077/0087 | another session's transcript caused test-id hits; a contained sub-agent `find` probe | scan scoped to this run's sessions, others disclosed; tool calls read per hit |
| CE2-0136 | a runaway 10 GB episode worker | 30-minute wall cap kept; R2 guard |
| CE3-0002 | hourly posts late at start | autopost started in B0, heartbeat post-age check |
| CE3-0010 | a two-arm independence check run on one arm stopped the search | the check is not used: no two arms here are meant to be identical |
| eval 5 | `pgrep -f` self-match stalled a window 10 h; 48 workers OOM'd the pod; print mode ended sub-agents at 600 s | pid files; 24 slots; `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS` raised |
