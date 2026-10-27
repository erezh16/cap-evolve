# AppWorld TEST_ALL results: 13 arms, test_normal × 5 trials, one window

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

## Main table (ranked by TGC; % of tasks / scenarios)

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

**Window noise check (`harnesslens − seed`, two byte-identical artifacts):** Δ TGC 1.5 [-1.7, 4.6], Δ SGC 1.8 [-2.1, 6.1].

## By difficulty

| arm | Easy TGC | Medium TGC | Hard TGC | Easy SGC | Medium SGC | Hard SGC |
|---|---|---|---|---|---|---|
| `seed` | 52.3 | 28.8 | 17.8 | 18.9 | 8.8 | 3.8 |
| `altk` | 70.2 | 32.5 | 23.5 | 47.4 | 8.8 | 8.6 |
| `ace` | 88.4 | 67.5 | 32.7 | 78.9 | 40.0 | 18.1 |
| `gepa` | 80.0 | 61.3 | 42.2 | 69.5 | 45.0 | 20.0 |
| `skillopt` | 80.7 | 70.0 | 37.8 | 68.4 | 50.0 | 16.2 |
| `wikiskill` | 78.2 | 62.9 | 32.7 | 56.8 | 33.8 | 13.3 |
| `evoskill` | 80.4 | 61.7 | 37.5 | 68.4 | 38.8 | 15.2 |
| `metaharness` | 70.2 | 50.8 | 33.0 | 50.5 | 26.2 | 8.6 |
| `harnesslens` | 59.3 | 25.0 | 18.4 | 28.4 | 5.0 | 2.9 |
| `miprov2` | 76.8 | 54.2 | 38.1 | 65.3 | 30.0 | 19.0 |
| `trace2skill` | 84.9 | 73.3 | 44.1 | 75.8 | 48.8 | 25.7 |
| `gepa_full` | 83.2 | 67.5 | 42.5 | 71.6 | 48.8 | 23.8 |
| `cape_k02` | 82.5 | 72.1 | 45.4 | 70.5 | 53.8 | 27.6 |

## Stochastic behaviour (§11.3)

| arm | tasks passing 0/1/2/3/4/5 of 5 | stable | flaky | pass@1 … pass@5 | pass^1 … pass^5 | within-task var share |
|---|---|---|---|---|---|---|
| `seed` | 58/27/37/21/15/10 | 40.5 | 59.5 | 32.6 / 48.0 / 56.8 / 62.3 / 65.5 | 32.6 / 17.3 / 10.8 / 7.7 / 6.0 | 55.9 |
| `altk` | 50/30/20/18/22/28 | 46.4 | 53.6 | 41.9 / 54.9 / 61.9 / 66.7 / 70.2 | 41.9 / 28.9 / 23.0 / 19.3 / 16.7 | 42.6 |
| `ace` | 34/15/12/18/21/68 | 60.7 | 39.3 | 61.5 / 71.2 / 75.5 / 78.0 / 79.8 | 61.5 / 51.9 / 46.5 / 43.0 / 40.5 | 32.6 |
| `gepa` | 34/16/15/16/21/66 | 59.5 | 40.5 | 60.5 / 70.4 / 75.1 / 77.9 / 79.8 | 60.5 / 50.5 / 45.2 / 41.8 / 39.3 | 33.3 |
| `skillopt` | 31/21/8/19/22/67 | 58.3 | 41.7 | 61.5 / 71.5 / 76.1 / 79.0 / 81.5 | 61.5 / 51.6 / 46.2 / 42.5 / 39.9 | 33.6 |
| `wikiskill` | 32/17/17/28/28/46 | 46.4 | 53.6 | 56.8 / 70.2 / 75.9 / 78.9 / 81.0 | 56.8 / 43.4 / 35.7 / 30.7 / 27.4 | 43.7 |
| `evoskill` | 32/18/18/19/21/60 | 54.8 | 45.2 | 58.9 / 70.2 / 75.6 / 78.8 / 81.0 | 58.9 / 47.7 / 41.8 / 38.2 / 35.7 | 37.2 |
| `metaharness` | 40/15/27/21/31/34 | 44.0 | 56.0 | 50.7 / 64.8 / 71.0 / 74.4 / 76.2 | 50.7 / 36.7 / 28.9 / 23.9 / 20.2 | 45.0 |
| `harnesslens` | 53/34/36/14/16/15 | 40.5 | 59.5 | 34.2 / 49.0 / 58.2 / 64.4 / 68.5 | 34.2 / 19.3 / 13.6 / 10.8 / 8.9 | 52.9 |
| `miprov2` | 39/21/14/11/28/55 | 56.0 | 44.0 | 55.8 / 66.1 / 71.0 / 74.3 / 76.8 | 55.8 / 45.5 / 40.1 / 36.1 / 32.7 | 33.4 |
| `trace2skill` | 28/13/11/17/24/75 | 61.3 | 38.7 | 66.3 / 75.7 / 79.6 / 81.8 / 83.3 | 66.3 / 56.9 / 51.4 / 47.5 / 44.6 | 33.7 |
| `gepa_full` | 30/15/15/14/24/70 | 59.5 | 40.5 | 63.5 / 73.3 / 77.7 / 80.4 / 82.1 | 63.5 / 53.6 / 48.2 / 44.5 / 41.7 | 33.9 |
| `cape_k02` | 27/16/16/7/28/74 | 60.1 | 39.9 | 65.6 / 74.9 / 79.2 / 82.0 / 83.9 | 65.6 / 56.2 / 51.1 / 47.4 / 44.0 | 33.1 |

