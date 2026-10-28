# AppWorld ablations of cap-evolve `main`: the two gate arms (addendum plan)

Status: **PLAN**, written 2026-10-28. Nothing below has run yet. This file is an **addendum** to
[`docs/ABLATIONS.md`](ABLATIONS.md) ("the base plan", commit `22f46ee`). It adds two cap-evolve ablation arms that
differ from the reference `abl_ref` **only in the acceptance gate**. Every rule, setting, model, budget, check and
procedure of the base plan applies to them unchanged, except where a section below says otherwise. Where this file
does not mention a section, that section of the base plan applies as written, with these two arms as the cap-evolve
arms it runs.

| arm id | name | what differs from the reference (the ablated factor) | issue |
|---|---|---|---|
| `abl_nogate` | **Cap evolve no gate** | no acceptance gate: every scored candidate is kept and becomes the new parent, even if it is worse | [#938](https://github.com/skillberry-ai/cap-evolve/issues/938) |
| `abl_naivegate` | **Cap evolve naive gate** | naive gate: a candidate is kept iff its mean paired gain is above 0, with no noise margin (no significance test) | [#939](https://github.com/skillberry-ai/cap-evolve/issues/939) |

The reference stays `abl_ref` ([#930](https://github.com/skillberry-ai/cap-evolve/issues/930)): the paired gate,
accepting iff Δ̄ > 0.2 · SE(Δ). Its search, champion and final-window records are already done (ledger ABL-0000 to
ABL-0715) and are **reused, not re-run** (section G7).

The ledger is the same `docs/ABLATION_STATUS.md` on branch `eval-abl` (fork `erezh16/cap-evolve`). It continues from
ABL-0716. Issues are on `skillberry-ai/cap-evolve`. Never push an evaluation branch to `origin`.

**The executing agent must read, in full and before anything else:** the base plan (all of it, rules R1 to R5 and Q1
to Q4 verbatim), this addendum, and every `error`, `repair`, `decision` and `abort` entry of the ledger ABL-0000 to
ABL-0715. Those entries are this run's own lessons. Where a source and this addendum disagree, stop, record it in the
ledger and ask the user (rule R5).

---

## G0. Scope at a glance (differences from base plan section 0 only)

| item | the two gate arms |
|---|---|
| code under test | unchanged: cap-evolve **`main` at `75b3bcd`**, core and skills unmodified (D4). Both gates are made from `main`'s own spec key `gate_k_se` (section G2) |
| everything else in base section 0 | unchanged: seed, agent `openai/gpt-oss-120b-a100` on RITS (medium effort, temperature 0), optimizer `aws/claude-sonnet-5-5` for every role, 147 search tasks (train ∪ dev), 1 search trial (seed 100), **B = 882 counted rollouts**, `max_metric_calls: 1029`, 6 scored iterations, no money or token cap, 200 turns per optimizer session, isolation, memory guard, ledger, parallelism |
| final window | **2 arms only** (the two new champions) × 168 `test_normal` × 2 trials, trial seeds **5000 + k** as in the first window = **672 cells**. The seed's and `abl_ref`'s cells come from the first window (user decision 2026-10-28; section G7) |

## G1. Decisions (added to base section 2)

| id | decision | source |
|---|---|---|
| D14 | two more cap-evolve arms, `abl_nogate` and `abl_naivegate`, under the base plan, with the same models and budget as every earlier arm | user request 2026-10-28 |
| D15 | both gates are set through `main`'s `gate_k_se` with `gate_mode: paired`: **`gate_k_se: -100000`** (no gate) and **`gate_k_se: 0`** (naive gate). No core change (D4 holds) | this addendum, section G2 |
| D16 | final window: only the two new champions, with the first window's trial seeds (5000 + k). The comparisons with `abl_ref` and the seed use their first-window cells: a **cross-window** comparison, disclosed as a deviation from base section 15 | user decision 2026-10-28 |
| D17 | the optimizer is told the true acceptance rule of its arm (AppWorld facts section, G4) | user decision 2026-10-28 |

## G2. How the gate is ablated with `main`'s own keys

`main`'s hill-climb passes `--gate-mode` and `--k-se` from the spec (`core/cap_evolve/cli.py:981-982`) to
`gate.decide(mode="paired")`. That accepts iff `Δ̄ > k_se · SE`, where Δ̄ is the mean paired per-task delta over the
147 val tasks and SE its standard error (`core/cap_evolve/gate.py:422-459`). Probed 2026-10-28 with the pinned
`gate.py` in `venv-abl`:

| arm | spec | rule in effect | probe: +1 task (Δ̄ = +0.0068) | probe: 20 tasks broken (Δ̄ = −0.136) | probe: all deltas 0 |
|---|---|---|---|---|---|
| `abl_ref` | `gate_k_se: 0.2` | Δ̄ > 0.2 · SE | accept | reject | reject |
| `abl_naivegate` | `gate_k_se: 0` | **Δ̄ > 0** | accept | reject | reject |
| `abl_nogate` | `gate_k_se: -100000` | Δ̄ > −100000 · SE, true for every scored candidate (G2.1) | accept | **accept** | reject (SE = 0 fallback, G2.1) |

### G2.1 What "no gate" does and does not change, exactly
- On 147 tasks with binary rewards, the smallest SE that is not zero is about 0.0068 (one task moved). −100000 · 0.0068 =
  −680, far below the lowest possible Δ̄ of −1. So **every scored candidate with SE > 0 is accepted**, whatever its
  score.
- **SE = 0** happens only when every task's delta is the same. With binary rewards that means every delta is 0: the
  candidate scored exactly like its parent on every task. `gate.py`'s fallback then applies Δ̄ > 0 and rejects it,
  so the parent's files stay. The scores are the same either way. Each such step is counted and reported.
- The value is written as the integer `-100000`. `{k:g}` (`run_abl.kfmt`) prints it as `-100000`, and argparse accepts
  that as the value of `--k-se`. (`-1e+06` would be refused as a flag, as probed.) The launch checks confirm
  `--k-se -100000` on the hill-climb command line (A-ABL-CORE item 4).
- Unchanged in both arms, as in `abl_ref`, because they are not acceptance on quality:
  - the coverage guard (`min_coverage` 0.6: a step with fewer valid scores is **indecisive**, not accepted);
  - a lint-rejected or surface-voided candidate (never scored, so never kept);
  - footprint masking of the delta vector (it changes SE only, which cannot change either verdict);
  - `no_regression` and `gate_max_broke`, off as in the reference.
- **The champion** is the last accepted candidate, as in every arm. For `abl_nogate` that is the last scored candidate,
  even if an earlier one scored higher. This is what "no gate" means. The report also shows the best-scoring candidate
  of the search for context, but that candidate is not scored in the window (D16: two champions only).

## G3. Arms and surfaces (rows added to base section 3)

| arm | optimizer | editable surface (enforced) | proposer feedback | gate |
|---|---|---|---|---|
| `abl_nogate` | as `abl_ref` | as `abl_ref` | as `abl_ref` (full F1 tier) | **none** (`gate_k_se: -100000`) |
| `abl_naivegate` | as `abl_ref` | as `abl_ref` | as `abl_ref` (full F1 tier) | **naive**, Δ̄ > 0 (`gate_k_se: 0`) |

**A-ABL-SAME** (base 5.4), rows added:

| arm | the only allowed differences from `abl_ref` |
|---|---|
| `abl_nogate` | `gate_k_se`, the AppWorld facts section's gate sentence |
| `abl_naivegate` | `gate_k_se`, the AppWorld facts section's gate sentence |

## G4. Optimizer instructions (base 9.4)

The base, the placement and the diff rules of base 9.4 apply as written. The reference's facts block
(`abl/facts_ref.md`) says, in its first paragraph: "… and accepts it only if the mean paired gain over the current best
clears its noise gate." Each arm replaces **exactly that clause** and nothing else:

- `abl_nogate`: "… and in this run keeps every candidate that is scored: there is no acceptance gate, so the candidate
  you ship becomes the new current best whatever its score, even if it is lower. A candidate that fails the lint is not
  run and not kept. The paragraph "How your edit is judged" further below describes the framework's default
  significance bar; it does not apply in this run."
- `abl_naivegate`: "… and keeps it if its mean paired gain over the current best is above zero: any net gain, however
  small, is kept, with no noise margin. The paragraph "How your edit is judged" further below describes the framework's
  default significance bar; it does not apply in this run, where the bar is zero."

Why the second sentence: core's fixed `{{ALGO_BRIEF}}` (`harness._algorithm_brief`) tells every arm that a candidate is
"ACCEPTED only if the per-task improvement clears a significance bar". Core is not changed (D4), so that text stays,
and the facts section, which comes earlier in the file, states that it does not apply. This is disclosed in both
reports. The RESULT stamps the framework writes (ACCEPTED / REJECTED) follow the arm's real rule.

`instructions.py` gets two `facts_for` branches, each a single `_once()` replacement. The stored
`diff -u abl_ref <arm>` must show that one clause and nothing else.

## G5. The arms

### G5.1 `abl_nogate`: Cap evolve no gate
- **Issue:** [#938](https://github.com/skillberry-ai/cap-evolve/issues/938).
- **Ablated factor:** the acceptance gate. Every scored candidate is accepted and becomes the parent of the next
  iteration: a random walk driven only by the optimizer's proposals. Everything else is as `abl_ref`: both surfaces,
  full F1 feedback, the reference instructions apart from the G4 clause, 6 scored iterations, B = 882.
- **Activate:**
  - spec: `gate_mode: paired`, `gate_k_se: -100000`; everything else byte-equal to `abl_ref`'s rendered spec;
  - `ARM_CONFIG["abl_nogate"]` = `abl_ref`'s row; `P.K_SE["abl_nogate"] = -100000`;
  - instructions: `abl/INSTRUCTIONS.abl_nogate.md`;
  - launch: `bash examples/appworld/abl/launch_abl.sh abl_nogate` (project `/workspace/aw_abl/arms/abl_nogate/.capevolve/project`,
    run ts `abl_nogate_s0`).
- **Acceptance:**
  - A-ABL-CORE 1 to 9, with item 3 expecting `gate_k_se: -100000` and item 4 expecting `--k-se -100000`;
  - the gate unit check (pinned `gate.py`, `decide(mode="paired", k_se=-100000)`): a 20-task regression (Δ̄ = −0.136)
    is **accepted**; a +1 task is accepted; an all-zero vector is rejected (SE = 0 fallback);
  - one mock dry run (4 dev ids) whose mock edit makes the candidate score **lower** than its parent. It must be recorded
    as accepted and become `best_id`. (Done by a trusted mock; no task file is read.)
  - A9 with this arm's exact launch configuration.
- **Reset:** base 9.8; item 5 also checks that a fresh render of `abl_ref`'s spec still has `gate_k_se: 0.2`.
- **Report:** label "no gate". Also report: the number of accepted steps with Δ̄ < 0 and Δ̄ = 0; the val score of the
  last scored candidate (the champion) against the best scored candidate of the search; and how far the val score
  falls from its peak.

### G5.2 `abl_naivegate`: Cap evolve naive gate
- **Issue:** [#939](https://github.com/skillberry-ai/cap-evolve/issues/939).
- **Ablated factor:** the gate's noise margin. A candidate is kept iff Δ̄ > 0, so any net improvement counts, however
  small and whether or not it is statistically significant. Everything else is as `abl_ref`.
- **Activate:**
  - spec: `gate_mode: paired`, `gate_k_se: 0`; everything else byte-equal to `abl_ref`'s rendered spec;
  - `ARM_CONFIG["abl_naivegate"]` = `abl_ref`'s row; `P.K_SE["abl_naivegate"] = 0`;
  - instructions: `abl/INSTRUCTIONS.abl_naivegate.md`;
  - launch: `bash examples/appworld/abl/launch_abl.sh abl_naivegate` (run ts `abl_naivegate_s0`).
- **Acceptance:**
  - A-ABL-CORE 1 to 9, with item 3 expecting `gate_k_se: 0` and item 4 expecting `--k-se 0`;
  - the gate unit check: Δ̄ = 0.1 · SE (rejected by `abl_ref`'s 0.2) is **accepted**; Δ̄ = −0.1 · SE is rejected;
    an all-zero vector is rejected;
  - A9 with this arm's exact launch configuration.
- **Reset:** base 9.8, as in G5.1.
- **Report:** label "naive gate (any gain)". Also report the steps with 0 < Δ̄ ≤ 0.2 · SE: those accepted here that
  `abl_ref`'s rule would have rejected. Context: in the first wave, 1 of 30 scored iterations of the five cap-evolve arms
  fell in that band (counts only), so this arm may well take the same path as `abl_ref`. If so, the result is "no
  measurable difference at this budget", and that is reported plainly.

## G6. Execution (differences from base sections 6, 11, 12, 13)

- **B0 again (the run's environment was idle since 2026-10-27 18:09 UTC):**
  1. **Memory guard first.** `MEMSTATE.json` is stale (about 16 h old on 2026-10-28) and `memok-abl` says WAIT. Restart
     `memguard.py` and confirm a fresh state within 10 s **before anything else** (R2). Record the earlier peak (90.19%)
     in the entry.
  2. **Deny rules (R1.4).** The 40 rules of `/workspace/aw_abl/launch/exec-settings.json` must be in force in the
     orchestrating session's settings (`/workspace/worktrees/base/.claude/settings.local.json`, git-excluded) and in
     `/workspace/worktrees/eval-abl/.claude/settings.local.json`. On 2026-10-28 the base copy was found **empty**
     (0 rules; the full copy was in `settings.local.json.abl-r1-backup-20261027`). It was restored byte-equal (40 rules)
     before any sealed path could be touched, and a live probe (a `Read` of `AW_STATE/cache/deny_probe.txt`) was refused.
     Record this as an `error`/`repair` pair. Re-check both files, and run the probe again, at the start of every
     orchestrating session and before P7.
  3. `root_full` mode 000 (checked 2026-10-28), `abl-main` clean at `75b3bcd` (checked), `/workspace` 10 GB free.
- **B1:** add `abl_nogate` and `abl_naivegate` to `CANDIDATES`, `CAPE_ARMS`, `ISSUES`, `METHOD_NAMES`, `RUN_ROOTS`,
  `RUN_TS`; `K_SE` per G5. `FINAL_ARMS_RUN = ("abl_nogate", "abl_naivegate")`. The first window's seed and `abl_ref`
  cells are read as reused cells. Use the cross-window path that `analyze.py` already has for `REUSED_WINDOW_ARMS`
  (CE3), reading from this run's own `AW_STATE/final`. Each change gets a unit test; commit each.
- **B5:** two `facts_for` branches (G4); `ARM_CONFIG` rows; `reset_check.py` knows both arms. Nothing else in the drivers
  changes.
- **Isolation (base 11):** each new arm's `AW_CAPE_EXTRA_DENY` covers **every** other arm's root: the six first-wave
  arms and the other new arm. The first-wave roots are read-only already (reset 9.8.6). A9 for each new arm before any
  counted rollout.
- **P2:** acceptance as G5 plus A1, A9, A11, A12 and A13 for the new arms. A13 must show that the new arms' baseline is
  the shared seed run, served from the cache: 147 hits, 0 counted, and a fresh seed episode raises `SeedRerunRefused`.
  Base checks that do not depend on the arm (A3 to A8, A10) passed in the first run. Re-run them read-only through
  `verify_build.py` and record that they still pass.
- **P3:** not re-run. The seed baseline is the cached P3 run (rule Q4).
- **P4:** both searches at once (one wave of 2, within the 3-search limit), 24 global slots. Per arm: search → freeze →
  reset check → isolation scan.
- **P5 to P6:** as in the base plan, for the two new arms. The P6 scan also covers this session's and any later
  orchestrating session's transcripts.
- **Posts (base 12):** milestone posts and hourly status posts on **both new issues** (`autopost.py` with the two issues
  only). No post goes to #930 to #935, apart from one short cross-reference comment on #930 (the reference) that names
  the two new issues.
- **Resume (base 13.4):** unchanged.

## G7. Final window and statistics (differences from base section 15)

- **Freeze:** as base 15, for the two new champions. Commit their hashes and the order hash before the first window
  episode.
- **Window:** 168 `test_normal` × **2 arms** (`abl_nogate`, `abl_naivegate`) × 2 trials = **672 cells**. Trial seeds
  are 5000 + k, k ∈ {0, 1}, the same as the first window, so each (task, trial) pair is run with the same seed for all
  arms. One shuffled order from a seed recorded in advance (`20261028` + a fixed suffix, in `manifest.json`).
  `root_full` is unlocked at P7 start and relocked at P7 end; both are logged. Everything else in base 15's window
  rules applies, including "no test trajectory is opened by anyone".
- **Reused cells:** the seed's and `abl_ref`'s 336 cells each from the first window (ABL-0700). They are read only as
  counts and rewards by `analyze.py`, never opened as trajectories.
- **Statistics:**
  - primary contrasts (2): `abl_nogate − abl_ref` and `abl_naivegate − abl_ref`;
  - secondary: each new arm − seed, and `abl_nogate − abl_naivegate`;
  - scenario-clustered paired bootstrap 95% CIs (56 clusters, 10,000 resamples), and Holm over the 2 primary
    contrasts. The 5 first-wave contrasts are not re-adjusted; a joint Holm over all 7 primary contrasts is reported as
    a labelled secondary;
  - the full base 5.2 metric table for both new arms at search and test, with `abl_ref` and the seed as reference rows.
- **Cross-window caveat (D16), stated in every report:** the new arms' cells run about two days after the first window.
  RITS serving, latency and any drift between the two windows are mixed into each contrast. As a check, report the
  first-window TGC of every arm next to the new arms, and flag any infra-retry or timeout rate that differs by more than
  2× between the windows. A difference smaller than about 8 TGC points is not resolved in any case (base 15).

## G8. Deviations (added to base section 16)

| source | here | why |
|---|---|---|
| base 15: one window for all arms | the two new arms in a second window; seed and `abl_ref` cells reused | D16, user decision 2026-10-28 |
| base 9.4: the AppWorld facts section never names the gate | the gate arms' facts sentence states the arm's acceptance rule and says core's `ALGO_BRIEF` paragraph does not apply | D17, user decision 2026-10-28 |
| base 13.4/#908: `abl_ref` in the same window | `abl_ref` is not re-run | D16 |
| #908 GATE-NONE (`abl_gate: none` on the unmerged branch) | `gate_k_se: -100000` on `main` (identical except for the SE = 0 step, G2.1) | D4 |

## G9. Budget and timeline (projection)

| phase | counted rollouts | wall (estimate) |
|---|---|---|
| G6 B0 to B5 (code changes and unit tests) + P2 acceptance (mock dry runs, A9 ×2) | ≈ 10 (not counted) | 2 to 3 h |
| P4: 2 searches at once, ≤ 882 each, 6 iterations | ≤ 1,764 | 7 to 9 h (first wave: 90 to 100 min per iteration with 3 searches; 2 searches are expected to be a little faster) |
| P5 + P6 | 0 (cache hits) | < 1 h |
| P7 window, 672 cells at 24 slots | 672 | 2 to 2.5 h (about 330 cells/h) |
| P8 + P9 | 0 | 1 h |
| **total** | **≈ 2,440** | **≈ 13 to 16 h** |

Optimizer spend is not capped. The five first-wave cap-evolve arms used $34 to $121 CLI-reported each (proxy about 40%
of that). Expect about $150 to $200 CLI-reported for the two arms. The agent is on RITS (unpriced; tokens reported).

## G10. Risks (added to base section 18)

| risk | mitigation |
|---|---|
| no gate drifts down and ends below the seed | that is a valid result of the ablation; the report shows the walk and the best-vs-last gap |
| the naive gate takes `abl_ref`'s path, so there is no contrast | expected to be possible (G5.2); report the band count and the null result as a bound |
| cross-window drift | same trial seeds; first-window context rows; infra-rate flag (G7) |
| the deny rules are lost again between sessions | G6 B0.2 check and live probe at every session start and before P7 |
| a negative `k_se` is rejected on some path (dashboard, intake) | A-ABL-CORE items 3 and 4 on the real launch; the mock dry run must show the accept |
