## Final window: test_normal, 168 tasks / 56 scenarios × 2 trials × 6 arms

| arm | TGC | SGC | Δ TGC vs seed [95% CI] | Δ SGC vs seed [95% CI] | missing |
|---|---|---|---|---|---|
| seed | 34.2 | 11.6 | — | — | 0 |
| gepa | 60.1 | 39.3 | 25.9 [18.5, 33.3] | 27.7 [17.0, 38.4] | 0 |
| skillopt | 59.2 | 41.1 | 25.0 [18.5, 31.8] | 29.5 [19.6, 40.2] | 0 |
| wikiskill | 55.1 | 32.1 | 20.8 [14.0, 28.0] | 20.5 [10.7, 31.2] | 0 |
| evoskill | 54.8 | 35.7 | 20.5 [13.7, 27.4] | 24.1 [15.2, 33.9] | 0 |
| metaharness | 52.1 | 33.9 | 17.9 [10.1, 25.3] | 22.3 [11.6, 33.0] | 0 |

## TGC by difficulty

| arm | Easy (n=57) | Medium (n=48) | Hard (n=63) |
|---|---|---|---|
| seed | 57.0 | 24.0 | 21.4 |
| gepa | 78.1 | 60.4 | 43.7 |
| skillopt | 80.7 | 64.6 | 35.7 |
| wikiskill | 73.7 | 59.4 | 34.9 |
| evoskill | 78.1 | 58.3 | 31.0 |
| metaharness | 68.4 | 47.9 | 40.5 |

## Agent cost, tokens and latency per episode (final window)

| arm | prompt tok/ep | completion tok/ep | steps/ep | s/ep | step-cap | ctx-exceeded | collateral | max prompt | trials agree |
|---|---|---|---|---|---|---|---|---|---|
| seed | 89,779 | 5,803 | 12.5 | 244 | 4 | 0 | 12 | 19,394 | 70% |
| gepa | 116,268 | 6,061 | 11.8 | 258 | 4 | 0 | 9 | 22,292 | 76% |
| skillopt | 148,513 | 6,585 | 11.8 | 280 | 1 | 0 | 14 | 25,305 | 77% |
| wikiskill | 100,663 | 6,079 | 11.0 | 257 | 4 | 0 | 8 | 20,949 | 76% |
| evoskill | 142,111 | 7,256 | 12.2 | 304 | 3 | 0 | 16 | 23,426 | 74% |
| metaharness | 107,990 | 6,972 | 14.3 | 292 | 4 | 0 | 11 | 20,472 | 78% |

## Optimizer side (search)

| candidate | counted search rollouts | optimizer calls | input tok | output tok | cache-read tok | USD | optimizer wall s |
|---|---|---|---|---|---|---|---|
| gepa | 900 | 33 | 761,846 | 184,757 | 0 | $5.06 (proxy) | 1,163 |
| skillopt | 900 | 74 | 2,331,763 | 180,038 | 0 | $9.7 (proxy) | 1,448 |
| wikiskill | 792 | 51 | 1,775,943 | 94,851 | 0 | $6.75 (proxy) | 767 |
| evoskill | 663 | 36 | 1,057,898 | 84,274 | 1,402,727 | $4.91 (reported) | 901 |
| metaharness | 887 | 7 | 2,217,164 | 7,046 | 38,925,416 | $28.18 (reported) | 4,536 |
