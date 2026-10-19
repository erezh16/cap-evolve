"""Assemble the three AppWorld evaluation run folders for the Box archive (docs/BACKUP_BOX.md).

    python build_backup.py OUT_DIR

Copies with metadata preserved (shutil.copy2 / copytree), derives the CI-compatible files, writes
README.md, runmeta.json and MANIFEST.json per run, and records capture timing in OUT_DIR/timing.json.
Never modifies a source. Secrets are never copied, and a scan checks that.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

AW = Path("/tmp/aw_eval")
RUNS = AW / "runs"
REPO = Path("/workspace/worktrees/base")
HOME = Path.home()
PROJ = HOME / ".claude" / "projects"
CTMP = Path(f"/tmp/claude-{os.getuid()}")
OUT = Path(sys.argv[1])

R1 = "2026-10-13-appworld-capevolve-hillclimb-gptoss120b-sonnet55-original-breach"
R2 = "2026-10-13-appworld-altkevolve-v130-retrieval-gptoss120b-sonnet55-original"
R3 = "2026-10-15-appworld-capevolve-hillclimb-gptoss120b-sonnet55-fix-clean"

log_lines: list[str] = []


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    log_lines.append(line)


def cp(src: Path, dst: Path) -> None:
    """Copy a file or a whole tree, keeping times and modes; symlinks are kept as symlinks."""
    src, dst = Path(src), Path(dst)
    if not src.exists() and not src.is_symlink():
        raise FileNotFoundError(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir() and not src.is_symlink():
        shutil.copytree(src, dst, symlinks=True, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dst, follow_symlinks=False)


def sh(*cmd, cwd=None, env=None) -> str:
    r = subprocess.run(list(cmd), capture_output=True, text=True, cwd=cwd, env=env)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd} failed: {r.stderr[-800:]}")
    return r.stdout


def jdump(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=str) + "\n")


# ---------------------------------------------------------------------------- sources per run
def cape_run_dir(name: str) -> Path:
    return RUNS / name / ".capevolve" / f"run_{name}"


def sessions_of(name: str) -> dict[str, Path]:
    """Optimizer claude-code session dirs of a cape run: {dir_name: path}."""
    tag = name.replace("_", "-")
    found = {}
    for base in (PROJ, RUNS / "optimizer_transcripts" / name):
        if base.is_dir():
            for d in base.iterdir():
                if d.is_dir() and f"runs-{tag}--capevolve-run-{tag}" in d.name:
                    found[d.name] = d
    return found


def session_ids(dirs: dict[str, Path]) -> set[str]:
    return {f.stem for d in dirs.values() for f in d.glob("*.jsonl")}


def copy_cape_arm(run_root: Path, name: str, role: str) -> dict:
    """The cap-evolve tree byte for byte, plus host/ (optimizer sessions) for one training attempt."""
    base = run_root if role == "" else run_root / role
    cp(RUNS / name / ".capevolve", base / "capevolve")
    host = base / "host"
    dirs = sessions_of(name)
    for dname, d in dirs.items():
        cp(d, host / "transcripts" / dname)
    ids = session_ids(dirs)
    for sid in ids:
        for sub in ("file-history", "session-env"):
            p = HOME / ".claude" / sub / sid
            if p.exists():
                cp(p, host / sub / sid)
    tag = name.replace("_", "-")
    if CTMP.is_dir():
        for d in CTMP.iterdir():
            if f"runs-{tag}--capevolve-run-{tag}" in d.name:
                cp(d, host / "claude-tmp" / d.name)
    rd = cape_run_dir(name)
    for f in sorted((rd / "work").glob("*.optimizer.stderr")):
        cp(f, host / "optimizer_stderr" / f.name)
    for f in sorted((rd / "work").glob("*/INSTRUCTIONS.md")):
        cp(f, host / "instructions" / f"{f.parent.name}.INSTRUCTIONS.md")
    proj = RUNS / name / ".capevolve" / "project"
    launch = {"command": f"bash examples/appworld/scripts/launch_cape_hc.sh {RUNS / name}",
              "spec": str(proj / "capevolve.yaml"), "optimizer": "claude-code",
              "optimizer_cli_template": "claude -p {prompt_text} --permission-mode acceptEdits --allowedTools Bash "
                                        "--disallowedTools Monitor --model {model} --max-turns 200 --max-budget-usd 15"}
    jdump(launch, host / "launch_args.json")
    return {"sessions": len(ids), "session_dirs": len(dirs)}


def rounds_and_champion(run_root: Path, name: str, role: str) -> dict:
    base = run_root if role == "" else run_root / role
    rd = cape_run_dir(name)
    events = [json.loads(l) for l in (rd / "events.jsonl").read_text().splitlines() if l.strip()]
    steps = [e for e in events if e.get("kind") == "step"]
    for i, e in enumerate(steps, 1):
        cid = e["candidate"]
        rdir = base / "rounds" / f"r{i}_{cid}"
        jdump(e, rdir / "verdict.json")
        w = rd / "work" / cid
        for fn in ("PROCESS.md", "DIAGNOSIS.json", "JOURNAL.md"):
            if (w / fn).is_file():
                cp(w / fn, rdir / fn)
        parent = rd / "candidates" / str(e.get("parent") or "seed")
        cand = rd / "candidates" / cid
        if cand.is_dir() and parent.is_dir():
            d = subprocess.run(["diff", "-ruN", "-x", ".git", "-x", "trajectories", "-x", "guidance",
                                str(parent), str(cand)], capture_output=True, text=True).stdout
            (rdir / "diff.patch").write_text(d)
    best = json.loads((rd / "state.json").read_text())["best_id"]
    ch = base / "champion"
    for sub in ("policy", "tools", "memory"):
        if (rd / "candidates" / best / sub).exists():
            cp(rd / "candidates" / best / sub, ch / sub)
    d = subprocess.run(["diff", "-ruN", str(rd / "candidates" / "seed"), str(rd / "candidates" / best),
                        "-x", "PROCESS.md", "-x", "JOURNAL.md", "-x", "DIAGNOSIS.json", "-x", "INSTRUCTIONS.md",
                        "-x", "*.md.bak"], capture_output=True, text=True).stdout
    (ch / "capability.diff").write_text(d)
    (ch / "CHAMPION.txt").write_text(f"{best}\n")
    return {"rounds": len(steps), "champion": best,
            "accepted": [e["candidate"] for e in steps if e.get("accept")]}


def ci_data(run_root: Path, name: str, role: str) -> None:
    """data/: metrics.jsonl, steps.jsonl, report.md via the CI metrics tool (metrics.py suite)."""
    base = run_root if role == "" else run_root / role
    rd = cape_run_dir(name)
    data = base / "data"
    data.mkdir(parents=True, exist_ok=True)
    rep = sh(str(AW / "venv-aw/bin/python"), str(REPO / "ci/benchmarks/lib/metrics.py"), "suite", str(rd),
             "--bench", "appworld", "--tier", "smoke", "--agent", "openai/gpt-oss-120b-a100", "--iters", "6",
             "--jsonl", str(data / "metrics.jsonl"), "--steps-jsonl", str(data / "steps.jsonl"),
             "--optimizer-model", "aws/claude-sonnet-5-5")
    (data / "report.md").write_text(rep)
    cp(rd / "events.jsonl", data / "events.jsonl")
    # CI's per-task export, mirroring examples/tau2_airline/export_run_artifacts.sh
    per = {}
    for split_dir in sorted((rd / "rollouts").iterdir()):
        tags: dict = {}
        for f in sorted(split_dir.glob("*.json")):
            task, tag, trial = f.stem.split("__")
            sc = json.loads(f.read_text()).get("score", {})
            row = tags.setdefault(tag, {}).setdefault(task, {"trials": [], "feedback": ""})
            row["trials"].append(sc.get("reward"))
            row["feedback"] = sc.get("feedback", "")
        for tag in tags.values():
            for row in tag.values():
                v = [x for x in row["trials"] if x is not None]
                row["reward"] = sum(v) / len(v) if v else None
        per[split_dir.name] = tags
    for split, tags in per.items():
        jdump(tags, data / f"{split}_per_task.json")


# ---------------------------------------------------------------------------- GitHub record
def fetch_posts() -> list[dict]:
    pages = json.loads(sh("gh", "api", "repos/skillberry-ai/cap-evolve/issues/804/comments", "--paginate", "--slurp"))
    return [{"id": c["id"], "url": c["html_url"], "created_at": c["created_at"], "updated_at": c["updated_at"],
             "user": c["user"]["login"], "body": c["body"]} for page in pages for c in page]


def classify(post: dict) -> str:
    b = post["body"][:200]
    if "ACE smoke test" in b or "ACE vs the seed" in b:
        return "ace"
    if post["created_at"] < "2026-10-14T00:00:00Z":
        return "plan"
    if post["created_at"] < "2026-10-15T11:42:00Z":
        return "original"
    return "fix"


def write_posts(dst: Path, posts: list[dict], keep: set[str]) -> int:
    n = 0
    for p in posts:
        if classify(p) not in keep:
            continue
        n += 1
        f = dst / f"{p['created_at'][:19].replace(':', '')}__{p['id']}.md"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f"<!-- {p['url']} | {p['user']} | created {p['created_at']} | updated {p['updated_at']} -->\n\n"
                     + p["body"] + "\n")
    jdump([p for p in posts if classify(p) in keep], dst / "comments.json")
    # the full thread, every comment with its class, so nothing is lost by the per-run selection
    jdump([dict(p, class_=classify(p)) for p in posts], dst / "full_thread_all_comments.json")
    return n


def gh_json(*args) -> object:
    return json.loads(sh("gh", *args))


# ---------------------------------------------------------------------------- runmeta / readme
def runmeta(run_id: str, algorithm: str, iterations, trials, extra: dict) -> dict:
    sha = sh("git", "-C", str(REPO), "rev-parse", "HEAD").strip()
    m = json.loads((RUNS / "manifest.json").read_text())
    return {"schema": "capevolve-runmeta (benchmarks.yml) + archive fields", "run_id": run_id,
            "run_url": "https://github.com/skillberry-ai/cap-evolve/issues/804", "bench": "appworld",
            "tier": "smoke-test_normal", "event": "local", "source": "docs/EVAL_SMOKE_TEST.md",
            "pr": None, "branch": "erezh-eval1", "sha": sha,
            "agent_model": "openai/gpt-oss-120b-a100", "agent_model_requested": "openai/gpt-oss-120b-a100",
            "agent_provider": "ibm-rits", "agent_provider_skipped": "",
            "optimizer_model": "aws/claude-sonnet-5-5", "optimizer_model_requested": "aws/claude-sonnet-5-5",
            "optimizer_provider": "claude-code gateway (ANTHROPIC_BASE_URL)", "optimizer_provider_skipped": "",
            "algorithm": algorithm, "iterations": iterations, "trials": trials, "gate_k_se": 1.0,
            "warm_seed": False, "reward_metric": "success (all requirement checks pass)",
            "appworld_commit": m["appworld"]["commit"], "appworld_patch_sha256": m["appworld"]["patch_sha256"],
            "splits": {"search": "train ∪ dev (147)", "held_out": "test_normal (168)"}, **extra}


# ---------------------------------------------------------------------------- shared pieces
def common(run_root: Path, posts: list[dict], post_keep: set[str]) -> dict:
    stats = {}
    stats["posts"] = write_posts(run_root / "posts" / "issue-804", posts, post_keep)
    drafts = run_root / "posts" / "local_drafts"
    for f in sorted((RUNS / "posts").glob("*.md")):
        cp(f, drafts / f.name)
    cp(RUNS / "posts" / "issues", drafts / "issues")
    for d in ("EVAL_SMOKE_TEST.md", "EVAL_SMOKE_TEST_FIX.md", "EVAL_SMOKE_TEST_SUMMARY.html", "BACKUP_BOX.md"):
        if (REPO / "docs" / d).is_file():
            cp(REPO / "docs" / d, run_root / "docs" / d)
    env = run_root / "env"
    cp(RUNS / "manifest.json", env / "manifest.json")
    cp(REPO / "examples/appworld", env / "examples_appworld")
    cp(AW / "reference", env / "reference")
    cp(AW / "lint_cache.json", env / "lint_cache.json")
    cp(AW / "split_ids.json", env / "split_ids.json")
    (env / "appworld_git_diff.patch").write_text(sh("git", "-C", str(AW / "appworld"), "diff"))
    (env / "appworld_commit.txt").write_text(sh("git", "-C", str(AW / "appworld"), "rev-parse", "HEAD"))
    for f in ("build_env.sh", "patch_lm.py", "a8.py", "audit_transcripts.py", "audit_run.py", "stability.py",
              "make_summary.py"):
        if (AW / f).is_file():
            cp(AW / f, env / "scripts" / f)
    for f in RUNS.glob("*.sh"):
        cp(f, env / "scripts" / f.name)
    cp(AW / "bin", env / "scripts" / "bin_claude_lock_shim")
    for f in ("cape_hc_estimate.txt",):
        if (RUNS / f).is_file():
            cp(RUNS / f, env / f)
    return stats


def progress(run_root: Path, names: list[str]) -> None:
    lg = run_root / "logs"
    for n in names:
        p = AW / "progress" / n
        if p.is_file():
            cp(p, lg / n)


# ---------------------------------------------------------------------------- per run
def build_r1(posts) -> dict:
    root = OUT / R1
    st = {"arm": copy_cape_arm(root, "cape_hc_s0", ""), "rounds": rounds_and_champion(root, "cape_hc_s0", "")}
    ci_data(root, "cape_hc_s0", "")
    cp(RUNS / "final", root / "final_window")
    iso = root / "isolation"
    cp(RUNS / "isolation_scan.json", iso / "isolation_scan_latest_run_cape_hc_s2.json")
    cp(AW / "audit_transcripts.py", iso / "audit_transcripts.py")
    # round-2 helper scripts the subagents wrote, and the sealed data-root copy
    diag = Path("/tmp/diag")
    for f in sorted(diag.glob("*.py")):
        cp(f, iso / "diag_round2_scripts" / f.name)
    sealed = iso / "diag_root_SEALED.tar"
    tmp = Path(tempfile.mkdtemp(prefix="seal_", dir=str(AW)))
    try:
        os.chmod(diag / "root", 0o700)
        with tarfile.open(sealed, "w") as t:          # uncompressed, on purpose
            t.add(diag / "root", arcname="diag_root")
    finally:
        os.chmod(diag / "root", 0o000)
        os.rmdir(tmp)
    (iso / "diag_root_SEALED.README.md").write_text(
        "# SEALED: train/dev gold data\n\n`diag_root_SEALED.tar` is the copy of `root_opt` that cap-evolve's "
        "optimizer subagents made to `/tmp/diag/root` in round 2 (finding F14). It holds AppWorld train/dev "
        "ground truth (solutions, answers, evaluation code). It is kept as evidence of the breach. Do not "
        "unpack it into any path an optimizer can read, and do not redistribute it (AppWorld rule).\n")
    acc = iso / "acceptance"
    cp(RUNS / "a6_dry", acc / "a6_dry")
    for f in ("probe_a2", "probes"):
        if (RUNS / f).exists():
            cp(RUNS / f, acc / f)
    for f in ("altk_probe", "altk_probe2"):
        cp(RUNS / f, acc / f)
    for f in ("acceptance.log", "a6.out", "a6b.out", "a8.out", "build.log", "build.out", "altk_install.out"):
        if (AW / "progress" / f).is_file():
            cp(AW / "progress" / f, acc / "logs" / f)
    progress(root, ["cape_hc.log", "cape_hc.out", "final.log", "final_run.out", "final_freeze.out",
                    "run_final.out", "PROGRESS.md", "status.out", "optimizer_guard.log"])
    st |= common(root, posts, {"plan", "original"})
    meta = runmeta(R1, "hill-climb (focus all)", 8, 1, {
        "conclusion": "completed; DISCARDED (isolation breach F14)", "capevolve_run": "cape_hc_s0",
        "date_start": "2026-10-13T15:59:01Z", "date_end": "2026-10-14T09:41:29Z",
        "iterations_note": "6 scored + 2 lost to the guard bug (F15); budget raised 6 -> 8 on resume",
        "metric_calls": 1029, "optimizer_usd": 67.84,
        "champion": st["rounds"]["champion"], "search_val": 0.884,
        "test_normal": {"tgc": 0.536, "sgc": 0.348, "window": "final (2026-10-14)"},
        "isolation": "breach: round 2 read train/dev answers and ran the grader; 0 test-id hits"})
    jdump(meta, root / "runmeta.json")
    return st


def build_r2(posts) -> dict:
    root = OUT / R2
    st = {}
    cp(RUNS / "altk", root / "altk")
    ch = root / "champion"
    cp(RUNS / "final" / "artifacts" / "altk", ch)   # the frozen test_normal artifact (retrieval blocks for test)
    cp(RUNS / "altk" / "cand_ret_dev", root / "champion_dev_render")
    cp(RUNS / "final", root / "final_window")
    cp(RUNS / "final2" / "results.jsonl", root / "final_window_2_rescored" / "results.jsonl")
    cp(RUNS / "final2" / "stability.json", root / "final_window_2_rescored" / "stability.json")
    (root / "final_window_2_rescored" / "README.md").write_text(
        "The second final window (2026-10-15) re-scored this byte-identical ALTK artifact alongside the "
        "fixed cap-evolve run. Rows with arm == 'altk' in results.jsonl are this arm's 2 extra trials. "
        "The full window lives in the fix run's folder.\n")
    data = root / "data"
    # CI-compatible steps: the ALTK pipeline as booked steps
    steps = [{"step": "seed_train_rollouts", "rollouts": 90, "source": "cape_hc_s0 baseline (shared)"},
             {"step": "mine", **json.loads((RUNS / "altk/mining_summary.json").read_text())},
             {"step": "dose_selection", **json.loads((RUNS / "altk/dose_selection.json").read_text())}]
    data.mkdir(parents=True, exist_ok=True)
    (data / "steps.jsonl").write_text("".join(json.dumps(s, default=str) + "\n" for s in steps))
    rows = [json.loads(l) for l in (RUNS / "final/results.jsonl").read_text().splitlines() if l.strip()]
    (data / "metrics.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows if r["arm"] == "altk"))
    res = json.loads((RUNS / "final/results.json").read_text())
    (data / "report.md").write_text((RUNS / "final/tables.md").read_text())
    host = root / "host"
    cp(RUNS / "altk" / "optimizer_usage.jsonl", host / "optimizer_usage.jsonl")
    cp(REPO / "examples/appworld/altk", host / "driver_code")
    progress(root, ["altk.log", "altk_pipeline.out", "altk_continue.out", "altk_install.out"])
    st |= common(root, posts, {"plan", "original"})
    meta = runmeta(R2, "altk-evolve v1.3.0 (mine train, lossless consolidation, dose on dev)", None, 1, {
        "conclusion": "completed; retained", "date_start": "2026-10-13T16:22:20Z", "date_end": "2026-10-13T18:26:00Z",
        "guidelines_mined": 1867, "guidelines_after_consolidation": 1715, "dose": "altk-ret",
        "dose_note": "altk-full infeasible: 402,775 chars > 30,000 memory lint (F11)",
        "search_rollouts": 147, "optimizer_calls": 1031,
        "test_normal": {"window_1": {"tgc": res["arms"]["altk"]["tgc"], "sgc": res["arms"]["altk"]["sgc"]},
                        "window_2": {"tgc": 0.473, "sgc": 0.241}}})
    jdump(meta, root / "runmeta.json")
    return st


def build_r3(posts) -> dict:
    root = OUT / R3
    st = {}
    for name, role in (("cape_hc_s1", "attempt1_cape_hc_s1_DISCARDED_generator_leak"),
                       ("cape_hc_s2", "attempt2_cape_hc_s2_SCORED")):
        st[name] = {"arm": copy_cape_arm(root, name, role), "rounds": rounds_and_champion(root, name, role)}
        ci_data(root, name, role)
        progress(root / role, [f"{name}.log", f"{name}.out"])
    cp(RUNS / "final2", root / "final_window")
    iso = root / "isolation"
    cp(RUNS / "isolation_scan.json", iso / "isolation_scan_cape_hc_s2.json")
    cp(RUNS / "isolation_check", iso / "a9_checks")
    for d in (RUNS / "optimizer_transcripts").iterdir():
        if d.name.startswith("-tmp-aw-eval-runs-isolation-check"):
            cp(d, iso / "a9_checks" / "transcripts" / d.name)
    cp(AW / "audit_run.py", iso / "audit_run.py")
    cp(AW / "sbx_try", iso / "claude_sandbox_probe_sbx_try")
    cp(AW / "isocheck_core", iso / "core_isolation_e2e")
    for d in PROJ.iterdir():
        if "isolation-check-sandbox" in d.name or d.name == "-tmp-aw-eval-sbx-try" or "isocheck-core" in d.name:
            cp(d, iso / "claude_sandbox_probe_transcripts" / d.name)
    progress(root, ["final2_run.out", "final.log", "optimizer_guard.log", "PROGRESS.md"])
    st |= common(root, posts, {"plan", "fix"})
    s2 = json.loads((cape_run_dir("cape_hc_s2") / "state.json").read_text())
    r2 = json.loads((RUNS / "final2/results.json").read_text())
    meta = runmeta(R3, "hill-climb (focus all)", 6, 1, {
        "conclusion": "completed; cape_hc_s2 scored, cape_hc_s1 discarded (F19)",
        "date_start": "2026-10-15T11:42:26Z", "date_end": "2026-10-15T21:58:55Z",
        "attempts": {"cape_hc_s1": {"champion": "cand_0001", "search_val": 0.769, "optimizer_usd": 44.23,
                                    "status": "discarded: read task generators of 6 train/dev scenarios"},
                     "cape_hc_s2": {"champion": s2["best_id"], "search_val": s2["spent"]["best_val"],
                                    "optimizer_usd": s2["spent"]["optimizer_usd"],
                                    "metric_calls": s2["spent"]["metric_calls"],
                                    "status": "scored; disclosed deviation F20 (read app implementation source)"}},
        "baseline": "reused from cape_hc_s0 (val 0.361)", "isolation": "namespace wrapper (examples/appworld/sandbox/claude)",
        "test_normal_window_2": {a: {"tgc": r2["arms"][a]["tgc"], "sgc": r2["arms"][a]["sgc"]} for a in r2["arms"]},
        "cape_minus_altk_tgc": {"delta": r2["pairs"]["cape-hc - altk"]["d_tgc"], "ci95": r2["pairs"]["cape-hc - altk"]["ci_tgc"]}})
    jdump(meta, root / "runmeta.json")
    return st


# ---------------------------------------------------------------------------- notice + readme
NOTICE = """# NOTICE: AppWorld protected data

