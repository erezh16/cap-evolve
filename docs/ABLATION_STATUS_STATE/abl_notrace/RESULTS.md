**Final results — Cap evolve no traces (no traces (evaluation feedback only)), AppWorld test_normal.**

### Setup
- code under test: cap-evolve `main` `75b3bcd`, core and skills unmodified (D4); stock hill-climb `--focus all`, paired gate `gate_k_se: 0.2` explicit, `main`'s optimizer template plus one AppWorld facts section, 6 scored iterations (cap-evolve arms)
- this arm: as the reference, plus `AW_ABL_FEEDBACK=eval_only`
- agent under test (all arms): `openai/gpt-oss-120b-a100` on RITS, `hosted_vllm/`, reasoning medium, temperature 0, 50 steps, AppWorld `42b5bcf` simplified ReAct agent
- optimizer (every role, every arm): `aws/claude-sonnet-5-5` via the gateway, Claude Code CLI 2.1.270 in Claude Code's sandbox, `--setting-sources ''`
- search: train = val = train ∪ dev (147), 1 trial (seed 100), B = 882 counted rollouts, no money or token cap (D12); the seed baseline is one shared P3 run (147, not counted)
- final window: 168 test_normal × 7 arms × 2 trials (seeds 5000 + k) = 2,688 cells, one shuffled order (seed 2026102507), 24 slots
- A-ABL-SAME vs abl_ref: pass

### Main result (test_normal, 168 tasks / 56 scenarios, 2 trials)
| arm | TGC | SGC | Δ TGC vs abl_ref [95% CI] | Δ TGC vs seed [95% CI] | missing |
|---|---|---|---|---|---|
| seed | 36.3 | 14.3 | — | — | 0 |
| abl_ref | 62.5 | 40.2 | — | 26.2 [19.3, 33.0] | 0 |
| **abl_notrace** | **49.7** | 32.1 | -12.8 [-19.9, -6.0] | 13.4 [4.2, 22.6] | 0 |

Primary contrast `abl_notrace − abl_ref`: Δ TGC -12.8 [-19.9, -6.0], Δ SGC -8.0 [-18.8, 2.7]; bootstrap p 0.0000 raw, **0.0000 Holm** (over the 5 primary contrasts).

Secondary `abl_notrace − abl_tracescore`: Δ TGC 4.5 [-0.9, 10.1], Δ SGC 8.9 [1.8, 17.0].

All seven arms:
| arm | TGC | SGC | Δ TGC vs abl_ref | p Holm |
|---|---|---|---|---|
| seed | 36.3 | 14.3 | — | — |
| abl_ref | 62.5 | 40.2 | — | — |
| abl_cc | 32.1 | 8.9 | -30.4 [-38.1, -22.6] | 0.0000 |
| abl_prompt | 61.6 | 43.8 | -0.9 [-6.5, 4.8] | 0.7794 |
| abl_tools | 51.2 | 29.5 | -11.3 [-18.8, -4.5] | 0.0008 |
| abl_notrace | 49.7 | 32.1 | -12.8 [-19.9, -6.0] | 0.0000 |
| abl_tracescore | 45.2 | 23.2 | -17.3 [-22.6, -12.2] | 0.0000 |
| abl_cc_best | 55.7 | 37.5 | — | — |

95% CI: scenario-clustered paired bootstrap (56 clusters, 10,000 resamples).

### TGC by difficulty
| arm | Easy (57) | Medium (48) | Hard (63) |
|---|---|---|---|
| seed | 57.9 | 29.2 | 22.2 |
| abl_ref | 80.7 | 69.8 | 40.5 |
| abl_cc | 54.4 | 20.8 | 20.6 |
| abl_prompt | 76.3 | 64.6 | 46.0 |
| abl_tools | 78.1 | 47.9 | 29.4 |
| abl_notrace | 79.8 | 44.8 | 26.2 |
| abl_tracescore | 70.2 | 45.8 | 22.2 |
| abl_cc_best | 76.3 | 60.4 | 33.3 |

