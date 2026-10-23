"""Resume eval CE2 from the last ledger entry (docs/EVAL_APPWORLD_CE2.md §14.4). One command:

  . examples/appworld/ce2/env.sh && python3 -I examples/appworld/ce2/resume_ce2.py [--dry-run] [--reason "..."]

1. fetch; fast-forward or push eval-ce2; stop if diverged; drop a torn uncommitted ledger tail;
2. refuse if a pid file names a live runner (P4 runner, a P4 chain, the after-P4 chain, the window); never pgrep -f;
3. container_age_s: if the pod restarted since the last entry, record it and apply R2's "relaunch smaller" (-25% slots);
4. re-verify the build symlinks and root_full mode 000 (unless P7 is running/next);
5. restart memguard (first), then the heartbeat and autopost;
6. append a `resume` entry and relaunch the phase runner: P4 -> p4_ce2.py loop (each arm continues through
   launch_ce2.sh ... --resume via run_ce2.py search); P5..P9 -> after_p4.py. Cached episodes are free on resume.
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

PIDS = {"p4 runner": P.AW_STATE / "p4" / "RUNNER.pid", "p4 ce2_k1": P.AW_STATE / "p4" / "ce2_k1.pid",
        "p4 ce2_k2": P.AW_STATE / "p4" / "ce2_k2.pid", "after_p4": P.AW_STATE / "AFTER_P4.pid",
        "window": P.AW_STATE / "RUNNING.pid"}


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
    if P.LEDGER_PREFIX != "CE2":
        raise SystemExit("source ce2/env.sh first")
    plan = []
    git("fetch", "-q", "origin", P.BRANCH, check=False)
    ab = git("rev-list", "--left-right", "--count", f"HEAD...origin/{P.BRANCH}", check=False).stdout.split()
    if len(ab) == 2:
        ahead, behind = map(int, ab)
        if ahead and behind:
            raise SystemExit("local and origin eval-ce2 have diverged: stop and ask the user")
        if behind:
            plan.append(f"fast-forward {behind}")
            a.dry_run or git("merge", "--ff-only", f"origin/{P.BRANCH}")
        if ahead:
            plan.append(f"push {ahead}")
            a.dry_run or git("push", "-q", "origin", f"HEAD:{P.BRANCH}")
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
        plan.append(f"pod restarted (container_age {age} s): relaunch smaller, slots {P.global_slots()} -> {n}")
        if not a.dry_run:
            P.SLOTS_DIR.mkdir(parents=True, exist_ok=True)
            P.atomic_write(P.SLOTS_DIR / "SIZE", f"{n}\n")
    for name in ("appworld", "root_opt", "root_full", "reference", "clones", "venvs/venv-aw"):
        q = P.AW_BUILD / name
        if not (q.is_symlink() and os.readlink(q) == f"/workspace/aw_rest/build/{name}"):
            raise SystemExit(f"build symlink {q} is wrong or missing: stop and ask the user")
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
    runner = (["p4_ce2.py", "loop"] if phase == "P4" else ["after_p4.py"] if phase in ("P5", "P6", "P7", "P8", "P9")
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
