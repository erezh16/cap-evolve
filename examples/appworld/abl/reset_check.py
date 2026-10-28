"""Reset check of one arm (docs/ABLATIONS.md §9.8), after its freeze and again at P6. Source abl/env.sh first.

  python -I reset_check.py ARM [--store-reference] [--no-archive]

  1. no process of the arm is alive (by its pid files, never pgrep -f);
  2. abl-main is clean and at 75b3bcd;
  3. none of AW_ABL_FEEDBACK, AW_ABL_TOOLS_LINT, AW_CAPE_ARM, CAPEVOLVE_* is set in this (the executing session's)
     environment or in abl/env.sh;
  4. the shared defaults are the reference's: AW_ABL_FEEDBACK unset means full, AW_ABL_TOOLS_LINT unset means off;
  5. a fresh render of abl_ref's spec, INSTRUCTIONS and shim settings equals the renders stored at abl_ref's launch
     (``--store-reference`` stores them; run once, at abl_ref's launch);
  6. the arm's per-call settings files under AW_HOME/opt are moved to AW_STATE/archive/<arm>/, and its project root
     is made read-only (chmod -R a-w); skipped with --no-archive (the throwaway-arm acceptance test).
Prints one JSON (counts, booleans, hashes) and writes AW_STATE/<arm>/reset_check.json. Exit 0 iff all pass.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EX = HERE.parent
sys.path[:0] = [str(HERE), str(EX / "scripts"), str(EX / "common")]
import awrest as P  # noqa: E402

P.setup_env()                              # AW_LINT_CACHE etc. before lints is imported

REF_STORE = P.AW_STATE / "abl" / "reference_renders"
SWITCHES = ("AW_ABL_FEEDBACK", "AW_ABL_TOOLS_LINT", "AW_CAPE_ARM")
PID_FILES = ("search.pid", "session.pid", "EVALD.pid")


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _drop_session_tmp(st: dict) -> bytes:
    """Other Claude sessions' temp dirs (/tmp/claude-<uid>/<dir>) are denied as they exist at each call, so they vary
    with time and say nothing about the arm's configuration; every other rule is compared (ABL-0294)."""
    tmp = f"/tmp/claude-{os.getuid()}/"
    # ABLATIONS_GATE.md G6: adding the gate arms adds their roots to every other arm's deny list (more is denied, never
    # less). abl_ref's render was stored before they existed, so their own deny entries are left out of the comparison.
    gate = tuple(f"/{a}" for a in getattr(P, "GATE_ARMS", ()))
    keep = lambda r: tmp not in r and not any(g + "/" in r or r.endswith(g) for g in gate)  # noqa: E731
    st["permissions"]["deny"] = [r for r in st["permissions"]["deny"] if keep(r)]
    st["sandbox"]["filesystem"]["denyRead"] = [r for r in st["sandbox"]["filesystem"]["denyRead"] if keep(r)]
    return json.dumps(st, indent=1, sort_keys=True).encode()


def reference_renders() -> dict[str, bytes]:
    """abl_ref's spec, INSTRUCTIONS and shim settings, rendered fresh (no file is written to the arm's project)."""
    import instructions
    import sandbox as SB
    proj = P.RUN_ROOTS["abl_ref"] / ".capevolve" / "project"
    spec = (proj / "capevolve.yaml").read_bytes()
    instr = instructions.render("abl_ref").encode()
    work = P.RUN_ROOTS["abl_ref"] / ".capevolve" / f"run_{P.RUN_TS['abl_ref']}" / "work" / "probe"
    st = _drop_session_tmp(SB.settings(work, [proj / "adapters"], "abl_ref"))
    return {"capevolve.yaml": spec, "INSTRUCTIONS.abl_ref.md": instr, "shim_settings.json": st}


