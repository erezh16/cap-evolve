"""Completeness audit of the assembled backup (docs/BACKUP_BOX.md): every source file is in it, byte-identical.

    python verify_completeness.py BACKUP_DIR

For each run, lists the source trees that belong to it and checks that every regular file under each
one has a copy with the same sha256 somewhere in that run's folder. Prints missing files and exits 1
if any are missing. Sources excluded by the plan (§4: venvs, data roots, secrets) are not listed.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

AW = Path("/tmp/aw_eval")
RUNS = AW / "runs"
HOME = Path.home()
CTMP = Path(f"/tmp/claude-{os.getuid()}")
B = Path(sys.argv[1])


def files(p: Path):
    if p.is_file():
        yield p
    elif p.is_dir():
        for f in p.rglob("*"):
            if f.is_file() and not f.is_symlink() and "__pycache__" not in f.parts:
                yield f


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sessions(tag: str) -> list[Path]:
    out = []
    for base in (HOME / ".claude/projects", RUNS / "optimizer_transcripts" / tag.replace("-", "_"), CTMP):
        if base.is_dir():
            out += [d for d in base.iterdir() if d.is_dir() and f"runs-{tag}--capevolve-run-{tag}" in d.name]
    return out


def session_ids(dirs: list[Path]) -> set[str]:
    return {f.stem for d in dirs for f in d.glob("*.jsonl")}


def side(ids: set[str]) -> list[Path]:
    return [p for sid in ids for sub in ("file-history", "session-env") if (p := HOME / ".claude" / sub / sid).exists()]


common = [RUNS / "posts", RUNS / "manifest.json", AW / "reference", AW / "lint_cache.json", AW / "split_ids.json",
          Path("/workspace/worktrees/base/examples/appworld")]
s0, s1, s2 = (sessions(t) for t in ("cape-hc-s0", "cape-hc-s1", "cape-hc-s2"))
SOURCES = {
    "2026-10-13-appworld-capevolve-hillclimb-gptoss120b-sonnet55-original-breach":
        [RUNS / "cape_hc_s0", RUNS / "final", RUNS / "a6_dry", RUNS / "altk_probe", RUNS / "altk_probe2",
         *[p for p in Path("/tmp/diag").glob("*.py")], *s0, *side(session_ids(s0)),
         *[AW / "progress" / n for n in ("cape_hc.log", "cape_hc.out", "final.log", "final_run.out", "acceptance.log",
                                          "a6.out", "a6b.out", "a8.out", "build.log", "build.out")], *common],
    "2026-10-13-appworld-altkevolve-v130-retrieval-gptoss120b-sonnet55-original":
        [RUNS / "altk", RUNS / "final", RUNS / "final2" / "results.jsonl",
         *[AW / "progress" / n for n in ("altk.log", "altk_pipeline.out", "altk_continue.out")], *common],
    "2026-10-15-appworld-capevolve-hillclimb-gptoss120b-sonnet55-fix-clean":
        [RUNS / "cape_hc_s1", RUNS / "cape_hc_s2", RUNS / "final2", RUNS / "isolation_check", AW / "sbx_try",
         AW / "isocheck_core", *s1, *s2, *side(session_ids(s1) | session_ids(s2)),
         *[AW / "progress" / n for n in ("cape_hc_s1.log", "cape_hc_s1.out", "cape_hc_s2.log", "cape_hc_s2.out",
                                          "final2_run.out", "optimizer_guard.log")], *common],
}

bad = 0
for run, srcs in SOURCES.items():
    have = {}
    for f in files(B / run):
        have.setdefault(sha(f), []).append(f)
    n = missing = 0
    for s in srcs:
        for f in files(s):
            n += 1
            if sha(f) not in have:
                missing += 1
                if missing <= 15:
                    print(f"  MISSING [{run[:40]}] {f}")
    bad += missing
    print(f"{run}: {n} source files checked, {missing} missing")
sys.exit(1 if bad else 0)
