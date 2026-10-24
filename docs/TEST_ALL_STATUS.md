# AppWorld TEST_ALL: status ledger

The execution ledger of the plan `docs/TEST_ALL.md` (on `cap-evolve-impr2`; a copy is on this branch, `test-all`).
Append-only. Entries `TA-NNNN` are written only by `examples/appworld/scripts/status_doc.py`, under
`flock(/workspace/aw_testall/state/ledger.lock)`, and each is committed and pushed with
`git push origin HEAD:test-all`. Nothing below the marker is ever edited. Counts and aggregates only: no task id,
task or supervisor text, trajectory, secret or per-task test outcome; no test score of any arm before the window
completes and the analysis has run (plan §4.1, §12.2).

<!-- CHECKPOINTS BELOW THIS LINE -->

## TA-0000 · 2026-10-24T22:34Z · P0 decisions, issues, B0-B3 · decision

Execution of docs/TEST_ALL.md starts (session 64d72acb). Decisions D1 to D9 (plan section 14) taken as written. Two more, from the user on 2026-10-24: D10, surfaces: section 3's column is kept as 'surfaces searched', and a measured column 'surfaces changed vs seed' (file sha256 vs the seed's) is added; T4 and the section 11.3 surface analysis use the measured one. Measured: gepa P (plan P+T), skillopt M, wikiskill M, evoskill M (plan P+T+M); the other 9 arms as planned; ace's helpers.py is empty (the seed's is a docstring only), so no helper code either way. D11, deny rules: this session runs from the base worktree, so the 58 rules of section 4.1.1 were written to test-all/.claude/settings.local.json exactly as listed AND merged into base/.claude/settings.local.json (40 -> 68 rules; git-excluded, nothing committed); a denied Read of a non-existent path under state/final was refused. Tracking issues (skillberry-ai/cap-evolve, one per arm, each with its projected plan as the body, 47.9K-48.6K chars, none shortened, content filter clean): seed #915, altk #916, ace #917, gepa #918, skillopt #919, wikiskill #920, evoskill #921, metaharness #922, harnesslens #923, miprov2 #924, trace2skill #925, gepa_full #926, cape_k02 #927. Hourly offsets i x 276 s recorded in manifest.json. Host: container_age_s=213059 cpu_limit=8 used_MB=2529  current_MB=10034  peak_MB=30794 oom_kills_since_start=0  oom_kills_whole_container=1  swap_max=0 limit_MB=32768  used_pct=7 verdict=OK  subagents_that_fit=29 (at 750 MB each, before what they run) . B0 done: branch test-all from origin/eval-ce3 8f32ee1 (eval-ce3 did not move), worktree /workspace/worktrees/test-all, state /workspace/aw_testall, scratch /tmp/aw_testall, memguard pid 697195 (90/85, 5 s), memok-testall. B1 done: awtestall.py profile (13 arms, 5 trials, seeds 7000+k, order seed 2026102501, LEDGER TA, pushed state docs/TEST_ALL_STATE/). B2 done: build symlinks into /workspace/aw_rest/build (appworld, root_full, root_opt, reference, clones, venv-aw; root_opt and clones are added for the dev acceptance episodes and verify_build); verify_build.py all ok (AppWorld 42b5bcf + patch diff sha256 as REST; fastapi 0.143.0, pydantic 2.12.5; 90/57/168/417 ids, scenarios and difficulties, split sha256 as REST; root_opt 148 dirs, 0 test-id hits; root_full 000 before and after); lint and publish caches copied byte-identical. B3 done: all 13 artifacts match their expected hashes (seed, harnesslens, miprov2, trace2skill, gepa_full, cape_k02 from local copies; altk, ace, gepa, skillopt, wikiskill, evoskill, metaharness from Box), seed and harnesslens scored copies byte-identical; lint passes on 12 arms, ace fails only the memory-size rule (55,513 chars > 30,000), the disclosed exception D6. Next: B4 window and analysis code, autopost and heartbeat.

