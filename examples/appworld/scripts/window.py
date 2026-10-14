"""Scoring windows: the dev diagnostic (P6), the final window (P8) and A10's mini window (plan §8.5, §10, §12).

A window is a list of cells (arm, task, trial) in one random order fixed by a recorded seed. Each cell
is one episode (adapter.run_episode) whose record is written atomically to <records>/<idx>.json; a
cell with a record (or, for dev, a pushed row) is never re-run. Results are checkpointed coalesced, at
most one ledger entry per `coalesce_s` (5 min). SIGTERM: running cells finish, no new cell starts.
"""

from __future__ import annotations

import csv
import io
import json
import os
import random
import signal
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "adapters"))
import awpaths as P  # noqa: E402
import adapter  # noqa: E402


def make_order(task_ids: list[str], arms: list[str], trials: int, seed: int) -> list[dict]:
    cells = [{"arm": a, "task_id": t, "trial": k} for t in task_ids for a in arms for k in range(trials)]
    random.Random(seed).shuffle(cells)
    for i, c in enumerate(cells):
        c["idx"] = i
    return cells


def order_sha(order: list[dict]) -> str:
    return P.sha256_bytes(json.dumps(order, sort_keys=True).encode())


class Window:
    def __init__(self, name: str, phase: str, label: str, order: list[dict], caps: dict[str, Path],
                 records: Path, seed_base: int, final: bool, workers: int, max_infra_retries: int,
                 coalesce_s: int = 300, pushed_rows_csv: Path | None = None, pushed_counts: Path | None = None,
                 ledger: bool = True, next_unit_done: str = "", trial_name: str | None = None):
        self.__dict__.update(locals())
        self.records.mkdir(parents=True, exist_ok=True)
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.new_done: list[int] = []
        self.trial_name = trial_name or name

    # -------------------------------------------------- done cells
    def pushed_rows(self) -> dict[int, dict]:
        if not self.pushed_rows_csv or not self.pushed_rows_csv.exists():
            return {}
        return {int(r["idx"]): r for r in csv.DictReader(io.StringIO(self.pushed_rows_csv.read_text()))}

    def done(self) -> dict[int, dict]:
        out = {}
        for p in self.records.glob("*.json"):
            try:
                out[int(p.stem)] = json.loads(p.read_text())
            except (ValueError, json.JSONDecodeError):
                p.unlink()  # torn record (cannot happen with atomic writes; defensive)
        return out

    # -------------------------------------------------- pushed state
    def row(self, c: dict, rec: dict) -> dict:
        return {"idx": c["idx"], "arm": c["arm"], "reward": adapter.score(rec), "steps": rec.get("steps"),
                "prompt_tokens_max": rec.get("prompt_tokens_max"), "completion_tokens": rec.get("completion_tokens"),
                "termination": rec.get("termination"), "infra_error": bool(rec.get("infra_error")),
                "infra_retries": rec.get("infra_retries", 0)}

    def write_pushed(self, done: dict[int, dict]) -> list[str]:
        arts = []
        if self.pushed_rows_csv:
            pushed = self.pushed_rows()
            rows = {**{i: r for i, r in pushed.items()}, **{i: self.row(self.order[i], rec) for i, rec in done.items()}}
            buf = io.StringIO()
            cols = ["idx", "arm", "reward", "steps", "prompt_tokens_max", "completion_tokens", "termination",
                    "infra_error", "infra_retries"]
            w = csv.DictWriter(buf, fieldnames=cols)
            w.writeheader()
            for i in sorted(rows):
                w.writerow({k: rows[i].get(k) for k in cols})
            P.atomic_write(self.pushed_rows_csv, buf.getvalue())
            arts.append("STATE/" + str(self.pushed_rows_csv.relative_to(P.PUSHED)))
        if self.pushed_counts:
            per_arm = {}
            for i, rec in done.items():
                a = self.order[i]["arm"]
                d = per_arm.setdefault(a, {"done": 0, "infra_retries": 0, "infra_missing": 0})
                d["done"] += 1
                d["infra_retries"] += rec.get("infra_retries", 0)
                d["infra_missing"] += int(bool(rec.get("infra_error")))
            P.write_json(self.pushed_counts, {"window": self.name, "cells_total": len(self.order),
                                              "cells_done": len(done), "per_arm": per_arm,
                                              "order_sha256": order_sha(self.order)})
            arts.append("STATE/" + str(self.pushed_counts.relative_to(P.PUSHED)))
        return arts

    def checkpoint(self, final_flush: bool = False) -> None:
        with self.lock:
            batch, self.new_done = sorted(self.new_done), []
        if not batch and not final_flush:
            return
        done = self.done()
        arts = self.write_pushed(done)
        n = len(done) + len(set(self.pushed_rows()) - set(done))
        P.progress_log(self.trial_name, self.phase, f"{self.name} {n}/{len(self.order)} cells")
        if not self.ledger:
            return
        import status_doc
        per_arm = {}
        for i in done:
            per_arm[self.order[i]["arm"]] = per_arm.get(self.order[i]["arm"], 0) + 1
        infra = sum(r.get("infra_retries", 0) for r in done.values())
        missing = sum(1 for r in done.values() if r.get("infra_error"))
        ctx = sum(1 for r in done.values() if r.get("termination") == "context_exceeded")
        rng = f"{batch[0] + 1}–{batch[-1] + 1}" if batch else "none new"
        complete = n >= len(self.order)
        prose = (f"{self.label}: {len(batch)} cells done since the last entry (order positions {rng}); "
                 f"{n}/{len(self.order)} done ({', '.join(f'{a} {v}' for a, v in sorted(per_arm.items()))}); "
                 f"infra retries {infra}, cells still infra-failed {missing}, context_exceeded {ctx}.\n"
                 f"Next: {self.next_unit_done if complete else f'{self.name} remaining cells'}.")
        status_doc.append("phase_done" if complete else "result", self.phase, self.label, prose,
                          done_through=f"{self.name}/{n}", next_unit=self.next_unit_done if complete else f"{self.name}/cells",
                          extra={"window": {"name": self.name, "done": n, "total": len(self.order),
                                            "order_sha256": order_sha(self.order)}},
                          artifacts=arts, subject=f"{self.name} {n}/{len(self.order)}")

    # -------------------------------------------------- run
    def _spec(self, c: dict) -> dict:
        return adapter.episode_spec(c["task_id"], f"{self.name}/{c['arm']}/{c['task_id']}/t{c['trial']}",
                                    self.caps[c["arm"]], self.seed_base + c["trial"], final=self.final)

    def run(self) -> int:
        signal.signal(signal.SIGTERM, lambda *_: self.stop.set())
        done = self.done()
        pushed = self.pushed_rows()
        todo = [c for c in self.order if c["idx"] not in done and c["idx"] not in pushed]
        P.progress_log(self.trial_name, self.phase, f"{self.name} start: {len(self.order) - len(todo)} done, "
                                                     f"{len(todo)} to run")
        items = [(self._spec(c), self.records / f"{c['idx']}.json") for c in todo]

        def on_done(k, rec):
            with self.lock:
                self.new_done.append(todo[k]["idx"])

        th = threading.Thread(target=adapter.run_episodes, args=(items,),
                              kwargs={"workers": self.workers, "max_infra_retries": self.max_infra_retries,
                                      "on_done": on_done, "stop_event": self.stop}, daemon=True)
        th.start()
        last = time.time()
        while th.is_alive():
            th.join(timeout=5)
            if time.time() - last >= self.coalesce_s:
                self.checkpoint()
                last = time.time()
        self.checkpoint(final_flush=True)
        return 0