**Flakiness across arms.** Pearson correlation of TGC with flaky share over the 13 arms: -0.91. Mean flaky share by surface changed: none 59.5 (n=2), M 45.3 (n=6), P 44.2 (n=5), T 45.4 (n=3). By difficulty (mean over arms): Easy 37.2, Medium 57.5, Hard 48.0.

## Trial-count sensitivity

| arm | TGC, first 1 | Δ vs seed, first 1 [95% CI] | TGC, first 2 | Δ vs seed, first 2 [95% CI] | TGC, first 3 | Δ vs seed, first 3 [95% CI] | TGC, first 4 | Δ vs seed, first 4 [95% CI] | TGC, first 5 | Δ vs seed, first 5 [95% CI] |
|---|---|---|---|---|---|---|---|---|---|---|
| `seed` | 29.8 | — | 29.2 | — | 31.5 | — | 31.5 | — | 32.6 | — |
| `altk` | 39.3 | 9.5 [1.2, 18.5] | 39.6 | 10.4 [3.0, 18.2] | 41.3 | 9.7 [2.6, 16.7] | 41.8 | 10.3 [4.2, 16.8] | 41.9 | 9.3 [3.3, 15.1] |
| `ace` | 64.3 | 34.5 [25.6, 44.0] | 61.3 | 32.1 [24.1, 39.9] | 61.1 | 29.6 [22.2, 36.9] | 61.8 | 30.2 [23.2, 37.1] | 61.5 | 28.9 [22.0, 35.4] |
| `gepa` | 60.1 | 30.4 [20.8, 39.3] | 59.5 | 30.4 [21.4, 39.6] | 59.5 | 28.0 [19.6, 36.5] | 60.4 | 28.9 [21.3, 36.8] | 60.5 | 27.9 [20.7, 35.1] |
| `skillopt` | 57.1 | 27.4 [19.6, 35.7] | 61.3 | 32.1 [24.7, 39.9] | 60.9 | 29.4 [22.6, 35.9] | 61.3 | 29.8 [23.1, 36.3] | 61.5 | 28.9 [22.6, 35.5] |
| `wikiskill` | 52.4 | 22.6 [13.7, 31.0] | 53.0 | 23.8 [16.7, 30.7] | 54.6 | 23.0 [16.1, 29.8] | 56.8 | 25.3 [18.8, 31.7] | 56.8 | 24.2 [18.6, 29.8] |
| `evoskill` | 60.7 | 31.0 [22.6, 39.3] | 60.7 | 31.5 [23.8, 39.3] | 59.5 | 28.0 [21.0, 34.9] | 58.6 | 27.1 [20.5, 33.8] | 58.9 | 26.3 [20.0, 33.0] |
| `metaharness` | 50.6 | 20.8 [11.3, 30.4] | 50.0 | 20.8 [13.4, 28.3] | 49.8 | 18.3 [11.5, 25.0] | 50.9 | 19.3 [13.1, 25.6] | 50.7 | 18.1 [12.6, 23.9] |
| `harnesslens` | 37.5 | 7.7 [0.6, 14.9] | 36.0 | 6.8 [1.2, 12.5] | 35.7 | 4.2 [0.0, 8.1] | 35.0 | 3.4 [-0.1, 7.0] | 34.2 | 1.5 [-1.5, 4.8] |
| `miprov2` | 57.1 | 27.4 [18.5, 36.9] | 57.7 | 28.6 [20.2, 36.6] | 57.5 | 26.0 [18.1, 33.3] | 57.0 | 25.4 [17.9, 32.6] | 55.8 | 23.2 [16.1, 30.0] |
| `trace2skill` | 67.3 | 37.5 [28.0, 47.0] | 67.6 | 38.4 [30.7, 46.4] | 66.1 | 34.5 [28.2, 41.3] | 65.8 | 34.2 [27.8, 40.8] | 66.3 | 33.7 [27.7, 40.2] |
| `gepa_full` | 63.1 | 33.3 [24.4, 42.3] | 62.8 | 33.6 [25.3, 42.0] | 63.9 | 32.3 [25.0, 40.1] | 63.2 | 31.7 [24.3, 39.1] | 63.5 | 30.8 [23.8, 38.0] |
| `cape_k02` | 62.5 | 32.7 [22.6, 42.3] | 64.9 | 35.7 [26.5, 44.6] | 64.7 | 33.1 [24.6, 41.5] | 65.2 | 33.6 [25.4, 41.8] | 65.6 | 33.0 [24.9, 41.1] |

