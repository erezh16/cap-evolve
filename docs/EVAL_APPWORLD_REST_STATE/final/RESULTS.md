## Final window: test_normal, 168 tasks / 56 scenarios × 2 trials × 6 arms

| arm | TGC | SGC | Δ TGC vs seed [95% CI] | Δ SGC vs seed [95% CI] | missing |
|---|---|---|---|---|---|
| seed | 33.3 | 8.0 | — | — | 0 |
| harnesslens | 34.5 | 13.4 | 1.2 [-5.4, 7.4] | 5.4 [0.0, 10.7] | 0 |
| miprov2 | 57.7 | 37.5 | 24.4 [17.3, 31.5] | 29.5 [18.8, 40.2] | 0 |
| trace2skill | 68.8 | 47.3 | 35.4 [29.2, 42.0] | 39.3 [29.5, 50.0] | 0 |
| gepa_full | 64.6 | 47.3 | 31.3 [24.4, 38.1] | 39.3 [28.6, 50.0] | 0 |
| cape_improve | 49.4 | 35.7 | 16.1 [8.9, 23.5] | 27.7 [17.9, 38.4] | 0 |

## TGC by difficulty

| arm | Easy (n=57) | Medium (n=48) | Hard (n=63) |
|---|---|---|---|
| seed | 55.3 | 27.1 | 18.3 |
| harnesslens | 54.4 | 28.1 | 21.4 |
| miprov2 | 79.8 | 62.5 | 34.1 |
| trace2skill | 86.0 | 79.2 | 45.2 |
| gepa_full | 81.6 | 69.8 | 45.2 |
| cape_improve | 76.3 | 51.0 | 23.8 |

## Agent cost, tokens and latency per episode (final window)

| arm | prompt tok/ep | completion tok/ep | steps/ep | s/ep | step-cap | ctx-exceeded | collateral | max prompt | trials agree |
|---|---|---|---|---|---|---|---|---|---|
| seed | 94,193 | 6,030 | 12.7 | 259 | 2 | 0 | 16 | 21,258 | 67% |
| harnesslens | 93,050 | 5,869 | 12.8 | 248 | 6 | 0 | 15 | 20,778 | 71% |
| miprov2 | 101,774 | 4,612 | 11.8 | 208 | 3 | 0 | 11 | 21,797 | 79% |
| trace2skill | 158,496 | 6,705 | 13.4 | 288 | 1 | 0 | 10 | 24,082 | 77% |
| gepa_full | 103,777 | 5,764 | 12.2 | 241 | 3 | 0 | 13 | 20,105 | 78% |
| cape_improve | 122,550 | 7,009 | 9.4 | 293 | 7 | 0 | 16 | 26,407 | 81% |

## Optimizer side (search; shared seed baseline of 147 rollouts counted once, not charged)

| candidate | counted rollouts (of 900) | cache hits | lint rejects | optimizer calls | input tok | output tok | cache-read tok | cache-write tok | USD | optimizer s |
|---|---|---|---|---|---|---|---|---|---|---|
| harnesslens | 162 | 195 | 0 | 270 | 9,410,029 | 1,042,108 | 2,279,443 | 801,654 | $30.1 (proxy); $7.78 (CLI-reported) | 8,039 |
| miprov2 | 558 | 638 | 0 | 74 | 266,064 | 51,579 | 0 | 0 | $1.05 (proxy) | 450 |
| trace2skill | 270 | 450 | 0 | 717 | 3,436,541 | 940,656 | 0 | 0 | $16.28 (proxy) | 5,398 |
| gepa_full | 809 | 142 | 0 | 70 | 902,011 | 61,985 | 0 | 0 | $2.42 (proxy) | 640 |
| cape_improve | 882 | 216 | 0 | 6 | 4,033,132 | 929,670 | 63,105,027 | 3,678,643 | $31.82 (proxy); $79.56 (CLI-reported) | 5,665 |
