"""Offline tests of the ablations' feedback filter (docs/ABLATIONS.md §9.7) on synthetic records only.

For each mode: the filtered rollout + score have exactly the §9.7 fields, no string of a removed field survives
in the serialized object, reward and metrics equal the reference's, and ``full`` is byte-identical to the shared
(CE2) adapter output, scored by the real shared ``Adapter.score``. Run in venv-abl. No task file or model call.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ABL = Path(__file__).resolve().parents[1]
EX = ABL.parent
sys.path[:0] = [str(ABL), str(EX / "adapters")]


from cap_evolve import Rollout, Score, Task  # noqa: E402  (venv-abl: the code under test, 75b3bcd)


def _shared():
    import importlib.util
    spec = importlib.util.spec_from_file_location("aw_shared_adapter", EX / "adapters" / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Adapter.__new__(mod.Adapter)     # score() uses no instance state


SHARED = _shared()
TASK = Task(id="synth_1", input={"instruction": "SYNTH_INSTRUCTION", "supervisor": {}})


REQ = "SYNTH_REQUIREMENT_TEXT the playlist must contain the requested items"
STEP = {"thought": "SYNTH_THOUGHT", "reasoning": "SYNTH_REASONING", "code": "print(SYNTH_CODE)",
        "output": "SYNTH_OUTPUT"}


def meta(success: bool) -> dict:
    return {"success": success, "num_tests": 4, "pass_count": 4 if success else 2,
            "failed_requirements": [] if success else [REQ], "collateral_damage": not success,
            "complete_task_called": True, "termination": "completed", "n_steps": 3, "prompt_tokens": 1200,
            "completion_tokens": 300, "max_prompt_tokens": 600, "api_errors": 1, "fs_probe": False,
            "episode_seconds": 12.0, "trimmed_steps": 0, "seed": 100, "cost_source": "unpriced",
            "cache_hit": False}


def rollout(success: bool) -> Rollout:
    return Rollout(task_id="synth_1", output="completed", trace=[dict(STEP), dict(STEP)], tokens=1500,
                   metadata=meta(success))


def ce2_score(r: Rollout) -> Score:
    """The shared (CE2 / reference) adapter's F1 score of a rollout."""
    return SHARED.score(TASK, r)


def load(mode: str):
    os.environ["AW_ABL_FEEDBACK"] = mode
    import feedback_filter
    return importlib.reload(feedback_filter)


def visible(F, success: bool) -> tuple[Rollout, Score, str]:
    r = F.filter_rollout(rollout(success))
    s = F.filter_score(ce2_score(r), r)
    return r, s, json.dumps({"rollout": r.to_dict(), "score": s.to_dict()}, sort_keys=True, default=str)


class FilterTest(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("AW_ABL_FEEDBACK", None)

    def test_unknown_value_raises_at_import(self):
        r = subprocess.run([sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(ABL)!r}); "
                            "import feedback_filter"], env={**os.environ, "AW_ABL_FEEDBACK": "evalonly"},
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("AW_ABL_FEEDBACK must be one of", r.stderr)

    def test_unset_means_full(self):
        os.environ.pop("AW_ABL_FEEDBACK", None)
        import feedback_filter
        self.assertEqual(importlib.reload(feedback_filter).MODE, "full")

    def test_full_is_byte_identical(self):
        F = load("full")
        for ok in (True, False):
            r0 = rollout(ok)
            ref = json.dumps({"rollout": r0.to_dict(), "score": ce2_score(r0).to_dict()}, sort_keys=True, default=str)
            self.assertEqual(visible(F, ok)[2], ref)
            self.assertIs(F.filter_rollout(r0), r0)

    def test_eval_only(self):
        F = load("eval_only")
        for ok in (True, False):
            r, s, txt = visible(F, ok)
            ref = ce2_score(rollout(ok))
            self.assertEqual(r.trace, [])
            self.assertEqual(r.output, "completed")
            self.assertEqual(r.metadata, meta(ok))                    # all F1 fields
            self.assertEqual((s.reward, s.metrics, s.feedback, s.raw), (ref.reward, ref.metrics, ref.feedback, ref.raw))
            for t in ("SYNTH_THOUGHT", "SYNTH_REASONING", "SYNTH_CODE", "SYNTH_OUTPUT"):
                self.assertNotIn(t, txt)
            self.assertEqual(REQ in txt, not ok)                      # failed requirements stay

    def test_trace_score(self):
        F = load("trace_score")
        for ok in (True, False):
            r, s, txt = visible(F, ok)
            ref = ce2_score(rollout(ok))
            self.assertEqual(r.trace, rollout(ok).trace)
            self.assertEqual(set(r.metadata), set(F.TRACE_SCORE_KEEP))
            self.assertEqual(s.feedback, f"Task reward: {int(ref.reward)}")
            self.assertEqual(s.raw, {})
            self.assertEqual((s.reward, s.metrics), (ref.reward, ref.metrics))
            for k in F.REMOVED_IN_TRACE_SCORE + ("requirement checks", "Failed requirements", "SYNTH_REQUIREMENT"):
                self.assertNotIn(k, txt)
            self.assertIn("SYNTH_THOUGHT", txt)

    def test_lint_reject_and_error_keep_their_text(self):
        for mode in ("eval_only", "trace_score"):
            F = load(mode)
            lr = Rollout(task_id="synth_1", output="lint_reject", trace=[], metadata={"lint_reject": ["helpers: bad import"],
                                                                              "success": False})
            self.assertIn("helpers: bad import", F.filter_score(ce2_score(lr), F.filter_rollout(lr)).feedback)
            er = Rollout(task_id="synth_1", error="infrastructure: timeout", metadata={"seed": 100})
            self.assertIn("not measured", F.filter_score(ce2_score(er), F.filter_rollout(er)).feedback)

    def test_input_not_mutated(self):
        for mode in ("eval_only", "trace_score"):
            F = load(mode)
            r0 = rollout(False)
            F.filter_rollout(r0)
            self.assertEqual(r0.to_dict(), rollout(False).to_dict())

if __name__ == "__main__":
    unittest.main()
