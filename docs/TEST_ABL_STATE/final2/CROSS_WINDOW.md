# AppWorld TEST_ABL: the gate arms vs `abl_ref` and the seed (cross-window)

| arm | window | TGC | SGC | Δ TGC vs `abl_ref` [95% CI] | Holm (2 primary) | Δ TGC vs seed [95% CI] | gate run's own window (2 trials) |
|---|---|---|---|---|---|---|---|
| `abl_ref` | 1 | 59.5 | 42.9 | — | — | — | 62.5 |
| `seed` | 1 | 34.2 | 10.7 | — | — | — | 36.3 |
| `abl_nogate` | 2 | 55.0 | 36.8 | -4.5 [-10.6, 1.2] | not significant | 20.8 [13.6, 28.1] | 55.7 |
| `abl_naivegate` | 2 | 57.1 | 38.6 | -2.4 [-7.5, 2.9] | not significant | 23.0 [15.5, 30.4] | 56.5 |

**Cross-window caveat.** `abl_ref` and the seed were scored in window 1 (2026-10-28 to 10-30) and the gate arms in window 2 (2026-11-01), on the same 168 tasks with the same trial seeds (7000 + k), so the comparison is paired by (task, trial). Any drift in the RITS serving between the two windows is mixed into each Δ. Drift check: infra retries per cell, window 1 (`abl_ref`, seed) 0.0327, window 2 (gate arms) 0.0077; differing by more than 2×: **yes**. One search seed per arm; differences of a few points are not resolved.
