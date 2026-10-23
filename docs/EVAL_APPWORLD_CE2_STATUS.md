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

## CE2-0006 · 2026-10-23T09:32Z · P3 posted ce2_k2 · posted

Posted 'execution started' on #910 (ce2_k2): https://github.com/skillberry-ai/cap-evolve/issues/910#issuecomment-6361876373

```json
{"cp": 6, "prev_cp": 5, "prev_commit": "ab4eea52e5d56ac06c5b518af365848e6fbd8fc4", "utc": "2026-10-23T09:32:18Z", "kind": "posted", "phase": "P3", "done_through": "P1/B4", "next": "P1/B5", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "ab4eea52e5d56ac06c5b518af365848e6fbd8fc4", "open_decisions": [], "memory": {"used_pct": 5.05, "peak_pct": 5.88, "state": "OK", "stale": false}, "post": "ce2_k2/start", "url": "https://github.com/skillberry-ai/cap-evolve/issues/910#issuecomment-6361876373"}
```

## CE2-0007 · 2026-10-23T09:56Z · P1 build B5 · result

B5 done. Driver examples/appworld/ce2/ (from REST's cape_improve/): run_ce2.py (setup, imp-check, accept, same, search, freeze, progress; --arm ce2_k1|ce2_k2), launch_ce2.sh (sources env.sh; venv-ce2 cap-evolve; CAPEVOLVE_SKILLS_DIR = pinned skills; shim first on PATH; AW_CAPE_ARM; RITS keys and CLAUDECODE unset; waits on memok-ce2; IMP launch checks 1-3, exit 3 on failure; refuses if claude is not the shim; stderr teed to progress/<arm>.log), sandbox_cc/claude (per-arm usage log from modelUsage, memok-ce2 and PAUSE wait, 10M cap, model variables pinned), adapter.py (all rollouts through the shared evaluator), capevolve.yaml (plan 9.3; gate_k_se filled per arm). Instructions (plan 9.4): byte copy of the pinned template (sha256 df486563...) plus ONE inserted section 'AppWorld facts for THIS run' immediately before PREPARATION, REST's block with the objective-score paragraph first; instructions.diff: 35 lines added, 0 removed; one rendered file for both arms (AW_STATE/ce2/INSTRUCTIONS.md, sha256 49bd1c55...). Sandbox deny list (plan 12): REST's list plus all of /workspace/aw_rest, /tmp/aw_rest, /tmp/aw_ce2, /workspace/worktrees, every AW_BUILD symlink and its target, the build venvs, the other arm's run root and the arm's own adapters dir; the optimizers' lint venv and tools moved to /workspace/aw_ce2/opt (not under a denied path). Both projects scaffolded with the pinned intake script; cap-evolve check {ok: true} (147 val tasks); A-CE2-SAME PASS: the rendered specs differ only in the gate_k_se line, INSTRUCTIONS identical. IMP launch checks 1-3 PASS for both arms (core from cape-impr2 at 8194578, clean; skills dir = the pinned skills, not ~/.claude/skills; gate_k_se 1 and 2).

```json
{"cp": 7, "prev_cp": 6, "prev_commit": "bae13b0c433ac7fc7bb011745ac7dc8b1b312419", "utc": "2026-10-23T09:56:03Z", "kind": "result", "phase": "P1", "done_through": "P1/B5", "next": "P2/acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {"STATE/ce2/instructions.diff": "305308b7143fa279fcfd7f14c9e92b0719194cb30d17612cbbbf8ea98280ae84", "STATE/ce2/same.json": "1805e1a1d8a071433d566c3fde23e92c17b1e3f0f1e6880595978455d5e2a0ae"}, "code": "bae13b0c433ac7fc7bb011745ac7dc8b1b312419", "open_decisions": [], "memory": {"used_pct": 5.02, "peak_pct": 7.97, "state": "OK", "stale": false}}
```

## CE2-0008 · 2026-10-23T09:56Z · P2 acceptance A1 A3 A5 A6 A7 A9 · result

Acceptance (none counted): A1 PASS (gateway via opt_llm and the claude CLI; modelUsage shows only aws/claude-sonnet-5-5). A3/A5 PASS (import os, open(answer.json) and a pathlib read fail in the REPL; root_opt has no test data; split_ids train = val = train ∪ dev (147), test = []; a no-op scores 0; scoring twice identical; no trace or gold persisted; the released-solution probe is not repeated, plan 17, REST passed it with the same code). A6 PASS (train order = load_task_ids, 90; an outside id and the test split refused). A7 PASS (final order 168 x 3 arms x 2 trials = 1,008 cells, reproducible from seed 2026102207, sha256 in manifest; root_full relocked). A9 PASS for EACH arm in its exact launch configuration (the shim, registry flags --allowedTools Bash and acceptEdits, workdir <run dir>/work/a9_ws): 21 secrets planted per arm (root_opt and a train ground_truth dir via symlink and target, root_full, the AppWorld clone, its generate/ and apps source, REST's cape_run and state, the other arm's project root, the arm's adapters dir, AW_STATE, scratch, the eval-ce2 checkout and core, the cape-impr2 checkout, venvs, a stand-in next to the base .env, ~/.claude/projects, ~/.config/gh, two probe dirs); 0 leaked; ce2_k1 Bash 9 / Read 22 / Grep 2 / one sub-agent, ce2_k2 Bash 8 / Read 22 / Grep 2 / one sub-agent; outbound HTTPS refused; AF_UNIX socket refused; workspace write and the lint ran. A first A9 attempt ran both arms in parallel and failed on its own cleanup (both planted in each other's dirs; no leak); re-run sequentially. Every planting dir removed (cleanup check: 0 left, root_full mode 000); A9's usage lines and result JSONs moved to AW_STATE/<arm>/accept/ (REST CP-0041), so each search's usage log starts empty. Remaining: A2, A4, A8, A10, A11, A12, A13, A-CE2 4-7 (mock dry run per arm).

```json
{"cp": 8, "prev_cp": 7, "prev_commit": "e30ebc1395c4c80cce4d1651fc3a200d25ec4077", "utc": "2026-10-23T09:56:05Z", "kind": "result", "phase": "P2", "done_through": "P2/A9", "next": "P2/acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {"STATE/acceptance/a9_ce2_k1.json": "66e38b596620d9a357f04e1aac21d4b0774bf0155f7c61574bc6d725e150eab3", "STATE/acceptance/a9_ce2_k2.json": "ae803fd48aa1903064a80e4415d58fbcdca2bc61f7613e8c294b1b81f3e09401"}, "code": "bae13b0c433ac7fc7bb011745ac7dc8b1b312419", "open_decisions": [], "memory": {"used_pct": 5.06, "peak_pct": 7.97, "state": "OK", "stale": false}}
```

## CE2-0009 · 2026-10-23T10:11Z · P2 A13 ran fresh episodes · repair

Repair (acceptance, nothing counted toward any arm). The first CE2 A13 run checked 'a candidate identical to the seed is served from the cache' AFTER the check's throwaway cache path had been swapped in (an ordering bug in my adaptation), so it ran fresh episodes of the seed on train ∪ dev, phase search, under the throwaway name acc_a13, into the throwaway A13 cache. Caught by the memory reading (52% at about 24 episodes); stopped after 99 episodes (all killed, slots released). Not counted: acc_a13 is not an arm. The real reused seed cache is unchanged (147 files, listing sha256 b1b269f1..., equal to CE2-0004). Fix: the CE2 check now runs on the real cache before any path swap and refuses to run if any of the 147 records is missing. Re-run PASS: the identical candidate is served from the cache on all 147 ids, 0 counted, TGC from cache 0.3741 (= the reused baseline); a fresh seed episode raises SeedRerunRefused; slot pool peak 2 with size 2 and 3 callers. A12 PASS (episode, chat and claude -p usage records carry every 5.2 field; the CLI line's model is aws/claude-sonnet-5-5; 1M in + 1M out + 1M cache read = USD 12.20). A2 PASS (max_model_len 40,144; 48/48 concurrent 200, 0 x 429; 1 dev episode completed, 20 steps; RITS key hits 0). A4 PASS (seed first request byte-identical, 23 messages; memory slot placement; helpers and notes with the doc text unchanged; lint reject without a rollout).

