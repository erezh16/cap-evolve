# Backup of the AppWorld evaluation runs to Box

Plan for collecting every evaluation run of the AppWorld smoke test (issue #804), organizing each
run as a folder tree, and copying it to the Box archive with `rclone`. The whole operation is timed.

## 1. Scope: which runs

The task names three runs. The evidence splits the third one in two, and both parts are kept:

| run | what it is | where its data is on this host |
|---|---|---|
| R1 cap-evolve, original | hill-climb, `cape_hc_s0`; round 2 read train/dev answers (breach, F14) | `/tmp/aw_eval/runs/cape_hc_s0`, its optimizer sessions, the first final window |
| R2 ALTK-Evolve, original | mining, dose selection, the retrieval champion | `/tmp/aw_eval/runs/altk`, the first final window |
| R3 cap-evolve, fix | **two training attempts**: `cape_hc_s1` (discarded, generator leak F19) and `cape_hc_s2` (scored, F20), plus the second final window | `/tmp/aw_eval/runs/cape_hc_s1`, `cape_hc_s2`, `final2` |

R3 is one run folder that contains both attempts. `cape_hc_s1` is part of the fix's history: it is why
there is a third training run. Both final windows also score the other arms, so their results are
stored in the run that owns each window (R1 + R2 share the first window; R3 owns the second). Each copy
says so.

Not in scope: the **ACE** smoke test, which is also posted on #804 (12 comments). It is a separate
evaluation on branch `erezh-eval2-ace`, and its data is not on this host. Its comments are kept with the
#804 export, but no ACE run folder is created.

## 2. Layout on Box

`eval-data:` (alias of `box:cap-evolve-paper-data/user/erezh`, empty before this backup):

```
eval-data:appworld/
  2026-10-13-appworld-capevolve-hillclimb-gptoss120b-sonnet55-original-breach/     (R1)
  2026-10-13-appworld-altkevolve-v130-retrieval-gptoss120b-sonnet55-original/      (R2)
  2026-10-15-appworld-capevolve-hillclimb-gptoss120b-sonnet55-fix-clean/           (R3)
```

Names follow the repo's archive convention, `docs/experiments/<date>-<bench>-<…>-<models>/`: the
start date, the benchmark, the method and its key setting, the agent model, the optimizer model, and
the run's status. They are plain ASCII, so they are safe on Box.

## 3. Inside each run folder

The layout follows `docs/experiments/2026-09-26-spreadsheetbench-…/README.md` and the CI artifact
(`runmeta.json`, `metrics.jsonl`, `steps.jsonl`, `report.md`). For cap-evolve, the run dir itself is kept
unchanged, so the cap-evolve tools can load it from the copy (§5).

```
<run>/
  README.md            what the run is, outcome, provenance, how to read the folder, caveats
  MANIFEST.json        every file: relative path, bytes, sha256; plus the source path it came from
  runmeta.json         run identity, in the CI benchmarks.yml schema (run_id = local name, models,
                       providers, algorithm, iterations, trials, gate_k_se, sha, dates, conclusion)
  data/                CI-compatible derived data: metrics.jsonl, steps.jsonl, report.md (metrics.py suite)
  capevolve/           cap-evolve arms only: the original .capevolve tree, byte for byte
    project/             capevolve.yaml, adapters/, seed_capability/, optimizer/INSTRUCTIONS.md, split_ids.json, sandbox/
    run_<name>/          state.json, events.jsonl, splits.json, baseline.json, final.json, graph.jsonl,
                         eval_index.jsonl, history/rejected.jsonl, JOURNAL.md, INSIGHTS.md, META_INSIGHTS.md,
                         FRAMEWORK_IMPROVEMENTS.md, report.md, dashboard.html, candidates/, rollouts/,
                         work/ (each round's optimizer workdir: LEDGER.md, RUNMAP.md, PROCESS.md, DIAGNOSIS.json,
                         trajectories/, guidance/), .git (the iteration store)
  champion/            the scored artifact (policy/, tools/, memory/) + capability.diff vs seed
  rounds/rN_<cand>/    per round: diff.patch, PROCESS.md, DIAGNOSIS.json, verdict.json (from events)
  host/                the optimizer as an agent: launch args, the instructions it received,
                       transcripts/ (claude-code session JSONL incl. subagents), file-history/,
                       session-env/, claude-tmp/ (task outputs), optimizer stderr
  altk/                ALTK arm only: store/ (filesystem backend), mined.json, mining_summary.json,
                       optimizer_usage.jsonl, cand_full/, cand_ret_dev/, dev_altk-ret/ (57 dev rollouts),
                       dose_selection.json, logs (mine/render/select .out)
  final_window/        the held-out window this run owns or shares: artifacts/ (frozen arms + hashes),
                       results.jsonl, results.json, tables.md, status.json, stability.json (window 2),
                       RESULTS.md (window 1)
  isolation/           isolation_scan.json, transcript audits, A9 check runs (the check itself),
                       the round-2 helper scripts from /tmp/diag (R1), sealed evidence (below)
  logs/                progress/*.log and *.out for this run, PROGRESS.md, guard log, build log
  posts/               the GitHub record: the #804 comments for this run as markdown (fetched from the
                       API, with ids and timestamps), the local drafts, linked issues/PRs as JSON
  docs/                the plan, appendices, fix plan, summary page, as of the backup commit
  env/                 environment record: manifest.json (commits, pip freeze, data hashes, patch),
                       the AppWorld patch, reference/ (optimizer read-only docs), lint_cache.json,
                       the example code at the commit, scripts used to launch
```

**Sealed evidence (R1 only).** `/tmp/diag/root` is the copy of the data root that round 2's subagents
made, and it holds train/dev **gold**. It is evidence of the breach, so it is kept. To stop it from
being taken for data, it goes in as one `isolation/diag_root_SEALED.tar` (not compressed), with a
README that says what it is. The task asked for no compression, and that is about the folder tree. This
one tar is a deliberate exception for gold data. Its permissions are `000`, so it is read with an
explicit `chmod` on a temporary copy.

**AppWorld data rule.** AppWorld's protected data is Apache 2.0 with one extra condition: any public
redistribution, including derivatives, must be encrypted. The run folders hold derivatives: task
instructions, trajectories and test results. **Decision (owner, 2026-10-19): the Box folder is a private,
access-restricted team archive, so the tree is uploaded unencrypted as planned.** Each run root gets a
`NOTICE.md` that states the rule and says not to make the folder public unencrypted.

## 3a. Reproducibility

**Goal:** each run folder must hold enough for someone else to repeat the run without this host.
Model sampling is not deterministic (F10: at temperature 0, trials still disagree), so "repeat" means
the same procedure, configuration and inputs, not the same bytes. Each run folder gets a
`reproduce/` subfolder. It is the single place to start.

**What a repeat needs, and where it is:**

| need | where | notes |
|---|---|---|
| exact cap-evolve code (core, skills, templates, CI tools, example) | `reproduce/code/capevolve_erezh-eval1.bundle` (git bundle, full history; verified, every commit checks out) + `code_commits.json` | per run: R1 at `32df0f1`; R3 attempt 1 at `95433f3`; attempt 2 at `95433f3` with the `sandbox/claude` allowlist of `ec30d13` (the wrapper is read at call time) |
| R1's example code (never committed) | `reproduce/code/r1_adapters_reconstructed/` | R1 ran before `examples/appworld` was committed, and its project copy was overwritten at the resume. The three adapter files are **rebuilt by replaying every recorded edit** from the session transcript, at the 3 points they were copied in (launch, round 4, resume); v3 is byte-identical to the run's own copy, and all compile. The other example files are rebuilt as of the first window |
| AppWorld code | `env/appworld_commit.txt` (`42b5bcf3…`), `env/appworld_git_diff.patch` | the public repo; git-lfs bundles are fetched by `git lfs pull` |
| AppWorld data | `reproduce/appworld_data.json`: version `0.2.0`, bundle URL, the tree hash of `root_full/data`, split-file hashes, counts | **not copied** (license: encrypted redistribution). `appworld download data` fetches the same version; the hashes prove identity |
| search data root | `reproduce/make_roots` command, the `root_opt` tree hash | rebuilt from the data by `scripts/make_roots.py` |
| Python environments | `reproduce/env/requirements-venv-aw.txt`, `requirements-venv-altk.txt` (exact `pip freeze`), interpreters (3.11.2, 3.12.15), `uv` 0.13.0, CPU torch index | |
| embedding model (ALTK) | `reproduce/models.json`: `sentence-transformers/all-MiniLM-L6-v2` @ revision `1110a243…` | public on Hugging Face |
| agent model | `reproduce/models.json`: `openai/gpt-oss-120b-a100` on IBM RITS (vLLM, `max_model_len` 40,144), the full litellm config (`adapters/aw_agent.py` MODEL_CONFIG), seeds `100 + trial` (search) and `5000 + trial` (final) | the endpoint's backend version is not visible from the client: a known limit |
| optimizer | `reproduce/models.json` + `reproduce/optimizer_cli.json`: Claude Code **2.1.270**; main loop `aws/claude-sonnet-5-5`; **subagents `aws/claude-opus-5-5`** (from the user settings `CLAUDE_CODE_SUBAGENT_MODEL`, confirmed in the transcripts); haiku for small helpers; `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1`; effort `high`; the CLI flags | the subagent model was **not** stated in the plan, and a repeat that leaves it out runs a different optimizer |
| optimizer's inherited config | `reproduce/env/claude_settings.redacted.json` (secrets removed), installed plugins and their versions | it inherits the user settings by design |
| exact launch | per attempt: `host/launch_args.json`, the spec, the rendered INSTRUCTIONS, the env vars (names and values without secrets), the wrapper + its settings | |
| orchestration record | `reproduce/orchestrator/`: the session transcript that ran the whole evaluation (every command, decision and check), its subagents, tool outputs, the host agent's own journal/audit, and the session memory | the most complete "how it was done" record; secrets redacted |
| host | `reproduce/env/host.json`: OS, kernel, container facts (rootless podman, `/dev/null` host bind, user namespaces on) | needed to reproduce the isolation behaviour (F17) |
| steps | `reproduce/REPRODUCE.md`: commands in order, for this run only | |

**Found while checking reproducibility** (not stated in the plan, and a repeat that leaves them out
runs a different setup):
- The optimizer's **subagents ran on `aws/claude-opus-5-5`**, not Sonnet 5.5: 220 / 359 / 403 subagent
  messages in R1 / R3a1 / R3a2 (plus 2 Haiku 4.5 helper calls). The main loop was Sonnet 5.5 throughout.
  The cause is the user setting `CLAUDE_CODE_SUBAGENT_MODEL`, which `claude -p` inherits.
- Claude Code **2.1.270** in every run (from the transcripts); `effortLevel: high` and
  `alwaysThinkingEnabled` were also inherited.
- R1's code is reconstructed (above).

**Reproducibility check before upload:** the assembler cross-checks that every hash in
`reproduce/` (data tree, split files, patch, champion trees) matches the files it refers to, and that
the git bundle verifies (`git bundle verify`) and contains every commit named in `code_commits.json`.

## 4. What is not copied, and why

| item | why | how it stays reproducible |
|---|---|---|
| `venv-aw`, `.venv`, `venv-pw`, `hf/` model cache | environments (396 MB+), rebuildable | exact freezes, interpreter versions and the model revision in `reproduce/` (§3a) |
| AppWorld clone, `root_full`, `root_opt` data | public, and the data is under a redistribution rule | commit `42b5bcf`, the patch, `sha256_tree` of `root_full/data` and `root_opt` |
| `.env`, `~/.claude/settings.json`, rclone config | secrets | names of the variables only |
| acceptance probes A1–A8, `a6_dry` | not counted runs (rule S1) | one copy under R1 `isolation/acceptance/` (A6 dry run, A8 table, check outputs) |

A secret scan runs over every folder before upload: the RITS key, the gateway token and the custom
header value must have 0 hits.

## 5. Compatibility with cap-evolve tools

After assembly, each cap-evolve copy is checked from the backup folder itself. The checks are read-only:
- `cap-evolve tail <run>/capevolve/run_<name> --from-start` replays the whole event stream (exit 0);
- `RunDir.open` + `dashboard.reduce_run` + `render_html` load the run and render the dashboard in memory.
  (`dashboard --export` would overwrite the original `dashboard.html` inside the backup.);
- `python ci/benchmarks/lib/metrics.py suite <run_dir> --bench appworld …` produces `data/`. Its
  `report.md` is the tool's own output, so it is a **train-fit** report: train = val, and the held-out
  numbers are in `final_window/`.

A run that fails any of these is fixed before upload.

## 6. Procedure and timing

```
T0  start   (date +%s.%N, written to timing.json)
    1. freeze: git rev-parse HEAD of erezh-eval1; the list of source paths
    2. assemble each run folder under /tmp/aw_eval/backup/<run>/ (cp -a, preserving times)
    3. derive: data/ (metrics.py), rounds/, champion/, runmeta.json, posts/ (gh api)
    4. verify: tool checks (§5), secret scan, MANIFEST.json (sha256 of every file)
T1  end of capture
    5. rclone copy each run folder to eval-data:appworld/<run>/ (--transfers 8, --checkers 16,
       --log-file per run; copy, never sync, so nothing on Box is ever deleted)
    6. rclone check <local> <remote>: Box keeps SHA-1 for every file, so this compares content,
       not just sizes. It must report 0 differences and 0 missing files.
T2  end of transfer
```

`timing.json` records T0, T1 and T2, the capture time (T1 − T0) and the transfer time (T2 − T1), both
per run and in total, with byte and file counts. It is uploaded too: in `eval-data:appworld/` as
`BACKUP_LOG.json`, and in each run's README. The rclone install is not timed (§7).

Tools: `scripts/backup/build_backup.py` (assemble, derive, verify, time) and
`scripts/backup/upload_box.sh` (copy, check, time), both in `examples/appworld/`.

## 7. rclone

v1.75.1 (released 2026-09-04): the official linux-amd64 build, SHA256-checked against rclone's
published `SHA256SUMS`, installed to `~/.local/bin` without root. The newer v1.75.2 was released less
than two weeks ago, so it was not used. The `eval-data` remote is already configured (a Box alias) and
was tested read-only (`rclone lsf`, `about`).

## 8. Result (executed 2026-10-19)

Uploaded to `eval-data:appworld/`, as plain folder trees (no compression; one uncompressed tar for the
sealed gold copy, §3). `rclone check` against Box SHA-1 reports **0 differences** in every run.

| run | files | size |
|---|---|---|
| R1 `2026-10-13-appworld-capevolve-hillclimb-gptoss120b-sonnet55-original-breach` | 3,678 | 315.0 MB |
| R2 `2026-10-13-appworld-altkevolve-v130-retrieval-gptoss120b-sonnet55-original` | 306 | 86.6 MB |
| R3 `2026-10-15-appworld-capevolve-hillclimb-gptoss120b-sonnet55-fix-clean` | 5,423 | 214.5 MB |
| + `BACKUP_LOG.json`, `timing.json` | 2 | |
| **Box total** | **9,406** | **587.6 MiB** |

**Timing** (rclone install not timed):

| step | seconds |
|---|---|
| capture and organize, phase 1 (assemble, derive, tool checks, secret scan, manifests) | 9.9 |
| capture, phase 2 (`reproduce/` per run, added after the reproducibility requirement) | 3.2 |
| **capture total** | **13.1** |
| transfer, phase 1 (R1 2,278 s · R2 197 s · R3 2,899 s) | 5,373.3 |
| transfer, phase 2 (new and changed files only) | 213.2 |
| **transfer total** | **5,586.5 (1 h 33 min)** |
| verification on Box (`rclone check`, both phases) | 202.0 |

The transfer is bound by the per-file overhead on Box, about 1 file/s for roughly 9,400 mostly small
files, not by bandwidth. Capture is under 15 s because it is local copying.

**Notes from execution**
- Phase-1 `rclone check` failed for R1 on one file only: `SYMLINKS.txt`, written after that run's copy had
  started. Phase 2 uploaded it, and the final check is clean.
- 9 symlinks (claude task-output links and an A9 test link) cannot be stored on Box. Each run lists its
  links in `SYMLINKS.txt`. Every target is either a file already in the backup or a file outside the run.
- Two capture attempts were discarded locally before the timed capture: a tool-check bug, and a rebuild
  after committing the tools. The figures above are the clean runs.
- F21 (optimizer subagents ran on Opus 5.5) was found while building `reproduce/`. It is not yet
  reflected in the run-folder names; that depends on the decision about the scored run.

**Added 2026-10-19: `data/metrics_full.jsonl`** in every run folder (and in each R3 attempt), with a
README. It holds reward, tokens, latency and cost in one file, at four levels: each held-out episode, each search round,
each ALTK optimizer call, and a run total. It is needed because the CI-format `metrics.jsonl` from
`metrics.py suite` has no optimized-side values for these runs. Cost coverage: the cap-evolve optimizer cost is the
CLI's own report; the ALTK optimizer cost is an **estimate** at the Claude Sonnet 5.5 list price ($2 / $10 per MTok;
$18.04 for 3.81M tokens); the **agent's cost is not measured** (IBM RITS does not price calls), so tokens stand in for it.
Upload of the 13 new and changed files: 94.0 s; check: 95.5 s, 0 differences. Box now holds 307 + 3,679 + 5,428 run
files.
