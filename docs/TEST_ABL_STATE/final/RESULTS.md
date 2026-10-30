# AppWorld TEST_ABL results: 7 arms, test_normal × 5 trials, one window

**Setup.** AppWorld `42b5bcf`, `test_normal` (168 tasks, 56 scenarios; Easy 57 / Medium 48 / Hard 63). Agent `openai/gpt-oss-120b-a100` on RITS (reasoning medium, temperature 0, the official simplified ReAct code agent, 50 steps, 100K completion tokens per task, 30-min wall cap); no optimizer. One shuffled window of 5,880 cells (7 arms × 168 × 5 trials, trial seeds 7000+k, order seed 2026102801, order sha256 `b619802205631452…`). Code: branch `test-abl` of `erezh16/cap-evolve`.

| arm | what it is | surfaces changed vs seed | hash (rule S) | source |
|---|---|---|---|---|
| `seed` | the unmodified AppWorld ReAct agent | none | `85a0da9cec2206a7…` | local |
| `abl_ref` | full cap-evolve main 75b3bcd, hill-climb, gate K = 0.2 (ablation study, #930) | P + T | `54a4f3799ae88776…` | local |
| `abl_cc_best` | plain Claude Code, one session, no cap-evolve; its best evaluated candidate (ablation study, #931) | P + T | `a2b6434e76a01093…` | local |
| `abl_prompt` | cap-evolve main 75b3bcd, edit surface = system prompt only (ablation study, #932) | P | `f979201fc17b5e55…` | local |
| `abl_tools` | cap-evolve main 75b3bcd, edit surface = tools only (ablation study, #933) | T (notes only) | `d78dcf6138cd9f41…` | local |
| `abl_notrace` | cap-evolve main 75b3bcd, proposer without conversation traces (ablation study, #934) | P + T | `973ebcb4af6b3bdd…` | local |
| `abl_tracescore` | cap-evolve main 75b3bcd, proposer with traces + reward only (ablation study, #935) | P + T | `c2da5909d55fac51…` | local |

## Primary: each ablation − `abl_ref` (Holm over the primary contrasts)

| ablation arm | Δ TGC vs `abl_ref` [95% CI] | Δ SGC vs `abl_ref` [95% CI] | bootstrap p | Holm (primary) |
|---|---|---|---|---|
| `abl_cc_best` (Claude code, best evaluated candidate) | -4.4 [-9.8, 0.8] | -9.6 [-18.2, -0.7] | 0.1010 | not significant |
| `abl_prompt` (Cap evolve prompt only) | 4.5 [-1.1, 10.1] | 3.2 [-5.4, 11.8] | 0.1208 | not significant |
| `abl_tools` (Cap evolve tools only) | -6.9 [-13.7, -0.2] | -10.4 [-19.6, -1.1] | 0.0408 | not significant |
| `abl_notrace` (Cap evolve no traces) | -12.5 [-18.3, -7.0] | -15.4 [-22.5, -8.6] | 0.0000 | significant |
| `abl_tracescore` (Cap evolve traces and score only) | -14.5 [-20.5, -8.9] | -15.7 [-23.6, -8.2] | 0.0000 | significant |

## Main table (ranked by TGC; % of tasks / scenarios)

| rank | arm | TGC [95% CI] | SGC | Δ TGC vs seed [95% CI] | Δ TGC vs `abl_ref` [95% CI] | not separable from top | missing |
|---|---|---|---|---|---|---|---|
| 1 | `abl_prompt` Cap evolve prompt only | 64.0 [54.5, 72.9] | 46.1 | 29.9 [23.1, 36.7] | 4.5 [-1.1, 10.1] | yes | 0 |
| 2 | `abl_ref` Cap-evolve full (reference) | 59.5 [49.3, 69.2] | 42.9 | 25.4 [18.1, 32.5] | — | yes | 5 |
| 3 | `abl_cc_best` Claude code, best evaluated candidate | 55.1 [46.0, 64.0] | 33.2 | 21.0 [14.6, 27.5] | -4.4 [-9.8, 0.8] | no | 0 |
| 4 | `abl_tools` Cap evolve tools only | 52.6 [43.3, 62.0] | 32.5 | 18.5 [12.0, 25.2] | -6.9 [-13.7, -0.2] | no | 0 |
| 5 | `abl_notrace` Cap evolve no traces | 47.0 [37.4, 56.7] | 27.5 | 12.9 [5.8, 19.8] | -12.5 [-18.3, -7.0] | no | 0 |
| 6 | `abl_tracescore` Cap evolve traces and score only | 45.0 [35.5, 54.5] | 27.1 | 10.8 [4.0, 18.0] | -14.5 [-20.5, -8.9] | no | 0 |
| 7 | `seed` seed agent | 34.2 [27.0, 41.5] | 10.7 | — | — | no | 0 |

## By difficulty

| arm | Easy TGC | Medium TGC | Hard TGC | Easy SGC | Medium SGC | Hard SGC |
|---|---|---|---|---|---|---|
| `seed` | 53.0 | 31.2 | 19.4 | 22.1 | 7.5 | 2.9 |
| `abl_ref` | 79.6 | 65.8 | 36.5 | 71.6 | 42.5 | 17.1 |
| `abl_cc_best` | 78.2 | 55.4 | 34.0 | 61.1 | 22.5 | 16.2 |
| `abl_prompt` | 78.2 | 70.0 | 46.7 | 65.3 | 45.0 | 29.5 |
| `abl_tools` | 80.4 | 50.0 | 29.5 | 65.3 | 23.8 | 9.5 |
| `abl_notrace` | 72.6 | 47.9 | 23.2 | 51.6 | 26.2 | 6.7 |
| `abl_tracescore` | 72.3 | 41.2 | 23.2 | 58.9 | 20.0 | 3.8 |

## Stochastic behaviour (5 trials)

| arm | tasks passing 0/1/2/3/4/5 of 5 | stable | flaky | pass@1 … pass@5 | pass^1 … pass^5 | within-task var share |
|---|---|---|---|---|---|---|
| `seed` | 56/35/23/22/20/12 | 40.5 | 59.5 | 34.2 / 48.8 / 57.0 / 62.5 / 66.7 | 34.2 / 19.6 / 13.2 / 9.5 / 7.1 | 51.9 |
| `abl_ref` | 35/20/9/17/24/63 | 58.3 | 41.7 | 59.5 / 69.4 / 73.9 / 76.8 / 79.2 | 59.5 / 49.6 / 44.2 / 40.4 / 37.5 | 32.8 |
| `abl_cc_best` | 33/20/17/26/29/43 | 45.2 | 54.8 | 55.1 / 68.6 / 74.6 / 78.0 / 80.4 | 55.1 / 41.6 / 34.0 / 29.0 / 25.6 | 43.7 |
| `abl_prompt` | 26/19/9/19/31/64 | 53.6 | 46.4 | 64.0 / 75.0 / 79.5 / 82.3 / 84.5 | 64.0 / 53.1 / 46.6 / 41.8 / 38.1 | 38.1 |
| `abl_tools` | 36/20/22/25/22/43 | 47.0 | 53.0 | 52.6 / 66.0 / 72.5 / 76.2 / 78.6 | 52.6 / 39.2 / 32.3 / 28.2 / 25.6 | 43.0 |
| `abl_notrace` | 49/23/14/22/22/38 | 51.8 | 48.2 | 47.0 / 58.8 / 64.5 / 68.1 / 70.8 | 47.0 / 35.2 / 29.2 / 25.2 / 22.6 | 37.8 |
| `abl_tracescore` | 49/25/22/13/25/34 | 49.4 | 50.6 | 45.0 / 57.2 / 63.6 / 67.9 / 70.8 | 45.0 / 32.8 / 27.0 / 23.2 / 20.2 | 39.4 |

**Flakiness across arms.** Pearson correlation of TGC with flaky share over the 7 arms: -0.71. Mean flaky share by surface changed: none 59.5 (n=1), P 48.3 (n=5), T 49.6 (n=5). By difficulty (mean over arms): Easy 41.9, Medium 61.0, Hard 50.6.

## Trial-count sensitivity

| arm | TGC, first 1 | Δ vs seed, first 1 [95% CI] | TGC, first 2 | Δ vs seed, first 2 [95% CI] | TGC, first 3 | Δ vs seed, first 3 [95% CI] | TGC, first 4 | Δ vs seed, first 4 [95% CI] | TGC, first 5 | Δ vs seed, first 5 [95% CI] |
|---|---|---|---|---|---|---|---|---|---|---|
| `seed` | 38.7 | — | 35.4 | — | 35.3 | — | 35.0 | — | 34.2 | — |
| `abl_ref` | 61.9 | 23.2 [14.3, 31.5] | 62.5 | 27.1 [19.0, 35.1] | 60.7 | 25.4 [17.9, 32.7] | 60.6 | 25.6 [18.2, 32.7] | 59.5 | 25.4 [18.0, 32.4] |
| `abl_cc_best` | 56.0 | 17.3 [7.7, 26.2] | 56.0 | 20.5 [13.7, 27.4] | 54.4 | 19.0 [12.5, 25.8] | 55.4 | 20.4 [13.7, 26.6] | 55.1 | 21.0 [14.8, 27.1] |
| `abl_prompt` | 64.9 | 26.2 [16.1, 36.3] | 64.6 | 29.2 [21.4, 36.6] | 63.9 | 28.6 [21.2, 35.5] | 64.1 | 29.2 [21.7, 36.2] | 64.0 | 29.9 [22.9, 36.5] |
| `abl_tools` | 54.8 | 16.1 [6.5, 25.6] | 53.3 | 17.9 [10.4, 25.0] | 54.6 | 19.2 [12.3, 26.6] | 53.6 | 18.6 [11.9, 25.6] | 52.6 | 18.5 [12.0, 25.2] |
| `abl_notrace` | 42.9 | 4.2 [-4.2, 12.5] | 45.2 | 9.8 [1.5, 17.9] | 47.8 | 12.5 [4.6, 19.8] | 47.3 | 12.4 [5.1, 19.5] | 47.0 | 12.9 [5.7, 19.6] |
| `abl_tracescore` | 47.6 | 8.9 [-0.6, 18.5] | 45.8 | 10.4 [3.0, 18.2] | 44.8 | 9.5 [2.2, 16.9] | 44.6 | 9.7 [2.2, 17.0] | 45.0 | 10.8 [4.3, 17.6] |

(The trial-count CIs use 2,000 bootstrap resamples; the main tables use 10,000.)

## All 21 pairs (row − column; Holm over all pairs, secondary)

| pair | Δ TGC [95% CI] | Δ SGC [95% CI] | bootstrap p | Holm |
|---|---|---|---|---|
| seed − abl_ref | -25.4 [-32.5, -18.1] | -32.1 [-42.1, -22.5] | 0.0000 | yes |
| seed − abl_cc_best | -21.0 [-27.5, -14.6] | -22.5 [-31.4, -13.9] | 0.0000 | yes |
| seed − abl_prompt | -29.9 [-36.7, -23.1] | -35.4 [-44.3, -26.4] | 0.0000 | yes |
| seed − abl_tools | -18.5 [-25.2, -12.0] | -21.8 [-30.7, -13.6] | 0.0000 | yes |
| seed − abl_notrace | -12.9 [-19.8, -5.8] | -16.8 [-23.9, -10.4] | 0.0000 | yes |
| seed − abl_tracescore | -10.8 [-18.0, -4.0] | -16.4 [-25.4, -8.6] | 0.0016 | yes |
| abl_ref − abl_cc_best | 4.4 [-0.8, 9.8] | 9.6 [0.7, 18.2] | 0.1010 | no |
| abl_ref − abl_prompt | -4.5 [-10.1, 1.1] | -3.2 [-11.8, 5.4] | 0.1208 | no |
| abl_ref − abl_tools | 6.9 [0.2, 13.7] | 10.4 [1.1, 19.6] | 0.0408 | no |
| abl_ref − abl_notrace | 12.5 [7.0, 18.3] | 15.4 [8.6, 22.5] | 0.0000 | yes |
| abl_ref − abl_tracescore | 14.5 [8.9, 20.5] | 15.7 [8.2, 23.6] | 0.0000 | yes |
| abl_cc_best − abl_prompt | -8.9 [-14.4, -3.7] | -12.9 [-20.7, -5.0] | 0.0008 | yes |
| abl_cc_best − abl_tools | 2.5 [-3.1, 8.0] | 0.7 [-6.4, 7.5] | 0.3732 | no |
| abl_cc_best − abl_notrace | 8.1 [2.5, 13.7] | 5.7 [-1.4, 12.9] | 0.0050 | yes |
| abl_cc_best − abl_tracescore | 10.1 [4.8, 15.7] | 6.1 [-1.1, 13.6] | 0.0000 | yes |
| abl_prompt − abl_tools | 11.4 [5.0, 18.0] | 13.6 [5.0, 22.1] | 0.0002 | yes |
| abl_prompt − abl_notrace | 17.0 [11.3, 22.7] | 18.6 [10.0, 27.1] | 0.0000 | yes |
| abl_prompt − abl_tracescore | 19.0 [13.0, 25.5] | 18.9 [10.4, 27.5] | 0.0000 | yes |
| abl_tools − abl_notrace | 5.6 [-1.2, 12.3] | 5.0 [-2.9, 12.9] | 0.1028 | no |
| abl_tools − abl_tracescore | 7.6 [1.2, 14.0] | 5.4 [-2.5, 13.6] | 0.0212 | no |
| abl_notrace − abl_tracescore | 2.0 [-2.3, 6.3] | 0.4 [-5.7, 6.1] | 0.3524 | no |

## Agent tokens, steps, latency and infra (per episode)

| arm | prompt tok/ep (mean / p50 / p90) | completion tok/ep (mean / p50 / p90) | steps (mean) | s/ep (mean / p50 / p90) | max prompt | step-cap | token-cap | ctx-exceeded | collateral | infra retries | pass fraction |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `seed` | 90,875 / 61,338 / 190,366 | 5,746 / 4,060 / 12,722 | 12.6 | 309 / 217 / 676 | 22,786 | 4 | 0 | 0 | 30 | 11 | 69.4 |
| `abl_ref` | 124,824 / 85,758 / 264,024 | 6,763 / 4,186 / 15,996 | 10.5 | 366 / 234 / 866 | 30,061 | 4 | 0 | 0 | 28 | 44 | 81.9 |
| `abl_cc_best` | 98,070 / 77,040 / 193,654 | 5,826 / 4,698 / 11,819 | 10.7 | 316 / 251 / 641 | 21,889 | 1 | 0 | 0 | 24 | 2 | 77.0 |
| `abl_prompt` | 126,242 / 103,880 / 233,999 | 5,618 / 4,309 / 11,780 | 11.6 | 309 / 229 / 629 | 23,933 | 1 | 0 | 0 | 26 | 7 | 82.5 |
| `abl_tools` | 89,127 / 58,821 / 185,854 | 5,881 / 4,259 / 13,080 | 11.7 | 316 / 230 / 689 | 22,957 | 5 | 0 | 0 | 21 | 16 | 74.7 |
| `abl_notrace` | 105,901 / 82,351 / 219,909 | 7,668 / 6,040 / 15,967 | 10.6 | 418 / 326 / 857 | 22,348 | 1 | 0 | 0 | 26 | 21 | 70.1 |
| `abl_tracescore` | 95,021 / 69,823 / 192,344 | 5,419 / 3,644 / 11,630 | 8.0 | 301 / 200 / 664 | 28,459 | 0 | 0 | 0 | 27 | 10 | 69.4 |

Agent cost: n/a (RITS is unpriced); agent tokens above stand in for it. No optimizer was called.

## The ablation study's own window (context)

| arm | this window TGC (5 trials) | other window TGC (2 trials) | other window |
|---|---|---|---|
| `seed` | 34.2 | 36.3 | other window: ablation study's final window (2026-10-27, 2 trials, seeds 5000+k) |
| `abl_ref` | 59.5 | 62.5 | other window: ablation study's final window (2026-10-27, 2 trials, seeds 5000+k) |
| `abl_cc_best` | 55.1 | 55.7 | other window: ablation study's final window (2026-10-27, 2 trials, seeds 5000+k) |
| `abl_prompt` | 64.0 | 61.6 | other window: ablation study's final window (2026-10-27, 2 trials, seeds 5000+k) |
| `abl_tools` | 52.6 | 51.2 | other window: ablation study's final window (2026-10-27, 2 trials, seeds 5000+k) |
| `abl_notrace` | 47.0 | 49.7 | other window: ablation study's final window (2026-10-27, 2 trials, seeds 5000+k) |
| `abl_tracescore` | 45.0 | 45.2 | other window: ablation study's final window (2026-10-27, 2 trials, seeds 5000+k) |

Context only, never a paired comparison. The seed's TGC in the other windows: ablation window 36.3.

**Deviations and disclosures.** Protocol: `docs/TEST_ALL.md` with the ablation champions as its arms (plan `docs/TEST_ABL.md` §15). `abl_cc` (seed-identical) was excluded. The gate arms are scored in a second window after this one (cross-window comparisons, labelled). Every issue and decision during execution is in `docs/TEST_ABL_ADDENDUM.md` and the ledger `docs/TEST_ABL_STATUS.md`.

**What these numbers cannot support.** Each champion came from **one** search with one search seed, so every ablation − reference contrast mixes the ablated factor with search randomness. This is a **single** test window, with 5 trials per task. In earlier AppWorld windows, identical artifacts drifted 4 to 6 TGC points between windows, and there is no seed-identical arm here to measure the within-window part (`abl_cc` was excluded). Differences of a few points are therefore not resolved, and a null result is a bound, not evidence of no effect. `abl_cc_best` was chosen by its search score (selection-biased). These are statements about the **artifacts**, not about the methods in general.
