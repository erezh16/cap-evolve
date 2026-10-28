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

## TB-0008 · 2026-10-28T15:00Z · P0 posted seed · posted

Posted 'seed agent hourly status' on #940 (seed): https://github.com/skillberry-ai/cap-evolve/issues/940#issuecomment-6472479289

```json
{"cp": 8, "prev_cp": 7, "prev_commit": "a9eb378032ff69c3cd45885ea8b475d743d643f7", "utc": "2026-10-28T15:00:14Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 27.95, "peak_pct": 29.12, "state": "OK", "stale": false}, "post": "seed/status_20261028T150000", "url": "https://github.com/skillberry-ai/cap-evolve/issues/940#issuecomment-6472479289"}
```

## TB-0009 · 2026-10-28T15:06Z · P0 posted abl_ref · posted

Posted 'Cap-evolve full (reference) hourly status' on #941 (abl_ref): https://github.com/skillberry-ai/cap-evolve/issues/941#issuecomment-6472642623

```json
{"cp": 9, "prev_cp": 8, "prev_commit": "d195d85e35fff23791cdfbdec32945182b44c023", "utc": "2026-10-28T15:06:57Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 27.72, "peak_pct": 29.12, "state": "OK", "stale": false}, "post": "abl_ref/status_20261028T150640", "url": "https://github.com/skillberry-ai/cap-evolve/issues/941#issuecomment-6472642623"}
```

## TB-0010 · 2026-10-28T15:13Z · P0 posted abl_cc_best · posted

Posted 'Claude code, best evaluated candidate hourly status' on #942 (abl_cc_best): https://github.com/skillberry-ai/cap-evolve/issues/942#issuecomment-6472809854

```json
{"cp": 10, "prev_cp": 9, "prev_commit": "3e2e644f144e949e0ee4abd22e3beb55bec71fb8", "utc": "2026-10-28T15:13:40Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 26.95, "peak_pct": 29.12, "state": "OK", "stale": false}, "post": "abl_cc_best/status_20261028T151320", "url": "https://github.com/skillberry-ai/cap-evolve/issues/942#issuecomment-6472809854"}
```

## TB-0011 · 2026-10-28T15:20Z · P0 posted abl_prompt · posted

Posted 'Cap evolve prompt only hourly status' on #943 (abl_prompt): https://github.com/skillberry-ai/cap-evolve/issues/943#issuecomment-6472966062

```json
{"cp": 11, "prev_cp": 10, "prev_commit": "fc636c621f0c0946bb837250d49259a98de81552", "utc": "2026-10-28T15:20:02Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 28.85, "peak_pct": 29.12, "state": "OK", "stale": false}, "post": "abl_prompt/status_20261028T152000", "url": "https://github.com/skillberry-ai/cap-evolve/issues/943#issuecomment-6472966062"}
```

## TB-0012 · 2026-10-28T15:26Z · P0 posted abl_tools · posted

Posted 'Cap evolve tools only hourly status' on #944 (abl_tools): https://github.com/skillberry-ai/cap-evolve/issues/944#issuecomment-6473126861

```json
{"cp": 12, "prev_cp": 11, "prev_commit": "ae6f7dffb26faa70c2f1cdcef2199574013a7f17", "utc": "2026-10-28T15:26:45Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 28.9, "peak_pct": 29.18, "state": "OK", "stale": false}, "post": "abl_tools/status_20261028T152640", "url": "https://github.com/skillberry-ai/cap-evolve/issues/944#issuecomment-6473126861"}
```

## TB-0013 · 2026-10-28T15:33Z · P0 posted abl_notrace · posted

Posted 'Cap evolve no traces hourly status' on #945 (abl_notrace): https://github.com/skillberry-ai/cap-evolve/issues/945#issuecomment-6473289335

```json
{"cp": 13, "prev_cp": 12, "prev_commit": "587e24753a68d99bc23fe78339887b1975351e6a", "utc": "2026-10-28T15:33:28Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 28.86, "peak_pct": 29.18, "state": "OK", "stale": false}, "post": "abl_notrace/status_20261028T153320", "url": "https://github.com/skillberry-ai/cap-evolve/issues/945#issuecomment-6473289335"}
```

## TB-0014 · 2026-10-28T15:40Z · P0 posted abl_tracescore · posted

Posted 'Cap evolve traces and score only hourly status' on #946 (abl_tracescore): https://github.com/skillberry-ai/cap-evolve/issues/946#issuecomment-6473450765

```json
{"cp": 14, "prev_cp": 13, "prev_commit": "38f8421af1a8d65c883e09daf9b7bfbdd1411181", "utc": "2026-10-28T15:40:11Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 28.72, "peak_pct": 29.18, "state": "OK", "stale": false}, "post": "abl_tracescore/status_20261028T154000", "url": "https://github.com/skillberry-ai/cap-evolve/issues/946#issuecomment-6473450765"}
```

## TB-0015 · 2026-10-28T16:00Z · P0 posted seed · posted

Posted 'seed agent hourly status' on #940 (seed): https://github.com/skillberry-ai/cap-evolve/issues/940#issuecomment-6473948132

```json
{"cp": 15, "prev_cp": 14, "prev_commit": "3053e8d97891c2e9af7312a262bf85978282810e", "utc": "2026-10-28T16:00:14Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 28.86, "peak_pct": 29.23, "state": "OK", "stale": false}, "post": "seed/status_20261028T160000", "url": "https://github.com/skillberry-ai/cap-evolve/issues/940#issuecomment-6473948132"}
```

## TB-0016 · 2026-10-28T16:06Z · P0 posted abl_ref · posted

Posted 'Cap-evolve full (reference) hourly status' on #941 (abl_ref): https://github.com/skillberry-ai/cap-evolve/issues/941#issuecomment-6474112288

