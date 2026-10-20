#!/usr/bin/env python3
"""The only writer of the checkpoint ledger: section 18 of docs/EVAL_APPWORLD_REST.md (plan §12.2).

  status_doc.py append --kind result --phase P4 --label "ACE adaptation" --prose "..." \
      --done-through ace/step/041/apply --next ace/step/042/episode [--set key=<json>]... \
      [--artifact STATE/ace/playbook.txt] [--artifact local/ace/playbooks/pb_041.txt]
  status_doc.py heartbeat [--every 60] [--silence 1500]     # nohup loop
  status_doc.py abort --reason "..."
  status_doc.py last                                         # print the last entry's json block

Every append: write pushed state (done by the caller, atomically), append the entry, fsync, run the
content filter on every file the commit would publish, `git commit -- <pathspec>`, `git push`
(never --force). All under flock(AW_STATE/ledger.lock). Importable: `append(...)`, `last_entry()`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import awrest as P  # noqa: E402

PATHSPEC = [str(P.LEDGER.relative_to(P.REPO)), str(P.PUSHED.relative_to(P.REPO)) + "/", "examples/appworld/"]
PUSH_STATE = P.AW_STATE / "ledger_push.json"
LOCK = P.AW_STATE / "ledger.lock"                      # rule R3
HB_PID = P.AW_STATE / "HEARTBEAT.pid"
TRAILER = "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
ENTRY_RE = re.compile(r"^## CP-(\d{4}) · ", re.M)
JSON_RE = re.compile(r"```json\n(.*?)\n```", re.S)


class Refused(RuntimeError):
    pass


def git(*args: str, check: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(P.REPO), *args], capture_output=True, text=True,
                          check=check, env=env)


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


# ---------------------------------------------------------------- ledger parsing

def entries(text: str | None = None) -> list[tuple[int, str]]:
    text = P.LEDGER.read_text() if text is None else text
    starts = [m.start() for m in ENTRY_RE.finditer(text)]
    out = []
    for i, s in enumerate(starts):
        chunk = text[s: starts[i + 1] if i + 1 < len(starts) else len(text)]
        out.append((int(chunk[6:10]), chunk))
    return out


def last_entry(text: str | None = None) -> dict:
    es = entries(text)
    if not es:
        return {}
    m = JSON_RE.search(es[-1][1])
    return json.loads(m.group(1)) if m else {}


# ---------------------------------------------------------------- content filter

_cache: dict | None = None


def _lint_cache() -> dict | None:
    global _cache
    if _cache is None and P.PUBLISH_CACHE.exists():
        c = json.loads(P.PUBLISH_CACHE.read_text())
        c["_ids"] = set(c["task_ids"])
        c["_ngrams"] = set(c["instruction_8grams"])
        c["_contacts"] = [x.lower() for x in c["contacts"]]
        _cache = c
    return _cache


WORD = re.compile(r"[a-z0-9']+")
ID_RE = re.compile(r"\b[0-9a-f]{7}_[0-9]+\b")


def ngrams8(text: str) -> set[str]:
    w = WORD.findall(text.lower())
    return {" ".join(w[i:i + 8]) for i in range(len(w) - 7)}


def violations(text: str, env_values: list[str] | None = None) -> list[str]:
    """Content rules of §12.2. Returns rule names (never the matched text)."""
    out = []
    env_values = [v for v in (env_values if env_values is not None else P.read_env_file().values())
                  if len(v) >= 8]
    if any(v in text for v in env_values):
        out.append("env_string")
    c = _lint_cache()
    if c is not None:
        if any(m in c["_ids"] for m in ID_RE.findall(text)):
            out.append("task_id")
        if ngrams8(text) & c["_ngrams"]:
            out.append("instruction_8gram")
        low = text.lower()
        if any(x in low for x in c["_contacts"]):
            out.append("supervisor_contact")
    return out


def files_to_publish() -> list[str]:
    """Paths under the pathspec that differ from HEAD or are untracked."""
    changed = git("diff", "--name-only", "HEAD", "--", *PATHSPEC).stdout.split()
    untracked = git("ls-files", "--others", "--exclude-standard", "--", *PATHSPEC).stdout.split()
    return sorted(set(changed) | set(untracked))


def check_publish(paths: list[str]) -> dict[str, list[str]]:
    bad = {}
    for rel in paths:
        p = P.REPO / rel
        if not p.is_file():
            continue
        try:
            text = p.read_text()
        except UnicodeDecodeError:
            continue
        # vendored upstream text is published verbatim from a public repository; ids/env still apply
        if rel == str(P.LEDGER.relative_to(P.REPO)):
            text = text.split(P.LEDGER_MARKER, 1)[-1]  # the plan above the marker is reviewed text
        v = violations(text)
        if "/vendor/" in rel or "/VENDORED" in rel:
            v = [x for x in v if x in ("env_string", "task_id")]
        if v:
            bad[rel] = v
    return bad


# ---------------------------------------------------------------- append

def _fmt_utc(t: dt.datetime) -> tuple[str, str]:
    return t.strftime("%Y-%m-%dT%H:%MZ"), t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_artifact(name: str) -> str:
    if name.startswith("STATE/"):
        return P.sha256_file(P.PUSHED / name[len("STATE/"):])
    if name.startswith("local/"):
        return P.sha256_file(P.AW_STATE / name[len("local/"):])
    raise ValueError(f"artifact must start with STATE/ or local/: {name}")


def append(kind: str, phase: str, label: str, prose: str, *, done_through=None, next_unit=None,
           extra: dict | None = None, artifacts: list[str] | None = None, subject: str | None = None,
           push: bool = True) -> dict:
    P.AW_STATE.mkdir(parents=True, exist_ok=True)
    with open(LOCK, "w") as lockf:
        fcntl.flock(lockf, fcntl.LOCK_EX)
        return _append_locked(kind, phase, label, prose, done_through, next_unit, extra or {},
                              artifacts or [], subject, push)


def _append_locked(kind, phase, label, prose, done_through, next_unit, extra, artifacts, subject, push):
    text = P.LEDGER.read_text()
    if P.LEDGER_MARKER not in text:
        raise Refused("ledger marker missing")
    prev = last_entry(text)
    es = entries(text)
    # entries are numbered 0, 1, 2, ... in file order; the count also covers a misnumbered entry
    cp = max(len(es), max((n for n, _ in es), default=-1) + 1)
    assert not es or cp > max(n for n, _ in es), "checkpoint numbers must increase"
    t = utcnow()
    head_min, head_sec = _fmt_utc(t)
    ps = P.read_json(PUSH_STATE, {}) or {}
    notes = []
    if ps.get("unpushed"):
        notes.append(f"Push note: {ps['unpushed']} earlier checkpoint commit(s) were not pushed "
                     f"({ps.get('last_error', 'unknown error')}); this checkpoint pushes them.")
    if ps.get("blocked"):
        notes.append("Push note: pushing is stopped (non-fast-forward on origin); commits are local "
                     "until the user decides.")
    obj = {"cp": cp, "prev_cp": prev.get("cp"), "prev_commit": git("rev-parse", "HEAD").stdout.strip(),
           "utc": head_sec, "kind": kind, "phase": phase,
           "done_through": done_through if done_through is not None else prev.get("done_through"),
           "next": next_unit if next_unit is not None else prev.get("next"),
           "candidate": extra.pop("candidate", None) if "candidate" in extra else prev.get("candidate"),
           "counts": prev.get("counts", {}), "spend": prev.get("spend", {}),
           "artifacts": {}, "code": None, "open_decisions": prev.get("open_decisions", [])}
    for k, v in extra.items():
        obj[k] = v
    for a in artifacts:
        obj["artifacts"][a] = _resolve_artifact(a)
    obj["code"] = git("log", "-1", "--format=%H", "--", "examples/appworld/").stdout.strip() or None
    body = prose.strip()
    if notes:
        body += "\n" + "\n".join(notes)
    js = json.dumps(obj, ensure_ascii=False)
    entry = f"\n## CP-{cp:04d} · {head_min} · {phase} {label} · {kind}\n\n{body}\n\n```json\n{js}\n```\n"
    # content filter on the entry itself before anything touches disk
    v = violations(entry)
    if v:
        P.progress_log("ledger", phase, f"REFUSED CP-{cp:04d}: entry violates {v}")
        raise Refused(f"ledger entry refused: {v}")
    with open(P.LEDGER, "a") as f:
        f.write(entry)
        f.flush()
        os.fsync(f.fileno())
    if os.environ.get("AW_TEST_APPEND_PAUSE"):  # A9 only: a window to SIGKILL mid-append
        time.sleep(float(os.environ["AW_TEST_APPEND_PAUSE"]))
    bad = check_publish(files_to_publish())
    if bad:
        git("checkout", "--", str(P.LEDGER.relative_to(P.REPO)))  # drop the uncommitted entry
        P.progress_log("ledger", phase, f"REFUSED CP-{cp:04d}: staged files violate {bad}")
        raise Refused(f"checkpoint refused, files violate content rules: {bad}")
    spec = [x for x in PATHSPEC if (P.REPO / x).exists()]
    msg = f"status: CP-{cp:04d} {phase} {subject or done_through or label}\n\n{TRAILER}\n"
    try:
        git("add", "--", *spec)
        git("commit", "-q", "-m", msg, "--", *spec)
    except subprocess.CalledProcessError as e:
        git("checkout", "--", str(P.LEDGER.relative_to(P.REPO)), check=False)
        P.progress_log("ledger", phase, f"ERROR CP-{cp:04d}: git {e.cmd[3:5]} failed: {e.stderr[-200:]}")
        raise
    commit = git("rev-parse", "HEAD").stdout.strip()
    if push:
        _push(ps)
    P.progress_log("ledger", phase, f"CP-{cp:04d} {kind} committed {commit[:10]}"
                   f" pushed={not (P.read_json(PUSH_STATE, {}) or {}).get('unpushed')}")
    obj["_commit"] = commit
    return obj


def _push(ps: dict) -> None:
    if ps.get("blocked"):
        ps["unpushed"] = ps.get("unpushed", 0) + 1
        P.write_json(PUSH_STATE, ps)
        return
    r = git("push", "-q", "origin", f"HEAD:{P.BRANCH}", check=False)
    if r.returncode == 0:
        P.write_json(PUSH_STATE, {"unpushed": 0, "last_push_utc": _fmt_utc(utcnow())[1]})
        return
    err = (r.stderr or "").strip().splitlines()[-1:] or ["?"]
    ps["unpushed"] = ps.get("unpushed", 0) + 1
    ps["last_error"] = err[0][:160]
    if "non-fast-forward" in r.stderr or "rejected" in r.stderr and "fetch first" in r.stderr:
        ps["blocked"] = True
    P.write_json(PUSH_STATE, ps)


# ---------------------------------------------------------------- heartbeat / abort

def runner_pid() -> int | None:
    try:
        pid = int((P.AW_STATE / "RUNNING.pid").read_text().split()[0])
    except (FileNotFoundError, ValueError, IndexError):
        return None
    return pid


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _latest_log_line() -> str:
    logs = sorted((p for p in P.PROGRESS.glob("*.log") if p.name not in ("ledger.log", "heartbeat.log")),
                  key=lambda p: p.stat().st_mtime)
    if not logs:
        return "(no log)"
    lines = logs[-1].read_text().strip().splitlines()
    return lines[-1] if lines else "(empty log)"


def heartbeat_once(silence: int) -> bool:
    prev = last_entry()
    last = dt.datetime.strptime(prev["utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    if (utcnow() - last).total_seconds() < silence:
        return False
    pid = runner_pid()
    alive = pid_alive(pid)
    state = f"alive (pid {pid})" if alive else (f"stalled (pid {pid} not running)" if pid else "no runner")
    tail = _latest_log_line().replace("`", "'")
    prose = (f"No checkpoint for {int((utcnow() - last).total_seconds() // 60)} min. "
             f"Phase {prev.get('phase')}, last result: {prev.get('done_through')}.\n"
             f"Runner: {state}. Last log line: `{tail}`.\nNext: {prev.get('next')}.")
    extra = {"runner": "alive" if alive else ("stalled" if pid else "none")}
    try:
        append("heartbeat", prev.get("phase", "?"), "heartbeat", prose, extra=extra,
               subject="heartbeat")
    except Refused:
        append("heartbeat", prev.get("phase", "?"), "heartbeat",
               prose.split("Last log line")[0] + "(log line withheld by the content filter).",
               extra=extra, subject="heartbeat")
    return True


def watch_once() -> None:
    """§8 / R2 watch duties of the heartbeat: every issue posted to within the hour; the memory guard alive."""
    import autopost
    late = autopost.check_ages(3600)
    st = P.read_json(P.AW_STATE / "watch.json", {}) or {}
    if late and st.get("late") != late:
        prev = last_entry()
        append("error", prev.get("phase", "?"), "hourly posts late",
               f"The last post on the issue of {', '.join(late)} is older than 60 minutes (section 8). The "
               "auto-poster is restarted by resume.py; checking it now.", subject="hourly posts late")
    st["late"] = late
    P.write_json(P.AW_STATE / "watch.json", st)
    if P.memstate().get("stale"):
        subprocess.Popen(["nohup", sys.executable, "-I", str(Path(__file__).parent / "memguard.py"), "loop"],
                         stdout=open(P.PROGRESS / "memguard.out", "a"), stderr=subprocess.STDOUT,
                         start_new_session=True)
        P.progress_log("ledger", "heartbeat", "memguard sample stale: guard restarted")
    try:
        ap = int((P.AW_STATE / "AUTOPOST.pid").read_text().strip())
    except (FileNotFoundError, ValueError):
        ap = None
    if not pid_alive(ap):
        subprocess.Popen(["nohup", sys.executable, "-I", str(Path(__file__).parent / "autopost.py"), "loop",
                          "--every", "3600"], stdout=open(P.PROGRESS / "autopost.out", "a"),
                         stderr=subprocess.STDOUT, start_new_session=True, cwd=str(P.REPO))
        P.progress_log("ledger", "heartbeat", "autopost not running: restarted")


def heartbeat_loop(every: int, silence: int) -> None:
    P.write_json(HB_PID, {"pid": os.getpid()})
    (P.AW_STATE / "HEARTBEAT.pid").write_text(str(os.getpid()))
    while True:
        try:
            heartbeat_once(silence)
            watch_once()
        except Exception as e:  # keep the loop alive; the failure is in the local log
            P.progress_log("ledger", "heartbeat", f"error {type(e).__name__}: {e}"[:300])
        time.sleep(every)


def abort(reason: str) -> None:
    pid = runner_pid()
    if pid_alive(pid):
        os.kill(pid, signal.SIGTERM)
    try:
        hb = int((P.AW_STATE / "HEARTBEAT.pid").read_text().strip())
        if pid_alive(hb):
            os.kill(hb, signal.SIGTERM)
    except (FileNotFoundError, ValueError):
        pass
    prev = last_entry()
    append("abort", prev.get("phase", "?"), "abort",
           f"Aborted on purpose: {reason}\nRunner pid {pid} sent SIGTERM; heartbeat stopped.\n"
           f"Resume with `python3 -I examples/appworld/scripts/resume.py`. Next: {prev.get('next')}.",
           extra={"reason": reason}, subject="abort")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("append")
    a.add_argument("--kind", required=True)
    a.add_argument("--phase", required=True)
    a.add_argument("--label", required=True)
    a.add_argument("--prose", required=True)
    a.add_argument("--done-through")
    a.add_argument("--next")
    a.add_argument("--subject")
    a.add_argument("--set", action="append", default=[], help="key=<json>")
    a.add_argument("--artifact", action="append", default=[])
    a.add_argument("--candidate")
    a.add_argument("--no-push", action="store_true")
    h = sub.add_parser("heartbeat")
    h.add_argument("--every", type=int, default=60)
    h.add_argument("--silence", type=int, default=25 * 60)
    h.add_argument("--once", action="store_true")
    b = sub.add_parser("abort")
    b.add_argument("--reason", required=True)
    sub.add_parser("last")
    args = ap.parse_args()
    if args.cmd == "append":
        extra = {"candidate": args.candidate} if args.candidate else {}
        for kv in args.set:
            k, v = kv.split("=", 1)
            extra[k] = json.loads(v)
        o = append(args.kind, args.phase, args.label, args.prose, done_through=args.done_through,
                   next_unit=args.next, extra=extra, artifacts=args.artifact, subject=args.subject,
                   push=not args.no_push)
        print(f"CP-{o['cp']:04d} {o['_commit'][:10]}")
    elif args.cmd == "heartbeat":
        if args.once:
            print(heartbeat_once(args.silence))
        else:
            heartbeat_loop(args.every, args.silence)
    elif args.cmd == "abort":
        abort(args.reason)
    elif args.cmd == "last":
        print(json.dumps(last_entry(), indent=1))


if __name__ == "__main__":
    main()
