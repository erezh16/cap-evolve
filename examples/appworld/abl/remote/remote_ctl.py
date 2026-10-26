"""Trusted helper of the abl_cc REMOTE run (docs/ABLATIONS.md §10.2; ledger ABL-0361). Source remote/env.remote.sh
first; run in venv-abl with -I. Counts and hashes only (rule R1): it never prints a task id, task text or trajectory.

  python -I remote_ctl.py restore PKG_DIR     # unpack the package's state into AW_HOME; verifies every hash
  python -I remote_ctl.py status              # counts: evaluations, rollouts used/left, sessions, daemon, open tickets
  python -I remote_ctl.py bundle OUT_DIR      # the return bundle (arm state, workdir, config dirs, cache records)
  python -I remote_ctl.py compare-manifest PKG_DIR   # this host's build manifest vs the original pod's (hashes)

restore refuses to overwrite: AW_STATE/abl_cc and AW_HOME/arms/abl_cc must not exist yet. The cache records of the
package go to AW_STATE/cache/main/ (the seed tree and every abl_cc candidate evaluated so far), so a resubmitted tree
stays free, exactly as on the original pod. A copy of the seed is also served from cache (SEED_BASELINE_DONE is set
from the package's seed baseline marker).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ABL = HERE.parent
EX = ABL.parent
sys.path[:0] = [str(EX / "scripts"), str(EX / "common")]
import awrest as P  # noqa: E402

ARM = "abl_cc"
STATE = P.AW_STATE / ARM
ROOT = P.AW_HOME / "arms" / ARM


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def restore(pkg: Path) -> int:
    # the gate checks (probe, A9) run first and leave only AW_STATE/abl_cc/accept/ and an empty arm root behind
    if (STATE.exists() and {p.name for p in STATE.iterdir()} - {"accept", "inflight"}) or \
            (ROOT.exists() and any(ROOT.iterdir())):
        raise SystemExit("restore: AW_STATE/abl_cc or AW_HOME/arms/abl_cc already holds arm state; refusing to overwrite")
    man = json.loads((pkg / "PACKAGE_MANIFEST.json").read_text())
    bad = [rel for rel, h in man["files"].items() if _sha(pkg / rel) != h]
    if bad:
        raise SystemExit(f"restore: {len(bad)} package file(s) differ from PACKAGE_MANIFEST.json")
    lst = (pkg / "cache" / "LISTING.sha256").read_text().splitlines()
    for line in lst:
        rel, h = line.split()
        if _sha(pkg / "cache" / "main" / rel) != h:
            raise SystemExit("restore: a cache record differs from LISTING.sha256")
    dst = P.AW_STATE / "cache" / "main"
    n = 0
    for line in lst:
        rel = line.split()[0]
        t = dst / rel
        if t.exists():
            if _sha(t) != _sha(pkg / "cache" / "main" / rel):
                raise SystemExit("restore: an existing cache record differs from the package")
            continue
        t.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pkg / "cache" / "main" / rel, t)
        n += 1
    shutil.copytree(pkg / "state_abl_cc", STATE, symlinks=True, dirs_exist_ok=True)
    ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copytree(pkg / "arm_abl_cc" / "work", ROOT / "work", symlinks=True)
    for d in sorted((pkg / "arm_abl_cc").glob("config*")):
        shutil.copytree(d, ROOT / d.name, symlinks=True)
    for f in ("SEED_BASELINE_DONE",):
        if (pkg / "state_root" / f).exists() and not (P.AW_STATE / f).exists():
            shutil.copy2(pkg / "state_root" / f, P.AW_STATE / f)
    sd = P.AW_STATE / "seed"
    if (pkg / "state_root" / "seed").is_dir() and not sd.exists():
        shutil.copytree(pkg / "state_root" / "seed", sd)
    for f in ("lint_cache.json",):
        if (pkg / "state_root" / f).exists() and not (P.AW_STATE / f).exists():
            shutil.copy2(pkg / "state_root" / f, P.AW_STATE / f)
    # the read-only marks of the original pod (reset item 6) are lifted: the session must be able to write here
    subprocess.run(["chmod", "-R", "u+w", str(ROOT / "work"), str(STATE)], check=True)
    print(json.dumps({"restored": True, "cache_records_copied": n, "cache_records_listed": len(lst),
                      "package_files_checked": len(man["files"]), **_status()}))
    return 0


def _status() -> dict:
    evals = P.read_jsonl(STATE / "evals.jsonl")
    used = len(P.read_jsonl(STATE / "rollouts.jsonl"))
    req = ROOT / "work" / ".eval" / "requests"
    pid = STATE / "EVALD.pid"
    alive = False
    if pid.exists():
        try:
            os.kill(int(pid.read_text().strip()), 0)
            alive = True
        except (OSError, ValueError):
            pass
    return {"evaluations_logged": len(evals),
            "evaluations_done": sum(1 for e in evals if e.get("state") == "done"),
            "mean_rewards_done": [e.get("mean_reward") for e in evals if e.get("state") == "done"],
            "rollouts_used": used, "rollouts_left": P.BUDGET_ROLLOUTS - used,
            "open_tickets": len(list(req.glob("*.json"))) if req.is_dir() else 0,
            "inflight_markers": len(list((STATE / "inflight").glob("*"))) if (STATE / "inflight").is_dir() else 0,
            "sessions_started": sorted(p.name for p in STATE.glob("SESSION*_STARTED")),
            "session_results": sorted(p.name for p in STATE.glob("session*_result.json")),
            "evald_alive": alive}


def bundle(out: Path) -> int:
    if out.exists():
        raise SystemExit("bundle: OUT_DIR exists")
    out.mkdir(parents=True)
    shutil.copytree(STATE, out / "state_abl_cc", symlinks=True,
                    ignore=shutil.ignore_patterns("inflight", "*.pid", "accept"))
    shutil.copytree(ROOT / "work", out / "arm_abl_cc" / "work", symlinks=True)
    for d in sorted(ROOT.glob("config*")):
        shutil.copytree(d, out / "arm_abl_cc" / d.name, symlinks=True)
    for f in ("probe_long_command.txt", "a9_abl_cc.json", "build_check.json"):
        for src in (P.AW_STATE / "remote" / f, P.AW_STATE / "acceptance" / f, P.AW_STATE / f):
            if src.exists():
                (out / "checks").mkdir(exist_ok=True)
                shutil.copy2(src, out / "checks" / f)
                break
    # every cache record of a tree abl_cc evaluated (the original pod's window does not need them, the reset and
    # re-check do): byte copies, listed with hashes
    import evaluator as E
    trees = set()
    for e in P.read_jsonl(STATE / "evals.jsonl"):
        if e.get("state") == "done" and e.get("cand"):
            for c in (STATE / "cands").glob(e["cand"] + "*"):
                trees.add(E.tree_hash(c)[:16])
    lst = []
    for t in sorted(trees):
        src = E.CACHE / "main" / t
        if src.is_dir():
            shutil.copytree(src, out / "cache" / "main" / t, dirs_exist_ok=True)
            lst += [f"{t}/{f.name} {_sha(f)}" for f in sorted((out / "cache" / "main" / t).glob("*.json"))]
    (out / "cache").mkdir(exist_ok=True)
    (out / "cache" / "LISTING.sha256").write_text("\n".join(lst) + "\n")
    files = {str(p.relative_to(out)): _sha(p) for p in sorted(out.rglob("*")) if p.is_file() and not p.is_symlink()}
    (out / "BUNDLE_MANIFEST.json").write_text(json.dumps({"arm": ARM, "status": _status(), "files": files}, indent=1))
    print(json.dumps({"bundle": str(out), "files": len(files), "cache_records": len(lst), **_status()}))
    return 0


KEYS = ("appworld.commit", "appworld.git_diff_sha256", "appworld.patch_sha256", "venv_aw.freeze_sha256",
        "data.root_full_tree_sha256", "data.split_file_sha256", "data.counts", "data.scenarios", "data.difficulty_1_2_3",
        "root_opt.tree_sha256", "root_opt.task_dirs", "root_opt.test_id_hits", "reference.tree_sha256",
        "venv_abl.freeze_sha256", "venv_abl.cape_commit", "seed.SEED_HASH", "m_cap.tokens")


def _get(d: dict, k: str):
    for part in k.split("."):
        d = (d or {}).get(part) if isinstance(d, dict) else None
    return d


def compare_manifest(pkg: Path) -> int:
    """The original pod's manifest (package) vs this host's (written by build.py b1-b4 and the run). Hashes only."""
    orig = json.loads((pkg / "reference_manifest.json").read_text())
    here = P.manifest()
    import evaluator as E
    here.setdefault("seed", {})["SEED_HASH"] = E.seed_hash()
    res = {k: {"match": _get(orig, k) == _get(here, k)} for k in KEYS}
    for k, v in res.items():
        if not v["match"] and isinstance(_get(orig, k), str):
            v.update(original=str(_get(orig, k))[:16], here=str(_get(here, k))[:16])
    res["ok"] = all(v["match"] for v in res.values())
    print(json.dumps(res, indent=1))
    return 0 if res["ok"] else 1


def main() -> int:
    if P.LEDGER_ID != "ABL":
        raise SystemExit("remote_ctl.py: source remote/env.remote.sh first")
    cmd = sys.argv[1]
    if cmd == "restore":
        return restore(Path(sys.argv[2]).resolve())
    if cmd == "status":
        print(json.dumps(_status()))
        return 0
    if cmd == "compare-manifest":
        return compare_manifest(Path(sys.argv[2]).resolve())
    if cmd == "bundle":
        return bundle(Path(sys.argv[2]).resolve())
    raise SystemExit(f"unknown command {cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
