"""Scoring windows of eval REST: the dev diagnostic (P5) and the one final window (P7) (plan §12.1, §14).

  venv-aw/bin/python -I window.py freeze      # copy each champion's artifact + the seed, lint, tree-hash
  venv-aw/bin/python -I window.py dev         # P5: the 5 champions on dev (57), 1 trial, seed 100, through the
                                              #     shared evaluator (phase P5): most cells are cache hits, and the
                                              #     seed's dev numbers are the P3 records (never re-run, Q4)
  venv-aw/bin/python -I window.py final       # P7: 168 test_normal × 6 arms × 2 trials (seeds 5000+k), one order

The final window is a list of cells (arm, task, trial) in one random order fixed by a recorded seed (regenerated
from the seed and checked against the sha256 in manifest.json; no id is pushed). Each cell is one episode in one
global slot (§7.3; waits while AW_STATE/PAUSE exists, R2), its record (counters and flags only) written atomically
to AW_STATE/final/records/<idx>.json; a cell with a record is never re-run. Infra failures retry up to 3 times.
Checkpoints are coalesced to <= 1 ledger entry per 5 min; only counts are pushed (no per-arm test score before
P8). SIGTERM: running cells finish, no new cell starts. root_full is unlocked at P7 start and relocked at its end.
"""

from __future__ import annotations

import json
import os
import random
import shutil
import signal
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "adapters"))
sys.path.insert(0, str(HERE.parent / "common"))
import awrest as P  # noqa: E402

P.setup_env()
DEV_ORDER_SEED = 2026102005
FINAL_ORDER_SEED = 2026102007
if P.LEDGER_PREFIX == "CE2":            # CE2 §16: 20261022 + a fixed suffix, recorded in manifest.json in advance
    FINAL_ORDER_SEED = 2026102207
if P.LEDGER_ID == "CE3":                # CE3 §2: 20261024 + the same suffix; the window runs FINAL_ARMS_RUN only
    FINAL_ORDER_SEED = 2026102407
if P.LEDGER_ID == "ABL":                # ABLATIONS §15: 20261025 + the same fixed suffix; seed + 6 champions, one window
    FINAL_ORDER_SEED = 2026102507
WINDOW_ARMS = tuple(getattr(P, "FINAL_ARMS_RUN", P.ARMS))   # CE3: ("ce3_k02",); otherwise every arm
FINAL_TRIALS = 2
FINAL_DIR = "final"
ART = P.AW_STATE / FINAL_DIR / "artifacts"
KEEP = ("success", "num_tests", "pass_count", "n_steps", "prompt_tokens", "completion_tokens", "max_prompt_tokens",
        "termination", "collateral_damage", "complete_task_called", "api_errors", "trimmed_steps", "fs_probe",
        "episode_seconds", "attempt")


def make_order(task_ids: list[str], arms: list[str], trials: int, seed: int) -> list[dict]:
    cells = [{"arm": a, "task_id": t, "trial": k} for t in task_ids for a in arms for k in range(trials)]
    random.Random(seed).shuffle(cells)
    for i, c in enumerate(cells):
        c["idx"] = i
    return cells


def order_sha(order: list[dict]) -> str:
    return P.sha256_bytes(json.dumps(order, sort_keys=True).encode())


# ------------------------------------------------------------------ freeze (§14)

def artifact_dir(cand: str) -> Path:
    return P.PUSHED / cand / "artifact"


def freeze() -> int:
    """Copy seed + each candidate's pushed artifact into final/artifacts/, lint each, record tree hashes."""
    import evaluator as E
    ART.mkdir(parents=True, exist_ok=True)
    hashes, labels = {}, {}
    for arm in P.ARMS:
        src = P.SEED_CAP if arm == "seed" else artifact_dir(arm)
        if not (src / "policy" / "instructions.txt").exists():
            raise SystemExit(f"artifact of {arm} missing at {src}")
        dst = ART / arm
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("README.md", "FREEZE.json"))
        (dst / "memory").mkdir(exist_ok=True)
        v = E.lint(dst)
        if v:
            raise SystemExit(f"frozen artifact {arm} fails the lint: {v}")
        hashes[arm] = E.tree_hash(dst)
        fz = P.read_json(src / "FREEZE.json", {}) or {}
        labels[arm] = fz.get("label", "seed" if arm == "seed" else "")
    if hashes["seed"] != E.seed_hash():
        raise SystemExit("the frozen seed differs from SEED_HASH")
    P.update_manifest(freeze={"tree_sha256": hashes, "labels": labels, "utc": P.utcnow()})
    print(json.dumps({"frozen": {a: h[:16] for a, h in hashes.items()}, "labels": labels}, indent=1))
    return 0


