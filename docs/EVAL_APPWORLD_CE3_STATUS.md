# AppWorld eval CE3: status ledger

The status ledger of the plan `docs/EVAL_APPWORLD_CE3.md` (Cap-Evolve Improvement 2 at gate K = 0.2, issue
skillberry-ai/cap-evolve #913; base plan `docs/EVAL_APPWORLD_CE2.md`). Append-only; every entry is written by
`examples/appworld/scripts/status_doc.py` under `flock(/workspace/aw_ce3/state/ledger.lock)`, then committed and
pushed to `origin eval-ce3`. Nothing below the marker is ever edited. Entry format and content rules: CE2 plan
section 14.2 and section 4.1 rule 6.

Pushed, publishable state: `docs/EVAL_APPWORLD_CE3_STATUS_STATE/`.

<!-- CHECKPOINTS BELOW THIS LINE -->

## CE3-0000 · 2026-10-24T10:29Z · P0 decisions · decision

Execution of eval CE3 starts (plan docs/EVAL_APPWORLD_CE3.md; base plan docs/EVAL_APPWORLD_CE2.md, applied unchanged except plan section 2). User decisions 2026-10-24: one arm ce3_k02, cap-evolve impr2 at 3db96a0 (CE2's pin), gate_k_se 0.2; no money or token cap (no optimizer_usd_per_iter, max_optimizer_usd 0 = off, the shim's 10M token cap off); 6 scored iterations, max_metric_calls 1029 and B = 900 kept (they fix the experiment's size); the window runs ce3_k02 only (168 test_normal x 2 trials = 336 cells), and the seed, ce2_k1 and ce2_k2 test_normal records of CE2's window (2026-10-23) are reused, every comparison labelled cross-window. Tracking issue #913 (skillberry-ai/cap-evolve), body = the plan projection. P1 done: branch eval-ce3 from origin/eval-ce2 (pushed as its own branch), worktree /workspace/worktrees/eval-ce3; executing-session deny rules (58) in .claude/settings.local.json (git-excluded); ~/bin/memok-ce3; memguard running on AW_STATE=/workspace/aw_ce3/state (5 s, 90/85). Build: /workspace/aw_ce3/build symlinks into REST's build (and venv-ce2), verify_build.py PASS (AppWorld 42b5bcf + patch, fastapi 0.143.0, pydantic 2.12.5, split/scenario/difficulty counts and split hashes, root_opt 148 dirs with 0 test-id hits, root_full mode 000); lint and publish caches copied byte-identical. Seed baseline (B4): seed_reuse.py PASS into CE3's state (147 records, listing sha256 b1b269f1..., = CE2-0004; train 0.400, dev 0.3333, union 0.3741); SEED_BASELINE_DONE set. Code: a ce3 profile (scripts/awce3.py) on top of CE2's (CE3 is one more CE2 arm); the CE2 driver, launcher, shim, sandbox, scan and ledger generalized; K is written with its decimals (a CE2 int(K) would have rendered 0.2 as 0: fixed before any use); the deny list adds CE2's run roots, state, opt dir and pushed artifacts. No open decision.

```json
{"cp": 0, "prev_cp": null, "prev_commit": "3a46c9c0b8c5538b295f7d8a1efccb3c128e77a3", "utc": "2026-10-24T10:29:18Z", "kind": "decision", "phase": "P0", "done_through": "P1/B4", "next": "P2/acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {"STATE/manifest.json": "0d74fdcf5e58e699fdc98dc1d4a5ff2558ce7599c87cac74134c6958c2e3cfc9"}, "code": "3a46c9c0b8c5538b295f7d8a1efccb3c128e77a3", "open_decisions": [], "memory": {"used_pct": 5.42, "peak_pct": 5.48, "state": "OK", "stale": false}, "issues": {"ce3_k02": 913}}
```

## CE3-0001 · 2026-10-24T10:32Z · P0 posted ce3_k02 · posted

Posted 'execution started' on #913 (ce3_k02): https://github.com/skillberry-ai/cap-evolve/issues/913#issuecomment-6383142923

```json
{"cp": 1, "prev_cp": 0, "prev_commit": "c2cea7521517866de20d7df2971342df5a296ee2", "utc": "2026-10-24T10:32:07Z", "kind": "posted", "phase": "P0", "done_through": "P1/B4", "next": "P2/acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "c2cea7521517866de20d7df2971342df5a296ee2", "open_decisions": [], "memory": {"used_pct": 7.65, "peak_pct": 7.65, "state": "OK", "stale": false}, "post": "ce3_k02/start", "url": "https://github.com/skillberry-ai/cap-evolve/issues/913#issuecomment-6383142923"}
```

## CE3-0002 · 2026-10-24T10:32Z · P0 hourly posts late · error

The last post on the issue of ce3_k02 is older than 60 minutes (section 8). The auto-poster is restarted by resume.py; checking it now.

```json
{"cp": 2, "prev_cp": 1, "prev_commit": "dc16daa63f9626ab8d1a83cb0fb212623e856801", "utc": "2026-10-24T10:32:08Z", "kind": "error", "phase": "P0", "done_through": "P1/B4", "next": "P2/acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "c2cea7521517866de20d7df2971342df5a296ee2", "open_decisions": [], "memory": {"used_pct": 7.72, "peak_pct": 7.72, "state": "OK", "stale": false}}
```

## CE3-0003 · 2026-10-24T10:47Z · P2 acceptance done · phase_done

P2 done; every acceptance check required before a counted rollout has passed. Re-run for CE3 (none counted): A1 PASS (gateway and claude CLI, modelUsage only aws/claude-sonnet-5-5); A9 PASS for ce3_k02 in its exact launch configuration (23 secrets planted, including both CE2 run roots, CE2's state and CE2's opt dir; 0 leaked; Bash 9 / Read 23 / Grep 2; outbound HTTPS and AF_UNIX refused; workspace write and lint ran; planting dirs removed, root_full 000); A11 PASS (5 s guard, PAUSE within 4.5 s, nothing starts while paused, resume below 85%, memok-ce3); A12 PASS; A13 PASS (an identical-to-seed candidate served from the reused cache on all 147 ids, 0 counted, TGC 0.3741; a fresh seed episode refused). A-CE3 1-8: code pin 3db96a0 clean; skills pin; gate_k_se 0.2 in spec and run_config; '--k-se 0.2' on the hill-climb command line and NO --max-budget-usd / --usd-budget flag (no money cap, CE3 §2); pinned gate.py accepts 0.3 SE at k 0.2, rejects it at 1, rejects 0.1 SE at 0.2; INSTRUCTIONS carry J1 with no forbidden string; guidance skills match the pin; the pinned hill-climb run.py ran; A-CE3-SAME: spec differs from CE2's ce2_k1 only in gate_k_se, the removed money caps and the header comment, INSTRUCTIONS identical. Carried from CE2 (same code): A2, A3/A5, A4, A6, A7 (re-done in P7 with the CE3 order seed 2026102407), A8, A10. Next: P4 search.

```json
{"cp": 3, "prev_cp": 2, "prev_commit": "832a41f544c8c8efa0eb58470a1ec5928cc2937d", "utc": "2026-10-24T10:47:05Z", "kind": "phase_done", "phase": "P2", "done_through": "P2/acceptance", "next": "P4/searches", "arm": null, "counts": {}, "spend": {}, "artifacts": {"STATE/acceptance/a9_ce3_k02.json": "35dfd927d643f3447c31306e1f7d1ca73fb9975987784ec185d93382f2b8bdd0", "STATE/acceptance/a_ce3_ce3_k02.json": "de79c046df526adcf130722fdda64edba35604158ba9c8a4d131b69f4e8d5352", "STATE/ce2/same.json": "a55b0760493bbc45ac42a8da1f63c825e8a97fa153d1fcc0389f6e71cf1358ae"}, "code": "832a41f544c8c8efa0eb58470a1ec5928cc2937d", "open_decisions": [], "memory": {"used_pct": 5.49, "peak_pct": 19.71, "state": "OK", "stale": false}}
```

## CE3-0004 · 2026-10-24T10:47Z · P4 searches launched · phase_start

P4: chain(s) ce3_k02 started (search, freeze, isolation scan); pid files AW_STATE/p4/<arm>.pid. Running now: ce3_k02. Global slots 24; memory 5.49%.

```json
{"cp": 4, "prev_cp": 3, "prev_commit": "50165368dd0597e465e2363ef0d54d42f381d9f7", "utc": "2026-10-24T10:47:07Z", "kind": "phase_start", "phase": "P4", "done_through": "P2/acceptance", "next": "P4/searches", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "832a41f544c8c8efa0eb58470a1ec5928cc2937d", "open_decisions": [], "memory": {"used_pct": 5.49, "peak_pct": 19.71, "state": "OK", "stale": false}}
```

## CE3-0005 · 2026-10-24T10:47Z · P4 posted ce3_k02 · posted

Posted 'search started' on #913 (ce3_k02): https://github.com/skillberry-ai/cap-evolve/issues/913#issuecomment-6383284254

```json
{"cp": 5, "prev_cp": 4, "prev_commit": "9ba5e1ebc25a28dbbf9e534a39d6fbc77af64e94", "utc": "2026-10-24T10:47:58Z", "kind": "posted", "phase": "P4", "done_through": "P2/acceptance", "next": "P4/searches", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "832a41f544c8c8efa0eb58470a1ec5928cc2937d", "open_decisions": [], "memory": {"used_pct": 6.25, "peak_pct": 19.71, "state": "OK", "stale": false}, "post": "ce3_k02/m4_launch", "url": "https://github.com/skillberry-ai/cap-evolve/issues/913#issuecomment-6383284254"}
```

## CE3-0006 · 2026-10-24T11:13Z · P4 heartbeat · heartbeat

No checkpoint for 25 min. Phase P4, last result: P2/acceptance.
Runner: no runner. Last log line: `2026-10-24T11:13:10Z | memguard | - | sample 47.18% (15458 MB) state OK peak 47.6%`.
Next: P4/searches.

```json
{"cp": 6, "prev_cp": 5, "prev_commit": "91c6944305f2193ee295ae1b22ff6accd328a7a9", "utc": "2026-10-24T11:13:10Z", "kind": "heartbeat", "phase": "P4", "done_through": "P2/acceptance", "next": "P4/searches", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "832a41f544c8c8efa0eb58470a1ec5928cc2937d", "open_decisions": [], "memory": {"used_pct": 47.18, "peak_pct": 47.58, "state": "OK", "stale": false}, "runner": "none"}
```
