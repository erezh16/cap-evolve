# Status ledger: AppWorld smoke test, ACE vs the seed agent

This is the checkpoint ledger of the evaluation planned in
[EVAL_SMOKE_TEST_ACE.md](EVAL_SMOKE_TEST_ACE.md) (section 10). It is cumulative: each checkpoint
appends one entry below the earlier ones, and no earlier entry is ever edited, reordered or deleted.
The last entry is the current state. After every checkpoint this file is committed and pushed to
branch `erezh-eval2-ace`.

- **Resume:** `python3 -I examples/appworld/scripts/resume.py` (`--dry-run` to only print the plan).
  It reads the `json` block of the last entry (plan section 10.4).
- **Detail records** behind each entry are in `AW_STATE=/workspace/aw_eval_ace/`, referenced by sha256.
  They are not in git.
- **Content rules:** this file is published by every push. It holds no secrets, no gold values, no task
  ids, no task or supervisor text, no trajectory text and no playbook text. Units are named by phase
  and index only.
- **Cadence:** a result is checkpointed at once (results that come faster than every 5 minutes are
  coalesced into one entry per 5 minutes), plus a heartbeat entry whenever 25 minutes pass without one.

Phases: P0 decisions · P1 build · P2 acceptance · P3 ACE start · P4 ACE adaptation · P5 freeze ·
P6 dev diagnostic · P7 isolation scan · P8 final window · P9 analysis · P10 report.

---

## CP-0000 · 2026-10-14T12:49Z · P0 decisions · phase_start

Plan written: `docs/EVAL_SMOKE_TEST_ACE.md`. Nothing has run. The host is fresh: no `AW_STATE`, no
scratch, no `.env`, no `examples/appworld/` code.
Open decisions: D5 (playbook size rule), D6 (adaptation set), D7 (batch size), plus plan section 16
items 11 (push playbook snapshots?) and 13 (fork visibility).
Next: P0, record the user's answers to D5–D7.

```json
{"cp": 0, "prev_cp": null, "prev_commit": null, "utc": "2026-10-14T12:49:59Z",
 "kind": "phase_start", "phase": "P0", "done_through": null, "next": "P0/decisions",
 "counts": {"rollouts_counted": 0}, "spend": {"opt_in_tok": 0, "opt_out_tok": 0, "usd_proxy": 0},
 "artifacts": {}, "code": null, "open_decisions": ["D5", "D6", "D7", "issue-11", "issue-13"]}
```
