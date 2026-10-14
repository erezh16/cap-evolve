# AppWorld smoke test: cap-evolve (hill-climb) vs ALTK-Evolve

Status: PLAN, written 2026-10-12; decisions D1 to D4 recorded 2026-10-13, D1 updated the same day (section 2); split rules S1 and S2 added 2026-10-13 (section 9). Nothing in
sections 4 to 12 has run yet. The probes in section 1 have run, and their results are given there.

This is a reduced first stage of the Suite F design in issue #804
(`research/capevolve-paper/designs/appworld_experimental_design.md` on branch
`research/capevolve-paper-20261011`, referred to below as "the design"). It keeps the design's
harness, splits, feedback tier and isolation ideas. It drops most arms, seeds and statistics.
Section 13 lists every deviation.

---

## 0. Scope

| item | this smoke test |
|---|---|
| methods compared | cap-evolve vs ALTK-Evolve. Both are scored against the same unmodified seed agent. No ACE, GEPA, SkillOpt, Trace2Skill or Tier 2 arms |
| cap-evolve configuration | `algorithm_skill: hill-climb` (`--focus all`), deterministic orchestration, `capabilities: [system-prompt, tools]`. Intake optimizes both the prompt and the tools |
| optimizer model, both methods | `aws/claude-sonnet-5-5`, through the gateway in `~/.claude/settings.json` (decision D1) |
| agent under test, both methods | `openai/gpt-oss-120b-a100` on RITS, reasoning effort `medium`, temperature 0 |
| benchmark | AppWorld, **official splits only** (`data/datasets/{train,dev,test_normal,test_challenge}.txt`). Search uses `train` (90 tasks) and `dev` (57); results come from `test_normal` (168); `test_challenge` is not used. For cap-evolve, **train = val = train ∪ dev** (147 tasks). Section 9 gives the rules |
| search seeds | 1 per method |
| final scoring | `test_normal`, 2 trials per task, for 3 arms (seed, cap-evolve champion, ALTK-Evolve champion), in one interleaved window |
| deliverable | a markdown results comment on issue #804 |
| parallelism | at most 10 concurrent sub-agents (we use 3). Every long-running trial writes to a progress log |

---

## 1. What was read and verified (2026-10-12)

Sources read: issue #804 and its comments; the full design document; the cap-evolve docs
(`RUN.md`, `llms.txt`, `docs/ADAPTER_CONTRACT.md`, `docs/HONEST_EVAL.md`,
`docs/GETTING_STARTED.md`, `docs/OPTIMIZE_YOUR_OWN.md`, `docs/HOLDOUT_PROTOCOL.md`,
`docs/TROUBLESHOOTING.md`), the skills (`intake` with `inputs/INPUTS.md`, `hill-climb`,
`finalize`, `system-prompt`, `tools`, `run-optimizer`, `optimizers/registry.yaml`),
`templates/project/capevolve.yaml` and the `examples/tau2_airline` adapter and gateway; the
AppWorld repository at the pinned commit (README, `guides/parallelizing_worlds.md`,
`experiments/code/simplified/*`, the ReAct prompt, the config generator and model configs);
the ALTK-Evolve repository at v1.3.0 (`README`, `docs/results`, `altk_evolve/config/*`, the
guideline generation, clustering and retrieval code, the MCP server and client API).

### 1.1 Probes that ran

| probe | result |
|---|---|
| RITS model listing (`https://rits.fmaas.res.ibm.com/ritsapi/inferenceinfo`) | `openai/gpt-oss-120b-a100` is served at `$RITS_URL/gpt-oss-120b-a100/v1` (vLLM, OpenAI-compatible) |
| RITS authentication | header `RITS_API_KEY: <token>` works. `Authorization: Bearer` returns 403. Note: `.env` names the key `RITS_API_KET` (typo); the plan reads that name and does not edit `.env` |
| RITS context window | `max_model_len` = **40,144 tokens**. Prompt plus `max_completion_tokens` must fit in it |
| RITS concurrency | 16 and 48 concurrent requests (about 1.6K-token prompts, about 400 output tokens each) all returned 200. p50 latency was 17 s and 28 s, with no 429 errors |
| RITS reasoning | `reasoning_effort: medium` is accepted, and the response carries `reasoning_content` |
| optimizer gateway (`ANTHROPIC_BASE_URL` in settings.json) | the `x-context-guru-token` header is required (401 without it). `aws/claude-opus-5-5` and `aws/claude-sonnet-5` return 200. on 2026-10-12, `aws/claude-sonnet-5-5` returned 403 "team not allowed to access model" (as did `claude-sonnet-5-5` and `aws/us.claude-sonnet-5-5`). **After the user updated `settings.json` on 2026-10-13 it returns 200** |
| AppWorld install from PyPI `appworld==0.1.3.post1` | works (seconds; data 193 MB). Split counts match the design: train 90/30, dev 57/19, test_normal 168/56, test_challenge 417/139, difficulties as listed there |
| AppWorld ReAct agent with the PyPI release | **does not work.** The `v0.1.3.post1` tag has no `experiments/code/simplified` (only `plain/` and `recoma/`). The head agents package (`42b5bcf`) needs pydantic 2 while the 0.1.3.post1 core needs pydantic 1. The design's pin (PyPI core + head ReAct agent) cannot be installed together |
| AppWorld core + agents both from source at `42b5bcf` | works with `git lfs pull`, `pip install -e . -e experiments[simplified]`, `appworld install --repo`, and **pydantic pinned to 2.12.x**. pydantic 2.14 breaks the import of fastapi 0.143. `appworld download data`: 198 MB, same split and difficulty counts as above |
| 3 real dev episodes, gpt-oss-120b on RITS, stock ReAct prompt | ran end to end: 1 of 3 passed, 1 / 5 / 11 steps, 30 / 80 / 294 s, max prompt 8.2K tokens (about 500 tokens added per step), about 27 s per step with 3 in flight |

### 1.2 Facts from the code that the plan depends on

- AppWorld LLM client (`experiments/code/simplified/language_model.py`): with `client_name:
  litellm`, the agent calls `litellm.completion`. `non_cached_lm_call` raises on any keyword it
  does not name, so `extra_headers` cannot be passed without a code change. The `openai/` litellm
  route rejects `reasoning_effort` for this model id. The `hosted_vllm/` route accepts it (verified).
  Any `base_url` is rendered as a template and needs a `MODEL_SERVER_URL` environment variable.
  `OpenAI()` is constructed at init whichever client is used, so `OPENAI_API_KEY` must be set
  (to a placeholder). `may_log_call` writes the full call arguments to `lm_calls.jsonl`, which
  would include any header we add.
- The ReAct agent (`react_code_agent.py`) renders `instructions.txt` with Jinja variables
  `instruction`, `main_user` and `app_descriptions`. It splits the prompt into messages on
  `USER:`/`ASSISTANT:` markers. The prompt has one worked Spotify demo and ends with
  `Task: {{ instruction }}`. `max_output_length` (in characters) trims old observations and then
  old turns. The generated config uses `max_steps` 50, `max_output_tokens_per_task` 100000,
  `max_cost_per_task` 10, `random_seed` 100, `raise_on_extra_parameters` true and
  `ignore_multiple_calls` true.
- AppWorld unified mode allows one live world per process (freezegun patches time process-wide).
  Each episode must run in its own process, with a unique `experiment_name` + `task_id`.
- AppWorld's official splits are four id files in `data/datasets/`: `train.txt` (90), `dev.txt`
  (57), `test_normal.txt` (168), `test_challenge.txt` (417). `load_task_ids(name)` reads them, and
  `valid_dataset_names()` is exactly these four. Verified 2026-10-13: the four sets are pairwise
  disjoint, and train and dev share no scenario. The README says `train` is for training and
  demonstrations, `dev` is for tuning and error analysis, and the two test sets are for aggregate
  scoring only. AppWorld's "validation" split is `dev`; there is no other.
