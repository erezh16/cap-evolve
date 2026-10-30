## Results — Cap-evolve full (reference) (`abl_ref`)

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

**This arm.** TGC **59.5** [49.3, 69.2], SGC **42.9**; rank **2 of 7** (not separable from the top arm). Δ vs seed: TGC 25.4 [18.1, 32.5], SGC 32.1 [22.5, 42.1]. This is the reference arm: every primary contrast is measured against it.

**All arms** (ranked by TGC)

| rank | arm | TGC [95% CI] | SGC | Δ TGC vs seed [95% CI] | Δ TGC vs `abl_ref` [95% CI] | not separable from top | missing |
|---|---|---|---|---|---|---|---|
| 1 | `abl_prompt` Cap evolve prompt only | 64.0 [54.5, 72.9] | 46.1 | 29.9 [23.1, 36.7] | 4.5 [-1.1, 10.1] | yes | 0 |
| 2 | `abl_ref` Cap-evolve full (reference) | 59.5 [49.3, 69.2] | 42.9 | 25.4 [18.1, 32.5] | — | yes | 5 |
| 3 | `abl_cc_best` Claude code, best evaluated candidate | 55.1 [46.0, 64.0] | 33.2 | 21.0 [14.6, 27.5] | -4.4 [-9.8, 0.8] | no | 0 |
| 4 | `abl_tools` Cap evolve tools only | 52.6 [43.3, 62.0] | 32.5 | 18.5 [12.0, 25.2] | -6.9 [-13.7, -0.2] | no | 0 |
| 5 | `abl_notrace` Cap evolve no traces | 47.0 [37.4, 56.7] | 27.5 | 12.9 [5.8, 19.8] | -12.5 [-18.3, -7.0] | no | 0 |
| 6 | `abl_tracescore` Cap evolve traces and score only | 45.0 [35.5, 54.5] | 27.1 | 10.8 [4.0, 18.0] | -14.5 [-20.5, -8.9] | no | 0 |
| 7 | `seed` seed agent | 34.2 [27.0, 41.5] | 10.7 | — | — | no | 0 |

| difficulty | TGC | SGC |
|---|---|---|
| Easy (n=57) | 79.6 | 71.6 |
| Medium (n=48) | 65.8 | 42.5 |
| Hard (n=63) | 36.5 | 17.1 |

**Stochastic behaviour (5 trials).** Tasks passing 0/1/2/3/4/5 of 5: 35/20/9/17/24/63; stable 58.3%, flaky 41.7%. pass@k: 59.5 / 69.4 / 73.9 / 76.8 / 79.2; pass^k: 59.5 / 49.6 / 44.2 / 40.4 / 37.5. Within-task share of variance 32.8%. TGC from the first 1..5 trials: 61.9, 62.5, 60.7, 60.6, 59.5.

**Agent cost.** Prompt tokens/episode 124,824 (p90 264,024), completion 6,763, steps 10.5, 366 s/episode (p90 866); max prompt 30,061; step-cap 4, token-cap 0, context-exceeded 0; infra retries 44, missing cells 5. Cost: n/a (RITS is unpriced; no optimizer).

**The ablation study's own window (context, not paired):** TGC 62.5 (other window: ablation study's final window (2026-10-27, 2 trials, seeds 5000+k)). This window's TGC from its first 2 trials: 62.5.

Full tables (all arms, every pair): [`docs/TEST_ABL_STATE/final/RESULTS.md`](https://github.com/erezh16/cap-evolve/blob/test-abl/docs/TEST_ABL_STATE/final/RESULTS.md).

**Deviations and disclosures.** Protocol: `docs/TEST_ALL.md` with the ablation champions as its arms (plan `docs/TEST_ABL.md` §15). `abl_cc` (seed-identical) was excluded. The gate arms are scored in a second window after this one (cross-window comparisons, labelled). Every issue and decision during execution is in `docs/TEST_ABL_ADDENDUM.md` and the ledger `docs/TEST_ABL_STATUS.md`.

**What these numbers cannot support.** Each champion came from **one** search with one search seed, so every ablation − reference contrast mixes the ablated factor with search randomness. This is a **single** test window, with 5 trials per task. In earlier AppWorld windows, identical artifacts drifted 4 to 6 TGC points between windows, and there is no seed-identical arm here to measure the within-window part (`abl_cc` was excluded). Differences of a few points are therefore not resolved, and a null result is a bound, not evidence of no effect. `abl_cc_best` was chosen by its search score (selection-biased). These are statements about the **artifacts**, not about the methods in general.
