# AppWorld TEST_ABL: the ablation champions, TEST only, 5 trials

Status: **PLAN**, written 2026-10-28. The status ledger is a separate file, **`docs/TEST_ABL_STATUS.md`** on branch
`test-abl` (fork `erezh16/cap-evolve`), appended under an exclusive file lock. This plan is not edited during
execution; findings, repairs and user decisions go into the ledger.

**What this is.** A **test-only** evaluation of the frozen champions of the AppWorld ablation study
(`docs/ABLATIONS.md` and its addendum `docs/ABLATIONS_GATE.md`, ledger `docs/ABLATION_STATUS.md` on `eval-abl`). It
runs **no training of any kind**. It fetches each champion and the unmodified **seed** agent, verifies each byte for
byte, and scores them together on AppWorld's held-out `test_normal` split (168 tasks), with **5 trials per task**. The
ablation study's own final window used 2 trials (seeds 5000 + k).

**Protocol.** This plan executes the protocol of **`docs/TEST_ALL.md`** ("TEST_ALL") with the **ablation competitors**
as its arms (user instruction 2026-10-28). Every rule of TEST_ALL applies here **unless this plan says otherwise**:
its §4 rules R1 to R5 (and through them REST's), §5 (the agent under test), §6 (fetch, verify, lint, no evaluator
cache), §8 (the window), §9 (acceptance T1 to T10), §10 (resume), §11 (analysis), §12 (issues and posts) and §13 to
§16. Section 15 of this plan lists every difference. TEST_ALL's code (branch `test-all`) is the starting point of this
run's code.

**You, the executing agent, have no memory of how these artifacts were made.** Everything you need is in this
document, in TEST_ALL, in the ablation plans and in the sources they name. Where a source and this plan disagree on
a fact, stop, record it in the ledger and ask the user (rule R5).

---

## 0. Scope at a glance

| item | this evaluation |
|---|---|
| arms, window 1 | **7**: the seed + the 6 ready ablation champions (§3): `abl_ref`, `abl_cc_best`, `abl_prompt`, `abl_tools`, `abl_notrace`, `abl_tracescore` |
| arms, window 2 (deferred) | **2**: `abl_nogate`, `abl_naivegate`, the gate-ablation champions. Their searches are still running (started 2026-10-28 11:29 UTC). They join only **when ready** (§3.2), in a second window (user decision 2026-10-28) |
| excluded | `abl_cc`: its champion is byte-identical to the seed (inert); user decision 2026-10-28 |
| benchmark | AppWorld at `42b5bcf3cd334fee33f0c37c02070a9f5807add5`, official split `test_normal` (168 tasks, 56 scenarios; Easy 57 / Medium 48 / Hard 63). `train`, `dev` and `test_challenge` are not scored |
| trials | **5 per task per arm**, trial seeds `7000 + k`, k ∈ {0..4} (as TEST_ALL) |
| window 1 | 7 arms × 168 × 5 = **5,880 cells**, one shuffled order (seed `2026102801`), run once |
| window 2 | 2 arms × 168 × 5 = **1,680 cells**, one shuffled order (seed `2026102802`), the same trial seeds, after window 1 |
| agent under test (every arm) | `openai/gpt-oss-120b-a100` on IBM RITS, `hosted_vllm/` route, reasoning effort `medium`, temperature 0, the official AppWorld simplified ReAct code agent (TEST_ALL §5) |
| optimizer | **none** |
| metrics | per arm: TGC, SGC, by difficulty, pass fraction, the stochasticity statistics of TEST_ALL §11.3; tokens, steps, latency; each ablation − `abl_ref` (primary), each arm − seed, all pairs, scenario-clustered paired bootstrap CIs, Holm |
| isolation | nobody (you, a sub-agent, a person) reads test task data, a test trajectory or any per-task test outcome; only trusted scripts touch them (rule R1) |
| memory | the 5-second memory guard, 90% pause / 85% resume (rule R2) |
| sharing the pod | the gate searches run on this pod. **No test window starts while any gate optimizer is live**, and window 1 starts only after the gate run's own P7 window has finished and relocked `root_full` (§8.1; user decisions 2026-10-28) |
| deliverables | `docs/TEST_ABL_STATE/final/RESULTS.md` + `analysis.json` (pushed); **one new tracking issue per arm** (the seed included): 7 now, 2 more when the gate arms are ready. Each opens with its projected plan, then hourly status, milestones and a results comment (§12) |
| estimated wall time | build + acceptance 2 to 3 h now; window 1 ≈ 23 h at 24 slots; window 2 ≈ 6.5 h (§13) |

---

## 1. Read these first (rule R5)

1. **`docs/TEST_ALL.md`** (this repo, branch `test-abl`): all of it. Then its ledger `docs/TEST_ALL_STATUS.md` on
   `fork/test-all`, every entry of kind `error`, `repair` or `decision`.
