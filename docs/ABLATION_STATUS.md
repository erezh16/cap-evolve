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