def _check_frozen() -> dict[str, Path]:
    import evaluator as E
    m = P.manifest()
    caps = {a: ART / a for a in P.ARMS}
    for a in P.ARMS:
        if E.tree_hash(caps[a]) != m["freeze"]["tree_sha256"][a]:
            raise SystemExit(f"frozen artifact {a} changed since the freeze")
    return caps


def dev() -> int:
    """P5: every arm on dev (57), 1 trial, seed 100, through the shared evaluator (phase P5, not counted)."""
    import evaluator as E
    caps = _check_frozen()
    ids = E.split_ids("dev")
    per = {}
    for arm in (P.ARMS if P.LEDGER_ID != "CE3" else ("seed",) + tuple(P.CANDIDATES)):
        recs = E.evaluate("seed" if arm == "seed" else arm, caps[arm], ids, phase="P5", tag="p5dev")
        ok = [r for r in recs if not r.get("error")]
        per[arm] = {"tgc": round(sum(r["reward"] for r in ok) / max(1, len(ok)), 4), "n": len(ok),
                    "cache_hits": sum(1 for r in recs if r.get("cache_hit")),
                    "fresh": sum(1 for r in recs if not r.get("cache_hit")),
                    "infra": sum(1 for r in recs if r.get("error"))}
    P.write_json(P.PUSHED / "p5dev" / "progress.json", {"window": "p5dev", "per_arm": per,
                                                        "label": "dev TGC, 1 trial, selection-biased for arms that "
                                                                 "selected on dev"})
    import status_doc
    status_doc.append("phase_done", "P5", "dev diagnostic",
                      "P5 dev diagnostic done (57 dev tasks, 1 trial, seed 100; the seed's numbers are its P3 records). "
                      + "; ".join(f"{a} {v['tgc']} ({v['fresh']} fresh, {v['cache_hits']} cached)" for a, v in per.items())
                      + ". Next: P6 full isolation scan.", done_through="P5/dev", next_unit="P6/scan",
                      artifacts=["STATE/p5dev/progress.json"], subject="P5 dev diagnostic")
    return 0


# ------------------------------------------------------------------ the final window runner

class Window:
    def __init__(self, name: str, phase: str, label: str, order: list[dict], caps: dict[str, Path], root: Path,
                 seed_base: int, final: bool, workers: int, retries: int, next_done: str, coalesce_s: int = 300):
        self.__dict__.update(locals())
        self.dir = P.AW_STATE / name
        self.records = self.dir / "records"
        self.records.mkdir(parents=True, exist_ok=True)
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.new = 0

    def done(self) -> dict[int, dict]:
        out = {}
        for p in self.records.glob("*.json"):
            try:
                out[int(p.stem)] = json.loads(p.read_text())
            except (ValueError, json.JSONDecodeError):
                p.unlink()
        return out

    def counts(self, done: dict[int, dict]) -> dict:
        per = {}
        for i, r in done.items():
            d = per.setdefault(self.order[i]["arm"], {"done": 0, "infra_missing": 0, "infra_retries": 0,
                                                      "context_exceeded": 0})
            d["done"] += 1
            d["infra_missing"] += int(bool(r.get("infra_error")))
            d["infra_retries"] += int(r.get("attempt") or 0)
            d["context_exceeded"] += int(r.get("termination") == "context_exceeded")
        return per

    def checkpoint(self, final_flush: bool = False) -> None:
        with self.lock:
            n_new, self.new = self.new, 0
        if not n_new and not final_flush:
            return
        done = self.done()
        per = self.counts(done)
        complete = len(done) >= len(self.order)
        prog = {"window": self.name, "cells_total": len(self.order), "cells_done": len(done), "per_arm": per,
                "order_sha256": order_sha(self.order)}
        P.write_json(P.PUSHED / self.name / "progress.json", prog)
        P.progress_log(self.name, self.phase, f"{len(done)}/{len(self.order)} cells")
        import status_doc
        status_doc.append("phase_done" if complete else "result", self.phase, self.label,
                          f"{self.label}: {n_new} cells since the last entry; {len(done)}/{len(self.order)} done "
                          f"({', '.join(a + ' ' + str(v['done']) for a, v in sorted(per.items()))}); infra still missing "
                          f"{sum(v['infra_missing'] for v in per.values())}, retries "
                          f"{sum(v['infra_retries'] for v in per.values())}.\n"
                          f"Next: {self.next_done if complete else self.name + ' remaining cells'}.",
                          done_through=f"{self.name}/{len(done)}", next_unit=self.next_done if complete else f"{self.name}/cells",
                          extra={"candidate": None, "window": {k: prog[k] for k in ("window", "cells_total", "cells_done",
                                                                                     "order_sha256")}},
                          artifacts=[f"STATE/{self.name}/progress.json"], subject=f"{self.name} {len(done)}/{len(self.order)}")

    def run(self) -> int:
        import adapter as A
        signal.signal(signal.SIGTERM, lambda *_: self.stop.set())
        os.environ["AW_INFRA_RETRIES"] = str(self.retries)
        os.environ["AW_EXPERIMENT"] = f"awrest_{self.name}"
        ad = A.Adapter()
        done = self.done()
        todo = [c for c in self.order if c["idx"] not in done]
        P.progress_log(self.name, self.phase, f"start: {len(done)} done, {len(todo)} to run, {self.workers} workers")
        (P.SCRATCH / "scratch").mkdir(parents=True, exist_ok=True)
        scratch = Path(tempfile.mkdtemp(prefix=f"{self.name}_", dir=P.SCRATCH / "scratch"))
        tasks = {}

        def one(c):
            if self.stop.is_set():
                return
            tid = c["task_id"]
            if tid not in tasks:
                tasks[tid] = A._task(tid, self.root)
            with P.Slot(f"{self.name}/{c['arm']}"):              # §7.3; waits while AW_STATE/PAUSE exists (R2)
                if self.stop.is_set():
                    return
                r = ad._episode(tasks[tid], self.caps[c["arm"]], seed=c["trial"], root=self.root, workdir=scratch,
                                random_seed=self.seed_base + c["trial"])
            m = r.metadata or {}
            rec = {"idx": c["idx"], "arm": c["arm"], "trial": c["trial"], "infra_error": r.error,
                   **{k: m.get(k) for k in KEEP}}
            P.atomic_write(self.records / f"{c['idx']}.json", json.dumps(rec))
            with self.lock:
                self.new += 1

        th = threading.Thread(target=lambda: list(ThreadPoolExecutor(self.workers).map(one, todo)), daemon=True)
        th.start()
        last = time.time()
        while th.is_alive():
            th.join(timeout=5)
            if time.time() - last >= self.coalesce_s:
                self.checkpoint()
                last = time.time()
        self.checkpoint(final_flush=True)
        shutil.rmtree(scratch, ignore_errors=True)
        return 0