```json
{"cp": 9, "prev_cp": 8, "prev_commit": "9740aae5c8330e57885dc4f68ccb5ab33c3f45ab", "utc": "2026-10-23T10:11:48Z", "kind": "repair", "phase": "P2", "done_through": "P2/A9", "next": "P2/acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {"local/acceptance/a13.json": "bd93609ae00524bf3fa22c5eb5db876b5ab38c2ae6e2c6d29c16877b06834cc9"}, "code": "9740aae5c8330e57885dc4f68ccb5ab33c3f45ab", "open_decisions": [], "memory": {"used_pct": 23.29, "peak_pct": 53.72, "state": "OK", "stale": false}}
```

## CE2-0010 · 2026-10-23T10:31Z · P2 posted ce2_k1 · posted

Posted 'Cap-Evolve-impr2 K=1 hourly status' on #909 (ce2_k1): https://github.com/skillberry-ai/cap-evolve/issues/909#issuecomment-6362895038

```json
{"cp": 10, "prev_cp": 9, "prev_commit": "8e737e069924785b9a49c1fb3df206e2dd8ebb96", "utc": "2026-10-23T10:31:54Z", "kind": "posted", "phase": "P2", "done_through": "P2/A9", "next": "P2/acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "9740aae5c8330e57885dc4f68ccb5ab33c3f45ab", "open_decisions": [], "memory": {"used_pct": 4.88, "peak_pct": 53.72, "state": "OK", "stale": false}, "post": "ce2_k1/status_20261023T1031", "url": "https://github.com/skillberry-ai/cap-evolve/issues/909#issuecomment-6362895038"}
```