- cap-evolve hill-climb: the baseline scores the seed on val and train. Each iteration copies
  the current best's **val** trajectories into the optimizer workdir, evaluates the child on val
  and applies the paired gate (accept iff mean per-task Δ > `gate_k_se` · SE). Train is scored
  only at the baseline and at the end-of-run bookend. When train and val hold the same ids, the
  baseline scores the set once (`train ids identical to val — not re-evaluated`) and every rollout
  is written under `rollouts/val/` (verified on `toy_calc` with train = val and `test: []`).
  **With `test: []` in `split_ids_file`,
  `cap-evolve run` completes and finalize scores 0 test tasks** (verified on `toy_calc`). The
  champion stays in `candidates/<best_id>/`, so we can score every arm on `test_normal` in one
  common window outside cap-evolve.
- ALTK-Evolve v1.3.0 (`703d033`; newer tags up to v1.6.1 exist) requires **Python ≥ 3.12**
  (the system Python is 3.11; the existing 3.12 venv `/workspace/worktrees/base/.venv` is used for it, see section 4). `save_trajectory` takes an OpenAI-style message list. It treats the
  **first user message as the task instruction** and parses only assistant messages (at most 50
  steps, each truncated to 2,000 characters). It segments the trajectory into subtasks, generates
  guidelines per segment with `litellm.completion(model=EVOLVE_GUIDELINES_MODEL,
  custom_llm_provider=EVOLVE_CUSTOM_LLM_PROVIDER)` (no `api_base` or headers are passed), and
  resolves conflicts. By default it uses no ground-truth outcome ("judge success from the
  trajectory"). `consolidate_guidelines(mode=lossless|lossy)` clusters with
  `sentence-transformers/all-MiniLM-L6-v2` (Hugging Face is reachable) and conserves support.
  `select_guidelines(task, top_k=10, core_support=3)` returns core plus top-k, and
  `format_selection` renders the block. Injection modes are `static` (full set) and `retrieval`.

---

## 2. Decisions (recorded 2026-10-13)

The user chose the recommended option for D1, D2 and D3, and the design's pin for D4.

| id | question | options | recommendation | **decision** |
|---|---|---|---|---|
| **D1** | The optimizer model `aws/claude-sonnet-5-5` is refused by the gateway for this team (403) | (a) you grant this team access to `aws/claude-sonnet-5-5`, or supply a credential that has it; (b) use `aws/claude-sonnet-5` (accessible, previous Sonnet); (c) use `aws/claude-opus-5-5` (accessible, stronger and costlier) | (a) if it can be done today, otherwise (b). The model is one variable, `OPT_MODEL`, used by both methods, so the choice cannot favour one side. Whatever is used is recorded in the results | **(a) `aws/claude-sonnet-5-5`**, for both methods. The user updated `settings.json` on 2026-10-13. After that, `aws/claude-sonnet-5-5` returned 200 on the Messages API, and `claude -p --model aws/claude-sonnet-5-5` completed (exit 0; `modelUsage` shows `aws/claude-sonnet-5-5`). The CLI prints a harmless `[claude-code:unrecognized_model]` line on stderr for its session-title helper |
| D2 | AppWorld version: the design's pin (PyPI 0.1.3.post1 + ReAct agent at `42b5bcf`) is not installable (section 1.1) | (a) core and agents both from source at `42b5bcf`, pydantic 2.12.x; (b) PyPI 0.1.3.post1 with the older `plain` agents | (a). It is the code the design means by "the official simplified ReAct agent" | **(a)** core and agents from source at `42b5bcf`, pydantic 2.12.x |
| D3 | Final trials per task | 1 (504 rollouts), 2 (1,008), 3 (1,512) | 2. It gives a within-task variance estimate for under an hour of extra wall time | **2 trials per task** (1,008 final episodes) |
| D4 | ALTK-Evolve version | v1.3.0 (the design's pin) or v1.6.1 (latest) | v1.3.0, as registered in the design | **v1.3.0** (`703d033`), as in the design |

---

## 3. Arms

| arm id | what it is | learned artifact | where it plugs in |
|---|---|---|---|
| `seed` | the official AppWorld simplified ReAct code agent with the stock `instructions.txt`, no memory, no helpers, no API notes | none | none |
| `cape-hc` | cap-evolve, hill-climb `--focus all`, stock paired gate `gate_k_se: 1.0`, capabilities `[system-prompt, tools]` | edited `policy/instructions.txt` + `tools/helpers.py` + `tools/api_notes.json` | prompt (P) and tools (T) surfaces |
| `altk` | ALTK-Evolve v1.3.0, guidelines mined from the seed's train trajectories, consolidated losslessly; the dose (full set vs core + top-k retrieval) is chosen on dev | guideline block | memory slot (M) of the same prompt |

All three arms use the same harness, model client, decoding parameters, step cap and
evaluator. Only the files of each arm's own surface differ.

---

## 4. Environment (built once, under `/tmp/aw_eval`)

`/workspace` has 11 GB free and `/tmp` has 81 GB, so every venv, data root and run directory
lives under `/tmp/aw_eval`. Only code and this plan live in the repository (`examples/appworld/`).

```
/tmp/aw_eval/
  appworld/            # git clone StonyBrookNLP/appworld @ 42b5bcf3cd334fee33f0c37c02070a9f5807add5 (+ git lfs pull, + our patch)
  venv-aw/             # python3.11: appworld (-e), appworld-agents (-e experiments[simplified]), pydantic>=2.12,<2.13, cap-evolve core (-e core)
  root_full/           # APPWORLD_ROOT with `appworld download data` (all splits). Used only by the final window
  root_opt/            # APPWORLD_ROOT for search time: data/api_docs, data/base_dbs, data/tasks/<train+dev ids>, data/datasets/{train,dev}.txt. No test ids, no test datasets
  reference/           # read-only context for the cap-evolve optimizer: README excerpts, the ReAct prompt, an API index generated from data/api_docs (public docs, no task data)
  runs/                # cap-evolve run dirs, ALTK store, final window outputs
  progress/            # one progress log per trial + PROGRESS.md (section 10)
```

Steps:
1. `git clone`, `git checkout 42b5bcf3…`, `git lfs install --local && git lfs pull`, apply
   `examples/appworld/patches/appworld-extra-headers.patch` (section 5.2) and record
   `git diff` plus its sha256 in `runs/manifest.json`.
2. `python3.11 -m venv venv-aw`, then `pip install -e appworld -e "appworld/experiments[simplified]"
   "pydantic>=2.12,<2.13"`, then `pip install -e /workspace/worktrees/base/core`, then
   `appworld install --repo` (run in `appworld/`).
3. `appworld download data --root root_full`. Check the split and difficulty counts against
   section 1.1 and stop on any mismatch. Record the sha256 of the data tree.
4. `examples/appworld/scripts/make_roots.py` builds `root_opt` from `root_full`: train and dev
   ids only, and `grep` finds none of the 585 test ids under it.
5. ALTK-Evolve runs in the existing Python 3.12 venv **`/workspace/worktrees/base/.venv`**
   (CPython 3.12.15, managed by `~/.local/bin/uv` 0.13.0; empty before this step, no pip). Install
   with `~/.local/bin/uv pip install -p /workspace/worktrees/base/.venv altk-evolve==1.3.0`, taking
   `torch` from the CPU wheel index (`--index-url https://download.pytorch.org/whl/cpu` for torch
   only), because `/workspace` has about 8 GB free and the CUDA wheels would use most of it.
   Pre-fetch `all-MiniLM-L6-v2` with `HF_HOME=/tmp/aw_eval/hf` so the model cache stays on `/tmp`.
   Record `uv pip freeze -p .venv` in `runs/manifest.json`. This venv is named `venv-altk` below.
   It is git-ignored, so nothing is committed from it.

---

## 5. Model access

### 5.1 Agent under test: gpt-oss-120b on RITS

AppWorld model config used by every arm, identical in search and in the final window:

```
client_name: litellm
name: hosted_vllm/openai/gpt-oss-120b-a100          # hosted_vllm route: accepts reasoning_effort (the openai/ route rejects it)
base_url: "{{MODEL_SERVER_URL}}/gpt-oss-120b-a100/v1"  # MODEL_SERVER_URL=$RITS_URL, rendered by fill_model_server_url
api_key: "unused"                                   # RITS ignores it; auth is the header below
extra_headers_env: {RITS_API_KEY: RITS_API_KET}     # new key added by our patch: header name -> env var holding the secret
reasoning_effort: medium
temperature: 0
max_completion_tokens: 6000
drop_reasoning_content: true                        # do not resend old reasoning; saves context in the 40K window
use_cache: false                                    # repeated trials must hit the model, not the joblib cache
retry_after_n_seconds: 15
max_retries: 20
cost_per_token: all 0                               # RITS is unpriced: reported as "unknown", never as $0
```

Agent parameters: `max_steps` 50, `ignore_multiple_calls` true, `max_output_length` 60000
characters (trims old observations so the prompt stays under about 30K tokens: the stock prompt
is about 3.2K tokens, the probe grew about 500 tokens per step, and 6K is reserved for
completion), `max_output_tokens_per_task` 100000, `random_seed` 100 + trial index,
`raise_on_extra_parameters` true. The process environment sets `OPENAI_API_KEY=unused`.

A context-window error from vLLM (HTTP 400) ends the episode with reward 0 and is classified
as `artifact:context_exceeded`, not as infrastructure. The rate is reported per arm.

### 5.2 The change to the AppWorld clone

`examples/appworld/patches/appworld-extra-headers.patch` touches only
`experiments/code/simplified/language_model.py`:
1. Add `extra_headers: dict[str, str] | None = None` to `non_cached_lm_call` and
   `cached_lm_call`, and forward it to `litellm.completion` (`client_name: litellm`) or to the
   `OpenAI` client's `default_headers` (`client_name: openai`).
2. Add `extra_headers_env: dict[str, str] | None = None` to `LanguageModel.__init__`. Each
   header value is read from the named environment variable at init, mirroring the existing
   `api_key_env_name`, so no secret is ever written into a config file.
3. In `may_log_call`, remove `extra_headers` and `api_key` from the logged arguments, so the
   RITS key never reaches `lm_calls.jsonl` (and so never reaches the trajectories the optimizer
   reads).

Acceptance (A2, section 11): one dev episode runs, and `grep -r "$RITS_API_KET" /tmp/aw_eval/runs`
finds nothing. The global `litellm.headers`, used in the probe of section 1.1, is not used: it
would apply the RITS header to every litellm call in the process.

### 5.3 Optimizer: the claude-code CLI for cap-evolve, litellm for ALTK-Evolve

- `OPT_MODEL=aws/claude-sonnet-5-5` (decision D1; verified through the API and the claude CLI on 2026-10-13).
- cap-evolve: `optimizer_skill: claude-code`, `optimizer_model: $OPT_MODEL`. The `claude` CLI
  inherits `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN` and `ANTHROPIC_CUSTOM_HEADERS` from the
  session environment that `settings.json` sets. Probe A1 runs `claude -p "reply ok" --model
  $OPT_MODEL` from a scratch directory before launch.
- ALTK-Evolve: our driver `examples/appworld/altk/altk_mine.py` (runs in `venv-altk` = `/workspace/worktrees/base/.venv`, Python 3.12) sets
  `EVOLVE_GUIDELINES_MODEL=EVOLVE_MODEL_NAME=anthropic/$OPT_MODEL` and
  `EVOLVE_CUSTOM_LLM_PROVIDER=anthropic`. It wraps `litellm.completion` once, in our process
  only, to add `api_base=$ANTHROPIC_BASE_URL`, `api_key=$ANTHROPIC_AUTH_TOKEN` and
  `extra_headers={x-context-guru-token: …}`, and to count tokens per call into
  `runs/altk/optimizer_usage.jsonl`. The library is not modified. Probe A1 also makes one
  `generate_guidelines` call on a toy trajectory.

---

## 6. The common harness and the capability layout

### 6.1 Injection: a subclass in our adapter, not edits to AppWorld

`examples/appworld/adapters/aw_agent.py` defines `CapReActAgent(SimplifiedReActCodeAgent)`. It
overrides only `initialize(world)`:
1. Read the prompt template from the candidate's `policy/instructions.txt` instead of the
   stock path. It must still render with `instruction`, `main_user` and `app_descriptions`.
2. If the candidate has a memory block (`memory/playbook.md`, or the per-task
   `memory/retrieval.json` entry for this task id), insert it immediately before the final
   `My name is: … Task: {{ instruction }}` block of the rendered prompt, under the heading
   `Guidelines learned from past task attempts:`. The seed and `cape-hc` have no memory
   block, so for them the prompt is byte-identical to stock.
3. Before step 1, run one setup snippet with `world.execute`. It defines the functions of
   `tools/helpers.py` in the REPL namespace, and it wraps `apis.api_docs.show_api_doc` and
   `show_api_descriptions` so their output gets the matching `tools/api_notes.json` note
   appended. The original text is left unchanged. The snippet is not an agent step and makes
   no app API call. A one-line notice is appended to the prompt only when helpers exist, so
   the agent knows they are there.
4. Count steps, prompt and completion tokens, trims and termination reason.

If the wrapper in step 3 cannot be installed through `world.execute` in this AppWorld version
(acceptance A4), the API notes are rendered into the prompt after the instructions instead.
That decision is made and logged before launch, never after a result.

### 6.2 Seed capability (`examples/appworld/seed_capability/`)

```
policy/instructions.txt   # byte copy of experiments/prompts/react_code_agent/instructions.txt @ 42b5bcf   (system-prompt)
tools/helpers.py          # empty module                                                               (tools)
tools/api_notes.json      # {}                                                                          (tools)
memory/                   # empty; used only by the altk arm. Not editable by cape-hc (not in its capabilities)
```

Lints run at materialization. A violating candidate is rejected with `lint_reject` before any
rollout:
- prompt: renders with the three Jinja variables; at most 8,000 tokens; no 8-gram from any
  train or dev task instruction; no supervisor name, email or phone number from any train or
  dev task (AppWorld permits generic hints, not task-specific ones).
- helpers: AST lint. No string literal equal to an AppWorld app or API name, no `apis.<app>.`
  attribute chain (helpers take `apis` and names as parameters), no imports outside `re`,
  `json`, `math`, `datetime`, `itertools`, `collections`, `functools`, no file or network
  access, no top-level calls; at most 400 lines. This encodes AppWorld's rule against
  hardcoded API calls.
- notes: at most 400 characters each and 20,000 tokens in total; the same n-gram check.
- memory block (altk): at most 30,000 characters (about 8K tokens), to stay inside the context
  budget.

---

## 7. cap-evolve arm (`cape-hc`): adapter and spec

### 7.1 Adapter (`examples/appworld/adapters/adapter.py`, contract in `docs/ADAPTER_CONTRACT.md`)

- `tasks(split)`: `train` and `val` both return the same 147 ids, the union of the official
  `train.txt` and `dev.txt` read with `load_task_ids` (rule S2, section 9). `test` returns `[]`.
  The ids are never typed by hand or sampled. A seal refuses any id outside train ∪ dev unless
  `AW_ALLOW_SEALED=final-eval-only` is set
  (only the final window sets it; the same pattern as the tau2 `TAU_ALLOW_SEALED_TEST`). The
  task input holds the instruction only; difficulty is never exposed.
- `run_trials(tasks, ctx, n_trials, base_seed)`: a `multiprocessing` spawn pool of
  `AW_WORKERS` processes (default 24) with `maxtasksperchild=1`. Each episode is one
  `CapReActAgent` run in one process with `experiment_name=<run>/<tag>/t<k>` and
  `APPWORLD_ROOT=root_opt` (search) or `root_full` (final). After the agent finishes, the worker
  calls `world.evaluate()` and serializes the result into `Rollout.metadata`: success,
  requirement texts of failures, pass count, the no-collateral-damage flag. **The `trace` field
  of failures is removed before anything is written**, because it contains gold values. The
  trajectory goes into `Rollout.trace` as (thought, code, output truncated to 2,000 characters)
  per step. Wall cap 30 minutes per episode. Provider 429/5xx or connection failure after the
  client's retries sets `Rollout.error` (infrastructure; never scored as a failure, retried
  once).
- `run_target`: delegates to `run_trials` with one task.
- `score`: reward 1.0 if success, else 0.0. The feedback is feedback tier F1 of the design:
  failed requirement texts, collateral-damage flag, whether `complete_task` was called, steps
  used, API error count parsed from outputs, termination reason. It never includes the gold
  answer, `trace`, `answer.json`, solution or test data. Shown-only metrics are steps and
  prompt and completion tokens. Deterministic on a fixed rollout.
- `trajectories(split)`: `None`, so the optimizer reads cap-evolve's per-rollout JSON (gold-free
  by construction). The native AppWorld output directory is not exposed, because its
  `lm_calls.jsonl` repeats the full prompt every step.
