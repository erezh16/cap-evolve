"""Idempotent build steps B1–B5 (plan §4), used by resume.py to rebuild what a host loss removed.

  python3 -I build.py check        # print which B steps are missing or mismatched (json)
  python3 -I build.py b1|b2|b3|b4|b5
Each step is checked against manifest.json; a mismatch after a rebuild stops (exit 2) for the user.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import awpaths as P  # noqa: E402

UV = Path.home() / ".local" / "bin" / "uv"


def sh(cmd: str, cwd: Path | None = None) -> None:
    subprocess.run(cmd, shell=True, check=True, cwd=str(cwd) if cwd else None)


def check() -> dict:
    m = P.manifest()
    out = {}
    a = P.APPWORLD_SRC
    if not (a / ".git").exists():
        out["b1"] = "missing"
    else:
        head = subprocess.run(["git", "-C", str(a), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        diff = subprocess.run(["git", "-C", str(a), "diff"], capture_output=True).stdout
        if head != P.APPWORLD_COMMIT or P.sha256_bytes(diff) != m["appworld"]["git_diff_sha256"]:
            out["b1"] = "mismatch"
    if not P.VENV_PY.exists() or not UV.exists():
        out["b2"] = "missing"
    if not P.ROOT_FULL.exists():
        out["b3"] = "missing"
    if not (P.ROOT_OPT / "data").exists() or not P.LINT_CACHE.exists():
        out["b4"] = "missing"
    if not (P.ACE_SRC / "ace-appworld" / ".git").exists() or not (P.HF_HOME / "hub").exists():
        out["b5"] = "missing"
    return out


def b1() -> None:
    if not (P.APPWORLD_SRC / ".git").exists():
        sh(f"git clone https://github.com/StonyBrookNLP/appworld.git {P.APPWORLD_SRC}")
    sh(f"git checkout -q {P.APPWORLD_COMMIT} && git lfs install --local && git lfs pull", P.APPWORLD_SRC)
    sh("git checkout -- .", P.APPWORLD_SRC)
    sh(f"git apply {P.EXAMPLE / 'patches' / 'appworld-extra-headers.patch'}", P.APPWORLD_SRC)


def b2() -> None:
    if not UV.exists():
        sh("curl -LsSf https://astral.sh/uv/0.13.0/install.sh | sh")
    if not P.VENV_PY.exists():
        sh(f"{UV} venv -p 3.11 {P.VENV}")
    sh(f"{UV} pip install -p {P.VENV} torch --index-url https://download.pytorch.org/whl/cpu")
    sh(f"{UV} pip install -p {P.VENV} -e {P.APPWORLD_SRC} -e '{P.APPWORLD_SRC}/experiments[simplified]' "
       f"'pydantic>=2.12,<2.13' -e {P.REPO / 'core'} sentence-transformers faiss-cpu tiktoken")
    sh(f"{P.VENV / 'bin' / 'appworld'} install --repo", P.APPWORLD_SRC)


def b3() -> None:
    if P.ROOT_FULL.exists():
        os.chmod(P.ROOT_FULL, 0o755)
    else:
        P.ROOT_FULL.mkdir(parents=True)
        sh(f"{P.VENV / 'bin' / 'appworld'} download data --root {P.ROOT_FULL}")
    r = subprocess.run([str(P.VENV_PY), "-I", str(P.EXAMPLE / "scripts" / "make_splits.py")],
                       env={**os.environ, "APPWORLD_ROOT": str(P.ROOT_FULL)}, capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode:
        raise SystemExit(2)


def b4() -> None:
    sh(f"python3 -I {P.EXAMPLE / 'scripts' / 'make_roots.py'}")


def b5() -> None:
    for name, url, commit in (("ace", "https://github.com/ace-agent/ace.git", P.ACE_COMMIT),
                              ("ace-appworld", "https://github.com/ace-agent/ace-appworld.git", P.ACE_APPWORLD_COMMIT)):
        d = P.ACE_SRC / name
        if not (d / ".git").exists():
            sh(f"git clone -q {url} {d}")
        sh(f"git checkout -q {commit}", d)
    sh(f"HF_HOME={P.HF_HOME} {P.VENV_PY} -c \"from sentence_transformers import SentenceTransformer as S; "
       f"S('sentence-transformers/all-mpnet-base-v2')\"")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "check":
        print(json.dumps(check()))
    else:
        globals()[cmd]()
