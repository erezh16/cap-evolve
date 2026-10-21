**Final results: GEPA-Full vs the seed agent (AppWorld test_normal).**

### Setup
- method: GEPA-Full, gepa 0.1.4; surface: P + T (prompt, helpers, one API-notes component per app); search splits: train (90): reflection minibatches; dev (57): Pareto front and final choice
- agent under test (all arms): `openai/gpt-oss-120b-a100` on RITS, reasoning medium, temperature 0, 50 steps, 100K completion tokens/task, the official simplified ReAct agent at AppWorld `42b5bcf`
- optimizer (every role): `aws/claude-sonnet-5-5` via the gateway (no temperature/seed sent); gold-free feedback (reward, failed requirement texts, collateral damage, steps, termination)
- budget: B = 900 counted search rollouts and 10M optimizer non-cache-read tokens; 1 search seed; 1 trial per task in search
- baseline: one shared seed run (train 90 + dev 57), reused by every candidate, not charged
- final window: 168 test_normal tasks × 6 arms × 2 trials = 2,016 cells, one shuffled order, 0 missing cells; seed and all five champions scored together

### Main result (test_normal, 168 tasks / 56 scenarios, 2 trials)
| arm | TGC | SGC | Δ TGC vs seed [95% CI] | Δ SGC vs seed [95% CI] | missing cells |
|---|---|---|---|---|---|
| seed | 33.3 | 8.0 | — | — | 0 |
| **GEPA-Full** | **64.6** | **47.3** | **31.3 [24.4, 38.1]** | 39.3 [28.6, 50.0] | 0 |

95% CI: scenario-clustered paired bootstrap (56 clusters, 10,000 resamples), unadjusted.

### TGC by difficulty
| arm | Easy (57) | Medium (48) | Hard (63) |
|---|---|---|---|
| seed | 55.3 | 27.1 | 18.3 |
| gepa_full | 81.6 | 69.8 | 45.2 |

### Agent cost, tokens and latency (final window, per episode)
| arm | prompt tok / ep (mean, p50, p90) | completion tok / ep | steps | s / ep (mean, p90) | step-cap | ctx-exceeded | pass fraction | trials agree |
|---|---|---|---|---|---|---|---|---|
| seed | 94,193, 63,997, 201,364 | 6,030 | 12.7 | 259, 542 | 2 | 0 | 0.680 | 67% |
| gepa_full | 103,777, 74,466, 199,765 | 5,764 | 12.2 | 241, 476 | 3 | 0 | 0.818 | 78% |

### Search phase (cost, tokens, latency, budget)
| | value |
|---|---|
| counted search rollouts | 809 of B = 900 (cache hits 142, lint-reject batches 0, infra 0); the shared seed baseline (147) is not charged |
| mean reward of counted rollouts | 0.5402 (search sets; selection-biased) |
| agent tokens / search episode (mean, p90) | prompt 71,020, 119,938; completion 3,926 |
| search episode seconds (mean, p90) | 169.4, 307.0 |
| optimizer calls | 70 (0 errors), model aws/claude-sonnet-5-5 |
| optimizer tokens | 902,011 in (non-cache-read) / 61,985 out / 0 cache-read / 0 cache-write |
| optimizer cost | **$2.42** proxy at Sonnet 5.5 list price |
| optimizer time | 640 s in calls (mean 9.1 s, p90 12.17 s); search wall 2026-10-20T22:20:08Z → 2026-10-21T07:03:37Z |
| dev diagnostic (57 dev, 1 trial) | 0.7193 (seed 0.3333) |
| agent cost | n/a (RITS is unpriced); tokens above |

### What changed (the frozen artifact)
- `policy/instructions.txt`: changed (11,350 → 15,974 chars)
- `tools/helpers.py`: unchanged from the seed
- `tools/api_notes.json`: changed (3 → 378 chars, 1 notes)
- `memory/playbook.md`: unchanged from the seed
- tree sha256 `eb3d11d38bad1193`; lint-clean; published in `docs/EVAL_APPWORLD_REST_STATE/gepa_full/artifact/` on branch `eval-rest`

### Isolation
Post-search and full scans: **0 test-id hits** in every optimizer-side record, workspace and transcript of this arm, and 0 in the orchestrating sessions' own transcripts. Not labelled an isolation breach. The only literal-string hits (`root_full`, `ground_truth`) are in the sandbox acceptance probe and the sandbox's own deny list.

### What this GEPA-Full is and is not
- "Full mode" here means GEPA's own MCPAdapter pattern: the prompt, the helpers module, and one tool-description component per AppWorld app (13 components), round-robin, evolved by GEPA 0.1.4's stock engine. Merge is off (the default).
- Custom proposer with `<new_text>` delimiters (the stock prompt's code fences break GEPA's parser), the lint inside it, and ≤ 2 re-reflections. Per-app reflective datasets hold only the steps that touched that app.
- The champion changed the prompt and one app's API note; the helpers stayed empty. With 13 components each visited about 3 times and a 3-task acceptance minibatch, tool components rarely change, as expected.
- max_metric_calls 894, so fresh episodes stay ≤ 900. Its dev score is the Pareto/selection set's.
- Common to all arms: Sonnet 5.5 optimizer (not each paper's model), gold-free feedback, B = 900 + 10M tokens, memory cap 14,000 tokens, 1 trial per task in search, the shared seed baseline.

### Deviations
See plan §15 and this issue's earlier posts. All five arms share the same harness, model client, decoding, caps, evaluator, final window and analysis.

### What the numbers cannot support
- **No ranking between candidates.** Each had one search seed, its own surface and budget use. Identical artifacts drifted by 4–6 TGC points between windows in earlier runs, and the two trials of a task agree on only 67–81% of tasks. For context only, Δ TGC vs seed of the other arms in this same window: HarnessLens 1.2, MIPROv2 24.4, Trace2Skill 35.4, Cap-Evolve-improve 16.1.
- Artifact-level statements only: one search run of this method under this configuration, not the method in general.
- Search-time scores are selection-biased; only the test_normal numbers above are held out.
- No multiplicity correction across the five comparisons.

Full tables: `docs/EVAL_APPWORLD_REST_STATE/final/RESULTS.md` and `analysis.json`; ledger: `docs/EVAL_APPWORLD_REST.md` §18.
