# cap-evolve repository cleanup: findings and proposed changes

| | |
|---|---|
| **Written** | 2026-10-05 |
| **cap-evolve** | `6af27e2` (`main` of `skillberry-ai/cap-evolve`, identical to this checkout) |
| **Prompted by** | The 2026-10-05 thread on PRs #495 and #581, where-scripts-live, a second repo for "ccc, parsec, benchmarks, plans and docs", plugins, and slow clones |
| **Companion** | [`docs/INFRA.md`](INFRA.md) covers build tooling: task runner, stamps, CI recipes. This document covers **repository structure**: what lives where, what a clone costs, and how non-core content should attach to core. It does not repeat INFRA.md. |

How the findings were checked. Every number marked **(measured)** was reproduced; Appendix A
lists the commands.

- A mirror clone and a plain clone of `skillberry-ai/cap-evolve` were made on 2026-10-05, and
  object sizes were read with `git rev-list --objects | git cat-file --batch-check`.
- Branch and PR state were read with `gh`, and repository settings and rulesets with `gh api`.
- Test suites were run in a fresh Python 3.11 venv (`pip install -e ./core[dev]`).
- Proposed fixes marked **(validated)** were applied to a scratch copy and run.
- Two subagent surveys (core extension points; cross-directory coupling) were spot-checked
  against the code before use.

File references use `path:line`.

---

## Contents