- `runner_model()`: `openai/gpt-oss-120b-a100`.

### 7.2 Spec (`examples/appworld/capevolve.yaml`)

```
capabilities: [system-prompt, tools]
capability_path: seed_capability
actions: [edit]
optimizer_skill: claude-code
optimizer_model: ${OPT_MODEL}
optimizer_max_turns: 200
optimizer_usd_per_iter: 15.0
max_optimizer_usd: 120.0
target_model: openai/gpt-oss-120b-a100
algorithm_skill: hill-climb
algorithm_focus: all
orchestration_mode: deterministic
memory_skill: md-files
optimizer_instructions_file: /abs/path/.capevolve/project/optimizer/INSTRUCTIONS.md   # absolute, issue #252
runner_repo_path: /tmp/aw_eval/reference
capability_sources: [reference/api_index.md, reference/react_agent_notes.md]
dataset_source: adapter
split_ids_file: split_ids.json        # {"train": train ∪ dev (147), "val": the same 147 ids, "test": []}; built by scripts/make_splits.py from data/datasets/{train,dev}.txt
num_trials: 1
gate_mode: paired
gate_k_se: 1.0
max_iterations: 6
stall: 0
max_metric_calls: 1050                # 147 baseline (scored once, train = val) + 6 x 147
protected_paths: [default]
store: git
```

