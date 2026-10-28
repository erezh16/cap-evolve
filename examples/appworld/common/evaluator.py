"""The single evaluator every eval-REST candidate calls (docs/EVAL_APPWORLD_REST.md §7.2, rules Q1, Q4).

  materialize(cand, files, base=None) -> Path   a content-addressed candidate dir: seed_capability with
                                                ``files`` ({"policy/instructions.txt": text, ...}) overriding it
  tree_hash(cdir) -> str                        the cache key part of a candidate: sha256 over its surfaces
  evaluate(cand, cdir, task_ids, *, phase, tag="") -> list[dict]
                                                one gold-free record per task (reward, F1 feedback, steps,
                                                tokens, termination, instruction), in task_ids order
  lint(cdir) -> list[str]                       the shared lint (+ the memory 8-gram rule and M_cap)
  counted(cand) -> int                          fresh search rollouts charged to the candidate so far

What evaluate() does, in order (§7.2):
 1. lints the candidate (in venv-aw) and returns lint-reject records, with every field of a normal record,
    without running anything;
 2. returns the cached record for each (tree hash, task, trial seed) already on disk: not counted, logged
    to AW_STATE/<cand>/cache_hits.jsonl. The cache is global (AW_STATE/cache/), so a candidate dir
    identical to the seed is served from the shared seed baseline of P3 (Q4);
 3. refuses a fresh episode of SEED_HASH once P3 is done (SeedRerunRefused) and any id outside
    train ∪ dev unless AW_ALLOW_SEALED=final-eval-only;
 4. raises BudgetExceeded before starting a batch that would take the candidate's fresh count past its cap
    (B = 900 for phase "search");
 5. runs each fresh episode in one global slot (AW_STATE/slots, §7.3; waits while AW_STATE/PAUSE exists,
    R2) through the shared adapter's worker (aw_agent.py subprocess, APPWORLD_ROOT=root_opt, 30-min wall
    cap, one infra retry with the same seed);
 6. appends every fresh record of phase "search" to AW_STATE/<cand>/rollouts.jsonl (counted) and caches
    it; an infrastructure failure is recorded but not cached.

Phases: "search" (counted against B), "P3" (the shared seed baseline, charged to "seed"), "P5" (the dev
diagnostic, not counted), "accept" (acceptance probes: not counted, cached in a separate namespace so a
probe never becomes part of the shared seed baseline). Must run in an AppWorld venv (venv-aw or
venv-cape); from any other venv ``evaluate`` and ``lint`` shell out to venv-aw.
"""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import awrest as P  # noqa: E402

P.setup_env()
SURFACES = ("policy/instructions.txt", "tools/helpers.py", "tools/api_notes.json", "memory/playbook.md")
PHASES = ("search", "P3", "P5", "accept")
CACHE = P.AW_STATE / "cache"
SEED_DONE = P.AW_STATE / "SEED_BASELINE_DONE"
RECORD_FIELDS = ("success", "num_tests", "pass_count", "failed_requirements", "collateral_damage",
                 "complete_task_called", "termination", "n_steps", "prompt_tokens", "completion_tokens",
                 "max_prompt_tokens", "api_errors", "fs_probe", "episode_seconds", "trimmed_steps")
_lock = threading.Lock()
_inflight: dict[str, int] = {}


class BudgetExceeded(RuntimeError):
    pass


class SeedRerunRefused(RuntimeError):
    pass


def _in_appworld_venv() -> bool:
    try:
        import appworld  # noqa: F401
        import cap_evolve  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------- candidates

def _content(base: Path, files: dict[str, str] | None = None) -> dict[str, str]:
    content: dict[str, str] = {}
    for rel in SURFACES:
        p = Path(base) / rel
        if p.is_file():
            content[rel] = p.read_text(encoding="utf-8")
    for rel, text in (files or {}).items():
        if rel not in SURFACES:
            raise ValueError(f"{rel} is not an injectable surface")
        content[rel] = text
    # an empty playbook is no memory: the same tree as none (the seed has no memory block)
    return {k: v for k, v in content.items() if not (k == "memory/playbook.md" and not v.strip())}


def _hash(content: dict[str, str]) -> str:
    return P.sha256_bytes(json.dumps(sorted(content.items())).encode())


def tree_hash(cdir: Path) -> str:
    """sha256 over the candidate's surface files (sorted (path, text) pairs). The cache key of Q1."""
    return _hash(_content(Path(cdir)))


def seed_hash() -> str:
    return tree_hash(P.SEED_CAP)


