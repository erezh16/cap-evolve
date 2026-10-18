# AppWorld eval 5: five optimization candidates vs the seed agent

Status: **PLAN**, written 2026-10-17. Nothing in the execution sections has run yet. This document is
**both the plan and the status ledger** (guideline 7.3): the plan is sections 0–14; the execution
ledger is appended below section 15 during the run, under an exclusive file lock.

This plan evaluates **five optimization candidates**, each as an independent arm scored against the
**same unmodified seed agent**, on the **AppWorld** benchmark, reusing the harness, splits, feedback
tier, isolation ideas and final-window machinery of two sibling plans that have already run:

- `docs/EVAL_SMOKE_TEST.md` — "the base plan" (cap-evolve hill-climb vs ALTK-Evolve), with its
  execution log (Appendix A), results (Appendix B) and fix (Appendix C). **Read it in full.**
- `docs/EVAL_SMOKE_TEST_FIX.md` — "the fix doc" (what to re-run and the optimizer-isolation fix).
  **Read it in full.**
- A third sibling, `docs/EVAL_SMOKE_TEST_ACE.md` on branch `erezh-eval2-ace` ("the ACE plan"),
  added the **checkpoint ledger / resume** machinery this plan adopts. The executing agent should
  read its sections 10 (orchestration, ledger, resume) and 4 (environment).

Every rule of the base plan is kept unless this document says otherwise. Section 13 lists every
deviation. The five candidates are:

| arm | method | reference implementation | pin studied |
|---|---|---|---|
| `gepa` | GEPA (reflective prompt evolution) | https://github.com/gepa-ai/gepa | PyPI `gepa==0.1.4` (tag `v0.1.4` = `8b0ce6c`) |
| `skillopt` | SkillOpt (self-evolving skill document) | https://github.com/microsoft/skillopt | `main` @ `ae2f766` (post-`v0.2.0`: `openai_compatible` backend) |
| `wikiskill` | WikiSkill (skills + wiki co-evolution) | https://github.com/kenhuangus/wikiskill | HEAD `0363334` (third-party reimpl.; see 7.3) |
| `evoskill` | EvoSkill (skill discovery from failures) | https://github.com/sentient-agi/EvoSkill | tag `v1.3.0` (`1d7dc3e`), HEAD `36f6f04` |
| `metaharness` | Meta-Harness (end-to-end harness search) | https://github.com/stanford-iris-lab/meta-harness | HEAD `8123cca` (no tags/releases) |

The expected deliverable of the whole evaluation is **one results comment per candidate on that
candidate's tracking issue** (section 5 / guideline 5), plus the five frozen artifacts and this
ledger. The main repository for issues is **`skillberry-ai/cap-evolve`** (the `origin` fork
`erezh16/cap-evolve` has issues disabled).

---

## 0. Scope

| item | this evaluation |
|---|---|
| methods compared | each of `gepa`, `skillopt`, `wikiskill`, `evoskill`, `metaharness` against the **same** unmodified seed. The five candidates are **not** compared against each other as a ranking (one search seed each; see 12). |
| optimizer model, every candidate | `aws/claude-sonnet-5-5`, through the gateway in `~/.claude/settings.json` (`ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_CUSTOM_HEADERS` with `x-context-guru-token`). This is decision D1 of the base plan, carried over. **Guideline 6.3.** |
| agent under test, every candidate and the seed | `openai/gpt-oss-120b-a100` on RITS (`hosted_vllm/` route, reasoning effort `medium`, temperature 0), credentials from `<repo>/.env` (`RITS_URL`, `RITS_API_KET`). **Guideline 6.3.** |
| benchmark | AppWorld, **official splits only** (`data/datasets/{train,dev,test_normal,test_challenge}.txt`). Search uses `train` (90) and `dev` (57); results come from `test_normal` (168); `test_challenge` is **not** used. Section 9 gives the split roles. |
| search seeds | 1 per candidate (guideline 6.1: the same for all). |
| trials | **1 trial per task during search; 2 trials per task in the final window; 1 search seed per experiment** — identical for every candidate (base decision D3; verified against `capevolve.yaml num_trials: 1` and `final_window.py TRIALS=2`). **Guideline 6.1.** |
| counted-rollout cap | **B = 900 counted search rollouts per candidate** and **optimizer ≤ 10M non-cache-read tokens per candidate** (#804; the same caps the ACE sibling used). Counted rollouts are reported beside every result; budgets are **not** matched exactly across methods (each method's natural loop differs), and that is disclosed (section 12). |
| final scoring | `test_normal`, 2 trials per task, for **6 arms** (seed + the five candidate champions), in **one interleaved window** (section 12). |
| metrics (every arm) | **reward** (→ TGC, SGC), **cost** (optimizer tokens + proxy USD; agent tokens unpriced on RITS), **tokens** (prompt/completion per episode), **latency** (per-episode seconds, phase wall time). Collected identically for all. **Guideline 6.2.** |
| parallelism | sub-agents and worker pools sized by `memcheck` (section 11 / `docs/CONTAINER_AGENT.md`), never by `nproc`. At most a few sub-agents at once. **Guideline 7.4.** |
| isolation | search-time `root_opt` (no test files); `root_full` `chmod 000` during search; REPL hardening (base F1); gold-free feedback tier F1; agentic optimizers confined by **Claude Code's own sandbox** (section 8 — the base plan's namespace wrapper does **not** work in this pod); gold-leaking proposer inputs de-fanged per candidate; post-search isolation scan. **Guideline 7.1.** |
| resumability | this document is appended with a checkpoint ledger (section 10) under `flock`; a single command resumes from the last checkpoint; the most recent in-flight step is an acceptable loss (guideline 7.3). |

---

## 1. What was read and verified (2026-10-17)

### 1.1 Sources read

The base plan and the fix doc in full (including base Appendices A–C); the ACE sibling plan
(`erezh-eval2-ace:docs/EVAL_SMOKE_TEST_ACE.md`) and its ledger, state and results; the committed
AppWorld example `examples/appworld/` on this branch (`adapter.py`, `aw_agent.py`, `lints.py`,
`capevolve.yaml`, `final_window.py`, `analyze.py`, `scan_isolation.py`, `make_roots.py`,
`make_splits.py`, `make_reference.py`, `optimizer/INSTRUCTIONS.template.md`, the `sandbox/` wrapper
and templates, the `altk/` driver); `docs/CONTAINER_AGENT.md`; `docs/HOLDOUT_PROTOCOL.md`;
`CLAUDE.md` (model-provider order); `ci/benchmarks/README.md` and `ci/benchmarks/model_catalog.txt`
(gateway/provider identities); issue #804 and its full update history (base plan's results). For
each candidate, the reference repository was cloned (read-only, under `/tmp/eval5_research/`, never
executed) and read together with its paper(s)/blog(s) — results in section 7.

### 1.2 Facts about this host that the plan depends on (probed 2026-10-17)

- **This is a fresh OpenShift pod.** `/tmp/aw_eval` from the base run is **gone**; there is no
  `.venv`, and (at probe time) no `.env` (the user has since added `.env` with `RITS_URL`,
  `RITS_API_KET`). The whole environment must be rebuilt from scratch (section 4). `python3` is
  3.11; `uv` 0.13.0 is at `/usr/local/bin/uv`.
- **`memcheck`:** `limit_MB=32768`, `cpu_limit=8`, `swap_max=0`, `memory.oom.group=1` (a pod: an
  OOM kills the **whole container** and restarts it — base/`SUBAGENT.md` cap-evolve incident).
  Disk: `/workspace` is a 20 GB volume (~17 GB free) that **persists**; `/tmp` is a larger
  `emptyDir` that does **not** survive a restart. So durable state lives on `/workspace`.
- **The base plan's optimizer-isolation namespace wrapper (`examples/appworld/sandbox/claude`)
  cannot run here.** `unshare -rm` fails with `ENOSYS` (the pod refuses user namespaces), so the
  wrapper's `unshare` step cannot start. This is the base plan's F17 condition.
- **Claude Code's own sandbox *does* work here** (via `devagent-bwrap` → landrun + proot; managed
  setting `sandbox.bwrapPath=/usr/local/bin/devagent-bwrap`). Probed on real `claude -p` calls with
  `aws/claude-sonnet-5-5`, I verified that under `sandbox.enabled=true`,
  `failIfUnavailable=true`, `allowUnsandboxedCommands=false`:
  - `filesystem.denyRead` of a planted directory makes it read as **empty** to Bash (`cat`/`ls`/`cp`
    all return "No such file or directory" or an empty listing) and the **Read tool is refused**;
  - `network.allowedDomains: []` with `DEVAGENT_BWRAP_NETWORK=restrict` **blocks outbound** to
    non-allowlisted hosts (curl/urllib get a proxy **403**); local file writes and `python3` still work;
  - creating an **AF_UNIX socket is blocked** (`Operation not permitted`), so a sandboxed command
    cannot drive tmux / a broker to escape;
  - `sandbox.excludedCommands` lets a **named trusted script** (e.g. the episode runner) still read
    gold while the agent's own commands cannot — the mechanism we use so the evaluator reads
    `root_full` while an agentic optimizer running in the same process cannot.
  This is exactly the mode the fix doc said to use "on any machine where A9 passes in `sandbox`
  mode". **It passes here**, so this plan uses Claude Code's sandbox, not the namespace wrapper
  (section 8).
- **Landlock alone (`landrun`) also confines an unsandboxed `claude`'s *own* file tools** (Read/
  Grep): an outer `landrun --ro`/`--rwx` allowlist makes planted files unreadable even to the
  Read tool. It is kept as a defence-in-depth option (section 8.4), but the primary mechanism is
  Claude Code's sandbox because it also blocks AF_UNIX sockets and gives network restriction.
