**Final results: Trace2Skill vs the seed agent (AppWorld test_normal).**

### Setup
- method: Trace2Skill, Qwen-Applications/Trace2Skill @ 3d0b52a; surface: M (static skill playbook); search splits: train (90): trajectories and the 3-way selection; dev unused in search
- agent under test (all arms): `openai/gpt-oss-120b-a100` on RITS, reasoning medium, temperature 0, 50 steps, 100K completion tokens/task, the official simplified ReAct agent at AppWorld `42b5bcf`
- optimizer (every role): `aws/claude-sonnet-5-5` via the gateway (no temperature/seed sent); gold-free feedback (reward, failed requirement texts, collateral damage, steps, termination)
- budget: B = 900 counted search rollouts and 10M optimizer non-cache-read tokens; 1 search seed; 1 trial per task in search
- baseline: one shared seed run (train 90 + dev 57), reused by every candidate, not charged
- final window: 168 test_normal tasks × 6 arms × 2 trials = 2,016 cells, one shuffled order, 0 missing cells; seed and all five champions scored together

### Main result (test_normal, 168 tasks / 56 scenarios, 2 trials)
| arm | TGC | SGC | Δ TGC vs seed [95% CI] | Δ SGC vs seed [95% CI] | missing cells |
|---|---|---|---|---|---|
| seed | 33.3 | 8.0 | — | — | 0 |
| **Trace2Skill** | **68.8** | **47.3** | **35.4 [29.2, 42.0]** | 39.3 [29.5, 50.0] | 0 |

95% CI: scenario-clustered paired bootstrap (56 clusters, 10,000 resamples), unadjusted.

### TGC by difficulty
| arm | Easy (57) | Medium (48) | Hard (63) |
|---|---|---|---|
| seed | 55.3 | 27.1 | 18.3 |
| trace2skill | 86.0 | 79.2 | 45.2 |

### Agent cost, tokens and latency (final window, per episode)
| arm | prompt tok / ep (mean, p50, p90) | completion tok / ep | steps | s / ep (mean, p90) | step-cap | ctx-exceeded | pass fraction | trials agree |
|---|---|---|---|---|---|---|---|---|
| seed | 94,193, 63,997, 201,364 | 6,030 | 12.7 | 259, 542 | 2 | 0 | 0.680 | 67% |
| trace2skill | 158,496, 124,318, 297,165 | 6,705 | 13.4 | 288, 584 | 1 | 0 | 0.840 | 77% |

### Search phase (cost, tokens, latency, budget)
| | value |
|---|---|
| counted search rollouts | 270 of B = 900 (cache hits 450, lint-reject batches 0, infra 0); the shared seed baseline (147) is not charged |
| mean reward of counted rollouts | 0.7852 (search sets; selection-biased) |
| agent tokens / search episode (mean, p90) | prompt 129,084, 211,415; completion 5,109 |
| search episode seconds (mean, p90) | 209.7, 401.1 |
| optimizer calls | 717 (0 errors), model aws/claude-sonnet-5-5 |
| optimizer tokens | 3,436,541 in (non-cache-read) / 940,656 out / 0 cache-read / 0 cache-write |
| optimizer cost | **$16.28** proxy at Sonnet 5.5 list price |
| optimizer time | 5,398 s in calls (mean 7.5 s, p90 14.41 s); search wall 2026-10-21T03:11:39Z → 2026-10-21T09:23:50Z |
| dev diagnostic (57 dev, 1 trial) | 0.6491 (seed 0.3333) |
| agent cost | n/a (RITS is unpriced); tokens above |

### What changed (the frozen artifact)
- `policy/instructions.txt`: unchanged from the seed
- `tools/helpers.py`: unchanged from the seed
- `tools/api_notes.json`: unchanged from the seed
- `memory/playbook.md`: changed (0 → 20,159 chars, 6,719 tokens)
- tree sha256 `a6b03deb2a044ed4`; lint-clean; published in `docs/EVAL_APPWORLD_REST_STATE/trace2skill/artifact/` on branch `eval-rest`

### Isolation
Post-search and full scans: **0 test-id hits** in every optimizer-side record, workspace and transcript of this arm, and 0 in the orchestrating sessions' own transcripts. Not labelled an isolation breach. The only literal-string hits (`root_full`, `ground_truth`) are in the sandbox acceptance probe and the sandbox's own deny list.

### What this Trace2Skill is and is not
- **Gold-free single-call analysts.** Trace2Skill's default agentic analyst reads the gold file and is not used; the single-call error and success analysts see the trajectory plus the failed-requirement texts only.
- Combined mode, MAP batch 1, merge batch 5, ≤ 5 merge levels, translation on, ≤ 3 verification rounds. Prompts adapted from spreadsheet to AppWorld wording (diff published), with reference files forbidden. The skill is delivered as a static playbook (≤ 14,000 tokens; the champion's is about 4.4K tokens).
- **The 3-seed selection, after a re-run (disclosed earlier on this issue).** Seeds 42 and 43 first replayed seed 41 through the gateway's response cache. By user decision they were re-run with a per-seed run line, so they sampled independently. Inputs were unchanged and no extra trajectory data was used. Train TGC: 0.778 / 0.800 / 0.778; seed 42 was selected (selection-biased).
- It saw no dev data during search, so its dev diagnostic (0.649) is the only number it did not select on before test.
- Common to all arms: Sonnet 5.5 optimizer (not each paper's model), gold-free feedback, B = 900 + 10M tokens, memory cap 14,000 tokens, 1 trial per task in search, the shared seed baseline.

### Deviations
See plan §15 and this issue's earlier posts. All five arms share the same harness, model client, decoding, caps, evaluator, final window and analysis.

### What the numbers cannot support
- **No ranking between candidates.** Each had one search seed, its own surface and budget use. Identical artifacts drifted by 4–6 TGC points between windows in earlier runs, and the two trials of a task agree on only 67–81% of tasks. For context only, Δ TGC vs seed of the other arms in this same window: HarnessLens 1.2, MIPROv2 24.4, GEPA-Full 31.3, Cap-Evolve-improve 16.1.
- Artifact-level statements only: one search run of this method under this configuration, not the method in general.
- Search-time scores are selection-biased; only the test_normal numbers above are held out.
- No multiplicity correction across the five comparisons.

Full tables: `docs/EVAL_APPWORLD_REST_STATE/final/RESULTS.md` and `analysis.json`; ledger: `docs/EVAL_APPWORLD_REST.md` §18.
