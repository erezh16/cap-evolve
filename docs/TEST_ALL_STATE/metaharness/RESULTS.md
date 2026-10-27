## Results — Meta-Harness (`metaharness`)

**Setup.** AppWorld `42b5bcf`, `test_normal` (168 tasks, 56 scenarios; Easy 57 / Medium 48 / Hard 63); agent `openai/gpt-oss-120b-a100` on RITS (reasoning medium, temperature 0, the official simplified ReAct code agent, 50 steps, 100K completion tokens per task, 30-min wall cap); no optimizer. One shuffled window of 10,920 cells (13 arms × 168 × 5 trials, trial seeds 7000+k, order seed 2026102501, order sha256 `725f659aefadafd4…`). Code: branch `test-all`.

| arm | method (source evaluation) | surfaces searched | surfaces changed vs seed | hash rule | hash | source |
|---|---|---|---|---|---|---|
| `seed` | the unmodified AppWorld ReAct agent | none | none | S | `85a0da9cec2206a7…` | local |
| `altk` | ALTK-Evolve v1.3.0, retrieval dose (smoke test, 2026-10-13) | M (retrieval) | M (retrieval) | B | `b2b3703744f29212…` | box |
| `ace` | ACE, offline, no ground truth (2026-10-14) | M | M | F | `e92fbff4b652aaaa…` | box |
| `gepa` | GEPA v0.1.4, prompt + tools (eval 5, 2026-10-18) | P + T | P | F | `26403e2c5e50ed92…` | box |
| `skillopt` | SkillOpt ae2f766 (eval 5) | P + T + M | M | F | `8314b3340e1c0d85…` | box |
| `wikiskill` | WikiSkill (re-implementation; eval 5) | P + T + M | M | F | `3895752eb7b9759b…` | box |
| `evoskill` | EvoSkill v1.3.0 (eval 5) | P + T + M | M | F | `23f5f8f76cf504ae…` | box |
| `metaharness` | Meta-Harness 8123cca (eval 5) | P + T | P + T | F | `ea0f2f68e37742b8…` | box |
| `harnesslens` | HarnessLens 369a5c8 (REST, 2026-10-20); inert, equals the seed | none | none | S | `85a0da9cec2206a7…` | local |
| `miprov2` | MIPROv2, DSPy 3.4.1 (REST) | P | P | S | `a4ff3a502879f520…` | local |
| `trace2skill` | Trace2Skill 3d0b52a (REST) | M | M | S | `a6b03deb2a044ed4…` | local |
| `gepa_full` | GEPA v0.1.4, full mode: prompt + per-app tool descriptions (REST) | P + T | P + T | S | `eb3d11d38bad1193…` | local |
| `cape_k02` | cap-evolve Improvement 2, commit 3db96a0, hill-climb with gate K = 0.2 (CE3, 2026-10-24) | P + T | P + T | S | `e0ec3d94752bd3a2…` | local |

**This arm.** TGC **50.7** [41.9, 59.5], SGC **27.9**; rank **10 of 13** (separable from the top arm). Δ vs seed: TGC 18.1 [12.5, 24.0], SGC 17.5 [10.0, 25.7] (Holm over 78 pairs: significant).

**All 13 competitors** (ranked by TGC; Δ vs the seed with scenario-clustered bootstrap CIs)

| rank | competitor | arm | TGC [95% CI] | SGC | Δ TGC vs seed [95% CI] | Δ SGC vs seed [95% CI] | Holm (78 pairs) | not separable from top | missing |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Trace2Skill | `trace2skill` | 66.3 [56.8, 75.5] | 49.3 | 33.7 [27.6, 39.9] | 38.9 [30.0, 48.2] | yes | yes | 0 |
| 2 | Cap-Evolve-impr2 K=0.2 | `cape_k02` | 65.6 [55.6, 75.0] | 49.6 | 33.0 [24.6, 41.0] | 39.3 [28.6, 49.6] | yes | yes | 0 |
| 3 | GEPA-Full | `gepa_full` | 63.5 [53.6, 72.9] | 47.1 | 30.8 [23.7, 37.9] | 36.8 [27.1, 46.8] | yes | yes | 0 |
| 4 | SkillOpt | `skillopt` | 61.5 [51.9, 70.7] | 43.6 | 28.9 [22.4, 35.4] | 33.2 [24.3, 42.5] | yes | yes | 0 |
| 5 | ACE | `ace` | 61.5 [51.7, 71.0] | 45.0 | 28.9 [21.8, 35.7] | 34.6 [25.0, 44.6] | yes | yes | 0 |
| 6 | GEPA | `gepa` | 60.5 [50.5, 70.2] | 43.9 | 27.9 [21.0, 35.0] | 33.6 [23.9, 43.9] | yes | no | 0 |
| 7 | EvoSkill | `evoskill` | 58.9 [49.4, 68.0] | 40.0 | 26.3 [19.9, 32.7] | 29.6 [20.4, 39.3] | yes | no | 0 |
| 8 | WikiSkill | `wikiskill` | 56.8 [47.7, 65.6] | 33.9 | 24.2 [18.6, 29.8] | 23.6 [16.1, 31.4] | yes | no | 0 |
| 9 | MIPROv2 | `miprov2` | 55.8 [45.8, 65.7] | 37.9 | 23.2 [16.3, 30.2] | 27.5 [18.6, 36.8] | yes | no | 0 |
| 10 | Meta-Harness | `metaharness` | 50.7 [41.9, 59.5] | 27.9 | 18.1 [12.5, 24.0] | 17.5 [10.0, 25.7] | yes | no | 0 |
| 11 | ALTK-Evolve | `altk` | 41.9 [33.0, 51.1] | 21.8 | 9.3 [3.5, 15.4] | 11.4 [3.9, 19.6] | no | no | 0 |
| 12 | HarnessLens | `harnesslens` | 34.2 [26.8, 42.1] | 12.1 | 1.5 [-1.7, 4.6] | 1.8 [-2.1, 6.1] | no | no | 0 |
| 13 | seed agent | `seed` | 32.6 [25.6, 40.0] | 10.4 | — | — | — | no | 0 |

