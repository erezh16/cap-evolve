# AppWorld ablations of cap-evolve `main` (75b3bcd): status ledger

The execution ledger of [`docs/ABLATIONS.md`](ABLATIONS.md) (rule R3, section 4.3). Append-only, newest last. Entries
are written only by `examples/appworld/scripts/status_doc.py` (profile `abl`, `AW_LEDGER_ID=ABL`), under
`flock(/workspace/aw_abl/state/ledger.lock)`, and pushed to `fork/eval-abl` after every entry. Nothing below the
marker is ever edited. Content rules: plan section 13.2 (no task ids, task text, trajectories, secrets or per-task test
outcomes).

Tracking issues (skillberry-ai/cap-evolve): `abl_ref` #930, `abl_cc` #931, `abl_prompt` #932, `abl_tools` #933,
`abl_notrace` #934, `abl_tracescore` #935.

<!-- CHECKPOINTS BELOW THIS LINE -->
