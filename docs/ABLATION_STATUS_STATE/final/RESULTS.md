## Final window: test_normal, 168 tasks / 56 scenarios × 2 trials × 8 arms

| arm | TGC | SGC | Δ TGC vs seed [95% CI] | Δ SGC vs seed [95% CI] | missing |
|---|---|---|---|---|---|
| seed | 36.3 | 14.3 | — | — | 0 |
| abl_ref | 62.5 | 40.2 | 26.2 [19.3, 33.0] | 25.9 [17.0, 35.7] | 0 |
| abl_cc | 32.1 | 8.9 | -4.2 [-10.1, 1.5] | -5.4 [-12.5, 1.8] | 0 |
| abl_prompt | 61.6 | 43.8 | 25.3 [17.3, 33.6] | 29.5 [19.6, 39.3] | 0 |
| abl_tools | 51.2 | 29.5 | 14.9 [7.4, 22.6] | 15.2 [4.5, 25.9] | 0 |
| abl_notrace | 49.7 | 32.1 | 13.4 [4.2, 22.6] | 17.9 [7.1, 28.6] | 0 |
| abl_tracescore | 45.2 | 23.2 | 8.9 [1.8, 16.7] | 8.9 [-0.9, 19.6] | 0 |
| abl_cc_best | 55.7 | 37.5 | 19.3 [11.9, 27.1] | 23.2 [13.4, 33.9] | 0 |

| ablation − abl_ref (primary) | Δ TGC [95% CI] | Δ SGC [95% CI] | p raw | p Holm |
|---|---|---|---|---|
| abl_cc | -30.4 [-38.1, -22.6] | -31.2 [-42.9, -19.6] | 0.0000 | 0.0000 |
| abl_prompt | -0.9 [-6.5, 4.8] | 3.6 [-5.4, 12.5] | 0.7794 | 0.7794 |
| abl_tools | -11.3 [-18.8, -4.5] | -10.7 [-21.4, -0.9] | 0.0004 | 0.0008 |
| abl_notrace | -12.8 [-19.9, -6.0] | -8.0 [-18.8, 2.7] | 0.0000 | 0.0000 |
| abl_tracescore | -17.3 [-22.6, -12.2] | -17.0 [-25.9, -8.9] | 0.0000 | 0.0000 |

abl_prompt − abl_tools (secondary): Δ TGC 10.4 [3.3, 17.6], Δ SGC 14.3 [6.2, 23.2].

abl_notrace − abl_tracescore (secondary): Δ TGC 4.5 [-0.9, 10.1], Δ SGC 8.9 [1.8, 17.0].

abl_cc_best − abl_ref (secondary): Δ TGC -6.8 [-13.1, -0.9], Δ SGC -2.7 [-12.5, 7.1].

abl_cc_best − abl_cc (secondary): Δ TGC 23.5 [16.1, 31.2], Δ SGC 28.6 [18.8, 38.4].

## TGC by difficulty

| arm | Easy (n=57) | Medium (n=48) | Hard (n=63) |
|---|---|---|---|
| seed | 57.9 | 29.2 | 22.2 |
| abl_ref | 80.7 | 69.8 | 40.5 |
| abl_cc | 54.4 | 20.8 | 20.6 |
| abl_prompt | 76.3 | 64.6 | 46.0 |
| abl_tools | 78.1 | 47.9 | 29.4 |
| abl_notrace | 79.8 | 44.8 | 26.2 |
| abl_tracescore | 70.2 | 45.8 | 22.2 |
| abl_cc_best | 76.3 | 60.4 | 33.3 |

## Agent cost, tokens and latency per episode (final window)

| arm | prompt tok/ep | completion tok/ep | steps/ep | s/ep | step-cap | ctx-exceeded | collateral | max prompt | trials agree |
|---|---|---|---|---|---|---|---|---|---|
| seed | 90,522 | 5,884 | 12.6 | 247 | 3 | 0 | 13 | 19,459 | 73% |
| abl_ref | 136,415 | 7,323 | 11.1 | 303 | 7 | 0 | 10 | 29,121 | 75% |
| abl_cc | 99,850 | 6,520 | 13.1 | 274 | 6 | 0 | 12 | 21,752 | 70% |
| abl_prompt | 132,537 | 6,141 | 11.9 | 260 | 2 | 0 | 9 | 24,983 | 80% |
| abl_tools | 83,355 | 5,557 | 11.2 | 234 | 1 | 0 | 9 | 23,277 | 73% |
| abl_notrace | 114,468 | 8,394 | 11.1 | 350 | 4 | 0 | 6 | 21,307 | 77% |
| abl_tracescore | 94,979 | 5,462 | 7.9 | 233 | 0 | 0 | 11 | 24,102 | 76% |
| abl_cc_best | 95,183 | 5,787 | 10.5 | 251 | 0 | 0 | 8 | 20,708 | 73% |

## Optimizer side (search; seed baseline reused from REST P3, not counted)

| candidate | counted rollouts (of 900) | cache hits | lint rejects | optimizer calls | input tok | output tok | cache-read tok | cache-write tok | USD | optimizer s |
|---|---|---|---|---|---|---|---|---|---|---|
| abl_ref | 882 | 996 | 0 | 11 | 4,823,827 | 906,919 | 69,384,831 | 4,437,449 | $34.81 (proxy); $87.03 (CLI-reported) | 7,672 |
| abl_cc | 588 | 261 | 0 | 4 | 1,667,605 | 245,279 | 25,255,525 | 1,558,299 | $11.62 (proxy); $29.05 (CLI-reported) | 5,200 |
| abl_prompt | 882 | 996 | 0 | 11 | 4,571,125 | 706,930 | 53,797,578 | 4,200,268 | $29.07 (proxy); $72.68 (CLI-reported) | 6,047 |
| abl_tools | 882 | 996 | 0 | 11 | 5,545,978 | 828,741 | 63,863,733 | 5,035,829 | $34.67 (proxy); $86.68 (CLI-reported) | 6,975 |
| abl_notrace | 882 | 261 | 0 | 6 | 1,107,710 | 766,983 | 16,793,246 | 961,352 | $13.72 (proxy); $34.31 (CLI-reported) | 6,820 |
| abl_tracescore | 882 | 261 | 0 | 6 | 6,862,651 | 1,203,676 | 97,860,463 | 6,356,956 | $48.51 (proxy); $121.28 (CLI-reported) | 5,849 |
