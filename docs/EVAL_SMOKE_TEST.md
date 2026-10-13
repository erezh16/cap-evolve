# AppWorld smoke test: cap-evolve (hill-climb) vs ALTK-Evolve

Status: PLAN, written 2026-10-12; decisions D1 to D4 recorded 2026-10-13 (section 2). Nothing in
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
| optimizer model, both methods | `aws/claude-sonnet-5`, through the gateway in `~/.claude/settings.json`. The requested `aws/claude-sonnet-5-5` is refused by the gateway for this team (decision D1) |
| agent under test, both methods | `openai/gpt-oss-120b-a100` on RITS, reasoning effort `medium`, temperature 0 |
| benchmark | AppWorld. Optimize on `train` (90 tasks) and `dev` (57), report on `test_normal` (168). `test_challenge` is not used |
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
| optimizer gateway (`ANTHROPIC_BASE_URL` in settings.json) | the `x-context-guru-token` header is required (401 without it). `aws/claude-opus-5-5` and `aws/claude-sonnet-5` return 200. **`aws/claude-sonnet-5-5` returns 403 "team not allowed to access model"**, and so do `claude-sonnet-5-5` and `aws/us.claude-sonnet-5-5` |
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
- cap-evolve hill-climb: the baseline scores the seed on val and train. Each iteration copies
  the current best's **val** trajectories into the optimizer workdir, evaluates the child on val
  and applies the paired gate (accept iff mean per-task Δ > `gate_k_se` · SE). Train is scored
  only at the baseline and at the end-of-run bookend. **With `test: []` in `split_ids_file`,
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
| **D1** | The optimizer model `aws/claude-sonnet-5-5` is refused by the gateway for this team (403) | (a) you grant this team access to `aws/claude-sonnet-5-5`, or supply a credential that has it; (b) use `aws/claude-sonnet-5` (accessible, previous Sonnet); (c) use `aws/claude-opus-5-5` (accessible, stronger and costlier) | (a) if it can be done today, otherwise (b). The model is one variable, `OPT_MODEL`, used by both methods, so the choice cannot favour one side. Whatever is used is recorded in the results | **(b) `aws/claude-sonnet-5`.** The recommendation was (a) if it could be done today, otherwise (b). On 2026-10-13 `aws/claude-sonnet-5-5` still returned 403 and `aws/claude-sonnet-5` returned 200, so (b) applies to both methods |
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

- `OPT_MODEL=aws/claude-sonnet-5` (decision D1; `aws/claude-sonnet-5-5` is refused by the gateway).
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

- `tasks(split)`: `train` gives the 90 train ids, `val` gives the 57 dev ids, `test` gives `[]`.
  A seal refuses any id outside train or dev unless `AW_ALLOW_SEALED=final-eval-only` is set
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
split_ids_file: split_ids.json        # {"train": 90 train ids, "val": 57 dev ids, "test": []}
num_trials: 1
gate_mode: paired
gate_k_se: 1.0
max_iterations: 6
stall: 0
max_metric_calls: 500                 # 147 baseline + 6 x 57
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

1. **Trajectories.** The seed's 90 train rollouts are reused from the cape-hc baseline
   (`runs/cape_hc_s0/rollouts/train/*__seed__t0.json`). It is the same seed, the same harness
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

Counted rollouts are reported beside every result: 90 (shared train seed) + 114 dev. ALTK-Evolve
needs no more natively. Budgets are therefore not matched; section 13 says so.

---

## 9. Splits, feedback and isolation

| role | split | who reads it |
|---|---|---|
| optimization signal | `train` (90): cap-evolve baseline bookend, ALTK mining | both, at search time |
| selection | `dev` (57): cape-hc proposer trajectories **and** its gate; altk dose choice | both, at search time |
| held out | `test_normal` (168) | nobody until the final window |