```json
{"cp": 0, "prev_cp": null, "prev_commit": "96ffecc234681b230325a9a772ccfba61aed4cd6", "utc": "2026-10-24T22:34:55Z", "kind": "decision", "phase": "P0", "done_through": "P1/b3", "next": "P1/b4", "arm": null, "counts": {}, "spend": {}, "artifacts": {"STATE/manifest.json": "ba054bb00892dd74fd0acd6c2429ac1648c32ea4bc03e5ae59352016ff38284f"}, "code": "96ffecc234681b230325a9a772ccfba61aed4cd6", "open_decisions": [], "memory": {"used_pct": 7.72, "peak_pct": 7.93, "state": "OK", "stale": false}, "issues": {"seed": 915, "altk": 916, "ace": 917, "gepa": 918, "skillopt": 919, "wikiskill": 920, "evoskill": 921, "metaharness": 922, "harnesslens": 923, "miprov2": 924, "trace2skill": 925, "gepa_full": 926, "cape_k02": 927}, "decisions": ["D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "D11"]}
```

## TA-0001 · 2026-10-24T22:38Z · P0 posted harnesslens · posted

Posted 'HarnessLens hourly status' on #923 (harnesslens): https://github.com/skillberry-ai/cap-evolve/issues/923#issuecomment-6390427752

```json
{"cp": 1, "prev_cp": 0, "prev_commit": "b3719fedee6f144e71d15073f9ef96e9ecdd48c8", "utc": "2026-10-24T22:38:42Z", "kind": "posted", "phase": "P0", "done_through": "P1/b3", "next": "P1/b4", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "b3719fedee6f144e71d15073f9ef96e9ecdd48c8", "open_decisions": [], "memory": {"used_pct": 7.85, "peak_pct": 7.93, "state": "OK", "stale": false}, "post": "harnesslens/status_20261024T223648", "url": "https://github.com/skillberry-ai/cap-evolve/issues/923#issuecomment-6390427752"}
```

## TA-0002 · 2026-10-24T22:41Z · P0 posted miprov2 · posted

Posted 'MIPROv2 hourly status' on #924 (miprov2): https://github.com/skillberry-ai/cap-evolve/issues/924#issuecomment-6390452869

```json
{"cp": 2, "prev_cp": 1, "prev_commit": "9b6b38cd3faf07f6210961cd1b3c6b474b5eae64", "utc": "2026-10-24T22:41:25Z", "kind": "posted", "phase": "P0", "done_through": "P1/b3", "next": "P1/b4", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "b3719fedee6f144e71d15073f9ef96e9ecdd48c8", "open_decisions": [], "memory": {"used_pct": 7.77, "peak_pct": 8.07, "state": "OK", "stale": false}, "post": "miprov2/status_20261024T224124", "url": "https://github.com/skillberry-ai/cap-evolve/issues/924#issuecomment-6390452869"}
```

## TA-0003 · 2026-10-24T22:46Z · P0 posted trace2skill · posted

Posted 'Trace2Skill hourly status' on #925 (trace2skill): https://github.com/skillberry-ai/cap-evolve/issues/925#issuecomment-6390496431

```json
{"cp": 3, "prev_cp": 2, "prev_commit": "245b809439894bec44d9a1b06f09dcbdc6df5bce", "utc": "2026-10-24T22:46:07Z", "kind": "posted", "phase": "P0", "done_through": "P1/b3", "next": "P1/b4", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "245b809439894bec44d9a1b06f09dcbdc6df5bce", "open_decisions": [], "memory": {"used_pct": 7.86, "peak_pct": 8.07, "state": "OK", "stale": false}, "post": "trace2skill/status_20261024T224600", "url": "https://github.com/skillberry-ai/cap-evolve/issues/925#issuecomment-6390496431"}
```

## TA-0004 · 2026-10-24T22:50Z · P0 posted gepa_full · posted

Posted 'GEPA-Full hourly status' on #926 (gepa_full): https://github.com/skillberry-ai/cap-evolve/issues/926#issuecomment-6390539120

```json
{"cp": 4, "prev_cp": 3, "prev_commit": "da1202d70a3d346bc602180374cfa3d0ac7f1944", "utc": "2026-10-24T22:50:50Z", "kind": "posted", "phase": "P0", "done_through": "P1/b3", "next": "P1/b4", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "da1202d70a3d346bc602180374cfa3d0ac7f1944", "open_decisions": [], "memory": {"used_pct": 7.9, "peak_pct": 8.07, "state": "OK", "stale": false}, "post": "gepa_full/status_20261024T225036", "url": "https://github.com/skillberry-ai/cap-evolve/issues/926#issuecomment-6390539120"}
```

## TA-0005 · 2026-10-24T22:53Z · P1 build B4 done · phase_done

