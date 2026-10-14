# AppWorld smoke test: ACE vs the seed agent

Status: PLAN, written 2026-10-14. Nothing in sections 4 to 12 has run yet. Decisions D1 to D3
carry over from the base plan; D4 is fixed by the design; **D5 to D7 are proposed and need the
user's choice before launch** (section 2). Section 16 lists the issues found when this plan was
reviewed.

This plan is a sibling of `docs/EVAL_SMOKE_TEST.md` (referred to below as "the base plan"),
which compared cap-evolve with ALTK-Evolve. Here the **only candidate evaluated is ACE** (Agentic
Context Engineering, Zhang et al., arXiv 2510.04618), scored against the same unmodified seed
agent. Every rule of the base plan is kept unless this document says otherwise; section 13
lists every difference from the base plan and from the Suite F design in issue #804
(`research/capevolve-paper/designs/appworld_experimental_design.md` on branch
`research/capevolve-paper-20261011` of `skillberry-ai/cap-evolve`, "the design"). The one new
requirement is a **checkpoint ledger**, the cumulative document `docs/EVAL_SMOKE_TEST_ACE_STATUS.md`,
pushed to branch `erezh-eval2-ace` at every checkpoint (section 10.2). The evaluation can be
aborted at any point and resumed from its last checkpoint, and no checkpoint is more than 30
minutes old.

---

## 0. Scope

| item | this smoke test |
|---|---|
| methods compared | ACE vs the unmodified seed agent. No cap-evolve, ALTK-Evolve, GEPA, SkillOpt, Trace2Skill or Tier 2 arms |
| ACE configuration | official no-ground-truth offline adaptation (`ACE_offline_no_GT_adaptation` semantics): Generator, Reflector, Curator; 1 epoch over the official `train` split; batch size 1; the common-harness agent is the Generator; the playbook is rendered into the memory slot of the stock prompt (design A-ACE) |
| optimizer model (ACE Reflector and Curator) | `aws/claude-sonnet-5-5`, through the gateway in `~/.claude/settings.json` (decision D1) |
| agent under test (ACE Generator and seed) | `openai/gpt-oss-120b-a100` on RITS, reasoning effort `medium`, temperature 0 |
| benchmark | AppWorld, **official splits only** (`data/datasets/{train,dev,test_normal,test_challenge}.txt`). ACE adapts on `train` (90 tasks); `dev` (57) is scored once as a diagnostic; results come from `test_normal` (168); `test_challenge` is not used. Section 9 gives the rules |
| search seeds | 1 |
| final scoring | `test_normal`, 2 trials per task, for 2 arms (seed, ACE playbook), in one interleaved window |
| deliverable | a markdown results comment on issue #804 (`skillberry-ai/cap-evolve`) |
| parallelism | at most 10 concurrent sub-agents (we use 2). Every long-running trial writes to a progress log |
| resumability | every checkpoint appends an entry to `docs/EVAL_SMOKE_TEST_ACE_STATUS.md`, committed and pushed to `origin erezh-eval2-ace`; results checkpointed at once (coalesced to ≤ 1 per 5 min), heartbeat if 25 min pass without one; one command resumes from the last entry (section 10) |

---

## 1. What was read and verified (2026-10-14)

Sources read: the base plan in full, including its Appendix A (execution log of 2026-10-13);
the design (section 3 on reference numbers, 4.4 on the memory surface, 6.3 A-ACE, the common
acceptance list); the ACE repository `ace-agent/ace` at `82709de0` (README, `EXTENDING_ACE.md`,
`ace/ace.py`, `ace/core/*`, `ace/prompts/*`, `pyproject.toml`, `.env.example`); the AppWorld fork
`ace-agent/ace-appworld` at `928e8687` (HEAD) and at `9f3e9215` (the submodule pin of `ace`):
README, `experiments/configs/ACE_*.jsonnet`, `experiments/code/ace/*.py`, `experiments/prompts/
appworld_react_*`, `experiments/playbooks/*`; the ACE paper (arXiv HTML, including the appendix
on the cost analysis and hyperparameter sensitivity).

The pins are the ones the design registered on 2026-10-12. On 2026-10-14 both are still the HEAD
of their repositories (`ace` last commit 2026-08-24, `ace-appworld` 2026-07-24).

### 1.1 Probes

The probes in section 1.1 of the base plan (RITS listing, authentication, context window
40,144 tokens, concurrency, reasoning; the optimizer gateway; the AppWorld install at
`42b5bcf`; 3 real dev episodes) are not repeated here as a separate step. **The host was found
fresh on 2026-10-14**: `/tmp/aw_eval`, `/workspace/worktrees/base/.venv`, `.env` and
`~/.local/bin/uv` do not exist, and no branch contains `examples/appworld/` (the code listed in
Appendix A.2 of the base plan was never committed). Free disk: 535 GB on the one volume that
holds both `/tmp` and `/workspace`. The probes are therefore re-run as acceptance checks A1 and
A2 (section 11), and all code is rebuilt (section 4).

### 1.2 Facts from the base plan that this plan depends on