Intake: the project is scaffolded with `skills/phases/intake/scripts/run.py`, and every
resolved input is recorded in `PROJECT.md`. `optimizer/INSTRUCTIONS.md` is customized as the
intake skill requires: every `{{…}}` placeholder is kept; the sections for capabilities not in
the run are deleted; and AppWorld facts are added (REPL semantics, where the trajectories are,
the hardcoding rule and the lints of 6.2, that the prompt must keep its three Jinja variables
and its `USER:`/`ASSISTANT:` structure, that helpers are plain functions taking `apis`). Then
`cap-evolve check .capevolve/project` must print `{"ok": true}` and
`cap-evolve estimate` is recorded.

Launch: `cap-evolve run --spec … --project … --run-ts cape_hc_s0 --dashboard off --follow`
under `nohup`, with stderr teed to `progress/cape_hc.log`.

---

## 8. ALTK-Evolve arm (`altk`)

The design (section 6.3, A-ALTK) is followed. It uses the library as released, because the
authors' AppWorld harness is not released.

1. **Trajectories.** The seed's rollouts of the 90 official `train` ids are reused from the
   cape-hc baseline. Because train = val there, they are under
   `runs/cape_hc_s0/rollouts/val/<train id>__seed__t0.json`; the 57 dev ids are filtered out, so
   ALTK mines `train` only, as in the design. It is the same seed, the same harness
   and the same rollouts, so the mining data is identical to what cap-evolve's baseline saw,
   and 90 rollouts are saved. If the cape-hc baseline fails, the altk sub-agent collects them
   itself with the same adapter.
2. **Conversion** (`altk/to_messages.py`): `[{user: "<instruction>\nSupervisor: <name>"},
   {assistant: thought + code}, {user: "Output: …"}, …]`. The bare task instruction comes first
   because ALTK uses the first user message as the task description. The stock demo and the
   API docs are not included (they would become the "task"). No outcome label is passed: the
   library's default mode, where success is judged from the trajectory itself.
3. **Mining** (`altk/altk_mine.py`, `venv-altk`, filesystem backend, namespace `aw_train`):
   `save_trajectory` per trajectory with `EVOLVE_GUIDELINES_MODE=standard` and segmentation on
   (library defaults), 8 trajectories in parallel. Then `consolidate_guidelines(mode="lossless")`
   (default threshold 0.80). The driver logs guideline count, total support before and after
   (they must be equal), and optimizer tokens.
4. **Rendering** (`altk/altk_render.py`), two doses:
   - `altk-full`: the whole consolidated set (`injection_mode=static`), one block in
     `memory/playbook.md`.
   - `altk-ret`: core (`core_support` 3) plus top-k 10 per task (`select_guidelines`,
     `injection_mode=retrieval`), one block per task id in `memory/retrieval.json`. Rendered for
     dev at selection time, and for test_normal only inside the final window. Retrieval uses
     only the instruction text.
   Both use the library's `format_selection` text, inserted into the memory slot of 6.1.
5. **Dose selection on dev** (rule fixed in advance): score both doses on the 57 dev tasks, 1
   trial each (114 rollouts). Take the higher TGC; on a tie take the one with fewer memory
   tokens. The chosen dose is the `altk` champion. The other dose's dev score is reported as a
   diagnostic.

Counted rollouts are reported beside every result: 90 (shared train seed rollouts) + 114 dev. ALTK-Evolve
needs no more natively. Budgets are therefore not matched; section 13 says so.

---

## 9. Splits, feedback and isolation

Two rules, set by the user on 2026-10-13:

- **S1. Official splits only.** Every task id in every trial comes from AppWorld's own split
  files (`data/datasets/*.txt`, read with `load_task_ids`), as listed in section 1.2. No
  re-splitting, sub-sampling or hand-picked subsets in any counted rollout. The acceptance probes
  of section 11 use a few dev ids and are not counted. The sha256 of each of the four id files
  is recorded in `runs/manifest.json`, and `make_splits.py` refuses to run if the counts differ
  from 90 / 57 / 168 / 417.
- **S2. cap-evolve: train = val = train ∪ dev.** In cap-evolve's `split_ids.json`, both `train`
  and `val` are the union of the official `train` and `dev` ids (147), and `test` is `[]`.
  `test_normal` is scored for every arm in the common final window (section 12).

| official split | cape-hc | altk | final window |
|---|---|---|---|
| `train` (90) | in cap-evolve's train = val: the optimizer's trajectories and the gate | mining (seed trajectories) | not used |
| `dev` (57) | in cap-evolve's train = val: the optimizer's trajectories and the gate | dose selection | not used |
| `test_normal` (168) | never at search time | never at search time | scored, 3 arms × 2 trials |
| `test_challenge` (417) | not used | not used | not used |

Consequences:
- cape-hc's val score is a fit metric: the optimizer reads trajectories from the same 147 tasks
  its gate is scored on, so the score is selection-biased. It is reported as "optimization set
  (train = val), selection-biased", the label of `docs/HOLDOUT_PROTOCOL.md`. Only `test_normal`
  is a held-out result.
- Both methods use only train ∪ dev at search time. cape-hc uses all 147 tasks for proposals and
  the gate. altk mines the 90 train tasks and selects its dose on the 57 dev tasks, following the
  official roles, as in the design. This difference is part of the methods and is stated in the
  results.

Isolation, scaled down from the design (section 5.2 there):
- Two data roots. Search-time processes get `APPWORLD_ROOT=root_opt`, which has no test files.
  `root_full` is used only by the final window. A separate OS user is not available on this
  host, so this is directory separation, not permission separation; disclosed.
- The adapter seal (7.1). Test ids appear in no search-time file, prompt or log.
- AppWorld REPL guards stay on (`raise_on_unsafe_syntax`, the execution guard). Acceptance A3
  checks that `import os` and `open(<root_opt>/data/tasks/<train id>/ground_truth/answer.json)`
  inside `world.execute` both fail.
