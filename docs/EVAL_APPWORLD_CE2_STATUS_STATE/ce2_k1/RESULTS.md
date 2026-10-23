**Final results — Cap-Evolve-impr2 K=1 (gate K = 1) vs the seed agent, AppWorld test_normal.**

### Setup
- method: cap-evolve "Improvement 2", commit `3db96a0` (= `8194578` + two Self-check wording fixes in the optimizer template, user decision, ledger CE2-0012; core and skills byte-identical to `8194578`), stock hill-climb `--focus all`, deterministic orchestration, `capabilities: [system-prompt, tools]`, paired gate with **`gate_k_se: 1`**; the other CE2 arm is identical except K
- agent under test (all arms): `openai/gpt-oss-120b-a100` on RITS, `hosted_vllm/` route, reasoning medium, temperature 0, 50 steps, 6,000 max completion tokens per call, 100K completion tokens per task, the official simplified ReAct agent at AppWorld `42b5bcf`
- optimizer (main loop and every sub-agent): `aws/claude-sonnet-5-5` via the gateway, Claude Code CLI 2.1.270 in Claude Code's sandbox (landrun + proot), `--setting-sources ''`, no temperature/seed sent; gold-free feedback (reward, failed requirement texts, collateral damage, steps, termination)
- search: train = val = official train ∪ dev (147), 1 trial per task (seed 100), 6 scored iterations, B = 900 counted rollouts, `max_metric_calls` 1029, `optimizer_usd_per_iter` 40 and `max_optimizer_usd` 300 (raised from 15 / 120 by user decision, CE2-0022); seed baseline **reused** from REST's P3 run (147 records, verified by hash and code identity, not re-run)
- final window: 168 test_normal × 3 arms (seed, K = 1, K = 2) × 2 trials (seeds 5000 + k) = 1,008 cells, one shuffled order (seed 2026102207), 24 global slots; all three arms run fresh in this window

### Main result (test_normal, 168 tasks / 56 scenarios, 2 trials)
| arm | TGC | SGC | Δ TGC vs seed [95% CI] | Δ SGC vs seed [95% CI] | missing cells |
|---|---|---|---|---|---|
| seed | 37.8 | 15.2 | — | — | 0 |
| **Cap-Evolve-impr2 K=1** | **51.2** | **28.6** | **13.4 [7.1, 20.2]** | 13.4 [3.6, 23.2] | 0 |
| Cap-Evolve-impr2 K=2 | 47.3 | 27.7 | 9.5 [2.1, 17.3] | 12.5 [5.4, 20.5] | 0 |

`ce2_k2 − ce2_k1`: Δ TGC -3.9 [-11.6, 3.9], Δ SGC -0.9 [-9.8, 8.0]. One search seed per arm, so this difference confounds the gate K with search randomness.

95% CI: scenario-clustered paired bootstrap (56 clusters, 10,000 resamples), unadjusted. TGC = mean over tasks of the mean over trials; SGC = scenario passes in a trial iff all its tasks pass.

### TGC by difficulty
| arm | Easy (57) | Medium (48) | Hard (63) |
|---|---|---|---|
| seed | 61.4 | 28.1 | 23.8 |
| ce2_k1 | 75.4 | 49.0 | 31.0 |
| ce2_k2 | 68.4 | 50.0 | 26.2 |

### Test phase: agent cost, tokens and latency (final window, per episode)
| arm | prompt tok / ep (mean, p50, p90) | completion tok / ep (mean, p90) | steps | s / ep (mean, p50, p90) | step-cap | token-cap | ctx-exceeded | pass fraction | trials agree |
|---|---|---|---|---|---|---|---|---|---|
| seed | 95,153, 67,280, 181,274 | 6,316, 12,803 | 13.0 | 256, 191, 509 | 5 | 0 | 0 | 0.704 | 66% |
| ce2_k1 | 88,784, 60,626, 185,408 | 6,915, 16,071 | 9.6 | 279, 183, 621 | 2 | 0 | 0 | 0.751 | 70% |
| ce2_k2 | 95,999, 70,167, 196,623 | 6,878, 15,142 | 10.6 | 278, 209, 578 | 3 | 0 | 0 | 0.733 | 77% |

Agent cost: n/a (RITS is unpriced). Final window wall: 2026-10-23T19:11:11.756840Z → 2026-10-23T22:41:50.529538Z.

### Train (search) phase: per-iteration verdicts
| iter | val (fit metric) | parent val | paired Δ̄ | SE | K·SE (K = 1) | verdict |
|---|---|---|---|---|---|---|
| 1 | 0.6871 | 0.3741 | +0.3129 | 0.0481 | 0.0481 | **accept** |
| 2 | 0.7211 | 0.6871 | +0.0340 | 0.0457 | 0.0457 | reject |
| 3 | 0.6803 | 0.6871 | -0.0068 | 0.0497 | 0.0497 | reject |
| 4 | 0.6667 | 0.6871 | -0.0204 | 0.0478 | 0.0478 | reject |
| 5 | 0.6803 | 0.6871 | -0.0068 | 0.0468 | 0.0468 | reject |
| 6 | 0.6599 | 0.6871 | -0.0272 | 0.0501 | 0.0501 | reject |

