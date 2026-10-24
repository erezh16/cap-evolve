# AppWorld TEST_ALL: every evaluated AppWorld champion, one test window, 5 trials

Status: **PLAN**, written 2026-10-24. Nothing below has run. The status ledger is a separate file,
**`docs/TEST_ALL_STATUS.md`**, appended during the run under an exclusive file lock (§4.3). This plan is not
edited during execution; findings go into the ledger.

**What this is.** A **test-only** evaluation. Twelve optimization methods were each already trained (searched) on
AppWorld in earlier evaluations, and each produced one frozen **champion** artifact. This plan runs **no training of
any kind**. It fetches the twelve champions plus the unmodified **seed** agent (13 arms in total), verifies each
byte for byte, and scores all of them together on AppWorld's held-out `test_normal` split (168 tasks), in **one**
shuffled window, with **5 trials per task** (earlier evaluations used 2).

**Why.** Every earlier result came from a different test window, and identical artifacts drifted 4 to 6 points of task
success between windows. One shared window makes the 13 arms directly comparable. Five trials per task also measure
the **stochastic behaviour of the agent model**: how often the same artifact, on the same task, passes in one trial
and fails in another.

**Base plan.** This plan is based on **`docs/EVAL_APPWORLD_REST.md`** (on branch `origin/eval-rest`; "REST"), the
plan of an earlier five-method evaluation in this same container type. Every rule of REST about the **test phase**
(its §4 rules R1 to R5, §5 rules Q1 to Q3, §10 to §14 where they concern the final window, §13 acceptance checks
that concern the window) applies here **unless this plan says otherwise**. REST's training sections (§9 searches,
P3 to P6) do **not** apply: nothing is trained. Section 15 lists every difference from REST.

**You, the executing agent, are a new session with no memory of how these artifacts were made.** Everything you need
is in this document, in REST, and in the sources it names. Where this plan and a source disagree on a fact, stop,
record it in the ledger, and ask the user (rule R5).

---

## 0. Scope at a glance

| item | this evaluation |
|---|---|
| arms | **13**: the seed + 12 champions (§3). No training, no search, no dev diagnostic |
| benchmark | AppWorld at commit `42b5bcf3cd334fee33f0c37c02070a9f5807add5`, official split `test_normal` (168 tasks, 56 scenarios; difficulty Easy 57 / Medium 48 / Hard 63). `train`, `dev` and `test_challenge` are not used |
| trials | **5 per task per arm**, trial seeds `7000 + k`, k ∈ {0, 1, 2, 3, 4} (§6.3) |
| window | 13 arms × 168 tasks × 5 trials = **10,920 episodes (cells)**, one shuffled order, run once |
| agent under test (every arm) | `openai/gpt-oss-120b-a100` on IBM RITS, `hosted_vllm/` route, reasoning effort `medium`, temperature 0, the official AppWorld simplified ReAct code agent (§5) |
| optimizer | **none**: no optimizer model is called anywhere in this plan |
| metrics | per arm: TGC, SGC, by difficulty, pass fraction, and the trial-to-trial stability statistics of §11; tokens, steps, latency; every arm vs the seed and every pair of arms, with paired bootstrap CIs |
| isolation | nobody (you, a sub-agent, a person) reads test task data, a test trajectory or any per-task test outcome; only the trusted scripts of §4.1 touch them (rule R1) |
| memory | the 5-second memory guard of REST rule R2, at 90% pause / 85% resume |
| resumability | the ledger `docs/TEST_ALL_STATUS.md`, appended under `flock`; one command resumes (rule R3) |
| deliverables | `docs/TEST_ALL_STATE/final/RESULTS.md` + `analysis.json` (pushed); **13 new tracking issues, one per arm** (the seed included), each with its projected plan as the first post, hourly status, milestones and a results comment (§12) |
| estimated wall time | **about 38 to 45 h** at 24 global slots (§13) |

---

## 1. Read these first (rule R5)

Read them in full before you write any code or run anything:

1. **`docs/EVAL_APPWORLD_REST.md` on branch `origin/eval-rest`**: sections 0 to 8 and 10 to 17, and every ledger
   entry (section 18) of kind `error`, `repair` or `decision`. Pay most attention to §4 (rules R1 to R5), §5.2
   (metrics), §7 (evaluator, slots), §10 (isolation), §12 (ledger, resume), §13 (acceptance), §14 (final window and
   statistics).
2. **`docs/CONTAINER_AGENT.md`** (any branch): sub-agent isolation and memory limits in this pod. `memcheck` is
   defined there; it is installed at `~/bin/memcheck`.
3. **`docs/BACKUP_BOX.md`** (any branch): how the earlier evaluations were archived to Box (§2 of this plan uses
   the archive).
4. **The code you will run**: branch **`origin/eval-ce3`**, directory `examples/appworld/`. It is REST's harness,
   extended by the two most recent evaluations ("CE2", "CE3"). The files that matter: `adapters/aw_agent.py` (one
   episode), `adapters/adapter.py` (the episode runner, `_episode`, `_memory_block`), `adapters/lints.py`,
   `scripts/awrest.py` (paths, constants, slot pool, memory state), `scripts/status_doc.py` (the ledger writer),
   `scripts/memguard.py`, `scripts/window.py` (the window runner), `scripts/analyze.py` (statistics),
   `scripts/post.py` and `scripts/autopost.py` (issue posts).
5. `CLAUDE.md` at the repository root.

---

## 2. Where everything is

### 2.1 This host

| what | where |
|---|---|
| repository (bare) | `/workspace/src/cap-evolve.git`; remotes `origin` = `git@github.com:erezh16/cap-evolve.git` (the fork; all branches below), `upstream` = `skillberry-ai/cap-evolve` (issues live there) |
| existing worktrees | `/workspace/worktrees/{base, eval-rest, eval-ce2, eval-ce3, cape-impr2, cape-improve, instr02}`: **read only** for you. Do not commit to or check out anything in them |
| AppWorld build | `/workspace/aw_rest/build/` (owned by REST): `appworld/` (clone at `42b5bcf` with the extra-headers patch), `root_full/` (all AppWorld data, **mode 000**), `root_opt/` (train + dev only; not used here), `reference/`, `venvs/venv-aw/` (the Python environment every episode runs in) |
| RITS credentials | `/workspace/worktrees/base/.env` (`RITS_URL`, `RITS_API_KET` — the typo is the real variable name). **Never print, copy or commit it.** The episode worker reads it itself (`AW_ENV_FILE`) |
| issue CLI | `gh`, logged in as `erezh16`; issues are opened on `skillberry-ai/cap-evolve` |
| Box | `rclone`, remote **`eval-data:`** (the evaluation archive), folder `eval-data:appworld/` |
| free disk | `/workspace` about 6 GB free (check `df -h /workspace` first; stop below 2 GB), `/tmp` about 90 GB (an `emptyDir`: it does not survive a pod restart) |

### 2.2 The champions: local storage first, Box second

For each arm, §3 gives **(a)** a local path on this host and **(b)** the same artifact on Box. **Use (a) if it exists
and its hash matches; otherwise fetch (b).** Either way, the copy you score must match the **expected hash** of §3
byte for byte (§6.1). Never edit an artifact. Never fetch from anywhere else.

