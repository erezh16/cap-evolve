"""P5 -> P9 of eval CE2, run as one nohup chain after P4 (docs/EVAL_APPWORLD_CE2.md §14.1). Source ce2/env.sh.

  python3 -I after_p4.py [--from P5|P6|P7|P8|P9]      # resumable: each finished phase is in AW_STATE/after_p4.json

P5: freeze into final/artifacts (window.py freeze; hashes checked) and the dev diagnostic (window.py dev; cache hits).
P6: full isolation scan (scan.py --full) and the model-usage / J1 / K re-check it carries; stops (exit 3, error
    entry) on any test-id hit, any optimizer model other than aws/claude-sonnet-5-5, or a failed J1/K re-check.
P7: the one final window (window.py final): root_full unlocked at start, relocked at the end (both logged).
P8: analysis (analyze.py). P9: per-arm drafts (report_ce2.py draft), then posts (report_ce2.py post).
Every phase start and end is a ledger entry; any failure is an `error` entry and the chain stops (R5).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EX = HERE.parent
sys.path[:0] = [str(EX / "scripts"), str(EX / "common")]
import awrest as P  # noqa: E402
import status_doc as S  # noqa: E402

ST = P.AW_STATE / "after_p4.json"
AW = str(P.VENV_PY)


def run(phase: str, cmd: list[str]) -> int:
    log = P.PROGRESS / f"{phase.lower()}.out"
    with open(log, "a") as f:
        f.write(f"== {P.utcnow()} {' '.join(cmd)}\n")
        f.flush()
        r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=str(P.REPO), env=dict(os.environ))
    return r.returncode


def fail(phase: str, what: str, rc: int) -> int:
    S.append("error", phase, f"{what} failed", f"{phase}: `{what}` exited {rc}; the chain stopped. See "
             f"AW_STATE/progress/{phase.lower()}.out. No automatic retry: the cause is investigated first (R5).",
             subject=f"{phase} {what} failed")
    return rc or 1


def p6_gate() -> tuple[bool, str]:
    sc = P.read_json(P.PUSHED / "isolation_scan.json", {}) or {}
    bad = []
    for a in P.CANDIDATES:
        v = sc.get(a) or {}
        if v.get("test_id_hits"):
            bad.append(f"{a}: {v['test_id_hits']} test-id hits")
        ce = v.get("ce2") or {}
        if ce.get("other_models"):
            bad.append(f"{a}: other optimizer models {ce['other_models']}")
        if not ce.get("j1_all_ok") or not ce.get("k_ok"):
            bad.append(f"{a}: J1 ok={ce.get('j1_all_ok')}, K ok={ce.get('k_ok')}")
    if (sc.get("_orchestrating_sessions") or {}).get("test_id_hits"):
        bad.append("orchestrating sessions: test-id hits")
    return not bad, "; ".join(bad)


def main() -> int:
    st = P.read_json(ST, {}) or {}
    done = set(st.get("done", []))
    (P.AW_STATE / "AFTER_P4.pid").write_text(str(os.getpid()))

    def mark(ph):
        done.add(ph)
        P.write_json(ST, {"done": sorted(done)})

    if "P5" not in done:
        for what, cmd in (("freeze", [AW, "-I", str(EX / "scripts" / "window.py"), "freeze"]),
                          ("dev diagnostic", [AW, "-I", str(EX / "scripts" / "window.py"), "dev"])):
            rc = run("P5", cmd)
            if rc:
                return fail("P5", what, rc)
        mark("P5")
    if "P6" not in done:
        rc = run("P6", [AW, "-I", str(EX / "scripts" / "scan.py"), "--full"])
        if rc:
            return fail("P6", "full isolation scan", rc)
        ok, why = p6_gate()
        if not ok:
            S.append("abort", "P6", "scan gate", f"P6 gate failed: {why}. The final window is NOT started; the user "
                     "is asked (R5).", subject="P6 gate failed")
            return 3
        mark("P6")
    if "P7" not in done:
        S.append("phase_start", "P7", "final window", f"P7 starts: 168 test_normal x 3 arms (seed, ce2_k1, ce2_k2) x 2 "
                 f"trials = 1,008 cells in one shuffled order (seed {P.manifest().get('final_order', {}).get('seed')}), "
                 f"{P.global_slots()} global slots; root_full is unlocked by window.py for the window and relocked at "
                 "its end; only rewards, counters and infra flags are read.", done_through="P6/scan",
                 next_unit="P7/final", subject="P7 start")
        rc = run("P7", [AW, "-I", str(EX / "scripts" / "window.py"), "final"])
        n = len(list((P.AW_STATE / "final" / "records").glob("*.json")))
        if rc or n < 1008:
            return fail("P7", f"final window ({n}/1008 cells)", rc or 1)
        mark("P7")
    if "P8" not in done:
        rc = run("P8", [AW, "-I", str(EX / "scripts" / "analyze.py")])
        if (os.stat(P.ROOT_FULL).st_mode & 0o777) != 0:
            os.chmod(P.ROOT_FULL, 0o000)
        if rc:
            return fail("P8", "analysis", rc)
        a = P.read_json(P.PUSHED / "final" / "analysis.json", {}) or {}
        v = a.get("vs_seed", {})
        k = a.get("k2_vs_k1") or {}
        f = lambda x: f"{100 * x:+.1f}"  # noqa: E731
        txt = "; ".join(f"{c} TGC {100 * a['arms'][c]['tgc']:.1f} / SGC {100 * a['arms'][c]['sgc']:.1f}, Δ TGC vs seed "
                        f"{f(v[c]['d_tgc'])} [{f(v[c]['ci_tgc'][0])}, {f(v[c]['ci_tgc'][1])}]" for c in P.CANDIDATES)
        S.append("phase_done", "P8", "analysis", f"P7 done (1,008/1,008 cells; root_full relocked). P8 analysis done "
                 f"(final/analysis.json, final/RESULTS.md, aggregates only). test_normal: seed TGC "
                 f"{100 * a['arms']['seed']['tgc']:.1f} / SGC {100 * a['arms']['seed']['sgc']:.1f}; {txt}; ce2_k2 − ce2_k1 "
                 f"Δ TGC {f(k.get('d_tgc', 0))} [{f(k.get('ci_tgc', [0, 0])[0])}, {f(k.get('ci_tgc', [0, 0])[1])}] "
                 "(one search seed each: K confounded with search randomness). Next: P9 results posts.",
                 done_through="P8/analysis", next_unit="P9/post",
                 artifacts=["STATE/final/analysis.json", "STATE/final/RESULTS.md"], subject="P8 analysis")
        mark("P8")
    if "P9" not in done:
        for what, sub in (("drafts", "draft"), ("posts", "post")):
            rc = run("P9", [AW, "-I", str(HERE / "report_ce2.py"), sub])
            if rc:
                return fail("P9", f"results {what}", rc)
            if sub == "draft":
                S.append("result", "P9", "results drafts", "P9: the two per-arm results comments drafted in "
                         f"docs/{P.PUSHED.name}/<arm>/RESULTS.md by ce2/report_ce2.py from final/analysis.json and the "
                         "pushed state; each passes the content filter when posted.", subject="P9 drafts")
        mark("P9")
        S.append("phase_done", "P9", "evaluation complete", "P9 done: results comments posted on #909 (ce2_k1) and #910 "
                 "(ce2_k2); URLs in the posted entries above. root_full is locked (chmod 000). The background loops "
                 "(autopost, heartbeat, memguard) are stopped next by the executing session.",
                 done_through="P9/post", next_unit="done", subject="P9 done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
