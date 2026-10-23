## Final window: test_normal, 168 tasks / 56 scenarios × 2 trials × 3 arms

| arm | TGC | SGC | Δ TGC vs seed [95% CI] | Δ SGC vs seed [95% CI] | missing |
|---|---|---|---|---|---|
| seed | 37.8 | 15.2 | — | — | 0 |
| ce2_k1 | 51.2 | 28.6 | 13.4 [7.1, 20.2] | 13.4 [3.6, 23.2] | 0 |
| ce2_k2 | 47.3 | 27.7 | 9.5 [2.1, 17.3] | 12.5 [5.4, 20.5] | 0 |

ce2_k2 − ce2_k1: Δ TGC -3.9 [-11.6, 3.9], Δ SGC -0.9 [-9.8, 8.0] (ce2_k2 − ce2_k1; one search seed each: K is confounded with search randomness).

## TGC by difficulty

| arm | Easy (n=57) | Medium (n=48) | Hard (n=63) |
|---|---|---|---|
| seed | 61.4 | 28.1 | 23.8 |
| ce2_k1 | 75.4 | 49.0 | 31.0 |
| ce2_k2 | 68.4 | 50.0 | 26.2 |

## Agent cost, tokens and latency per episode (final window)

| arm | prompt tok/ep | completion tok/ep | steps/ep | s/ep | step-cap | ctx-exceeded | collateral | max prompt | trials agree |
|---|---|---|---|---|---|---|---|---|---|
| seed | 95,153 | 6,316 | 13.0 | 256 | 5 | 0 | 9 | 22,376 | 66% |
| ce2_k1 | 88,784 | 6,915 | 9.6 | 279 | 2 | 0 | 10 | 21,498 | 70% |
| ce2_k2 | 95,999 | 6,878 | 10.6 | 278 | 3 | 0 | 10 | 21,236 | 77% |

## Optimizer side (search; seed baseline reused from REST P3, not counted)

| candidate | counted rollouts (of 900) | cache hits | lint rejects | optimizer calls | input tok | output tok | cache-read tok | cache-write tok | USD | optimizer s |
|---|---|---|---|---|---|---|---|---|---|---|
| ce2_k1 | 882 | 204 | 0 | 6 | 4,917,940 | 1,126,883 | 89,087,964 | 4,074,396 | $40.96 (proxy); $102.4 (CLI-reported) | 6,370 |
| ce2_k2 | 882 | 204 | 0 | 6 | 2,585,982 | 777,510 | 55,103,897 | 2,222,890 | $25.08 (proxy); $62.7 (CLI-reported) | 4,821 |