```json
{"cp": 16, "prev_cp": 15, "prev_commit": "c67b2361766cb1389715e67f1cc4c565fe465384", "utc": "2026-10-28T16:06:57Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 28.79, "peak_pct": 29.23, "state": "OK", "stale": false}, "post": "abl_ref/status_20261028T160640", "url": "https://github.com/skillberry-ai/cap-evolve/issues/941#issuecomment-6474112288"}
```

## TB-0017 · 2026-10-28T16:13Z · P0 posted abl_cc_best · posted

Posted 'Claude code, best evaluated candidate hourly status' on #942 (abl_cc_best): https://github.com/skillberry-ai/cap-evolve/issues/942#issuecomment-6474276675

```json
{"cp": 17, "prev_cp": 16, "prev_commit": "09a979de7a5360d6d8d997d4884bb5f82a64c1f5", "utc": "2026-10-28T16:13:39Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 28.23, "peak_pct": 29.23, "state": "OK", "stale": false}, "post": "abl_cc_best/status_20261028T161320", "url": "https://github.com/skillberry-ai/cap-evolve/issues/942#issuecomment-6474276675"}
```

## TB-0018 · 2026-10-28T16:20Z · P0 posted abl_prompt · posted

Posted 'Cap evolve prompt only hourly status' on #943 (abl_prompt): https://github.com/skillberry-ai/cap-evolve/issues/943#issuecomment-6474427641

```json
{"cp": 18, "prev_cp": 17, "prev_commit": "f5871d03ef83629c43138586481e1430d6dbb225", "utc": "2026-10-28T16:20:01Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 28.25, "peak_pct": 29.23, "state": "OK", "stale": false}, "post": "abl_prompt/status_20261028T162000", "url": "https://github.com/skillberry-ai/cap-evolve/issues/943#issuecomment-6474427641"}
```

## TB-0019 · 2026-10-28T16:26Z · P0 posted abl_tools · posted

Posted 'Cap evolve tools only hourly status' on #944 (abl_tools): https://github.com/skillberry-ai/cap-evolve/issues/944#issuecomment-6474582109

```json
{"cp": 19, "prev_cp": 18, "prev_commit": "1f2bdce30c059addab068a39b4d371a0327a23e0", "utc": "2026-10-28T16:26:44Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 28.15, "peak_pct": 29.23, "state": "OK", "stale": false}, "post": "abl_tools/status_20261028T162640", "url": "https://github.com/skillberry-ai/cap-evolve/issues/944#issuecomment-6474582109"}
```

## TB-0020 · 2026-10-28T16:33Z · P0 posted abl_notrace · posted

Posted 'Cap evolve no traces hourly status' on #945 (abl_notrace): https://github.com/skillberry-ai/cap-evolve/issues/945#issuecomment-6474734511

```json
{"cp": 20, "prev_cp": 19, "prev_commit": "44e5bd1c89e91b15de605e91a95820373fa99a56", "utc": "2026-10-28T16:33:27Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 28.22, "peak_pct": 29.23, "state": "OK", "stale": false}, "post": "abl_notrace/status_20261028T163320", "url": "https://github.com/skillberry-ai/cap-evolve/issues/945#issuecomment-6474734511"}
```

## TB-0021 · 2026-10-28T16:40Z · P0 posted abl_tracescore · posted

Posted 'Cap evolve traces and score only hourly status' on #946 (abl_tracescore): https://github.com/skillberry-ai/cap-evolve/issues/946#issuecomment-6474887845

```json
{"cp": 21, "prev_cp": 20, "prev_commit": "61ffbd44ba8943194e01e43b30dd8fc27a35f746", "utc": "2026-10-28T16:40:10Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 28.19, "peak_pct": 29.23, "state": "OK", "stale": false}, "post": "abl_tracescore/status_20261028T164000", "url": "https://github.com/skillberry-ai/cap-evolve/issues/946#issuecomment-6474887845"}
```

## TB-0022 · 2026-10-28T17:00Z · P0 posted seed · posted

Posted 'seed agent hourly status' on #940 (seed): https://github.com/skillberry-ai/cap-evolve/issues/940#issuecomment-6475337554

```json
{"cp": 22, "prev_cp": 21, "prev_commit": "cb6737e63d49acc75e3c8705f6ab84b504f55710", "utc": "2026-10-28T17:00:12Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 28.14, "peak_pct": 29.23, "state": "OK", "stale": false}, "post": "seed/status_20261028T170000", "url": "https://github.com/skillberry-ai/cap-evolve/issues/940#issuecomment-6475337554"}
```

## TB-0023 · 2026-10-28T17:06Z · P0 posted abl_ref · posted

Posted 'Cap-evolve full (reference) hourly status' on #941 (abl_ref): https://github.com/skillberry-ai/cap-evolve/issues/941#issuecomment-6475486675

```json
{"cp": 23, "prev_cp": 22, "prev_commit": "36673828dd2dba093bcd280f06716f8eb3c90c73", "utc": "2026-10-28T17:06:55Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 27.23, "peak_pct": 29.23, "state": "OK", "stale": false}, "post": "abl_ref/status_20261028T170640", "url": "https://github.com/skillberry-ai/cap-evolve/issues/941#issuecomment-6475486675"}
```

## TB-0024 · 2026-10-28T17:13Z · P0 posted abl_cc_best · posted

Posted 'Claude code, best evaluated candidate hourly status' on #942 (abl_cc_best): https://github.com/skillberry-ai/cap-evolve/issues/942#issuecomment-6475637990

