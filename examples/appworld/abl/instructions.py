"""The per-arm optimizer instructions of the ablations (docs/ABLATIONS.md §9.4, §10.3 to §10.6).

  python3 -I instructions.py render [--out DIR]     # INSTRUCTIONS.<arm>.md for the five cap-evolve arms + diffs

INSTRUCTIONS.base.md is a byte copy of abl-main's templates/project/optimizer/INSTRUCTIONS.md (sha256 in
VENDORED.md). Each arm's file inserts ONE section, ``## AppWorld facts for THIS run``, immediately before
``## PREPARATION:``. The reference's section is CE2's block (facts_ref.md, from ``**Objective score for this
run.**`` to the lint command, unchanged). An ablation arm replaces exactly the sentences its plan section names,
with the plan's text; each replaced span must occur exactly once, or rendering fails. The lint command's
``{AW_LINT_*}`` placeholders are filled by run_abl.py setup.
"""

from __future__ import annotations

import difflib
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE / "INSTRUCTIONS.base.md"
FACTS_REF = HERE / "facts_ref.md"
BASE_SHA256 = "84de4f00a5254c47f0627a9e753129375ce12d20ecdcbeeb0e266d6106de2fce"
ANCHOR = "## PREPARATION:"
CAPE_ARMS = ("abl_ref", "abl_prompt", "abl_tools", "abl_notrace", "abl_tracescore", "abl_nogate", "abl_naivegate")

# the reference's three-file bullet list (facts_ref.md), split by bullet so the surface arms can keep theirs
_B_POLICY_START = "- `policy/instructions.txt` — the ReAct prompt (capability system-prompt)."
_B_HELPERS_START = "- `tools/helpers.py` — plain Python functions (capability tools)"
_B_NOTES_START = "- `tools/api_notes.json` — "
_B_MEMORY = "- `memory/` is NOT part of this run: do not create or edit files there.\n"
_LIST_HEAD = "The candidate is three files; nothing else is read by the agent under test:\n"

_TRAJ_REF = ("`./trajectories/` holds one JSON per rollout: `input.instruction`, `rollout.trace` (per step:\n"
             "thought, reasoning excerpt, code, output truncated to 2,000 chars), `rollout.metadata`\n"
             "(termination, steps, tokens, failed requirement texts, collateral-damage flag) and\n"
             "`score.feedback`. A requirement text says WHAT the evaluator checked, never the gold value.\n")
_GATE_REF = "and accepts it only if the mean paired gain over the current best clears its noise gate."
_GATE_NOTE = ("The paragraph \"How your edit is judged\" further below describes the framework's default significance "
              "bar; it does not apply in this run")
_PARTIAL_REF = "Partial passes earn nothing; the failed-requirement texts in each trajectory say which checks failed."


def _bullets(facts: str) -> dict[str, str]:
    i0 = facts.index(_LIST_HEAD)
    p, h, n, m = (facts.index(s) for s in (_B_POLICY_START, _B_HELPERS_START, _B_NOTES_START, _B_MEMORY))
    assert i0 < p < h < n < m
    return {"head": _LIST_HEAD, "policy": facts[p:h], "helpers": facts[h:n], "notes": facts[n:m], "memory": _B_MEMORY,
            "list": facts[i0:m + len(_B_MEMORY)]}


def _once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"instructions: expected exactly one occurrence of {old[:70]!r}, found {text.count(old)}")
    return text.replace(old, new)