Fetch from Box with `rclone copy <box path> <local dir>` (never `sync`, `move` or `delete`; never write to Box).

---

## 3. The 13 arms

All twelve champions were trained with the same agent under test (`openai/gpt-oss-120b-a100` on RITS, reasoning
medium, temperature 0, the AppWorld ReAct agent at `42b5bcf`) and the same optimizer model (`aws/claude-sonnet-5-5`),
on AppWorld's official train and dev splits only. They differ in method, in which surfaces they changed, and in
search budget. An artifact is a directory with up to four surfaces:

- `policy/instructions.txt`: the agent's prompt (a Jinja template); the seed's is AppWorld's stock prompt;
- `tools/helpers.py`: plain Python functions defined in the agent's REPL before step 1;
- `tools/api_notes.json`: per-app or per-API notes appended to the API documentation the agent looks up;
- `memory/playbook.md` (one block for every task) **or** `memory/retrieval.json` (a per-task block, keyed by task id):
  inserted before the prompt's final `My name is: … Task: …` block.

| # | arm id | method (evaluation it came from) | surfaces | local path on this host | Box path (under `eval-data:appworld/`) | expected hash (full) | hash rule |
|---|---|---|---|---|---|---|---|
| 0 | `seed` | the unmodified AppWorld ReAct agent | none | `/workspace/worktrees/eval-ce3/examples/appworld/seed_capability/` | (not needed) | `85a0da9cec2206a7bc683c11d60b5cb0acac7328d43c6e9197324d1e45971f3c` | S |
| 1 | `altk` | ALTK-Evolve v1.3.0, retrieval dose (smoke test, 2026-10-13) | M (retrieval) | none | `2026-10-15-appworld-capevolve-hillclimb-gptoss120b-sonnet55-fix-clean/final_window/artifacts/altk/` | `b2b3703744f292128d428e791d3f6d70b5eca3a2572d194b96b6075603f1e131` | B |
| 2 | `ace` | ACE, offline, no ground truth (2026-10-14) | M | none | `2026-10-14-appworld-ace-offline-nogt-gptoss120b-sonnet55-qualified/final_window/artifacts/ace/` | `e92fbff4b652aaaa8cce0e46bd9556b4706141834f1486245d7b9edc919b117f` | F |
| 3 | `gepa` | GEPA v0.1.4, prompt + tools (eval 5, 2026-10-18) | P + T | none | `2026-10-18-appworld-gepa-v014-pt-gptoss120b-sonnet55-qualified/champion/artifact/` | `26403e2c5e50ed9243c750457cb9f317f28970271c00b799f1d9018a1cdeffc6` | F |
| 4 | `skillopt` | SkillOpt `ae2f766` (eval 5) | P + T + M | none | `2026-10-18-appworld-skillopt-ae2f766-m-gptoss120b-sonnet55-qualified/champion/artifact/` | `8314b3340e1c0d8569f3785608186d9eb2cf65782f9be2bc17de0ca94319ca04` | F |
| 5 | `wikiskill` | WikiSkill (re-implementation; eval 5) | P + T + M | none | `2026-10-18-appworld-wikiskill-reimpl-m-gptoss120b-sonnet55-qualified/champion/artifact/` | `3895752eb7b9759b4455aabf9ddde54b27442ad405245ec3272906cfa145b167` | F |
| 6 | `evoskill` | EvoSkill v1.3.0 (eval 5) | P + T + M | none | `2026-10-18-appworld-evoskill-v130-m-gptoss120b-sonnet55-scored/champion/artifact/` | `23f5f8f76cf504aee5eba4edbe4c209c160395f428bb39f11b36799ede22a804` | F |
| 7 | `metaharness` | Meta-Harness `8123cca` (eval 5) | P + T | none | `2026-10-19-appworld-metaharness-8123cca-pt-gptoss120b-sonnet55-qualified/champion/artifact/` | `ea0f2f68e37742b8b45fc2a257ad309fac85ebaf3ed00cf0cf60ee2a7cd0fe16` | F |
| 8 | `harnesslens` | HarnessLens `369a5c8` (REST, 2026-10-20). **Inert**: its search accepted nothing, so its artifact equals the seed (it is a second copy of the seed arm; §11 uses it as a within-window noise check) | none | `/workspace/worktrees/eval-rest/docs/EVAL_APPWORLD_REST_STATE/harnesslens/artifact/` | `2026-10-21-appworld-harnesslens-369a5c8-ptm-gptoss120b-sonnet55-inert-qualified/champion/` | `85a0da9cec2206a7bc683c11d60b5cb0acac7328d43c6e9197324d1e45971f3c` | S |
| 9 | `miprov2` | MIPROv2, DSPy 3.4.1 (REST) | P | `/workspace/worktrees/eval-rest/docs/EVAL_APPWORLD_REST_STATE/miprov2/artifact/` | `2026-10-20-appworld-miprov2-dspy341-p-gptoss120b-sonnet55-qualified/champion/` | `a4ff3a502879f5206e5b32161f244c939635eb7d5bd70be59a8f9af01db6314a` | S |
| 10 | `trace2skill` | Trace2Skill `3d0b52a` (REST) | M | `/workspace/worktrees/eval-rest/docs/EVAL_APPWORLD_REST_STATE/trace2skill/artifact/` | `2026-10-21-appworld-trace2skill-3d0b52a-m-gptoss120b-sonnet55-qualified/champion/` | `a6b03deb2a044ed4c74920d02d6589b2113530ffd9053a947854152a8e4e5b6f` | S |
| 11 | `gepa_full` | GEPA v0.1.4, full mode: prompt + per-app tool descriptions (REST) | P + T | `/workspace/worktrees/eval-rest/docs/EVAL_APPWORLD_REST_STATE/gepa_full/artifact/` | `2026-10-20-appworld-gepafull-v014-pt-gptoss120b-sonnet55-qualified/champion/` | `eb3d11d38bad1193cd20fc480f3d5de3ac04fc5e0bcf7002493bd7ae3187110e` | S |
| 12 | `cape_k02` | cap-evolve "Improvement 2", commit `3db96a0`, hill-climb with gate K = 0.2 (CE3, 2026-10-24) — **the only cap-evolve arm** | P + T | `/workspace/aw_ce3/state/ce3_k02/champion/` (also pushed: `origin/eval-ce3:docs/EVAL_APPWORLD_CE3_STATUS_STATE/ce3_k02/artifact/`) | not yet on Box: if the local copies are gone, check `rclone lsf eval-data:appworld/` for a `…capevolve-impr2-3db96a0-k02…` folder; if there is none, stop and ask | `e0ec3d94752bd3a2f067dfa2522695767d4077888a5f62fa360991c3e04019fb` | S |

**Excluded on purpose, do not add:** cap-evolve's other trained artifacts (the smoke test's `cape-hc`, REST's
`cape_improve` at K = 0.5, CE2's K = 1 and K = 2). The user asked for exactly one cap-evolve arm, K = 0.2. Also
excluded: the smoke test's breached first `cape-hc` run and its discarded attempt 1.