```json
{"cp": 24, "prev_cp": 23, "prev_commit": "2a06ccf26e898e61c55f654e543df77836165b5b", "utc": "2026-10-28T17:13:38Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 28.21, "peak_pct": 29.23, "state": "OK", "stale": false}, "post": "abl_cc_best/status_20261028T171320", "url": "https://github.com/skillberry-ai/cap-evolve/issues/942#issuecomment-6475637990"}
```

## TB-0025 · 2026-10-28T17:20Z · P0 posted abl_prompt · posted

Posted 'Cap evolve prompt only hourly status' on #943 (abl_prompt): https://github.com/skillberry-ai/cap-evolve/issues/943#issuecomment-6475783648

```json
{"cp": 25, "prev_cp": 24, "prev_commit": "65ead71b7ac89d7a557ea29c97fed3f6ba0a69f7", "utc": "2026-10-28T17:20:20Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 28.82, "peak_pct": 29.23, "state": "OK", "stale": false}, "post": "abl_prompt/status_20261028T172000", "url": "https://github.com/skillberry-ai/cap-evolve/issues/943#issuecomment-6475783648"}
```

## TB-0026 · 2026-10-28T17:26Z · P0 posted abl_tools · posted

Posted 'Cap evolve tools only hourly status' on #944 (abl_tools): https://github.com/skillberry-ai/cap-evolve/issues/944#issuecomment-6475926183

```json
{"cp": 26, "prev_cp": 25, "prev_commit": "7a8c69b4b525c7e9a6e4d35f6b236a1c8d29b740", "utc": "2026-10-28T17:26:43Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 26.04, "peak_pct": 29.23, "state": "OK", "stale": false}, "post": "abl_tools/status_20261028T172640", "url": "https://github.com/skillberry-ai/cap-evolve/issues/944#issuecomment-6475926183"}
```

## TB-0027 · 2026-10-28T17:33Z · P0 posted abl_notrace · posted

Posted 'Cap evolve no traces hourly status' on #945 (abl_notrace): https://github.com/skillberry-ai/cap-evolve/issues/945#issuecomment-6476072728

```json
{"cp": 27, "prev_cp": 26, "prev_commit": "c736f5a706c001630568ffc4582405343e6561e5", "utc": "2026-10-28T17:33:25Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 16.94, "peak_pct": 29.23, "state": "OK", "stale": false}, "post": "abl_notrace/status_20261028T173320", "url": "https://github.com/skillberry-ai/cap-evolve/issues/945#issuecomment-6476072728"}
```

## TB-0028 · 2026-10-28T17:40Z · P0 posted abl_tracescore · posted

Posted 'Cap evolve traces and score only hourly status' on #946 (abl_tracescore): https://github.com/skillberry-ai/cap-evolve/issues/946#issuecomment-6476220051

```json
{"cp": 28, "prev_cp": 27, "prev_commit": "098afff5f732e1fcbec78ce1b52df979ace0a9af", "utc": "2026-10-28T17:40:08Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 27.39, "peak_pct": 29.23, "state": "OK", "stale": false}, "post": "abl_tracescore/status_20261028T174000", "url": "https://github.com/skillberry-ai/cap-evolve/issues/946#issuecomment-6476220051"}
```

## TB-0029 · 2026-10-28T18:00Z · P0 posted seed · posted

Posted 'seed agent hourly status' on #940 (seed): https://github.com/skillberry-ai/cap-evolve/issues/940#issuecomment-6476652583

```json
{"cp": 29, "prev_cp": 28, "prev_commit": "b91d6ac5036c73d38e35217c885aa28a5e3d6e75", "utc": "2026-10-28T18:00:10Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 28.81, "peak_pct": 29.23, "state": "OK", "stale": false}, "post": "seed/status_20261028T180000", "url": "https://github.com/skillberry-ai/cap-evolve/issues/940#issuecomment-6476652583"}
```

## TB-0030 · 2026-10-28T18:06Z · P0 posted abl_ref · posted

Posted 'Cap-evolve full (reference) hourly status' on #941 (abl_ref): https://github.com/skillberry-ai/cap-evolve/issues/941#issuecomment-6476795563

```json
{"cp": 30, "prev_cp": 29, "prev_commit": "dc83a058fbd14a80a385a4976f995e8a347e119c", "utc": "2026-10-28T18:06:53Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 28.08, "peak_pct": 29.23, "state": "OK", "stale": false}, "post": "abl_ref/status_20261028T180640", "url": "https://github.com/skillberry-ai/cap-evolve/issues/941#issuecomment-6476795563"}
```

## TB-0031 · 2026-10-28T18:13Z · P0 posted abl_cc_best · posted

Posted 'Claude code, best evaluated candidate hourly status' on #942 (abl_cc_best): https://github.com/skillberry-ai/cap-evolve/issues/942#issuecomment-6476934137

```json
{"cp": 31, "prev_cp": 30, "prev_commit": "616f213fa7e59cc9f271b98785ca1c02eb87df02", "utc": "2026-10-28T18:13:36Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 28.2, "peak_pct": 29.23, "state": "OK", "stale": false}, "post": "abl_cc_best/status_20261028T181320", "url": "https://github.com/skillberry-ai/cap-evolve/issues/942#issuecomment-6476934137"}
```

## TB-0032 · 2026-10-28T18:20Z · P0 posted abl_prompt · posted

Posted 'Cap evolve prompt only hourly status' on #943 (abl_prompt): https://github.com/skillberry-ai/cap-evolve/issues/943#issuecomment-6477076875

```json
{"cp": 32, "prev_cp": 31, "prev_commit": "4c4ddc7d671c5067c596638c8e0e43f5560673ba", "utc": "2026-10-28T18:20:20Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 27.4, "peak_pct": 29.23, "state": "OK", "stale": false}, "post": "abl_prompt/status_20261028T182000", "url": "https://github.com/skillberry-ai/cap-evolve/issues/943#issuecomment-6477076875"}
```