def _own_pid(tag: str):
    pidf = P.AW_STATE / "RUNNING.pid"
    pidf.write_text(f"{os.getpid()} {tag}\n")
    return pidf


def final() -> int:
    """P7: the one common final window (168 test_normal × 6 arms × 2 trials = 2,016 cells)."""
    os.environ["AW_ALLOW_SEALED"] = "final-eval-only"
    os.environ["AW_APPWORLD_ROOT"] = str(P.ROOT_FULL)
    if (os.stat(P.ROOT_FULL).st_mode & 0o777) == 0:
        os.chmod(P.ROOT_FULL, 0o755)
        P.progress_log(FINAL_DIR, "P7", "root_full unlocked for the final window")
    ids = P.read_split("test_normal", P.ROOT_FULL)
    if len(ids) != 168:
        raise SystemExit("expected 168 test_normal ids")
    order = make_order(ids, list(WINDOW_ARMS), FINAL_TRIALS, FINAL_ORDER_SEED)
    m = P.manifest()
    if m.get("final_order", {}).get("sha256") not in (None, order_sha(order)):
        raise SystemExit("regenerated final order differs from the recorded sha256")
    P.write_json(P.AW_STATE / FINAL_DIR / "order.json", order)
    P.update_manifest(final_order={"seed": FINAL_ORDER_SEED, "sha256": order_sha(order), "cells": len(order),
                                   "trials": FINAL_TRIALS, "trial_seeds": "5000 + trial", "infra_retries": 3})
    caps = _check_frozen()
    pidf = _own_pid("window final")
    try:
        rc = Window(FINAL_DIR, "P7", "final window", order, caps, P.ROOT_FULL, P.FINAL_SEED_BASE, True,
                    P.global_slots(), 3, "P8/analysis").run()
    finally:
        pidf.unlink(missing_ok=True)
    done = len(list((P.AW_STATE / FINAL_DIR / "records").glob("*.json")))
    if done >= len(order):
        os.chmod(P.ROOT_FULL, 0o000)
        P.progress_log(FINAL_DIR, "P7", "final window complete; root_full relocked")
    return rc


if __name__ == "__main__":
    raise SystemExit({"freeze": freeze, "dev": dev, "final": final}[sys.argv[1]]())