- Feedback tier F1 only (7.1): no `trace`, no gold answer, no solution.
- No leaderboard bundles and no `appworld download experiment-outputs`.
- After both searches, a transcript scan greps every optimizer transcript, workdir and ALTK
  store for test ids, the canary string, `test_normal`, `root_full`, `answer.json` and
  `ground_truth`. The counts go into the results. A hit is reported, and the arm is labelled
  "isolation breach".

---

## 10. Orchestration, sub-agents and progress log

The long work runs as detached `nohup` processes that write their own logs. Sub-agents start
and watch them and handle failures, so a sub-agent that stops does not kill a trial. At most 3
sub-agents run at once (the limit is 10).

| sub-agent | trial | depends on | RITS concurrency |
|---|---|---|---|
| `cape-hc` | the cap-evolve run (section 7) | environment + acceptance checks | `AW_WORKERS=24` |
| `altk` | mining → rendering → dose selection (section 8) | cape-hc's baseline train rollouts (`baseline.json` written) | 24 |
| `final` | final window + analysis (section 12) | both champions frozen | 48 |

Progress log (what to watch):
- `/tmp/aw_eval/progress/<trial>.log`: one line per event, `UTC | trial | phase | detail`.
  Examples: `baseline val=0.xx`, `iter 3 ACCEPT val=…`, `mined 41/90`, `dose altk-ret dev=…`,
  `final 312/1008 episodes`.
- `/tmp/aw_eval/progress/PROGRESS.md`: one table (trial, phase, % done, last event, rollouts
  used, optimizer tokens, ETA), regenerated every 5 minutes by
  `examples/appworld/scripts/status.py`. It reads cap-evolve's `events.jsonl` and the
  ALTK/final logs.
- To watch: `watch -n 60 cat /tmp/aw_eval/progress/PROGRESS.md`, or
  `cap-evolve tail /tmp/aw_eval/runs/cape_hc_s0/.capevolve/run_cape_hc_s0`.

---

## 11. Acceptance checks before any counted rollout

| id | check |
|---|---|
| A1 | `aws/claude-sonnet-5-5` answers through the claude CLI (verified 2026-10-13) and through the ALTK litellm wrapper |
| A2 | RITS through the patched client: 1 dev episode completes; the RITS key appears nowhere under `/tmp/aw_eval/runs` |
| A3 | REPL isolation (section 9) and `root_opt` contains no test id; `split_ids.json` equals train.txt ∪ dev.txt exactly (rule S2) |
| A4 | injection: on 1 dev task, the seed prompt is byte-identical to the stock agent's first request; a playbook block appears in the right place; the helper and notes setup works and leaves `show_api_doc`'s original text unchanged; a lint-violating helper is rejected without a rollout |
| A5 | scoring: a scripted correct solution (a train task's released solution, run through `world.execute`) gives reward 1; a no-op gives 0; the persisted metadata has no `trace`; `score` twice is identical |
| A6 | `cap-evolve check` is `{"ok": true}` on the real `split_ids.json` (train = val = 147, test = []); a 1-iteration dry run on a throwaway copy whose split file holds 4 dev ids, with `optimizer_skill: mock`, completes, and its baseline logs `train ids identical to val` |
| A7 | ALTK: one trajectory → `save_trajectory` → ≥ 1 guideline; consolidation conserves support; both renderers produce a block under the size limit |
| A8 | context: the longest of 10 dev episodes stays under 34K prompt tokens with `max_output_length` 60000 |

---

## 12. Final window, statistics and the report

- Freeze: `cape-hc` = `candidates/<best_id>` of its run (the seed if nothing was accepted;
  then the arm is "inert" and says so). `altk` = the chosen dose. Copy each into
  `runs/final/artifacts/<arm>/` and record sha256 tree hashes.
- Window: 168 test_normal tasks × 3 arms × 2 trials = 1,008 episodes, in one random order with a
  recorded seed, `AW_ALLOW_SEALED=final-eval-only`, `APPWORLD_ROOT=root_full`, 48 workers. For
  `altk-ret`, the per-task blocks are rendered first from the instruction text only. Trial seeds
  are `random_seed` 5000 + trial. Infrastructure failures are retried up to 3 times; a cell that
  still fails is scored 0 (primary) and reported as missing (sensitivity).
- Only rewards, counters and infrastructure flags are read from test rollouts. No test
  trajectory is read by a person or an LLM; AppWorld forbids error analysis on test.
- Metrics: TGC (mean over tasks of the mean over trials of success); SGC (a scenario passes in
  trial k if all 3 of its tasks pass; averaged over k); both by difficulty (Easy 57, Medium 48,
  Hard 63). Paired differences `cape-hc − seed`, `altk − seed`, `cape-hc − altk` with a
  scenario-clustered paired bootstrap (56 clusters, 10,000 resamples) 95% CI, no multiplicity
  correction. Each run is one search seed, so these are artifact-level statements only.
- Cost table: target tokens per task (prompt and completion), steps per task, step-cap hits,
  context-exceeded count; memory tokens per step and guideline count (altk); optimizer input and
  output tokens and calls per method (cap-evolve from its `state.json` spend, ALTK from the
  wrapper log); counted rollouts per method; search-time score of each champion (cape-hc: val = train ∪ dev, a fit metric; altk: dev); wall time.
- Side-by-side with the colleagues' gpt-oss-120b numbers (design section 3.1: no memory 39.9 /
  21.4, ALTK-Evolve 56.0 / 37.5), compared only as gains over each side's own baseline. Their
  harness, template and dose differ (design section 3.2).

Results comment on #804 (markdown): setup block (commits, models, settings, D1–D4 outcomes);
the main table (TGC, SGC, Δ vs seed with CI, per arm); the difficulty table; the cost table;
what changed (cape-hc: summary of accepted edits; altk: number of guidelines and 3 example
guidelines); isolation scan counts; deviations (section 13) and what the numbers cannot
support (one search seed, no matched budget, no Holm, no TOST). No task text, ids, solutions or
gold values are posted (AppWorld redistribution rule). The draft is written to
`runs/final/RESULTS.md` first, then posted with `gh issue comment 804 --body-file`.

---

## 13. Deviations from the full design, and why

| design | smoke test | why |
|---|---|---|
| 2 targets (DeepSeek-V3.2, gpt-oss-120b) | gpt-oss-120b only | scope 2.4 |
| 8 CapEvolve cells, 5 Tier-1 + 4 Tier-2 competitors | `cape-hc` (prompt+tools, a cell the design does not list) + `altk` | scope 2.1, 2.2, 2.5 |
| 3 search seeds, N* matched budget (B = 900) | 1 seed; cape-hc ≤ 1,050 counted rollouts, altk native (~204) | smoke scale; counts are reported beside the scores |
| CapEvolve optimizes on `train` and gates on `dev` | cape-hc: train = val = train ∪ dev (147); its val score is a fit metric | user rule S2 (section 9) |
| final n = 3 per arm, seed n = 10, seed-check, template panel, drift blocks | n = 2 for all three arms, one interleaved window | smoke scale (D3) |
| Holm families F1–F6, TOST 0.10, pipeline-level t(2) | unadjusted paired cluster-bootstrap CIs, artifact level only | 1 seed and 3 arms |
| `appworld==0.1.3.post1` + head ReAct agent | core + agents from source at `42b5bcf`, pydantic 2.12.x | the pin is not installable (section 1.1, D2) |
| `max_completion_tokens` 8000 | 6000 + history trimming (`max_output_length` 60000) | RITS window is 40,144 tokens |
| separate OS user, containers, closed egress, proposer sandbox | separate data roots, adapter seal, REPL guards, transcript scan | host constraints; disclosed |
| surfaces T (helpers + notes) and M (playbook) for CapEvolve | cape-hc edits P + T; M is used only by altk | scope 2.5 ("tools and prompts") |

---

## 14. Budget and timeline (projections)

| phase | rollouts | wall time (estimate) |
|---|---|---|
| build + acceptance checks | ≈ 30 | 2–3 h of build work |
| cape-hc baseline (train ∪ dev, scored once since train = val) | 147 | 0.5 h |
| cape-hc 6 iterations (optimizer 15–40 min + 147 rollouts each) | 882 | 4.5–7 h |
| altk mining (≈ 500–800 optimizer calls) + 2 doses on dev, in parallel with cape-hc | 114 | 1.5–2 h |
| final window | 1,008 | 2–3 h |
| analysis, report, post | 0 | 0.5 h |
| **total** | **≈ 2,180** | **≈ 11–15 h** after the build |

