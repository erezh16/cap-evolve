"""P4: the candidate searches, at most 3 at once on the shared slot pool (docs/EVAL_APPWORLD_REST.md §12.1, R2, R4).

  python3 -I p4.py loop [--max 3]      # nohup; resume.py relaunches it
  python3 -I p4.py status

Order (§12.1): cape_improve, gepa_full, miprov2 first; then harnesslens, trace2skill. Each candidate runs as one
detached chain `search → freeze → scan` (each step its own subprocess, in the candidate's venv), with its pid in
AW_STATE/p4/<cand>.pid (never pgrep -f). A step's exit status goes to AW_STATE/p4/<cand>.json. A failed step is
an `error` ledger entry and the chain stops (no automatic retry: the cause is investigated first, R5).

R2 escalation: while AW_STATE/PAUSE exists no new chain starts. If PAUSED lasts > 10 min, the global slots are cut
by 25% (decision entry); if it still lasts another 10 min, the most recently started search gets SIGTERM (it resumes
later from its own state; decision entry). Slots are raised back by 4 (never above 24 here) after 30 min below 65%.
When all five chains are done: phase_done P4, next = P5/dev.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import awrest as P  # noqa: E402
import status_doc as S  # noqa: E402

EX = HERE.parent
ORDER = ("cape_improve", "gepa_full", "miprov2", "harnesslens", "trace2skill")
PY = {"cape_improve": P.VENV_PY, "gepa_full": P.VENV_PY, "miprov2": P.VENVS / "venv-mipro" / "bin" / "python",
      "harnesslens": P.VENVS / "venv-hl" / "bin" / "python", "trace2skill": P.VENVS / "venv-t2s" / "bin" / "python"}
D = P.AW_STATE / "p4"


def chain_cmd(c: str) -> str:
    drv = EX / c / f"run_{c}.py"
    py = PY[c]
    log = P.PROGRESS / f"p4_{c}.out"
    st = D / f"{c}.json"
    steps = [("search", f"{py} -I {drv} search"), ("freeze", f"{py} -I {drv} freeze"),
             ("scan", f"{P.VENV_PY} -I {HERE / 'scan.py'} {c}")]
    done = (P.read_json(st, {}) or {}).get("done", [])
    parts = []
    for name, cmd in steps:
        if name in done:
            continue
        parts.append(f"echo '== {name} '$(date -u +%FT%TZ) >> {log}; {cmd} >> {log} 2>&1; rc=$?; "
                     f"{sys.executable} -I {HERE / 'p4.py'} mark {c} {name} $rc; [ $rc -eq 0 ] || exit $rc")
    return " ; ".join(parts) or "true"


def pid_of(c: str) -> int | None:
    try:
        return int((D / f"{c}.pid").read_text().split()[0])
    except (FileNotFoundError, ValueError, IndexError):
        return None


def alive(c: str) -> bool:
    """Live and not a zombie (an exited, unreaped chain still answers kill(pid, 0))."""
    pid = pid_of(c)
    if not S.pid_alive(pid):
        return False
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except (FileNotFoundError, IndexError):
        return False


def reap() -> None:
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if pid == 0:
            return


def state(c: str) -> dict:
    return P.read_json(D / f"{c}.json", {}) or {}


def finished(c: str) -> bool:
    return set(state(c).get("done", [])) >= {"search", "freeze", "scan"}


def failed(c: str) -> bool:
    return bool(state(c).get("failed"))


def start(c: str) -> None:
    D.mkdir(parents=True, exist_ok=True)
    p = subprocess.Popen(["/bin/bash", "-c", chain_cmd(c)], cwd=str(P.REPO), env=P.setup_env(dict(os.environ)),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    (D / f"{c}.pid").write_text(f"{p.pid} {P.utcnow()}\n")
    st = state(c)
    st.setdefault("started", []).append(P.utcnow())
    st.pop("failed", None)
    P.write_json(D / f"{c}.json", st)
    P.progress_log("p4", "P4", f"start {c} chain pid {p.pid}")
    S.append("phase_start", "P4", f"{c} search",
             f"P4: {c} chain started (search, freeze, isolation scan), pid file AW_STATE/p4/{c}.pid. Running chains: "
             f"{', '.join(x for x in ORDER if alive(x)) or 'none'}. Global slots {P.global_slots()}; memory "
             f"{P.memstate().get('used_pct')}%.", extra={"candidate": c}, subject=f"P4 start {c}")


def mark(c: str, step: str, rc: int) -> int:
    st = state(c)
    if rc == 0:
        st.setdefault("done", []).append(step)
    else:
        st["failed"] = {"step": step, "rc": rc, "t": P.utcnow()}
        S.append("error", "P4", f"{c} {step} failed",
                 f"P4: {c} step `{step}` exited {rc}; the chain stopped. See AW_STATE/progress/p4_{c}.out. "
                 "No automatic retry: the cause is investigated first (R5).", extra={"candidate": c},
                 subject=f"P4 {c} {step} failed")
    P.write_json(D / f"{c}.json", st)
    return 0


def set_slots(n: int, why: str) -> None:
    n = max(4, min(P.GLOBAL_SLOTS_MAX, n))
    P.SLOTS_DIR.mkdir(parents=True, exist_ok=True)
    P.atomic_write(P.SLOTS_DIR / "SIZE", f"{n}\n")
    S.append("decision", "P4", "slots", f"Global episode slots set to {n}: {why} (rule R2).", subject=f"slots {n}")


def loop(maxn: int) -> int:
    D.mkdir(parents=True, exist_ok=True)
    (D / "RUNNER.pid").write_text(str(os.getpid()))
    paused_since, cut_at, low_since = None, None, None
    while True:
        reap()
        running = [c for c in ORDER if alive(c)]
        todo = [c for c in ORDER if not finished(c) and not failed(c) and c not in running]
        if not running and not todo:
            if all(finished(c) for c in ORDER):
                S.append("phase_done", "P4", "searches done",
                         "P4 done: all five chains (search, freeze, isolation scan) finished. Next: P5 dev diagnostic.",
                         done_through="P4/searches", next_unit="P5/dev", extra={"candidate": None},
                         subject="P4 done")
            return 0
        ms = P.memstate()
        now = time.time()
        if P.paused() or ms.get("stale"):
            paused_since = paused_since or now
            if now - paused_since > 600 and cut_at is None:
                set_slots(int(P.global_slots() * 0.75), "PAUSED for more than 10 minutes")
                cut_at = now
            elif cut_at and now - cut_at > 600 and running:
                last = max(running, key=lambda c: (state(c).get("started") or [""])[-1])
                os.killpg(pid_of(last), signal.SIGTERM)
                S.append("decision", "P4", "stop search",
                         f"PAUSED for more than 20 minutes: stopped the most recently started chain ({last}) "
                         "gracefully; it resumes from its own state when memory allows (rule R2).",
                         extra={"candidate": last}, subject=f"stop {last}")
                st = state(last)
                st["stopped_by_guard"] = P.utcnow()
                P.write_json(D / f"{last}.json", st)
                cut_at = now
        else:
            paused_since, cut_at = None, None
            if float(ms.get("used_pct") or 100) < 65:
                low_since = low_since or now
                if now - low_since > 1800 and P.global_slots() < P.GLOBAL_SLOTS_DEFAULT:
                    set_slots(P.global_slots() + 4, "30 minutes below 65%")
                    low_since = now
            else:
                low_since = None
            if todo and len(running) < maxn:
                # rule R2 spawn check: fresh guard, not paused, memcheck says something fits
                r = subprocess.run([str(Path.home() / "bin" / "memok")], capture_output=True, text=True)
                if r.returncode == 0:
                    start(todo[0])
                    time.sleep(120)       # let the new chain's memory show before deciding on the next one
                    continue
        time.sleep(30)


def status() -> int:
    for c in ORDER:
        print(c, "alive" if alive(c) else "-", json.dumps(state(c)))
    return 0


if __name__ == "__main__":
    a = sys.argv
    if a[1] == "mark":
        raise SystemExit(mark(a[2], a[3], int(a[4])))
    if a[1] == "status":
        raise SystemExit(status())
    raise SystemExit(loop(int(a[a.index("--max") + 1]) if "--max" in a else 3))
