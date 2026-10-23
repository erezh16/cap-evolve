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

## CE2-0001 · 2026-10-23T09:28Z · P1 B0 push to wrong branch · error

Error and repair in B0. The worktree was created with 'git worktree add -b eval-ce2 ... origin/eval-rest', which set the new branch's upstream to origin/eval-rest; with push.default=upstream the first push of B0 (commit f283fd2: this plan copy and the ledger header, two new files) went to origin/eval-rest instead of a new branch. Repair, approved by the user: origin/eval-ce2 created at f283fd2; origin/eval-rest restored to d049ba6 (REST's last commit) with a force-with-lease that required it to still be at f283fd2; the upstream of eval-ce2 set to origin/eval-ce2. status_doc.py always pushes HEAD:eval-ce2 explicitly. No REST file was changed at any point.

```json
{"cp": 1, "prev_cp": 0, "prev_commit": "e5dbc4edb239247f5a49859983a3e48d8e3e2ccd", "utc": "2026-10-23T09:28:38Z", "kind": "error", "phase": "P1", "done_through": "P1/B0", "next": "P1/B1", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "a390b3abc432cfbfb5642d00bbd706a42c3f337e", "open_decisions": [], "memory": {"used_pct": 4.91, "peak_pct": 5.88, "state": "OK", "stale": false}}
```

## CE2-0002 · 2026-10-23T09:28Z · P1 R1 directory listing · error

Rule R1 note (executing session): during B1 a directory listing intended for Claude's transcript dirs also listed the names of three entries under REST's cape_run work dir (one candidate dir, its integrity json and its optimizer stderr file). Only these names were shown; no file content of REST's run, champion, trajectories or results was read. The executing session's transcript is part of the P6 scan. No optimizer is affected: no optimizer has run yet.

```json
{"cp": 2, "prev_cp": 1, "prev_commit": "83115d25bacbd5b219342c3d698fb75f407a3c72", "utc": "2026-10-23T09:28:39Z", "kind": "error", "phase": "P1", "done_through": "P1/B0", "next": "P1/B1", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "a390b3abc432cfbfb5642d00bbd706a42c3f337e", "open_decisions": [], "memory": {"used_pct": 4.91, "peak_pct": 5.88, "state": "OK", "stale": false}}
```

## CE2-0003 · 2026-10-23T09:28Z · P1 build B1 B2 B3 · result

B1: CE2 constants in examples/appworld/scripts/awce2.py (CANDIDATES ce2_k1, ce2_k2; ISSUES 909, 910; METHOD_NAMES; K_SE 1 / 2; run roots /workspace/aw_ce2/run_k1, run_k2; cape pin 8194578 at /workspace/worktrees/cape-impr2), loaded by awrest.py only when AW_PROFILE=ce2 (REST unchanged otherwise); examples/appworld/ce2/env.sh sets AW_PROFILE, AW_HOME, AW_STATE, AW_SCRATCH_ROOT, AW_LEDGER_NAME, AW_BRANCH, AW_REPO, AW_ENV_FILE; status_doc.py writes CE2-NNNN entries with arm and memory fields. Kept from REST: B = 900, 10M optimizer tokens, seeds 100 / 5000, Sonnet 5.5 prices, models, 24 / 32 slots, split counts, AppWorld commit. B2: AW_BUILD/{appworld, root_opt, root_full, reference, clones, venvs/venv-aw} are symlinks into /workspace/aw_rest/build; verify_build.py (trusted) PASS: AppWorld HEAD 42b5bcf, git diff and patch sha256 equal REST's manifest; fastapi 0.143.0, pydantic 2.12.5; split counts 90/57/168/417, scenarios 30/19/56/139, difficulties and split-file sha256 all equal; root_opt 148 task dirs, only train/dev split files, 0 test-id hits; root_full mode 000 before and after. Lint and publishing caches copied by copy_caches.py, byte-identical (sha256 534cb748..., 5246180e...; 732 ids, 1,528 8-grams, 249 contacts). B3: venv-ce2 = venv-aw's freeze (123 packages) with -e /workspace/worktrees/cape-impr2/core instead of the eval-rest core; its freeze equals the requirement file; cap_evolve imports from the cape-impr2 worktree; no eval-rest or cape-improve core. Remaining hard-coded REST names (sandbox, A9, scan, report, autopost texts) are fixed in B5 and listed then.

