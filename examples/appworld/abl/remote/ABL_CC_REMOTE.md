# abl_cc on a bubblewrap host: instructions for the executing agent

You are the executing agent of one arm of the AppWorld ablations of cap-evolve: **`abl_cc`, plain Claude Code** (issue
[skillberry-ai/cap-evolve#931](https://github.com/skillberry-ai/cap-evolve/issues/931)). The other five arms ran on the
original pod. `abl_cc` moved here because the original pod's sandbox kills any sandboxed Bash command after about 5 s
(see `DEVAGENT_BWRAP_ISSUES.md` in the package, and ledger entry ABL-0361). Your job: unpack the package, rebuild the
environment, prove that the sandbox here isolates **and** lets long commands run, restore the arm's state, run **one**
fresh Claude Code session, let its evaluations finish, and upload the result bundle to the Box folder
`claude-code-ablation/result/` (step 8, item 7). Nothing else.

**What you start with:** this file and the package file **`claude-code-ablation.tar.gz`** with its checksum file
`claude-code-ablation.tar.gz.sha256`. The user gives them to you, or they are in the user's Box folder
`claude-code-ablation` (for example `rclone copy box:claude-code-ablation/ <dir>` if an rclone remote `box:` is set up).
Nothing is unpacked yet. Step 1 unpacks it; every later step uses the unpacked directory, called `$PKG` below.

Read this whole file before any action. Then, after step 2 (the checkout), read in the `eval-abl` checkout: `docs/ABLATIONS.md` (the plan; at least
sections 3, 4, 9.7, 10.2, 11, 13.2, 13.4 and 14 A9), `docs/ABLATION_STATUS.md` entries ABL-0340, ABL-0341, ABL-0347 and
ABL-0361, and `examples/appworld/abl/cc/` (driver, daemon, prompt). If a source disagrees with this file, or a choice
could favour one arm, **stop and ask the user**.

---

## 0. Mandatory execution rules (section 4 of `docs/ABLATIONS.md`, verbatim)

The plan's section 4 binds you and every sub-agent you spawn. **Paste the full text of section 4 of
`docs/ABLATIONS.md` (from "## 4. MANDATORY EXECUTION RULES" up to, not including, "## 5.") into the prompt of every
sub-agent, word for word.** Prefer to spawn none.

What the rules mean here, in addition to the text:

- **R1 (no agent sees what it must not see).** Never open, print or grep with any tool: `ground_truth/`, `answer.json`,
  `private_data.json`, `evaluation.py`, `solution.py`, `compiled_solution.py`, `root_full`, any `test_normal` /
  `test_challenge` data or id, `appworld/generate/`, `src/appworld/apps/`, `.env` or any secrets file,
  `~/.claude/projects/*`, `/tmp/claude-*/*`, the session's transcripts (`arms/abl_cc/config*`), the cache records
  (`state/cache/`), and the trajectories under `work/.eval/results/*/trajectories/`. Trusted scripts handle these;
  you run them and read only their counts, booleans and hashes. Never print a task id, task text or trajectory.
  The other five arms' state is **not** in this package and must never be fetched.
- **R2 (memory).** Install `memcheck` and `memok-abl` (step 3), start `memguard.py` before anything heavy, and run
  `~/bin/memok-abl && ~/bin/memcheck` before every process launch and every sub-agent spawn.
- **R3 (ledger).** This host does **not** write `docs/ABLATION_STATUS.md` (that ledger has one writer, on the original
  pod). Keep your own append-only log in `docs/ABL_CC_REMOTE_LOG.md` (section 0.2) and commit it only to branch
  **`eval-abl-cc-remote`** of the fork. Never commit or push to `eval-abl`, `ablations`, `main` or any other branch.
- **R5.** Check every number against its source. Prefer a correct pause to a fast wrong step. On anything surprising,
  stop and ask the user.
- **Never** disable or weaken the sandbox, never add flags or tools to the session, never re-prompt the session, never
  edit `PROMPT.txt`, `launch_cc.sh`, `evald.py`, `sandbox_cc/claude` or `common/sandbox.py` beyond the host paths
  named in step 2. A change to them is a user decision.

### 0.1 What must stay identical to the original pod

| item | value |
|---|---|
| code | fork `erezh16/cap-evolve`, branch `eval-abl` at the commit named in `PACKAGE_MANIFEST.json` (`code_commit`) |
| AppWorld | commit `42b5bcf`, with `examples/appworld/patches/appworld-extra-headers.patch` |
| cap-evolve core in the venvs | `main` at `75b3bcdd0fc7292f9717f2b6dcb720f147452df9`, checked out at `/workspace/worktrees/abl-main` (read-only) |
| Claude Code CLI | **2.1.270** (`claude --version`) |
| optimizer model | `aws/claude-sonnet-5-5` via the same gateway, every role |
| agent under test | `openai/gpt-oss-120b-a100` on RITS, `hosted_vllm/`, reasoning medium, temperature 0 |
| session | `launch_cc.sh`: `claude -p "$(cat PROMPT.txt)" --permission-mode acceptEdits --allowedTools Bash --disallowedTools Monitor --model aws/claude-sonnet-5-5 --output-format json --max-turns 1200`, through the shim `abl/sandbox_cc/claude` (adds `--settings` with the sandbox and `--setting-sources ''`), fresh empty `CLAUDE_CONFIG_DIR` |
| prompt | `abl/cc/PROMPT.txt`, sha256 `12e145ec240640337157fa4172ffe914c138c2e6e4942fc9f2b2e4313a3d7456` |
| sandbox | Claude Code sandbox `enabled`, `failIfUnavailable: true`, `allowUnsandboxedCommands: false`, deny list from `common/sandbox.py`, network = gateway host only. **Here it must run on real bubblewrap**, not a fallback. |
| budget | B = 882 counted rollouts for the whole arm; what earlier sessions used stays used |
| search tasks | train ∪ dev = 147 tasks, 1 trial, seed 100, phase `search`, data root `root_opt` |

### 0.2 Your log

Create `docs/ABL_CC_REMOTE_LOG.md` on branch `eval-abl-cc-remote` (step 2), and log step 1 there too. Append one short entry per step:
UTC time, step, result (counts, booleans, hashes only), and any deviation. Commit and push after each entry:
`git -C $AW_REPO commit -m "abl_cc remote: <step>" -- docs/ABL_CC_REMOTE_LOG.md && git -C $AW_REPO push fork HEAD:eval-abl-cc-remote`.
Before every commit, check that the diff has no task id, task text, path under the sealed set, secret or score per task.

---

## 1. Unpack the package file

Do this first: step 2 needs the code commit recorded in the package. The package holds AppWorld task data (train and
dev only) in its cache records, rollout logs and trajectories, so it is part of the sealed set (R1). **Unpack and check
it only with the commands below; never list, open or grep its contents yourself.** Only the trusted scripts read it.
You may read the two text documents (`ABL_CC_REMOTE.md`, `DEVAGENT_BWRAP_ISSUES.md`) and the manifest fields named
below.

```bash
# the directory that holds the two files you were given
IN=/path/to/the/downloaded/files
cd "$IN" && sha256sum -c claude-code-ablation.tar.gz.sha256        # must print: claude-code-ablation.tar.gz: OK
mkdir -p /workspace/aw_abl_pkg && [ -z "$(ls -A /workspace/aw_abl_pkg)" ]   # a new, empty directory
tar -xzf "$IN/claude-code-ablation.tar.gz" -C /workspace/aw_abl_pkg --no-same-owner
export PKG=/workspace/aw_abl_pkg/claude-code-ablation
python3 -I -c "import json,sys;m=json.load(open(sys.argv[1]));print(m['code_commit'], m['snapshot_utc'], json.dumps(m['arm_status']))" "$PKG/PACKAGE_MANIFEST.json"
cmp "$PKG/ABL_CC_REMOTE.md" "$IN/ABL_CC_REMOTE.md" && echo "instructions match the package copy"
```

If the checksum fails, or the instructions you were given differ from the copy in the package, stop and ask the user.
Note `code_commit` (used in step 2) and `arm_status` (used in step 6). Keep `$PKG` outside every git checkout, and
never commit it. Set `PKG` again in every new shell (or add `export PKG=…` to `env.remote.sh` in step 2).

The package has the full file list with a sha256 for every file in `PACKAGE_MANIFEST.json`; step 6 checks every one.

## 2. Host requirements and checkout

The host needs: Linux x86_64 with **unprivileged user namespaces allowed** (check: `unshare -Ur true` exits 0, and
`bwrap --unshare-all --ro-bind / / --dev /dev --proc /proc -- true` exits 0). It also needs `bubblewrap` and `socat`
(Claude Code's sandbox needs both), git and git-lfs, `uv`, Python 3.11, Claude Code CLI 2.1.270, at least 8 CPUs and
32 GB RAM, and about 10 GB of disk. It needs network access to the gateway, RITS, GitHub and Hugging Face (the AppWorld
data download). **If either namespace check fails, stop**: this host cannot run the arm, so tell the user.

If a sandbox wrapper such as `devagent-bwrap` is set in `/etc/claude-code/managed-settings.json` (`sandbox.bwrapPath`),
check which tier it picks: `devagent-bwrap --devagent-tier --unshare-net --ro-bind / / --dev /dev --proc /proc -- true`
must print `bubblewrap`, not `landrun + proot`. If no wrapper is set, Claude Code uses `/usr/bin/bwrap` directly; that
is fine too.

```bash
mkdir -p /workspace/worktrees && cd /workspace/worktrees
git clone git@github.com:erezh16/cap-evolve.git eval-abl && cd eval-abl
git remote rename origin fork && git remote add origin git@github.com:skillberry-ai/cap-evolve.git
git checkout -b eval-abl-cc-remote <code_commit from step 1>
git worktree add --detach /workspace/worktrees/abl-main 75b3bcdd0fc7292f9717f2b6dcb720f147452df9
```

Keep the paths `/workspace/worktrees/eval-abl`, `/workspace/worktrees/abl-main` and `/workspace/aw_abl`: the profile
(`scripts/awabl.py`: `ARMS_HOME`, `CAPE_TREE`) and the venv's editable install use them. If the host cannot use these
paths, stop and ask the user.

Gateway and RITS credentials (ask the user for them; never print them):
- `~/.claude/settings.json` → `env`: `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN` (and `ANTHROPIC_CUSTOM_HEADERS` if
  your gateway needs it), plus `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS` as on the original pod. The shim reads these.
- a `KEY=VALUE` file with `RITS_URL` and `RITS_API_KET` (this exact key name), mode 600, outside every checkout;
  set its path as `AW_ENV_FILE` in `examples/appworld/abl/remote/env.remote.sh`.

Then add your session id to `AW_SESSION_IDS` in `env.remote.sh`, and from now on **source only `env.remote.sh`** (it
replaces `abl/env.sh` on this host; `AW_BRANCH=eval-abl-cc-remote`). It sets `AW_HOST_ENV`, so the launchers,
which source `abl/env.sh` themselves, get this host's values back; check with
`bash -c '. examples/appworld/abl/remote/env.remote.sh; . examples/appworld/abl/env.sh; echo $AW_BRANCH'` → `eval-abl-cc-remote`. Commit `env.remote.sh` without the secrets path if
it is private (or keep it uncommitted). Start the log (0.2).

**Executing-agent deny rules (R1.4).** Copy the deny rules from `$PKG/launch/exec-settings.json` (the original pod's
`/workspace/aw_abl/launch/exec-settings.json`) to `/workspace/worktrees/eval-abl/.claude/settings.local.json` and launch your
own session with `--settings` pointing at it, as on the original pod. Add the package's data
directories to the denied paths too: `Read(//workspace/aw_abl_pkg/claude-code-ablation/cache/**)`,
`…/state_abl_cc/**`, `…/arm_abl_cc/**` and `…/state_root/**` (and the same with `Edit(`). The two documents,
`PACKAGE_MANIFEST.json`, `reference_manifest.json` and `launch/` stay readable.

## 3. Memory guard (R2), before anything heavy

```bash
. /workspace/worktrees/eval-abl/examples/appworld/abl/remote/env.remote.sh
mkdir -p ~/bin "$AW_STATE/progress"
install -m 755 examples/appworld/abl/remote/memcheck ~/bin/memcheck
install -m 755 examples/appworld/abl/remote/memok-abl ~/bin/memok-abl
nohup python3 -I examples/appworld/scripts/memguard.py loop >> "$AW_STATE/progress/memguard.out" 2>&1 &
sleep 10; ~/bin/memok-abl && ~/bin/memcheck
```

`memok-abl` must print `-> OK`. Restart the guard whenever `MEMSTATE.json` is older than 30 s.

## 4. Build (plan section 6.2, B2 to B4) and compare with the original pod

Run each step and keep only its one-line JSON:

```bash
cd /workspace/worktrees/eval-abl/examples/appworld
python3 -I scripts/build.py b1     # AppWorld clone at 42b5bcf + patch
python3 -I scripts/build.py b2     # venv-aw (CPU torch, AppWorld, fastapi 0.143.0, pydantic 2.12.x, -e abl-main/core)
python3 -I scripts/build.py b3     # data download into root_full, split checks, publish cache
python3 -I scripts/build.py b4     # root_opt (train + dev only, 0 test-id hits), reference, lint cache, chmod 000 root_full
```

Then `venv-abl` (plan B3): a venv with **exactly** venv-aw's freeze. On the original pod it was built as
`uv venv -p 3.11 $AW_HOME/build/venvs/venv-abl` followed by `uv pip install -p … -r $AW_STATE/venv-aw.freeze.txt
--index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple`, and its freeze was
byte-equal to venv-aw's (122 packages). Then:

```bash
$AW_HOME/build/venvs/venv-abl/bin/python -I examples/appworld/abl/verify_build.py      # must exit 0
$AW_HOME/build/venvs/venv-abl/bin/python -I examples/appworld/abl/remote/remote_ctl.py compare-manifest "$PKG"
```

`compare-manifest` compares this host's `docs/ABLATION_STATUS_STATE/manifest.json` with the original pod's
(`$PKG/reference_manifest.json`): AppWorld commit and diff hash, venv freezes, the data tree and split hashes,
counts, root_opt tree hash and 0 test-id hits, the reference tree hash, the seed capability hash, and the memory cap.
**Every key must match** (`"ok": true`). If one differs, stop and ask the user: a different build is a different
experiment. Do not edit the reference manifest. Do not commit the manifest the build wrote over the original one.
Restore the original with `git checkout -- docs/ABLATION_STATUS_STATE/manifest.json` after the comparison.

## 5. Gate checks on this host (all must pass before the restore and the session)

Run them in this order and log each result:

1. **Reachability:** `python3 -I examples/appworld/scripts/accept.py a1` (gateway, CLI) and `… a2` (RITS model,
   concurrency, one dev episode). Both must pass.
2. **Long-command probe:** `bash examples/appworld/abl/remote/probe_long_command.sh | tee $AW_STATE/remote/probe_long_command.txt`
   (create `$AW_STATE/remote` first). It runs, through the arm's own shim and sandbox, `sleep 12`, `sleep 90`, and a
   100 s loop. **All three must print PASS**, and the `tier:` line must say bubblewrap (or that no wrapper is present).
3. **A9 for abl_cc** (plan section 11, the arm's exact launch configuration):
   `$AW_HOME/build/venvs/venv-abl/bin/python -I examples/appworld/scripts/check_a9.py cli --cand abl_cc --shim examples/appworld/abl/sandbox_cc/claude`.
   **PASS** iff `ok: true`: 0 of the planted secrets leaked, enough tries, network and AF_UNIX refused, workspace write,
   lint ran, eval request spooled. A9 uses a sibling dir `arms/abl_cc/a9_ws` and moves its usage lines to
   `AW_STATE/abl_cc/accept/`. The probe does the same. That is why both run **before** the restore: the arm's
   restored logs then contain only the real sessions. A9 plants its secrets in the sealed places (`root_opt` gold,
   `root_full`, the app source, `AW_STATE`, …); you never read them, and A9 removes them itself.
4. Never start `evald.py` by hand: only `launch_cc.sh` starts it (step 7).

If any check fails, stop and ask the user. Do not change the sandbox to make a check pass.

## 6. Restore the arm's state (after the gate checks)

```bash
$AW_HOME/build/venvs/venv-abl/bin/python -I examples/appworld/abl/remote/remote_ctl.py restore "$PKG"
```

It checks every package file against `PACKAGE_MANIFEST.json` and every cache record against
`cache/LISTING.sha256`. It then copies the cache records into `AW_STATE/cache/main/` (the seed tree, so a seed copy is
free, and every candidate tree evaluated so far, so a resubmission is free). It also copies `state_abl_cc/` to
`AW_STATE/abl_cc/`, the session workdir and config dirs to `AW_HOME/arms/abl_cc/`, and the seed-baseline marker. Record
its JSON in the log. Expect: the same `arm_status` you noted in step 1: `evaluations_done` = the number in `PACKAGE_MANIFEST.json`, `rollouts_used` + `rollouts_left`
= 882, `open_tickets` = 0, `inflight_markers` = 0, and `sessions_started` = `SESSION_STARTED`, `SESSION2_STARTED`.

What the earlier sessions did is in the package manifest (`arm_status`). The workdir is what session 2 left: the seed
surfaces at the top level plus its own subdirectories `c0`, `c1`, `c2`, its git history, and `.eval/` (requests and
results). Session 3 starts from exactly this workdir. That matches the original pod's decision for session 2
(ABL-0341): same workdir, earlier results visible in `.eval/results/`, no memory of the earlier sessions (fresh config
dir).

## 7. The one session (session 3)

This is one fresh session with the same three-line prompt, the remaining budget, the current workdir and an empty
config dir (`config3`). It is a recorded deviation from the plan's no-re-prompting rule, by user decision (ABL-0361),
for the same reason as session 2 (ABL-0341): the earlier sessions ended because their waits were killed. Start it
exactly once:

```bash
cd /workspace/worktrees/eval-abl
~/bin/memok-abl && ~/bin/memcheck
AW_CC_SESSION=3 nohup bash examples/appworld/abl/cc/launch_cc.sh > $AW_STATE/progress/abl_cc_session3.out 2>&1 &
```

`launch_cc.sh` refuses to start if `SESSION3_STARTED` exists, if `SESSION2_STARTED` is missing, if `config3` is not
empty, if the prompt hash differs, or if the shim is not first on PATH. It starts `evald.py` (the trusted,
unsandboxed eval daemon) and then the session, which writes `AW_STATE/abl_cc/session3_result.json` at the end.

While it runs:
- **Do not talk to the session, and do not send it input or signals.** Do not read its transcripts (R1).
- Watch only counts: `remote_ctl.py status` every 10 to 15 minutes, `~/bin/memok-abl`, `ps` (pids and elapsed time
  only), and the daemon log lines `AW_STATE/progress/abl_cc_evald.out` (they carry ticket, candidate hash, state, mean
  reward, rollouts; no task data). Log each new evaluation: ticket, mean reward, rollouts used of 882.
- If memory goes PAUSED, the evaluator waits on its own; nothing to do unless it lasts more than 10 minutes (R2
  escalation: lower `AW_STATE/slots/SIZE` by 25%, log it).
- If the gateway or RITS fails (HTTP 429/5xx in `AW_STATE/progress/abl_cc.log`), log it and ask the user. Do not
  restart the session.
- Each evaluation of 147 tasks takes about 1 hour at 24 slots. The session may run several hours (up to 1,200 turns).

The session ends on its own (end of turn, the turn cap, or the budget). **No re-prompt and no further session.**

## 8. After the session ends

1. **Let the daemon finish** any ticket still running: wait until `remote_ctl.py status` shows `open_tickets: 0`, and
   until `AW_STATE/abl_cc/inflight/` is empty. Then stop the daemon: `kill $(cat $AW_STATE/abl_cc/EVALD.pid)`.
   An evaluation the session requested counts. Its result simply arrives after the session.
2. **Freeze:** `$AW_HOME/build/venvs/venv-abl/bin/python -I examples/appworld/abl/cc/run_cc.py freeze`. The champion is
   the workdir's three surfaces when the session ended (plan 10.2). Log its JSON: tree hash, inert, deviation, best
   evaluated.
3. **Isolation scan of the arm:** `python3 -I examples/appworld/scripts/scan.py abl_cc`. Log the test-id hit count
   only. Any hit: stop and ask the user.
4. **Bundle:** `$AW_HOME/build/venvs/venv-abl/bin/python -I examples/appworld/abl/remote/remote_ctl.py bundle /workspace/aw_abl/export/return_abl_cc`,
   then:

   ```bash
   cd /workspace/aw_abl/export
   tar -czf abl_cc_return.tar.gz return_abl_cc            # the top directory must be return_abl_cc/
   sha256sum abl_cc_return.tar.gz > abl_cc_return.tar.gz.sha256
   ```

   The bundle holds the arm state (evals, rollouts, cache-hit and usage logs, claude_calls, session results,
   candidates, champion), the workdir, all config dirs (the session transcripts, for the original pod's isolation
   scan), the check results (`checks/probe_long_command.txt`, `checks/a9_abl_cc.json`), and the cache records of every
   evaluated tree. It **contains task data in the rollout and cache records and in the trajectories**. That is fine for
   the transfer to the original pod's trusted scripts. It must **not** be committed to git or posted anywhere public.
   Check before uploading that `checks/probe_long_command.txt` and `checks/a9_abl_cc.json` are in the bundle: the
   original pod refuses a result without them.
5. Commit to `eval-abl-cc-remote` only: the log, `docs/ABLATION_STATUS_STATE/abl_cc/progress.json` and
   `docs/ABLATION_STATUS_STATE/abl_cc/artifact/` (the frozen champion: three surface files plus `FREEZE.json`). Before
   committing, check them with the scan result of item 3 above (0 test-id hits in the artifact). Push.
6. **Report:** write `/workspace/aw_abl/export/REMOTE_REPORT.md` (uploaded in item 7) and give the same text to the
   user. It holds: the tarball sha256, counts (evaluations, rollouts of 882, best evaluated mean val as a fit metric,
   champion tree hash, inert or not), optimizer usage (calls, tokens, CLI-reported USD from the session results), the
   probe and A9 results, the session's start and end time and stop reason, and every deviation. Counts and hashes
   only: no task id, task text, trajectory or per-task score. **No test number exists for this arm yet**: the
   champion's held-out test score is produced only in the original pod's single final window (plan P7), together
   with the other arms.

7. **Upload the result to Box, automatically, without waiting for the user.** The original pod watches the Box folder
   `claude-code-ablation/result/` (the same Box folder the package came from) and takes over as soon as the result is
   complete there. Upload exactly these files, **in this order**, with the marker last:

   ```bash
   cd /workspace/aw_abl/export
   R=box:claude-code-ablation/result           # the same Box account and folder the package came from
   rclone copyto abl_cc_return.tar.gz        $R/abl_cc_return.tar.gz
   rclone copyto abl_cc_return.tar.gz.sha256 $R/abl_cc_return.tar.gz.sha256
   rclone copyto REMOTE_REPORT.md            $R/REMOTE_REPORT.md      # item 6, counts only
   rclone check  . $R --include "abl_cc_return.tar.gz*" --download     # must report 0 differences
   date -u +%FT%TZ > UPLOAD_COMPLETE && rclone copyto UPLOAD_COMPLETE $R/UPLOAD_COMPLETE
   ```

   - **`UPLOAD_COMPLETE` goes last**, only after `rclone check` passes. The original pod starts the import when it sees
     the marker, so a marker before the tarball is complete means the import reads a partial file.
   - If this host has no rclone remote for that Box account, ask the user once for access (an rclone `box` remote, or
     another way to put the files in that folder). Do not upload anywhere else.
   - Do not upload twice. If an upload must be repeated (a failed check), delete `UPLOAD_COMPLETE` from the folder
     first, upload again, and write the marker last.
   - Never put anything else in that folder: no unpacked bundle, no logs with task data.
Your work ends with item 7. The original pod downloads, checks and installs the result, then runs abl_cc's freeze,
isolation scan and reset check there and continues with the remaining phases.

Do not post on the GitHub issues from this host. The original pod's executing agent records the remote run in the
ledger and on #931 when the result is imported.

## 9. Package contents (inside `claude-code-ablation.tar.gz`, unpacked as `$PKG`)

| path | what |
|---|---|
| `ABL_CC_REMOTE.md` | this file (also in the repo at `examples/appworld/abl/remote/`, and next to the tarball in Box) |
| `DEVAGENT_BWRAP_ISSUES.md` | why the arm moved: the original pod's sandbox kills long commands |
| `PACKAGE_MANIFEST.json` | code commit, snapshot time, arm status (counts), sha256 of every file below |
| `reference_manifest.json` | the original pod's build manifest (hashes, counts) for `compare-manifest` |
| `state_abl_cc/` | the arm's state: `evals.jsonl`, `rollouts.jsonl` (counted), `cache_hits.jsonl`, `optimizer_usage.jsonl`, `claude_calls/`, `session_result.json`, `session2_result.json`, `SESSION*_STARTED`, `cands/` (evaluated candidate trees) |
| `arm_abl_cc/work/` | the session workdir (git repo, `c0` to `c2`, `.eval/` requests and results) |
| `arm_abl_cc/config`, `config2` | the earlier sessions' config dirs (transcripts; for the scan only, never read) |
| `cache/main/`, `cache/LISTING.sha256` | evaluator cache records of the seed tree and of every abl_cc candidate evaluated so far |
| `state_root/` | `SEED_BASELINE_DONE` (the shared seed baseline marker: a seed copy is served from cache) |
| `launch/exec-settings.json` | the executing agent's deny rules (R1.4) |

The package contains task data in the cache and rollout records and in the trajectories under
`work/.eval/results/`. Treat it like the AppWorld data itself: not public, not committed, and opened only by the
trusted scripts.