Throughput basis: the probe's 30–300 s per episode, and RITS at 48 concurrent requests without
errors. RITS has no budget. Optimizer spend: cap-evolve capped at $120 by `max_optimizer_usd`;
ALTK about 4–6M input and 0.5–1M output tokens. Both are recorded exactly.

## 15. Risks

| risk | mitigation |
|---|---|
| optimizer gateway fails or throttles mid-run | A1 before launch; cap-evolve `--resume`; the ALTK store is idempotent per trajectory |
| context window overflow on long episodes | `max_output_length` trimming, A8, the `context_exceeded` count per arm; the altk memory block is size-capped |
| RITS throttling or outage during the final window | infrastructure retries with new seeds; one window, so all arms are hit equally; a pause/resume flag in the final runner |
| cape-hc accepts nothing (inert) | that is a result: reported as "no candidate cleared the gate", with the per-iteration val (train ∪ dev) deltas |
| gpt-oss output format (code block missing, or `complete_task` called at step 1) | that is seed behaviour; both methods may address it (prompt, or guidelines); counted per arm |
| ALTK extraction errors on unusual trajectories | the library already logs and skips (`Standard guideline generation failed …`); the number of skipped trajectories is reported |
| sub-agent stops mid-trial | trials are detached processes with on-disk state (`cap-evolve run --resume`; the ALTK store is idempotent per trajectory id) |

---

## Appendix A. Execution log, findings and deviations (2026-10-13)

This appendix records what happened when the plan was executed, what was found that the plan
did not anticipate, and every place where the execution differs from sections 0 to 15. Section
numbers refer to the plan above. Results are in Appendix B.

### A.1 Environment as found, and as built

| item | plan assumed | found / done |
|---|---|---|
| Python 3.12 venv `/workspace/worktrees/base/.venv` | exists, managed by `~/.local/bin/uv` 0.13.0 | did not exist; `uv` was not installed. Installed `uv` 0.13.0 and CPython 3.12.15 with it (`uv python install 3.12`), created `.venv` (git-ignored) |
| RITS credentials | `.env` with `RITS_API_KET` | no `.env` in the worktree at the start; the user created it (`RITS_URL`, `RITS_API_KET`). The key is read from that file by each episode worker and never exported (A.3) |
| free disk | `/workspace` 11 GB, `/tmp` 81 GB | both on one 1.5 TB volume with 544 GB free; layout under `/tmp/aw_eval` kept as planned |
| AppWorld build (§4 steps 1–3) | as written | worked as written: `42b5bcf`, `git lfs pull`, pydantic 2.12.5, fastapi 0.143.0, litellm 1.80.0; split counts 90/57/168/417 and scenario counts 30/19/56/139 match §1.1. `data/tasks` also holds a `_base_` dir (copied to `root_opt`) |
| ALTK-Evolve (§4 step 5) | `uv pip install altk-evolve==1.3.0`, CPU torch | worked as written |

### A.2 Code added (all under `examples/appworld/`)

| file | role (plan section) |
|---|---|
| `patches/appworld-extra-headers.patch` | §5.2, 18 added lines in `language_model.py` (sha256 recorded in `runs/manifest.json`) |
| `adapters/aw_agent.py` | `CapReActAgent` (§6.1) and the one-episode worker (one process per episode) |
| `adapters/adapter.py` | the cap-evolve adapter (§7.1) |
| `adapters/lints.py` | the candidate lints (§6.2), also runnable by the optimizer before it stops |
| `seed_capability/` | §6.2; `policy/instructions.txt` is a byte copy of the stock prompt |
| `capevolve.yaml`, `optimizer/INSTRUCTIONS.template.md`, `scripts/setup_project.sh` | §7.2 spec, intake-customized instructions (every `{{…}}` placeholder kept), scaffolding + `cap-evolve check` |
| `scripts/make_roots.py`, `make_splits.py`, `make_reference.py`, `awpaths.py` | §4 step 4, rule S1/S2 split file, optimizer reference dir |
| `scripts/check_injection.py`, `check_scoring_isolation.py`, `altk/check_altk.py` | acceptance A4, A3 + A5, A7 |
| `altk/altk_common.py`, `to_messages.py`, `altk_mine.py`, `altk_render.py`, `select_dose.py`, `run_altk.sh` | the altk arm (§8) |
| `scripts/final_window.py`, `analyze.py`, `scan_isolation.py`, `status.py` | §12 window and statistics, §9 scan, §10 progress page |

### A.3 Findings

**F1. The AppWorld REPL guard does not block file reads or the environment (affects A3 and isolation).**
`os`, `pathlib` and `io` are on AppWorld's import allowlist (`appworld/common/safety_guard.py`,
`ALLOWED_MODULE_NAMES`). `open()` is blocked at syntax level, but `pathlib.Path(...).read_text()`
goes through AppWorld's read-only `open` replacement and succeeds, and `os.listdir` and
`os.environ` work. Probe: from inside `world.execute`, the agent could list `/tmp/aw_eval` and
read `split_ids.json`; `subprocess`, `sys`, `socket` and `io.open` were blocked. So A3's
expectation that `import os` fails was wrong for this AppWorld version, and the agent under test
could have read `ground_truth/answer.json` (train/dev at search time, test in the final window)
or the RITS key. Done, identically for all three arms: (a) the episode worker removes `os`,
`pathlib`, `io`, `shutil` and `glob` from the import allowlist; (b) the RITS key is read from
`.env` by the worker, used to build the client, and then removed from `os.environ` before the
world starts; (c) every episode records `fs_probe` = whether the agent's code mentions
`ground_truth`, `answer.json`, `/data/tasks`, `APPWORLD_ROOT`, `root_full`, `root_opt` or
`test_normal`; the count per arm is reported. With (a), A3 passes as written.

**F2. `max_output_tokens_per_task` is never enforced by AppWorld at `42b5bcf`.**
`UsageTracker.exceeded()` checks overall cost, overall input/output tokens and per-task *cost*
only; the per-task output-token limit is stored and never read. With RITS priced at 0, the
per-task cost cap never fires either, so only `max_steps` would bind. The episode loop in
`aw_agent.py` enforces 100,000 completion tokens per task itself (termination `token_cap`),
the same for every arm.

**F3. The official gpt-oss-120b ReAct config differs from §5.1 in three ways.**
`experiments/configs/simplified_react_code_agent/openai/gpt-oss-120b-medium-reasoning_openrouter`
uses `api_type: responses`, `drop_reasoning_content: false` and `max_output_length: null` (no
trimming), with `max_retries` 100. The plan's `hosted_vllm` chat-completions route,
`drop_reasoning_content: true` and 60,000-character trimming are kept (they are what fits RITS's
40K window), but they are a deviation from the official config and are listed in A.4.
In A8 the longest of 10 dev episodes reached 12,169 prompt tokens and no trimming fired, so the
trimming choice has not mattered so far.

**F4. The setup snippet is a REPL interaction.** Defining helpers and wrapping the API-doc
lookups goes through `world.execute`, so it appears once in AppWorld's `environment_io` log and
counts once toward `max_interactions` (1,000). It is not an agent step and makes no app API
call. For the seed and the altk arm (no helpers, no notes) no snippet runs at all, which keeps
the seed byte-identical to stock (A4.1).

