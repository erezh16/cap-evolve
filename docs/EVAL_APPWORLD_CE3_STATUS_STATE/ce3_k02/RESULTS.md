**Final results — Cap-Evolve-impr2 K=0.2 (gate K = 0.2) vs the seed agent, AppWorld test_normal.**

### Setup
- method: cap-evolve "Improvement 2", commit `3db96a0` (= `8194578` + two Self-check wording fixes in the optimizer template, user decision, ledger CE2-0012; core and skills byte-identical to `8194578`), stock hill-climb `--focus all`, deterministic orchestration, `capabilities: [system-prompt, tools]`, paired gate with **`gate_k_se: 0.2`**; CE2's arms (K = 1, K = 2; #909, #910) are identical except K and the money caps
- agent under test (all arms): `openai/gpt-oss-120b-a100` on RITS, `hosted_vllm/` route, reasoning medium, temperature 0, 50 steps, 6,000 max completion tokens per call, 100K completion tokens per task, the official simplified ReAct agent at AppWorld `42b5bcf`
- optimizer (main loop and every sub-agent): `aws/claude-sonnet-5-5` via the gateway, Claude Code CLI 2.1.270 in Claude Code's sandbox (landrun + proot), `--setting-sources ''`, no temperature/seed sent; gold-free feedback (reward, failed requirement texts, collateral damage, steps, termination)
- search: train = val = official train ∪ dev (147), 1 trial per task (seed 100), 6 scored iterations, B = 900 counted rollouts, `max_metric_calls` 1029, **no money or token cap** (CE3 plan §2: no `optimizer_usd_per_iter`, `max_optimizer_usd` 0 = off, no token cap; spend recorded exactly); seed baseline **reused** from REST's P3 run (147 records, verified by hash and code identity, not re-run)
- final window: **this arm only**, 168 test_normal × 2 trials (seeds 5000 + k) = 336 cells (order seed 2026102407), 24 global slots. The seed, K = 1 and K = 2 test records are **reused from CE2's window** (2026-10-23, 1,008 cells, 0 missing), by user decision: every comparison below is cross-window

