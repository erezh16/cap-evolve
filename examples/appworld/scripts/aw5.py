"""Shared paths, constants and small helpers for AppWorld eval 5 (docs/EVAL_APPWORLD_5.md §4).

Stdlib only: imported by the ledger writer (system python3), by every candidate venv, and by venv-aw.
``setup_env()`` points the base-plan modules (adapter, lints, awpaths) at the eval-5 layout through
their environment variables, so the shared harness runs unchanged.
"""

from __future__ import annotations

import datetime as _dt
import fcntl
import hashlib
import json
import os
import tempfile
from pathlib import Path

# AW_REPO / AW_LEDGER_NAME / AW_BRANCH are overridden only by acceptance A10 (throwaway clone and branch).
REPO = Path(os.environ.get("AW_REPO", Path(__file__).resolve().parents[3]))
EXAMPLE = Path(__file__).resolve().parents[1]
LEDGER = REPO / "docs" / os.environ.get("AW_LEDGER_NAME", "EVAL_APPWORLD_5.md")
PUSHED = REPO / "docs" / (LEDGER.stem + "_STATE")
BRANCH = os.environ.get("AW_BRANCH", "eval5")
LEDGER_MARKER = "<!-- CHECKPOINTS BELOW THIS LINE -->"

AW_HOME = Path(os.environ.get("AW_HOME", "/workspace/aw_eval5"))
AW_STATE = Path(os.environ.get("AW_STATE", AW_HOME / "state"))
AW_BUILD = AW_HOME / "build"
APPWORLD_SRC = AW_BUILD / "appworld"
VENVS = AW_BUILD / "venvs"
VENV_AW = VENVS / "venv-aw"
VENV_PY = VENV_AW / "bin" / "python"
CLONES = AW_BUILD / "clones"
ROOT_FULL = AW_BUILD / "root_full"
ROOT_OPT = AW_BUILD / "root_opt"
REFERENCE = AW_BUILD / "reference"
HF_HOME = AW_BUILD / "hf"
SCRATCH = Path(os.environ.get("AW_SCRATCH_ROOT", "/tmp/aw_eval5"))
PROGRESS = AW_STATE / "progress"
LINT_CACHE = AW_STATE / "lint_cache.json"          # the adapter lint's cache (8-grams, contacts, app/API names)
PUBLISH_CACHE = AW_STATE / "publish_cache.json"    # the publishing filter's cache (all 732 ids, 8-grams, contacts)
ENV_FILE = Path(os.environ.get("AW_ENV_FILE", REPO / ".env"))
SEED_CAP = EXAMPLE / "seed_capability"

APPWORLD_COMMIT = "42b5bcf3cd334fee33f0c37c02070a9f5807add5"
OPT_MODEL = "aws/claude-sonnet-5-5"
AGENT_MODEL = "openai/gpt-oss-120b-a100"
SPLIT_COUNTS = {"train": 90, "dev": 57, "test_normal": 168, "test_challenge": 417}
CANDIDATES = ("gepa", "skillopt", "wikiskill", "evoskill", "metaharness")
ARMS = ("seed",) + CANDIDATES
ISSUES = {"gepa": 881, "skillopt": 882, "wikiskill": 883, "evoskill": 884, "metaharness": 885}
ISSUE_REPO = "skillberry-ai/cap-evolve"
PINS = {
    "gepa": ("https://github.com/gepa-ai/gepa", "8b0ce6cd99a234f6b74daf37558a2ac0ce18f975"),
    "skillopt": ("https://github.com/microsoft/skillopt", "ae2f766ea02cb41855b6f8f10e38e10264ce0a1b"),
    "wikiskill": ("https://github.com/kenhuangus/wikiskill", "03633345829c452680d18a17004afd33eee729da"),
    "evoskill": ("https://github.com/sentient-agi/EvoSkill", "1d7dc3e6d204473c541f63eea2c99fb7f7eba3fd"),
    "metaharness": ("https://github.com/stanford-iris-lab/meta-harness", "8123ccabe2b19fa1123090b2e5f1bacc20963ce8"),
}
BUDGET_ROLLOUTS = 900                      # B: counted search rollouts per candidate (§0)
BUDGET_OPT_TOKENS = 10_000_000             # optimizer non-cache-read tokens per candidate (§0)
SEARCH_SEED_BASE = 100                     # trial seed of every search rollout (1 trial/task, §0)
PRICE_IN, PRICE_OUT = 3.0, 15.0            # proxy USD per MTok for Sonnet (§12), flagged as a proxy


def setup_env(env: dict | None = None) -> dict:
    """Environment for the shared harness (adapter.py, lints.py, awpaths.py) in the eval-5 layout."""
    e = os.environ if env is None else env
    e.setdefault("AW_EVAL", str(AW_BUILD))
    e.setdefault("AW_LINT_CACHE", str(LINT_CACHE))
    e.setdefault("AW_SCRATCH", str(SCRATCH / "scratch"))
    e.setdefault("AW_SECRETS_FILE", str(ENV_FILE))
    e.setdefault("AW_KEY_ENV", "RITS_API_KET")
    e.setdefault("HF_HOME", str(HF_HOME))
    mc = manifest().get("m_cap", {}).get("tokens")
    if mc:
        e.setdefault("AW_MEMORY_MAX_TOKENS", str(mc))
    return e


def utcnow() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
    """Temp file in the same dir, fsync, rename (§10.3)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=path.suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(data.encode() if isinstance(data, str) else data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def write_json(path: Path | str, obj) -> None:
    atomic_write(path, json.dumps(obj, indent=1, ensure_ascii=False) + "\n")


def read_json(path: Path | str, default=None):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return default


def append_jsonl(path: Path | str, obj: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def read_jsonl(path: Path | str) -> list[dict]:
    try:
        return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]
    except FileNotFoundError:
        return []


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
    PROGRESS.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS / f"{trial}.log", "a") as f:
        f.write(f"{utcnow()} | {trial} | {phase} | {detail}\n")


def manifest() -> dict:
    return read_json(PUSHED / "manifest.json", {}) or {}


def update_manifest(**kv) -> dict:
    m = manifest()
    m.update(kv)
    write_json(PUSHED / "manifest.json", m)
    return m


def read_split(name: str, root: Path | None = None) -> list[str]:
    """Ids of an official split in file order (the parse of appworld.task.load_task_ids)."""
    root = root or (ROOT_OPT if name in ("train", "dev") else ROOT_FULL)
    return [x.strip() for x in (root / "data" / "datasets" / f"{name}.txt").read_text().splitlines() if x.strip()]


def cand_state(cand: str) -> Path:
    d = AW_STATE / cand
    d.mkdir(parents=True, exist_ok=True)
    return d
