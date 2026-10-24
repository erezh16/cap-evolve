"""Shared paths, constants and small helpers for AppWorld eval REST (docs/EVAL_APPWORLD_REST.md §6, §7).

Stdlib only: imported by the ledger writer (system python3), by every candidate venv, and by venv-aw.
``setup_env()`` points the base-plan modules (adapter, lints, awpaths) at the eval-REST layout through
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
LEDGER = REPO / "docs" / os.environ.get("AW_LEDGER_NAME", "EVAL_APPWORLD_REST.md")
PUSHED = REPO / "docs" / (LEDGER.stem + "_STATE")
BRANCH = os.environ.get("AW_BRANCH", "eval-rest")
LEDGER_MARKER = "<!-- CHECKPOINTS BELOW THIS LINE -->"

AW_HOME = Path(os.environ.get("AW_HOME", "/workspace/aw_rest"))
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
SCRATCH = Path(os.environ.get("AW_SCRATCH_ROOT", "/tmp/aw_rest"))
PROGRESS = AW_STATE / "progress"
LINT_CACHE = AW_STATE / "lint_cache.json"          # the adapter lint's cache (8-grams, contacts, app/API names)
PUBLISH_CACHE = AW_STATE / "publish_cache.json"    # the publishing filter's cache (all 732 ids, 8-grams, contacts)
# The RITS key lives in the base worktree's .env (§1.2); it is read there, never copied (R1).
ENV_FILE = Path(os.environ.get("AW_ENV_FILE", REPO / ".env" if (REPO / ".env").exists()
                               else "/workspace/worktrees/base/.env"))
SEED_CAP = EXAMPLE / "seed_capability"

APPWORLD_COMMIT = "42b5bcf3cd334fee33f0c37c02070a9f5807add5"
OPT_MODEL = "aws/claude-sonnet-5-5"
AGENT_MODEL = "openai/gpt-oss-120b-a100"
SPLIT_COUNTS = {"train": 90, "dev": 57, "test_normal": 168, "test_challenge": 417}
CANDIDATES = ("harnesslens", "miprov2", "trace2skill", "gepa_full", "cape_improve")
ARMS = ("seed",) + CANDIDATES
ISSUES = {"harnesslens": 897, "miprov2": 898, "trace2skill": 899, "gepa_full": 900, "cape_improve": 901}
ISSUE_REPO = "skillberry-ai/cap-evolve"
METHOD_NAMES = {"harnesslens": "HarnessLens", "miprov2": "MIPROv2", "trace2skill": "Trace2Skill",
                "gepa_full": "GEPA-Full", "cape_improve": "Cap-Evolve-improve"}
# Pins of §0 / D4. Full shas are resolved and recorded in manifest.json by build.py b5.
PINS = {
    "harnesslens": ("https://github.com/jhxu5214/HarnessLens", "369a5c8"),
    "miprov2": ("https://github.com/stanfordnlp/dspy", "3.4.1"),          # PyPI dspy==3.4.1 (tag 3.4.1)
    "trace2skill": ("https://github.com/Qwen-Applications/Trace2Skill", "3d0b52a"),
    "gepa_full": ("https://github.com/gepa-ai/gepa", "8b0ce6cd99a234f6b74daf37558a2ac0ce18f975"),
}
CAPE_IMPROVE_COMMIT = "470f3fabdad780a2a791037067a73ae9b0295473"
CAPE_IMPROVE_TREE = Path("/workspace/worktrees/cape-improve")
BUDGET_ROLLOUTS = 900                      # B: counted (fresh) search rollouts per candidate (§0)
BUDGET_OPT_TOKENS = 10_000_000             # optimizer non-cache-read tokens per candidate (§0)
SEARCH_SEED_BASE = 100                     # trial seed of every search rollout (1 trial/task, Q1)
FINAL_SEED_BASE = 5000                     # final window trial seeds 5000 + k, k in {0, 1} (Q1)
SEED_BASELINE_PHASE = "P3"                 # the one shared seed run (Q4)
# Proxy USD per MTok, Claude Sonnet 5.5 list price (§5.2). Not eval 5's $3/$15.
PRICE_IN, PRICE_OUT, PRICE_CACHE_READ, PRICE_CACHE_WRITE = 2.0, 10.0, 0.20, 2.50
GLOBAL_SLOTS_DEFAULT = 24                  # §4.2 / §7.3: start at 24, never above 32
GLOBAL_SLOTS_MAX = 32
SLOTS_DIR = AW_STATE / "slots"
PAUSE_FILE = AW_STATE / "PAUSE"            # created by memguard.py at >= 90%, removed below 85% (R2)
MEMSTATE = AW_STATE / "MEMSTATE.json"


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


# ---------------------------------------------------------------- rule R2 (memory) and §7.3 (slots)

def memstate() -> dict:
    """The guard's last sample, plus ``stale`` when it is older than 30 s (the guard is dead)."""
    m = read_json(MEMSTATE, {}) or {}
    try:
        age = (_dt.datetime.now(_dt.timezone.utc) - _dt.datetime.strptime(m["t"], "%Y-%m-%dT%H:%M:%SZ")
               .replace(tzinfo=_dt.timezone.utc)).total_seconds()
    except (KeyError, ValueError):
        age = 1e9
    m["age_s"] = age
    m["stale"] = age > 30
    return m


