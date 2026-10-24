#!/usr/bin/env python3
"""Resume TEST_ALL from the last ledger entry (docs/TEST_ALL.md §10). One command:

  . examples/appworld/test_all/env.sh && python3 -I examples/appworld/test_all/resume.py [--dry-run] [--no-launch]
                                                                                       [--reason "..."] [--window]

1. git fetch origin test-all; fast-forward or push; stop if diverged.
2. Refuse if AW_STATE/RUNNING.pid names a live process (the pid is checked; never pgrep -f).
3. If container_age_s (memcheck) is shorter than the time since the last ledger entry, the pod restarted: record it
   and shrink the slot pool by 25% (AW_STATE/slots/SIZE).
4. Re-verify the build symlinks, root_full mode (000), and every artifact's hash by its own rule (§6.3).
5. Restart memguard first, then the heartbeat and autopost (which posts at once on any issue older than 60 min).
6. Append a `resume` entry; with --window (or when the last entry's `next` is the window), relaunch the window
   runner under nohup; it skips cells that have records.
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
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))
import awrest as P  # noqa: E402
import status_doc as S  # noqa: E402

REST_BUILD = Path("/workspace/aw_rest/build")
LINKS = ("appworld", "root_full", "root_opt", "reference", "clones", "venvs/venv-aw")


def git(*a, check=True):
    return subprocess.run(["git", "-C", str(P.REPO), *a], capture_output=True, text=True, check=check)


def sync(plan, dry):
    git("fetch", "-q", "origin", P.BRANCH, check=False)
    ab = git("rev-list", "--left-right", "--count", f"HEAD...origin/{P.BRANCH}", check=False).stdout.split()
    if len(ab) == 2:
        ahead, behind = map(int, ab)
        if ahead and behind:
            raise SystemExit("local and origin/test-all have diverged: stop and ask the user")
        if behind:
            plan.append(f"fast-forward {behind} commit(s)")
            dry or git("merge", "--ff-only", f"origin/{P.BRANCH}")
        elif ahead:
            plan.append(f"push {ahead} commit(s)")
            if not dry:
                git("push", "-q", "origin", f"HEAD:{P.BRANCH}")
                P.write_json(S.PUSH_STATE, {"unpushed": 0})
    rel = str(P.LEDGER.relative_to(P.REPO))
    if git("diff", "--name-only", "--", rel).stdout.strip():
        plan.append("drop a torn uncommitted ledger tail")
        dry or git("checkout", "--", rel)


def alive(name: str) -> bool:
    try:
        return S.pid_alive(int((P.AW_STATE / name).read_text().split()[0]))
    except (FileNotFoundError, ValueError, IndexError):
        return False


def memcheck() -> dict:
    out = subprocess.run([str(Path.home() / "bin" / "memcheck")], capture_output=True, text=True).stdout
    d = {}
    for tok in out.split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            d[k] = v
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-launch", action="store_true")
    ap.add_argument("--window", action="store_true")
    ap.add_argument("--reason", default="")
    a = ap.parse_args()
    plan: list[str] = []
    sync(plan, a.dry_run)
    if alive("RUNNING.pid"):
        raise SystemExit("a window runner is alive (RUNNING.pid); refusing to start a second one")
    if (P.AW_STATE / "RUNNING.pid").exists():
        plan.append("remove the stale RUNNING.pid")
        a.dry_run or (P.AW_STATE / "RUNNING.pid").unlink()
    last = S.last_entry()
    mc = memcheck()
    since = time.time() - time.mktime(time.strptime(last["utc"], "%Y-%m-%dT%H:%M:%SZ")) + time.timezone \
        if last.get("utc") else 0
    restarted = int(mc.get("container_age_s", 1e12)) < since
    if restarted:
        new = max(1, int(P.global_slots() * 0.75))
        plan.append(f"pod restarted (container_age_s {mc.get('container_age_s')} < {int(since)} s since the last entry): "
                    f"slots {P.global_slots()} -> {new}")
        if not a.dry_run:
            P.SLOTS_DIR.mkdir(parents=True, exist_ok=True)
            (P.SLOTS_DIR / "SIZE").write_text(f"{new}\n")
    bad_links = [n for n in LINKS if not ((P.AW_BUILD / n).is_symlink()
                                         and os.readlink(P.AW_BUILD / n) == str(REST_BUILD / n))]
    if bad_links:
        raise SystemExit(f"build symlinks wrong or missing: {bad_links}: stop and ask the user")
    mode = os.stat(P.ROOT_FULL).st_mode & 0o777
    if mode != 0:
        plan.append(f"root_full was {oct(mode)}: relocked to 000")
        a.dry_run or os.chmod(P.ROOT_FULL, 0o000)
    import fetch_artifacts as FA
    bad = FA.check_scored(P.manifest().get("artifacts") or {})
    if bad:
        raise SystemExit(f"artifact hash check failed for {bad}: stop and ask the user")
    plan.append("13 artifacts re-verified by their own hash rules")
    n_rec = len(list((P.AW_STATE / "final" / "records").glob("*.json"))) if (P.AW_STATE / "final" / "records").exists() else 0
    launch = not a.no_launch and not a.dry_run
    for name, cmd in (("MEMGUARD.pid", ["memguard.py", "loop", "--high", "90", "--low", "85", "--every", "5"]),
                      ("HEARTBEAT.pid", ["status_doc.py", "heartbeat", "--every", "60"]),
                      ("AUTOPOST.pid", ["autopost.py", "loop"])):
        if not alive(name):
            plan.append(f"restart {cmd[0]}")
            if launch:
                subprocess.Popen(["nohup", sys.executable, "-I", str(HERE.parent / "scripts" / cmd[0]), *cmd[1:]],
                                 stdout=open(P.PROGRESS / (cmd[0].split(".")[0] + ".out"), "a"),
                                 stderr=subprocess.STDOUT, start_new_session=True, cwd=str(P.REPO))
                if name == "MEMGUARD.pid":
                    time.sleep(7)
    win = a.window or str(last.get("next") or "").startswith("P3/window")
    if win:
        plan.append(f"relaunch the window runner ({n_rec} cell records on disk are kept, not re-run)")
    print(json.dumps({"last": f"{P.LEDGER_ID}-{int(last.get('cp', 0)):04d}", "next": last.get("next"), "plan": plan,
                      "records": n_rec, "restarted": restarted}, indent=1))
    if a.dry_run:
        return 0
    S.append("resume", last.get("phase", "?"), "resume",
             f"Resume{(' (' + a.reason + ')') if a.reason else ''}. Plan: {'; '.join(plan)}. Window records on disk: "
             f"{n_rec}. Next: {last.get('next')}.", extra={"plan": plan, "restarted": restarted}, subject="resume")
    if win and launch:
        launch_window()
    return 0


def launch_window() -> int:
    log = open(P.PROGRESS / "window.out", "a")
    p = subprocess.Popen(["nohup", str(P.VENV_PY), "-I", str(HERE.parent / "scripts" / "window.py"), "final"],
                         stdout=log, stderr=subprocess.STDOUT, start_new_session=True, cwd=str(P.REPO),
                         env=P.setup_env(dict(os.environ)))
    return p.pid


if __name__ == "__main__":
    raise SystemExit(main())