def materialize(cand: str, files: dict[str, str] | None = None, base: Path | None = None) -> Path:
    """Content-addressed candidate dir under AW_STATE/<cand>/cands/<sha12>/ (idempotent)."""
    content = _content(Path(base or P.SEED_CAP), files)
    h = _hash(content)[:12]
    d = P.AW_STATE / cand / "cands" / h
    if not (d / ".done").exists():
        tmp = d.with_name(d.name + f".tmp{os.getpid()}_{threading.get_ident()}")
        shutil.rmtree(tmp, ignore_errors=True)
        for rel, text in content.items():
            (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            (tmp / rel).write_text(text, encoding="utf-8")
        (tmp / "memory").mkdir(parents=True, exist_ok=True)
        (tmp / ".done").write_text(h)
        if not (d / ".done").exists():
            shutil.rmtree(d, ignore_errors=True)
            os.replace(tmp, d)
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    return d


def read_surfaces(cdir: Path) -> dict[str, str]:
    return _content(Path(cdir))


def memory_tokens(text: str) -> int:
    try:
        import tiktoken
        return len(tiktoken.get_encoding("o200k_base").encode(text))
    except Exception:  # noqa: BLE001
        return len(text) // 3


def m_cap_tokens() -> int | None:
    return P.manifest().get("m_cap", {}).get("tokens")


def lint(cdir: Path) -> list[str]:
    """The shared lint, plus the memory slot's 8-gram / supervisor-contact rule and the token cap M_cap.
    Always runs in venv-aw (eval 5 lesson: jinja2 and tiktoken live there)."""
    if not _in_appworld_venv():
        r = subprocess.run([str(P.VENV_PY), "-I", str(Path(__file__)), "lint", str(cdir)], capture_output=True,
                           text=True, env=P.setup_env(dict(os.environ)))
        try:
            return json.loads(r.stdout)["violations"]
        except (json.JSONDecodeError, KeyError):
            raise RuntimeError(f"lint subprocess failed: {r.stderr[-800:]}") from None
    sys.path.insert(0, str(HERE.parent / "adapters"))
    import lints
    v = lints.lint_candidate(Path(cdir))
    pb = Path(cdir) / "memory" / "playbook.md"
    if pb.is_file():
        text = pb.read_text(encoding="utf-8")
        v += lints._leaks(text, "memory/playbook.md")
        cap = m_cap_tokens()
        n = memory_tokens(text)
        if cap and n > cap:
            v.append(f"memory/playbook.md: {n} tokens > M_cap {cap}")
    return v


# ---------------------------------------------------------------- accounting

def counted(cand: str) -> int:
    return len(P.read_jsonl(P.AW_STATE / cand / "rollouts.jsonl"))


def cache_hits(cand: str) -> int:
    return len(P.read_jsonl(P.AW_STATE / cand / "cache_hits.jsonl"))


def _cache_path(h: str, tid: str, seed: int, phase: str) -> Path:
    ns = "accept" if phase == "accept" else "main"
    return CACHE / ns / h[:16] / f"{tid}__s{seed}.json"


def _ledger_file(cand: str, phase: str) -> Path:
    if phase == "search":
        return P.AW_STATE / cand / "rollouts.jsonl"           # counted against B
    if phase == "P3":
        return P.AW_STATE / "seed" / "rollouts.jsonl"         # the shared seed baseline (147)
    return P.AW_STATE / cand / f"{phase.lower()}_rollouts.jsonl"  # P5 / accept: not counted


def _record(task, rollout, score) -> dict:
    m = rollout.metadata or {}
    return {"task_id": task.id, "instruction": task.input["instruction"], "supervisor": task.input["supervisor"],
            "reward": float(score.reward), "feedback": score.feedback, "error": rollout.error,
            "lint_reject": bool(m.get("lint_reject")),
            "steps": rollout.trace or [],
            **{k: m.get(k) for k in RECORD_FIELDS}}


def _lint_reject_record(task, violations: list[str]) -> dict:
    """The same fields as a normal record (eval 5 lesson: a driver crashed on a missing field)."""
    rec = {"task_id": task.id, "instruction": task.input["instruction"], "supervisor": task.input["supervisor"],
           "reward": 0.0, "feedback": "LINT_REJECT (candidate not run): " + "; ".join(violations), "error": None,
           "lint_reject": True, "steps": []}
    rec.update({k: None for k in RECORD_FIELDS})
    rec.update({"success": False, "num_tests": 0, "pass_count": 0, "failed_requirements": [], "n_steps": 0,
                "prompt_tokens": 0, "completion_tokens": 0, "max_prompt_tokens": 0, "api_errors": 0,
                "termination": "lint_reject", "fs_probe": False, "episode_seconds": 0.0, "trimmed_steps": 0})
    return rec


class _FileLock:
    """flock on a file, so a budget check and its reservation are atomic across processes."""

    def __init__(self, path: Path):
        self.p = path

    def __enter__(self):
        self.p.parent.mkdir(parents=True, exist_ok=True)
        self.f = open(self.p, "a")
        fcntl.flock(self.f, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        fcntl.flock(self.f, fcntl.LOCK_UN)
        self.f.close()
        return False


def _reserved(cand: str) -> int:
    """Fresh episodes in flight across processes, from AW_STATE/<cand>/inflight/<pid>_<tid>."""
    d = P.AW_STATE / cand / "inflight"
    n = 0
    for f in d.glob("*") if d.exists() else []:
        try:
            pid = int(f.name.split("_")[0])
            os.kill(pid, 0)
            n += int(f.read_text() or 0)
        except (ValueError, ProcessLookupError, FileNotFoundError):
            f.unlink(missing_ok=True)       # a dead process's reservation
        except PermissionError:
            n += int(f.read_text() or 0)
    return n


# ---------------------------------------------------------------- evaluate

def _evaluate_local(cand: str, cdir: Path, task_ids: list[str], phase: str, tag: str, hard_cap: int,
                    seed: int) -> list[dict]:
    if phase not in PHASES:
        raise ValueError(f"phase must be one of {PHASES}")
    sys.path.insert(0, str(HERE.parent / "adapters"))
    import adapter as A
    ad = A.Adapter()
    cdir = Path(cdir).resolve()
    h = tree_hash(cdir)
    ad._check_seal(task_ids)                                      # rule 3: test ids are sealed
    root = str(A._appworld_root())
    tasks = {t: A._task_cached(t, root) for t in dict.fromkeys(task_ids)}
    out: dict[str, dict] = {}
    todo = []
    if os.environ.get("AW_ABL_TOOLS_LINT") == "1":
        # ABLATIONS §10.4: the arm's own lint runs before the cross-arm tree-hash cache, so a cached record of the
        # same tree made by an arm without this lint can never serve a candidate this arm must reject
        v = lint(cdir)
        if v:
            P.append_jsonl(P.AW_STATE / cand / "lint_rejects.jsonl",
                           {"t": P.utcnow(), "phase": phase, "tag": tag, "cand": h[:12], "tasks": len(tasks),
                            "violations": len(v)})
            return [_lint_reject_record(tasks[t], v) for t in task_ids]
    for tid in tasks:
        cp = _cache_path(h, tid, seed, phase)
        if cp.exists():                                           # rule 2: cache hit, not counted
            out[tid] = dict(json.loads(cp.read_text()), cache_hit=True)
            P.append_jsonl(P.AW_STATE / cand / "cache_hits.jsonl",
                           {"t": P.utcnow(), "phase": phase, "tag": tag, "cand": h[:12], "seed": seed,
                            "reward": out[tid]["reward"]})
        else:
            todo.append(tid)
    if todo:
        v = lint(cdir)
        if v:  # rule 1: rejected before any rollout; every task 0 with the violations, nothing counted
            for tid in todo:
                out[tid] = _lint_reject_record(tasks[tid], v)
            P.append_jsonl(P.AW_STATE / cand / "lint_rejects.jsonl",
                           {"t": P.utcnow(), "phase": phase, "tag": tag, "cand": h[:12], "tasks": len(todo),
                            "violations": len(v)})
            P.progress_log(cand, phase, f"lint_reject {h[:12]}: {len(v)} violation(s), {len(todo)} tasks scored 0")
            return [dict(out[t]) for t in task_ids]
        if phase != "accept" and h == seed_hash() and SEED_DONE.exists():
            raise SeedRerunRefused(f"{cand}: {len(todo)} fresh episode(s) of the seed after P3 (rule Q4); "
                                   "only cache hits of the shared seed baseline are allowed")
        charge = "seed" if phase == "P3" else cand
        res_file = P.AW_STATE / charge / "inflight" / f"{os.getpid()}_{threading.get_ident()}"
        with _FileLock(P.AW_STATE / charge / ".budget.lock"):    # rule 4: check and reserve, atomically
            used = len(P.read_jsonl(_ledger_file(cand, phase))) + _reserved(charge)
            if phase == "search" and used + len(todo) > hard_cap:
                raise BudgetExceeded(f"{cand}: {used} counted + {len(todo)} > cap {hard_cap}")
            res_file.parent.mkdir(parents=True, exist_ok=True)
            res_file.write_text(str(len(todo)))
        try:
            out.update(_run_fresh(ad, cand, cdir, h, [tasks[t] for t in todo], phase, tag, seed))
        finally:
            res_file.unlink(missing_ok=True)
    return [dict(out[t]) for t in task_ids]


def _run_fresh(ad, cand: str, cdir: Path, h: str, tasks: list, phase: str, tag: str, seed: int) -> dict:
    import tempfile
    sys.path.insert(0, str(HERE.parent / "adapters"))
    import adapter as A
    root = A._appworld_root()
    os.environ.setdefault("AW_EXPERIMENT", f"awrest_{cand}")
    scratch = Path(os.environ.get("AW_SCRATCH", str(P.SCRATCH / "scratch")))
    scratch.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="aw_eps_", dir=scratch))
    lf = _ledger_file(cand, phase)

    def one(task):
        with P.Slot(f"{cand}/{phase}"):                          # rule 5: one global slot per episode (R2 aware)
            r = ad._episode(task, cdir, seed, root, workdir, random_seed=seed)
        rec = _record(task, r, ad.score(task, r))
        if not rec["error"]:                                      # infra failures are never cached (Q1)
            P.atomic_write(_cache_path(h, task.id, seed, phase), json.dumps(rec))
        P.append_jsonl(lf, {"t": P.utcnow(), "phase": phase, "tag": tag, "cand": h[:12], "seed": seed,
                            "reward": rec["reward"], "infra": bool(rec["error"]), "steps": rec.get("n_steps"),
                            "prompt_tokens": rec.get("prompt_tokens"),
                            "completion_tokens": rec.get("completion_tokens"),
                            "max_prompt_tokens": rec.get("max_prompt_tokens"),
                            "seconds": rec.get("episode_seconds"), "termination": rec.get("termination"),
                            "fs_probe": rec.get("fs_probe")})
        return task.id, rec

    n = max(1, min(len(tasks), P.global_slots()))
    with ThreadPoolExecutor(max_workers=n) as pool:
        res = dict(pool.map(one, tasks))
    try:
        workdir.rmdir()
    except OSError:
        pass
    ok = sum(1 for r in res.values() if r["reward"] == 1.0)
    P.progress_log(cand, phase, f"{tag or '-'}: {len(res)} fresh episodes of {h[:12]}, passed {ok}, "
                                f"infra {sum(1 for r in res.values() if r['error'])}")
    return res


