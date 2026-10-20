# Results: GEPA vs seed on AppWorld test_normal (gpt-oss-120b)

**Headline.** On the 168 held-out test_normal tasks (2 trials each), the GEPA champion scores **TGC 60.1 vs 34.2** for the unmodified seed, **Δ +25.9 points, 95% CI [+18.5, +33.3]**. SGC is **39.3 vs 11.6**, Δ +27.7 [+17.0, +38.4]. Both intervals exclude 0. The isolation scan found 0 test-id hits.

## Setup
- **Method:** GEPA, PyPI `gepa==0.1.4` (`8b0ce6c`). Surface learned: P + T (prompt template, helpers, API notes).
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
| **gepa** | **60.1** | **39.3** |
| Δ vs seed [95% CI] | +25.9 [+18.5, +33.3] | +27.7 [+17.0, +38.4] |

CIs come from a scenario-clustered paired bootstrap (56 clusters, 10,000 resamples), unadjusted for multiplicity. Every cell ran, so dropping missing cells changes nothing.

## TGC by difficulty

| difficulty (n) | seed | gepa | Δ |
|---|---|---|---|
| Easy (57) | 57.0 | 78.1 | +21.1 |
| Medium (48) | 24.0 | 60.4 | +36.5 |
| Hard (63) | 21.4 | 43.7 | +22.2 |

## Cost, tokens and latency

Agent side, final window, per episode:

| arm | prompt tok | completion tok | steps | s | step-cap hits | ctx exceeded | collateral damage | max prompt tok | trials agree |
|---|---|---|---|---|---|---|---|---|---|
| seed | 89,779 | 5,803 | 12.5 | 244 | 4 | 0 | 12 | 19,394 | 70% |
| gepa | 116,268 | 6,061 | 11.8 | 258 | 4 | 0 | 9 | 22,292 | 76% |

The agent runs on RITS, which is unpriced, so agent tokens have no dollar cost.

Optimizer side (search): 33 calls, 0.76M input / 0.18M output tokens, **$5.06 (proxy at list price $3/$15 per MTok)**, 19 min of optimizer wall time. **900 counted search rollouts** (of 900).

## What the search did and what changed
GEPA 0.1.4 reflective evolution over three text components (`policy/instructions.txt`, `tools/helpers.py`, `tools/api_notes.json`).
- Settings: round_robin module selection, minibatch 3, Pareto candidate selection, strict improvement, no merge, max_metric_calls 987, seed 0.
- Data: trainset = official train (90 tasks, reflection minibatches); valset = official dev (57 tasks, Pareto front and final choice).
- Reflection used GEPA's instruction-proposal text with two changes: the new text is delimited by `<new_text>` (the stock prompt contains about 45 ``` fences), and the lint rules are stated in the prompt. Over the whole search the reflector's output was lint-rejected 7 times and failed to parse once; each time it was re-asked with the lint or parse error, and it never gave up. There were 0 refusals.
- Search end: the evaluator's hard cap B = 900 counted rollouts was hit 3 calls before GEPA's own 987. The result is GEPA's state saved before the abandoned iteration.
- Outcome: 13 candidates in the pool. The champion is candidate 12 (dev 0.719; the seed scored 0.421 in the same search). In the frozen artifact the prompt is rewritten (about 22K chars, adding a section of general app/API facts and answer rules); helpers and API notes are unchanged from the seed.

The frozen artifact passed the lint (no train/dev instruction 8-grams, no supervisor contacts, no hardcoded `apis.<app>` chains). It is published in `docs/EVAL_APPWORLD_5_STATE/gepa/artifact/`.

## Isolation
- 0 test-id hits across every optimizer-side record, workspace and the frozen artifact.
- test_normal was locked during the search. AppWorld's REPL was hardened (no `os`, `pathlib`, `io`, `shutil` or `glob`). Feedback was gold-free.
- The optimizer makes plain chat calls with no shell or file access.
- Dev diagnostic (57 dev tasks, 1 trial, selection-biased): gepa 0.6491 vs seed 0.3684.

## What this GEPA is and is not
This is a statement about **one artifact from one search seed** in this configuration, not about GEPA as published. Deviations from the published method: the optimizer is Sonnet, not the target model; the feedback is gold-free F1 (the ACE paper's GEPA baseline had gold labels); one search seed; 0/1 rewards with minibatch 3 make acceptance noisy. Common to all five arms: the optimizer is `aws/claude-sonnet-5-5`; the stock AppWorld template plus an injectable memory slot; a fixed rollout budget (B = 900); gold-free F1 feedback; and the memory cap (30,000 chars / M_cap 13,500 tokens).

## What the numbers cannot support
- **No ranking between candidates.** Budgets and surfaces differ, and with one search seed per method these are artifact-level results.
- Two identical artifacts scored in different windows have drifted by about 4–6 TGC points (base plan F10), and within this window the two trials of a task agreed on only 76% of tasks for this arm. Gaps of a few points between candidates are within noise.
- For context only, Δ TGC vs seed for all five candidates in this window: GEPA +25.9 · SkillOpt +25.0 · WikiSkill +20.8 · EvoSkill +20.5 · Meta-Harness +17.9.
- Search-time scores (dev and the search set) are selection-biased and overstate test performance.

## Deviations from the plan, all recorded in the ledger (`docs/EVAL_APPWORLD_5.md` §15)
- One voided final window (stopped at 1,001 cells when Meta-Harness was re-run; never used for results).
- A container restart during this window (no data lost; resumed at 24 workers instead of 48).
- Memory watermarks at 90/80%.
- Code: `examples/appworld/` @ `e313482` and later fix commits on branch `eval5`.