**Hash rules.** The earlier evaluations recorded their artifacts' hashes with three different functions. Verify each
arm with **its own** rule, exactly as written here (all are implemented in `scripts/awrest.py` or below):

- **S** ("surface hash", REST/CE2/CE3): `evaluator.tree_hash(dir)` in `examples/appworld/common/evaluator.py` on
  `origin/eval-ce3`: sha256 of `json.dumps(sorted((path, text)))` over the four surfaces
  `policy/instructions.txt`, `tools/helpers.py`, `tools/api_notes.json`, `memory/playbook.md` (an empty playbook
  counts as absent). It **ignores** every other file, including `memory/retrieval.json`.
- **F** ("full tree", eval 5 and ACE): `awrest.sha256_tree(dir)`: sha256 over every file, sorted by relative path,
  each contributing `relpath + b"\0" + sha256_hex(file) + b"\n"`. Compute it over a copy **without** `FREEZE.json`
  and `README.md` (those were written after the freeze).
- **B** ("binary tree", the smoke test's ALTK): every file sorted by relative path, each contributing
  `relpath + b"\0" + sha256_digest(file)` (the 32 raw bytes, no newline), over the whole directory including
  `memory/README.md` and `memory/render_stats.json`.

The planner (2026-10-24) fetched every Box artifact above and confirmed that each one reproduces its expected hash
under its rule. If one does not match for you, stop and ask.

**The arms are not equally treated, and the report says so** (§12): they were searched with different methods,
budgets and surfaces, and with one search seed each. This window compares the 13 **artifacts** under one test
condition. It does not rank the methods in general.

---

## 4. Mandatory execution rules

Rules R1 to R5 of REST §4 apply in full. **Every sub-agent you spawn receives the text of this section verbatim in its
prompt.** The differences for this plan:

### 4.1 Rule R1: no one sees test data

- **Sealed set:** everything under `root_full/` (all test tasks and gold), every final-window record before the
  analysis step aggregates it, AppWorld's native per-episode output dirs, `ground_truth/`, `answer.json`,
  `solution.py`, `compiled_solution.py`, `evaluation.py`, the task generators (`appworld/generate/`), the app source
  (`appworld/src/appworld/apps/`), `.env`, the gateway token, `~/.config/gh`, and other sessions' transcripts
  (`~/.claude/projects/*` other than your own, `/tmp/claude-<uid>/*` other than your own).
- **Who may touch it:** only trusted scripts that run as separate processes: the episode worker (`aw_agent.py`), the
  window runner, the analysis, and the artifact-verification script (§6.1). They print counts, flags and aggregates,
  never a task id, task text or per-task outcome.
- **You and your sub-agents** never open a sealed file with any tool (`Read`, `Grep`, `Glob`, `cat`, `head`,
  `python -c "open(…)"`, `ls` of a test dir). Claude Code `permissions.deny` rules back this up (§4.1.1).

#### 4.1.1 Claude Code deny rules: what is in place, and what to write

**How they work.** A `permissions.deny` rule such as `Read(//workspace/x/**)` stops **Claude Code's own tools**
(`Read`, `Edit`, `Write`, `Grep`, `Glob`) and, under auto mode, Bash commands that name the path, **in the session
that loaded the settings file**. It does **not** apply to processes that session starts with `nohup`, or to their
children: the window runner, the episode workers, `fetch_artifacts.py`, the analysis and `autopost.py` read and write
sealed paths freely. That split is the design of R1: scripts may touch the sealed set, the LLM may not. Settings load
from `~/.claude/settings.json` (user), `<project>/.claude/settings.json` and `<project>/.claude/settings.local.json`
(the project is the directory the session was started in), `--settings` files, and
`/etc/claude-code/managed-settings.json`.

**What is in place on this host (2026-10-24).**

| settings file | deny rules | covers |
|---|---|---|
| `~/.claude/settings.json` (user) | none | — |
| `/etc/claude-code/managed-settings.json` | none (sets only `sandbox.bwrapPath`) | — |
| `/workspace/worktrees/eval-ce3/.claude/settings.local.json` | 58 | REST's sealed build paths (`root_full`, `root_opt/data/tasks`, `appworld/{generate,src/appworld/apps,data}`), REST's `cape_run`, `state`, `backup`; the same under `/workspace/aw_ce2/build/` and `/workspace/aw_ce3/build/`; CE2's `state/{final,cache}`; `/tmp/aw_ce2`, `/tmp/aw_rest`; the `.env` files |
| `/workspace/worktrees/eval-ce2/.claude/settings.local.json` | 40 | the CE2 subset of the above |
| `/workspace/worktrees/base/.claude/settings.local.json` | 40 | the same as eval-ce2's |
| `/workspace/worktrees/eval-rest/.claude/settings.local.json` | 2 | the `.env` files |

None of these loads for your session unless you start it in one of those worktrees. `test-all` is created from
`origin/eval-ce3` by `git worktree add`, which does **not** copy `.claude/settings.local.json` (it is git-excluded),
so a session started in `/workspace/worktrees/test-all` begins with **no** deny rules until you write them.

**Would they interfere?** Not with any script of this plan (scripts are not subject to them). They would block
**you** in four places this plan needs, so the file you write must leave these paths readable:

1. **REST's state**: `/workspace/aw_rest/state/**` is denied in eval-ce2's and eval-ce3's files. You do not need
   it: B2's `copy_caches.py` reads it as a script.
2. **REST's pushed artifacts**: the local champion paths of §3 rows 8 to 11
   (`/workspace/worktrees/eval-rest/docs/EVAL_APPWORLD_REST_STATE/<arm>/artifact/`) are **not** denied anywhere.
   They hold no test data (they are the frozen artifacts); `fetch_artifacts.py` reads them as a script. Keep them
   readable.
3. **CE3's champion**: `/workspace/aw_ce3/state/ce3_k02/champion/` (§3 row 12) is not denied anywhere today. Keep
   it that way: deny only CE3's `state/final/**` and `state/cache/**` (its test records and episode cache), **not**
   `/workspace/aw_ce3/state/**`, so that you can still list and hash the champion you are about to score.
4. **Root-owned test data under the new state dir**: deny `/workspace/aw_testall/state/final/**` (cell records,
   the order with task ids) but **not** `/workspace/aw_testall/state/progress/**` (logs you read to monitor the run,
   counts only) or `/workspace/aw_testall/state/final/artifacts/**` (the scored copies; you print their hashes and
   sizes). Claude Code evaluates deny rules before allow rules, so carve the artifacts out by **not** denying a
   parent of them: deny `/workspace/aw_testall/state/final/records/**` and `/workspace/aw_testall/state/final/order.json`
   individually instead of `final/**`.

**What to write in B0.** `/workspace/worktrees/test-all/.claude/settings.local.json`, and start your session in that
worktree (or pass the same file with `--settings`). It must contain exactly these `Read(...)` **and** `Edit(...)` pairs
(every path absolute, written with a leading `//`):

- `/workspace/aw_rest/build/root_full/**`, `/workspace/aw_rest/build/root_opt/data/tasks/**`,
  `/workspace/aw_rest/build/appworld/generate/**`, `/workspace/aw_rest/build/appworld/src/appworld/apps/**`,
  `/workspace/aw_rest/build/appworld/data/**` (the targets of the build symlinks);
- the same five under `/workspace/aw_testall/build/` (the symlinks; a rule on a symlink path does not cover its
  target and vice versa, so both are needed);
- `/workspace/aw_rest/state/**`, `/workspace/aw_rest/cape_run/**`, `/workspace/aw_rest/backup/**`,
  `/workspace/aw_ce2/state/final/**`, `/workspace/aw_ce2/state/cache/**`, `/workspace/aw_ce3/state/final/**`,
  `/workspace/aw_ce3/state/cache/**`, `/tmp/aw_rest/**`, `/tmp/aw_ce2/**`, `/tmp/aw_ce3/**` (earlier evaluations'
  test records and caches);
- `/workspace/aw_testall/state/final/records/**`, `/workspace/aw_testall/state/final/order.json`,
  `/tmp/aw_testall/**` (this window's records, order and AppWorld's native outputs);
- every `.env`: `/workspace/worktrees/base/.env`, `/workspace/worktrees/eval-rest/.env`,
  `/workspace/worktrees/eval-ce2/.env`, `/workspace/worktrees/eval-ce3/.env`, `/workspace/worktrees/test-all/.env`;
- `~/.config/gh/**` written as `//home/dev/.config/gh/**`.

Check it in P2 (T9, §9): with your own session, a `Read` of one denied path and one carved-out path
(`/workspace/aw_testall/state/progress/memguard.log`) returns denied and allowed respectively. Do **not** copy the
eval-ce3 file wholesale: it denies `/workspace/aw_rest/state/**` (harmless) but lacks every `aw_testall` path and
`/tmp/aw_ce3`, and it does not protect this window's records.

**The auto-mode classifier** is a separate check from deny rules: in auto mode it has refused, in earlier runs, a
force-push, the creation of a `root_full` symlink, writing a script that copies from REST's state, and a listing of
`root_full`. If it refuses a step this plan needs (most likely B2's symlinks or B3's Box copy), do not work around
it: stop, say which step and why it is needed, and ask the user to run it or to switch permission mode.
- **`root_full` stays `chmod 000`** except while the window runs (P3); the window runner unlocks it at start and
  relocks it at the end, and logs both. Check it is `000` again after P3 and after any crash.
- **No artifact is opened for its content by an LLM** other than what §6.2's lint does as a script. You may print an
  artifact's file sizes, line counts and hashes.
- **Nothing is published** that contains a task id, task or supervisor text, a train/dev instruction 8-gram, a
  trajectory, a secret or a per-task test outcome. Every commit and post passes the content filter of
  `status_doc.py` (`violations()`).
- There is **no optimizer** in this plan, so REST's optimizer sandbox (§10, A9) does not apply.

### 4.2 Rule R2: memory

As REST R2: the guard `memguard.py` (with `AW_STATE=/workspace/aw_testall/state`) samples every 5 s, sets `PAUSE`
at ≥ 90% of the container limit and clears it below 85%; the window starts no new episode while paused; you run
`memcheck` and the memok check (§7, B0) before every process launch and sub-agent spawn. Episode workers use about
0.75 GB each; start at **24 global slots**, never above 32. In the predecessor windows, **one** episode in a few
thousand grew to about 10 GB before the 30-minute episode wall cap killed it (container use rose from 46% to 77%);
the cap is the protection, so keep it at 1,800 s. If the container restarts (`container_age_s` resets), relaunch with
25% fewer slots.

### 4.3 Rule R3: ledger and resume

- Ledger: **`docs/TEST_ALL_STATUS.md`** on branch **`test-all`**, written only by `status_doc.py` under
  `flock(/workspace/aw_testall/state/ledger.lock)`; append-only; every entry committed and pushed with
  `git push origin HEAD:test-all` (always name the branch explicitly: `git worktree add -b … origin/<x>` sets the
  new branch to track `<x>`, and with `push.default=upstream` a bare `git push` would push onto `<x>` — a mistake a
  predecessor made).
- Entry ids **`TA-NNNN`**; format as REST §12.2.
- Cadence: an entry at every phase boundary, acceptance check, decision, error and resume; coalesced window progress
  at most every 5 minutes; a heartbeat after 25 silent minutes.
- One command resumes (§10). A window cell with a record is never re-run.

### 4.4 Rule R4: parallelism

Episodes are the parallel unit, through the global slot pool. Build and acceptance steps may use parallel
sub-agents (each with this section's text, each subject to the R2 check). Sub-agents never spawn sub-agents.

### 4.5 Rule R5: quality over speed

Read the sources first. Check every number and hash against its source. When something is unclear or surprising,
stop, record it in the ledger, and ask the user (`AskUserQuestion`, recommended option first). Report failures
plainly.

---

## 5. The agent under test (identical for every arm)

Unchanged from REST §5.3 and the base smoke-test plan §5.1. `adapters/aw_agent.py` on `origin/eval-ce3` already
implements it; **do not change it**:

- model `hosted_vllm/openai/gpt-oss-120b-a100` at `$RITS_URL/gpt-oss-120b-a100/v1`, header `RITS_API_KEY` from
  `RITS_API_KET`, reasoning effort `medium`, temperature 0, `max_completion_tokens` 6000, `drop_reasoning_content`,
  `use_cache: false`, retries 20 after 15 s;
- AppWorld simplified ReAct code agent at `42b5bcf`, `max_steps` 50, `max_output_length` 60,000 characters,
  100,000 completion tokens per task (enforced by the worker), a 30-minute wall cap per episode;
- `os`, `pathlib`, `io`, `shutil`, `glob` removed from AppWorld's import allowlist; the RITS key removed from the
  environment before the world starts; the gold-bearing `trace` dropped before anything is written;
- the memory block (if any) is inserted before the final `My name is: … Task: …` block, under the heading
  `Guidelines learned from past task attempts:` unless the block already starts with one.

**`random_seed` per trial** goes to AppWorld's agent config (`random_seed = 7000 + k`). Note that the model is served
at temperature 0 and the gateway takes no seed, so the trial seed does not by itself make trials differ; the
earlier windows nevertheless saw the two trials of a task disagree on 19 to 38% of tasks. Measuring that
variability is one of the goals (§11).

---

## 6. The artifacts in the window

### 6.1 Fetch and verify (script, P1)

Write `examples/appworld/test_all/fetch_artifacts.py` (stdlib only). For each arm of §3:

1. If the local path exists, copy it to `/workspace/aw_testall/state/final/artifacts/<arm>/`; else
   `rclone copy eval-data:appworld/<box path> /workspace/aw_testall/state/final/artifacts/<arm>/`.
2. Remove `FREEZE.json`, `README.md` and `capability.diff` **from a scratch copy used for hashing only** (rule F);
   the scored copy keeps exactly the files listed in step 4.
3. Compute the arm's hash with its rule (S, F or B; §3) and compare with the expected value. On any mismatch: the
   script exits non-zero, nothing is scored, and you ask the user.
4. The scored copy contains only the surfaces the harness reads: `policy/instructions.txt`, `tools/helpers.py`,
   `tools/api_notes.json`, and `memory/playbook.md` or `memory/retrieval.json` where present. Record in the
   manifest, per arm: the source used (local or Box path), the expected and computed hash, the rule, the file list
   with sizes and sha256, and the surfaces present.
5. Also verify, as a cross-check: `seed` and `harnesslens` scored copies are byte-identical to each other (rule S
   says they are; confirm file by file).

### 6.2 Lint (script, P1)

Run the shared lint `adapters/lints.py::lint_candidate()` on every scored copy (in `venv-aw`, with
`AW_LINT_CACHE` pointing at the lint cache of §7 B2). Record the result per arm. **Expected:**

- every arm passes, except possibly the memory-size rule: `ace`'s playbook is **55,513 characters / 13,430 tokens**,
  over the lint's 30,000-character limit. ACE's own evaluation capped it by tokens (`M_cap` = 13,500 tokens, by
  its plan's rule `min(30,000, 34,000 − P_max − H_max)`), and it was scored with its own lint (`memory_lint`,
  token-based). **Do not truncate or edit it.** Score it as frozen; record the lint result as a known, disclosed
  exception. In ACE's window its episodes peaked at 32,828 prompt tokens with 0 `context_exceeded`; here any
  `context_exceeded` episode scores 0 and is counted per arm.
- `altk`'s per-task blocks are up to 10,781 characters each (168 blocks), within the limit.
- If any **other** arm fails the lint, stop and ask.

### 6.3 Why the window must not go through the evaluator's cache (important)

`common/evaluator.py`'s cache key is the **surface hash (rule S)**, which ignores `memory/retrieval.json`. The `altk`
artifact has only stock P and T plus a `retrieval.json`, so its surface hash **equals the seed's**. Any code path that
looks artifacts up by surface hash (the evaluator cache, `window.py`'s `_check_frozen` against a manifest of surface
hashes) would treat `altk` as a copy of the seed. The window must therefore:

- run every cell directly through `adapter.Adapter()._episode(task, cdir, seed, root, workdir, random_seed)` — as
  `window.py`'s `Window.run` already does — **never** through `evaluator.evaluate()`;
- identify each arm by its **directory and its own hash (§3 rule)**, recorded in the manifest at freeze, and re-check
  them with the same rules at window start and after any resume (`_check_frozen` must use the per-arm rule, not
  `tree_hash`).

Acceptance check T4 (§9) proves the `altk` memory block reaches the prompt.

---

## 7. Build (P0 to P1)

Every step is idempotent and has one ledger entry.

- **B0. Branch, worktree, guard, issue.**
  - `cd /workspace/worktrees/base && git fetch origin && git worktree add --no-track -b test-all
    /workspace/worktrees/test-all origin/eval-ce3`, then
    `git -C /workspace/worktrees/test-all push origin HEAD:refs/heads/test-all` and
    `git -C /workspace/worktrees/test-all branch --set-upstream-to=origin/test-all`. Check with
    `git ls-remote origin test-all eval-ce3` that **only** `test-all` was created and `eval-ce3` did not move.
  - Copy this plan to `docs/TEST_ALL.md` in the worktree (it is on `cap-evolve-impr2`; copy the file, do not merge
    branches). Create `docs/TEST_ALL_STATUS.md` with a header and the marker `<!-- CHECKPOINTS BELOW THIS LINE -->`.
  - State dirs: `mkdir -p /workspace/aw_testall/{state/progress,launch} /tmp/aw_testall`.
  - The deny rules of §4.1.1 into `/workspace/worktrees/test-all/.claude/settings.local.json` (exactly that list;
    not a copy of eval-ce3's file).
  - `~/bin/memok-testall`: a copy of `~/bin/memok-ce3.py` reading `/workspace/aw_testall/state/MEMSTATE.json`
    (and its two-line shell wrapper, as `~/bin/memok-ce3`).
  - Start the memory guard **first**:
    `cd examples/appworld/scripts && AW_PROFILE=testall AW_HOME=/workspace/aw_testall AW_STATE=/workspace/aw_testall/state nohup python3 -I memguard.py loop --high 90 --low 85 --every 5 &`;
    check `MEMSTATE.json` is fresh within 10 s.
  - Open the **13 tracking issues** (§12.1), one per arm, each with its projected plan as the body, and record the
    13 numbers. Then start `autopost.py` and the heartbeat (§12.2), so hourly status runs from the build on.
  - Ledger TA-0000: decisions D1 to D9 (§14), the 13 issue numbers, host facts (`memcheck`).
- **B1. Profile.** Add `scripts/awtestall.py` and an `AW_PROFILE=testall` branch in `scripts/awrest.py`, following
  the existing `ce2`/`ce3` pattern (read `scripts/awce2.py` and `scripts/awce3.py`): `ARMS` = the 13 arm ids of §3 in
  table order, `CANDIDATES` = the 12 non-seed arms, `ISSUES` = {arm: its own issue number} for all **13** arms
  (the seed included; §12.1), `METHOD_NAMES` (for all 13, the seed as "seed agent"),
  `LEDGER_ID = "TA"`, `EVAL_NAME = "TEST_ALL"`, `FINAL_TRIALS = 5`, `FINAL_SEED_BASE = 7000`, the order seed of §8.
  Write `examples/appworld/test_all/env.sh` (`AW_PROFILE=testall`, `AW_HOME=/workspace/aw_testall`,
  `AW_STATE=/workspace/aw_testall/state`, `AW_SCRATCH_ROOT=/tmp/aw_testall`, `AW_LEDGER_NAME=TEST_ALL_STATUS.md`,
  `AW_BRANCH=test-all`, `AW_REPO=/workspace/worktrees/test-all`, `AW_ENV_FILE=/workspace/worktrees/base/.env`,
  `AW_SESSION_IDS=<your session id>`). Grep the scripts you use for `CE2`, `CE3`, `ce2_`, `ce3_`, `aw_ce2`, `aw_ce3`,
  `K_SE`, `REUSED_WINDOW_ARMS` and remove every CE-specific path from the code paths this plan runs (CE3's window
  joins reused CE2 records; **this window joins nothing**).
- **B2. Build reuse.** `/workspace/aw_testall/build/{appworld, root_full, reference, venvs/venv-aw}` = symlinks into
  `/workspace/aw_rest/build/`. Re-run the read-only build check `examples/appworld/ce2/verify_build.py` adapted to
  this profile: AppWorld HEAD `42b5bcf`, its `git diff` sha256 equals REST's manifest, fastapi 0.143.0 and pydantic
  2.12.5 in `venv-aw`, `test_normal` 168 ids / 56 scenarios / difficulties 57-48-63, split-file sha256 as REST's
  manifest, `root_full` mode 000 before and after. Copy the lint cache and the publishing cache with
  `examples/appworld/ce2/copy_caches.py` (it copies from REST's state; adapt the profile check). Any mismatch: stop.
- **B3. Artifacts:** §6.1 and §6.2.
- **B4. Window and analysis code** (§8, §11).

Commit after each step that changes code (`git commit` with the pathspec `docs/TEST_ALL*`, `examples/appworld/`),
push with `git push origin HEAD:test-all`.

---

## 8. The window (P3)

- **Cells:** `[{arm, task_id, trial} for task in test_normal for arm in ARMS for trial in range(5)]`, shuffled once
  with `random.Random(2026102501)` (`window.make_order`), indexed 0 to 10,919. Recorded in advance: the seed and the
  order's sha256 in `manifest.json` (A7 of REST, §9 T3). The order file itself (it holds task ids) stays local.
- **Per cell:** one episode in one global slot through `Adapter()._episode(task, <arm dir>, seed=trial,
  root=root_full, workdir=<scratch>, random_seed=7000 + trial)`; the record (counters and flags only: success,
  num_tests, pass_count, n_steps, prompt/completion tokens, max prompt tokens, termination, collateral damage,
  complete_task_called, api_errors, trimmed_steps, fs_probe, episode_seconds, attempt) written atomically to
  `/workspace/aw_testall/state/final/records/<idx>.json`; a cell with a record is never re-run.
- **Infra failures** (provider errors after the client's retries, the 30-minute wall cap): retried up to 3 times
  inside the cell; a cell that still fails is scored 0 (primary analysis) and dropped (sensitivity analysis), and
  counted per arm.
- `AW_ALLOW_SEALED=final-eval-only`, `APPWORLD_ROOT`/`AW_APPWORLD_ROOT` = `root_full` (unlocked by the runner at start,
  relocked at the end), 24 global slots, `PAUSE` honoured, SIGTERM stops new cells and lets running ones finish.
- **Runner:** `scripts/window.py final` with the testall profile (13 arms, 5 trials, per-arm hash check of §6.3),
  started under `nohup` with its pid in `AW_STATE/RUNNING.pid` (check pids, **never `pgrep -f`**: a self-matching
  pattern once stalled a window for 10 h). Progress: a coalesced ledger entry every 5 minutes (counts per arm only),
  `final/progress.json` pushed, a milestone post on **all 13 issues** at every 10% (§12.2).
- **Stall rule:** no new cell for 15 minutes → an `error` entry; investigate (memory, RITS reachability with one
  `curl` to `$RITS_URL/gpt-oss-120b-a100/v1/models`, worker processes) before anything else.
- **Never read** a cell record's content yourself during the window. Counts come from `final/progress.json`.

---

## 9. Acceptance before the window (P2)

None of these episodes count. Use **dev** task ids only (`root_opt`), never a test id.

| id | check |
|---|---|
| T1 | RITS: `max_model_len` 40,144 on `/models`; 1 dev episode with the seed completes through `_episode` (REST A2); the RITS key appears nowhere under `/workspace/aw_testall`, `/tmp/aw_testall` or the pushed files |
| T2 | build (B2) and REPL hardening: in `world.execute`, `import os`, `open(<answer.json path>)` and a `pathlib` read all fail (REST A3, `scripts/check_scoring_isolation.py` with `AW_A5_NO_SOLUTION=1`); `root_full` unreadable while the window is not running |
| T3 | order: regenerating it from the seed gives the same sha256; 10,920 cells; every (arm, task, trial) exactly once |
| T4 | **injection per arm**: for each of the 13 arms, render the agent's first request for one **dev** task without calling the model (`aw_agent.py`'s prompt-building path, as `scripts/check_injection.py` does) and record: number of messages, prompt tokens, whether a memory block is present, whether helpers are defined, whether notes are appended. Expected: `seed` and `harnesslens` byte-identical to the stock first request (23 messages); `altk` has a memory block (its `retrieval.json` has entries for test ids only, so for a dev id the block is empty — confirm the lookup by checking that `retrieval.json` has exactly 168 keys and that `_memory_block` returns a non-empty string for one of them, **inside the trusted script, printing only the length**); every arm with M has its block before `My name is:`; every arm with T has its helpers defined |
| T5 | context: for the 3 arms with the largest first-request token count (from T4), 1 dev episode each completes without `context_exceeded`; record max prompt tokens |
| T6 | memory guard: `MEMSTATE.json` fresh, period 5 s; a synthetic allocation in a child process crossing a test watermark sets `PAUSE` within 10 s and a slot cannot be taken while paused (REST A11, `scripts/accept.py a11` with the testall profile) |
| T7 | ledger: 3 concurrent `status_doc.py append` calls all land with unique numbers; the content filter refuses an entry with a task id and one with an `.env` value (REST A10, against a throwaway clone and a local bare remote; nothing pushed to GitHub) |
| T8 | resume: a 6-cell mini window on dev ids (2 arms × 3 tasks), SIGKILLed after 2 cells, resumes with 0 cells re-run |
| T9 | deny rules (§4.1.1): from your own session, a `Read` of `/workspace/aw_testall/build/root_full/data` and of `/workspace/aw_testall/state/final/records/` is refused, and a `Read` of `/workspace/aw_testall/state/progress/memguard.log` and of `/workspace/aw_testall/state/final/artifacts/seed/policy/instructions.txt` succeeds; a `nohup` script reading `root_full` (T1's episode) is **not** blocked |
| T10 | posting schedule (§12.2): the 13 hourly slots are distinct, 276 s apart, and survive a restart of `autopost.py` (it reads them from `manifest.json`); a dry run prints, for each arm, its next due time |

All must pass and be in the ledger before P3.

---

## 10. Resume (`examples/appworld/test_all/resume.py`)

1. `git fetch origin test-all`; fast-forward or push; stop if diverged.
2. Refuse if `AW_STATE/RUNNING.pid` names a live process (check the pid; never `pgrep -f`).
3. If `container_age_s` (from `memcheck`) is shorter than the time since the last ledger entry, the pod restarted:
   record it and set the slot pool 25% smaller (`AW_STATE/slots/SIZE`).
4. Re-verify the build symlinks, `root_full` mode (000 unless the window is next), and every artifact's hash (§6.3).
5. Restart `memguard.py` first, then the heartbeat (`status_doc.py heartbeat`) and `autopost.py` (all 13 issues;
   it posts at once on any issue whose last post is older than 60 minutes).
6. Append a `resume` entry and relaunch the window runner under `nohup`; it skips cells that have records.

---

## 11. Analysis (P4)

`scripts/analyze.py` with the testall profile (adapt: 13 arms, 5 trials, no reused records, no `k2_vs_k1`). Inputs:
the order and the cell records (counts and flags only). Outputs `docs/TEST_ALL_STATE/final/analysis.json` and
`RESULTS.md`, aggregates only.

### 11.1 Primary metrics, per arm

- **TGC** = mean over the 168 tasks of the mean success over the 5 trials; **SGC** = for each trial, the share of the
  56 scenarios whose tasks all pass, averaged over the 5 trials. Both overall and by difficulty (Easy 57 / Medium 48
  / Hard 63).
- Pass fraction (`pass_count / num_tests`), tokens per episode (mean, p50, p90), steps, episode seconds (mean, p50,
  p90), step-cap / token-cap / `context_exceeded` hits, collateral-damage count, infra retries and missing cells.

### 11.2 Comparisons

- **Each arm − seed**, and **every pair of arms** (78 pairs): Δ TGC and Δ SGC with a **scenario-clustered paired
  bootstrap** (resample the 56 scenarios with replacement, 10,000 resamples, `random.Random(0)`), 95% percentile CI.
  Report unadjusted CIs, and also mark which pairwise differences survive a Holm correction over the 78 pairs.
- **Ranking:** the arms ordered by TGC, each with its 95% CI, plus the set of arms not separable from the top arm
  (CI of the difference contains 0).
- **`harnesslens` vs `seed`:** two byte-identical artifacts in one window. Their Δ is a direct measure of the
  window's noise; report it next to every other Δ.

### 11.3 Stochastic behaviour (the 5-trial goal)

Per arm, over its 168 tasks × 5 trials:

- **per-task pass count distribution**: how many tasks pass 0, 1, 2, 3, 4, 5 of 5 trials;
- **stable share**: the share of tasks that pass all 5 or fail all 5; **flaky share**: the rest;
- **pass@k and pass^k** for k = 1 to 5 (pass@k = share of tasks with at least one success in the first k trials,
  averaged over trial orders; pass^k = share with all k successes), the usual "any vs every" reliability curves;
- **within-task variance** of success, averaged over tasks, and the share of TGC's variance that is within-task;
- **trial-count sensitivity**: TGC and the seed-relative Δ computed from the first 1, 2, 3, 4 and 5 trials (trial
  index order), each with its bootstrap CI, so the report shows how much the 2-trial results of earlier evaluations
  could move with more trials;
- **agreement with the earlier windows** (context, never a paired comparison): each arm's earlier test_normal TGC
  (from its own evaluation's pushed results: REST `docs/EVAL_APPWORLD_REST_STATE/final/analysis.json`, eval 5
  `origin/eval5:docs/EVAL_APPWORLD_5_STATE/final/…`, CE3 `origin/eval-ce3:docs/EVAL_APPWORLD_CE3_STATUS_STATE/final/analysis.json`,
  the smoke test and ACE from their Box folders' `final_window/`), shown next to this window's TGC and labelled
  "other window".

Across arms: is flakiness related to the arm's TGC, to difficulty, and to the surface types (P, T, M)?

---

## 12. Tracking issues and posts: one new issue per arm (13)

### 12.1 Open the 13 issues (B0, before any other build step)

Open **13 new issues** on `skillberry-ai/cap-evolve`, one per arm of §3, the seed included. Do not reuse any earlier
evaluation's issue.

- **Title:** `AppWorld TEST_ALL: <Method name> (<arm id>), test_normal × 5 trials (gpt-oss-120b)`, for example
  `AppWorld TEST_ALL: ACE (ace), test_normal × 5 trials (gpt-oss-120b)` and
  `AppWorld TEST_ALL: seed agent (seed), test_normal × 5 trials (gpt-oss-120b)`.
- **Labels:** `paper-experiment`, `algorithm`.
- **Body: the plan projected for that arm** (the "projected plan for starters"). Build it with a script
  (`examples/appworld/test_all/issue_bodies.py`) from this file, never by hand, so all 13 stay consistent:
  1. a header naming the arm, the evaluation (`docs/TEST_ALL.md` on `cap-evolve-impr2`, ledger
     `docs/TEST_ALL_STATUS.md` on `test-all`), and a note that progress is posted at least hourly and that no test
     score is posted before the window completes;
  2. **this arm's own section**: its row of §3 (method, source evaluation, surfaces, local and Box source, expected
     hash and rule), what the artifact is and is not, and anything this plan says about it in particular (`seed`:
     the baseline every Δ is measured against; `harnesslens`: inert, seed-identical, the window's noise check;
     `altk`: the per-task retrieval memory and §6.3; `ace`: the memory-lint exception D6; `cape_k02`: the only
     cap-evolve arm, D3);
  3. **every common section**, verbatim: §0, §1, §3 (the full table, so each issue shows the other 12 arms), §4,
     §5, §6, §8, §9, §11, §12, §13, §14, §15, §16.
  If a body exceeds GitHub's 65,536-character limit, shorten only the common sections, to a pointer at the plan
  file, keeping §0, §3 and this arm's section in full; record that in the ledger.
- Every body passes the content filter (`status_doc.violations()`) before it is posted.
- Record the 13 issue numbers in `manifest.json` (`issues: {arm: number}`) and in TA-0000. The profile's `ISSUES`
  (B1) is this map.
- If an issue cannot be opened, stop: the run does not start with fewer than 13 issues.

### 12.2 Posts on every issue

Every post goes through `scripts/post.py` (keyed, recorded as a `posted` ledger entry with its URL, never posted
twice, content-filtered).

- **Milestones**, on all 13 issues (one post per issue per milestone, with that issue's arm named): build and
  acceptance done (with this arm's fetch source, hash check and lint result, and its T4 injection line); window
  started; every 10% of the window; window done; results.
- **Hourly status**, on **each of the 13 issues**, at least once an hour, from build start until that issue's results
  comment is posted, whatever the stage. **The 13 hourly posts are spread evenly across the hour, one "timer" per
  arm**, so at most one hourly post goes out at a time (GitHub's secondary rate limit punishes bursts of writes, and
  REST's `autopost.py` posted every candidate in the same loop pass):
  - Arm *i* (0 to 12, in §3 table order) owns the **offset** `i × 276 s` into each hour (276 = ⌊3600 / 13⌋):
    `seed` at :00:00, `altk` at :04:36, `ace` at :09:12, `gepa` at :13:48, `skillopt` at :18:24, `wikiskill` at
    :23:00, `evoskill` at :27:36, `metaharness` at :32:12, `harnesslens` at :36:48, `miprov2` at :41:24, `trace2skill`
    at :46:00, `gepa_full` at :50:36, `cape_k02` at :55:12 (UTC).
  - Record the 13 offsets in `manifest.json` (`hourly_offset_s: {arm: seconds}`) in B0, before the first post, so a
    restart keeps them.
  - **One process**, `autopost.py loop` (rewrite REST's loop accordingly), holds the 13 timers: it wakes every 20 s
    and, for each arm whose slot `floor(now / 3600) × 3600 + offset` has passed and which has not posted in that
    hour, builds **that arm's** status and posts it. It posts at most one hourly status per wake-up, so a backlog
    after a pause drains one post at a time, 20 s apart. It writes each arm's last post time to
    `AW_STATE/autopost.json` atomically after each post.
  - The **heartbeat** (every 60 s) checks each issue against its own slot: an arm whose last post is older than
    60 minutes **plus 5 minutes of grace** gets an `error` entry naming the arm, and `autopost.py` is restarted if its
    pid is dead. Do not use REST's `check_ages(every)` unchanged: it assumes all issues post together.
  - **Milestone posts** are not on the timer: they go out when the milestone happens, but `post.py` sends them
    **sequentially with 3 s between issues** (13 posts ≈ 40 s), and a milestone post on an issue counts as that hour's
    status for it only if it carries the status fields below.
  - `post.py` retries on HTTP 403 or 429: wait for `Retry-After` (or 60 s if absent), then retry, up to 5 times; a
    post that still fails is an `error` entry, never dropped silently.
  - Each hourly post gives:
  - the stage (build, acceptance, window, analysis, results);
  - **this arm's** cells done of **840** (168 × 5), and its infra retries and missing cells so far;
  - the whole window's cells done of 10,920, and the ETA at the last hour's rate;
  - memory (used %, peak, guard state);
  - the last ledger entry (id, time, phase).
  Counts only: **no test score of any arm is posted or written to the ledger before the window is complete** and the
  analysis has run.
- **The heartbeat** checks every 60 s that the last post on **each** of the 13 issues is under 60 minutes old; for any
  that is not, it records an `error` entry naming the arm and posts at once (REST §8).

### 12.3 Results comments

After P4, one results comment per issue (13), drafted to `docs/TEST_ALL_STATE/<arm>/RESULTS.md` by
`examples/appworld/test_all/report.py` from `final/analysis.json` and the pushed state only:

- **every arm:** the setup (commits, models, the 13 arms with sources, hashes and surfaces); **this arm's** TGC and
  SGC with 95% CIs, by difficulty, its rank among the 13 with uncertainty, and its Δ vs the seed and vs every other arm
  (the row of the pairwise matrix, unadjusted and Holm); **this arm's** stochasticity numbers (§11.3: pass-count
  distribution, stable and flaky shares, pass@k and pass^k, trial-count sensitivity); its agent tokens, steps,
  latency and infra counts; its earlier window's TGC as context, labelled "other window";
- **the seed's issue:** the seed's own numbers and its stochasticity, the full ranking table of all 13, and the
  `harnesslens` − `seed` noise check;
- **`harnesslens`'s issue:** the same noise check, stated as the result for this arm;
- the full tables (all arms, the 78-pair matrix) are in the combined `docs/TEST_ALL_STATE/final/RESULTS.md`, linked
  from every comment;
- every comment closes with the deviations and what the numbers cannot support (one search seed per method; methods
  differ in surfaces and search budget; a single window). Content filter applies.

Then, as a courtesy, a one-line pointer comment on each arm's **earlier** evaluation issue (smoke test #804 for
`altk`; the ACE evaluation's issue as named in its Box folder's `README.md` and `posts/`; eval 5 #881–#885; REST
#897–#901; CE3 #913), linking this run's issue for that arm. Counts and links only.

---

## 13. Budget and timeline (projection)

| phase | episodes | wall (estimate) |
|---|---|---|
| P0 + P1 build and fetch | 0 | 1 to 2 h |
| P2 acceptance | ≈ 10 dev episodes | 0.5 to 1 h |
| P3 window, 10,920 cells at 24 slots | 10,920 | **≈ 36 to 42 h** (CE2's window ran 1,008 cells in 3.5 h ≈ 290 cells/h; arms with long memory blocks and extra steps may be slower) |
| P4 analysis, P5 posts | 0 | < 1 h |
| **total** | **≈ 10,930** | **≈ 38 to 45 h** |

No optimizer spend. The agent model on RITS is unpriced: report agent tokens per arm, "n/a (unpriced)" for cost,
never $0. Plan for the window to span two days; the hourly posts and the resume procedure exist for that.

---

## 14. Decisions (record in TA-0000)

| id | decision | source |
|---|---|---|
| D1 | test only; no training, search or dev diagnostic | user, 2026-10-24 |
| D2 | 13 arms: seed + the 12 champions of §3, including the inert HarnessLens (a seed-identical arm) | user, 2026-10-24 |
| D3 | exactly one cap-evolve arm: CE3's K = 0.2 champion (`e0ec3d94…`) | user, 2026-10-24 |
| D4 | 5 trials per task, trial seeds 7000 + k; one window | user, 2026-10-24 |
| D5 | champions from local storage first, Box (`eval-data:appworld/`) second, each verified by its own hash rule | user, 2026-10-24 |
| D6 | ACE's 55,513-character playbook is scored as frozen, over the 30,000-character lint limit, disclosed (its own evaluation capped it by tokens) | this plan, §6.2 |
| D7 | the window bypasses the evaluator cache and identifies arms by directory and per-arm hash (§6.3) | this plan |
| D8 | branch `test-all` from `origin/eval-ce3`, worktree `/workspace/worktrees/test-all`, state `/workspace/aw_testall`, scratch `/tmp/aw_testall` | this plan |
| D9 | 13 new tracking issues, one per arm including the seed; each opens with its projected plan, then hourly status, milestones and a results comment (§12) | user, 2026-10-24 |

If a question comes up that these do not answer, ask the user and record the answer as a `decision` entry.

---

## 15. Differences from REST

| REST | here | why |
|---|---|---|
| plan + ledger in one file | plan `docs/TEST_ALL.md`, ledger `docs/TEST_ALL_STATUS.md` | the same split as CE2/CE3 |
| P1 to P9 with five searches | P0 build, P1 fetch/verify/lint, P2 acceptance, P3 window, P4 analysis, P5 posts | test only (D1) |
| 6 arms (seed + 5 champions trained in the run) | 13 arms, champions from earlier runs (local or Box) | D2, D5 |
| 2 trials per task, seeds 5000 + k, 2,016 cells | **5 trials**, seeds 7000 + k, **10,920 cells** | D4; new seeds so no cell repeats an earlier window's seed |
| order seed 2026102007 | 2026102501 | a new window |
| artifacts frozen from the run, identified by surface hash | fetched, verified by each source's own hash rule; arms identified by directory | §6.3: the surface hash cannot tell `altk` from the seed |
| one tracking issue per candidate (5; the seed had none) | one **new** issue per arm, **13** (the seed included), each with its projected plan, hourly status, milestones and a results comment; plus a pointer comment on each arm's earlier issue | D9 |
| optimizer sandbox, A9, opt_llm, budget caps | not applicable | no optimizer |
| `arm − seed` only; "no ranking between candidates" | `arm − seed`, all 78 pairs (unadjusted and Holm), and a ranking with its uncertainty, still labelled artifact-level | the point of one shared window |
| stability = share of tasks whose 2 trials agree | the §11.3 stochasticity section | 5 trials |

## 16. Risks

| risk | mitigation |
|---|---|
| a 40-hour window is interrupted (pod restart, RITS outage, session end) | per-cell records, the resume command, pid files, hourly posts; RITS outages are infra retries; a long outage is a stall (§8), wait and resume |
| one runaway episode exhausts memory | the 30-minute wall cap, the memory guard, 24 slots (§4.2) |
| an artifact cannot be fetched or does not match its hash | stop and ask; never substitute another artifact |
| `altk` silently scored as a seed copy | §6.3, check T4 |
| ACE overflows the context window on some test tasks | scored 0 as `context_exceeded`, counted and reported per arm (D6) |
| results read as a method ranking | the report states the artifact-level limits (§12) |
| hourly posts on 13 issues stop for some arms | the heartbeat checks each issue's last-post age every 60 s and posts at once (§12.2); `autopost.py` loops over all 13 arms, the seed included |
| 13 posts per milestone and 13 per hour trip GitHub's rate limits | hourly posts on 13 staggered timers, 276 s apart (§12.2); milestones sent sequentially, 3 s apart; `post.py` honours `Retry-After` on 403/429; a post later than 65 minutes is an `error` entry, never skipped silently |
| deny rules block a needed step, or fail to block a sealed path | §4.1.1 gives the exact list and the carve-outs; T9 checks both directions before the window |
| `/workspace` fills (records are small; about 11K files × ~2 KB) | check `df -h /workspace` at each phase start; stop below 2 GB |
