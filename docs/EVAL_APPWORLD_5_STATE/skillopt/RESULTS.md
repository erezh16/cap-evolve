# Results: SkillOpt vs seed on AppWorld test_normal (gpt-oss-120b)

**Headline.** On the 168 held-out test_normal tasks (2 trials each), the SkillOpt champion scores **TGC 59.2 vs 34.2** for the unmodified seed, **Δ +25.0 points, 95% CI [+18.5, +31.8]**. SGC is **41.1 vs 11.6**, Δ +29.5 [+19.6, +40.2]. Both intervals exclude 0. The isolation scan found 0 test-id hits.

## Setup
- **Method:** SkillOpt, `microsoft/skillopt` @ `ae2f766`. Surface learned: M (static memory playbook).
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
| **skillopt** | **59.2** | **41.1** |
| Δ vs seed [95% CI] | +25.0 [+18.5, +31.8] | +29.5 [+19.6, +40.2] |

CIs come from a scenario-clustered paired bootstrap (56 clusters, 10,000 resamples), unadjusted for multiplicity. Every cell ran, so dropping missing cells changes nothing.

## TGC by difficulty

| difficulty (n) | seed | skillopt | Δ |
|---|---|---|---|
| Easy (57) | 57.0 | 80.7 | +23.7 |
| Medium (48) | 24.0 | 64.6 | +40.6 |
| Hard (63) | 21.4 | 35.7 | +14.3 |

## Cost, tokens and latency

Agent side, final window, per episode:

| arm | prompt tok | completion tok | steps | s | step-cap hits | ctx exceeded | collateral damage | max prompt tok | trials agree |
|---|---|---|---|---|---|---|---|---|---|
| seed | 89,779 | 5,803 | 12.5 | 244 | 4 | 0 | 12 | 19,394 | 70% |
| skillopt | 148,513 | 6,585 | 11.8 | 280 | 1 | 0 | 14 | 25,305 | 77% |

The agent runs on RITS, which is unpriced, so agent tokens have no dollar cost.

Optimizer side (search): 74 calls, 2.33M input / 0.18M output tokens, **$9.7 (proxy at list price $3/$15 per MTok)**, 24 min of optimizer wall time. **900 counted search rollouts** (of 900).

## What the search did and what changed
SkillOpt `ReflACTTrainer` evolving one Markdown skill document injected into the memory slot.
- Settings: SkillOpt's own defaults (its `configs/_base_`), with batch 40, minibatch 8, merge 8, learning rate 4→2 cosine, slow update on, meta skill on, strict gate on full dev (`gate_metric=hard`), seed 42.
- Every optimizer stage (analyst, merge, ranking, slow update, meta skill) went through the gateway shim: no temperature, max_tokens 16384.
- Epochs: **3 instead of 4**, the least-distorting change that fits B = 900 (§7.2). The evaluator cap was reached during the last step.
- Data: train = official train (90 tasks); the gate is the official dev set (57 tasks).
- Rollouts give the optimizer compacted conversations (outputs ≤ 2,000 chars, total ≤ 60,000) with the gold-free failed-check report. `reference_text` was never set.
- Gate results: steps 1, 2 and 8 accepted (dev hard 0.649 → 0.719 → 0.754; seed baseline on the same gate 18/57 = 0.316). The frozen skill is step 8's: 24,118 chars, about 5.7K tokens.

The frozen artifact passed the lint (no train/dev instruction 8-grams, no supervisor contacts, no hardcoded `apis.<app>` chains). It is published in `docs/EVAL_APPWORLD_5_STATE/skillopt/artifact/`.

## Isolation
- 0 test-id hits across every optimizer-side record, workspace and the frozen artifact.
- test_normal was locked during the search. AppWorld's REPL was hardened (no `os`, `pathlib`, `io`, `shutil` or `glob`). Feedback was gold-free.
- The optimizer makes plain chat calls with no shell or file access.
- Dev diagnostic (57 dev tasks, 1 trial, selection-biased): skillopt 0.7368 vs seed 0.3684.

## What this SkillOpt is and is not
This is a statement about **one artifact from one search seed** in this configuration, not about SkillOpt as published. Deviations from the published method: the optimizer is Sonnet, not GPT-5.5 as in the paper; the skill sits in the memory slot (USER turn), not in the system prompt; 3 epochs instead of 4; no Hidden Reference; compacted trajectories. Common to all five arms: the optimizer is `aws/claude-sonnet-5-5`; the stock AppWorld template plus an injectable memory slot; a fixed rollout budget (B = 900); gold-free F1 feedback; and the memory cap (30,000 chars / M_cap 13,500 tokens).

## What the numbers cannot support
- **No ranking between candidates.** Budgets and surfaces differ, and with one search seed per method these are artifact-level results.
- Two identical artifacts scored in different windows have drifted by about 4–6 TGC points (base plan F10), and within this window the two trials of a task agreed on only 77% of tasks for this arm. Gaps of a few points between candidates are within noise.
- For context only, Δ TGC vs seed for all five candidates in this window: GEPA +25.9 · SkillOpt +25.0 · WikiSkill +20.8 · EvoSkill +20.5 · Meta-Harness +17.9.
- Search-time scores (dev and the search set) are selection-biased and overstate test performance.

## Deviations from the plan, all recorded in the ledger (`docs/EVAL_APPWORLD_5.md` §15)
- One voided final window (stopped at 1,001 cells when Meta-Harness was re-run; never used for results).
- A container restart during this window (no data lost; resumed at 24 workers instead of 48).
- Memory watermarks at 90/80%.
- Code: `examples/appworld/` @ `e313482` and later fix commits on branch `eval5`.
