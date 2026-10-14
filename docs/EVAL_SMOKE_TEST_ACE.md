# AppWorld smoke test: ACE vs the seed agent

Status: PLAN, written 2026-10-14; decisions D5 to D7 and the review feedback recorded the same day
(sections 2 and 16). Nothing in sections 4 to 12 has run yet. Decisions D1 to D3 carry over from
the base plan; D4 is fixed by the design. Live progress is in
[`EVAL_SMOKE_TEST_ACE_STATUS.md`](EVAL_SMOKE_TEST_ACE_STATUS.md).

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
| limits | memory cap `M_cap` = min(30,000 tokens (design), what fits the RITS window (base §0/§13)) ≈ 13.5K tokens; optimizer ≤ 10M non-cache-read tokens and ≤ 900 counted rollouts per search (#804); 6,000 completion tokens per step, 50 steps, 30-minute wall cap per episode (base plan) |
| resumability | every checkpoint appends an entry to `docs/EVAL_SMOKE_TEST_ACE_STATUS.md`, committed and pushed together with the continuation state `docs/EVAL_SMOKE_TEST_ACE_STATE/` to `origin erezh-eval2-ace`; results checkpointed at once (coalesced to ≤ 1 per 5 min), heartbeat if 25 min pass without one; one command resumes from the last entry (section 10) |

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
  characters, 318 bullets, about 29K tokens**: about twice the memory cap of this plan (about 13.5K
  tokens, section 6.2), and close to gpt-oss-120b's whole 40,144-token window.
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
| F3 official gpt-oss config differs | kept as in base §5.1 and listed in section 13.2 |
| F4 setup snippet is a REPL interaction | neither arm has helpers or notes, so no snippet runs; both prompts are stock up to the memory slot |
| F5 structured-output path fails on the gateway | ACE uses text responses parsed as JSON (`extract_json_from_text`), so no `response_format`/`tool_choice` is sent; A1 checks it |
| F10 the seed is nearly deterministic at temperature 0 | D3 kept (2 trials); the within-task agreement between the 2 trials is reported (section 12) |
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
| **D5** | The ACE playbook grows without bound (official run: 117,794 characters); the memory cap is `M_cap` tokens (section 6.2; planning value about 13,000), and the Generator must run with the playbook in its 40K context *during* adaptation | (a) **lazy grow-and-refine at the cap**: when an ADD would push the playbook over `M_cap`, run ACE's own `BulletpointAnalyzer` (threshold 0.90, `all-mpnet-base-v2`, LLM merge with `OPT_MODEL`) once; if it is still over, drop that step's ADDs (logged as `cap_drop`) and keep adapting; (b) the same without dedup: drop ADDs at the cap; (c) let it grow, then take the last per-task snapshot ≤ `M_cap` as the artifact; (d) let it grow, with no cap (the Generator overflows; the final artifact fails the lint) | **(a)**. It is the mechanism the paper describes ("lazily, when the context window is exceeded", appendix "Pruning Trigger"), it uses ACE's released code, it keeps every Generator episode inside the context budget, and the rule depends only on token counts, never on scores. (c) wastes the later adaptation steps; (d) repeats F11 | **(a)**, user 2026-10-14 |
| **D6** | Adaptation set | (a) official `train` (90), dev only as a diagnostic; (b) `train ∪ dev` (147), in the spirit of base rule S2 | **(a)**. It is the official ACE config, the paper's "90 adaptation queries", the design's A-ACE, and the same as the altk arm (mine train). Rule S2 was written for cap-evolve's gate, which does not exist here | **(a)**, user 2026-10-14 |
| **D7** | ACE batch size | (a) 1, sequential (paper, official config); (b) 4 (design: "only if wall-clock requires it") | **(a)**. About 4 to 6 h (revised to 5–7 h in section 14) fits the smoke budget. At HEAD, batch > 1 also turns on augmented shuffling × 2 and parallel curation, which is a different algorithm | **(a)**, user 2026-10-14 |

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

The first run's state under `/tmp` was lost between sessions (section 1.1). Free space is no
longer the constraint the base plan worked around (one 1.5 TB volume, 535 GB free), so this plan
keeps everything that is costly to rebuild on `/workspace`, and pushes what is needed to continue
(section 10.3):
- **pushed state**, in git on branch `erezh-eval2-ace`: the ledger
  `docs/EVAL_SMOKE_TEST_ACE_STATUS.md`, the state folder `docs/EVAL_SMOKE_TEST_ACE_STATE/`, and the
  code `examples/appworld/`;
- **durable local state**, outside git: `AW_HOME=/workspace/aw_eval_ace/` with `state/` (detail
  records that may not be published) and `build/` (clones, venv, data roots, model cache);
- **scratch** on `/tmp/aw_eval_ace/`: AppWorld's native per-episode output dirs only.

```
/workspace/worktrees/base/                   # the repo, branch erezh-eval2-ace (pushed at every checkpoint)
  docs/EVAL_SMOKE_TEST_ACE_STATUS.md         # THE LEDGER (section 10.2)
  docs/EVAL_SMOKE_TEST_ACE_STATE/            # pushed continuation state (section 10.3)
    manifest.json                            # commits, patch sha256, data / split-file / venv-freeze hashes, order seeds and order-file sha256, M_cap
    ace/playbook.txt                         # the current ACE playbook (lint-checked; overwritten each step; git history keeps every snapshot)
    ace/progress.json                        # last applied step, next_global_id, one summary row per step, spend, per-step isolation-scan counts
    dev/cells.csv                            # one row per finished dev-diagnostic cell: order index, arm, reward, steps, tokens, termination, infra flag (no task ids)
    final/progress.json                      # final window: counts only (cells done per arm, infra retries); no per-cell outcome
    final/artifacts/ace/memory/playbook.md   # the frozen artifact; analysis.json (aggregates), RESULTS.md (draft) at the end
  examples/appworld/                         # the code (section 4.1)
/workspace/aw_eval_ace/                      # AW_HOME (durable, outside git, never pushed)
  state/                                     # AW_STATE
    RUNNING.pid                              # the live phase runner (resume lock)
    records/<phase>/<unit>.json              # one gold-free record per unit of work (episode, ACE step, check); hold task ids
    ace/steps/<iii>/{episode,messages,reflector,curator,apply}.json   # hold trajectories and task text
    ace/playbooks/pb_<iii>.txt               # local copy of every playbook snapshot (000 = initial)
    ace/llm_calls.jsonl                      # every Reflector / Curator / merge call: prompt, response, tokens
    final/order.json, final/records/         # the window order and per-cell records (hold test ids and per-task outcomes)
    final/artifacts/<arm>/                   # frozen artifacts of both arms
    progress/                                # one progress log per trial + PROGRESS.md
  build/                                     # AW_BUILD (rebuildable from manifest.json, kept to avoid redoing it)
    appworld/                                # git clone StonyBrookNLP/appworld @ 42b5bcf3cd334fee33f0c37c02070a9f5807add5 (+ git lfs pull, + our patch)
    ace-src/{ace,ace-appworld}/              # clones at the D4 pins, read-only (vendoring source)
    venv-aw/                                 # uv venv, CPython 3.11 (section 4, B2)
    root_full/                               # APPWORLD_ROOT with all splits; final window only; chmod 000 during search
    root_opt/                                # APPWORLD_ROOT for search: api_docs, base_dbs, tasks/<train+dev ids>, datasets/{train,dev}.txt
    hf/                                      # HF_HOME (all-mpnet-base-v2)
/tmp/aw_eval_ace/aw_outputs/                 # AppWorld native per-episode output dirs, deleted after each record is written
```

Build steps (each one checkpoint, each idempotent, each under 30 minutes):
- **B1.** In `AW_BUILD`: `git clone`, `git checkout 42b5bcf3…`, `git lfs install --local && git lfs
  pull`, apply `examples/appworld/patches/appworld-extra-headers.patch` (section 5.2), record `git
  diff` and its sha256 in `manifest.json`.
- **B2. uv and the venv.** If `~/.local/bin/uv` is missing, install it
  (`curl -LsSf https://astral.sh/uv/0.13.0/install.sh | sh`, the version the first smoke test used),
  and record `uv --version`. If no CPython 3.11 is found, `uv python install 3.11`. Then
  `uv venv -p 3.11 $AW_BUILD/venv-aw`, and with `uv pip install -p $AW_BUILD/venv-aw`: first `torch`
  from `--index-url https://download.pytorch.org/whl/cpu` (CPU wheels only), then `-e appworld -e
  "appworld/experiments[simplified]" "pydantic>=2.12,<2.13"`, `-e /workspace/worktrees/base/core`
  (the `Rollout` type of the shared adapter; cap-evolve itself is not run), `sentence-transformers
  faiss-cpu`. Then `appworld install --repo` with the venv's `appworld`. Record `uv pip freeze` and
  its sha256. The venv is outside git and outside `/tmp`, so a session restart does not lose it.
- **B3.** `appworld download data --root root_full`. Check split counts (90 / 57 / 168 / 417),
  scenario counts (30 / 19 / 56 / 139) and difficulty counts (levels 1/2/3: train 36/36/18, dev
  30/24/3, test_normal 57/48/63, test_challenge 72/150/195; design §2), as base §4 step 3 does; stop
  on any mismatch. Record the data tree sha256.
- **B4.** `examples/appworld/scripts/make_roots.py` builds `root_opt` (train + dev ids and
  `_base_`); `grep` finds none of the 585 test ids under it. `chmod 000 root_full`.
- **B5.** Clone `ace` and `ace-appworld` at the D4 pins into `ace-src/`; vendor the files of
  section 8.1 into `examples/appworld/ace/vendor/` with a `VENDORED.md` that lists source path,
  commit and sha256 of each file. Pre-fetch `all-mpnet-base-v2` into `HF_HOME`.
- **B6.** Write the code of section 4.1, and commit it after each file group passes its unit check.
  The commits go to branch `erezh-eval2-ace` and are pushed with the next checkpoint (section 10.2).
- **B7.** The user puts `.env` (`RITS_URL`, `RITS_API_KET`) in the worktree if it is missing. It
  is git-ignored and is never copied into `AW_HOME` or the pushed state.

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
  temperature=0, max_tokens=4096)`, the header read from `ANTHROPIC_CUSTOM_HEADERS`. No
  `response_format`, no tools. Retries: 50, 10 s apart (ACE's config). No cache. `max_tokens` 4096 is
  ACE's default (`ace/` CLI `--max_tokens`; the AppWorld configs set none). The count of responses cut
  at the limit is reported.
- Every call is appended to `AW_STATE/ace/llm_calls.jsonl`: role, step, prompt sha256, full prompt
  and response text, input and output tokens, latency, error. The prompt text is kept so that the
  isolation scan (section 9) can read exactly what the optimizer saw.
- Optimizer cap, from #804 and design §7: **10M non-cache-read tokens (input + output) per search,
  soft 8.5M**. Reflector, Curator and merge calls all count. At 8.5M a `cap_spend` checkpoint (soft)
  is written and the run continues. At 10M the loop stops after the current step and a `cap_spend`
  checkpoint (hard) is written. As in the design, a guard stop is a budget termination: the artifact
  is the playbook at the stop, and the stop is disclosed. Spend is also shown in USD at proxy list
  prices ($2 / $10 per Mtok input / output), labelled "proxy". The cumulative count is kept in the
  pushed `ace/progress.json`, so the cap survives restarts and the loss of `AW_STATE`.
- Counted-rollout cap, from the same post: B = 900 per search. ACE's native count (90 adaptation
  episodes; 57 dev diagnostic) is far below it, so it never binds; it is checked anyway.

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

Lints, as in the base plan. Here only the memory block varies. Its cap, `M_cap`, follows the design
(#804; design §4.4: the M surface holds at most 30,000 tokens) within the scope limits of
the base plan (§0 and §13: gpt-oss-120b on RITS, a 40,144-token window, 6,000 completion tokens,
history trimmed at 60,000 characters):

```
M_cap = min(30,000, 34,000 − P_max − H_max) tokens, rounded down to a multiple of 500
```

- 34,000 is the base plan's prompt limit (A8), 40,144 − 6,000 rounded down.
- `P_max` is the largest stock prompt over train ∪ dev, rendered with the task block and the
  memory heading but no playbook. It is measured once over all 147 tasks (prompt only, no model
  call). Planning value about 3.5K tokens.
- `H_max` is the token count of 60,000 characters of agent history at the lowest characters-per-token
  ratio seen in A8's 10 dev episodes. Planning value about 17K tokens.
- Tokens are counted with gpt-oss's encoding (tiktoken `o200k_harmony`), cross-checked in A8 against
  vLLM's reported `prompt_tokens`.

Planning value: `M_cap` ≈ 13,500 tokens (34,000 − 3,500 − 17,000; about 50,000 characters). The
design's 30,000 tokens does not fit the RITS window, so the scope limit binds. With this cap the
playbook cannot push an episode over the window for any history up to the trimming limit, *as long
as* the prompt is no longer than `P_max` and the history is no denser than measured. Test prompts
cannot be measured before the window (the seal), so an episode can still overflow. Such an episode
is `context_exceeded`, scored 0 and counted per arm (base §5.1). `M_cap` is fixed in P2 (A8), before any
counted rollout, and recorded in `manifest.json` and in a `decision` checkpoint. It is checked at
every playbook write during adaptation (section 8.4) and again at freeze. A playbook over the cap is
never used for a rollout.

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
  `infra_error`. It is never scored as a failure. It is retried once in search and up to 3 times in
  the final window, **with new trial seeds** (base §15, design §8.5): attempt *a* uses
  `random_seed` + 1000·*a*.
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
P3 (its sha256 goes into the P3 checkpoint, the ids do not). Playbook state `pb_000` = the initial playbook, `next_global_id` from
`get_next_global_id`. For training task *i* = 1 … 90, four sub-steps, each persisted before the
next starts:

1. **episode**: one common-harness episode with `memory/playbook.md = pb_{i-1}` (root_opt, trial
   seed 100). Writes `ace/steps/<iii>/episode.json` (the record of section 7) and `messages.json`.
   This is a counted rollout. On `infra_error` it is retried once with a new trial seed (section 7);
   if it fails again, the step is recorded as `skipped_infra` and the playbook is carried forward unchanged.
2. **reflector**: the no-GT reflector prompt filled with `pb_{i-1}` and the message list. The test
   report, the outcome and any gold are not sent (section 1.3). Writes `reflector.json` (response
   text, tokens).
3. **curator**: the curator prompt with the instruction, `pb_{i-1}`, the reflection and the
   message list. Writes `curator.json` (raw response, parsed operations or the parse error).
4. **apply**: per-bullet filter (section 8.3), then `apply_curator_operations`, then the size rule
   (section 8.4). Writes `ace/playbooks/pb_<iii>.txt` and `apply.json` (ops proposed / applied / `lint_drop` /
   `cap_drop`, dedup run or not, tokens, characters, bullets, sha256). It also scans this step's
   Reflector and Curator inputs and outputs for the isolation patterns of section 9. Then the
   checkpoint for step *i* copies `pb_<i>` to the pushed `ace/playbook.txt`, adds the step's row to
   `ace/progress.json`, and appends the ledger entry, all in one commit.

A resumed run reuses every sub-step file that exists and verifies, so no paid call is repeated
and the trajectory a reflection was made from never changes (section 10.4).

### 8.3 Per-bullet lint

The design's M surface rule (design §4.4) forbids verbatim train or dev instruction n-grams in the
playbook, and its anti-memorization lint (design §5.4) also forbids task ids. With the base plan's
n-gram size (8, base §6.2), the rule is: no 8-gram from any train or dev instruction and no task id.
It also checks for supervisor names, emails and phone numbers from any train or dev task (base
§6.2's prompt rule), for a stated reason. ACE's Curator sees the instruction and the prompt's `My
name is: …` block verbatim, and the playbook is now pushed and published at every checkpoint (user
items 3 and 4), so it must hold no task data (AppWorld's redistribution rule, base §12).

The rule is applied **per bullet**, before the `ADD` is applied, for a stated reason: ACE has no
candidate to reject. Rejecting the whole playbook, as the base plan does with a candidate, would
discard the arm, and a playbook with a violating bullet could not be pushed. A violating bullet is
dropped and logged (`lint_drop`, with the rule), and the rest of the step's operations are applied.
Bullets written by the dedup merge (section 8.4) are new text, so they are linted the same way
before they enter the playbook.

### 8.4 Size rule (D5 (a))

After the per-bullet filter, if `tokens(pb_{i-1} + ADDs) > M_cap`:
1. run `BulletpointAnalyzer.analyze(threshold=0.90, merge=True)` on the playbook *with* the new
   bullets, with merges made by `OPT_MODEL` through `ace_llm.py` (role `merge`, logged and metered).
   Each merged bullet is linted (section 8.3). A merged bullet that fails is dropped
   (`lint_drop`);
2. if the result is ≤ `M_cap` tokens, it becomes `pb_<i>`;
3. otherwise the step's ADDs are dropped (`cap_drop`), `pb_<i> = pb_{i-1}`, and adaptation goes on
   (later steps may still add once a dedup has made room).

The rule reads token counts only. The number of dedup runs, merged bullets and `cap_drop`
bullets is reported.

### 8.5 Freeze and the dev diagnostic

- Freeze: the ACE artifact is `pb_090` (or, after a guard stop of the optimizer cap, the playbook at
  the stop; this is disclosed). Lint, render into `final/artifacts/ace/memory/playbook.md`, record
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
- After the search (base §9: "after both searches"; here, after ACE adaptation), `scan_isolation.py` greps
  `llm_calls.jsonl`, every `ace/steps/*` file and every playbook for the 585 test ids, `test_normal`,
  `root_full`, `answer.json` and `ground_truth` (F16: the canary is release-wide, so
  it is reported but not used as the test signal). The same patterns are also checked at every ACE step (section 8.2), so that the scan counts are
  pushed and survive the loss of `llm_calls.jsonl` (user item 3). It also counts `fs_probe` hits per arm,
  over adaptation, the dev diagnostic and the final window. A hit
  is reported, and the arm is labelled "isolation breach".

---

## 10. Orchestration, progress log, checkpoint ledger and resume

The long work runs as detached `nohup` processes that write their own logs and records (A.4).
The main session, or at most 2 sub-agents (`ace`: adaptation → freeze → dev diagnostic; `final`:
final window → analysis), starts and watches them. Nothing depends on a sub-agent or the main
session staying alive: **the last entry of `docs/EVAL_SMOKE_TEST_ACE_STATUS.md` says where the run
is and what comes next, and `AW_STATE` holds the detail behind it.**

Phases (the ids used in the ledger), each with its resume rule (section 10.4):

| phase | what | done when | resume rule |
|---|---|---|---|
| P0 | decisions | all decisions recorded | — |
| P1 | build B1–B7 | each B step's check passes | first unfinished B step |
| P2 | acceptance A1–A10 | each check passes | first unfinished check |
| P3 | ACE start: train order (sha256), `pb_000`, `M_cap` | checkpoint written | redo (seconds) |
| P4 | ACE adaptation, 90 steps × 4 sub-steps | step 90 applied, or guard stop | first missing sub-step |
| P5 | freeze (lint, hash) | artifact hashes recorded | redo (seconds) |
| P6 | dev diagnostic, 114 cells | all cells done | skip done cells |
| P7 | isolation scan | scan counts recorded | redo (minutes) |
| P8 | final window, 672 cells | all cells done | skip done cells (local records) |
| P9 | analysis | `analysis.json` recorded | redo (minutes) |
| P10 | report, post | `posted` entry | never post twice |

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
- To watch: `watch -n 60 cat /workspace/aw_eval_ace/state/progress/PROGRESS.md`, or the last entry of the
  ledger on GitHub.

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

Since CP-0041: ACE step 041 done (+3 bullets, 1 lint_drop, 0 cap_drop); 1 counted rollout.
Totals: rollouts counted 41 (ace 41, seed 0); playbook 63 bullets, 21,480 chars; optimizer 2.31M in / 0.19M out tok, $6.50 proxy.
Runner: alive (pid 81234), last log `step 41/90 +3 bullets (1 lint_drop) pb=21,480 chars`.
Next: P4 ace/step/042 episode.

```json
{"cp": 42, "prev_cp": 41, "prev_commit": "<sha>", "utc": "2026-10-15T03:12:09Z",
 "kind": "result", "phase": "P4", "done_through": "ace/step/041/apply",
 "next": "ace/step/042/episode", "counts": {...}, "spend": {...},
 "artifacts": {"STATE/ace/playbook.txt": "<sha256>", "local/ace/playbooks/pb_041.txt": "<sha256>", "...": "..."},
 "code": "<git sha of examples/appworld>", "open_decisions": []}
```
````

  The prose lines are for people; the fenced `json` block is what `resume.py` parses. Its
  `artifacts` map names pushed files (`STATE/…`) and local files in `AW_STATE` (`local/…`) by sha256
  (sections 10.3, 10.4).
- `kind` is one of `phase_start`, `result`, `phase_done`, `heartbeat`, `decision` (user decisions,
  verbatim), `abort`, `resume`, `restore`, `rebuild`, `repair`, `error`, `cap_spend`, `posted`.

**Content rules (everything pushed is published).** For the ledger and every file in
`docs/EVAL_SMOKE_TEST_ACE_STATE/`: no secret or key, no gold value or solution, **no task id**, no
task instruction or supervisor detail from any split, no trajectory text, no Reflector or Curator
text, and **no per-task test outcome** (per-task test rewards are for the statistics only, design
§5.2 item 9; with the public split files any per-cell list could be mapped back to task ids). Units
are named by phase and index (`ace/step/041`, `final 312/672 cells`), never by task id.
The one piece of learned text that is pushed is the ACE playbook (`ace/playbook.txt`). Each of its
bullets has passed the per-bullet lint (section 8.3), and the user accepted publishing it
(2026-10-14). Final-window entries carry counts and progress only until P9, when the aggregate
results (the main table of section 12) are added. Before every commit, `scripts/status_doc.py`
checks all staged pushed files, and refuses the checkpoint if any contains one of the 732 task ids,
a string from `.env`, a train or dev instruction 8-gram, or a supervisor name, email or phone. A
refusal is logged locally and stops the runner.

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
1. Update the pushed state files the checkpoint reports (section 10.3), each written atomically;
   then append the entry to the ledger, `fsync`.
2. `git commit -m "status: CP-0042 P4 ace/step/041" -- docs/EVAL_SMOKE_TEST_ACE_STATUS.md
   docs/EVAL_SMOKE_TEST_ACE_STATE/ examples/appworld/`. The pathspec commits only these paths, never
   other work in the tree. The ledger entry and the state it describes are always in the same commit.
3. `git push origin erezh-eval2-ace`. Never `--force`. If the push fails (network, auth), the commit
   stays local, the failure is noted in the next entry, and the next checkpoint pushes both. If the
   push is rejected as non-fast-forward (someone else pushed to the branch), the writer stops pushing,
   keeps committing locally, and the next status check asks the user.

Code changes (B6, or a fix during the run) are committed under the same pathspec and pushed with the
next checkpoint. The entry records the code sha.

### 10.3 What is pushed, what stays local

The aim is that a resume redoes as little as possible, **even if this host is lost entirely**.
Everything a later phase needs, and that may be published, is pushed with every checkpoint.

| item | where | why it can or cannot be pushed |
|---|---|---|
| ledger | `docs/EVAL_SMOKE_TEST_ACE_STATUS.md` | the state and the resume point |
| manifest: commits, patch, data / split-file / venv hashes, `M_cap`, the order seeds and order-file sha256 | `…_STATE/manifest.json` | hashes and numbers only. The window orders are **regenerated** from the seed and `load_task_ids`, and checked against the sha256, so no id is pushed |
| current ACE playbook `pb_<i>` | `…_STATE/ace/playbook.txt` (git history holds every `pb_<i>`) | lint-checked generic guidance |
| ACE progress: last applied step, `next_global_id`, one row per step (episode success, steps, tokens, ops proposed / applied / `lint_drop` / `cap_drop`, dedup, playbook tokens), optimizer tokens per role, per-step isolation-scan counts | `…_STATE/ace/progress.json` | counts only; a step is named by its index in the official train order |
| dev-diagnostic cells: order index, arm, reward, steps, tokens, termination, infra flag and retries | `…_STATE/dev/cells.csv` | dev is a tuning split; no ids; joined to ids only locally, by regenerating the order |
| final window: counts only (cells done per arm, infra retries) | `…_STATE/final/progress.json` | per-cell test outcomes are **not** pushed (content rules, section 10.2) |
| frozen artifact, `analysis.json`, `RESULTS.md` draft | `…_STATE/final/` | contain no ids or task text |
| code | `examples/appworld/` | — |
| episode records, `messages.json`, Reflector and Curator text, `llm_calls.jsonl`, `order.json`, final-window per-cell records | `AW_STATE` only | contain task ids, task text, trajectories or per-task test outcomes |
| clones, venv, data roots, model cache | `AW_BUILD` only | rebuildable from `manifest.json` (B1–B5) |

Local records are written to a temp file, `fsync`ed and renamed (atomic) **before** the checkpoint
that reports them. A unit is done if its local record exists and verifies, or if its pushed row
exists.

**Worst-case redo after an abort**:
- **host intact**: the in-flight episodes (at most 30 minutes each, re-run from scratch with the same
  seed), at most one in-flight optimizer call, and the build or analysis step in progress
  (idempotent, at most 30 minutes);
- **host lost** (`/workspace` gone): additionally the build (B1–B5, about 1–2 h), the dev cells
  finished since the last coalesced checkpoint (at most 5 minutes), in P4 the one ACE step in
  progress, and in P8 the **whole final window** (up to 2 h). The final window is re-run from cell 1
  with the same order and seeds. This is the one place where "minimize redo" (user item 3) gives way
  to the content rules. The isolation scan of earlier steps is not lost: it is done per step and its counts
  are pushed.

### 10.4 Resume

One command: `python3 -I examples/appworld/scripts/resume.py` (with `--dry-run` to only print the
plan). It works the same after a crash, a kill, a host restart or a new Claude session.

1. **Read the ledger.** `git fetch origin erezh-eval2-ace`. If the local branch is missing or behind,
   use `origin/erezh-eval2-ace` (fast-forward only). If local has unpushed checkpoint commits, push them
   first. Parse the `json` block of the last entry. If the last entry is torn (crash mid-append,
   uncommitted), drop the uncommitted tail with `git checkout -- docs/EVAL_SMOKE_TEST_ACE_STATUS.md`;
   the records it would have reported are adopted in step 4.
2. **Lock**: refuse if `RUNNING.pid` names a live runner (no double runs). Stale pid files are removed.
3. **Environment**: compare `manifest.json` with `AW_BUILD`. A missing or mismatched clone, venv or
   data root is rebuilt by re-running its B step (idempotent; B2 reinstalls uv if needed), checked
   against the recorded sha256. If a
   rebuilt hash differs (e.g. upstream data changed), stop and ask the user. Re-apply
   `chmod 000 root_full` if the phase is before P8.
4. **Reconcile local state with the pushed state.** Verify the pushed files against the hashes in the
   last entry. Local records that verify but are newer than the last entry are adopted and reported in
   the `resume` entry. Temp files without a rename are deleted. If `AW_STATE` is missing, it is
   re-created from the pushed state: `pb_<i>` from `ace/playbook.txt`, `next_global_id` and spend from
   `ace/progress.json`, the window orders regenerated from their seeds and checked against their
   sha256, and finished dev cells from `dev/cells.csv`. This is logged as `restore`. A hash mismatch between
   the ledger and the pushed files stops the resume and asks the user.
5. **Continue** at the `next` unit:
   - P1/P2: re-run the first unfinished B or A step.
   - P4: load `pb_<last apply>` and `next_global_id`, and start at the first missing sub-step of step
     *last apply* + 1. An existing local `episode.json` is never re-run, and an existing
     `reflector.json` or `curator.json` is never re-requested. If they were lost with the host, that
     one step is redone from its episode.
   - P6: skip every cell with a done local record or a pushed row. P8: skip every cell with a done
     local record (if the records were lost with the host, the window restarts from cell 1). Run the
     rest in the recorded order with the recorded seeds.
   - P3, P5, P7, P9: redo (each takes seconds to minutes and is idempotent). Infrastructure retries count from the records, so a resume does not reset them.
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
| A2 | RITS, as the probes of base §1.1: the model listing shows `max_model_len` = 40,144 (stop if it differs; `M_cap` depends on it); 48 concurrent short requests return 200 with no 429; through the patched client, 1 dev episode completes; the RITS key appears nowhere under `AW_HOME`, `/tmp/aw_eval_ace` or the pushed files |
| A3 | REPL isolation with F1's hardening (`import os`, `open(answer.json)`, a `pathlib` read all fail); `root_opt` has no test id; `root_full` is unreadable during search |
| A4 | injection: on 1 dev task the seed's first request is byte-identical to the stock agent's; a playbook appears in the slot before `My name is:`; a playbook of `M_cap` + 1 tokens is refused before any rollout |
| A5 | scoring: a train task's released compiled solution gives reward 1, a no-op 0; the record has no `trace`; scoring twice is identical |
| A6 | split and seal: `tasks("train")` = `train.txt` exactly (90, same order as `load_task_ids`); a test id is refused without `AW_ALLOW_SEALED` |
| A7 | ACE loop on 4 dev tasks into a throwaway state dir (not counted): the ported reflector and curator prompts are byte-identical to ACE's rendering on a fixed message list; ≥ 1 bullet is added with a fresh id in a whitelisted section; a non-`ADD` or off-whitelist operation is skipped as in ACE; a planted bullet with a train 8-gram is `lint_drop`ped; a synthetic playbook of 1.3 × `M_cap` tokens triggers the D5 rule, and its outcome is logged; the gateway's content filter does not blank any Reflector or Curator field on these real prompts (if it does, the field is renamed in our copy of the prompt and recorded, as the design's A-ACE acceptance requires); the playbook's token count is measured. the transcript scan of section 9 over these runs' Reflector and Curator calls finds no test id or ground-truth path. This is the design's A-ACE acceptance and common acceptance (iii) and (iv), on dev ids per rule S1 |
| A8 | context and `M_cap`: 10 dev episodes with no playbook give the characters-per-token ratio of history (lowest one used); `P_max` is measured over the 147 train ∪ dev prompts; `M_cap` is computed (section 6.2) and recorded; then 3 dev episodes with an `M_cap`-token playbook in the slot stay under 34K prompt tokens (vLLM's `prompt_tokens`), and tiktoken's count is within 2% of vLLM's |
| A9 | resume, ACE: run the A7 loop against a **throwaway status file and branch** (`acceptance/status-test`, deleted afterwards) and kill it (SIGKILL) three times, once each after `episode.json`, after `reflector.json` and in the middle of a status append; resume each time; the final playbook equals that of an uninterrupted run from the same stored sub-steps, no paid call is repeated (count in `llm_calls.jsonl`), every entry is a committed, pushed, append-only addition (`git log -p` shows only added lines), and a resume from a fresh clone of the branch **with `AW_STATE` deleted** restores `pb_<i>` and continues at the same `next` unit, redoing only the step in progress |
| A10 | resume and publishing, windows: a 12-cell mini window on dev ids, killed mid-way and resumed: no cell is run twice, all 12 cells are done, the order is the recorded one; cells arriving fast are coalesced into ≤ 1 entry per 5 min (tested with a 1-min setting); a heartbeat entry appears after 25 minutes of silence (tested with 1 min) and marks a killed runner `stalled`; a push failure (bad remote URL) leaves a local commit that the next checkpoint pushes; the content filter refuses an entry that contains a task id or a string from `.env` |

A8 runs before A4 and A7, because they use `M_cap`. None of the acceptance rollouts are counted
(rule S1).

---

## 12. Final window, statistics and the report

- Freeze: `ace` = the artifact of section 8.5; `seed` = the seed capability. Copy each into
  `final/artifacts/<arm>/` and record sha256 tree hashes in a checkpoint.
- Window: 168 test_normal tasks × 2 arms × 2 trials = **672 episodes**, in one random order with a
  recorded seed (order file hashed in the P8 checkpoint), `AW_ALLOW_SEALED=final-eval-only`,
  `APPWORLD_ROOT=root_full` (unlocked at P8 start, logged), 48 workers. Trial seeds are `random_seed`
  5000 + trial. Infrastructure failures are retried up to 3 times with new trial seeds (section 7); a cell that still fails is scored
  0 (primary) and reported as missing (sensitivity).
- Only rewards, counters and infrastructure flags are read from test records. No test trajectory is
  read by a person or an LLM; AppWorld forbids error analysis on test.
- Metrics: TGC (mean over tasks of the mean over trials of success); SGC (a scenario passes in trial k if all 3 of its tasks pass; averaged over k); both
  by difficulty (Easy 57, Medium 48, Hard 63). Paired difference `ace − seed` with a
  scenario-clustered paired bootstrap (56 clusters, 10,000 resamples) 95% CI. One contrast, so no
  multiplicity question; one search seed, so it is an artifact-level statement only.
- Cost table: target tokens per task (prompt and completion), steps per task, step-cap hits,
  `context_exceeded` count; playbook characters, tokens and bullets, memory tokens per step; dedup
  runs, `lint_drop` and `cap_drop` counts; optimizer input and output tokens, calls per role and proxy
  USD (from `llm_calls.jsonl`); counted rollouts per arm; dev diagnostic scores; the share of tasks whose 2
  trials agree, per arm (F10); wall time per phase
  (from the status document).
- Side by side, compared only as gains over each side's own no-memory baseline (design §9.2,
  interpretation rule 1): the colleagues' gpt-oss-120b (no memory 39.9 / 21.4, ReAct + ACE 54.8 /
  35.7) and the ACE paper's (ReAct 54.8 / 33.9, ACE offline no GT 58.3 / 41.1). Their harness,
  template, reflector model and epochs differ (section 13).

Results comment on #804 (markdown): setup block (commits, models, settings, D1–D7 outcomes); the main
table (TGC, SGC, Δ vs seed with CI); the difficulty table; the cost table; what changed (playbook
size, number of bullets by section, 3 example bullets); isolation scan counts;
resume history (number of aborts and resumes, units re-run, from the status document); deviations (section 13)
and what the numbers cannot support (one search seed, one method, no matched budget, no TOST).
A **"What this ACE is and is not"** paragraph, placed directly under the main table, states the
choices that make this ACE differ from the paper's and from the colleagues' runs, and why any of them
could explain the result as well as ACE itself could:
1. the common template (the stock AppWorld prompt with a memory slot), not ACE's 27K-character
   Generator prompt;
2. Sonnet 5.5 as Reflector and Curator, a stronger model than the target (the paper uses the target);
3. 1 epoch and 1 reflection per task (the paper allows up to 5 of each);
4. the `M_cap` size rule (D5), with the number of dedup runs and `cap_drop`s;
5. the no-GT Reflector, which is never told whether a task passed;
6. 50 steps instead of ACE's 40.
The paragraph says plainly that a null or small result is a result about *this configuration*, not
evidence that ACE does not work. No
task text, ids, solutions or gold values are posted (AppWorld redistribution rule). The draft is written to
`final/RESULTS.md` first, then posted with
`gh issue comment 804 -R skillberry-ai/cap-evolve --body-file …` (the `origin` remote, the
`erezh16` fork, has issues disabled), and a `posted` checkpoint records the comment URL.

---

## 13. Deviations, and why

### 13.1 From the base plan

| base plan | here | why |
|---|---|---|
| arms seed, cape-hc, altk | seed, ace | task scope: ACE is the only candidate |
| all state under `/tmp/aw_eval` | pushed state in git, build and detail records on `/workspace`, only AppWorld's native outputs on `/tmp` | `/tmp` was wiped between sessions (section 1.1); continuation with the least redo (user, 2026-10-14) |
| progress log + `PROGRESS.md` | the same, plus the cumulative ledger `docs/EVAL_SMOKE_TEST_ACE_STATUS.md` pushed to `erezh-eval2-ace` at every checkpoint, the heartbeat and `resume.py` | new requirement (section 10) |
| rule S2 (cap-evolve train = val) | not applicable; ACE adapts on train (D6) | no cap-evolve arm |
| memory lint: at most 30,000 characters | at most `M_cap` tokens (≈ 13.5K, about 50,000 characters); the design's no-instruction-n-gram rule and the supervisor-contact check, applied per bullet | cap: the design's M cap within the base scope limits (user, 2026-10-14); n-gram rule: design §4.4; contact check and per-bullet application: section 8.3 |
| final window 1,008 episodes | 672 | 2 arms |
| venv-altk (Python 3.12), `venv-aw` via `python3.11 -m venv` | one uv-managed venv, `venv-aw` (CPython 3.11), uv installed if missing; ACE's vendored modules run in it (`ace-appworld` needs ≥ 3.11) | no ALTK arm; uv was missing on the host (user, 2026-10-14) |
| optimizer via claude CLI + litellm wrapper | litellm client only (`ace_llm.py`) | ACE's optimizer roles are plain LLM calls |
| `optimizer_guard.sh`, claude shim (F14, F15) | not needed | the optimizer has no tools |
| posting `gh issue comment 804` | `gh issue comment 804 -R skillberry-ai/cap-evolve` | the fork has issues disabled (review item 7, accepted) |

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
| design A-ACE: "reflection rounds 5" | 1 | the same design line specifies `ACE_offline_no_GT_adaptation` semantics, and that code has no rounds. In ACE, a "round" means: only after an answer judged *wrong against the label*, reflect, re-run the Generator, check again, up to 5 times (`ace/ace.py`, `max_num_rounds`; `adaptation_agent.py`, `num_retries` in the with-GT path only). In AppWorld that needs the evaluator's verdict on each attempt, which the no-GT Reflector has no slot for, and every round is another full counted episode (up to 450 more). The two parts of the design line cannot both hold, so the stated no-GT semantics win |
| design A-ACE acceptance: "bullets with counters" | bullets with ids, no counters | the AppWorld ACE code has no counters (section 1.3) |
| ACE's own Generator template (27K chars) | stock template + memory slot | design: one template for every arm; template panel not run |
| ACE config `max_steps` 40, `use_cache` true | 50, false | common harness; repeated trials must hit the model |
| ACE playbook unbounded | `M_cap` ≈ 13.5K tokens with D5's rule | gpt-oss's 40K window |
| design M cap 30,000 tokens | `M_cap` = min(30,000, what fits the window) ≈ 13.5K tokens | base scope §0/§13 (RITS window, 6,000 completion tokens); user instruction 2026-10-14 |
| #804: 90-minute wall cap per rollout | 30 minutes, as in the base plan (§7.1) | base rule kept; in the first smoke test it fired once and the retry finished in 206 s (F13); it also bounds the work an abort can lose |
| #804: optimizer cap 10M non-cache-read tokens, B = 900 rollouts per search | the same | — |
| ACE with-GT, online mode, `ace-native` | not run | Tier F2 feedback; out of scope |
| `appworld==0.1.3.post1` + head ReAct agent | source at `42b5bcf`, pydantic 2.12.x | as in the base plan (D2) |
| `max_completion_tokens` 8000 | 6000 + trimming | RITS window |
| official gpt-oss-120b ReAct config: `api_type: responses`, `drop_reasoning_content: false`, `max_output_length: null`, `max_retries` 100 (design §4.1: 100) | base §5.1: chat completions via `hosted_vllm`, `drop_reasoning_content: true`, `max_output_length` 60000, `max_retries` 20 | as in the base plan (F3): what fits RITS's 40K window |
| feedback tier F1 "used by every arm" (design §4.5) | ACE's no-GT Reflector gets the trajectory only (no success flag, no failed requirement texts) | ACE's own no-GT setting (design A-ACE: `ACE_offline_no_GT_adaptation` semantics); giving it F1 would change the method |
| design items the base smoke test also left out: test_challenge window (family F5), E-AW-00 probes and the K = 20 dev null pool, registry and hash-chain registration (§12), the frozen infra classifier, the "no retry credit" sensitivity and the ≥ 95 %-valid-cells rule (§8.5), the 3-h hang rule, the concurrency admission rule, the hourly seed canary, `ground_truth_mode: minimal`, the surface lock | not run, as in the base plan | smoke scale; alignment with the base plan, which omitted them too. `max_cost_per_task` 10 is set but inert (RITS is priced 0, F2) |
| separate OS user, containers, closed egress | data roots, seal, REPL hardening, tool-less optimizer, scan | host constraints; disclosed |

### 13.3 Choices made where neither the user, the base plan nor the design decides

Each one is listed with its reason, so that none is a silent deviation:

| choice | reason |
|---|---|
| ACE's `reflector_call`/`curator_call` logic is ported line for line, not imported; A7 checks the prompts are byte-identical | the module imports ACE's AppWorld fork, which cannot share a venv with the AppWorld build of D2 |
| `ace/core/*` (the finance-task Reflector and Curator) is not used, although the design lists it next to the AppWorld modules | `ace/core` prompts are the FiNER/XBRL ones (with bullet tags and a token budget); ACE's own AppWorld adaptation uses the `ace-appworld` modules and prompts, which are the ones used here |
| `pb_000` is ACE's shipped initial playbook | ACE's own starting point; the design's erratum 8 (`identical_to_own_seed`) anticipates it |
| train order = `load_task_ids("train")`, no shuffle | ACE's config and code |
| a training episode with an infra error is retried once (base rule); if it fails again the step is skipped and the playbook carried forward | ACE has no rule for it; scoring it 0, as the final window does, would feed a broken trajectory to the Reflector |
| Generator seed 100 during adaptation | base §5.1, `random_seed` 100 + trial index, trial 0 |
| training records keep the agent's final message list | it is the Reflector's input in ACE (`trimmed_messages`) |
| Reflector / Curator: temperature 0, 50 retries 10 s apart, `max_tokens` 4096 | ACE's config and CLI default |
| tokens counted with tiktoken `o200k_harmony`, checked against vLLM | needed to apply `M_cap`, which is in tokens |
| isolation patterns also checked per ACE step | user item 3: the counts are pushed and survive the loss of `llm_calls.jsonl` |
| acceptance runs use dev ids although the design's A-ACE check says "after 3 train tasks" | user rule S1: acceptance probes use a few dev ids and are not counted |
| supervisor-contact check and per-bullet application of the memory lint | section 8.3 |
| dev diagnostic (57 + 57 rollouts) | part of D6 (a) as accepted by the user |

---

## 14. Budget and timeline (projections)

| phase | rollouts | wall time (estimate) |
|---|---|---|
| P1 build (everything from scratch) + P2 acceptance | ≈ 40 (not counted) | 3–4 h |
| P3–P4 ACE adaptation: 90 × (episode 0.5–9 min, mean about 3 with the growing playbook; Reflector + Curator about 1–2 min) | 90 | 5–7 h |
| P5 freeze + P6 dev diagnostic (24 workers) + P7 scan | 114 | 0.5 h |
| P8 final window (48 workers) | 672 | 1.5–2 h |
| P9, P10 analysis and report | 0 | 0.5 h |
| **total** | **≈ 916** (204 counted search-time: ace 90 + 57, seed 57; 672 final; ≈ 40 acceptance, not counted) | **≈ 8–10 h** after the build |

Optimizer: per task, the Reflector and the Curator each read about 15–45K tokens: the prompt, the
playbook (up to `M_cap` ≈ 13.5K tokens, sent twice, as the playbook field and inside the
conversation history) and the trajectory. That is about 4–8M input and 0.3–0.5M output tokens for 90
tasks, plus dedup merges, about $12–22 at proxy prices. This is under the 10M-token cap, but late
steps at a full playbook may reach the soft 8.5M (section 15). The ACE paper reports 39.3M input tokens for
its AppWorld adaptation with the target in all three roles, about 8.2M of it Reflector and Curator
(design §10.2). RITS has no budget. All usage is recorded exactly and reported per provider
(RITS for the agent, the gateway for `OPT_MODEL`).

---

## 15. Risks

| risk | mitigation |
|---|---|
| abort, crash, host restart, `/tmp` wiped, host lost | ledger and continuation state pushed at every checkpoint, build and records on `/workspace`, `resume.py` restores from git if needed (section 10) |
| two runners at once after a confused resume | `RUNNING.pid` lock; resume refuses while a runner is alive |
| ledger damage or divergence | append-only entries, one commit per checkpoint, never force-pushed; torn uncommitted tail dropped; non-fast-forward or missing artifact stops and asks |
| a checkpoint publishes something it must not | content rules and the `status_doc.py` filter (task ids, `.env` strings, instruction 8-grams); A10 tests the filter |
| push fails (network, auth) for a long time | checkpoints keep committing locally; `PROGRESS.md` shows "unpushed: N"; the state is then only as durable as `/workspace` until a push succeeds |
| the playbook outgrows the cap early (official rate ≈ 1,300 characters per task → `M_cap` (≈ 50,000 characters) after ≈ 37 tasks) | D5 rule; dedup and `cap_drop` counts reported; if most steps after the cap are `cap_drop`, that is a result about ACE at this context size and is reported as such |
| the optimizer guard (soft 8.5M / hard 10M) is reached before step 90 | the soft mark is checkpointed; a hard stop is a budget termination, disclosed, with the step reached |
| optimizer gateway fails or throttles | A1; 50 retries; a failed step leaves sub-step files, and resume continues from them |
| gateway content filter on some CoT fields (design: noted in earlier suites) | A1 and A7 use the real prompts; if a field is filtered, rename it in our copy of the prompt, log it as a deviation, and re-run A7 before launch |
| Curator returns invalid JSON often | ACE's own behaviour (skip the update) is kept; the invalid-JSON rate is reported |
| context overflow with the playbook in the slot | cap, A8 at the cap, dev diagnostic `context_exceeded` count before the test window |
| RITS throttling or outage in the final window | infra retries with new seeds; one interleaved window, so both arms are hit equally; resume from records |
| gpt-oss output format issues | seed behaviour; counted per arm |
| ACE adds task-specific content | per-bullet lint (section 8.3) |

---

## 16. Review: issues found in this plan, and how they were resolved

Found when the plan was checked on 2026-10-14. The user answered the same day; each item gives the
resolution, and the plan above has been updated to match.

1. **D5, D6 and D7 were open.** *Resolved:* the user accepted the recommendations: D5 (a) lazy dedup at
   the cap and `cap_drop` beyond it; D6 (a) adapt on train; D7 (a) batch size 1 (section 2).
2. **Nothing from the first smoke test is on disk** (`examples/appworld/`, `/tmp/aw_eval`, `.venv`,
   `.env`, `uv`). *Resolved:* B2 installs uv 0.13.0 if it is missing and creates the uv venv `venv-aw`
   (CPython 3.11) on `/workspace`. The build is from scratch (3–4 h). `.env` must still be supplied (B7).
3. **The pushed ledger alone could not restore a mid-run state.** *Resolved:* everything needed to
   continue that may be published is pushed at every checkpoint (section 10.3): the current playbook,
   ACE progress and spend, the cell results without ids, the manifest with the order seeds, and the
   code. A resume on a fresh host redoes only the build, the work in flight and at most 5 minutes of
   window cells.
4. **Publishing at every checkpoint** (fork visibility, about 150–250 commits). *Accepted* by the user.
   Squash the branch history before any PR to `main`.
5. **The comparison is confounded by design choices.** *Resolved:* the results comment gets a fixed
   "What this ACE is and is not" paragraph under the main table (section 12).
6. **Smaller points.**
   - *Memory cap units:* resolved per the user's instruction. The cap follows the design's M cap
     (30,000 tokens) within the base plan's scope limits (§0, §13: the RITS window, 6,000 completion
     tokens, 60,000-character trimming): `M_cap = min(30,000, 34,000 − P_max − H_max)` ≈ 13.5K tokens,
     measured in A8 (section 6.2). The other #804 limits are adopted too: the optimizer cap of 10M
     non-cache-read tokens per search (it replaces the $60 soft cap of the first draft, which had no
     source) and B = 900. The #804 90-minute wall cap per rollout is *not* adopted: the base plan's 30
     minutes is kept (base rule, F13), and section 13.2 lists this.
   - Still true, and disclosed in the report: sequential adaptation is the critical path (5–7 h);
     the no-GT Reflector sees no outcome; dev is used only as a diagnostic; the per-bullet application of
     the memory lint (section 8.3); a heartbeat proves the ledger is alive, not that the runner is
     advancing (`status.py` flags no `result` entry for 75 minutes while the runner is alive: one ACE
     step can take a 30-minute wall-cap kill, a 30-minute retry and the two optimizer calls).
7. **Base-plan inconsistencies** (missing Appendix B, posting command without `-R`, "we use 3"
   sub-agents). *Accepted.* This plan uses `-R skillberry-ai/cap-evolve`. The base plan is left as
   the record of its own run.

8. **Alignment review (2026-10-14).** At the user's request, the plan was checked against the base
   plan, the design and #804. Self-introduced deviations were reverted:
   - the review step before posting;
   - the extra `solution` scan pattern;
   - `max_tokens` 8192 (now ACE's default, 4096);
   - a 3-task ACE acceptance loop (now 4 dev tasks, design acceptance (iii));
   - a 45-minute stall flag that ACE steps can legitimately exceed.

   Omissions were restored:
   - difficulty-count check (B3);
   - RITS window and concurrency probes (A2);
   - new trial seeds on infra retries;
   - soft optimizer guard 8.5M;
   - task-id lint (design §5.4) and the lint of merged bullets;
   - transcript scan in A7 (design acceptance (iv));
   - the full TGC definition.

   Inconsistencies were fixed: phases defined (section 10), counts, times, paths and references.
   One change went against "minimize redo": per-task test outcomes are not pushed, because with the
   public split files they could be mapped back to task ids (base §12, design §5.2 item 9).
   Every remaining difference is in sections 13.1 to 13.3, with its reason.

Remaining open points:
- **Design vs code:** the design's A-ACE "reflection rounds 5" and "bullets with counters" do not
  exist in ACE's no-GT AppWorld code. The plan follows the code, and section 13.2 says so.
- **Ledger order:** "adds on top" was read as append-only, oldest first (newest entry last). Earlier
  entries are never edited in either reading.
- **The first push of state uses the real branch.** A9's throwaway branch tests the mechanism first.
- **Option, not adopted:** push the final-window per-cell records *encrypted*, with a key kept outside
  git, so that P8 survives a host loss too. It is only useful if the user stores the key off-host.
