# AppWorld ablations: interim status report

Snapshot: **2026-10-26 14:15 UTC**, during phase P4 (the searches). Plan: [`docs/ABLATIONS.md`](ABLATIONS.md); ledger:
[`docs/ABLATION_STATUS.md`](ABLATION_STATUS.md) (entries ABL-0000 to ABL-0347).

## Status, best score and ETA per arm

**Train score** = the arm's best search score: mean reward over the 147 search tasks (official train 90 + dev 57),
1 trial. The search tunes on these same tasks (train = val), so it is a **fit metric, selection-biased**, not a
held-out result. **Test score** = `test_normal` (168 tasks × 2 trials) in the one final window (phase P7), which has
not started. By plan rule §12, no test score of any arm is produced or posted before the window completes, so the
test column is empty for every arm.

The seed (unmodified agent) scored **0.401** on the same 147 tasks (train 0.389, dev 0.421), the common baseline of
every arm.

| arm | what it is | status | iterations scored / accepted | counted rollouts (of 882) | best train score (fit metric) | test score | optimizer USD (proxy / CLI-reported) | ETA search done (UTC) |
|---|---|---|---|---|---|---|---|---|
| `abl_ref` ([#930](https://github.com/skillberry-ai/cap-evolve/issues/930)) | full cap-evolve (reference) | **search done**; frozen, scanned, reset | 6 / 5 | 882 | **0.830** | not yet (P7) | 34.81 / 87.03 | done 13:53 on 10-26 |
| `abl_prompt` ([#932](https://github.com/skillberry-ai/cap-evolve/issues/932)) | prompt only | **search done**; frozen, scanned, reset | 6 / 3 | 882 | **0.816** | not yet (P7) | 29.07 / 72.68 | done 12:26 on 10-26 |
| `abl_tools` ([#933](https://github.com/skillberry-ai/cap-evolve/issues/933)) | tools only | **search done**; frozen, scanned, reset | 6 / 3 | 882 | **0.694** | not yet (P7) | 34.67 / 86.68 | done 12:30 on 10-26 |
| `abl_notrace` ([#934](https://github.com/skillberry-ai/cap-evolve/issues/934)) | no traces (evaluation feedback only) | **searching**, iteration 2 of 6 | 1 / 1 | 148 | 0.490 | not yet (P7) | 3.23 / 8.07 | ≈ 21:30–23:30 on 10-26 |
| `abl_tracescore` ([#935](https://github.com/skillberry-ai/cap-evolve/issues/935)) | traces + score only (no evaluation feedback) | **searching**, iteration 2 of 6 | 1 / 1 | 147 | 0.490 | not yet (P7) | 8.93 / 22.32 | ≈ 21:30–23:30 on 10-26 |
| `abl_cc` ([#931](https://github.com/skillberry-ai/cap-evolve/issues/931)) | plain Claude Code, no cap-evolve | **session 2 running** (since 14:13); first real candidate evaluating | evaluations done: 1 (seed copy, cached) | 76 | 0.401 (seed copy; no candidate scored yet) | not yet (P7) | session 1: — / 4.14 | unknown; ≈ 18:00–02:00 (see below) |

Proxy USD is at Claude Sonnet 5.5 list price ($2 in, $10 out, $0.20 cache read, $2.50 cache write per MTok) from
each session's `modelUsage`; CLI-reported USD is the Claude Code CLI's own total. The agent under test (gpt-oss-120b
on RITS) is unpriced. Every arm uses only `aws/claude-sonnet-5-5` as its optimizer.

## Overall ETA

| phase | expected (UTC) |
|---|---|
| P4: last search ends (`abl_notrace`, `abl_tracescore`, or `abl_cc`, whichever is last) | ≈ 23:30 on 10-26 to 02:00 on 10-27 |
| P5 dev diagnostic + P6 full isolation scan and reset checks | ≈ 1 h after P4 |
| P7 final window: 168 test tasks × 7 arms (seed + 6 champions) × 2 trials = 2,352 cells | ≈ 7 h (about 330 cells/h at 24 slots) |
| P8 analysis + P9 results comment on each issue (train and **test** scores, Δ vs `abl_ref` with CIs and Holm p) | **≈ 08:00–10:00 on 10-27** |

The basis is measured, not assumed: a scored iteration took about 90–100 minutes with three searches sharing the 24
episode slots (wave 1). The two information arms are on the same pace and have 5 iterations left.

## What the ETA depends on

- **`abl_cc`** is one Claude Code session with up to 1,200 turns. How long it runs and how many of its 6 possible
  evaluations it uses is the method's own choice, so its finish time is the least certain. One evaluation of 147
  tasks takes about an hour.
- **Episode speed** (RITS latency, episode length) and any **memory pause** (none so far; peak 49.6% of the
  container's 32 GB).

## Events that affected the search (all in the ledger)

- **Gateway key budget exhausted** (2026-10-25 17:55 UTC; ABL-0180): every optimizer call got HTTP 429 for about
  15 minutes. Iterations 2 to 6 of the first wave were lost (no optimizer output, 0 rollouts), not scored as
  rejections. After the key was replaced, the three arms resumed in place with 5 extra iterations, so each still
  had 6 scored iterations and the same 882-rollout budget (ABL-0181). No counted rollout was lost.
- **`abl_cc` first session ended after 9 minutes** (ABL-0340): it submitted its first candidate, found it could not
  wait for the hour-long evaluation, scheduled a reminder that cannot fire in print mode, and ended its turn. By user
  decision it gets **one fresh session** with the same 3-line prompt and the same budget (ABL-0341), disclosed as a
  deviation from the plan's no-re-prompting rule. The first session's candidate keeps evaluating.
- **`abl_cc` session init** shows Claude Code's bundled skills and full tool set, as in every arm's optimizer (same
  CLI, same flags); recorded as a deviation by user decision (ABL-0057).
- **Plumbing repairs**, none affecting a scored result: the ledger writer's git race (ABL-0217), the reset check's
  environment and temp-dir comparison (ABL-0306, ABL-0330), and two `abl_cc` launch fixes (ABL-0347).
- **Missing episodes**: in `abl_ref` two iterations were scored on 146 of 147 tasks; one episode each hit the
  30-minute wall cap twice and counts as missing data, not as a failure (the harness's standard handling).

## Isolation so far

All three finished arms: **0 test-id hits** in every optimizer record, workdir, transcript and frozen artifact; only
`aws/claude-sonnet-5-5` used; the optimizer instructions and gate K = 0.2 in effect in every iteration. The sandbox
check (A9) passed for all six arms before any counted rollout: 30 planted secrets each, 0 leaked. The full scan of
every arm and of the orchestrating sessions runs in P6, before the test window.

## What these numbers cannot support yet

- The train scores are fit metrics on the tasks the searches tuned on; they overstate held-out performance (in
  earlier AppWorld runs by 20–35 points). Only the P7 test scores are held out.
- One search seed per arm: any difference between arms mixes the ablated factor with search randomness. Earlier
  windows measured about 3–4 TGC points of SE per arm, so differences under about 8 points will not be resolved.
- Comparisons are made only inside the one final window; nothing here should be read as a ranking.

Counts and aggregates only: no task id, task text, trajectory or per-task outcome.
