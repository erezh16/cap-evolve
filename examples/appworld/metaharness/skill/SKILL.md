---
name: meta-harness-appworld
description: Run one iteration of harness evolution for the AppWorld ReAct code agent.
---

# Meta-Harness (AppWorld)

Run ONE iteration of agent harness evolution.

**You do NOT run the agent or the AppWorld evaluation yourself.** You analyze results + failed and successful trajectories, propose one harness variant, and implement it. The outer loop (`meta_harness_appworld.py`) validates, smoke-tests and benchmarks every candidate. AppWorld, the model server and the network are not reachable from this workspace, and you have no access outside it.

## CRITICAL CONSTRAINTS

- You MUST produce 1 new candidate every iteration.
- Do NOT write "the frontier is optimal" or "stop iterating", or abort early.

### Anti-overfitting rules

- **No task-specific hints.** Do not hardcode knowledge about specific tasks. The harness must be general-purpose.
- **Never mention task ids, task instructions, person names, emails, phone numbers or other specific values** from the trajectories in any candidate file. If your improvement only helps one task, it's too specific.
- **General guidance is OK.** Rules like "page through list APIs until a page comes back empty" are fine -- they happen to help specific tasks but apply broadly. The test: would this advice be useful to an agent working on MANY unfamiliar AppWorld tasks?
- **If in doubt, make it more general.**

## CONTEXT

You are evolving the harness of the official AppWorld simplified ReAct code agent (model: gpt-oss-120b, reasoning effort medium, temperature 0, 40K-token context window, at most 50 steps). Read `reference/react_agent_notes.md` first: it explains exactly how each harness file is used. `reference/api_index.md` lists every app and API.

**The search space is the four harness files of a candidate** — everything the harness lets you change:

- `policy/instructions.txt` — the prompt template (Jinja; split into chat messages on `USER:` / `ASSISTANT:` lines; keeps the worked demo structure and must end with the `My name is: … Task: {{ instruction }}` block).
- `tools/helpers.py` — Python helpers defined in the agent's REPL before step 1 (the agent is told their names and signatures).
- `tools/api_notes.json` — notes appended to the agent's API-doc lookups (`"app"` or `"app.api"` → note ≤ 400 chars).
- `memory/playbook.md` — an optional static guidance block inserted right before the final task block (≤ 30,000 characters).

The lint rules are in `reference/react_agent_notes.md` and are enforced by `tools/lint` (a wrapper around `tools/lints.py` with its own Python).

## CANDIDATE DESIGN

Each candidate is a directory `candidates/<name>/` holding only those four files (`policy/instructions.txt` is required; the other three are optional). Start from a copy of an existing candidate (usually the current best, `_best` in `logs/frontier_val.json`) and make your changes in the copy.

### What you can and cannot modify

- **CAN**: create `candidates/<new_name>/` and edit its files freely.
- **CANNOT**: modify any existing candidate, anything under `runs/`, `logs/` (except writing `logs/pending_eval.json`), `reference/` or `tools/`.

### Design principles

- Your primary goal is to raise the agent's task success rate (TGC) on AppWorld; fewer tokens and steps per task is the tie-breaker.
- One mechanism per candidate. Each candidate tests exactly one hypothesis. If you're tempted to add "and also..." -- that's a second candidate.
- Mechanism-first. Identify a specific failure mode or hypothesis from trajectories, then design changes that target it. Never add changes speculatively.

## WORKFLOW

### Step 1: Analyze (1 subagent)

Launch ONE Agent subagent (subagent_type: "general-purpose"). It should:

1. Read state files:
   - `logs/frontier_val.json` - current best candidate per task and overall
   - `logs/evolution_summary.jsonl` - what's been tried, what worked/didn't, plus `rollout_metrics`
2. **Deep-read failed AND successful trajectories.** Most important step.
   Each evaluated candidate has `runs/<candidate>/<task>/trajectory.md` (the agent's steps: thought, code, REPL output) and `runs/<candidate>/<task>/eval.json` (reward, the failed requirement checks, steps, tokens, termination), plus `runs/<candidate>/summary.json`.
3. Read the candidate files in `candidates/*/`.
4. Return:

```
STATE: <5-line summary: current scores, what's been tried, avg tokens/steps>

HYPOTHESIS: "<falsifiable claim about what will improve scores>"
CANDIDATE: name=<snake_case>, changes="<specific changes>", prediction="<expected TGC improvement AND expected token/step impact>"
```

### Step 2: Implement (1 subagent)

Launch **1 Agent subagent** (subagent_type: "general-purpose"). The prompt must include the candidate name, the parent candidate, the specific changes from Step 1, and the working directory.

The subagent should:

1. Copy the parent: `cp -r candidates/<parent> candidates/<snake_case_name>`.
2. Make targeted changes according to the instructions.
3. **Smoke check** (pure Python only — never the agent or AppWorld): `tools/lint candidates/<name>` must print `"ok": true`, and if helpers changed, `python3 -I -c "import ast,sys; ast.parse(open('candidates/<name>/tools/helpers.py').read())"`.
4. Return: directory path, lint status

### Step 3: Write pending_eval.json

Write `logs/pending_eval.json`:

```json
{
  "iteration": <N>,
  "candidates": [
    {
      "name": "<name>",
      "path": "candidates/<name>",
      "parent": "<parent name>",
      "hypothesis": "<falsifiable claim>",
      "changes": "<what was changed>",
      "expected_efficiency": "<expected token/step impact>"
    }
  ]
}
```

Output: `CANDIDATES: <name1>`

## IMPORTANT NOTES

- Candidate names are snake_case and new every iteration.
- The prompt template must keep the Jinja variables `{{ main_user.first_name }}`, `{{ main_user.last_name }}`, `{{ main_user.email }}`, `{{ main_user.phone_number }}` and `{{ instruction }}` (and may use `{{ app_descriptions }}`), start with `USER:`, and end with the final task block.
- Helpers import only re, json, math, datetime, itertools, collections, functools; they take `apis` and app/API names as parameters (no `apis.<app>.` chains, no app/API name string literals); no top-level calls.
- A candidate that fails validation or the lint is scored 0 on every task without being run.
