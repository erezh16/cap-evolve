"""P4 of eval CE2: both searches launched together, each a chain search -> freeze -> isolation scan
(docs/EVAL_APPWORLD_CE2.md §14.1, §9.7, rules R2 and R4). Source ce2/env.sh first.

  python3 -I p4_ce2.py loop        # nohup; resume.py relaunches it
  python3 -I p4_ce2.py status

Each arm's chain is a detached bash process (pid in AW_STATE/p4/<arm>.pid; never pgrep -f), each step its own
subprocess; a step's exit status goes to AW_STATE/p4/<arm>.json. A failed step is an `error` ledger entry and that
chain stops (no automatic retry, R5). Both chains start in the same loop pass (within the same minute, R4).

Every 60 s the loop also: refreshes each arm's pushed progress.json; writes one `result` ledger entry and one
milestone post per new iteration verdict (val, Δ̄, SE, K·SE, verdict; ce2_k2 also "would pass at K = 1"); after
both arms have iteration 1, runs the independence check of §9.7 (if the two cand_0001 diffs are byte-identical,
both searches are stopped before iteration 2 with a `decision` entry and the user is asked).

R2 escalation: PAUSED > 10 min: global slots -25% (decision entry); > 20 min: ce2_k2 is asked to stop at its next
iteration boundary (SIGTERM to its chain; resumes later with --resume; decision entry).
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

if P.LEDGER_PREFIX != "CE2":
    raise SystemExit("p4_ce2.py: source ce2/env.sh first")
D = P.AW_STATE / "p4"
VC_PY = P.VENVS / "venv-ce2" / "bin" / "python"
STEPS = ("search", "freeze", "scan")


def run_dir(arm: str) -> Path:
    return P.RUN_ROOTS[arm] / ".capevolve" / f"run_{P.RUN_TS[arm]}"


def chain_cmd(arm: str) -> str:
    drv = HERE / "run_ce2.py"
    log = P.PROGRESS / f"p4_{arm}.out"
    cmds = {"search": f"{VC_PY} -I {drv} search --arm {arm}", "freeze": f"{VC_PY} -I {drv} freeze --arm {arm}",
            "scan": f"{P.VENV_PY} -I {EX / 'scripts' / 'scan.py'} {arm}"}
    done = state(arm).get("done", [])
    parts = []
    for name in STEPS:
        if name in done:
            continue
        parts.append(f"echo '== {name} '$(date -u +%FT%TZ) >> {log}; {cmds[name]} >> {log} 2>&1; rc=$?; "
                     f"{sys.executable} -I {HERE / 'p4_ce2.py'} mark {arm} {name} $rc; [ $rc -eq 0 ] || exit $rc")
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
    env = dict(os.environ)
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
    import importlib
    R = importlib.import_module("run_ce2")
    R.select_arm(arm)
    return R.iteration_rows(run_dir(arm))


def _refresh_progress(arm: str) -> None:
    subprocess.run([str(VC_PY), "-I", str(HERE / "run_ce2.py"), "progress", "--arm", arm, "--level", "search running"],
                   capture_output=True, text=True, env=dict(os.environ))


def verdict_text(arm: str, i: int, r: dict) -> str:
    if r.get("indecisive"):
        return f"iteration {i}: evaluation error (indecisive; consumes the iteration, #876)"
    if "delta" not in r:
        return f"iteration {i}: val {r.get('val')}, {'ACCEPT' if r.get('accept') else 'reject'}"
    k = P.K_SE[arm]
    t = (f"iteration {i}: val {r['val']:.4f} (parent {r['parent_val']:.4f}); paired Δ̄ {r['delta']:+.4f}, "
         f"SE {r['se']:.4f}, K·SE {r['bar']:.4f} (K = {k}) → {'ACCEPT' if r['accept'] else 'reject'}")
    if arm == "ce2_k2":
        t += f"; would pass at K = 1: {'yes' if r['would_pass_k1'] else 'no'} (reporting only)"
    return t


def report_iterations() -> None:
    import post
    seen = P.read_json(D / "reported.json", {}) or {}
    for arm in P.CANDIDATES:
        if not (run_dir(arm) / "events.jsonl").exists():
            continue
        _refresh_progress(arm)
        rows = _rows(arm)
        n0 = int(seen.get(arm, 0))
        for i in range(n0, len(rows)):
            r = rows[i]
            pr = P.read_json(P.PUSHED / arm / "progress.json", {}) or {}
            txt = verdict_text(arm, i + 1, r)
            body = (f"**{P.METHOD_NAMES[arm]}: {txt}.**\n\n- iterations scored {pr.get('iterations_done')} of 6, "
                    f"accepted {pr.get('accepted')}; best search score {pr.get('best_search_score')} "
                    f"({pr.get('best_search_label')}); counted rollouts {pr.get('counted_rollouts')} of "
                    f"{P.BUDGET_ROLLOUTS}; optimizer proxy ${(pr.get('optimizer') or {}).get('proxy_usd')}.\n\n"
                    "Counts and aggregates only (val = train ∪ dev, 147 tasks, 1 trial: a fit metric).")
            S.append("result", "P4", f"{arm} iteration {i + 1}", f"P4 {arm}: {txt}. Counted rollouts "
                     f"{pr.get('counted_rollouts')} of {P.BUDGET_ROLLOUTS}; optimizer proxy USD "
                     f"{(pr.get('optimizer') or {}).get('proxy_usd')}; best search score (fit metric) "
                     f"{pr.get('best_search_score')}.", extra={"arm": arm, "iteration": i + 1, "verdict": r},
                     artifacts=[f"STATE/{arm}/progress.json"], subject=f"P4 {arm} iter {i + 1}")
            post.post(arm, f"iter_{i + 1}", f"{P.METHOD_NAMES[arm]} iteration {i + 1}", body)
            seen[arm] = i + 1
            P.write_json(D / "reported.json", seen)


def _diff_sha(arm: str) -> str | None:
    rd = run_dir(arm)
    for f in (rd / "prior_iterations" / "cand_0001" / "diff.patch", rd / "work" / "cand_0001" / "diff.patch"):
        if f.is_file():
            return hashlib.sha256(f.read_bytes()).hexdigest()
    c = rd / "candidates" / "cand_0001"
    if c.is_dir():
        sys.path.insert(0, str(EX / "common"))
        import evaluator as E
        return "tree:" + E.tree_hash(c)
    return None


def independence_check() -> None:
    st = P.read_json(D / "independence.json", {}) or {}
    if st.get("done"):
        return
    if not all(len(_rows(a)) >= 1 for a in P.CANDIDATES if (run_dir(a) / "events.jsonl").exists()) or \
            not all((run_dir(a) / "events.jsonl").exists() for a in P.CANDIDATES):
        return
    shas = {a: _diff_sha(a) for a in P.CANDIDATES}
    if not all(shas.values()):
        return
    identical = len(set(shas.values())) == 1
    st = {"done": True, "identical": identical, "sha_prefix": {a: s[:16] for a, s in shas.items()}, "t": P.utcnow()}
    P.write_json(D / "independence.json", st)
    if identical:
        for a in P.CANDIDATES:
            s2 = state(a)
            s2["stopped_by_decision"] = P.utcnow()
            P.write_json(D / f"{a}.json", s2)
            if alive(a):
                os.killpg(pid_of(a), signal.SIGTERM)
        S.append("decision", "P4", "arms not independent",
                 "Independence check after iteration 1 (plan 9.7, REST CP-0135): the two arms' cand_0001 candidates are "
                 "byte-identical. Both searches are stopped before iteration 2; the user is asked how to proceed.",
                 extra={"independence": st}, subject="P4 independence FAIL")
    else:
        S.append("result", "P4", "independence check",
                 "Independence check after iteration 1 (plan 9.7): the two arms' cand_0001 candidates differ "
                 f"(sha256 prefixes {st['sha_prefix']}); the searches continue.", extra={"independence": st},
                 subject="P4 independence ok")


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
            independence_check()
        except Exception as e:  # noqa: BLE001 — reporting must never stop the searches
            P.progress_log("p4", "P4", f"report error {type(e).__name__}: {e}"[:300])
        running = [a for a in P.CANDIDATES if alive(a)]
        stopped = (P.read_json(D / "independence.json", {}) or {}).get("identical")
        todo = [a for a in P.CANDIDATES if not finished(a) and not failed(a) and a not in running
                and not state(a).get("stopped_by_decision") and not (state(a).get("stopped_by_guard") and k2_stopped)]
        if not running and not todo:
            if all(finished(a) for a in P.CANDIDATES):
                S.append("phase_done", "P4", "searches done",
                         "P4 done: both chains (search, freeze, isolation scan) finished. Next: P5 dev diagnostic.",
                         done_through="P4/searches", next_unit="P5/dev", extra={"arm": None}, subject="P4 done")
            return 0
        ms = P.memstate()
        now = time.time()
        if P.paused() or ms.get("stale"):
            paused_since = paused_since or now
            if now - paused_since > 600 and cut_at is None:
                set_slots(int(P.global_slots() * 0.75), "PAUSED for more than 10 minutes")
                cut_at = now
            elif cut_at and now - paused_since > 1200 and "ce2_k2" in running and not k2_stopped:
                s2 = state("ce2_k2")
                s2["stopped_by_guard"] = P.utcnow()
                P.write_json(D / "ce2_k2.json", s2)
                os.killpg(pid_of("ce2_k2"), signal.SIGTERM)
                k2_stopped = True
                S.append("decision", "P4", "stop ce2_k2",
                         "PAUSED for more than 20 minutes: ce2_k2's search was stopped (SIGTERM); it resumes with "
                         "--resume when memory allows, and both arms still end with 6 scored iterations (rule R2).",
                         extra={"arm": "ce2_k2"}, subject="R2 stop ce2_k2")
        else:
            paused_since, cut_at = None, None
            if k2_stopped and "ce2_k2" not in running:
                k2_stopped = False          # memory is back: ce2_k2 resumes (its search step runs with --resume)
            if todo and not stopped:
                r = subprocess.run([str(Path.home() / "bin" / "memok-ce2")], capture_output=True, text=True)
                if r.returncode == 0:
                    for a in todo:          # R4: both arms in the same pass, within the same minute
                        start(a)
                    S.append("phase_start", "P4", "searches launched" if first else "search relaunched",
                             f"P4: chain(s) {', '.join(todo)} started (search, freeze, isolation scan); pid files "
                             f"AW_STATE/p4/<arm>.pid. Running now: {', '.join(a for a in P.CANDIDATES if alive(a))}. "
                             f"Global slots {P.global_slots()}; memory {P.memstate().get('used_pct')}%.",
                             extra={"arm": None}, subject="P4 launch")
                    first = False
        time.sleep(60)


def status() -> int:
    for a in P.CANDIDATES:
        print(a, "alive" if alive(a) else "-", json.dumps(state(a)))
    return 0


if __name__ == "__main__":
    a = sys.argv
    if a[1] == "mark":
        raise SystemExit(mark(a[2], a[3], int(a[4])))
    if a[1] == "status":
        raise SystemExit(status())
    raise SystemExit(loop())
