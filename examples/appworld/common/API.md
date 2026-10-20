# Shared code for the eval-REST candidate drivers (docs/EVAL_APPWORLD_REST.md §6–§10)

Every driver lives in `examples/appworld/<cand>/run_<cand>.py` with sub-commands `accept`, `search`,
`freeze`. It imports the shared modules below and nothing from another candidate's directory.

```python
import sys; from pathlib import Path
EX = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(EX / "scripts"), str(EX / "common")]
import awrest as P          # paths, constants, json/jsonl helpers, Slot, wait_unpaused, memstate
import evaluator as E       # the only path to an AppWorld episode
import opt_llm              # the only path to a plain-chat optimizer call
import sandbox as SB        # Claude Code sandbox settings + claude_call() for file/shell optimizer roles
import status_doc as S      # ledger: S.append(kind, phase, label, prose, ...)
import post                 # issue posts: post.post(cand, key, title, body)
```

## awrest (`scripts/awrest.py`)
- `P.CANDIDATES`, `P.ISSUES`, `P.METHOD_NAMES`, `P.OPT_MODEL` (`aws/claude-sonnet-5-5`), `P.BUDGET_ROLLOUTS` (900),
  `P.BUDGET_OPT_TOKENS` (10M), `P.SEARCH_SEED_BASE` (100), price constants.
- Paths: `P.AW_STATE` (`/workspace/aw_rest/state`), `P.AW_BUILD`, `P.CLONES/<cand>` (read-only pinned clones),
  `P.VENVS`, `P.SEED_CAP` (the seed capability dir), `P.PUSHED` (`docs/EVAL_APPWORLD_REST_STATE/`, published),
  `P.SCRATCH` (`/tmp/aw_rest`), `P.REFERENCE` (public API index + agent notes; no task data).
- `P.cand_state(cand)` → `AW_STATE/<cand>/` (local-only state: resume files, logs, records).
- `P.read_json / write_json (atomic) / append_jsonl (flock) / read_jsonl / atomic_write / sha256_* / utcnow`.
- `P.progress_log(cand, phase, detail)` → `AW_STATE/progress/<cand>.log`.
- `P.wait_unpaused(who)` blocks while `AW_STATE/PAUSE` exists (memory guard, rule R2). The evaluator, `opt_llm.chat`
  and `SB.claude_call` already call it; a driver that starts any other heavy process must call it first.

## evaluator (`common/evaluator.py`)
- `E.split_ids("train" | "dev")` → official ids in file order (90 / 57). Any other split raises.
- `E.materialize(cand, files: dict[rel, text], base=None) -> Path`: content-addressed candidate dir; `files` keys are
  the surfaces `policy/instructions.txt`, `tools/helpers.py`, `tools/api_notes.json`, `memory/playbook.md`
  (missing keys come from `base`, default the seed). Identical content → identical dir and tree hash.
