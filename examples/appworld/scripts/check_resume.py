"""A9 and A10: resume and publishing tests against a throwaway clone, status file and branch
(`acceptance/status-test`, deleted afterwards). Dev ids only; nothing is counted.

  python3 -I check_resume.py a9     ACE loop on 4 dev tasks, SIGKILLed after episode.json, after
                                    reflector.json and mid status-append; resumed each time; then a
                                    fresh clone with AW_STATE deleted resumes the step in progress.
  python3 -I check_resume.py a10    12-cell mini window, killed and resumed; coalescing (1-min
                                    setting); heartbeat after 1 min marks a killed runner stalled; a push
                                    failure is pushed by the next checkpoint; the content filter refuses
                                    a task id and an .env string.
  python3 -I check_resume.py cleanup
Prints flags and counts only.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "scripts"))
import awpaths as P  # noqa: E402

TEST_BRANCH = "acceptance/status-test"
BASE = P.AW_HOME / "acceptance_resume"
ORIGIN = subprocess.run(["git", "-C", str(P.REPO), "remote", "get-url", "origin"], capture_output=True,
                        text=True).stdout.strip()
HEADER = ("# Throwaway status file for acceptance tests A9/A10 (plan §11). Deleted after the test.\n\n"
          "Content rules as in docs/EVAL_SMOKE_TEST_ACE_STATUS.md.\n\n---\n")


def sh(*a, cwd=None, env=None, check=True):
    return subprocess.run(list(a), cwd=cwd, env=env, capture_output=True, text=True, check=check)


def test_env(clone: Path, state: Path, ledger_name: str) -> dict:
    return {**os.environ, "AW_REPO": str(clone), "AW_STATE": str(state), "AW_BRANCH": TEST_BRANCH,
            "AW_LEDGER_NAME": ledger_name, "HF_HOME": str(P.HF_HOME), "HF_HUB_OFFLINE": "1",
            "ACE_CALLS_LOG": str(state / "ace" / "llm_calls.jsonl"), "AW_ENV_FILE": str(P.ENV_FILE)}


def fresh_clone(dest: Path, create: bool) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    if create:
        sh("git", "clone", "-q", "--branch", P.BRANCH, ORIGIN, str(dest))
        sh("git", "checkout", "-q", "-b", TEST_BRANCH, cwd=dest)
    else:
        sh("git", "clone", "-q", "--branch", TEST_BRANCH, ORIGIN, str(dest))
    sh("git", "config", "user.email", "devagent@localhost", cwd=dest)
    sh("git", "config", "user.name", "devagent", cwd=dest)


def init_ledger(clone: Path, name: str, env: dict) -> None:
    led = clone / "docs" / name
    led.write_text(HEADER)
    state_dir = clone / "docs" / (Path(name).stem.removesuffix("_STATUS") + "_STATE")
    state_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(P.PUSHED / "manifest.json", state_dir / "manifest.json")
    sh("python3", "-I", str(clone / "examples/appworld/scripts/status_doc.py"), "append", "--kind", "phase_start",
       "--phase", "TEST", "--label", "test", "--prose", "Throwaway ledger for an acceptance test.", "--next",
       "ace/step/001/episode", cwd=clone, env=env)


def added_only(clone: Path, name: str) -> bool:
    log = sh("git", "log", "-p", "--format=", "--", f"docs/{name}", cwd=clone).stdout
    removed = [l for l in log.splitlines() if l.startswith("-") and not l.startswith("---")]
    return not removed


def pushed(clone: Path) -> bool:
    sh("git", "fetch", "-q", "origin", TEST_BRANCH, cwd=clone)
    return sh("git", "rev-parse", "HEAD", cwd=clone).stdout == sh("git", "rev-parse", f"origin/{TEST_BRANCH}", cwd=clone).stdout


# ------------------------------------------------------------------ A9

def ace_cmd(clone: Path, state: Path, name: str) -> list[str]:
    st = clone / "docs" / (Path(name).stem.removesuffix("_STATUS") + "_STATE")
    return [str(P.VENV_PY), "-I", str(clone / "examples/appworld/ace/run_ace.py"), "--split", "dev", "--limit", "4",
            "--ace-dir", str(state / "ace"), "--pushed-dir", str(st / "ace"), "--exp-prefix", "a9", "--trial-name", "a9"]


def run_until(cmd, env, cwd, cond, timeout=3600) -> str:
    """Start cmd; SIGKILL it as soon as cond() is true. Returns 'killed' or 'exited'."""
    p = subprocess.Popen(cmd, env=env, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    t0 = time.time()
    while p.poll() is None and time.time() - t0 < timeout:
        if cond():
            os.killpg(p.pid, signal.SIGKILL)
            p.wait()
            return "killed"
        time.sleep(0.5)
    return "exited"


def resume(clone: Path, env: dict) -> dict:
    r = sh("python3", "-I", str(clone / "examples/appworld/scripts/resume.py"), "--no-launch", "--reason", "A9 test",
           cwd=clone, env=env, check=False)
    return {"rc": r.returncode, "out": r.stdout[-400:], "err": r.stderr[-300:]}


def a9() -> dict:
    name = "A9_TEST_STATUS.md"
    clone, state = BASE / "a9_repo", BASE / "a9_state"
    for d in (clone, state):
        if d.exists():
            shutil.rmtree(d)
    state.mkdir(parents=True)
    fresh_clone(clone, create=True)
    env = test_env(clone, state, name)
    init_ledger(clone, name, env)
    steps = state / "ace" / "steps"
    led = clone / "docs" / name
    res = {"kills": [], "resumes": []}
    # kill 1: after step 001 episode.json
    res["kills"].append(run_until(ace_cmd(clone, state, name), env, clone, lambda: (steps / "001/episode.json").exists()))
    res["resumes"].append(resume(clone, env))
    # kill 2: after step 002 reflector.json (or step 002 skipped curation: then after 003)
    def refl():
        return any((steps / f"{i:03d}/reflector.json").exists() for i in (2, 3))
    res["kills"].append(run_until(ace_cmd(clone, state, name), env, clone, refl))
    res["resumes"].append(resume(clone, env))
    # kill 3: mid status append (the ledger is modified but not committed)
    env3 = {**env, "AW_TEST_APPEND_PAUSE": "15"}
    def mid_append():
        return bool(sh("git", "diff", "--name-only", "--", f"docs/{name}", cwd=clone).stdout.strip())
    res["kills"].append(run_until(ace_cmd(clone, state, name), env3, clone, mid_append))
    res["torn_tail_before_resume"] = mid_append()
    res["resumes"].append(resume(clone, env))
    res["torn_tail_after_resume"] = mid_append()
    # kill 4: once step 003 is applied and step 004's episode has started -> host loss simulation
    prog = clone / "docs" / "A9_TEST_STATE" / "ace" / "progress.json"
    def three_applied():
        return prog.exists() and json.loads(prog.read_text())["last_applied_step"] >= 3
    run_until(ace_cmd(clone, state, name), env, clone, three_applied)
    calls_before_loss = (state / "ace" / "llm_calls.jsonl").read_text().splitlines()
    sh("git", "push", "-q", "origin", f"HEAD:{TEST_BRANCH}", cwd=clone, check=False)
    lost_state = BASE / "a9_state_lost"
    if lost_state.exists():
        shutil.rmtree(lost_state)
    state.rename(lost_state)  # AW_STATE deleted (kept aside only to compare)
    clone2 = BASE / "a9_repo_fresh"
    fresh_clone(clone2, create=False)
    state.mkdir(parents=True)
    env2 = test_env(clone2, state, name)
    res["fresh_resume"] = resume(clone2, env2)
    res["restored_pb"] = (state / "ace" / "playbooks" / "pb_003.txt").exists()
    rc = subprocess.run(ace_cmd(clone2, state, name), env=env2, cwd=clone2, capture_output=True, text=True)
    res["final_run_rc"] = rc.returncode
    # checks
    p2 = json.loads((clone2 / "docs/A9_TEST_STATE/ace/progress.json").read_text())
    res["steps_done"] = p2["last_applied_step"]
    calls = [json.loads(l) for l in calls_before_loss] + \
            [json.loads(l) for l in (state / "ace" / "llm_calls.jsonl").read_text().splitlines()] \
        if (state / "ace" / "llm_calls.jsonl").exists() else [json.loads(l) for l in calls_before_loss]
    per = {}
    for c in calls:
        per[(c["role"], c["step"])] = per.get((c["role"], c["step"]), 0) + 1
    res["repeated_paid_calls"] = sum(v - 1 for v in per.values() if v > 1)
    res["calls_after_host_loss_steps"] = sorted({c["step"] for c in calls[len(calls_before_loss):]})
    # replay: an uninterrupted apply from the same stored sub-steps gives the same final playbook
    replay = BASE / "a9_replay"
    if replay.exists():
        shutil.rmtree(replay)
    (replay / "ace" / "steps").mkdir(parents=True)
    for src_state in (lost_state, state):
        for d in sorted((src_state / "ace" / "steps").glob("*")):
            dst = replay / "ace" / "steps" / d.name
            if dst.exists() and d.name != "004":
                continue
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(d, dst)
            (dst / "apply.json").unlink(missing_ok=True)
    env_r = test_env(clone2, replay, name)
    n_before = len(calls)
    rr = subprocess.run([str(P.VENV_PY), "-I", str(clone2 / "examples/appworld/ace/run_ace.py"), "--split", "dev",
                         "--limit", "4", "--ace-dir", str(replay / "ace"), "--pushed-dir", str(replay / "pushed"),
                         "--no-ledger", "--exp-prefix", "a9r", "--trial-name", "a9r"], env=env_r, capture_output=True, text=True)
    replay_calls = len((replay / "ace" / "llm_calls.jsonl").read_text().splitlines()) if (replay / "ace" / "llm_calls.jsonl").exists() else 0
    a = (state / "ace" / "playbooks" / "pb_004.txt")
    b = (replay / "ace" / "playbooks" / "pb_004.txt")
    res["replay_rc"] = rr.returncode
    res["replay_new_calls"] = replay_calls
    res["final_equals_uninterrupted"] = a.exists() and b.exists() and a.read_text() == b.read_text()
    res["append_only"] = added_only(clone2, name)
    res["pushed"] = pushed(clone2)
    res["kills"] = res["kills"]
    res["ok"] = (res["kills"] == ["killed"] * 3 and all(r["rc"] == 0 for r in res["resumes"]) and
                 res["torn_tail_before_resume"] and not res["torn_tail_after_resume"] and
                 res["fresh_resume"]["rc"] == 0 and res["restored_pb"] and res["final_run_rc"] == 0 and
                 res["steps_done"] == 4 and res["repeated_paid_calls"] == 0 and res["replay_new_calls"] == 0 and
                 res["final_equals_uninterrupted"] and res["append_only"] and res["pushed"] and
                 set(res["calls_after_host_loss_steps"]) <= {4})
    for k in ("resumes", "fresh_resume"):
        res[k] = [{"rc": r["rc"]} for r in res[k]] if isinstance(res[k], list) else {"rc": res[k]["rc"]}
    return res


# ------------------------------------------------------------------ A10

def a10() -> dict:
    name = "A10_TEST_STATUS.md"
    clone, state = BASE / "a10_repo", BASE / "a10_state"
    for d in (clone, state):
        if d.exists():
            shutil.rmtree(d)
    state.mkdir(parents=True)
    # reuse the test branch if A9 created it, else create it
    exists = sh("git", "ls-remote", "--heads", ORIGIN, TEST_BRANCH).stdout.strip()
    fresh_clone(clone, create=not exists)
    env = test_env(clone, state, name)
    init_ledger(clone, name, env)
    res = {}
    code = r'''
import os, sys, json
sys.path.insert(0, os.environ["EXS"]); sys.path.insert(0, os.environ["EXA"])
import awpaths as P, window, adapter, shutil
from pathlib import Path
ids = adapter.tasks("dev")[13:19]
order = window.make_order(ids, ["seed", "ace"], 1, 804010)
cap = P.AW_STATE / "cap_ace"
if not cap.exists():
    shutil.copytree(P.EXAMPLE / "seed_capability", cap)
    (cap / "memory" / "playbook.md").write_text((P.EXAMPLE / "ace/vendor/playbooks/appworld_initial_playbook.txt").read_text())
(P.AW_STATE / "order.json").write_text(json.dumps(order))
(P.AW_STATE / "RUNNING.pid").write_text(f"{os.getpid()} a10\n")
w = window.Window("a10mini", "TEST", "mini window", order, {"seed": P.EXAMPLE / "seed_capability", "ace": cap},
                  P.AW_STATE / "records", seed_base=100, final=False, workers=3, max_infra_retries=1, coalesce_s=60,
                  pushed_rows_csv=P.PUSHED / "dev" / "cells.csv", next_unit_done="TEST/done", trial_name="a10")
w.run()
'''
    env_w = {**env, "EXS": str(clone / "examples/appworld/scripts"), "EXA": str(clone / "examples/appworld/adapters")}
    recs = state / "records"
    # run until >= 4 cells done, SIGKILL
    p = subprocess.Popen([str(P.VENV_PY), "-I", "-c", code], env=env_w, cwd=str(state), start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    while p.poll() is None and len(list(recs.glob("*.json"))) < 4:
        time.sleep(2)
    done_before = {int(x.stem): x.stat().st_mtime for x in recs.glob("*.json")}
    os.killpg(p.pid, signal.SIGKILL)
    p.wait()
    res["killed_after_cells"] = len(done_before)
    # heartbeat after 1 min of silence marks the killed runner stalled
    time.sleep(65)
    hb = sh("python3", "-I", str(clone / "examples/appworld/scripts/status_doc.py"), "heartbeat", "--once",
            "--silence", "60", cwd=clone, env=env)
    led = (clone / "docs" / name).read_text()
    res["heartbeat_written"] = hb.stdout.strip() == "True"
    res["heartbeat_stalled"] = '"runner": "stalled"' in led.split("## CP-")[-1]
    # resume the window
    rc = subprocess.run([str(P.VENV_PY), "-I", "-c", code], env=env_w, cwd=str(state), capture_output=True, text=True)
    done_after = {int(x.stem): x.stat().st_mtime for x in recs.glob("*.json")}
    res["cells_done"] = len(done_after)
    res["no_cell_rerun"] = all(done_after[i] == t for i, t in done_before.items())
    order = json.loads((state / "order.json").read_text())
    res["order_recorded"] = sorted(done_after) == list(range(12)) and len(order) == 12
    # coalescing: result entries of this window at least ~60 s apart
    import re
    ts = [m for m in re.findall(r'"utc": "([^"]+)", "kind": "(?:result|phase_done)", "phase": "TEST"', led + (clone / "docs" / name).read_text())]
    import datetime as dt
    tt = sorted({dt.datetime.strptime(x, "%Y-%m-%dT%H:%M:%SZ") for x in ts})
    gaps = [(b - a).total_seconds() for a, b in zip(tt, tt[1:])]
    res["coalesced_entries"] = len(tt)
    res["min_gap_s"] = min(gaps) if gaps else None
    res["coalesced_ok"] = all(g >= 55 for g in gaps[:-1]) if len(gaps) > 1 else True
    # push failure: a bad remote URL leaves a local commit; the next checkpoint pushes both
    sh("git", "remote", "set-url", "origin", "git@github.com:invalid/does-not-exist.git", cwd=clone)
    sh("python3", "-I", str(clone / "examples/appworld/scripts/status_doc.py"), "append", "--kind", "result", "--phase",
       "TEST", "--label", "test", "--prose", "Push-failure test entry.", cwd=clone, env=env)
    ps = json.loads((state / "ledger_push.json").read_text())
    res["push_failure_recorded"] = ps.get("unpushed") == 1
    sh("git", "remote", "set-url", "origin", ORIGIN, cwd=clone)
    sh("python3", "-I", str(clone / "examples/appworld/scripts/status_doc.py"), "append", "--kind", "result", "--phase",
       "TEST", "--label", "test", "--prose", "Entry after the push failure.", cwd=clone, env=env)
    res["next_checkpoint_pushed_both"] = pushed(clone) and json.loads((state / "ledger_push.json").read_text()).get("unpushed") == 0
    res["push_note_in_entry"] = "were not pushed" in (clone / "docs" / name).read_text().split("## CP-")[-1]
    # content filter
    dev_id = json.loads(P.LINT_CACHE.read_text())["task_ids"][0]
    env_val = next(v for v in P.read_env_file().values() if len(v) >= 8)
    refusals = []
    for txt in (f"leak {dev_id}", f"leak {env_val}"):
        r = sh("python3", "-I", str(clone / "examples/appworld/scripts/status_doc.py"), "append", "--kind", "result",
               "--phase", "TEST", "--label", "test", "--prose", txt, cwd=clone, env=env, check=False)
        refusals.append(r.returncode != 0 and "refused" in r.stderr)
    res["filter_refuses_task_id"], res["filter_refuses_env"] = refusals
    res["append_only"] = added_only(clone, name)
    res["ok"] = (res["heartbeat_written"] and res["heartbeat_stalled"] and res["cells_done"] == 12 and
                 res["no_cell_rerun"] and res["order_recorded"] and res["coalesced_ok"] and
                 res["push_failure_recorded"] and res["next_checkpoint_pushed_both"] and res["push_note_in_entry"] and
                 all(refusals) and res["append_only"])
    return res


def cleanup() -> dict:
    r = sh("git", "push", "-q", ORIGIN, "--delete", TEST_BRANCH, check=False)
    if BASE.exists():
        shutil.rmtree(BASE)
    return {"branch_deleted": r.returncode == 0, "ok": True}


def main() -> int:
    res = {"a9": a9, "a10": a10, "cleanup": cleanup}[sys.argv[1]]()
    (P.AW_STATE / "acceptance").mkdir(parents=True, exist_ok=True)
    P.write_json(P.AW_STATE / "acceptance" / f"{sys.argv[1]}.json", res)
    print(json.dumps(res))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