def paused() -> bool:
    return PAUSE_FILE.exists()


def wait_unpaused(what: str = "", poll: float = 5.0) -> float:
    """Block while AW_STATE/PAUSE exists (R2: nothing new starts). Returns the seconds waited."""
    t0 = __import__("time").time()
    logged = False
    while PAUSE_FILE.exists():
        if not logged and what:
            progress_log(what, "-", "PAUSED by memguard: waiting before starting new work")
            logged = True
        __import__("time").sleep(poll)
    return __import__("time").time() - t0


def global_slots() -> int:
    """The global episode-slot pool size (§7.3), from AW_STATE/slots/SIZE (resizable while running)."""
    try:
        n = int((SLOTS_DIR / "SIZE").read_text().strip())
    except (FileNotFoundError, ValueError):
        n = GLOBAL_SLOTS_DEFAULT
    return max(1, min(GLOBAL_SLOTS_MAX, n))


class Slot:
    """One global episode slot: ``flock`` on AW_STATE/slots/<i>.lock, shared by every process (§7.3).

    Acquiring waits while PAUSE exists (R2), then takes the first free lock among the first
    ``global_slots()`` files. The lock is released when the holder exits, even on a crash.
    """

    def __init__(self, who: str = ""):
        self.who, self.f, self.i = who, None, None

    def __enter__(self):
        import time
        SLOTS_DIR.mkdir(parents=True, exist_ok=True)
        while True:
            wait_unpaused(self.who)
            for i in range(global_slots()):
                f = open(SLOTS_DIR / f"{i}.lock", "a+")
                try:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    f.close()
                    continue
                if PAUSE_FILE.exists():   # paused between the wait and the lock: give it back
                    fcntl.flock(f, fcntl.LOCK_UN)
                    f.close()
                    break
                self.f, self.i = f, i
                f.seek(0)
                f.truncate()
                f.write(f"{os.getpid()} {self.who} {utcnow()}\n")
                f.flush()
                return self
            time.sleep(0.5)

    def __exit__(self, *exc):
        if self.f:
            fcntl.flock(self.f, fcntl.LOCK_UN)
            self.f.close()
            self.f = None
        return False


def slots_in_use() -> int:
    n = 0
    for p in SLOTS_DIR.glob("*.lock"):
        with open(p, "a+") as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(f, fcntl.LOCK_UN)
            except BlockingIOError:
                n += 1
    return n


# ---------------------------------------------------------------- eval CE2 profile (docs/EVAL_APPWORLD_CE2.md §6.2 B1)
# CE2 changes only the constants that are not environment-driven, in scripts/awce2.py. Every CE2 command sources
# examples/appworld/ce2/env.sh, which sets AW_PROFILE=ce2 (inherited by every subprocess); without it nothing changes.
LEDGER_PREFIX = "CP"                       # ledger entry ids: CP-NNNN (REST), CE2-NNNN (CE2)
EVAL_NAME = "eval REST"
LEDGER_ID = None                           # the visible ledger id when it differs from LEDGER_PREFIX (CE3)
if os.environ.get("AW_PROFILE") == "ce2":
    from awce2 import *  # noqa: E402,F401,F403
elif os.environ.get("AW_PROFILE") == "ce3":     # CE3 is one more CE2 arm: CE2's code paths with CE3's constants
    from awce3 import *  # noqa: E402,F401,F403
elif os.environ.get("AW_PROFILE") == "testall":  # TEST_ALL (docs/TEST_ALL.md): 13 arms, test window only, no training
    from awtestall import *  # noqa: E402,F401,F403
    PUSHED = REPO / "docs" / "TEST_ALL_STATE"     # plan §11, §12.3: docs/TEST_ALL_STATE/ (not <ledger stem>_STATE)
    ISSUES = {a: int(n) for a, n in (manifest().get("issues") or {}).items()}   # written once by open_issues.py
LEDGER_ID = LEDGER_ID or LEDGER_PREFIX
TESTALL = os.environ.get("AW_PROFILE") == "testall"
