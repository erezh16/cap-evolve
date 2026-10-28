"""B3 (docs/TEST_ALL.md §6.2): the shared lint on every scored copy. Run in venv-aw (jinja2, tiktoken):

  . examples/appworld/test_all/env.sh && $VENV_AW/bin/python -I examples/appworld/test_all/lint_arms.py

A trusted script. Prints per arm the number of violations and each violation's text cut before any quoted example
(an 8-gram example would be train/dev instruction text, which is never printed or published). Also records the
surface sizes (chars, lines, o200k tokens of the memory) that §6.2 quotes. Writes AW_STATE/final/lint.json and
manifest.json `lint`. Exit 0 iff every arm passes except the disclosed ACE memory-size exception (D6).
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "scripts"))
sys.path.insert(0, str(EX / "adapters"))
import awrest as P  # noqa: E402

P.setup_env()
os.environ["AW_LINT_CACHE"] = str(P.LINT_CACHE)
import lints  # noqa: E402

ART = P.AW_STATE / "final" / "artifacts"
ACE_EXCEPTION = re.compile(r"^memory/playbook\.md: \d+ chars > 30000$")


def safe(v: str) -> str:
    return re.split(r", e\.g\. |\(\d+ hit", v)[0].strip()


def sizes(d: Path) -> dict:
    out = {}
    for rel in ("policy/instructions.txt", "tools/helpers.py", "tools/api_notes.json", "memory/playbook.md"):
        p = d / rel
        if p.is_file():
            t = p.read_text(encoding="utf-8")
            out[rel] = {"chars": len(t), "lines": len(t.splitlines()), "tokens_o200k": lints._tokens(t)}
    rj = d / "memory" / "retrieval.json"
    if rj.is_file():
        blocks = json.loads(rj.read_text(encoding="utf-8"))
        out["memory/retrieval.json"] = {"keys": len(blocks), "max_block_chars": max((len(b) for b in blocks.values()),
                                                                                  default=0)}
    return out


def main() -> int:
    res, ok = {}, True
    arms = tuple(P.WINDOW_ARMS) if getattr(P, "TESTABL", False) else tuple(P.ARMS)
    for arm in arms:
        v = [safe(x) for x in lints.lint_candidate(ART / arm)]
        exc = [x for x in v if arm == "ace" and ACE_EXCEPTION.match(x)]   # TEST_ALL D6 only; none in TEST_ABL
        other = [x for x in v if x not in exc]
        res[arm] = {"violations": v, "disclosed_exception": exc, "pass": not other, "sizes": sizes(ART / arm)}
        ok &= not other
        print(json.dumps({"arm": arm, "n_violations": len(v), "violations": v, "pass_except_D6": not other}))
    P.write_json(P.AW_STATE / "final" / ("lint_w2.json" if getattr(P, "WINDOW", "1") == "2" else "lint.json"), res)
    P.update_manifest(lint=(P.manifest().get("lint") or {}) | {a: {"pass": r["pass"], "violations": r["violations"],
                                "disclosed_exception": r["disclosed_exception"], "sizes": r["sizes"]}
                            for a, r in res.items()})
    print(json.dumps({"all_pass_except_D6": ok}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