This folder holds derivatives of AppWorld's protected data: task instructions, agent trajectories on
train/dev tasks, test task ids and per-task results, and (R1 only, `isolation/diag_root_SEALED.tar`)
a copy of train/dev ground truth. AppWorld releases that data under Apache 2.0 with one extra
requirement: **any public redistribution must be encrypted**. This archive is a private, access-restricted
team folder (owner's decision, 2026-10-19). Do not make it, or any part of it, public unencrypted.
"""

README = {
R1: """# R1: cap-evolve (hill-climb) on AppWorld: original evaluation, isolation breach

**Status: DISCARDED as a result.** Kept as evidence and for diagnosis.

- What: cap-evolve `hill-climb --focus all`, capabilities `[system-prompt, tools]`, paired gate k = 1.0, 1 trial,
  train = val = official train ∪ dev (147); test sealed. Agent `openai/gpt-oss-120b-a100` (IBM RITS, reasoning
  medium, temperature 0); optimizer `aws/claude-sonnet-5-5` via claude-code. cap-evolve run `cape_hc_s0`, 13–14 Oct 2026.
- Outcome: 6 scored iterations (+2 lost to a guard bug, F15). Champion `cand_0006`, search val 0.884 (seed 0.361).
  Held-out test_normal in final window 1: TGC 53.6 / SGC 34.8 (seed 35.1 / 13.4; ALTK-Evolve 41.1 / 23.2).
- **Breach (F14):** in round 2 the optimizer's subagents read train/dev answers and solutions and ran the grader.
  No test access (0 test-id hits).

Folders: `capevolve/` (the unmodified cap-evolve tree: `project/` + `run_cape_hc_s0/`, loadable by cap-evolve's tools),
`champion/`, `rounds/`, `data/` (CI-compatible metrics/steps/report), `host/` (optimizer sessions and transcripts),
`final_window/` (window 1, shared with R2), `isolation/` (scan, round-2 scripts, sealed gold copy, acceptance checks),
`logs/`, `posts/` (issue #804 comments up to the first summary, drafts, issues/PRs), `docs/`, `env/`.
""",
R2: """# R2: ALTK-Evolve v1.3.0 on AppWorld: original evaluation

**Status: retained.** The ALTK-Evolve artifact is unchanged in both final windows.

- What: guidelines mined from the seed agent's 90 official-train trajectories (shared with R1's baseline),
  lossless consolidation, dose chosen on the 57 dev tasks. Agent `openai/gpt-oss-120b-a100` (RITS); optimizer
  `aws/claude-sonnet-5-5` through litellm. 13 Oct 2026.
- Outcome: 1,867 guidelines mined, 1,715 after consolidation. The full playbook (~83K tokens) failed the memory lint,
  so the retrieval dose was chosen (dev TGC 0.456). Test_normal: window 1 TGC 41.1 / SGC 23.2; window 2 TGC 47.3 / SGC 24.1.

Folders: `altk/` (the whole ALTK run dir: store, mining, renders, dev rollouts, dose selection), `champion/`
(the frozen test_normal artifact), `champion_dev_render/`, `data/`, `host/` (optimizer usage log, driver code),
`final_window/` (window 1, shared with R1), `final_window_2_rescored/`, `logs/`, `posts/`, `docs/`, `env/`.
""",
R3: """# R3: cap-evolve (hill-climb) on AppWorld: fix evaluation (clean training, second final window)

**Status: scored result** (attempt 2). Attempt 1 is discarded but kept.

- Why: R1's champion was built on a round that saw practice answers. The fix re-trains cap-evolve with every optimizer
  call in a namespace wrapper that hides answers, the grader and test data (docs/EVAL_SMOKE_TEST_FIX.md), then re-scores
  all three arms in one new window.
- `attempt1_cape_hc_s1_DISCARDED_generator_leak/`: champion `cand_0001` (val 0.769). Round 1 read AppWorld's task-generator
  code for 6 train/dev scenarios (F19).
- `attempt2_cape_hc_s2_SCORED/`: AppWorld generators hidden too. Champion `cand_0004` (val 0.789), 882 metric calls, $54.16.
  0 answer/test/generator access; disclosed deviation F20 (read app implementation source).
- Final window 2 (test_normal, 168 tasks x 3 arms x 2 trials): cap-evolve TGC 57.1 / SGC 40.2; ALTK-Evolve 47.3 / 24.1;
  seed 31.5 / 10.7. cap-evolve minus ALTK-Evolve: +9.8 TGC [+1.2, +18.5].

Each attempt has `capevolve/` (unmodified tree), `champion/`, `rounds/`, `data/`, `host/`, `logs/`. Run level:
`final_window/` (window 2), `isolation/` (scan, A9 planted-secret checks with transcripts, sandbox probes),
`logs/`, `posts/` (issue #804 fix updates 7–22 and the closing summary), `docs/`, `env/`.
""",
}


def write_readme(root: Path, name: str, timing: dict | None = None) -> None:
    (root / "NOTICE.md").write_text(NOTICE)
    txt = README[name] + "\nProvenance: `runmeta.json`. Every file with its size and sha256: `MANIFEST.json`.\n"
    if timing:
        txt += f"\nBackup: captured {timing['t1_utc']} (assembly {timing['runs'][name]['assemble_seconds']} s).\n"
    (root / "README.md").write_text(txt)


def tool_checks(root: Path, name: str) -> dict:
    """The copied cap-evolve run dirs must load in cap-evolve's own tools, from the backup itself.

    Read-only: `tail --from-start` replays events.jsonl, and the dashboard is rendered in memory
    (reduce_run + render_html), because `dashboard --export` would overwrite the run's original
    dashboard.html inside the backup."""
    out = {}
    probe = (
        "import sys, json; sys.path.insert(0, sys.argv[2])\n"
        "from pathlib import Path\n"
        "from cap_evolve.rundir import RunDir\n"
        "from cap_evolve import dashboard\n"
        "rd = RunDir.open(Path(sys.argv[1]))\n"
        "red = dashboard.reduce_run(rd)\n"
        "html = dashboard.render_html(red, rd)\n"
        "print(json.dumps({'best_id': rd.best_id, 'html_bytes': len(html)}))\n")
    for rd in sorted(root.glob("**/capevolve/run_*")):
        rel = str(rd.relative_to(root))
        env = dict(os.environ, PYTHONPATH=str(REPO / "core"))
        r1 = subprocess.run([str(AW / "venv-aw/bin/cap-evolve"), "tail", str(rd), "--from-start", "--idle-timeout", "5",
                             "--no-color"], capture_output=True, text=True, env=env, timeout=600)
        r2 = subprocess.run([str(AW / "venv-aw/bin/python"), "-c", probe, str(rd), str(REPO / "core")],
                            capture_output=True, text=True, env=env, timeout=600, cwd="/tmp")
        try:
            dash = json.loads(r2.stdout.strip().splitlines()[-1])
        except Exception:  # noqa: BLE001
            dash = {"error": (r2.stderr or r2.stdout)[-400:]}
        out[rel] = {"tail_rc": r1.returncode, "tail_lines": len(r1.stdout.splitlines()),
                    "dashboard_render": dash, "dashboard_rc": r2.returncode}
    return out


# ---------------------------------------------------------------------------- verify
SECRETS = []


def load_secrets() -> None:
    for line in (REPO / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            v = line.split("=", 1)[1].strip().strip('"')
            if len(v) >= 12 and not v.startswith("http"):
                SECRETS.append(v)
    for k in ("ANTHROPIC_AUTH_TOKEN",):
        if len(os.environ.get(k, "")) >= 12:
            SECRETS.append(os.environ[k])
    for line in os.environ.get("ANTHROPIC_CUSTOM_HEADERS", "").splitlines():
        if ":" in line and len(line.split(":", 1)[1].strip()) >= 12:
            SECRETS.append(line.split(":", 1)[1].strip())


def scan_and_manifest(root: Path) -> dict:
    files, hits = [], []
    sealed = root / "isolation" / "diag_root_SEALED.tar"
    for p in sorted(root.rglob("*")):
        if p.is_symlink() or not p.is_file():
            continue
        b = p.read_bytes()
        h = hashlib.sha256(b).hexdigest()
        files.append({"path": str(p.relative_to(root)), "bytes": len(b), "sha256": h})
        if p != sealed:
            for s in SECRETS:
                if s.encode() in b:
                    hits.append(str(p.relative_to(root)))
    return {"files": files, "secret_hits": hits}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    timing = {"t0": time.time(), "t0_utc": datetime.now(timezone.utc).isoformat()}
    load_secrets()
    log(f"secrets loaded for the scan: {len(SECRETS)}")
    posts = fetch_posts()
    log(f"fetched {len(posts)} comments of #804")
    per = {}
    for name, fn in ((R1, build_r1), (R2, build_r2), (R3, build_r3)):
        t = time.time()
        log(f"assembling {name}")
        per[name] = {"stats": fn(posts)}
        per[name]["assemble_seconds"] = round(time.time() - t, 2)
    gh_record = {"issues": {}, "prs": {}}
    for n in (804, 875, 876, 877, 878):
        gh_record["issues"][n] = gh_json("issue", "view", str(n), "--repo", "skillberry-ai/cap-evolve",
                                         "--json", "number,title,state,url,body,createdAt,author,labels")
    for n in (874, 879):
        gh_record["prs"][n] = gh_json("pr", "view", str(n), "--repo", "skillberry-ai/cap-evolve",
                                      "--json", "number,title,state,url,body,createdAt,headRefName,headRefOid,commits,files")
    for name in per:
        jdump(gh_record, OUT / name / "posts" / "github_issues_and_prs.json")
    for name in per:
        per[name]["tool_checks"] = tool_checks(OUT / name, name)
        bad = {k: v for k, v in per[name]["tool_checks"].items()
               if v["tail_rc"] or v["dashboard_rc"] or not v["dashboard_render"].get("html_bytes")}
        log(f"{name}: tool checks {'OK' if not bad else 'FAILED ' + json.dumps(bad)[:400]}")
        if bad:
            return 4
        write_readme(OUT / name, name)
    for name in per:
        t = time.time()
        res = scan_and_manifest(OUT / name)
        if res["secret_hits"]:
            log(f"SECRET HITS in {name}: {res['secret_hits'][:10]}")
            return 3
        tot = sum(f["bytes"] for f in res["files"])
        jdump({"run": name, "generated_utc": datetime.now(timezone.utc).isoformat(),
               "files": len(res["files"]), "bytes": tot, "entries": res["files"]}, OUT / name / "MANIFEST.json")
        per[name].update(files=len(res["files"]) + 1, bytes=tot, verify_seconds=round(time.time() - t, 2))
        log(f"{name}: {per[name]['files']} files, {tot / 1e6:.1f} MB, 0 secret hits")
    timing["t1"] = time.time()
    timing["t1_utc"] = datetime.now(timezone.utc).isoformat()
    timing["capture_seconds"] = round(timing["t1"] - timing["t0"], 2)
    timing["runs"] = per
    jdump(timing, OUT / "timing.json")
    (OUT / "build.log").write_text("\n".join(log_lines) + "\n")
    log(f"capture done in {timing['capture_seconds']} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
