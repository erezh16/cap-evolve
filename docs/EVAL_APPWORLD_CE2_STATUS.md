# AppWorld eval CE2: status ledger

The status ledger of the plan `docs/EVAL_APPWORLD_CE2.md` (Cap-Evolve Improvement 2 at gate K = 1 and K = 2,
issues skillberry-ai/cap-evolve #909 and #910). Rule R3 (plan section 4.3): append-only; every entry is written
by `examples/appworld/scripts/status_doc.py` under `flock(/workspace/aw_ce2/state/ledger.lock)`, then committed
and pushed to `origin eval-ce2`. Nothing below the marker is ever edited. Entry format: plan section 14.2.
Content rules (no task id, task or supervisor text, train/dev 8-gram, trajectory, secret or per-task test
outcome): plan section 4.1 rule 6 and section 14.2.

Pushed, publishable state: `docs/EVAL_APPWORLD_CE2_STATUS_STATE/`.

<!-- CHECKPOINTS BELOW THIS LINE -->

## CE2-0000 · 2026-10-23T09:27Z · P0 decisions · decision

Execution of the eval CE2 plan starts. Decisions D1 to D10 (plan section 2) are taken as written: optimizer aws/claude-sonnet-5-5 for every role (D1); AppWorld 42b5bcf from source, pydantic 2.12.x, fastapi 0.143.0 (D2); 1 search trial, 2 final trials, 1 search seed per arm (D3); candidate pin 8194578 for both arms, gate_k_se 1 (ce2_k1) and 2 (ce2_k2) (D4); REST's P3 seed baseline reused (D5); final window seed + ce2_k1 + ce2_k2, 1,008 cells (D6); this separate ledger file (D7); Claude Code sandbox via the PATH shim with --setting-sources '' (D8); memory guard 90/85 every 5 s (D9); branch eval-ce2, worktree /workspace/worktrees/eval-ce2, state /workspace/aw_ce2 (D10). Issues on skillberry-ai/cap-evolve: ce2_k1 #909, ce2_k2 #910; each already carries its plan projection. Host: memcheck limit 32,768 MB, cpu_limit 8, oom.group 1, swap 0. B0 done: worktree eval-ce2 (from origin/eval-rest); worktree cape-impr2 detached at 8194578 (clean); executing-session deny rules copied into eval-ce2/.claude/settings.local.json (git-excluded); ~/bin/memok-ce2 created; memguard.py running with AW_STATE=/workspace/aw_ce2/state (5 s samples, a fresh MEMSTATE.json within 7 s). No open decision.

```json
{"cp": 0, "prev_cp": null, "prev_commit": "a390b3abc432cfbfb5642d00bbd706a42c3f337e", "utc": "2026-10-23T09:27:41Z", "kind": "decision", "phase": "P0", "done_through": "P0/decisions", "next": "P1/B1", "arm": null, "counts": {}, "spend": {}, "artifacts": {"STATE/manifest.json": "840e832dd6ec0ce76575547ea529d268275404d24bf2932518df38a77e339ad9"}, "code": "a390b3abc432cfbfb5642d00bbd706a42c3f337e", "open_decisions": [], "memory": {"used_pct": 4.9, "peak_pct": 5.88, "state": "OK", "stale": false}, "issues": {"ce2_k1": 909, "ce2_k2": 910}}
```
