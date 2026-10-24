## Final window(s): test_normal, 168 tasks / 56 scenarios × 2 trials; ce3_k02 run in this window, seed, ce2_k1, ce2_k2 reused from CE2's window

| arm | TGC | SGC | Δ TGC vs seed [95% CI] | Δ SGC vs seed [95% CI] | missing |
|---|---|---|---|---|---|
| seed (reused, CE2 window) | 37.8 | 15.2 | — | — | 0 |
| ce2_k1 (reused, CE2 window) | 51.2 | 28.6 | — | — | 0 |
| ce2_k2 (reused, CE2 window) | 47.3 | 27.7 | — | — | 0 |
| ce3_k02 | 61.6 | 44.6 | 23.8 [16.7, 31.2] | 29.5 [18.8, 40.2] | 0 |

ce3_k02 − ce2_k1: Δ TGC 10.4 [4.5, 16.4], Δ SGC 16.1 [8.0, 24.1] (cross-window: the reused arm ran in CE2's window (2026-10-23)).

ce3_k02 − ce2_k2: Δ TGC 14.3 [8.0, 20.5], Δ SGC 17.0 [8.0, 25.9] (cross-window: the reused arm ran in CE2's window (2026-10-23)).

Every Δ in this table compares an arm of this window with an arm of CE2's window (2026-10-23): cross-window, so it includes window-to-window drift (CE2's predecessors measured 4–6 TGC points for identical artifacts).

## TGC by difficulty

| arm | Easy (n=57) | Medium (n=48) | Hard (n=63) |
|---|---|---|---|
| seed | 61.4 | 28.1 | 23.8 |
| ce2_k1 | 75.4 | 49.0 | 31.0 |
| ce2_k2 | 68.4 | 50.0 | 26.2 |
| ce3_k02 | 78.9 | 64.6 | 43.7 |

## Agent cost, tokens and latency per episode (final window)

| arm | prompt tok/ep | completion tok/ep | steps/ep | s/ep | step-cap | ctx-exceeded | collateral | max prompt | trials agree |
|---|---|---|---|---|---|---|---|---|---|
| seed | 95,153 | 6,316 | 13.0 | 256 | 5 | 0 | 9 | 22,376 | 66% |
| ce2_k1 | 88,784 | 6,915 | 9.6 | 279 | 2 | 0 | 10 | 21,498 | 70% |
| ce2_k2 | 95,999 | 6,878 | 10.6 | 278 | 3 | 0 | 10 | 21,236 | 77% |
| ce3_k02 | 114,902 | 7,207 | 11.1 | 285 | 1 | 0 | 13 | 22,311 | 80% |

## Optimizer side (search; seed baseline reused from REST P3, not counted)

| candidate | counted rollouts (of 900) | cache hits | lint rejects | optimizer calls | input tok | output tok | cache-read tok | cache-write tok | USD | optimizer s |
|---|---|---|---|---|---|---|---|---|---|---|
| ce3_k02 | 882 | 204 | 0 | 6 | 6,269,403 | 1,194,931 | 85,454,718 | 5,787,729 | $44.47 (proxy); $111.18 (CLI-reported) | 7,062 |
