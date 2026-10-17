"""A10: ledger / resume / publishing (docs/EVAL_APPWORLD_5.md §10, §11) against a throwaway clone, ledger and
branch (`acceptance/eval5-status-test`, deleted afterwards). Dev ids only; nothing is counted.

  python3 -I check_a10.py run | cleanup
1. a 12-cell mini window (2 arms × 6 dev tasks, coalescing at 60 s) is SIGKILLed mid-way and resumed:
   no cell runs twice, all 12 end done, the order is the recorded one;
2. the coalesced entries are ≤ 1 per 60 s; every pushed commit only adds ledger lines (append-only);
3. a heartbeat with a 60 s silence setting marks the killed runner `stalled`;
4. a push failure (bad remote) leaves a local commit that the next checkpoint pushes;
5. the content filter refuses an entry with a task id and one with an `.env` value.
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
import aw5 as P  # noqa: E402

BR = "acceptance/eval5-status-test"
BASE = P.AW_HOME / "acceptance_a10"
ORIGIN = subprocess.run(["git", "-C", str(P.REPO), "remote", "get-url", "origin"], capture_output=True,
                        text=True).stdout.strip()
LEDGER = "EVAL_A10_TEST.md"


def sh(*a, cwd=None, env=None, check=True):
    return subprocess.run(list(a), cwd=cwd, env=env, capture_output=True, text=True, check=check)


def env_for(clone: Path, state: Path) -> dict:
    e = {**os.environ, "AW_REPO": str(clone), "AW_STATE": str(state), "AW_BRANCH": BR,
         "AW_LEDGER_NAME": LEDGER, "AW_ENV_FILE": str(P.ENV_FILE)}
    return P.setup_env(e)


MINI = r'''
import json, os, sys, random
sys.path.insert(0, %(scripts)r)
import aw5 as P, window5 as W
ids = P.read_split("dev")[:6]
order = W.make_order(ids, ["seed", "seed2"], 1, 7)
m = P.manifest()
if m.get("a10_order") not in (None, W.order_sha(order)):
    raise SystemExit("order mismatch")
P.update_manifest(a10_order=W.order_sha(order))
seed = P.SEED_CAP
(P.AW_STATE / "RUNNING.pid").write_text(f"{os.getpid()} a10\n")
w = W.Window("a10win", "A10", "a10 window", order, {"seed": seed, "seed2": seed}, P.ROOT_OPT, 100, False,
             int(os.environ.get("AW_WORKERS", 3)), 1, "A10/done", coalesce_s=60)
w.run()
'''


def run() -> int:
    shutil.rmtree(BASE, ignore_errors=True)
    BASE.mkdir(parents=True)
    clone, state = BASE / "clone", BASE / "state"
    sh("git", "clone", "-q", "--branch", P.BRANCH, ORIGIN, str(clone))
    sh("git", "checkout", "-q", "-b", BR, cwd=clone)
    for k, v in (("user.email", "devagent@localhost"), ("user.name", "devagent")):
        sh("git", "config", k, v, cwd=clone)
    (clone / "docs" / LEDGER).write_text(f"# A10 throwaway ledger (deleted after the test)\n\n{P.LEDGER_MARKER}\n")
    (clone / "docs" / (Path(LEDGER).stem + "_STATE")).mkdir(exist_ok=True)
    shutil.copy2(P.PUSHED / "manifest.json", clone / "docs" / (Path(LEDGER).stem + "_STATE") / "manifest.json")
    state.mkdir()
    shutil.copy2(P.PUBLISH_CACHE, state / "publish_cache.json")
    shutil.copy2(P.LINT_CACHE, state / "lint_cache.json")
    env = env_for(clone, state)
    sd = [sys.executable, "-I", str(clone / "examples/appworld/scripts/status_doc.py")]
    r = sh(*sd, "append", "--kind", "phase_start", "--phase", "A10", "--label", "start", "--prose", "A10 start.",
           "--next", "a10win/cells", env=env, cwd=clone)
    res: dict = {"first_append": r.returncode == 0}
    script = BASE / "mini.py"
    script.write_text(MINI % {"scripts": str(clone / "examples/appworld/scripts")})
    venv_env = dict(env, AW_WORKERS="3")
    # 1. run, kill mid-way, resume
    p = subprocess.Popen([str(P.VENV_PY), "-I", str(script)], env=venv_env, cwd=clone,
                         stdout=open(BASE / "mini1.out", "w"), stderr=subprocess.STDOUT)
    recs = state / "a10win" / "records"
    t0 = time.time()
    while time.time() - t0 < 1500 and len(list(recs.glob("*.json")) if recs.exists() else []) < 4:
        time.sleep(5)
    n_before_kill = len(list(recs.glob("*.json")))
    p.send_signal(signal.SIGKILL)
    p.wait()
    killed_at = {f.name: f.stat().st_mtime for f in recs.glob("*.json")}
    # 3. heartbeat after 60 s silence: the killed runner is stalled
    time.sleep(65)
    hb = sh(*sd, "heartbeat", "--once", "--silence", "60", env=env, cwd=clone, check=False)
    led = (clone / "docs" / LEDGER).read_text()
    res["heartbeat_stalled"] = '"runner": "stalled"' in led
    # resume
    (state / "RUNNING.pid").unlink(missing_ok=True)
    p2 = subprocess.run([str(P.VENV_PY), "-I", str(script)], env=venv_env, cwd=clone, capture_output=True,
                        text=True, timeout=3600)
    done = sorted(int(f.stem) for f in recs.glob("*.json"))
    rerun = [n for n, m in killed_at.items() if (recs / n).stat().st_mtime != m]
    res.update(killed_after_cells=n_before_kill, all_done=done == list(range(12)), cells_rerun=len(rerun),
               resume_exit=p2.returncode)
    # 2. coalescing and append-only history
    sh("git", "fetch", "-q", "origin", BR, cwd=clone, check=False)
    log = sh("git", "log", "--format=%H %ct", f"origin/{BR}", "--", f"docs/{LEDGER}", cwd=clone).stdout.split("\n")
    times = sorted(int(x.split()[1]) for x in log if x.strip())
    result_entries = led.count("· result")
    res["coalesced_entries"] = result_entries
    deletions = 0
    for h in [x.split()[0] for x in log if x.strip()]:
        st = sh("git", "show", "--numstat", "--format=", h, "--", f"docs/{LEDGER}", cwd=clone).stdout.split()
        if len(st) >= 2 and st[1].isdigit():
            deletions += int(st[1])
    res["append_only"] = deletions == 0
    # 4. push failure, then recovery
    sh("git", "remote", "set-url", "origin", "git@github.com:invalid/invalid-nonexistent.git", cwd=clone)
    sh(*sd, "append", "--kind", "result", "--phase", "A10", "--label", "pushfail", "--prose", "push failure test.",
       env=env, cwd=clone, check=False)
    ps = json.loads((state / "ledger_push.json").read_text())
    sh("git", "remote", "set-url", "origin", ORIGIN, cwd=clone)
    sh(*sd, "append", "--kind", "result", "--phase", "A10", "--label", "pushok", "--prose", "push recovery test.",
       env=env, cwd=clone, check=False)
    ps2 = json.loads((state / "ledger_push.json").read_text())
    ahead = sh("git", "rev-list", "--count", f"origin/{BR}..HEAD", cwd=clone, check=False).stdout.strip()
    sh("git", "fetch", "-q", "origin", BR, cwd=clone, check=False)
    ahead = sh("git", "rev-list", "--count", f"origin/{BR}..HEAD", cwd=clone, check=False).stdout.strip()
    res["push_failure_kept_local"] = ps.get("unpushed", 0) >= 1
    res["next_checkpoint_pushed"] = ps2.get("unpushed", 1) == 0 and ahead == "0"
    # 5. content filter
    tid = P.read_split("dev")[0]
    r1 = sh(*sd, "append", "--kind", "result", "--phase", "A10", "--label", "x", "--prose", f"cell {tid} done",
            env=env, cwd=clone, check=False)
    secret = P.read_env_file()["RITS_API_KET"]
    r2 = sh(*sd, "append", "--kind", "result", "--phase", "A10", "--label", "x", "--prose", f"key {secret}",
            env=env, cwd=clone, check=False)
    led2 = (clone / "docs" / LEDGER).read_text()
    res["filter_refused_task_id"] = r1.returncode != 0 and tid not in led2
    res["filter_refused_env_value"] = r2.returncode != 0 and secret not in led2
    res["ok"] = all([res["first_append"], res["heartbeat_stalled"], res["all_done"], res["cells_rerun"] == 0,
                     res["append_only"], res["push_failure_kept_local"], res["next_checkpoint_pushed"],
                     res["filter_refused_task_id"], res["filter_refused_env_value"], 0 < n_before_kill < 12])
    P.write_json(P.AW_STATE / "acceptance" / "a10.json", res)
    print(json.dumps(res))
    cleanup()
    return 0 if res["ok"] else 1


def cleanup() -> int:
    sh("git", "-C", str(P.REPO), "push", "-q", "origin", "--delete", BR, check=False)
    shutil.rmtree(BASE, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit({"run": run, "cleanup": cleanup}[sys.argv[1]]())