### Test phase: agent tokens and latency (per episode)
| arm | prompt tok / ep (mean, p50, p90) | completion tok / ep (mean, p90) | steps | s / ep (mean, p50, p90) | step-cap | token-cap | ctx-exceeded | pass fraction | trials agree |
|---|---|---|---|---|---|---|---|---|---|
| seed | 90,522, 62,498, 184,800 | 5,884, 13,170 | 12.6 | 247, 176, 541 | 3 | 0 | 0 | 0.679 | 73% |
| abl_ref | 136,415, 85,556, 265,091 | 7,323, 17,000 | 11.1 | 303, 187, 706 | 7 | 0 | 0 | 0.814 | 75% |
| abl_cc | 99,850, 65,603, 220,433 | 6,520, 14,725 | 13.1 | 274, 178, 578 | 6 | 0 | 0 | 0.680 | 70% |
| abl_prompt | 132,537, 106,787, 244,671 | 6,141, 12,672 | 11.9 | 260, 198, 533 | 2 | 0 | 0 | 0.812 | 80% |
| abl_tools | 83,355, 56,223, 175,621 | 5,557, 11,986 | 11.2 | 234, 169, 484 | 1 | 0 | 0 | 0.748 | 73% |
| abl_notrace | 114,468, 79,453, 231,537 | 8,394, 16,417 | 11.1 | 350, 251, 724 | 4 | 0 | 0 | 0.716 | 77% |
| abl_tracescore | 94,979, 66,615, 188,164 | 5,462, 12,142 | 7.9 | 233, 158, 504 | 0 | 0 | 0 | 0.708 | 76% |
| abl_cc_best | 95,183, 74,603, 191,953 | 5,787, 11,565 | 10.5 | 251, 192, 503 | 0 | 0 | 0 | 0.778 | 73% |

### Search phase
- iterations scored / consumed / accepted: 6 / 6 / 3; voided steps (sealed surface changed): 0; lint rejects 0
- counted rollouts 882 of 882; metric calls 1029 of 1,029; cache hits 147
- champion search score 0.6122448979591837 (fit metric, selection-biased)
- seed baseline (shared P3, not counted): val None
- optimizer: 6 sessions; 1107710 input / 766983 output / 16793246 cache-read tokens; **$13.72** proxy (Sonnet 5.5 list price); CLI-reported $34.31
- agent cost: n/a (RITS, unpriced); tokens per episode in the test table; search episodes: prompt mean 89,451

### What changed (the frozen artifact)
- `policy/instructions.txt`: changed (11,350 → 19,820 chars, 4,770 tokens (seed 2,745))
- `tools/helpers.py`: changed (174 → 16,827 chars, 27 helper functions, 378 lines)
- `tools/api_notes.json`: changed (3 → 12,706 chars, 54 notes, 10,894 chars)
- champion `cand_0006`; tree sha256 `973ebcb4af6b3bdd` = the run's own candidate; lint-clean; published in `docs/ABLATION_STATUS_STATE/abl_notrace/artifact/` on branch `eval-abl`

### Isolation and reset
Scans: **0 test-id hits** in this arm's optimizer records, workdirs, transcripts and artifact; 0 in the orchestrating sessions' transcripts (61 files). Not labelled an isolation breach. Reset check (§9.8): pass.

### Deviations
- see the ledger `docs/ABLATION_STATUS.md` (entries of kind error, repair, decision); none affects a counted rollout unless stated there.

### What the numbers cannot support
- Artifact-level statements only: one search seed per arm, so each contrast confounds the ablated factor with search randomness. Earlier windows measured an SE of about 3 to 4 TGC points per arm, so a difference under about 8 TGC points is not resolved; a null result is a bound ("less than about X").
- Search scores are fit metrics (train = val, selection-biased); only the test_normal numbers are held out.
- No test number of an earlier evaluation is compared here (other windows).

Full tables: `docs/ABLATION_STATUS_STATE/final/RESULTS.md` and `analysis.json`.