2. **`docs/ABLATIONS.md`** and **`docs/ABLATIONS_GATE.md`**: what each arm is, how it was searched and frozen (§3, §10,
   §15 of the base; G2 to G7 of the addendum). And the ledger `docs/ABLATION_STATUS.md` on `fork/eval-abl`: every entry of kind
   `error`, `repair`, `decision`, `abort`, and every `reset`/scan entry of the arms in §3.
3. **`docs/CONTAINER_AGENT.md`**: sub-agent isolation and memory limits in this pod (`~/bin/memcheck`).
4. **The code you run**: branch `test-abl`, created from `fork/test-all`, with `examples/appworld/adapters/` and
   `examples/appworld/common/` taken from `fork/eval-abl`. Those are the harness files that ran the ablation searches and
   their window; the diff against `test-all` only adds the tools-only lint, which is off unless `AW_ABL_TOOLS_LINT=1`.
5. `CLAUDE.md` at the repository root.

---

## 2. Where everything is

| what | where |
|---|---|
| repository | `/workspace/src/cap-evolve.git`; remotes **`fork`** = `erezh16/cap-evolve` (every branch; push here) and **`origin`** = `skillberry-ai/cap-evolve` (**issues only; never push a branch to it**) |
| this run's worktree | `/workspace/worktrees/test-abl`, branch `test-abl` (pushed as `fork/test-abl`). The other worktrees (`base`, `eval-abl`, `abl-main`) are **read only** for this run |
| AppWorld build | `/workspace/aw_abl/build/` (owned by the ablation run): `appworld/` (`42b5bcf` + extra-headers patch), `root_full/` (all data, **mode 000**), `root_opt/` (train + dev), `reference/`, `venvs/venv-aw/`. Used **in place** (`AW_HOME=/workspace/aw_abl`), never modified |
| this run's state | **`AW_STATE=/workspace/aw_abl/state/testabl`** (durable). It is inside the ablation run's `AW_STATE`, which every gate optimizer's sandbox already denies. Scratch: **`/tmp/aw_abl/testabl`**, also denied to them |
| RITS credentials | `/workspace/worktrees/base/.env` (`RITS_URL`, `RITS_API_KET`). **Never print, copy or commit it.** The episode worker reads it itself |
| issue CLI | `gh`, logged in as `erezh16`; issues on `skillberry-ai/cap-evolve` |
| Box | `rclone`, remote `eval-data:`, folder `eval-data:appworld/` (read only: `rclone copy` only) |
| free disk | `/workspace` ≈ 9.9 GB free (stop below 2 GB) |

---

## 3. The arms

All champions were searched with the same agent under test (`openai/gpt-oss-120b-a100` on RITS, medium, temperature 0,
the AppWorld ReAct agent at `42b5bcf`) and the same optimizer (`aws/claude-sonnet-5-5`), on AppWorld's train ∪ dev (147
tasks, 1 trial), with B = 882 counted rollouts each. Cap-evolve arms ran cap-evolve `main` `75b3bcd`. An artifact has
up to three surfaces here: `policy/instructions.txt` (P), and `tools/helpers.py` + `tools/api_notes.json` (T).
`memory/` was sealed in every ablation arm.

### 3.1 Window 1 (ready)

