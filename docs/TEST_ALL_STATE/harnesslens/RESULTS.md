## Results — HarnessLens (`harnesslens`)

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

**This arm.** TGC **34.2** [26.8, 42.1], SGC **12.1**; rank **12 of 13** (separable from the top arm). Δ vs seed: TGC 1.5 [-1.7, 4.6], SGC 1.8 [-2.1, 6.1] (Holm over 78 pairs: not significant).

**Result for this arm:** HarnessLens's artifact is byte-identical to the seed, so its Δ vs the seed is the window's noise check. **Window noise check (`harnesslens − seed`, two byte-identical artifacts):** Δ TGC 1.5 [-1.7, 4.6], Δ SGC 1.8 [-2.1, 6.1].

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
| Easy (n=57) | 59.3 | 28.4 |
| Medium (n=48) | 25.0 | 5.0 |
| Hard (n=63) | 18.4 | 2.9 |

**Δ vs every other arm** (unadjusted 95% CI; Holm over the 78 pairs):

| vs | Δ TGC [95% CI] | Δ SGC [95% CI] | Holm |
|---|---|---|---|
| `seed` | 1.5 [-1.7, 4.6] | 1.8 [-2.1, 6.1] | no |
| `altk` | -7.7 [-13.3, -2.4] | -9.6 [-17.5, -2.5] | no |
| `ace` | -27.4 [-34.4, -20.4] | -32.9 [-43.2, -22.9] | yes |
| `gepa` | -26.3 [-33.3, -19.4] | -31.8 [-41.8, -22.1] | yes |
| `skillopt` | -27.4 [-34.0, -21.0] | -31.4 [-40.7, -22.5] | yes |
| `wikiskill` | -22.6 [-28.3, -16.8] | -21.8 [-30.0, -13.9] | yes |
| `evoskill` | -24.8 [-31.2, -18.6] | -27.9 [-37.1, -18.9] | yes |
| `metaharness` | -16.5 [-22.0, -11.3] | -15.7 [-23.6, -8.6] | yes |
| `miprov2` | -21.7 [-28.6, -14.9] | -25.7 [-35.0, -17.1] | yes |
| `trace2skill` | -32.1 [-38.6, -25.6] | -37.1 [-46.4, -27.9] | yes |
| `gepa_full` | -29.3 [-36.2, -22.5] | -35.0 [-44.6, -25.4] | yes |
| `cape_k02` | -31.4 [-39.0, -23.5] | -37.5 [-47.9, -26.8] | yes |

**Stochastic behaviour (5 trials).** Tasks passing 0/1/2/3/4/5 of 5: 53/34/36/14/16/15; stable 40.5%, flaky 59.5%. pass@k: 34.2 / 49.0 / 58.2 / 64.4 / 68.5; pass^k: 34.2 / 19.3 / 13.6 / 10.8 / 8.9. Within-task share of variance 52.9%. TGC from the first 1..5 trials: 37.5, 36.0, 35.7, 35.0, 34.2.

**Agent cost.** Prompt tokens/episode 93,118 (p90 194,013), completion 6,116, steps 12.7, 266 s/episode (p90 542); max prompt 20,228; step-cap 7, token-cap 0, context-exceeded 0; infra retries 5, missing cells 0. Cost: n/a (unpriced).

**Other window (context, not paired):** TGC 34.5 (other window: REST window (2026-10-21)).

**Window noise check (`harnesslens − seed`, two byte-identical artifacts):** Δ TGC 1.5 [-1.7, 4.6], Δ SGC 1.8 [-2.1, 6.1].

Full tables (all arms, the 78-pair matrix): [`docs/TEST_ALL_STATE/final/RESULTS.md`](https://github.com/erezh16/cap-evolve/blob/test-all/docs/TEST_ALL_STATE/final/RESULTS.md).

**Deviations and disclosures.** ACE's playbook (55,513 chars) is over the shared lint's 30,000-char memory limit and was scored as frozen (D6). Surfaces: §3's column is 'surfaces searched'; the measured 'surfaces changed vs the seed' differ for gepa (P only), skillopt, wikiskill and evoskill (M only) (D10). The executing session's deny rules were merged into the base worktree's settings, since the session ran from there (D11). Other deviations, if any, are in the ledger (`docs/TEST_ALL_STATUS.md`).

**What these numbers cannot support.** Each champion came from **one** search with one search seed; the methods differ in the surfaces they may change, in search budget and in their own settings; and this is a **single** test window (window-to-window drift of identical artifacts was 4 to 6 TGC points in earlier evaluations; here the `harnesslens − seed` noise check measures the within-window part). So the ranking compares 13 **artifacts** under one test condition. It does not rank the methods in general.
