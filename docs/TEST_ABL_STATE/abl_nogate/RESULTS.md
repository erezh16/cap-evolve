## Results — Cap evolve no gate (`abl_nogate`)

**Setup.** AppWorld `42b5bcf`, `test_normal` (168 tasks, 56 scenarios; Easy 57 / Medium 48 / Hard 63). Agent `openai/gpt-oss-120b-a100` on RITS (reasoning medium, temperature 0, the official simplified ReAct code agent, 50 steps, 100K completion tokens per task, 30-min wall cap); no optimizer. One shuffled window of 1,680 cells (2 arms × 168 × 5 trials, trial seeds 7000+k, order seed 2026102802, order sha256 `9451061cba48e4d2…`). Code: branch `test-abl` of `erezh16/cap-evolve`.

| arm | what it is | surfaces changed vs seed | hash (rule S) | source |
|---|---|---|---|---|
| `abl_nogate` | cap-evolve main 75b3bcd, no acceptance gate (gate ablation, #938) | P + T | `cdbc5827f70b02e1…` | local |
| `abl_naivegate` | cap-evolve main 75b3bcd, naive gate (gate ablation, #939) | P + T | `fa2bfe23ace7fc05…` | local |

**This arm.** TGC **55.0** [44.9, 64.6], SGC **36.8**; rank **2 of 2** (not separable from the top arm).

**All arms** (ranked by TGC)

| rank | arm | TGC [95% CI] | SGC | Δ TGC vs seed [95% CI] | Δ TGC vs `abl_ref` [95% CI] | not separable from top | missing |
|---|---|---|---|---|---|---|---|
| 1 | `abl_naivegate` Cap evolve naive gate | 57.1 [47.0, 66.8] | 38.6 | — | — | yes | 0 |
| 2 | `abl_nogate` Cap evolve no gate | 55.0 [44.9, 64.6] | 36.8 | — | — | yes | 0 |

| difficulty | TGC | SGC |
|---|---|---|
| Easy (n=57) | 78.2 | 62.1 |
| Medium (n=48) | 53.8 | 36.2 |
| Hard (n=63) | 34.9 | 14.3 |

**Stochastic behaviour (5 trials).** Tasks passing 0/1/2/3/4/5 of 5: 42/15/12/23/26/50; stable 54.8%, flaky 45.2%. pass@k: 55.0 / 66.1 / 70.7 / 73.2 / 75.0; pass^k: 55.0 / 43.9 / 37.3 / 32.9 / 29.8. Within-task share of variance 36.0%. TGC from the first 1..5 trials: 56.5, 59.2, 56.3, 55.7, 55.0.

**Agent cost.** Prompt tokens/episode 124,272 (p90 255,325), completion 6,279, steps 9.6, 256 s/episode (p90 543); max prompt 26,263; step-cap 5, token-cap 0, context-exceeded 0; infra retries 4, missing cells 0. Cost: n/a (RITS is unpriced; no optimizer).

**The ablation study's own window (context, not paired):** TGC n/a (other window: ablation study's final window (2026-10-27, 2 trials, seeds 5000+k)). This window's TGC from its first 2 trials: 59.2.

Full tables (all arms, every pair): [`docs/TEST_ABL_STATE/final2/RESULTS.md`](https://github.com/erezh16/cap-evolve/blob/test-abl/docs/TEST_ABL_STATE/final2/RESULTS.md).

**Deviations and disclosures.** Protocol: `docs/TEST_ALL.md` with the ablation champions as its arms (plan `docs/TEST_ABL.md` §15). `abl_cc` (seed-identical) was excluded. The gate arms are scored in a second window after this one (cross-window comparisons, labelled). Every issue and decision during execution is in `docs/TEST_ABL_ADDENDUM.md` and the ledger `docs/TEST_ABL_STATUS.md`.

**What these numbers cannot support.** Each champion came from **one** search with one search seed, so every ablation − reference contrast mixes the ablated factor with search randomness. This is a **single** test window, with 5 trials per task. In earlier AppWorld windows, identical artifacts drifted 4 to 6 TGC points between windows, and there is no seed-identical arm here to measure the within-window part (`abl_cc` was excluded). Differences of a few points are therefore not resolved, and a null result is a bound, not evidence of no effect. `abl_cc_best` was chosen by its search score (selection-biased). These are statements about the **artifacts**, not about the methods in general.