- **Gateway cyber-safety classifier.** `aws/claude-sonnet-5-5` through the gateway **refuses**
  prompts that read like "try hard to exfiltrate this planted secret by every means" (`[cyber]`
  safeguard; also tripped by instructing a sub-`claude` to retry with a named bypass flag). The
  isolation acceptance check (A9) must therefore use a **neutral framing** ("I am checking which
  files are visible in this workspace; run these commands and paste the output"), which reproduces
  the same access attempts without tripping the classifier (verified). Never instruct any agent to
  disable or bypass its sandbox.
- **Model id note.** The installed Claude Code (2.1.270) prints a harmless
  `[claude-code:unrecognized_model]` line for `aws/claude-sonnet-5-5` and assumes a 200K context
  window; set `CLAUDE_CODE_MAX_CONTEXT_TOKENS` or append `[1m]` only if an optimizer needs the
  larger window (none here do). The CLI still completes (exit 0).
- **Gateway facts carried from the ACE sibling (findings G1/G2), to apply to every candidate whose
  optimizer calls the gateway directly (not via the `claude` CLI):**
  - **G1:** the gateway **rejects `temperature`** for `aws/claude-sonnet-5-5` (HTTP 400). Omit it
    (model default). Do not retry deterministic 4xx (other than 429).
  - **G2:** some prompts end with `finish_reason: refusal` because of a specific phrase in a
    "chain of thought / reasoning / thinking process" field description; if a candidate's optimizer
    prompt triggers it, remove only that phrase in **our copy** of the prompt (never the vendored
    original), log it, and re-run the acceptance check. (Verified for ACE; watch for it in GEPA's
    reflection prompt and SkillOpt's analyst prompt, which are free-text-JSON.)
  - **G3 (verified for every candidate):** no candidate's optimizer path needs structured output
    or forced `tool_choice` — all parse free-text JSON — so the base plan's F5 (gateway rejects
    forced `tool_choice type tool/any`) is **not** a blocker. EvoSkill is the one exception
    (its Claude-Agent-SDK structured-output path): A-`evoskill` smoke-tests it and falls back to
    text-JSON parsing if the gateway rejects it (section 7.4).

### 1.3 Facts from the base-plan code the plan reuses unchanged

- The episode worker `examples/appworld/adapters/aw_agent.py` runs **one AppWorld episode per
  subprocess** with the common model config (gpt-oss-120b, `hosted_vllm/` route, `reasoning_effort
  medium`, temp 0, `max_completion_tokens` 6000, `drop_reasoning_content`, `use_cache: false`,
  `max_output_length` 60000, `max_steps` 50, token cap 100,000/task), reads the RITS key from
  `.env` and drops it from `os.environ` before the world starts, and **hardens the REPL** (removes
  `os`, `pathlib`, `io`, `shutil`, `glob` from AppWorld's import allowlist — base F1). It records
  `fs_probe` (did agent code name a gold path). The gold-bearing `trace` is dropped before anything
  is written. **Every candidate's agent-under-test runs through this worker**, unchanged, so the
  agent side is identical across arms.
- `CapReActAgent` injects three surfaces: **(P)** the prompt template `policy/instructions.txt`;
  **(T)** `tools/helpers.py` REPL helpers + `tools/api_notes.json` notes appended to API-doc
  lookups; **(M)** a memory block (`memory/playbook.md` static, or per-task `memory/retrieval.json`)
  inserted right before the final `My name is: … Task: {{ instruction }}` block. With all three
  empty the first request is **byte-identical to stock** (the seed).
- The adapter `examples/appworld/adapters/adapter.py` exposes `tasks(split)`, `run_trials(tasks,
  candidate_dir, n_trials, base_seed)` → `{task_id: [Rollout,...]}`, `run_target`, and
  `score(task, rollout)` → reward 0/1 + **gold-free** feedback tier F1 (failed requirement texts,
  collateral-damage flag, `complete_task` called, steps, API errors, termination) + the metrics
  list (`reward`, `steps`, `prompt_tokens`, `completion_tokens`). A **seal** refuses any id outside
  train ∪ dev unless `AW_ALLOW_SEALED=final-eval-only`. This is the single evaluator every candidate
  calls.
- `examples/appworld/lints.py` rejects a candidate before any rollout: prompt must keep its three
  Jinja variables, `USER:`/`ASSISTANT:` structure and the final block, ≤ 8,000 tokens; helpers may
  not hardcode app/API names or `apis.<app>.` chains, import outside a small allowlist, or make
  top-level calls; notes ≤ 400 chars each / 20,000 total; memory block ≤ 30,000 chars; nothing may
  contain an 8-gram of a train/dev instruction or a supervisor contact. **The lint runs against
  every candidate's artifact(s)** on whatever surface it writes.
- `final_window.py` (freeze + run), `analyze.py` (TGC/SGC, by difficulty, scenario-clustered paired
  bootstrap), `scan_isolation.py`, `make_roots.py`, `make_splits.py`, `make_reference.py`,
  `status.py` are reused. `final_window.py`/`analyze.py` currently hardcode three arms; the
  executing agent **generalizes `ARMS`** to `("seed", "gepa", "skillopt", "wikiskill", "evoskill",
  "metaharness")` (section 12).

---

## 2. Decisions carried over, and the new ones

| id | decision | source |
|---|---|---|
| D1 | optimizer model `aws/claude-sonnet-5-5` for every candidate | base plan; guideline 6.3 |
| D2 | AppWorld core + agents from source at `42b5bcf`, pydantic 2.12.x | base plan |
| D3 | 1 trial/task search, 2 trials/task final, 1 search seed | base plan; guideline 6.1 |
| D4-x | each candidate's version pin: GEPA `0.1.4`, SkillOpt `ae2f766`, WikiSkill `0363334`, EvoSkill `v1.3.0`, Meta-Harness `8123cca` | section 7 (studied 2026-10-17) |
| **D5** | **isolation mechanism = Claude Code's sandbox** (not the namespace wrapper, which cannot run in this pod) for the two agentic optimizers; pure-LLM optimizers need no sandbox but still run under the gold-free feedback and `root_full chmod 000` regime | 1.2, section 8 |
| **D6** | **surface per candidate** (which of P/T/M each arm learns), chosen to be the most faithful to each method's native design: see 7 and section 3 | section 7 |
| **D7** | **search splits:** GEPA uses `train`(90)=feedback / `dev`(57)=Pareto-val (its native D_feedback/D_pareto); the four skill-memory methods adapt on `train`(90) and use `dev`(57) only for selection/diagnostic. No method's counted search rollouts exceed **B=900** | 7, 9 |
| **D8** | **ledger = this document**, appended under `flock`; resume from the last checkpoint; one tracking issue per candidate | guidelines 5, 7.3 |

These eight are the only decisions. If the executing agent finds a source conflict (e.g. a
candidate's paper vs its code), it follows the **code** at the pinned commit and records the choice
in the ledger, as the ACE sibling did.

---

## 3. Arms

| arm id | what it is | learned artifact | surface it plugs into |
|---|---|---|---|
| `seed` | the official AppWorld simplified ReAct code agent, stock prompt, no memory/helpers/notes | none | none |
| `gepa` | GEPA reflective evolution of the agent's text components | edited `policy/instructions.txt` + `tools/helpers.py` + `tools/api_notes.json` | P + T |
| `skillopt` | SkillOpt self-evolving skill document | `memory/playbook.md` | M (static) |
| `wikiskill` | WikiSkill skills compiled into a playbook | `memory/playbook.md` | M (static) |
| `evoskill` | EvoSkill skills discovered from failures | `memory/playbook.md` | M (static) |
| `metaharness` | Meta-Harness end-to-end harness search | `policy/instructions.txt` + `tools/helpers.py` + `tools/api_notes.json` (+ optional `memory/playbook.md`) | P + T (+ M) |

**All six arms use the same harness, model client, decoding parameters, step cap and evaluator.**
Only each arm's own surface files differ. The seed is byte-identical to stock. This is the single
most important fairness property and it is **guaranteed by construction** because every arm's agent
runs through the one unmodified `aw_agent.py` worker (1.3).

---

## 4. Environment (built once, mostly on `/workspace`)

Because `/tmp` is wiped between sessions and the pod can be OOM-restarted, durable state lives on
`/workspace`; only AppWorld's native per-episode output dirs go on `/tmp`. Layout follows the ACE
sibling (its section 4), renamed for eval 5:

```
/workspace/worktrees/base/                 # the repo, branch eval5 (committed + pushed at every checkpoint)
  docs/EVAL_APPWORLD_5.md                  # THIS DOCUMENT: plan (0–14) + appended ledger (section 15)
  docs/EVAL_APPWORLD_5_STATE/              # pushed continuation state (section 10.3)
    manifest.json                          # commits, patch sha256, data/split/venv hashes, order seeds, caps
    <cand>/progress.json                   # per-candidate: last step, counts, spend, per-step scan counts
    <cand>/artifact/…                      # the frozen artifact of each candidate (lint-checked; publishable)
    final/progress.json                    # final window: counts only (no per-cell test outcomes)
    final/{analysis.json,RESULTS.md}       # written at P9
  examples/appworld/                       # the shared harness + the five candidate drivers (section 4.1)
/workspace/aw_eval5/                        # AW_HOME (durable, OUTSIDE git, never pushed)
  state/                                   # AW_STATE: RUNNING.pid, records/<phase>/<unit>.json, per-candidate optimizer logs, final/order.json + per-cell records
  build/                                   # AW_BUILD (rebuildable from manifest.json)
    appworld/   venvs/   root_full/ (chmod 000 during search)   root_opt/   hf/   clones of the 5 candidate repos (read-only)
/tmp/aw_eval5/aw_outputs/                   # AppWorld native per-episode outputs, deleted after each gold-free record is written
```

Secrets: `AW_SECRETS_FILE=<repo>/.env` (`RITS_URL`, `RITS_API_KET`) — git-ignored, read by each
episode worker, **never** exported, copied into `AW_HOME`, or published. The optimizer gateway
credentials come from `~/.claude/settings.json` (already present).

Build steps (each one checkpoint, each idempotent, each < 30 min so an OOM restart loses little):

- **B1.** Clone `StonyBrookNLP/appworld` @ `42b5bcf`, `git lfs pull`, apply
  `examples/appworld/patches/appworld-extra-headers.patch`; record `git diff` + sha256 in
  `manifest.json`.
- **B2.** `uv venv -p 3.11 build/venvs/venv-aw`; install `-e appworld -e
  "appworld/experiments[simplified]" "pydantic>=2.12,<2.13"`, `-e /workspace/worktrees/base/core`
  (for the shared `Rollout` type), then `appworld install --repo`. Record `uv pip freeze` + sha256.
- **B3.** `appworld download data --root root_full`; check split counts (90/57/168/417), scenario
  counts (30/19/56/139) and difficulty counts (train 36/36/18, dev 30/24/3, test_normal 57/48/63);
  stop on mismatch. Record data-tree sha256.
- **B4.** `make_roots.py` builds `root_opt` (train+dev tasks + `_base_`, no test ids — greps to
  confirm 0 test-id hits); `make_splits.py` writes split files; `make_reference.py` writes the
  optimizer reference dir (public API index + agent notes; **no task data**). `chmod 000 root_full`.
  Build the lint cache (`lints.py --write-cache`) so the lint can run while `root_opt` is locked.
- **B5. Per-candidate venvs/clones** (section 7 gives exact installs). To avoid dependency clashes,
  **each candidate gets its own uv venv** under `build/venvs/venv-<cand>` (Python per 7); the
  AppWorld agent always runs via `venv-aw` in a subprocess, so a candidate venv never needs
  AppWorld importable. Clone each candidate repo at its D4 pin into `build/clones/<cand>`
  (read-only; vendor only the pure modules a driver imports, with a `VENDORED.md` listing source
  path, commit and sha256).
- **B6.** Write the five candidate drivers and the generalized final-window/analysis code
  (section 4.1), committing after each passes its offline unit check.
- **B7.** The user supplies `.env` (done). Confirm variable names only.

### 4.1 Code to write (all under `examples/appworld/`)

Reused unchanged from this branch: `adapters/*.py`, `lints.py`, `seed_capability/`,
`patches/`, `scripts/{make_roots,make_splits,make_reference,status,scan_isolation}.py`. Reuse the
ACE sibling's `scripts/{status_doc,resume,build}.py` pattern for the ledger/resume (section 10).

New, per candidate, under `examples/appworld/<cand>/`:
- a **driver** that runs the method's loop, calling the shared adapter's `run_trials`/`score` as the
  evaluator (one subprocess per episode, `AW_WORKERS` concurrency), and writing the method's output
  onto the arm's surface files;
- a **gateway LLM shim** for the optimizer model (`aws/claude-sonnet-5-5`) that sets the base URL,
  `x-context-guru-token` header and omits `temperature` (G1), logging **one usage line per call**
  (`{t, seconds, model, prompt_tokens, completion_tokens, error}`) to
  `AW_STATE/<cand>/optimizer_usage.jsonl` — the single cost/latency source for the optimizer side
  (guideline 6.2). The ALTK/ACE shims in `altk/altk_common.py` / `ace/ace_llm.py` are the templates;
- a **freeze** step that renders the method's final result into the arm's surface files, lints it,
  and copies it to `docs/EVAL_APPWORLD_5_STATE/<cand>/artifact/`.

Generalized: `scripts/final_window.py` and `scripts/analyze.py` take `ARMS = ("seed","gepa",
"skillopt","wikiskill","evoskill","metaharness")` (keep the base plan's structure; just widen the
tuple and the pairwise contrasts to `<cand> − seed` for each candidate).

---

## 5. Tracking issues and progress reporting (guideline 5)

Before execution starts, **one GitHub issue per candidate** is opened on
`git@github.com:skillberry-ai/cap-evolve.git` (i.e. `gh issue create -R skillberry-ai/cap-evolve`).
The **first post** on each issue is a **projection of this plan for that candidate**: the candidate's
own section 7.x, plus the common sections (0, 2, 3, 6, 8, 9, 11, 12 and this section). Titles:
`AppWorld eval 5: <Method> vs seed (gpt-oss-120b)`.

During execution, the agent posts **periodic progress updates** on the respective candidate's issue,
following the base plan's cadence (interim updates as phases complete — build/acceptance done, each
search milestone, freeze, isolation scan, final-window progress, final results), and the ledger's
content rules (section 10.2): **no task ids, no gold values, no task/supervisor text, no trajectory
text, no secrets, no per-task test outcomes.** The final post on each issue is that candidate's
results comment (section 12). The ledger (section 15) records each post's URL in a `posted` entry so
nothing is posted twice.

The five tracking issues (created 2026-10-17 on `skillberry-ai/cap-evolve`, each seeded with its
plan projection):

| arm | issue |
|---|---|
| `gepa` | [#881](https://github.com/skillberry-ai/cap-evolve/issues/881) |
| `skillopt` | [#882](https://github.com/skillberry-ai/cap-evolve/issues/882) |
| `wikiskill` | [#883](https://github.com/skillberry-ai/cap-evolve/issues/883) |
| `evoskill` | [#884](https://github.com/skillberry-ai/cap-evolve/issues/884) |
| `metaharness` | [#885](https://github.com/skillberry-ai/cap-evolve/issues/885) |

These numbers are also recorded in `manifest.json` and in the ledger's first checkpoint (CP-0000).

---

## 6. The common harness and capability layout

As in the base plan (its section 6), reused unchanged:

- **Seed capability** `examples/appworld/seed_capability/`: `policy/instructions.txt` (byte copy of
  the stock prompt @ `42b5bcf`), empty `tools/helpers.py`, `tools/api_notes.json = {}`, empty
  `memory/`. The seed arm is this directory verbatim.
- **Injection** via `CapReActAgent.initialize` (1.3): P from `policy/instructions.txt`; T from
  `tools/`; M before the final task block. No surface present ⇒ byte-identical to stock.
- **Lints** (1.3) run at materialization of every candidate artifact and inside the final-window
  freeze; a violating artifact is rejected (`lint_reject`, scored 0) before any rollout.
- **Feedback tier F1** (gold-free) is the only signal any optimizer receives from the evaluator.
  Methods whose native design feeds the optimizer **ground-truth answers** (EvoSkill, SkillOpt's
  "Hidden Reference", WikiSkill's exact-match target) are **de-fanged** so that the ground-truth
  slot carries only F1 text (failed requirement texts) or a withheld-sentinel (section 7).

**Memory cap.** The lint caps a memory block at 30,000 chars; additionally, because the RITS window
is 40,144 tokens and 6,000 are reserved for completion, the executing agent measures `P_max` (the
stock prompt over the 147 train∪dev tasks) and `H_max` and fixes an effective cap
`M_cap = min(30,000 chars, 34,000 − P_max − H_max tokens)` (≈ 13K tokens, as the ACE sibling found),
checked in acceptance A8. Any method whose playbook would exceed `M_cap` must prune/dedup to fit
(section 7); an over-cap artifact is a lint reject.

---

## 7. The five candidate arms

Common to all five: the optimizer is `aws/claude-sonnet-5-5` via the gateway shim; the agent under
test is the shared `aw_agent.py` worker; the evaluator is the shared adapter's `run_trials`/`score`;
search uses only train∪dev; the lint and `M_cap` apply to the artifact; counted search rollouts ≤
**B=900**; optimizer tokens ≤ 10M; **1 trial/task** in search. Each subsection states: the method,
its surface (D6), how to deploy it, the glue code, the faithful settings, the de-fang/isolation
specifics, the budget mapping, the conflicts and least-distorting resolutions, the per-candidate
acceptance check, and the frozen artifact.

### 7.1 `gepa` — GEPA (pin `gepa==0.1.4`)

**Method.** Reflective evolution of a candidate `dict[str,str]` of text components. Loop: seed eval
on the full valset; pick a parent from the per-instance Pareto front; run the parent on a train
minibatch (default 3) with trace capture; reflect once per selected component via the reflection LM;
run the child on the same minibatch; accept iff the summed minibatch score strictly improves; then
full-val eval and Pareto update; optional system-aware merge (default **off**). Final = highest mean
val. Pure Python, **zero hard deps**; **no shell**, no structured output / `tool_choice` (free-text
between ``` fences). Verified: adapter protocol `evaluate(batch, candidate, capture_traces) ->
EvaluationBatch(outputs, scores, trajectories, num_metric_calls?)`, `make_reflective_dataset`,
optional `propose_new_texts`; `reflection_lm` accepts a **callable** `(str)->str`.

**Surface (D6): P + T** — three components `"policy/instructions.txt"`, `"tools/helpers.py"`,
`"tools/api_notes.json"`, seeded from `seed_capability` (helpers `""`, notes `"{}"`). This matches
the base cap-evolve arm's `[system-prompt, tools]`, so GEPA is the closest head-to-head to the base
plan's champion. `module_selector="round_robin"` (paper default). Leave M out.

**Deploy.** `pip install gepa==0.1.4` into `venv-aw` (it is importable alongside AppWorld; zero
deps). Driver runs **inside `venv-aw`** so `sys.executable` launches episode subprocesses correctly.

**Glue.** A `GEPAAdapter` whose `evaluate` writes the candidate dict into a content-hashed copy of
`seed_capability`, calls `run_trials(tasks, cdir, n_trials=1, base_seed=FIXED)` then `score`; scores
= rewards; trajectories = instruction + per-step thought/code/output (outputs truncated ≤ ~1k
chars) + the F1 feedback string; implement `batch_evaluate` to fill `AW_WORKERS`; a lint-failing
candidate returns zeros with the lint text as feedback (or, better, lint inside a custom proposer
and re-reflect up to ~2× before returning `{}`). `make_reflective_dataset`: one record per minibatch
task per component (`Inputs`/`Generated Outputs`/`Feedback`). **reflection_lm** = our gateway
callable (omit temperature per G1; exposes `total_cost`; logs usage). **Output delimiter:** the
stock prompt has ~45 ``` fences, which breaks GEPA's "first-to-last ```" extractor, so use a
**per-component reflection template** that asks for the new text inside `<new_text>…</new_text>` and
parse that in a `custom_candidate_proposer` (or `propose_new_texts`). Templates must state the lint
constraints (Jinja vars, USER:/ASSISTANT:, final block, ≤8000 tokens; helper import/literal rules;
notes JSON `app`/`app.api` ≤400 chars).

**Faithful settings.** `reflection_minibatch_size=3`, `candidate_selection_strategy="pareto"`,
`skip_perfect_score=True`, `perfect_score=1.0`, `acceptance_criterion="strict_improvement"`,
`use_merge=False` (default; best Qwen result; a merge variant is out of scope), `cache_evaluation=
False`, `seed=0`, `track_best_outputs=True`, wandb/mlflow off.

**Splits (D7).** `trainset`=train(90) for reflection minibatches, `valset`=dev(57) for the Pareto
front and final choice — GEPA's native D_feedback/D_pareto, and exactly the ACE paper's GEPA
baseline. (Using train∪dev=147 as valset would cost 147 per acceptance and cripple GEPA inside B.)

**Budget.** `max_metric_calls=987` so the worst-case overshoot (≤ 2·minibatch + |val| = 63) keeps
the counted total ≤ 1,050 and the search ≤ ~900 counted rollouts; ≈ 1,029/57 ≈ 18× |val|, inside
the docs' 15–30× guidance and close to ACE's GEPA run (1,434). One metric call per episode.

**Isolation.** No shell; leakage limited to what `score()`/traces carry — already gold-free. Keep
`root_full chmod 000`. **The reflection prompt famously invites copying example text**, so expect
lint rejections (8-grams, contacts, hardcoded `apis.<app>`); state the lint rules in the template
and count rejects.

**Conflicts.** 0/1 rewards + minibatch 3 + 1 trial ⇒ noisy acceptance and large Pareto ties — kept
(it is the method); reported. The ACE-paper GEPA run had gold labels in feedback; **ours is
gold-free (F1 only)**, which is fairer but weaker, and is disclosed.

**Acceptance A-`gepa`.** On 4 dev tasks into a throwaway run dir: one reflection call returns
parseable text via the `<new_text>` delimiter; the candidate-dict → candidate-dir mapping lints
clean; the gateway shim completes with no `temperature` and no refusal (G1/G2); `evaluate` returns
scores and gold-free trajectories; `batch_evaluate` fills workers. Not counted.

**Artifact.** `result.best_candidate` rendered to `policy/instructions.txt` + `tools/*`.

### 7.2 `skillopt` — SkillOpt (pin `main` @ `ae2f766`)

**Method.** Evolves **one Markdown skill document** injected into the prompt, via bounded LLM patch
ops (append/insert_after/replace/delete). Loop (`ReflACTTrainer.train`): baseline on val; per
epoch/step — rollout train batch; reflect per failure/success minibatch (M=8) → JSON patch; merge;
LLM-rank-and-clip to L_t (cosine 4→2); apply; **strict-improvement gate on full val** (cache by
skill hash); plus a per-epoch ungated "slow update" block and optimizer-side "meta skill". Pure
chat calls; **no tool_choice/structured output** on the optimizer path. **Risky backends
(`claude_chat`, `codex_exec`, `claude_code_exec`, SkillOpt-Sleep) are NOT used.**

**Surface (D6): M (static `memory/playbook.md`)** — a 1:1 fit (SkillOpt optimizes exactly one prose
doc). Keep P and T frozen at the seed. Report as "M-only, method-native".

**Deploy.** `pip install -e .` from `ae2f766` into `venv-skillopt` (Python ≥3.10; deps `openai,
pyyaml, numpy, openpyxl, azure-*`, plus `anthropic` for the shim). No GPU/docker/services. Drive
`ReflACTTrainer(cfg, adapter).train()` from a launcher, not the CLI.

**Glue.** An `AppWorldAdapter(EnvAdapter)` implementing `build_train_env`/`build_eval_env`/
`rollout(env, skill_content, out_dir)`/`get_task_types`. `rollout` writes `skill_content` to a
per-run `memory/playbook.md`, calls `run_trials` (gpt-oss-120b) concurrently, returns `hard`=success
(0/1) and `soft`=fraction of requirement checks passed, `fail_reason`=short failed-check summary; it
writes a **compacted** `conversation.json` (per-step code + outputs truncated ~2k chars, cap ~15–20k
tokens) plus a final `{"role":"system"}` **gold-free** F1 evaluation report (train only); caches
`results.jsonl` for resume. Split dir: `train/`=90 official train, `val/`=57 dev, `test/`=`[]`,
`eval_test: false`. **Optimizer shim:** monkeypatch `openai_compatible_backend.chat_optimizer` (and
`chat` dispatch) to call the gateway via the Anthropic client with the custom header, `max_tokens=
16384`, no temperature (G1), logging usage to the tracker/JSONL. **Length guard:** reject (or
pre-truncate) any candidate skill over `M_cap`.

**Faithful settings.** `num_epochs=4`, `batch_size=40`, `minibatch_size=8`, `merge_batch_size=8`,
`learning_rate=4→min 2` cosine, `use_slow_update=true` (ungated), `use_meta_skill=true`,
`use_gate=true` (`gate_metric=hard`), `sel_env_num=0` (full dev gate), `seed=42`. Lower
`analyst_workers` only if the gateway throttles (semantics unchanged).

**Splits (D7).** Only train trajectories/slow-update samples reach the optimizer; dev is the gate
only. Faithful to the paper's train/val/test roles.

**Budget.** ~3 steps/epoch × 4 ≈ 12 steps ⇒ baseline 57 + 12·(40+57) + slow-updates 3·40 + final 57
≈ **~1.4k rollouts** uncached — **over B=900**. Resolution (least-distorting): keep every default
except **scale `num_epochs` down** (and/or rely on the skill-hash cache) until counted rollouts ≤
900; do **not** disable slow/meta updates or change M/gate semantics. Record the actual count.

**Isolation.** Pure chat; no shell. Keep `root_full chmod 000`. **De-fang:** never set
`reference_text` (its "Hidden Reference" would print gold); the train `[verification]` F1 report is
fine (train-only, gold-free). Ensure `test/` is a dummy and `eval_test:false`.

**Conflicts.** ~13–16 strict-improvement gates on 57 noisy dev tasks ⇒ optimistic selection — kept,
reported. Untruncated-trajectory context blow-up ⇒ compact observations (above), do not cut M.
Skill placed in M-slot (USER turn), not system prompt as in the paper — disclosed. Optimizer is
Sonnet, not GPT-5.5 — disclosed.

**Acceptance A-`skillopt`.** 1-step dry run on 4 dev tasks into a throwaway store: the monkeypatched
optimizer call reaches the gateway and returns a parseable patch; a rollout writes `memory/
playbook.md`, runs the agent and returns `hard`/`soft`; the gate caches by hash; an over-`M_cap`
skill is rejected. Not counted.

**Artifact.** `out_root/best_skill.md` → `memory/playbook.md`.

### 7.3 `wikiskill` — WikiSkill (pin HEAD `0363334`)

**Method.** Co-evolves a small library of `SKILL.md` skills with an optimizer-side wiki of failure/
success patterns. Loop (Algorithm 1): baseline val; per iteration — roll out **all** train tasks
with current skills; sample ≤5 fail / ≤3 pass traces (≤15k chars each); one **Wiki Maintainer** LLM
call (JSON patch of wiki pages); a **Skill Proposer** ReAct loop (≤20 turns, reads wiki, returns one
atomic create/patch of one skill); apply + re-run **all** val; accept iff strictly better (skills
rolled back on reject, wiki kept). Delivered to the agent as the concatenation of all active
`SKILL.md` into the prompt — **no retrieval** (the paper deliberately avoids it; wiki never reaches
the agent). Stdlib-only; `OpenAICompatLLM` over `urllib` to `{base_url}/chat/completions`;
**no tool_choice/structured output** (free-text JSON).

**Important maturity caveat (verified, be candid in the issue).** This repo is a **third-party,
AI-assisted reimplementation** (no official code exists; 7 commits, never run on a real benchmark;
prompts heavily condensed vs the paper's Appendix E; `extract_json` is fragile). The executing agent
**must write**: the gateway LLM wrapper, the AppWorld inference adapter, the outcome summary/
feedback, parallel rollouts, cost logging, paper-faithful prompts (restore Appendix E), and the
skills→playbook export. Record in the issue that this is a reimplementation and list what was
written, so the result is read as "WikiSkill-as-reimplemented", not "WikiSkill as published".

**Surface (D6): M (static `memory/playbook.md`)** — the method injects all active skills into the
prompt with no retrieval, which is exactly a static playbook. Do **not** use per-task
`retrieval.json` (the paper avoids retrieval). Keep P and T frozen.

**Deploy.** Vendor the ~6 core modules (`orchestrator/agents/skills/workspace/llm/prompts.py`) into
`examples/appworld/wikiskill/vendor/` with `VENDORED.md`; no pip install needed (stdlib). Add an
`AnthropicGatewayLLM(chat(messages, …)->str)` implementing the `LLM` protocol (system→top-level
`system`, `x-context-guru-token` header, model `aws/claude-sonnet-5-5`, no temperature per G1, text
only; log usage; `max_tokens` ~8k for the proposer).

**Glue.** Replace `orch.inference` with `AppWorldInference.run(task)->Trajectory`: render current
skills into `memory/playbook.md`; run our ReAct harness on the task id; `correct`=AppWorld success;
`messages`=the agent transcript + a final `{"role":"user","content":"EVALUATION: <F1 failed
checks>"}` so the Maintainer sees why it failed; `prediction`=that F1 string. Override the outcome
summary to PASS/FAIL + one-line failure reason + trace path (AppWorld has no `y`). Override
`_rollout` for a thread pool sized to vLLM capacity. train=90, val=57; **never call
`evaluate_test()`**. Restore the Appendix E Maintainer/Proposer prompts, add `no_action` handling,
and record full proposal text in `skill-impact.md`. Export the accepted skill set to the final
`memory/playbook.md` under the 30,000-char / `M_cap` limit (tell the proposer the budget;
reject over-budget proposals).

**Faithful settings.** K=8 iterations (paper indexes 0–7), full-batch train, 1 rollout/task/iter,
5+3 trace sample (15k-char cap), ReAct turns ≤20, strict-improvement gate on dev, skills-only
rollback, early stop at val=1.0, proposer/maintainer temp (dropped per G1).

**Splits (D7).** train=90 (rollouts + mining signal), val=57 (gate + final choice). No retrieval.

**Budget.** K=8 ⇒ 57 baseline + 8·(90+57) ≈ **~1,233 rollouts** — **over B=900**. Resolution: reduce
K (e.g. to ~5–6) and/or skip val when a proposal is invalid, until counted ≤ 900; keep everything
else. Record the actual count and K used.

**Isolation.** The Proposer's only tool is a workspace-scoped `read_file` (prefix check; no symlink
resolve) over the **wiki/skills workspace only** — give it a scratch dir containing no gold. No
shell, no network beyond the gateway. Keep `root_full chmod 000`. Correctness in the repo is
exact-string match; we replace it with AppWorld success + gold-free F1 feedback.

**Conflicts.** Binary exact-match vs unit-test eval → use success + F1 report (richer but train-
only, allowed). Strict gate on 57 noisy dev tasks → kept, reported. 15k-char trace cap vs long
AppWorld transcripts → kept (truncate longest first). Optimizer is a fixed Sonnet rather than self-
evolution → disclosed.

**Acceptance A-`wikiskill`.** 2-iteration dry run on a few dev tasks into a throwaway workspace: the
gateway wrapper returns parseable JSON for Maintainer and Proposer; a skill is created and injected
into `memory/playbook.md`; `AppWorldInference.run` returns a Trajectory with `correct` and the F1
EVALUATION message; the export respects `M_cap`. Not counted.

**Artifact.** `active_skills_context()` of the accepted skill set → `memory/playbook.md`.

### 7.4 `evoskill` — EvoSkill (pin `v1.3.0` `1d7dc3e`; HEAD `36f6f04`)

**Method.** Evolves a frontier of "programs" (git branches holding `.claude/skills/<name>/SKILL.md`
folders). Loop (`SelfImprovingLoop.run`): base program scored on val; pick parent from frontier
(`selection_strategy="best"`); draw a round-robin failure batch; run the parent; a **Proposer**
(Claude Agent) returns create/patch; a **Skill Builder** (Claude Agent) writes one `SKILL.md`;
score child on full val; admit to frontier (size 3) if it beats the worst; append proposal+outcome
to `feedback_history.md`; stop at `max_iterations` or `no_improvement_limit`. **The agents run
Claude Code with Bash/Read/WebFetch/WebSearch and `acceptEdits`** — a real coding agent.

**Surface (D6): M (static `memory/playbook.md`)** — EvoSkill evolves SKILL.md files but our agent
can't read files, so render the frontier program's skills (sorted `name: description` + body,
excluding the repo's `brainstorming`/`skill-creator` meta-skills) into `memory/playbook.md`, ≤30,000
chars / `M_cap`. Keep P frozen (`prompt_only` is unevaluated and broken in the CLI). T optional and
**not** used (keeps it a clean M arm).

**Deploy.** `pip install` from `v1.3.0` into `venv-evoskill` (Python ≥3.12; heavy deps incl.
`claude-agent-sdk`, `harbor`; the Node Claude Code CLI + git). Docker only for `--docker`/Harbor —
**not** used. Drive `SelfImprovingLoop` from Python.

**Glue.** `AppWorldAgent(Agent)` modelled on `HarborAgent`: `run(task_id)` renders the playbook from
the program's skills, runs our ReAct harness (gpt-oss-120b) in a subprocess, returns an `AgentTrace`
with `output.final_answer=json.dumps({"reward": tgc})` and a **gold-free** `result` text (truncated
trajectory + F1 failed-requirement texts); scorer `harbor_reward_scorer` (ignores ground truth).
`train_pools`=90 train (category = difficulty 1/2/3), `val_data`=57 dev. **Patch the 1020 s
per-eval timeout** (`evaluation/evaluate.py`) or keep episode cap under it.

**De-fang (critical — EvoSkill leaks gold and has shell/web access).**
1. **Ground truth:** the Proposer query normally contains `Ground Truth: {ground_truth}` and the
   prompts tell it to compare against gold. Pass a **gold-free sentinel** as `ground_truth`
   ("withheld; see failed checks in trace") and edit a **copy** of the Proposer prompts to replace
   "ground truth answer / compare to the ground truth" with "evaluation feedback (failed checks)".
2. **Agent tools:** build options for Proposer = `Read,Glob,Grep` and Skill Builder = `Read,Write,
   Edit,Glob,Grep`; **remove `Bash,WebFetch,WebSearch,Skill`**; `setting_sources=[]` (no inherited
   `CLAUDE.md`). Run both agents under **Claude Code's sandbox** (section 8) with `denyRead` on
   every gold path, `root_full`, `root_opt/**/ground_truth`, `.env`, other sessions' transcripts,
   and `network.allowedDomains:[]` + `DEVAGENT_BWRAP_NETWORK=restrict` (the gateway host allowlisted
   so the SDK still reaches the optimizer; WebSearch disabled anyway). This closes the base plan's
   F8/F14 class.
3. **project_root** = a fresh scratch git repo containing only `.claude/skills/{brainstorming,
   skill-creator}` and `.evoskill/` — **never** the cap-evolve worktree (its `git stash`/`checkout`
   would touch our tree). Disable `RunCache` or rely on its skills-hash key.
4. **Gateway:** inherit `ANTHROPIC_BASE_URL`/`AUTH_TOKEN`/`CUSTOM_HEADERS`; set a small/fast model
   override; the model id `aws/claude-sonnet-5-5` passes through unchanged. **Smoke-test the SDK
   `output_format` (structured output) against the gateway first (G3 exception); if rejected, parse
   JSON from result text** (the OpenHands-path fallback). Log `trace.usage` tokens + `duration_ms`
   + `total_cost_usd` per role; also log task-side tokens from our harness (HarborAgent reports 0).

**Faithful settings.** `skill_only`, `frontier_size=3`, `selection_strategy="best"` (code default;
note Algorithm 1 says round-robin), failure threshold 0.8 on 0/1 TGC, `no_improvement_limit=5`, one
trial/task, iterations ≈ **1.5 epochs** of the train pool.

**Budget.** ~1.5 epochs × (6 failure candidates/iter) ⇒ ~22 iterations; base 57 + 22·(6+57) ≈
**~1,450 rollouts** with full-dev val — **over B=900**. Resolution: use a **stratified ~20-task dev
subset** for the per-iteration val (the paper itself uses ~7% validation) and/or cap iterations,
until counted ≤ 900; state which. Final selection still re-scored on full dev at freeze.

**Isolation.** As de-fanged above; plus `root_full chmod 000` and the post-search scan. This is the
highest-isolation-risk arm; A-`evoskill` must pass the sandbox check (A9) before any counted
rollout.

**Conflicts.** Gold leakage by design → removed (1). Shell/web access → removed (2). Noisy small-val
selection → reported. Fixed Sonnet vs self-evolution with Opus → disclosed. Cost-accounting bugs in
the loop (undercount on all-pass / early-stop) → log tokens ourselves.

**Acceptance A-`evoskill`.** (a) A9 sandbox check passes (section 8) with the de-fang settings; (b)
2-iteration dry run on a few dev tasks into the scratch repo: Proposer sees **no** `Ground Truth`,
Skill Builder writes a SKILL.md with no Bash/web, the playbook renders ≤ `M_cap`, `run` returns a
reward-only AgentTrace with gold-free `result`, the SDK structured-output path works or falls back.
Not counted.

**Artifact.** Rendered best-frontier skills → `memory/playbook.md`.

### 7.5 `metaharness` — Meta-Harness (pin HEAD `8123cca`)

**Method.** Not a library — a **pattern**: an outer loop + a **Claude Code proposer** (driven by a
SKILL.md) + a filesystem of logs. The proposer reads prior candidates' source and raw traces and
writes new harness code; the outer loop validates, smoke-tests and benchmarks each candidate, keeps
a frontier, and logs one row per candidate. The proposer runs `claude --dangerously-skip-permissions`
with Read/Glob/Grep/Agent/Write/Edit/**Bash** — a full coding agent with shell. Full traces are the
key ingredient (paper ablation: traces 50.0 vs scores-only 34.6). No AppWorld integration exists;
the TB2 example is the template to copy.

**Surface (D6): P + T (+ optional M).** The method natively targets the whole harness program;
restricting to our injectable surfaces is acceptable. Treat a candidate as a **directory**
`candidates/<name>/{policy/instructions.txt, tools/helpers.py, tools/api_notes.json,
memory/playbook.md}` and allow the proposer to edit all of them, with one hypothesis per candidate.
Prefer `playbook.md` over per-task `retrieval.json` (a per-task file keyed by train/dev ids cannot
transfer to test).

**Deploy.** Copy `reference_examples/terminal_bench_2/` into `examples/appworld/metaharness/` and
write a new `meta_harness_appworld.py` (model on the TB2 outer loop). Python ≥3.11; `litellm` is
only for inner models (unused — our harness runs the agent); the proposer needs the Node Claude Code
CLI. **No Harbor/Modal/Runloop, no docker.** Do **not** run `claude_wrapper.py`'s self-test.

**Glue.**
1. **Outer loop:** Phase 0 scores the seed; then N iterations of proposer → `pending_eval.json` →
   validate → smoke → evaluate → update `frontier_val.json` + `evolution_summary.jsonl`.
2. **Validator** (outside the proposer): the Jinja template renders with the three vars and parses
   USER:/ASSISTANT:; `helpers.py` imports under `python -I` and exposes expected names;
   `api_notes.json` parses; the diff is confined to the four allowed files; a **forbidden-string
   scan** finds no train/dev/test task ids, no gold strings, no `test_normal` (port
   `controller.validate_source`). Then the shared lint.
3. **Evaluator:** `run_trials(candidate_dir, train90+dev57, n_trials=1)` + `score`; write per-task
   dirs with reward, the **gold-free** trajectory (prompts, code, truncated REPL outputs), the F1
   eval report, and token metrics; return per-task rewards (TGC; also record SGC).
4. **SKILL.md:** an AppWorld proposer skill adapted from the TB2 one — role, directory layout,
   allowed files, output format, anti-overfitting rules (no task ids/values), and "**do not run the
   agent or AppWorld evaluation yourself; no access outside the workspace**".
5. **Proposer call:** keep the `claude_wrapper` as the method's defining component, **swap the model
   to `aws/claude-sonnet-5-5`** and set `ANTHROPIC_DEFAULT_{OPUS,SONNET,HAIKU}_MODEL` +
   `CLAUDE_CODE_SUBAGENT_MODEL` to the same id; **remove the `ANTHROPIC_API_KEY` pop** (or use
   `ANTHROPIC_AUTH_TOKEN`) so the gateway auth survives; `--effort` may need
   `CLAUDE_CODE_ALWAYS_ENABLE_EFFORT=1` — verify, else drop it.

**De-fang / isolation (critical — this is the base plan's F8/F14/F19/F20 class).** The proposer is a
shell agent, so it must run under **Claude Code's sandbox** (section 8): a workspace holding only
`candidates/`, the search-set **gold-free** traces/scores, the public API docs, and the AppWorld
`src/`+`experiments/` **only if a module import is actually needed** (the base plan's F19/F20 showed
`generate/` leaks task generators and even `src/` app implementations are a disclosed deviation —
**prefer excluding AppWorld from the proposer's view entirely**, since the validator imports happen
outside the proposer). `denyRead` the AppWorld `data/` tree (test tasks + ground truth), `root_full`,
`root_opt/**/ground_truth`, adapter internals that read gold, `.env`, and other sessions'
transcripts; `network.allowedDomains:[]`+`restrict`. **Remove the SKILL.md "prototype by running
code" step**, or allow only pure-Python checks that call neither the solver nor AppWorld. The
`claude_wrapper` logs every tool call and file read (`claude_sessions/*/meta.json`) — the post-search
scan greps `files_read` + Bash for test ids/gold paths. Every rollout the proposer could spend
(smoke tests, prototypes) counts against B.

**Faithful settings.** Search set = train+dev (147), traces exposed to the proposer (the method's
"discovery" protocol and full-trace finding); selection = best mean TGC on the search set, token
tie-break; **1 trial/task** (TB2 uses 2 in search, but this plan fixes 1 for all arms per guideline
6.1); 1 candidate per iteration (the TB2 skill); smoke test on (1 task). Run 2–3 **debugging**
iterations first to tune the SKILL.md (paper App. D), **not counted** toward B.

**Budget.** Each counted iteration = 1 candidate × (smoke 1 + 147 eval) + validator = ~148 counted
rollouts. With B=900 ⇒ about **5–6 counted iterations**. Count smoke/baseline/prototype rollouts
against B. Proposer tokens are ~10 MTok/iter (far larger than the other arms) — report separately,
cap at 10M total ⇒ this also bounds iterations.

**Conflicts.** Fixed Sonnet vs the paper's Opus-max → keep the CLI proposer, swap the id, disclose.
Shell leakage → sandbox + de-fang (above). Pareto-frontier not native to scalar TGC → scalar + token
tie-break. Proposer may try to run the agent/eval itself → forbidden in the SKILL.md and blocked by
the sandbox (no AppWorld in view, no network). Budget asymmetry (10 MTok/iter) → reported, not
equalized.

**Acceptance A-`metaharness`.** (a) A9 sandbox check passes with the proposer's exact flags
(`--allowedTools …`, the de-fang `denyRead`/network settings) and a 1-iteration smoke call through
the gateway with `aws/claude-sonnet-5-5` returns a valid `pending_eval.json` and writes only allowed
files; (b) the validator rejects a candidate that touches a disallowed file or embeds a task id; (c)
the evaluator writes gold-free per-task dirs and returns rewards. Not counted.

**Artifact.** `frontier_val.json` best candidate's directory → `policy/instructions.txt` + `tools/*`
(+ `memory/playbook.md` if used).

---

## 8. Optimizer isolation (how gold is kept away from agentic optimizers)

The base plan's **namespace wrapper does not work in this pod** (1.2: `unshare` → `ENOSYS`). The
replacement, verified working here, is **Claude Code's own sandbox** (the fix doc's "switch to
Claude Code's sandbox on any machine where A9 passes in `sandbox` mode"):

- **Who needs it.** Only the two **agentic** optimizers that run a shell/coding agent:
  `evoskill` (Proposer + Skill Builder) and `metaharness` (the proposer). The three pure-LLM
  optimizers (`gepa`, `skillopt`, `wikiskill`) make only chat calls with **no shell**, so they need
  no sandbox; they still run with `root_full chmod 000`, gold-free feedback (F1), and the post-search
  scan.
- **Settings** (per the probed, working config, rendered from
  `examples/appworld/sandbox/optimizer-sandbox.template.json` with the eval-5 paths):
  `sandbox.enabled=true`, `failIfUnavailable=true`, `allowUnsandboxedCommands=false`;
  `filesystem.denyRead=[root_opt gold paths, root_full, the AppWorld data tree, .env, ~/.claude/
  projects, other sessions' dirs]`; `permissions.deny=[Read(//<those>/**)]` (Read rules cover all
  file-reading tools; a Glob/Grep rule is rejected — use Read); `network.allowedDomains=[]` with
  `env.DEVAGENT_BWRAP_NETWORK=restrict` **except** the gateway host, which must be allowlisted so the
  optimizer can still call the model.
- **Trusted evaluator.** The episode runner reads `root_full`/`root_opt` legitimately; list it in
  `sandbox.excludedCommands` (verified: an excluded named script still reads a `denyRead` file while
  the agent's own `cat` cannot) **or** run evaluation in a separate process outside the agent's
  sandbox (preferred — the drivers already run episodes as subprocesses; keep the agent and the
  evaluator in separate processes so the agent is sandboxed and the evaluator is not).
- **A9 acceptance (every agentic arm, before any counted rollout).** Plant a random secret in each
  gold location, then make **one real optimizer call** with the arm's exact flags that, using a
  **neutral "which files are visible here" framing** (1.2 — not an exfiltration-styled prompt, which
  the gateway's `[cyber]` classifier refuses), tries to `cat`/Read/`cp`/`find` each secret, reach a
  tmux socket, and reach the network. **PASS iff** no secret appears in the transcript, the call
  really tried (Bash+Read uses present), and normal work still runs (a workspace file written, the
  lint runs). Then the post-search scan (`scan_isolation.py` + the proposer's own `files_read` logs)
  must show 0 test-id hits.
- **Defence in depth (optional).** An outer `landrun` allowlist around the whole optimizer process
  also confines `claude`'s **own** Read/Grep tools and blocks AF_UNIX sockets (verified); it can wrap
  the sandboxed call for belt-and-braces, but is not required if A9 passes in `sandbox` mode.

Never instruct any optimizer to disable its sandbox or retry with a bypass flag (the classifier and
`allowUnsandboxedCommands=false` both forbid it; so does this plan).

---

## 9. Splits, feedback and isolation (shared)

- **S1. Official splits only.** Every counted task id comes from AppWorld's own split files, read
  with `load_task_ids`. No re-splitting or hand-picked subsets in any counted rollout (acceptance
  probes use a few dev ids and are not counted). `make_splits.py`/`make_roots.py` refuse to run if
  the counts differ from 90/57/168/417. The four files' sha256 go in `manifest.json`.
- **Split roles (D7).** Search uses only train∪dev. `gepa`: train=feedback, dev=Pareto-val.
  `skillopt`/`wikiskill`/`evoskill`: adapt on train, dev for the gate/selection (and a diagnostic).
  `metaharness`: train∪dev as one discovery set. **`test_normal` is never touched at search time by
  any arm.** `test_challenge` is unused.

| official split | search-time role | final window |
|---|---|---|
| `train` (90) | optimizer signal / minibatches / mining | not used |
| `dev` (57) | gate / Pareto-val / dose-selection / diagnostic | not used |
| `test_normal` (168) | never | scored, 6 arms × 2 trials |
| `test_challenge` (417) | never | never |

- **Isolation (shared).** Two data roots (search uses `root_opt`, no test files; final uses
  `root_full`); `root_full chmod 000` during all search; the adapter seal; REPL hardening (base F1);
  feedback tier F1 only (no `trace`, no gold answer, no solution); AppWorld's native per-episode
  output dirs deleted after each gold-free record is read; agentic optimizers sandboxed (section 8);
  gold-leaking proposer inputs de-fanged (section 7). After each search, the transcript/workdir scan
  (`scan_isolation.py`, plus each agentic proposer's own tool-call logs) greps for test ids, gold
  file names, `test_normal`, `root_full`, `ground_truth`; counts go in each candidate's results and
  a hit labels the arm "isolation breach" (as the base plan's F14).

---

## 10. Orchestration, ledger and resume

Long work runs as detached `nohup` processes writing their own logs and records; the main session or
a few sub-agents start and watch them. **Nothing depends on a sub-agent or the main session staying
alive**: the last ledger entry (section 15) says where the run is and what comes next, and
`AW_STATE` holds the detail.

**Phases** (ids used in the ledger), per candidate where relevant:
`P0` decisions · `P1` build B1–B7 · `P2` acceptance A1–A10 + A-`<cand>` · `P3..P5` per-candidate
search → freeze (run the five candidates **one at a time** by default — see 11 — each: start,
adapt within B, freeze, per-step scan) · `P6` dev diagnostic · `P7` isolation scan · `P8` the one
common final window (6 arms) · `P9` analysis · `P10` five results posts. Each phase has a resume
rule (skip done units; redo an idempotent step; never post twice).

### 10.1 Progress log
`AW_STATE/progress/<cand>.log` (one line per event) and a `PROGRESS.md` table regenerated every 5
min by `status.py` (phase, % done, last event, rollouts used, optimizer tokens + proxy USD, ETA,
last checkpoint number/age/pushed), per candidate + the final window.

### 10.2 The ledger = this document (guideline 7.3)
Checkpoint entries are **appended to the bottom of this file** (section 15), newest last, never
editing an earlier entry, under **`flock(AW_STATE/ledger.lock)`** so concurrent evaluation agents
cannot clobber each other (guideline 7.3). Each entry: a human prose line + a fenced `json` block
(`cp`, `prev_cp`, `utc`, `kind`, `phase`, `candidate`, `done_through`, `next`, `counts`, `spend`,
`artifacts` by sha256, `code` sha, `open_decisions`). `kind` ∈ {phase_start, result, phase_done,
heartbeat, decision, abort, resume, restore, rebuild, repair, error, cap_spend, posted}. After every
checkpoint the file + `docs/EVAL_APPWORLD_5_STATE/` + `examples/appworld/` are committed (pathspec
only) and pushed to `origin eval5` (never `--force`). **Content rules (everything pushed/posted is
published):** no secret, no gold value/solution, **no task id**, no task/supervisor text, no
trajectory text, no optimizer-prompt text, **no per-task test outcome** (with public split files a
per-cell list maps back to ids). The one learned text that may be published is a candidate's artifact
**only if** it is a memory/prompt that passed the per-item lint (8-gram / contact checks); the agent
confirms this per candidate before posting. A `status_doc.py`-style content filter checks every
staged file and refuses the checkpoint on any task id, `.env` string, train/dev 8-gram, or supervisor
contact.

**Cadence.** Checkpoint at once on every phase start/end, decision, build step, acceptance check,
freeze, scan, error, abort, resume, and each completed search milestone; coalesce fast results
(dev/final cells) to ≤ 1 entry per 5 min; a heartbeat if 25 min pass without one. So the checkpoint
resolution is ≤ 30 min and the most recent in-flight step is the only acceptable loss (guideline 7.3).

### 10.3 What is pushed vs local
Pushed (publishable): this ledger; `manifest.json` (hashes, seeds, caps — orders are **regenerated**
from seeds and checked against sha256, so no id is pushed); each candidate's `progress.json` (counts/
spend/scan counts, steps named by index); each candidate's lint-checked `artifact/`; `final/
progress.json` (counts only); `final/analysis.json` + `RESULTS.md`; the code. Local only (`AW_STATE`):
episode records, trajectories, optimizer-prompt/response logs, `order.json`, final per-cell records,
`.env`. Rebuildable only (`AW_BUILD`): clones, venvs, data roots, model cache. **Worst-case redo** on
host loss: the build (~1–2 h), the one in-flight search step, dev cells since the last coalesced
checkpoint (≤5 min), and (if local final records are lost) the **whole final window** (the one place
"minimize redo" yields to the content rules — per-cell test outcomes are not pushed).

### 10.4 Resume
One command (`resume.py`, modelled on the ACE sibling's): `git fetch`; parse the last ledger entry's
json; refuse if `RUNNING.pid` is alive; rebuild any missing/mismatched `AW_BUILD` item from
`manifest.json` (re-`chmod 000 root_full` if before P8); reconcile local records with the pushed
state; continue at `next` (skip done units; redo idempotent steps; never repost). Append a `resume`
entry, relaunch the phase runner under `nohup`, restart the heartbeat.

---

## 11. Acceptance checks before any counted rollout

Common (base plan A1–A8, carried over, run once):

| id | check |
|---|---|
| A1 | `aws/claude-sonnet-5-5` answers through each candidate's gateway shim (header sent, no `temperature` — G1; no refusal — G2) and through the `claude` CLI (for the agentic arms). |
| A2 | RITS via the patched client: model listing shows `max_model_len` 40,144; 48 concurrent short requests return 200, no 429; 1 dev episode completes; the RITS key appears nowhere under `AW_HOME`/`/tmp/aw_eval5`/pushed files. |
| A3 | REPL isolation (base F1): `import os`, `open(answer.json)`, a `pathlib` read all fail; `root_opt` has no test id; `root_full` unreadable during search. |
| A4 | injection: on 1 dev task the seed's first request is byte-identical to stock; a memory block lands before `My name is:`; helpers+notes work with the original doc text unchanged; a lint-violating artifact is rejected without a rollout. |
| A5 | scoring: a train task's released compiled solution → reward 1, a no-op → 0; the persisted record has no `trace`/gold; scoring twice is identical. |
| A6 | splits/seal: `tasks("train")`=`train.txt` (90, order of `load_task_ids`); a test id is refused without `AW_ALLOW_SEALED`. |
| A7 | the dev diagnostic / final-window order is reproducible from its seed and matches its sha256. |
| A8 | context + `M_cap`: 10 no-memory dev episodes stay < 34K prompt tokens; `P_max`/`H_max` measured; `M_cap` computed and recorded; 3 dev episodes with an `M_cap`-sized memory block stay < 34K and tiktoken is within 2% of vLLM. |
| A9 | **optimizer isolation (agentic arms only):** section 8 — Claude Code's sandbox hides every planted gold secret, blocks the network except the gateway, blocks AF_UNIX sockets, and normal work still runs; neutral framing so the `[cyber]` classifier does not refuse. |
| A10 | ledger/resume: a mini run killed mid-way resumes with no unit run twice, append-only pushed entries, coalescing + heartbeat work, the content filter refuses an entry containing a task id or `.env` string. |

Per candidate: **A-`gepa`, A-`skillopt`, A-`wikiskill`, A-`evoskill`, A-`metaharness`** (defined in
7.x). None of the acceptance rollouts are counted (S1).

**Container discipline (guideline 7.2 / 7.4, `docs/CONTAINER_AGENT.md`).** Before spawning any
sub-agent or worker pool, run `memcheck`; start no more than `subagents_that_fit` and never on
CAUTION/STOP; size `AW_WORKERS`/pools from `cpu.max` (8) and memory (32 GB), **never `nproc`** (which
reads 96 here); keep heavy candidate searches **sequential** (one candidate at a time) so two
24-worker jobs never coexist — this is exactly the OOM-restart incident the base plan hit. On an OOM
restart (`container_age_s` < session, `oom.group=1`), **do not relaunch unchanged**: resume
(section 10.4) and relaunch smaller. The final window may use more workers (48) because it runs
alone.

---

## 12. Final window, statistics and the five reports

- **Freeze.** Each candidate's champion artifact (section 7) is copied into `final/artifacts/<cand>/`
  and tree-hashed; `seed` = `seed_capability`. An inert candidate (nothing beat the seed) is frozen
  as the seed and labelled "inert".
- **Window.** 168 `test_normal` tasks × **6 arms** × **2 trials** = **2,016 episodes**, in **one**
  shuffled order (recorded seed, order-file hashed), `AW_ALLOW_SEALED=final-eval-only`,
  `APPWORLD_ROOT=root_full` (unlocked at P8 start, logged), 48 workers, trial seeds `5000+trial`,
  infra retries ≤ 3 with new seeds; a cell that still fails is scored 0 (primary) and reported
  missing (sensitivity). Only rewards/counters/infra flags are read; **no test trajectory is ever
  read** by a person or an LLM.
- **Metrics (identical for all arms — guideline 6.2).** TGC (mean over tasks of mean over trials of
  success); SGC (a scenario passes in trial k iff all its tasks pass; averaged over k); both by
  difficulty (Easy 57 / Medium 48 / Hard 63). Paired difference **`<cand> − seed`** for each
  candidate, scenario-clustered paired bootstrap (56 clusters, 10,000 resamples) 95% CI, unadjusted.
  **Cost/tokens/latency table per arm:** target prompt+completion tokens/task, steps/task, step-cap
  hits, context-exceeded, collateral damage, max prompt tokens, memory tokens/step (the M arms),
  per-episode seconds; optimizer input/output tokens + calls + proxy USD (from each shim's
  `optimizer_usage.jsonl`; proxy at list prices $3/$15 per MTok for Sonnet, flagged as a proxy);
  counted search rollouts; dev diagnostic score; share of tasks whose 2 trials agree (base F10);
  wall time per phase.
- **Comparison discipline.** These are **artifact-level** statements (one search seed per method);
  the five candidates are each compared **to the seed inside the one window**, not ranked against
  each other (unmatched search budgets; window-to-window drift of ~4–6 TGC points for identical
  artifacts, base F10/Appendix C — a ~10-point gap is near what one window resolves). Each report
  carries a **"What this <method> is and is not"** paragraph listing the choices that deviate from
  the method's published form (optimizer model = Sonnet not the target/Opus; the common stock
  template + memory slot; 1 epoch/limited iterations within B; gold-free F1 feedback; `M_cap`; and,
  for `wikiskill`, that it is a reimplementation), so a null or large result is read as a result
  about **this configuration**.
- **Reports (guideline 5).** One markdown comment per candidate, posted to that candidate's tracking
  issue with `gh issue comment <n> -R skillberry-ai/cap-evolve --body-file …`: setup block (commits,
  models, settings, decisions); the main table (`<cand>` + seed TGC/SGC, Δ vs seed with CI); the
  difficulty table; the cost/tokens/latency table; what changed (artifact summary + 3 example items,
  lint-clean); isolation scan counts; the "what this is and is not" paragraph; deviations (section
  13) and what the numbers cannot support. Draft to `final/RESULTS.md` first; a `posted` ledger entry
  records each URL. No task text/ids/solutions/gold are posted (AppWorld redistribution rule). A
  short cross-candidate summary (each candidate's Δ-vs-seed side by side, with the drift caveat) may
  be added to the ledger, but it is explicitly **not** a ranking.

---

## 13. Deviations from the base plan and the sibling plans

| base / sibling | here | why |
|---|---|---|
| arms seed, cape-hc, altk | seed + five new candidates | task scope (guideline 4) |
| optimizer isolation via the namespace wrapper (`sandbox/claude`) | **Claude Code's own sandbox** for the agentic arms; pure-LLM arms need none | the pod refuses `unshare` (1.2, base F17); the sandbox passes A9 here (fix doc) |
| all state under `/tmp/aw_eval` | durable state on `/workspace/aw_eval5` + pushed git state; only AppWorld outputs on `/tmp` | `/tmp` is wiped between sessions; OOM-restart durability (ACE sibling) |
| final window 1,008 (3 arms) | **2,016** (6 arms × 168 × 2) | six arms |
| results comment on #804 | **one tracking issue per candidate** on `skillberry-ai/cap-evolve`, periodic updates | guideline 5 |
| cap-evolve `optimizer_guard.sh` / claude shim (F14/F15) | not used; the two agentic arms use Claude Code's sandbox, the three pure-LLM arms have no shell | mechanism change (1.2) |
| memory lint 30,000 chars | the same, plus the token `M_cap` (≈13K) | RITS 40K window (base §0/§13, ACE sibling) |
| 3 search seeds, matched budget | 1 seed/arm, each ≤ B=900 counted rollouts, budgets not matched across methods | smoke scale; counts reported |
| GEPA/EvoSkill/etc. native gold-in-feedback or shell access | gold-free F1 feedback; gold-leaking inputs de-fanged; agents sandboxed and tool-restricted | isolation (guideline 7.1); base F8/F14/F19/F20 |
| each method's native epoch/iteration count | reduced where needed to fit B=900 and 10M optimizer tokens | smoke scale; disclosed per candidate |
| method optimizer = the target model (several papers) | `aws/claude-sonnet-5-5` for all | guideline 6.3; one optimizer variable, cannot favour one arm |

Per-candidate conflicts and their least-distorting resolutions are in section 7.

---

## 14. Budget and timeline (projection)

| phase | counted rollouts | wall (estimate) |
|---|---|---|
| P1 build + P2 acceptance (incl. A-`<cand>`) | ≈ 60 (not counted) | 3–5 h |
| P3–P5 five candidate searches, sequential, ≤ 900 each | ≤ 4,500 | 20–35 h (dominated by the two agentic arms + SkillOpt's full-val gates) |
| P6 dev diagnostic (6 arms × 57, as needed) + P7 scan | ≈ 342 | 1 h |
| P8 one final window (6 arms × 168 × 2) | 2,016 | 3–5 h |
| P9 analysis + P10 five posts | 0 | 1 h |
| **total** | **≈ 7,000** | **≈ 28–45 h** after the build |

Throughput basis: base plan's 30–300 s/episode, RITS at 48 concurrent with no errors, no RITS
budget. Optimizer spend: each candidate ≤ 10M non-cache-read tokens; the three pure-LLM arms ~2–8M;
the two agentic arms ~10 MTok/iteration (far larger — reported separately). All usage recorded
exactly and reported per provider (RITS unpriced for the agent; the gateway for the optimizer).
Run candidates **sequentially** (section 11) to respect the 32 GB / 8-CPU limit; within a candidate,
episodes are the parallel unit (`AW_WORKERS` sized by `memcheck`).

## 15. Execution ledger (appended during the run)

> This section is appended to during execution (guideline 7.3), newest entry last, under
> `flock(AW_STATE/ledger.lock)`. The header above is written once; nothing below it is ever edited.
> The first entry (CP-0000) records the five tracking-issue numbers. Content rules: section 10.2.

<!-- CHECKPOINTS BELOW THIS LINE -->

## CP-0000 · 2026-10-17T23:14Z · P0 decisions · decision

Execution of the eval-5 plan starts. Decisions D1–D8 (section 2) are taken as written; no open decision.
Tracking issues (skillberry-ai/cap-evolve): gepa #881, skillopt #882, wikiskill #883, evoskill #884, metaharness #885; each already carries its plan projection as the first post.
Host: memcheck limit 32,768 MB, cpu_limit 8, oom.group 1. Next: P1 build.

```json
{"cp": 0, "prev_cp": null, "prev_commit": "cb68423b4335d0f2d99f14603980a657b754da0f", "utc": "2026-10-17T23:14:03Z", "kind": "decision", "phase": "P0", "done_through": "P0/decisions", "next": "P1/B1", "candidate": null, "counts": {}, "spend": {}, "artifacts": {"STATE/manifest.json": "3c4c9266ad803a11d4b66a5f85c31f2192412c8615beb530a82d2bcc3120246c"}, "code": "ec30d13ae3acc7595248614c52c93e9d833c100a", "open_decisions": [], "issues": {"gepa": 881, "skillopt": 882, "wikiskill": 883, "evoskill": 884, "metaharness": 885}}
```

## CP-0001 · 2026-10-17T23:14Z · P1 build · result

B1–B5 and B7 done. B1: AppWorld @42b5bcf + LFS + extra-headers patch (diff sha256 recorded). B2: venv-aw (CPython 3.11, pydantic 2.12.5, gepa 0.1.4 installed alongside). B3: data downloaded; splits 90/57/168/417, scenarios 30/19/56/139, difficulty counts match; publishing cache built. B4: root_opt 148 task dirs (train+dev+_base_), 0 test-id hits; lint cache and optimizer reference dir built; root_full chmod 000. B5: five candidate repos cloned at their D4 pins (all verified); venv-skillopt (3.11) and venv-evoskill (3.12) built; wikiskill and metaharness drivers run in venv-aw. B7: .env present with variable names ['RITS_API_KET', 'RITS_URL'] (values not read here).
B6 (drivers) comes next together with acceptance; one dev episode already ran end to end through the shared evaluator (not counted). Next: P2 acceptance A1.

```json
{"cp": 1, "prev_cp": 0, "prev_commit": "e9ed3d1bf0bd4f44ffa3a63f48093c08bdd4e384", "utc": "2026-10-17T23:14:28Z", "kind": "result", "phase": "P1", "done_through": "P1/B5", "next": "P2/A1", "candidate": null, "counts": {}, "spend": {}, "artifacts": {"STATE/manifest.json": "3c4c9266ad803a11d4b66a5f85c31f2192412c8615beb530a82d2bcc3120246c"}, "code": "e9ed3d1bf0bd4f44ffa3a63f48093c08bdd4e384", "open_decisions": []}
```

## CP-0002 · 2026-10-17T23:24Z · P2 acceptance · result

A1 pass: aws/claude-sonnet-5-5 answers through the shared gateway shim (header sent, no temperature, JSON parses) and through the claude CLI (modelUsage = aws/claude-sonnet-5-5). A2 pass: RITS max_model_len 40,144; 48/48 concurrent requests 200, 0 × 429; 1 dev episode with lm_calls logging; RITS key found nowhere under AW_HOME, /tmp/aw_eval5, the pushed state or the code. A3+A5 pass (base checks unchanged: import os / open / pathlib reads blocked; root_opt has no test data; released solution → 1, no-op → 0, scoring deterministic, no trace/gold persisted; root_full locked). A4 pass (seed byte-identical to stock, 23 messages; memory slot before 'My name is:'; helpers + notes; a lint-violating candidate rejected with 0 rollouts counted). A6 pass (train order = load_task_ids; outside id and test split refused). A7 pass (dev-diagnostic order reproducible from its seed, 342 cells).
Container: 10 concurrent episodes peak about 4.1 GB anonymous memory (≈0.4 GB each), so 24 search workers and 48 final-window workers fit the 32 GB limit. Next: A8 (running), then A9/A10 and the per-candidate checks.

```json
{"cp": 2, "prev_cp": 1, "prev_commit": "a47ec421713a0c7da9221f6949f4fcb2aef9c21c", "utc": "2026-10-17T23:24:38Z", "kind": "result", "phase": "P2", "done_through": "P2/A7", "next": "P2/A8", "candidate": null, "counts": {}, "spend": {}, "artifacts": {"STATE/acceptance.json": "d68ff21a459d746edee5992aca70a8f35c0ead30e200c4c206cfacd600eb694d", "STATE/manifest.json": "7c991829b9684fcd144d8ac4eb2f117fe074fe44adf8150943e9a40a80f39981"}, "code": "e9ed3d1bf0bd4f44ffa3a63f48093c08bdd4e384", "open_decisions": []}
```

## CP-0003 · 2026-10-17T23:33Z · P2 acceptance A8 · result

A8 pass: 10 no-memory dev episodes (0 infra errors), longest prompt 10,985 tokens; lowest history chars/token 3.544 → H_max 16,930; P_max 3,230 over the 147 train ∪ dev stock prompts (chat-template overhead 157 tokens, constant). M_cap = min(30,000 chars, 34,000 − P_max − H_max) = 13,500 tokens (floored to 500; the ACE sibling found the same). With the largest memory the lint allows (30,000 chars ≈ 5,341 tokens, so the char cap binds first) 3 dev episodes peaked at 14,129 prompt tokens; tiktoken o200k_harmony matched vLLM exactly on their first request.
Next: A9 (sandbox isolation for the agentic arms) and A10 (ledger/resume), then the per-candidate checks.

```json
{"cp": 3, "prev_cp": 2, "prev_commit": "6297dae8d43497ce8f0e57fe1d7fe3545a32ba28", "utc": "2026-10-17T23:33:43Z", "kind": "result", "phase": "P2", "done_through": "P2/A8", "next": "P2/A9", "candidate": null, "counts": {}, "spend": {}, "artifacts": {"STATE/acceptance.json": "4d502505b3d1eef1650e7ab84637add1f3bd430619569fbf2759067bd28989db", "STATE/manifest.json": "79a254c9371e2a21f30c8ccdb840ca13fe66e762301eeaf37fcd375724d65b1c"}, "code": "6297dae8d43497ce8f0e57fe1d7fe3545a32ba28", "open_decisions": []}
```

## CP-0004 · 2026-10-17T23:38Z · P2 acceptance A9 (CLI) · result

A9 pass for the claude-CLI path (the metaharness proposer's flags: Read, Glob, Grep, Write, Edit, Bash, Agent; acceptEdits; --setting-sources ''; Claude Code sandbox enabled, failIfUnavailable, allowUnsandboxedCommands=false; denyRead + Read/Edit deny rules on every gold, test, AppWorld, evaluator, secrets and transcript location; network restricted to the gateway host). 11 secrets planted (root_opt, a train ground_truth dir, root_full, AppWorld generate/ and src/, AW_STATE, episode scratch, the repo, candidate clones, a transcript dir, a probe dir): 0 leaked. Tool uses {'Bash': 7, 'Read': 11, 'Grep': 2, 'Write': 1}; Bash cat/find/cp saw nothing, every Read was refused by the deny rules, an outbound HTTPS request and an AF_UNIX socket were both refused; a workspace file was written and the lint ran (ok). Neutral 'which files are visible' framing, no classifier refusal.
One fix during the check: denying Claude's whole temp root broke the CLI's per-command cwd file; the deny now covers only other sessions' dirs under it. The Agent-SDK path (evoskill) gets its own A9 in A-evoskill. Next: A10.

```json
{"cp": 4, "prev_cp": 3, "prev_commit": "c2df2d095a57bcf06018b87a957969c59b167169", "utc": "2026-10-17T23:38:09Z", "kind": "result", "phase": "P2", "done_through": "P2/A9", "next": "P2/A10", "candidate": null, "counts": {}, "spend": {}, "artifacts": {"STATE/acceptance.json": "ad97a1567098259cf5bc7f6309617e97b3bb329193e5319ea92d6623314b03cb"}, "code": "c2df2d095a57bcf06018b87a957969c59b167169", "open_decisions": []}
```

## CP-0005 · 2026-10-17T23:38Z · P2 code · result

B6 code committed so far: shared evaluator, gateway shim, sandbox settings, window runner (dev + final), resume/pipeline, acceptance checks A1–A10, the gepa and skillopt drivers. Next: A10.

```json
{"cp": 5, "prev_cp": 4, "prev_commit": "c130d33a8b5229f90e151fd5458e3972e0bd14ce", "utc": "2026-10-17T23:38:59Z", "kind": "result", "phase": "P2", "done_through": "P2/A9", "next": "P2/A10", "candidate": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "c130d33a8b5229f90e151fd5458e3972e0bd14ce", "open_decisions": []}
```

## CP-0006 · 2026-10-17T23:56Z · P2 acceptance A10, A-gepa · result

A10 pass (throwaway clone + branch, deleted afterwards): a 12-cell mini window SIGKILLed after 4 cells and resumed ran 0 cells twice and finished all 12 in the recorded order; entries coalesced; history append-only; a heartbeat after 60 s of silence marked the killed runner stalled; a push failure kept the commit local and the next checkpoint pushed it; the content filter refused an entry with a task id and one with an .env value.
A-gepa pass (3 dev tasks as trainset, 1 as valset, throwaway, not counted): GEPA 0.1.4 ran 3 iterations / 14 metric calls; the <new_text> reflection parsed on the first call (0 parse failures, 0 lint rejects, 0 refusals, 0 gateway errors, no temperature); the accepted child lints clean. Fix found by this check: the evaluator replayed GEPA's repeated parent-minibatch evaluations from the cache, which GEPA counts as fresh metric calls; replays are now keyed by call site + iteration (GEPA, SkillOpt step dir, WikiSkill iteration), so only a resumed step is replayed. Next: A-skillopt, A-wikiskill, then the agentic arms.

```json
{"cp": 6, "prev_cp": 5, "prev_commit": "33409f881fbd48075e2bcb4a97ec33fc434f57cc", "utc": "2026-10-17T23:56:32Z", "kind": "result", "phase": "P2", "done_through": "P2/A-gepa", "next": "P2/A-skillopt", "candidate": null, "counts": {}, "spend": {}, "artifacts": {"STATE/acceptance.json": "e68275246b4f424494ded1245effe81045c9f7629009845a12206b551cb0e254"}, "code": "33409f881fbd48075e2bcb4a97ec33fc434f57cc", "open_decisions": []}
```

## CP-0007 · 2026-10-18T00:04Z · P2 acceptance A9 (Agent SDK, evoskill) · result

A9 pass for the Agent-SDK path with EvoSkill's de-fanged options (Proposer Read/Glob/Grep; Skill Builder Read/Write/Edit/Glob/Grep; Bash, WebFetch, WebSearch, Skill, TodoWrite, BashOutput removed and disallowed; setting_sources []; the same sandbox settings; scratch git project root). 11 planted secrets, 0 leaked; tool uses {'Read': 22, 'Grep': 1, 'Glob': 1, 'StructuredOutput': 2, 'Write': 2} (no Bash or web tool); the builder wrote in its workspace. G3 exception checked: the SDK's structured output (output_format json_schema) works through the gateway for both roles, so no text-JSON fallback is needed. Next: A-skillopt, A-wikiskill (running), A-evoskill, A-metaharness.

```json
{"cp": 7, "prev_cp": 6, "prev_commit": "412da03013bc80c32a9803181f9628d9f0fe0548", "utc": "2026-10-18T00:04:44Z", "kind": "result", "phase": "P2", "done_through": "P2/A9-evoskill", "next": "P2/A-skillopt", "candidate": null, "counts": {}, "spend": {}, "artifacts": {"STATE/acceptance.json": "2cc77d5f54b1c0e28fa30ff3c4fc1e2c67af9c15b92e6878322f82cc208eb22c"}, "code": "412da03013bc80c32a9803181f9628d9f0fe0548", "open_decisions": []}
```

## CP-0008 · 2026-10-18T00:19Z · P2 acceptance A-skillopt · result

A-skillopt pass (1 epoch / 1 step, 3 dev tasks as train, 1 as val, throwaway, not counted): ReflACTTrainer ran with SkillOpt's own defaults; the monkeypatched optimizer (openai_compatible.chat_optimizer → gateway shim) answered the analyst stage with a parseable patch (0 errors, no temperature); rollouts wrote memory/playbook.md, ran the agent and returned hard/soft; 3 compacted conversation.json files carry the gold-free F1 report as the final system message; the gate rejected the step (val did not strictly improve); an over-cap skill (54,000 chars) was lint-rejected without a rollout; 'Hidden Reference' never appears in any optimizer prompt. Next: A-wikiskill (re-run after a fix), A-evoskill, A-metaharness.

```json
{"cp": 8, "prev_cp": 7, "prev_commit": "c904bb72e7544eb50dbfb0b58e886ebe77103996", "utc": "2026-10-18T00:19:42Z", "kind": "result", "phase": "P2", "done_through": "P2/A-skillopt", "next": "P2/A-wikiskill", "candidate": null, "counts": {}, "spend": {}, "artifacts": {"STATE/acceptance.json": "644a314c71e3f9c83803f481836ba7d46f9f803672e4acbddeb4255d4693a438"}, "code": "c904bb72e7544eb50dbfb0b58e886ebe77103996", "open_decisions": []}
```

## CP-0009 · 2026-10-18T00:38Z · P2 acceptance A-wikiskill · result

A-wikiskill pass on the second run (2 iterations, 3 dev tasks as train, 2 as val, throwaway workspace, not counted): the gateway LLM answered the Wiki Maintainer (3 pattern pages written) and the ReAct Skill Proposer (reads of wiki pages and traces/<task> paths resolved), one skill was created and accepted (val 0.5 → 1.0), rendered into memory/playbook.md (3,180 chars, lint clean), every raw trace ends with the F1 EVALUATION message, and the full proposal text is in skill-impact.md; 0 gateway errors. The first run produced no proposal: with the paper's Appendix E prompt (which names read_file/finish but no call syntax) the model emitted XML-style tool calls, the vendored parser did not recognize them, and one turn hit max_tokens. Fixes: a short 'How to call the tools' section (one JSON tool call per reply) appended to our copy of the prompt, and XML-style calls read as JSON (recorded in wikiskill/prompts/SOURCE.md). Also added to the shared candidate lint: the memory slot now gets the same 8-gram / supervisor-contact check as the prompt, helpers and notes (the base lint checked only its length). Next: A-evoskill, A-metaharness (running).

```json
{"cp": 9, "prev_cp": 8, "prev_commit": "d7fbe4c0fd7bda052fa86f268b25b3ae59663978", "utc": "2026-10-18T00:38:48Z", "kind": "result", "phase": "P2", "done_through": "P2/A-wikiskill", "next": "P2/A-evoskill", "candidate": null, "counts": {}, "spend": {}, "artifacts": {"STATE/acceptance.json": "810b42d99dae527a7cec1c551ce68c43afe72a68fba23de8303eb5b43013c209"}, "code": "d7fbe4c0fd7bda052fa86f268b25b3ae59663978", "open_decisions": []}
```

## CP-0010 · 2026-10-18T00:56Z · P2 acceptance A-metaharness · result

A-metaharness pass (throwaway workspace, 4 dev tasks as the search set, not counted): (b) the validator rejected a candidate with a file outside the four harness files and one embedding a task id, and accepted the seed; (c) the evaluator wrote gold-free per-task dirs (trajectory.md + eval.json, no gold strings) and returned rewards; (a) one real proposer iteration through the vendored claude_wrapper (aws/claude-sonnet-5-5, Read/Glob/Grep/Agent/Write/Edit/Bash, the SKILL.md as system prompt, the A9-checked sandbox and --permission-mode acceptEdits in place of the wrapper's permission bypass) exited 0 after 5 min with 28 tool calls (two sub-agents, as the skill prescribes), wrote a valid pending_eval.json and only allowed files; the candidate validated, smoke-tested and was benchmarked. Fixes found here: the proposer's env swap had dropped PATH (exit 127); the seed copy carried a non-harness README; and the proposer, needing a Python with jinja2 for the lint, listed the build venvs — the build venvs are now denied too, and the workspace gets its own lint venv (jinja2 + tiktoken only) and an offline tiktoken cache. A-evoskill is re-running after a fix (Claude Code protects .claude/ even under acceptEdits, so the Skill Builder could not write SKILL.md; a write gate now allows only program-skill files). Next: start the counted searches, one candidate at a time, beginning with gepa.

```json
{"cp": 10, "prev_cp": 9, "prev_commit": "0739f3e146060520e19dbfcc9391a7b6d0ad140d", "utc": "2026-10-18T00:56:25Z", "kind": "result", "phase": "P2", "done_through": "P2/A-metaharness", "next": "P2/A-evoskill", "candidate": null, "counts": {}, "spend": {}, "artifacts": {"STATE/acceptance.json": "cbabb2ad366e1c50e4dd95f04262c5ecb4d7a869bf52438313fd116ecb1bbed0"}, "code": "0739f3e146060520e19dbfcc9391a7b6d0ad140d", "open_decisions": []}
```

## CP-0011 · 2026-10-18T01:12Z · P2 acceptance done · phase_done

A-evoskill pass on the third run (2 iterations on 6 dev tasks as the train pool and 3 as val, scratch git project root, not counted): the Proposer's queries carry no 'Ground Truth' line and no reference answer (the de-fanged query and prompt copy), the Skill Builder wrote a SKILL.md with Read/Write/Edit/Glob/Grep only (no Bash or web), the program's skills rendered into a 3,289-char playbook, the run returned a reward-only AgentTrace with a gold-free result, structured output worked, usage was logged per role. Fixes found here: Claude Code protects .claude/ even under acceptEdits, so a can_use_tool write gate now allows Write/Edit only to program-skill files (never the meta-skills, settings or hooks), and Write/Edit are left out of allowed_tools so the gate is not shadowed.
All acceptance checks pass (a1, a10, a2, a3a5, a4, a6, a7, a8, a9_cli, a9_sdk_evoskill, a_evoskill, a_gepa, a_metaharness, a_skillopt, a_wikiskill). P2 done. Next: P3 counted searches, one candidate at a time (gepa → skillopt → wikiskill → evoskill → metaharness), each search → freeze → per-candidate scan, run by pipeline5.py under nohup.

```json
{"cp": 11, "prev_cp": 10, "prev_commit": "1b13eb8f8c842f568049cc9cfbc8f17d1a51ee90", "utc": "2026-10-18T01:12:31Z", "kind": "phase_done", "phase": "P2", "done_through": "P2/done", "next": "gepa/search", "candidate": null, "counts": {}, "spend": {}, "artifacts": {"STATE/acceptance.json": "f9021a177b26592cc4f8fb33e432b7bb2836c7fcb610bcd426d82048d052eaa7"}, "code": "1b13eb8f8c842f568049cc9cfbc8f17d1a51ee90", "open_decisions": []}
```

## CP-0012 · 2026-10-18T01:38Z · P2 heartbeat · heartbeat

No checkpoint for 25 min. Phase P2, last result: P2/done.
Runner: alive (pid 32143). Last log line: `2026-10-18T01:37:40Z | gepa | P3/train | 1/3 episodes, passed 0, infra errors 0`.
Next: gepa/search.

```json
{"cp": 12, "prev_cp": 11, "prev_commit": "f0e15476f6777e7d776b120a5ce8e71c46372d1c", "utc": "2026-10-18T01:38:29Z", "kind": "heartbeat", "phase": "P2", "done_through": "P2/done", "next": "gepa/search", "candidate": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "f0e15476f6777e7d776b120a5ce8e71c46372d1c", "open_decisions": [], "runner": "alive"}
```

## CP-0013 · 2026-10-18T01:40Z · P3 gepa search · result

GEPA iteration 1: accepted=False, candidates 1, best dev 0.4211, metric calls 63/987.
Counted rollouts 63/900; optimizer 1 calls, 0.02M in / 0.01M out tok, $0.17 proxy; reflection lint rejects 0, parse fails 0, refusals 0.

```json
{"cp": 13, "prev_cp": 12, "prev_commit": "03367bc299b4cf7366e491d7d12ba5e346b93f39", "utc": "2026-10-18T01:40:46Z", "kind": "result", "phase": "P3", "done_through": "gepa/search/iteration 1", "next": "gepa/search", "candidate": "gepa", "counts": {"gepa": {"counted_rollouts": 63}}, "spend": {"gepa": {"in": 21768, "out": 6923, "proxy_usd": 0.17}}, "artifacts": {"STATE/gepa/progress.json": "6a55dd84000aea9ed45b09b2fb7058321fc589296d3ddacdf0d4e18725b55032"}, "code": "03367bc299b4cf7366e491d7d12ba5e346b93f39", "open_decisions": []}
```

## CP-0014 · 2026-10-18T01:56Z · P3 gepa search · result

GEPA iteration 2: accepted=False, candidates 1, best dev 0.4211, metric calls 69/987.
Counted rollouts 69/900; optimizer 2 calls, 0.05M in / 0.01M out tok, $0.37 proxy; reflection lint rejects 0, parse fails 0, refusals 0.

```json
{"cp": 14, "prev_cp": 13, "prev_commit": "f5d80d01d4955f1408c64e1f186a991d0847f60d", "utc": "2026-10-18T01:56:12Z", "kind": "result", "phase": "P3", "done_through": "gepa/search/iteration 2", "next": "gepa/search", "candidate": "gepa", "counts": {"gepa": {"counted_rollouts": 69}}, "spend": {"gepa": {"in": 50924, "out": 14705, "proxy_usd": 0.37}}, "artifacts": {"STATE/gepa/progress.json": "ad86acedc0d7e8974eec22366f9e2fbf59306bfbc07e9fdd4294ece9ba220958"}, "code": "03367bc299b4cf7366e491d7d12ba5e346b93f39", "open_decisions": []}
```

## CP-0015 · 2026-10-18T02:14Z · P3 gepa search · result

GEPA iteration 3: accepted=False, candidates 1, best dev 0.4211, metric calls 75/987.
Counted rollouts 75/900; optimizer 3 calls, 0.08M in / 0.02M out tok, $0.46 proxy; reflection lint rejects 0, parse fails 0, refusals 0.

```json
{"cp": 15, "prev_cp": 14, "prev_commit": "5d3d9dabc0a7b775723facb357b73f024e63ecd4", "utc": "2026-10-18T02:14:46Z", "kind": "result", "phase": "P3", "done_through": "gepa/search/iteration 3", "next": "gepa/search", "candidate": "gepa", "counts": {"gepa": {"counted_rollouts": 75}}, "spend": {"gepa": {"in": 76804, "out": 15433, "proxy_usd": 0.46}}, "artifacts": {"STATE/gepa/progress.json": "dbf6aec0fb0cf5464cb4c4b03aa7793b8f4a7dffc33c32ab98ad06a2703931cd"}, "code": "03367bc299b4cf7366e491d7d12ba5e346b93f39", "open_decisions": []}
```

## CP-0016 · 2026-10-18T02:40Z · P3 heartbeat · heartbeat

No checkpoint for 25 min. Phase P3, last result: gepa/search/iteration 3.
Runner: alive (pid 32143). Last log line: `2026-10-18T02:32:04Z | gepa | P3/dev | 55/57 episodes, passed 38, infra errors 0`.
Next: gepa/search.

```json
{"cp": 16, "prev_cp": 15, "prev_commit": "2505094ec39cc108eda0c6e51a41161fcae48d63", "utc": "2026-10-18T02:40:30Z", "kind": "heartbeat", "phase": "P3", "done_through": "gepa/search/iteration 3", "next": "gepa/search", "candidate": "gepa", "counts": {"gepa": {"counted_rollouts": 75}}, "spend": {"gepa": {"in": 76804, "out": 15433, "proxy_usd": 0.46}}, "artifacts": {}, "code": "03367bc299b4cf7366e491d7d12ba5e346b93f39", "open_decisions": [], "runner": "alive"}
```

## CP-0017 · 2026-10-18T02:41Z · P3 gepa search · result

GEPA iteration 5: accepted=True, candidates 2, best dev 0.6842, metric calls 141/987.
Counted rollouts 141/900; optimizer 4 calls, 0.10M in / 0.02M out tok, $0.62 proxy; reflection lint rejects 0, parse fails 0, refusals 0.

```json
{"cp": 17, "prev_cp": 16, "prev_commit": "10a8f7f606069bf6881e4c0b0cee1c6657e56924", "utc": "2026-10-18T02:41:22Z", "kind": "result", "phase": "P3", "done_through": "gepa/search/iteration 5", "next": "gepa/search", "candidate": "gepa", "counts": {"gepa": {"counted_rollouts": 141}}, "spend": {"gepa": {"in": 95869, "out": 22407, "proxy_usd": 0.62}}, "artifacts": {"STATE/gepa/progress.json": "f0bdd508f46032d345acdb9ddbc6c1215247942949e9f08ffac34a038ee165bf"}, "code": "03367bc299b4cf7366e491d7d12ba5e346b93f39", "open_decisions": []}
```

## CP-0018 · 2026-10-18T02:54Z · P3 gepa search · result

GEPA iteration 6: accepted=False, candidates 2, best dev 0.6842, metric calls 147/987.
Counted rollouts 147/900; optimizer 7 calls, 0.15M in / 0.04M out tok, $1.01 proxy; reflection lint rejects 2, parse fails 0, refusals 0.

```json
{"cp": 18, "prev_cp": 17, "prev_commit": "eae7e2d3f4ced5d4ed2a2817c100c1a5d16c0073", "utc": "2026-10-18T02:54:00Z", "kind": "result", "phase": "P3", "done_through": "gepa/search/iteration 6", "next": "gepa/search", "candidate": "gepa", "counts": {"gepa": {"counted_rollouts": 147}}, "spend": {"gepa": {"in": 146068, "out": 38113, "proxy_usd": 1.01}}, "artifacts": {"STATE/gepa/progress.json": "bcd24e9b8023e7dd8bf5fc9bf8ec5568ab905e1d5a443a46264e0aff76eab3ab"}, "code": "03367bc299b4cf7366e491d7d12ba5e346b93f39", "open_decisions": []}
```

## CP-0019 · 2026-10-18T03:07Z · P3 gepa search · result

GEPA iteration 7: accepted=True, candidates 3, best dev 0.6842, metric calls 210/987.
Counted rollouts 210/900; optimizer 8 calls, 0.16M in / 0.04M out tok, $1.07 proxy; reflection lint rejects 2, parse fails 0, refusals 0.

```json
{"cp": 19, "prev_cp": 18, "prev_commit": "b4bb0685dd0d10d7ce299ff4a74d32217bdf6c4b", "utc": "2026-10-18T03:07:26Z", "kind": "result", "phase": "P3", "done_through": "gepa/search/iteration 7", "next": "gepa/search", "candidate": "gepa", "counts": {"gepa": {"counted_rollouts": 210}}, "spend": {"gepa": {"in": 158546, "out": 39426, "proxy_usd": 1.07}}, "artifacts": {"STATE/gepa/progress.json": "a2a30a84e012234691e757f8195f8254964fda0a898f291b3ad858277196219a"}, "code": "03367bc299b4cf7366e491d7d12ba5e346b93f39", "open_decisions": []}
```

## CP-0020 · 2026-10-18T03:32Z · P3 heartbeat · heartbeat

No checkpoint for 25 min. Phase P3, last result: gepa/search/iteration 7.
Runner: alive (pid 32143). Last log line: `2026-10-18T03:32:24Z | gepa | P3/dev | 25/57 episodes, passed 17, infra errors 0`.
Next: gepa/search.

```json
{"cp": 20, "prev_cp": 19, "prev_commit": "60c9832c2a6b65626ed8dcdb02617dfae52f00ab", "utc": "2026-10-18T03:32:32Z", "kind": "heartbeat", "phase": "P3", "done_through": "gepa/search/iteration 7", "next": "gepa/search", "candidate": "gepa", "counts": {"gepa": {"counted_rollouts": 210}}, "spend": {"gepa": {"in": 158546, "out": 39426, "proxy_usd": 1.07}}, "artifacts": {}, "code": "03367bc299b4cf7366e491d7d12ba5e346b93f39", "open_decisions": [], "runner": "alive"}
```

## CP-0021 · 2026-10-18T03:53Z · P3 gepa search · result

GEPA iteration 8: accepted=True, candidates 4, best dev 0.6842, metric calls 273/987.
Counted rollouts 273/900; optimizer 9 calls, 0.18M in / 0.05M out tok, $1.27 proxy; reflection lint rejects 2, parse fails 0, refusals 0.

```json
{"cp": 21, "prev_cp": 20, "prev_commit": "56992bfd19504f8535435e1819dd8fd50585a9e6", "utc": "2026-10-18T03:53:00Z", "kind": "result", "phase": "P3", "done_through": "gepa/search/iteration 8", "next": "gepa/search", "candidate": "gepa", "counts": {"gepa": {"counted_rollouts": 273}}, "spend": {"gepa": {"in": 184926, "out": 47362, "proxy_usd": 1.27}}, "artifacts": {"STATE/gepa/progress.json": "4eec60bbe3cdcbed5825347df1019a347dbb2df0529c88294a828dc68a755bed"}, "code": "03367bc299b4cf7366e491d7d12ba5e346b93f39", "open_decisions": []}
```