## CE2-0011 · 2026-10-23T10:31Z · P2 posted ce2_k2 · posted

Posted 'Cap-Evolve-impr2 K=2 hourly status' on #910 (ce2_k2): https://github.com/skillberry-ai/cap-evolve/issues/910#issuecomment-6362895721

```json
{"cp": 11, "prev_cp": 10, "prev_commit": "5cbc3e087da52ce38d1a0936e2912fb8818f1151", "utc": "2026-10-23T10:31:57Z", "kind": "posted", "phase": "P2", "done_through": "P2/A9", "next": "P2/acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "9740aae5c8330e57885dc4f68ccb5ab33c3f45ab", "open_decisions": [], "memory": {"used_pct": 4.89, "peak_pct": 53.72, "state": "OK", "stale": false}, "post": "ce2_k2/status_20261023T1031", "url": "https://github.com/skillberry-ai/cap-evolve/issues/910#issuecomment-6362895721"}
```

## CE2-0012 · 2026-10-23T10:53Z · P2 candidate pin 3db96a0 · decision

User decision (2026-10-23), changing D4's pin: A-CE2 item 5 on the ce2_k1 dry run found the forbidden string 'largest expected reward gain' in the optimizer's INSTRUCTIONS.md. Its source was the pinned template itself: the Self-check line kept the old 'reward' wording, which contradicts plan 9.6.5 (forbidden string) and 9.4 (every pinned sentence unchanged). Asked, the user said the line should read 'objective score gain' and to fix, commit and continue; after reviewing every remaining 'reward' the user also reworded the next line. Commits on cap-evolve-impr2 (pushed): a09e48d (line 142 'largest expected objective score gain') and 3db96a0 (line 143 'cost the most objective score degradation'). The other uses of 'reward' (a trace's reward 0; strategy 4's softness clause about the agent's benchmark reward) are kept as written, by the user's review. core/ and skills/ are byte-identical between 8194578 and 3db96a0, so J2 to J5 are unaffected. The candidate for both arms is now 3db96a08ef77d7701f21771d389c6471a5d88344: cape-impr2 worktree detached there (clean), venv-ce2 imports its core, CAPE_COMMIT updated. The CE2 instructions were re-derived from the 3db96a0 template: insertions only (35 lines, 0 removed), no 'reward gain' left; rendered sha256 dccf0853...; A-CE2-SAME and IMP launch checks 1-3 re-run, PASS for both arms. Both arms' mock dry runs (A-CE2 4-7) are re-run on this pin. Reported as a deviation from the plan's pin in both results. Acceptance also PASS since CE2-0009: A8 (10 dev episodes, max prompt 11,763 tokens; H_max 17,560, P_max 3,230, M_cap 13,000; 3 max-memory episodes under 13.6K, tiktoken = vLLM), A10 (killed mini window resumed with 0 cells re-run; heartbeat marked the runner stalled; push failure kept local then pushed; filter refused a task id and an .env value; 3 concurrent writers x 4 appends all landed, unique, committed; local bare remote only), A11 (guard period 5 s; PAUSE within 4.5 s of crossing; no slot and no optimizer call while paused; resume only below the low mark; memok-ce2 reads the CE2 state).

```json
{"cp": 12, "prev_cp": 11, "prev_commit": "09fa3bc30630624f59d2d7d42fab7d14d4ac7565", "utc": "2026-10-23T10:53:40Z", "kind": "decision", "phase": "P2", "done_through": "P2/A9", "next": "P2/acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {"STATE/manifest.json": "01542c460b708716a73c632cc3db4ad1b33ed6cd08b1ff32e6fd3f5c20ab16cb", "STATE/ce2/instructions.diff": "305308b7143fa279fcfd7f14c9e92b0719194cb30d17612cbbbf8ea98280ae84", "STATE/ce2/same.json": "1805e1a1d8a071433d566c3fde23e92c17b1e3f0f1e6880595978455d5e2a0ae"}, "code": "09fa3bc30630624f59d2d7d42fab7d14d4ac7565", "open_decisions": [], "memory": {"used_pct": 5.03, "peak_pct": 53.72, "state": "OK", "stale": false}}
```

## CE2-0013 · 2026-10-23T10:54Z · P2 acceptance done · phase_done

P2 done: every acceptance check of plan section 15 has passed and is in the ledger (A1-A13: CE2-0008, CE2-0009, CE2-0012; A9 per arm: CE2-0008). A-CE2 1-8, each arm, on the candidate pin 3db96a0 (CE2-0012): (1) cap_evolve imports from /workspace/worktrees/cape-impr2/core, HEAD 3db96a0, clean; (2) skills dir = the pinned skills, not ~/.claude/skills; (3) gate_k_se 1 / 2 in the rendered spec and in run_config; (4) hill-climb command line --k-se 1 (ce2_k1) and --k-se 2 (ce2_k2), baseline served from the cache; pinned gate.py: 1.5 SE accepted at K=1 and rejected at K=2, 2.5 SE accepted by both, 0.7 SE rejected by both; (5) work/cand_0001/INSTRUCTIONS.md has every required string and none forbidden, instructions.diff insertions only; (6) guidance tools and system-prompt SKILL.md sha256 equal the pin, diagnose head lines match; (7) the pinned hill-climb scripts/run.py ran (sha256 c04938fc...); (8) A-CE2-SAME: specs differ only in gate_k_se, INSTRUCTIONS identical. The 1-iteration mock dry runs (4 dev ids, accept namespace) counted 0 rollouts. P3 is the reused seed baseline (CE2-0004). Next: P4, both searches launched together.

```json
{"cp": 13, "prev_cp": 12, "prev_commit": "4072450aac84034ca81fe1c4b79494003542e54c", "utc": "2026-10-23T10:54:07Z", "kind": "phase_done", "phase": "P2", "done_through": "P2/acceptance", "next": "P4/searches", "arm": null, "counts": {}, "spend": {}, "artifacts": {"STATE/acceptance/a_ce2_ce2_k1.json": "76d93a6271946cecf098f26cbe1a76a3423ae8d8bfb7dec5852c0f7c2bdd5515", "STATE/acceptance/a_ce2_ce2_k2.json": "6b3d2d60d8ef384ff0f093bd650ad9df74204b9c85656c1871654db56a4db72a"}, "code": "09fa3bc30630624f59d2d7d42fab7d14d4ac7565", "open_decisions": [], "memory": {"used_pct": 5.07, "peak_pct": 53.72, "state": "OK", "stale": false}}
```

## CE2-0014 · 2026-10-23T10:56Z · P4 searches launched · phase_start

P4: chain(s) ce2_k1, ce2_k2 started (search, freeze, isolation scan); pid files AW_STATE/p4/<arm>.pid. Running now: ce2_k1, ce2_k2. Global slots 24; memory 5.05%.

```json
{"cp": 14, "prev_cp": 13, "prev_commit": "75a4e1ed28c9279e3db732027a7d069b12f09a45", "utc": "2026-10-23T10:56:30Z", "kind": "phase_start", "phase": "P4", "done_through": "P2/acceptance", "next": "P4/searches", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "75a4e1ed28c9279e3db732027a7d069b12f09a45", "open_decisions": [], "memory": {"used_pct": 5.05, "peak_pct": 53.72, "state": "OK", "stale": false}}
```

## CE2-0015 · 2026-10-23T10:57Z · P4 posted ce2_k1 · posted

Posted 'search started' on #909 (ce2_k1): https://github.com/skillberry-ai/cap-evolve/issues/909#issuecomment-6363312140

```json
{"cp": 15, "prev_cp": 14, "prev_commit": "25b237968a0f38e672a600e35f39e68437c94eef", "utc": "2026-10-23T10:57:18Z", "kind": "posted", "phase": "P4", "done_through": "P2/acceptance", "next": "P4/searches", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "75a4e1ed28c9279e3db732027a7d069b12f09a45", "open_decisions": [], "memory": {"used_pct": 6.44, "peak_pct": 53.72, "state": "OK", "stale": false}, "post": "ce2_k1/m4_launch", "url": "https://github.com/skillberry-ai/cap-evolve/issues/909#issuecomment-6363312140"}
```

## CE2-0016 · 2026-10-23T10:57Z · P4 posted ce2_k2 · posted

Posted 'search started' on #910 (ce2_k2): https://github.com/skillberry-ai/cap-evolve/issues/910#issuecomment-6363312745

```json
{"cp": 16, "prev_cp": 15, "prev_commit": "a760177651a6d0de3062122d5466e1cabbb4e4b6", "utc": "2026-10-23T10:57:20Z", "kind": "posted", "phase": "P4", "done_through": "P2/acceptance", "next": "P4/searches", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "75a4e1ed28c9279e3db732027a7d069b12f09a45", "open_decisions": [], "memory": {"used_pct": 6.44, "peak_pct": 53.72, "state": "OK", "stale": false}, "post": "ce2_k2/m4_launch", "url": "https://github.com/skillberry-ai/cap-evolve/issues/910#issuecomment-6363312745"}
```

## CE2-0017 · 2026-10-23T10:58Z · P4 posted ce2_k1 · posted

Posted 'Cap-Evolve-impr2 K=1 new best search-time score' on #909 (ce2_k1): https://github.com/skillberry-ai/cap-evolve/issues/909#issuecomment-6363323097

```json
{"cp": 17, "prev_cp": 16, "prev_commit": "22537c08dd4ebb365c824082afef680d243f50fb", "utc": "2026-10-23T10:58:00Z", "kind": "posted", "phase": "P4", "done_through": "P2/acceptance", "next": "P4/searches", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "75a4e1ed28c9279e3db732027a7d069b12f09a45", "open_decisions": [], "memory": {"used_pct": 6.55, "peak_pct": 53.72, "state": "OK", "stale": false}, "post": "ce2_k1/m4_best_0.3741496598639456", "url": "https://github.com/skillberry-ai/cap-evolve/issues/909#issuecomment-6363323097"}
```
