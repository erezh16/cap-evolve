"""Episode runner and scorer (plan §7).

tasks(split)            ids from load_task_ids only; the seal refuses ids outside train ∪ dev
                        unless AW_ALLOW_SEALED=final-eval-only.
run_episodes(specs, workers)
                        thread pool; each episode is its own subprocess (aw_agent.py SPEC OUT),
                        30-minute wall cap (real kill); infra errors retried with new trial seeds
                        (attempt a uses seed + 1000·a); records written atomically; AppWorld's
                        native output dir deleted after the record is written.
score(record)           1.0 if success else 0.0.
"""

from __future__ import annotations

import concurrent.futures as cf
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import awpaths as P  # noqa: E402

WALL_CAP_S = int(os.environ.get("AW_WALL_CAP_S", 1800))
SEARCH_SPLITS = ("train", "dev")


class Sealed(PermissionError):
    pass


def _split_ids(split: str) -> list[str]:
    """load_task_ids in a subprocess with the right root (the caller may be outside the venv)."""
    root = P.ROOT_FULL if split not in SEARCH_SPLITS else P.ROOT_OPT
    code = ("import json,sys; from appworld.task import load_task_ids; "
            "print(json.dumps(load_task_ids(sys.argv[1])))")
    r = subprocess.run([str(P.VENV_PY), "-I", "-c", code, split], capture_output=True, text=True,
                       env={**os.environ, "APPWORLD_ROOT": str(root)}, check=True)
    return json.loads(r.stdout.strip().splitlines()[-1])


def tasks(split: str) -> list[str]:
    if split not in SEARCH_SPLITS and os.environ.get("AW_ALLOW_SEALED") != "final-eval-only":
        raise Sealed(f"split {split!r} is sealed (set AW_ALLOW_SEALED=final-eval-only in the final window)")
    return _split_ids(split)


def check_seal(task_id: str, allowed: set[str] | None = None) -> None:
    if os.environ.get("AW_ALLOW_SEALED") == "final-eval-only":
        return
    if allowed is None:
        allowed = set(_split_ids("train")) | set(_split_ids("dev"))
    if task_id not in allowed:
        raise Sealed("task id outside train ∪ dev refused by the seal")


def score(record: dict) -> float:
    return 1.0 if record.get("success") else 0.0


def _run_one(spec: dict, out_path: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="awspec-") as td:
        sp = Path(td) / "spec.json"
        sp.write_text(json.dumps(spec))
        tmp_out = Path(td) / "out.json"
        env = {k: v for k, v in os.environ.items() if k not in ("RITS_API_KET", "RITS_API_KEY")}
        env["APPWORLD_ROOT"] = spec["appworld_root"]
        env["HF_HOME"] = str(P.HF_HOME)
        t0 = time.time()
        try:
            proc = subprocess.run([str(P.VENV_PY), "-I", str(HERE / "aw_agent.py"), str(sp), str(tmp_out)],
                                  env=env, capture_output=True, text=True, timeout=WALL_CAP_S,
                                  cwd=str(P.AW_STATE))
            if tmp_out.exists():
                rec = json.loads(tmp_out.read_text())
            else:
                rec = {"infra_error": True, "termination": "infra_error", "success": False,
                       "error": f"worker exit {proc.returncode}: {proc.stderr[-400:]}"}
        except subprocess.TimeoutExpired:
            rec = {"infra_error": True, "termination": "wall_cap", "success": False,
                   "error": f"wall cap {WALL_CAP_S}s"}
        rec.setdefault("task_id", spec["task_id"])
        rec.setdefault("experiment_name", spec["experiment_name"])
        rec["wall_s_outer"] = round(time.time() - t0, 1)
    nd = rec.pop("native_output_dir", None)
    exp_dir = Path(spec["appworld_root"]) / "experiments" / "outputs" / spec["experiment_name"]
    for d in (nd, exp_dir):
        if d and Path(d).exists():
            shutil.rmtree(Path(d).resolve(), ignore_errors=True)
    return rec


def run_episode(spec: dict, out_path: Path | str, max_infra_retries: int = 1,
                on_attempt=None) -> dict:
    """Run one cell with infra retries (new trial seed per attempt). Writes the record atomically."""
    out_path = Path(out_path)
    base_seed = int(spec["trial_seed"])
    attempts = []
    rec = {}
    for a in range(max_infra_retries + 1):
        s = dict(spec, trial_seed=base_seed + 1000 * a)
        if a:
            s["experiment_name"] = f"{spec['experiment_name']}-r{a}"
        rec = _run_one(s, out_path)
        attempts.append({"attempt": a, "seed": s["trial_seed"], "termination": rec.get("termination"),
                         "infra_error": bool(rec.get("infra_error")), "error": (rec.get("error") or "")[:200]})
        if on_attempt:
            on_attempt(a, rec)
        if not rec.get("infra_error"):
            break
    rec["attempts"] = attempts
    rec["infra_retries"] = len(attempts) - 1
    P.atomic_write(out_path, json.dumps(rec, indent=1) + "\n")
    return rec


def run_episodes(items: list[tuple[dict, Path]], workers: int | None = None, max_infra_retries: int = 1,
                 on_done=None, stop_event: threading.Event | None = None) -> list[dict]:
    """items: (spec, out_path). Cells whose record already exists are skipped (resume)."""
    workers = workers or int(os.environ.get("AW_WORKERS", 24))
    results: list[dict | None] = [None] * len(items)

    def job(i):
        spec, out = items[i]
        if stop_event is not None and stop_event.is_set():
            return i, None
        if Path(out).exists():
            return i, json.loads(Path(out).read_text())
        return i, run_episode(spec, out, max_infra_retries=max_infra_retries)

    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(job, i) for i in range(len(items))]
        for f in cf.as_completed(futs):
            i, rec = f.result()
            results[i] = rec
            if on_done and rec is not None:
                on_done(i, rec)
    return results  # type: ignore[return-value]


def episode_spec(task_id: str, experiment_name: str, capability_dir: Path | str, trial_seed: int,
                 final: bool = False, **extra) -> dict:
    return {"task_id": task_id, "experiment_name": experiment_name,
            "capability_dir": str(capability_dir), "trial_seed": int(trial_seed),
            "appworld_root": str(P.ROOT_FULL if final else P.ROOT_OPT), "max_steps": 50,
            "token_cap": 100000, **extra}