Section 1.2 of the base plan holds unchanged: the AppWorld LLM client and its keyword limits;
the ReAct agent's Jinja variables, `USER:`/`ASSISTANT:` splitting and trimming; one live world
per process; the four official split files (90 / 57 / 168 / 417, pairwise disjoint, train and
dev share no scenario; `dev` is AppWorld's validation split). The cap-evolve and ALTK-Evolve facts
of that section do not apply here.

### 1.3 Facts about ACE from the code

- **Roles.** `adaptation_agent.py` (`StarAgent.solve_task_wo_gt`): for each training task, one
  Generator episode with the current playbook; when the episode ends (`task_completed()` or cost
  limit), the code calls `evaluate_task`, then `curator_call()`, which first calls
  `reflector_call()`. **One attempt and one reflection per task.** The retry loop
  (`num_retries = 5`) exists only in `solve_task_with_gt`.
- **No-GT reflector input** (`prompts/appworld_react_reflector_no_gt_prompt.txt`): the playbook
  and the full conversation history (the Generator's trimmed messages, including the prompt).
  The ground-truth code, execution error, test report and API-spec slots are literal
  `[not applicable]`; the `{{test_report}}` placeholder is not in this prompt, so the computed
  test report is never sent. The Reflector judges from execution feedback inside the trajectory
  only.
- **Curator** (`prompts/appworld_react_curator_prompt.txt`, `adaptation_react.py:curator_call`):
  input is the task instruction, the current playbook, the reflection and the conversation
  history. Output is JSON `{reasoning, operations}`; **only `ADD` operations** are accepted, into
  a whitelist of 8 sections (`strategies_and_hard_rules`, `apis_to_use_for_specific_information`,
  `useful_code_snippets_and_templates`, `common_mistakes_and_correct_strategies`,
  `problem_solving_heuristics_and_workflows`, `verification_checklist`,
  `troubleshooting_and_pitfalls`, `others`). Invalid JSON skips the update and keeps the
  playbook.
- **Playbook format.** Sections `## …`, bullets `[<slug>-<5 digits>] <content>`. In the AppWorld
  code `format_playbook_line` drops the helpful/harmful counters ("counts removed") and
  `update_bullet_counts` is never called: **the AppWorld variant has no counters**, unlike the
  finance code in `ace/` and the paper's description.
- **Initial playbook** `experiments/playbooks/appworld_initial_playbook.txt`: 1,469 characters,
  8 bullets that restate the key instructions of the AppWorld prompt, with all 8 section headers.
- **No size control in the AppWorld code.** There is no token budget. `bulletpoint_analyzer.py`
  (HEAD only; embedding model `all-mpnet-base-v2`, faiss, cosine threshold 0.90, LLM merge with the
  curator model) is off by default and is wired only into the batch path
  (`adaptation_react_parallel.py`). In `ace/`, `playbook_token_budget` (80,000) is only text in
  the curator prompt and is not enforced.
- **Size reached.** The shipped no-GT offline playbook after 1 epoch over train
  (`appworld_offline_trained_no_gt_playbook.txt`, DeepSeek-V3.1 in all roles) is **117,794
  characters, 318 bullets, about 29K tokens**: 4× the 30,000-character memory cap of the base
  plan (section 6.2), and close to gpt-oss-120b's whole 40,144-token window.
- **Generator template.** ACE uses its own 27,020-character prompt
  (`appworld_react_generator_prompt.txt`, about 6.8K tokens) with a `### PLAYBOOK BEGIN/END` block.
  The template params also compute `relevant_apis` from `world.task.ground_truth.required_apis`,
  which the template does not render. We do not use ACE's Generator, so neither the template nor
  this ground-truth load enters our harness (design: "replace only the Generator by the
  common-harness agent").
- **Official config** (`ACE_offline_no_GT_adaptation.jsonnet`): `dataset: train`, `num_epochs: 1`,
  `max_steps: 40`, temperature 0, `use_cache: true`, `max_retries: 50` with a 10 s wait, task
  order = `load_task_ids("train")`, no shuffle.
- **Batch path** (`run.py`, HEAD): `batch_size > 1` switches to `ace_adaptation_react_parallel`,
  which runs AppWorld in decoupled server mode, curates per batch with parallel curator chunks,
  and turns on **augmented shuffling with factor 2** by default (each trajectory is curated twice).
  It is a different algorithm from the paper's batch size 1.
- **LLM client** (`lite_llm_generator.py`): providers `sambanova`, `together`, `openai` only;
  `base_url` and `custom_llm_provider` forwarding is commented out, so it cannot reach our
  gateway. Line 53 contains a hardcoded third-party API key; it is never used or copied here.
- **Paper settings.** Batch size 1; "maximum number of Reflector refinement rounds and the maximum
  number of epochs in offline adaptation" 5; the AppWorld cost analysis uses "1 epoch and 1
  reflector refinement round" on 90 adaptation queries (357 rollouts vs GEPA's 1,434). The same LLM
  plays all three roles. gpt-oss-120b rows (Table 5, test_normal TGC / SGC): ReAct 54.8 / 33.9,
  ACE offline no GT 58.3 / 41.1, ACE offline with GT 61.3 / 39.3.
- **Licence**: both repositories Apache-2.0.

### 1.4 Lessons carried over from the first smoke test (base plan, Appendix A)

These are now part of the plan from the start, not findings to rediscover:

| base finding | how it is built in here |
|---|---|
| F1 REPL guard allows `os`, `pathlib`, `io` | the episode worker removes `os`, `pathlib`, `io`, `shutil`, `glob` from AppWorld's import allowlist, reads the RITS key from `.env`, builds the client, then removes the key from `os.environ` before the world starts; every episode records `fs_probe` (section 9) |
| F2 `max_output_tokens_per_task` not enforced | the episode loop enforces 100,000 completion tokens per task (termination `token_cap`) |
| F3 official gpt-oss config differs | kept as in base §5.1 and listed in section 13 |
| F4 setup snippet is a REPL interaction | neither arm has helpers or notes, so no snippet runs; both prompts are stock up to the memory slot |
| F5 structured-output path fails on the gateway | ACE uses text responses parsed as JSON (`extract_json_from_text`), so no `response_format`/`tool_choice` is sent; A1 checks it |
| F10 the seed is nearly deterministic at temperature 0 | D3 kept (2 trials); noted in the report |
| F11 the full ALTK set did not fit the memory cap | the ACE playbook has the same risk (section 1.3); the size rule is fixed in advance (D5, section 8.4) |
| F13 the 30-minute wall cap can fire | kept: classified as infrastructure, retried once |
| F14/F8 the claude-code optimizer read train/dev gold | ACE's Reflector and Curator are plain LLM calls with no tools and no file access; they see only what our driver sends. `root_full` stays `chmod 000` during search anyway |
| F16 the canary string is release-wide | the isolation scan counts test ids as the test-access signal |
| A.4 thread pool + one subprocess per episode | used as the episode runner from the start |

---

## 2. Decisions

| id | question | options | recommendation | **decision** |
|---|---|---|---|---|
| D1 | optimizer model | — | — | **`aws/claude-sonnet-5-5`** (carried over from the base plan, user decision 2026-10-13). Used for ACE's Reflector and Curator and for the dedup merge. Re-verified by A1 |
| D2 | AppWorld version | — | — | **core and agents from source at `42b5bcf`, pydantic 2.12.x** (carried over). ACE's AppWorld fork (`appworld 0.1.4.dev0`) is not installed; only its pure ACE modules are vendored (section 8.1) |
| D3 | final trials per task | — | — | **2** (carried over): 168 × 2 arms × 2 = 672 final episodes |
| D4 | ACE version | — | — | **`ace@82709de0`, `ace-appworld@928e8687`**, the design's pins (still HEAD on 2026-10-14) |
| **D5** | The ACE playbook grows without bound (official run: 117,794 characters); the memory cap is 30,000 characters (base §6.2), and the Generator must run with the playbook in its 40K context *during* adaptation | (a) **lazy grow-and-refine at the cap**: when an ADD would push the playbook over 30,000 characters, run ACE's own `BulletpointAnalyzer` (threshold 0.90, `all-mpnet-base-v2`, LLM merge with `OPT_MODEL`) once; if it is still over, drop that step's ADDs (logged as `cap_drop`) and keep adapting; (b) the same without dedup: drop ADDs at the cap; (c) let it grow, then take the last per-task snapshot ≤ 30,000 characters as the artifact; (d) let it grow, with no cap (the Generator overflows; the final artifact fails the lint) | **(a)**. It is the mechanism the paper describes ("lazily, when the context window is exceeded", appendix "Pruning Trigger"), it uses ACE's released code, it keeps every Generator episode inside the context budget, and the rule depends only on character counts, never on scores. (c) wastes the later adaptation steps; (d) repeats F11 | **pending (user)** |
| **D6** | Adaptation set | (a) official `train` (90), dev only as a diagnostic; (b) `train ∪ dev` (147), in the spirit of base rule S2 | **(a)**. It is the official ACE config, the paper's "90 adaptation queries", the design's A-ACE, and the same as the altk arm (mine train). Rule S2 was written for cap-evolve's gate, which does not exist here | **pending (user)** |
| **D7** | ACE batch size | (a) 1, sequential (paper, official config); (b) 4 (design: "only if wall-clock requires it") | **(a)**. About 4 to 6 h (section 14) fits the smoke budget. At HEAD, batch > 1 also turns on augmented shuffling × 2 and parallel curation, which is a different algorithm | **pending (user)** |

---

## 3. Arms

| arm id | what it is | learned artifact | where it plugs in |
|---|---|---|---|
| `seed` | the official AppWorld simplified ReAct code agent with the stock `instructions.txt`, no memory, no helpers, no API notes | none | none |
| `ace` | ACE offline adaptation, no ground truth, 1 epoch over train, Reflector and Curator = `OPT_MODEL`, Generator = the common-harness agent with the current playbook in its memory slot. The artifact is the playbook after the last training task, size-controlled by D5 | `memory/playbook.md` (ACE playbook text, bullets with ids) | memory slot (M) of the same prompt |

Both arms use the same harness, model client, decoding parameters, step cap and evaluator. Only
`memory/playbook.md` differs.

---

## 4. Environment

The first run's state under `/tmp` was lost between sessions (section 1.1), so this plan splits
the layout in two:
- **durable state**, needed to resume and to report, on `/workspace`:
  `AW_STATE=/workspace/aw_eval_ace/`;
- **scratch**, which can be rebuilt from the manifest, on `/tmp`: `AW_SCRATCH=/tmp/aw_eval_ace/`.

```
/workspace/aw_eval_ace/            # AW_STATE (durable detail records; outside git, never pushed; section 10.3)
/workspace/worktrees/base/docs/EVAL_SMOKE_TEST_ACE_STATUS.md   # THE LEDGER (section 10.2): in git, pushed at every checkpoint
  RUNNING.pid                      # the live phase runner (resume lock)
  manifest.json                    # commits, patch sha256, data tree sha256, split-file sha256, venv freeze hashes
  records/<phase>/<unit>.json      # one gold-free record per unit of work (episode, ACE step, check)
  ace/playbooks/pb_<iii>.txt       # playbook after training task iii (000 = initial)
  ace/steps/<iii>/{episode,reflector,curator,apply}.json
  ace/llm_calls.jsonl              # every Reflector / Curator / merge call: prompt hash, response, tokens
  final/                           # frozen artifacts, order file, window records, RESULTS.md
  progress/                        # one progress log per trial + PROGRESS.md
/tmp/aw_eval_ace/                  # AW_SCRATCH (rebuildable)
  appworld/                        # git clone StonyBrookNLP/appworld @ 42b5bcf3cd334fee33f0c37c02070a9f5807add5 (+ git lfs pull, + our patch)
  ace-src/{ace,ace-appworld}/      # clones at the D4 pins, read-only (vendoring source)
  venv-aw/                         # python3.11: appworld (-e), appworld-agents (-e experiments[simplified]), pydantic>=2.12,<2.13, cap-evolve core (-e core), sentence-transformers, faiss-cpu, torch (CPU)
  root_full/                       # APPWORLD_ROOT with all splits; final window only; chmod 000 during search
  root_opt/                        # APPWORLD_ROOT for search: api_docs, base_dbs, tasks/<train+dev ids>, datasets/{train,dev}.txt
  hf/                              # HF_HOME (all-mpnet-base-v2)
  aw_outputs/                      # AppWorld native per-episode output dirs, deleted after each record is written
```

Build steps (each one checkpoint, each idempotent, each under 30 minutes):
- **B1.** `git clone`, `git checkout 42b5bcf3…`, `git lfs install --local && git lfs pull`, apply
  `examples/appworld/patches/appworld-extra-headers.patch` (section 5.2), record `git diff` and
  its sha256 in `manifest.json`.
- **B2.** `python3.11 -m venv venv-aw`; `pip install -e appworld -e
  "appworld/experiments[simplified]" "pydantic>=2.12,<2.13"`; `pip install -e
  /workspace/worktrees/base/core` (provides the `Rollout` type of the shared adapter; cap-evolve
  itself is not run); `pip install sentence-transformers faiss-cpu` with torch from
  `https://download.pytorch.org/whl/cpu`; `appworld install --repo`. Record `pip freeze` and its sha256.
- **B3.** `appworld download data --root root_full`. Check split counts (90 / 57 / 168 / 417) and
  scenario counts (30 / 19 / 56 / 139); stop on any mismatch. Record the data tree sha256.
- **B4.** `examples/appworld/scripts/make_roots.py` builds `root_opt` (train + dev ids and
  `_base_`); `grep` finds none of the 585 test ids under it.
- **B5.** Clone `ace` and `ace-appworld` at the D4 pins into `ace-src/`; vendor the files of
  section 8.1 into `examples/appworld/ace/vendor/` with a `VENDORED.md` that lists source path,
  commit and sha256 of each file. Pre-fetch `all-mpnet-base-v2` into `HF_HOME`.
- **B6.** Write the code of section 4.1, and commit it **locally** to the working branch after each
  file group passes its unit check. These commits go to branch `erezh-eval2-ace` and are pushed
  with the next checkpoint (section 10.2); the checkpoint records the code sha.
- **B7.** The user puts `.env` (`RITS_URL`, `RITS_API_KET`) in the worktree if it is missing. It
  is git-ignored and is never copied into `AW_STATE` or `AW_SCRATCH`.

### 4.1 Code (all under `examples/appworld/`)

| file | role |
|---|---|
| `patches/appworld-extra-headers.patch` | section 5.2 (as in the base plan) |
| `adapters/aw_agent.py` | `CapReActAgent` (section 6.1) and the one-episode worker (one subprocess per episode, F1 hardening, F2 token cap, writes the agent's final message list for the Reflector) |
| `adapters/adapter.py` | episode runner and scorer (section 7) |
| `adapters/lints.py` | the lints of section 6.2, plus the per-bullet filter of section 8.3 |
| `seed_capability/` | section 6.2 |
| `ace/vendor/` | ACE files, unmodified (section 8.1) |
| `ace/ace_llm.py` | the Reflector / Curator / merge client to the gateway (section 5.3) |
| `ace/run_ace.py` | the ACE loop with per-step checkpoints (section 8.2) |
| `scripts/make_roots.py`, `make_splits.py`, `awpaths.py` | B4, rule S1 split check |
| `scripts/status_doc.py` | the only writer of the ledger: append (with the content filter), commit, push, heartbeat, abort (section 10.2) |
| `scripts/resume.py` | the resume procedure (section 10.4) |
| `scripts/check_*.py` | acceptance checks (section 11) |
| `scripts/dev_diag.py`, `final_window.py`, `analyze.py`, `scan_isolation.py`, `status.py` | sections 8.5, 12, 9, 10.1 |

---

## 5. Model access

### 5.1 Agent under test: gpt-oss-120b on RITS

Identical to section 5.1 of the base plan, for both arms, in adaptation, the dev diagnostic and
the final window:

```
client_name: litellm
name: hosted_vllm/openai/gpt-oss-120b-a100
base_url: "{{MODEL_SERVER_URL}}/gpt-oss-120b-a100/v1"  # MODEL_SERVER_URL=$RITS_URL
api_key: "unused"
extra_headers_env: {RITS_API_KEY: RITS_API_KET}
reasoning_effort: medium
temperature: 0
max_completion_tokens: 6000
drop_reasoning_content: true
use_cache: false
retry_after_n_seconds: 15
max_retries: 20
cost_per_token: all 0                               # reported as "unknown", never as $0
```

Agent parameters: `max_steps` 50, `ignore_multiple_calls` true, `max_output_length` 60000
characters, 100,000 completion tokens per task enforced in the loop (F2), `random_seed` 100 +
trial index, `raise_on_extra_parameters` true, `OPENAI_API_KEY=unused`. A vLLM context-window
error (HTTP 400) ends the episode with reward 0 as `artifact:context_exceeded`, reported per arm.

### 5.2 The change to the AppWorld clone

As section 5.2 of the base plan: `extra_headers` and `extra_headers_env` in
`experiments/code/simplified/language_model.py`, and both removed from logged calls. Acceptance
A2.

### 5.3 Optimizer: the ACE Reflector, Curator and merge client

- `OPT_MODEL=aws/claude-sonnet-5-5` (D1).
- `ace/ace_llm.py` replaces ACE's `LiteLLMGenerator` (which cannot reach the gateway, section 1.3)
  with one function, `generate(messages, role) -> {content, usage}`:
  `litellm.completion(model="anthropic/" + OPT_MODEL, api_base=$ANTHROPIC_BASE_URL,
  api_key=$ANTHROPIC_AUTH_TOKEN, extra_headers={x-context-guru-token: …},
  temperature=0, max_tokens=8192)`, the header read from `ANTHROPIC_CUSTOM_HEADERS`. No
  `response_format`, no tools. Retries: 50, 10 s apart (ACE's config). No cache.
- Every call is appended to `AW_STATE/ace/llm_calls.jsonl`: role, step, prompt sha256, full prompt
  and response text, input and output tokens, latency, error. The prompt text is kept so that the
  isolation scan (section 9) can read exactly what the optimizer saw.
- Spend is metered from the logged usage at proxy list prices ($2 / $10 per Mtok input / output),
  labelled "proxy". Soft cap: **$60** for the ACE search. Above it, the loop stops after the
  current step and a `cap_spend` checkpoint is written. The cumulative spend is recomputed from
  `llm_calls.jsonl` on resume, so the cap survives restarts.

---

## 6. The common harness and the capability layout

### 6.1 Injection

As section 6.1 of the base plan. `CapReActAgent(SimplifiedReActCodeAgent)` overrides only
`initialize(world)`: it reads `policy/instructions.txt` and inserts `memory/playbook.md`, if
non-empty, immediately before the final `My name is: … Task: {{ instruction }}` block under the
heading `Guidelines learned from past task attempts:`. The seed has no memory block, so its prompt
is byte-identical to stock. Neither arm has helpers or notes, so no setup snippet runs (F4). The
ACE playbook is inserted as ACE writes it (section headers and `[id]` bullets).

### 6.2 Seed capability (`examples/appworld/seed_capability/`)

```
policy/instructions.txt   # byte copy of experiments/prompts/react_code_agent/instructions.txt @ 42b5bcf
tools/helpers.py          # empty module (unused by both arms)
tools/api_notes.json      # {} (unused by both arms)
memory/                   # empty for the seed; playbook.md for ace
```

Lints, as in the base plan. Here only the memory block varies: **at most 30,000 characters**
(about 8K tokens), checked at every playbook write during adaptation (section 8.4) and again at
freeze. A playbook that fails is never used for a rollout.

---

## 7. The episode adapter (`examples/appworld/adapters/adapter.py`)

The base plan's section 7.1, without the cap-evolve parts:
- `tasks(split)` reads ids with `load_task_ids` only. A seal refuses any id outside train ∪ dev
  unless `AW_ALLOW_SEALED=final-eval-only` is set (only the final window sets it). The task input
  holds the instruction only; difficulty is never exposed.
- `run_episodes(specs, workers)`: a thread pool of `AW_WORKERS` threads, each running one episode
  as its own subprocess (`aw_agent.py SPEC OUT`, A.4), `experiment_name=<phase>/<arm>/<task>/t<k>`,
  `APPWORLD_ROOT=root_opt` (search) or `root_full` (final). Wall cap 30 minutes per episode (a
  real kill). After the agent finishes, the worker calls `world.evaluate()` and writes the record:
  success, pass count, failed requirement texts, the no-collateral-damage flag, steps, prompt and
  completion tokens, trims, termination reason, `fs_probe`, `playbook_sha256`. **The evaluator's
  `trace` is removed before anything is written.** For training episodes it also writes
  `messages.json`, the agent's final trimmed message list (the input ACE's Reflector expects).
  AppWorld's native output dir is then deleted.
- Each record is written to a temp file, fsynced and renamed into `records/…` (atomic), before
  the checkpoint that reports it (section 10.3).
- Provider 429/5xx or connection failure after the client's retries marks the record
  `infra_error` (never scored as a failure, retried once in search, up to 3 times in the final
  window).
- `score`: reward 1.0 if success, else 0.0. Deterministic on a fixed record.

---

## 8. ACE arm (`ace`)

The design's A-ACE is followed: ACE's released Reflector, Curator and playbook code, with the
Generator replaced by the common-harness agent.

### 8.1 What is reused from ACE (vendored, unmodified)

From `ace-appworld@928e8687`, `experiments/`:
- `prompts/appworld_react_reflector_no_gt_prompt.txt`, `prompts/appworld_react_curator_prompt.txt`;
- `playbooks/appworld_initial_playbook.txt` (the initial playbook);
- `code/ace/playbook.py` (`apply_curator_operations`, `extract_json_from_text`,
  `get_next_global_id`), `get_section_slug` from `code/ace/utils.py`, and
  `code/ace/bulletpoint_analyzer.py` (used only by D5 (a)).

From `adaptation_react.py`, the logic of `reflector_call` and `curator_call` is ported line for
line into `run_ace.py`: the same placeholder filling, the same `=== FULL CONVERSATION HISTORY ===`
rendering of the message list, the same JSON schema checks, `ADD`-only rule and section whitelist,
and the same "skip the update on invalid JSON" behaviour. It is ported, not imported, because
that module imports ACE's AppWorld fork. A unit test (A7) compares the ported prompt rendering
byte for byte with ACE's own on a fixed message list.

Not used: ACE's Generator prompt and agent, its LLM client, its evaluation agent, the with-GT path,
the online mode, the batch path.

### 8.2 The loop (`run_ace.py`, sequential, batch size 1 per D7)

The task order is `load_task_ids("train")` (ACE's order, no shuffle), recorded in `AW_STATE` at
phase start (its sha256 goes into the P3 checkpoint, the ids do not). Playbook state `pb_000` = the initial playbook, `next_global_id` from
`get_next_global_id`. For training task *i* = 1 … 90, four sub-steps, each persisted before the
next starts:

1. **episode**: one common-harness episode with `memory/playbook.md = pb_{i-1}` (root_opt, trial
   seed 100). Writes `ace/steps/<i>/episode.json` (the record of section 7 plus `messages.json`).
   This is a counted rollout. On `infra_error` it is retried once; if it fails again, the step is
   recorded as `skipped_infra` and the playbook is carried forward unchanged.
2. **reflector**: the no-GT reflector prompt filled with `pb_{i-1}` and the message list. The test
   report, the outcome and any gold are not sent (section 1.3). Writes `reflector.json` (response
   text, tokens).
3. **curator**: the curator prompt with the instruction, `pb_{i-1}`, the reflection and the
   message list. Writes `curator.json` (raw response, parsed operations or the parse error).
4. **apply**: per-bullet filter (section 8.3), then `apply_curator_operations`, then the size rule
   (section 8.4). Writes `pb_<i>.txt` and `apply.json` (ops proposed / applied / `lint_drop` /
   `cap_drop`, dedup run or not, characters, bullets, sha256), then the checkpoint entry for
   step *i*.

A resumed run reuses every sub-step file that exists and verifies, so no paid call is repeated
and the trajectory a reflection was made from never changes (section 10.4).

### 8.3 Per-bullet lint

ACE's Curator sees the task instruction, so a bullet can quote it. Each `ADD` is checked before it
is applied, with the prompt rules of base §6.2: no 8-gram from any train or dev instruction, no
supervisor name, email or phone number from any train or dev task. A violating bullet is dropped
and logged (`lint_drop`, with the rule); the rest of the step's operations are applied. This is
the base plan's lint, applied per bullet because ACE has no candidate-level reject step; section
13 lists it.

### 8.4 Size rule (D5; option (a) is shown, change it if the user chooses otherwise)

After the per-bullet filter, if `len(pb_{i-1} + ADDs) > 30,000` characters:
1. run `BulletpointAnalyzer.analyze(threshold=0.90, merge=True)` on the playbook *with* the new
   bullets, with merges made by `OPT_MODEL` through `ace_llm.py` (role `merge`, logged and metered);
2. if the result is ≤ 30,000 characters, it becomes `pb_<i>`;
3. otherwise the step's ADDs are dropped (`cap_drop`), `pb_<i> = pb_{i-1}`, and adaptation goes on
   (later steps may still add once a dedup has made room).

The rule reads character counts only. The number of dedup runs, merged bullets and `cap_drop`
bullets is reported.

### 8.5 Freeze and the dev diagnostic

- Freeze: the ACE artifact is `pb_090` (or the last step's playbook, if the spend cap stopped
  the loop; this is disclosed). Lint, render into `final/artifacts/ace/memory/playbook.md`, record
  the tree sha256. `identical_to_own_seed`: whether `pb_090` equals ACE's initial playbook
  (design erratum 8). It is "inert" if it equals the empty seed memory, which cannot happen
  because ACE starts from its 8-bullet initial playbook. This is reported.
- Dev diagnostic (no decision depends on it): `seed` and `ace` on the 57 dev tasks, 1 trial each
  (114 rollouts, root_opt). It reports the search-time score and is a last check of the context
  budget with the real playbook (`context_exceeded` count) before the test window.

Counted rollouts reported beside every result: 90 (adaptation) + 57 (dev diagnostic) for `ace`,
57 for `seed`. Optimizer calls: about 180 plus dedup merges.

---

## 9. Splits, feedback and isolation

- **S1. Official splits only** (base §9, unchanged). Every id comes from `data/datasets/*.txt`
  through `load_task_ids`. No re-splitting, sub-sampling or hand-picked subsets in any counted
  rollout. Acceptance probes use a few dev ids and are not counted. The sha256 of the four id files
  is in `manifest.json`; `make_splits.py` refuses if the counts differ from 90 / 57 / 168 / 417.
- **S2** (base §9) governs cap-evolve's `split_ids.json`. There is no cap-evolve arm, so it has no
  effect here; D6 records the choice for ACE.

| official split | ace | seed | final window |
|---|---|---|---|
| `train` (90) | adaptation (Generator episodes → Reflector → Curator) | not used | not used |
| `dev` (57) | diagnostic, 1 trial, after freeze | diagnostic, 1 trial | not used |
| `test_normal` (168) | never at search time | never at search time | scored, 2 arms × 2 trials |
| `test_challenge` (417) | not used | not used | not used |

Feedback: ACE's no-GT Reflector sees the trajectory only (environment outputs, errors, the
agent's own `complete_task` call). That is less than feedback tier F1 of the design (no failed
requirement texts, no success flag), and it is ACE's own setting. The with-GT setting (Tier F2) is
not run.

Isolation, as in the base plan, with the lessons of section 1.4:
- Two data roots; search processes get `APPWORLD_ROOT=root_opt`; `root_full` is `chmod 000` from
  B4 until the final window starts, and re-locked by `resume.py` if a resume lands before it.
- The adapter seal (section 7). Test ids appear in no search-time file, prompt or log.
- REPL guards on, with F1's allowlist hardening, in every arm and phase.
- The optimizer has no tools: its whole input is in `llm_calls.jsonl`.
- No leaderboard bundles, no `appworld download experiment-outputs`.
- After adaptation and again after the dev diagnostic, `scan_isolation.py` greps
  `llm_calls.jsonl`, every `ace/steps/*` file and every playbook for the 585 test ids, `test_normal`,
  `root_full`, `answer.json`, `ground_truth` and `solution` (F16: the canary is release-wide, so
  it is reported but not used as the test signal). It also counts `fs_probe` hits per arm. A hit
  is reported, and the arm is labelled "isolation breach".

---

## 10. Orchestration, progress log, checkpoint ledger and resume

The long work runs as detached `nohup` processes that write their own logs and records (A.4).
The main session, or at most 2 sub-agents (`ace`: adaptation → freeze → dev diagnostic; `final`:
final window → analysis), starts and watches them. Nothing depends on a sub-agent or the main
session staying alive: **the last entry of `docs/EVAL_SMOKE_TEST_ACE_STATUS.md` says where the run
is and what comes next, and `AW_STATE` holds the detail behind it.**

| sub-agent | trial | depends on | RITS concurrency |
|---|---|---|---|
| `ace` | adaptation (sequential, 1 episode in flight), freeze, dev diagnostic | environment + acceptance | 1, then 24 |
| `final` | final window + analysis | ace frozen | 48 |

### 10.1 Progress log (what to watch)

- `AW_STATE/progress/<trial>.log`: one line per event, `UTC | trial | phase | detail`, e.g.
  `step 41/90 +3 bullets (1 lint_drop) pb=21,480 chars`, `dedup 34→29 bullets`,
  `dev ace 31/57`, `final 312/672 episodes`.
- `AW_STATE/progress/PROGRESS.md`: one table (trial, phase, % done, last event, rollouts used,
  optimizer tokens and proxy USD, playbook size, ETA, **last checkpoint number, its age, and whether it is pushed**), regenerated
  every 5 minutes by `scripts/status.py`.
- To watch: `watch -n 60 cat /workspace/aw_eval_ace/progress/PROGRESS.md`.

### 10.2 The checkpoint ledger: `docs/EVAL_SMOKE_TEST_ACE_STATUS.md`

The ledger is a named, human-readable document in the repository,
**`docs/EVAL_SMOKE_TEST_ACE_STATUS.md`**, on branch **`erezh-eval2-ace`**. It is **cumulative**:
each checkpoint appends one new entry after all earlier ones. An earlier entry is never edited,
reordered or deleted, so the document is the full history of the evaluation, and its last entry
is the current state. After every checkpoint the document is **committed and pushed to
`origin erezh-eval2-ace`**, so the state survives the loss of this host (`/tmp` and `/workspace`).

**Layout of the document.**
- A fixed header, written once at creation (CP-0000): what the document is, a link to this plan,
  the resume command, and the content rules below.
- Then one entry per checkpoint, oldest first:

````
## CP-0042 · 2026-10-15T03:12Z · P4 ACE adaptation · result

Since CP-0041: ACE steps 040–041 done (+5 bullets, 1 lint_drop, 0 cap_drop); 2 counted rollouts.
Totals: rollouts counted 41 (ace 41, seed 0); playbook 63 bullets, 21,480 chars; optimizer 2.31M in / 0.19M out tok, $6.50 proxy.
Runner: alive (pid 81234), last log `step 41/90 +3 bullets (1 lint_drop) pb=21,480 chars`.
Next: P4 ace/step/042 episode.

```json
{"cp": 42, "prev_cp": 41, "prev_commit": "<sha>", "utc": "2026-10-15T03:12:09Z",
 "kind": "result", "phase": "P4", "done_through": "ace/step/041/apply",
 "next": "ace/step/042/episode", "counts": {...}, "spend": {...},
 "artifacts": {"ace/playbooks/pb_041.txt": "<sha256>", "...": "..."},
 "code": "<git sha of examples/appworld>", "open_decisions": []}
```
````

  The prose lines are for people; the fenced `json` block is what `resume.py` parses. Its
  `artifacts` map names files in `AW_STATE` by sha256 (section 10.4).
- `kind` is one of `phase_start`, `result`, `phase_done`, `heartbeat`, `decision` (user decisions,
  verbatim), `abort`, `resume`, `rebuild`, `repair`, `error`, `cap_spend`, `posted`.

**Content rules (the document is published by every push).** No secret or key, no gold value or
solution, **no task id**, no task instruction or supervisor detail from any split, no trajectory
text, no playbook text. Units are named by phase and index (`ace/step/041`, `final cell 312/672`),
never by task id. Final-window entries carry counts and progress only until P9, when the aggregate
results (the main table of section 12) are added. `scripts/status_doc.py` refuses to write an entry
that contains any of the 732 task ids, any string from `.env`, or the text of any train or dev
instruction 8-gram, and logs the refusal locally.

**When a checkpoint is written.** Every new result is checkpointed promptly, and nothing goes more
than 30 minutes without a checkpoint:
- **at once**: every phase start and end, every user decision, every build step (B1–B7), every
  acceptance check (A1–A10), every completed ACE training step (after its `apply`; 90 entries),
  the freeze, the isolation scan, every error, `cap_spend`, abort and resume;
- **coalesced**: results that arrive faster than every 5 minutes (episodes of the dev diagnostic
  and the final window) are gathered into one entry at most every 5 minutes ("cells 301–312 done");
- **heartbeat**: if 25 minutes pass with no checkpoint, `status_doc.py heartbeat` (a `nohup` loop for
  the whole evaluation) writes a `heartbeat` entry with the phase, the last result, whether the
  runner PID in `AW_STATE/RUNNING.pid` is alive, and the tail of its log. A dead runner is recorded as
  `stalled`.

So the checkpoint resolution is at most 30 minutes, and finer whenever results arrive. Expected size:
about 150–250 entries (90 ACE steps, about 50 build and acceptance entries, about 20–40 coalesced
window entries, heartbeats), each 6–15 lines.

**How a checkpoint is committed and pushed** (`scripts/status_doc.py append`, the only writer, under
`flock`):
1. Append the entry to the document, `fsync`.
2. `git commit -m "status: CP-0042 P4 ace/step/041" -- docs/EVAL_SMOKE_TEST_ACE_STATUS.md`. The
   pathspec commits this one file only, never other work in the tree.
3. `git push origin erezh-eval2-ace`. Never `--force`. If the push fails (network, auth), the commit
   stays local, the failure is noted in the next entry, and the next checkpoint pushes both. If the
   push is rejected as non-fast-forward (someone else pushed to the branch), the writer stops pushing,
   keeps committing locally, and the next status check asks the user.

Code commits of B6 go to the same branch and are pushed with the next checkpoint; the entry records
the code sha.

### 10.3 Detail records in `AW_STATE` (not pushed)

The status document holds the state and the resume point. The bulky or sensitive detail behind it
stays in the durable, git-ignored `AW_STATE` (section 4) and is referenced from the document by
sha256:
- per-unit records `records/<phase>/<unit>.json`, written to a temp file, `fsync`ed and renamed
  (atomic) **before** the checkpoint that reports them;
- ACE sub-step files `ace/steps/<i>/{episode,reflector,curator,apply}.json`, playbook snapshots
  `ace/playbooks/pb_<i>.txt`, `ace/llm_calls.jsonl`;
- `final/` (order file, per-cell records, which contain test ids).

A unit is done if its record exists and verifies, whether or not a checkpoint entry has reported it
yet (results between two coalesced checkpoints are safe on disk). **Worst-case loss on an abort**:
the in-flight episodes (at most 30 minutes each, re-run from scratch with the same seed), at most
one in-flight optimizer call (re-made), and the build or analysis step in progress (idempotent, at
most 30 minutes).

### 10.4 Resume

One command: `python3 -I examples/appworld/scripts/resume.py` (with `--dry-run` to only print the
plan). It works the same after a crash, a kill, a host restart or a new Claude session.

1. **Read the ledger.** `git fetch origin erezh-eval2-ace`. If the local branch is missing or behind,
   use `origin/erezh-eval2-ace` (fast-forward only). If local has unpushed checkpoint commits, push them
   first. Parse the `json` block of the last entry. If the last entry is torn (crash mid-append,
   uncommitted), drop the uncommitted tail with `git checkout -- docs/EVAL_SMOKE_TEST_ACE_STATUS.md`;
   the records it would have reported are adopted in step 4.
2. **Lock**: refuse if `RUNNING.pid` names a live runner (no double runs). Stale pid files are removed.
3. **Environment**: compare `manifest.json` with scratch. A missing or mismatched clone, venv or data
   root is rebuilt by re-running its B step (idempotent), checked against the recorded sha256. If a
   rebuilt hash differs (e.g. upstream data changed), stop and ask the user. Re-apply
   `chmod 000 root_full` if the phase is before P8.
4. **Reconcile `AW_STATE` with the last entry.** Verify every artifact the last entry names, by
   sha256. Records that exist and verify but are newer than the last entry are adopted (they are
   reported in the `resume` entry). Temp files without a rename are deleted. **If `AW_STATE` is
   missing or an artifact the ledger names is missing or wrong, stop and ask the user**: the document
   says exactly which phase and unit were reached, but the playbook snapshots and records are not in
   git (section 16, issue 11). From P1–P3 and P8 onwards, phases can be re-run from their start. P4
   cannot restart mid-way without `pb_<i>`.
5. **Continue** at the `next` unit:
   - P1/P2: re-run the first unfinished B or A step.
   - P4: load `pb_<last apply>` and `next_global_id`, and start at the first missing sub-step. An
     existing `episode.json` is never re-run, and an existing `reflector.json` or `curator.json` is
     never re-requested.
   - P6 and P8: skip every cell with a done record, and run the rest in the recorded order with the
     recorded seeds. Infrastructure retries count from the records, so a resume does not reset them.
   - P10: if a `posted` entry exists, never post again.
6. Append a `resume` entry (what was adopted, what was skipped, what will run, and the user's reason if
   given), commit and push it, relaunch the phase runner under `nohup`, and restart the heartbeat if
   it is not running.

To abort on purpose: `scripts/status_doc.py abort --reason "…"` sends SIGTERM to the runner (which
finishes writing the current record but starts no new unit), writes, commits and pushes an `abort`
entry, and stops the heartbeat. A plain kill is also safe; the next resume handles it.

---

## 11. Acceptance checks before any counted rollout

| id | check |
|---|---|
| A1 | `aws/claude-sonnet-5-5` answers through `ace_llm.py` (the gateway header is sent; no `response_format`); one Reflector and one Curator call on a toy message list return parseable JSON |
| A2 | RITS through the patched client: 1 dev episode completes; the RITS key appears nowhere under `AW_STATE` or `AW_SCRATCH` |
| A3 | REPL isolation with F1's hardening (`import os`, `open(answer.json)`, a `pathlib` read all fail); `root_opt` has no test id; `root_full` is unreadable during search |
| A4 | injection: on 1 dev task the seed's first request is byte-identical to the stock agent's; a playbook appears in the slot before `My name is:`; a 30,001-character playbook is refused before any rollout |
| A5 | scoring: a train task's released compiled solution gives reward 1, a no-op 0; the record has no `trace`; scoring twice is identical |
| A6 | split and seal: `tasks("train")` = `train.txt` exactly (90, same order as `load_task_ids`); a test id is refused without `AW_ALLOW_SEALED` |
| A7 | ACE loop on 3 dev tasks into a throwaway state dir (not counted): the ported reflector and curator prompts are byte-identical to ACE's rendering on a fixed message list; ≥ 1 bullet is added with a fresh id in a whitelisted section; a non-`ADD` or off-whitelist operation is skipped as in ACE; a planted bullet with a train 8-gram is `lint_drop`ped; a synthetic 40,000-character playbook triggers the D5 rule, and its outcome is logged |
| A8 | context: the longest of 10 dev episodes **with a 30,000-character playbook in the slot** stays under 34K prompt tokens with `max_output_length` 60000 |
| A9 | resume, ACE: run the A7 loop against a **throwaway status file and branch** (`acceptance/status-test`, deleted afterwards) and kill it (SIGKILL) three times, once each after `episode.json`, after `reflector.json` and in the middle of a status append; resume each time; the final playbook equals that of an uninterrupted run from the same stored sub-steps, no paid call is repeated (count in `llm_calls.jsonl`), every entry is a committed, pushed, append-only addition (`git log -p` shows only added lines), and a resume from a fresh clone of the branch finds the same `next` unit |
| A10 | resume and publishing, windows: a 12-cell mini window on dev ids, killed mid-way and resumed: no cell is run twice, all 12 cells are done, the order is the recorded one; cells arriving fast are coalesced into ≤ 1 entry per 5 min (tested with a 1-min setting); a heartbeat entry appears after 25 minutes of silence (tested with 1 min) and marks a killed runner `stalled`; a push failure (bad remote URL) leaves a local commit that the next checkpoint pushes; the content filter refuses an entry that contains a task id or a string from `.env` |

None of the acceptance rollouts are counted (rule S1).

---

## 12. Final window, statistics and the report

- Freeze: `ace` = the artifact of section 8.5; `seed` = the seed capability. Copy each into
  `final/artifacts/<arm>/` and record sha256 tree hashes in a checkpoint.
- Window: 168 test_normal tasks × 2 arms × 2 trials = **672 episodes**, in one random order with a
  recorded seed (order file hashed in the P8 checkpoint), `AW_ALLOW_SEALED=final-eval-only`,
  `APPWORLD_ROOT=root_full` (unlocked at P8 start, logged), 48 workers. Trial seeds are `random_seed`
  5000 + trial. Infrastructure failures are retried up to 3 times; a cell that still fails is scored
  0 (primary) and reported as missing (sensitivity).
- Only rewards, counters and infrastructure flags are read from test records. No test trajectory is
  read by a person or an LLM; AppWorld forbids error analysis on test.
- Metrics: TGC; SGC (a scenario passes in trial k if all 3 of its tasks pass; averaged over k); both
  by difficulty (Easy 57, Medium 48, Hard 63). Paired difference `ace − seed` with a
  scenario-clustered paired bootstrap (56 clusters, 10,000 resamples) 95% CI. One contrast, so no
  multiplicity question; one search seed, so it is an artifact-level statement only.
- Cost table: target tokens per task (prompt and completion), steps per task, step-cap hits,
  `context_exceeded` count; playbook characters, tokens and bullets, memory tokens per step; dedup
  runs, `lint_drop` and `cap_drop` counts; optimizer input and output tokens, calls per role and proxy
  USD (from `llm_calls.jsonl`); counted rollouts per arm; dev diagnostic scores; wall time per phase
  (from the status document).
- Side by side, compared only as gains over each side's own no-memory baseline (design section 3,
  interpretation rule 1): the colleagues' gpt-oss-120b (no memory 39.9 / 21.4, ReAct + ACE 54.8 /
  35.7) and the ACE paper's (ReAct 54.8 / 33.9, ACE offline no GT 58.3 / 41.1). Their harness,
  template, reflector model and epochs differ (section 13).

Results comment on #804 (markdown): setup block (commits, models, settings, D1–D7 outcomes); the main
table (TGC, SGC, Δ vs seed with CI); the difficulty table; the cost table; what changed (playbook
size, number of bullets by section, 3 example bullets checked by the lint); isolation scan counts;
resume history (number of aborts and resumes, units re-run, from the status document); deviations (section 13)
and what the numbers cannot support (one search seed, one method, no matched budget, no TOST). No
task text, ids, solutions or gold values are posted (AppWorld redistribution rule), and example
bullets are checked for task-specific content before posting. The draft is written to
`final/RESULTS.md` first and shown to the user; then it is posted with
`gh issue comment 804 -R skillberry-ai/cap-evolve --body-file …` (the `origin` remote, the
`erezh16` fork, has issues disabled), and a `posted` checkpoint records the comment URL.

---

## 13. Deviations, and why

### 13.1 From the base plan

| base plan | here | why |
|---|---|---|
| arms seed, cape-hc, altk | seed, ace | task scope: ACE is the only candidate |
| all state under `/tmp/aw_eval` | durable `AW_STATE` on `/workspace`, rebuildable scratch on `/tmp` | `/tmp` was wiped between sessions (section 1.1); resume needs durable state |
| progress log + `PROGRESS.md` | the same, plus the cumulative ledger `docs/EVAL_SMOKE_TEST_ACE_STATUS.md` pushed to `erezh-eval2-ace` at every checkpoint, the heartbeat and `resume.py` | new requirement (section 10) |
| rule S2 (cap-evolve train = val) | not applicable; ACE adapts on train (D6) | no cap-evolve arm |
| memory lint: size only | size, plus the prompt's 8-gram and supervisor-contact checks per bullet | ACE's Curator reads the task instruction verbatim (section 8.3) |
| final window 1,008 episodes | 672 | 2 arms |
| venv-altk (Python 3.12) | not needed; ACE's vendored modules run in `venv-aw` (3.11; `ace-appworld` needs ≥ 3.11) | no ALTK arm |
| optimizer via claude CLI + litellm wrapper | litellm client only (`ace_llm.py`) | ACE's optimizer roles are plain LLM calls |
| `optimizer_guard.sh`, claude shim (F14, F15) | not needed | the optimizer has no tools |
| posting `gh issue comment 804` | `-R skillberry-ai/cap-evolve`, after the user sees the draft | the fork has issues disabled |

### 13.2 From the design and from ACE's paper and code

| design / ACE | smoke test | why |
|---|---|---|
| 2 targets | gpt-oss-120b only | as in the base plan |
| full competitor set, CapEvolve cells | ACE only | task scope |
| 3 search seeds, matched budget N* | 1 seed; ACE native count (90 + 57 diagnostic) | smoke scale |
| final n = 3, seed n = 10, template panel, drift blocks | n = 2 for both arms, one window | smoke scale (D3) |
| Holm families, TOST | one unadjusted paired cluster-bootstrap CI | one contrast, one seed |
| ACE paper: target model as Reflector and Curator | `OPT_MODEL` (Sonnet 5.5) | design primary (matched optimizer); `ace-target` exploratory cell not run |
| ACE paper: up to 5 epochs and 5 reflection rounds | 1 epoch, 1 reflection per task | official no-GT config and the paper's own AppWorld cost setting; in the no-GT code there are no rounds (section 1.3) |
| design A-ACE: "reflection rounds 5" | 1 | the parameter exists only in the with-GT path (section 16, issue 3) |
| design A-ACE acceptance: "bullets with counters" | bullets with ids, no counters | the AppWorld ACE code has no counters (section 1.3) |
| ACE's own Generator template (27K chars) | stock template + memory slot | design: one template for every arm; template panel not run |
| ACE config `max_steps` 40, `use_cache` true | 50, false | common harness; repeated trials must hit the model |
| ACE playbook unbounded | 30,000-character cap with D5's rule | gpt-oss's 40K window and the base plan's memory lint |
| ACE with-GT, online mode, `ace-native` | not run | Tier F2 feedback; out of scope |
| `appworld==0.1.3.post1` + head ReAct agent | source at `42b5bcf`, pydantic 2.12.x | as in the base plan (D2) |
| `max_completion_tokens` 8000 | 6000 + trimming | RITS window |
| separate OS user, containers, closed egress | data roots, seal, REPL hardening, tool-less optimizer, scan | host constraints; disclosed |

---

## 14. Budget and timeline (projections)

| phase | rollouts | wall time (estimate) |
|---|---|---|
| P1 build (everything from scratch) + P2 acceptance | ≈ 40 (not counted) | 3–4 h |
| P4 ACE adaptation: 90 × (episode 0.5–5 min, mean about 2.5 with the growing playbook; Reflector + Curator about 1–2 min) | 90 | 4–6 h |
| P5 freeze + P6 dev diagnostic (24 workers) | 114 | 0.5 h |
| P8 final window (48 workers) | 672 | 1.5–2 h |
| P9, P10 analysis and report | 0 | 0.5 h |
| **total** | **≈ 876 counted** | **≈ 7–9 h** after the build |

Optimizer: per task, the Reflector and the Curator each read about 15–40K tokens (prompt, playbook up
to about 8K tokens, trajectory), so about 5–7M input and 0.3–0.5M output tokens for 90 tasks, plus
dedup merges, about $15–25 at proxy prices (soft cap $60). The ACE paper reports 39.3M input tokens for
its AppWorld adaptation with the target in all three roles, about 8.2M of it Reflector and Curator
(design section 9). RITS has no budget. All usage is recorded exactly and reported per provider
(RITS for the agent, the gateway for `OPT_MODEL`).

---

## 15. Risks

| risk | mitigation |
|---|---|
| abort, crash, host restart, `/tmp` wiped | the pushed status document + durable `AW_STATE` + `resume.py` (section 10); scratch is rebuilt from the manifest |
| two runners at once after a confused resume | `RUNNING.pid` lock; resume refuses while a runner is alive |
| ledger damage or divergence | append-only entries, one commit per checkpoint, never force-pushed; torn uncommitted tail dropped; non-fast-forward or missing artifact stops and asks |
| a checkpoint publishes something it must not | content rules and the `status_doc.py` filter (task ids, `.env` strings, instruction 8-grams); A10 tests the filter |
| push fails (network, auth) for a long time | checkpoints keep committing locally; `PROGRESS.md` shows "unpushed: N"; the state is then only as durable as `/workspace` until a push succeeds |
| the playbook outgrows the cap early (official rate ≈ 1,300 characters per task → cap after ≈ 23 tasks) | D5 rule; dedup and `cap_drop` counts reported; if most steps after the cap are `cap_drop`, that is a result about ACE at this context size and is reported as such |
| optimizer gateway fails or throttles | A1; 50 retries; a failed step leaves sub-step files, and resume continues from them |
| gateway content filter on some CoT fields (design: noted in earlier suites) | A1 and A7 use the real prompts; if a field is filtered, rename it in our copy of the prompt, log it as a deviation, and re-run A7 before launch |
| Curator returns invalid JSON often | ACE's own behaviour (skip the update) is kept; the invalid-JSON rate is reported |
| context overflow with the playbook in the slot | cap, A8 at the cap, dev diagnostic `context_exceeded` count before the test window |
| RITS throttling or outage in the final window | infra retries; one interleaved window, so both arms are hit equally; resume from records |
| gpt-oss output format issues | seed behaviour; counted per arm |
| ACE adds task-specific content | per-bullet lint; example bullets checked before posting |

---

## 16. Review: issues found in this plan

Found when the plan was checked on 2026-10-14. Items 1 to 3, 11 and 13 need the user's answer before launch.

1. **D5, D6 and D7 are open.** The size rule (D5) is the most consequential: ACE's official
   playbook is 4× the memory cap, and the Generator needs the playbook in context *during*
   adaptation, so this choice shapes the artifact. The plan is written for the recommended options.
2. **Nothing from the first smoke test is on disk.** `examples/appworld/` (Appendix A.2 of the base
   plan) was never committed, and `/tmp/aw_eval`, `.venv`, `.env` and `uv` are gone. The build is
   from scratch (3–4 h, not the 2–3 h of the base plan), and the base plan's acceptance results do
   not carry over. `.env` with the RITS key must be supplied again (B7).
3. **The design's A-ACE spec does not match ACE's AppWorld code** in two places: "reflection rounds
   5" exists only in the with-GT path, and "bullets with counters" does not exist in the AppWorld
   variant. The plan follows the code (1 reflection per task, no counters) and says so. If the
   design meant the paper's 5 rounds, that would need ground truth (excluded) or a new retry loop
   that ACE does not ship.
4. **The comparison is confounded by design choices, and the report must say so.** It uses the common
   template instead of ACE's 27K-character Generator prompt, a stronger Reflector/Curator model
   than the target (the paper uses the target), 1 epoch, and, under D5, a size cap ACE does not
   have. A null result could come from any of these, not from ACE itself. The base plan accepted the
   same trade-off for ALTK-Evolve.
5. **The no-GT Reflector sees no outcome at all.** It is not told whether the task passed. This is
   ACE's setting, and less feedback than the F1 tier the base plan gave cap-evolve. It is disclosed.
6. **Sequential adaptation is the critical path** (4–6 h with one RITS request in flight). D7 (b)
   would shorten it, but at HEAD it also turns on augmented shuffling and parallel curation.
7. **Dev is barely used.** Under D6 (a), dev only gives a diagnostic score. This follows the
   official roles and ACE's lack of a selection step, but it leaves 57 tasks of search-time data
   unused by the method.
8. **The per-bullet lint is a rule addition** (section 8.3). It is stricter than the base plan's
   memory lint and may remove useful generic bullets that happen to share an 8-gram with an
   instruction. The `lint_drop` count is reported.
9. **The memory cap is in characters (30,000), while the design's M surface cap is 30,000 tokens.**
   The plan keeps the base plan's character cap (rule unchanged), which is about 4× tighter than the
   design's. A8 checks that the cap fits; it could be relaxed to about 60,000 characters within the
   34K-token prompt budget if the user prefers, but that would change a base-plan rule.
10. **Base-plan inconsistencies inherited or noticed:** the base plan says "Results are in Appendix B",
    which does not exist; its posting command lacks `-R skillberry-ai/cap-evolve`, needed from this
    clone (fixed here); its §0 still says "we use 3" sub-agents, while Appendix A.4 records that the work
    was watched from the main session.
11. **The pushed ledger alone cannot restore a mid-adaptation run.** By the content rules, the
    status document holds counts, hashes and the resume point but no playbook text and no records.
    If `AW_STATE` on `/workspace` is lost during P4, the document says exactly where the run was, but
    the run must restart P4 from step 1 (P6 and P8 restart only their own window). Option, needing the
    user's decision: also push each lint-checked playbook snapshot `pb_<i>.txt` (generic guidelines,
    no ids, already checked for instruction 8-grams and supervisor contacts) to the same branch. That
    makes P4 restorable from GitHub alone, at the cost of publishing the playbook as it grows.
12. **Heartbeat ≠ progress.** A heartbeat proves the ledger is alive, not that the runner is
    advancing. A single episode can take up to 30 minutes, so a sequential ACE step can legitimately
    go 30+ minutes without a `result` entry. `status.py` flags a runner as stuck, and the next heartbeat entry
    says so, if no `result` entry has appeared for 45 minutes while its PID is alive.
13. **Publishing at every checkpoint.** The branch is pushed about 150–250 times. Anyone with access
    to the `erezh16/cap-evolve` fork sees the live state, including dev diagnostic scores and, after
    P9, the test results before the #804 comment is posted. The content filter keeps out ids, task
    text and secrets, but the user should confirm the fork's visibility is acceptable. The branch
    history also gets one commit per checkpoint; squash it before any PR to `main`.
14. **"Adds on top" was read as append-only, oldest first** (the newest entry last). If newest-first is
    wanted, `status_doc.py` would insert after the header instead; earlier entries are still never
    edited.