**F5. ALTK-Evolve's structured-output path does not work with this gateway.** For an
`anthropic/` model litellm emulates `response_format` with a forced `tool_choice`, and the
gateway rejects that for `aws/claude-sonnet-5-5` (HTTP 400, "tool_choice: type tool and any are
not supported for this model"). The driver reports no response-schema support for this model
(`litellm.supports_response_schema` patched in our process before ALTK is imported), so the
library uses its own prompt-JSON path, the one it already uses for groq models. The library is
not modified.

**F6. `save_trajectory` returns trajectory entities, not guidelines.** The miner counts each
task's guidelines in the store by `metadata.source_task_id`. Guidelines are written with the
library's conflict resolution on (an extra LLM call per batch), its default for this tool.

**F7. `format_selection` already writes the heading.** Its block starts with "Guidelines learned
from past task attempts (follow these carefully; …)". The memory slot adds the plan's heading
only when the block lacks one, so the heading is not doubled.

**F8. The claude-code optimizer can read the whole host.** The registry row gives it `Bash`
(`--allowedTools Bash`), so it could read `root_opt/.../ground_truth` (train/dev gold) and any
other file. Mitigations added beyond §9: `root_full` is `chmod 000` for the whole search phase
and unlocked only for the final window; the RITS key is not in the environment that cap-evolve
(and so the optimizer) inherits; AppWorld's native per-episode output dirs (which hold the
evaluation report with gold traces) are deleted after each episode's gold-free record is read.
The optimizer instructions say not to look for gold data. The transcript scan of §9 remains the
check; it cannot prevent a read of train/dev ground truth, only detect it.

**F9. `cap-evolve estimate` does not price this optimizer model.** It reported $0.36 for 6
iterations from its bundled price table. The binding limits are the claude CLI's
`--max-budget-usd 15` per iteration and `max_optimizer_usd: 120`.

**F10. Temperature 0 is not deterministic at scale (corrected).** In A6, re-scoring the unchanged
seed on 4 dev tasks gave identical rewards (paired Δ = 0, SE = 0). In the final window, however, the two
trials of a task disagreed on 64/168 tasks (seed), 42/168 (cape-hc) and 40/168 (altk). So D3's second
trial carries real variance information, and the search's single trial per task is a noisy measurement.

**F11. The `altk-full` dose cannot be used: 1,715 guidelines, 402,775 characters.** Mining the
90 seed train trajectories gave 1,867 guidelines (88 trajectories mined; 2 failed in the library's
conflict resolution, "Failed to resolve conflicts after 3 attempts"). Lossless consolidation at
threshold 0.80 found 282 clusters and merged them to 1,715 guidelines, with support conserved
(1,867 → 1,867). The full set rendered by `format_selection` is 402,775 characters, about 83,500
tokens: more than twice gpt-oss-120b's whole 40,144-token window, and 13× the plan's 30,000-character
memory cap. By the plan's own lint rule (§6.2: a violating candidate is rejected before any rollout),
`altk-full` was infeasible and was not run. `altk-ret` (core of 18 guidelines with support ≥ 3, plus
the top 10 retrieved per task; at most 10,729 characters, 2,086 tokens per dev task on average) was the
only feasible dose and is the altk champion. Its dev TGC was 0.456 (57 tasks, 0 infra errors). The
plan expected the full set to be small enough to compare; at this harness's segmentation (25–31
guidelines per trajectory) it is not. A lossy consolidation (`lossy_target_num_guidelines` 12) would
give a feasible "full" dose, but it is a different arm from the one the plan fixed, so it was not
substituted. Counted altk rollouts: 90 (shared seed train rollouts) + 57 dev = 147, not 204.

**F12. Lossless consolidation is slow.** It makes one LLM call per cluster, sequentially: 282
clusters took 53 minutes (13 s per call). Mining used 8 parallel trajectories and took 30 minutes. ALTK
optimizer usage for mining and consolidation: 1,031 calls (1 error), 2.50M input and 1.30M output
tokens. The plan's estimate (500–800 calls, 4–6M input) was off by about 1.5× in calls and 0.5× in
input tokens.

**F13. The 30-minute wall cap fired once.** In iteration 2, one episode's first attempt passed 1,800 s;
it was classified as infrastructure, retried once, and finished in 206 s (6 steps). No other search
episode was retried or errored.

**F14. ISOLATION BREACH in cape-hc iteration 2 (train/dev gold; test not reached).** An early
grep of the optimizer transcripts during the run found 36 tool calls, all in iteration 2
(`cand_0002`, accepted, val 0.653 → 0.707), made by the claude-code optimizer's parallel subagents:
- `ls` of `root_opt/data/tasks/<id>/ground_truth/`, and `cat`/`sed` of `solution.py`,
  `private_data.json`, `evaluation.py` and `public_data.json` for train/dev tasks (e.g. `34d9492_1`,
  `68ee2c9_1`, `68ee2c9_2`, `7d7fbf6_1`);
- a copy of `root_opt` to `/tmp/diag/root`, and scripts that ran released `compiled_solution.py` files
  and the subagents' own helper code through `AppWorld(...)` and `world.evaluate(suppress_errors=False)`,
  which prints the evaluator's gold traces (outputs under `root_opt/experiments/outputs/diag*`);
- `find /` for task directories, and `ls root_full` (refused: `root_full` was `chmod 000`).
No test id, test file or canary was read. Iterations 1 and 3 have no such call. This goes past
feedback tier F1 (§7.1, §9): the optimizer saw solutions and gold traces for some train/dev tasks.
The lints (no 8-grams, no task values, no hardcoded API chains) still passed, so what could carry over
is knowledge of how tasks are solved and checked, not literal answers. The instruction "do not try to
find gold answers … on disk" did not stop subagents that were exploring how to verify a helper.
From iteration 4 on (18:37 UTC), `runs/optimizer_guard.sh` puts `root_opt` (and `/tmp/diag/root`) at
`chmod 000` whenever an optimizer `claude -p` process runs and restores it when the process exits,
before the harness scores the candidate. The lint then reads a pre-built cache (`lint_cache.json`:
instruction 8-grams, supervisor contacts, app/API names) instead of `root_opt`. Iterations 3 to 6 build
on iteration 2's accepted edits. **Decision (user, 2026-10-13): continue, and label the cape-hc arm
"isolation breach (train/dev gold read in iteration 2)" in every result, as §9 says.** The guard is
directory permissions under one OS user, so a determined optimizer could undo it; the full transcript
scan after the search checks iterations 4 to 6 again.

**F15. The first guard broke iterations 4–6; fixed with a synchronous `claude` shim and a resume.**
The first guard polled once a second for an optimizer process. When iteration 4's optimizer exited
(18:50:49), the harness asked the adapter for its tasks within the same second, while `root_opt`
was still locked. The evaluation raised, the step was recorded as "indecisive (evaluation error)",
and the harness launched iteration 5's optimizer at once. So the guard never saw a gap, and iterations 5
and 6 failed the same way. After 3 consecutive evaluation errors the harness stopped the run, correctly
calling it "a broken environment/adapter, not bad candidates". Cost: 3 optimizer calls whose candidates
were never scored ($10.53 + $3.82 + $0.79 = $15.14 of the $48.52 spent up to then), and no rollouts.
Fix: (a) `/tmp/aw_eval/bin/claude`, first on the cap-evolve process's PATH only, locks `root_opt`, runs
the real CLI, and unlocks before it returns, so the lock is exactly the optimizer call; (b) the adapter
caches the task list and waits up to 60 s for a readable root before an evaluation. The run was resumed
on 2026-10-14 with `cap-evolve run --resume --max-iterations 8`. With 5 iterations counted as used, that
leaves 3 more, so the run still gets 6 scored iterations (1–3, then three after the resume). The lost
iteration-4 candidate (`work/cand_0004`, $10.53) was not scored.

**F16. AppWorld's canary string is release-wide.** All 732 tasks (train, dev, test_normal,
test_challenge) carry the same `canary_string`, so a canary hit cannot distinguish test data from
train/dev. The post-search scan (`runs/isolation_scan.json`) therefore counts test ids as the
test-access signal. Result: 0 test-id hits in every optimizer transcript, workdir, the cape-hc run dir
and the ALTK store. Train/dev gold reads: iteration 2 only (F14). Iteration 1 listed one train task
directory (it saw that a `ground_truth` folder exists) but opened nothing. Iteration 4's optimizer,
which ran unguarded from 18:27 to 18:37, made directory listings only. Iterations 3 and 5–8: none.

### A.4 Deviations from the plan

