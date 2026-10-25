"""The abl_cc eval daemon (docs/ABLATIONS.md §10.2): a trusted, unsandboxed host process and the arm's ONLY path to
rollouts. Run in venv-abl, after sourcing abl/env.sh, with AW_CAPE_ARM=abl_cc and AW_ABL_FEEDBACK=full.

  python -I evald.py loop WORKDIR        # nohup; pid in AW_STATE/abl_cc/EVALD.pid
  python -I evald.py once WORKDIR        # process the queued requests, then exit (tests, resume)

The sandboxed session can only drop ``WORKDIR/.eval/requests/<ticket>.json`` = ``{"dir": "<relative subdir>"}``
(through ``./eval_candidate``). For each request, oldest first, the daemon:
 1. resolves ``dir`` strictly inside WORKDIR: no absolute path, no ``..``, no symlink anywhere on the way or in a
    surface file, regular files only, each under 1 MB; anything else is refused;
 2. copies the three surface files into a content-addressed staging dir (evaluator.materialize), so the candidate
    cannot change mid-evaluation; ``memory/`` is not read (D13, as the cap-evolve arms);
 3. evaluates the FIXED 147 train ∪ dev ids through the shared evaluator (phase search, seed 100): the lint runs
    first (a reject costs 0 rollouts and returns the violations), cache hits are free (the seed and identical
    resubmissions), and B = 882 counted rollouts is enforced (a request that would pass it is refused, 0 spent);
 4. writes ``.eval/results/<ticket>/summary.json`` (mean reward, per-task reward, lint status, rollouts used and
    left) and ``trajectories/*.json`` in the reference's ``{"input", "rollout", "score"}`` format, built with
    abl/adapter.py's functions with AW_ABL_FEEDBACK=full (the same F1 content as abl_ref's ./trajectories/);
 5. logs every request in AW_STATE/abl_cc/evals.jsonl (counts and hashes only).
``.eval/results/<ticket>/status.json`` carries the progress while an evaluation runs. PAUSE is honoured by the
evaluator's slots (R2). The daemon never reads anything else the session wrote.
"""

from __future__ import annotations

import json
import os
import stat
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ABL = HERE.parent
EX = ABL.parent
sys.path[:0] = [str(ABL), str(EX / "common"), str(EX / "scripts")]
ARM = "abl_cc"
os.environ["AW_CAPE_ARM"] = ARM
os.environ.setdefault("AW_EXAMPLE", str(EX))
if os.environ.setdefault("AW_ABL_FEEDBACK", "full") != "full":
    raise SystemExit("evald: abl_cc gets the reference's feedback content (AW_ABL_FEEDBACK=full)")
import awrest as P  # noqa: E402
import evaluator as E  # noqa: E402

SURFACES = ("policy/instructions.txt", "tools/helpers.py", "tools/api_notes.json")
# A-ABL-CC dry run (AW_CC_DRY=1): 4 dev ids, the accept namespace (never counted, never the real cache), B = 8
DRY = os.environ.get("AW_CC_DRY") == "1"
PHASE = "accept" if DRY else "search"
BUDGET = 8 if DRY else P.BUDGET_ROLLOUTS
MAX_FILE = 1 << 20
STATE = P.AW_STATE / ARM
SEED = P.SEARCH_SEED_BASE


class Refused(Exception):
    pass


def search_ids() -> list[str]:
    if DRY:
        return P.read_split("dev")[:4]
    ids = P.read_split("train") + P.read_split("dev")
    if len(ids) != 147 or len(set(ids)) != 147:
        raise SystemExit(f"evald: train ∪ dev has {len(ids)} ids, expected 147")
    return ids


def resolve_candidate(work: Path, rel) -> Path:
    """Rule 1: the candidate dir, strictly inside WORKDIR, with no symlink on the way."""
    if not isinstance(rel, str) or not rel or "\0" in rel or rel.startswith("/") or "\\" in rel:
        raise Refused("dir must be a relative path inside the working directory")
    parts = Path(rel).parts
    if any(p == ".." for p in parts):
        raise Refused("dir may not contain '..'")
    cur = work
    for p in parts:
        if p == ".":
            continue
        cur = cur / p
        if cur.is_symlink():
            raise Refused("dir may not contain a symlink")
    real, root = cur.resolve(), work.resolve()
    if real != root and root not in real.parents:
        raise Refused("dir resolves outside the working directory")
    if not real.is_dir():
        raise Refused("dir is not a directory")
    return real


def read_candidate(cdir: Path) -> dict[str, str]:
    files = {}
    for rel in SURFACES:
        p = cdir / rel
        for q in (p.parent, p):
            if q.is_symlink():
                raise Refused(f"{rel}: symlinks are not allowed")
        if not p.exists():
            continue
        st = p.lstat()
        if not stat.S_ISREG(st.st_mode):
            raise Refused(f"{rel}: not a regular file")
        if st.st_size > MAX_FILE:
            raise Refused(f"{rel}: larger than {MAX_FILE} bytes")
        files[rel] = p.read_text(encoding="utf-8", errors="replace")
    if "policy/instructions.txt" not in files:
        raise Refused("policy/instructions.txt is missing")
    return files


def _write(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, p)


def used() -> int:
    """Counted rollouts of this arm (dry run: its accept-namespace rollouts, a separate count)."""
    return len(P.read_jsonl(STATE / "accept_rollouts.jsonl")) if DRY else E.counted(ARM)


