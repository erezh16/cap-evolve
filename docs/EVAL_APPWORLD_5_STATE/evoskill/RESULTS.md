# Results: EvoSkill vs seed on AppWorld test_normal (gpt-oss-120b)

**Headline.** On the 168 held-out test_normal tasks (2 trials each), the EvoSkill champion scores **TGC 54.8 vs 34.2** for the unmodified seed, **Δ +20.5 points, 95% CI [+13.7, +27.4]**. SGC is **35.7 vs 11.6**, Δ +24.1 [+15.2, +33.9]. Both intervals exclude 0. The isolation scan found 0 test-id hits.

## Setup
- **Method:** EvoSkill, `sentient-agi/EvoSkill` `v1.3.0` (`1d7dc3e`). Surface learned: M (static memory playbook).
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
| **evoskill** | **54.8** | **35.7** |
| Δ vs seed [95% CI] | +20.5 [+13.7, +27.4] | +24.1 [+15.2, +33.9] |

CIs come from a scenario-clustered paired bootstrap (56 clusters, 10,000 resamples), unadjusted for multiplicity. Every cell ran, so dropping missing cells changes nothing.

## TGC by difficulty

| difficulty (n) | seed | evoskill | Δ |
|---|---|---|---|
| Easy (57) | 57.0 | 78.1 | +21.1 |
| Medium (48) | 24.0 | 58.3 | +34.4 |
| Hard (63) | 21.4 | 31.0 | +9.5 |

## Cost, tokens and latency

Agent side, final window, per episode:

| arm | prompt tok | completion tok | steps | s | step-cap hits | ctx exceeded | collateral damage | max prompt tok | trials agree |
|---|---|---|---|---|---|---|---|---|---|
| seed | 89,779 | 5,803 | 12.5 | 244 | 4 | 0 | 12 | 19,394 | 70% |
| evoskill | 142,111 | 7,256 | 12.2 | 304 | 3 | 0 | 16 | 23,426 | 74% |

The agent runs on RITS, which is unpriced, so agent tokens have no dollar cost.

Optimizer side (search): 36 calls, 1.06M input / 0.08M output tokens, 1.4M cache-read, **$4.91 (reported by the Agent SDK)**, 15 min of optimizer wall time. **663 counted search rollouts** (of 900).

## What the search did and what changed
EvoSkill `SelfImprovingLoop` (skill_only), driven from Python.
- Settings: frontier size 3, selection "best", failure threshold 0.8, no_improvement_limit 5, and 6 train samples per iteration (3 difficulty categories × 2).
- Val per iteration: a fixed stratified **20-task dev subset** (§7.4 budget rule). At freeze, the 3 frontier programs were re-scored on the full 57-task dev set (counted).
- **De-fanged:**
  - the Proposer gets a withheld sentinel instead of ground truth, and a copy of its prompt with the ground-truth phrases replaced by "evaluation feedback (failed checks)";
  - the Proposer's tools are Read/Glob/Grep and the Skill Builder's are Read/Write/Edit/Glob/Grep, with Bash and web tools removed. A write gate allows only program-skill files;
  - the project root is a scratch git repo;
  - both agents ran in Claude Code's sandbox (A9 passed).
- Search ran to its iteration cap (22 in all; the resumed run did iterations 5–22; 17 children scored, one lint-rejected). Base 0.30 on the val subset; best children 0.75. At freeze, `iter-skill-25` scored 0.754 on full dev (iter-skill-26 0.737, iter-skill-17 0.702) and is the champion: an 18.3K-char playbook, about 4.5K tokens.
- One crash (a driver bug on a lint-rejected child, iteration 4) was fixed and resumed with EvoSkill's own continue mode.

The frozen artifact passed the lint (no train/dev instruction 8-grams, no supervisor contacts, no hardcoded `apis.<app>` chains). It is published in `docs/EVAL_APPWORLD_5_STATE/evoskill/artifact/`.

## Isolation
- 0 test-id hits across every optimizer-side record, workspace and the frozen artifact.
- test_normal was locked during the search. AppWorld's REPL was hardened (no `os`, `pathlib`, `io`, `shutil` or `glob`). Feedback was gold-free.
- Both Claude agents ran in Claude Code's sandbox with the de-fanged tool sets (A9 via the Agent SDK: 0 of 11 planted secrets leaked).
- Dev diagnostic (57 dev tasks, 1 trial, selection-biased): evoskill 0.7018 vs seed 0.3684.

## What this EvoSkill is and is not
This is a statement about **one artifact from one search seed** in this configuration, not about EvoSkill as published. Deviations from the published method: ground truth was withheld and the Proposer's gold comparisons were de-fanged; no Bash or web tools; val on a 20-task dev subset (the full dev re-score happens at freeze only); the optimizer is Sonnet, not Opus; skills are rendered into a static playbook in the memory slot (the agent cannot read skill files). Common to all five arms: the optimizer is `aws/claude-sonnet-5-5`; the stock AppWorld template plus an injectable memory slot; a fixed rollout budget (B = 900); gold-free F1 feedback; and the memory cap (30,000 chars / M_cap 13,500 tokens).

## What the numbers cannot support
- **No ranking between candidates.** Budgets and surfaces differ, and with one search seed per method these are artifact-level results.
- Two identical artifacts scored in different windows have drifted by about 4–6 TGC points (base plan F10), and within this window the two trials of a task agreed on only 74% of tasks for this arm. Gaps of a few points between candidates are within noise.
- For context only, Δ TGC vs seed for all five candidates in this window: GEPA +25.9 · SkillOpt +25.0 · WikiSkill +20.8 · EvoSkill +20.5 · Meta-Harness +17.9.
- Search-time scores (dev and the search set) are selection-biased and overstate test performance.

## Deviations from the plan, all recorded in the ledger (`docs/EVAL_APPWORLD_5.md` §15)
- One voided final window (stopped at 1,001 cells when Meta-Harness was re-run; never used for results).
- A container restart during this window (no data lost; resumed at 24 workers instead of 48).
- Memory watermarks at 90/80%.
- Code: `examples/appworld/` @ `e313482` and later fix commits on branch `eval5`.