(The trial-count CIs use 2,000 bootstrap resamples; the main tables use 10,000.)

## All 78 pairs (row − column; Holm over the 78 Δ TGC)

| pair | Δ TGC [95% CI] | Δ SGC [95% CI] | bootstrap p | Holm |
|---|---|---|---|---|
| seed − altk | -9.3 [-15.4, -3.5] | -11.4 [-19.6, -3.9] | 0.0020 | no |
| seed − ace | -28.9 [-35.7, -21.8] | -34.6 [-44.6, -25.0] | 0.0000 | yes |
| seed − gepa | -27.9 [-35.0, -21.0] | -33.6 [-43.9, -23.9] | 0.0000 | yes |
| seed − skillopt | -28.9 [-35.4, -22.4] | -33.2 [-42.5, -24.3] | 0.0000 | yes |
| seed − wikiskill | -24.2 [-29.8, -18.6] | -23.6 [-31.4, -16.1] | 0.0000 | yes |
| seed − evoskill | -26.3 [-32.7, -19.9] | -29.6 [-39.3, -20.4] | 0.0000 | yes |
| seed − metaharness | -18.1 [-24.0, -12.5] | -17.5 [-25.7, -10.0] | 0.0000 | yes |
| seed − harnesslens | -1.5 [-4.6, 1.7] | -1.8 [-6.1, 2.1] | 0.3334 | no |
| seed − miprov2 | -23.2 [-30.2, -16.3] | -27.5 [-36.8, -18.6] | 0.0000 | yes |
| seed − trace2skill | -33.7 [-39.9, -27.6] | -38.9 [-48.2, -30.0] | 0.0000 | yes |
| seed − gepa_full | -30.8 [-37.9, -23.7] | -36.8 [-46.8, -27.1] | 0.0000 | yes |
| seed − cape_k02 | -33.0 [-41.0, -24.6] | -39.3 [-49.6, -28.6] | 0.0000 | yes |
| altk − ace | -19.6 [-26.3, -13.0] | -23.2 [-33.2, -13.6] | 0.0000 | yes |
| altk − gepa | -18.6 [-26.0, -11.7] | -22.1 [-32.5, -12.1] | 0.0000 | yes |
| altk − skillopt | -19.6 [-26.2, -13.2] | -21.8 [-31.1, -12.5] | 0.0000 | yes |
| altk − wikiskill | -14.9 [-21.5, -8.3] | -12.1 [-21.1, -3.6] | 0.0000 | yes |
| altk − evoskill | -17.0 [-24.0, -10.2] | -18.2 [-28.6, -8.6] | 0.0000 | yes |
| altk − metaharness | -8.8 [-15.6, -2.3] | -6.1 [-14.6, 2.1] | 0.0080 | no |
| altk − harnesslens | 7.7 [2.4, 13.3] | 9.6 [2.5, 17.5] | 0.0040 | no |
| altk − miprov2 | -13.9 [-21.2, -7.0] | -16.1 [-25.0, -7.5] | 0.0000 | yes |
| altk − trace2skill | -24.4 [-31.3, -17.9] | -27.5 [-37.5, -17.9] | 0.0000 | yes |
| altk − gepa_full | -21.5 [-28.7, -14.8] | -25.4 [-35.7, -15.7] | 0.0000 | yes |
| altk − cape_k02 | -23.7 [-31.1, -16.5] | -27.9 [-37.9, -18.2] | 0.0000 | yes |
| ace − gepa | 1.1 [-4.9, 7.0] | 1.1 [-7.5, 10.0] | 0.7164 | no |
| ace − skillopt | -0.0 [-4.6, 4.6] | 1.4 [-5.4, 8.6] | 0.9922 | no |
| ace − wikiskill | 4.8 [-0.7, 10.0] | 11.1 [2.5, 19.6] | 0.0924 | no |
| ace − evoskill | 2.6 [-2.4, 7.9] | 5.0 [-2.5, 12.5] | 0.3198 | no |
| ace − metaharness | 10.8 [4.2, 17.9] | 17.1 [7.9, 26.8] | 0.0016 | no |
| ace − harnesslens | 27.4 [20.4, 34.4] | 32.9 [22.9, 43.2] | 0.0000 | yes |
| ace − miprov2 | 5.7 [-1.2, 12.7] | 7.1 [-1.8, 16.4] | 0.1096 | no |
| ace − trace2skill | -4.8 [-10.2, 0.6] | -4.3 [-12.1, 3.6] | 0.0874 | no |
| ace − gepa_full | -1.9 [-7.1, 3.3] | -2.1 [-10.0, 5.7] | 0.4858 | no |
| ace − cape_k02 | -4.0 [-9.9, 1.3] | -4.6 [-12.1, 2.9] | 0.1440 | no |
| gepa − skillopt | -1.1 [-5.7, 3.7] | 0.4 [-6.4, 6.8] | 0.6480 | no |
| gepa − wikiskill | 3.7 [-1.7, 9.0] | 10.0 [1.8, 18.2] | 0.1856 | no |
| gepa − evoskill | 1.5 [-2.4, 5.7] | 3.9 [-2.5, 10.4] | 0.4808 | no |
| gepa − metaharness | 9.8 [4.3, 15.4] | 16.1 [8.9, 23.6] | 0.0006 | yes |
| gepa − harnesslens | 26.3 [19.4, 33.3] | 31.8 [22.1, 41.8] | 0.0000 | yes |
| gepa − miprov2 | 4.6 [-0.1, 9.8] | 6.1 [-0.7, 13.2] | 0.0592 | no |
| gepa − trace2skill | -5.8 [-10.5, -1.3] | -5.4 [-12.1, 1.8] | 0.0134 | no |
| gepa − gepa_full | -3.0 [-6.4, 0.2] | -3.2 [-9.6, 2.9] | 0.0756 | no |
| gepa − cape_k02 | -5.1 [-10.1, -0.4] | -5.7 [-13.6, 1.8] | 0.0380 | no |
| skillopt − wikiskill | 4.8 [-0.8, 10.5] | 9.6 [1.4, 17.9] | 0.0938 | no |
| skillopt − evoskill | 2.6 [-0.7, 6.2] | 3.6 [-2.1, 9.3] | 0.1342 | no |
| skillopt − metaharness | 10.8 [5.1, 16.8] | 15.7 [9.3, 22.5] | 0.0000 | yes |
| skillopt − harnesslens | 27.4 [21.0, 34.0] | 31.4 [22.5, 40.7] | 0.0000 | yes |
| skillopt − miprov2 | 5.7 [-0.0, 11.5] | 5.7 [-1.4, 13.2] | 0.0512 | no |
| skillopt − trace2skill | -4.8 [-9.8, 0.1] | -5.7 [-13.2, 1.4] | 0.0588 | no |
| skillopt − gepa_full | -1.9 [-6.8, 2.5] | -3.6 [-10.4, 3.2] | 0.4212 | no |
| skillopt − cape_k02 | -4.0 [-9.3, 0.8] | -6.1 [-13.2, 1.1] | 0.1098 | no |
| wikiskill − evoskill | -2.1 [-7.7, 3.6] | -6.1 [-15.0, 2.9] | 0.4624 | no |
| wikiskill − metaharness | 6.1 [0.6, 11.4] | 6.1 [-0.7, 13.2] | 0.0286 | no |
| wikiskill − harnesslens | 22.6 [16.8, 28.3] | 21.8 [13.9, 30.0] | 0.0000 | yes |
| wikiskill − miprov2 | 1.0 [-4.9, 6.7] | -3.9 [-11.4, 3.6] | 0.7556 | no |
| wikiskill − trace2skill | -9.5 [-13.6, -5.5] | -15.4 [-22.5, -8.6] | 0.0000 | yes |
| wikiskill − gepa_full | -6.7 [-11.4, -1.9] | -13.2 [-21.4, -5.4] | 0.0060 | no |
| wikiskill − cape_k02 | -8.8 [-14.9, -2.5] | -15.7 [-24.6, -6.8] | 0.0066 | no |
| evoskill − metaharness | 8.2 [2.6, 14.2] | 12.1 [5.0, 19.6] | 0.0032 | no |
| evoskill − harnesslens | 24.8 [18.6, 31.2] | 27.9 [18.9, 37.1] | 0.0000 | yes |
| evoskill − miprov2 | 3.1 [-3.1, 9.6] | 2.1 [-6.1, 10.7] | 0.3364 | no |
| evoskill − trace2skill | -7.4 [-12.4, -2.4] | -9.3 [-17.5, -1.1] | 0.0046 | no |
| evoskill − gepa_full | -4.5 [-9.0, -0.5] | -7.1 [-13.6, -1.1] | 0.0306 | no |
| evoskill − cape_k02 | -6.7 [-11.9, -1.7] | -9.6 [-17.9, -1.4] | 0.0108 | no |
| metaharness − harnesslens | 16.5 [11.3, 22.0] | 15.7 [8.6, 23.6] | 0.0000 | yes |
| metaharness − miprov2 | -5.1 [-8.9, -1.3] | -10.0 [-14.6, -5.4] | 0.0090 | no |
| metaharness − trace2skill | -15.6 [-21.0, -10.2] | -21.4 [-29.3, -13.9] | 0.0000 | yes |
| metaharness − gepa_full | -12.7 [-18.7, -7.1] | -19.3 [-27.5, -11.4] | 0.0000 | yes |
| metaharness − cape_k02 | -14.9 [-21.2, -8.6] | -21.8 [-30.0, -13.6] | 0.0000 | yes |
| harnesslens − miprov2 | -21.7 [-28.6, -14.9] | -25.7 [-35.0, -17.1] | 0.0000 | yes |
| harnesslens − trace2skill | -32.1 [-38.6, -25.6] | -37.1 [-46.4, -27.9] | 0.0000 | yes |
| harnesslens − gepa_full | -29.3 [-36.2, -22.5] | -35.0 [-44.6, -25.4] | 0.0000 | yes |
| harnesslens − cape_k02 | -31.4 [-39.0, -23.5] | -37.5 [-47.9, -26.8] | 0.0000 | yes |
| miprov2 − trace2skill | -10.5 [-15.5, -5.7] | -11.4 [-19.6, -3.9] | 0.0000 | yes |
| miprov2 − gepa_full | -7.6 [-13.5, -2.1] | -9.3 [-17.9, -1.4] | 0.0050 | no |
| miprov2 − cape_k02 | -9.8 [-16.1, -3.8] | -11.8 [-19.6, -3.9] | 0.0014 | no |
| trace2skill − gepa_full | 2.9 [-1.8, 7.5] | 2.1 [-5.0, 9.3] | 0.2290 | no |
| trace2skill − cape_k02 | 0.7 [-4.8, 6.2] | -0.4 [-8.6, 7.9] | 0.8106 | no |
| gepa_full − cape_k02 | -2.1 [-7.3, 2.9] | -2.5 [-10.4, 5.0] | 0.4018 | no |

