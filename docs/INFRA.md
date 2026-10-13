# cap-evolve infrastructure — current state, and what adopting skillberry-store's build system would mean

| | |
|---|---|
| **Written** | 2026-10-05 |
| **cap-evolve** | `6af27e2` (branch `infra`) |
| **skillberry-store** | `da481ee` (`main`) |
| **skillberry-common (upstream repo)** | `6136693` (`main`) |
| **Scope** | Part 1 describes how cap-evolve is set up, tested, run, benchmarked, deployed and published today. Part 2 describes skillberry-store's Makefile and script system (`skillberry-common/`). Part 3 assesses adopting that system in cap-evolve. Part 4 gives a recommendation. |

How the findings were checked. Every script, workflow and operational document listed here
was read. Anything marked **(verified)** was reproduced on a disposable copy:

- the full cap-evolve test suites were run in a fresh venv;
- skillberry-store's make system was run on a copy of its clone;
- the `make` sketch in §4.3 was run end to end against a copy of this repository;
- CI history was read with `gh run list`.
- a push of the store's `skillberry-common/` to its upstream repository was rehearsed on copies of both (§4.9).

Appendix A lists the commands. File references use `path:line`.

## Contents

- [Part 1 — cap-evolve today](#part-1--cap-evolve-today)
  - [1.1 What the repository builds and ships](#11-what-the-repository-builds-and-ships)
  - [1.2 Toolchain and environments](#12-toolchain-and-environments)
  - [1.3 Workflows](#13-workflows)
  - [1.4 Cross-cutting findings](#14-cross-cutting-findings)
- [Part 2 — skillberry-store's infrastructure](#part-2--skillberry-stores-infrastructure)
- [Part 3 — Assessment: adopting it in cap-evolve](#part-3--assessment-adopting-it-in-cap-evolve)
- [Part 4 — Recommendation](#part-4--recommendation)
  - [4.8 Validation: does the Part 4 solution cover what Parts 1–3 require?](#48-validation-does-the-part-4-solution-cover-what-parts-13-require)
  - [4.9 What changes if skillberry-store's `skillberry-common/` is pushed upstream?](#49-what-changes-if-skillberry-stores-skillberry-common-is-pushed-upstream)
- [Appendix A — How the findings were verified](#appendix-a--how-the-findings-were-verified)

---

# Part 1 — cap-evolve today

The repository has **no task runner**. `git ls-files` finds no Makefile, justfile, tox,
nox, Taskfile or pre-commit configuration. It also has no Python linter or formatter
configuration, no lockfile, and no `.python-version` or `.nvmrc`.

Everything runs through bash scripts, `npm` scripts, Python scripts and inline GitHub
Actions steps. Make appears in one place only: cap-evolve drives other repositories' Makefiles
(skillberry-store, skillberry-agent, skillberry-benchmarks) when it provisions external
stacks; see W7.

## 1.1 What the repository builds and ships

**Core package and CLI**

| Artifact | Source | How it is built or installed | Who uses it | Published? |
|---|---|---|---|---|
| `cap-evolve-core` (CLI `cap-evolve`) | `core/` (setuptools, 40 modules, about 20k lines, **zero runtime dependencies**) | `pip install ./core`. Contributors use `-e ./core[dev]`. | Everyone | No. Not on PyPI. Version `0.1.0` is hard-coded in `core/pyproject.toml:7` and `core/cap_evolve/__init__.py:58`. |

**Dashboard**

| Artifact | Source | How it is built or installed | Who uses it | Published? |
|---|---|---|---|---|
| `capevolve-dashboard` (backend) | `dashboard/backend/` (FastAPI, uvicorn) | `pip install ./dashboard/backend`. It depends on `cap-evolve-core` by name, so core must be installed first. | `cap-evolve dashboard` | No |
| Dashboard SPA | `dashboard/frontend/` (React, Vite, TypeScript) | `npm ci && npm run build`. The output `dist/` (1.1 MB) is **committed**, and the backend serves it from the source tree (`server.py:25-29`). | Backend; `pages.yml`; `benchmarks.yml` | Committed. The CI `build-dashboard` job rebuilds it and fails if the result differs (`ci.yml:113-129`). |

**Auxiliary packages**

| Artifact | Source | How it is built or installed | Who uses it | Published? |
|---|---|---|---|---|
| `capevolve-harbor` | `capevolve_harbor/` | Installed only by `ci_setup.sh:43` | swebench and parsec harbor adapters | No |
| `capevolve-telemetry` | `capevolve_telemetry/` | Extras `mlflow`, `otel`, `all` | The `observers:` block of `capevolve.yaml` | No. Its README tells users to `pip install` it from PyPI, which cannot work. |

**Skills, plugin and templates**

| Artifact | Source | How it is built or installed | Who uses it | Published? |
|---|---|---|---|---|
| Skills library (22 skills, 114 script files) and the registry | `skills/`. The manifest `skills/_registry/manifest.json` is generated and committed. | `install.sh` copies skills into a host's skills directory and rebuilds the manifest. | Coding-agent hosts; `cap-evolve run` | Committed |
| Claude Code plugin | `plugins/cap-evolve/`: a symlink to `skills/` plus 4 hooks | `claude --plugin-dir ./plugins/cap-evolve` | Claude Code | `.claude-plugin/marketplace.json` |
| Templates | `templates/{skill,project,adapters}` | Copied by `intake`, `cap-evolve init` and example scripts | Users | Committed. Not inside the wheel, so they work only from a checkout. |

**Site and benchmark history**

| Artifact | Source | How it is built or installed | Who uses it | Published? |
|---|---|---|---|---|
| Site | `site/`: static, 454 files. `site/skillsbench/` (422 files, 9 MB) is generated **and** committed. | `pages.yml` assembles and deploys it. | Public | GitHub Pages |
| Benchmark history | Orphan branches `benchmark-history` and `skillsbench-history` | Written by the `benchmarks.yml` `aggregate` job | `pages.yml` | Git branches |

**Container images and media**

| Artifact | Source | How it is built or installed | Who uses it | Published? |
|---|---|---|---|---|
| Container images | `openshift/images/cap-evolve-runner/Dockerfile`, `ci/benchmarks/parsec/docker/parsec-agent-base/Dockerfile`, `third_party/spreadsheetbench/code_exec_docker/Dockerfile.*` (never built; the adapter pulls an upstream image) | `podman build` by hand | OpenShift; parsec | **None published.** The OpenShift README uses a placeholder `quay.io/<your-org>`. |
| Demo video and slides | `scripts/demo-video/`, `presentation/` | Manual pipeline that only runs on macOS (`say`, macOS font paths, vhs, ffmpeg) | README, site | The 15.5 MB mp4 is committed. |

## 1.2 Toolchain and environments

| Tool | Required by |
|---|---|
| Python 3.10+ (documented everywhere) | core. CI tests only **3.11** (`ci.yml:37-40`). The benchmark runner uses **3.12** (`ci_setup.sh:24`). tau2-bench needs **>=3.12,<3.14** (`examples/tau2_airline/setup.sh:16,40`), which contradicts `REPRODUCE_tau2.md:42`. The blackbox services use **3.11**. The OpenShift image uses **3.12**. |
| Node 22 | CI only. No doc names a Node version, and `package.json` has no `engines` field. |
| `uv` | Benchmark runner (`ci_setup.sh:23`), skillsbench (`benchflow`), blackbox stack, parsec, CCC |
| Docker | Harbor (swebench, parsec), spreadsheetbench executor, skillsbench sandbox |
| Rootless Podman without subuid | IBM CCC cluster (`scripts/ccc/setup_podman.sh`) |
| `claude` CLI and npm | The default optimizer. `ci_setup.sh:249-259` installs it into `~/.local` if it is missing. |
| `gh` | Arming the self-hosted runner (`ci/benchmarks/runner/arm-runner.sh`) |
| `make` | Only to drive *other* repositories' Makefiles: `blackbox_env.require_make()` (`skills/interventions/llm-proxies/blackbox/scripts/blackbox_env.py:567-601`, issue #573) |
| LSF (`bsub`), `oc`, `vhs`, `ffmpeg`, `say` | CCC batch jobs, OpenShift, demo video |

## 1.3 Workflows

Each workflow below lists who uses it, its entry points, what runs, and how state is cached.

### W1 — First run (zero-API toy)

- **Who:** a new user, and CI (`toy-example` and `install-smoke` jobs).
- **Entry:**
  ```bash
  python3 -m venv .venv && . .venv/bin/activate
  pip install ./core
  bash examples/toy_calc/run.sh
  ```
- **What runs:** `run.sh` sets `PYTHONPATH=$REPO/core`, `CAPEVOLVE_SKILLS_DIR`,
  `CAPEVOLVE_TOY_DATA` and `CAPEVOLVE_MOCK_SCRIPT`. It hand-builds a project in a fresh
  `mktemp -d` and runs `python3 -m cap_evolve.cli run`. The `mock` optimizer adds the `[CALC]`
  marker, so the score goes from 0.0 to 1.0 deterministically.
- **State:** none. Each run uses a new temporary directory.
- **Note:** the same hand-written scaffold appears three times: `run.sh`,
  `ci/e2e_all_algorithms.sh:40-59` and `ci.yml:192-207`. `cap-evolve init` exists but none of
  them use it.

### W2 — Install into a coding-agent host

- **Who:** users of Claude Code, Codex, Gemini, opencode, Bob and other hosts.
- **Entry:** one of
  - `claude --plugin-dir ./plugins/cap-evolve`
  - `./install.sh [--host H | --dest D | --link]`

  followed by `pip install ./core` and pointing the agent at `RUN.md`.
- **What runs:**
  1. `install.sh` resolves a destination: `$CAPEVOLVE_SKILLS_DIR`, then `--host`, then
     `./.claude/skills`, then `~/.claude/skills`, then `~/.capevolve/skills`.
  2. It copies (or, with `--link`, symlinks) every directory that contains a `meta.yaml`.
  3. It copies component-level files such as `optimizers/registry.yaml`.
  4. It rebuilds the manifest for both the source tree and the destination.
  5. It verifies the installed tree and exits 1 if anything is missing (`install.sh:106-142`).
- **CI:** `install-smoke` installs into a fake HOME and runs toy_calc from outside the
  repository.
- **State:** the destination directory, overwritten on every run. It is not versioned, and
  core does not detect a stale install. Core's skills lookup checks `~/.claude/skills` *before*
  the checkout (`core/cap_evolve/cli.py:55-71`), so an old install silently takes precedence.
  This is why every example script exports `CAPEVOLVE_SKILLS_DIR`. It also breaks a core test;
  see §1.4.5.

### W3 — Optimize your own agent (the product's main workflow)

- **Entry:** either let a coding agent follow `RUN.md`, or drive it by hand:
  ```bash
  cap-evolve init
  # implement adapter.py
  cap-evolve check .capevolve/project
  cap-evolve estimate --spec …
  cap-evolve run --spec … --project …
  # inspect with: cap-evolve dashboard | watch | diff --best
  ```
- **What runs:** the pipeline intake → implement-and-check → baseline → algorithm → finalize
  → report. Each candidate is a git commit in the run's store. The run state lives in
  `.capevolve*/` (gitignored), and a fixed `--run-ts` resumes an existing run.
- **Infrastructure needs:** none beyond Python. Real runs need model credentials, set in
  `.env` or the environment (`docs/INSTALL.md:85-92`).

### W4 — Contributor dev loop

- **Who:** human contributors, coding agents (Bob through `.bob/rules/01-cap-evolve.md`), and
  the Bob "fix issue" bot.
- **What runs:** there is no single entry point. Section 1.4.1 shows that six documents give
  six different command sets.
- What CI actually enforces:
  - core and dashboard pytest;
  - the ci-lib tests;
  - frontend build, tests and the `dist/` drift check;
  - toy_calc;
  - install-smoke;
  - lychee link check;
  - CLI-subcommand doc check;
  - skill lint;
  - codespell.
- **State:** the developer's own venv and `dashboard/frontend/node_modules`. Nothing is
  cached or stamped. Each developer decides when to re-run `pip install` and `npm ci`.

### W5 — Always-on CI (GitHub-hosted)

`ci.yml`, triggered on push to `main` and on PRs, takes about 3 minutes in total:

| Job | Steps | Lines |
|---|---|---|
| `test-python` | `pip install -e ./core[dev]` → pytest `core/tests`, then `pip install -e ./dashboard/backend[dev]` → pytest | `:29-52` |
| `test-ci-lib` | pytest `ci/benchmarks/lib`, every `ci/benchmarks/lib/test_*.sh`, and `sync_models.py --validate` | `:54-86` |
| `build-dashboard` | `npm ci`, build, vitest, then fail on `dist/` drift (modified or untracked files) | `:88-129` |
| `toy-example` | `pip install ./core`, toy_calc, assert `test_reward 1.0` | `:131-154` |
| `install-smoke` | `./install.sh --host claude` into a fake HOME, then toy_calc from the install | `:156-214` |
| `docs-links` | lychee in offline mode, plus `ci/check_cli_subcommands.py` | `:216-238` |
| `lint-skills` | `skills/_registry/lint_skills.py skills` (blocking) | `:240-262` |
| `spellcheck` | codespell over README and `docs/` | `:264-280` |

The header comment of `ci.yml` lists 6 jobs, but the file defines 8.

Notes:

- **Nothing is cached.** No `actions/cache`, no setup-python pip cache, no npm cache.
- **Delegated workflows:**
  - `codeql.yml`, `label-new-{issues,prs}.yml` and `{fix-issues,fix-pr-reviews,test-pr}-with-bob.yml`
    call **skillberry-common's reusable workflows at `@main` with `secrets: inherit`**.
  - So cap-evolve already depends on skillberry-common, through GitHub rather than vendored
    files. See §3.8 for the supply-chain implication.
  - The Bob issue-fixer has its own copy of the setup and verify commands
    (`fix-issues-with-bob.yml`, the `setup_command` and `verify_command` inputs). That is
    another place where the CI recipe is duplicated.

### W6 — Benchmark CI (self-hosted, real models, real money)

```
benchmarks.yml (dispatch or `benchmark-<tier>-<bench>` PR label; trust-guarded to OWNER/MEMBER/COLLABORATOR)
  plan      (ubuntu-latest)  selects tier×bench legs, keeping those with a ci/benchmarks/<bench>/<tier>/tasks.json
  bench     ([self-hosted, ibm-vpc], timeout 1440 min, one leg per matrix entry)
    ci_setup.sh <bench>      cached venv + benchmark clones/datasets under $CAPEVOLVE_CI_CACHE; claude CLI;
                             gateway preflight (entitlement, then budget) choosing the provider
                             in order RITS → ibm-ete-int → ibm-ete (resolve_provider.sh, model_catalog.txt)
    live_push.sh             background poller pushing live snapshots
    run_suite.sh <bench>     writes capevolve.yaml from tasks.json + overrides.env, runs `cap-evolve run`,
                             emits metrics.jsonl / steps.jsonl / report.md / optimized/
    export_static            dashboard snapshot;  assert_run.py;  runmeta.json;  upload-artifact;  PR comment
  aggregate (ubuntu-latest)  record.py build → push to benchmark-history (single writer, rebase-retry)
pages.yml (workflow_run: Benchmarks)  folds benchmark-history runs/ + records into the site and redeploys
```

**Related workflows**

| Workflow | Purpose | Runs on | Trigger |
|---|---|---|---|
| `integration-tests.yml` | tau2 task 9, end to end, by dispatch or the `integration-test` label | self-hosted | dispatch or label |
| `sync-model-lists.yml` | Rewrites the model pickers in `benchmarks.yml` from what each gateway key serves, then commits with `SKILLBERRY_BOT_TOKEN` (no doc mentions this token) | self-hosted | cron `7,37 * * * *` |
| `benchmark-history-prune.yml` | Deletes records older than N days | GitHub-hosted | dispatch |

**The runner**

- `arm-runner.sh` registers an ephemeral runner with the label `ibm-vpc` on skillberry-1.
- `ci_setup.sh` is the heaviest piece of infrastructure in the repo. It is explicitly
  idempotent and keeps its state in `$CAPEVOLVE_CI_CACHE` (default `~/.cache/capevolve-ci`),
  **outside the checkout**. The reason is that `actions/checkout` wipes untracked files in the
  workspace (`ci_setup.sh:183`).
- Its caching guards are "does X exist?" checks. For example, `[ -x "$CAPEVOLVE_PY" ] || uv venv`
  at `:24`, and `[ -d "$CACHE/tau2-bench/.git" ] || git clone` at `:152`.

**Manual publishing.** When a CI run does not publish itself, `ci/benchmarks/PUBLISHING.md`
replays the same scripts by hand: `metrics.py`, a hand-written `runmeta.json`, `record.py`, a
push to the branch, and a Pages dispatch.

### W7 — Example reproduction

Examples that need setup: `tau2_airline`, `skillsbench`, `tau2_custom/{direct,blackbox}`.

**Entry:**

```bash
bash examples/<ex>/setup.sh && bash examples/<ex>/run.sh   # also smoke.sh / itest.sh
```

**What runs, in order.** Each step is guarded differently:

1. Create `$REPO/.venv`, only if it is missing.
2. `pip install -e core` and the benchmark, on **every** run.
3. Clone into `vendor/` if missing. tau2-bench is **unpinned** and never updated after the
   first clone. skillberry-benchmarks is pinned, but runs `git fetch --all` on every run.
4. `intake --force`, which **wipes `.capevolve/project`**.
5. `cap-evolve check`.

**Collisions and side effects:**

- Three examples (four scripts: `tau2_airline/setup.sh` and `itest.sh`, `skillsbench/setup.sh`,
  `tau2_custom/direct/setup.sh`) scaffold into the same `.capevolve/project`. Running one
  example's setup destroys another's project. Only blackbox uses a separate directory.
- `tau2_airline/setup.sh:63` writes the clone SHA into the *committed*
  `run_full/TAU2_COMMIT.txt`, which dirties the tree.

**blackbox provisions an external stack through that stack's own Makefiles.**
`blackbox_env.provision()` clones skillberry-store and skillberry-agent at pinned refs, creates
a py3.11 venv for each, and runs `make install-requirements` and `make run` in them. So
cap-evolve is already a downstream consumer of the build system assessed in Part 2. It has
already had to work around three of its hazards:

- `make` missing on a runner (issue #573, `require_make()`);
- a stale `/tmp/<service>-service.pid` sentinel that makes `make run` exit 0 without starting
  anything (`blackbox_env.py:366-371, 796-797`);
- the truncating log redirect in `start-service.sh`, which forces cap-evolve to rotate logs
  itself (`blackbox_env.py:744-760`).

### W8 — Cluster runs (IBM CCC / LSF) and parsec

**Session setup.** `source scripts/ccc/setup_podman.sh` sets up rootless Podman on a host with
no root, no `sudo` and no subuid range:

- `/tmp/podman-$UID` storage;
- a `docker` shim;
- a `podman system service` guarded by a pidfile;
- a patched `ubuntu:24.04` image, guarded by the **hand-versioned stamp**
  `$STORAGE_BASE/.patched-ubuntu24-v7` (`:180`). This is the only hand-written stamp in the
  repo. Changing the recipe requires bumping `-v7` by hand, and the stamp is per host and kept
  in `/tmp`.

**Running.**

- `run_ccc_experiment.sh` and `submit_ccc_experiment.sh` run experiments, the latter as a
  `bsub` wrapper.
- `parsec_stack.sh up|status|down|reap` starts 5 simulator containers plus parsec-live.

**Parsec staging.** This is a 5-stage hand pipeline (`ci/benchmarks/parsec/README.md:193-217`):

1. `patch-harbor-tasks-v2.sh`
2. `bake-aap2-skill.sh`, an **LLM-backed generation that runs again from scratch every time**
3. `start-sims-v2.sh`
4. `patch-harbor-tasks-v2.1.sh`
5. run, then `stop-sims-v2.sh`

The outputs are coupled to `run_suite.sh` by duplicated path literals.

**Task-by-task optimization.** `scripts/v4_t2_e1/` scaffolds 21 projects and uses `final.json`
as a done-marker plus an `fcntl` lock.

### W9 — OpenShift

The deployment is entirely manual:

1. `oc apply` the manifests: namespace, `anyuid` ServiceAccount, PVC, two vLLM Deployments, a
   runner Deployment and a Job.
2. `podman build`/`push` the runner image to a registry of your choice.
3. `oc cp` the project in and the results out.

Problems with the image and the Job:

- The image clones tau2-bench **unpinned at build time**.
- It installs no optimizer CLI, although the manifests assume claude-code.
- The repo has no `.dockerignore`, so the whole repository is sent as build context.
- The Job's fixed `--run-ts run1` resumes the old run on the PVC.

### W10 — Site and documentation publishing

`pages.yml` runs on pushes that touch `site/**`, on dispatch, and after each Benchmarks run. It:

1. copies in the demo mp4;
2. builds a `VITE_STATIC=1` dashboard shell with `npm ci` and vite;
3. clones `benchmark-history` and renders `benchmarks.json` and `meta.json`;
4. clones `skillsbench-history` and renders `site/skillsbench`, after
   `pip install markdown`, an undeclared dependency.

Two gaps:

- `scripts/build_skillsbench_site.py` has a `--check` mode that CI never runs, so the committed
  copy of `site/skillsbench` goes stale silently.
- `scripts/preview-site.sh` serves `site/` but repeats none of the deploy steps, so the video
  returns 404 locally.

### W11 — Demo video and presentation

Manual and macOS-only. Every run of `build.sh` re-encodes every shot. Only `music.py` has a
content cache, and that cache ignores edits to the chord table.

### W12 — Versioning and release

- **One release ever:** `v0.1.0`, on 2026-07-27. Everything since is `[Unreleased]` in
  `CHANGELOG.md`.
- **The version is hand-maintained in six places:**
  - the four `pyproject.toml` files;
  - `core/cap_evolve/__init__.py:58`;
  - `plugins/cap-evolve/.claude-plugin/plugin.json`.

  The frontend is `0.0.0`.
- **Nothing is published.** No workflow publishes to PyPI, a container registry or GitHub
  releases.
- **Provenance is partial.** Benchmark records carry the commit SHA (`benchmarks.yml:709`),
  but runs started locally, on CCC or on OpenShift record no code version at all.

## 1.4 Cross-cutting findings

### 1.4.1 The same recipe, in many divergent copies

**Test and dev commands.** No two sources agree:

| Source | Install | Checks |
|---|---|---|
| `CONTRIBUTING.md:8-11,37` | `pip install -e ./core` (no `[dev]`, so pytest is missing and the openpyxl/pandas tests silently skip) | core pytest, `build_manifest.py`, `compileall`, `lint_skills.py` |
| `.bob/rules/01-cap-evolve.md:35-39` ("the same ones CI runs") | `-e ./core[dev] -e ./dashboard/backend[dev]` | core and dashboard pytest, `lint_skills`, `npm ci && build && test`. Missing: ci-lib, `sync_models`, CLI-docs, lychee, codespell. |
| `.github/PULL_REQUEST_TEMPLATE.md:5-9` | none | core pytest, `build_manifest.py`, each changed skill's `check.py` |
| `.review/postmerge-algos.md:52` | none (`PYTHONPATH=core:dashboard/backend`) | core pytest, toy_calc |
| `fix-issues-with-bob.yml` inputs | `pip install -e ./core[dev] -e ./dashboard/backend[dev] && npm ci` | core and dashboard pytest, `lint_skills`, npm build and test |
| `ci.yml` (the truth) | per job | 8 jobs (W5). `compileall` is never run, and neither is the PR template's `build_manifest.py`. |

**Install commands.** Core is installed in four different ways. The dashboard is installed in
three. The `venv` + core-install block appears in five example scripts, each slightly
different: index URL, pip upgrade, `set -e`. The intake → copy adapter → `cap-evolve check`
block appears in five scripts.

### 1.4.2 Python environments

There are at least nine ways of creating or using a Python environment:

| Approach | Where |
|---|---|
| `python3 -m venv .venv` | examples |
| `uv venv --python 3.12` in a cache directory | `ci_setup.sh` |
| `uv venv -p 3.11 <service>/.venv` + `make install-requirements` | blackbox |
| `uv venv` + `uv pip install -e` | `parsec_bootstrap.sh` |
| `uv run` inside external checkouts | parsec staging |
| `uv tool install` | benchflow, harbor; a stale machine-global core install is detected by the v4 preflight |
| a throwaway venv in `/tmp/vidvenv` | demo video |
| system `pip` | CI, OpenShift image |
| plain `PYTHONPATH=core` or `sys.path.insert` | toy example, e2e, hooks, many utilities |

**One venv per checkout is not true here, and cannot be.** tau2 needs Python 3.12 or later,
the Skillberry services need 3.11, and the benchmark runner keeps one cached venv per arm. This
fact matters for Part 3.

### 1.4.3 Heavy operations: current guards and gaps

| Operation | Where | Current guard | Weakness |
|---|---|---|---|
| Create a venv | examples, `ci_setup.sh:24`, blackbox | Interpreter exists | Not tied to the requested Python version |
| `pip install -e core` (+ benchmark) | every example `setup.sh`, `ci_setup.sh:28` | none (runs every time) | Fast with uv. Slow with pip (about 30 s for dev extras, **(verified)**). |
| tau2-bench clone | `ci_setup.sh:152`, `tau2_airline/setup.sh:57`, `itest.sh:41`, OpenShift Dockerfile | `.git` exists | **Unpinned and frozen at the first clone.** CI, examples and images can run different tau2 code, and nothing records which. |
| skillberry-benchmarks clone | `ci_setup.sh:161`, `tau2_custom/*/setup.sh` | `.git` exists + pinned ref | `git fetch --all` runs every time (network) |
| skillsbench, rfe-creator clones | `ci_setup.sh:212`; `rfe-creator/utils/fetch_data.sh` | `.git` exists; rfe uses fetch + `reset --hard origin/main` every time | Unpinned |
| SpreadsheetBench dataset | `spreadsheetbench/fetch_data.sh` | **`dataset.json` acts as the stamp**; downloads go to a temp dir and then `mv` | The cleanest cache in the repo. Unpinned `main` tarballs, no checksum. |
| Warm the npm cache for in-container claude-code | `ci_setup.sh:69-87` | Runs every time (cheap) | — |
| `npm ci` + vite build | `ci.yml`, `pages.yml`, `benchmarks.yml` aggregate, by hand for `run_full/ui` | none | Three cold installs per change. Locally, the developer remembers. |
| Skillberry stack install | `blackbox_env.provision()` | `.git` exists, `.venv` exists | `make install-requirements` runs every provision |
| Patched ubuntu image (CCC) | `setup_podman.sh:180` | Hand-versioned stamp | Not keyed on the recipe; not reconciled with whether the image exists; per host |
| parsec agent base image | `build-parsec-agent-base.sh` | none | Unpinned `ubi9/ubi:latest` |
| LLM-backed AAP2 skill bake | `bake-aap2-skill.sh` | none (wipe and regenerate) | **Costs real money every run.** The strongest stamp candidate in the repo. |
| Parsec task patchers | `patch-harbor-tasks*.sh` | none (`rm -rf` + recopy) | Cheap, but output paths are duplicated literals |
| Demo assets (TTS, vhs, Playwright, x264) | `scripts/demo-video` | Logo PNGs and music only | Everything else re-renders every run |

### 1.4.4 Generated artifacts that are committed

| Artifact | Freshness check |
|---|---|
| `dashboard/frontend/dist/` | **CI** (`ci.yml:116-129`) |
| `skills/_registry/manifest.json` | none. It is deterministic, and regenerating it at `6af27e2` gives a byte-identical file **(verified)**, so a check would be trivial. |
| `site/skillsbench/**` | none. It is overwritten at deploy time; `--check` exists but is unused. |
| `examples/tau2_airline/run_full/ui/` | none. Its README says it "goes stale silently". |
| `core/cap_evolve/demo_session/` | a test (regenerated byte-for-byte) |
| SpreadsheetBench and SWE-bench `tasks.json` / `split_ids.json` | tests (partly) |
| `examples/tau2_airline/run_full/TAU2_COMMIT.txt` | rewritten by `setup.sh` |

### 1.4.5 Test coverage and hermeticity (verified)

Suites were run in a fresh Python 3.11 venv, as `ci.yml` installs them, on `6af27e2`.

| Suite | Result | In CI? |
|---|---|---|
| `core/tests` (about 3 min) | 1818 passed, 4 skipped, **1 failed** (with `CAPEVOLVE_SKILLS_DIR` pinned). Without the pin, **one more fails** whenever `~/.claude/skills` exists. That is where Claude Code keeps user-level skills, so the directory exists on many contributors' machines. | yes |
| `dashboard/backend/tests` | 42 passed | yes |
| `ci/benchmarks/lib` | 67 passed | yes |
| `capevolve_harbor/tests` | 42 passed, **1 failed** (`test_parse_job_dir_reads_cost_tokens`: tokens `0 != 5000`) | **no** |
| `capevolve_telemetry/tests` | 21 passed, **1 failed** (`ModuleNotFoundError: opentelemetry.sdk`: the test needs the `[otel]` extra and does not `importorskip`) | **no** |
| `scripts/v4_t2_e1/tests` | 64 passed, 23 skipped, **2 failed** (stale `TASK_ID` message assertions) | **no** |

The two `core` failures are both environment-dependent. CI on `main` is green.

1. `test_cli_surface.py::test_spec_defaults_relative_to_project_not_the_cwd` resolves skills
   from `~/.claude/skills` before the checkout (`cli.py:59`). It fails on a developer machine
   and passes on a clean CI HOME.
2. `test_spreadsheetbench_verify_turns.py::test_a_correction_supersedes_the_earlier_answer`
   fails because the adapter's change detector `_artifact_stamp` returns
   `(st_mtime_ns, st_size)` (`templates/adapters/spreadsheetbench/adapter.py:878-891`). Two
   same-size writes within one kernel timestamp tick produce identical stamps. This was
   reproduced on ext4, where two back-to-back writes got the same `mtime_ns`. This is an
   mtime-based stamp failing in exactly the way skillberry's "concept 4" (§2.3) warns about.

**Suites outside CI have quietly broken.** A single `test` entry point that covers every
package would have caught all four of those failures.

### 1.4.6 Defects and documentation drift found while surveying

Ordered roughly by impact. Items 1–7 are fixable in under a day in total.

1. The four failing tests outside CI and the two environment-dependent core tests (§1.4.5).
2. tau2-bench is unpinned and frozen at the first clone, in four places (§1.4.3). Results are
   not reproducible across runners.
3. Reusable workflows run at `@main` with `secrets: inherit` (§3.8).
4. `templates/skill/scripts/_bootstrap.py` (44 lines) has drifted from the 20 byte-identical
   deployed copies (about 82 lines) and lacks the `CAPEVOLVE_CORE`-first and eviction logic.
   New skills inherit the old bug.
5. The plugin hooks find run directories only under `.capevolve/run_*` (`_hooklib.py:64-84`).
   They are silent for `.capevolve-blackbox/` and the parsec `v4_*` layouts.
6. `rfe-creator/utils/fetch_data.sh:44-46` needs PyYAML in the *system* Python, but PyYAML is
   installed only into the CI venv.
7. `tau2_airline/setup.sh` accepts `VENV=…`, but `run.sh:19,21` hard-codes
   `$REPO/.venv/bin/cap-evolve`.
8. **Stale docs:**
   - `docs/INSTALL.md:21` lists 6 CLI subcommands; there are 14.
   - The dispatch table in `ci/benchmarks/README.md:166-175` shows old defaults.
   - `benchmarks.yml` comments say the 10-input dispatch limit is reached, but it has 11 inputs.
   - `REPRODUCE_skillsbench.md:74` says setup installs the dashboard; it doesn't.
   - `REPRODUCE_tau2.md:141` says `gate_mode significant`; the example uses `paired`.
   - The exgentic how-to uses the non-existent `algorithm_skill: all-at-once`.
   - `HANDOFF.md` is a personal note dated 2026-09-09 with `/Users/...` paths.
9. Other drift:
   - `.gitignore:38-40` re-includes a deleted evograph `dist/`.
   - The 0.1.0 section of the CHANGELOG lists examples and a subcommand that do not exist.
   - The `ci.yml` header says 6 jobs; the file has 8.

---

# Part 2 — skillberry-store's infrastructure

skillberry-store is a FastAPI **network service** with:

- a React UI;
- 16 plugin packages;
- a generated OpenAPI Python SDK;
- a native Go CLI (`sbs`);
- a container image published to GHCR.

Its build system is a GNU make framework. The framework lives in **`skillberry-common/`**,
which is vendored into the repo with `git subtree` and shared across "Skillberry assets".
Project-specific files sit on top of it.

## 2.1 Layout and include chain

```
Makefile                          # copied from skillberry-common/default/Makefile.default
 ├─ $(shell git remote add skillberry-common git@github.com:…)   # at parse time, if missing
 ├─ include .mk/local.mk          # MANDATORY identifiers: ASSET_NAME, ACRONYM, SERVICE_*, VERSION_LOCATION …
 │    ├─ include .mk/dev.mk       # project additions: lint, Go CLI, UI stamps, image variants
 │    └─ include .mk/process.mk   # project additions: run: ui-build, plugin config
 └─ include skillberry-common/Makefile
      ├─ .mk/globals.mk   help, .DEFAULT guard, .stamps/, BUILD_VERSION, ssh-agent stamp, env checks, *-common subtree targets
      ├─ .mk/dev.mk       git hooks, test/test-e2e, verify-venv, install stamps, git-state manifest, release, SDK generation
      ├─ .mk/process.mk   run/stop as a detached process with a PID sentinel and log in /tmp
      ├─ .mk/docker.mk    base image, service image, label-scoped stamps, pull-or-build, run, multi-arch push
      ├─ .mk/ci.mk        ci-pull-request (lint, test, test-e2e), ci-push (registry build + update-sdk)
      └─ .mk/common.mk    (empty)
skillberry-common/scripts/   git_state.py, install-requirements.sh, check_venv.sh + match_spec.py, ensure_pip.py,
                             docker-reconcile-stamp.sh, stage-extra-copy.sh, check-multiarch.sh, start/stop-service.sh,
                             mk_srv_env.sh, update_env_vars.sh, subtree-delta.sh, split-common.sh, make-help.py, sdk_cli.py
skillberry-common/default/   templates for a new asset: Makefile, local.mk, Dockerfile, pyproject.toml, .gitignore, .dockerignore, pre-push
skillberry-common/packages/llm-client/   an LLM client library (49 files), unused by the store
```

Projects extend the framework by **adding prerequisites** to common targets. They do not
override recipes. For example, `run: ui-build`, `test: cli-test`, and
`generate-sdk: install-build-requirements`. This keeps the shared recipes untouched, but it
means a target's real behaviour is spread across several files.

## 2.2 What it provides

**Help, guards and environment checks**

| Area | Targets / mechanism |
|---|---|
| Self-documenting help | `make help` groups targets by `##@` sections and `## description` comments (`scripts/make-help.py`). |
| Unknown-target guard | `.DEFAULT:` prints "Unimplemented target" and fails. |
| Environment checks | `verify-venv` requires an **active** venv whose Python matches `SUPPORTED_PYTHON_VERSIONS := 3.11 3.12+`. It then runs `ensure_pip.py` and `pip install uv`. `check-rits-watsonx-envs` checks credentials. |

**Installing, version labels and tests**

| Area | Targets / mechanism |
|---|---|
| Dependency install | `install-requirements [ODEPS=extra] [SKIPOPT=1]` runs `uv pip install -e .[extra]`. It is guarded by `.stamps/install-requirements-$(ODEPS)` and depends on `pyproject.toml`. |
| State label | `BUILD_VERSION` is computed by `git_state.py version`: `<release>`, `<release>-N-g<sha>` or `g<sha>`, plus `-dirty-<content hash>`. It is projected into `VERSION_LOCATION`, a Python module the app reads. |
| Tests | `test` runs `pytest`; `test-e2e` runs `pytest …/e2e`. Each first installs `ODEPS=test`. The project adds `lint` (black on four directories). |

**Running and containers**

| Area | Targets / mechanism |
|---|---|
| Process lifecycle | `run` runs `start-service.sh`: nohup, PID in `/tmp/<svc>-service.pid`, log in `/tmp/<svc>.log`, `tail -F`. `stop` and `clean` stop it and clean up. `.stamps/srv.env` holds the port variables. |
| Container images | `base-image-build` and `docker-build`, with `DBT=local\|registry` (multi-arch push), `CUSTOM_TAG`, `IMAGE_TAG_SUFFIX`, `EXTRA_BUILD_ARGS` and `EXTRA_COPY_FILES`. `docker-pull`; `docker-get` (pull, falling back to a build); `docker-run` (with `--network=host` and `.env`); `docker-stop`, `docker-clean`, `docker-rmi`. Both docker (buildx) and podman (manifest) paths are supported. |

**SDK, release, CI and the subtree itself**

| Area | Targets / mechanism |
|---|---|
| SDK | `generate-sdk` runs openapi-generator against the *running* service. `update-sdk` runs `docker-run`, waits for the service, runs `generate-sdk`, then `git commit`. |
| Release | `RELEASE_VERSION=x.y.z make release [REDO=1]`. It must be on a clean `main`. It creates `branch-<ver>` and tag `<ver>`, pushes both, runs `gh release create` with notes from the commit range, then runs `DBT=registry make docker-build`. `REDO=1` deletes the remote branch, tag, GitHub release and local images first. |
| CI entry points | `ci-pull-request` runs `lint`, `test` and `test-e2e`. `ci-push` adds `DBT=registry docker-build` and `update-sdk`. `.githooks/pre-push` is meant to run the PR checks when `ENABLE_QC` is set. |
| Subtree management | `fetch-common`, `pull-common`, `push-common` (marked "NOT RECOMMENDED"), `split-common` (creates a `splitbr/<branch>/<remote>/<user>` branch to PR back), `status-common` (ahead/behind counts) |
| New-asset templates | `skillberry-common/default/*` |
| Deploy-only mode | `DEPLOY_ONLY=TRUE` (set inside the runtime image) skips git plumbing, dependency installs and UI builds on the `run` path. The image's `CMD` is `make run`, so **make and the whole framework ship inside the runtime image.** |

## 2.3 The stamp and git-state model ("build concepts")

This is the most interesting part, and the newest: PR #324, merged 2026-09-17, documented in
`docs/design/build_concepts.md`. It defines six concepts.

**1. One label for the repository state.**
- `git_state.py version` derives a label from HEAD, from the nearest release (a tag or
  `branch-<ver>`), and from `git status`.
- A dirty tree gets a 7-hex fingerprint of `git diff HEAD` plus the contents of untracked,
  non-ignored files.
- So different dirty states get different labels. Staging an edit that is already in the
  working tree does not change the label.

**2. A manifest that only changes when the content does.**
- `.stamps/git-version-manifest` lists `HEAD` and one line per changed path: status, blob hash
  and path.
- It is recomputed on every invocation that reaches it (a `FORCE` prerequisite).
- It is **rewritten only when its content differs**, so its mtime stays stable and nothing
  downstream refires spuriously.
- When it is rewritten, it reports what changed (`~ + - !` per file, with
  `VERBOSE_BUILD_VERSION`).
- `VERSION_LOCATION` follows the same rule.
- The general rule is stated explicitly: *every generated file that gates downstream builds
  must be rewritten only when its content changes.*

**3. Image stamps are scoped to the label and checked against reality.**
- Docker stamps are named after the image tag (`.stamps/docker-build-local-<label>`), so a new
  state means a new, missing stamp, which triggers a rebuild.
- Going back to an already-built state (stash pop, a checkout back and forth) rebuilds
  **nothing**, because the manifest is only an *order-only* prerequisite.
- At parse time, `docker-reconcile-stamp.sh` deletes the stamps when the image they claim
  exists has been removed (for example by `docker rmi`).
- A pull satisfies the stamp just as well as a build (`docker-get`).

**4. No parallel mtime scans.**
Change detection goes through the git manifest, never through `find -newer` over a
hand-maintained file list.

**5 and 6. Install stamps.**
- The install stamp depends on `pyproject.toml` and `ODEPS` only.
- After a successful install, at most one non-empty-`ODEPS` stamp is valid, and the base stamp
  always is.
- A failed install touches nothing, so the next run retries.

Assessment of the model:

- **Concepts 1–3 are well reasoned.** The history in #324 shows each rule was paid for with a
  real bug:
  - a feature branch named `branch-drop-…` became "the latest release";
  - per-file `git hash-object` took 15.6 s on a tree with many untracked files;
  - `make release` baked the *pre-release* label into the image;
  - returning to an already-built state rebuilt the image.
- **Concept 5 has a deliberate hole.** It states that *"the virtual environment directory must
  not be a prerequisite"*. But the stamp lives in the repo (`.stamps/`) while the thing it
  vouches for lives in a venv. Create a fresh venv, or switch to another one, and
  `install-requirements` skips the install, because the stamp says it was done
  **(verified with `make -n`)**. `verify-venv` only checks that *some* venv with an allowed
  Python is active.
- **The store breaks its own concept 4.** Its UI stamps depend on
  `$(shell find src/skillberry_store/ui/src -type f)` mtimes (`.mk/dev.mk:177`).
- **In CI, stamps give nothing.** Every job starts from a fresh checkout. The store also checks
  out shallow with no tags, so the release lookup finds nothing and CI images are labelled
  `g<sha>` (for example `gda481ee-full`) rather than `0.2.1-26-g…`.

## 2.4 How the store itself uses it

**PR CI.**
- Steps: `apt-get install make`, `python -m venv .venv`, `source .venv/bin/activate`,
  `make ci-pull-request`.
- Time: 12–17 minutes, with no pip, uv or npm cache.
- Health: 19 of the last 20 runs green.

**Push CI.**
- Steps: QEMU and buildx setup, a venv, `make ci-push`.
- The workflow has no registry login step and no `packages: write` permission. **All of the
  last 40 runs failed** (2026-07-07 to 2026-10-04), each with
  `failed to push ghcr.io/skillberry-ai/skillberry-store:gda481ee-full … 403 Forbidden`
  **(verified with `gh run list` and `--log-failed`)**.
- Each run takes 23–28 minutes (lint, tests, image build) before it fails.
- So `update-sdk` and the core image push have not run on `main` in three months.

**Image.**
- The Dockerfile runs `make install-requirements` and `make ui-build` inside the build, then
  `CMD make run` with `DEPLOY_ONLY=TRUE`.

**Documented developer flows.**
- `make install-requirements`, `make run`, `make ui-dev`, `make test`, `make docker-run`.
- Not documented anywhere outside the Makefiles: `make release`, the `*-common` subtree
  targets, `ENABLE_QC` and `update-sdk`.

## 2.5 Distribution: a git subtree that has drifted both ways

`skillberry-common/` is a non-squashed git subtree of `skillberry-ai/skillberry-common`.

**History.**
- It was added three times (2026-01-04 to 01-06).
- 19 "Pull from skillberry-common" commits and 15 splits followed, all by one maintainer.
- Activity peaked in January–March 2026. **The last sync was 2026-04-28.**

**Drift since then.**
- 17 store commits changed `skillberry-common/` in place: about +1566/−318 lines across 13
  files.
- The upstream repository last received framework changes on 2026-06-09 (#172).

**Result (verified with `diff -rq` of upstream `6136693` against the store's copy):**

| Only in the store's copy (upstream `main` lacks it) | Only upstream |
|---|---|
| `scripts/git_state.py`, `install-requirements.sh`, `docker-reconcile-stamp.sh`, `stage-extra-copy.sh`, which together make up **the whole stamp and git-state system of §2.3**. Plus newer `globals.mk`, `dev.mk`, `docker.mk` (440 vs 335 lines), `process.mk`, `ci.mk` and `Dockerfile.default`. | `.github/workflows/*` (the reusable workflows cap-evolve calls) and `trigger-templates/` |

So "adopting skillberry-common" today means choosing between two things:

- **the upstream repo**, which is four months behind and lacks the feature that makes it
  interesting (stamps);
- **a copy of skillberry-store's in-tree fork**, which would become a third, divergent copy.

## 2.6 Defects found in the framework

These were reproduced on a disposable copy unless marked otherwise.

**Breaks a workflow outright**

| # | Defect | Evidence | Consequence |
|---|---|---|---|
| 1 | GHCR push without login | `push.yml` has no login step and no `packages: write` (40 of 40 runs failed) | The image and SDK publishing pipeline is broken on `main` |
| 2 | A blank line *before* the shebang in `check-multiarch.sh` and `split-common.sh` | Run through `/bin/sh` on Debian/Ubuntu (dash): `Syntax error: "(" unexpected` and `set: Illegal option -o pipefail` **(verified)** | `make base-image-build`, `multiarch-check` and `split-common` fail on Debian/Ubuntu hosts, including GitHub's Ubuntu runners |
| 3 | `.githooks/pre-push` calls `make ci_pull_request` (underscores) | The target is `ci-pull-request` | With `ENABLE_QC` set, every push fails with "Unimplemented target". The same bug is in the default template. |

**Silently does the wrong thing**

| # | Defect | Evidence | Consequence |
|---|---|---|---|
| 4 | Podman detection is dead code | `$(wildcard "~/.bashrc")` contains literal quotes and never matches. A probe with `alias docker='podman'` in `.bashrc` still gives `DOCKER=docker` **(verified)**. The README tells users to write `` docker alias=`podman` ``, which is invalid shell. | Podman-only hosts get `docker: command not found`. A shell alias would not reach make's subshells anyway. |
| 5 | `match_spec.py` returns `1` (truthy) when a non-final version component mismatches | `3.12+` accepts `4.0.0`; `3.11` accepts `2.11.0` **(verified)** | The Python version gate is wrong across major versions. Minor in practice. |
| 6 | The install stamp is not tied to the venv (§2.3) | `make -n install-requirements` in a fresh venv with an existing stamp plans no install **(verified)** | A new or switched venv is left empty |
| 7 | UI `node_modules` stamp: `(test -d node_modules \|\| npm ci)` | `.mk/dev.mk:237` | A changed lockfile with an existing `node_modules` gets the stamp touched but the dependencies are not updated |
| 8 | The docker stamp ignores `EXTRA_BUILD_ARGS`, `PLUGIN_EXTRAS` and `EXTRA_COPY_FILES` | `docker.mk:275`; acknowledged in `plugins-installation.md` | Changing the plugin set does not rebuild the image |

**Side effects, cost and portability**

| # | Defect | Evidence | Consequence |
|---|---|---|---|
| 9 | Work done at parse time on **every** invocation, including `make help` | `git remote add skillberry-common git@github.com:…` (**verified**: `make help` added the remote); `mkdir .stamps`; `git_state.py version` (git status, diff, hashing); `docker image inspect` reconcile; all of it needs `python` on PATH (outside a venv on Debian: `python: No such file or directory` **(verified)**) | Surprising side effects in forks, CI and agent sandboxes. An SSH-only URL breaks `pull-common` for HTTPS-only contributors. |
| 10 | `verify-venv` runs `python -m pip install uv` on every install | `dev.mk:68` | A network round-trip on every `make test`. `ensure_pip.py` may download `get-pip.py`. |
| 11 | `install-requirements` quietly runs `git config core.hooksPath .githooks` | `dev.mk:25-32` | Overrides a contributor's own hooks setup (pre-commit, husky) |
| 12 | Fixed `/tmp/<svc>-service.pid` and `/tmp/<svc>.log`. The log is a truncating `nohup … >&`. | `process.mk:3-4`, `start-service.sh:22` | One instance per host. A stale sentinel means `make run` exits 0 without starting anything. Each start erases the previous log. cap-evolve's `blackbox_env.py` works around all three. |
| 13 | Recursive calls use `make`, not `$(MAKE)`, in `ci.mk` and `release` | `ci.mk:7-26`, `dev.mk:178` | `-n`, `-j` and `-k` are not propagated |
| 14 | Assumptions about Linux, GNU tools and SSH | GNU `sed -i` (`dev.mk:242,261`); `--network=host`; `SSH_KEY ?= ~/.ssh/id_rsa`; `ssh-agent` started per stamp and never stopped; `ssh-keyscan github.ibm.com` in the base image | Friction on macOS and Docker Desktop. Leftover GitHub Enterprise references. |

---

# Part 3 — Assessment: adopting it in cap-evolve

## 3.1 Fit: what the framework assumes vs. what cap-evolve is

The framework is a good fit for what it was built for. Most of its value, and most of its
code, is about that use case, so whether it suits cap-evolve depends mainly on how far
cap-evolve resembles it.

**The product and its users**

| skillberry-common assumes… | cap-evolve actually… | Consequence |
|---|---|---|
| **One network service per repo**, shipped as a **container image** with a **generated SDK** (`SERVICE_PORTS`, `SERVICE_ENTRY_MODULE`, `SERVICE_HAS_SDK` are mandatory in `local.mk`) | is a **stdlib-only library + CLI + skills tree**. Users `pip install ./core`. The dashboard is an optional local tool that `cap-evolve dashboard` already starts on demand with a health probe. | `process.mk`, the SDK targets, `update-sdk` and most of `docker.mk` have nothing to act on |
| Users and operators run `make` | Users are often **coding agents following `RUN.md`**, and the headline promise is "two minutes, no API key, zero runtime deps" | make must stay a *contributor* tool. Routing the quickstart through make would add a prerequisite and remove nothing. |
| Release = branch per version + tag + GitHub release + GHCR multi-arch image | The natural release is a PyPI wheel (or four), a tag, the plugin marketplace entry, and possibly a runner image | The `release` target does the wrong thing for cap-evolve and is destructive with `REDO=1` |

**The development environment**

| skillberry-common assumes… | cap-evolve actually… | Consequence |
|---|---|---|
| **One active venv per checkout**, Python 3.11 / 3.12+ | needs **several environments by design** (§1.4.2): tau2 needs ≥3.12, the Skillberry services 3.11, one cached venv per runner arm. CI uses `actions/setup-python`, which is not a venv. | `verify-venv` fails in cap-evolve's existing CI jobs, and repo-level install stamps would lie whenever the developer switches environment |
| **One `pyproject.toml` at the root** (`.stamps/install-requirements-$(ODEPS)` depends on `pyproject.toml`) | has **four** `pyproject.toml` files in subdirectories plus an npm package | `install-requirements` cannot be used as is; it would need rewriting |
| A Linux host with Docker + buildx, an SSH key for GitHub, `python` on PATH | Contributors use macOS (the demo pipeline, many docs). CCC uses rootless Podman without subuid behind a `docker` shim. Agents run in sandboxes. Many clones are HTTPS. | Parse-time side effects (`git remote add` with an SSH URL, the `python` lookup) and the broken podman detection all hit cap-evolve's contexts |

**Where the heavy work happens**

| skillberry-common assumes… | cap-evolve actually… | Consequence |
|---|---|---|
| The heavy operations are **image builds and dependency installs** in the checkout | The heavy operations are **benchmark provisioning on a persistent self-hosted runner** (clones, datasets, venvs in `$CAPEVOLVE_CI_CACHE`), **LLM-backed generation** (`bake-aap2-skill.sh`), and **runtime containers** that tools such as harbor, the spreadsheetbench executor and benchflow start themselves | Repo-local `.stamps/` are wiped by `actions/checkout` on the runner (`ci_setup.sh:183`). Image stamps do not touch containers that cap-evolve does not build. |

## 3.2 Component-by-component

*Value* is what the component would buy cap-evolve. *Cost / risk* includes defects from §2.6.

**Adopt or adapt**

| Component | Value for cap-evolve | Cost / risk | Verdict |
|---|---|---|---|
| `make help` (`##@` sections) and the `.DEFAULT` unknown-target guard | **High** for contributors: one self-documenting front door replaces six divergent recipes (§1.4.1) | Tiny: about 5 lines of awk | **Adopt the pattern.** Write it from scratch; the subtree is not needed. |
| `install-requirements` + install stamps | **Medium**: skips a 30 s reinstall when nothing changed | The store's version is venv-agnostic, assumes a root pyproject, depends on uv and `pip install uv`, and quietly sets `core.hooksPath` | **Adapt**: keep the stamp in the venv, keyed on all four pyprojects (§4.3) |
| `git_state.py` label + manifest + `VERSION_LOCATION` | **Medium–high, but not as a make feature.** cap-evolve's product is honest numbers, and runs started outside CI record no code version (W12). A label with a dirty-content fingerprint is exactly the provenance a run record needs. | As a make pivot it gates nothing in cap-evolve (no image builds). Runs start from the CLI and agents, never from make. | **Adapt the idea into core** (stdlib, computed when a run starts, written to the run's metadata). Do not adopt it as a make pivot. |
| Content-idempotent generated files (concept 2) | **High, cheap**: `manifest.json`, `site/skillsbench`, `demo_session/`, `TAU2_COMMIT.txt` | Discipline, not code | **Adopt the rule** |
| `ci-pull-request` / `ci-push` (CI calls make) | **High**: local equals CI, and the Bob workflows' `verify_command` collapses to `make ci` | Must not serialize cap-evolve's 8 parallel jobs | **Adapt**: CI jobs call individual targets, and `make ci` aggregates them locally |
| Reusable GitHub workflows (codeql, Bob, labels) | Already adopted | `@main` + `secrets: inherit` (§3.8) | **Keep, but pin to a commit SHA** |

**Borrow later, or drop**

| Component | Value for cap-evolve | Cost / risk | Verdict |
|---|---|---|---|
| Docker stamp reconciliation + label-scoped image tags (concept 3) | **Low today**: cap-evolve builds two images, by hand, and rarely | `docker.mk` defects 4, 8, 14 (§2.6). buildx is unavailable behind CCC's podman shim. `--network=host`. | **Defer.** Borrow the *pattern* when a runner-image workflow is written (Phase 3). |
| OpenShift image hardening (`chgrp 0`, `chmod g=u`, arbitrary UID, from #305; `stage-extra-copy.sh` from #311) | **Medium** for W9: cap-evolve's manifests currently need the `anyuid` SCC | Small, self-contained Dockerfile idiom | **Borrow when touching the runner image** |
| `run` / `stop` process lifecycle | **None**: `cap-evolve dashboard` already has `ensure_up()` | `/tmp` sentinels, truncating logs (defect 12). cap-evolve already works around these for the Skillberry stack. | **Drop** |
| SDK generation / `update-sdk` | None: there is no OpenAPI service to generate from | — | **Drop** |
| `release` | Low: wrong artifact (no PyPI) | Destructive `REDO`, `sleep 10`, a branch per release | **Drop.** Write a PyPI/tag workflow when releases resume. |
| `verify-venv`, `check_venv.sh`, `ensure_pip.py`, `check-rits-watsonx-envs` | Low: `cap-evolve doctor` and `ci_setup.sh`'s gateway preflight already cover readiness better | Defects 5 and 10; fails under setup-python | **Drop** |
| `git subtree` vendoring + `*-common` targets | Negative: about 83 files (49 of them an unused `llm-client` package) plus a second copy of the reusable workflows' source | Upstream is four months behind the useful version (§2.5); parse-time `git remote add` with an SSH URL; split and push need maintainer discipline that has lapsed | **Drop** |
| `.githooks/pre-push`, `git-hooks-setup` | Low | Broken (defect 3); changes the developer's git configuration | **Drop.** Document `make ci` as the pre-push check instead. |
| `default/` templates, `llm-client` | None | — | **Drop** |

## 3.3 Workflows enabled

What follows assumes the adapted, middle-ground version. Full adoption enables the same
things, plus the image items marked †.

1. **A single contributor entry point.** `make help`, then `make ci`, runs exactly what
   `ci.yml` runs.
   - This replaces the six divergent recipes in `CONTRIBUTING.md`, `.bob/rules`, the PR
     template, `.review`, the Bob issue-fixer inputs and `ci.yml`.
   - Coding agents also get stable verbs. `.bob/rules` and `fix-issues-with-bob.yml`'s
     `verify_command` can both become `make ci`.
2. **Coverage for suites that rotted.** `test-packages` runs harbor and telemetry, and
   `scripts/v4_t2_e1/tests` can be added the same way. Together they catch the four failures
   in §1.4.5 that CI has never seen.
3. **Hermetic tests by default.** Pinning `CAPEVOLVE_SKILLS_DIR` in the test targets fixes the
   failure that appears on any developer machine with a `~/.claude/skills` directory.
4. **Incremental frontend work.**
   - `npm ci` runs only when `package-lock.json` changes, and the bundle is rebuilt only when
     its sources change.
   - Measured on this repo: a cold `make dashboard` took 20 s; a repeat took 8 ms
     **(verified)**.
   - `make ci` then fails on `dist/` drift, as CI does.
5. **Freshness checks for committed generated files.** `make manifest-check` exists in the
   sketch. A `make site-check` built on `build_skillsbench_site.py --check` would follow the
   same pattern.
6. **Cheap no-op reinstalls.** A dev install that took about 30 s on its first run took 23 ms
   on the next **(verified)**. The stamp is per venv, so `VENV=.venv-312 make test` works for the
   tau2 Python range.
7. **Provenance.** With the label idea moved into core, every run directory records which code
   produced it, including local, CCC and OpenShift runs.
8. † **A published, labelled runner image** (`make image` / `image-push`) for OpenShift,
   replacing the `quay.io/<your-org>` placeholder. This requires registry credentials in CI,
   which is the same gap that has broken the store's push for three months.
9. † **Scripted releases.** This only applies once rewritten for PyPI; the store's flow does
   not transfer.

## 3.4 Workflows blocked or degraded

These come mainly with *full* adoption. The middle ground in §4.3 avoids each of them by
design.

| Affected | How |
|---|---|
| Hosts without GNU make | Windows, minimal containers, some runners. cap-evolve has already met this once (issue #573). The middle ground keeps every user path make-free. |
| Every invocation, in forks, CI and agent sandboxes | Parse-time side effects: `git remote add skillberry-common git@github.com:…` runs even for `make help`, plus `git status`/hash work, a `docker image inspect` and a hard requirement for `python` on PATH. An agent that runs `make help` to learn the targets changes the repository's git config. |
| CI | `verify-venv` rejects `actions/setup-python`. Every job would need a "create venv, then `source` it" step, as the store does. |
| Developers switching environments (tau2 at 3.12, a second venv for a PR, a recreated `.venv`) | Repo-level install stamps say "installed" for a venv that is empty (defect 6). |
| Self-hosted benchmark runner | `.stamps/` sits inside the checkout, which `actions/checkout` wipes on every job. No stamp benefit at all, unless the stamp directory is moved to `$CAPEVOLVE_CI_CACHE`, which the framework does not support. |
| CCC (rootless Podman behind a `docker` shim) | `DOCKER=docker` → `buildx build` → no buildx. The podman branch is unreachable (defect 4). |
| Contributors who use pre-commit or husky | `install-requirements` silently resets `core.hooksPath` |
| Maintainers | Two sources of truth for the framework (the store's fork and upstream), `pull-common` conflicts, and 14 known defects (§2.6) to fix or live with |

## 3.5 Value by persona

| Persona | Full adoption | Middle ground (§4) |
|---|---|---|
| **End user** (`pip install ./core`, toy, own adapter) | None. Negative if the docs start sending users through make. | None, and none is lost: user paths stay make-free |
| **Coding-agent host** (RUN.md) | None for running. Negative: parse-time side effects in the sandbox. | Small: stable verbs (`make ci`, `make test`) when an agent edits the repo |
| **Contributor** | Medium: `make help`, `make test`. Offset by the venv requirement, Python version gate, hooks and SSH remote. | **High**: one command, parity with CI, faster no-op reinstalls and rebuilds, hermetic tests |
| **Benchmark operator** (runner, `benchmarks.yml`) | None: stamps are wiped by checkout, and the heavy work is in `ci_setup.sh`, not make | Medium, from Phase 2: pinned and stamped clones, a stamped LLM bake, and recorded refs, done in shell where the work already is |
| **Cluster researcher** (CCC/LSF) | Negative: podman path broken, docker.mk unusable | Small: a recipe-keyed stamp for the patched ubuntu image |
| **Maintainer / release** | Low: wrong release artifact, broken publish path to copy | Medium, from Phase 3: a single-source version and a PyPI workflow written for cap-evolve |

## 3.6 General patterns: what to take, what to avoid

The task names "not repeating heavy operations using stamps" as an example, so this section
looks at stamps in detail.

### Patterns worth adopting

**P1 — Key a stamp on its true inputs.**
- The store's install stamp depends on `pyproject.toml`; its node stamp depends on the
  lockfile. The useful idea is to name the stamp after its inputs.
- In cap-evolve:
  - pip installs → all four pyprojects;
  - `npm ci` → `package-lock.json`;
  - benchmark clones → the **pinned ref**, which also makes them reproducible;
  - the CCC patched image → a hash of the Dockerfile text instead of a hand-bumped `-v7`;
  - the AAP2 bake → `hash(spec, model, harness ref)`.

**P2 — Store the stamp with the artifact, not with the repo.**
- This is the fix for the store's concept-5 hole. Put stamps in the venv
  (`.venv/.capevolve-stamps/`), in `node_modules/`, or in the clone directory under
  `$CAPEVOLVE_CI_CACHE`.
- Deleting the artifact then deletes the stamp, so the reconcile step becomes free.
- On the runner, this is also the **only** location that survives `actions/checkout`.

**P3 — Reconcile a stamp with reality (concept 3).**
- When an artifact can disappear behind the stamp's back, check that it still exists before
  trusting the stamp.
- cap-evolve's runner does disappear things behind stamps' backs. `ci_setup.sh` reaps harbor
  job directories and orphaned containers, and tells operators to run
  `docker image prune -a`.
- So image stamps there must check existence, for example
  `podman image exists … || rebuild` in `setup_podman.sh`.

**P4 — Write generated files only when the content changes (concept 2).**
- This keeps mtimes stable, keeps diffs honest, and stops dirtying the tree.
- It applies directly to:
  - `TAU2_COMMIT.txt`, which `setup.sh` rewrites inside a committed file; record it in the run
    directory instead;
  - `manifest.json`, which is already deterministic;
  - the skillsbench site render.

**P5 — Label artifacts by state, so returning to an old state is free (concept 3).**
- For cap-evolve, this matters most for **paid** artifacts: LLM-baked skills and expensive
  baselines.
- A cache keyed by `(inputs hash)` means switching branches back and forth never pays twice.

**P6 — A provenance label with a dirty-content fingerprint (concept 1).**
- Compute it in core at run start, and write it to the run's metadata (runmeta).
- cap-evolve's results are only as credible as their provenance, and hand-run experiments
  (`docs/experiments/*`) currently have none.

**P7 — CI calls the same verbs developers do**, and `make help` documents them.

**P8 — Keep the user path separate from the contributor path.**
- The store's `DEPLOY_ONLY` separates dev-time work from runtime work.
- cap-evolve's equivalent: users never need make, contributors use it.

### Anti-patterns to avoid

**A1 — Work and side effects at parse time.**
- `$(shell git remote add …)`, git hashing, `docker inspect` and `mkdir` all run on every
  invocation, including `help`.
- Make's parse phase should only read.

**A2 — A repository-level stamp for state outside the repository.**
- Examples are a venv, an image, or a cache directory (defect 6).

**A3 — mtime-only change detection for content that can change in place.**
- The store's UI scan has this problem.
- So does cap-evolve's own `_artifact_stamp`, which uses `(mtime_ns, size)` and is flaky
  (§1.4.5).
- Use a content hash or a git-tracked input list. If mtime has to be used, back it with a
  drift check. The sketch does this for the committed `dist/`.

**A4 — Network calls in a "check" step.**
- An example is `pip install uv` on every install.
- A check that downloads things is not idempotent.

**A5 — Global `/tmp` sentinels and truncating logs.**
- They allow one instance per host, and a stale sentinel looks like success.
- Use paths derived from the checkout or `$XDG_RUNTIME_DIR`, and verify a recorded PID is
  alive (`kill -0` plus an argv check, as `blackbox_env` does).

**A6 — Quietly changing a developer's configuration.**
- The store sets `core.hooksPath`, adds git remotes, and edits `.env`.

**A7 — Vendoring by subtree without upstream discipline.**
- The result is a fork that drifts, and an upstream that falls behind its best version
  (§2.5).

### Where stamps actually pay off in cap-evolve

| Heavy operation | Stamp key | Stamp location | Cost avoided per repeat | Needs make? |
|---|---|---|---|---|
| Dev install (4 packages) | 4 × `pyproject.toml` | `$(VENV)/.capevolve-stamps/dev` | about 30 s (pip) | Makefile (§4.3) |
| `npm ci` | `package-lock.json` | `node_modules/.capevolve-stamp` | about 15 s, network | Makefile |
| Dashboard bundle | the tracked `src/` file list (mtime, plus the CI drift check) | `dist/index.html` | 5–20 s | Makefile |
| Benchmark clones on the runner (tau2, skillsbench, rfe-creator, skillberry-benchmarks) | pinned ref | `$CACHE/<clone>/.capevolve-stamp` (+ `$VENV/.capevolve-stamps/<name>` for its install) | a network fetch on every job; **adds reproducibility**, which is worth more than the time | No: a shell helper in `ci_setup.sh` |
| AAP2 skill bake (LLM) | hash(spec, model, harness ref) | `<output>/.capevolve-inputs` | **real money** on every run | No: shell |
| CCC patched ubuntu image | hash of the inline Dockerfile + `podman image exists` | `$STORAGE_BASE/.patched-ubuntu24-<hash>` | about 500 MB of apt per new storage root, plus manual bumps | No: shell |
| parsec agent base image | Dockerfile hash + pinned base digest + image existence | podman label or tag | a full image build | No: shell |
| Demo video segments | per-shot input hash | `/tmp/video/seg_*.inputs` | minutes of x264 per edit | No |

Most of the benefit is **not** in make. It sits in shell scripts that CI and researchers
already run. The pattern is what transfers, and a 10-line shell helper implements it
(§4.4).

## 3.7 Effort and risk, roughly estimated

These are informed estimates for one engineer who knows both repositories, not measurements.

**Full adoption**

| Work | Estimate |
|---|---|
| Subtree add; `local.mk` with service fields that do not apply; reworking installs for four sub-packages | 3–5 days |
| Moving CI to venv + make; docs and agent rules | 2–3 days |
| Fixing or working around defects 2–14 (or accepting them) | 3–5 days |
| **Total initial effort** | **about 2–3 weeks** |
| Ongoing | Subtree pulls and splits, or a permanently diverging fork. Every upstream change needs re-validation against cap-evolve's multi-environment reality. |
| Risk | Medium. Side effects and stamp lies would hit agent-driven contributors first, and they are the least likely to diagnose a lying stamp. |

**Middle ground (§4)**

| Phase | Estimate |
|---|---|
| Phase 0 fixes | 1–1.5 days (revised in §4.8) |
| Phase 1: Makefile + CI + docs | about 2 days (revised in §4.8) |
| Phase 2: runner pins and stamps + provenance + example isolation | 2–3 days (revised in §4.8) |
| Phase 3: release or image workflows, only when needed | 2–3 days each |

Ongoing: about 100 lines of make that cap-evolve owns, plus a shell helper. Risk: low. Every
piece can be reverted on its own, and users are never touched.

## 3.8 Governance and supply chain

Vendoring with a subtree has one real advantage: the code is pinned by commit and reviewed in
the consuming repository's PRs. cap-evolve's *current* link to skillberry-common has neither
property.

**All six delegated workflows call `skillberry-ai/skillberry-common/.github/workflows/*.yml@main`
with `secrets: inherit`.** So any commit to skillberry-common's `main` runs, unreviewed by
cap-evolve, with every secret the calling workflow can see. `secrets: inherit` forwards all
of the caller's repository and organisation secrets. In this repository that includes the IBM
gateway keys (`IBM_ETE_INT_API_KEY`, `IBM_ETE_API_KEY`, `IBM_RITS_API_KEY`) and
`SKILLBERRY_BOT_TOKEN`, which has write access to the repository.

This is independent of the make question, and cheaper to fix than anything above:

- pin each `uses:` line to a commit SHA, and let Dependabot or a periodic PR bump it;
- replace `secrets: inherit` with the specific secrets each workflow needs.

---

# Part 4 — Recommendation

## 4.1 Verdict

**Adopting skillberry-store's infrastructure wholesale is not worth the effort.** The reasons,
in order of weight:

1. **It solves a different problem.**
   - The framework exists to build, run, version and publish **one network service as a
     container image with a generated SDK**.
   - cap-evolve is a zero-dependency library, CLI and skills tree that users install with pip
     and that agents drive. It has four sub-packages, several Python environments by design,
     and its heavy work happens on a persistent benchmark runner.
   - About half of the framework (`process.mk`, SDK, `release`, most of `docker.mk`) has
     nothing to act on. The parts that remain (venv model, root `pyproject`, repo-level
     stamps) conflict with how cap-evolve works (§3.1).
2. **The version worth adopting is not the one available.**
   - The stamp and git-state system that makes the framework attractive exists only in
     skillberry-store's in-tree fork.
   - Upstream skillberry-common has been four months behind since its last sync (§2.5).
   - Adopting it means taking on a third copy, or a subtree workflow that has already lapsed.
3. **It brings real defects and hostile side effects.**
   - 14 issues in §2.6, including a publish pipeline that has failed for three months.
   - Parse-time `git remote add` with an SSH URL.
   - Install stamps that lie when the venv changes.
   - Podman detection that never fires.
   - These land hardest on agent-driven and cluster workflows, which are cap-evolve's core
     audiences.
4. **What cap-evolve needs is small, and only partly make-shaped.**
   - The concrete wins are a contributor front door with CI parity, coverage for rotting
     suites, hermetic tests, incremental frontend builds, pinned and stamped benchmark
     provisioning, and run provenance.
   - That is about 100 lines of make plus a 10-line shell helper, all owned by cap-evolve. Most
     of the stamp value lives in `ci_setup.sh` and the CCC/parsec scripts, not in make
     (§3.6).

**The ideas behind skillberry-store's build system are good and worth taking. The code is
not.** Specifically:

- stamps keyed on true inputs (P1);
- the content-idempotence rule (P4);
- reconciling stamps with artifacts (P3);
- label-scoped, state-addressed artifacts (P5);
- a provenance label with a dirty fingerprint (P6);
- CI calling developer verbs (P7);
- self-documenting help.

## 4.2 Middle ground: take this, adapt that, drop the rest

| Take, as an idea or as a few lines rewritten | Adapt | Drop |
|---|---|---|
| `##@` / `##` self-documenting `make help`; the `.DEFAULT` unknown-target guard | Install stamps → **stored in the venv**, keyed on all four pyprojects | `git subtree` + `*-common` targets + the parse-time `git remote add` |
| The content-idempotence rule for every generated file (concept 2) | `ci-pull-request` → `make ci`, with CI jobs calling individual targets | `verify-venv`, `check_venv`, `match_spec`, `ensure_pip`, `pip install uv` |
| Reconcile a stamp with its artifact (concept 3), applied in shell on the runner and CCC | Git-state label → **computed in core at run start**, written to the run metadata, not used as a make pivot | `process.mk` (`run`/`stop`, `/tmp` sentinels) |
| A cache keyed by state/inputs, so returning to an old state is free (concept 3) | `docker.mk` ideas (label tags, pull-or-build, reconcile) → only when a runner-image workflow is written | SDK generation, `update-sdk`, `release` (rewrite for PyPI when needed) |
| OpenShift arbitrary-UID hardening idiom (#305), when the runner image is next touched | Reusable workflows → keep, but **pin to SHA** and pass only the secrets each needs | `.githooks` + `git-hooks-setup`, `default/` templates, `llm-client` |

## 4.3 Proposed `Makefile` (verified sketch)

What the sketch does:

- It is contributor and CI tooling only. Every user path in README, INSTALL, GETTING_STARTED
  and RUN stays make-free.
- It owns its venv, so it works under `actions/setup-python`, with no active venv needed.
- It does nothing at parse time beyond read-only queries (`git ls-files`, and asking `$(PYTHON)` for its version).
- Its stamps live inside the artifacts they describe.

It was run end to end on a copy of this repository at `6af27e2`, with GNU make 4.3, Python
3.11 and Node 22:

| Target | Result |
|---|---|
| `make help` | prints the grouped targets |
| `make nope` | exits 2 with a hint |
| `make install` (cold / repeat) | 29.9 s / 23 ms. Touching any `pyproject.toml` re-plans the install, and `VENV=.venv-alt` gets its own. A user's existing `.venv` of the right Python version is adopted. One built by a different version is refused with a message and never deleted. A missing `PYTHON` fails clearly. (Revised after the §4.8 validation, which found the first version did not check the interpreter.) |
| `make dashboard` (cold / repeat) | 20 s / 8 ms. Touching a `src/` file re-plans only `npm run build`. The rebuilt `dist/` was byte-identical to the committed one. |
| `make toy` | 1.3 s; fails correctly when the expected reward is not reached |
| `make lint`, `make manifest-check` | 1.8 s, 1.3 s, both pass |
| `make -k ci` | 3 min 44 s. Every target ran. It failed on exactly the known issues of §1.4.5: the `core` mtime flake, and harbor's token test in `test-packages`, a suite CI never ran. Lint, manifest, toy, the dashboard build and 194 vitest tests passed. |

`make -k test` continues across targets but not across lines within one recipe. That is why
each suite has its own target.

```make
# cap-evolve developer Makefile — SKETCH (see docs/INFRA.md §4.3). Contributor/CI
# convenience only: users never need make (`pip install ./core` stays the install).
# Recipes must not rely on .SHELLFLAGS: macOS ships GNU make 3.81, which ignores it.
SHELL         := bash
.SHELLFLAGS   := -euo pipefail -c
.DEFAULT_GOAL := help
MAKEFLAGS     += --no-builtin-rules

PYTHON ?= python3
VENV   ?= .venv
VPY    := $(VENV)/bin/python
# Stamps live INSIDE the artifact they describe: delete the venv (or node_modules)
# and its stamps go with it, so a stamp can never outlive what it vouches for.
VSTAMP := $(VENV)/.capevolve-stamps
FE     := dashboard/frontend
# Hermetic tests: never resolve skills from a developer's ~/.claude/skills.
TESTENV := CAPEVOLVE_SKILLS_DIR=$(CURDIR)/skills

.DEFAULT: ; @echo "make: no target '$@' — run 'make help'" >&2; exit 2

##@ Setup
help: ## Show this help
	@awk 'BEGIN{FS=":.*## "} /^##@/{printf "\n\033[1m%s\033[0m\n",substr($$0,5)} \
	  /^[a-zA-Z0-9_-]+:.*## /{printf "  \033[36m%-18s\033[0m %s\n",$$1,$$2}' $(MAKEFILE_LIST)

# The interpreter version is part of the venv stamp. A venv built by another Python is
# reported, never deleted: it may be a user's own `python3 -m venv .venv` (README).
PYVER  := $(shell $(PYTHON) -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null)
VENVOK := $(VSTAMP)/python-$(PYVER)
$(VENVOK):
	@[ -n "$(PYVER)" ] || { echo "cannot run PYTHON=$(PYTHON)" >&2; exit 1; }
	@if [ -x $(VPY) ]; then \
	  have=$$($(VPY) -c 'import sys; print("%d.%d" % sys.version_info[:2])'); \
	  [ "$$have" = "$(PYVER)" ] || { echo "$(VENV) is Python $$have, PYTHON=$(PYTHON) is $(PYVER):" \
	    "remove $(VENV) or pass VENV=<new dir>" >&2; exit 1; }; \
	else $(PYTHON) -m venv $(VENV); fi
	@mkdir -p $(@D) && touch $@

# Keyed on every pyproject.toml, and stored in the venv, so `VENV=.venv-312 make test`
# gets its own install instead of trusting another venv's stamp.
PYPROJECTS := core/pyproject.toml dashboard/backend/pyproject.toml \
              capevolve_harbor/pyproject.toml capevolve_telemetry/pyproject.toml
$(VSTAMP)/dev: $(PYPROJECTS) | $(VENVOK)
	$(VPY) -m pip install -q -e "./core[dev]" -e "./dashboard/backend[dev]" \
	  -e ./capevolve_harbor -e "./capevolve_telemetry[dev]"
	@mkdir -p $(@D) && touch $@

install: $(VSTAMP)/dev ## Editable dev install (re-runs only when a pyproject.toml changes)

##@ Test & lint (the same commands ci.yml runs)
test: test-core test-dashboard test-ci-lib test-packages ## All Python suites (make -k test runs every one)
test-core: install ## core/tests (~1800 tests, ~3 min)
	$(TESTENV) $(VPY) -m pytest core/tests -q
test-dashboard: install ## dashboard/backend/tests
	$(TESTENV) $(VPY) -m pytest dashboard/backend/tests -q
test-ci-lib: install ## ci/benchmarks/lib (pytest + shell tests)
	$(VPY) -m pytest ci/benchmarks/lib -q
	for t in ci/benchmarks/lib/test_*.sh; do bash "$$t" || exit 1; done
test-packages: install ## capevolve_harbor + capevolve_telemetry (not in ci.yml today)
	$(VPY) -m pytest capevolve_harbor/tests -q
	$(VPY) -m pytest capevolve_telemetry/tests -q

lint: install ## Skill lint, CLI-subcommand doc check, model-picker sync, compileall
	$(VPY) skills/_registry/lint_skills.py skills
	$(VPY) ci/check_cli_subcommands.py
	$(VPY) ci/benchmarks/lib/sync_models.py --repo . --validate
	$(VPY) -m compileall -q core skills >/dev/null

manifest-check: install ## Fail if skills/_registry/manifest.json is stale
	$(VPY) skills/_registry/build_manifest.py skills >/dev/null
	git diff --exit-code -- skills/_registry/manifest.json

toy: install ## Zero-API end-to-end proof (toy_calc must reach test_reward 1.0)
	out="$$(PATH="$(CURDIR)/$(VENV)/bin:$$PATH" bash examples/toy_calc/run.sh)" || exit 1; \
	  echo "$$out"; grep -q '"test_reward": 1.0' <<<"$$out"

##@ Dashboard frontend
# npm ci only when the lockfile changes; the stamp sits in node_modules itself.
# dist/ is rebuilt by mtime. That is acceptable ONLY because dist/ is committed and
# `make ci` (like ci.yml) fails on any drift, so a missed rebuild cannot ship.
$(FE)/node_modules/.capevolve-stamp: $(FE)/package-lock.json
	cd $(FE) && npm ci --no-audit --no-fund
	@touch $@

FE_SRC := $(shell git ls-files $(FE)/src $(FE)/index.html $(FE)/vite.config.ts \
            $(FE)/tsconfig.json $(FE)/tsconfig.app.json $(FE)/tsconfig.node.json \
            $(FE)/tailwind.config.js $(FE)/postcss.config.js 2>/dev/null)
$(FE)/dist/index.html: $(FE_SRC) $(FE)/node_modules/.capevolve-stamp
	cd $(FE) && npm run build

dashboard: $(FE)/dist/index.html ## Rebuild the committed dist/ bundle if src/ changed
dashboard-test: $(FE)/node_modules/.capevolve-stamp ## vitest
	cd $(FE) && npm test

##@ Aggregate
ci: lint manifest-check test toy dashboard dashboard-test ## Everything ci.yml checks, locally
	@test -z "$$(git status --porcelain -- $(FE)/dist)" || \
	  { echo "dist/ differs from the commit: commit the rebuilt bundle" >&2; exit 1; }

.PHONY: help install test test-core test-dashboard test-ci-lib test-packages lint \
        manifest-check toy dashboard dashboard-test ci
```

To wire it in:

- **CI.** Each `ci.yml` job keeps its own runner for parallelism, but its body becomes
  `make lint`, `make test-core`, `make dashboard dashboard-test`, and so on. Add
  `test-packages` (after fixing the two failures) and `manifest-check` as new jobs. Add
  `actions/cache` keyed on the pyprojects and `package-lock.json`. In GitHub-hosted CI that is
  the right tool for repeat work, not stamps.
- **Docs and agents.** `CONTRIBUTING.md`, `.bob/rules/01-cap-evolve.md`, the PR template and
  `fix-issues-with-bob.yml` (`setup_command: make install`, `verify_command: make ci`) all
  point at `make help` and `make ci`. The six divergent recipes collapse to one.
- **macOS.** macOS ships GNU make 3.81, which ignores `.SHELLFLAGS`. No recipe depends on
  `.SHELLFLAGS`: loops use `|| exit 1`, and the toy check captures output instead of using a
  pipe.

## 4.4 Beyond make: stamps where the heavy work lives

The benchmark runner, CCC and parsec scripts get the stamp pattern from a small shell helper
(tested: one run for the same inputs; stale when an input changes; stale when the artifact is
deleted):

```bash
# stamp.sh — content-keyed stamps for heavy, idempotent steps (source me).
#   stamp_fresh <file> <input>...   true iff <file> records exactly these inputs
#   stamp_write <file> <input>...   record them; call ONLY after the step succeeded
# Keys are hashed with `git hash-object` (git is present wherever these scripts run;
# sha256sum is not on macOS). Put <file> INSIDE the artifact it vouches for.
stamp_key()   { printf '%s\n' "$@" | git hash-object --stdin; }
stamp_fresh() { local f="$1"; shift; [ -f "$f" ] && [ "$(cat "$f")" = "$(stamp_key "$@")" ]; }
stamp_write() { local f="$1"; shift; mkdir -p "$(dirname "$f")" && stamp_key "$@" >"$f.tmp" && mv "$f.tmp" "$f"; }
```

How it would be used:

- **Pin every clone.** In `ci_setup.sh`, give tau2-bench, skillsbench and rfe-creator a
  `*_REF` default next to the existing skillberry-benchmarks pin.
  - Stamp the clone in `<clone>/.capevolve-stamp` and the editable install in
    `$VENV/.capevolve-stamps/<name>`. The install stamp lives in the venv, so a recreated venv
    re-installs.
  - Replace `fetch --all` and `reset --hard origin/main` with "fetch the pinned ref only when
    the stamp is stale".
  - Echo every resolved ref into `runmeta.json`.
  - This closes finding 2 of §1.4.6: tau2 unpinned and frozen in four places.
- **The AAP2 bake.** `stamp_fresh "$OUT/.capevolve-inputs" "$(git hash-object "$SPEC")" "$MODEL" "$HARNESS_REF"`
  skips a paid LLM regeneration when nothing changed.
- **CCC's patched ubuntu image.** Replace the hand-bumped `-v7` with a hash of the inline
  Dockerfile, and also require `podman image exists` (P3).
- **Run provenance (P6).** Port the ~60 relevant lines of `git_state.py` (`compute_version` and
  `_dirty_fingerprint`; stdlib only) into `cap_evolve`. Write `code_version` (for example
  `g6af27e2-dirty-1a2b3c4`) into each run's metadata at start, and show it in the dashboard
  masthead and in `report.md`.

## 4.5 Phased plan

Items marked **◆** were added by the validation in §4.8. Without them, the plan did not
cover every requirement in Parts 1–3. The estimates include them.

**Phase 0 — fix what this survey found.** No new infrastructure; about 1–1.5 days.

1. The two stale v4 assertions, harbor's token parsing test, and telemetry's missing
   `importorskip` (§1.4.5).
2. Make `test_cli_surface` hermetic. Replace `_artifact_stamp`'s `(mtime_ns, size)` with a
   content hash (A3).
3. Pin the six reusable workflows to a SHA and narrow `secrets:` (§3.8). This is also a
   prerequisite for the upstream push discussed in §4.9.
4. Sync `templates/skill/scripts/_bootstrap.py` with the deployed shim. Make the hooks' run-dir
   discovery cover `.capevolve-*/` and nested layouts.
5. Fix the doc drift in §1.4.6, items 8–9. ◆ Also document `SKILLBERRY_BOT_TOKEN`, and name
   `.review/postmerge-algos.md` among the recipes to collapse.
6. ◆ `rfe-creator/utils/fetch_data.sh` must use the venv's Python (the caller's
   `$CAPEVOLVE_PY`), not the system Python, for its PyYAML merge (§1.4.6 #6).
7. ◆ `tau2_airline/run.sh` must honour the same `VENV` that `setup.sh` accepts (§1.4.6 #7).

*Exit criterion:* every suite in the repo passes in a fresh venv, without `CAPEVOLVE_SKILLS_DIR`
set by hand.

**Phase 1 — contributor front door.** About 2 days.

1. Add the §4.3 Makefile, plus `scripts/v4_t2_e1/tests` in `test-packages`.
2. Switch the `ci.yml` job bodies to make targets. Add `test-packages`, `manifest-check` and
   `actions/cache`. ◆ Use the same npm cache in `pages.yml` and in the `benchmarks.yml`
   `aggregate` job, which run the third and fourth cold `npm ci`.
3. Point CONTRIBUTING, the PR template, `.bob/rules`, `.review/` and the Bob workflow inputs at
   `make ci`.
4. ◆ **Python versions.** The docs promise 3.10+, but CI tests only 3.11. Add a `test-core`
   matrix of 3.10 and 3.12 (`PYTHON=python3.X VENV=.venv-3X make test-core`, which the revised
   sketch supports), or raise `requires-python` to what is actually tested.
5. ◆ **Node version.** Declare `"engines": {"node": ">=22"}` and add `.nvmrc`. No document names
   a Node version today.
6. ◆ **`make site-check`.** Install `markdown` into the dev venv, run
   `build_skillsbench_site.py --check` against `skillsbench-history`, and fail on drift.
   Either do that or stop committing `site/skillsbench/**`, which the deploy regenerates
   anyway.
7. ◆ *(Optional, in core.)* `cap-evolve doctor` should warn when the skills directory it
   resolved (for example `~/.claude/skills`) has a different manifest from the checkout it runs
   from. That is the product-side half of the W2 finding; Phase 0.2 only fixes the tests.

*Exit criterion:* `make ci` locally and `ci.yml` run the same commands, and no document lists a
different recipe.

**Phase 2 — heavy operations, provenance and isolation.** About 2–3 days.

1. The stamp helper and pinned refs in `ci_setup.sh` and the example `setup.sh` scripts. Pass
   `--run-ts` timestamps, not fixed tags, where resume is not intended. ◆ Also pin tau2 in the
   OpenShift Dockerfile (one `ARG TAU2_REF`). That is the fourth unpinned copy, and it does not
   need to wait for Phase 3.
2. The AAP2 and CCC image stamps. ◆ Also the parsec agent base image: pin the `ubi9/ubi` base by
   digest, and stamp on the Dockerfile hash plus `podman image exists`.
3. `code_version` in run metadata. ◆ `setup.sh` should stop rewriting the committed
   `run_full/TAU2_COMMIT.txt`, because the resolved ref now goes into the run metadata (P4).
4. ◆ **SpreadsheetBench data.** Pin the dataset tarballs to a commit and verify a recorded
   sha256 in `fetch_data.sh`. `dataset.json` stays the stamp.
5. ◆ **Per-example project directories.** Each example scaffolds into its own
   `.capevolve-<example>/`, as blackbox already does. Running one example's setup then no
   longer wipes another's project. The Phase 0.4 hook discovery already covers `.capevolve-*`.
6. ◆ **One shared setup library for the examples** (`examples/_lib/setup.sh`): venv, core
   install, pinned clone and intake, all built on the stamp helper. The five copies of that
   block are replaced. Where the hand scaffold in toy `run.sh`, `e2e_all_algorithms.sh` and
   `ci.yml` only lays out a project, use `cap-evolve init`.

*Exit criteria:*
- Two runs from the same commit on two machines report the same benchmark refs and
  `code_version`.
- A re-dispatch with unchanged inputs does no clone or install work.
- Running every example's `setup.sh` in sequence leaves every project intact.

**Phase 3 — only when there is a consumer.** 2–3 days each.

1. **Release.** Make `cap_evolve/__init__.py` the single version source (dynamic version in
   all four pyprojects). Add a tag-triggered workflow that builds wheels and publishes to PyPI
   with trusted publishing. ◆ The workflow should also fail if `plugin.json`'s version
   disagrees with the tag.
2. **Runner image.** Add a workflow that builds `openshift/images/cap-evolve-runner`, tagged
   with the git label, with `docker/login-action`, `packages: write` and a `.dockerignore`.
   - Borrow skillberry's label-tag and pull-or-build ideas, and its arbitrary-UID hardening, so
     the `anyuid` SCC can go.
   - ◆ Install the optimizer CLI in the image, since the manifests assume claude-code.
   - ◆ Replace the Job's fixed `--run-ts run1` with a per-Job value.
   - Do **not** copy the store's push job. It has no registry login and has failed 40 runs in a
     row.

## 4.6 When to revisit full adoption

Reconsider only if **both** of these become true:

1. **cap-evolve ships a long-running service as a container image.** For example a hosted
   optimizer or dashboard service with an API and SDK. Today it does not, and the dashboard is
   a local tool.
2. **skillberry-common becomes a dependable upstream.** That means:
   - versioned releases consumed by tag;
   - the stamp system merged upstream;
   - an HTTPS remote;
   - no parse-time side effects;
   - stamps that can live outside the checkout;
   - support for more than one `pyproject.toml`;
   - green CI in its main consumer.

If cap-evolve then wants the framework, it should take it as a pinned dependency (a tag
fetched at build time, or a submodule pinned to a tag), not as a subtree to edit in place.

## 4.7 Feedback worth sending upstream

Most of §2.6 is cheap to fix and would help every Skillberry asset, including the
skillberry-store and skillberry-agent copies that cap-evolve's blackbox arm already runs.
Ranked:

1. `push.yml`: add `docker/login-action` with `packages: write`. Image and SDK publishing on
   `main` has been broken since 2026-07-07.
2. Remove the blank line before the shebang in `check-multiarch.sh` and `split-common.sh`
   (they break under dash).
3. Fix `pre-push` (`ci_pull_request` → `ci-pull-request`; `#!/usr/bin/sh` → `#!/bin/sh`).
4. Fix podman detection: drop the quoted `$(wildcard "~/…")`, or better, accept `DOCKER ?=`
   from the environment. Correct the alias line in the README.
5. Move install stamps into the venv (concept 5). Make `npm ci` depend on the lockfile rather
   than `test -d node_modules`.
6. Remove parse-time side effects (`git remote add`, `mkdir`, `docker inspect`). Use `$(MAKE)`
   in recursive calls. Fix `match_spec.py`'s truthy `return 1`.
7. Sync the store's `skillberry-common/` back upstream (`split-common`), so the stamp system
   exists where other assets can get it.

## 4.8 Validation: does the Part 4 solution cover what Parts 1–3 require?

*Question asked after the first version of this report: does the recommended solution in
Part 4 cover the required solution for cap-evolve, as the report itself defines it?*

**Short answer: it covered the core, but not everything.** The first version of Part 4
covered every *high-value* requirement:

- one contributor entry point with CI parity;
- the suites CI never ran;
- hermetic tests;
- incremental frontend builds;
- pinned, stamped benchmark provisioning;
- provenance;
- the supply-chain fix.

It also covered every workflow listed in §3.3 except the site freshness check.

A requirement-by-requirement check against Parts 1–3 found **12 requirements with no
coverage, and 7 with only partial coverage.** One of the uncovered ones was a defect in the
§4.3 sketch itself. All 19 are now closed:

- the 18 plan gaps are folded into the phased plan (§4.5, marked ◆);
- the sketch defect is fixed and re-verified (§4.3).

The revised plan costs about 1.5–2 days more than the original estimate. Four items remain
out of scope on purpose; they are listed at the end of this section.

**How it was checked.** Every requirement, defect and weakness stated in Parts 1–3 was listed
and traced to the Part 4 item that addresses it. There were 31 in total, from §1.2–1.4,
W1–W12, §3.3 and the §3.6 stamp table. Where a Part 4 artifact could be tested (the Makefile),
the requirement was re-tested rather than read.

Legend: ✅ covered as first written · ◑ partly covered, completed by a ◆ item ·
❌ not covered, added as a ◆ item · ⊘ out of scope by design.

### Contributor workflow and CI

| # | Requirement (source) | Covered by | Status |
|---|---|---|---|
| 1 | One entry point; collapse the six divergent recipes (§1.4.1) | §4.3 `make help`/`make ci`; Phase 1.1–1.3 | ◑ The recipe in `.review/postmerge-algos.md` was not named → Phase 1.3, Phase 0.5 |
| 2 | Run the suites CI never runs: harbor, telemetry, v4 (§1.4.5) | `test-packages`; Phase 0.1, 1.1 | ✅ |
| 3 | Hermetic tests that ignore `~/.claude/skills` (§1.4.5) | `TESTENV` in the sketch; Phase 0.2 | ✅ |
| 4 | Fix the mtime-tick flake (§1.4.5) | Phase 0.2 | ✅ |
| 5 | Every CI check runnable locally: lint-skills, CLI-docs, sync_models, toy, dashboard drift (W5) | `lint`, `toy`, `dashboard`, `ci` targets | ✅ lychee and codespell remain CI-only. Both need non-Python binaries, which is acceptable: they check docs, not code. |
| 6 | Repeat work cached in CI (W5) | `actions/cache` for `ci.yml` | ◑ `pages.yml` and `benchmarks.yml` were not covered → Phase 1.2 |
| 7 | CI tests the Python versions the docs promise: 3.10+ in docs, 3.11 in CI, 3.12 on the runner (§1.2) | — | ❌ → Phase 1.4 |
| 8 | A declared Node version (§1.2) | — | ❌ → Phase 1.5 |
| 9 | **The venv stamp is tied to the interpreter version (§1.4.3).** The sketch repeated the weakness it criticises. | — | ❌ **Fixed in the §4.3 sketch and re-verified.** A mismatched venv is refused, never deleted. A user's venv of the right version is adopted. |

### Generated artifacts

| # | Requirement (source) | Covered by | Status |
|---|---|---|---|
| 10 | Freshness check for `manifest.json` (§1.4.4) | `manifest-check` | ✅ |
| 11 | Freshness check for `site/skillsbench` (§1.4.4, W10) | Mentioned only in §3.3 | ❌ → Phase 1.6 |
| 12 | `TAU2_COMMIT.txt` no longer dirties the tree (§1.4.4, P4) | P4 named it; no phase did | ◑ → Phase 2.3 |
| 13 | `run_full/ui` goes stale silently (§1.4.4) | — | ⊘ It is a frozen snapshot of a historical run, not a build output. Its README already says so; regenerating it would change history. |

### Benchmark runner, examples and heavy operations

| # | Requirement (source) | Covered by | Status |
|---|---|---|---|
| 14 | Pin tau2 in all four places (§1.4.6 #2) | Phase 2.1 (CI and examples), Phase 3.2 (image) | ◑ The image pin was left waiting for Phase 3 → Phase 2.1 |
| 15 | Pin and stamp skillberry-benchmarks, skillsbench and rfe-creator clones (§1.4.3) | §4.4; Phase 2.1 | ✅ |
| 16 | Stamp the AAP2 LLM bake (§1.4.3) | §4.4; Phase 2.2 | ✅ |
| 17 | Recipe-keyed, reconciled stamp for CCC's patched image (§1.4.3) | §4.4; Phase 2.2 | ✅ |
| 18 | Pin and stamp the parsec base image (§1.4.3, §3.6) | Listed in the §3.6 table; no phase | ❌ → Phase 2.2 |
| 19 | Pin and checksum the SpreadsheetBench dataset (§1.4.3) | — | ❌ → Phase 2.4 |
| 20 | No silent resume from fixed `--run-ts` (W7, W9) | Phase 2.1 (examples) | ◑ OpenShift `run1` was not covered → Phase 3.2 |
| 21 | Examples must not wipe each other's `.capevolve/project` (W7) | — | ❌ → Phase 2.5 |
| 22 | De-duplicate the venv and scaffold blocks in five example scripts; use `cap-evolve init` (§1.4.1, W1) | — | ❌ → Phase 2.6 |
| 23 | Provenance for runs started outside CI (W12) | §4.4; Phase 2.3 | ✅ |

### Defects, operations and release

| # | Requirement (source) | Covered by | Status |
|---|---|---|---|
| 24 | Defects #3, #4, #5 and #8–9 of §1.4.6 | Phase 0.3–0.5 | ✅ |
| 25 | Defect #6: rfe-creator needs PyYAML in the system Python | — | ❌ → Phase 0.6 |
| 26 | Defect #7: `run.sh` ignores `VENV` | — | ❌ → Phase 0.7 |
| 27 | OpenShift image gaps (W9): unpinned tau2, no `.dockerignore`, `anyuid`, no optimizer CLI | Phase 3.2 | ◑ The optimizer CLI was missing → Phase 3.2; the pin moved to Phase 2.1 |
| 28 | Version kept in six places (W12) | Phase 3.1 (four pyprojects and `__init__`) | ◑ `plugin.json` was not covered → Phase 3.1 |
| 29 | `SKILLBERRY_BOT_TOKEN` undocumented (W6) | — | ❌ → Phase 0.5 |
| 30 | A stale `~/.claude/skills` install silently wins over the checkout (W2, product behaviour) | Only the test side (Phase 0.2) | ❌ → Phase 1.7 (optional, a core change) |
| 31 | Reusable workflows at `@main` with `secrets: inherit` (§3.8) | Phase 0.3 | ✅ |

**Totals (31 requirements):** 11 ✅, 7 ◑, 12 ❌ (11 added to the plan, 1 fixed in the
sketch), 1 ⊘. The `run_full/ui` row is the ⊘.

### Out of scope on purpose

These four items were reviewed and deliberately left out, so they are not gaps:

- **Consolidating the nine Python-environment strategies (§1.4.2).** They exist because
  different tools need different Pythons. The plan does not try to unify them. Instead it makes
  them *safe*: every install stamp now lives in, and is keyed on, its own venv.
- **Demo-video caching (W11, §3.6).** It is low value, and the pipeline is manual and
  macOS-only. The stamp helper applies if it is ever wanted.
- **Refactoring duplicated literals in the CCC and parsec scripts (W8).** That is code hygiene,
  not infrastructure adoption. It is worth doing whenever the parsec staging is next touched.
- **Variant user-install commands in user docs (`pip install ./core` vs `-e`).** These are
  intentional. Users install, contributors install editable. Only the contributor recipes are
  collapsed.

**Effort after validation.**

| Phase | Before | After |
|---|---|---|
| 0 | ≤1 day | 1–1.5 days |
| 1 | 1–2 days | about 2 days |
| 2 | 1–2 days | 2–3 days |
| 3 | unchanged | unchanged |

So the middle ground is about 5–6.5 days before Phase 3, against roughly 2–3 weeks plus
upkeep for full adoption, which still delivers less (§3.5). **The §4.1 verdict stands.**

## 4.9 What changes if skillberry-store's `skillberry-common/` is pushed upstream?

*Question: how would the Part 4 answer change if the updated skillberry-common in
skillberry-store were pushed to its upstream repository?*

### The push is feasible (verified by simulation)

The push was rehearsed on throwaway copies of both repositories. The store's `pull-common`,
then `split-common`, then a push to upstream `main`:

1. **Pulling upstream into the store** conflicts in two files: `dev.mk` (6 hunks) and
   `docker.mk` (12 hunks). Every hunk is upstream's *old* code that the store replaced, such as
   the mtime `code-scan` that #324 replaced with `git_state.py`. Taking the store side
   throughout is correct. The merge then adds only upstream's `.github/workflows/*` and
   `trigger-templates/`; nothing else changes.
2. **The split fast-forwards onto upstream `main`.** No force-push is needed.
3. **The result:**
   - upstream `main` gains `git_state.py`, `install-requirements.sh`,
     `docker-reconcile-stamp.sh` and `stage-extra-copy.sh` (13 files, +1417/−300);
   - the six reusable workflows cap-evolve calls stay **byte-identical**.

**One hazard has to be stated.** A `push-common` without first pulling is rejected: the
store's un-pulled split is not a fast-forward of upstream `main`, and it contains no `.github/`
**(verified)**. Someone forcing it, or replacing the upstream tree with the store's copy, would
**delete `.github/workflows/`**. That would instantly break cap-evolve's six `@main` callers:
CodeQL, the Bob workflows and the labellers. The push must go through `split-common` and a
reviewed merge. And cap-evolve should pin its callers to a SHA first (Phase 0.3), so that no
upstream event can break or exploit them.

### What the push fixes

It removes **reason 2 of §4.1**: "the version worth adopting is not the one available". After
the push, upstream would have the stamp system, and adopting it would no longer mean taking on
a third, divergent copy.

### What it leaves unchanged

Three things stay as they are:

1. **Fit (reason 1) does not change.** The framework still assumes one service per repository,
   one active venv, one root `pyproject.toml`, an image and an SDK. None of the §3.1 mismatches
   depend on where the code lives.
2. **The defects (reason 3) travel with the code.** In the simulated upstream, **12 of the 14
   defects in §2.6 are still present**: numbers 2–6 and 8–14, each re-checked on the pushed
   tree. The two that stay behind (#1, the GHCR login in `push.yml`, and #7, the UI
   `node_modules` stamp) live in store-only files.

   Pushing as-is moves the hazards cap-evolve would hit (parse-time `git remote add`,
   venv-agnostic install stamps, dead podman detection, dash-broken scripts) to the place
   cap-evolve would consume them from.
3. **The size of the need (reason 4) does not change.** cap-evolve still needs about 100 lines
   of make and a shell helper, and most of the stamp value still lives in `ci_setup.sh` and the
   CCC/parsec scripts.

### The §4.6 conditions after the push

| Condition for revisiting full adoption | After the push |
|---|---|
| cap-evolve ships a long-running service image | Unchanged: no |
| Stamp system merged upstream | **Met** |
| Versioned releases consumed by tag | Not met: upstream has **no tags** at all |
| HTTPS remote | Not met: `Makefile.default` still uses `git@github.com:` |
| No parse-time side effects | Not met (defect 9) |
| Stamps that can live outside the checkout | Not met (defect 6) |
| More than one `pyproject.toml` | Not met |
| Green CI in its main consumer | Not met: the store's `push.yml` stays red until defect 1 is fixed in the store |

**So the push meets one of the seven framework conditions, and none of the product condition.**

### The answer after the push

**The verdict does not change: still no wholesale adoption, and still the §4.2 middle ground.**
Four details do change:

1. **Take code, not just ideas, where a whole file is useful on its own.** With upstream
   authoritative, a single self-contained file can be *vendored from a pinned upstream commit*
   rather than re-written. The source SHA is recorded in the file header, and a small CI check
   diffs it against that commit.
   - The best candidate is the label and fingerprint logic in `git_state.py` (P6).
   - This does **not** extend to `.mk` files or the subtree. Phase 2.3 still places the code
     inside `cap_evolve`: it must ship in the wheel, run without make and stay stdlib-only, and
     `git_state.py` already is stdlib-only.
2. **Phase 3.2 (runner image) gets a real alternative to borrowing.** If defects 4, 8, 9 and 14
   are also fixed upstream, `docker.mk` could be *included* from a pinned upstream ref, with
   cap-evolve's own `local.mk`.
   - That trades about a day of writing an image workflow for a dependency on the framework's
     service-shaped variables (`SERVICE_PORTS`, `SERVICE_ENTRY_MODULE`), which a batch runner
     image does not have.
   - On balance, borrowing still wins for one image. Including the upstream file wins only if
     cap-evolve ends up publishing several images.
3. **The blackbox arm benefits only marginally.** cap-evolve also drives skillberry-agent
   through the same framework: `blackbox_env.py:67-71` relies on skillberry-common's PID
   sentinels.
   - Once the agent pulls the new upstream, it gains the git-state label and reconciled docker
     stamps.
   - Its install was already stamped: the old upstream keys `install-requirements` on
     `pyproject.toml` and the `.venv` mtime, in a vendor directory that persists in
     `$CAPEVOLVE_CI_CACHE`.
   - So the push saves cap-evolve little time. Its workarounds for `/tmp` sentinels and
     truncated logs stay necessary until defect 12 is fixed upstream.
4. **Pushing the defect fixes upstream becomes a single, worthwhile act.** The fixes are in
   §4.7. They would now reach every Skillberry asset at once, including the two that cap-evolve
   drives. The best order is:
   1. fix §4.7 items 2–6 in the store's copy;
   2. `split-common`, merge upstream, and **tag** the result;
   3. cap-evolve pins its reusable-workflow callers to that tag's SHA.

   That ordering moves up to four §4.6 conditions:
   - no parse-time side effects comes from item 6;
   - stamps outside the checkout comes from item 5;
   - versioned releases comes from the tag;
   - the HTTPS remote needs one more change: `SB_COMMON_REPO` in `Makefile.default` becomes an
     `https://` URL.

   It leaves multi-`pyproject` support, green CI and the product condition, so the verdict would
   *still* hold.

**When the verdict would flip.** Full adoption becomes reasonable only after all of these:

- the push;
- the defect fixes;
- a tagged release;
- support for several `pyproject.toml` files and for stamps outside the checkout;
- cap-evolve shipping a service image.

Even then it should be consumed as a pinned, tagged dependency, never as a subtree edited in
place (§4.6).

---

# Appendix A — How the findings were verified

All of this ran on disposable copies under the job's temp directory. Nothing in this
repository was changed except this file.

| Claim | Command(s) |
|---|---|
| cap-evolve suite results (§1.4.5) | `python3 -m venv V && V/bin/pip install -e "./core[dev]" -e "./dashboard/backend[dev]"`; `pytest core/tests` (with and without `CAPEVOLVE_SKILLS_DIR=$PWD/skills`, and with a clean `HOME`); `pytest dashboard/backend/tests capevolve_harbor/tests capevolve_telemetry/tests scripts/v4_t2_e1/tests ci/benchmarks/lib` |
| mtime-tick collision | Python: two back-to-back same-size `write_bytes` calls on ext4 gave the same `st_mtime_ns` |
| Manifest determinism | `python3 skills/_registry/build_manifest.py skills && git status --short` (clean) |
| CI history | `gh run list -R skillberry-ai/cap-evolve -w CI -b main`; `gh run list -R skillberry-ai/skillberry-store -w push.yml -L 40` (40 failures); `gh run view <id> --log-failed` (GHCR 403) |
| Subtree drift | `git clone` of `skillberry-ai/skillberry-common`; `diff -rq sbc sbs/skillberry-common`; `git log`/`git diff --shortstat 2f2f1d9 HEAD -- skillberry-common` in the store |
| Parse-time side effects | `make help` on a copy of the store, then `git remote -v` (remote added); `make print_build_version` outside a venv (`python: No such file or directory`) |
| Podman detection | `HOME=<dir with .bashrc: alias docker='podman'> make -f probe.mk show-docker` → `DOCKER=docker` |
| dash shebang breakage | `sh -c 'skillberry-common/scripts/check-multiarch.sh podman …'` and `split-common.sh` on Debian (`/bin/sh → dash`) |
| `match_spec.py` | `match_spec.py 3.12+ 4.0.0` → exit 0; `match_spec.py 3.11 2.11.0` → exit 0 |
| Install stamp vs. venv | `touch .stamps/install-requirements-` in a fresh venv, then `make -n install-requirements` (no install planned) |
| Sketch Makefile (§4.3) | `git archive HEAD` into a fresh git repo; the timings and outcomes in the §4.3 table; `make -k ci` |
| Stamp helper (§4.4) | Unit-style run: same inputs → one execution; changed input → stale; deleted artifact → stale |
| Revised sketch (§4.3, §4.8 row 9) | Fresh `make install`, then a no-op repeat; `make install PYVER=3.12` against a 3.11 `.venv` (refused, venv kept); `PYTHON=/nonexistent make install` (clear error); a user-made `python3 -m venv .venv` (adopted); `toy`, `lint`, `manifest-check`, `test-dashboard`, `test-ci-lib` re-run green |
| Upstream push (§4.9) | On copies: `git subtree pull --prefix skillberry-common <upstream> main` in the store (conflicts in `dev.mk` (6 hunks) and `docker.mk` (12), resolved store-side), then `git subtree split`, `merge-base --is-ancestor` (fast-forward), push to a bare upstream copy, `git diff --quiet 6136693 main -- .github trigger-templates` (unchanged), and a per-defect grep on the pushed tree. The un-pulled split was checked for fast-forward and for the presence of `.github/`. |

