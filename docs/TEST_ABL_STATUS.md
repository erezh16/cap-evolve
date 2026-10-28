# AppWorld TEST_ABL: status ledger

Plan: [`docs/TEST_ABL.md`](TEST_ABL.md) (branch `test-abl`). Append-only; written only by
`examples/appworld/scripts/status_doc.py` under `flock(/workspace/aw_abl/state/testabl/ledger.lock)` and pushed with
`git push fork HEAD:test-abl`. Entry ids `TB-NNNN`. Counts and aggregates only: no task id, task text, trajectory or
per-task test outcome, and no test score of any arm before its window completes and the analysis has run.

<!-- CHECKPOINTS BELOW THIS LINE -->

## TB-0000 · 2026-10-28T14:08Z · P0 decisions, issues, host · decision

TEST_ABL B0. Test-only evaluation of the AppWorld ablation champions under docs/TEST_ALL.md's protocol (plan docs/TEST_ABL.md). Decisions D1 to D12 of plan §14 (user decisions 2026-10-28): window 1 = seed, abl_ref, abl_cc_best, abl_prompt, abl_tools, abl_notrace, abl_tracescore (5,880 cells); abl_cc excluded (seed-identical); abl_nogate and abl_naivegate deferred until ready, then window 2 (1,680 cells); no window while a gate optimizer is live, window 1 after the gate run's own P7; 24 slots; one issue per arm including the seed. Issues opened: seed #940, abl_ref #941, abl_cc_best #942, abl_prompt #943, abl_tools #944, abl_notrace #945, abl_tracescore #946. Host: memory limit 32768 MB, 8 CPUs, /workspace 9.9 GB free; deny rules: 40 ablation rules plus 12 testabl rules in the base session settings (none removed), T9 probe done (records denied, progress allowed). Build check (abl verify_build, read only): pass; root_full 000 before and after. Caches copied, sha256 equal. B3: 7 artifacts fetched from the local pushed copies, rule S hash match 7/7, lint 7/7 pass.

```json
{"cp": 0, "prev_cp": null, "prev_commit": "84aa75276a7368bd1fe5a8e0a994c2938b316ce1", "utc": "2026-10-28T14:08:21Z", "kind": "decision", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "84aa75276a7368bd1fe5a8e0a994c2938b316ce1", "open_decisions": [], "memory": {"used_pct": 27.41, "peak_pct": 28.43, "state": "OK", "stale": false}, "issues": {"seed": 940, "abl_ref": 941, "abl_cc_best": 942, "abl_prompt": 943, "abl_tools": 944, "abl_notrace": 945, "abl_tracescore": 946}}
```

## TB-0001 · 2026-10-28T14:08Z · P0 posted seed · posted

Posted 'seed agent hourly status' on #940 (seed): https://github.com/skillberry-ai/cap-evolve/issues/940#issuecomment-6471209770

```json
{"cp": 1, "prev_cp": 0, "prev_commit": "016bcda89b03e6c91a45557cd83771aad216e12e", "utc": "2026-10-28T14:08:34Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 28.49, "peak_pct": 28.49, "state": "OK", "stale": false}, "post": "seed/status_20261028T140000", "url": "https://github.com/skillberry-ai/cap-evolve/issues/940#issuecomment-6471209770"}
```

## TB-0002 · 2026-10-28T14:08Z · P0 posted abl_ref · posted

Posted 'Cap-evolve full (reference) hourly status' on #941 (abl_ref): https://github.com/skillberry-ai/cap-evolve/issues/941#issuecomment-6471218895

```json
{"cp": 2, "prev_cp": 1, "prev_commit": "5e8c2f5879fb9aefe0f2b3ee59652b13e001a7cc", "utc": "2026-10-28T14:08:56Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 28.39, "peak_pct": 28.49, "state": "OK", "stale": false}, "post": "abl_ref/status_20261028T140640", "url": "https://github.com/skillberry-ai/cap-evolve/issues/941#issuecomment-6471218895"}
```

## TB-0003 · 2026-10-28T14:13Z · P0 posted abl_cc_best · posted

Posted 'Claude code, best evaluated candidate hourly status' on #942 (abl_cc_best): https://github.com/skillberry-ai/cap-evolve/issues/942#issuecomment-6471327777

```json
{"cp": 3, "prev_cp": 2, "prev_commit": "0d90504197664a07fd1e6db06f2dac30b3f8d9e9", "utc": "2026-10-28T14:13:39Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 28.28, "peak_pct": 28.57, "state": "OK", "stale": false}, "post": "abl_cc_best/status_20261028T141320", "url": "https://github.com/skillberry-ai/cap-evolve/issues/942#issuecomment-6471327777"}
```

## TB-0004 · 2026-10-28T14:20Z · P0 posted abl_prompt · posted

Posted 'Cap evolve prompt only hourly status' on #943 (abl_prompt): https://github.com/skillberry-ai/cap-evolve/issues/943#issuecomment-6471479439

```json
{"cp": 4, "prev_cp": 3, "prev_commit": "96708506b7faf1503e59f81ee21808c5e243e21d", "utc": "2026-10-28T14:20:02Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 27.55, "peak_pct": 29.12, "state": "OK", "stale": false}, "post": "abl_prompt/status_20261028T142000", "url": "https://github.com/skillberry-ai/cap-evolve/issues/943#issuecomment-6471479439"}
```

## TB-0005 · 2026-10-28T14:26Z · P0 posted abl_tools · posted

Posted 'Cap evolve tools only hourly status' on #944 (abl_tools): https://github.com/skillberry-ai/cap-evolve/issues/944#issuecomment-6471650116

```json
{"cp": 5, "prev_cp": 4, "prev_commit": "2df19924f9fb9da9a127f920cdff46af9300a960", "utc": "2026-10-28T14:26:44Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 28.85, "peak_pct": 29.12, "state": "OK", "stale": false}, "post": "abl_tools/status_20261028T142640", "url": "https://github.com/skillberry-ai/cap-evolve/issues/944#issuecomment-6471650116"}
```

## TB-0006 · 2026-10-28T14:33Z · P0 posted abl_notrace · posted

Posted 'Cap evolve no traces hourly status' on #945 (abl_notrace): https://github.com/skillberry-ai/cap-evolve/issues/945#issuecomment-6471829204

```json
{"cp": 6, "prev_cp": 5, "prev_commit": "6bd26bb6b08f677a86aacbbcecb5e24eb3e8293c", "utc": "2026-10-28T14:33:27Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 28.92, "peak_pct": 29.12, "state": "OK", "stale": false}, "post": "abl_notrace/status_20261028T143320", "url": "https://github.com/skillberry-ai/cap-evolve/issues/945#issuecomment-6471829204"}
```

## TB-0007 · 2026-10-28T14:40Z · P0 posted abl_tracescore · posted

Posted 'Cap evolve traces and score only hourly status' on #946 (abl_tracescore): https://github.com/skillberry-ai/cap-evolve/issues/946#issuecomment-6471990744

```json
{"cp": 7, "prev_cp": 6, "prev_commit": "9c96449e9c50a3be475acfcd574ead6f757161a3", "utc": "2026-10-28T14:40:10Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 26.8, "peak_pct": 29.12, "state": "OK", "stale": false}, "post": "abl_tracescore/status_20261028T144000", "url": "https://github.com/skillberry-ai/cap-evolve/issues/946#issuecomment-6471990744"}
```
