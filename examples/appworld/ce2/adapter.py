"""cap-evolve adapter of the CE2 arms (docs/EVAL_APPWORLD_CE2.md §7.2; REST's cape_improve adapter, REST §9.5, §7.2).

Copied into ``<project>/adapters/adapter.py`` by ``run_ce2.py setup``. The arm is ``AW_CAPE_ARM``. It is the shared AppWorld
adapter (``examples/appworld/adapters/adapter.py``: tasks = train ∪ dev for train and val, test = [], the
seal, F1 scoring) with ONE change: ``run_trials`` goes through the shared evaluator
(``common/evaluator.py``), so the tree-hash cache, the shared seed baseline (Q4: the seed's 147 records are
cache hits, 0 counted), the global slot pool, the PAUSE guard (R2) and the hard cap B = 900 apply to
cap-evolve exactly as to every other candidate.

The evaluator returns gold-free records; they are turned back into ``Rollout`` objects with the metadata
``score`` reads. ``AW_CAPE_PHASE`` selects the evaluator phase: ``search`` (counted, the default) or
``accept`` (acceptance dry runs, never counted). A lint-rejected candidate costs no episode; the evaluator
returns lint-reject records and ``score`` reports them (cap-evolve still counts them as metric calls, #877).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import importlib.util

EX = Path(os.environ.get("AW_EXAMPLE", "/workspace/worktrees/eval-ce2/examples/appworld"))
sys.path[:0] = [str(EX / "common"), str(EX / "scripts")]

from cap_evolve import Rollout  # noqa: E402

import evaluator as E  # noqa: E402  (imports awrest and calls setup_env(): AW_EVAL, AW_LINT_CACHE, ... first)


def _load_shared():
    """The shared adapter, loaded by path: this file is also called adapter.py and sits first on sys.path
    when cap-evolve loads it, so a plain ``import adapter`` would import this file again."""
    sys.path.insert(1, str(EX / "adapters"))           # its sibling ``lints`` module
    spec = importlib.util.spec_from_file_location("aw_shared_adapter", EX / "adapters" / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_shared = _load_shared()

CAND = os.environ.get("AW_CAPE_ARM", "")
if CAND not in E.P.CANDIDATES:
    raise RuntimeError(f"AW_CAPE_ARM must be one of {E.P.CANDIDATES}, not {CAND!r}")


def _phase() -> str:
    p = os.environ.get("AW_CAPE_PHASE", "search")
    if p not in ("search", "accept"):
        raise ValueError(f"AW_CAPE_PHASE must be search or accept, not {p!r}")
    return p


def _rollout(rec: dict, seed: int) -> Rollout:
    if rec.get("lint_reject"):
        viol = rec["feedback"].split(": ", 1)[-1].split("; ")
        return Rollout(task_id=rec["task_id"], output="lint_reject", trace=[],
                       metadata={"lint_reject": viol, "success": False, "cost_source": "unpriced"})
    if rec.get("error"):
        return Rollout(task_id=rec["task_id"], error=rec["error"],
                       metadata={"seed": seed, "cost_source": "unpriced", "infra_error": rec["error"]})
    meta = {k: rec.get(k) for k in E.RECORD_FIELDS}
    meta.update(seed=seed, cost_source="unpriced", cache_hit=bool(rec.get("cache_hit")))
    return Rollout(task_id=rec["task_id"], output=rec.get("termination"), trace=rec.get("steps") or [],
                   tokens=int(rec.get("prompt_tokens") or 0) + int(rec.get("completion_tokens") or 0),
                   cost_usd=0.0, metadata=meta)


class Adapter(_shared.Adapter):
    def run_trials(self, tasks, ctx, *, n_trials: int, base_seed: int):
        """All trials through the shared evaluator. Trial k uses seed 100 + k (the plan's search seed, Q1),
        whatever base_seed cap-evolve passes, so the cache key matches the shared seed baseline."""
        cdir = Path(ctx).resolve()
        tasks = list(tasks)
        self._check_seal([t.id for t in tasks])
        out: dict[str, list] = {t.id: [None] * n_trials for t in tasks}
        for k in range(n_trials):
            seed = 100 + k
            recs = E.evaluate(CAND, cdir, [t.id for t in tasks], phase=_phase(), tag=f"capevolve/t{k}", seed=seed)
            for t, rec in zip(tasks, recs):
                out[t.id][k] = _rollout(rec, seed)
        return out

    def run_target(self, task, ctx, *, seed: int = 0) -> Rollout:
        return self.run_trials([task], ctx, n_trials=1, base_seed=seed)[task.id][0]
