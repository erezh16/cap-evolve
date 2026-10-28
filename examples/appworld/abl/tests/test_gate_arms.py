"""ABLATIONS_GATE.md (abl_nogate, abl_naivegate): the profile rows, the instruction variants and the K parsing.

Offline: no task file, no episode, no optimizer call.
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ABL = HERE.parent
sys.path[:0] = [str(ABL), str(ABL.parent / "scripts")]

import instructions  # noqa: E402

GATE = ("abl_nogate", "abl_naivegate")


def test_profile_rows():
    import awabl as P
    assert P.CANDIDATES[:6] == ("abl_ref", "abl_cc", "abl_prompt", "abl_tools", "abl_notrace", "abl_tracescore")
    assert P.CANDIDATES[6:] == GATE and P.GATE_ARMS == GATE
    assert P.ISSUES["abl_nogate"] == 938 and P.ISSUES["abl_naivegate"] == 939
    assert P.K_SE["abl_ref"] == 0.2 and P.K_SE["abl_nogate"] == -100000 and P.K_SE["abl_naivegate"] == 0
    assert all(P.K_SE[a] == 0.2 for a in ("abl_prompt", "abl_tools", "abl_notrace", "abl_tracescore"))


def test_k_written_argparse_safe():
    # run_abl.kfmt is f"{k:g}"; a value like -1e+06 would be read by argparse as a flag
    for k, s in ((-100000.0, "-100000"), (0.0, "0"), (0.2, "0.2")):
        assert f"{k:g}" == s


def test_instructions_change_only_the_gate_clause():
    ref = instructions.render("abl_ref")
    for arm in GATE:
        t = instructions.render(arm)
        d = [x for x in instructions.udiff(ref, t, "a", "b").splitlines()
             if x[:1] in "+-" and x[:3] not in ("+++", "---")]
        assert len(d) == 2, d                      # one line out, one line in
        assert instructions._GATE_REF in d[0] and instructions._GATE_REF not in d[1]
        assert "does not apply in this run" in d[1]
        rest_a, rest_b = d[0][1:].split(instructions._GATE_REF), d[1][1:]
        assert rest_b.startswith(rest_a[0]) and rest_b.endswith(rest_a[1])
    assert "there is no acceptance gate" in instructions.render("abl_nogate")
    assert "above zero" in instructions.render("abl_naivegate")


def test_verdict_regex_reads_negative_and_zero_k():
    src = (ABL / "run_abl.py").read_text()
    rx = re.compile(re.search(r'_GATE_RE = re\.compile\(r"(.+?)"\)', src).group(1))
    for reason, k in (("paired Δ̄=-0.1361 > -100000.0·SE=-2837.4200 (SE=0.0284, n=147", -100000.0),
                      ("paired Δ̄=+0.0068 > 0.0·SE=0.0000 (SE=0.0068, n=147", 0.0),
                      ("paired Δ̄=+0.0884 > 0.2·SE=0.0096 (SE=0.0481, n=147", 0.2)):
        m = rx.search(reason)
        assert m and float(m.group(2)) == k
    spec_rx = re.compile(re.search(r'r"(\^gate_k_se:\\s\*\(-\?\[0-9\.\]\+\))"', src).group(1))
    for line, k in (("gate_k_se: -100000", -100000.0), ("gate_k_se: 0", 0.0), ("gate_k_se: 0.2", 0.2)):
        assert float(spec_rx.search(line).group(1)) == k
