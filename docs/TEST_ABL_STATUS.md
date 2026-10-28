# AppWorld TEST_ABL: status ledger

Plan: [`docs/TEST_ABL.md`](TEST_ABL.md) (branch `test-abl`). Append-only; written only by
`examples/appworld/scripts/status_doc.py` under `flock(/workspace/aw_abl/state/testabl/ledger.lock)` and pushed with
`git push fork HEAD:test-abl`. Entry ids `TB-NNNN`. Counts and aggregates only: no task id, task text, trajectory or
per-task test outcome, and no test score of any arm before its window completes and the analysis has run.

<!-- CHECKPOINTS BELOW THIS LINE -->
