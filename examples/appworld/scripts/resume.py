#!/usr/bin/env python3
"""Resume AppWorld eval 5 from the last checkpoint (docs/EVAL_APPWORLD_5.md §10.4).

  python3 -I examples/appworld/scripts/resume.py [--dry-run] [--reason "..."] [--no-launch]

1. Read the ledger: fetch origin, fast-forward if behind, push if ahead; drop a torn uncommitted tail.
2. Lock: refuse if RUNNING.pid names a live runner; remove a stale one.
3. Environment: compare manifest.json with AW_BUILD; rebuild missing B steps (build5.py); re-lock
   root_full before P8.
4. Reconcile: verify the pushed files named in the last entry against their hashes; count local records
   newer than it (each runner adopts its own: GEPA's run_dir state, SkillOpt's runtime_state.json, the
   evaluator's per-episode records, the windows' per-cell records — none is re-run or re-requested).
5. Append a `resume` entry, relaunch the phase runner (pipeline5.py) under nohup, restart the heartbeat.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aw5 as P  # noqa: E402
import status_doc as S  # noqa: E402

BEFORE_P8 = {"P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"}


def git(*a, check=True):
    return subprocess.run(["git", "-C", str(P.REPO), *a], capture_output=True, text=True, check=check)


def sync_branch(plan: list[str], dry: bool) -> None:
    git("fetch", "-q", P.REMOTE, P.BRANCH, check=False)
    ab = git("rev-list", "--left-right", "--count", f"HEAD...{P.REMOTE}/{P.BRANCH}", check=False).stdout.split()
    if len(ab) == 2:
        ahead, behind = map(int, ab)
        if behind and not ahead:
            plan.append(f"fast-forward {behind} commit(s) from origin")
            if not dry:
                git("merge", "--ff-only", f"{P.REMOTE}/{P.BRANCH}")
        elif behind and ahead:
            raise SystemExit("local and origin have diverged: stop and ask the user")
        elif ahead:
            plan.append(f"push {ahead} unpushed checkpoint commit(s)")
            if not dry:
                git("push", "-q", P.REMOTE, f"HEAD:{P.BRANCH}")
                P.write_json(S.PUSH_STATE, {"unpushed": 0})
    rel = str(P.LEDGER.relative_to(P.REPO))
    if git("diff", "--name-only", "--", rel).stdout.strip():
        plan.append("drop torn uncommitted ledger tail")
        if not dry:
            git("checkout", "--", rel)
    pushed = str(P.PUSHED.relative_to(P.REPO))
    if git("status", "--porcelain", "--", pushed).stdout.strip():
        plan.append("reset uncommitted pushed-state files to the last checkpoint")
        if not dry:
            git("checkout", "--", pushed, check=False)
            git("clean", "-fdq", "--", pushed, check=False)


def lock(plan: list[str], dry: bool) -> None:
    pid = S.runner_pid()
    if S.pid_alive(pid):
        raise SystemExit(f"a runner is alive (pid {pid}); refusing to start a second one")
    if pid:
        plan.append(f"remove stale RUNNING.pid ({pid})")
        if not dry:
            (P.AW_STATE / "RUNNING.pid").unlink(missing_ok=True)


def environment(plan: list[str], dry: bool, phase: str) -> None:
    import build5
    if P.ROOT_FULL.exists():
        os.chmod(P.ROOT_FULL, 0o755)  # check() needs to stat inside; relocked below
    missing = build5.check()
    for step in sorted(missing):
        plan.append(f"rebuild {step} ({missing[step]})")
        if not dry:
            getattr(build5, step)()
    if missing and not dry:
        again = build5.check()
        if again:
            raise SystemExit(f"rebuild did not restore {again}: stop and ask the user")
        m = P.manifest()
        if P.sha256_tree(P.ROOT_OPT) != m.get("root_opt", {}).get("tree_sha256"):
            raise SystemExit("rebuilt root_opt differs from the recorded sha256: stop and ask the user")
    if phase in BEFORE_P8 and P.ROOT_FULL.exists():
        plan.append("re-lock root_full (chmod 000)")
        if not dry:
            os.chmod(P.ROOT_FULL, 0o000)


def reconcile(last: dict, plan: list[str]) -> list[str]:
    for name, sha in (last.get("artifacts") or {}).items():
        if name.startswith("STATE/"):
            p = P.PUSHED / name[len("STATE/"):]
            if not p.exists() or P.sha256_file(p) != sha:
                raise SystemExit(f"pushed file {name} does not match the last entry: stop and ask the user")
    adopted = []
    for c in P.CANDIDATES:
        n = len(P.read_jsonl(P.AW_STATE / c / "rollouts.jsonl"))
        if n:
            adopted.append(f"{c}: {n} counted rollouts on record")
    for w in ("p6dev", "p8final"):
        d = P.AW_STATE / w / "records"
        if d.exists():
            adopted.append(f"{w}: {len(list(d.glob('*.json')))} local cell records")
    return adopted


def heartbeat_alive() -> bool:
    try:
        return S.pid_alive(int((P.AW_STATE / "HEARTBEAT.pid").read_text().strip()))
    except (FileNotFoundError, ValueError):
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reason", default="")
    ap.add_argument("--no-launch", action="store_true")
    a = ap.parse_args()
    P.AW_STATE.mkdir(parents=True, exist_ok=True)
    P.PROGRESS.mkdir(parents=True, exist_ok=True)
    plan: list[str] = []
    sync_branch(plan, a.dry_run)
    last = S.last_entry()
    lock(plan, a.dry_run)
    environment(plan, a.dry_run, last.get("phase", "P0"))
    adopted = reconcile(last, plan)
    nxt = last.get("next")
    import pipeline5
    runnable = pipeline5.step_of(nxt or "") is not None
    plan.append(f"continue at next = {nxt}" + ("" if runnable else " (not an automatic step: run it by hand)"))
    if not heartbeat_alive() and not a.no_launch:
        plan.append("restart the heartbeat loop")
    print(json.dumps({"last_cp": last.get("cp"), "phase": last.get("phase"), "next": nxt, "plan": plan,
                      "adopted": adopted}, indent=1))
    if a.dry_run:
        return 0
    S.append("resume", last.get("phase", "?"), "resume",
             f"Resume{(' (reason: ' + a.reason + ')') if a.reason else ''}. Plan: {'; '.join(plan)}.\n"
             f"Local work on record: {', '.join(adopted) or 'none'}.\nNext: {nxt}.",
             extra={"adopted": adopted, "plan": plan}, subject="resume")
    if not heartbeat_alive() and not a.no_launch:
        subprocess.Popen(["nohup", sys.executable, "-I", str(Path(__file__).parent / "status_doc.py"), "heartbeat"],
                         stdout=open(P.PROGRESS / "heartbeat.out", "a"), stderr=subprocess.STDOUT,
                         start_new_session=True, cwd=str(P.REPO))
    try:
        ap_alive = S.pid_alive(int((P.AW_STATE / "AUTOPOST.pid").read_text().strip()))
    except (FileNotFoundError, ValueError):
        ap_alive = False
    if not ap_alive and not a.no_launch:  # periodic per-candidate issue updates (user decision D9)
        subprocess.Popen(["nohup", sys.executable, "-I", str(Path(__file__).parent / "autopost5.py"), "loop", "--every", "3600"],
                         stdout=open(P.PROGRESS / "autopost.out", "a"), stderr=subprocess.STDOUT,
                         start_new_session=True, cwd=str(P.REPO))
    try:
        mg_alive = S.pid_alive(int((P.AW_STATE / "MEMGUARD.pid").read_text().strip()))
    except (FileNotFoundError, ValueError):
        mg_alive = False
    if not mg_alive and not a.no_launch:  # memory watermarks: pause new episodes at 90%, resume below 80%
        subprocess.Popen(["nohup", sys.executable, "-I", str(Path(__file__).parent / "memguard5.py"), "loop",
                          "--high", "90", "--low", "80"], stdout=open(P.PROGRESS / "memguard.out", "a"),
                         stderr=subprocess.STDOUT, start_new_session=True, cwd=str(P.REPO))
    if runnable and not a.no_launch:
        subprocess.Popen(["nohup", str(P.VENV_PY), "-I", str(Path(__file__).parent / "pipeline5.py")],
                         stdout=open(P.PROGRESS / "pipeline.out", "a"), stderr=subprocess.STDOUT,
                         start_new_session=True, env=P.setup_env(dict(os.environ)), cwd=str(P.REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
