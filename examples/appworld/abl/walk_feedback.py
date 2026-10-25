"""A-ABL feedback walk (docs/ABLATIONS.md §10.5, §10.6): walk a run dir (incl. every work/<cid>) and print COUNTS only.

  python -I walk_feedback.py RUN_DIR

Counts, over every rollout JSON ({"input", "rollout", "score"}) and every other text file: non-empty `trace` arrays,
step keys thought/code/reasoning, failed-requirement fields (failed_requirements, pass_count, num_tests,
collateral_damage) and the evaluation phrases "requirement checks" / "Failed requirements". Nothing else is printed.
"""

import json
import sys
from pathlib import Path

FIELDS = ("failed_requirements", "pass_count", "num_tests", "collateral_damage")
PHRASES = ("requirement checks", "Failed requirements")


def walk(root: Path) -> dict:
    c = {"rollout_files": 0, "nonempty_traces": 0, "step_keys_thought_code_reasoning": 0, "lint_reject_rollouts": 0,
         "failing_rollouts": 0, "failing_with_failed_requirements": 0, "eval_field_occurrences": 0,
         "eval_phrase_occurrences": 0, "text_files": 0}
    for p in root.rglob("*"):
        if not p.is_file() or p.stat().st_size > 50_000_000:
            continue
        t = p.read_text(encoding="utf-8", errors="ignore")
        c["text_files"] += 1
        c["eval_phrase_occurrences"] += sum(t.count(x) for x in PHRASES)
        c["eval_field_occurrences"] += sum(t.count(f'"{x}"') for x in FIELDS)
        if p.suffix != ".json":
            continue
        try:
            d = json.loads(t)
        except ValueError:
            continue
        if not (isinstance(d, dict) and {"rollout", "score"} <= set(d)):
            continue
        c["rollout_files"] += 1
        r = d["rollout"] or {}
        m = r.get("metadata") or {}
        if m.get("lint_reject"):
            c["lint_reject_rollouts"] += 1
            continue
        tr = r.get("trace") or []
        c["nonempty_traces"] += bool(tr)
        c["step_keys_thought_code_reasoning"] += sum(1 for s in tr if isinstance(s, dict)
                                                     for k in ("thought", "code", "reasoning") if k in s)
        if (d["score"] or {}).get("reward", 1) < 1:
            c["failing_rollouts"] += 1
            c["failing_with_failed_requirements"] += "failed_requirements" in m
    return c


if __name__ == "__main__":
    print(json.dumps(walk(Path(sys.argv[1]))))
