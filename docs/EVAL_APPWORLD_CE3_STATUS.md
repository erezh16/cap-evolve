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
