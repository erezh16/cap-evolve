"""Rebuild the exact adapter code R1 (cape_hc_s0) ran with, from the orchestrating session's transcript.

    python reconstruct_r1_code.py SESSION.jsonl OUT_DIR

R1 started before examples/appworld was committed, and its project/adapters/ copy was overwritten at
the resume (2026-10-14 07:58). This replays every Write and every in-place edit of
examples/appworld/adapters/{adapter,aw_agent,lints}.py recorded in the session, in order, and writes a
snapshot of the three files at each point where they were copied into the cape_hc_s0 project:
    v1_launch      2026-10-13 15:58  (project scaffolded, search started 15:59)
    v2_lint_cache  2026-10-13 18:37  (lints.py with the lint cache copied in; rounds 4+)
    v3_resume      2026-10-14 07:58  (adapter.py with the readable-root wait; the resume)
Each snapshot is checked: v3 must equal the run dir's project/adapters (byte-identical), and v1's files
must compile. A Python-level in-place edit (a `python3 - <<EOF` patch) is re-run against the file.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SESSION, OUT = Path(sys.argv[1]), Path(sys.argv[2])
NAMES = ("adapter.py", "aw_agent.py", "lints.py")
# every other file of examples/appworld as it stood at the first window (2026-10-14 10:32), rebuilt the same way
SCRIPT_CUT = "2026-10-14T10:32:00"
CUTS = {"v1_launch": "2026-10-13T15:58:30", "v2_lint_cache": "2026-10-13T18:38:30", "v3_resume": "2026-10-14T07:59:30"}
RUN_COPY = Path("/tmp/aw_eval/runs/cape_hc_s0/.capevolve/project/adapters")


def events():
    for line in SESSION.open(errors="replace"):
        try:
            d = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        m = d.get("message") if isinstance(d, dict) else None
        if not isinstance(m, dict):
            continue
        for c in m.get("content") or []:
            if isinstance(c, dict) and c.get("type") == "tool_use":
                yield d.get("timestamp", ""), c["name"], c.get("input") or {}


def scripts_at(cut: str) -> dict[str, str]:
    """All examples/appworld files (except the three adapters) as last written/edited before ``cut``."""
    files: dict[str, str] = {}
    for ts, name, inp in events():
        if ts >= cut:
            break
        if name == "Bash":
            # files created by shell heredocs: `cat > <path> <<'EOF' ... EOF`
            cmd = inp.get("command", "")
            for hm in re.finditer(r"cat > (\S+) <<'(\w+)'\n(.*?)\n\2(?:\n|$)", cmd, re.S):
                path, body = hm.group(1), hm.group(3)
                mm = re.search(r"examples/appworld/(.+)$", path)
                rel = mm.group(1) if mm else (path if re.match(r"(scripts|altk|optimizer|sandbox)/|capevolve\.yaml$", path) else None)
                if rel and Path(rel).name not in NAMES:
                    files[rel] = body + "\n"
            continue
        fp = str(inp.get("file_path", ""))
        m = re.search(r"examples/appworld/(.+)$", fp)
        if not m or Path(fp).name in NAMES:
            continue
        rel = m.group(1)
        if name == "Write":
            files[rel] = inp["content"]
        elif name == "Edit" and rel in files and files[rel].count(inp["old_string"]):
            files[rel] = files[rel].replace(inp["old_string"], inp["new_string"], 0 if inp.get("replace_all") else 1) \
                if not inp.get("replace_all") else files[rel].replace(inp["old_string"], inp["new_string"])
    return files


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="r1code_"))
    ex = work / "examples/appworld/adapters"
    ex.mkdir(parents=True)
    state: dict[str, str] = {}
    log = []
    cut_iter = iter(sorted(CUTS.items(), key=lambda kv: kv[1]))
    nxt = next(cut_iter)

    def snapshot(tag):
        d = OUT / tag
        d.mkdir(parents=True, exist_ok=True)
        for n in NAMES:
            if n in state:
                (d / n).write_text(state[n])
        log.append({"snapshot": tag, "files": {n: hashlib.sha256(state[n].encode()).hexdigest() for n in state}})

    for ts, name, inp in events():
        while nxt and ts >= nxt[1]:
            snapshot(nxt[0])
            nxt = next(cut_iter, None)
        s = json.dumps(inp)
        if name == "Write" and str(inp.get("file_path", "")).endswith(tuple(f"examples/appworld/adapters/{n}" for n in NAMES)):
            fn = Path(inp["file_path"]).name
            state[fn] = inp["content"]
            log.append({"ts": ts, "op": "write", "file": fn})
        elif name == "Edit" and str(inp.get("file_path", "")).endswith(tuple(f"examples/appworld/adapters/{n}" for n in NAMES)):
            fn = Path(inp["file_path"]).name
            old, new = inp["old_string"], inp["new_string"]
            assert state.get(fn, "").count(old) >= 1, (ts, fn, "edit target missing")
            state[fn] = state[fn].replace(old, new) if inp.get("replace_all") else state[fn].replace(old, new, 1)
            log.append({"ts": ts, "op": "edit", "file": fn})
        elif name == "Bash":
            cmd = inp.get("command", "")
            touched = [n for n in NAMES if re.search(rf"adapters/{re.escape(n)}", cmd)]
            if not touched or not re.search(r"python3 - <<|sed -i", cmd):
                continue
            if not re.search(r"(open\(p, ?\"w\"\)|write_text|sed -i)", cmd):
                continue                                   # read-only use
            for n in NAMES:
                if n in state:
                    (ex / n).write_text(state[n])
            # re-run the patch against the reconstructed tree (paths rewritten to the temp tree)
            cmd2 = re.sub(r"/workspace/worktrees/base/examples/appworld/", str(work / "examples/appworld") + "/", cmd)
            cmd2 = re.sub(r"cd /workspace/worktrees/base/examples/appworld", f"cd {work}/examples/appworld", cmd2)
            cmd2 = re.sub(r"cd /workspace/worktrees/base(?![/\w])", f"cd {work}", cmd2)
            if "/tmp/aw_eval/runs/" in cmd2 and "cp " in cmd2:
                cmd2 = re.split(r"&&\s*for d in|; *for d in|\n *cp ", cmd2)[0]   # drop copies into live run dirs
            r = subprocess.run(["bash", "-c", cmd2], cwd=str(work / "examples/appworld"), capture_output=True, text=True)
            changed = []
            for n in NAMES:
                if (ex / n).is_file():
                    t = (ex / n).read_text()
                    if state.get(n) != t:
                        state[n] = t
                        changed.append(n)
            log.append({"ts": ts, "op": "patch", "touched": touched, "changed": changed, "rc": r.returncode,
                        "stderr": r.stderr[-200:]})
    while nxt:
        snapshot(nxt[0])
        nxt = next(cut_iter, None)
    sc = scripts_at(SCRIPT_CUT)
    for rel, txt in sc.items():
        d = OUT / "scripts_at_first_window" / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        d.write_text(txt)
    log.append({"scripts_at_first_window": sorted(sc), "note": "Write/Edit-tool content only; in-place shell "
                "patches to these files are listed in the session transcript"})
    checks = {}
    for n in NAMES:
        checks[f"v3_resume/{n} == run dir copy"] = (OUT / "v3_resume" / n).read_bytes() == (RUN_COPY / n).read_bytes()
    for tag in CUTS:
        for n in NAMES:
            r = subprocess.run([sys.executable, "-m", "py_compile", str(OUT / tag / n)], capture_output=True)
            checks[f"{tag}/{n} compiles"] = r.returncode == 0
    (OUT / "RECONSTRUCTION.json").write_text(json.dumps({"checks": checks, "log": log}, indent=1))
    (OUT / "README.md").write_text(
        "# R1 adapter code, reconstructed\n\nR1 (`cape_hc_s0`) ran before `examples/appworld` was committed, and the "
        "run's own `project/adapters/` was overwritten at the resume. These are the three adapter files at each point "
        "they were copied into the run, rebuilt by replaying every recorded edit from the orchestrating session "
        "(`reproduce/orchestrator/session/`):\n\n"
        "- `v1_launch/`: from the search start (2026-10-13 15:59) to round 3\n"
        "- `v2_lint_cache/`: lints.py reads the lint cache; from 18:37 (round 4 on)\n"
        "- `v3_resume/`: adapter.py waits for a readable root; from the resume (2026-10-14 07:59): rounds 6–8, final window\n\n"
        "`RECONSTRUCTION.json` holds the replay log and the checks: v3 is byte-identical to the run dir's copy, and every "
        "snapshot compiles.\n")
    ok = all(checks.values())
    print(json.dumps(checks, indent=1))
    print("RECONSTRUCTION", "OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
