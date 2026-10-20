# Results: Meta-Harness vs seed on AppWorld test_normal (gpt-oss-120b)

**Headline.** On the 168 held-out test_normal tasks (2 trials each), the Meta-Harness champion scores **TGC 52.1 vs 34.2** for the unmodified seed, **Δ +17.9 points, 95% CI [+10.1, +25.3]**. SGC is **33.9 vs 11.6**, Δ +22.3 [+11.6, +33.0]. Both intervals exclude 0. The isolation scan found 0 test-id hits.

## Setup
- **Method:** Meta-Harness, `stanford-iris-lab/meta-harness` @ `8123cca`. Surface learned: P + T (+ optional M); the champion uses P + T.
- **Agent under test (all 6 arms):** `openai/gpt-oss-120b` on RITS. The official AppWorld simplified ReAct code agent (`42b5bcf`), reasoning effort medium, temperature 0, 50 steps, 40K context. The same harness, worker, decoding and evaluator are used for every arm; only each arm's surface files differ.
- **Optimizer:** `aws/claude-sonnet-5-5` via the gateway (D1). The same model for all five candidates.
- **Splits:** official only. Search used train (90) and dev (57). **test_normal (168) was sealed and locked (`chmod 000`) during every search** and scored once, in the final window. test_challenge was not used.
- **Feedback:** gold-free tier F1 (failed requirement texts, collateral flag, steps, errors), never the gold answer or trace.
- **Budget:** ≤ B = 900 counted search rollouts and ≤ 10M optimizer tokens per candidate, 1 trial per task in search, 1 search seed.
- **Final window:** **one** interleaved window of 168 tasks × 6 arms (seed + 5 candidates) × 2 trials = 2,016 episodes, in one shuffled order (recorded seed). Trial seeds 5000 + trial. 0 missing cells; infra retries: 0 for this arm, 1 for the seed.

## Main result (test_normal, 168 tasks / 56 scenarios × 2 trials)

| arm | TGC | SGC |
|---|---|---|
| seed | 34.2 | 11.6 |
| **metaharness** | **52.1** | **33.9** |
| Δ vs seed [95% CI] | +17.9 [+10.1, +25.3] | +22.3 [+11.6, +33.0] |

CIs come from a scenario-clustered paired bootstrap (56 clusters, 10,000 resamples), unadjusted for multiplicity. Every cell ran, so dropping missing cells changes nothing.

## TGC by difficulty

| difficulty (n) | seed | metaharness | Δ |
|---|---|---|---|
| Easy (57) | 57.0 | 68.4 | +11.4 |
| Medium (48) | 24.0 | 47.9 | +24.0 |
| Hard (63) | 21.4 | 40.5 | +19.0 |

## Cost, tokens and latency

Agent side, final window, per episode:

| arm | prompt tok | completion tok | steps | s | step-cap hits | ctx exceeded | collateral damage | max prompt tok | trials agree |
|---|---|---|---|---|---|---|---|---|---|
| seed | 89,779 | 5,803 | 12.5 | 244 | 4 | 0 | 12 | 19,394 | 70% |
| metaharness | 107,990 | 6,972 | 14.3 | 292 | 4 | 0 | 11 | 20,472 | 78% |

The agent runs on RITS, which is unpriced, so agent tokens have no dollar cost.

Optimizer side (search): 7 calls, 2.22M input / 0.01M output tokens, 38.9M cache-read, **$28.18 (reported by the CLI)**, 76 min of optimizer wall time. **887 counted search rollouts** (of 900).