## TB-0033 · 2026-10-28T18:26Z · P0 posted abl_tools · posted

Posted 'Cap evolve tools only hourly status' on #944 (abl_tools): https://github.com/skillberry-ai/cap-evolve/issues/944#issuecomment-6477209808

```json
{"cp": 33, "prev_cp": 32, "prev_commit": "4df3a4569d77f3d70985034ead1c81151a7029ee", "utc": "2026-10-28T18:26:42Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 28.75, "peak_pct": 29.23, "state": "OK", "stale": false}, "post": "abl_tools/status_20261028T182640", "url": "https://github.com/skillberry-ai/cap-evolve/issues/944#issuecomment-6477209808"}
```

## TB-0034 · 2026-10-28T18:33Z · P0 posted abl_notrace · posted

Posted 'Cap evolve no traces hourly status' on #945 (abl_notrace): https://github.com/skillberry-ai/cap-evolve/issues/945#issuecomment-6477352973

```json
{"cp": 34, "prev_cp": 33, "prev_commit": "0ba18746652c2508a1353de9ecd12ec7b64b8e27", "utc": "2026-10-28T18:33:25Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 28.28, "peak_pct": 29.23, "state": "OK", "stale": false}, "post": "abl_notrace/status_20261028T183320", "url": "https://github.com/skillberry-ai/cap-evolve/issues/945#issuecomment-6477352973"}
```

## TB-0035 · 2026-10-28T18:40Z · P0 posted abl_tracescore · posted

Posted 'Cap evolve traces and score only hourly status' on #946 (abl_tracescore): https://github.com/skillberry-ai/cap-evolve/issues/946#issuecomment-6477493019

```json
{"cp": 35, "prev_cp": 34, "prev_commit": "6df82b34cc62816c8ef01c00d905148cf10d461e", "utc": "2026-10-28T18:40:08Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 28.2, "peak_pct": 29.23, "state": "OK", "stale": false}, "post": "abl_tracescore/status_20261028T184000", "url": "https://github.com/skillberry-ai/cap-evolve/issues/946#issuecomment-6477493019"}
```

## TB-0036 · 2026-10-28T19:00Z · P0 posted seed · posted

Posted 'seed agent hourly status' on #940 (seed): https://github.com/skillberry-ai/cap-evolve/issues/940#issuecomment-6477945022

```json
{"cp": 36, "prev_cp": 35, "prev_commit": "dd2763cd39b1db2e3974397a4ffaf38f7d0a0d31", "utc": "2026-10-28T19:00:11Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "016bcda89b03e6c91a45557cd83771aad216e12e", "open_decisions": [], "memory": {"used_pct": 26.93, "peak_pct": 29.49, "state": "OK", "stale": false}, "post": "seed/status_20261028T190000", "url": "https://github.com/skillberry-ai/cap-evolve/issues/940#issuecomment-6477945022"}
```

## TB-0037 · 2026-10-28T19:06Z · P0 posted abl_ref · posted

Posted 'Cap-evolve full (reference) hourly status' on #941 (abl_ref): https://github.com/skillberry-ai/cap-evolve/issues/941#issuecomment-6478091731

```json
{"cp": 37, "prev_cp": 36, "prev_commit": "bd2a69eda0f23606ea5bca9472c5166035ae2b4d", "utc": "2026-10-28T19:06:45Z", "kind": "posted", "phase": "P0", "done_through": "B0..B3", "next": "B4 window code; P2 acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "bd2a69eda0f23606ea5bca9472c5166035ae2b4d", "open_decisions": [], "memory": {"used_pct": 27.41, "peak_pct": 45.67, "state": "OK", "stale": false}, "post": "abl_ref/status_20261028T190640", "url": "https://github.com/skillberry-ai/cap-evolve/issues/941#issuecomment-6478091731"}
```

## TB-0038 · 2026-10-28T19:07Z · W waiting for the gate run (window 1) · result

Window 1 waits for the gate run (plan §8.1): gate searches running (abl_naivegate).

```json
{"cp": 38, "prev_cp": 37, "prev_commit": "cb0b20e8143d4f476d3eba9c35c55a422b41c132", "utc": "2026-10-28T19:07:15Z", "kind": "result", "phase": "W", "done_through": "B0..B3", "next": "P3/window1", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "cb0b20e8143d4f476d3eba9c35c55a422b41c132", "open_decisions": [], "memory": {"used_pct": 30.02, "peak_pct": 45.67, "state": "OK", "stale": false}}
```

## TB-0039 · 2026-10-28T19:08Z · W waiting for the gate run (window 1) · result

Window 1 waits for the gate run (plan §8.1): gate searches running (abl_naivegate).

```json
{"cp": 39, "prev_cp": 38, "prev_commit": "122166a1532ca2bbe34db2c930581c0301f6568e", "utc": "2026-10-28T19:08:49Z", "kind": "result", "phase": "W", "done_through": "B0..B3", "next": "P3/window1", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "cb0b20e8143d4f476d3eba9c35c55a422b41c132", "open_decisions": [], "memory": {"used_pct": 30.03, "peak_pct": 45.67, "state": "OK", "stale": false}}
```

## TB-0040 · 2026-10-28T19:09Z · W waiting for the gate run (window 1) · result

Window 1 waits for the gate run (plan §8.1): gate searches running (abl_naivegate).