| # | arm id | name | ablated factor | issue of its search | surfaces searched / changed vs seed | local path (first) | Box path (second; under `eval-data:appworld/`) | expected hash (rule S) |
|---|---|---|---|---|---|---|---|---|
| 0 | `seed` | seed agent | none: the unmodified AppWorld ReAct agent | — | none / none | `/workspace/worktrees/eval-abl/examples/appworld/seed_capability/` | (not needed) | `85a0da9cec2206a7bc683c11d60b5cb0acac7328d43c6e9197324d1e45971f3c` |
| 1 | `abl_ref` | Cap-evolve full (reference) | nothing: full cap-evolve, gate K = 0.2 | #930 | P + T / P + T | `/workspace/worktrees/eval-abl/docs/ABLATION_STATUS_STATE/abl_ref/artifact/` | `2026-10-25-appworld-capevolve-abl-full-75b3bcd-gptoss120b-sonnet55-qualified/champion/` | `54a4f3799ae887761849d5b96e7da0f0e0e4939000ac18c528c60b5d652790c2` |
| 2 | `abl_cc_best` | Claude code, best evaluated candidate | no cap-evolve: plain Claude Code; the best candidate it evaluated (the session's own named best) | #931 | P + T / P + T | `/workspace/worktrees/eval-abl/docs/ABLATION_STATUS_STATE/abl_cc_best/artifact/` | `2026-10-26-appworld-capevolve-abl-plainclaudecode-75b3bcd-gptoss120b-sonnet55-qualified/abl_cc_best/frozen_artifact/` | `a2b6434e76a0109310d94d88fb193a0ece2435e98d0a12d443b6cc4a6f31ca71` |
| 3 | `abl_prompt` | Cap evolve prompt only | edit surface = the system prompt only | #932 | P / P | `/workspace/worktrees/eval-abl/docs/ABLATION_STATUS_STATE/abl_prompt/artifact/` | `2026-10-25-appworld-capevolve-abl-promptonly-75b3bcd-gptoss120b-sonnet55-qualified/champion/` | `f979201fc17b5e55725b5032b411a486af837b470997a1bbfb40a818ba850eaa` |
| 4 | `abl_tools` | Cap evolve tools only | edit surface = the tools only | #933 | T / T (notes only) | `/workspace/worktrees/eval-abl/docs/ABLATION_STATUS_STATE/abl_tools/artifact/` | `2026-10-25-appworld-capevolve-abl-toolsonly-75b3bcd-gptoss120b-sonnet55-qualified/champion/` | `d78dcf6138cd9f41c9ec819aaa43c0c78f6b68bdc983d04058ba64b8731c0434` |
| 5 | `abl_notrace` | Cap evolve no traces | proposer gets reward + evaluation feedback, no traces | #934 | P + T / P + T | `/workspace/worktrees/eval-abl/docs/ABLATION_STATUS_STATE/abl_notrace/artifact/` | `2026-10-26-appworld-capevolve-abl-notrace-75b3bcd-gptoss120b-sonnet55-qualified/champion/` | `973ebcb4af6b3bddc83a597c6eedb12e65c03a7da34a4b81fba01c63da9723c8` |
| 6 | `abl_tracescore` | Cap evolve traces and score only | proposer gets traces + reward only, no evaluation feedback | #935 | P + T / P + T | `/workspace/worktrees/eval-abl/docs/ABLATION_STATUS_STATE/abl_tracescore/artifact/` | `2026-10-26-appworld-capevolve-abl-tracescore-75b3bcd-gptoss120b-sonnet55-qualified/champion/` | `c2da5909d55fac51bdc26ef678b53d302c2184869a144182db3a6431ff28327c` |

**Hash rule.** Every arm uses **rule S** (TEST_ALL §3): `evaluator.tree_hash(dir)`, the sha256 of
`json.dumps(sorted((path, text)))` over `policy/instructions.txt`, `tools/helpers.py`, `tools/api_notes.json`,
`memory/playbook.md` (an empty playbook counts as absent). The expected values are the ablation run's freeze hashes
(`docs/ABLATION_STATUS_STATE/manifest.json` `freeze.tree_sha256` and each `FREEZE.json`). The planner (2026-10-28)
recomputed all seven from the local paths; each matches. None of these artifacts has a `memory/retrieval.json`, so rule S
identifies each of them uniquely. Nevertheless, TEST_ALL §6.3 applies unchanged: the window never goes through the
evaluator cache, and it identifies arms by directory and by hash.

**Excluded on purpose, do not add:** `abl_cc` (the plain Claude Code session's final working directory; inert, equal
to the seed byte for byte; user decision 2026-10-28). Do not add any non-ablation champion either (TEST_ALL's
competitors).

### 3.2 Window 2 (deferred until ready)

| # | arm id | name | ablated factor | issue of its search | surfaces |
|---|---|---|---|---|---|
| 7 | `abl_nogate` | Cap evolve no gate | no acceptance gate (`gate_k_se: -100000`) | #938 | P + T |
| 8 | `abl_naivegate` | Cap evolve naive gate | naive gate, Δ̄ > 0 (`gate_k_se: 0`) | #939 | P + T |

**"Ready" means all of these, read from the ablation ledger (counts and flags only):** the arm's search ended; its
champion was frozen (a `FREEZE.json` and a `freeze.tree_sha256` entry pushed on `fork/eval-abl`); its `reset` check
passed; its isolation scan reported no breach; **and** the gate run's own final window (ABLATIONS_GATE G7, 672 cells)
has completed and `root_full` is mode 000 again. Until then, the two arms get no issue, no hourly post and no cell. Once
both are ready, the executing agent:
1. adds them to the profile (`WINDOW2_ARMS`) with their expected hashes (rule S, from the pushed freeze), local path
   `eval-abl:docs/ABLATION_STATUS_STATE/<arm>/artifact/` and the Box path if a backup exists;
2. opens their two issues (§12.1) and starts their hourly timers;
3. fetches, verifies and lints them (§6), and runs T4 and T5 for them;
4. after window 1 completes, runs window 2 (§8.2).

If one gate arm is ready and the other is not, wait, and post the reason on the ready arm's issue. If the gate run is
aborted, or a gate arm is labelled "isolation breach", stop and ask the user.

**The arms are not equally treated, and the report says so** (§12.3). Each ablation contrast mixes the ablated factor
with search randomness: one search seed per arm. This window compares **artifacts** under one test condition.

---

## 4. Mandatory execution rules

TEST_ALL §4 (rules R1 to R5) applies in full, with this run's paths. **Every sub-agent you spawn receives the text
of this section and of TEST_ALL §4, verbatim, in its prompt.** Differences:

### 4.1 Rule R1: no one sees test data

- **Sealed set**: as TEST_ALL §4.1, with this run's paths: `/workspace/aw_abl/build/root_full/**`,
  `root_opt/data/tasks/**`, `appworld/{generate,src/appworld/apps,data,experiments/outputs}/**`;
  **`/workspace/aw_abl/state/testabl/final/records/**`, `…/testabl/final/order.json`, `…/testabl/final2/records/**`,
  `…/testabl/final2/order.json`**, the copied caches `…/testabl/{lint_cache,publish_cache}.json`, `…/testabl/fetch/**`;
  the ablation run's own `state/final/**` and `state/cache/**`; `/tmp/aw_abl/**`; every `.env`; `~/.config/gh`; and other
  sessions' transcripts.
- **Deny rules.** This session runs in `/workspace/worktrees/base`, and its
  `.claude/settings.local.json` holds the ablation run's 40 rules. In B0 (2026-10-28) **12 rules were added**, and none
  removed: `Read`/`Edit` of `/workspace/aw_abl/state/testabl/{final/records/**, final/order.json, cache/**,
  lint_cache.json, publish_cache.json, fetch/**}`. B1 adds `final2/records/**` and `final2/order.json`. The backup of
  the file before the change is `settings.local.json.pre-testabl-20261028`. The same rules go into
  `/workspace/worktrees/test-abl/.claude/settings.local.json`, for any session started there. The ablation rules
  already deny `/workspace/aw_abl/state/final/**`, `cache/**` and `/tmp/aw_abl/**`. They leave
  `/workspace/aw_abl/state/testabl/progress/**` and `…/testabl/final/artifacts/**` readable, and those must stay
  readable.
- **Gate optimizers.** The gate searches' optimizer sandboxes deny `/workspace/aw_abl/state` and `/tmp/aw_abl`, so
  everything this run writes lies outside their view. A test window unlocks `root_full`, so **no test window runs
  while a gate optimizer session is live** (§8.1).
- `root_full` stays **`chmod 000`** except while one of this run's windows runs. Scripts that need the test ids or
  difficulties (the order, the analysis) unlock it only for the read and relock it at once. Check it is 000 after every
  window, after every crash, and before the gate run's P7.
- Nothing is published that contains a task id, task or supervisor text, a train/dev 8-gram, a trajectory, a secret
  or a per-task test outcome. Every commit and post passes `status_doc.violations()`.

### 4.2 Rule R2: memory

As TEST_ALL §4.2, with this run's own guard instance (`memguard.py` with `AW_STATE=/workspace/aw_abl/state/testabl`).
It samples the same container cgroup as the ablation run's guard. Each run's episodes honour their own guard's `PAUSE`,
and both guards trip at the same watermarks. Before every process launch and sub-agent spawn, run `memcheck` and
`memok-testabl`. A window starts at **24 global slots**, and only when no gate search or gate window is running (§8.1).
Never go above 32. Keep the 1,800 s episode wall cap.

### 4.3 Rule R3: ledger and resume

As TEST_ALL §4.3. Ledger **`docs/TEST_ABL_STATUS.md`** on branch **`test-abl`**, entry ids **`TB-NNNN`**, written only by
`status_doc.py` under `flock(/workspace/aw_abl/state/testabl/ledger.lock)`. Every entry is committed and pushed with
**`git push fork HEAD:test-abl`** (`AW_REMOTE=fork`; never `origin`, never `--force`, always an explicit refspec).

### 4.4 Rule R4 and 4.5 Rule R5

As TEST_ALL §4.4 and §4.5. In particular: stop and ask when a source disagrees with this plan, when a choice could
favour one arm, or when anything is surprising.

---

## 5. The agent under test (identical for every arm)

TEST_ALL §5 unchanged: model `hosted_vllm/openai/gpt-oss-120b-a100` at `$RITS_URL/gpt-oss-120b-a100/v1`, reasoning
`medium`, temperature 0, `max_completion_tokens` 6000, `max_steps` 50, `max_output_length` 60,000, 100,000 completion
tokens per task, a 30-minute wall cap per episode, the hardened REPL, `random_seed = 7000 + k`.
`adapters/aw_agent.py` is not changed. `AW_ABL_TOOLS_LINT` and `AW_ABL_FEEDBACK` are **unset** in every process of this
run: they affect only search-time linting and the optimizer's feedback, never an episode.

---

## 6. The artifacts in the window

- **Fetch and verify** (`test_all/fetch_artifacts.py`, profile `testabl`): TEST_ALL §6.1. For each arm, copy the local
  path if it exists **and** its rule-S hash matches; otherwise `rclone copy` the Box path. The scored copy at
  `AW_STATE/final/artifacts/<arm>/` holds only `policy/instructions.txt`, `tools/helpers.py`, `tools/api_notes.json`
  and an empty `memory/`. Record the source, the expected and computed hashes, and the files with their sizes and sha256.
  On any mismatch, stop and ask. The seed–harnesslens identity check of TEST_ALL §6.1 step 5 does **not** apply (there is
  no seed-identical arm).
- **Lint** (`test_all/lint_arms.py`): the shared `lints.lint_candidate()` on every scored copy, with the ablation run's
  lint cache, `AW_ABL_TOOLS_LINT` unset. **Expected: every arm passes** (each was lint-clean at its own freeze). There is
  no disclosed exception (TEST_ALL's D6 concerned ACE). Any failure: stop and ask.
- **No evaluator cache** (TEST_ALL §6.3): every cell goes through `Adapter()._episode`. The arms are identified by
  directory and by hash, re-checked at window start and after every resume.

---

## 7. Build

Every step is idempotent and has one ledger entry.

- **B0. Branch, worktree, guard, issues.**
  - `git -C /workspace/worktrees/base worktree add --no-track -b test-abl /workspace/worktrees/test-abl fork/test-all`.
    Take `examples/appworld/{adapters,common}` from `fork/eval-abl` (§1 item 4). Add this plan, and create
    `docs/TEST_ABL_STATUS.md` with a header and the marker `<!-- CHECKPOINTS BELOW THIS LINE -->`. Then
    `git push fork HEAD:refs/heads/test-abl`, and check with `git ls-remote fork test-abl test-all eval-abl` that only
    `test-abl` was created.
  - State dirs: `mkdir -p /workspace/aw_abl/state/testabl/{progress,final/records,final/artifacts} /tmp/aw_abl/testabl`.
  - The deny rules of §4.1, plus the T9 probe (done 2026-10-28: a `Read` of a file under `testabl/final/records/` was
    refused, and one under `testabl/progress/` succeeded).
  - `~/bin/memok-testabl` (a copy of `~/bin/memok-abl` reading `/workspace/aw_abl/state/testabl/MEMSTATE.json`).
  - Start the memory guard **first** (`AW_PROFILE=testabl … memguard.py loop --high 90 --low 85 --every 5`), and check
    that `MEMSTATE.json` is fresh within 10 s.
  - Open the **7 tracking issues** of window 1 (§12.1), record their numbers, then start `autopost.py` and the
    heartbeat (§12.2).
  - Ledger TB-0000: decisions D1 to D12 (§14), the issue numbers, host facts.
- **B1. Profile.** `scripts/awtestabl.py` and an `AW_PROFILE=testabl` branch in `scripts/awrest.py`, on top of
  TEST_ALL's: `ARMS` = window 1's 7 arms in §3.1 order, `WINDOW2_ARMS` = () until §3.2's readiness holds,
  `ALL_ARMS` = `ARMS + WINDOW2_ARMS`, `REF_ARM = "abl_ref"`, `LEDGER_ID = "TB"`, `EVAL_NAME = "TEST_ABL"`,
  `FINAL_TRIALS = 5`, `FINAL_SEED_BASE = 7000`, order seeds 2026102801 / 2026102802, and hourly offsets (§12.2).
  `test_abl/env.sh` holds the environment of §2. Every TEST_ALL code path keyed on its 13 arms
  (`harnesslens`, `altk`, `ace`, the 13/10,920/840 constants, `origin` pushes) is generalised or switched for this
  profile; each change is listed in the ledger.
- **B2. Build re-check, read only.** Run `examples/appworld/abl/verify_build.py` (the ablation run's own check, from
  `eval-abl`, with `AW_STATE` of this run): AppWorld `42b5bcf` + patch, fastapi 0.143.0 / pydantic 2.12.5, split
  counts 90/57/168/417, scenarios, difficulties, split sha256s against the ablation manifest, `root_opt` 0 test-id hits,
  `root_full` 000 before and after. Copy the lint cache and the publishing cache from `/workspace/aw_abl/state/`
  byte for byte, by script (sha256 equal, mode 600).
- **B3. Artifacts**: §6.
- **B4. Window and analysis code**: §8, §11.

Commit after each step that changes code, and push to `fork` `test-abl`.

---

## 8. The windows

### 8.1 When a window may start (user decisions 2026-10-28)

A window may start only when all of these hold:
- the build and every acceptance check of §9 have passed and are in the ledger;
- **no gate optimizer session or gate search runner is alive** (the ablation run's pid files under
  `/workspace/aw_abl/state/p4/`, checked by pid, never `pgrep -f`);
- **the gate run's own P7 window has completed**, or the gate run has recorded that it will not run one, and
  `root_full` is mode 000. Window 1 then has the machine to itself;
- `memok-testabl` is OK.

Window 1 therefore starts after the gate run's P7, expected ≈ 21:00 to 23:00 UTC on 2026-10-28. Until then, the hourly
posts report "waiting for the gate run" as the stage. Window 2 starts when window 1 has completed and §3.2 holds.

### 8.2 Cells and runner

- **Window 1 cells:** `[{arm, task_id, trial} for task in test_normal for arm in ARMS for trial in range(5)]`, shuffled
  once with `random.Random(2026102801)` (`window.make_order`), indexed 0 to 5,879. **Window 2:** the same for
  `WINDOW2_ARMS` with `random.Random(2026102802)`, indexed 0 to 1,679, in `AW_STATE/final2/`. Both seeds and both order
  sha256 values go into `manifest.json` before their window's first cell. The order files stay local.
- **Per cell** (TEST_ALL §8 unchanged): one episode in one global slot through `Adapter()._episode(task, <arm dir>,
  seed=trial, root=root_full, workdir=<scratch>, random_seed=7000 + trial)`. The record holds counters and flags only and is
  written atomically. A cell with a record is never re-run. Infra failures are retried up to 3 times. A cell that still
  fails scores 0 (primary) or is dropped (sensitivity).
- `AW_ALLOW_SEALED=final-eval-only`, `root_full` unlocked by the runner at start and relocked at the end (both logged),
  24 global slots in this run's own pool (`AW_STATE/slots/`), `PAUSE` honoured, SIGTERM drains. The pid is kept in
  `AW_STATE/RUNNING.pid`.
- Progress: a coalesced ledger entry every 5 minutes (counts per arm only), `final/progress.json` pushed, a milestone
  post on every issue of the window's arms at every 10%.
- **Stall rule:** no new cell for 15 minutes is an `error` entry. Investigate memory, RITS (one `curl` of `/models`) and
  the workers before anything else.
- **Never read** a cell record yourself. Counts come from `progress.json`.

---

## 9. Acceptance before window 1 (P2)

TEST_ALL §9, on **dev ids only**, nothing counted, with these changes:

| id | check |
|---|---|
| T1 | RITS `max_model_len` 40,144; 1 dev seed episode through `_episode` completes; the RITS key appears nowhere under this run's state, scratch or pushed files |
| T2 | REPL hardening (`scripts/check_scoring_isolation.py` with `AW_A5_NO_SOLUTION=1`): `import os`, `open(<answer.json>)` and a `pathlib` read all fail; `root_full` mode 000 |
| T3 | window 1 order: regenerating from the seed gives the same sha256; **5,880** cells; every (arm, task, trial) exactly once; **840** per arm |
| T4 | injection per arm (no model call, one dev task): `seed` byte-identical to the stock first request (23 messages); every arm that changed P has a first request that differs from stock; every arm with helpers has them defined and the notice in the prompt; every arm with notes has a note appended on a doc lookup; no arm has a memory block |
| T5 | context: the 3 arms with the largest first-request token count each complete 1 dev episode without `context_exceeded` |
| T6 | memory guard: this run's guard is fresh at a 5 s period; a synthetic allocation crossing a test watermark sets `PAUSE` within 10 s; a slot cannot be taken while paused (`scripts/accept.py a11`) |
| T7 | ledger: 3 concurrent appends all land with unique numbers; the content filter refuses a task id and an `.env` value (`check_a10.py`, throwaway clone, local bare remote; nothing pushed to GitHub) |
| T8 | resume: a 6-cell mini window on dev ids (2 arms × 3 tasks), SIGKILLed after 2 cells, resumes with 0 cells re-run |
| T9 | deny rules: from this session, a `Read` under `testabl/final/records/` is refused and a `Read` of `testabl/progress/…` and `testabl/final/artifacts/seed/policy/instructions.txt` succeeds |
| T10 | posting schedule: the hourly slots are distinct and 400 s apart (§12.2), survive an `autopost.py` restart, and a dry run prints each arm's next due time |

The gate arms get T4 and T5 for themselves when they join (§3.2). Everything must pass, with results in the ledger,
before a window starts.

---

## 10. Resume (`examples/appworld/test_all/resume.py`, profile `testabl`)

TEST_ALL §10, with remote `fork` and branch `test-abl`: sync (fast-forward or push; stop if diverged); refuse if
`RUNNING.pid` is alive; detect a pod restart (`container_age_s`) and shrink the slots by 25%; re-verify `root_full`
(000 unless a window is next) and every artifact's hash; restart the memory guard, then the heartbeat and `autopost.py`;
append a `resume` entry. If the last entry's `next` is a window **and** §8.1 holds, relaunch the window runner, which
skips cells with records.

---

## 11. Analysis (P4)

`test_all/analyze_all.py` with the testabl profile, run in `venv-aw` as a trusted script, after each window.
Definitions are TEST_ALL §11 unchanged (TGC, SGC, by difficulty, pass fraction, tokens, steps, latency, caps, infra; the
§11.3 stochasticity section: pass-count distribution, stable and flaky shares, pass@k and pass^k for k = 1 to 5,
within-task variance, trial-count sensitivity).

**Comparisons (window 1, within-window):**
- **Primary (5):** each ablation arm − `abl_ref` (`abl_prompt`, `abl_tools`, `abl_notrace`, `abl_tracescore`,
  `abl_cc_best`). Δ TGC and Δ SGC with a scenario-clustered paired bootstrap (56 scenarios, 10,000 resamples,
  `random.Random(0)`), 95% percentile CI, bootstrap two-sided p, **Holm over the 5**.
- **Secondary:** each arm − seed (6); `abl_prompt − abl_tools`; `abl_notrace − abl_tracescore`; all 21 pairs
  (unadjusted, and Holm over the 21); the ranking with its uncertainty.
- **Context ("other window", never a paired comparison):** each arm's TGC in the ablation study's own final window
  (2 trials, seeds 5000 + k; `fork/eval-abl:docs/ABLATION_STATUS_STATE/final/analysis.json`), next to this window's,
  together with this window's TGC computed from its first 2 trials.
- **No within-window noise arm:** `abl_cc` was excluded (D2), so there is no seed-identical arm. The report says so and
  quotes TEST_ALL's `harnesslens − seed` result as context.

**Window 2** (after it runs): the same per-arm metrics for the gate arms; `abl_nogate − abl_ref` and
`abl_naivegate − abl_ref` (primary, Holm over the 2), each gate arm − seed, and `abl_nogate − abl_naivegate`. Gate arm
vs a window-1 arm is a **cross-window** paired bootstrap on the same (task, trial seed) cells, labelled as such. As a
drift check, report the infra-retry and timeout rates of both windows, and flag any rate that differs by more than 2×.

Outputs: `docs/TEST_ABL_STATE/final/analysis.json` and `RESULTS.md` (window 1), and `docs/TEST_ABL_STATE/final2/…`
(window 2). Aggregates only.

---

## 12. Tracking issues and posts: one new issue per arm

### 12.1 Open the issues

- **Window 1 (B0): 7 new issues** on `skillberry-ai/cap-evolve`, one per arm of §3.1, the seed included (user decision
  2026-10-28). **Window 2: 2 more**, opened when the gate arms are ready (§3.2). Never reuse an earlier issue.
- **Title:** `AppWorld TEST_ABL: <name> (<arm id>), test_normal × 5 trials (gpt-oss-120b)`.
- **Labels:** `paper-experiment`, `algorithm`.
- **Body: the plan projected for that arm**, built by `test_all/issue_bodies.py` (profile testabl) from this file,
  never by hand: (1) a header naming the arm, this plan, the ledger, the hourly-post promise, and that no test score is
  posted before the analysis; (2) **this arm's own section**: its row of §3, its source search and issue, what the
  artifact is and is not, the fetch/hash/lint result once known, and what this plan says about it in particular; (3)
  **every common section verbatim**: §0, §1, §3, §4, §5, §6, §8, §9, §11, §12, §13, §14, §15, §16. If a body exceeds
  65,536 characters, shorten only the common sections other than §0 and §3, to pointers.
- Every body passes the content filter. The numbers go into `manifest.json` (`issues`) and the ledger.
- The executing agent **lists the issue numbers to the user** as soon as they are opened (user request 2026-10-28).
- If an issue cannot be opened, stop.

### 12.2 Posts on every issue

TEST_ALL §12.2 applies, with these values:
- **Hourly status on each open issue, at least once an hour**, from build start until its results comment, whatever
  the stage (build, acceptance, waiting for the gate run, window, analysis, results). One process, `autopost.py loop`,
  keeps one staggered timer per arm. Arm *i* (in the order `seed`, `abl_ref`, `abl_cc_best`, `abl_prompt`,
  `abl_tools`, `abl_notrace`, `abl_tracescore`, `abl_nogate`, `abl_naivegate`) owns the offset **i × 400 s**
  (⌊3600 / 9⌋): `seed` :00:00, `abl_ref` :06:40, `abl_cc_best` :13:20, `abl_prompt` :20:00, `abl_tools` :26:40,
  `abl_notrace` :33:20, `abl_tracescore` :40:00, `abl_nogate` :46:40, `abl_naivegate` :53:20. A gate arm's timer starts
  only when its issue exists. The offsets go into `manifest.json` in B0.
- Each hourly post gives: the stage; this arm's cells done of 840, its infra retries and missing cells; its window's
  cells done and an ETA; memory; the last ledger entry. **Counts only: no test score before the analysis.**
- **Milestones** on every issue of the affected arms, sequentially 3 s apart: build and acceptance done (with this
  arm's fetch source, hash check, lint and T4 line); window started; every 10%; window done; results.
- The heartbeat (every 60 s) checks each open issue against its own slot. A post older than 65 minutes is an `error`
  entry naming the arm and triggers a post at once, and a dead `autopost.py` is restarted. `post.py` honours
  `Retry-After` on 403/429.

### 12.3 Results comments

After each window's analysis: one results comment per arm of that window, drafted to
`docs/TEST_ABL_STATE/<arm>/RESULTS.md` by `test_all/report_all.py` (profile testabl). Each holds the setup; this arm's
TGC/SGC with CIs, by difficulty; its Δ vs `abl_ref` (primary, raw and Holm) and vs the seed; its row of the pairwise
matrix; its stochasticity numbers; tokens, steps, latency, infra; its first-ablation-window TGC as context; and the
limits (one search seed per arm; a single window; for the gate arms, the cross-window caveat). Then a one-line
pointer comment on the arm's **search issue** (#930, #931, #932 to #935, #938, #939) linking this run's issue.
Counts and links only.

---

## 13. Budget and timeline (projection)

| phase | episodes | wall (estimate) |
|---|---|---|
| P0 + P1 build and fetch | 0 | 1 to 2 h (from 2026-10-28 ≈ 12:30 UTC) |
| P2 acceptance | ≈ 10 dev episodes | 0.5 to 1 h |
| wait for the gate run's searches, freeze, scans and P7 (§8.1) | 0 | until ≈ 21:00 to 23:00 UTC on 10-28 |
| P3 window 1: 5,880 cells at 24 slots | 5,880 | **≈ 23 h** (TEST_ALL measured ≈ 260 cells/h) |
| P4 analysis + P5 posts, window 1 | 0 | < 1 h; window 1 results **≈ 22:00 to 24:00 UTC on 10-29** |
| gate arms join (§3.2): issues, fetch, T4/T5 | ≈ 4 dev episodes | < 1 h, during window 1 |
| window 2: 1,680 cells | 1,680 | ≈ 6.5 h; gate results **≈ 05:00 to 07:00 UTC on 10-30** |

No optimizer spend. The agent on RITS is unpriced: report agent tokens per arm and "n/a (unpriced)" for cost, never
$0. Spend is reported per provider: RITS only.

---

## 14. Decisions (record in TB-0000)

| id | decision | source |
|---|---|---|
| D1 | test only: no training, search or dev diagnostic; TEST_ALL's protocol with the ablation competitors as arms | user, 2026-10-28 |
| D2 | window 1 = seed + `abl_ref`, `abl_cc_best`, `abl_prompt`, `abl_tools`, `abl_notrace`, `abl_tracescore`; `abl_cc` (seed-identical) excluded | user, 2026-10-28 |
| D3 | the gate arms (`abl_nogate`, `abl_naivegate`) are deferred until ready (§3.2) and run in a second window, after window 1 | user, 2026-10-28 |
| D4 | 5 trials per task, trial seeds 7000 + k (TEST_ALL D4) | TEST_ALL |
| D5 | champions from the pushed local copies first, Box second, each verified by rule S against the ablation freeze hashes | TEST_ALL D5 |
| D6 | the window bypasses the evaluator cache and identifies arms by directory and hash (TEST_ALL D7) | TEST_ALL |
| D7 | one new issue per arm, the seed included: 7 now, 2 when the gate arms are ready; the numbers are listed to the user | user, 2026-10-28 |
| D8 | no window while a gate optimizer is live; window 1 starts after the gate run's own P7 has completed and relocked `root_full` | user, 2026-10-28 |
| D9 | window at 24 slots in this run's own pool, once it has the machine to itself | user, 2026-10-28 (12 slots were approved while sharing; not needed under D8) |
| D10 | state inside the ablation run's denied `AW_STATE` (`/workspace/aw_abl/state/testabl`); 12 deny rules added to the base session's settings, none removed | user, 2026-10-28 |
| D11 | branch `test-abl` from `fork/test-all`, harness files from `fork/eval-abl`, pushed only to `fork` | this plan |
| D12 | primary contrasts: each ablation − `abl_ref`, Holm over the 5 (window 1) and over the 2 (window 2) | ABLATIONS §15, G7 |

If a question comes up that these do not answer, ask the user and record the answer as a `decision` entry.

---

## 15. Differences from TEST_ALL

| TEST_ALL | here | why |
|---|---|---|
| 13 arms: seed + 12 champions of earlier evaluations | window 1: seed + 6 ablation champions; window 2: the 2 gate champions | D1 to D3 |
| one window, 10,920 cells, order seed 2026102501 | two windows: 5,880 cells (seed 2026102801) and 1,680 cells (seed 2026102802) | D3 |
| three hash rules (S, F, B) | rule S for every arm (the ablation run's freeze hash) | §3 |
| ACE memory-lint exception (D6) | none expected; any lint failure stops the run | §6 |
| `harnesslens − seed` noise check | no seed-identical arm (`abl_cc` excluded); TEST_ALL's result quoted as context | D2 |
| arm − seed and all 78 pairs | primary: ablation − `abl_ref` with Holm; secondary: − seed, 21 pairs | D12 |
| own build (symlinks to REST's) at `/workspace/aw_testall` | the ablation run's build in place; state at `/workspace/aw_abl/state/testabl` | the REST build is gone from this pod; D10 |
| pushes to `origin` (then the fork) | pushes to `fork`; `origin` is `skillberry-ai` here | D11 |
| 13 issues, 276 s apart | 7 + 2 issues, 400 s apart | D7 |
| ran alone on the pod | shares the pod with the gate searches: no window while they are live (§8.1) | D8 |

## 16. Risks

| risk | mitigation |
|---|---|
| the gate run's P7 relocks `root_full` under a running window | D8: no window of this run overlaps any gate activity; pid checks before launch |
| a gate optimizer sees test data while `root_full` is unlocked | D8; all this run's state lies under paths their sandbox denies |
| two memory guards on one cgroup | both trip at the same watermarks; each run's episodes honour their own `PAUSE`; under D8 only one run has episodes at a time |
| the gate arms never become ready (abort, breach) | stop and ask; window 1 is unaffected |
| a 23-hour window is interrupted | per-cell records, resume command, pid files, hourly posts |
| results read as a method ranking | the report states the artifact-level limits and one search seed per arm |
| hourly posts stop on some issue | per-issue age check every 60 s, staggered timers, `Retry-After` |
| `/workspace` fills | records are small (≈ 7.6K files × 2 KB); `df` at each phase start; stop below 2 GB |