B4 done: window.py runs the testall profile (13 arms x 168 x 5 trials, order seed 2026102501, trial seeds 7000+k, per-arm hash check through fetch_artifacts.check_scored instead of tree_hash, section 6.3; root_full relocked whenever the runner exits). analyze_all.py (section 11: TGC/SGC overall and by difficulty, all 78 pairs with a 56-scenario paired bootstrap, 10,000 resamples, Random(0), Holm over the 78 pairs, ranking with CIs, harnesslens-seed noise check, pass-count distribution, stable/flaky shares, pass@k and pass^k, within-task variance, trial-count sensitivity, earlier windows as context) and report_all.py (combined RESULTS.md and 13 per-arm comments), tested on a synthetic 13 x 168 x 5 window in a throwaway state (78 pairs, pass@1 = TGC, monotone pass@k/pass^k; about 15 min at 10,000 resamples). resume.py (section 10) dry run clean. autopost.py runs the 13 staggered timers (TA-0001 to TA-0004 on their slots); the heartbeat checks each issue's age, the guard and the section 8 stall rule. Next: P2 acceptance T1 to T10.

```json
{"cp": 5, "prev_cp": 4, "prev_commit": "45064a267990ae533d09176ab96e9f13aa326dc3", "utc": "2026-10-24T22:53:14Z", "kind": "phase_done", "phase": "P1", "done_through": "P1/b4", "next": "P2/acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "45064a267990ae533d09176ab96e9f13aa326dc3", "open_decisions": [], "memory": {"used_pct": 7.87, "peak_pct": 8.07, "state": "OK", "stale": false}}
```

## TA-0006 · 2026-10-24T22:55Z · P1 posted cape_k02 · posted

Posted 'Cap-Evolve-impr2 K=0.2 hourly status' on #927 (cape_k02): https://github.com/skillberry-ai/cap-evolve/issues/927#issuecomment-6390579258

```json
{"cp": 6, "prev_cp": 5, "prev_commit": "c2204b9bb9bbeb6506e916bbe5f12402d69b070a", "utc": "2026-10-24T22:55:13Z", "kind": "posted", "phase": "P1", "done_through": "P1/b4", "next": "P2/acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "45064a267990ae533d09176ab96e9f13aa326dc3", "open_decisions": [], "memory": {"used_pct": 14.66, "peak_pct": 14.66, "state": "OK", "stale": false}, "post": "cape_k02/status_20261024T225512", "url": "https://github.com/skillberry-ai/cap-evolve/issues/927#issuecomment-6390579258"}
```

## TA-0007 · 2026-10-24T23:00Z · P1 posted seed · posted

Posted 'seed agent hourly status' on #915 (seed): https://github.com/skillberry-ai/cap-evolve/issues/915#issuecomment-6390624816

```json
{"cp": 7, "prev_cp": 6, "prev_commit": "9cf7be2e8b0a5c078fc8f9b6942c8113d60dfe0a", "utc": "2026-10-24T23:00:16Z", "kind": "posted", "phase": "P1", "done_through": "P1/b4", "next": "P2/acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "9cf7be2e8b0a5c078fc8f9b6942c8113d60dfe0a", "open_decisions": [], "memory": {"used_pct": 7.81, "peak_pct": 25.44, "state": "OK", "stale": false}, "post": "seed/status_20261024T230000", "url": "https://github.com/skillberry-ai/cap-evolve/issues/915#issuecomment-6390624816"}
```

## TA-0008 · 2026-10-24T23:04Z · P1 posted altk · posted

Posted 'ALTK-Evolve hourly status' on #916 (altk): https://github.com/skillberry-ai/cap-evolve/issues/916#issuecomment-6390665492

```json
{"cp": 8, "prev_cp": 7, "prev_commit": "057eea721594b7cee2e6ab9048431852be1042a8", "utc": "2026-10-24T23:04:42Z", "kind": "posted", "phase": "P1", "done_through": "P1/b4", "next": "P2/acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "057eea721594b7cee2e6ab9048431852be1042a8", "open_decisions": [], "memory": {"used_pct": 12.92, "peak_pct": 25.44, "state": "OK", "stale": false}, "post": "altk/status_20261024T230436", "url": "https://github.com/skillberry-ai/cap-evolve/issues/916#issuecomment-6390665492"}
```