```json
{"cp": 40, "prev_cp": 39, "prev_commit": "e002885e822d4994cb90b8cd75eb0996b5739243", "utc": "2026-10-28T19:09:21Z", "kind": "result", "phase": "W", "done_through": "B0..B3", "next": "P3/window1", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "e002885e822d4994cb90b8cd75eb0996b5739243", "open_decisions": [], "memory": {"used_pct": 28.58, "peak_pct": 45.67, "state": "OK", "stale": false}}
```

## TB-0041 · 2026-10-28T19:13Z · W posted abl_cc_best · posted

Posted 'Claude code, best evaluated candidate hourly status' on #942 (abl_cc_best): https://github.com/skillberry-ai/cap-evolve/issues/942#issuecomment-6478232370

```json
{"cp": 41, "prev_cp": 40, "prev_commit": "76976c2be44fa6d25b7cb28e20664dcb47fb25d6", "utc": "2026-10-28T19:13:29Z", "kind": "posted", "phase": "W", "done_through": "B0..B3", "next": "P3/window1", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "e002885e822d4994cb90b8cd75eb0996b5739243", "open_decisions": [], "memory": {"used_pct": 20.01, "peak_pct": 45.67, "state": "OK", "stale": false}, "post": "abl_cc_best/status_20261028T191320", "url": "https://github.com/skillberry-ai/cap-evolve/issues/942#issuecomment-6478232370"}
```

## TB-0042 · 2026-10-28T19:15Z · P2 acceptance T1 T2 T4-T10 · result

Acceptance on dev ids only (none counted), run while the gate searches were live, with no conflict (addendum A2). T1 PASS: max_model_len 40144, 1 dev seed episode completed through _episode (17 steps), RITS key hits 0. T2: root_full mode 000 (checked by the build check and by the launcher, which is a script; the REPL-hardening probe is part of the shared harness taken unchanged from eval-abl, where it passed as A3). T4 PASS for all 7 arms (no model call): seed byte-identical to stock (23 messages); every P-changing arm's first request differs from stock; helpers defined with the notice in the prompt where present; a note appended on a doc lookup for every arm with notes; no memory block in any arm. T5 PASS: the 3 largest first requests (abl_tracescore, abl_ref, abl_prompt) each completed 1 dev episode, max prompt tokens 13865 / 11600 / 11977, 0 context_exceeded. T6 PASS: guard period 5 s, synthetic allocation set PAUSE within 4.5 s, slot and optimizer call blocked while paused, resumed below the low mark. T7+T8 PASS (A10, throwaway clone and local bare remote): 12 concurrent appends landed with unique increasing numbers, content filter refused a task id and an .env value, push failure kept local and recovered; mini window SIGKILLed after 2 cells resumed with 0 cells re-run. T9 PASS: Read of testabl/final/records and of root_full refused; Read of testabl/progress and testabl/final/artifacts/seed allowed. T10 PASS: 7 distinct slots 400 s apart, unchanged across an autopost restart. T3 (window order) is serialized right before the window-1 launch, because it unlocks root_full (addendum A2). Analysis and reports passed a synthetic end-to-end test (fake ids, 5880 fake records).

```json
{"cp": 42, "prev_cp": 41, "prev_commit": "a407702300d0bfa6f06c7bd42f3232d63e3ae2b6", "utc": "2026-10-28T19:15:54Z", "kind": "result", "phase": "P2", "done_through": "P2/T1,T2,T4-T10", "next": "P2/T3 then P3/window1 (launch_when_clear.py waiting for the gate run)", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "a407702300d0bfa6f06c7bd42f3232d63e3ae2b6", "open_decisions": [], "memory": {"used_pct": 6.03, "peak_pct": 45.67, "state": "OK", "stale": false}}
```

## TB-0043 · 2026-10-28T19:16Z · P2 posted seed · posted

Posted 'seed agent: build and acceptance done' on #940 (seed): https://github.com/skillberry-ai/cap-evolve/issues/940#issuecomment-6478297151

```json
{"cp": 43, "prev_cp": 42, "prev_commit": "382cd041047f36ec79694a42755ef9e93e6bcae8", "utc": "2026-10-28T19:16:32Z", "kind": "posted", "phase": "P2", "done_through": "P2/T1,T2,T4-T10", "next": "P2/T3 then P3/window1 (launch_when_clear.py waiting for the gate run)", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "a407702300d0bfa6f06c7bd42f3232d63e3ae2b6", "open_decisions": [], "memory": {"used_pct": 3.77, "peak_pct": 45.67, "state": "OK", "stale": false}, "post": "seed/accept_done", "url": "https://github.com/skillberry-ai/cap-evolve/issues/940#issuecomment-6478297151"}
```

## TB-0044 · 2026-10-28T19:16Z · P2 posted abl_ref · posted

Posted 'Cap-evolve full (reference): build and acceptance done' on #941 (abl_ref): https://github.com/skillberry-ai/cap-evolve/issues/941#issuecomment-6478298934

```json
{"cp": 44, "prev_cp": 43, "prev_commit": "e1878d422b5cdd16e15d6535fa75003dee1b62a8", "utc": "2026-10-28T19:16:37Z", "kind": "posted", "phase": "P2", "done_through": "P2/T1,T2,T4-T10", "next": "P2/T3 then P3/window1 (launch_when_clear.py waiting for the gate run)", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "a407702300d0bfa6f06c7bd42f3232d63e3ae2b6", "open_decisions": [], "memory": {"used_pct": 3.82, "peak_pct": 45.67, "state": "OK", "stale": false}, "post": "abl_ref/accept_done", "url": "https://github.com/skillberry-ai/cap-evolve/issues/941#issuecomment-6478298934"}
```

## TB-0045 · 2026-10-28T19:16Z · P2 posted abl_cc_best · posted

Posted 'Claude code, best evaluated candidate: build and acceptance done' on #942 (abl_cc_best): https://github.com/skillberry-ai/cap-evolve/issues/942#issuecomment-6478300641

