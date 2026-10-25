"""Offline tests of the tools-only anti-smuggling lint (docs/ABLATIONS.md §10.4). Synthetic helpers only."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

EX = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EX / "adapters"))
import lints  # noqa: E402

# synthetic lint data: the test never reads the real lint cache or any task file
lints.lint_data = lambda: {"apps": {"spotify"}, "api_names": {"show_playlist"}, "grams": set(), "contacts": []}

LONG = "Step one: check the account. " * 12          # 348 characters of fixed text


class SmugglingLintTest(unittest.TestCase):
    def check(self, src: str) -> list[str]:
        return lints.lint_tools_smuggling(src)

    def test_literal_return_rejected(self):
        self.assertTrue(self.check(f"def get_procedure():\n    return {LONG!r}\n"))

    def test_fstring_join_concat_and_constant_rejected(self):
        self.assertTrue(self.check(f"def p(x):\n    return f'{{x}} {LONG}'\n"))
        self.assertTrue(self.check(f"def p():\n    return '\\n'.join([{LONG[:180]!r}, {LONG[:180]!r}])\n"))
        self.assertTrue(self.check(f"def p():\n    return {LONG[:150]!r} + {LONG[:150]!r}\n"))
        self.assertTrue(self.check(f"STEPS = {LONG!r}\n\ndef p():\n    return STEPS\n"))
        self.assertTrue(self.check(f"def p():\n    s = {LONG!r}\n    return s\n"))

    def test_normal_helpers_and_docstrings_pass(self):
        ok = (f'def paged(apis, app, api, **kw):\n    """{LONG}"""\n    out, page = [], 0\n'
              "    while True:\n        r = getattr(getattr(apis, app), api)(page_index=page, **kw)\n"
              "        if not r:\n            return out\n        out += r\n        page += 1\n\n"
              "def fmt(x):\n    return f'value: {x}'\n")
        self.assertEqual(self.check(ok), [])

    def test_threshold(self):
        self.assertEqual(self.check(f"def p():\n    return {'a' * 200!r}\n"), [])
        self.assertTrue(self.check(f"def p():\n    return {'a' * 201!r}\n"))

    def test_off_unless_switch(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "tools").mkdir()
            (Path(d) / "tools" / "helpers.py").write_text(f"def p():\n    return {LONG!r}\n")
            os.environ.pop("AW_ABL_TOOLS_LINT", None)
            src = (Path(d) / "tools" / "helpers.py").read_text()
            self.assertFalse(any("fixed literal text" in v for v in lints.lint_helpers(src)))
            os.environ["AW_ABL_TOOLS_LINT"] = "1"
            try:
                hit = [v for v in lints.lint_candidate(Path(d)) if "fixed literal text" in v]
            finally:
                os.environ.pop("AW_ABL_TOOLS_LINT")
            self.assertEqual(len(hit), 1)


if __name__ == "__main__":
    unittest.main()