Note the asymmetry, inherent to the two methods: cap-evolve's proposer learns from dev
trajectories and is gated on dev, while ALTK learns from train and only selects on dev. Both
use train ∪ dev and nothing else. Dev scores are search diagnostics, never results.

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
| A1 | `aws/claude-sonnet-5` answers through the claude CLI and through the ALTK litellm wrapper |
| A2 | RITS through the patched client: 1 dev episode completes; the RITS key appears nowhere under `/tmp/aw_eval/runs` |
| A3 | REPL isolation (section 9) and `root_opt` contains no test id |
| A4 | injection: on 1 dev task, the seed prompt is byte-identical to the stock agent's first request; a playbook block appears in the right place; the helper and notes setup works and leaves `show_api_doc`'s original text unchanged; a lint-violating helper is rejected without a rollout |
| A5 | scoring: a scripted correct solution (a train task's released solution, run through `world.execute`) gives reward 1; a no-op gives 0; the persisted metadata has no `trace`; `score` twice is identical |
| A6 | `cap-evolve check` is `{"ok": true}`; a 1-iteration dry run on 4 dev tasks with `optimizer_skill: mock` completes |
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
  wrapper log); counted rollouts per method; dev score of each champion; wall time.
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
| 3 search seeds, N* matched budget (B = 900) | 1 seed; cape-hc ≤ 500 counted rollouts, altk native (~204) | smoke scale; counts are reported beside the scores |
| final n = 3 per arm, seed n = 10, seed-check, template panel, drift blocks | n = 2 for all three arms, one interleaved window | smoke scale (D3) |
| Holm families F1–F6, TOST 0.10, pipeline-level t(2) | unadjusted paired cluster-bootstrap CIs, artifact level only | 1 seed and 3 arms |
| `appworld==0.1.3.post1` + head ReAct agent | core + agents from source at `42b5bcf`, pydantic 2.12.x | the pin is not installable (section 1.1, D2) |
| `max_completion_tokens` 8000 | 6000 + history trimming (`max_output_length` 60000) | RITS window is 40,144 tokens |
| separate OS user, containers, closed egress, proposer sandbox | separate data roots, adapter seal, REPL guards, transcript scan | host constraints; disclosed |
| surfaces T (helpers + notes) and M (playbook) for CapEvolve | cape-hc edits P + T; M is used only by altk | scope 2.5 ("tools and prompts") |
| optimizer Sonnet 5.5 (`aws/claude-sonnet-5-5`) | `aws/claude-sonnet-5` for both methods (D1) | the gateway refuses Sonnet 5.5 for this team; the results comment states this |

---

## 14. Budget and timeline (projections)

| phase | rollouts | wall time (estimate) |
|---|---|---|
| build + acceptance checks | ≈ 30 | 2–3 h of build work |
| cape-hc baseline (train 90 + dev 57) | 147 | 0.5 h |
| cape-hc 6 iterations (optimizer 15–40 min + 57 dev rollouts each) | 342 | 3–5 h |
| altk mining (≈ 500–800 optimizer calls) + 2 doses on dev, in parallel with cape-hc | 114 | 1.5–2 h |
| final window | 1,008 | 2–3 h |
| analysis, report, post | 0 | 0.5 h |
| **total** | **≈ 1,640** | **≈ 8–12 h** after the build |

Throughput basis: the probe's 30–300 s per episode, and RITS at 48 concurrent requests without
errors. RITS has no budget. Optimizer spend: cap-evolve capped at $120 by `max_optimizer_usd`;
ALTK about 4–6M input and 0.5–1M output tokens. Both are recorded exactly.

## 15. Risks

| risk | mitigation |
|---|---|
| optimizer gateway fails or throttles mid-run | A1 before launch; cap-evolve `--resume`; the ALTK store is idempotent per trajectory |
| context window overflow on long episodes | `max_output_length` trimming, A8, the `context_exceeded` count per arm; the altk memory block is size-capped |
| RITS throttling or outage during the final window | infrastructure retries with new seeds; one window, so all arms are hit equally; a pause/resume flag in the final runner |
| cape-hc accepts nothing (inert) | that is a result: reported as "no candidate cleared the gate", with the per-iteration dev deltas |
| gpt-oss output format (code block missing, or `complete_task` called at step 1) | that is seed behaviour; both methods may address it (prompt, or guidelines); counted per arm |
| ALTK extraction errors on unusual trajectories | the library already logs and skips (`Standard guideline generation failed …`); the number of skipped trajectories is reported |
| sub-agent stops mid-trial | trials are detached processes with on-disk state (`cap-evolve run --resume`; the ALTK store is idempotent per trajectory id) |