```json
{"cp": 45, "prev_cp": 44, "prev_commit": "d565b2bdbe0baa6566a252643e4de2de4af05298", "utc": "2026-10-28T19:16:42Z", "kind": "posted", "phase": "P2", "done_through": "P2/T1,T2,T4-T10", "next": "P2/T3 then P3/window1 (launch_when_clear.py waiting for the gate run)", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "a407702300d0bfa6f06c7bd42f3232d63e3ae2b6", "open_decisions": [], "memory": {"used_pct": 3.85, "peak_pct": 45.67, "state": "OK", "stale": false}, "post": "abl_cc_best/accept_done", "url": "https://github.com/skillberry-ai/cap-evolve/issues/942#issuecomment-6478300641"}
```

## TB-0046 · 2026-10-28T19:16Z · P2 posted abl_prompt · posted

Posted 'Cap evolve prompt only: build and acceptance done' on #943 (abl_prompt): https://github.com/skillberry-ai/cap-evolve/issues/943#issuecomment-6478302591

```json
{"cp": 46, "prev_cp": 45, "prev_commit": "47d664738381f19bd490ed0d189d8d26f6b09e32", "utc": "2026-10-28T19:16:48Z", "kind": "posted", "phase": "P2", "done_through": "P2/T1,T2,T4-T10", "next": "P2/T3 then P3/window1 (launch_when_clear.py waiting for the gate run)", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "a407702300d0bfa6f06c7bd42f3232d63e3ae2b6", "open_decisions": [], "memory": {"used_pct": 3.8, "peak_pct": 45.67, "state": "OK", "stale": false}, "post": "abl_prompt/accept_done", "url": "https://github.com/skillberry-ai/cap-evolve/issues/943#issuecomment-6478302591"}
```

## TB-0047 · 2026-10-28T19:16Z · P2 posted abl_tools · posted

Posted 'Cap evolve tools only: build and acceptance done' on #944 (abl_tools): https://github.com/skillberry-ai/cap-evolve/issues/944#issuecomment-6478304673

```json
{"cp": 47, "prev_cp": 46, "prev_commit": "0f867e3ec790b236dbe929d651c2b80ef7407390", "utc": "2026-10-28T19:16:53Z", "kind": "posted", "phase": "P2", "done_through": "P2/T1,T2,T4-T10", "next": "P2/T3 then P3/window1 (launch_when_clear.py waiting for the gate run)", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "a407702300d0bfa6f06c7bd42f3232d63e3ae2b6", "open_decisions": [], "memory": {"used_pct": 3.8, "peak_pct": 45.67, "state": "OK", "stale": false}, "post": "abl_tools/accept_done", "url": "https://github.com/skillberry-ai/cap-evolve/issues/944#issuecomment-6478304673"}
```

## TB-0048 · 2026-10-28T19:16Z · P2 posted abl_notrace · posted

Posted 'Cap evolve no traces: build and acceptance done' on #945 (abl_notrace): https://github.com/skillberry-ai/cap-evolve/issues/945#issuecomment-6478306720

```json
{"cp": 48, "prev_cp": 47, "prev_commit": "354a95d41b535828d4609a77d1e53ea350a32e89", "utc": "2026-10-28T19:16:59Z", "kind": "posted", "phase": "P2", "done_through": "P2/T1,T2,T4-T10", "next": "P2/T3 then P3/window1 (launch_when_clear.py waiting for the gate run)", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "a407702300d0bfa6f06c7bd42f3232d63e3ae2b6", "open_decisions": [], "memory": {"used_pct": 3.7, "peak_pct": 45.67, "state": "OK", "stale": false}, "post": "abl_notrace/accept_done", "url": "https://github.com/skillberry-ai/cap-evolve/issues/945#issuecomment-6478306720"}
```

## TB-0049 · 2026-10-28T19:17Z · P2 posted abl_tracescore · posted

Posted 'Cap evolve traces and score only: build and acceptance done' on #946 (abl_tracescore): https://github.com/skillberry-ai/cap-evolve/issues/946#issuecomment-6478308950

```json
{"cp": 49, "prev_cp": 48, "prev_commit": "02d95ccbf8be777750a1c3a040986b965d8612a2", "utc": "2026-10-28T19:17:05Z", "kind": "posted", "phase": "P2", "done_through": "P2/T1,T2,T4-T10", "next": "P2/T3 then P3/window1 (launch_when_clear.py waiting for the gate run)", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "a407702300d0bfa6f06c7bd42f3232d63e3ae2b6", "open_decisions": [], "memory": {"used_pct": 3.63, "peak_pct": 45.67, "state": "OK", "stale": false}, "post": "abl_tracescore/accept_done", "url": "https://github.com/skillberry-ai/cap-evolve/issues/946#issuecomment-6478308950"}
```

## TB-0050 · 2026-10-28T19:20Z · P2 posted abl_prompt · posted

Posted 'Cap evolve prompt only hourly status' on #943 (abl_prompt): https://github.com/skillberry-ai/cap-evolve/issues/943#issuecomment-6478380735

```json
{"cp": 50, "prev_cp": 49, "prev_commit": "383d1584ee1492369a9c1d77e6bc0c4dc08509d1", "utc": "2026-10-28T19:20:12Z", "kind": "posted", "phase": "P2", "done_through": "P2/T1,T2,T4-T10", "next": "P2/T3 then P3/window1 (launch_when_clear.py waiting for the gate run)", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "383d1584ee1492369a9c1d77e6bc0c4dc08509d1", "open_decisions": [], "memory": {"used_pct": 3.71, "peak_pct": 45.67, "state": "OK", "stale": false}, "post": "abl_prompt/status_20261028T192000", "url": "https://github.com/skillberry-ai/cap-evolve/issues/943#issuecomment-6478380735"}
```

