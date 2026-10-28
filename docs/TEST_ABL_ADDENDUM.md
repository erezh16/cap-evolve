# AppWorld TEST_ABL: addendum (issues and decisions during execution)

Companion to [`docs/TEST_ABL.md`](TEST_ABL.md). The user instructed on 2026-10-28 at about 19:00 UTC: run to the end
without pausing; where two tasks conflict, serialize them; for any issue, make a reasonable decision without asking,
and record it here. Each item is also a `decision` or `error`/`repair` entry in the ledger `docs/TEST_ABL_STATUS.md`.
Counts and aggregates only.

## Decisions taken with the user before this instruction (2026-10-28, also plan §14)

| id | decision |
|---|---|
| U1 | Window 1 = seed + `abl_ref`, `abl_cc_best`, `abl_prompt`, `abl_tools`, `abl_notrace`, `abl_tracescore`; `abl_cc` (seed-identical) excluded |
| U2 | Gate arms deferred until ready, scored in a second window after window 1 (option "two windows") |
| U3 | A separate slot pool of 12 was approved while sharing the pod; not used, because U4 means no window overlaps the gate run |
| U4 | Window 1 starts only after the gate searches **and** the gate run's own P7 window have finished, so `root_full` is never unlocked while a gate optimizer is live |
| U5 | One issue per arm, the seed included |
| U6 | 12 deny rules added to the base session's settings (none removed) |

## Issues and decisions during execution

| # | UTC | issue | decision |
|---|---|---|---|
| A1 | 10-28 14:10 to 19:00 | The executing agent paused after B3 (twice) instead of continuing with B4 and P2. Hourly posts kept running on all 7 issues, but acceptance started only at about 19:00 | Resumed at once. The lost slack is about 4.5 h. Window 1's start is bound by the gate run (≈ 22:30 to 23:00), so the expected finish time does not move |
| A2 | 10-28 18:57 | Conflict check for acceptance during the gate searches. T1/T5 (4 dev episodes on `root_opt`, own slot pool) and T7/T8 (A10: a throwaway clone with a local bare remote, 12 dev cells) do not touch `root_full`, the gate run's state or its slots. **T3 unlocks `root_full`** to read the test ids | T1, T4, T5, T6, T7, T8, T9 and T10 run now. **T3 is serialized after the gate run's P7 has finished** (U4), immediately before the window-1 launch. T2's `root_full`-locked check is run read-only (mode check only) |
| A3 | 10-28 18:58 | TEST_ALL's acceptance scripts assume TEST_ALL's 13 arms (T3: 10,920 cells, 840 per arm; T4: `altk`, `harnesslens`; A10: TEST_ALL paths and `memok-testall`) | Generalised for the testabl profile (committed on `test-abl`). T4's expectation for the ablation arms: no memory block; P changes the first request; T is live where present. T4 passed for all 7 arms (seed byte-identical to stock, 23 messages) |
| A4 | 10-28 18:59 | The two memory guards (the ablation run's and this run's) sample the same cgroup and agree (both 10.15% at 14:05) | Kept both. Before any launch, both `memok-abl` and `memok-testabl` must be OK |
| A5 | 10-28 19:10 | The gate run's own P5 to P7 (its dev diagnostic, full scan and 672-cell window) are **not automatic**: `p4_abl.py` ends the gate P4 with "started by hand after a check", and no orchestrating session of the gate run is reachable from this session. Under U4, window 1 could wait indefinitely | `test_abl/launch_when_clear.py` (nohup) waits until no gate search process is alive and the gate P4 `phase_done` is in the ablation ledger. It then starts window 1 at once if the gate run's P7 has completed. Otherwise it waits up to **30 minutes** for a gate P5/P6/P7 to begin. If none begins, **window 1 goes first**, and the gate run's P7 must then wait for it (window 1 holds `root_full` unlocked for about 23 h; a gate P7 started meanwhile would be relocked by window 1's end and vice versa). If a gate P5 to P7 does start within the grace period, window 1 waits for its P7 to finish (U4). Before every launch it re-checks that `root_full` is mode 000, that no gate-run window or chain is alive, and that both memory guards are OK. This session does **not** start the gate run's own P5 to P7 (they belong to its plan and its session) |
| A6 | 10-28 19:10 | Window 2 needs the gate champions frozen **and** the gate run's own scan/reset passed, and the gate run's P7 is either done or not started | Window 2's launch reuses the same watcher (`--window 2`) after window 1 completes. The gate issues open when both gate champions are frozen with a passing reset check and a 0-hit isolation scan (ledger entries), whether or not the gate P7 ran |
