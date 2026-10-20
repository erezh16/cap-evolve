# Results: WikiSkill vs seed on AppWorld test_normal (gpt-oss-120b)

**Headline.** On the 168 held-out test_normal tasks (2 trials each), the WikiSkill champion scores **TGC 55.1 vs 34.2** for the unmodified seed, **Δ +20.8 points, 95% CI [+14.0, +28.0]**. SGC is **32.1 vs 11.6**, Δ +20.5 [+10.7, +31.2]. Both intervals exclude 0. The isolation scan found 0 test-id hits.

## Setup
- **Method:** WikiSkill, `kenhuangus/wikiskill` @ `0363334` (third-party reimplementation). Surface learned: M (static memory playbook).
- **Agent under test (all 6 arms):** `openai/gpt-oss-120b` on RITS. The official AppWorld simplified ReAct code agent (`42b5bcf`), reasoning effort medium, temperature 0, 50 steps, 40K context. The same harness, worker, decoding and evaluator are used for every arm; only each arm's surface files differ.
- **Optimizer:** `aws/claude-sonnet-5-5` via the gateway (D1). The same model for all five candidates.
- **Splits:** official only. Search used train (90) and dev (57). **test_normal (168) was sealed and locked (`chmod 000`) during every search** and scored once, in the final window. test_challenge was not used.
- **Feedback:** gold-free tier F1 (failed requirement texts, collateral flag, steps, errors), never the gold answer or trace.
- **Budget:** ≤ B = 900 counted search rollouts and ≤ 10M optimizer tokens per candidate, 1 trial per task in search, 1 search seed.
- **Final window:** **one** interleaved window of 168 tasks × 6 arms (seed + 5 candidates) × 2 trials = 2,016 episodes, in one shuffled order (recorded seed). Trial seeds 5000 + trial. 0 missing cells; infra retries: 2 for this arm, 1 for the seed.

## Main result (test_normal, 168 tasks / 56 scenarios × 2 trials)

| arm | TGC | SGC |
|---|---|---|
| seed | 34.2 | 11.6 |
| **wikiskill** | **55.1** | **32.1** |
| Δ vs seed [95% CI] | +20.8 [+14.0, +28.0] | +20.5 [+10.7, +31.2] |

CIs come from a scenario-clustered paired bootstrap (56 clusters, 10,000 resamples), unadjusted for multiplicity. Every cell ran, so dropping missing cells changes nothing.

## TGC by difficulty

| difficulty (n) | seed | wikiskill | Δ |
|---|---|---|---|
| Easy (57) | 57.0 | 73.7 | +16.7 |
| Medium (48) | 24.0 | 59.4 | +35.4 |
| Hard (63) | 21.4 | 34.9 | +13.5 |

## Cost, tokens and latency

Agent side, final window, per episode:

| arm | prompt tok | completion tok | steps | s | step-cap hits | ctx exceeded | collateral damage | max prompt tok | trials agree |
|---|---|---|---|---|---|---|---|---|---|
| seed | 89,779 | 5,803 | 12.5 | 244 | 4 | 0 | 12 | 19,394 | 70% |
| wikiskill | 100,663 | 6,079 | 11.0 | 257 | 4 | 0 | 8 | 20,949 | 76% |

The agent runs on RITS, which is unpriced, so agent tokens have no dollar cost.

Optimizer side (search): 51 calls, 1.78M input / 0.09M output tokens, **$6.75 (proxy at list price $3/$15 per MTok)**, 13 min of optimizer wall time. **792 counted search rollouts** (of 900).

## What the search did and what changed
WikiSkill (Algorithm 1) as reimplemented by the vendored `kenhuangus/wikiskill` loop. Each iteration:
- roll out **all** 90 train tasks with the current skills;
- sample 5 failing and 3 passing traces (15k chars each);
- make one Wiki Maintainer call;
- run a ReAct Skill Proposer (≤ 20 turns, `read_file` over the workspace only);
- validate on **all** 57 dev tasks and accept the change only on strict improvement, rolling back skills (not the wiki) otherwise.

Prompts: the paper's Appendix E Maintainer and Proposer prompts replace the repository's condensed ones, plus a one-paragraph tool-call syntax note. Accepted skills are rendered into the memory slot with no retrieval.

**K = 5 iterations instead of 8**, to fit B = 900 (57 + 5 × 147 = 792).

Trajectory: baseline 0.333 → it1 create 0.456 (accepted) → it2 patch 0.456 (rejected) → it3 patch 0.561 (accepted) → it4 patch 0.614 (accepted) → it5 second skill 0.596 (rejected). The frozen playbook is one skill: 7,859 chars, about 1.9K tokens.

The frozen artifact passed the lint (no train/dev instruction 8-grams, no supervisor contacts, no hardcoded `apis.<app>` chains). It is published in `docs/EVAL_APPWORLD_5_STATE/wikiskill/artifact/`.

## Isolation
- 0 test-id hits across every optimizer-side record, workspace and the frozen artifact.
- test_normal was locked during the search. AppWorld's REPL was hardened (no `os`, `pathlib`, `io`, `shutil` or `glob`). Feedback was gold-free.
- The optimizer makes plain chat calls with no shell or file access.
- Dev diagnostic (57 dev tasks, 1 trial, selection-biased): wikiskill 0.5439 vs seed 0.3684.

## What this WikiSkill is and is not
This is a statement about **one artifact from one search seed** in this configuration, not about WikiSkill as published. Deviations from the published method: **a third-party, AI-assisted reimplementation** (no official code exists), with the paper's Appendix E prompts restored; the gateway LLM wrapper, AppWorld inference adapter, outcome summary, parallel rollouts, cost logging, tool-call syntax note and skills→playbook export are ours; K = 5 instead of 8; the optimizer is a fixed Sonnet. Common to all five arms: the optimizer is `aws/claude-sonnet-5-5`; the stock AppWorld template plus an injectable memory slot; a fixed rollout budget (B = 900); gold-free F1 feedback; and the memory cap (30,000 chars / M_cap 13,500 tokens).

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