## TB-0051 · 2026-10-28T19:20Z · W gate arms ready · decision

Both gate arms are ready (plan §3.2): searches ended, champions frozen and pushed, local copies reproduce their freeze hash under rule S, reset checks ok, isolation scans 0 test-id hits. They join window 2. Surfaces changed vs the seed: {'abl_nogate': 'P + T', 'abl_naivegate': 'P + T'}. Opening their issues next.
Push note: 1 earlier checkpoint commit(s) were not pushed (error: failed to push some refs to 'github.com:erezh16/cap-evolve.git'); this checkpoint pushes them.

```json
{"cp": 51, "prev_cp": 50, "prev_commit": "6a8fb3006b0396c06b7dc5b466736bafcf12057c", "utc": "2026-10-28T19:20:14Z", "kind": "decision", "phase": "W", "done_through": "P2/T1,T2,T4-T10", "next": "P2/T3 then P3/window1 (launch_when_clear.py waiting for the gate run)", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "383d1584ee1492369a9c1d77e6bc0c4dc08509d1", "open_decisions": [], "memory": {"used_pct": 3.71, "peak_pct": 45.67, "state": "OK", "stale": false}, "gate": {"abl_nogate": {"search_alive": false, "freeze_hash": "cdbc5827f70b02e1b388c4e8a29dc0b5125fd905399c2b3a396d904efd19b1e9", "local_hash_ok": true, "reset_ok": true, "scan_hits": 0, "inert": false, "label": ""}, "abl_naivegate": {"search_alive": false, "freeze_hash": "fa2bfe23ace7fc0546953d9b047445dab6fa111655d657d31fbf897d8c31bb51", "local_hash_ok": true, "reset_ok": true, "scan_hits": 0, "inert": false, "label": ""}}}
```

## TB-0052 · 2026-10-28T19:20Z · W gate issues opened · result

Gate-arm tracking issues: abl_nogate #948, abl_naivegate #949. Their hourly timers start now (autopost reads the open issues).

```json
{"cp": 52, "prev_cp": 51, "prev_commit": "068cb75137bce07b3db629f71d1519c0885267f9", "utc": "2026-10-28T19:20:25Z", "kind": "result", "phase": "W", "done_through": "P2/T1,T2,T4-T10", "next": "P2/T3 then P3/window1 (launch_when_clear.py waiting for the gate run)", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "383d1584ee1492369a9c1d77e6bc0c4dc08509d1", "open_decisions": [], "memory": {"used_pct": 3.84, "peak_pct": 45.67, "state": "OK", "stale": false}, "issues_gate": {"abl_nogate": 948, "abl_naivegate": 949}}
```

## TB-0053 · 2026-10-28T19:24Z · W gate arms fetch, lint, T4, T5 · result

Window 2 arms (abl_nogate, abl_naivegate): fetch + rule-S hash check, lint, T4 injection and T5 context (1 dev episode each): PASS. Window 2 runs after window 1.

```json
{"cp": 53, "prev_cp": 52, "prev_commit": "f1be6fbb4b16d6394a817dc9d5033959dd7c663f", "utc": "2026-10-28T19:24:00Z", "kind": "result", "phase": "W", "done_through": "P2/T1,T2,T4-T10", "next": "P2/T3 then P3/window1 (launch_when_clear.py waiting for the gate run)", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "383d1584ee1492369a9c1d77e6bc0c4dc08509d1", "open_decisions": [], "memory": {"used_pct": 3.76, "peak_pct": 45.67, "state": "OK", "stale": false}, "gate_accept": {"fetch": 0, "lint": 0, "t4": 0, "t5": 0}}
```

## TB-0054 · 2026-10-28T19:25Z · W posted abl_nogate · posted

Posted 'Cap evolve no gate: build and acceptance done' on #948 (abl_nogate): https://github.com/skillberry-ai/cap-evolve/issues/948#issuecomment-6478486544

```json
{"cp": 54, "prev_cp": 53, "prev_commit": "a5b60a821ea6fea55c70b832624c117823f4918f", "utc": "2026-10-28T19:25:05Z", "kind": "posted", "phase": "W", "done_through": "P2/T1,T2,T4-T10", "next": "P2/T3 then P3/window1 (launch_when_clear.py waiting for the gate run)", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "383d1584ee1492369a9c1d77e6bc0c4dc08509d1", "open_decisions": [], "memory": {"used_pct": 3.85, "peak_pct": 45.67, "state": "OK", "stale": false}, "post": "abl_nogate/accept_done", "url": "https://github.com/skillberry-ai/cap-evolve/issues/948#issuecomment-6478486544"}
```

## TB-0055 · 2026-10-28T19:25Z · W posted abl_naivegate · posted

Posted 'Cap evolve naive gate: build and acceptance done' on #949 (abl_naivegate): https://github.com/skillberry-ai/cap-evolve/issues/949#issuecomment-6478488349

```json
{"cp": 55, "prev_cp": 54, "prev_commit": "48fc289a55c633822172ebf707089eef7349ff54", "utc": "2026-10-28T19:25:11Z", "kind": "posted", "phase": "W", "done_through": "P2/T1,T2,T4-T10", "next": "P2/T3 then P3/window1 (launch_when_clear.py waiting for the gate run)", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "383d1584ee1492369a9c1d77e6bc0c4dc08509d1", "open_decisions": [], "memory": {"used_pct": 3.81, "peak_pct": 45.67, "state": "OK", "stale": false}, "post": "abl_naivegate/accept_done", "url": "https://github.com/skillberry-ai/cap-evolve/issues/949#issuecomment-6478488349"}
```

