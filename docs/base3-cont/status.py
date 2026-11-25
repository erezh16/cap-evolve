"""base3 status collector (docs/base3.md §5). Run on the Docker host:
    ~/b3/venv/bin/python ~/b3/status.py            -> JSON for all three benchmarks
Reads only the runs' own files plus docker ps / free / df. Never kills or changes anything."""
import glob, json, os, re, subprocess, time
from datetime import datetime, timezone

B3 = os.path.expanduser("~/b3")
NOW = time.time()


def sh(cmd):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60).stdout
    except Exception as e:  # noqa: BLE001
        return f"ERR {e}"


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if t else None


def pid_alive(pidfile):
    try:
        pid = int(open(pidfile).read().strip())
    except Exception:  # noqa: BLE001
        return None, False
    return pid, os.path.exists(f"/proc/{pid}")


def log_info(logfile):
    try:
        txt = open(logfile, errors="replace").read()
    except OSError:
        return {}
    out = {}
    m = re.search(r"^START (\S+)", txt, re.M)
    out["start"] = m.group(1) if m else None
    for k in ("BASELINE_EXIT", "FINALIZE_EXIT", "RUN_END", "WATCHDOG_STOP", "TEST_MOSTLY_INFRA"):
        m = re.findall(rf"^{k} (.*)$", txt, re.M)
        out[k.lower()] = m[-1] if m else None
    out["watchdog"] = out.pop("watchdog_stop")
    out["tail"] = txt.strip().splitlines()[-3:] if txt.strip() else []
    return out


def rollouts(run_dir, split):
    """Per-trial scores and infra counts from written rollouts (only exist once a grid completes)."""
    fs = glob.glob(f"{run_dir}/rollouts/{split}/*.json")
    if not fs:
        return None
    per_trial, infra, tok = {}, 0, 0
    for f in fs:
        m = re.search(r"__t(\d+)\.json$", f)
        t = int(m.group(1)) if m else -1
        d = json.load(open(f))
        r, s = d.get("rollout") or {}, d.get("score") or {}
        tok += int(r.get("tokens") or 0)
        if r.get("error"):
            infra += 1
            continue
        per_trial.setdefault(t, []).append(float(s.get("reward") or 0.0))
    return {"n_files": len(fs), "infra": infra, "tokens": tok,
            "per_trial": {k: {"n": len(v), "mean": round(sum(v) / len(v), 4)} for k, v in sorted(per_trial.items())}}


def newest_mtime(paths):
    ts = [os.path.getmtime(p) for p in paths if os.path.exists(p)]
    return max(ts) if ts else None


def common(name, base):
    pid, alive = pid_alive(f"{base}/run.pid")
    li = log_info(f"{base}/run.log")
    run_dir = sorted(glob.glob(f"{base}/run_base/run_*"), key=os.path.getmtime)
    run_dir = run_dir[-1] if run_dir else None
    st = {"bench": name, "pid": pid, "alive": alive, "log": li, "run_dir": run_dir}
    if run_dir:
        st["val"] = rollouts(run_dir, "val")
        st["test"] = rollouts(run_dir, "test")
        st["final_json"] = os.path.exists(f"{run_dir}/final.json")
        st["phase"] = "finalize" if li.get("baseline_exit") else "baseline"
    if li.get("watchdog"):
        st["watchdog_stop"] = li["watchdog"]
    if li.get("run_end"):
        st["state"] = "completed" if "done rc=0" in li["run_end"] else "terminated"
    elif alive:
        st["state"] = "running"
    elif pid:
        st["state"] = "terminated"
    else:
        st["state"] = "not-started"
    return st


def ssb():
    base = f"{B3}/ssb"
    st = common("spreadsheetbench", base)
    view = sorted(glob.glob(f"{base}/view_real*"), key=os.path.getmtime)[-1]
    outs = glob.glob(f"{view}/outputs/*")
    st["episodes_started"] = len(outs)
    st["containers"] = int(sh("docker ps -q --filter name=conv-capevolve | wc -l").strip() or 0)
    st["last_activity"] = newest_mtime(outs + glob.glob(f"{view}/outputs/*/*"))
    st["total"] = 200 + 1400
    return st


def sb():
    base = f"{B3}/sb"
    st = common("skillsbench", base)
    res = []
    if st.get("run_dir"):
        res = [p for p in glob.glob(f"{st['run_dir']}/bench_jobs/**/result.json", recursive=True)]
    st["trial_results"] = len(res)
    st["containers"] = int(sh("docker ps -q --filter label=com.docker.compose.project | wc -l").strip() or 0)
    st["last_activity"] = newest_mtime(res + glob.glob(f"{st.get('run_dir') or '/nonexistent'}/bench_jobs/*/*/*"))
    st["total"] = 35 + 15
    return st


def swe():
    base = f"{B3}/swe"
    st = common("swe_bench", base)
    start = None
    if st["log"].get("start"):
        start = datetime.fromisoformat(st["log"]["start"].replace("Z", "+00:00")).timestamp()
    res = [p for p in glob.glob(f"{base}/jobs/*/*/result.json") if start and os.path.getmtime(p) >= start]
    rew, exc = [], 0
    for p in res:
        try:
            d = json.load(open(p))
        except Exception:  # noqa: BLE001
            continue
        if d.get("exception_info"):
            exc += 1
        else:
            r = ((d.get("verifier_result") or {}).get("rewards") or {}).get("reward")
            rew.append(float(r or 0.0))
    st["trial_results"] = len(res)
    st["trial_exceptions"] = exc
    st["resolved_so_far"] = {"n": len(rew), "mean": round(sum(rew) / len(rew), 4) if rew else None}
    st["containers"] = int(sh("docker ps --format '{{.Names}}' | grep -c '__' ").strip() or 0)
    st["last_activity"] = newest_mtime(res + glob.glob(f"{base}/jobs/*/*/*"))
    st["total"] = 250 + 500
    return st


def watchdog():
    pid, alive = pid_alive(f"{B3}/gw_watchdog.pid")
    try:
        tail = open(f"{B3}/gw_watchdog.log").read().strip().splitlines()[-3:]
    except OSError:
        tail = []
    return {"pid": pid, "alive": alive, "log_tail": tail}


def host():
    mem = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":")
        mem[k] = int(v.split()[0])
    used = 1 - mem["MemAvailable"] / mem["MemTotal"]
    boot = NOW - float(open("/proc/uptime").read().split()[0])
    dstart = sh("systemctl show docker --property=ActiveEnterTimestamp --value").strip()
    return {"mem_used_pct": round(100 * used, 1), "boot": iso(boot), "docker_started": dstart,
            "disk_free_gb": round(int(sh("df --output=avail -B1 / | tail -1").strip()) / 1e9, 1),
            "load": open("/proc/loadavg").read().split()[:3], "now": iso(NOW)}


out = {"host": host(), "watchdog": watchdog(), "benches": []}
for f in (ssb, sb, swe):
    st = f()
    la = st.get("last_activity")
    st["min_since_activity"] = round((NOW - la) / 60, 1) if la else None
    st["last_activity"] = iso(la)
    st["stalled"] = bool(st["state"] == "running" and (la is None or NOW - la > 1800))
    out["benches"].append(st)
print(json.dumps(out, indent=1, default=str))