## Agent tokens, steps, latency and infra (per episode)

| arm | prompt tok/ep (mean / p50 / p90) | completion tok/ep (mean / p50 / p90) | steps (mean) | s/ep (mean / p50 / p90) | max prompt | step-cap | token-cap | ctx-exceeded | collateral | infra retries | pass fraction |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `seed` | 93,167 / 64,948 / 196,604 | 6,020 / 4,253 / 13,108 | 12.6 | 261 / 186 / 563 | 21,981 | 14 | 0 | 0 | 35 | 2 | 67.1 |
| `altk` | 141,117 / 119,546 / 261,462 | 7,255 / 5,712 / 14,333 | 14.9 | 316 / 247 / 617 | 24,497 | 3 | 0 | 0 | 29 | 4 | 74.9 |
| `ace` | 236,039 / 202,652 / 447,809 | 5,017 / 3,799 / 10,652 | 11.6 | 228 / 174 / 466 | 33,789 | 0 | 0 | 0 | 28 | 1 | 79.4 |
| `gepa` | 117,969 / 82,557 / 237,095 | 5,967 / 4,084 / 13,170 | 11.9 | 261 / 179 / 564 | 24,796 | 9 | 0 | 0 | 23 | 5 | 79.4 |
| `skillopt` | 158,929 / 125,175 / 294,120 | 6,958 / 5,372 / 13,742 | 12.3 | 305 / 233 / 586 | 29,034 | 13 | 0 | 0 | 38 | 4 | 81.7 |
| `wikiskill` | 94,322 / 66,709 / 193,760 | 5,682 / 4,307 / 11,753 | 10.5 | 252 / 192 / 525 | 23,645 | 2 | 0 | 0 | 23 | 3 | 78.3 |
| `evoskill` | 145,556 / 111,099 / 267,181 | 7,193 / 5,656 / 14,144 | 12.4 | 313 / 241 / 612 | 24,503 | 12 | 0 | 0 | 32 | 4 | 79.1 |
| `metaharness` | 104,937 / 76,586 / 207,872 | 6,698 / 4,957 / 13,669 | 14.1 | 293 / 220 / 600 | 19,474 | 8 | 0 | 0 | 29 | 8 | 74.8 |
| `harnesslens` | 93,118 / 65,385 / 194,013 | 6,116 / 4,275 / 13,009 | 12.7 | 266 / 188 / 542 | 20,228 | 7 | 0 | 0 | 32 | 5 | 67.4 |
| `miprov2` | 101,886 / 77,398 / 201,626 | 4,589 / 3,437 / 8,939 | 11.8 | 207 / 155 / 396 | 23,007 | 5 | 0 | 0 | 20 | 1 | 78.8 |
| `trace2skill` | 151,694 / 126,236 / 269,123 | 6,782 / 5,635 / 13,124 | 13.1 | 296 / 242 / 576 | 27,153 | 1 | 0 | 0 | 17 | 1 | 83.1 |
| `gepa_full` | 103,757 / 75,741 / 199,635 | 5,822 / 4,204 / 11,518 | 12.1 | 257 / 183 / 514 | 20,511 | 7 | 0 | 0 | 24 | 6 | 81.5 |
| `cape_k02` | 113,922 / 92,092 / 210,580 | 7,398 / 5,433 / 15,425 | 10.9 | 322 / 242 / 676 | 23,282 | 6 | 0 | 0 | 37 | 7 | 81.0 |