def check(arm: str, archive: bool = True) -> dict:
    res: dict = {"arm": arm}
    st = P.AW_STATE / arm
    pids = {}
    for f in PID_FILES:
        p = st / f
        if p.is_file():
            try:
                pid = int(p.read_text().split()[0])
            except (ValueError, IndexError):
                continue
            pids[f] = {"pid": pid, "alive": _alive(pid)}
    res["1_no_live_process"] = {"ok": not any(v["alive"] for v in pids.values()), "pid_files": pids}
    head = subprocess.run(["git", "-C", str(P.CAPE_TREE), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(P.CAPE_TREE), "status", "--porcelain"], capture_output=True, text=True).stdout
    res["2_abl_main_clean"] = {"ok": head == P.CAPE_COMMIT and not dirty.strip(), "head": head[:12],
                               "dirty_entries": len(dirty.splitlines())}
    env_set = [k for k in os.environ if k in SWITCHES or k.startswith("CAPEVOLVE_")]
    envsh = (HERE / "env.sh").read_text()
    in_envsh = sorted({m for m in re.findall(r"\b(AW_ABL_\w+|AW_CAPE_ARM|CAPEVOLVE_\w+)\b", envsh)})
    res["3_no_switch_set"] = {"ok": not env_set and not in_envsh, "session_env": env_set, "env_sh": in_envsh}
    import importlib
    saved = {k: os.environ.pop(k) for k in ("AW_ABL_FEEDBACK", "AW_ABL_TOOLS_LINT") if k in os.environ}
    try:
        import feedback_filter as F
        F = importlib.reload(F)
        sys.path.insert(0, str(EX / "adapters"))
        import tempfile
        import lints
        with tempfile.TemporaryDirectory() as d:     # a helper returning 300 literal characters, switch unset
            (Path(d) / "policy").mkdir()
            shutil.copy2(P.SEED_CAP / "policy" / "instructions.txt", Path(d) / "policy" / "instructions.txt")
            (Path(d) / "tools").mkdir()
            (Path(d) / "tools" / "helpers.py").write_text("def p():\n    return " + repr("x" * 300) + "\n")
            tools_off = not any("fixed literal text" in v for v in lints.lint_candidate(Path(d)))
        res["4_defaults"] = {"ok": F.MODE == "full" and tools_off, "feedback_default": F.MODE,
                             "tools_lint_default_off": tools_off}
    finally:
        os.environ.update(saved)
    cur = reference_renders()
    stored = {n: (REF_STORE / n).read_bytes() for n in cur if (REF_STORE / n).is_file()}
    if "shim_settings.json" in stored:          # the same volatile-entry filter on the render stored at launch
        stored["shim_settings.json"] = _drop_session_tmp(json.loads(stored["shim_settings.json"]))
    res["5_reference_renders"] = {"ok": bool(stored) and len(stored) == len(cur)
                                  and all(stored[n] == cur[n] for n in cur),
                                  "files": {n: {"fresh": _sha(cur[n])[:12], "stored": _sha(stored[n])[:12]
                                                if n in stored else None} for n in cur}}
    moved = 0
    if archive:
        dst = P.AW_STATE / "archive" / arm
        dst.mkdir(parents=True, exist_ok=True)
        opt = P.AW_HOME / "opt"
        for f in opt.glob(f"{arm}.settings*.json") if opt.exists() else []:
            shutil.move(str(f), dst / f.name)
            moved += 1
        root = P.RUN_ROOTS[arm]
        if root.exists():
            subprocess.run(["chmod", "-R", "a-w", str(root)], check=True)
        writable = root.exists() and any(os.access(p, os.W_OK) for p in [root, *root.rglob("*")][:5000]
                                         if not p.is_symlink())
        res["6_archived_readonly"] = {"ok": not writable, "settings_files_moved": moved, "root_writable": writable}
    else:
        res["6_archived_readonly"] = {"ok": True, "skipped": "--no-archive"}
    res["ok"] = all(v["ok"] for k, v in res.items() if isinstance(v, dict))
    P.write_json(st / "reset_check.json", res)
    return res


def store_reference() -> dict:
    REF_STORE.mkdir(parents=True, exist_ok=True)
    out = {}
    for n, b in reference_renders().items():
        P.atomic_write(REF_STORE / n, b.decode())
        out[n] = _sha(b)
    return out


def main() -> int:
    if P.LEDGER_ID != "ABL":
        raise SystemExit("reset_check.py: source abl/env.sh first")
    arm = sys.argv[1]
    if "--store-reference" in sys.argv:
        print(json.dumps({"stored": store_reference()}))
        return 0
    if arm not in P.RUN_ROOTS:
        raise SystemExit(f"unknown arm {arm}")
    r = check(arm, archive="--no-archive" not in sys.argv)
    print(json.dumps(r, indent=1))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
