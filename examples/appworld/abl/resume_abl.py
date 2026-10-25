"""Resume the ablations from the last ledger entry (docs/ABLATIONS.md §13.4; CE2's resume_ce2.py). One command:

  . examples/appworld/abl/env.sh && python3 -I examples/appworld/abl/resume_abl.py [--dry-run] [--reason "..."]

1. fetch; fast-forward or push eval-abl; stop if diverged; drop a torn uncommitted ledger tail;
2. refuse if a pid file names a live runner (P4 runner, a P4 chain, abl_cc's session or daemon, after-P4, window);
3. container_age_s: if the pod restarted since the last entry, record it and relaunch smaller (-25% slots and one
   search fewer, R2); /tmp/aw_abl is recreated;
4. re-verify the build (abl/verify_build.py) and root_full mode 000 (unless P7 is next);
5. abl_cc: if its session started and ended, nothing; if it started but died with no result (a pod restart), it is
   NOT re-prompted (#908): an error entry, and the user is asked (fresh session from the last workdir, or freeze);
6. restart memguard (first), then the heartbeat and autopost;
7. append a `resume` entry and relaunch the phase runner: P4 -> p4_abl.py loop (each cap-evolve arm continues with
   launch_abl.sh ... --resume via run_abl.py search; evald.py restarts and finishes any accepted ticket from the
   cache); P5..P9 -> after_p4.py.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EX = HERE.parent
sys.path[:0] = [str(EX / "scripts"), str(EX / "common")]
import awrest as P  # noqa: E402
import status_doc as S  # noqa: E402

PIDS = {"p4 runner": P.AW_STATE / "p4" / "RUNNER.pid", **{f"p4 {a}": P.AW_STATE / "p4" / f"{a}.pid" for a in P.CANDIDATES},
        "abl_cc session": P.AW_STATE / "abl_cc" / "session.pid", "abl_cc evald": P.AW_STATE / "abl_cc" / "EVALD.pid",
        "after_p4": P.AW_STATE / "AFTER_P4.pid", "window": P.AW_STATE / "RUNNING.pid"}


def git(*a, check=True):
    return subprocess.run(["git", "-C", str(P.REPO), *a], capture_output=True, text=True, check=check)


def pid(p: Path):
    try:
        return int(p.read_text().split()[0])
    except (FileNotFoundError, ValueError, IndexError):
        return None


def container_age() -> int:
    up = float(Path("/proc/uptime").read_text().split()[0])
    start = int(Path("/proc/1/stat").read_text().rsplit(")", 1)[1].split()[19]) / os.sysconf("SC_CLK_TCK")
    return int(up - start)


def nohup(args: list[str], log: str) -> None:
    subprocess.Popen(["nohup", *args], stdout=open(P.PROGRESS / log, "a"), stderr=subprocess.STDOUT,
                     start_new_session=True, cwd=str(P.REPO), env=dict(os.environ))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reason", default="")
    a = ap.parse_args()
    if P.LEDGER_ID != "ABL":
        raise SystemExit("source abl/env.sh first")
    plan = []
    git("fetch", "-q", P.REMOTE, P.BRANCH, check=False)
    ab = git("rev-list", "--left-right", "--count", f"HEAD...{P.REMOTE}/{P.BRANCH}", check=False).stdout.split()
    if len(ab) == 2:
        ahead, behind = map(int, ab)
        if ahead and behind:
            raise SystemExit(f"local and {P.REMOTE}/{P.BRANCH} have diverged: stop and ask the user")
        if behind:
            plan.append(f"fast-forward {behind}")
            a.dry_run or git("merge", "--ff-only", f"{P.REMOTE}/{P.BRANCH}")
        if ahead:
            plan.append(f"push {ahead}")
            a.dry_run or git("push", "-q", P.REMOTE, f"HEAD:{P.BRANCH}")
    rel = str(P.LEDGER.relative_to(P.REPO))
    if git("diff", "--name-only", "--", rel).stdout.strip():
        plan.append("drop torn uncommitted ledger tail")
        a.dry_run or git("checkout", "--", rel)
    live = {k: pid(v) for k, v in PIDS.items() if S.pid_alive(pid(v))}
    if live:
        raise SystemExit(f"live runner(s) {live}: refusing to start a second one")
    last = S.last_entry()
    age = container_age()
    last_t = time.mktime(time.strptime(last["utc"], "%Y-%m-%dT%H:%M:%SZ")) - time.timezone
    restarted = age < time.time() - last_t
    if restarted:
        n = max(4, int(P.global_slots() * 0.75))
        plan.append(f"pod restarted (container_age {age} s): relaunch smaller, slots {P.global_slots()} -> {n}, "
                    "one search fewer at once")
        if not a.dry_run:
            P.SLOTS_DIR.mkdir(parents=True, exist_ok=True)
            P.atomic_write(P.SLOTS_DIR / "SIZE", f"{n}\n")
            P.atomic_write(P.AW_STATE / "p4" / "MAX_RUNNING", "2\n")
    P.SCRATCH.mkdir(parents=True, exist_ok=True)
    vb = subprocess.run([str(P.VENVS / "venv-abl" / "bin" / "python"), "-I", str(HERE / "verify_build.py")],
                        capture_output=True, text=True, env=dict(os.environ))
    if vb.returncode:
        raise SystemExit("verify_build.py failed: stop and ask the user (AW_STATE/build_check.json)")
    plan.append("build verified")
    cc = P.AW_STATE / "abl_cc"
    if (cc / "SESSION_STARTED").exists() and not S.pid_alive(pid(cc / "session.pid")):
        res = cc / "session_result.json"
        ended = res.is_file() and res.stat().st_size > 0 and '"type"' in res.read_text(errors="ignore")[-4000:]
        if not ended and not (cc / "SESSION_DIED_RECORDED").exists():
            plan.append("abl_cc session died with no result: not re-prompted; the user is asked (§13.4)")
            if not a.dry_run:
                S.append("error", "P4", "abl_cc session died",
                         "abl_cc's single Claude Code session ended with no result (a restart). Per plan 13.4 it is not "
                         "re-prompted. Open decision for the user: start one fresh session from the last workdir state, "
                         "or freeze as is.", extra={"arm": "abl_cc"}, subject="abl_cc died")
                (cc / "SESSION_DIED_RECORDED").write_text(P.utcnow())
    nxt = str(last.get("next") or "")
    if not nxt.startswith("P7") and (os.stat(P.ROOT_FULL).st_mode & 0o777) != 0:
        plan.append("re-lock root_full")
        a.dry_run or os.chmod(P.ROOT_FULL, 0o000)
    for name, f, args, log in (
            ("memguard", "MEMGUARD.pid", [sys.executable, "-I", str(EX / "scripts" / "memguard.py"), "loop", "--high", "90",
                                          "--low", "85", "--every", "5"], "memguard.out"),
            ("heartbeat", "HEARTBEAT.pid", [sys.executable, "-I", str(EX / "scripts" / "status_doc.py"), "heartbeat"],
             "heartbeat.out"),
            ("autopost", "AUTOPOST.pid", [sys.executable, "-I", str(EX / "scripts" / "autopost.py"), "loop", "--every",
                                          "3600"], "autopost.out")):
        if not S.pid_alive(pid(P.AW_STATE / f)):
            plan.append(f"restart {name}")
            if not a.dry_run:
                nohup(args, log)
                if name == "memguard":
                    time.sleep(7)
    phase = nxt.split("/")[0] if nxt[:1] == "P" else last.get("phase")
    runner = (["p4_abl.py", "loop"] if phase == "P4" else ["after_p4.py"] if phase in ("P5", "P6", "P7", "P8", "P9")
              else None)
    plan.append(f"continue at {nxt}: " + (" ".join(runner) if runner else "not an automatic step (run by hand)"))
    print(json.dumps({"last_cp": last.get("cp"), "next": nxt, "plan": plan, "container_age_s": age}, indent=1))
    if a.dry_run:
        return 0
    S.append("resume", last.get("phase", "?"), "resume",
             f"Resume{(' (reason: ' + a.reason + ')') if a.reason else ''}. Plan: {'; '.join(plan)}. Next: {nxt}.",
             extra={"plan": plan, "container_age_s": age, "pod_restarted": restarted}, subject="resume")
    if runner:
        nohup([sys.executable, "-I", str(HERE / runner[0]), *runner[1:]], runner[0].replace(".py", ".out"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