def evaluate(cand: str, cdir: Path, task_ids: list[str], *, phase: str, tag: str = "",
             hard_cap: int = P.BUDGET_ROLLOUTS, seed: int = P.SEARCH_SEED_BASE) -> list[dict]:
    if _in_appworld_venv():
        return _evaluate_local(cand, cdir, list(task_ids), phase, tag, hard_cap, seed)
    req = {"cand": cand, "cdir": str(cdir), "task_ids": list(task_ids), "phase": phase, "tag": tag,
           "hard_cap": hard_cap, "seed": seed}
    work = P.AW_STATE / cand / "evalreq"
    work.mkdir(parents=True, exist_ok=True)
    rq = work / f"{os.getpid()}_{threading.get_ident()}.json"
    rq.write_text(json.dumps(req))
    r = subprocess.run([str(P.VENV_PY), "-I", str(Path(__file__)), "serve", str(rq)], capture_output=True,
                       text=True, env=P.setup_env(dict(os.environ)))
    out = rq.with_suffix(".out")
    resp = json.loads(out.read_text()) if out.exists() else None
    rq.unlink(missing_ok=True)
    out.unlink(missing_ok=True)
    if r.returncode or resp is None or "records" not in resp:
        if resp and resp.get("budget"):
            raise BudgetExceeded(resp["error"])
        if resp and resp.get("seed_rerun"):
            raise SeedRerunRefused(resp["error"])
        raise RuntimeError(f"evaluator subprocess failed: {(resp or {}).get('error') or r.stderr[-1500:]}")
    return resp["records"]