| plan | done | why |
|---|---|---|
| §7.1 `multiprocessing` spawn pool, `maxtasksperchild=1` | a thread pool of `AW_WORKERS` that runs each episode as its own subprocess (`aw_agent.py SPEC OUT`) | the same one-world-per-process isolation, plus a real kill at the 30-minute wall cap (`subprocess` timeout) |
| §10 sub-agents watch the trials | detached `nohup` processes (`launch_cape_hc.sh`, `altk/run_altk.sh`, `final_window.py`) with on-disk logs, watched from the main session | the work is sequenced by scripts; nothing depends on a sub-agent staying alive |
| §5.1 model config | as planned, plus F2's token cap enforced in the loop | F2 |
| §9 REPL guards "stay on" | stay on, and 5 modules removed from the import allowlist for every arm | F1 |
| §8 step 3 "segmentation on" | library defaults (standard mode, segmentation on), prompt-JSON path | F5 |
| A3 `import os` fails | passes only with F1's hardening | F1 |
| §8 step 5: dose selection scores both doses (114 dev rollouts) | `altk-full` failed the 30,000-character memory lint and was not run; `altk-ret` was scored on dev (57 rollouts) and chosen as the only feasible dose | F11 |
| §7.2 `max_iterations: 6` | resumed with `--max-iterations 8`: 3 iterations lost to the guard bug count as used, so 6 scored iterations remain the target | F15 |
| §9 isolation by directory separation only | plus `optimizer_guard.sh` from iteration 4: `root_opt` locked while the optimizer runs | F14 |
| §6.2 lint `lint_reject` "before any rollout" | the adapter runs no episode for a violating candidate and scores every task 0 with the violations as feedback; the cap-evolve gate then rejects it. These count as metric calls but cost no model call | hill-climb has no pre-gate hook (the built-in pre-gate belongs to `agent-optimize`) |

### A.5 Acceptance checks (§11)

| id | result |
|---|---|
| A1 | pass. `claude -p --model aws/claude-sonnet-5-5` answered `ok`; through the ALTK wrapper, segmentation + guideline generation on a toy trajectory made 4 calls with no error (after F5) |
| A2 | pass. One dev episode through the patched client: success, 9 steps, max prompt 7,863 tokens, 118 s. `grep` for the key under `runs/` and AppWorld's outputs (with `lm_calls.jsonl` logging on): 0 hits |
| A3 | pass, with F1's hardening: `import os`, `open(answer.json)` and a `pathlib` read all fail; `root_opt` holds 147 task dirs + `_base_`, only `train.txt`/`dev.txt`, 0 test-id hits; `split_ids.json` train = val = train.txt ∪ dev.txt (147), test = [] |
| A4 | pass. Seed first request byte-identical to stock (23 messages); memory block in the final USER message before `My name is:`; helpers defined and notes appended with the original doc JSON unchanged; a violating helper is rejected with 6 violations (import, literal app/API names, `apis.<app>` chain, top-level call) |
| A5 | pass. The released compiled solution of a train task gives reward 1, a no-op 0; scoring twice is identical; the persisted record has no failure trace and no gold answer |
| A6 | pass. `cap-evolve check` `{"ok": true}` on the real project (147 tasks). Mock 1-iteration dry run on 4 dev ids: baseline 0.75, `train ids identical to val — not re-evaluated`, iteration completed, finalize scored 0 test tasks. (The first dry run hit an adapter bug: the candidate path was relative while the worker runs elsewhere. Fixed; the harness had correctly marked it INDECISIVE, not a rejection) |
| A7 | pass. 2 dev trajectories → 10 and 15 guidelines; lossless consolidation 25 → 25, support 25 → 25; full block 6,389 chars, retrieval blocks ≤ 2,906 chars (limit 30,000). 18 optimizer calls |
| A8 | pass. 10 dev episodes, 0 infra errors, 5 passed; max prompt 12,169 tokens (limit 34,000); longest 28 steps / 530 s |

None of the acceptance rollouts are counted (rule S1).

---

## Appendix B. Results (2026-10-14)

Interim results were posted to issue #804 as they came in (updates 1–6), followed by a closing
summary. Raw data: `/tmp/aw_eval/runs/final/results.jsonl` (one line per episode: rewards, counters and
infra flags only) and `results.json`. The analysis is `examples/appworld/scripts/analyze.py`.

### B.1 Search

| | cape-hc | altk |
|---|---|---|
| champion | iteration 6 (`cand_0006`) | retrieval dose (`altk-ret`) |
| search-time score | val = train ∪ dev 0.884 (seed 0.361), a fit metric | dev TGC 0.456 (seed 0.333) |
| iterations | 1 ✓ 0.653, 2 ✓⚠ 0.707, 3 ✓ 0.776, 4–5 lost (F15), 6 ✓ 0.884, 7 ✗ 0.830, 8 ✗ 0.864 | mined 90 train trajectories → 1,867 → 1,715 guidelines |
| counted search rollouts | 1,029 | 147 (90 shared seed train + 57 dev) |
| optimizer | $67.84, 47.5M tokens (about $15 on 3 unscored candidates) | 1,031 calls, 2.50M in / 1.30M out tokens |
| isolation | **breach, train/dev gold read in iteration 2 (F14)**; 0 test-id hits | 0 hits |

### B.2 Final window (test_normal, 168 tasks / 56 scenarios × 2 trials, 1,008 episodes, 0 infra errors, 0 missing cells)

| arm | TGC | SGC | Δ TGC vs seed [95% CI] | Δ SGC vs seed [95% CI] |
|---|---|---|---|---|
| seed | 35.1 | 13.4 | — | — |
| cape-hc ⚠ isolation breach | 53.6 | 34.8 | +18.5 [+10.7, +26.2] | +21.4 [+10.7, +32.1] |
| altk | 41.1 | 23.2 | +6.0 [−0.9, +13.1] | +9.8 [+2.7, +17.9] |

cape-hc − altk: Δ TGC +12.5 [+3.9, +21.4], Δ SGC +11.6 [0.0, +23.2]. Intervals come from a
scenario-clustered paired bootstrap (56 clusters, 10,000 resamples), unadjusted.

| TGC by difficulty | Easy (57) | Medium (48) | Hard (63) |
|---|---|---|---|
| seed | 52.6 | 29.2 | 23.8 |
| cape-hc | 79.8 | 52.1 | 31.0 |
| altk | 64.0 | 28.1 | 30.2 |

| per episode | prompt tok | completion tok | steps | step-cap hits | context exceeded | collateral damage | max prompt tok | fs_probe |
|---|---|---|---|---|---|---|---|---|
| seed | 93,302 | 5,948 | 12.7 | 4 | 0 | 9 | 19,301 | 0 |
| cape-hc | 90,613 | 5,866 | 8.8 | 1 | 0 | 14 | 22,234 | 0 |
| altk | 140,583 | 7,044 | 14.8 | 3 | 0 | 14 | 21,653 | 0 |

### B.3 Reading

- Both learned artifacts beat the seed on held-out test. For cape-hc the CI excludes 0 on both
  metrics; for altk it excludes 0 on SGC only. cape-hc also beats altk on TGC.
- cape-hc's gain sits on Easy and Medium tasks. On Hard tasks the two arms are level
  (31.0 vs 30.2, against the seed's 23.8).
- cape-hc's val (0.884) overstates its test TGC (0.536) by 35 points. Train = val makes val a fit
  metric. The prompt and helpers fit the 147 search tasks well and transfer only partly.
- altk costs about 50% more prompt tokens per episode (memory block plus more steps). cape-hc takes the
  fewest steps (8.8), but it has more collateral-damage failures than the seed (14 vs 9).
- The seed (35.1 / 13.4) is below the colleagues' no-memory gpt-oss-120b numbers (39.9 / 21.4).
  Their ALTK gain was +16.1 / +16.1; here altk gains +6.0 / +9.8 with the retrieval dose only, since
  the full playbook is infeasible (F11).
- Limits: one search seed per method; unmatched budgets (1,029 vs 147 search rollouts); no multiplicity
  correction; cape-hc's isolation breach (F14). These are statements about two artifacts, not about
  the methods.
