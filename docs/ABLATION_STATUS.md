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
