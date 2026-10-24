# AppWorld eval CE3: Cap-Evolve Improvement 2 at gate K = 0.2

Status: **PLAN**, written 2026-10-24. Nothing in sections 4 to 9 has run yet. The status ledger is a separate file,
**`docs/EVAL_APPWORLD_CE3_STATUS.md`**, appended during the run under an exclusive file lock (CE2 rule R3).

CE3 is **one more arm of CE2** (`docs/EVAL_APPWORLD_CE2.md`, on branch `eval-ce2`, executed 2026-10-22 to 2026-10-23):
the same candidate, harness, models, splits, isolation, memory guard, ledger and posting machinery, with the gate's
K set to **0.2**. **CE2 is the base plan of CE3**: every rule, check and procedure of CE2 (its sections 0 to 19, rules
R1 to R5 and Q1 to Q4, acceptance A1 to A13 and A-CE2 1 to 9) applies to CE3 unchanged, **except** the differences in
section 2 below. The CE2 ledger (`docs/EVAL_APPWORLD_CE2_STATUS.md`) records the repairs and user decisions that CE3
inherits (section 3).

| arm id | method | pin | gate |
|---|---|---|---|
| `ce3_k02` | Cap-Evolve, Improvement 2, K = 0.2 | `3db96a0` (`3db96a08ef77d7701f21771d389c6471a5d88344`), the pin CE2 ran on | `gate_k_se: 0.2` |

Tracking issue: one new issue on `skillberry-ai/cap-evolve`, labels `paper-experiment`, `algorithm`, titled "AppWorld eval
CE3: Cap-Evolve impr2, K=0.2 vs seed (gpt-oss-120b)". Its body is this plan's projection.

---

## 1. What K = 0.2 means here

The paired gate accepts a child iff its mean paired per-task Δ over the 147 val tasks exceeds **0.2 · SE(Δ)**. On
147 tasks with 1 trial, CE2 measured SE(Δ) between 0.040 and 0.050, so the bar is about **0.008 to 0.010**: a net gain
of about **1.5 tasks** clears it. This is the loosest gate of the series (CE2: K = 1 and 2; REST's Improvement 1:
K = 0.5) and accepts more noise-level children. Expected (stated in advance): more accepts than CE2's 1 of 6 per
arm, and a higher risk of drift between val and test. Neither is a fault.

For context only, from CE2's per-iteration tables (search score, fit metric): no child of iterations 2 to 6 had a
positive Δ̄ in either arm except ce2_k1 iteration 2 (Δ̄ +0.034, SE 0.046), which K = 0.2 would have accepted. CE3 is
an independent search: it does not replay CE2's candidates.

## 2. Differences from CE2 (everything else as CE2)

