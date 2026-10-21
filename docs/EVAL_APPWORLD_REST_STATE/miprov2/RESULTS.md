**Final results: MIPROv2 vs the seed agent (AppWorld test_normal).**

### Setup
- method: MIPROv2, DSPy 3.4.1 (`dspy.MIPROv2`); surface: P (instruction + up to 3 demos in the prompt); search splits: train (90): dataset summary and demo pool; dev (57): minibatches and full evals (selection)
- agent under test (all arms): `openai/gpt-oss-120b-a100` on RITS, reasoning medium, temperature 0, 50 steps, 100K completion tokens/task, the official simplified ReAct agent at AppWorld `42b5bcf`
- optimizer (every role): `aws/claude-sonnet-5-5` via the gateway (no temperature/seed sent); gold-free feedback (reward, failed requirement texts, collateral damage, steps, termination)
- budget: B = 900 counted search rollouts and 10M optimizer non-cache-read tokens; 1 search seed; 1 trial per task in search
- baseline: one shared seed run (train 90 + dev 57), reused by every candidate, not charged
- final window: 168 test_normal tasks × 6 arms × 2 trials = 2,016 cells, one shuffled order, 0 missing cells; seed and all five champions scored together

### Main result (test_normal, 168 tasks / 56 scenarios, 2 trials)
| arm | TGC | SGC | Δ TGC vs seed [95% CI] | Δ SGC vs seed [95% CI] | missing cells |
|---|---|---|---|---|---|
| seed | 33.3 | 8.0 | — | — | 0 |
| **MIPROv2** | **57.7** | **37.5** | **24.4 [17.3, 31.5]** | 29.5 [18.8, 40.2] | 0 |

95% CI: scenario-clustered paired bootstrap (56 clusters, 10,000 resamples), unadjusted.

### TGC by difficulty
| arm | Easy (57) | Medium (48) | Hard (63) |
|---|---|---|---|
| seed | 55.3 | 27.1 | 18.3 |
| miprov2 | 79.8 | 62.5 | 34.1 |

### Agent cost, tokens and latency (final window, per episode)
| arm | prompt tok / ep (mean, p50, p90) | completion tok / ep | steps | s / ep (mean, p90) | step-cap | ctx-exceeded | pass fraction | trials agree |
|---|---|---|---|---|---|---|---|---|
| seed | 94,193, 63,997, 201,364 | 6,030 | 12.7 | 259, 542 | 2 | 0 | 0.680 | 67% |
| miprov2 | 101,774, 77,030, 198,506 | 4,612 | 11.8 | 208, 367 | 3 | 0 | 0.791 | 79% |

### Search phase (cost, tokens, latency, budget)
| | value |
|---|---|
| counted search rollouts | 558 of B = 900 (cache hits 638, lint-reject batches 0, infra 0); the shared seed baseline (147) is not charged |
| mean reward of counted rollouts | 0.5896 (search sets; selection-biased) |
| agent tokens / search episode (mean, p90) | prompt 73,417, 143,109; completion 3,326 |
| search episode seconds (mean, p90) | 164.5, 285.9 |
| optimizer calls | 74 (0 errors), model aws/claude-sonnet-5-5 |
| optimizer tokens | 266,064 in (non-cache-read) / 51,579 out / 0 cache-read / 0 cache-write |
| optimizer cost | **$1.05** proxy at Sonnet 5.5 list price |
| optimizer time | 450 s in calls (mean 6.1 s, p90 9.58 s); search wall 2026-10-20T22:29:37Z → 2026-10-21T02:59:02Z |
| dev diagnostic (57 dev, 1 trial) | 0.7368 (seed 0.3333) |
| agent cost | n/a (RITS is unpriced); tokens above |

### What changed (the frozen artifact)
- `policy/instructions.txt`: changed (11,350 → 16,139 chars)
- `tools/helpers.py`: unchanged from the seed
- `tools/api_notes.json`: unchanged from the seed
- `memory/playbook.md`: unchanged from the seed
- tree sha256 `a4ff3a502879f520`; lint-clean; published in `docs/EVAL_APPWORLD_REST_STATE/miprov2/artifact/` on branch `eval-rest`

### Isolation
Post-search and full scans: **0 test-id hits** in every optimizer-side record, workspace and transcript of this arm, and 0 in the orchestrating sessions' own transcripts. Not labelled an isolation breach. The only literal-string hits (`root_full`, `ground_truth`) are in the sandbox acceptance probe and the sandbox's own deny list.

### What this MIPROv2 is and is not
- MIPROv2 optimizes only the instruction and few-shot demos of one DSPy predictor. The whole AppWorld agent is wrapped as one module whose instruction is the stock prompt's job-description prose; tools, helpers and memory are untouched.
- **Demo pool from the seed's successful train trajectories** (one condensation call each, then lint), not from BootstrapFewShot re-runs. No labelled demos. The champion has 2 demos.
- Settings: `auto=None`, 6 candidates, 16 trials, minibatch 35, full eval every 5 steps (DSPy 3.4.1 ran 5 full evals). The proposer's temperatures were dropped (gateway). DSPy's Optuna study has no storage, so resume is a seeded replay.
- Its dev score is the selection set's (selection-biased); only test_normal is held out.
- Common to all arms: Sonnet 5.5 optimizer (not each paper's model), gold-free feedback, B = 900 + 10M tokens, memory cap 14,000 tokens, 1 trial per task in search, the shared seed baseline.

### Deviations
See plan §15 and this issue's earlier posts. All five arms share the same harness, model client, decoding, caps, evaluator, final window and analysis.

### What the numbers cannot support
- **No ranking between candidates.** Each had one search seed, its own surface and budget use. Identical artifacts drifted by 4–6 TGC points between windows in earlier runs, and the two trials of a task agree on only 67–81% of tasks. For context only, Δ TGC vs seed of the other arms in this same window: HarnessLens 1.2, Trace2Skill 35.4, GEPA-Full 31.3, Cap-Evolve-improve 16.1.
- Artifact-level statements only: one search run of this method under this configuration, not the method in general.
- Search-time scores are selection-biased; only the test_normal numbers above are held out.
- No multiplicity correction across the five comparisons.

Full tables: `docs/EVAL_APPWORLD_REST_STATE/final/RESULTS.md` and `analysis.json`; ledger: `docs/EVAL_APPWORLD_REST.md` §18.
