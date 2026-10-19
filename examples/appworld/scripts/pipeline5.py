"""The phase runner of eval 5 (docs/EVAL_APPWORLD_5.md §10): continues at the ledger's `next` unit.

  venv-aw/bin/python -I pipeline5.py            # run from the last entry's `next` until a manual step
Candidates run one at a time (§11), in the order of aw5.CANDIDATES; each is `search` → `freeze` → `scan`. After the
five: P6 dev diagnostic, P7 scan, P8 final window, P9 analysis. Posting (P10) and every acceptance check
are manual steps (they need a person to read them first). Each step is its own subprocess and is
resumable on its own (GEPA run_dir, SkillOpt runtime_state, evaluator episode records, window cells).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import aw5 as P  # noqa: E402

EX = HERE.parent
DRIVERS = {
    "gepa": (P.VENV_PY, EX / "gepa" / "run_gepa.py"),
    "skillopt": (P.VENVS / "venv-skillopt" / "bin" / "python", EX / "skillopt" / "run_skillopt.py"),
    "wikiskill": (P.VENV_PY, EX / "wikiskill" / "run_wikiskill.py"),
    "evoskill": (P.VENVS / "venv-evoskill" / "bin" / "python", EX / "evoskill" / "run_evoskill.py"),
    "metaharness": (P.VENV_PY, EX / "metaharness" / "meta_harness_appworld.py"),
}


def step_of(nxt: str):
    """`next` unit -> (argv, the unit that follows when it succeeds), or None for a manual step."""
    parts = nxt.split("/")
    if parts[0] in DRIVERS and len(parts) >= 2 and parts[1] in ("search", "freeze", "scan"):
        c, what = parts[0], parts[1]
        py, script = DRIVERS[c]
        if what == "search":
            return [str(py), "-I", str(script), "search"], f"{c}/freeze"
        if what == "freeze":
            return [str(py), "-I", str(script), "freeze"], f"{c}/scan"
        i = P.CANDIDATES.index(c)  # per-candidate isolation scan, then the next candidate's search (§10)
        after = f"{P.CANDIDATES[i + 1]}/search" if i + 1 < len(P.CANDIDATES) else "P6/refreeze"
        return [str(P.VENV_PY), "-I", str(HERE / "scan5.py"), c], after
    if nxt == "metaharness/rerun":  # D11: 2 replacement iterations, then freeze → scan → P6 (only the changed arm re-runs)
        return [str(P.VENV_PY), "-I", str(EX / "metaharness" / "meta_harness_appworld.py"), "search"], "metaharness/freeze"
    if nxt == "P6/refreeze":
        return [str(P.VENV_PY), "-I", str(HERE / "window5.py"), "refreeze"], "p6dev/cells"
    if nxt == "P6/freeze":
        return [str(P.VENV_PY), "-I", str(HERE / "window5.py"), "freeze"], "p6dev/cells"
    if nxt.startswith("p6dev"):
        return [str(P.VENV_PY), "-I", str(HERE / "window5.py"), "dev"], "P7/scan"
    if nxt == "P7/scan":
        return [str(P.VENV_PY), "-I", str(HERE / "scan5.py")], "P8/final"
    if nxt.startswith("P8") or nxt.startswith("p8final"):
        return [str(P.VENV_PY), "-I", str(HERE / "window5.py"), "final"], "P9/analysis"
    if nxt == "P9/analysis":
        return [str(P.VENV_PY), "-I", str(HERE / "analyze5.py")], "P10/post"
    return None


def main() -> int:
    import status_doc as S
    while True:
        last = S.last_entry()
        st = step_of(last.get("next") or "")
        if st is None:
            P.progress_log("pipeline", last.get("phase", "?"), f"stop at manual step {last.get('next')}")
            return 0
        argv, after = st
        P.progress_log("pipeline", last.get("phase", "?"), f"run {' '.join(Path(a).name for a in argv[2:])}")
        r = subprocess.run(argv, env=P.setup_env(dict(os.environ)), cwd=str(P.REPO))
        if r.returncode:
            S.append("error", last.get("phase", "?"), "step failed",
                     f"Step `{last.get('next')}` exited {r.returncode}; see the local progress logs. Runner stopped.",
                     subject=f"error {last.get('next')}")
            return r.returncode
        now = S.last_entry()
        if now.get("next") == last.get("next"):  # the step did not checkpoint its own completion
            S.append("phase_done", now.get("phase", "?"), "step done", f"Step `{last.get('next')}` done. Next: {after}.",
                     done_through=last.get("next"), next_unit=after, subject=f"done {last.get('next')}")


if __name__ == "__main__":
    sys.exit(main())