## What the search did and what changed
Meta-Harness ported from its Terminal-Bench-2 reference.
- **Outer loop:** Phase 0 scores the seed on the search set (train ∪ dev, 147 tasks). Each iteration then runs the proposer → `pending_eval.json` → validator (outside the proposer: forbidden strings, file allowlist, render and parse checks, shared lint) → 1-task smoke test → 147-task evaluation → frontier with token tie-break.
- **Proposer:** the vendored `claude_wrapper` (`claude -p`, `aws/claude-sonnet-5-5`, Read/Glob/Grep/Agent/Write/Edit/Bash) driven by an AppWorld adaptation of the TB2 SKILL.md, with the "do not run the agent or AppWorld" rule. Its workspace held only candidates, gold-free per-task trajectories and scores, the public API reference and a lint.
- **Iterations:** 7 (5 producing candidates). Iterations 2 and 4 were lost: `claude -p` ended their analysis sub-agents at 600 s. After the fix, user decision D11 ran 2 replacement iterations within B (887/900 counted rollouts).
- **Search-set TGC:** seed 0.401; it1 `no_answer_on_action_tasks` 0.558; **it3 `fetch_all_pages_helper` 0.585 (champion)**; it5 0.544; it6 0.578; it7 0.571.
- **The champion changes P + T:** prompt edits plus a page-fetching helper and API notes.

The frozen artifact passed the lint (no train/dev instruction 8-grams, no supervisor contacts, no hardcoded `apis.<app>` chains). It is published in `docs/EVAL_APPWORLD_5_STATE/metaharness/artifact/`.

## Isolation
- 0 test-id hits across every optimizer-side record, workspace and the frozen artifact. The only literal `root_full` / `ground_truth` strings in the optimizer area are in the A9 acceptance transcript (my planted-secret probe, which names those paths), not in any search session.
- test_normal was locked during the search. AppWorld's REPL was hardened (no `os`, `pathlib`, `io`, `shutil` or `glob`). Feedback was gold-free.
- The proposer ran in Claude Code's sandbox (A9: 0 of 11 planted secrets leaked; network restricted to the gateway; AF_UNIX blocked). Its own logs show every file read and write inside the optimizer workspace.
- Dev diagnostic (57 dev tasks, 1 trial, selection-biased): metaharness 0.5088 vs seed 0.3684.

## What this Meta-Harness is and is not
This is a statement about **one artifact from one search seed** in this configuration, not about Meta-Harness as published. Deviations from the published method: the proposer ran with `--permission-mode acceptEdits` inside Claude Code's sandbox instead of the wrapper's `--dangerously-skip-permissions` (**user decision D10**); Sonnet instead of Opus (no `--effort`); search restricted to the four injectable harness files, not arbitrary agent code; 1 trial per task in search (TB2 uses 2); 2 of 7 iterations were lost to the CLI's 600 s sub-agent limit, and 2 replacements were run (D11); AppWorld was kept out of the proposer's view. Common to all five arms: the optimizer is `aws/claude-sonnet-5-5`; the stock AppWorld template plus an injectable memory slot; a fixed rollout budget (B = 900); gold-free F1 feedback; and the memory cap (30,000 chars / M_cap 13,500 tokens).

## What the numbers cannot support
- **No ranking between candidates.** Budgets and surfaces differ, and with one search seed per method these are artifact-level results.
- Two identical artifacts scored in different windows have drifted by about 4–6 TGC points (base plan F10), and within this window the two trials of a task agreed on only 78% of tasks for this arm. Gaps of a few points between candidates are within noise.
- For context only, Δ TGC vs seed for all five candidates in this window: GEPA +25.9 · SkillOpt +25.0 · WikiSkill +20.8 · EvoSkill +20.5 · Meta-Harness +17.9.
- Search-time scores (dev and the search set) are selection-biased and overstate test performance.

## Deviations from the plan, all recorded in the ledger (`docs/EVAL_APPWORLD_5.md` §15)
- One voided final window (stopped at 1,001 cells when Meta-Harness was re-run; never used for results).
- A container restart during this window (no data lost; resumed at 24 workers instead of 48).
- Memory watermarks at 90/80%.
- Code: `examples/appworld/` @ `e313482` and later fix commits on branch `eval5`.
