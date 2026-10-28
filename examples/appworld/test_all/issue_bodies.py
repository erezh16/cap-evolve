#!/usr/bin/env python3
"""§12.1 (docs/TEST_ALL.md): the first post of each of the 13 tracking issues, the plan projected for that arm.

  . examples/appworld/test_all/env.sh && python3 -I examples/appworld/test_all/issue_bodies.py [--out DIR]

Built from the plan file, never by hand: (1) a header; (2) this arm's own section (its row of §3, the surfaces
it changed as measured at fetch, what the artifact is and is not, and what the plan says about it in particular);
(3) the common sections §0, §1, §3, §4, §5, §6, §8, §9, §11, §12, §13, §14, §15, §16, verbatim. A body over
GitHub's 65,536-character limit has its common sections other than §0 and §3 replaced by pointers to the plan
file. Every body passes the content filter (status_doc.violations). Writes <out>/<arm>.md and prints sizes only.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "scripts"))
import awrest as P  # noqa: E402
import status_doc as S  # noqa: E402

PLAN = P.REPO / "docs" / getattr(P, "PLAN_NAME", "TEST_ALL.md")
COMMON = ("0", "1", "3", "4", "5", "6", "8", "9", "11", "12", "13", "14", "15", "16")
KEEP_FULL = ("0", "3")
LIMIT = 65536
PLAN_URL = "https://github.com/erezh16/cap-evolve/blob/cap-evolve-impr2/docs/TEST_ALL.md"
LEDGER_URL = "https://github.com/erezh16/cap-evolve/blob/test-all/docs/TEST_ALL_STATUS.md"
if getattr(P, "TESTABL", False):          # TEST_ABL: the plan and the ledger both live on branch test-abl
    PLAN_URL = "https://github.com/erezh16/cap-evolve/blob/test-abl/docs/TEST_ABL.md"
    LEDGER_URL = "https://github.com/erezh16/cap-evolve/blob/test-abl/docs/TEST_ABL_STATUS.md"

PARTICULAR = {
    "seed": "The **baseline** every Δ of this evaluation is measured against: AppWorld's official simplified ReAct code "
            "agent with its stock prompt, no helpers, no API notes and no memory. Its first request is byte-identical "
            "to stock (checked in T4). It also ranks among the 13 arms like any other artifact.",
    "harnesslens": "**Inert.** HarnessLens's search in REST accepted no edit, so its frozen artifact equals the seed "
                   "byte for byte (verified file by file at fetch, §6.1 step 5). It is a second copy of the seed arm "
                   "in the same window, so `harnesslens − seed` is a direct measure of the window's noise (§11.2). "
                   "Its result says nothing about HarnessLens as a method beyond \"its search found nothing to accept\".",
    "altk": "**Per-task retrieval memory.** The artifact keeps the stock prompt, helpers and notes and adds "
            "`memory/retrieval.json`: one memory block per test task, keyed by task id (168 keys; the largest block is "
            "10,781 characters), selected by ALTK-Evolve's own retrieval at its smoke-test dose. The common surface hash "
            "(rule S) ignores `retrieval.json`, so it equals the seed's: the window therefore never looks artifacts up "
            "by surface hash and runs every cell directly through the episode runner, identifying arms by directory "
            "and per-arm hash (§6.3, D7). T4 checks that its memory block reaches the prompt.",
    "ace": "**Memory-lint exception (D6).** ACE's playbook is 55,513 characters / 13,430 tokens, over the shared lint's "
           "30,000-character memory limit. ACE's own evaluation capped memory by tokens (13,500) and scored it with its "
           "own token-based lint. It is scored here **as frozen**, not truncated or edited, and the exception is "
           "disclosed. Any `context_exceeded` episode scores 0 and is counted for this arm.",
    "cape_k02": "**The only cap-evolve arm (D3).** cap-evolve \"Improvement 2\" at commit `3db96a0`, hill-climb with "
                "gate K = 0.2, trained in CE3 (2026-10-24). cap-evolve's other trained artifacts (the smoke test's "
                "`cape-hc`, REST's `cape_improve` at K = 0.5, CE2's K = 1 and K = 2) are excluded on purpose.",
}


if getattr(P, "TESTABL", False):
    PARTICULAR = {
        "seed": "The **baseline**: AppWorld's official simplified ReAct code agent with its stock prompt, no helpers, no "
                "API notes and no memory. Every ablation arm started its search from it. Its first request is "
                "byte-identical to stock (checked in T4). Every arm − seed Δ is a secondary contrast (§11).",
        "abl_ref": "**The reference.** Full cap-evolve (`main` `75b3bcd`, hill-climb, paired gate K = 0.2), with nothing "
                   "ablated. The primary contrasts of this evaluation are each ablation arm − `abl_ref` (§11, D12).",
        "abl_cc_best": "**Plain Claude Code, secondary artifact.** The `abl_cc` arm was one plain Claude Code session "
                       "without cap-evolve. Its final working directory equals the seed (inert) and is excluded here "
                       "(D2). This arm is the **best candidate that session evaluated** (the session's own named best, "
                       "ablation ledger decision ABL-0485), frozen and scored as a secondary artifact. It was picked by "
                       "its search score, so it is selection-biased in the same way as every champion.",
        "abl_prompt": "**Prompt only.** Only `policy/instructions.txt` could change; `tools/` stayed byte-identical to "
                      "the seed (verified at fetch).",
        "abl_tools": "**Tools only.** Only `tools/helpers.py` and `tools/api_notes.json` could change; the prompt stayed "
                     "byte-identical to the seed. The frozen champion changed only `tools/api_notes.json` (measured at "
                     "planning, file sha256 vs the seed's).",
        "abl_notrace": "**No traces.** The proposer saw each rollout's reward and evaluation feedback, but no "
                       "conversation trace. The artifact surfaces are the reference's.",
        "abl_tracescore": "**Traces and score only.** The proposer saw full conversation traces and only the 0/1 reward, "
                          "with no evaluation feedback. The artifact surfaces are the reference's.",
        "abl_nogate": "**No gate (deferred, §3.2).** Every scored candidate was kept. Scored in window 2, after "
                      "window 1; comparisons with window-1 arms are cross-window.",
        "abl_naivegate": "**Naive gate (deferred, §3.2).** A candidate was kept iff its mean paired gain was above 0. "
                         "Scored in window 2, after window 1; comparisons with window-1 arms are cross-window.",
    }


def sections(text: str) -> dict[str, str]:
    """'## N. Title' sections of the plan, by number, verbatim (heading included)."""
    parts = re.split(r"(?m)^(?=## \d+\. )", text)
    out = {}
    for p in parts:
        m = re.match(r"## (\d+)\. ", p)
        if m:
            out[m.group(1)] = p.rstrip().rstrip("-").rstrip() + "\n"
    return out


def table_row(text: str, arm: str) -> tuple[str, str]:
    lines = sections(text)["3"].splitlines()
    head = next(i for i, l in enumerate(lines) if l.startswith("| # | arm id"))
    row = next(l for l in lines if re.match(rf"\| \d+ \| `{re.escape(arm)}` \|", l))
    return "\n".join(lines[head:head + 2]), row


def own_section(text: str, arm: str) -> str:
    if getattr(P, "TESTABL", False):
        return own_section_testabl(text, arm)
    hdr, row = table_row(text, arm)
    a = (P.manifest().get("artifacts") or {}).get(arm, {})
    lint = (P.manifest().get("lint") or {}).get(arm, {})
    spec = P.ARTIFACTS[arm]
    src = (f"local copy (`{spec['local']}`)" if a.get("source") == "local" else
           f"Box (`{P.BOX_ROOT}{spec['box']}`)") if a else "(not fetched yet)"
    is_not = ("It is one **frozen artifact**, produced by one search with one search seed, a method-specific budget "
              "and method-specific surfaces. Scoring it here measures this artifact under one shared test condition; "
              "it does **not** rank the method in general (§3, §12.3).") if arm != "seed" else (
              "It is not trained or modified in any way.")
    lines = [f"## This arm: {P.METHOD_NAMES[arm]} (`{arm}`)", "",
             "Its row of §3:", "", hdr, row, "",
             f"- **Method / source evaluation:** {P.SOURCE_EVAL[arm]}.",
             f"- **Surfaces searched** (§3): {P.SURFACES_OF[arm]}. **Surfaces the frozen artifact changed vs the seed** "
             f"(file sha256 compared with the seed's at fetch, decision D10): {P.SURFACES_CHANGED[arm]}.",
             f"- **Fetched from:** {src}; hash rule {spec['rule']}; expected `{spec['hash']}`; computed "
             f"`{a.get('computed', 'n/a')}`; **match: {'yes' if a.get('computed') == spec['hash'] else 'no'}**.",
             f"- **Scored files** (only the surfaces the harness reads): "
             + (", ".join(f"`{p}`" for p in sorted(a.get("scored_files") or {})) or "n/a") + ".",
             f"- **Lint** (§6.2): " + ("pass" if lint.get("pass") and not lint.get("violations") else
                                         "pass except the disclosed exception D6: " + "; ".join(lint.get("violations", []))
                                         if lint.get("pass") else "not run yet" if not lint else "FAIL") + ".",
             "", f"**What this artifact is and is not.** {is_not}"]
    if arm in PARTICULAR:
        lines += ["", PARTICULAR[arm]]
    return "\n".join(lines) + "\n"


def own_section_testabl(text: str, arm: str) -> str:
    sec = sections(text)["3"]
    lines = sec.splitlines()
    head = next(i for i, l in enumerate(lines) if l.startswith("| # | arm id"))
    hdr = "\n".join(lines[head:head + 2])
    row = next(l for l in lines if re.match(rf"\| \d+ \| `{re.escape(arm)}` \|", l))
    a = (P.manifest().get("artifacts") or {}).get(arm, {})
    lint = (P.manifest().get("lint") or {}).get(arm, {})
    spec = P.ARTIFACTS.get(arm)
    out = [f"## This arm: {P.METHOD_NAMES[arm]} (`{arm}`)", "", "Its row of §3:", "", hdr, row, "",
           f"- **Source:** {P.SOURCE_EVAL[arm]}."
           + (f" Search issue: #{P.SEARCH_ISSUES[arm]}." if arm in P.SEARCH_ISSUES else ""),
           f"- **Surfaces searched:** {P.SURFACES_OF[arm]}; **changed vs the seed:** "
           f"{P.SURFACES_CHANGED.get(arm, 'measured at fetch')}."]
    if spec:
        out.append(f"- **Expected hash** (rule S, the ablation freeze): `{spec['hash']}`; fetch result: "
                   + (f"source {a.get('source')}, computed `{a.get('computed')}`, match "
                      f"{'yes' if a.get('computed') == spec['hash'] else 'NO'}" if a else "not fetched yet (B3)") + ".")
    out.append("- **Lint** (§6): " + ("pass" if lint.get("pass") else "FAIL" if lint else "not run yet (B3)") + ".")
    out += ["", ("**What this artifact is and is not.** It is one **frozen artifact**, from one search with one search "
                 "seed. Scoring it here measures this artifact under one shared test condition. It does **not** measure "
                 "the ablated factor free of search randomness (§3, §12.3).") if arm != "seed" else
            "**What this artifact is.** The unmodified agent, not trained or modified in any way."]
    if arm in PARTICULAR:
        out += ["", PARTICULAR[arm]]
    return "\n".join(out) + "\n"


def header(arm: str, n_issue: int | None = None) -> str:
    if getattr(P, "TESTABL", False):
        win = "window 2 (the gate arms, after window 1)" if arm in P.GATE_ARMS else "window 1"
        return (f"# AppWorld TEST_ABL: {P.METHOD_NAMES[arm]} (`{arm}`), test_normal × 5 trials (gpt-oss-120b)\n\n"
                f"This issue tracks the **{P.METHOD_NAMES[arm]}** arm (`{arm}`) of the AppWorld TEST_ABL evaluation: "
                f"a **test-only** evaluation of the frozen champions of the AppWorld ablation study (#930 to #935, "
                f"#938, #939) and the seed agent, on `test_normal` (168 tasks), 5 trials per task, with no training of "
                f"any kind. It follows the protocol of `docs/TEST_ALL.md`. This arm is scored in {win}.\n\n"
                f"- Plan: [`docs/TEST_ABL.md`]({PLAN_URL}) on branch `test-abl` of the `erezh16/cap-evolve` fork.\n"
                f"- Ledger: [`docs/TEST_ABL_STATUS.md`]({LEDGER_URL}) on branch `test-abl`.\n"
                f"- Progress is posted here **at least hourly** (this arm's slot: {P.HOURLY_OFFSET_S[arm] // 60:02d}:"
                f"{P.HOURLY_OFFSET_S[arm] % 60:02d} past each UTC hour), plus milestones. **No test score of any arm is "
                f"posted before its window completes** and the analysis has run.\n\n"
                "Below: this arm's own section, then the common sections of the plan, verbatim.\n")
    return (f"# AppWorld TEST_ALL: {P.METHOD_NAMES[arm]} (`{arm}`), test_normal × 5 trials (gpt-oss-120b)\n\n"
            f"This issue tracks the **{P.METHOD_NAMES[arm]}** arm (`{arm}`) of the AppWorld TEST_ALL evaluation: 13 frozen "
            f"artifacts (the seed agent + 12 champions of earlier evaluations) scored together on `test_normal` "
            f"(168 tasks) in **one** shuffled window, 5 trials per task, with no training of any kind.\n\n"
            f"- Plan: [`docs/TEST_ALL.md`]({PLAN_URL}) on branch `cap-evolve-impr2` of the `erezh16/cap-evolve` fork.\n"
            f"- Ledger: [`docs/TEST_ALL_STATUS.md`]({LEDGER_URL}) on branch `test-all`.\n"
            f"- Progress is posted here **at least hourly** (this arm's slot: {P.HOURLY_OFFSET_S[arm] // 60:02d}:"
            f"{P.HOURLY_OFFSET_S[arm] % 60:02d} past each UTC hour), plus milestones. **No test score of any arm is "
            f"posted before the window completes** and the analysis has run.\n\n"
            "Below: this arm's own section, then the common sections of the plan, verbatim.\n")


def body(arm: str, text: str, short: bool = False) -> str:
    sec = sections(text)
    parts = [header(arm), own_section(text, arm), "---\n\n# The plan's common sections (verbatim)\n"]
    for n in COMMON:
        if short and n not in KEEP_FULL:
            title = sec[n].splitlines()[0]
            parts.append(f"{title}\n\n(Shortened for GitHub's size limit: see §{n} of [the plan]({PLAN_URL}).)\n")
        else:
            parts.append(sec[n])
    return "\n".join(parts)


def build(out: Path) -> dict:
    text = PLAN.read_text()
    out.mkdir(parents=True, exist_ok=True)
    res = {}
    for arm in (P.ISSUE_ARMS if hasattr(P, "ISSUE_ARMS") else P.ARMS):
        b, short = body(arm, text), False
        if len(b) > LIMIT:
            b, short = body(arm, text, short=True), True
        v = S.violations(b)
        (out / f"{arm}.md").write_text(b)
        res[arm] = {"chars": len(b), "shortened": short, "violations": v}
    return res


if __name__ == "__main__":
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else P.AW_STATE / "issue_bodies"
    r = build(out)
    print(json.dumps(r, indent=1))
    raise SystemExit(0 if all(not v["violations"] and v["chars"] <= LIMIT for v in r.values()) else 1)
