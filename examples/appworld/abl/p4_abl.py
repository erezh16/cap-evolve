"""P4 of the ablations: six searches in two waves of up to three, each a chain search -> freeze -> isolation scan ->
reset check (docs/ABLATIONS.md §13.1, §4.4 R4, §9.8, rules R2 and R4). Source abl/env.sh first. CE2's p4_ce2.py with:
waves (abl_ref, abl_prompt, abl_tools launched in the same pass; then abl_notrace, abl_tracescore, abl_cc, each as soon
as a running chain finishes; never more than MAX_RUNNING at once); abl_cc's chain (its session, freeze, scan, reset);
no two-arm independence check (no arms here are meant to be identical, CE3-0010).

  python3 -I p4_abl.py loop        # nohup; resume relaunches it
  python3 -I p4_abl.py status

Each chain is a detached bash process (pid in AW_STATE/p4/<arm>.pid; never pgrep -f); a step's exit status goes to
AW_STATE/p4/<arm>.json. A failed step is an `error` ledger entry and that chain stops (no automatic retry, R5).
Every 60 s: refreshes each arm's pushed progress.json; one `result` entry and one post per new iteration verdict
(cap-evolve arms) or evaluation (abl_cc). R2 escalation: PAUSED > 10 min: global slots -25%; > 20 min: the most
recently started chain is asked to stop at its next iteration boundary (SIGTERM; resumes later with --resume).
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EX = HERE.parent
sys.path[:0] = [str(EX / "scripts"), str(EX / "common"), str(HERE)]
import awrest as P  # noqa: E402
import status_doc as S  # noqa: E402

if P.LEDGER_ID != "ABL":
    raise SystemExit("p4_abl.py: source abl/env.sh first")
D = P.AW_STATE / "p4"
VC_PY = P.VENVS / "venv-abl" / "bin" / "python"
STEPS = ("search", "freeze", "scan", "reset")
WAVES = (("abl_ref", "abl_prompt", "abl_tools"), ("abl_notrace", "abl_tracescore", "abl_cc"),
         ("abl_nogate", "abl_naivegate"))   # R4; the third wave is ABLATIONS_GATE.md G6
ORDER = tuple(a for w in WAVES for a in w)
MAX_RUNNING = 3


def run_dir(arm: str) -> Path:
    return P.RUN_ROOTS[arm] / ".capevolve" / f"run_{P.RUN_TS[arm]}"


def chain_cmd(arm: str) -> str:
    drv = HERE / "run_abl.py"
    log = P.PROGRESS / f"p4_{arm}.out"
    if arm == "abl_cc":
        st_ = state(arm)
        sec = (st_.get("second_session") or "")       # ABL-0341: one recorded second session
        n = st_.get("session")                        # ABL-0462/0465: session 3, after the sandbox fix
        pre = f"AW_CC_SESSION={int(n)} " if n else (f"AW_CC_SECOND_SESSION={sec} " if sec else "")
        search = pre + f"bash {HERE / 'cc' / 'launch_cc.sh'}"
        if n:   # the session's evaluations still count: let the daemon finish them before the freeze (§10.2)
            # drain even if the CLI exits non-zero (e.g. the turn cap); the step keeps the session's exit code
            search = f"{{ {search}; r=$?; bash {HERE / 'cc' / 'drain_evald.sh'} && [ $r -eq 0 ]; }}"
        cmds = {"search": search, "freeze": f"{VC_PY} -I {HERE / 'cc' / 'run_cc.py'} freeze"}
    else:
        cmds = {"search": f"{VC_PY} -I {drv} search --arm {arm}", "freeze": f"{VC_PY} -I {drv} freeze --arm {arm}"}
    cmds["scan"] = f"{P.VENV_PY} -I {EX / 'scripts' / 'scan.py'} {arm}"
    cmds["reset"] = f"{VC_PY} -I {HERE / 'reset_check.py'} {arm}"
    done = state(arm).get("done", [])
    parts = []
    for name in STEPS:
        if name in done:
            continue
        parts.append(f"echo '== {name} '$(date -u +%FT%TZ) >> {log}; {cmds[name]} >> {log} 2>&1; rc=$?; "
                     f"{sys.executable} -I {HERE / 'p4_abl.py'} mark {arm} {name} $rc; [ $rc -eq 0 ] || exit $rc")
    return " ; ".join(parts) or "true"


def state(arm: str) -> dict:
    return P.read_json(D / f"{arm}.json", {}) or {}


def pid_of(arm: str) -> int | None:
    try:
        return int((D / f"{arm}.pid").read_text().split()[0])
    except (FileNotFoundError, ValueError, IndexError):
        return None


def alive(arm: str) -> bool:
    pid = pid_of(arm)
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


def finished(arm: str) -> bool:
    return set(state(arm).get("done", [])) >= set(STEPS)


def failed(arm: str) -> bool:
    return bool(state(arm).get("failed"))


def start(arm: str) -> None:
    D.mkdir(parents=True, exist_ok=True)
    # the runner imports run_abl to read verdicts, and select_arm() sets AW_CAPE_ARM in this process: no chain may
    # inherit an arm name or switch from the runner (plan 9.2 step 5, 9.8 item 3; ABL-0294)
    env = {k: v for k, v in os.environ.items()
           if k not in ("AW_CAPE_ARM", "AW_ABL_FEEDBACK", "AW_ABL_TOOLS_LINT") and not k.startswith("CAPEVOLVE_")}
    p = subprocess.Popen(["/bin/bash", "-c", chain_cmd(arm)], cwd=str(P.REPO), env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    (D / f"{arm}.pid").write_text(f"{p.pid} {P.utcnow()}\n")
    st = state(arm)
    st.setdefault("started", []).append(P.utcnow())
    st.pop("failed", None)
    st.pop("stopped_by_guard", None)
    P.write_json(D / f"{arm}.json", st)
    P.progress_log("p4", "P4", f"start {arm} chain pid {p.pid}")


def mark(arm: str, step: str, rc: int) -> int:
    st = state(arm)
    if rc == 0:
        st.setdefault("done", []).append(step)
    elif st.get("stopped_by_guard") or st.get("stopped_by_decision"):
        st["interrupted"] = {"step": step, "rc": rc, "t": P.utcnow()}
    else:
        st["failed"] = {"step": step, "rc": rc, "t": P.utcnow()}
        S.append("error", "P4", f"{arm} {step} failed",
                 f"P4: {arm} step `{step}` exited {rc}; the chain stopped. See AW_STATE/progress/p4_{arm}.out. "
                 "No automatic retry: the cause is investigated first (R5).", extra={"arm": arm},
                 subject=f"P4 {arm} {step} failed")
    P.write_json(D / f"{arm}.json", st)
    return 0


def set_slots(n: int, why: str) -> None:
    n = max(4, min(P.GLOBAL_SLOTS_MAX, n))
    P.SLOTS_DIR.mkdir(parents=True, exist_ok=True)
    P.atomic_write(P.SLOTS_DIR / "SIZE", f"{n}\n")
    S.append("decision", "P4", "slots", f"Global episode slots set to {n}: {why} (rule R2).", subject=f"slots {n}")


# ---------------------------------------------------------------- per-iteration verdicts and posts

def _rows(arm: str) -> list[dict]:
    if arm == "abl_cc":
        return [e for e in P.read_jsonl(P.AW_STATE / "abl_cc" / "evals.jsonl") if e.get("state") == "done"]
    import importlib
    R = importlib.import_module("run_abl")
    R.select_arm(arm)
    return R.iteration_rows(run_dir(arm))


def _refresh_progress(arm: str) -> None:
    cmd = ([str(VC_PY), "-I", str(HERE / "cc" / "run_cc.py"), "progress"] if arm == "abl_cc" else
           [str(VC_PY), "-I", str(HERE / "run_abl.py"), "progress", "--arm", arm, "--level", "search running"])
    subprocess.run(cmd, capture_output=True, text=True, env=dict(os.environ))


def verdict_text(arm: str, i: int, r: dict) -> str:
    if arm == "abl_cc":
        return (f"evaluation {i}: mean val {r.get('mean_reward')} ({'lint reject, 0 rollouts' if r.get('lint') == 'rejected' else 'lint ok'}); "
                f"{r.get('fresh')} new rollouts, {r.get('rollouts_used')} of {P.BUDGET_ROLLOUTS} used")
    if r.get("kind") in ("tamper", "capability_invalid"):
        return f"iteration {i}: voided before any rollout ({r['kind']}: a sealed surface changed or the capability is invalid; consumes the iteration)"
    if r.get("indecisive"):
        return f"iteration {i}: evaluation error (indecisive; consumes the iteration, #876)"
    if "delta" not in r:
        return f"iteration {i}: val {r.get('val')}, {'ACCEPT' if r.get('accept') else 'reject'}"
    k = P.K_SE[arm]
    t = (f"iteration {i}: val {r['val']:.4f} (parent {r['parent_val']:.4f}); paired Δ̄ {r['delta']:+.4f}, "
         f"SE {r['se']:.4f}, K·SE {r['bar']:.4f} (K = {k:g}) → {'ACCEPT' if r['accept'] else 'reject'}")
    return t


def report_iterations() -> None:
    import post
    seen = P.read_json(D / "reported.json", {}) or {}
    for arm in P.CANDIDATES:
        # abl_cc has no cap-evolve run dir: its unit of progress is the daemon's evaluation log
        src = (P.AW_STATE / "abl_cc" / "evals.jsonl") if arm == "abl_cc" else (run_dir(arm) / "events.jsonl")
        if not src.exists():
            continue
        _refresh_progress(arm)
        rows = _rows(arm)
        n0 = int(seen.get(arm, 0))
        for i in range(n0, len(rows)):
            r = rows[i]
            pr = P.read_json(P.PUSHED / arm / "progress.json", {}) or {}
            txt = verdict_text(arm, i + 1, r)
            done_txt = (f"evaluations {pr.get('evaluations_done')} of 6" if arm == "abl_cc" else
                        f"iterations scored {pr.get('iterations_done')} of 6, accepted {pr.get('accepted')}")
            body = (f"**{P.METHOD_NAMES[arm]}: {txt}.**\n\n- {done_txt}; best search score {pr.get('best_search_score')} "
                    f"({pr.get('best_search_label')}); counted rollouts {pr.get('counted_rollouts')} of "
                    f"{P.BUDGET_ROLLOUTS}; optimizer proxy ${(pr.get('optimizer') or {}).get('proxy_usd')}.\n\n"
                    "Counts and aggregates only (val = train ∪ dev, 147 tasks, 1 trial: a fit metric).")
            S.append("result", "P4", f"{arm} iteration {i + 1}", f"P4 {arm}: {txt}. Counted rollouts "
                     f"{pr.get('counted_rollouts')} of {P.BUDGET_ROLLOUTS}; optimizer proxy USD "
                     f"{(pr.get('optimizer') or {}).get('proxy_usd')}; best search score (fit metric) "
                     f"{pr.get('best_search_score')}.", extra={"arm": arm, "iteration": i + 1, "verdict": r},
                     artifacts=[f"STATE/{arm}/progress.json"], subject=f"P4 {arm} {i + 1}")
            word = "evaluation" if arm == "abl_cc" else "iteration"
            post.post(arm, f"{'eval' if arm == 'abl_cc' else 'iter'}_{i + 1}", f"{P.METHOD_NAMES[arm]} {word} {i + 1}", body)
            seen[arm] = i + 1
            P.write_json(D / "reported.json", seen)


# ---------------------------------------------------------------- loop

def loop() -> int:
    D.mkdir(parents=True, exist_ok=True)
    (D / "RUNNER.pid").write_text(str(os.getpid()))
    paused_since, cut_at, k2_stopped = None, None, False
    first = True
    while True:
        reap()
        try:
            report_iterations()
        except Exception as e:  # noqa: BLE001 — reporting must never stop the searches
            P.progress_log("p4", "P4", f"report error {type(e).__name__}: {e}"[:300])
        running = [a for a in ORDER if alive(a)]
        stopped = False
        todo = [a for a in ORDER if not finished(a) and not failed(a) and a not in running
                and not state(a).get("stopped_by_decision") and not (state(a).get("stopped_by_guard") and k2_stopped)]
        if not running and not todo:
            if all(finished(a) for a in ORDER):
                S.append("phase_done", "P4", "searches done",
                         "P4 done: all six chains (search, freeze, isolation scan, reset check) finished. Next: P5 dev "
                         "diagnostic.", done_through="P4/searches", next_unit="P5/dev", extra={"arm": None},
                         subject="P4 done")
                subprocess.Popen(["nohup", sys.executable, "-I", str(HERE / "after_p4.py")],
                                 stdout=open(P.PROGRESS / "after_p4.out", "a"), stderr=subprocess.STDOUT,
                                 start_new_session=True, cwd=str(P.REPO), env=dict(os.environ))
            return 0
        ms = P.memstate()
        now = time.time()
        if P.paused() or ms.get("stale"):
            paused_since = paused_since or now
            if now - paused_since > 600 and cut_at is None:
                set_slots(int(P.global_slots() * 0.75), "PAUSED for more than 10 minutes")
                cut_at = now
            elif cut_at and now - paused_since > 1200 and running and not k2_stopped:
                # the most recently started cap-evolve chain (abl_cc is never stopped: no re-prompting, §13.4)
                cand = [a for a in running if a != "abl_cc"]
                last = max(cand, key=lambda a: (state(a).get("started") or [""])[-1]) if cand else None
                if last:
                    s2 = state(last)
                    s2["stopped_by_guard"] = P.utcnow()
                    P.write_json(D / f"{last}.json", s2)
                    os.killpg(pid_of(last), signal.SIGTERM)
                    k2_stopped = True
                    S.append("decision", "P4", f"stop {last}",
                             f"PAUSED for more than 20 minutes: {last}'s search (the most recently started) was stopped "
                             "(SIGTERM); it resumes with --resume when memory allows and still ends with 6 scored "
                             "iterations (rule R2).", extra={"arm": last}, subject=f"R2 stop {last}")
        else:
            paused_since, cut_at = None, None
            if k2_stopped and not any(state(a).get("stopped_by_guard") and alive(a) for a in ORDER):
                k2_stopped = False          # memory is back: the stopped arm resumes (its search step runs with --resume)
                for a in ORDER:
                    if state(a).get("stopped_by_guard"):
                        s2 = state(a)
                        s2.pop("stopped_by_guard")
                        P.write_json(D / f"{a}.json", s2)
            cap = MAX_RUNNING
            try:                            # resume after a pod restart writes a smaller cap (R2 "relaunch smaller")
                cap = min(cap, int((D / "MAX_RUNNING").read_text().strip()))
            except (FileNotFoundError, ValueError):
                pass
            free = cap - len(running)
            todo = todo[:max(0, free)]
            if todo and not stopped:
                r = subprocess.run([str(Path.home() / "bin" / "memok-abl")], capture_output=True, text=True)
                if r.returncode == 0:
                    for a in todo:          # R4: a wave's arms in the same pass, within the same minute
                        start(a)
                    S.append("phase_start", "P4", "searches launched" if first else "search relaunched",
                             f"P4: chain(s) {', '.join(todo)} started (search, freeze, isolation scan); pid files "
                             f"AW_STATE/p4/<arm>.pid. Running now: {', '.join(a for a in ORDER if alive(a))}. "
                             f"Global slots {P.global_slots()}; memory {P.memstate().get('used_pct')}%.",
                             extra={"arm": None}, subject="P4 launch")
                    first = False
        time.sleep(60)


def status() -> int:
    for a in ORDER:
        print(a, "alive" if alive(a) else "-", json.dumps(state(a)))
    return 0


def rearm(arm: str, session: int, reason: str) -> int:
    """By user decision only (ABL-0462): a held chain runs again from its first step, with a numbered session for
    abl_cc. The earlier steps' records stay in the ledger; their results are superseded by the new run."""
    st = state(arm)
    if alive(arm):
        raise SystemExit(f"rearm: the {arm} chain is running")
    st.setdefault("notes", []).append(f"{P.utcnow()} rearmed: {reason}; earlier done {st.get('done', [])}")
    st["done"] = []
    for k in ("stopped_by_decision", "failed", "interrupted", "stopped_by_guard"):
        st.pop(k, None)
    if session:
        st["session"] = session
    P.write_json(D / f"{arm}.json", st)
    return 0


if __name__ == "__main__":
    a = sys.argv
    if a[1] == "mark":
        raise SystemExit(mark(a[2], a[3], int(a[4])))
    if a[1] == "rearm":
        raise SystemExit(rearm(a[2], int(a[a.index("--session") + 1]) if "--session" in a else 0,
                               a[a.index("--reason") + 1]))
    if a[1] == "status":
        raise SystemExit(status())
    raise SystemExit(loop())
