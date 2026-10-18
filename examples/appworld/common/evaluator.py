"""The single evaluator every eval-5 candidate calls (docs/EVAL_APPWORLD_5.md §1.3, §4.1, §7).

  materialize(cand, files) -> Path        candidate dir: a content-hashed copy of seed_capability with
                                          ``files`` ({"policy/instructions.txt": text, ...}) overriding it
  evaluate(cand, cdir, task_ids, *, phase, split, reuse) -> list[dict]
                                          one gold-free record per task: reward, F1 feedback, steps
                                          (thought/code/output), tokens, termination, instruction
  lint(cdir) -> list[str]                 the shared lint (+ the M_cap token rule)
  counted(cand) -> int                    fresh search rollouts used so far

Runs the shared adapter's ``run_trials`` (one subprocess per episode, AW_WORKERS at a time) and
``score`` (reward 0/1 + feedback tier F1). 1 trial per task, trial seed 100 (§0). Every fresh episode is
appended to ``AW_STATE/<cand>/rollouts.jsonl`` and counts against the candidate's hard cap (B=900 unless
the driver passes another, §7); a batch that would cross it raises ``BudgetExceeded`` before it starts.
``reuse=True`` replays an identical (candidate tree, ``tag``, task, seed) episode from the local record
instead of re-running it; a replay is not counted. Drivers pass a ``tag`` naming the call site and step
(GEPA iteration, SkillOpt step dir, WikiSkill iteration), so a replay happens only when a resumed run
repeats the same in-flight step, never where the method itself means to re-run a task. Must run in venv-aw (the adapter imports AppWorld types); ``evaluate`` falls back to a venv-aw
subprocess when called from a candidate venv.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import aw5 as P  # noqa: E402

P.setup_env()
SURFACES = ("policy/instructions.txt", "tools/helpers.py", "tools/api_notes.json", "memory/playbook.md")
_lock = threading.Lock()


class BudgetExceeded(RuntimeError):
    pass


def _in_venv_aw() -> bool:
    try:
        import cap_evolve  # noqa: F401
        return True
    except ImportError:
        return False


def materialize(cand: str, files: dict[str, str] | None = None, base: Path | None = None) -> Path:
    """Content-addressed candidate dir under AW_STATE/<cand>/cands/<sha12>/ (idempotent)."""
    base = Path(base or P.SEED_CAP)
    content: dict[str, str] = {}
    for rel in SURFACES:
        p = base / rel
        if p.is_file():
            content[rel] = p.read_text(encoding="utf-8")
    for rel, text in (files or {}).items():
        if rel not in SURFACES:
            raise ValueError(f"{rel} is not an injectable surface")
        content[rel] = text
    content = {k: v for k, v in content.items() if not (k == "memory/playbook.md" and not v.strip())}
    h = P.sha256_bytes(json.dumps(sorted(content.items())).encode())[:12]
    d = P.AW_STATE / cand / "cands" / h
    if not (d / ".done").exists():
        tmp = d.with_name(d.name + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        for rel, text in content.items():
            (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            (tmp / rel).write_text(text, encoding="utf-8")
        (tmp / "memory").mkdir(parents=True, exist_ok=True)
        (tmp / ".done").write_text(h)
        shutil.rmtree(d, ignore_errors=True)
        os.replace(tmp, d)
    return d


def read_surfaces(cdir: Path) -> dict[str, str]:
    return {rel: (Path(cdir) / rel).read_text(encoding="utf-8") for rel in SURFACES if (Path(cdir) / rel).is_file()}


def cand_hash(cdir: Path) -> str:
    return Path(cdir).name if (Path(cdir) / ".done").exists() else P.sha256_tree(cdir)[:12]


def memory_tokens(text: str) -> int:
    try:
        import tiktoken
        return len(tiktoken.get_encoding("o200k_base").encode(text))
    except Exception:  # noqa: BLE001
        return len(text) // 3


def m_cap_tokens() -> int | None:
    return P.manifest().get("m_cap", {}).get("tokens")


def lint(cdir: Path) -> list[str]:
    """The shared lint, plus two eval-5 rules for the memory slot (§1.3, §6): the 8-gram / supervisor-contact
    check the shared lint applies to the prompt, helpers and notes (lints.py checks only the memory's length),
    and the token cap M_cap."""
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


def counted(cand: str) -> int:
    return len(P.read_jsonl(P.AW_STATE / cand / "rollouts.jsonl"))


def _rec_path(cand: str, h: str, tid: str, seed: int, tag: str = "") -> Path:
    import re
    t = re.sub(r"[^A-Za-z0-9._-]+", "_", tag).strip("_")
    return P.AW_STATE / cand / "episodes" / h / (t or "_") / f"{tid}__s{seed}.json"


def _record(task, rollout, score) -> dict:
    m = rollout.metadata or {}
    return {"task_id": task.id, "instruction": task.input["instruction"], "supervisor": task.input["supervisor"],
            "reward": float(score.reward), "feedback": score.feedback, "error": rollout.error,
            "lint_reject": bool(m.get("lint_reject")),
            "steps": rollout.trace or [],
            **{k: m.get(k) for k in ("success", "num_tests", "pass_count", "failed_requirements",
                                     "collateral_damage", "complete_task_called", "termination", "n_steps",
                                     "prompt_tokens", "completion_tokens", "max_prompt_tokens", "api_errors",
                                     "fs_probe", "episode_seconds", "trimmed_steps")}}


def _evaluate_local(cand: str, cdir: Path, task_ids: list[str], phase: str, split: str, reuse: bool,
                    hard_cap: int, seed: int, tag: str = "") -> list[dict]:
    sys.path.insert(0, str(HERE.parent / "adapters"))
    import adapter as A
    ad = A.Adapter()
    cdir = Path(cdir).resolve()
    h = cand_hash(cdir)
    out: dict[str, dict] = {}
    todo = []
    for tid in task_ids:
        rp = _rec_path(cand, h, tid, seed, tag)
        if reuse and rp.exists():
            out[tid] = dict(json.loads(rp.read_text()), replayed=True)
        else:
            todo.append(tid)
    if todo:
        v = lint(cdir)
        if v:  # rejected before any rollout (§6): every task 0, the violations as feedback, nothing counted
            for tid in todo:
                out[tid] = {"task_id": tid, "reward": 0.0, "lint_reject": True, "steps": [],
                            "feedback": "LINT_REJECT (candidate not run): " + "; ".join(v), "error": None}
            P.progress_log(cand, phase, f"lint_reject {h}: {len(v)} violation(s), {len(todo)} tasks scored 0")
        else:
            with _lock:
                used = counted(cand)
                if used + len(todo) > hard_cap:
                    raise BudgetExceeded(f"{cand}: {used} counted + {len(todo)} > cap {hard_cap}")
            os.environ.setdefault("AW_PROGRESS_LOG", str(P.PROGRESS / f"{cand}.log"))
            os.environ["AW_TRIAL"], os.environ["AW_PHASE"] = cand, f"{phase}/{split}"
            os.environ.setdefault("AW_EXPERIMENT", f"eval5_{cand}")
            tasks = [A._task_cached(t, str(A.ROOT_OPT)) for t in todo]
            res = ad.run_trials(tasks, cdir, n_trials=1, base_seed=seed)
            for t in tasks:
                r = res[t.id][0]
                rec = _record(t, r, ad.score(t, r))
                P.atomic_write(_rec_path(cand, h, t.id, seed, tag), json.dumps(rec))
                P.append_jsonl(P.AW_STATE / cand / "rollouts.jsonl", {
                    "t": P.utcnow(), "phase": phase, "split": split, "cand": h, "tag": tag, "reward": rec["reward"],
                    "infra": bool(rec["error"]), "steps": rec.get("n_steps"), "prompt_tokens": rec.get("prompt_tokens"),
                    "completion_tokens": rec.get("completion_tokens"), "seconds": rec.get("episode_seconds"),
                    "termination": rec.get("termination"), "fs_probe": rec.get("fs_probe")})
                out[t.id] = rec
    return [out[t] for t in task_ids]


def evaluate(cand: str, cdir: Path, task_ids: list[str], *, phase: str, split: str, reuse: bool = False,
             hard_cap: int = P.BUDGET_ROLLOUTS, seed: int = P.SEARCH_SEED_BASE, tag: str = "") -> list[dict]:
    if _in_venv_aw():
        return _evaluate_local(cand, cdir, task_ids, phase, split, reuse, hard_cap, seed, tag)
    req = {"cand": cand, "cdir": str(cdir), "task_ids": task_ids, "phase": phase, "split": split, "reuse": reuse,
           "hard_cap": hard_cap, "seed": seed, "tag": tag}
    work = P.AW_STATE / cand / "evalreq"
    work.mkdir(parents=True, exist_ok=True)
    rq = work / f"{os.getpid()}_{threading.get_ident()}.json"
    rq.write_text(json.dumps(req))
    r = subprocess.run([str(P.VENV_PY), "-I", str(Path(__file__)), "serve", str(rq)], capture_output=True,
                       text=True, env=P.setup_env(dict(os.environ)))
    resp = json.loads(rq.with_suffix(".out").read_text()) if rq.with_suffix(".out").exists() else None
    rq.unlink(missing_ok=True)
    rq.with_suffix(".out").unlink(missing_ok=True)
    if r.returncode or resp is None:
        if resp and resp.get("budget"):
            raise BudgetExceeded(resp["error"])
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
        recs = _evaluate_local(rq["cand"], Path(rq["cdir"]), rq["task_ids"], rq["phase"], rq["split"], rq["reuse"],
                               rq["hard_cap"], rq["seed"], rq.get("tag", ""))
        out.write_text(json.dumps({"records": recs}))
        return 0
    except BudgetExceeded as e:
        out.write_text(json.dumps({"budget": True, "error": str(e)}))
        return 3


if __name__ == "__main__":
    if sys.argv[1] == "serve":
        raise SystemExit(_serve(sys.argv[2]))
    if sys.argv[1] == "lint":
        v = lint(Path(sys.argv[2]))
        print(json.dumps({"ok": not v, "violations": v}, indent=1))
        raise SystemExit(1 if v else 0)
