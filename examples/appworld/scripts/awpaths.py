"""Shared paths and small helpers for the ACE AppWorld smoke test (docs/EVAL_SMOKE_TEST_ACE.md §4).

Stdlib only: imported by the ledger writer (system python3) and by the venv code alike.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

# AW_REPO / AW_LEDGER_NAME / AW_BRANCH are overridden only by the acceptance tests A9/A10 (throwaway
# clone, status file and branch); the evaluation itself uses the defaults.
REPO = Path(os.environ.get("AW_REPO", Path(__file__).resolve().parents[3]))
EXAMPLE = Path(__file__).resolve().parents[1]
LEDGER = REPO / "docs" / os.environ.get("AW_LEDGER_NAME", "EVAL_SMOKE_TEST_ACE_STATUS.md")
PUSHED = REPO / "docs" / (LEDGER.stem.removesuffix("_STATUS") + "_STATE")
BRANCH = os.environ.get("AW_BRANCH", "erezh-eval2-ace")

AW_HOME = Path(os.environ.get("AW_HOME", "/workspace/aw_eval_ace"))
AW_STATE = Path(os.environ.get("AW_STATE", AW_HOME / "state"))
AW_BUILD = AW_HOME / "build"
APPWORLD_SRC = AW_BUILD / "appworld"
ACE_SRC = AW_BUILD / "ace-src"
VENV = AW_BUILD / "venv-aw"
VENV_PY = VENV / "bin" / "python"
ROOT_FULL = AW_BUILD / "root_full"
ROOT_OPT = AW_BUILD / "root_opt"
HF_HOME = AW_BUILD / "hf"
SCRATCH = Path("/tmp/aw_eval_ace/aw_outputs")
PROGRESS = AW_STATE / "progress"
LINT_CACHE = AW_HOME / "state" / "lint_cache.json"   # ids, instruction 8-grams, contacts (local only; fixed path)
ENV_FILE = REPO / ".env"

APPWORLD_COMMIT = "42b5bcf3cd334fee33f0c37c02070a9f5807add5"
ACE_COMMIT = "82709de050e1db6e6ef2f07bcb0393560b94992a"
ACE_APPWORLD_COMMIT = "928e86877d34cd10eaba159606386f93a1765090"
OPT_MODEL = "aws/claude-sonnet-5-5"
AGENT_MODEL = "openai/gpt-oss-120b-a100"
SPLIT_COUNTS = {"train": 90, "dev": 57, "test_normal": 168, "test_challenge": 417}


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path | str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_tree(root: Path | str) -> str:
    """Hash of (relative path, file sha256) over every file under root, sorted."""
    root = Path(root)
    h = hashlib.sha256()
    for p in sorted(x for x in root.rglob("*") if x.is_file()):
        h.update(str(p.relative_to(root)).encode() + b"\0" + sha256_file(p).encode() + b"\n")
    return h.hexdigest()


def atomic_write(path: Path | str, data: str | bytes) -> None:
    """Temp file in the same dir, fsync, rename (§7, §10.3)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=path.suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(data.encode() if isinstance(data, str) else data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def write_json(path: Path | str, obj) -> None:
    atomic_write(path, json.dumps(obj, indent=1, sort_keys=False) + "\n")


def read_json(path: Path | str, default=None):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return default


def read_env_file(path: Path | str = ENV_FILE) -> dict[str, str]:
    out = {}
    try:
        for line in Path(path).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip().removeprefix("export ").strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return out


def progress_log(trial: str, phase: str, detail: str) -> None:
    import datetime as _dt
    PROGRESS.mkdir(parents=True, exist_ok=True)
    utc = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(PROGRESS / f"{trial}.log", "a") as f:
        f.write(f"{utc} | {trial} | {phase} | {detail}\n")


def manifest() -> dict:
    return read_json(PUSHED / "manifest.json", {}) or {}


def update_manifest(**kv) -> dict:
    m = manifest()
    m.update(kv)
    write_json(PUSHED / "manifest.json", m)
    return m
