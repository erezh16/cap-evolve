**Final results — Cap evolve no gate (no gate), AppWorld test_normal.**

### Setup
- plan: `docs/ABLATIONS.md` + addendum `docs/ABLATIONS_GATE.md` (branch `ablations`, erezh16/cap-evolve); reference arm `abl_ref` (#930)
- code under test: cap-evolve `main` `75b3bcd`, core and skills unmodified (D4); stock hill-climb `--focus all`, paired gate, `main`'s optimizer template plus one AppWorld facts section, 6 scored iterations
- this arm's only difference from `abl_ref`: `gate_k_se: -100000`: every scored candidate is kept and becomes the next parent, even if worse, and the one sentence of the AppWorld facts section that states the acceptance rule (A-ABL-SAME: pass)
- agent under test: `openai/gpt-oss-120b-a100` on RITS, reasoning medium, temperature 0, 50 steps; optimizer `aws/claude-sonnet-5-5` (every role), Claude Code CLI 2.1.270 in its sandbox
- search: 147 tasks (train ∪ dev), 1 trial, B = 882 counted rollouts, baseline = the shared seed run (cache)
- gate window (2026-10-28): 168 test_normal × the 2 gate arms × 2 trials = 672 cells, one shuffled order (seed 2026102807), trial seeds 5000 + k as the first window, 12 slots; the seed's and `abl_ref`'s cells are reused from the first window (2026-10-27)

### Main result (test_normal, 168 tasks / 56 scenarios, 2 trials)
| arm | window | TGC | SGC | Δ TGC vs abl_ref [95% CI] | Δ TGC vs seed [95% CI] | missing |
|---|---|---|---|---|---|---|
| seed | first (reused) | 36.3 | 14.3 | — | — | 0 |
| abl_ref | first (reused) | 62.5 | 40.2 | — | — | 0 |
| **abl_nogate** | gate | **55.7** | 33.9 | -6.8 [-11.9, -1.8] | 19.3 [11.6, 27.4] | 0 |
| abl_naivegate | gate | 56.5 | 34.8 | -6.0 [-10.7, -1.2] | 20.2 [13.4, 27.7] | 0 |

Primary contrast `abl_nogate − abl_ref` (cross-window): Δ TGC -6.8 [-11.9, -1.8], Δ SGC -6.2 [-14.3, 1.8]; bootstrap p 0.0106 raw, **0.0212 Holm** (over the 2 gate contrasts). Joint Holm over all 7 primary contrasts (5 first-wave + 2 gate; secondary): 0.0318.

Secondary `abl_nogate − abl_naivegate` (in-window): Δ TGC -0.9 [-6.0, 4.2], Δ SGC -0.9 [-8.9, 7.1].

95% CI: scenario-clustered paired bootstrap (56 clusters, 10,000 resamples); per-task pairs line up by (task, trial) across the two windows.

### How to read this (both gate arms together)
- The naive gate made **0 decisions** that differ from `abl_ref`'s rule: every gain it kept also cleared 0.2·SE. So its search ran exactly as `abl_ref`'s rule would have run it, and its test difference from `abl_ref` (-6.0 [-10.7, -1.2] TGC) **cannot be attributed to the gate**. It measures what one independent search of the same configuration, scored a day later, differs by: search randomness plus any cross-window change.
- The no gate arm differs from `abl_ref` by -6.8 [-11.9, -1.8] TGC, about the same as the naive gate. In the same window, no gate − naive gate is -0.9 [-6.0, 4.2] TGC, which includes 0. So removing the gate, which here meant keeping 2 candidates that `abl_ref`'s rule would have rejected, shows **no measurable effect beyond that floor** at this budget.
- The CIs and p-values above resample tasks and scenarios. They do not include the variation between searches, which this pair of arms suggests is about as large as the gaps measured here. Read the p-values against `abl_ref` as "these two champions score lower than this particular `abl_ref` champion", not as an effect of the gate.

**Cross-window caveat (D16).** The gate arms ran about a day after the first window. Any change in RITS serving between the two windows is mixed into every contrast with `abl_ref` or the seed. Drift check (rate per episode; seed + `abl_ref` in the first window vs the two gate arms): infra retries 0.0149 vs 0.0015, context-exceeded 0.0000 vs 0.0000; flagged (more than 2× and at least 3 episodes apart): infra_retries. A retry re-runs an infrastructure failure with a new seed; no cell is missing in either window. The `abl_nogate − abl_naivegate` contrast is in-window.

Context (first window, all arms):
| arm (first window, 2026-10-27) | TGC | SGC |
|---|---|---|
| seed | 36.3 | 14.3 |
| abl_ref | 62.5 | 40.2 |
| abl_cc | 32.1 | 8.9 |
| abl_prompt | 61.6 | 43.8 |
| abl_tools | 51.2 | 29.5 |
| abl_notrace | 49.7 | 32.1 |
| abl_tracescore | 45.2 | 23.2 |

### TGC by difficulty
| arm | Easy (57) | Medium (48) | Hard (63) |
|---|---|---|---|
| seed | 57.9 | 29.2 | 22.2 |
| abl_ref | 80.7 | 69.8 | 40.5 |
| abl_nogate | 75.4 | 60.4 | 34.1 |
| abl_naivegate | 80.7 | 58.3 | 33.3 |

### Test phase: agent tokens and latency (per episode)
| arm | prompt tok / ep | completion tok / ep | steps | s / ep | ctx-exceeded | infra retries | pass fraction | trials agree |
|---|---|---|---|---|---|---|---|---|
| seed | 90,522 | 5,884 | 12.6 | 247 | 0 | 1 | 0.679 | 73% |
| abl_ref | 136,415 | 7,323 | 11.1 | 303 | 0 | 9 | 0.814 | 75% |
| abl_nogate | 121,755 | 6,253 | 9.4 | 239 | 0 | 1 | 0.770 | 71% |
| abl_naivegate | 108,217 | 6,567 | 8.9 | 249 | 0 | 0 | 0.779 | 80% |

### Search phase: every iteration's decision
| iteration | val (fit) | parent | paired Δ̄ | SE | kept | `abl_ref`'s rule (Δ̄ > 0.2·SE) |
|---|---|---|---|---|---|---|
| 1 | 0.5782 | 0.4014 | +0.1769 | 0.0508 | yes | keep |
| 2 | 0.6939 | 0.5782 | +0.1156 | 0.0448 | yes | keep |
| 3 | 0.8231 | 0.6939 | +0.1293 | 0.0413 | yes | keep |
| 4 | 0.7551 | 0.8231 | -0.0680 | 0.0382 | yes | reject **(differs)** |
| 5 | 0.7891 | 0.7551 | +0.0340 | 0.0436 | yes | keep |
| 6 | 0.7823 | 0.7891 | -0.0068 | 0.0392 | yes | reject **(differs)** |

Decisions that differ from `abl_ref`'s rule: **2 of 6**.

- iterations scored / accepted: 6 / 6; counted rollouts 882 of 882; metric calls 1029 of 1,029
- champion `cand_0006` (the last accepted candidate): search score **0.7823**; best score seen during the search 0.8231 (fit metrics, train ∪ dev, selection-biased)
- optimizer: 6 sessions; **$50.37** proxy (Sonnet 5.5 list price); CLI-reported $125.93
- agent cost: n/a (RITS, unpriced); tokens per episode in the test table

### What changed (the frozen artifact)
- `policy/instructions.txt`: changed (11,350 → 33,050 chars, 7,810 tokens (seed 2,745))
- `tools/helpers.py`: changed (174 → 23,205 chars, 38 helper functions, 397 lines)
- `tools/api_notes.json`: changed (3 → 13,347 chars, 54 notes, 11,577 chars)
- champion `cand_0006`; tree sha256 `cdbc5827f70b02e1` = the run's own candidate; lint-clean; published in `docs/ABLATION_STATUS_STATE/abl_nogate/artifact/` on branch `eval-abl`

### Isolation and reset
Scans: **0 test-id hits** in this arm's optimizer records, workdirs, transcripts and artifact; optimizer models only `aws/claude-sonnet-5-5`. Not labelled an isolation breach. Reset check (§9.8): pass. Orchestrating sessions: 2 test-id hits over 100 files, all in one command output of the previous orchestrating session on 2026-10-27 18:35 UTC, after the first window's results were posted (an id only, no task content or outcome; no optimizer can read those transcripts; ledger ABL-0796).

### Deviations
- the gate window runs only the two gate champions; `abl_ref` and the seed are reused from the first window (D16, user decision)
- the optimizer is told this arm's acceptance rule in the AppWorld facts section, and that core's fixed "How your edit is judged" paragraph (which describes a significance bar) does not apply (D17, user decision)
- 12 episode slots instead of 24 from 12:10 UTC on 2026-10-28 (ABL-0732, user request: another workload in the pod); this slows the run and does not change any result
- see the ledger `docs/ABLATION_STATUS.md` (entries ABL-0716 onwards, kinds error, repair, decision)

### What the numbers cannot support
- One search seed per arm: each contrast mixes the gate with search randomness. A difference under about 8 TGC points is not resolved; a null result is a bound.
- Search scores are fit metrics (train = val, selection-biased); only the test_normal numbers are held out.
- Contrasts with `abl_ref` and the seed are cross-window (see above).

Full numbers: `docs/ABLATION_STATUS_STATE/final_gate/analysis.json`.