def _progress_thread(status: Path, stop: threading.Event, base: int, cached: int, total: int, ticket: str) -> None:
    while not stop.wait(20):
        done = used() - base + cached
        _write(status, {"ticket": ticket, "state": "running", "tasks_done": min(done, total), "tasks": total,
                        "t": P.utcnow()})


def budget() -> dict:
    u = used()
    return {"rollouts_used": u, "rollouts_left": BUDGET - u, "budget": BUDGET}


def handle(work: Path, req_file: Path) -> dict:
    import adapter as AD                     # abl/adapter.py: _rollout and the filtered score (full = reference)
    ticket = req_file.stem
    res_dir = work / ".eval" / "results" / ticket
    status = res_dir / "status.json"
    log = {"t": P.utcnow(), "ticket": ticket}
    try:
        try:
            req = json.loads(req_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise Refused("the request is not a JSON object") from None
        if not isinstance(req, dict) or set(req) != {"dir"}:
            raise Refused('the request must be exactly {"dir": "<relative subdir>"}')
        files = read_candidate(resolve_candidate(work, req["dir"]))
        cdir = E.materialize(ARM, files)
        h = E.tree_hash(cdir)
        log["cand"] = h[:12]
        ids = search_ids()
        _write(status, {"ticket": ticket, "state": "queued_to_run", "tasks_done": 0, "tasks": len(ids), "t": P.utcnow()})
        base = used()
        cached = sum(1 for t in ids if E._cache_path(h, t, SEED, PHASE).exists())
        if not E.lint(cdir) and base + (len(ids) - cached) > BUDGET:     # a lint reject is free, so check only clean ones
            raise Refused(f"the rollout budget is spent ({base} of {BUDGET} used; this candidate needs "
                          f"{len(ids) - cached} new rollouts)")
        stop = threading.Event()
        th = threading.Thread(target=_progress_thread, args=(status, stop, base, cached, len(ids), ticket), daemon=True)
        th.start()
        try:
            recs = E.evaluate(ARM, cdir, ids, phase=PHASE, tag=f"abl_cc/{ticket}", seed=SEED, hard_cap=BUDGET)
        except E.BudgetExceeded:
            raise Refused(f"the rollout budget is spent ({budget()['rollouts_used']} of {BUDGET} used; "
                          "an evaluation needs one rollout per task not yet run for this candidate)") from None
        finally:
            stop.set()
        ad = AD.Adapter()
        tasks = {t.id: t for t in ad.tasks("train")}
        if any(t not in tasks for t in ids):
            raise RuntimeError("evald: an evaluated id is not in the adapter's train ∪ dev tasks")
        traj = res_dir / "trajectories"
        per_task, lint_reject = {}, False
        for rec in recs:
            r = AD.F.filter_rollout(AD._rollout(rec, SEED))
            sc = ad.score(tasks[rec["task_id"]], r)
            lint_reject = lint_reject or bool(rec.get("lint_reject"))
            per_task[rec["task_id"]] = sc.reward
            _write(traj / f"{rec['task_id']}__{ticket}__t0.json",
                   {"input": tasks[rec["task_id"]].input, "rollout": r.to_dict(), "score": sc.to_dict()})
        fresh = used() - base
        summary = {"ticket": ticket, "candidate_dir": req["dir"], "lint": "rejected" if lint_reject else "ok",
                   "mean_reward": round(sum(per_task.values()) / len(per_task), 4), "tasks": len(per_task),
                   "per_task_reward": per_task, "rollouts_this_evaluation": fresh, **budget()}
        if lint_reject:
            summary["lint_violations"] = recs[0]["feedback"]
        _write(res_dir / "summary.json", summary)
        _write(status, {"ticket": ticket, "state": "done", "tasks_done": len(ids), "tasks": len(ids), "t": P.utcnow()})
        log.update(state="done", lint=summary["lint"], mean_reward=summary["mean_reward"], fresh=fresh,
                   cache_hits=len(ids) - fresh if not lint_reject else 0, **budget())
    except Refused as e:
        _write(res_dir / "summary.json", {"ticket": ticket, "refused": str(e), **budget()})
        _write(status, {"ticket": ticket, "state": "refused", "reason": str(e), "t": P.utcnow()})
        log.update(state="refused", reason=str(e)[:200], **budget())
    except Exception as e:  # noqa: BLE001 — an infra fault is reported to the session as such, never as a score
        _write(status, {"ticket": ticket, "state": "error", "reason": "evaluation infrastructure error; retry later",
                        "t": P.utcnow()})
        log.update(state="error", error=f"{type(e).__name__}: {e}"[:300])
    finally:
        req_file.rename(req_file.with_suffix(".taken"))
        P.append_jsonl(STATE / "evals.jsonl", log)
        P.progress_log(ARM, "evald", json.dumps({k: v for k, v in log.items() if k not in ("reason", "error")}))
    return log


def pending(work: Path) -> list[Path]:
    q = work / ".eval" / "requests"
    return sorted((p for p in q.glob("*.json") if p.is_file() and not p.is_symlink()),
                  key=lambda p: p.stat().st_mtime) if q.is_dir() else []


def main() -> int:
    cmd, work = sys.argv[1], Path(sys.argv[2]).resolve()
    STATE.mkdir(parents=True, exist_ok=True)
    if cmd == "once":
        for rq in pending(work):
            print(json.dumps(handle(work, rq)))
        return 0
    (STATE / "EVALD.pid").write_text(str(os.getpid()))
    while True:
        for rq in pending(work):
            handle(work, rq)
        time.sleep(5)


if __name__ == "__main__":
    raise SystemExit(main())