### Train (search) phase: cost, tokens, latency, budget
| | value |
|---|---|
| seed baseline (reused from REST P3, not re-run, not counted) | val = train ∪ dev 0.3741; train 0.4; dev 0.3333 (147 records, 1 trial, seed 100) |
| champion's search score | 0.6870748299319728 (fit metric: train = val = train ∪ dev, selection-biased) |
| iterations scored / consumed / accepted | 6 / 6 / 1 |
| counted search rollouts | 882 of B = 900 (cache hits 204, lint-reject batches 0, infra 0) |
| cap-evolve metric calls | 1029 of 1,029 |
| mean reward of counted rollouts | 0.6825 (search set; selection-biased) |
| agent tokens / search episode | prompt mean 52,454, p50 42,838, p90 102,914; completion mean 3,777; max prompt 22,498 |
| search episode steps / seconds | steps mean 6.2; seconds mean 157.7, p50 128.5, p90 293.2; step-cap 0, token-cap 0, ctx-exceeded 0 |
| optimizer sessions | 6 (0 errors); models in modelUsage: `aws/claude-sonnet-5-5` (6 sessions) |
| optimizer tokens (modelUsage, main loop + sub-agents) | 4,917,940 input (non-cache-read, incl. cache writes) / 1,126,883 output / 89,087,964 cache-read / 4,074,396 cache-write |
| optimizer cost (gateway) | **$40.96** proxy at Sonnet 5.5 list price ($2 in, $10 out, $0.20 cache read, $2.50 cache write per MTok); CLI-reported $102.4; cap-evolve's own tally $102.39875200000003 |
| optimizer time | 6,370 s in sessions (mean 1061.7 s, p90 1382.35 s) |
| search wall time | 2026-10-23T11:46:30Z → 2026-10-23T16:32:33Z |
| dev diagnostic (57 dev, 1 trial; dev ⊂ val) | 0.7368 (seed 0.3333) |
| agent cost (RITS) | n/a (unpriced); tokens above |

### What changed (the frozen artifact)
- `policy/instructions.txt`: changed (11,350 → 17,404 chars, 4,277 tokens (seed 2,745))
- `tools/helpers.py`: changed (174 → 9,219 chars, 21 helper functions, 227 lines)
- `tools/api_notes.json`: changed (3 → 7,599 chars, 32 notes, 6,630 chars)
- champion `cand_0001`; tree sha256 `4be1fd94503a9ff4` = the run's own candidate; lint-clean; published in `docs/EVAL_APPWORLD_CE2_STATUS_STATE/ce2_k1/artifact/` on branch `eval-ce2`

### Evidence that the evaluated system is Improvement 2 with K = 1
- J3 code pin: core imported from the `3db96a0` worktree, clean: pass
- J2/J4 skills pin: `CAPEVOLVE_SKILLS_DIR` resolves to the pinned skills, not `~/.claude/skills`: pass
- J5 `gate_k_se: 1` in the spec and the run_config event: pass / pass; `--k-se 1` on the hill-climb command line: pass
- J1 Improvement 2's instructions (objective score, PREPARATION, Strategies for constructing edits incl. SOFT / JUDGEMENT CALLS, AppWorld facts) in every iteration's `INSTRUCTIONS.md` (6 iterations), no old-template marker: pass
- J2 guidance SKILL.md files equal the pinned skills (diagnose: head lines): pass
- J3 the pinned hill-climb `run.py` ran (sha256 `c04938fc`): pass
- optimizer models seen in modelUsage after the search: ['aws/claude-sonnet-5-5']; other models: []
- `instructions.diff` (pinned template vs the run's template) shows only the inserted AppWorld section; the two arms' specs differ only in `gate_k_se` and their instructions are identical (A-CE2-SAME)

### Isolation
Post-search and full scans: **0 test-id hits** in every optimizer-side record, workdir, transcript and the frozen artifact of this arm; 0 in the orchestrating sessions' own transcripts (22 files). Not labelled an isolation breach. Literal-string counts per location are in `docs/EVAL_APPWORLD_CE2_STATUS_STATE/isolation_scan.json`.

### Deviations
- candidate pin `3db96a0` instead of the plan's `8194578` (two wording fixes in the template's Self-check, user decision; CE2-0012);
- the seed baseline is REST's P3 run, reused (plan D5); the released-solution scoring probe was not repeated (plan §17);
- other incidents and repairs are in the ledger (`docs/EVAL_APPWORLD_CE2_STATUS.md`), none affecting a counted rollout unless stated there.

### What the numbers cannot support
- Artifact-level statements only: one search run of this configuration, not the method in general.
- `ce2_k2 − ce2_k1` confounds the gate K with search randomness (one search seed per arm).
- Search scores are fit metrics (train = val, selection-biased); only the test_normal numbers above are held out.
- REST's Improvement 1 numbers come from another window (identical artifacts drifted 4–6 TGC points between windows) and are not compared here.
- No multiplicity correction.

Full tables: `docs/EVAL_APPWORLD_CE2_STATUS_STATE/final/RESULTS.md` and `analysis.json`; ledger: `docs/EVAL_APPWORLD_CE2_STATUS.md`.
