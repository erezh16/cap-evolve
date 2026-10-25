# AppWorld ablations of cap-evolve `main` (75b3bcd): status ledger

The execution ledger of [`docs/ABLATIONS.md`](ABLATIONS.md) (rule R3, section 4.3). Append-only, newest last. Entries
are written only by `examples/appworld/scripts/status_doc.py` (profile `abl`, `AW_LEDGER_ID=ABL`), under
`flock(/workspace/aw_abl/state/ledger.lock)`, and pushed to `fork/eval-abl` after every entry. Nothing below the
marker is ever edited. Content rules: plan section 13.2 (no task ids, task text, trajectories, secrets or per-task test
outcomes).

Tracking issues (skillberry-ai/cap-evolve): `abl_ref` #930, `abl_cc` #931, `abl_prompt` #932, `abl_tools` #933,
`abl_notrace` #934, `abl_tracescore` #935.

<!-- CHECKPOINTS BELOW THIS LINE -->

## ABL-0000 · 2026-10-25T09:27Z · P0 decisions · decision

Execution of docs/ABLATIONS.md starts. Decisions D1 to D13 (plan section 2) are taken as written: optimizer aws/claude-sonnet-5-5 for every role (D1); agent openai/gpt-oss-120b-a100 on RITS (D2); 1 search trial, 2 final trials, 1 search seed per arm (D3); code under test cap-evolve main 75b3bcd, core and skills unmodified (D4); fresh reference arm abl_ref (D5); abl_cc is plain Claude Code (D6); gate_k_se 0.2 explicit and main's INSTRUCTIONS template (D7); one shared seed run P3 (D8); Claude Code sandbox via the PATH shim with --setting-sources '' (D9); memory guard 90/85 every 5 s (D10); this ledger on fork/eval-abl, one issue per arm, hourly posts (D11); no money or token cap, 200 turns per cap-evolve session (D12); memory/* sealed in every cap-evolve arm (D13). Issues on skillberry-ai/cap-evolve: abl_ref #930, abl_cc #931, abl_prompt #932, abl_tools #933, abl_notrace #934, abl_tracescore #935 (each has only its body and a bot labelling comment). Host facts re-probed 2026-10-25: memory limit 32768 MB, cpu_limit 8, swap 0, oom.group 1 (an OOM restarts the pod), used 4%; /workspace 17 GB free, /tmp 170 GB free; unshare fails (ENOSYS); sandbox via devagent-bwrap (managed setting); Claude Code CLI 2.1.270; gh logged in as erezh16; main = 75b3bcd, template sha256 84de4f00... confirmed; no earlier AppWorld build on this pod. B0 done: worktree eval-abl from fork/eval-ce3 (--no-track, upstream fork/eval-abl), abl-main detached at 75b3bcd (clean), plan copied byte-identical, ~/bin/memcheck and ~/bin/memok-abl installed, memguard.py running (5 s, MEMSTATE fresh). Repair in B0: the shared ledger and resume scripts pushed to the hard-coded remote origin; they now use awrest.REMOTE (AW_REMOTE=fork in abl/env.sh), so nothing goes to skillberry-ai. User decision (2026-10-25, R1.4): this B0 session was not launched with exec-settings.json; it stops after B0 and the run continues in a new session launched with --settings /workspace/aw_abl/launch/exec-settings.json in /workspace/worktrees/eval-abl (deny rules also in its git-excluded .claude/settings.local.json). No sealed-set file exists yet (AppWorld is not built), so nothing could have been read. Orchestrating sessions so far: 12194466 (this one).

```json
{"cp": 0, "prev_cp": null, "prev_commit": "8ac42a2ac8bbf3f22e296a02eee70b4ddfac2e28", "utc": "2026-10-25T09:27:21Z", "kind": "decision", "phase": "P0", "done_through": "P1/B0", "next": "P1/B1 (relaunched session)", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "8ac42a2ac8bbf3f22e296a02eee70b4ddfac2e28", "open_decisions": [], "memory": {"used_pct": 4.36, "peak_pct": 4.39, "state": "OK", "stale": false}, "issues": {"abl_ref": 930, "abl_cc": 931, "abl_prompt": 932, "abl_tools": 933, "abl_notrace": 934, "abl_tracescore": 935}, "host": {"limit_MB": 32768, "cpu_limit": 8, "swap_max": 0, "oom_group": 1, "workspace_free_GB": 17, "tmp_free_GB": 170, "claude_cli": "2.1.270", "unshare": "ENOSYS"}, "sessions": ["12194466-3ee6-4d3d-afab-8ab8118a33cc"]}
```

## ABL-0001 · 2026-10-25T10:16Z · P0 executing worktree and deny rules · decision

