# AppWorld TEST_ABL results: 2 arms, test_normal × 5 trials, one window

**Setup.** AppWorld `42b5bcf`, `test_normal` (168 tasks, 56 scenarios; Easy 57 / Medium 48 / Hard 63). Agent `openai/gpt-oss-120b-a100` on RITS (reasoning medium, temperature 0, the official simplified ReAct code agent, 50 steps, 100K completion tokens per task, 30-min wall cap); no optimizer. One shuffled window of 1,680 cells (2 arms × 168 × 5 trials, trial seeds 7000+k, order seed 2026102802, order sha256 `9451061cba48e4d2…`). Code: branch `test-abl` of `erezh16/cap-evolve`.

| arm | what it is | surfaces changed vs seed | hash (rule S) | source |
|---|---|---|---|---|
| `abl_nogate` | cap-evolve main 75b3bcd, no acceptance gate (gate ablation, #938) | P + T | `cdbc5827f70b02e1…` | local |
| `abl_naivegate` | cap-evolve main 75b3bcd, naive gate (gate ablation, #939) | P + T | `fa2bfe23ace7fc05…` | local |

## Primary: each ablation − `abl_ref` (Holm over the primary contrasts)

(No `abl_ref` in this window: the gate arms' contrasts with `abl_ref` are cross-window.)

## Main table (ranked by TGC; % of tasks / scenarios)

| rank | arm | TGC [95% CI] | SGC | Δ TGC vs seed [95% CI] | Δ TGC vs `abl_ref` [95% CI] | not separable from top | missing |
|---|---|---|---|---|---|---|---|
| 1 | `abl_naivegate` Cap evolve naive gate | 57.1 [47.0, 66.8] | 38.6 | — | — | yes | 0 |
| 2 | `abl_nogate` Cap evolve no gate | 55.0 [44.9, 64.6] | 36.8 | — | — | yes | 0 |

## By difficulty

| arm | Easy TGC | Medium TGC | Hard TGC | Easy SGC | Medium SGC | Hard SGC |
|---|---|---|---|---|---|---|
| `abl_nogate` | 78.2 | 53.8 | 34.9 | 62.1 | 36.2 | 14.3 |
| `abl_naivegate` | 77.5 | 61.3 | 35.6 | 64.2 | 36.2 | 17.1 |

## Stochastic behaviour (5 trials)

| arm | tasks passing 0/1/2/3/4/5 of 5 | stable | flaky | pass@1 … pass@5 | pass^1 … pass^5 | within-task var share |
|---|---|---|---|---|---|---|
| `abl_nogate` | 42/15/12/23/26/50 | 54.8 | 45.2 | 55.0 / 66.1 / 70.7 / 73.2 / 75.0 | 55.0 / 43.9 / 37.3 / 32.9 / 29.8 | 36.0 |
| `abl_naivegate` | 41/13/15/16/26/57 | 58.3 | 41.7 | 57.1 / 67.3 / 71.6 / 74.0 / 75.6 | 57.1 / 47.0 / 41.1 / 37.0 / 33.9 | 33.2 |

**Flakiness across arms.** Pearson correlation of TGC with flaky share over the 2 arms: -1.00. Mean flaky share by surface changed: P 43.5 (n=2), T 43.5 (n=2). By difficulty (mean over arms): Easy 35.1, Medium 47.9, Hard 47.6.

## Trial-count sensitivity

| arm | TGC, first 1 | Δ vs seed, first 1 [95% CI] | TGC, first 2 | Δ vs seed, first 2 [95% CI] | TGC, first 3 | Δ vs seed, first 3 [95% CI] | TGC, first 4 | Δ vs seed, first 4 [95% CI] | TGC, first 5 | Δ vs seed, first 5 [95% CI] |
|---|---|---|---|---|---|---|---|---|---|---|
| `abl_nogate` | 56.5 | — | 59.2 | — | 56.3 | — | 55.7 | — | 55.0 | — |
| `abl_naivegate` | 60.1 | — | 58.3 | — | 58.5 | — | 57.6 | — | 57.1 | — |

(The trial-count CIs use 2,000 bootstrap resamples; the main tables use 10,000.)

## All 1 pairs (row − column; Holm over all pairs, secondary)

| pair | Δ TGC [95% CI] | Δ SGC [95% CI] | bootstrap p | Holm |
|---|---|---|---|---|
| abl_nogate − abl_naivegate | -2.1 [-6.8, 2.6] | -1.8 [-8.6, 5.0] | 0.3838 | no |

## Agent tokens, steps, latency and infra (per episode)

| arm | prompt tok/ep (mean / p50 / p90) | completion tok/ep (mean / p50 / p90) | steps (mean) | s/ep (mean / p50 / p90) | max prompt | step-cap | token-cap | ctx-exceeded | collateral | infra retries | pass fraction |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `abl_nogate` | 124,272 / 91,445 / 255,325 | 6,279 / 4,476 / 13,268 | 9.6 | 256 / 185 / 543 | 26,263 | 5 | 0 | 0 | 31 | 4 | 76.2 |
| `abl_naivegate` | 110,470 / 84,851 / 223,548 | 6,822 / 4,906 / 14,413 | 9.1 | 276 / 205 / 567 | 24,333 | 1 | 0 | 0 | 22 | 9 | 79.2 |

Agent cost: n/a (RITS is unpriced); agent tokens above stand in for it. No optimizer was called.

## The ablation study's own window (context)

| arm | this window TGC (5 trials) | other window TGC (2 trials) | other window |
|---|---|---|---|
| `abl_nogate` | 55.0 | n/a | other window: ablation study's final window (2026-10-27, 2 trials, seeds 5000+k) |
| `abl_naivegate` | 57.1 | n/a | other window: ablation study's final window (2026-10-27, 2 trials, seeds 5000+k) |

Context only, never a paired comparison. The seed's TGC in the other windows: ablation window 36.3.

**Deviations and disclosures.** Protocol: `docs/TEST_ALL.md` with the ablation champions as its arms (plan `docs/TEST_ABL.md` §15). `abl_cc` (seed-identical) was excluded. The gate arms are scored in a second window after this one (cross-window comparisons, labelled). Every issue and decision during execution is in `docs/TEST_ABL_ADDENDUM.md` and the ledger `docs/TEST_ABL_STATUS.md`.

**What these numbers cannot support.** Each champion came from **one** search with one search seed, so every ablation − reference contrast mixes the ablated factor with search randomness. This is a **single** test window, with 5 trials per task. In earlier AppWorld windows, identical artifacts drifted 4 to 6 TGC points between windows, and there is no seed-identical arm here to measure the within-window part (`abl_cc` was excluded). Differences of a few points are therefore not resolved, and a null result is a bound, not evidence of no effect. `abl_cc_best` was chosen by its search score (selection-biased). These are statements about the **artifacts**, not about the methods in general.