def facts_for(arm: str) -> str:
    f = FACTS_REF.read_text(encoding="utf-8")
    b = _bullets(f)
    if arm == "abl_ref":
        return f
    if arm == "abl_prompt":       # §10.3
        new = ("The candidate you may edit is ONE file, `policy/instructions.txt` (capability system-prompt):\n"
               + b["policy"]
               + "In this run `tools/` and `memory/` are read-only: a candidate that changes, adds or removes any file\n"
               "under them is voided before it is run. The agent's REPL helpers and API notes stay as they are.\n")
        return _once(f, b["list"], new)
    if arm == "abl_tools":        # §10.4
        new = (b["head"] + b["helpers"] + b["notes"]
               + "In this run `policy/instructions.txt` and `memory/` are read-only: a candidate that changes, adds or\n"
               "removes any file under them is voided before it is run. All your changes go into the tools. A helper\n"
               "may not return fixed procedure or checklist text (more than 200 characters of literal text): the lint\n"
               "rejects it.\n")
        return _once(f, b["list"], new)
    if arm == "abl_notrace":      # §10.5
        return _once(f, _TRAJ_REF,
                     "`./trajectories/` holds one JSON per rollout with NO conversation: `input.instruction`,\n"
                     "`rollout.metadata` (termination, steps, tokens, failed requirement texts, collateral-damage flag)\n"
                     "and `score.feedback`. `rollout.trace` is empty: this run does not show you what the agent did,\n"
                     "only how each task was graded. A requirement text says WHAT the evaluator checked, never the gold\n"
                     "value.\n")
    if arm == "abl_tracescore":   # §10.6
        f = _once(f, _PARTIAL_REF, "Partial passes earn nothing. In this run you are NOT told which checks failed: "
                                   "each rollout carries only its reward.")
        return _once(f, _TRAJ_REF,
                     "`./trajectories/` holds one JSON per rollout: `input.instruction`, `rollout.trace` (per step:\n"
                     "thought, reasoning excerpt, code, output truncated to 2,000 chars), `rollout.metadata`\n"
                     "(termination, steps, tokens) and `score.feedback`, which is only `Task reward: 0` or\n"
                     "`Task reward: 1`. Infer why a run lost reward from the conversation itself.\n")
    if arm == "abl_nogate":       # ABLATIONS_GATE.md G4: only the gate clause changes
        return _once(f, _GATE_REF,
                     "and in this run keeps every candidate that is scored: there is no acceptance gate, so the "
                     "candidate you ship becomes the new current best whatever its score, even if it is lower. A "
                     "candidate that fails the lint is not run and not kept. " + _GATE_NOTE + ".")
    if arm == "abl_naivegate":    # ABLATIONS_GATE.md G4
        return _once(f, _GATE_REF,
                     "and keeps it if its mean paired gain over the current best is above zero: any net gain, however "
                     "small, is kept, with no noise margin. " + _GATE_NOTE + ", where the bar is zero.")
    raise SystemExit(f"instructions: no instructions for arm {arm!r}")


def render(arm: str) -> str:
    base = BASE.read_text(encoding="utf-8")
    if hashlib.sha256(base.encode()).hexdigest() != BASE_SHA256:
        raise SystemExit("instructions: INSTRUCTIONS.base.md is not the vendored template")
    i = base.index(ANCHOR)
    if base.count(ANCHOR) != 1:
        raise SystemExit("instructions: the anchor ## PREPARATION: must occur once")
    return base[:i] + facts_for(arm) + base[i:]


def udiff(a: str, b: str, la: str, lb: str) -> str:
    return "".join(difflib.unified_diff(a.splitlines(True), b.splitlines(True), la, lb))


def main() -> int:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else HERE
    base = BASE.read_text(encoding="utf-8")
    ref = render("abl_ref")
    for arm in CAPE_ARMS:
        t = render(arm)
        (out / f"INSTRUCTIONS.{arm}.md").write_text(t, encoding="utf-8")
        (out / f"instructions_{arm}.diff").write_text(udiff(base, t, "INSTRUCTIONS.base.md", f"INSTRUCTIONS.{arm}.md"))
        if arm != "abl_ref":
            (out / f"instructions_ref_vs_{arm}.diff").write_text(
                udiff(ref, t, "INSTRUCTIONS.abl_ref.md", f"INSTRUCTIONS.{arm}.md"))
        print(arm, hashlib.sha256(t.encode()).hexdigest()[:12])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