Agent cost: n/a (RITS is unpriced); agent tokens above stand in for it. No optimizer was called.

## Earlier windows (context)

| arm | this window TGC (5 trials) | other window TGC (2 trials) | other window |
|---|---|---|---|
| `seed` | 32.6 | 33.3 | other window: REST window (2026-10-21); the seed also ran in every other window |
| `altk` | 41.9 | 47.3 | other window: smoke test window (2026-10-15) |
| `ace` | 61.5 | 6400.0 | other window: ACE window (2026-10-14) |
| `gepa` | 60.5 | 60.1 | other window: eval 5 window (2026-10-19) |
| `skillopt` | 61.5 | 59.2 | other window: eval 5 window (2026-10-19) |
| `wikiskill` | 56.8 | 55.1 | other window: eval 5 window (2026-10-19) |
| `evoskill` | 58.9 | 54.8 | other window: eval 5 window (2026-10-19) |
| `metaharness` | 50.7 | 52.1 | other window: eval 5 window (2026-10-19) |
| `harnesslens` | 34.2 | 34.5 | other window: REST window (2026-10-21) |
| `miprov2` | 55.8 | 57.7 | other window: REST window (2026-10-21) |
| `trace2skill` | 66.3 | 68.8 | other window: REST window (2026-10-21) |
| `gepa_full` | 63.5 | 64.6 | other window: REST window (2026-10-21) |
| `cape_k02` | 65.6 | 61.6 | other window: CE3 window (2026-10-24) |

Context only, never a paired comparison. The seed's TGC in the other windows: REST 33.3, eval 5 34.2, CE3 37.8, smoke 31.5, ACE 3420.0.

**Deviations and disclosures.** ACE's playbook (55,513 chars) is over the shared lint's 30,000-char memory limit and was scored as frozen (D6). Surfaces: §3's column is 'surfaces searched'; the measured 'surfaces changed vs the seed' differ for gepa (P only), skillopt, wikiskill and evoskill (M only) (D10). The executing session's deny rules were merged into the base worktree's settings, since the session ran from there (D11). Other deviations, if any, are in the ledger (`docs/TEST_ALL_STATUS.md`).

**What these numbers cannot support.** Each champion came from **one** search with one search seed; the methods differ in the surfaces they may change, in search budget and in their own settings; and this is a **single** test window (window-to-window drift of identical artifacts was 4 to 6 TGC points in earlier evaluations; here the `harnesslens − seed` noise check measures the within-window part). So the ranking compares 13 **artifacts** under one test condition. It does not rank the methods in general.