User decision (2026-10-25), replacing the relaunch decision of ABL-0000: the orchestrating sessions run with /workspace/worktrees/base as their project folder (VS Code), not eval-abl, and not with --settings. The 40 deny rules of /workspace/aw_abl/launch/exec-settings.json were copied byte-identical into /workspace/worktrees/base/.claude/settings.local.json (git-excluded through the shared info/exclude; base git status clean). Verified live: a Read of a planted non-secret probe file (AW_STATE/cache/deny_probe.txt) was refused, and so was a shell rm of it (the Edit deny also covers shell writes); the user removes the probe by hand. Deviation from plan 6.1 ('do not touch base except to copy the plan'): one untracked, git-excluded settings file in base. All code, commits and pushes stay in the eval-abl worktree (absolute paths). The work continues in a new session in base (to keep this session's memory small); its id is appended to AW_SESSION_IDS in abl/env.sh. The rules cover file tools and are also enforced on shell commands here; the post-search scan of orchestrating transcripts stays mandatory. Open item: the hourly posts on #930 to #935 have not started (last post about 07:30 UTC); the next session starts autopost first and records it as an error entry.

```json
{"cp": 1, "prev_cp": 0, "prev_commit": "e8c5fd3b899c8a74eafec0e17d743684c2190a5a", "utc": "2026-10-25T10:16:21Z", "kind": "decision", "phase": "P0", "done_through": "P1/B0", "next": "P1/autopost then P1/B1 (new session in base)", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "8ac42a2ac8bbf3f22e296a02eee70b4ddfac2e28", "open_decisions": [], "memory": {"used_pct": 4.12, "peak_pct": 5.31, "state": "OK", "stale": false}}
```

## ABL-0002 · 2026-10-25T10:23Z · P1 hourly posts late · error

Hourly status posts on #930 to #935 are late (plan section 12): the last post on each issue is from about 07:30 UTC (issue bodies and a bot labelling comment), more than 60 minutes ago, because autopost was not started in B0 (CE3-0002 lesson not applied; open item of ABL-0001). Repair now: autopost.py and post.py adapted to the abl profile (six arms; abl_cc reports evaluations of 6 and no gate; no money or token cap; plan and ledger references point to docs/ABLATIONS.md); autopost loop and the heartbeat (60 s post-age and guard checks) are started next, and the first hourly status goes to all six issues at once. Session 5cbfcce5 added to AW_SESSION_IDS. Memory guard alive (5 s, OK, 4.7%).

```json
{"cp": 2, "prev_cp": 1, "prev_commit": "6363ce4c626abd8ec2f7db495b9c35d102d1d31d", "utc": "2026-10-25T10:23:42Z", "kind": "error", "phase": "P1", "done_through": "P1/B0", "next": "P1/autopost then P1/B1", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "6363ce4c626abd8ec2f7db495b9c35d102d1d31d", "open_decisions": [], "memory": {"used_pct": 4.73, "peak_pct": 5.31, "state": "OK", "stale": false}}
```

## ABL-0003 · 2026-10-25T10:23Z · P1 posted abl_ref · posted

Posted 'Cap-evolve full (reference) hourly status' on #930 (abl_ref): https://github.com/skillberry-ai/cap-evolve/issues/930#issuecomment-6396465620

```json
{"cp": 3, "prev_cp": 2, "prev_commit": "1db81db4428b041d1f027e9e19ef6defc18ceb98", "utc": "2026-10-25T10:23:55Z", "kind": "posted", "phase": "P1", "done_through": "P1/B0", "next": "P1/autopost then P1/B1", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "6363ce4c626abd8ec2f7db495b9c35d102d1d31d", "open_decisions": [], "memory": {"used_pct": 4.81, "peak_pct": 5.31, "state": "OK", "stale": false}, "post": "abl_ref/status_20261025T1023", "url": "https://github.com/skillberry-ai/cap-evolve/issues/930#issuecomment-6396465620"}
```

## ABL-0004 · 2026-10-25T10:23Z · P1 posted abl_cc · posted

Posted 'Claude code (plain Claude Code) hourly status' on #931 (abl_cc): https://github.com/skillberry-ai/cap-evolve/issues/931#issuecomment-6396465977

```json
{"cp": 4, "prev_cp": 3, "prev_commit": "ee85c35fb94737f616e9067dc9195f9eac0e3380", "utc": "2026-10-25T10:23:58Z", "kind": "posted", "phase": "P1", "done_through": "P1/B0", "next": "P1/autopost then P1/B1", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "6363ce4c626abd8ec2f7db495b9c35d102d1d31d", "open_decisions": [], "memory": {"used_pct": 4.81, "peak_pct": 5.31, "state": "OK", "stale": false}, "post": "abl_cc/status_20261025T1023", "url": "https://github.com/skillberry-ai/cap-evolve/issues/931#issuecomment-6396465977"}
```

## ABL-0005 · 2026-10-25T10:24Z · P1 posted abl_prompt · posted

Posted 'Cap evolve prompt only hourly status' on #932 (abl_prompt): https://github.com/skillberry-ai/cap-evolve/issues/932#issuecomment-6396466350

```json
{"cp": 5, "prev_cp": 4, "prev_commit": "52b1366aa38ec37e8b969c75931d4401e900d68f", "utc": "2026-10-25T10:24:00Z", "kind": "posted", "phase": "P1", "done_through": "P1/B0", "next": "P1/autopost then P1/B1", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "6363ce4c626abd8ec2f7db495b9c35d102d1d31d", "open_decisions": [], "memory": {"used_pct": 4.81, "peak_pct": 5.31, "state": "OK", "stale": false}, "post": "abl_prompt/status_20261025T1023", "url": "https://github.com/skillberry-ai/cap-evolve/issues/932#issuecomment-6396466350"}
```

## ABL-0006 · 2026-10-25T10:24Z · P1 posted abl_tools · posted

Posted 'Cap evolve tools only hourly status' on #933 (abl_tools): https://github.com/skillberry-ai/cap-evolve/issues/933#issuecomment-6396466695

```json
{"cp": 6, "prev_cp": 5, "prev_commit": "d6121b2fe33ccb51287b1a6fc68a7f82efd6e68c", "utc": "2026-10-25T10:24:02Z", "kind": "posted", "phase": "P1", "done_through": "P1/B0", "next": "P1/autopost then P1/B1", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "6363ce4c626abd8ec2f7db495b9c35d102d1d31d", "open_decisions": [], "memory": {"used_pct": 4.81, "peak_pct": 5.31, "state": "OK", "stale": false}, "post": "abl_tools/status_20261025T1024", "url": "https://github.com/skillberry-ai/cap-evolve/issues/933#issuecomment-6396466695"}
```

## ABL-0007 · 2026-10-25T10:24Z · P1 posted abl_notrace · posted

Posted 'Cap evolve no traces hourly status' on #934 (abl_notrace): https://github.com/skillberry-ai/cap-evolve/issues/934#issuecomment-6396467059

```json
{"cp": 7, "prev_cp": 6, "prev_commit": "4576027da4c321ce9421b39c822a03eadaf0557a", "utc": "2026-10-25T10:24:05Z", "kind": "posted", "phase": "P1", "done_through": "P1/B0", "next": "P1/autopost then P1/B1", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "6363ce4c626abd8ec2f7db495b9c35d102d1d31d", "open_decisions": [], "memory": {"used_pct": 4.81, "peak_pct": 5.31, "state": "OK", "stale": false}, "post": "abl_notrace/status_20261025T1024", "url": "https://github.com/skillberry-ai/cap-evolve/issues/934#issuecomment-6396467059"}
```

## ABL-0008 · 2026-10-25T10:24Z · P1 posted abl_tracescore · posted

Posted 'Cap evolve traces and score only hourly status' on #935 (abl_tracescore): https://github.com/skillberry-ai/cap-evolve/issues/935#issuecomment-6396467501

```json
{"cp": 8, "prev_cp": 7, "prev_commit": "14e94898f495dc0fc0ddf5b2a6a82e869641c458", "utc": "2026-10-25T10:24:07Z", "kind": "posted", "phase": "P1", "done_through": "P1/B0", "next": "P1/autopost then P1/B1", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "6363ce4c626abd8ec2f7db495b9c35d102d1d31d", "open_decisions": [], "memory": {"used_pct": 4.81, "peak_pct": 5.31, "state": "OK", "stale": false}, "post": "abl_tracescore/status_20261025T1024", "url": "https://github.com/skillberry-ai/cap-evolve/issues/935#issuecomment-6396467501"}
```

## ABL-0009 · 2026-10-25T10:27Z · P1 build B1 · result

B1 done. Profile scripts/awabl.py (AW_PROFILE=abl, loaded on top of CE3 and CE2): CANDIDATES abl_ref, abl_cc, abl_prompt, abl_tools, abl_notrace, abl_tracescore; ARMS = seed + those; ISSUES 930 to 935; METHOD_NAMES; CAPE_COMMIT 75b3bcd, CAPE_TREE /workspace/worktrees/abl-main; BUDGET_ROLLOUTS 882; BUDGET_OPT_TOKENS None (D12); K_SE 0.2 for the five cap-evolve arms, written with decimals. Verified unchanged: SEARCH_SEED_BASE 100, FINAL_SEED_BASE 5000, prices 2.00/10.00/0.20/2.50, OPT_MODEL aws/claude-sonnet-5-5, AGENT_MODEL openai/gpt-oss-120b-a100, slots 24/32, split counts 90/57/168/417, AppWorld 42b5bcf. abl/env.sh as plan B1 (plus AW_REMOTE=fork, ABL-0000; AW_SESSION_IDS now two sessions). Grep for hard-coded aw_rest, aw_ce2, aw_ce3, eval-ce2, eval-ce3, EVAL_APPWORLD_CE, ce2_k, ce3_k02, cape-impr2, 3db96a0, memok-ce, int(K): fixed in the shared code: common/sandbox.py (abl deny adds /workspace/aw_rest, aw_ce2, aw_ce3 and /tmp/aw_ce2, aw_ce3; transcript-dir tags for /workspace/aw_abl); scripts/scan.py (patterns add aw_rest, aw_ce2, aw_ce3 and every other arm root aw_abl/arms/<arm>); scripts/accept.py (A11 reads memok-abl); scripts/check_a10.py (throwaway branch acceptance/eval-abl-status-test, local bare remote only); scripts/analyze.py (the CE2 K2-K1 contrast now runs only under the CE2 profile); scripts/autopost.py and post.py (ABL-0002). The CE2 two-arm independence check is not used (no arms meant to be identical, CE3-0010): it lives in ce2/p4_ce2.py, which B5 replaces with abl/. Remaining hits are in ce2/ (driver, launcher, resume, report, seed_reuse, copy_caches, verify_build, VENDORED, yaml templates) and in the REST-era docs (common/API.md, docstrings): ce2/ is copied to abl/ in B5 and fixed there; seed_reuse.py is not used (fresh P3, D8). Verified the abl_ref deny list: AW_STATE, build roots, AppWorld, venvs, abl-main, all worktrees, the other five arm roots and their opt dirs, the arm own adapters dir, all earlier homes.

```json
{"cp": 9, "prev_cp": 8, "prev_commit": "6f6c5239a203e3451d060d7b8ce6727f9c2405a6", "utc": "2026-10-25T10:27:24Z", "kind": "result", "phase": "P1", "done_through": "P1/B1", "next": "P1/B2", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "6f6c5239a203e3451d060d7b8ce6727f9c2405a6", "open_decisions": [], "memory": {"used_pct": 4.68, "peak_pct": 5.31, "state": "OK", "stale": false}}
```

## ABL-0010 · 2026-10-25T10:33Z · P1 build B2 B3 B4 · result

B2 to B4 done, fresh build under /workspace/aw_abl/build (no symlinks, no earlier build). B2: AppWorld cloned at 42b5bcf with git lfs and the extra-headers patch (git diff sha256 755de8b8..., equal to REST manifest); venv-aw (Python 3.11, uv): CPU torch, -e appworld, -e appworld/experiments[simplified], pydantic 2.12.5, fastapi 0.143.0, tiktoken, anthropic, and -e abl-main/core (the code under test; the eval branch core and gepa are not installed, gepa has no arm here), 122 packages; appworld install --repo. B3: data downloaded into root_full; split counts 90/57/168/417, scenarios 30/19/56/139, difficulties as the base plan, splits pairwise disjoint, train and dev share no scenario; split-file sha256 and data tree sha256 cf0e28f5... all equal to REST manifest; publishing cache 732 ids, 1,528 8-grams, 249 contacts. B4: root_opt 148 task dirs (train + dev + _base_), only train.txt/dev.txt, 0 test-id hits; lint cache and reference dir built; root_full chmod 000. B3 (plan numbering) venv-abl = venv-aw freeze reinstalled (CPU torch index), freeze byte-equal to venv-aw (122 packages, sha256 a4a2c98d...), its only editable core is /workspace/worktrees/abl-main/core, cap_evolve imports from there, cap-evolve CLI present; abl-main still clean at 75b3bcd. New abl/verify_build.py (trusted, read-only, from CE2 verify_build without the REST symlink and manifest checks, plus venv-abl core pin) PASS: no symlinks in AW_BUILD, AppWorld head, diff and patch hashes, both venvs fastapi 0.143.0 / pydantic 2.12.5, all split counts, scenarios, difficulties and hashes, root_opt 148/0 hits, root_full 000 before and after, caches present. /workspace 14 GB free. Note: a listing of root_opt task dirs was refused by the session deny rules, as intended; only the build script counts read task files.

```json
{"cp": 10, "prev_cp": 9, "prev_commit": "03dfcfb9c1cba58e624e40bab1fa5e77b02c4be9", "utc": "2026-10-25T10:33:14Z", "kind": "result", "phase": "P1", "done_through": "P1/B4", "next": "P1/B5", "arm": null, "counts": {}, "spend": {}, "artifacts": {"STATE/manifest.json": "6ea0fda0127aa8542f8346f92fec041f610991cd7cfc953e226dba542437aed6", "local/build_check.json": "cf8a3f178834baec40f1cc239ac6f1d2a418acc78d5f62c7fe1eaecc58ad53a2"}, "code": "03dfcfb9c1cba58e624e40bab1fa5e77b02c4be9", "open_decisions": [], "memory": {"used_pct": 4.8, "peak_pct": 5.46, "state": "OK", "stale": false}}
```

## ABL-0011 · 2026-10-25T10:38Z · P1 build B5.1 feedback filter · result

B5 piece 1 done: the feedback filter (plan 9.7). abl/feedback_filter.py, a pure function selected by AW_ABL_FEEDBACK (full | eval_only | trace_score; unset = full; any other value raises at import). abl/adapter.py = CE2 adapter plus the filter on every Rollout returned by run_trials (fresh records and cache hits alike) and on every Score (score() = the shared F1 score of the filtered rollout, then the filter). Checked in the code under test (75b3bcd harness): every proposer-visible rollout file is json of input, rollout.to_dict() and score.to_dict(), and FAILURES/ledger text comes from score.feedback, so filtering these two objects covers the derived files. eval_only: trace [], output = termination, metadata and feedback unchanged. trace_score: trace kept, metadata only termination, n_steps, complete_task_called, api_errors, tokens, success, seed, cost_source, cache_hit; feedback Task reward: 0|1; raw {}. Reward and metrics never change. Lint-reject and not-measured rollouts keep their text in every mode. Unit tests (abl/tests/test_feedback_filter.py, venv-abl, synthetic records only, the real shared Adapter.score): 7/7 pass, including full byte-identical to the shared adapter output, no removed-field string in eval_only/trace_score serializations, unknown value raises, input not mutated.

```json
{"cp": 11, "prev_cp": 10, "prev_commit": "d472197dea03facebc1f85b859e35320b3ef6d56", "utc": "2026-10-25T10:38:41Z", "kind": "result", "phase": "P1", "done_through": "P1/B5.1", "next": "P1/B5.2", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "d472197dea03facebc1f85b859e35320b3ef6d56", "open_decisions": [], "memory": {"used_pct": 4.79, "peak_pct": 5.46, "state": "OK", "stale": false}}
```

## ABL-0012 · 2026-10-25T11:04Z · P1 heartbeat · heartbeat

No checkpoint for 25 min. Phase P1, last result: P1/B5.1.
Runner: no runner. Last log line: `2026-10-25T11:03:38Z | memguard | - | sample 1.93% (631 MB) state OK peak 5.5%`.
Next: P1/B5.2.

```json
{"cp": 12, "prev_cp": 11, "prev_commit": "542b0430d4438481aedbc980c2280fb804abcb3f", "utc": "2026-10-25T11:04:19Z", "kind": "heartbeat", "phase": "P1", "done_through": "P1/B5.1", "next": "P1/B5.2", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "d472197dea03facebc1f85b859e35320b3ef6d56", "open_decisions": [], "memory": {"used_pct": 1.93, "peak_pct": 5.46, "state": "OK", "stale": false}, "runner": "none"}
```

## ABL-0013 · 2026-10-25T11:23Z · P1 posted abl_ref · posted

Posted 'Cap-evolve full (reference) hourly status' on #930 (abl_ref): https://github.com/skillberry-ai/cap-evolve/issues/930#issuecomment-6397010024

```json
{"cp": 13, "prev_cp": 12, "prev_commit": "8f2268f5677f70aa98d30f427118a2a347026f03", "utc": "2026-10-25T11:23:20Z", "kind": "posted", "phase": "P1", "done_through": "P1/B5.1", "next": "P1/B5.2", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "d472197dea03facebc1f85b859e35320b3ef6d56", "open_decisions": [], "memory": {"used_pct": 1.99, "peak_pct": 5.46, "state": "OK", "stale": false}, "post": "abl_ref/status_20261025T1123", "url": "https://github.com/skillberry-ai/cap-evolve/issues/930#issuecomment-6397010024"}
```

## ABL-0014 · 2026-10-25T11:23Z · P1 posted abl_cc · posted

Posted 'Claude code (plain Claude Code) hourly status' on #931 (abl_cc): https://github.com/skillberry-ai/cap-evolve/issues/931#issuecomment-6397010410

```json
{"cp": 14, "prev_cp": 13, "prev_commit": "64ab82aec47b6d6984cc1ccef0e14d51fe253603", "utc": "2026-10-25T11:23:22Z", "kind": "posted", "phase": "P1", "done_through": "P1/B5.1", "next": "P1/B5.2", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "d472197dea03facebc1f85b859e35320b3ef6d56", "open_decisions": [], "memory": {"used_pct": 1.99, "peak_pct": 5.46, "state": "OK", "stale": false}, "post": "abl_cc/status_20261025T1123", "url": "https://github.com/skillberry-ai/cap-evolve/issues/931#issuecomment-6397010410"}
```

## ABL-0015 · 2026-10-25T11:23Z · P1 posted abl_prompt · posted

Posted 'Cap evolve prompt only hourly status' on #932 (abl_prompt): https://github.com/skillberry-ai/cap-evolve/issues/932#issuecomment-6397010799

```json
{"cp": 15, "prev_cp": 14, "prev_commit": "bce12632ecc042d67136d2b798491bc818e1822b", "utc": "2026-10-25T11:23:24Z", "kind": "posted", "phase": "P1", "done_through": "P1/B5.1", "next": "P1/B5.2", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "d472197dea03facebc1f85b859e35320b3ef6d56", "open_decisions": [], "memory": {"used_pct": 1.99, "peak_pct": 5.46, "state": "OK", "stale": false}, "post": "abl_prompt/status_20261025T1123", "url": "https://github.com/skillberry-ai/cap-evolve/issues/932#issuecomment-6397010799"}
```

## ABL-0016 · 2026-10-25T11:23Z · P1 posted abl_tools · posted

Posted 'Cap evolve tools only hourly status' on #933 (abl_tools): https://github.com/skillberry-ai/cap-evolve/issues/933#issuecomment-6397011192

```json
{"cp": 16, "prev_cp": 15, "prev_commit": "0501888ff57ca54ff1e07e4403cbd9543f811ea4", "utc": "2026-10-25T11:23:27Z", "kind": "posted", "phase": "P1", "done_through": "P1/B5.1", "next": "P1/B5.2", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "d472197dea03facebc1f85b859e35320b3ef6d56", "open_decisions": [], "memory": {"used_pct": 1.99, "peak_pct": 5.46, "state": "OK", "stale": false}, "post": "abl_tools/status_20261025T1123", "url": "https://github.com/skillberry-ai/cap-evolve/issues/933#issuecomment-6397011192"}
```

## ABL-0017 · 2026-10-25T11:23Z · P1 posted abl_notrace · posted

Posted 'Cap evolve no traces hourly status' on #934 (abl_notrace): https://github.com/skillberry-ai/cap-evolve/issues/934#issuecomment-6397011573

```json
{"cp": 17, "prev_cp": 16, "prev_commit": "8e631399c924c19e6315446fe64fdbfe38c124a6", "utc": "2026-10-25T11:23:29Z", "kind": "posted", "phase": "P1", "done_through": "P1/B5.1", "next": "P1/B5.2", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "d472197dea03facebc1f85b859e35320b3ef6d56", "open_decisions": [], "memory": {"used_pct": 1.99, "peak_pct": 5.46, "state": "OK", "stale": false}, "post": "abl_notrace/status_20261025T1123", "url": "https://github.com/skillberry-ai/cap-evolve/issues/934#issuecomment-6397011573"}
```

## ABL-0018 · 2026-10-25T11:23Z · P1 posted abl_tracescore · posted

Posted 'Cap evolve traces and score only hourly status' on #935 (abl_tracescore): https://github.com/skillberry-ai/cap-evolve/issues/935#issuecomment-6397011970

```json
{"cp": 18, "prev_cp": 17, "prev_commit": "28ed719e272760142084ed332ccde04c6f2dce12", "utc": "2026-10-25T11:23:32Z", "kind": "posted", "phase": "P1", "done_through": "P1/B5.1", "next": "P1/B5.2", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "d472197dea03facebc1f85b859e35320b3ef6d56", "open_decisions": [], "memory": {"used_pct": 1.94, "peak_pct": 5.46, "state": "OK", "stale": false}, "post": "abl_tracescore/status_20261025T1123", "url": "https://github.com/skillberry-ai/cap-evolve/issues/935#issuecomment-6397011970"}
```

## ABL-0019 · 2026-10-25T11:49Z · P1 heartbeat · heartbeat

No checkpoint for 25 min. Phase P1, last result: P1/B5.1.
Runner: no runner. Last log line: `2026-10-25T11:48:41Z | memguard | - | sample 1.93% (633 MB) state OK peak 5.5%`.
Next: P1/B5.2.

```json
{"cp": 19, "prev_cp": 18, "prev_commit": "a7d056fcbe1c2c9db544a5b5c300f23025011acd", "utc": "2026-10-25T11:49:20Z", "kind": "heartbeat", "phase": "P1", "done_through": "P1/B5.1", "next": "P1/B5.2", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "d472197dea03facebc1f85b859e35320b3ef6d56", "open_decisions": [], "memory": {"used_pct": 1.93, "peak_pct": 5.46, "state": "OK", "stale": false}, "runner": "none"}
```

## ABL-0020 · 2026-10-25T12:14Z · P1 heartbeat · heartbeat

No checkpoint for 25 min. Phase P1, last result: P1/B5.1.
Runner: no runner. Last log line: `2026-10-25T12:13:44Z | memguard | - | sample 4.93% (1614 MB) state OK peak 6.2%`.
Next: P1/B5.2.

```json
{"cp": 20, "prev_cp": 19, "prev_commit": "3ba978c5ae45e4c34ccd1f04a27a2ae9e0cfbe4b", "utc": "2026-10-25T12:14:22Z", "kind": "heartbeat", "phase": "P1", "done_through": "P1/B5.1", "next": "P1/B5.2", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "d472197dea03facebc1f85b859e35320b3ef6d56", "open_decisions": [], "memory": {"used_pct": 4.86, "peak_pct": 6.18, "state": "OK", "stale": false}, "runner": "none"}
```

## ABL-0021 · 2026-10-25T12:22Z · P1 posted abl_ref · posted

Posted 'Cap-evolve full (reference) hourly status' on #930 (abl_ref): https://github.com/skillberry-ai/cap-evolve/issues/930#issuecomment-6397579835

```json
{"cp": 21, "prev_cp": 20, "prev_commit": "03e3092b1d029105fd299911d178b09a597d4036", "utc": "2026-10-25T12:22:35Z", "kind": "posted", "phase": "P1", "done_through": "P1/B5.1", "next": "P1/B5.2", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "d472197dea03facebc1f85b859e35320b3ef6d56", "open_decisions": [], "memory": {"used_pct": 4.93, "peak_pct": 6.18, "state": "OK", "stale": false}, "post": "abl_ref/status_20261025T1222", "url": "https://github.com/skillberry-ai/cap-evolve/issues/930#issuecomment-6397579835"}
```

## ABL-0022 · 2026-10-25T12:22Z · P1 posted abl_cc · posted

Posted 'Claude code (plain Claude Code) hourly status' on #931 (abl_cc): https://github.com/skillberry-ai/cap-evolve/issues/931#issuecomment-6397580236

```json
{"cp": 22, "prev_cp": 21, "prev_commit": "6fb5225af6479dd9c16c1b68658c15b9a3be3d35", "utc": "2026-10-25T12:22:37Z", "kind": "posted", "phase": "P1", "done_through": "P1/B5.1", "next": "P1/B5.2", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "d472197dea03facebc1f85b859e35320b3ef6d56", "open_decisions": [], "memory": {"used_pct": 4.93, "peak_pct": 6.18, "state": "OK", "stale": false}, "post": "abl_cc/status_20261025T1222", "url": "https://github.com/skillberry-ai/cap-evolve/issues/931#issuecomment-6397580236"}
```

## ABL-0023 · 2026-10-25T12:22Z · P1 posted abl_prompt · posted

Posted 'Cap evolve prompt only hourly status' on #932 (abl_prompt): https://github.com/skillberry-ai/cap-evolve/issues/932#issuecomment-6397580614

```json
{"cp": 23, "prev_cp": 22, "prev_commit": "848a42388bc1fba58bbcacd8892fe49ed1bd69f8", "utc": "2026-10-25T12:22:39Z", "kind": "posted", "phase": "P1", "done_through": "P1/B5.1", "next": "P1/B5.2", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "d472197dea03facebc1f85b859e35320b3ef6d56", "open_decisions": [], "memory": {"used_pct": 4.93, "peak_pct": 6.18, "state": "OK", "stale": false}, "post": "abl_prompt/status_20261025T1222", "url": "https://github.com/skillberry-ai/cap-evolve/issues/932#issuecomment-6397580614"}
```

## ABL-0024 · 2026-10-25T12:22Z · P1 posted abl_tools · posted

Posted 'Cap evolve tools only hourly status' on #933 (abl_tools): https://github.com/skillberry-ai/cap-evolve/issues/933#issuecomment-6397580993

```json
{"cp": 24, "prev_cp": 23, "prev_commit": "ebf2b8158ece2bbe6e35a35252625d436ae05267", "utc": "2026-10-25T12:22:42Z", "kind": "posted", "phase": "P1", "done_through": "P1/B5.1", "next": "P1/B5.2", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "d472197dea03facebc1f85b859e35320b3ef6d56", "open_decisions": [], "memory": {"used_pct": 4.93, "peak_pct": 6.18, "state": "OK", "stale": false}, "post": "abl_tools/status_20261025T1222", "url": "https://github.com/skillberry-ai/cap-evolve/issues/933#issuecomment-6397580993"}
```

## ABL-0025 · 2026-10-25T12:22Z · P1 posted abl_notrace · posted

Posted 'Cap evolve no traces hourly status' on #934 (abl_notrace): https://github.com/skillberry-ai/cap-evolve/issues/934#issuecomment-6397581385

```json
{"cp": 25, "prev_cp": 24, "prev_commit": "4d5d13f4cb28c0f48e033926150f7b504d70311a", "utc": "2026-10-25T12:22:44Z", "kind": "posted", "phase": "P1", "done_through": "P1/B5.1", "next": "P1/B5.2", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "d472197dea03facebc1f85b859e35320b3ef6d56", "open_decisions": [], "memory": {"used_pct": 4.93, "peak_pct": 6.18, "state": "OK", "stale": false}, "post": "abl_notrace/status_20261025T1222", "url": "https://github.com/skillberry-ai/cap-evolve/issues/934#issuecomment-6397581385"}
```

## ABL-0026 · 2026-10-25T12:22Z · P1 posted abl_tracescore · posted

Posted 'Cap evolve traces and score only hourly status' on #935 (abl_tracescore): https://github.com/skillberry-ai/cap-evolve/issues/935#issuecomment-6397581765

```json
{"cp": 26, "prev_cp": 25, "prev_commit": "80244804d63c2a0b3d4bfebd70b32b46d880e0ff", "utc": "2026-10-25T12:22:47Z", "kind": "posted", "phase": "P1", "done_through": "P1/B5.1", "next": "P1/B5.2", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "d472197dea03facebc1f85b859e35320b3ef6d56", "open_decisions": [], "memory": {"used_pct": 4.88, "peak_pct": 6.18, "state": "OK", "stale": false}, "post": "abl_tracescore/status_20261025T1222", "url": "https://github.com/skillberry-ai/cap-evolve/issues/935#issuecomment-6397581765"}
```

## ABL-0027 · 2026-10-25T12:36Z · P1 build B5.2 tools lint · result

B5 piece 2 done: the tools-only anti-smuggling lint (plan 10.4) in adapters/lints.py, active only with AW_ABL_TOOLS_LINT=1 (unset = the reference lint, unchanged: the 15 existing offline tests pass). It rejects a helper whose return value is more than 200 characters of fixed literal text: a string literal, the literal parts of an f-string, + or % of literals, a literal join over a list or tuple of literals, .format/.strip of a literal, or a module-level or local string constant returned by name. Docstrings and api_notes are not rejected (they are the tools surface). Design point for fairness: the evaluator cache is keyed by candidate tree only, so a tree first scored by another arm could otherwise be served to abl_tools without its lint; with the switch on, common/evaluator.py now runs the lint before the cache lookup (a reject costs 0 rollouts, logged in lint_rejects.jsonl). For every other arm the evaluator path is unchanged. Tests abl/tests/test_tools_lint.py (synthetic helpers): literal, f-string, join, concat, module and local constants rejected; a normal paged helper with a long docstring passes; threshold 200 passes, 201 rejected; off without the switch. 12/12 abl tests pass.

```json
{"cp": 27, "prev_cp": 26, "prev_commit": "b1c5cc0c3b386c13b69131f45d7fb1183b59568d", "utc": "2026-10-25T12:36:57Z", "kind": "result", "phase": "P1", "done_through": "P1/B5.2", "next": "P1/B5.3", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "b1c5cc0c3b386c13b69131f45d7fb1183b59568d", "open_decisions": [], "memory": {"used_pct": 2.92, "peak_pct": 6.18, "state": "OK", "stale": false}}
```

## ABL-0028 · 2026-10-25T12:41Z · P1 build B5.3 instructions · result

B5 piece 3 done: the optimizer instructions (plan 9.4, 10.3 to 10.6). abl/INSTRUCTIONS.base.md = byte copy of abl-main templates/project/optimizer/INSTRUCTIONS.md (sha256 84de4f00..., equal to the 3db96a0 template; abl/VENDORED.md). abl/facts_ref.md = CE2 block ## AppWorld facts for THIS run, from the objective-score paragraph to the lint command, unchanged (sha256 8a7b9ce9...). abl/instructions.py renders one file per cap-evolve arm with the facts section inserted once immediately before ## PREPARATION:, every placeholder and template sentence unchanged; each ablation replaces only the spans its plan section names, each required to occur exactly once. Stored in docs/ABLATION_STATUS_STATE/abl/: the five INSTRUCTIONS.<arm>.md and diffs. diff base vs arm: insertions only for all five (ref +35, prompt +24, tools +33, notrace +36, tracescore +35, 0 removed). diff abl_ref vs arm: abl_prompt only the file-list head and bullets (keeps the policy bullet unchanged, adds the tools/memory read-only sentence); abl_tools only the list (drops the policy bullet, keeps helpers and notes bullets, adds the read-only and literal-text sentences); abl_notrace only the trajectories sentence; abl_tracescore only the partial-passes sentence and the trajectories sentence. The section names no K, arm, earlier evaluation or result. The lint placeholders {AW_LINT_*} are filled at setup. Rendered sha256 prefixes: ref 220d3ea7, prompt 21c0efa7, tools eed16b6d, notrace 838f753b, tracescore 861283ea.

```json
{"cp": 28, "prev_cp": 27, "prev_commit": "6ad7746572a5cf8dc633db443c1b09839fa7e12d", "utc": "2026-10-25T12:41:54Z", "kind": "result", "phase": "P1", "done_through": "P1/B5.3", "next": "P1/B5.4", "arm": null, "counts": {}, "spend": {}, "artifacts": {"STATE/abl/INSTRUCTIONS.abl_ref.md": "220d3ea7f9c9eb72b26ae6a753ae055e02f767883f3ae4dddd4bf48af276ce14"}, "code": "6ad7746572a5cf8dc633db443c1b09839fa7e12d", "open_decisions": [], "memory": {"used_pct": 2.12, "peak_pct": 6.18, "state": "OK", "stale": false}}
```

## ABL-0029 · 2026-10-25T12:56Z · P1 build B5.4-B5.6 · result

B5 pieces 4 to 6 done. (4) Per-arm specs: abl/capevolve.yaml = plan 9.3 with @CAPABILITIES@, @PROTECTED@, @K_SE@ filled by abl/run_abl.py from one table ARM_CONFIG (the only per-arm differences: capabilities, protected_paths, the arm INSTRUCTIONS file, AW_ABL_FEEDBACK, AW_ABL_TOOLS_LINT). run_abl.py = CE2 run_ce2.py on venv-abl and abl-main, with: no inherited CAPEVOLVE_*/AW_ABL_* variables; the arm switches in every cap-evolve command; IMP launch checks 1-3 plus a switch check (spec capabilities/protected_paths and the env switches); voided (tamper / capability_invalid) steps counted as consumed iterations; gate unit check at K = 0.2; A-ABL-SAME. abl/launch_abl.sh (plan 9.2 steps 1-9; pid file) and abl/sandbox_cc/claude (CE2 shim with memok-abl, no token cap). The five projects are scaffolded with the pinned intake script; cap-evolve check ok for all five; IMP launch checks pass for all five (core abl-main, skills dir abl-main/skills not ~/.claude/skills, gate_k_se 0.2, switches), and a wrong switch is refused (exit 1). A-ABL-SAME PASS: vs abl_ref, abl_prompt and abl_tools differ only in capabilities and protected_paths (abl_tools also AW_ABL_TOOLS_LINT), abl_notrace and abl_tracescore only in AW_ABL_FEEDBACK; every INSTRUCTIONS difference equals the arm facts sentences. (5) abl_cc: abl/cc/PROMPT.txt = the plan three lines byte-for-byte (sha256 12e145ec...); evald.py (trusted daemon: strict relative-path resolve, no symlinks, regular files under 1 MB, staging copy, the fixed 147 ids, B = 882 checked before a run, lint reject free, cache hits free, reference-format trajectories through abl/adapter.py with feedback full, evals.jsonl log; a dry mode on 4 dev ids in the accept namespace with B = 8); eval_candidate / eval_status touch only ./.eval/; run_cc.py (workdir: seed surfaces, the two reference docs, the scripts, git init; config-dir and prompt-hash check; freeze per 10.2; progress); launch_cc.sh (refuses a second session: no re-prompting; daemon pid file; the shim; CLAUDE_CONFIG_DIR empty; --max-turns 1200). abl_cc deny list: the five other arm roots and their opt dirs, not its own work or config dir. (6) abl/reset_check.py (plan 9.8 items 1-6; reference renders stored, to be refreshed at abl_ref launch); dry run PASS on abl_prompt; with a switch set it fails item 3. Offline tests: 17/17 abl tests (filter, tools lint, evald refusals: absolute path, .., symlink out, symlinked surface, extra keys, bad JSON) and the 15 shared tests pass.

```json
{"cp": 29, "prev_cp": 28, "prev_commit": "1b583d5ea77378b00b20f17909424076985c3343", "utc": "2026-10-25T12:56:03Z", "kind": "result", "phase": "P1", "done_through": "P1/B5.6", "next": "P1/B5.7 (p4, report, resume), then P2", "arm": null, "counts": {}, "spend": {}, "artifacts": {"STATE/abl/same.json": "5d9499fb1c10fb2fb446ac3c0bbb177e80dd464a58325874356df140a4b6d6d2"}, "code": "1b583d5ea77378b00b20f17909424076985c3343", "open_decisions": [], "memory": {"used_pct": 2.15, "peak_pct": 6.18, "state": "OK", "stale": false}}
```

## ABL-0030 · 2026-10-25T13:02Z · P1 build done · phase_done

B5 piece 7 and P1 done. abl/p4_abl.py (CE2 P4 runner with: waves abl_ref + abl_prompt + abl_tools launched in one pass, then abl_notrace, abl_tracescore, abl_cc as slots free, at most 3 chains at once; each chain search -> freeze -> isolation scan -> reset check; abl_cc chain = launch_cc.sh, run_cc.py freeze; per-iteration (or per-evaluation for abl_cc) result entries and posts; voided steps reported as such; no two-arm independence check (CE3-0010); R2 escalation stops the most recently started cap-evolve chain, never abl_cc; a restart cap MAX_RUNNING). abl/after_p4.py (P5-P9; P6 also runs reset_check for every arm and gates on it; J1/K gate only for cap-evolve arms). scripts/analyze.py: for the abl profile, the five primary contrasts each ablation - abl_ref with the same scenario-clustered paired bootstrap CI plus a two-sided bootstrap p (raw) and Holm-adjusted p over the five, and the secondary pairs abl_prompt - abl_tools and abl_notrace - abl_tracescore (Holm verified on a hand example); the cross-window text now keys on reused arms only. abl/report_abl.py (plan 15 report: setup, activation lines, main table vs abl_ref and seed with raw/Holm p, all-arms table, difficulty, test cost, search rows, artifact, isolation and reset, deviations, limits). scripts/scan.py: abl_cc locations (workdir incl. the .eval spool, config dir transcripts, archive, artifact) and the J1/K re-check via run_abl.py with the arm switches. scripts/window.py: final order seed 2026102507 (plan 15: 20261025 + the fixed suffix). abl/resume_abl.py (plan 13.4: pid refusal, restart detection with -25% slots and one search fewer, verify_build, abl_cc no re-prompt with an error entry and a user question, loops restarted, phase runner); dry run ok. Tests: 17/17 abl, 15/15 shared.

```json
{"cp": 30, "prev_cp": 29, "prev_commit": "56d60296cdde2385949a689621722d39129bdf24", "utc": "2026-10-25T13:02:42Z", "kind": "phase_done", "phase": "P1", "done_through": "P1/B5", "next": "P2/acceptance", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "56d60296cdde2385949a689621722d39129bdf24", "open_decisions": [], "memory": {"used_pct": 2.13, "peak_pct": 6.18, "state": "OK", "stale": false}}
```

## ABL-0031 · 2026-10-25T13:08Z · P2 acceptance A1-A7 A12 · result

Acceptance (none counted, phase accept): A1 PASS (gateway via opt_llm, JSON reply parses; claude CLI exit 0, modelUsage only aws/claude-sonnet-5-5). A2 PASS (RITS max_model_len 40,144; 48/48 concurrent 200, 0 x 429, 12.6 s; 1 dev episode completed through the patched client, 6 steps; RITS key hits 0). A3/A5 PASS (import os, open(answer.json) and a pathlib read fail in the REPL; root_opt has no test data; split_ids train = val = train u dev (147), test = []; the released train solution, run by the trusted script, scores 1 and its output is not printed (R1); a no-op scores 0; scoring twice identical; no failure trace or gold persisted; root_full relocked). A4 PASS (seed first request byte-identical to stock, 23 messages; memory slot placement; helpers and notes with the doc text unchanged; a lint-violating helper rejected without a rollout). A6 PASS (train order = load_task_ids, 90; an outside id and the test split refused). A7 PASS (final order 168 x 7 arms x 2 trials = 2,352 cells, reproducible from seed 2026102507, sha256 in manifest; dev order = file order; root_full relocked). A12 PASS (episode, chat and claude -p usage records carry every 5.2 field; CLI model aws/claude-sonnet-5-5; 1M in + 1M out + 1M cache read = USD 12.20). Repairs on the way: opt_llm treated the disabled token cap (None, D12) as a number (A1/A12 TypeError, no call made): None now means no cap; A5.1 printed the start of the solution output into the check log: it now prints the reward only.

```json
{"cp": 31, "prev_cp": 30, "prev_commit": "023acd8b066d7ca9432faf89902766b4ab0b4a92", "utc": "2026-10-25T13:08:19Z", "kind": "result", "phase": "P2", "done_through": "P2/A12", "next": "P2/A8 A10 A11 A13 A9 A-ABL", "arm": null, "counts": {}, "spend": {}, "artifacts": {"local/acceptance/a7.json": "f678330dca1ef0833757b1f028fff9e30eb46ddfe15352bc712cc239a34f0195"}, "code": "023acd8b066d7ca9432faf89902766b4ab0b4a92", "open_decisions": [], "memory": {"used_pct": 2.15, "peak_pct": 6.18, "state": "OK", "stale": false}}
```

## ABL-0032 · 2026-10-25T13:20Z · P2 acceptance A8 A11 · result

A8 PASS (10 dev episodes: max prompt 12,767 tokens < 34K; H_max 16,910, P_max 3,230, M_cap 13,500 tokens / 30,000 chars; 3 dev episodes with a maximal memory block stayed under 13.3K prompt tokens, tiktoken = vLLM; 0 infra). Memory is sealed in this run (D13), so M_cap only bounds the lint. A11 PASS on the second run (guard period 5 s; PAUSE within 4.5 s of crossing; no episode slot and no optimizer call start while paused; resume only below the low mark; transitions logged). The first run failed only its last item, spawn_check_reads_memstate: ~/bin/memok-abl worked but did not name the file it reads, which the check looks for; memok-abl now prints its MEMSTATE path (behaviour unchanged). None counted.

```json
{"cp": 32, "prev_cp": 31, "prev_commit": "b119f645f7169370e5dd6b11dcdefe64874a6869", "utc": "2026-10-25T13:20:49Z", "kind": "result", "phase": "P2", "done_through": "P2/A11", "next": "P2/A10 A13 A9 A-ABL", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "b119f645f7169370e5dd6b11dcdefe64874a6869", "open_decisions": [], "memory": {"used_pct": 7.36, "peak_pct": 23.21, "state": "OK", "stale": false}}
```

## ABL-0033 · 2026-10-25T13:21Z · P2 posted abl_ref · posted

Posted 'Cap-evolve full (reference) hourly status' on #930 (abl_ref): https://github.com/skillberry-ai/cap-evolve/issues/930#issuecomment-6398175506

```json
{"cp": 33, "prev_cp": 32, "prev_commit": "c0e7b009cff10e8c2fbbbec8298e723e2a53e370", "utc": "2026-10-25T13:21:49Z", "kind": "posted", "phase": "P2", "done_through": "P2/A11", "next": "P2/A10 A13 A9 A-ABL", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "b119f645f7169370e5dd6b11dcdefe64874a6869", "open_decisions": [], "memory": {"used_pct": 7.39, "peak_pct": 23.21, "state": "OK", "stale": false}, "post": "abl_ref/status_20261025T1321", "url": "https://github.com/skillberry-ai/cap-evolve/issues/930#issuecomment-6398175506"}
```

## ABL-0034 · 2026-10-25T13:21Z · P2 posted abl_cc · posted

Posted 'Claude code (plain Claude Code) hourly status' on #931 (abl_cc): https://github.com/skillberry-ai/cap-evolve/issues/931#issuecomment-6398175919

```json
{"cp": 34, "prev_cp": 33, "prev_commit": "dfd0e7a366ce04f3ed4c0670a26a62fc33aad25b", "utc": "2026-10-25T13:21:52Z", "kind": "posted", "phase": "P2", "done_through": "P2/A11", "next": "P2/A10 A13 A9 A-ABL", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "dfd0e7a366ce04f3ed4c0670a26a62fc33aad25b", "open_decisions": [], "memory": {"used_pct": 7.39, "peak_pct": 23.21, "state": "OK", "stale": false}, "post": "abl_cc/status_20261025T1321", "url": "https://github.com/skillberry-ai/cap-evolve/issues/931#issuecomment-6398175919"}
```

## ABL-0035 · 2026-10-25T13:21Z · P2 posted abl_prompt · posted

Posted 'Cap evolve prompt only hourly status' on #932 (abl_prompt): https://github.com/skillberry-ai/cap-evolve/issues/932#issuecomment-6398176342

```json
{"cp": 35, "prev_cp": 34, "prev_commit": "3b719bfa2cdbf005e38c6876411fcf01a032b6df", "utc": "2026-10-25T13:21:54Z", "kind": "posted", "phase": "P2", "done_through": "P2/A11", "next": "P2/A10 A13 A9 A-ABL", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "dfd0e7a366ce04f3ed4c0670a26a62fc33aad25b", "open_decisions": [], "memory": {"used_pct": 7.39, "peak_pct": 23.21, "state": "OK", "stale": false}, "post": "abl_prompt/status_20261025T1321", "url": "https://github.com/skillberry-ai/cap-evolve/issues/932#issuecomment-6398176342"}
```

## ABL-0036 · 2026-10-25T13:21Z · P2 posted abl_tools · posted

Posted 'Cap evolve tools only hourly status' on #933 (abl_tools): https://github.com/skillberry-ai/cap-evolve/issues/933#issuecomment-6398176748

```json
{"cp": 36, "prev_cp": 35, "prev_commit": "b1d9b35340426fae3a7862184fd7b72a9c4a02d9", "utc": "2026-10-25T13:21:56Z", "kind": "posted", "phase": "P2", "done_through": "P2/A11", "next": "P2/A10 A13 A9 A-ABL", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "dfd0e7a366ce04f3ed4c0670a26a62fc33aad25b", "open_decisions": [], "memory": {"used_pct": 7.37, "peak_pct": 23.21, "state": "OK", "stale": false}, "post": "abl_tools/status_20261025T1321", "url": "https://github.com/skillberry-ai/cap-evolve/issues/933#issuecomment-6398176748"}
```

## ABL-0037 · 2026-10-25T13:21Z · P2 posted abl_notrace · posted

Posted 'Cap evolve no traces hourly status' on #934 (abl_notrace): https://github.com/skillberry-ai/cap-evolve/issues/934#issuecomment-6398177192

```json
{"cp": 37, "prev_cp": 36, "prev_commit": "a05f5f637d437f227e1ec9dbc3dae158116d3ba0", "utc": "2026-10-25T13:21:59Z", "kind": "posted", "phase": "P2", "done_through": "P2/A11", "next": "P2/A10 A13 A9 A-ABL", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "dfd0e7a366ce04f3ed4c0670a26a62fc33aad25b", "open_decisions": [], "memory": {"used_pct": 7.37, "peak_pct": 23.21, "state": "OK", "stale": false}, "post": "abl_notrace/status_20261025T1321", "url": "https://github.com/skillberry-ai/cap-evolve/issues/934#issuecomment-6398177192"}
```

## ABL-0038 · 2026-10-25T13:22Z · P2 posted abl_tracescore · posted

Posted 'Cap evolve traces and score only hourly status' on #935 (abl_tracescore): https://github.com/skillberry-ai/cap-evolve/issues/935#issuecomment-6398177650

```json
{"cp": 38, "prev_cp": 37, "prev_commit": "69500458b01d783ef78590aea6d0574122fdb646", "utc": "2026-10-25T13:22:01Z", "kind": "posted", "phase": "P2", "done_through": "P2/A11", "next": "P2/A10 A13 A9 A-ABL", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "dfd0e7a366ce04f3ed4c0670a26a62fc33aad25b", "open_decisions": [], "memory": {"used_pct": 7.37, "peak_pct": 23.21, "state": "OK", "stale": false}, "post": "abl_tracescore/status_20261025T1322", "url": "https://github.com/skillberry-ai/cap-evolve/issues/935#issuecomment-6398177650"}
```

## ABL-0039 · 2026-10-25T13:30Z · P2 acceptance A10, A-ABL-CORE abl_ref · result

A10 PASS (throwaway clone, ledger EVAL_A10_TEST.md, branch acceptance/eval-abl-status-test in a local bare remote; AW_REMOTE pinned to that local origin; nothing pushed to GitHub; the real ledger untouched): a 12-cell mini window SIGKILLed after 4 cells resumed with 0 cells re-run, all 12 done; heartbeat marked the killed runner stalled; 1 coalesced entry; append-only; a push failure kept the commit local and the next checkpoint pushed it; the content filter refused a task id and a fake .env value; 3 concurrent writers all landed with unique increasing numbers, all committed. A-ABL-CORE for abl_ref PASS (1-iteration mock dry run on 4 dev ids, accept namespace, 0 counted: 4 accept rollouts, 12 cache hits): cap-evolve check ok; pinned gate.py (decide, paired) accepts 0.3 SE at k 0.2 and rejects it at 1, rejects 0.1 SE at 0.2; IMP 1 code pin (abl-main core, 75b3bcd, clean), 2 skills dir = abl-main/skills, 3 gate_k_se 0.2 in spec and run_config, 4 --k-se 0.2 on the one hill-climb command line, 5 the work/cand_0001/INSTRUCTIONS.md has every required string (title, PREPARATION, objective score, Strategies for constructing edits, SOFT and JUDGEMENT CALLS, prefer code over prose, AppWorld facts, objective score for this run) and none forbidden, the base-vs-arm diff is insertions only, 6 guidance tools and system-prompt SKILL.md sha256 equal the pin and diagnose head lines match, 7 the pinned hill-climb run.py ran; switch spec and env checks ok. Repair: the first dry run made no edit (mock: no mock_script.json found) because the launcher strips inherited CAPEVOLVE_* (9.2 step 5) and the driver passed CAPEVOLVE_MOCK_SCRIPT; the driver now passes AW_MOCK_SCRIPT and the launcher exports CAPEVOLVE_MOCK_SCRIPT only when AW_CAPE_PHASE=accept, so a counted search can never see a mock script. Re-run: the mock note reached cand_0001.

```json
{"cp": 39, "prev_cp": 38, "prev_commit": "415ecd61e9bd463d3af2949924d433d90d93ad21", "utc": "2026-10-25T13:30:36Z", "kind": "result", "phase": "P2", "done_through": "P2/A-ABL-CORE-abl_ref", "next": "P2/A13 A9 A-ABL other arms", "arm": null, "counts": {}, "spend": {}, "artifacts": {"local/acceptance/a10.json": "c625a4e3a15cebe5c7908f3307069fc15926f30adf469f744869dc5371348505"}, "code": "415ecd61e9bd463d3af2949924d433d90d93ad21", "open_decisions": [], "memory": {"used_pct": 2.15, "peak_pct": 23.21, "state": "OK", "stale": false}}
```

## ABL-0040 · 2026-10-25T13:53Z · P2 A-ABL-CORE, per-arm checks · result

A-ABL-CORE and the per-arm checks (plan 9.6, 10.3 to 10.6), 1-iteration mock dry runs on 4 dev ids, accept namespace, 0 counted rollouts in every run; each run with the arm launcher switches. Every scored dry run passed IMP 1-7 and the switch checks (abl-main core and skills, gate_k_se 0.2 in spec and run_config, --k-se 0.2 on the hill-climb command line, J1 strings present and none forbidden, guidance present exactly for the arm capabilities and equal to the pin, the pinned hill-climb script). abl_prompt (10.3): an edit adding a file under tools/ gave a step_indecisive (integrity: TAMPERED, added tools/extra_helpers.py) with 0 rollouts; a prompt-only edit was scored (4 accept rollouts). abl_tools (10.4): an edit adding a file under policy/ gave step_indecisive (TAMPERED) with 0 new rollouts; a helper edit was scored (4 rollouts); a helper returning 300 literal characters was lint-rejected before any episode (lint_rejects.jsonl 1 entry, 0 rollouts). Note: a mock edit that overwrites an existing sealed file fails inside the mock itself (the seal clears its write bits), which voids nothing but proves the read-only layer; the add-a-file edits exercise the hash seal. abl_notrace (10.5) and abl_tracescore (10.6), counts only from abl/walk_feedback.py over the whole run dir (12 rollout files, 158 text files each): notrace 0 non-empty traces, 0 thought/code/reasoning keys, failing rollouts with failed-requirement fields 3/3; tracescore 12/12 traces present, 294 step keys, 0 failed_requirements/pass_count/num_tests/collateral_damage fields, 0 occurrences of requirement checks or Failed requirements; the abl_ref control run has both (traces 12, 294 step keys, 72 evaluation fields, 48 phrases). The info-arm records were served from the shared accept cache (the same tree as abl_ref dry run), so the walk also confirms the filter applies to cache hits. A-ABL-SAME PASS (ABL-0029); guidance check made capability-aware (plan 9.6.6). reset_check dry run PASS on abl_prompt (ABL-0029).

```json
{"cp": 40, "prev_cp": 39, "prev_commit": "a84cf00f359030e499b2a87a6275fec36401c407", "utc": "2026-10-25T13:53:43Z", "kind": "result", "phase": "P2", "done_through": "P2/A-ABL-arms", "next": "P2/A9 per arm, A-ABL-CC", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "a84cf00f359030e499b2a87a6275fec36401c407", "open_decisions": [], "memory": {"used_pct": 2.16, "peak_pct": 23.21, "state": "OK", "stale": false}}
```

## ABL-0041 · 2026-10-25T14:06Z · P2 A-ABL-CC daemon · result

A-ABL-CC daemon items PASS (evald.py dry mode: 4 dev ids, accept namespace, B = 8; a throwaway workdir set up by run_cc.py; 0 rollouts counted against the real B = 882): six requests through ./eval_candidate: (1) a byte copy of the seed was served from the shared accept cache, 0 rollouts; (2) a new candidate cost 4 rollouts (4 of 8 used); (3) the same candidate resubmitted was free (4 cache hits); (4) a lint-violating helper was rejected with 0 rollouts and its violations returned; (5) a second new candidate cost 4 (8 of 8); (6) a third new candidate was refused before running (budget spent, 0 rollouts). Results are in the reference format: trajectories/*.json with input, rollout (trace with steps, metadata with every F1 field) and score (F1 feedback text), and summary.json with mean and per-task reward, lint status, rollouts used and left; ./eval_status reads them. Path refusals (absolute path, .., symlink out, symlinked surface, extra request keys, bad JSON) are covered by the offline tests (ABL-0029). Repair: evald put abl/ first on sys.path, so the evaluator imported abl/adapter.py instead of the shared adapter (every request errored, nothing ran); evald now loads abl/adapter.py by path. Prompt sha256 check: run_cc.py check-config (PROMPT.txt = the plan three lines, 12e145ec...).

```json
{"cp": 41, "prev_cp": 40, "prev_commit": "54e148b40a77536e052c1dda164e0752cb8dc2f6", "utc": "2026-10-25T14:06:06Z", "kind": "result", "phase": "P2", "done_through": "P2/A-ABL-CC-daemon", "next": "P2/A-ABL-CC session init, A9 per arm, A13", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "54e148b40a77536e052c1dda164e0752cb8dc2f6", "open_decisions": [], "memory": {"used_pct": 2.16, "peak_pct": 23.21, "state": "OK", "stale": false}}
```

## ABL-0042 · 2026-10-25T14:07Z · P2 A-ABL-CC session init · decision

A-ABL-CC item 1 FAILS as specified. One real claude -p call through the shim with abl_cc exact launch flags (fresh empty CLAUDE_CONFIG_DIR, --setting-sources none, --permission-mode acceptEdits --allowedTools Bash --disallowedTools Monitor, Sonnet 5.5) shows in its system/init event: 17 skills (all bundled with Claude Code CLI 2.1.270, none from the user or the project; no plugins, no MCP), an auto-memory directory under the config dir (empty; no CLAUDE.md), and the CLI full tool set (Bash, Read, Edit, Write, Task, Skill, Workflow, Cron*, worktree and messaging tools), because --allowedTools only pre-approves Bash and does not restrict the set. The plan (10.2) requires the init to list no skill and no CLAUDE.md memory and tools that match the flags. The cap-evolve arms run the same CLI with the same registry flags, so their optimizer sessions see the same bundled skills and tools. Options: (a) add --disable-slash-commands (all skills off) and turn off auto-memory for abl_cc only (meets 10.2 literally, but abl_cc then has fewer CLI features than the cap-evolve optimizer); (b) the same switches in the shim for every arm (all arms equal, but the cap-evolve arms registry command line then differs from main, against J4/D4); (c) keep the CLI as is for every arm and treat the bundled skills, auto-memory and tool set as part of plain Claude Code (equal across arms; the A-ABL-CC item is recorded as a deviation). Asked of the user (a choice that could favour one arm). Nothing else is blocked: A9, A13 and the remaining checks continue meanwhile; no counted rollout starts before the answer.

```json
{"cp": 42, "prev_cp": 41, "prev_commit": "0ef799c3cbbcd3c9988fc9886ecdb277d0935603", "utc": "2026-10-25T14:07:12Z", "kind": "decision", "phase": "P2", "done_through": "P2/A-ABL-CC-daemon", "next": "P2/A-ABL-CC (user decision), A9 per arm, A13", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "54e148b40a77536e052c1dda164e0752cb8dc2f6", "open_decisions": ["abl_cc init: bundled skills, auto-memory, tool list"], "memory": {"used_pct": 2.12, "peak_pct": 23.21, "state": "OK", "stale": false}}
```

## ABL-0043 · 2026-10-25T14:21Z · P2 posted abl_ref · posted

Posted 'Cap-evolve full (reference) hourly status' on #930 (abl_ref): https://github.com/skillberry-ai/cap-evolve/issues/930#issuecomment-6398799492

```json
{"cp": 43, "prev_cp": 42, "prev_commit": "b335064b38fa6a6158a1b344de4878c21dc7e8b6", "utc": "2026-10-25T14:21:04Z", "kind": "posted", "phase": "P2", "done_through": "P2/A-ABL-CC-daemon", "next": "P2/A-ABL-CC (user decision), A9 per arm, A13", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "54e148b40a77536e052c1dda164e0752cb8dc2f6", "open_decisions": ["abl_cc init: bundled skills, auto-memory, tool list"], "memory": {"used_pct": 1.98, "peak_pct": 23.21, "state": "OK", "stale": false}, "post": "abl_ref/status_20261025T1421", "url": "https://github.com/skillberry-ai/cap-evolve/issues/930#issuecomment-6398799492"}
```

## ABL-0044 · 2026-10-25T14:21Z · P2 posted abl_cc · posted

Posted 'Claude code (plain Claude Code) hourly status' on #931 (abl_cc): https://github.com/skillberry-ai/cap-evolve/issues/931#issuecomment-6398799964

```json
{"cp": 44, "prev_cp": 43, "prev_commit": "9bc7214551cd8a0b895cd236d3689765780e3652", "utc": "2026-10-25T14:21:06Z", "kind": "posted", "phase": "P2", "done_through": "P2/A-ABL-CC-daemon", "next": "P2/A-ABL-CC (user decision), A9 per arm, A13", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "54e148b40a77536e052c1dda164e0752cb8dc2f6", "open_decisions": ["abl_cc init: bundled skills, auto-memory, tool list"], "memory": {"used_pct": 1.98, "peak_pct": 23.21, "state": "OK", "stale": false}, "post": "abl_cc/status_20261025T1421", "url": "https://github.com/skillberry-ai/cap-evolve/issues/931#issuecomment-6398799964"}
```

## ABL-0045 · 2026-10-25T14:21Z · P2 posted abl_prompt · posted

Posted 'Cap evolve prompt only hourly status' on #932 (abl_prompt): https://github.com/skillberry-ai/cap-evolve/issues/932#issuecomment-6398800418

```json
{"cp": 45, "prev_cp": 44, "prev_commit": "4f8beecec45683ee448a37e93ff493b82a436247", "utc": "2026-10-25T14:21:09Z", "kind": "posted", "phase": "P2", "done_through": "P2/A-ABL-CC-daemon", "next": "P2/A-ABL-CC (user decision), A9 per arm, A13", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "54e148b40a77536e052c1dda164e0752cb8dc2f6", "open_decisions": ["abl_cc init: bundled skills, auto-memory, tool list"], "memory": {"used_pct": 1.98, "peak_pct": 23.21, "state": "OK", "stale": false}, "post": "abl_prompt/status_20261025T1421", "url": "https://github.com/skillberry-ai/cap-evolve/issues/932#issuecomment-6398800418"}
```

## ABL-0046 · 2026-10-25T14:21Z · P2 posted abl_tools · posted

Posted 'Cap evolve tools only hourly status' on #933 (abl_tools): https://github.com/skillberry-ai/cap-evolve/issues/933#issuecomment-6398800941

```json
{"cp": 46, "prev_cp": 45, "prev_commit": "65ec0e5f7e74e884c5a2e146cb1927aedcc5b60c", "utc": "2026-10-25T14:21:12Z", "kind": "posted", "phase": "P2", "done_through": "P2/A-ABL-CC-daemon", "next": "P2/A-ABL-CC (user decision), A9 per arm, A13", "arm": null, "counts": {}, "spend": {}, "artifacts": {}, "code": "54e148b40a77536e052c1dda164e0752cb8dc2f6", "open_decisions": ["abl_cc init: bundled skills, auto-memory, tool list"], "memory": {"used_pct": 1.99, "peak_pct": 23.21, "state": "OK", "stale": false}, "post": "abl_tools/status_20261025T1421", "url": "https://github.com/skillberry-ai/cap-evolve/issues/933#issuecomment-6398800941"}
```
