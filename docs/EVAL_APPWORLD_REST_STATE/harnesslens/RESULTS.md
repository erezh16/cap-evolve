**Final results: HarnessLens vs the seed agent (AppWorld test_normal).**

### Setup
- method: HarnessLens, jhxu5214/HarnessLens @ 369a5c8; surface: P + T + M (prompt, helpers, API notes, playbook); search splits: train (90) only; no validation split (the champion is the last accepted parent)
- agent under test (all arms): `openai/gpt-oss-120b-a100` on RITS, reasoning medium, temperature 0, 50 steps, 100K completion tokens/task, the official simplified ReAct agent at AppWorld `42b5bcf`
- optimizer (every role): `aws/claude-sonnet-5-5` via the gateway (no temperature/seed sent); gold-free feedback (reward, failed requirement texts, collateral damage, steps, termination)
- budget: B = 900 counted search rollouts and 10M optimizer non-cache-read tokens; 1 search seed; 1 trial per task in search
- baseline: one shared seed run (train 90 + dev 57), reused by every candidate, not charged
- final window: 168 test_normal tasks × 6 arms × 2 trials = 2,016 cells, one shuffled order, 0 missing cells; seed and all five champions scored together

### Main result (test_normal, 168 tasks / 56 scenarios, 2 trials)
| arm | TGC | SGC | Δ TGC vs seed [95% CI] | Δ SGC vs seed [95% CI] | missing cells |
|---|---|---|---|---|---|
| seed | 33.3 | 8.0 | — | — | 0 |
| **HarnessLens** | **34.5** | **13.4** | **1.2 [-5.4, 7.4]** | 5.4 [0.0, 10.7] | 0 |

95% CI: scenario-clustered paired bootstrap (56 clusters, 10,000 resamples), unadjusted.

### TGC by difficulty
| arm | Easy (57) | Medium (48) | Hard (63) |
|---|---|---|---|
| seed | 55.3 | 27.1 | 18.3 |
| harnesslens | 54.4 | 28.1 | 21.4 |

### Agent cost, tokens and latency (final window, per episode)
| arm | prompt tok / ep (mean, p50, p90) | completion tok / ep | steps | s / ep (mean, p90) | step-cap | ctx-exceeded | pass fraction | trials agree |
|---|---|---|---|---|---|---|---|---|
| seed | 94,193, 63,997, 201,364 | 6,030 | 12.7 | 259, 542 | 2 | 0 | 0.680 | 67% |
| harnesslens | 93,050, 63,759, 192,686 | 5,869 | 12.8 | 248, 510 | 6 | 0 | 0.701 | 71% |

### Search phase (cost, tokens, latency, budget)
| | value |
|---|---|
| counted search rollouts | 162 of B = 900 (cache hits 195, lint-reject batches 0, infra 0); the shared seed baseline (147) is not charged |
| mean reward of counted rollouts | 0.5679 (search sets; selection-biased) |
| agent tokens / search episode (mean, p90) | prompt 67,929, 137,073; completion 4,309 |
| search episode seconds (mean, p90) | 166.4, 300.0 |
| optimizer calls | 270 (0 errors), model aws/claude-sonnet-5-5 |
| optimizer tokens | 9,410,029 in (non-cache-read) / 1,042,108 out / 2,279,443 cache-read / 801,654 cache-write |
| optimizer cost | **$30.1** proxy at Sonnet 5.5 list price (CLI-reported $7.78) |
| optimizer time | 8,039 s in calls (mean 29.8 s, p90 50.76 s); search wall 2026-10-21T03:07:29Z → 2026-10-21T05:56:12Z |
| dev diagnostic (57 dev, 1 trial) | 0.3333 (seed 0.3333) |
| agent cost | n/a (RITS is unpriced); tokens above |

### What changed (the frozen artifact)
- `policy/instructions.txt`: unchanged from the seed
- `tools/helpers.py`: unchanged from the seed
- `tools/api_notes.json`: unchanged from the seed
- `memory/playbook.md`: unchanged from the seed
- tree sha256 `85a0da9cec2206a7`; lint-clean; published in `docs/EVAL_APPWORLD_REST_STATE/harnesslens/artifact/` on branch `eval-rest`

### Isolation
Post-search and full scans: **0 test-id hits** in every optimizer-side record, workspace and transcript of this arm, and 0 in the orchestrating sessions' own transcripts. Not labelled an isolation breach. The only literal-string hits (`root_full`, `ground_truth`) are in the sandbox acceptance probe and the sandbox's own deny list.

### What this HarnessLens is and is not
- **A port, not the shipped runtime.** HarnessLens's controller logic, gates, cost formulas and all role prompts are vendored byte-identical from 369a5c8. Its runtime (opencode/codex/pi CLIs, tau2, docker) cannot run AppWorld, so it was replaced. The analysis roles are plain-chat calls with the trial bundle inlined; the Harness Editor is a sandboxed `claude -p` with Read/Write/Edit/Glob/Grep.
- **Inert.** 13 iterations, 0 accepted (every Review returned reject_delta or revise_delta). The search stopped at the common 10M optimizer-token cap after only 162 of 900 counted rollouts. Inlining bundles makes each iteration cost about 0.8M tokens, so the token cap bound the search long before B. The frozen artifact is the seed, so its test score measures the seed in this window; the gap to the seed arm is window noise (trial agreement 67–71%).
- Other port choices: channel preflight is lint + render checks, not one real rollout; screen batches of 10 TRAIN tasks (code minimum 5); confirmation re-uses the trial seed, so a parent re-run is a cache hit (rule Q1); reasoning text is left out of trial packets.
- Common to all arms: Sonnet 5.5 optimizer (not each paper's model), gold-free feedback, B = 900 + 10M tokens, memory cap 14,000 tokens, 1 trial per task in search, the shared seed baseline.

### Deviations
See plan §15 and this issue's earlier posts. All five arms share the same harness, model client, decoding, caps, evaluator, final window and analysis.

### What the numbers cannot support
- **No ranking between candidates.** Each had one search seed, its own surface and budget use. Identical artifacts drifted by 4–6 TGC points between windows in earlier runs, and the two trials of a task agree on only 67–81% of tasks. For context only, Δ TGC vs seed of the other arms in this same window: MIPROv2 24.4, Trace2Skill 35.4, GEPA-Full 31.3, Cap-Evolve-improve 16.1.
- Artifact-level statements only: one search run of this method under this configuration, not the method in general.
- Search-time scores are selection-biased; only the test_normal numbers above are held out.
- No multiplicity correction across the five comparisons.

Full tables: `docs/EVAL_APPWORLD_REST_STATE/final/RESULTS.md` and `analysis.json`; ledger: `docs/EVAL_APPWORLD_REST.md` §18.
