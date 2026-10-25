# AppWorld eval CE2: Cap-Evolve Improvement 2 at gate K = 1 and K = 2

Status: **PLAN**, written 2026-10-22. Nothing in sections 6 to 18 has run yet. The status ledger is a
separate file, **`docs/EVAL_APPWORLD_CE2_STATUS.md`**, appended during the run under an exclusive file
lock (rule R3, section 4.3). This plan is not edited during execution; findings go into the ledger.

The plan evaluates **two optimization candidates** on AppWorld. Both are the same code, cap-evolve
"Improvement 2", and differ **only** in the K argument of the acceptance gate. Each is scored against the
**same unmodified seed agent**.

| arm id | method | reference implementation | pin | gate |
|---|---|---|---|---|
| `ce2_k1` | Cap-Evolve, Improvement 2, K = 1 | https://github.com/erezh16/cap-evolve/tree/cap-evolve-impr2 | `8194578` (`819457804eff4658a1582318e2b067562522d1a1`) | `gate_k_se: 1` |
| `ce2_k2` | Cap-Evolve, Improvement 2, K = 2 | https://github.com/erezh16/cap-evolve/tree/cap-evolve-impr2 | `8194578` (same commit) | `gate_k_se: 2` |

Tracking issues (on `skillberry-ai/cap-evolve`; the `origin` fork has issues disabled):

