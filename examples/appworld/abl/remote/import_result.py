"""Import of the abl_cc REMOTE result into this pod (docs/ABLATIONS.md §10.2; ledger ABL-0361). Trusted script (R1):
it reads the bundle only to verify and copy it, and prints counts, booleans and hashes only. Source abl/env.sh first;
run in venv-abl with -I.

  python -I import_result.py check TARBALL SHA_FILE   # sha256, safe members, BUNDLE_MANIFEST hashes, cache listing
  python -I import_result.py install TARBALL           # check again, then install over this pod's abl_cc state

install keeps what it replaces: AW_STATE/abl_cc and AW_HOME/arms/abl_cc move to AW_STATE/archive/abl_cc_pre_remote_<ts>/.
It refuses unless the local abl_cc chain is held (p4/abl_cc.json: stopped_by_decision), no local evald or session runs,
and the bundle's evaluation and rollout logs start with this pod's own (the remote run only appended). The remote
cache records are added to AW_STATE/cache/main/ (an existing record must be byte-identical). Nothing is posted here;
the watcher (watch_result.sh) records the ledger entries and starts the arm's freeze, scan and reset.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
EX = HERE.parents[1]
sys.path[:0] = [str(EX / "scripts"), str(EX / "common")]
import awrest as P  # noqa: E402

ARM = "abl_cc"
STATE = P.AW_STATE / ARM
ROOT = P.RUN_ROOTS[ARM]
TOP = "return_abl_cc"


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _lines(p: Path) -> list[str]:
    return [l for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def _extract(tarball: Path, dst: Path) -> Path:
    """Only regular files, dirs and relative in-tree symlinks under return_abl_cc/; no device, no hard link, no '..'."""
    with tarfile.open(tarball, "r:gz") as t:
        for m in t.getmembers():
            parts = Path(m.name).parts
            if not parts or parts[0] != TOP or ".." in parts or m.name.startswith("/"):
                raise SystemExit(f"import_result: unsafe member path in the tarball")
            if not (m.isfile() or m.isdir() or m.issym()):
                raise SystemExit("import_result: the tarball holds a special file or hard link")
            if m.issym() and (m.linkname.startswith("/") or ".." in Path(m.linkname).parts):
                raise SystemExit("import_result: the tarball holds a symlink that leaves its directory")
        t.extractall(dst)
    return dst / TOP


def check(tarball: Path, sha_file: Path | None) -> tuple[dict, Path, Path]:
    res: dict = {}
    if sha_file is not None:
        want = sha_file.read_text().split()[0]
        res["tarball_sha256_ok"] = _sha(tarball) == want
        if not res["tarball_sha256_ok"]:
            raise SystemExit(json.dumps(res))
    tmp = Path(tempfile.mkdtemp(prefix="abl_cc_import_", dir=str(P.AW_STATE / "archive")))
    b = _extract(tarball, tmp)
    man = json.loads((b / "BUNDLE_MANIFEST.json").read_text())
    bad = [rel for rel, h in man["files"].items() if not (b / rel).is_file() or _sha(b / rel) != h]
    res["bundle_files"] = len(man["files"])
    res["bundle_files_ok"] = not bad
    lst = _lines(b / "cache" / "LISTING.sha256")
    res["cache_records"] = len(lst)
    res["cache_listing_ok"] = all(_sha(b / "cache" / "main" / r) == h for r, h in (l.split() for l in lst))
    # the remote run only appended to this pod's logs: its first lines are ours, byte for byte
    for f in ("evals.jsonl", "rollouts.jsonl"):
        mine, theirs = _lines(STATE / f), _lines(b / "state_abl_cc" / f)
        res[f"{f}_extends_local"] = theirs[:len(mine)] == mine
        res[f"{f}_local_remote"] = [len(mine), len(theirs)]
    res["session3_result"] = (b / "state_abl_cc" / "session3_result.json").is_file()
    res["session3_started"] = (b / "state_abl_cc" / "SESSION3_STARTED").is_file()
    res["config3"] = (b / "arm_abl_cc" / "config3").is_dir()
    res["rollouts_within_budget"] = len(_lines(b / "state_abl_cc" / "rollouts.jsonl")) <= P.BUDGET_ROLLOUTS
    res["status"] = man.get("status")
    for f in ("probe_long_command.txt", "a9_abl_cc.json"):
        res[f"check_{f}"] = (b / "checks" / f).is_file()
    a9 = P.read_json(b / "checks" / "a9_abl_cc.json", {}) or {}
    res["a9_ok"] = bool(a9.get("ok"))
    pr = (b / "checks" / "probe_long_command.txt")
    txt = pr.read_text() if pr.exists() else ""
    res["probe_pass"] = sum(1 for l in txt.splitlines() if l.split(":", 1)[-1].strip().startswith("PASS")) >= 3
    res["ok"] = all(res[k] for k in ("bundle_files_ok", "cache_listing_ok", "evals.jsonl_extends_local",
                                       "rollouts.jsonl_extends_local", "session3_result", "session3_started",
                                       "config3", "rollouts_within_budget", "a9_ok", "probe_pass"))
    return res, tmp, b


def install(tarball: Path) -> int:
    st = P.read_json(P.AW_STATE / "p4" / "abl_cc.json", {}) or {}
    if not st.get("stopped_by_decision"):
        raise SystemExit("import_result: the local abl_cc chain is not held (stopped_by_decision); refusing")
    for pf in ("EVALD.pid", "session.pid"):
        try:
            os.kill(int((STATE / pf).read_text().strip()), 0)
            raise SystemExit(f"import_result: a local abl_cc process ({pf}) is alive; refusing")
        except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
            pass
    res, tmp, b = check(tarball, None)
    if not res["ok"]:
        print(json.dumps({k: v for k, v in res.items() if k != "status"}))
        return 1
    ts = P.utcnow().replace(":", "").replace("-", "")
    keep = P.AW_STATE / "archive" / f"abl_cc_pre_remote_{ts}"
    keep.mkdir(parents=True)
    os.replace(STATE, keep / "state_abl_cc")
    os.replace(ROOT, keep / "arm_abl_cc")
    n = 0
    for line in _lines(b / "cache" / "LISTING.sha256"):
        rel = line.split()[0]
        dst = P.AW_STATE / "cache" / "main" / rel
        if dst.exists():
            if _sha(dst) != _sha(b / "cache" / "main" / rel):
                raise SystemExit("import_result: an existing cache record differs from the bundle")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(b / "cache" / "main" / rel, dst)
        n += 1
    shutil.copytree(b / "state_abl_cc", STATE, symlinks=True)
    ROOT.mkdir(parents=True)
    shutil.copytree(b / "arm_abl_cc" / "work", ROOT / "work", symlinks=True)
    for d in sorted((b / "arm_abl_cc").glob("config*")):
        shutil.copytree(d, ROOT / d.name, symlinks=True)
    (STATE / "remote").mkdir(exist_ok=True)
    for f in (b / "checks").glob("*") if (b / "checks").is_dir() else []:
        shutil.copy2(f, STATE / "remote" / f.name)
    shutil.copy2(b / "BUNDLE_MANIFEST.json", STATE / "remote" / "BUNDLE_MANIFEST.json")
    shutil.rmtree(tmp, ignore_errors=True)
    out = {"installed": True, "archived_local_state": str(keep), "cache_records_added": n,
           **{k: res[k] for k in ("bundle_files", "cache_records", "evals.jsonl_local_remote",
                                  "rollouts.jsonl_local_remote", "a9_ok", "probe_pass")}, "status": res["status"]}
    P.write_json(STATE / "remote" / "import.json", out)
    print(json.dumps(out))
    return 0


def main() -> int:
    if P.LEDGER_ID != "ABL":
        raise SystemExit("import_result.py: source abl/env.sh first")
    cmd = sys.argv[1]
    if cmd == "check":
        res, tmp, _ = check(Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve())
        shutil.rmtree(tmp, ignore_errors=True)
        print(json.dumps(res))
        return 0 if res["ok"] else 1
    if cmd == "install":
        return install(Path(sys.argv[2]).resolve())
    raise SystemExit(f"unknown command {cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