```json
{"cp": 3, "prev_cp": 2, "prev_commit": "fe907f7409b31eb488f186d46cc97bd28d7977fc", "utc": "2026-10-23T09:28:41Z", "kind": "result", "phase": "P1", "done_through": "P1/B3", "next": "P1/B4", "arm": null, "counts": {}, "spend": {}, "artifacts": {"local/build_check.json": "c25cbef281343d54c28e9286be185755251151e1a6dfafcd72c1fda8f091c4dc"}, "code": "a390b3abc432cfbfb5642d00bbd706a42c3f337e", "open_decisions": [], "memory": {"used_pct": 4.91, "peak_pct": 5.88, "state": "OK", "stale": false}}
```

## CE2-0004 · 2026-10-23T09:28Z · P3 seed baseline reused · decision

Seed baseline reused from REST P3, 2026-10-20, 147 records, not re-run (user decision 2026-10-22, D5). seed_reuse.py (trusted, plan section 7.4) PASS: seed_capability tree hash = SEED_HASH 85a0da9cec2206a7...; aw_agent.py (model config), seed_capability/, evaluator.py and the AppWorld patch byte-identical to REST commit a0c85b4; 147 cache files copied, sorted (file, sha256) listing sha256 b1b269f1... before and after; ids = train.txt ∪ dev.txt exactly, trial seed 100, 0 infra errors, no trace key; train TGC 0.400, dev 0.3333, union 0.3741, equal to REST's seed/baseline.json; no other REST cache record copied. AW_STATE/SEED_BASELINE_DONE created; from now on a fresh seed episode raises SeedRerunRefused. The baseline is labelled 'reused' in every result and its cost is not counted in this run.

```json
{"cp": 4, "prev_cp": 3, "prev_commit": "4c684f4290541306b17b00a2d2e1a7593bb5ea88", "utc": "2026-10-23T09:28:42Z", "kind": "decision", "phase": "P3", "done_through": "P1/B4", "next": "P1/B5", "arm": null, "counts": {}, "spend": {}, "artifacts": {"local/seed_reuse.json": "74dd254402ed0898c94fea8e9416dfa3d41358bb5f9415b9ddfc4fc7073b76f5", "STATE/manifest.json": "840e832dd6ec0ce76575547ea529d268275404d24bf2932518df38a77e339ad9"}, "code": "a390b3abc432cfbfb5642d00bbd706a42c3f337e", "open_decisions": [], "memory": {"used_pct": 4.95, "peak_pct": 5.88, "state": "OK", "stale": false}}
```

## CE2-0005 · 2026-10-23T09:32Z · P3 posted ce2_k1 · posted

Posted 'execution started' on #909 (ce2_k1): https://github.com/skillberry-ai/cap-evolve/issues/909#issuecomment-6361875715

```json
{"cp": 5, "prev_cp": 4, "prev_commit": "fa73a15686fa97a83e93919d540a502f4c92f2fe", "utc": "2026-10-23T09:32:16Z", "kind": "posted", "phase": "P3", "done_through": "P1/B4", "next": "P1/B5", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "a390b3abc432cfbfb5642d00bbd706a42c3f337e", "open_decisions": [], "memory": {"used_pct": 5.01, "peak_pct": 5.88, "state": "OK", "stale": false}, "post": "ce2_k1/start", "url": "https://github.com/skillberry-ai/cap-evolve/issues/909#issuecomment-6361875715"}
```
