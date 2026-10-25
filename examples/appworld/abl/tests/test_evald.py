"""Offline tests of the abl_cc eval daemon's request checks (docs/ABLATIONS.md §10.2, A-ABL-CC): paths outside the
working directory, symlinks out, extra arguments and malformed requests are refused before any evaluation. No
episode runs; AW_STATE is a temporary directory. Run in venv-abl after sourcing abl/env.sh."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ABL = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix="evald_test_"))
os.environ["AW_STATE"] = str(TMP / "state")
sys.path.insert(0, str(ABL / "cc"))
import evald  # noqa: E402


def workdir() -> Path:
    w = Path(tempfile.mkdtemp(dir=TMP))
    (w / "cand" / "policy").mkdir(parents=True)
    (w / "cand" / "tools").mkdir()
    (w / "cand" / "policy" / "instructions.txt").write_text("USER: x")
    (w / ".eval" / "requests").mkdir(parents=True)
    return w


def request(w: Path, body) -> Path:
    p = w / ".eval" / "requests" / f"t{len(list((w / '.eval' / 'requests').iterdir()))}.json"
    p.write_text(body if isinstance(body, str) else json.dumps(body))
    return p


class EvaldTest(unittest.TestCase):
    def refused(self, w: Path, body) -> str:
        log = evald.handle(w, request(w, body))
        self.assertEqual(log["state"], "refused", log)
        s = json.loads((w / ".eval" / "results" / log["ticket"] / "summary.json").read_text())
        self.assertIn("refused", s)
        return log["reason"]

    def test_outside_paths_refused(self):
        w = workdir()
        self.assertIn("relative", self.refused(w, {"dir": "/etc"}))
        self.assertIn("..", self.refused(w, {"dir": "../x"}))
        self.assertIn("..", self.refused(w, {"dir": "cand/../.."}))
        self.assertIn("not a directory", self.refused(w, {"dir": "nope"}))

    def test_symlinks_refused(self):
        w = workdir()
        (w / "out").symlink_to("/tmp")
        self.assertIn("symlink", self.refused(w, {"dir": "out"}))
        (w / "cand" / "tools" / "helpers.py").symlink_to("/etc/hostname")
        self.assertIn("symlink", self.refused(w, {"dir": "cand"}))

    def test_extra_arguments_and_bad_json_refused(self):
        w = workdir()
        self.assertIn("exactly", self.refused(w, {"dir": "cand", "task_ids": ["x"]}))
        self.assertIn("exactly", self.refused(w, {"dir": "cand", "phase": "P5"}))
        self.assertIn("JSON", self.refused(w, "not json"))
        self.assertIn("exactly", self.refused(w, ["cand"]))

    def test_missing_prompt_refused(self):
        w = workdir()
        (w / "cand" / "policy" / "instructions.txt").unlink()
        self.assertIn("missing", self.refused(w, {"dir": "cand"}))

    def test_request_is_consumed_and_logged(self):
        w = workdir()
        p = request(w, {"dir": "/"})
        evald.handle(w, p)
        self.assertFalse(p.exists())
        self.assertTrue(p.with_suffix(".taken").exists())
        self.assertTrue(any(e["state"] == "refused" for e in evald.P.read_jsonl(evald.STATE / "evals.jsonl")))


if __name__ == "__main__":
    unittest.main()