| difficulty | TGC | SGC |
|---|---|---|
| Easy (n=57) | 70.2 | 50.5 |
| Medium (n=48) | 50.8 | 26.2 |
| Hard (n=63) | 33.0 | 8.6 |

**Δ vs every other arm** (unadjusted 95% CI; Holm over the 78 pairs):

| vs | Δ TGC [95% CI] | Δ SGC [95% CI] | Holm |
|---|---|---|---|
| `seed` | 18.1 [12.5, 24.0] | 17.5 [10.0, 25.7] | yes |
| `altk` | 8.8 [2.3, 15.6] | 6.1 [-2.1, 14.6] | no |
| `ace` | -10.8 [-17.9, -4.2] | -17.1 [-26.8, -7.9] | no |
| `gepa` | -9.8 [-15.4, -4.3] | -16.1 [-23.6, -8.9] | yes |
| `skillopt` | -10.8 [-16.8, -5.1] | -15.7 [-22.5, -9.3] | yes |
| `wikiskill` | -6.1 [-11.4, -0.6] | -6.1 [-13.2, 0.7] | no |
| `evoskill` | -8.2 [-14.2, -2.6] | -12.1 [-19.6, -5.0] | no |
| `harnesslens` | 16.5 [11.3, 22.0] | 15.7 [8.6, 23.6] | yes |
| `miprov2` | -5.1 [-8.9, -1.3] | -10.0 [-14.6, -5.4] | no |
| `trace2skill` | -15.6 [-21.0, -10.2] | -21.4 [-29.3, -13.9] | yes |
| `gepa_full` | -12.7 [-18.7, -7.1] | -19.3 [-27.5, -11.4] | yes |
| `cape_k02` | -14.9 [-21.2, -8.6] | -21.8 [-30.0, -13.6] | yes |

**Stochastic behaviour (5 trials).** Tasks passing 0/1/2/3/4/5 of 5: 40/15/27/21/31/34; stable 44.0%, flaky 56.0%. pass@k: 50.7 / 64.8 / 71.0 / 74.4 / 76.2; pass^k: 50.7 / 36.7 / 28.9 / 23.9 / 20.2. Within-task share of variance 45.0%. TGC from the first 1..5 trials: 50.6, 50.0, 49.8, 50.9, 50.7.

**Agent cost.** Prompt tokens/episode 104,937 (p90 207,872), completion 6,698, steps 14.1, 293 s/episode (p90 600); max prompt 19,474; step-cap 8, token-cap 0, context-exceeded 0; infra retries 8, missing cells 0. Cost: n/a (unpriced).

**Other window (context, not paired):** TGC 52.1 (other window: eval 5 window (2026-10-19)).

**Window noise check (`harnesslens − seed`, two byte-identical artifacts):** Δ TGC 1.5 [-1.7, 4.6], Δ SGC 1.8 [-2.1, 6.1].

Full tables (all arms, the 78-pair matrix): [`docs/TEST_ALL_STATE/final/RESULTS.md`](https://github.com/erezh16/cap-evolve/blob/test-all/docs/TEST_ALL_STATE/final/RESULTS.md).

**Deviations and disclosures.** ACE's playbook (55,513 chars) is over the shared lint's 30,000-char memory limit and was scored as frozen (D6). Surfaces: §3's column is 'surfaces searched'; the measured 'surfaces changed vs the seed' differ for gepa (P only), skillopt, wikiskill and evoskill (M only) (D10). The executing session's deny rules were merged into the base worktree's settings, since the session ran from there (D11). Other deviations, if any, are in the ledger (`docs/TEST_ALL_STATUS.md`).

**What these numbers cannot support.** Each champion came from **one** search with one search seed; the methods differ in the surfaces they may change, in search budget and in their own settings; and this is a **single** test window (window-to-window drift of identical artifacts was 4 to 6 TGC points in earlier evaluations; here the `harnesslens − seed` noise check measures the within-window part). So the ranking compares 13 **artifacts** under one test condition. It does not rank the methods in general.