| CE2 | CE3 | source |
|---|---|---|
| two arms, `ce2_k1` (K = 1) and `ce2_k2` (K = 2), launched together | **one arm, `ce3_k02`, `gate_k_se: 0.2`** | user, 2026-10-24 |
| 2 issues (#909, #910) | **1 new issue** (above), same posting rules: milestones, every iteration's verdict, hourly status, final results comment | user |
| `optimizer_usd_per_iter: 40`, `max_optimizer_usd: 300` (CE2-0022); 10M optimizer non-cache-read token cap in the shim | **no money or token cap**: `optimizer_usd_per_iter` absent (no `--max-budget-usd`), `max_optimizer_usd: 0` (off), the shim's token cap off. Spend is still recorded exactly (modelUsage, proxy USD and CLI-reported USD) | user, 2026-10-24: "ignore any budget caps" |
| 6 scored iterations; `max_metric_calls: 1029`; B = 900 counted rollouts | **kept**: 6 scored iterations, `max_metric_calls: 1029`, B = 900 (these fix the experiment's size, not its spend, so the arm stays comparable with K = 1 and K = 2) | user, 2026-10-24 |
| final window: seed + `ce2_k1` + `ce2_k2`, 1,008 cells, one window | **only `ce3_k02` is run**: 168 test_normal × 2 trials (seeds 5000 + k) = **336 cells**. The seed, `ce2_k1` and `ce2_k2` test_normal records of CE2's window (2026-10-23 19:11 to 22:41 UTC, 1,008 cells, 0 missing) are **reused, not re-run** | user, 2026-10-24 |
| arm − seed and K2 − K1 within one window | `ce3_k02` − seed, − `ce2_k1`, − `ce2_k2`, each with the same scenario-clustered paired bootstrap CI, **labelled "cross-window"** in every table and post (CE2 measured 4 to 6 TGC points of drift between windows for identical artifacts) | user, 2026-10-24 |
| A-CE2-SAME (two arms differ only in K) | **A-CE3-SAME**: the rendered `capevolve.yaml` and optimizer INSTRUCTIONS of `ce3_k02` differ from CE2's `ce2_k1` only in `gate_k_se` and the two removed money caps; the INSTRUCTIONS are byte-identical (sha256 `dccf0853…`) | consistency |
| independence check of the two arms after iteration 1 | not applicable (one arm) | — |
| acceptance A9 per arm | A9 for `ce3_k02` in its exact launch configuration; the deny list adds **both CE2 run roots** (`/workspace/aw_ce2/run_k1`, `run_k2`) and CE2's frozen artifacts, so the K = 0.2 optimizer cannot see CE2's searches (CE2 rule R1 "the other arm's run") | consistency |
| A-CE2 4 gate unit check (1.5·SE, 2.5·SE, 0.7·SE at K = 1, 2) | A-CE3 4: with the pinned `gate.py`, Δ̄ = 0.3·SE is **accepted** at k_se = 0.2 and rejected at 1; Δ̄ = 0.1·SE is rejected at 0.2; the hill-climb command line carries `--k-se 0.2` | consistency |

## 3. Inherited from CE2 (already in place; re-verified, not rebuilt)

- **Build:** CE2's `/workspace/aw_ce2/build` (symlinks into REST's build, B2-verified) and `venv-ce2` (core from the
  `cape-impr2` worktree). The `cape-impr2` worktree is at `3db96a0`, clean. CE2's `verify_build.py` re-runs read-only.
- **Seed baseline:** the 147 REST P3 seed records, already copied and hash-verified into CE2's cache (CE2-0004). CE3
  uses its own `AW_STATE` (below) and copies them with CE2's `seed_reuse.py` (same hash checks). 0 fresh seed episodes.
- **User decisions of CE2 that stay in force:** pin `3db96a0` (CE2-0012); the orchestrating-session scan covers
  this run's own sessions, other sessions' hits disclosed as out of scope (CE2-0087); a sub-agent shell probe
  that returns nothing and reads nothing is reported as a "contained probe" (CE2-0087).
- **Code:** CE2's `examples/appworld/` (`ce2/` driver, `awce2.py` profile, ledger writer, autopost, scan, window,
  analyze, report). CE3 adds a `ce3` profile and arm, and a window mode that runs one arm and joins the reused CE2
  records for the analysis. Branch **`eval-ce3`** from `origin/eval-ce2`, worktree `/workspace/worktrees/eval-ce3`.
- **State:** `/workspace/aw_ce3` (`AW_HOME`; its own `state/`, run root `run_k02/`), `/tmp/aw_ce3` (scratch). CE2's
  state is read only by trusted scripts (the seed copy, the reused-records join) and is denied to the optimizer.

## 4. Phases

| phase | content |
|---|---|
| P0 | decisions (this section 2), issue number, CE3-0000 |
| P1 | branch, worktree, `ce3` profile, `AW_STATE`, memory guard, seed-record copy, A-CE3 driver changes |
| P2 | acceptance: A1, A2, A4, A9, A11, A12, A13 re-run for CE3 (cheap, same code); A-CE3 1 to 8; A3, A5 to A8 and A10 carried from CE2 (unchanged code, recorded) |
| P4 | the search (6 iterations) → freeze → isolation scan |
| P5 | dev diagnostic (cache hits) |
| P6 | full isolation scan, model-usage and J1/K re-check; gate as CE2 |
| P7 | the window: `ce3_k02` only, 336 cells; root_full unlocked at start, relocked at end |
| P8 | analysis: `ce3_k02` alone; vs the reused CE2 seed, K = 1 and K = 2 records, labelled cross-window |
| P9 | results comment on the CE3 issue |

## 5. Budget and timeline (projection; no money cap)

| phase | counted rollouts | wall (estimate) |
|---|---|---|
| P1 + P2 | ≈ 15 (not counted) | 1 to 1.5 h |
| P4, 6 iterations | ≤ 882 | 5 to 6 h (CE2: about 55 to 70 min per iteration) |
| P5, P6 | 0 | < 0.5 h |
| P7, 336 cells at 24 slots | 336 | about 1.5 h |
| P8, P9 | 0 | < 0.5 h |
| **total** | **≈ 1,220** | **≈ 8 to 10 h** |

Optimizer spend is not capped. CE2's per-arm rate was about $40 proxy at Sonnet 5.5 list price ($63 to $102 CLI-reported)
over 6 iterations; a looser gate accepts more children, which changes the parent, not the session length, so a similar
range is expected. Every session's modelUsage, proxy USD and CLI-reported USD are recorded and reported.

## 6. Risks specific to CE3

| risk | mitigation |
|---|---|
| a session with no USD cap runs very long | `optimizer_max_turns: 200` stays (a turn cap, not a budget); a session over 90 minutes is flagged on the issue and in the ledger |
| cross-window comparisons read as paired | every comparison with CE2's arms labelled "cross-window" in tables, posts and the ledger |
| the optimizer sees CE2's searches | both CE2 run roots and CE2's artifacts in the deny list; A9 plants a secret there |