def split_ids(name: str) -> list[str]:
    if name not in ("train", "dev"):
        raise PermissionError("search-time code reads only the train and dev splits")
    return P.read_split(name)


def _serve(path: str) -> int:
    rq = json.loads(Path(path).read_text())
    out = Path(path).with_suffix(".out")
    try:
        recs = _evaluate_local(rq["cand"], Path(rq["cdir"]), rq["task_ids"], rq["phase"], rq.get("tag", ""),
                               rq["hard_cap"], rq["seed"])
        out.write_text(json.dumps({"records": recs}))
        return 0
    except BudgetExceeded as e:
        out.write_text(json.dumps({"budget": True, "error": str(e)}))
        return 3
    except SeedRerunRefused as e:
        out.write_text(json.dumps({"seed_rerun": True, "error": str(e)}))
        return 4
    except Exception as e:  # noqa: BLE001 — reported to the caller
        out.write_text(json.dumps({"error": f"{type(e).__name__}: {e}"[:1500]}))
        return 1


if __name__ == "__main__":
    if sys.argv[1] == "serve":
        raise SystemExit(_serve(sys.argv[2]))
    if sys.argv[1] == "lint":
        v = lint(Path(sys.argv[2]))
        print(json.dumps({"ok": not v, "violations": v}, indent=1))
        raise SystemExit(1 if v else 0)
    if sys.argv[1] == "seed-hash":
        print(seed_hash())