| arm | issue |
|---|---|
| `ce2_k1` | [#909](https://github.com/skillberry-ai/cap-evolve/issues/909) |
| `ce2_k2` | [#910](https://github.com/skillberry-ai/cap-evolve/issues/910) |

**The executing agent must read these in full before doing anything else** (rule R5):
- `docs/EVAL_SMOKE_TEST.md` ("the base plan"): sections 0 to 15 and Appendices A (findings F1 to F20),
  B and C.
- `docs/EVAL_SMOKE_TEST_FIX.md` ("the fix doc"): what was re-run and why; optimizer isolation.
- `docs/CONTAINER_AGENT.md` ("the container guide"): sub-agent isolation and memory in this pod.
- `docs/EVAL_APPWORLD_REST.md` on branch `origin/eval-rest` ("REST"): the most recent sibling, executed
  2026-10-20 to 2026-10-21 in this same pod with the same models, harness and final-window machinery.
  Its section 9.5 evaluated cap-evolve "Improvement 1" (`470f3fa`, k = 0.5). Its code under
  `examples/appworld/` is the starting point of this run's code. Read its sections 0 to 17 and every
  ledger entry of kind `error`, `repair` or `decision` (Appendix A below summarizes them).
- The candidate: `git diff 470f3fa 8194578 -- templates/project/optimizer/INSTRUCTIONS.md`, the whole
  pinned `templates/project/optimizer/INSTRUCTIONS.md`, `skills/algorithms/hill-climb/SKILL.md`,
  `skills/capabilities/{system-prompt,tools}/SKILL.md`, `skills/phases/diagnose/SKILL.md`,
  `core/cap_evolve/gate.py` (`decide`, the paired branch), and `core/cap_evolve/cli.py:982`.

Every rule of the base plan and of REST is kept unless this document says otherwise. Section 17 lists
every deviation. Where a source and this plan disagree on a fact, stop, record it in the ledger and ask
the user (rule R5).

Deliverables of the execution: one results comment per arm on that arm's issue (section 16), the two
frozen artifacts, the ledger, and a hourly-or-better progress record on both issues.

---

## 0. Scope and the non-negotiable rules at a glance

| item | this evaluation |
|---|---|
| methods | `ce2_k1`, `ce2_k2`: cap-evolve `8194578`, stock hill-climb `--focus all`, deterministic orchestration, `capabilities: [system-prompt, tools]`, identical in every setting except `gate_k_se` |
| **the seed** | the official AppWorld simplified ReAct code agent, stock prompt, no helpers, notes or memory (`seed_capability`, `SEED_HASH = 85a0da9cec2206a7…`). Its search-time baseline (train 90 + dev 57, 1 trial, trial seed 100) is **reused from REST's shared seed run** (user decision 2026-10-22, D5); no fresh seed episode runs at search time. The seed is one arm of the final window, run there fresh |
| optimizer model, both arms | `aws/claude-sonnet-5-5` via the gateway in `~/.claude/settings.json`, for the main loop **and** every sub-agent (rule Q3) |
| agent under test, every arm | `openai/gpt-oss-120b-a100` on RITS, `hosted_vllm/` route, reasoning effort `medium`, temperature 0, base plan §5.1 config (rule Q3) |
| benchmark | AppWorld at `42b5bcf`, **official splits only**. Search: train = val = train ∪ dev (147, base rule S2). Results: `test_normal` (168). `test_challenge` unused |
| trials | **search: 1 trial per task (trial seed 100); final window: 2 trials per task (trial seeds 5000 + k, k ∈ {0,1}); 1 search seed per arm**, identical for both arms (rule Q1) |
| budget per arm | 6 scored iterations; `max_metric_calls: 1029` (147 cached baseline + 6 × 147); hard cap **B = 900 counted (fresh) search rollouts**; `max_optimizer_usd: 120`; ≤ 10M optimizer non-cache-read tokens |
| final window | `test_normal` 168 × **3 arms** (seed, `ce2_k1`, `ce2_k2`) × 2 trials = **1,008 episodes**, in **one** interleaved shuffled order |
| metrics | reward, cost, tokens, latency at **both** the train (search) and the test phase, identical definitions for every arm (rule Q2) |
| isolation | no agent of any kind, executing or optimizing, sees gold, ground truth, solutions, task generators, app source, sealed splits, test outcomes, REST's run data, or the other arm's run (rule R1) |
| memory | sampled every **5 s** (never > 10 s) by a guard service; at ≥ 90% of the container limit nothing new starts (no sub-agent, episode or optimizer call) until it is back below 85% (rule R2) |
| resumability | `docs/EVAL_APPWORLD_CE2_STATUS.md` is the status ledger, appended under `flock`; one command resumes; only the in-flight step may be lost (rule R3) |
| parallelism | both searches run at the same time on one shared episode-slot pool; parallel sub-agents for build and checks, within rule R2 (rule R4) |

---

## 1. What was read and verified (2026-10-22)

### 1.1 Sources read
Everything listed at the top, REST's full ledger (CP-0000 to CP-0333) and code, `docs/BACKUP_BOX.md`,
`docs/VERIFICATION_SCAN.md`, `docs/TRAIN_BREAKDOWN.md`, issue #901, `CLAUDE.md`. Only read-only probes ran.

### 1.2 What "Improvement 2" is (verified)
- `cap-evolve-impr2` = `470f3fa` (REST's "Improvement 1": `gate_k_se` default 0.5 and the "Strategies
  for selecting improvements" section) + `6db6ffb`, `0a2e982` (docs only) + **`8194578`**, which changes
  only `templates/project/optimizer/INSTRUCTIONS.md` (59+, 53−).
- `git diff --quiet 470f3fa 8194578 -- core skills` is clean: **core and skills are byte-identical to
  Improvement 1**. The only code-level difference from REST's cape_improve is the optimizer instructions
  template, plus the K value this plan sets.
- What `8194578` changes in the optimizer instructions:
  1. "reward" becomes the **objective score**: title `# Optimize the capability — ship the edit with the
     largest expected objective score gain`; GOAL "raise the objective score…", plus "Take your time, study
     these instructions in detail and be meticulous…".
  2. A mandatory `## PREPARATION:` section: `### 1. Understand the objective score` (locate the
     objective score defined by the intake, or the default one, and its components), then
     `### 2. Editing how-to. Read these first`. The old Process, lever, CHECK, NON-OVERFITTING, Handover
     and Self-check sections are demoted to `####` under it, text unchanged.
  3. A new closing `## Strategies for constructing edits:` with six items: (1) largest expected
     objective-score gain on the whole distribution (moved and reworded); (2) REAL and GENERAL (moved);
     (3) "Make it work well for the tasks you're not seeing"; (4) **"Make capabilities that are SOFT and
     allow JUDGEMENT CALLS"**: every added or edited capability carries a "softness clause"; (5) code
     changes with great care, text when code would be too rigid, and the whole tools skill; (6) on code
     surfaces prefer code over prose (moved).
  4. Removed: the old `## Strategies for selecting improvements` ("Optimize code before prompts") and
     the old top-level placement of "On code surfaces". Item 5 now pulls the other way: code "with great
     care".
- The template's placeholders are unchanged: `TARGET_READER`, `FOCUS_SUMMARY`, `EMPTY_SEED`,
  `FAILURES` (×2), `PASSING`, `BENCH_REPO`, `PARALLEL_NOTE`, `CAP_BRIEF`, `ALGO_BRIEF`.
- The pinned `templates/project/capevolve.yaml` still has `gate_k_se: 0.5`. This plan overrides it per
  arm (K = 1, K = 2). Core falls back to 1.0 when the key is missing (`cli.py:982`; the hill-climb
  script's `--k-se` default is 1.0). The gate (`gate.py`, paired mode) accepts iff the mean paired
  per-task Δ > K · SE(Δ). The pinned hill-climb SKILL.md notes that at K = 1 a candidate that improves
  exactly one val task and changes nothing else has Δ̄ = SE, so it is rejected.
- **Objective score in this run:** no `objectives:` block in the spec, so the run is single-objective and
  gates on `reward` alone (`skills/phases/intake/inputs/INPUTS.md`, "objectives"). The objective score is
  the AppWorld reward: 1.0 if every AppWorld test of the task passes, else 0.0, averaged over the 147
  tasks. Section 9.4 tells the optimizer so, in identical words for both arms.

### 1.3 Facts about this host (probed 2026-10-22)
- `memcheck`: `limit_MB=32768`, `cpu_limit=8`, `swap_max=0`, `oom_kills_whole_container=1`
  (an OOM restarts the **whole pod**), used 4%. `nproc` is not the CPU limit.
- `/workspace`: 20 GB, **8.7 GB free**, persists across restarts. `/tmp`: 295 GB, 90 GB free, an
  `emptyDir` that does not survive a pod restart. Durable state lives on `/workspace`.
- REST's build is intact and reusable: `/workspace/aw_rest/build/{appworld, root_opt, root_full
  (mode 000), reference, clones, venvs/venv-aw, venvs/venv-cape}` (3.4 GB). `venv-cape` has
  `-e /workspace/worktrees/cape-improve/core` (`470f3fa`).
- REST's evaluator cache holds the 147 seed records at `/workspace/aw_rest/state/cache/main/85a0da9cec2206a7/`
  (147 files). The code that produced them (commit `a0c85b4`, P3) and `origin/eval-rest` have identical
  `adapters/aw_agent.py`, `seed_capability/` and `common/evaluator.py` (empty `git diff`). The records
  are therefore valid for this run, provided the check of section 7.4 passes.
- REST's memory guard is not running (`MEMSTATE.json` last written 2026-10-21T16:14Z). `~/bin/memok`
  reads `/workspace/aw_rest/state/MEMSTATE.json` (hard-coded path).
- Claude Code CLI 2.1.270; sandbox via `devagent-bwrap` (landrun + proot); the fix doc's namespace
  wrapper cannot run here (`unshare` fails, REST §1.2).
- `.env` (RITS key) is in `/workspace/worktrees/base/.env`. A user-level deny rule already blocks `Read`
  of it. Its value must never be printed, copied or committed.
- `CLAUDE.md`'s provider order governs `benchmarks.yml` CI runs; this run uses no CI (agent on RITS,
  optimizer on the gateway, base D1). Spend is still reported **per provider**.

### 1.4 What REST measured for Improvement 1 (context only, never a baseline for this run)
cape_improve (`470f3fa`, k = 0.5): 6 iterations, 4 accepted, val 0.374 → 0.837 (fit metric); 882
counted rollouts; optimizer $31.82 proxy (CLI-reported $79.56); about 45 min per iteration; test_normal
TGC 49.4 vs seed 33.3 (Δ +16.1 [8.9, 23.5]). These numbers come from **another window** and are not
compared with this run's numbers except as clearly labelled context (base F10, Appendix C.2: identical
artifacts drift 4–6 TGC points between windows).

---

## 2. Decisions

| id | decision | source |
|---|---|---|
| D1 | optimizer `aws/claude-sonnet-5-5` for both arms and every optimizer role (main loop, sub-agents, helpers) | base D1; guideline 6.3 |
| D2 | AppWorld core and agents from source at `42b5bcf`, pydantic 2.12.x, fastapi 0.143.0 (REST CP-0008) | base D2 |
| D3 | 1 trial per task in search, 2 per task in the final window, 1 search seed per arm | base D3; guideline 6.1 |
| D4 | candidate pin `8194578` for both arms; K = 1 and K = 2 | user task |
| D5 | **reuse REST's shared seed baseline** (147 records, cache key `(SEED_HASH, task, 100, main)`) as both arms' search baseline; 0 fresh seed episodes at search time | user decision 2026-10-22 |
| D6 | final window: seed + `ce2_k1` + `ce2_k2`, 1,008 episodes, one window; REST's cape_improve champion is **not** an arm | user decision 2026-10-22 |
| D7 | status ledger = **new file** `docs/EVAL_APPWORLD_CE2_STATUS.md` (REST's file is left untouched) | user decision 2026-10-22 |
| D8 | isolation: Claude Code's sandbox via the REST PATH shim (`--setting-sources ''` forced), with this plan's deny list (section 12) | REST D7, CP-0013 |
| D9 | memory guard at 90% (pause) / 85% (resume), sampled every 5 s, enforced on sub-agents, episodes and optimizer calls | guideline 7.2 |
| D10 | branch `eval-ce2` (from `origin/eval-rest`), worktree `/workspace/worktrees/eval-ce2`; state under `/workspace/aw_ce2` | section 6 |

If the executing agent meets a question these decisions do not answer, it asks the user (one
`AskUserQuestion`, recommended option first) and records the answer as a `decision` entry. It never
decides silently where the choice could favour one arm.

---

## 3. Arms

| arm id | learned artifact | surface |
|---|---|---|
| `seed` | none: `examples/appworld/seed_capability/` verbatim (byte-identical to stock) | none |
| `ce2_k1` | `candidates/<best_id>/` of the K = 1 run: edited `policy/instructions.txt`, `tools/helpers.py`, `tools/api_notes.json` | P + T |
| `ce2_k2` | the same, from the K = 2 run | P + T |

All three arms use the same harness, model client, decoding parameters, step cap, token cap and
evaluator: every arm's agent runs through the one unmodified `aw_agent.py` worker. Only each arm's own
surface files differ. An arm whose run accepts nothing is frozen as the seed and labelled **inert**.

---

## 4. MANDATORY EXECUTION RULES (read before any action; they override convenience)

> **These five rules are not optional.** A step that would break one of them is not taken: the agent
> stops, records an `abort` or `decision` entry, and asks the user. **Every sub-agent the executing agent
> spawns receives the text of this section verbatim in its prompt.**

### 4.1 Rule R1: no agent ever sees what it must not see (guideline 7.1)

**Forbidden content (the "sealed set"):**
- `ground_truth/` of any task, `answer.json`, `private_data.json`, `evaluation.py`, `solution.py`,
  `compiled_solution.py`, the evaluator's failure `trace`, AppWorld's native per-episode output dirs;
- AppWorld's task generators (`appworld/generate/`, base F19) and app implementation source
  (`src/appworld/apps/`, base F20);
- all `test_normal` and `test_challenge` task data and ids, `root_full`, and every final-window record
  until the analysis step reads counts from it;
- **REST's run data**: `/workspace/aw_rest/state/` (except the copy step of 7.4, done by a script),
  `/workspace/aw_rest/cape_run/` (Improvement 1's trajectories, workdirs, champion) and
  `/workspace/aw_rest/backup/`. **Optimizers** also never see REST's plan, ledger, results or issues (an
  optimizer that saw Improvement 1's edits would not search independently); the executing agent may read
  REST's plan, ledger and code, as this plan requires;
- **the other arm's run**: the K = 1 optimizer never sees the K = 2 run dir and vice versa;
- `.env`, the gateway token, other sessions' transcripts (`~/.claude/projects/*`, `/tmp/claude-*/*`),
  `~/.config/gh`.

**Who may touch it:** only named trusted scripts running as separate unsandboxed processes: the episode
worker (`aw_agent.py`), the windows (`window.py`), the build steps, the seed-cache copier (7.4), the
lint-cache builder and the isolation scan. No LLM, sub-agent or person reads it.

**How it is enforced (all layers apply; none is enough alone):**
1. **Data roots.** Search-time episodes use `root_opt` (train + dev only; a grep of every test id finds 0
   hits). `root_full` stays `chmod 000` until P7 starts and again after P7.
2. **Gold-free feedback (tier F1).** The only evaluator output the optimizer sees: reward 0/1, the pass
   fraction, the **texts** of failed requirements, the collateral-damage flag, whether `complete_task`
   was called, steps, API-error count and termination. Never a gold answer, `trace`, solution or
   reference value.
3. **Optimizer sandbox** (section 12): Claude Code's sandbox with `failIfUnavailable`,
   `allowUnsandboxedCommands: false`, `filesystem.denyRead` plus `permissions.deny Read(...)`/`Edit(...)`
   on the deny list, network restricted to the gateway host, no `WebFetch`/`WebSearch`, user settings
   **not** loaded (`--setting-sources ''`). Check A9 passes for **each arm's exact launch configuration**
   before any counted rollout.
4. **Executing agent and its sub-agents.** The orchestrating sessions never open a sealed-set file with
   any tool (`Read`, `Grep`, `Glob`, `cat`, `head`, `python -c open(...)`, …), never print a test record,
   never read a test trajectory, and never read REST's cape_improve run or results. The session is
   launched with `--settings /workspace/aw_ce2/launch/exec-settings.json` (deny rules for the sealed set);
   in B0, copy the same rules into `/workspace/worktrees/eval-ce2/.claude/settings.local.json`
   (git-excluded). Spawn sub-agents only with prompts that repeat this section. A sub-agent that writes
   code gets a dedicated directory and tests against **dev ids only**, with a mock or the shared
   evaluator, never by reading task files. Code that must handle task data is **run, never read**.
   **Use sub-agent isolation** (`isolation: "worktree"` for code-writing sub-agents) so that a sub-agent
   sees only its own checkout.
5. **Detection.** After each search (P4) and again before the window (P6), the isolation scan greps
   every optimizer transcript (sub-agents included), workdir, frozen artifact **and the orchestrating
   sessions' own transcripts** for: every test id, `test_normal`, `test_challenge`, `root_full`,
   `ground_truth`, `answer.json`, `compiled_solution`, `solution.py`, `generate/tasks`,
   `src/appworld/apps`, `aw_rest/cape_run`, `aw_rest/state`, and the other arm's run dir. Read the
   **tool calls** of each hit, not only the text (`docs/VERIFICATION_SCAN.md` §A1). Counts only are
   published. A real hit labels the arm "isolation breach" in every result (base F14).
6. **Nothing is ever published** that contains a task id, task or supervisor text, a train/dev 8-gram, a
   trajectory, a secret or a per-task test outcome (AppWorld redistribution rule; content filter, 14.2).

### 4.2 Rule R2: memory is watched every 5 s, and nothing new starts above 90% (guideline 7.2)

Follow `docs/CONTAINER_AGENT.md` §2 in full. In addition:
- **Guard service** `memguard.py` (REST's, with `AW_STATE=/workspace/aw_ce2/state`): a `nohup` process
  started in B0 **before anything heavy**, relaunched by `resume.py` and by the heartbeat if its
  `MEMSTATE.json` is older than 30 s. Every **5 s** it reads this container's cgroup: `used = anon +
  shmem` of `memory.stat` over `memory.max` (or `memory.high` if lower), and atomically writes
  `AW_STATE/MEMSTATE.json` = `{t, used_pct, used_MB, limit_MB, state, peak_pct}`.
- **Watermarks:** at `used_pct ≥ 90` it sets `state = PAUSED` and creates `AW_STATE/PAUSE`. It clears
  both only when `used_pct < 85`. One line per transition and one sample line per minute go to
  `AW_STATE/progress/memguard.log`.
- **`memok`:** `~/bin/memok` reads REST's path. Use `~/bin/memok-ce2` (a copy reading
  `/workspace/aw_ce2/state/MEMSTATE.json`; exit 0 only if `state == OK` and the file is < 30 s old).
  The cape launcher (`launch_ce2.sh`) and the shim wait on `memok-ce2`, never on `memok`.
- **Who honours it:**
  - the shared evaluator and the window: no new episode starts while PAUSED; in-flight episodes finish;
  - the claude shim: no new optimizer session starts while PAUSED;
  - **the executing agent: before every sub-agent spawn and every process launch**, run `memok-ce2` and
    `memcheck`. Spawn nothing if PAUSED, if `MEMSTATE.json` is older than 30 s (restart the guard first),
    or if `subagents_that_fit` is 0. Wait and re-check every 30 s.
- **Escalation:** if PAUSED for more than 10 minutes, shrink what was started, most recent first: lower
  the global episode slots by 25%; after 20 minutes, ask the K = 2 search to stop at its next iteration
  boundary (it resumes later with `--resume`). Record a `decision` entry each time. Never stop both arms
  unevenly without recording it; the arms must end with the same number of scored iterations.
- **Sizing:** pools from `cpu_limit` (8) and measured memory, never from `nproc`. Episode workers about
  0.5 GB each. **24 global slots** for search and for the window (REST peak 47.8% with three searches at
  24; eval 5 OOM-restarted at 48). Raise by 4 only after 30 minutes with peak `used_pct` < 65%, never
  above 32. Each claude-code optimizer session with parallel sub-agents is budgeted at 2 GB.
- **After a restart** (`container_age_s` shorter than the session; counters reset by `oom.group=1`),
  treat the work launched just before as the cause. Resume (14.4) and relaunch **smaller**: −25% slots.

### 4.3 Rule R3: the status ledger; the run can resume at any time (guideline 7.3)

- The ledger is **`docs/EVAL_APPWORLD_CE2_STATUS.md`** on branch `eval-ce2`. It is append-only. Every
  append happens under **`flock(/workspace/aw_ce2/state/ledger.lock)`**, through the one writer
  `status_doc.py` (REST's, with `AW_LEDGER_NAME=EVAL_APPWORLD_CE2_STATUS.md`, `AW_BRANCH=eval-ce2`).
  No driver, sub-agent or session edits the file directly, so concurrent updates never overwrite each
  other. A10 tests this with 3 concurrent writers.
- Every append: write the pushed state files atomically, append the entry, `fsync`, run the content
  filter, `git commit -- <pathspec>`, `git push origin eval-ce2` (never `--force`).
- Resolution: an entry at every phase boundary, build step, acceptance check, iteration verdict, freeze,
  scan, error and resume; coalesced results at most every 5 min; a heartbeat after 25 silent minutes.
  The only acceptable loss on a crash is the step in flight (an optimizer session or a batch of
  episodes), which is redone on resume.
- One command, `resume.py`, continues from the last entry (14.4).

### 4.4 Rule R4: parallelize as much as rule R2 allows (guideline 7.4)

- **Build and checks:** independent build steps and acceptance checks run in parallel sub-agents (for
  example: B5 venv + instructions derivation; A9 for each arm; A10/A11 harness checks), each with rule
  R1's text, each subject to the R2 spawn check.
- **Search:** both arms run **at the same time**, launched within the same minute, on one global pool
  of episode slots, so their searches see the same RITS conditions and total concurrency never exceeds
  the pool.
- **Inside an arm:** episodes are the parallel unit, always through the global pool; the claude-code
  optimizer may use its own parallel sub-agents (registry `parallel: true`), which inherit the sandbox.
- **Watchers:** detached `nohup` processes do the long work; at most one watcher sub-agent per running
  search, plus one for the guard and posting. Nothing depends on a sub-agent staying alive.
- **Never nest:** the executing agent's sub-agents must not spawn sub-agents (container guide §2.5).

### 4.5 Rule R5: quality over speed (guideline 8)

Take the time to read every source named here before writing code. Check every number against its
source. Prefer a correct pause to a fast wrong step. Before any counted rollout, every acceptance check
of section 15 passes and its result is in the ledger. When something is unclear or a result looks
surprising, stop and investigate (and ask the user if needed) before continuing. Report failures and
deviations plainly in the ledger and on the issues.

---

## 5. Quality rules for valid results (guideline 6)

### 5.1 Rule Q1: the same number of trials everywhere (guideline 6.1)

Verified against the sources: base plan §0 "search seeds: 1 per method", §7.2 `num_trials: 1`, decision
D3 "2 trials per task" in the final window; the fix doc and Appendix C kept them; REST Q1 used the same.

| level | value | applies to |
|---|---|---|
| search seeds per arm | **1** | both arms (one cap-evolve run each) |
| trials per task during search | **1**, trial seed **100** | every search episode of both arms; the reused seed baseline has the same |
| trials per task in the final window | **2**, trial seeds **5000 + k**, k ∈ {0, 1} | all 3 arms |
| dev diagnostic (P5) | **1**, trial seed 100 | both champions (cache hits: dev ⊂ val) |

**One (candidate tree, task, trial seed) is run at most once.** The evaluator caches every record by
`(tree hash, task id, trial seed, phase)`. A repeat returns the cached record, uncounted. An
infrastructure failure is not cached and is retried once with the same seed (base §7.1).

### 5.2 Rule Q2: the same metrics for both arms, at train and at test (guideline 6.2)

Collected by shared code only (the evaluator, the shim's usage logger, the window, `analyze.py`), never
by a per-arm counter, so the definitions cannot differ. **Every** arm reports **every** row.

| metric | train phase (search, train = val = 147) | test phase (final window) | source |
|---|---|---|---|
| **reward** | per iteration: val score, paired Δ̄, SE, K·SE, verdict; champion's search score (labelled "fit metric, train = val, selection-biased"); seed baseline (reused, labelled); TGC and pass fraction of counted rollouts | TGC, SGC, by difficulty (Easy 57, Medium 48, Hard 63); Δ vs seed with 95% CI; `ce2_k2 − ce2_k1` with 95% CI; pass fraction as a secondary | evaluator records; cap-evolve `events.jsonl`; window records |
| **tokens, agent** | prompt and completion tokens per episode (mean, p50, p90, total), max prompt tokens, steps, step-cap, token-cap and context-exceeded hits | the same | `aw_agent.py` record fields |
| **tokens, optimizer** | input, output, cache-read, cache-write tokens; sessions; per iteration; by model and role (main loop vs sub-agents), from the CLI's **`modelUsage`** (REST CP-0326: the top-level `usage` misses sub-agents) | n/a | `optimizer_usage.jsonl` per arm |
| **cost** | optimizer USD **proxy** at Claude Sonnet 5.5 list price: $2.00 / MTok input, $10.00 output, $0.20 cache read, $2.50 5-min cache write; plus the CLI-reported `total_cost_usd`, labelled. Agent: RITS is unpriced: "n/a (unpriced)", **never $0**; agent tokens stand in | agent: "n/a (unpriced)" plus tokens | shim, CLI JSON |
| **latency** | per-episode wall seconds (mean, p50, p90); per optimizer session seconds (mean, p90) and total; per-iteration wall time (optimizer + evaluation); search wall time; time to champion | per-episode wall seconds (mean, p50, p90); window wall time | `wall_seconds`; shim timing; ledger timestamps |
| **budget** | counted rollouts (of B = 900), metric calls (of 1,029), cache hits, lint rejects, infra retries, iterations scored vs consumed | infra retries, missing cells | evaluator; cap-evolve state |
| **stability** | n/a | share of tasks whose 2 trials agree, per arm | window records |
| **artifact size** | per champion: chars/tokens of `instructions.txt`, helper count and lines, notes count and chars | the same artifact | freeze |

Spend is reported **per provider**: RITS (agent: tokens, unpriced) and the gateway (optimizer: tokens,
proxy USD, CLI USD). A12 checks that one record of each kind carries every field above.

### 5.3 Rule Q3: the same models for every arm (guideline 6.3)

- **Optimizer:** `aws/claude-sonnet-5-5` through the gateway for every optimizer call of both arms,
  **including the claude-code optimizer's sub-agents and helper calls**. The shim environment sets
  `ANTHROPIC_MODEL`, `ANTHROPIC_DEFAULT_{OPUS,SONNET,HAIKU}_MODEL`, `ANTHROPIC_SMALL_FAST_MODEL` and
  `CLAUDE_CODE_SUBAGENT_MODEL` all to that id, and the spec sets `optimizer_model: aws/claude-sonnet-5-5`.
  No `temperature`, `top_p`, `top_k` or `seed` is sent (REST G1). A1 checks it per arm; after each search
  the scan counts every `modelUsage` key: **any other model id is an `error` entry** and is reported.
  Effort and thinking settings are whatever the shim passes, identical for both arms; record them.
- **Agent under test:** `openai/gpt-oss-120b-a100` on RITS with the base plan §5.1 config unchanged:
  `hosted_vllm/` route, reasoning effort `medium`, temperature 0, `max_completion_tokens` 6000,
  `drop_reasoning_content`, `use_cache: false`, `max_output_length` 60000 chars, `max_steps` 50, 100,000
  completion tokens per task. No arm changes the agent model, its decoding or its caps.

### 5.4 Rule Q4: one seed, reused, and arms that differ only in K

- Both arms start from `seed_capability` (`SEED_HASH`) and read the reused REST seed records as their
  baseline (section 7.4). No fresh seed episode runs in search (`SeedRerunRefused`).
- The two arms' specs, instructions, launcher, sandbox settings, adapter, slot pool and launch time are
  identical except: `gate_k_se`, the run dir, the run ts and the issue number. A `diff` of the two
  rendered `capevolve.yaml` files and of the two rendered `INSTRUCTIONS.md` files is stored in the pushed
  state and must show only those differences (check A-CE2-SAME).

---

## 6. Environment and code

### 6.1 Layout

```
/workspace/worktrees/eval-ce2/             # NEW worktree, branch eval-ce2 from origin/eval-rest; all commits and pushes go here
  docs/EVAL_APPWORLD_CE2.md                # this plan (copied from the base worktree, never edited after)
  docs/EVAL_APPWORLD_CE2_STATUS.md         # THE STATUS LEDGER (rule R3)
  docs/EVAL_APPWORLD_CE2_STATUS_STATE/     # pushed, publishable state (manifest, per-arm progress, artifacts, final counts)
  examples/appworld/                       # REST's harness + examples/appworld/ce2/ (this run's driver)
/workspace/worktrees/cape-impr2/           # NEW worktree, DETACHED at 8194578: the code under test. Read-only: never commit here
/workspace/aw_ce2/                         # AW_HOME, durable, outside git, never pushed
  launch/exec-settings.json                # the executing session's deny rules (R1.4)
  state/                                   # AW_STATE: ledger.lock, MEMSTATE.json, PAUSE, pid files, cache/, slots/, per-arm state, logs
  build/                                   # AW_BUILD: symlinks into /workspace/aw_rest/build (see B2) + venvs/venv-ce2
  run_k1/  run_k2/                         # the two cap-evolve project roots (.capevolve/project + run dir)
/tmp/aw_ce2/                               # AW_SCRATCH: AppWorld native outputs (deleted after each record)
```

Do not commit to `cap-evolve-impr2`: the candidate is the commit `8194578`, not the branch tip. Do not
touch `/workspace/worktrees/base`, `/workspace/worktrees/eval-rest` or `/workspace/worktrees/cape-improve`
except to read. Never use bare `git stash`.

### 6.2 Build steps (each idempotent, each one ledger entry)

- **B0.** `git worktree add -b eval-ce2 /workspace/worktrees/eval-ce2 origin/eval-rest`; copy this plan
  in; create `docs/EVAL_APPWORLD_CE2_STATUS.md` with a header and the marker
  `<!-- CHECKPOINTS BELOW THIS LINE -->`; commit; push `-u origin eval-ce2`.
  `git worktree add --detach /workspace/worktrees/cape-impr2 8194578`. Copy the deny rules into
  `eval-ce2/.claude/settings.local.json` (git-excluded). Create `~/bin/memok-ce2`. Start `memguard.py`
  (R2) and verify a fresh `MEMSTATE.json` within 10 s. First ledger entry CE2-0000: decisions D1–D10,
  issue numbers, host facts.
- **B1. Configuration, not forks.** `awrest.py` reads `AW_HOME`, `AW_STATE`, `AW_LEDGER_NAME`, `AW_BRANCH`
  and `AW_SCRATCH_ROOT` from the environment. Put the CE2 values in one env file
  `examples/appworld/ce2/env.sh` sourced by every CE2 command. Change the constants that are not
  env-driven in a CE2 copy of the module (`scripts/awce2.py`, imported as `awrest` by the CE2 entry
  points) rather than editing REST's: `CANDIDATES = ("ce2_k1", "ce2_k2")`, `ARMS`, `ISSUES`,
  `METHOD_NAMES` ("Cap-Evolve-impr2 K=1", "Cap-Evolve-impr2 K=2"), `PINS`, the cape pin
  (`8194578…`, `/workspace/worktrees/cape-impr2`). Keep `BUDGET_ROLLOUTS = 900`,
  `BUDGET_OPT_TOKENS = 10M`, `SEARCH_SEED_BASE = 100`, `FINAL_SEED_BASE = 5000`, the prices,
  `OPT_MODEL`, `AGENT_MODEL`, `GLOBAL_SLOTS_DEFAULT = 24`, `GLOBAL_SLOTS_MAX = 32`, `SPLIT_COUNTS`,
  `APPWORLD_COMMIT`. Grep every script the run uses for hard-coded `aw_rest`, `eval-rest`,
  `EVAL_APPWORLD_REST`, `cape_improve`, `cape-improve`, `470f3fa`, `cape_run` and `memok`, and fix each
  hit for CE2 (list them in the ledger).
- **B2. Build reuse.** `/workspace/aw_ce2/build/{appworld, root_opt, root_full, reference, clones,
  venvs/venv-aw}` are **symlinks** to the REST build (no copy: `/workspace` has 8.7 GB free). Re-run
  REST's B3/B4 checks read-only: AppWorld at `42b5bcf` with the patch (sha256 as REST's manifest),
  fastapi 0.143.0 and pydantic 2.12.5 in `venv-aw`, split counts 90/57/168/417, scenario counts
  30/19/56/139, difficulties, `root_opt` 148 dirs with 0 test-id hits, `root_full` mode 000, the lint and
  publish caches present (copy them to the new `AW_STATE`). Any mismatch: stop and ask. Every deny list
  (R1, section 12) names **both** the symlink and its target path.
- **B3. `venv-ce2`.** A new venv = `venv-aw`'s freeze + `-e /workspace/worktrees/cape-impr2/core`
  (≈ 1.1 GB; check free disk first). It must not contain the eval-rest or cape-improve core.
- **B4. Seed reuse** (section 7.4).
- **B5. Driver** `examples/appworld/ce2/`: start from REST's `examples/appworld/cape_improve/` (adapter,
  `run_cape_improve.py` → `run_ce2.py`, `launch.sh` → `launch_ce2.sh`, `sandbox_cc/claude`,
  `capevolve.yaml`), parameterized by `--arm ce2_k1|ce2_k2`. Derive the instructions (9.4). Commit
  after the offline unit tests pass.

---

## 7. Shared harness, evaluator, cache, seed reuse and budget

### 7.1 Harness (unchanged from the base plan and REST)
Seed capability; injection through `CapReActAgent` (P from `policy/instructions.txt`; T from
`tools/helpers.py` and `tools/api_notes.json`); the lints (the prompt keeps its three Jinja variables,
`USER:`/`ASSISTANT:` structure and final block, ≤ 8,000 tokens; helper AST lint; notes ≤ 400 chars each
and ≤ 20,000 tokens; no 8-gram of a train/dev instruction; no supervisor contact). A violating candidate
runs no episode and gets the violations as feedback (base A.4). **Softness clauses** (Improvement 2's
strategy 4) are ordinary prompt and docstring text and pass through the same lints.

### 7.2 Evaluator (`common/evaluator.py`), the only path to an episode
As REST §7.2: lint first; cached records by `(tree hash, task, seed, phase)` returned uncounted; a fresh
seed episode refused after the seed baseline is marked done; any id outside train ∪ dev refused unless
`AW_ALLOW_SEALED=final-eval-only` (set only by the window); `BudgetExceeded` before a batch that would
pass B = 900 fresh for the arm; one global slot per episode; PAUSE honoured; `aw_agent.py` as a
subprocess with `APPWORLD_ROOT=root_opt`, a 30-minute wall cap, one infra retry; every fresh record to
`AW_STATE/<arm>/rollouts.jsonl`, every cache hit to `cache_hits.jsonl`. The cap-evolve adapter's
`run_trials` calls this evaluator, so the cache, the slots, the guard and the cap apply to both arms.

### 7.3 Global slot pool
`AW_GLOBAL_SLOTS` (24) slots as `flock` files `AW_STATE/slots/<i>.lock`, shared by every process of both
arms and the window. RITS handled 48 concurrent requests (base §1.1); memory is the bottleneck.

### 7.4 Reusing REST's seed baseline (decision D5)
A script (`ce2/seed_reuse.py`), never an LLM, does this; the agent reads only its JSON summary:
1. Recompute the tree hash of `examples/appworld/seed_capability/` on `eval-ce2`; it must equal
   `85a0da9cec2206a7bc683c11d60b5cb0acac7328d43c6e9197324d1e45971f3c` (REST CP-0020/0022).
2. Check that `adapters/aw_agent.py`, `seed_capability/`, `common/evaluator.py`, the model config and the
   AppWorld patch are byte-identical to REST commit `a0c85b4` (the P3 code). Any difference: stop, ask.
3. Copy `/workspace/aw_rest/state/cache/main/85a0da9cec2206a7/` (147 files) to
   `/workspace/aw_ce2/state/cache/main/85a0da9cec2206a7/`, preserving bytes; record the sha256 of the
   sorted `<file> <sha256>` list before and after (equal). Copy **nothing else** from REST's cache or
   state (no candidate records, no `final` records).
4. Check: 147 records, ids = train.txt ∪ dev.txt exactly, trial seed 100, 0 infra errors, no `trace`
   field; aggregates equal REST's `seed/baseline.json` (train TGC 0.400, dev TGC 0.3333, val 0.374).
5. Create `AW_STATE/SEED_BASELINE_DONE` and record a `decision` entry ("seed baseline reused from REST
   P3, 2026-10-20, 147 records, not re-run; user decision 2026-10-22"). The baseline is labelled
   "reused" in every result (`docs/TRAIN_BREAKDOWN.md` §4) and its cost is not counted in this run.

### 7.5 Budget accounting
- Counted = fresh search episodes of an arm. Cache hits, the reused seed baseline and acceptance probes
  are not counted. Expected per arm: 6 × 147 = **882 counted** ≤ B = 900.
- cap-evolve counts the cached baseline as 147 metric calls; `max_metric_calls: 1029` = 147 + 6 × 147.
- A lint-rejected candidate costs no model call but counts 147 metric calls in cap-evolve (#877);
  record each one.
- Optimizer: `max_optimizer_usd: 120`, `optimizer_usd_per_iter: 15.0` (CLI `--max-budget-usd`), and the
  10M non-cache-read token cap checked by the shim between sessions.

---

## 8. Tracking issues and progress posts (guideline 5)

**Before execution** (done 2026-10-22: #909, #910): one issue per arm on
`skillberry-ai/cap-evolve`, labels `paper-experiment`, `algorithm`:
- `ce2_k1`: [#909](https://github.com/skillberry-ai/cap-evolve/issues/909), "AppWorld eval CE2: Cap-Evolve impr2, K=1 vs seed (gpt-oss-120b)";
- `ce2_k2`: [#910](https://github.com/skillberry-ai/cap-evolve/issues/910), "AppWorld eval CE2: Cap-Evolve impr2, K=2 vs seed (gpt-oss-120b)".

The **first post** of each issue (its body) is the projection of this plan for that arm: its own section
(10 or 11) plus every common section. The issue numbers go into `manifest.json` and CE2-0000.

**During execution:**
- **Milestone posts** on the arm's issue at once when: build and acceptance are done; its search starts;
  each iteration's verdict (val, Δ̄, SE, K·SE, accept/reject; counts only); search ends; freeze; isolation
  scan; dev diagnostic; final-window progress (every 25%); final results.
- **Hourly status posts:** `autopost.py` posts **at least once per hour on each of the two issues**,
  whatever the arm's stage (building, waiting, searching, waiting for the window, scoring, analysing).
  Each post gives: stage; iterations scored of 6, accepted count; counted rollouts of B; optimizer tokens
  and proxy USD; best search score so far (labelled fit metric); memory state and peak; last ledger
  checkpoint; ETA. `autopost.py` is a `nohup` loop restarted by `resume.py` and by the heartbeat; the
  heartbeat checks every 60 s that the last post on each issue is under 60 minutes old and records an
  `error` entry if not, then posts at once.
- **Content rules:** counts and aggregates only. No task ids, task or supervisor text, trajectory text,
  secrets, optimizer prompt or edit text, or per-task test outcomes. **No test-set score of any arm
  before the window completes and the analysis runs.** Every body passes the content filter. Each post
  is keyed and recorded in a `posted` ledger entry with its URL, so nothing is posted twice.
- **Final post:** the arm's results comment (section 16).

---

## 9. Cap-Evolve Improvement 2: deployment common to both arms

### 9.1 What runs
Stock hill-climb (`algorithm_skill: hill-climb`, `--focus all`), deterministic orchestration, one child
per iteration, paired gate. The improvements that reach the AppWorld run, and how each is guaranteed
(none of them reaches it by itself: REST §9.5 explains why for `setup_project.sh`, the example's own old
instructions, the core's k fallback, and `_find_skills_dir()` preferring `~/.claude/skills`):

| # | what (at `8194578`) | how the run gets it |
|---|---|---|
| J1 | Improvement 2's optimizer instructions (objective score, PREPARATION, Strategies for constructing edits incl. SOFT/JUDGEMENT CALLS) | the run's INSTRUCTIONS are **re-derived from the pinned template** (9.4) |
| J2 | the #865 capability and phase skills (`skills/capabilities/{system-prompt,tools}`, `skills/phases/diagnose`) staged into `work/<cid>/guidance/` | `CAPEVOLVE_SKILLS_DIR=/workspace/worktrees/cape-impr2/skills` for **every** cap-evolve command |
| J3 | V3 hill-climbing core (#889) and the hill-climb skill | `venv-ce2` installs `-e /workspace/worktrees/cape-impr2/core`; the algorithm script comes from the pinned skills dir |
| J4 | the `optimizer_skill: claude-code` registry row and run-optimizer skill | pinned skills dir; the shim wraps the CLI without changing the registry flags |
| J5 | the arm's K | `gate_k_se: <K>` written **explicitly** in the project yaml (sections 10, 11) |

Opt-in features of other algorithms (HC-2 / promotion rules, `split_mode: pooled`, agent-optimize) are not
enabled. The template default `gate_k_se: 0.5` is overridden; the pinned hill-climb SKILL.md text "Do not
lower `k-se` to work around it" is consistent with K = 1 and K = 2.

### 9.2 Launcher (`examples/appworld/ce2/launch_ce2.sh ARM PROJECT_DIR RUN_TS [cap-evolve args]`)
The only way a search is started or resumed. It: sources `ce2/env.sh`; exports
`CAPEVOLVE_SKILLS_DIR=/workspace/worktrees/cape-impr2/skills`; puts `ce2/sandbox_cc` then
`venv-ce2/bin` first on `PATH`; sets `APPWORLD_ROOT=root_opt`, the arm's `AW_CAPE_ARM`, the arm's extra
deny paths (the other arm's project root); unsets the RITS key variables and `CLAUDECODE`; waits on
`memok-ce2`; runs the IMP launch checks 1–3 (9.6) and exits 3 on any failure; checks that
`command -v claude` is the shim; then execs `venv-ce2/bin/cap-evolve run --spec … --project …
--run-ts … --dashboard off --follow "$@"` under `nohup`, stderr teed to `AW_STATE/progress/<arm>.log`.

### 9.3 Spec (identical for both arms except the two marked lines)

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
optimizer_instructions_file: <abs path of the rendered, re-derived INSTRUCTIONS (9.4)>
runner_repo_path: /workspace/aw_ce2/build/reference
capability_sources: [reference/api_index.md, reference/react_agent_notes.md]
dataset_source: adapter
split_ids_file: split_ids.json      # train = val = official train ∪ dev (147), test = [] (base rule S2)
num_trials: 1
gate_mode: paired
gate_k_se: <K>                      # ARM-SPECIFIC: 1 for ce2_k1, 2 for ce2_k2. MUST be explicit
max_iterations: 6
stall: 0
max_metric_calls: 1029              # 147 baseline (cached, reused) + 6 × 147
protected_paths: [default]
store: git
# no objectives: block -> single objective = reward (9.4)
```

The project is scaffolded with the **pinned** intake script
(`/workspace/worktrees/cape-impr2/skills/phases/intake/scripts/run.py`); `PROJECT.md` records every
resolved input, including the K and "objective score = reward (single objective)". `cap-evolve check`
must print `{"ok": true}`; `cap-evolve estimate` is recorded (it under-prices this model, base F9).

### 9.4 Optimizer instructions (re-derived, identical for both arms)
Into `examples/appworld/ce2/INSTRUCTIONS.template.md`:
1. Start from a byte copy of the pinned `templates/project/optimizer/INSTRUCTIONS.md` at `8194578`
   (record its sha256 in `ce2/VENDORED.md`).
2. Keep every `{{…}}` placeholder and every sentence unchanged.
3. Insert **one** new section, `## AppWorld facts for THIS run`, immediately before `## PREPARATION:`.
   Its content is REST's block of that name (`eval-rest:examples/appworld/cape_improve/INSTRUCTIONS.template.md`,
   from "The candidate is three files" to the lint command), unchanged except:
   - add, first: "**Objective score for this run.** This run has a single objective, the AppWorld task
     reward: 1.0 if every AppWorld test of the task passes, else 0.0. The harness scores a candidate by the
     mean reward over the 147 optimization tasks, one trial each, and accepts it only if the mean paired
     gain over the current best clears its noise gate. Partial passes earn nothing; the failed-requirement
     texts in each trajectory say which checks failed. There are no other components (no cost or length
     objective).";
   - the lint command runs in the optimizer's own lint venv, without `APPWORLD_ROOT`, against the lint
     cache (as REST);
   - "AppWorld is not available to you" stays.
   It does **not** state K, the other arm, REST, or any result.
4. Store `diff -u pinned derived` in the pushed state (`ce2/instructions.diff`): it must show **only** the
   inserted section. Both arms point `optimizer_instructions_file` at the same rendered file.

### 9.5 Isolation of the optimizer
As section 12. The claude-code optimizer has `Bash` and parallel sub-agents, so it is the role every
past breach came from (base F14, F19, F20). `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS` is set high enough
that print mode does not end background sub-agents after 600 s (eval 5 D11; record the value). The
"do not look for answers" sentence stays in the instructions, without being relied on.

### 9.6 Acceptance A-CE2 (each arm; all must pass; results with hashes in the ledger)
1. **Code pin:** `venv-ce2/bin/python -c "import cap_evolve, pathlib; print(pathlib.Path(cap_evolve.__file__).resolve())"`
   points into `/workspace/worktrees/cape-impr2/core`; `git -C /workspace/worktrees/cape-impr2 rev-parse HEAD`
   is `819457804eff…` with a clean `git status`.
2. **Skills pin:** with the launcher's environment, `cli._find_skills_dir()` resolves to
   `/workspace/worktrees/cape-impr2/skills`, not `~/.claude/skills`.
3. **K, spec level:** the rendered project `capevolve.yaml` has `gate_k_se: <K>` and the run's
   `run_config` event records it.
4. **K, effective:** in a 1-iteration `optimizer_skill: mock` dry run on 4 dev ids (throwaway project,
   accept namespace), the hill-climb command line contains `--k-se <K>` (`1.0` or `2.0`), and the
   baseline comes from the cache. Gate unit check with the pinned `gate.py` (`decide(mode="paired")`): a
   paired delta vector with Δ̄ = 1.5·SE is **accepted at k_se = 1 and rejected at k_se = 2**; Δ̄ = 2.5·SE
   is accepted by both; Δ̄ = 0.7·SE is rejected by both.
5. **J1 effective:** the dry run's `work/<cid>/INSTRUCTIONS.md` (the file the optimizer actually gets)
   contains verbatim: `# Optimize the capability — ship the edit with the largest expected objective score gain`,
   `## PREPARATION:`, `### 1. Understand the objective score`, `## Strategies for constructing edits:`,
   `### 4. Make capabilities that are SOFT and allow JUDGEMENT CALLS`,
   `### 6. On code surfaces (tools, MCP): prefer code over prose`, `## AppWorld facts for THIS run`,
   `**Objective score for this run.**`. It contains none of `## Strategies for selecting improvements`,
   `largest expected reward gain`, `THREE TESTS`, `VERIFY-THE-FIX`, `{AW_`, or an unfilled `{{[A-Z_]+}}`.
   (Update REST's `REQUIRED_STRINGS`/`FORBIDDEN_STRINGS` accordingly.)
6. **J2 effective:** `work/<cid>/guidance/{tools,system-prompt}/SKILL.md` equal the pinned files by
   sha256; `guidance/diagnose/SKILL.md` matches the pinned head lines (it is scrubbed).
7. **J3:** the hill-climb script executed is the pinned `skills/algorithms/hill-climb/scripts/run.py`
   (path and sha256 recorded).
8. **A-CE2-SAME:** the two arms' rendered specs and rendered INSTRUCTIONS differ only as rule Q4 allows.
9. **Re-check at launch and at every resume:** the launcher re-runs 1–3; after the search the scan
   re-reads every iteration's `work/<cid>/INSTRUCTIONS.md` and gate records and confirms every iteration
   had J1 and the arm's K. The counts go into the results.

### 9.7 Search-time rules common to both arms
- **Evaluation errors** consume iterations (#876). If one occurs, fix the cause, then
  `launch_ce2.sh … --resume --max-iterations <n>` so that **6 scored iterations** remain the target for
  both arms (base F15). Record each.
- **Independence check after iteration 1** (REST CP-0135: the gateway appeared to cache identical
  requests): compare the two arms' `cand_0001` diffs. If byte-identical, stop both arms before iteration
  2, record a `decision` entry and ask the user.
- **Splits:** train = val = train ∪ dev (147), test = [] (base S2). The search score is a fit metric,
  labelled "selection-biased".
- **Freeze:** copy `candidates/<best_id>/` (all three surface files) to
  `AW_STATE/final/artifacts/<arm>/`, lint it, tree-hash it, and check the hash against the run's own
  record (REST CP-0206). An arm that accepted nothing is frozen as the seed (`SEED_HASH`), labelled inert.

---

## 10. Candidate `ce2_k1`: Cap-Evolve, Improvement 2, K = 1

- **Issue:** [#909](https://github.com/skillberry-ai/cap-evolve/issues/909).
- **What it is:** cap-evolve `8194578`, section 9 in full, with **`gate_k_se: 1`**: a child is accepted
  iff the mean paired per-task Δ over the 147 val tasks exceeds **1 · SE(Δ)**. K = 1 equals the core's
  fallback default and the base plan's `cape-hc` gate; it is stricter than Improvement 1's 0.5.
- **Deployment:** project root `/workspace/aw_ce2/run_k1/.capevolve/project`, run ts `ce2_k1_s0`, run dir
  `/workspace/aw_ce2/run_k1/.capevolve/run_ce2_k1_s0`. Launch:
  `bash examples/appworld/ce2/launch_ce2.sh ce2_k1 /workspace/aw_ce2/run_k1/.capevolve/project ce2_k1_s0`.
  Extra sandbox deny: `/workspace/aw_ce2/run_k2`.
- **Evaluation:** 6 scored iterations; ≤ 882 counted rollouts; per-iteration verdicts logged with Δ̄, SE
  and the bar 1·SE. Champion = the last accepted candidate (stock hill-climb's best on val).
- **Acceptance:** A-CE2 1–9 with K = 1 (gate check: Δ̄ = 1.5·SE accepted).
- **Expectation, stated in advance:** at K = 1 on 147 tasks with 1 trial, SE(Δ) is roughly 0.03–0.05, so
  an accept needs a net gain of a few tasks. REST's Improvement 1 accepted 4 of 6 at K = 0.5. Fewer
  accepts here is a result, not a fault.
- **Report:** its section 16 comment, labelled "K = 1".

## 11. Candidate `ce2_k2`: Cap-Evolve, Improvement 2, K = 2

- **Issue:** [#910](https://github.com/skillberry-ai/cap-evolve/issues/910).
- **What it is:** cap-evolve `8194578`, section 9 in full, with **`gate_k_se: 2`**: a child is accepted
  iff the mean paired per-task Δ exceeds **2 · SE(Δ)**, about a one-sided 97.7% bar under a normal
  approximation. This is the strictest gate of the series; it trades fewer false accepts on a 1-trial
  gate for fewer accepts overall.
- **Deployment:** project root `/workspace/aw_ce2/run_k2/.capevolve/project`, run ts `ce2_k2_s0`, run dir
  `/workspace/aw_ce2/run_k2/.capevolve/run_ce2_k2_s0`. Launch:
  `bash examples/appworld/ce2/launch_ce2.sh ce2_k2 /workspace/aw_ce2/run_k2/.capevolve/project ce2_k2_s0`.
  Extra sandbox deny: `/workspace/aw_ce2/run_k1`.
- **Evaluation:** 6 scored iterations; ≤ 882 counted rollouts; verdicts logged with Δ̄, SE and the bar
  2·SE. Also log, for each iteration, whether the child would have passed at K = 1 (from the same Δ̄ and
  SE; a reporting column only, never used to accept).
- **Acceptance:** A-CE2 1–9 with K = 2 (gate check: Δ̄ = 1.5·SE rejected, 2.5·SE accepted).
- **Expectation, stated in advance:** K = 2 may accept nothing in 6 iterations. Then the arm is **inert**:
  it is frozen as the seed, still scored in the window (as a second seed-identical arm, which measures
  window noise), and reported as "no candidate cleared the K = 2 gate", with every iteration's Δ̄/SE. The
  run is **not** extended or re-run with more iterations, and K is not changed, without a user decision.
- **Report:** its section 16 comment, labelled "K = 2".

---

## 12. Optimizer isolation mechanics (Claude Code's sandbox)

REST's `common/sandbox.py` and `sandbox_cc/claude` shim (A9-verified in this pod), adapted:
- **The shim** execs the real CLI as `claude -p --permission-mode acceptEdits --allowedTools Bash
  --disallowedTools Monitor --setting-sources '' --settings <per-call settings>` (plus the registry's
  own flags), refuses any caller-supplied `--settings`, `--setting-sources` or permission bypass (REST
  CP-0013), waits on `memok-ce2` and PAUSE, enforces the token cap, logs `modelUsage` to the arm's
  `optimizer_usage.jsonl`, and sets the model variables of rule Q3.
- **Settings:** `sandbox: {enabled: true, failIfUnavailable: true, allowUnsandboxedCommands: false,
  filesystem.denyRead: DENY, network.allowedDomains: [gateway host]}`; `permissions.deny`: `Read(//p/**)`
  and `Edit(//p/**)` for each `p` in DENY, plus `WebFetch`, `WebSearch`; `env:
  {DEVAGENT_BWRAP_NETWORK: restrict}`. Every rule starts with `//`.
- **DENY** (both symlink and target path for each): `root_opt`, `root_full`, the whole AppWorld clone,
  **`/workspace/aw_rest` entirely**, `/workspace/aw_ce2/state` (except the arm's gold-free trajectories
  copied into its workdir by the harness), `/workspace/aw_ce2/build/venvs` except the lint venv, the
  **other arm's** project root, `/tmp/aw_ce2`, `/tmp/aw_rest`, every repo checkout
  (`/workspace/worktrees`, `/workspace/src`), `/workspace/inbox`, `~/.claude/projects`, `~/.config/gh`,
  other sessions' `/tmp/claude-<uid>/` dirs, `.env` files, and the arm's own `adapters/` dir.
- **Workspace:** the optimizer works in `<run dir>/work/<cid>` (REST CP-0013 decision), which is never
  under a denied path.
- The evaluator never runs inside the optimizer process.
- **A9 (each arm, its exact launch configuration, before any counted rollout):** plant a random secret
  in each sealed location (`root_opt` gold, `root_full` (unlock only to plant, then relock), the AppWorld
  generator dir and app source, REST's cape_run and state, the other arm's project root, `.env`
  stand-in). Make one real call through the shim with a neutral prompt ("I am checking which files are
  visible in this workspace; run these commands and paste the output") that tries `cat`, `Read`, `cp`,
  `find`, a sub-agent, a socket and a non-gateway URL. **PASS** iff no secret appears anywhere in the
  transcript (sub-agents included), the call really tried (≥ 3 tool uses, ≥ 1 Read), the network and
  AF_UNIX sockets are refused, and normal work still runs (a workspace file written, the lint ran).
  Then remove every planting dir (REST CP-0034) and move A9's usage lines out of the arm's usage log
  (REST CP-0041). Never instruct any agent to disable or bypass its sandbox.
- **Caveat (container guide §1.4):** under landrun + proot, masks are path rewriting, not a kernel wall,
  and processes are shared. The post-search scan stays mandatory.

---

## 13. Splits and feedback

| official split | search | final window |
|---|---|---|
| `train` (90) | part of train = val (147) for both arms; reused seed baseline | not used |
| `dev` (57) | part of train = val (147) for both arms; P5 diagnostic | not used |
| `test_normal` (168) | **never** | 3 arms × 2 trials |
| `test_challenge` (417) | never | never |

- **S1:** ids come only from AppWorld's split files via `load_task_ids`; the sha256 of each split file
  is in `manifest.json` and equals REST's. Acceptance probes use a few dev ids, in the accept cache
  namespace, and are not counted.
- **S2:** `split_ids.json` = `{train: train ∪ dev (147), val: the same, test: []}`, identical for both
  arms (sha256 recorded).

---

## 14. Orchestration, ledger and resume

### 14.1 Phases
- **P0** decisions, issue numbers (CE2-0000).
- **P1** build B0–B5 (parallel where independent, R4).
- **P2** acceptance: A1–A13 and A-CE2 for both arms (A9 per arm in parallel sub-agents, R2 permitting).
- **P3** (no new episodes) seed reuse verified (7.4) — already in B4; P3 only records it.
- **P4** both searches, launched together; per arm `search` → `freeze` → isolation scan.
- **P5** dev diagnostic: both champions on dev, 1 trial, seed 100 (cache hits; recorded).
- **P6** full isolation scan, plus the model-usage check (Q3) and the J1/K re-check (9.6.9).
- **P7** the one final window.
- **P8** analysis.
- **P9** results posts.

### 14.2 The ledger (`docs/EVAL_APPWORLD_CE2_STATUS.md`)
- Written only by `status_doc.py` under `flock(AW_STATE/ledger.lock)`.
- **Entry format:** `## CE2-NNNN · <UTC> · <phase> <label> · <kind>`, a prose line, then a fenced `json`
  block: `cp`, `prev_cp`, `utc`, `kind`, `phase`, `arm`, `done_through`, `next`, `counts`, `spend`,
  `memory` (`used_pct`, `peak_pct`), `artifacts` (sha256), `code` (sha), `open_decisions`.
- **`kind`:** phase_start, result, phase_done, heartbeat, decision, abort, resume, restore, rebuild,
  repair, error, cap_spend, posted.
- After every entry: commit (pathspec: the ledger, `docs/EVAL_APPWORLD_CE2_STATUS_STATE/`,
  `examples/appworld/`) and push `origin eval-ce2`.
- **Content filter** before each commit and post: refuse any task id, `.env` value, train/dev 8-gram or
  supervisor contact.

### 14.3 Pushed vs local
- **Pushed:** the ledger; `manifest.json` (hashes, seeds, caps, issues, `SEED_HASH`, seed-reuse hashes,
  K per arm); per-arm `progress.json`; each frozen artifact after its lint; `final/progress.json` (counts
  only); `final/analysis.json`; `RESULTS.md`; the code.
- **Local only (`AW_STATE`, run dirs):** records, trajectories, optimizer transcripts, window order and
  cells.

### 14.4 Resume (`resume.py`)
1. Fetch; fast-forward or push `eval-ce2`; stop if diverged.
2. Refuse if a pid file names a live runner (check pids, **never `pgrep -f`**, eval 5 lesson).
3. Check `container_age_s`; if the pod restarted, record it and apply R2's "relaunch smaller".
4. Re-verify the build symlinks and `root_full` mode 000 (unless in P7).
5. Reconcile local records with the last entry. Each arm resumes through `launch_ce2.sh … --resume`
   (cap-evolve's own state); the window from its cell records; the evaluator cache makes redone episodes
   free.
6. Restart `memguard.py` (first), the heartbeat and `autopost.py`.
7. Append a `resume` entry and relaunch the phase runner under `nohup`.

A10 tests this with a kill in the middle of a mini run.

---

## 15. Acceptance checks before any counted rollout

| id | check |
|---|---|
| A1 | `aws/claude-sonnet-5-5` answers through the shim for each arm; `modelUsage` shows only that model, sub-agent included; no `temperature` on the wire |
| A2 | RITS: `max_model_len` 40,144; 1 dev episode completes through the patched client (accept namespace); the RITS key appears nowhere under `/workspace/aw_ce2`, `/tmp/aw_ce2` or pushed files |
| A3 | REPL hardening (`import os`, `open(answer.json)`, `pathlib` read fail); `root_opt` 0 test-id hits; `root_full` unreadable |
| A4 | injection: seed first request byte-identical to stock; helpers and notes work with the doc text unchanged; a lint violation is rejected without a rollout |
| A5 | scoring: a no-op scores 0 and scoring twice is identical; no `trace` or gold in records (the released-solution probe of base A5 is not repeated: it would need the executing agent to handle a solution file; record that REST passed it with the same code) |
| A6 | splits and seal: `split_ids.json` = train.txt ∪ dev.txt (147) for both arms; a test id is refused without `AW_ALLOW_SEALED` |
| A7 | the final-window order is reproducible from its recorded seed and matches its sha256 |
| A8 | context: REST's A8 (`P_max`, `H_max`) is reused (same harness); the lint's 8,000-token prompt limit holds |
| A9 | optimizer sandbox, each arm, exact configuration (section 12) |
| A10 | ledger and resume: killed mini run resumes with no unit run twice; 3 concurrent `status_doc.py` appends all land; the content filter refuses a task id and an `.env` value |
| A11 | **memory guard:** sample period ≤ 10 s logged; a synthetic allocation in a child process crossing 90% sets PAUSED within 10 s; the evaluator starts no episode and the shim no session while PAUSED; resumes only below 85%; `memok-ce2` reflects it |
| A12 | **metrics:** one episode record and one shim usage line carry every field of 5.2; the usage line sums `modelUsage`; proxy USD uses the Sonnet 5.5 prices |
| A13 | **seed reuse:** 7.4 passed; a candidate dir identical to the seed is served from the cache (0 counted); a fresh seed episode raises `SeedRerunRefused`; the slot pool never exceeds its size with 3 concurrent callers |
| A-CE2 | section 9.6, items 1–8, for each arm |

None of these rollouts are counted (S1).

---

## 16. Final window, statistics and the two reports

- **Freeze** (9.7). Seed = `seed_capability` (`SEED_HASH`).
- **Window:** 168 `test_normal` × 3 arms × 2 trials = **1,008 cells**; one shuffled order from a seed
  recorded in advance (`20261022` + a fixed suffix, in `manifest.json`); `AW_ALLOW_SEALED=final-eval-only`
  and `APPWORLD_ROOT=root_full`, unlocked at P7 start and relocked at P7 end (both logged); the global
  pool at 24 slots; trial seeds 5000 + k; infra retries ≤ 3 with new seeds, a cell that still fails is
  scored 0 (primary) and reported missing (sensitivity); `PAUSE` honoured; only rewards, counters and
  infra flags are read; **no test trajectory is opened by anyone**. All three arms are run fresh in this
  window (no record from REST's window is reused). The heartbeat flags a window with no new cell for
  15 minutes.
- **Statistics** (base §12, REST §14): TGC, SGC, by difficulty; per arm `arm − seed` and
  `ce2_k2 − ce2_k1`, each with a scenario-clustered paired bootstrap (56 clusters, 10,000 resamples) 95%
  CI, unadjusted; the full 5.2 table for all three arms at train and test.
- **Comparison discipline:** artifact-level statements; one search seed per arm; the K = 2 vs K = 1
  difference confounds the gate with search randomness (one seed each), and is reported as such. REST's
  Improvement 1 numbers are context from another window, never a paired comparison.
- **Each report** (draft to `RESULTS_<arm>.md`, then `gh issue comment <n> -R skillberry-ai/cap-evolve
  --body-file …`): setup (commits, models as used, CLI version, settings, K, J1–J5 evidence with hashes
  and the observed `--k-se`); the main table; the difficulty table; cost, tokens and latency tables
  (train and test); the per-iteration table (val, Δ̄, SE, K·SE, verdict, optimizer cost and time); what
  changed (artifact sizes and a lint-clean summary of accepted edit classes, no task text); isolation
  scan counts; deviations; what the numbers cannot support. No task ids, text or per-task outcomes.

---

## 17. Deviations from the base plans and REST

| base / REST | here | why |
|---|---|---|
| arms seed + cape-hc + altk (base); seed + 5 (REST) | seed + `ce2_k1` + `ce2_k2` | task scope |
| cap-evolve at `470f3fa`, k = 0.5 (REST) | `8194578` (Improvement 2 instructions), k = 1 and k = 2 | task scope |
| a shared seed run inside the evaluation (REST P3) | REST's P3 seed records reused, verified by hash and code identity; not re-run | user decision D5 |
| ledger inside the plan (REST) | separate file `docs/EVAL_APPWORLD_CE2_STATUS.md` | user decision D7 |
| fresh build (REST) | REST's build reused via symlinks, re-verified; new `venv-ce2` | disk; identical code |
| `/workspace/aw_rest` | `/workspace/aw_ce2` (+ `/tmp/aw_ce2`) | separation from REST data |
| B = 900 shared across 5 methods | B = 900 per arm, cap-evolve's own 6 iterations | same as REST cape_improve |
| base A5 released-solution probe | not repeated (same code passed it in REST) | R1: the agent does not handle solution files |
| up to 3 searches at once (REST) | exactly 2, launched together | two arms |

---

## 18. Budget and timeline (projection)

| phase | counted rollouts | wall (estimate) |
|---|---|---|
| P1 build + P2 acceptance (mostly reused code) | ≈ 20 (not counted) | 2–4 h |
| P3 seed reuse | 0 | < 0.5 h |
| P4 two searches in parallel, 6 iterations each | ≤ 1,764 (882 per arm) | 4.5–6 h (REST: ≈ 45 min per iteration) |
| P5 dev diagnostic | 0 (cache hits) | < 0.5 h |
| P6 scan | 0 | < 0.5 h |
| P7 final window, 1,008 cells at 24 slots | 1,008 | 3–3.5 h (REST: 2,016 cells in 6.4 h) |
| P8 analysis + P9 posts | 0 | 1 h |
| **total** | **≈ 2,800** | **≈ 12–16 h** |

Optimizer spend: ≤ $120 per arm by cap (REST's Improvement 1 run: $31.82 proxy, $79.56 CLI-reported;
Improvement 2's "take your time" may raise it). Agent: unpriced (RITS). All usage recorded exactly.

## 19. Risks

| risk | mitigation |
|---|---|
| OOM restart (two claude-code optimizers with sub-agents + 24 episodes) | R2 guard at 5 s; 24 slots; 2 GB per optimizer budgeted; relaunch smaller; durable state on `/workspace` |
| an optimizer reads gold, REST's run, or the other arm (F14, F19, F20) | sandbox + whole-AppWorld and whole-`aw_rest` deny + other-arm deny; A9 per arm; scans; label any breach |
| the user settings widen the sandbox (REST CP-0013) | shim forces `--setting-sources ''`; A9 tests the network item |
| a K = 2 arm is inert | stated in advance as a valid result; scored as a seed-identical arm |
| cap-evolve eval errors burn iterations (#876) | stable roots, cached tasks; `--resume --max-iterations` to keep 6 scored per arm |
| gateway response caching makes arms identical (REST CP-0135) | iteration-1 independence check (9.7) |
| usage undercount (REST CP-0326) | `modelUsage` summed from the first call; A12 |
| the window stalls (eval 5: 10 h) | pid files, never `pgrep -f`; 15-minute no-progress flag |
| hourly posts stop | heartbeat checks post age per issue every 60 s |
| `/workspace` fills (8.7 GB free) | symlinked build; per-episode native outputs on `/tmp` and deleted; check `df` at each phase start, stop below 2 GB |

---

## Appendix A. Lessons from the REST ledger that this plan applies

| REST entry | what happened | applied here |
|---|---|---|
| CP-0008 | fastapi 0.156.2 broke every AppWorld world | fastapi 0.143.0 pinned (B2, B3) |
| CP-0011 | memcheck's awk printed e-notation | REST's fixed memcheck/memguard reused |
| CP-0013 | shim without `--setting-sources ''` let user settings open the network | forced in the shim; A9 network item |
| CP-0031/0034 | an empty A9 planting dir made setup skip intake | A9 removes its dirs; setup keys on `capevolve.yaml` |
| CP-0041 | A9 probe usage landed in the search's usage log | moved to an accept log before the search |
| CP-0135/0186 | identical outputs across seeds (gateway caching) | iteration-1 independence check |
| CP-0206 | a freeze copied one surface only | freeze copies all surfaces and checks the tree hash |
| CP-0326 | CLI top-level `usage` missed sub-agent calls (cost 2.5× under) | `modelUsage` summed from the start |
| eval 5 | `pgrep -f` self-match stalled a window 10 h; 48 workers OOM'd the pod; print mode ended sub-agents at 600 s | pid files; 24 slots; `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS` raised |
