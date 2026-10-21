**Final results: Cap-Evolve-improve vs the seed agent (AppWorld test_normal).**

### Setup
- method: Cap-Evolve-improve, cap-evolve `cap-evolve-improve` @ 470f3fa; surface: P + T (prompt, helpers, API notes); search splits: train = val = train ∪ dev (147); its search score is a fit metric
- agent under test (all arms): `openai/gpt-oss-120b-a100` on RITS, reasoning medium, temperature 0, 50 steps, 100K completion tokens/task, the official simplified ReAct agent at AppWorld `42b5bcf`
- optimizer (every role): `aws/claude-sonnet-5-5` via the gateway (no temperature/seed sent); gold-free feedback (reward, failed requirement texts, collateral damage, steps, termination)
- budget: B = 900 counted search rollouts and 10M optimizer non-cache-read tokens; 1 search seed; 1 trial per task in search
- baseline: one shared seed run (train 90 + dev 57), reused by every candidate, not charged
- final window: 168 test_normal tasks × 6 arms × 2 trials = 2,016 cells, one shuffled order, 0 missing cells; seed and all five champions scored together

### Main result (test_normal, 168 tasks / 56 scenarios, 2 trials)
| arm | TGC | SGC | Δ TGC vs seed [95% CI] | Δ SGC vs seed [95% CI] | missing cells |
|---|---|---|---|---|---|
| seed | 33.3 | 8.0 | — | — | 0 |
| **Cap-Evolve-improve** | **49.4** | **35.7** | **16.1 [8.9, 23.5]** | 27.7 [17.9, 38.4] | 0 |

95% CI: scenario-clustered paired bootstrap (56 clusters, 10,000 resamples), unadjusted.

### TGC by difficulty
| arm | Easy (57) | Medium (48) | Hard (63) |
|---|---|---|---|
| seed | 55.3 | 27.1 | 18.3 |
| cape_improve | 76.3 | 51.0 | 23.8 |

### Agent cost, tokens and latency (final window, per episode)
| arm | prompt tok / ep (mean, p50, p90) | completion tok / ep | steps | s / ep (mean, p90) | step-cap | ctx-exceeded | pass fraction | trials agree |
|---|---|---|---|---|---|---|---|---|
| seed | 94,193, 63,997, 201,364 | 6,030 | 12.7 | 259, 542 | 2 | 0 | 0.680 | 67% |
| cape_improve | 122,550, 71,448, 276,878 | 7,009 | 9.4 | 293, 634 | 7 | 0 | 0.759 | 81% |

### Search phase (cost, tokens, latency, budget)
| | value |
|---|---|
| counted search rollouts | 882 of B = 900 (cache hits 216, lint-reject batches 0, infra 0); the shared seed baseline (147) is not charged |
| mean reward of counted rollouts | 0.7528 (search sets; selection-biased) |
| agent tokens / search episode (mean, p90) | prompt 56,907, 114,610; completion 3,662 |
| search episode seconds (mean, p90) | 186.5, 361.4 |
| optimizer calls | 6 (0 errors), model aws/claude-sonnet-5-5 |
| optimizer tokens | 4,033,132 in (non-cache-read) / 929,670 out / 63,105,027 cache-read / 3,678,643 cache-write |
| optimizer cost | **$31.82** proxy at Sonnet 5.5 list price (CLI-reported $79.56) |
| optimizer time | 5,665 s in calls (mean 944.2 s, p90 1536.16 s); search wall 2026-10-20T22:33:22Z → 2026-10-21T03:02:03Z |
| dev diagnostic (57 dev, 1 trial) | 0.8596 (seed 0.3333) |
| agent cost | n/a (RITS is unpriced); tokens above |

### What changed (the frozen artifact)
- `policy/instructions.txt`: changed (11,350 → 31,384 chars)
- `tools/helpers.py`: changed (174 → 22,663 chars, 38 helper functions)
- `tools/api_notes.json`: changed (3 → 5,725 chars, 37 notes)
- `memory/playbook.md`: unchanged from the seed
- tree sha256 `7d5614a96268f552`; lint-clean; published in `docs/EVAL_APPWORLD_REST_STATE/cape_improve/artifact/` on branch `eval-rest`

**Improvements of cap-evolve-improve, verified in effect** (post-search re-check of every iteration):

- I5 code pin: core imported from the 470f3fa worktree, clean: pass
- I4/I6 skills pin: `CAPEVOLVE_SKILLS_DIR` resolves to the pinned skills, not `~/.claude/skills`: pass
- I1 `gate_k_se: 0.5` in the spec and the run_config event: pass; `--k-se 0.5` on the hill-climb command line: pass
- I2/I3 the INSTRUCTIONS.md handed to the optimizer contains the strategy section and the #865 text in all iterations, with no old-template markers: pass
- I4 guidance SKILL.md files equal the pinned skills: pass
- I5 the pinned hill-climb `run.py` ran: pass (sha256 `c04938fc`)
- `instructions.diff` (pinned template vs the run's template) shows only the inserted AppWorld section

### Isolation
Post-search and full scans: **0 test-id hits** in every optimizer-side record, workspace and transcript of this arm, and 0 in the orchestrating sessions' own transcripts. Not labelled an isolation breach. The only literal-string hits (`root_full`, `ground_truth`) are in the sandbox acceptance probe and the sandbox's own deny list.

### What this Cap-Evolve-improve is and is not
- **The improved version as committed (470f3fa), every improvement checked in effect** (I1–I6, below): `gate_k_se` 0.5 explicit, optimizer instructions re-derived from the pinned template (strategy section included), the pinned #865 skills via `CAPEVOLVE_SKILLS_DIR`, the pinned V3 hill-climb core, and the claude-code optimizer.
- Stock hill-climb `--focus all`, 6 iterations, 1 trial, paired gate. Train = val = train ∪ dev (147), so its search score (0.837) is a fit metric. It overstates its test TGC (49.4) by about 34 points.
- Isolation applied by hand: a PATH shim runs the optimizer inside Claude Code's sandbox (deny rules on all gold, AppWorld, the evaluator and secrets; network restricted to the gateway; `--setting-sources ''`). The sandbox check (A9) passed only after one fix: the user's settings had widened the network allowlist.
- k = 0.5 raises false accepts on 1-trial gates; 4 of 5 scored iterations were accepted.
- Common to all arms: Sonnet 5.5 optimizer (not each paper's model), gold-free feedback, B = 900 + 10M tokens, memory cap 14,000 tokens, 1 trial per task in search, the shared seed baseline.

### Deviations
See plan §15 and this issue's earlier posts. All five arms share the same harness, model client, decoding, caps, evaluator, final window and analysis.

### What the numbers cannot support
- **No ranking between candidates.** Each had one search seed, its own surface and budget use. Identical artifacts drifted by 4–6 TGC points between windows in earlier runs, and the two trials of a task agree on only 67–81% of tasks. For context only, Δ TGC vs seed of the other arms in this same window: HarnessLens 1.2, MIPROv2 24.4, Trace2Skill 35.4, GEPA-Full 31.3.
- Artifact-level statements only: one search run of this method under this configuration, not the method in general.
- Search-time scores are selection-biased; only the test_normal numbers above are held out.
- No multiplicity correction across the five comparisons.

Full tables: `docs/EVAL_APPWORLD_REST_STATE/final/RESULTS.md` and `analysis.json`; ledger: `docs/EVAL_APPWORLD_REST.md` §18.
