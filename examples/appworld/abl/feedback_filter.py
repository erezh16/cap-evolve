"""The ablations' proposer-feedback filter (docs/ABLATIONS.md §9.7), selected by ``AW_ABL_FEEDBACK``.

A pure function of the adapter's ``Rollout`` and ``Score``. cap-evolve builds every file it shows the optimizer
(``./trajectories/``, ``{{FAILURES}}``, ``baseline.json``, ``state.json``, LEDGER, JOURNAL, rejected reasons) from
these two objects, so filtering them here filters all of those. The evaluator's own records in ``AW_STATE`` stay
complete; the optimizer cannot read them (§11).

  full         (default; abl_ref, abl_prompt, abl_tools)   everything as the shared adapter returns it
  eval_only    (abl_notrace)       ``Rollout.trace`` = [], output = termination; metadata and feedback unchanged
  trace_score  (abl_tracescore)    trace kept; metadata only TRACE_SCORE_KEEP; feedback ``Task reward: 0|1``, raw {}

``reward`` and ``Score.metrics`` are never changed, so the gate sees exactly what it sees in the reference. A
lint-reject or not-measured rollout keeps its text in every mode (the lint's own output, not evaluation feedback).
An unknown value raises at import.
"""

from __future__ import annotations

import copy
import os

MODES = ("full", "eval_only", "trace_score")
MODE = os.environ.get("AW_ABL_FEEDBACK", "full")
if MODE not in MODES:
    raise RuntimeError(f"AW_ABL_FEEDBACK must be one of {MODES}, not {MODE!r}")

# §9.7: readable from the trace or bookkeeping; every evaluation field is left out
TRACE_SCORE_KEEP = ("termination", "n_steps", "complete_task_called", "api_errors", "prompt_tokens",
                    "completion_tokens", "max_prompt_tokens", "success", "seed", "cost_source", "cache_hit")
REMOVED_IN_TRACE_SCORE = ("failed_requirements", "pass_count", "num_tests", "collateral_damage")


def _passthrough(rollout) -> bool:
    m = rollout.metadata or {}
    return bool(rollout.error) or bool(m.get("lint_reject"))


def filter_rollout(rollout, mode: str = MODE):
    """A filtered copy of ``rollout``; the input is not changed."""
    if mode == "full" or _passthrough(rollout):
        return rollout
    r = copy.deepcopy(rollout)
    if mode == "eval_only":
        r.trace = []
        r.output = (r.metadata or {}).get("termination", r.output)
    elif mode == "trace_score":
        r.metadata = {k: v for k, v in (r.metadata or {}).items() if k in TRACE_SCORE_KEEP}
    return r


def filter_score(score, rollout, mode: str = MODE):
    """The proposer-visible Score: same reward and metrics, filtered feedback and raw."""
    if mode != "trace_score" or _passthrough(rollout) or (score.raw or {}).get("errored"):
        return score
    s = copy.deepcopy(score)
    s.feedback = f"Task reward: {int(round(score.reward))}"
    s.raw = {}
    return s