- `E.tree_hash(cdir)`, `E.seed_hash()`; `E.read_surfaces(cdir)`.
- `E.lint(cdir) -> list[str]` (empty = clean). Always runs in venv-aw (shells out from other venvs).
- `E.evaluate(cand, cdir, task_ids, *, phase, tag="") -> list[dict]` in `task_ids` order:
  - `phase="search"`: counted against B = 900 (fresh episodes only); raises `E.BudgetExceeded` **before** a batch that
    would cross it. `phase="accept"`: acceptance probes, never counted, separate cache. (`"P3"`, `"P5"` are
    the orchestrator's.)
  - Cache: one record per (tree hash, task, trial seed 100). A repeat is a cache hit (`rec["cache_hit"] = True`,
    not counted). After P3, the seed's 147 train+dev records are in the cache, so an unchanged candidate is free;
    a **fresh** seed episode after P3 raises `E.SeedRerunRefused` (a driver bug if it happens).
  - Lint-rejected candidate: no episode runs; each record has `lint_reject=True`, reward 0, the violations in
    `feedback`, and every other field present (0 / [] / None).
  - Record fields (gold-free, feedback tier F1): `task_id, instruction, supervisor, reward (0/1), feedback (text:
    pass/fail, failed requirement texts, collateral damage, complete_task called, steps, API errors, termination),
    error (infra; not cached), lint_reject, steps [{thought?, code, output}...], success, num_tests, pass_count,
    failed_requirements [texts], collateral_damage, complete_task_called, termination, n_steps, prompt_tokens,
    completion_tokens, max_prompt_tokens, api_errors, fs_probe, episode_seconds, trimmed_steps`.
    Look at one real record before writing a renderer; do not guess field shapes.
  - Episodes run in the global slot pool (24 slots shared by every process); pass a whole batch in one call and
    the evaluator parallelises it. Calling evaluate() from several threads is also safe.
  - From a non-AppWorld venv each call shells out to venv-aw (one subprocess per call; batch your calls).
- `E.counted(cand)`, `E.cache_hits(cand)`.

## opt_llm (`common/opt_llm.py`)
- `opt_llm.chat(messages | str, *, cand, role, system=None, max_tokens=8192) -> str`: one Messages-API call to
  `aws/claude-sonnet-5-5` through the gateway. Sends **no** temperature/top_p/top_k/seed (the gateway rejects them),
  no tools, no response_format. Retries 429/5xx; raises on other 4xx; raises `opt_llm.Refusal` on
  `finish_reason=refusal`; raises `opt_llm.BudgetExceeded` once the candidate's non-cache-read tokens reach 10M.
  Logs a usage line to `AW_STATE/<cand>/optimizer_usage.jsonl` and the full call to `llm_calls.jsonl` (local).
- `opt_llm.totals(cand)`, `opt_llm.proxy_usd(totals)`.
- A library that calls an LLM itself (DSPy, Trace2Skill) gets a client object that routes into `opt_llm.chat`.

## sandbox (`common/sandbox.py`)
- `SB.OPT_ROOT` = `/tmp/aw_rest/opt`; a role's workspace must be `SB.OPT_ROOT/<cand>/<job>/` and hold only what the
  method needs (no gold, no AppWorld, no evaluator code).
- `SB.claude_call(cand, role, prompt, workspace, *, allowed_tools, max_turns, system_append=None, ...) -> dict`:
  one `claude -p --output-format json` call inside Claude Code's sandbox (§10 settings: denyRead of the sealed set,
  AppWorld, AW_STATE, venvs, clones, checkouts, other workspaces; network = gateway host only; no WebFetch/WebSearch;
  `allowUnsandboxedCommands: false`). Usage is logged to the same `optimizer_usage.jsonl`.
- `SB.settings_file(cand, workspace)`, `SB.claude_env()`, `SB.ensure_lint_venv()` (jinja2 + tiktoken lint venv
  usable inside the sandbox, run `lints.py` with `AW_LINT_CACHE=<copy of the lint cache in the workspace>`).

## Ledger, progress, posts
- Pushed progress for the hourly status: `P.write_json(P.PUSHED / cand / "progress.json", {...})` with at least
  `stage` (short text), `counted_rollouts`, `cache_hits`, `best_search_score`, `best_search_label`
  (e.g. "dev TGC, selection-biased"), `eta`; plus method-specific counts. **Counts and aggregates only**: never a
  task id, task or supervisor text, trajectory text, optimizer prompt text, or a secret (the content filter
  refuses the commit).
- Milestones (§8: search start, each accepted candidate, every 25% of B, search end, freeze):
  `S.append("result", "P4", f"{cand} search", prose, done_through=..., next_unit=..., extra={"candidate": cand,
  "counts": {...}, "spend": {...}})` — at most one coalesced result entry per 5 minutes, and
  `post.post(cand, key, title, body)` with a unique key. Drivers do not commit or push by any other means.
- Resume: `search` must continue from the method's own saved state after a kill (only the in-flight step may be
  lost) and must never re-request a counted episode (the cache makes repeats free; rely on it).