### Main result (test_normal, 168 tasks / 56 scenarios, 2 trials)
| arm | window | TGC | SGC | Δ TGC vs seed [95% CI] | Δ SGC vs seed [95% CI] | missing cells |
|---|---|---|---|---|---|---|
| seed | CE2 (reused) | 37.8 | 15.2 | — | — | 0 |
| ce2_k1 | CE2 (reused) | 51.2 | 28.6 | (CE2 within-window: see #909, #910) | | 0 |
| ce2_k2 | CE2 (reused) | 47.3 | 27.7 | (CE2 within-window: see #909, #910) | | 0 |
| **Cap-Evolve-impr2 K=0.2** | **this (CE3)** | **61.6** | **44.6** | **23.8 [16.7, 31.2]** (cross-window) | 29.5 [18.8, 40.2] (cross-window) | 0 |

| comparison (cross-window) | Δ TGC [95% CI] | Δ SGC [95% CI] |
|---|---|---|
| ce3_k02 − seed | 23.8 [16.7, 31.2] | 29.5 [18.8, 40.2] |
| ce3_k02 − ce2_k1 | 10.4 [4.5, 16.4] | 16.1 [8.0, 24.1] |
| ce3_k02 − ce2_k2 | 14.3 [8.0, 20.5] | 17.0 [8.0, 25.9] |

**Cross-window.** The new arm ran in this window (2026-10-24); the seed and both CE2 champions are CE2's window records (2026-10-23), reused by user decision. Identical artifacts drifted 4–6 TGC points between windows in earlier runs, so these Δ include window drift and are weaker than within-window comparisons.

95% CI: scenario-clustered paired bootstrap (56 clusters, 10,000 resamples), unadjusted. TGC = mean over tasks of the mean over trials; SGC = scenario passes in a trial iff all its tasks pass.

### TGC by difficulty
| arm | Easy (57) | Medium (48) | Hard (63) |
|---|---|---|---|
| seed | 61.4 | 28.1 | 23.8 |
| ce2_k1 | 75.4 | 49.0 | 31.0 |
| ce2_k2 | 68.4 | 50.0 | 26.2 |
| ce3_k02 | 78.9 | 64.6 | 43.7 |

### Test phase: agent cost, tokens and latency (final window, per episode)
| arm | prompt tok / ep (mean, p50, p90) | completion tok / ep (mean, p90) | steps | s / ep (mean, p50, p90) | step-cap | token-cap | ctx-exceeded | pass fraction | trials agree |
|---|---|---|---|---|---|---|---|---|---|
| seed | 95,153, 67,280, 181,274 | 6,316, 12,803 | 13.0 | 256, 191, 509 | 5 | 0 | 0 | 0.704 | 66% |
| ce2_k1 | 88,784, 60,626, 185,408 | 6,915, 16,071 | 9.6 | 279, 183, 621 | 2 | 0 | 0 | 0.751 | 70% |
| ce2_k2 | 95,999, 70,167, 196,623 | 6,878, 15,142 | 10.6 | 278, 209, 578 | 3 | 0 | 0 | 0.733 | 77% |
| ce3_k02 | 114,902, 91,960, 220,559 | 7,207, 15,239 | 11.1 | 285, 221, 582 | 1 | 0 | 0 | 0.787 | 80% |

Agent cost: n/a (RITS is unpriced). Final window wall: 2026-10-24T15:21:12.656893Z → 2026-10-24T16:35:53.902090Z.

### Train (search) phase: per-iteration verdicts
| iter | val (fit metric) | parent val | paired Δ̄ | SE | K·SE (K = 0.2) | verdict |
|---|---|---|---|---|---|---|
| 1 | 0.7483 | 0.3741 | +0.3741 | 0.0465 | 0.0093 | **accept** |
| 2 | 0.7891 | 0.7483 | +0.0408 | 0.0385 | 0.0077 | **accept** |
| 3 | 0.8299 | 0.7891 | +0.0408 | 0.0385 | 0.0077 | **accept** |
| 4 | 0.8367 | 0.8299 | +0.0068 | 0.0341 | 0.0068 | reject |
| 5 | 0.8299 | 0.8299 | +0.0000 | 0.0334 | 0.0067 | reject |
| 6 | 0.8776 | 0.8299 | +0.0476 | 0.0352 | 0.0070 | **accept** |

### Train (search) phase: cost, tokens, latency, budget
| | value |
|---|---|
| seed baseline (reused from REST P3, not re-run, not counted) | val = train ∪ dev 0.3741; train 0.4; dev 0.3333 (147 records, 1 trial, seed 100) |
| champion's search score | 0.8775510204081632 (fit metric: train = val = train ∪ dev, selection-biased) |
| iterations scored / consumed / accepted | 6 / 6 / 4 |
| counted search rollouts | 882 of B = 900 (cache hits 204, lint-reject batches 0, infra 0) |
| cap-evolve metric calls | 1029 of 1,029 |
| mean reward of counted rollouts | 0.8186 (search set; selection-biased) |
| agent tokens / search episode | prompt mean 77,756, p50 66,167, p90 133,153; completion mean 4,532; max prompt 21,128 |
| search episode steps / seconds | steps mean 8.8; seconds mean 208.6, p50 165.3, p90 372.0; step-cap 0, token-cap 0, ctx-exceeded 0 |
| optimizer sessions | 6 (0 errors); models in modelUsage: `aws/claude-sonnet-5-5` (6 sessions) |
| optimizer tokens (modelUsage, main loop + sub-agents) | 6,269,403 input (non-cache-read, incl. cache writes) / 1,194,931 output / 85,454,718 cache-read / 5,787,729 cache-write |
| optimizer cost (gateway) | **$44.47** proxy at Sonnet 5.5 list price ($2 in, $10 out, $0.20 cache read, $2.50 cache write per MTok); CLI-reported $111.18; cap-evolve's own tally $111.18231024999999 |
| optimizer time | 7,062 s in sessions (mean 1177.1 s, p90 1665.15 s) |
| search wall time | 2026-10-24T11:07:01Z → 2026-10-24T15:17:35Z |
| dev diagnostic (57 dev, 1 trial; dev ⊂ val) | 0.8772 (seed 0.3333) |
| agent cost (RITS) | n/a (unpriced); tokens above |

### What changed (the frozen artifact)
- `policy/instructions.txt`: changed (11,350 → 24,677 chars, 6,056 tokens (seed 2,745))
- `tools/helpers.py`: changed (174 → 17,029 chars, 40 helper functions, 365 lines)
- `tools/api_notes.json`: changed (3 → 7,397 chars, 39 notes, 6,125 chars)
- champion `cand_0006`; tree sha256 `e0ec3d94752bd3a2` = the run's own candidate; lint-clean; published in `docs/EVAL_APPWORLD_CE3_STATUS_STATE/ce3_k02/artifact/` on branch `eval-ce2`

### Evidence that the evaluated system is Improvement 2 with K = 0.2
- J3 code pin: core imported from the `3db96a0` worktree, clean: pass
- J2/J4 skills pin: `CAPEVOLVE_SKILLS_DIR` resolves to the pinned skills, not `~/.claude/skills`: pass
- J5 `gate_k_se: 0.2` in the spec and the run_config event: pass / pass; `--k-se 0.2` on the hill-climb command line: pass
- J1 Improvement 2's instructions (objective score, PREPARATION, Strategies for constructing edits incl. SOFT / JUDGEMENT CALLS, AppWorld facts) in every iteration's `INSTRUCTIONS.md` (6 iterations), no old-template marker: pass
- J2 guidance SKILL.md files equal the pinned skills (diagnose: head lines): pass
- J3 the pinned hill-climb `run.py` ran (sha256 `c04938fc`): pass
- optimizer models seen in modelUsage after the search: ['aws/claude-sonnet-5-5']; other models: []
- `instructions.diff` (pinned template vs the run's template) shows only the inserted AppWorld section; the two arms' specs differ only in `gate_k_se` and their instructions are identical (A-CE2-SAME)

### Isolation
Post-search and full scans: **0 test-id hits** in every optimizer-side record, workdir, transcript and the frozen artifact of this arm; 0 in the orchestrating sessions' own transcripts (43 files). Not labelled an isolation breach. Literal-string counts per location are in `docs/EVAL_APPWORLD_CE3_STATUS_STATE/isolation_scan.json`.

### Deviations
- candidate pin `3db96a0` instead of the plan's `8194578` (two wording fixes in the template's Self-check, user decision; CE2-0012);
- the seed baseline is REST's P3 run, reused (plan D5); the released-solution scoring probe was not repeated (plan §17);
- no money or token cap, and the window ran this arm only with the seed, K = 1 and K = 2 records reused from CE2 (CE3 plan §2, user decisions 2026-10-24);
- other incidents and repairs are in the ledger (`docs/EVAL_APPWORLD_CE3_STATUS.md`), none affecting a counted rollout unless stated there.

### What the numbers cannot support
- Artifact-level statements only: one search run of this configuration, not the method in general.
- Every comparison with the seed, K = 1 or K = 2 is cross-window (their records are CE2's window), so it includes window drift; and each K had one search seed, so K is confounded with search randomness.
- Search scores are fit metrics (train = val, selection-biased); only the test_normal numbers above are held out.
- REST's Improvement 1 numbers come from another window (identical artifacts drifted 4–6 TGC points between windows) and are not compared here.
- No multiplicity correction.

Full tables: `docs/EVAL_APPWORLD_CE3_STATUS_STATE/final/RESULTS.md` and `analysis.json`; ledger: `docs/EVAL_APPWORLD_CE3_STATUS.md`.