- [Summary](#summary)
- [1. The questions, and where each is answered](#1-the-questions-and-where-each-is-answered)
- [2. Findings](#2-findings)
- [3. Target structure](#3-target-structure)
- [4. Proposed changes](#4-proposed-changes)
- [5. Phased plan and exit criteria](#5-phased-plan-and-exit-criteria)
- [6. Decisions the team needs to make](#6-decisions-the-team-needs-to-make)
- [Appendix A — How the numbers were measured](#appendix-a--how-the-numbers-were-measured)
- [Appendix B — Branch inventory](#appendix-b--branch-inventory)

---

## Summary

**Why the clone is slow.** A plain `git clone` downloads all 175 branches: 159 MB and 4,072
commits, while `main` has only 476. **111 MB of that is 16 orphan data branches** (measured).
`benchmark-history` alone is 100 MB, and it has grown 33–45 MB a month since August, because CI
commits a live dashboard snapshot to it every 5 minutes per running benchmark leg. Of its 2,525
commits, 2,326 are such snapshots. All 159 code branches together add only **2.7 MB** beyond
`main`. Deleting stale branches is good hygiene, but **it does not fix the clone**. Moving the
data branches out of this repository does.

`main` is 48 MB. More than three quarters of that is media and generated output (a 15 MB demo
video, screenshots, a 4.6 MB PDF, a generated site tree, committed run dumps). The code itself
is about 10 MB of history.

**What to do with the two PRs.**

- **#495** is merged. It is fine where it is for now, but it introduced two defects that CI
  could not see (§2.5):
  - it broke a `capevolve_harbor` test, and with it token accounting for one result format;
  - it added `scripts/v4_t2_e1/tests`, which fail on every machine and are run by no workflow.
- **#581** conflicts because its branch was cut from a 4-week-old `main`, and #495 was then
  squash-merged. Resolving the conflicts the obvious way would **revert newer parsec code on
  `main`**. Instead, cherry-pick its single tip commit onto `main`. That leaves exactly the 7
  intended files, with one trivial conflict (§2.6, validated).

**Where things should live.** Use three repositories, each with one job (§3):

| Repository | Job | Content |
|---|---|---|
| `cap-evolve` (this one) | The product, plus the regression harness that tests it | core, dashboard, skills, templates, plugin, public benchmark harness, toy examples, user docs, site source |
| `cap-evolve-lab` (new; name to be decided) | Experiments and their record | parsec, CCC, `v4_*` runners, design specs and plans, experiment write-ups, presentations, the content of `parsec-history` and `skillsbench-history` |
| `cap-evolve-bench-data` (new; name to be decided) | Machine-written benchmark records | today's `benchmark-history` (`records/`, `runs/`). Live snapshots go to short-lived per-run branches. |

**"Plugins?"** It depends on what the content is:

- **Skills and adapters** contributed from another repo should attach to core as a plugin. Core
  is close to supporting this: adapters can already live anywhere. Skills need one small
  installer feature (§4.5) because core reads exactly one skills root.
- **Experiments are not plugins.** They are *consumers* of core. They should pin a core release
  the way any user would, not be wired in through submodules or subtrees.

**Order of work.**

1. **This week, no new repos needed:** land #581 safely, fix the #495 defects, run every test
   directory in CI, and turn on branch auto-deletion.
2. **Next:** move the benchmark data out, which is the clone fix.
3. **Then:** create the lab repo.

Expected result: a plain clone drops from 159 MB to about 51 MB with step 2, and to about 11 MB
only if the team also agrees to the optional `main` history rewrite (§4.6).

---

## 1. The questions, and where each is answered

| # | Question from the thread | Answer |
|---|---|---|
| Q1 | "Take another look at PRs #495 and #581" | §2.5, §2.6, §4.1 (A1–A3) |
| Q2 | "Where such scripts (and their corresponding tests) should live" | §2.7, §3.2 |
| Q3 | "Open another repo and move there all ccc, parsec, benchmarks, plans and docs" | §3.1, §3.4, §4.3 |
| Q4 | "Maybe plugins? … the best way to extend a working repo with highly related content" | §2.8, §3.3, §4.5 |
| Q5 | "We need to understand why the clone is taking too long" | §2.1, §2.2, §4.2 |
| Q6 | "We need a serious cleanup" | §2.3, §2.4, §2.9, §4.4 |

---

## 2. Findings

### 2.1 Why the clone is slow (measured)

These clones were measured on a host with a fast link, so absolute times on a laptop or VPN
will be several times longer. The ratios are what matter.

| Clone command | Time | `.git` size | What it fetches |
|---|---|---|---|
| `git clone` (default) | **31 s** | **159 MB** | all 175 branches and the tag `v0.1.0` |
| `git clone --single-branch` | 9 s | 50 MB | `main` only, full history |
| `git clone --filter=blob:none` | 9 s | 44 MB | all commits and trees, plus only the blobs `main` checks out |
| `git clone --depth 1` | 7 s | 39 MB | `main`'s tip only |

The default clone does **not** fetch the 442 `refs/pull/*` refs or `refs/notes/bob`, so these
are irrelevant to clone time.

**Packed object size by ref set** (union of reachable objects, deduplicated):

| Ref set | Size |
|---|---|
| `main` | 48.4 MB |
| `main` + open-PR branches + tag | 48.7 MB |
| All 159 code branches (merged, closed, open, no-PR) | 51.1 MB |
| The 16 orphan branches (no common history with `main`) | **111.0 MB** |
| …of which `benchmark-history` | **100.4 MB** |
| …of which `skillsbench-history` | 7.5 MB |
| …of which `parsec-history` | 2.0 MB |

**Conclusion.** About 70% of a default clone is benchmark *data* that no developer needs in
order to work on cap-evolve. The 136 merged-but-undeleted branches cost almost nothing in
bytes; they cost clarity, not clone time.

**What `main` itself is made of** (packed, full history):

| Content | Size |
|---|---|
| Media and generated output: `docs/assets/**`, `site/assets/**`, `site/skillsbench/**`, `*.mp4/gif/png/jpg/pdf`, `examples/tau2_airline/run_*` dumps, `presentation/reveal/**`, `docs/experiments/**` | 37.1 MB |
| Everything else (code, tests, docs text) | 10.1 MB |
| Commits and trees | 1.2 MB |

At the tip, `docs/assets/` is 26 MB on its own. That includes
`docs/assets/demo/cap-evolve-demo.mp4` (14.8 MB) and the PDF
`site/skillsbench/results/evo_skill_paper/2604.01687v1.pdf` (4.8 MB). All of `core/` is 0.7 MB
packed.

### 2.2 `benchmark-history` is a database stored in git

**Who writes and reads it:**

| Writer or reader | Where | What it does |
|---|---|---|
| `aggregate` job (writer) | `benchmarks.yml:766-870` | Commits `records/<run>__<slug>.json` and `runs/<run>__<slug>/ui/`. The latter is a full static dashboard build plus run data, about 13 MB uncompressed per run. |
| `live_push.sh` (writer) | `ci/benchmarks/lib/live_push.sh:85-118`, `INTERVAL=300` at `:32` | Every 5 minutes, per running leg, it clones the branch, replaces `live/<run>__<slug>/`, and commits. |
| `benchmark-history-prune.yml` (writer) | `:34-68` | Deletes old records in a new commit. Its header admits that this "does not reclaim .git object storage". |
| `pages.yml` (reader) | `:84-107` | Clones the tip, copies all of `runs/` into the site, and renders `benchmarks.json`. |
| `site/benchmarks.js` (reader) | `:1`, `:118` | Reads `live/` straight from `raw.githubusercontent.com/skillberry-ai/cap-evolve/benchmark-history`. |

**Measured state:**

- **Commits.** 2,525 in total: 2,326 `live: update …`, 179 `bench: record run …`, 0 prune.
  - By month: Jul 192, Aug 687, Sep 1,185, Oct 1–5 461.
- **Growth.** Cumulative packed size was 18.5 MB on Aug 1, 63.5 MB on Sep 1, 96.2 MB on Oct 1,
  and 100.4 MB on Oct 5.
- **Tip.** 35,277 files and about 1.5 GB uncompressed: `runs/` holds 114 runs and `live/` 13
  directories.
- **Snapshot history.** The live snapshots are "overwritten in place" (`live_push.sh:3-5`), but
  every overwrite is a commit. Git therefore keeps all of them: **19,764 historical `live/`
  blobs, 22.6 MB packed**, none of which anyone will ever read.

**Costs beyond the clone:**

1. **CI cost.** Each live cycle does `git clone --depth 1` of a 1.5 GB tip just to change one
   directory, once per leg every 5 minutes. The `aggregate`, prune and Pages jobs do the same.
   This has already caused one hang (`live_push.sh:122-128`, run 36304767214).
2. **Pages size.** `pages.yml` copies every `runs/` snapshot into the Pages artifact. The latest
   deploy (run 37307873581, 2026-10-05) uploaded a **298 MB compressed** artifact. Uncompressed,
   `runs/` alone is about 1.5 GB, above GitHub's *documented* 1 GB limit for a published Pages
   site. Deploys still succeed today, so the limit is evidently not enforced strictly. This is a
   risk, not a current failure.
3. **No protection.** The `no new branches` ruleset *excludes* `benchmark-history`,
   `skillsbench-history` and `parsec-history`, and the `main` ruleset targets only the default
   branch. So these three branches have no deletion or force-push protection at all.
4. **Public URLs.** `site/benchmarks.js` and docs link to raw URLs on this repo. Moving the data
   must update them (§4.2).

### 2.3 What is on `main`, classified

Classes: **Core** = needed to use or develop cap-evolve. **Harness** = the benchmark regression
suite for core. **Lab** = experiment-specific. **Notes** = internal working notes.

| Path | Files | Class | Coupling (evidence) |
|---|---|---|---|
| `core/`, `dashboard/`, `skills/`, `templates/`, `plugins/`, `.claude-plugin/`, `install.sh` | — | Core | — |
| `capevolve_harbor/`, `capevolve_telemetry/` | 19 | Core (optional packages) | harbor is used by `templates/adapters/harbor/adapter.py:254,393`. Neither package's `tests/` runs in CI (§2.7). |
| `examples/toy_calc`, `examples/toy_skill` | 11 | Core | `ci.yml:150,199-207`; about 20 `core/tests` files |
| `examples/tau2_airline`, `examples/tau2_custom`, `examples/skillsbench` | 248 | Harness / user docs | `run_suite.sh:291,331-337`; `core/tests/test_tau2_*`, `test_ci_tau2_custom_arms.py`; `README.md`, `docs/REPRODUCE_*`. Includes about 4.5 MB of committed run dumps (`examples/tau2_airline/run_*`). |
| `ci/benchmarks/` except `parsec/` | 71 | Harness | `benchmarks.yml`, `ci.yml:73-86`, about 35 `core/tests` files |
| `ci/benchmarks/parsec/` | 12 | **Lab** | Local-only leg, not in `benchmarks.yml`'s BENCHES, and its tasks are internal (`core/tests/test_benchmarks_plan_legs.py:250-258`). That test asserts the directory exists. |
| `third_party/spreadsheetbench/` | 25 | Harness | `run_suite.sh:834,842`; `templates/adapters/spreadsheetbench/adapter.py` |
| `scripts/v4_t2_e1/` (from #495) | 11 | **Lab** | Nothing outside it uses it. It reaches *into* the repo: `adapter.py:71-74` (`parents[4]` on `sys.path`) and `scaffold_projects.py:31-32` (writes to `REPO_ROOT/.capevolve`). |
| `scripts/ccc/` | 8 | **Lab** | Every script assumes `PROJECT_ROOT=$SCRIPT_DIR/../..` (e.g. `run_ccc_parsec.sh:70`). The only inbound link is `docs/how-to/ccc/CCC_PODMAN_SETUP.md`. |
| `docs/how-to/ccc/` | 1 | **Lab** | Moves with `scripts/ccc` |
| `scripts/demo-video/`, `presentation/` | 9 + 12 | Lab (marketing) | macOS-only pipeline. `presentation/` has no inbound references. |
| `scripts/build_skillsbench_site.py`, `scripts/preview-site.sh`, `scripts/tools/` | 5 | Core (site tooling) | `pages.yml:121` |
| `docs/superpowers/` | 9 | Lab (design record) | Three files it is *cited* for no longer exist (§2.9) |
| `docs/experiments/` | 224 (3.3 MB) | Lab | Comments only (`ci.yml:272`) |
| `docs/evidence/` | 8 | Lab | No inbound references |
| `docs/assets/` | 36 (26.8 MB) | Core (media) | `README.md:31-35`, `pages.yml:66-72` |
| `site/` | 454 | Core (site source), but 421 files are **generated** | `site/skillsbench/**` is regenerated on every deploy (`pages.yml:114-123`), yet committed |
| `openshift/` | 10 | Harness (deployment) | `site/harbor-openshift.html` |
| `HANDOFF.md`, `OUTREACH.md`, `.review/` | 3 | **Notes** | `OUTREACH.md:3-4` says of itself "Not part of the project — uncommitted by design" |

### 2.4 Branch hygiene and repository settings

Branch inventory (175 branches; detail in Appendix B):

| State | Count |
|---|---|
| Head of a merged PR, never deleted | **136** |
| Head of a closed, unmerged PR | 17 |
| Head of an open PR | 9 |
| No PR at all | 13 |
| Orphan (no common history with `main`), counted among the above | 16 |

Why so many remain:

- `delete_branch_on_merge` is **false** for the repository.
- `main` allows **squash merges only** (ruleset `main`). A squash-merged branch is never an
  ancestor of `main`, so `git branch --merged` cannot find stale branches. Cleanup has to be
  driven by PR state, as in Appendix B.
- The ruleset `no new branches` blocks creation, update, **deletion** and force-push on every
  branch except `main` and the three history branches, unless the actor is on the bypass list.
  So a contributor who is not on that list cannot delete their own merged branch, even when
  GitHub offers the button.
- Orphan branches have become the team's convention for content that "has no home on `main`".
  The `parsec-history` README says so explicitly, and so do `skillsbench-history`,
  `presentations/*`, `reports/*` and `assets/pr-*-screenshots`. That convention is the direct
  cause of §2.1: **an orphan branch is a separate repository that every clone of this one
  downloads anyway.**

### 2.5 PR #495 (merged 2026-10-04): what it added and two defects

#495 added `scripts/v4_t2_e1/` (adapter, scaffolder, runner, preflight, tests), four
`scripts/ccc/` scripts, `docs/how-to/ccc/CCC_PODMAN_SETUP.md`, six design documents,
`HANDOFF.md`, and a change to `capevolve_harbor/results.py`.

**Defect 1 — `capevolve_harbor` regression (measured).**

- `capevolve_harbor/tests/test_results.py::test_parse_job_dir_reads_cost_tokens` passes at
  `3d06c10^` (43 passed) and fails at `3d06c10` (`assert 0 == 5000`).
- #495 rewrote `_extract_cost_tokens` (`capevolve_harbor/results.py:208-228`) to read harbor's
  nested `stats.*` keys. In doing so it **dropped** the flat `tokens` / `total_tokens` /
  `input_tokens + output_tokens` keys and the `cost` key.
- Any harbor result in the flat shape now reports 0 tokens. That includes this package's own
  fixtures and older harbor builds.
- `capevolve_harbor` is shared code: the swebench harbor adapter template uses it too.
- CI stayed green because **no workflow runs `capevolve_harbor/tests`**. Fix: §4.1 A2.

**Defect 2 — the new tests fail everywhere and nothing runs them (measured).**

- On a clean machine, `pytest scripts/v4_t2_e1/tests` gives **2 failed, 64 passed, 23
  skipped**.
- The 23 skips need `PARSEC_V4N`, which points at an internal parsec checkout.
- The 2 failures (`test_adapter.py:42-55`) test `TASK_ID` handling. The adapter's own docstring
  (`adapter.py:17-22`) says that handling was removed. These tests would fail on the author's
  machine too.
- `ci.yml` runs only `core/tests`, `dashboard/backend/tests` and `ci/benchmarks/lib`, so the
  drift was invisible. Fix: §4.1 A3.

**Whether #495's code belongs here.** Its scripts depend on an internal checkout
(`PARSEC_V4N`), internal task names and a private cluster. They are "Lab" by every criterion in
§3.2. Leaving them on `main` until the lab repo exists is reasonable, as Osher said. Moving them
twice is not, so move them once, in Phase 3.

### 2.6 PR #581 (open): why it conflicts and how to land it safely (validated)

#581's intent is to delete the 6 parsec design documents and `HANDOFF.md` from `main`, now that
#580 has added them to `parsec-history`, and to re-point one comment.

**Why GitHub reports conflicts and a 15-file diff:**

- The branch's merge base with `main` is `8efb1e88` (2026-09-07). It carries the *pre-squash*
  history of #495.
- After #495 was squash-merged, the PR's diff against `main` re-adds 15 files.
- Several of these are **older** than what is on `main` now:

| Path | PR #581 head vs `main` |
|---|---|
| `scripts/v4_t2_e1/common/adapters/adapter.py` | older by 138 changed lines |
| `scripts/ccc/parsec_stack.sh` | older (17 changed lines) |
| `capevolve_harbor/results.py` | older (19 changed lines) |
| `scripts/ccc/run_ccc_parsec_g2.sh` | **missing** (237 lines on `main`) |
| `docs/superpowers/{specs,plans}/2026-09-24-ibm-provider-rename*` | **missing** (not parsec docs; landed on `main` separately) |

Resolving the conflicts with "keep the branch's side", or merging `main` into the branch
carelessly, would revert parsec fixes, delete a runner script, or delete the
IBM-provider-rename design record.

**Safe procedure (validated on a scratch clone).** Only the PR's tip commit `638b373a8` carries
the intended change, so cherry-pick that commit onto current `main`:

```bash
git fetch origin main pull/581/head:pr581
git switch -c chore/move-parsec-docs-to-history-v2 origin/main
git cherry-pick 638b373a8          # one conflict: HANDOFF.md (modify/delete)
git rm HANDOFF.md                  # the PR's intent is to delete it
git cherry-pick --continue
git show --stat HEAD               # expect exactly 7 files: 6 docs + HANDOFF.md deleted,
                                   # 1 line changed in scripts/v4_t2_e1/scaffold_projects.py
git push --force-with-lease origin chore/move-parsec-docs-to-history-v2:chore/move-parsec-docs-to-history
```

**Nothing is lost.** All 6 design documents on `parsec-history` are byte-identical to `main`'s
copies. The `parsec-history` copy of `HANDOFF.md` is the curated one: it adds an archival note
and rewrites links to be branch-relative.

**Push permissions.** The force-push targets a non-`main` branch, so the `no new branches`
ruleset applies: only a bypass actor can update the PR branch. Alternatively, open the result
as a new PR and close #581.

### 2.7 Where scripts and tests live today

| Test directory | Run by CI? | Result in a fresh venv |
|---|---|---|
| `core/tests` | yes (`ci.yml:45-46`) | passes in CI. Locally, 2 tests fail when a `~/.claude/skills` exists, because it outranks the checkout (`cli.py:55-69`; documented in INFRA.md §1.4.5). |
| `dashboard/backend/tests` | yes (`ci.yml:51-52`) | passes |
| `ci/benchmarks/lib` (pytest and `test_*.sh`) | yes (`ci.yml:73-86`) | passes |
| `capevolve_harbor/tests` | **no** | **1 failed, 42 passed**: the #495 regression |
| `capevolve_telemetry/tests` | **no** | **1 failed, 21 passed**: `test_otel_observer.py::test_state_round_trip` needs the `[otel]` extra but does not `importorskip` |
| `scripts/v4_t2_e1/tests` | **no** | **2 failed, 64 passed, 23 skipped** |

The coupling also runs the other way. About 35 `core/tests` files hard-code paths under
`ci/benchmarks/`, and about 20 hard-code `examples/toy_calc`. One test
(`test_benchmarks_plan_legs.py:257-258`) asserts that `ci/benchmarks/parsec/pilot` exists. So
`core/tests` is partly a test suite *for the harness*, and moving the harness requires moving
those tests with it.

**Pattern.** Every test directory that CI does not run is currently broken. The rule in §3.2
("on `main` ⇒ run by CI") follows directly from this.

### 2.8 How core can be extended today (the "plugins?" question)

| Extension | Can it live in another repo today? | Evidence |
|---|---|---|
| **Adapter** (`adapters/adapter.py` in a project) | **Yes** | `check.py:69-89` loads `<project>/adapters/adapter.py` from wherever `--project` points. It only needs `import cap_evolve`. |
| **Benchmark project** (`capevolve.yaml`, `split_ids.json`, seed) | Yes | Located by `--project` and `--spec` |
| **Skill** (algorithm, capability, phase, intervention, memory) | **Not without copying** | `_find_skills_dir()` (`cli.py:55-69`) returns the *first* existing directory, and `_resolve_skills()` (`cli.py:405-410`) reads exactly one `_registry/manifest.json`. Children receive one `CAPEVOLVE_SKILLS_DIR` (`skills/algorithms/agent-optimize/scripts/host.py:1027-1034`). |
| Optimizer row | Single file | `skills/optimizers/registry.yaml`. `CAPEVOLVE_OPTIMIZER_REGISTRY` names one file. |
| New algorithm or intervention name | **Needs a core edit** | `branding.ALGORITHMS` (`branding.py:332`) drives `doctor` and `init`. Also `CONVERGENCE_ALGORITHMS` and `OPTIMIZER_CONTEXT_ALGORITHMS` (`cli.py:379,387`), and `intervention.KNOWN` (`intervention.py:36`). |
| Observer backend | Needs a core edit | `capevolve_telemetry/config.py:35-70` hard-codes `mlflow` and `otel` |
| Claude Code plugin | Yes | `.claude-plugin/marketplace.json` can list more plugins, including ones in another repo. But core never reads a plugin's skill directory, so such skills are visible to the *host* and invisible to `cap-evolve run`. |
| A released, pinned core | **No release since `v0.1.0`** (2026-07-27) | Not on PyPI. `skills/` and `templates/` are not in the wheel (`core/pyproject.toml`; `harness.py:3231-3232`). Several lookups resolve relative to the source tree: `harness.py:2295,2346,2379,3211,3285,3319`. |

**Conclusion.** "Plugins" is the right model for *skills and adapters* contributed from
elsewhere. Core is two small changes away from supporting it (§4.5). A separate consumer repo
also needs **a version of core to pin**, and today only one tag exists.

### 2.9 Content that should not be on a public `main`

`skillberry-ai/cap-evolve` is **public, with 17 forks**.

- **User-specific absolute paths:**
  - `/Users/boazc/…` and `/dccstor/knewedge2/boazc` in `HANDOFF.md:14-31,195`,
    `docs/superpowers/plans/2026-09-17-*` and `2026-09-23-*`, and
    `docs/superpowers/specs/2026-09-22-*:85`;
  - `/Users/eranra` in `docs/superpowers/plans/2026-09-24-*:26`;
  - `/Users/osherelhadad` in `examples/tau2_airline/run_agentopt_v{2,3,4}/events.jsonl:4`.
- **Internal content:**
  - `ci/benchmarks/parsec` and `scripts/v4_t2_e1` name internal Red Hat/IBM task sets and
    simulators. The repo's own test calls them "internal Red Hat" (`test_benchmarks_plan_legs.py:252`).
  - `parsec-history` holds their results.
  - **The team should confirm that this is cleared for publication.** Moving it to another repo
    does not remove it from this repo's history or from existing forks.
- **Notes that say they should not be committed:** `OUTREACH.md:3-4`, `HANDOFF.md`, and
  `.review/postmerge-algos.md` (a one-off review).
- **Dangling references to deleted design documents:**
  - `docs/superpowers/specs/2026-07-29-live-benchmark-monitoring-design.md` (cited at
    `live_push.sh:6`);
  - `…-persist-capevolve-ui-ci-benchmarks-design.md` (cited at
    `benchmark-history-prune.yml:4`);
  - `docs/superpowers/plans/2026-09-30-issue-606-reader-profile-experiment.md`.

  The two 07-29 specs were deleted in #183 (2026-08-04).

---

## 3. Target structure

### 3.1 Three repositories, three jobs

```
skillberry-ai/cap-evolve               the product + its regression harness      (clone: ~51 MB, ~10 MB if history is rewritten)
  core/ dashboard/ skills/ templates/ plugins/ .claude-plugin/ install.sh
  capevolve_harbor/ capevolve_telemetry/
  examples/{toy_calc,toy_skill,tau2_airline,tau2_custom,skillsbench}   (run dumps removed)
  ci/ (benchmarks harness for PUBLIC benches) third_party/ openshift/
  docs/ (user + contributor docs only)   site/ (source only; generated parts built at deploy)
        │
        │  pins a tagged release (pip "git+…@vX.Y.Z#subdirectory=core" + shallow checkout for skills/)
        ▼
skillberry-ai/cap-evolve-lab           experiments and their written record
  parsec/            ← ci/benchmarks/parsec, scripts/v4_t2_e1, scripts/ccc, docs/how-to/ccc
  skillsbench/       ← skillsbench-history (as a directory, not an orphan branch)
  history/parsec/    ← parsec-history (as a directory)
  design/            ← docs/superpowers/**, HANDOFF.md
  experiments/       ← docs/experiments/**, docs/evidence/**
  presentations/     ← presentation/, presentations/* and reports/* orphan branches
  media/             ← scripts/demo-video/
  skills/ (optional) lab-only skills, layered into a cap-evolve install (§4.5 E1)

skillberry-ai/cap-evolve-bench-data    machine-written benchmark data (CI is the only writer)
  records/ runs/     ← benchmark-history (tip only; history compacted)
  branches live-<run>__<slug>          one single-commit branch per running leg, deleted at the end
```

**Why not one repo with plugins inside it?** The clone problem is about bytes in history, and
the content does not change that. Any directory or orphan branch in this repo is downloaded by
every clone, whatever it is called.

**Why not two repos (code plus everything else)?** The data and the lab content have different
writers and lifetimes:

- the data is machine-written every 5 minutes, needs no review, and can be compacted freely;
- the lab content is human-written, reviewed, and must keep its history.

Mixing them recreates §2.2 inside the lab repo.

### 3.2 Rules for where things go

These rules are proposed for `CONTRIBUTING.md`, with a short pointer in `CLAUDE.md` and
`.bob/rules/01-cap-evolve.md`, so that human and agent contributors apply the same ones.

1. **`main` of cap-evolve holds what a user or contributor of cap-evolve needs.** That means
   code that ships or tests what ships, the public benchmark harness, and user and contributor
   docs. If removing a file would not break a user, a contributor, CI or the public site, it
   belongs elsewhere.
2. **Anything on `main` that has tests has those tests run by CI.** A test directory that no
   workflow runs is deleted or moved. Every test directory not run by CI is broken today (§2.7).
3. **Tests sit next to the code they test.** A package keeps `<pkg>/tests/`. Experiment scripts
   keep their tests in the lab repo, beside the scripts. `core/tests` tests core; harness tests
   live under `ci/benchmarks/**/tests` (§4.3 C6).
4. **No orphan branches for content.** History, results, decks, screenshots and reports go to
   the lab repo, or to the data repo if CI writes them. PR screenshots go into the PR
   description, or into the lab repo if they must be kept.
5. **No machine-specific paths, no session handoffs, no personal notes on `main`.** Use
   environment variables (as `PARSEC_V4N` already does) and keep notes in the lab repo or
   outside git.
6. **Binary media over 1 MB goes into a GitHub release asset**, not into the tree (§4.4).
7. **Generated output is either committed and checked by CI, or built at deploy time — never
   both.** `dashboard/frontend/dist` is the first kind (`ci.yml:116-129`). `site/skillsbench/**`
   currently sits in both and must become the second kind (§4.4 D2).

### 3.3 How the lab attaches to core: consumer and plugin, not submodule

| Mechanism | Verdict | Reason |
|---|---|---|
| Lab **pins a core release** (`cap-evolve-core @ git+https://github.com/skillberry-ai/cap-evolve@vX.Y.Z#subdirectory=core`, plus a shallow `--branch vX.Y.Z` checkout for `skills/` and `templates/` until they ship in the wheel) | **Recommended** | This is how real users consume cap-evolve. It forces core to have releases (§4.5 E6), and an experiment stays reproducible against the exact core it ran on. |
| Lab contributes **skills** by layering them into the installed skills root (`install.sh --with <lab>/skills`, §4.5 E1) | **Recommended**, when the lab has skills | Keeps core's single-root contract (`cli.py:55-69`, `host.py:1027-1034`), so nothing downstream changes. |
| Lab contributes **adapters and projects** | Works today | Adapters are loaded from the project directory (`check.py:69-89`) |
| git **submodule** of core inside the lab | Not recommended | Pins by SHA with no release semantics. Every lab clone pulls core's 48 MB again. |
| git **subtree** in either direction | Not recommended | INFRA.md §2.5 shows what this did to skillberry-store: drift in both directions, with maintainer-only split and push. |
| Lab code under `cap-evolve/plugins/<x>` | Not recommended | Fixes nothing about the clone (§3.1) |

### 3.4 What deliberately stays: the benchmark harness

Osher's list included "benchmarks". This document recommends moving the benchmark **data** and
the **internal** benchmark (parsec) now, but **keeping the public benchmark harness**
(`ci/benchmarks/` without `parsec/`, plus `benchmarks.yml`) in cap-evolve for now. The
reasons:

- **It is core's regression suite.** It is dispatched against PRs of this repo through
  `benchmark-<tier>-<bench>` labels (`benchmarks.yml`; INFRA.md W6). Moving it makes every
  core PR's benchmark a cross-repo dispatch, which needs a token with write access to both
  repos.
- **Core's tests depend on it.** About 35 `core/tests` files test harness code by path (§2.7).
  They would have to move first.
- **It is small:** about 0.2 MB packed. Moving it does nothing for clone time.

Revisit this after Phase 4 (§5), once core has tagged releases. At that point a
`cap-evolve-benchmarks` repo can pin core like any consumer, and core PRs can request runs
through `repository_dispatch`.

---

## 4. Proposed changes

Each item lists what to change, where, and how to verify it. Code is shown as diffs against
`6af27e2`.

### 4.1 Immediate (no new repositories needed)

**A1 — Land #581 by cherry-pick.** Follow the procedure in §2.6. Before pushing, check:

```bash
git grep -n 'HANDOFF.md\|superpowers/plans/2026-09-17\|superpowers/plans/2026-09-23'
```

The only expected hit is the re-pointed comment at `scripts/v4_t2_e1/scaffold_projects.py:88`.

**A2 — Fix the `capevolve_harbor` regression from #495** (validated: 44 passed, including the
new test).

```diff
--- a/capevolve_harbor/results.py
+++ b/capevolve_harbor/results.py
@@ def _extract_cost_tokens(result_path: Path) -> tuple[float, int]:
         data = json.loads(result_path.read_text(encoding="utf-8"))
         stats = data.get("stats") or {}
-        cost = float(stats.get("cost_usd") or data.get("cost_usd") or 0)
+        cost = float(stats.get("cost_usd") or data.get("cost_usd") or data.get("cost") or 0)
         tokens = int(
             (stats.get("n_input_tokens") or 0)
             + (stats.get("n_output_tokens") or 0)
             + (stats.get("n_cache_tokens") or 0)
+            # Older harbor builds (and this package's own fixtures) write flat keys.
+            or data.get("tokens")
+            or data.get("total_tokens")
+            or (data.get("input_tokens") or 0) + (data.get("output_tokens") or 0)
+            or 0
         )
```

```diff
--- a/capevolve_harbor/tests/test_results.py
+++ b/capevolve_harbor/tests/test_results.py
@@ (append)
+
+
+def test_parse_job_dir_reads_nested_stats(tmp_path):
+    t = tmp_path / "task-009__x"
+    t.mkdir()
+    (t / "result.json").write_text(json.dumps({"stats": {
+        "cost_usd": 0.25, "n_input_tokens": 100, "n_output_tokens": 20, "n_cache_tokens": 5}}))
+    from capevolve_harbor.results import _extract_cost_tokens
+    assert _extract_cost_tokens(t / "result.json") == (0.25, 125)
```

**A3 — Make `scripts/v4_t2_e1/tests` truthful.** Delete the two tests of the removed `TASK_ID`
behaviour, and test what the constructor does now (`adapter.py:228-238`):

```diff
--- a/scripts/v4_t2_e1/tests/test_adapter.py
+++ b/scripts/v4_t2_e1/tests/test_adapter.py
 class TestAdapterTaskResolution(unittest.TestCase):
-    def test_raises_clearly_when_task_id_unset(self):
-        with patch.dict(os.environ, {}, clear=True):
-            with self.assertRaises(RuntimeError) as ctx:
-                adapter_mod.Adapter()
-            self.assertIn("TASK_ID", str(ctx.exception))
-
-    def test_raises_clearly_when_task_dir_missing(self):
-        ...
+    def test_raises_clearly_when_parsec_v4n_unset(self):
+        with patch.object(adapter_mod, "V4N", None):
+            with self.assertRaises(RuntimeError) as ctx:
+                adapter_mod.Adapter()
+            self.assertIn("PARSEC_V4N", str(ctx.exception))
```

These tests move to the lab repo in Phase 3, which runs them in its own CI (§4.3 C5). Until
then, A4 covers them.

**A4 — Run every test directory on `main` in CI.** In `ci.yml`'s `test-python` job, after the
dashboard step (`ci.yml:51-52`):

```diff
       - name: Run pytest (dashboard backend)
         run: python -m pytest dashboard/backend/tests -q
+
+      - name: Run pytest (capevolve_harbor, capevolve_telemetry)
+        run: |
+          pip install -e ./capevolve_harbor -e "./capevolve_telemetry"
+          python -m pytest capevolve_harbor/tests capevolve_telemetry/tests -q
+
+      # Lab scripts that still live on main (moved out in Phase 3). Tests that need the
+      # internal parsec checkout skip themselves when PARSEC_V4N is unset.
+      - name: Run pytest (scripts/v4_t2_e1)
+        run: python -m pytest scripts/v4_t2_e1/tests -q
```

Also make `capevolve_telemetry/tests/test_otel_observer.py` call
`pytest.importorskip("opentelemetry")`. Alternatively, install `./capevolve_telemetry[all]`
above. Then update the job list in `ci.yml`'s header comment, which already miscounts its jobs
(INFRA.md W5).

**A5 — Repository settings and branch cleanup.** These need a repository admin.

1. Turn on **"Automatically delete head branches"**:
   `gh api -X PATCH repos/skillberry-ai/cap-evolve -f delete_branch_on_merge=true`.
2. Add the *GitHub* deletion path to the `no new branches` ruleset's bypass, or drop `deletion`
   from that ruleset's rules. Otherwise contributors cannot clean up after themselves.
3. Protect the history branches until Phase 2 retires them. Add a ruleset that targets
   `benchmark-history`, `skillsbench-history` and `parsec-history`, with `deletion` and
   `non_fast_forward` rules, and bypass only for the bot or app that writes them.
4. Delete the 136 merged and 17 closed-unmerged PR branches. Script it from PR state, because
   squash merges defeat `--merged`:

   ```bash
   gh pr list -R skillberry-ai/cap-evolve --state merged --limit 1000 --json headRefName \
     --jq '.[].headRefName' | sort -u > /tmp/merged.txt
   git ls-remote --heads origin | awk '{sub("refs/heads/","",$2); print $2}' | sort > /tmp/remote.txt
   comm -12 /tmp/merged.txt /tmp/remote.txt \
     | grep -vxE 'main|benchmark-history|skillsbench-history|parsec-history' \
     | tee /tmp/to-delete.txt          # REVIEW THIS LIST before the next line
   xargs -n 20 git push origin --delete < /tmp/to-delete.txt
   ```

   Treat the 13 no-PR branches individually, as Appendix B lists them. As §2.1 shows, this step
   barely changes clone size. Its value is that the branch list becomes meaningful again.

**A6 — Tell people how to clone now.** Until Phase 2 lands, add this to `README.md` and
`CONTRIBUTING.md`:

```bash
git clone --single-branch https://github.com/skillberry-ai/cap-evolve   # 50 MB instead of 159 MB
```

**A7 — Delete notes that say they should not be committed:** `OUTREACH.md` and
`.review/postmerge-algos.md`. (`HANDOFF.md` goes with A1.) Fix the three dangling design-doc
references from §2.9 by removing the citations, or by pointing them at the lab repo once it
exists.

### 4.2 Move benchmark data out (the clone fix)

**B1 — Create `skillberry-ai/cap-evolve-bench-data`** (placeholder name) and seed it with the
**tip** of `benchmark-history` as a single root commit. The 2,525-commit history is not worth
keeping: records are cumulative in the tip, and every commit was machine-written.

```bash
git clone --depth 1 --branch benchmark-history https://github.com/skillberry-ai/cap-evolve bh
cd bh && rm -rf live                     # live/ moves to per-run branches (B4)
git checkout --orphan main && git add -A && git commit -m "seed from cap-evolve benchmark-history @ $(git rev-parse --short HEAD@{1})"
git push https://github.com/skillberry-ai/cap-evolve-bench-data main
```

Keep `benchmark-history` read-only in cap-evolve until B8.

**B2 — Credentials.** `github.token` cannot write to another repository. Use a GitHub App that
is installed on the data repo only, through `actions/create-github-app-token`, in the three
writers: `benchmarks.yml` `bench` and `aggregate`, and `benchmark-history-prune.yml`. Store the
app's ID and key as `BENCH_DATA_APP_ID` and `BENCH_DATA_APP_KEY`. Do not reuse
`SKILLBERRY_BOT_TOKEN`: it has write access to *this* repo, and INFRA.md §3.8 already flags how
widely secrets are inherited.

**B3 — One variable for the location.** Add the repository variable
`BENCH_DATA_REPO=skillberry-ai/cap-evolve-bench-data` and use it everywhere.

`benchmarks.yml`, `aggregate` job (`:847-868`). The blobless sparse clone (B5) also goes here:

```diff
+      - uses: actions/create-github-app-token@v1
+        id: data-token
+        with:
+          app-id: ${{ secrets.BENCH_DATA_APP_ID }}
+          private-key: ${{ secrets.BENCH_DATA_APP_KEY }}
+          owner: ${{ github.repository_owner }}
+          repositories: cap-evolve-bench-data      # the data repo's name (placeholder)
       - name: Push to benchmark-history (single writer, with rebase-retry)
         run: |
           ...
           for attempt in 1 2 3 4 5; do
             rm -rf _hist
-            git clone --depth 1 --branch benchmark-history \
-              "https://x-access-token:${{ github.token }}@github.com/${{ github.repository }}.git" _hist || {
+            git clone --depth 1 --filter=blob:none --no-checkout \
+              "https://x-access-token:${{ steps.data-token.outputs.token }}@github.com/${{ vars.BENCH_DATA_REPO }}.git" _hist || {
                 echo "branch missing — bootstrap it per ci/benchmarks/README.md"; exit 1; }
+            git -C _hist sparse-checkout set --no-cone /records/ && git -C _hist checkout -q
             mkdir -p _hist/records
             ...
             cd _hist
-            git add records
-            [ -d runs ] && git add runs
+            git add --sparse records
+            [ -d runs ] && git add --sparse runs
             git commit -m "bench: record run ${{ github.run_id }}" || { echo "nothing to commit"; exit 0; }
-            if git push origin benchmark-history; then echo "pushed"; exit 0; fi
+            if git push origin HEAD; then echo "pushed"; exit 0; fi
```

Make the same three substitutions (token, URL, `push origin HEAD`) in
`benchmark-history-prune.yml:40-64`.

`pages.yml:91-92`. This is a read, so it needs no token while the data repo is public:

```diff
-          if ! git clone --depth 1 --branch benchmark-history \
-              "https://github.com/${{ github.repository }}.git" _bench_history; then
+          if ! git clone --depth 1 \
+              "https://github.com/${{ vars.BENCH_DATA_REPO }}.git" _bench_history; then
```

Also update `site/benchmarks.js:1` (see B4), `ci/benchmarks/README.md:367-421` (bootstrap),
`ci/benchmarks/PUBLISHING.md:130-199` (the manual path), `ci/benchmarks/utils/rebuild_record.py`
and the references listed in §2.3. Run `git grep -n benchmark-history` before and after; the
only remaining hits should be historical (`CHANGELOG.md`).

**B4 — Live snapshots: one single-commit branch per running leg** (validated, including two
concurrent writers).

- Each poller owns its own branch, `live-<run_id>__<slug>`, in the data repo.
- Every cycle it builds a **fresh one-commit tree** and force-pushes it.
- This removes the 1.5 GB clone per cycle, the push races between pollers (each has a
  different branch), and the history accumulation (the branch always has exactly one commit).
- `--cleanup` deletes the branch.

```diff
--- a/ci/benchmarks/lib/live_push.sh
+++ b/ci/benchmarks/lib/live_push.sh
 remote_url() {
-  echo "${LIVE_REMOTE:-https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git}"
+  echo "${LIVE_REMOTE:-https://x-access-token:${GH_TOKEN}@github.com/${BENCH_DATA_REPO:?}.git}"
 }
@@
-# Clone benchmark-history, replace live/<slug_dir> in one commit, push. ...
+# Publish <src> as the ONLY commit of branch live-<slug_dir> on the data repo (force-push).
+# One branch per poller => no races with other legs, no clone, no history kept.
 push_live() {
   local src="$1" slug_dir="$2" clone_dir="${RUNNER_TEMP:-/tmp}/_live_hist_$$"
+  local ref="refs/heads/live-$slug_dir"
   for attempt in $(seq 1 "$ATTEMPTS"); do
     rm -rf "$clone_dir"
-    if ! git_bounded clone --depth 1 --branch benchmark-history "$(remote_url)" "$clone_dir" 2>/dev/null; then
-      ...
-    fi
-    (
-      cd "$clone_dir" || exit 1
-      mkdir -p live
-      rm -rf "live/$slug_dir"
-      if [ -n "$src" ]; then
-        mkdir -p "live/$slug_dir/data"
-        cp -R "$src/." "live/$slug_dir/data/"
-      fi
-      git_bounded add -A live
-      ...
-      git_bounded commit -m "live: update $slug_dir" -q || exit 0
-      git_bounded push origin benchmark-history
-    )
+    (
+      if [ -z "$src" ]; then             # cleanup: drop the branch
+        git_bounded push "$(remote_url)" --delete "$ref" 2>/dev/null || true; exit 0
+      fi
+      mkdir -p "$clone_dir/data" && cd "$clone_dir" || exit 1
+      cp -R "$src/." data/
+      git_bounded init -q
+      git_bounded add -A data
+      git_bounded -c user.name=skillberry-bot -c user.email=actions@github.com \
+        commit -q -m "live: $slug_dir"
+      git_bounded push --force "$(remote_url)" "HEAD:$ref"
+    )
```

The poller's step in `benchmarks.yml:593,615` exports `BENCH_DATA_REPO` and the app token in
place of `GH_TOKEN: ${{ github.token }}`. The reader changes once:

```diff
--- a/site/benchmarks.js
+++ b/site/benchmarks.js
-const RAW = "https://raw.githubusercontent.com/skillberry-ai/cap-evolve/benchmark-history";
+const RAW = "https://raw.githubusercontent.com/skillberry-ai/cap-evolve-bench-data";
@@
-    const dataBase = encodeURIComponent(`${RAW}/live/${it.runId}__${it.tier}-${it.bench}/data`);
+    const dataBase = encodeURIComponent(`${RAW}/live-${it.runId}__${it.tier}-${it.bench}/data`);
```

Before relying on this, update `core/tests/test_live_push_cleanup_is_bounded.py` and the
`ci/benchmarks/lib/test_*.sh` tests that exercise `live_push.sh`. In those tests,
`LIVE_REMOTE=file://…` keeps working unchanged.

A stale-branch sweep is needed for legs that die without cleanup. Add a daily step that
deletes `live-*` branches whose run is no longer `in_progress`, using
`gh run view <run_id> --json status`.

**B5 — Stop downloading the tip to append a record** (validated). The sparse blobless clone in
the B3 diff checks out `records/` only.

| Measure | Sparse blobless clone | Today |
|---|---|---|
| Clone plus checkout time | 0.35 s | depth-1 clone of the tip |
| On disk | 7.8 MB `.git` + 4 MB worktree | about 1.5 GB |

The validation pushed new files into `records/` and `runs/` with `git add --sparse` and kept
all 35,277 existing files.

**B6 — Keep the data repo small.** Prune already deletes old records (`benchmark-history-prune.yml`).
Make it also **compact history**: commit the current tree as a new root and force-push it. In
the data repo this is safe, because CI is the only writer and the history has no value. Grant
the force-push bypass to the app only.

```bash
git checkout --orphan compacted && git commit -qm "compact @ $(date -u +%F)" && git push --force origin compacted:main
```

**B7 — Bound the Pages artifact.** Do not copy every historical `runs/<id>/ui` into the site.
Either:

- serve snapshots straight from the data repo, the way `live/` is already served from raw URLs;
  the dashboard shell takes `?dataBase=`, as at `site/benchmarks.js:118`; or
- copy only the last *N* runs per tier and bench into the artifact.

Either option keeps the site well under the documented 1 GB limit (§2.2).

**B8 — Retire the branches in cap-evolve.** Do this after B1–B7 have run green for one full
benchmark cycle, and after every reader has been switched:

1. Delete `benchmark-history`, `bench-history/add-report-url` and `skillsbench-history` (the
   last one after C2).
2. Delete the other 13 orphan branches once their content has moved (C2).
3. Remove the history branches from the `no new branches` exclusion list.

GitHub repacks on its own schedule. Clones made after that fetch about 51 MB (measured with the
current code branches) instead of 159 MB. Objects that are still referenced by `refs/pull/*`
stay on GitHub's side, but default clones never fetch them.

### 4.3 Create the lab repository

**C1 — Contents** (from §2.3):

- `ci/benchmarks/parsec/`
- `scripts/v4_t2_e1/`
- `scripts/ccc/`
- `docs/how-to/ccc/`
- `docs/superpowers/**`
- `docs/experiments/**`
- `docs/evidence/**`
- `presentation/`
- `scripts/demo-video/`
- the content of these orphan branches: `parsec-history`, `skillsbench-history`, `presentations/*`,
  `reports/*`, `add-v4-g2-reward-heatmap`, `v4-t4-e2-and-overall-mean`,
  `docs/v4_g2_e1-add-hours-column`, `parsec-v4/t4-g3-merge`, and the `parsec-history-*`
  branches (several are heads of open PRs into `parsec-history`; merge or close those first).

**C2 — Migrate with history, for the human-written content.** Use `git filter-repo` on a fresh
clone, once per source:

```bash
# Run from an empty working directory. Each source is a separate clone; filter-repo rewrites it.
# main-side paths, history kept, re-rooted under parsec/ etc.
git clone --single-branch https://github.com/skillberry-ai/cap-evolve lab-src
git -C lab-src filter-repo \
  --path ci/benchmarks/parsec/ --path scripts/v4_t2_e1/ --path scripts/ccc/ --path docs/how-to/ccc/ \
  --path docs/superpowers/ --path docs/experiments/ --path docs/evidence/ \
  --path presentation/ --path scripts/demo-video/ \
  --path-rename ci/benchmarks/parsec/:parsec/bench/ \
  --path-rename scripts/v4_t2_e1/:parsec/v4_t2_e1/ \
  --path-rename scripts/ccc/:parsec/ccc/ \
  --path-rename docs/how-to/ccc/:parsec/docs/ \
  --path-rename docs/superpowers/:design/ \
  --path-rename docs/experiments/:experiments/ --path-rename docs/evidence/:experiments/evidence/ \
  --path-rename presentation/:presentations/deck/ --path-rename scripts/demo-video/:media/demo-video/
# each orphan branch: --to-subdirectory-filter, then merge with --allow-unrelated-histories
git clone --single-branch --branch parsec-history https://github.com/skillberry-ai/cap-evolve ph
(cd ph && git filter-repo --to-subdirectory-filter history/parsec)
git -C lab-src pull --allow-unrelated-histories ../ph parsec-history
```

Then, in cap-evolve, **one PR** removes those paths from `main`, updates `.gitignore:35-36,60`
and `ci.yml:272,279` (codespell and comment references), and removes `ci/benchmarks/parsec`
from `core/tests/test_benchmarks_plan_legs.py:257-258`. The asserted list becomes
`["spreadsheetbench", "swebench"]`. The test's docstring at `:250-255` already anticipates
this.

**C3 — Code changes in the moved files.** They currently find core by walking up the source
tree. In the lab they get core from the pinned install instead:

| File | Today | In the lab |
|---|---|---|
| `scripts/v4_t2_e1/common/adapters/adapter.py:71-74` | puts `parents[4]` (cap-evolve root) on `sys.path` for `cap_evolve` and `capevolve_harbor` | delete the block. Both come from `pip install` (C4). |
| `scripts/v4_t2_e1/tests/test_adapter.py:24` | `parents[3]/"core"` on `sys.path` | delete it, same reason |
| `scripts/v4_t2_e1/preflight_check.py:20-21` | `REPO_ROOT/core` | `importlib.util.find_spec("cap_evolve")` |
| `scripts/v4_t2_e1/run_one_task.py:53-54`, `scaffold_projects.py:31-32` | write projects to `REPO_ROOT/.capevolve` | write to `$LAB_ROOT/.capevolve` (the lab's own, gitignored) |
| `scripts/ccc/*.sh` (`PROJECT_ROOT=$SCRIPT_DIR/../..`, `CAPEVOLVE_SKILLS_DIR=$PROJECT_ROOT/skills`) | assume the cap-evolve checkout | `CAPEVOLVE_HOME` (the pinned checkout from C4); `CAPEVOLVE_SKILLS_DIR=$CAPEVOLVE_HOME/skills` |
| `scripts/ccc/parsec_stack.sh:64` | points at `scripts/v4_t2_e1/common/parsec_paths.py` | `parsec/v4_t2_e1/common/parsec_paths.py` |

**C4 — How the lab installs core.** Use one script, `lab/bootstrap.sh`, and one pin file,
`CAPEVOLVE_VERSION`:

```bash
#!/usr/bin/env bash
# Install the cap-evolve release this lab is pinned to. CAPEVOLVE_HOME holds the checkout
# (skills/ and templates/ are not in the wheel yet, see cap-evolve docs/CHANGE_CE.md §4.5 E5).
set -euo pipefail
LAB="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VER="$(cat "$LAB/CAPEVOLVE_VERSION")"                 # e.g. v0.2.0
CAPEVOLVE_HOME="${CAPEVOLVE_HOME:-$LAB/.cache/cap-evolve-$VER}"
[ -d "$CAPEVOLVE_HOME/.git" ] || git clone -q --depth 1 --branch "$VER" \
  https://github.com/skillberry-ai/cap-evolve "$CAPEVOLVE_HOME"
pip install -e "$CAPEVOLVE_HOME/core" -e "$CAPEVOLVE_HOME/capevolve_harbor"
bash "$CAPEVOLVE_HOME/install.sh" --dest "$LAB/.cache/skills-$VER" ${LAB_SKILLS:+--with "$LAB/skills"}
echo "export CAPEVOLVE_HOME=$CAPEVOLVE_HOME CAPEVOLVE_SKILLS_DIR=$LAB/.cache/skills-$VER"
```

Until E6 produces tags, pin to a commit SHA by making `CAPEVOLVE_VERSION` a SHA and using
`git fetch --depth 1 origin <sha>`.

**C5 — Lab CI.** A GitHub-hosted job runs `bootstrap.sh` and then `pytest parsec/*/tests`. The
`PARSEC_V4N`-gated tests skip, and the rest must pass, which enforces rule 2 of §3.2. Tests
that need the internal checkout run on the self-hosted runner, by dispatch.

**C6 — Harness tests that live in `core/tests`** (optional; do it with §3.4's revisit). Move the
roughly 35 files that test `ci/benchmarks/**` by path to `ci/benchmarks/tests/`, and run them
from the existing `test-ci-lib` job. `core/tests` then tests core only, and a future move of
the harness carries its tests with it.

### 4.4 Shrink `main`'s tip

These changes speed up shallow and blobless clones immediately: the tip drops from 37 MB to
under 10 MB. They also stop future growth. A full clone of `main` stays about 48 MB unless §4.6
is done.

**D1 — The demo video becomes a release asset.**

1. Attach `cap-evolve-demo.mp4` to a GitHub release, for example a `media-2026-10` pre-release
   or the next version release.
2. Point `README.md:31,35` at the asset URL.
3. In `pages.yml:66-72`, download the asset instead of `cp docs/assets/demo/…`. Keep the
   step's existing "fail loudly if missing" check.
4. Update `scripts/demo-video/README.md:96` to `gh release upload` the result.
5. Remove the file from the tree.

**D2 — `site/skillsbench/**` is generated at deploy, so stop committing it.**

- `pages.yml:111` already says that only `index.html` should be committed, and
  `scripts/build_skillsbench_site.py` rebuilds the rest.
- Delete the other 421 generated files, including the 4.8 MB arXiv PDF; link to
  `arxiv.org/abs/2604.01687` instead.
- Add `site/skillsbench/*` and `!site/skillsbench/index.html` to `.gitignore`.
- The source moves to the lab repo (C1), so `pages.yml:117` clones the lab repo's
  `skillsbench/` directory instead of the `skillsbench-history` branch.

**D3 — Compress screenshots.** These are the PNGs over 300 KB in `docs/assets/screenshots/`,
`docs/assets/demo/dash-fullcolor/` and `site/assets/`. Re-encoding them with `pngquant` or as
WebP typically cuts their size by about two thirds without visible loss. That is an estimate,
not a measurement. Also re-export `docs/assets/cap-evolve-logo.png` (1.9 MB) at the size it is
displayed.

**D4 — Committed run dumps in `examples/`.**

- `examples/tau2_airline/run_*` holds about 4.5 MB across 165 files.
- `core/tests/test_dashboard.py:474` and `test_dashboard_agent_run.py:294,322` read two of them,
  `run_full/ui` and `run_agentopt_v4`. Keep only those, and move the other run dumps to the lab.
- Scrub `/Users/osherelhadad` from `run_agentopt_v{2,3,4}/events.jsonl:4` (§2.9).

### 4.5 Core changes for extensibility

**E1 — `install.sh --with <dir>`, repeatable: layer extra skill roots into one install.** This
keeps core's single-root contract (§2.8), so no Python changes are needed.

```diff
--- a/install.sh
+++ b/install.sh
 #   ./install.sh --link           # symlink instead of copy (dev mode)
+#   ./install.sh --with DIR       # also install the skills under DIR (repeatable), e.g. a
+#                                 # lab repo's skills/; a name clash with core is an error
@@
 LINK=0
+EXTRA=()
@@
     --link) LINK=1; shift;;
+    --with) EXTRA+=("$(cd "$2" && pwd)"); shift 2;;
@@
-  done < <(find "$SRC/$comp" -name meta.yaml -type f 2>/dev/null | sort)
+  done < <(for root in "$SRC" "${EXTRA[@]}"; do
+             find "$root/$comp" -name meta.yaml -type f 2>/dev/null; done | sort)
```

`${EXTRA[@]}` under `set -u` with an empty array needs bash 4.4 or later. macOS's bash 3.2
needs `${EXTRA[@]+"${EXTRA[@]}"}`. The loop body (`cp -R`/`ln -s` into `$DEST/<name>`) is
unchanged, and the existing manifest rebuild and verification (`install.sh:106-142`) then cover
the extra skills too.

**E2 — Duplicate skill names become an error.** `build_manifest.py:108` writes
`manifest["skills"][name] = …`, so a second skill with the same name silently replaces the
first. With E1 that becomes a real hazard:

```diff
--- a/skills/_registry/build_manifest.py
+++ b/skills/_registry/build_manifest.py
         name = str(meta["name"])
+        if name in manifest["skills"]:
+            manifest["errors"].append(
+                f"{skill_dir}: skill name {name!r} already defined at "
+                f"{manifest['skills'][name]['path']}")
+            continue
         fm = read_frontmatter(skill_md) if skill_md.exists() else {}
```

**E3 — One function for "where are skills and templates".** Six call sites resolve
`Path(__file__).resolve().parents[2]` and ignore the resolved skills root:
`harness.py:2295,2346,2379,3211,3285,3319`. Replace them with helpers in one module, such as a
new `core/cap_evolve/paths.py`. The helpers honour `CAPEVOLVE_SKILLS_DIR` and fall back to the
source tree in one place:

```python
def skills_root() -> Path | None:            # the one resolution order, shared with cli.py
    ...                                      # body of cli._find_skills_dir (cli.py:55-69)

def skill_path(*parts: str) -> Path:         # component layout or flat install
    root = skills_root()
    cand = root / Path(*parts) if root else None
    if cand and cand.exists():
        return cand
    flat = root / parts[-1] if root else None   # install.sh copies skills flat ($DEST/<name>)
    return flat if flat and flat.exists() else _SRC / "skills" / Path(*parts)

def template_path(*parts: str) -> Path:      # templates/ until E5 ships them in the wheel
    return _SRC / "templates" / Path(*parts)
```

This also fixes the `~/.claude/skills`-wins defect at the source:

- INFRA.md §1.4.5 records it, and it is why 2 `core/tests` fail on machines that have a
  personal skills install (§2.7).
- Put the checkout first when running from source, *or* have the test `conftest.py` set
  `CAPEVOLVE_SKILLS_DIR` to the repo's `skills/`.
- INFRA.md §4.3's Makefile sketch already does the latter.

**E4 — Derive "known" lists from the manifest, not from code.**

- **Algorithms.** `branding.ALGORITHMS` (`branding.py:332`) should keep only display text. The
  "unknown algorithm" check in `doctor` (`cli.py:1403-1405`) and the choices for `init`
  (`cli.py:1599`) should come from manifest entries with `component: algorithm`.
- **Interventions.** `intervention.KNOWN` (`intervention.py:36`) should accept any manifest
  entry with `component: intervention`. `intervention.py:60-75` already checks the component.
- **Algorithm traits.** `CONVERGENCE_ALGORITHMS` and `OPTIMIZER_CONTEXT_ALGORITHMS`
  (`cli.py:379,387`) become `meta.yaml` fields, such as `supports: [convergence,
  optimizer_context]`, carried into the manifest by `build_manifest.py:108-120`.

E4 is what lets a lab or third-party *algorithm* work without a core PR. It is not needed for
the parsec move, so it can wait.

**E5 — Ship `skills/` and `templates/` with the package.** This lets a consumer use cap-evolve
with `pip install` alone, which is what C4 works around. Either move both under
`core/cap_evolve/_data/` with a symlink back, or add them as setuptools data files. In both
cases E3's helpers become the only place that knows the location. This is a larger change, and
it is also the precondition for publishing to PyPI (INFRA.md W12).

**E6 — Tag releases.** There has been no tag since `v0.1.0` (2026-07-27), and the version is
hand-maintained in six places (INFRA.md W12). The lab pin (C4) needs real tags. A minimal
scheme:

- tag `main` as `v0.2.0` when Phase 2 lands;
- then tag on each user-visible change set;
- with a `release.yml` that checks the six version strings agree.

### 4.6 Optional: rewrite `main`'s history

After §4.4, `main`'s *history* still holds about 37 MB of media and generated files. Removing
it with `git filter-repo` would make a full clone of `main` about **11 MB** (measured estimate:
10.1 MB of other blobs plus 1.2 MB of commits and trees).

**What it costs:**

- Every commit SHA changes. That breaks every open PR (9 today) and every fork (17).
- It breaks links to commits in issues, CHANGELOG entries and benchmark records. Records carry
  `commit_sha` (`benchmarks.yml:709`).
- The `main` ruleset (`non_fast_forward`) has to be lifted temporarily.
- Everyone must re-clone.

**Recommendation.** Do it only if the team decides, under §2.9, that internal content must be
purged from history anyway. In that case, do both purges in one rewrite, during a freeze, after
the open PRs have merged. Otherwise skip it: shallow and blobless clones already deliver most
of the benefit.

---

## 5. Phased plan and exit criteria

| Phase | Items | Effort (estimate) | Exit criterion (measurable) |
|---|---|---|---|
| **1. This week** | A1–A7 | 1 day plus admin clicks | #581 merged as 7 files. `ci.yml` runs all six test directories and they pass. `delete_branch_on_merge=true`. Fewer than 40 branches remain. |
| **2. Data out** | B1–B8, D1, D2 | 3–4 days | Two full benchmark cycles green against `BENCH_DATA_REPO`. Live panel works. `git clone` of cap-evolve is ≤ 55 MB, and `--depth 1` is ≤ 12 MB. No `benchmark-history` hits in `git grep`, except in CHANGELOG. |
| **3. Lab repo** | C1–C5, D3, D4, E1, E2 | 3–5 days | Lab CI green on a pinned SHA. `git grep -n 'parsec\|ccc\|v4_t2_e1'` on cap-evolve returns only harness-agnostic mentions. No orphan branches remain in cap-evolve. |
| **4. Core extensibility and releases** | E3, E6, then E4, E5 | 1–2 weeks, incremental | `v0.2.0` tagged, and the lab pins it. `core/tests` passes with a personal `~/.claude/skills` present. A lab skill installs through `--with` and runs through `cap-evolve run`. |
| **5. Revisit** | §3.4 (harness repo?), §4.6 (history rewrite?) | decision | Recorded decision |

Phases 1 and 2 are independent of each other and can run in parallel. Phase 3 depends on Phase
2 only for D2's new source (`pages.yml`).

---

## 6. Decisions the team needs to make

1. **Repository names and owners** for the data repo and the lab repo. Who owns the lab
   (Boaz), and who owns the data repo (whoever owns `benchmarks.yml`)?
2. **Publication clearance** for parsec content (§2.9). If any of it is not cleared: make the
   lab repo private, and decide whether §4.6's history purge is required.
3. **The benchmark harness** stays in cap-evolve for now (§3.4). Agree, or name the condition
   under which it moves.
4. **The `no new branches` ruleset.** Keep it as it is (bypass-only branch writes), or allow
   contributors to delete their own branches (A5.2)?
5. **The release cadence** that the lab will pin to (E6).
6. **The live-run panel.** Accept the per-run branch design (B4), or drop near-live snapshots
   and show only "running" status plus completed records?

---

## Appendix A — How the numbers were measured

```bash
# Clone timings (2026-10-05, same host, SSH)
git clone --mirror git@github.com:skillberry-ai/cap-evolve ce-clone      # all refs, for analysis
time git clone git@github.com:skillberry-ai/cap-evolve ce-plain           # 31 s, .git 159 MB
time git clone --single-branch …   # 9 s, 50 MB    |  --filter=blob:none …  # 9 s, 44 MB
time git clone --depth 1 …         # 7 s, 39 MB

# Packed size of the union of objects reachable from a ref set
sz(){ git rev-list --objects "$@" | cut -d' ' -f1 \
      | git cat-file --batch-check='%(objectsize:disk)' | awk '{s+=$1} END{printf "%.1f MB\n", s/1048576}'; }
sz main; sz benchmark-history; sz $(orphans); sz $(non-orphan heads) --tags
# orphan = no merge base with main:  git merge-base main "$b" || echo "$b"

# benchmark-history composition and growth
git log --format=%s benchmark-history | awk '/^live: /{l++} /^bench: record/{r++} END{print l, r, NR}'
for d in 2026-08-01 2026-09-01 2026-10-01; do sz $(git rev-list -1 --before=$d benchmark-history); done
git rev-list --objects benchmark-history | awk '$2 ~ /^live\//{print $1}' | sort -u \
  | git cat-file --batch-check='%(objectsize:disk)' | awk '{s+=$1;n++} END{print n, s/1048576}'

# Branch state from PRs (squash merges defeat --merged)
gh pr list -R skillberry-ai/cap-evolve --state all --limit 1000 --json headRefName,state
gh api repos/skillberry-ai/cap-evolve --jq .delete_branch_on_merge          # false
gh api repos/skillberry-ai/cap-evolve/rulesets/<id>                          # 'main', 'no new branches'

# PR #581
git fetch origin pull/581/head:pr581; git merge-base main pr581              # 8efb1e88 (2026-09-07)
git diff --stat main pr581 -- scripts/ccc scripts/v4_t2_e1 capevolve_harbor docs/superpowers
# cherry-pick trial on a scratch clone of main: 1 conflict (HANDOFF.md), 7 files result

# Tests (fresh venv, Python 3.11.2, pip install -e ./core[dev] pytest)
pytest scripts/v4_t2_e1/tests     # 2 failed, 64 passed, 23 skipped
pytest capevolve_harbor/tests     # 1 failed, 42 passed  (43 passed at 3d06c10^)
pytest capevolve_telemetry/tests  # 1 failed, 21 passed  (ModuleNotFoundError: opentelemetry)

# Data-repo write paths (validated on a local bare copy of benchmark-history)
git clone --depth 1 --filter=blob:none --no-checkout --branch benchmark-history file://… sp
git -C sp sparse-checkout set --no-cone /records/ /meta.json; git -C sp checkout   # 0.35 s, 7.8 MB + 4.1 MB
# per-run live branches: init + commit + push --force HEAD:refs/heads/live-<slug>; two writers in parallel
```

## Appendix B — Branch inventory (2026-10-05)

**Orphan branches (16).** All of them move to the lab repo or to the data repo:

- **Data:** `benchmark-history`, `bench-history/add-report-url`
- **Experiment results:** `skillsbench-history`, `parsec-history`, `parsec-history-add-v4-design-docs`,
  `parsec-history-cleanup`, `parsec-v4/t4-g3-merge`, `add-v4-g2-reward-heatmap`,
  `v4-t4-e2-and-overall-mean`, `docs/v4_g2_e1-add-hours-column`
- **Reports and decks:** `presentations/consolidate-v4-decks`, `presentations/v4_g2_improvements`,
  `reports/v4_skillset_variant_comparison`
- **PR screenshots:** `assets/pr-625-screenshots`, `assets/pr-629-screenshots`, `pr-assets/627`

**Branches with no PR (13).** Each needs an owner's decision:

`agent-optimize-retry-mid-session-kill`, `ci_skillberry_benchmarks_tau2`,
`ci_skillberry_benchmarks_tau2_2`, `ci_skillberry_benchmarks_tau2_2_intervention_review`,
`evidence/issue-138-screenshots`, `evidence/pr290-telemetry-screenshots`, `test-rits-x-508`,
`test/skillberry-2-smoke`. The other five in this group are orphan branches already listed
above.

**Delete after review:** the 136 merged-PR and 17 closed-PR head branches. Produce the exact
list with the script in §4.1 A5.4.