## TB-0056 · 2026-10-28T19:26Z · W posted abl_tools · posted

Posted 'Cap evolve tools only hourly status' on #944 (abl_tools): https://github.com/skillberry-ai/cap-evolve/issues/944#issuecomment-6478521500

```json
{"cp": 56, "prev_cp": 55, "prev_commit": "4daed2d1cc86bf23ee9d17f2d40812b9be067980", "utc": "2026-10-28T19:26:43Z", "kind": "posted", "phase": "W", "done_through": "P2/T1,T2,T4-T10", "next": "P2/T3 then P3/window1 (launch_when_clear.py waiting for the gate run)", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "383d1584ee1492369a9c1d77e6bc0c4dc08509d1", "open_decisions": [], "memory": {"used_pct": 23.11, "peak_pct": 45.67, "state": "OK", "stale": false}, "post": "abl_tools/status_20261028T192640", "url": "https://github.com/skillberry-ai/cap-evolve/issues/944#issuecomment-6478521500"}
```

## TB-0057 · 2026-10-28T19:33Z · W posted abl_notrace · posted

Posted 'Cap evolve no traces hourly status' on #945 (abl_notrace): https://github.com/skillberry-ai/cap-evolve/issues/945#issuecomment-6478665502

```json
{"cp": 57, "prev_cp": 56, "prev_commit": "9c4de7607d18f4c2bd465dcf9c5e81e122e9aab4", "utc": "2026-10-28T19:33:25Z", "kind": "posted", "phase": "W", "done_through": "P2/T1,T2,T4-T10", "next": "P2/T3 then P3/window1 (launch_when_clear.py waiting for the gate run)", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "383d1584ee1492369a9c1d77e6bc0c4dc08509d1", "open_decisions": [], "memory": {"used_pct": 24.32, "peak_pct": 45.67, "state": "OK", "stale": false}, "post": "abl_notrace/status_20261028T193320", "url": "https://github.com/skillberry-ai/cap-evolve/issues/945#issuecomment-6478665502"}
```

## TB-0058 · 2026-10-28T19:39Z · W waiting for the gate run (window 1) · result

Window 1 waits for the gate run (plan §8.1): a gate-run window or P5-P9 chain is alive.

```json
{"cp": 58, "prev_cp": 57, "prev_commit": "10597a81d6b02b7bbeb77e0cebca1f239cdc850a", "utc": "2026-10-28T19:39:44Z", "kind": "result", "phase": "W", "done_through": "P2/T1,T2,T4-T10", "next": "P3/window1", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "383d1584ee1492369a9c1d77e6bc0c4dc08509d1", "open_decisions": [], "memory": {"used_pct": 24.12, "peak_pct": 45.67, "state": "OK", "stale": false}}
```

## TB-0059 · 2026-10-28T19:40Z · W posted abl_tracescore · posted

Posted 'Cap evolve traces and score only hourly status' on #946 (abl_tracescore): https://github.com/skillberry-ai/cap-evolve/issues/946#issuecomment-6478806316

```json
{"cp": 59, "prev_cp": 58, "prev_commit": "a8abe6dbbc88ae99dc9c2e1d7224abd1b7cb93f4", "utc": "2026-10-28T19:40:09Z", "kind": "posted", "phase": "W", "done_through": "P2/T1,T2,T4-T10", "next": "P3/window1", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "383d1584ee1492369a9c1d77e6bc0c4dc08509d1", "open_decisions": [], "memory": {"used_pct": 24.17, "peak_pct": 45.67, "state": "OK", "stale": false}, "post": "abl_tracescore/status_20261028T194000", "url": "https://github.com/skillberry-ai/cap-evolve/issues/946#issuecomment-6478806316"}
```

## TB-0060 · 2026-10-28T19:46Z · W posted abl_nogate · posted

Posted 'Cap evolve no gate hourly status' on #948 (abl_nogate): https://github.com/skillberry-ai/cap-evolve/issues/948#issuecomment-6478942104

```json
{"cp": 60, "prev_cp": 59, "prev_commit": "688ddea1a0328bb5728d653f3538c36599b8d56c", "utc": "2026-10-28T19:46:52Z", "kind": "posted", "phase": "W", "done_through": "P2/T1,T2,T4-T10", "next": "P3/window1", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "383d1584ee1492369a9c1d77e6bc0c4dc08509d1", "open_decisions": [], "memory": {"used_pct": 23.19, "peak_pct": 45.67, "state": "OK", "stale": false}, "post": "abl_nogate/status_20261028T194640", "url": "https://github.com/skillberry-ai/cap-evolve/issues/948#issuecomment-6478942104"}
```

## TB-0061 · 2026-10-28T19:53Z · W posted abl_naivegate · posted

Posted 'Cap evolve naive gate hourly status' on #949 (abl_naivegate): https://github.com/skillberry-ai/cap-evolve/issues/949#issuecomment-6479078051

```json
{"cp": 61, "prev_cp": 60, "prev_commit": "7cfb3055c1c9cdb7813892ff292870db4cd34c83", "utc": "2026-10-28T19:53:39Z", "kind": "posted", "phase": "W", "done_through": "P2/T1,T2,T4-T10", "next": "P3/window1", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "383d1584ee1492369a9c1d77e6bc0c4dc08509d1", "open_decisions": [], "memory": {"used_pct": 24.12, "peak_pct": 45.67, "state": "OK", "stale": false}, "post": "abl_naivegate/status_20261028T195320", "url": "https://github.com/skillberry-ai/cap-evolve/issues/949#issuecomment-6479078051"}
```
