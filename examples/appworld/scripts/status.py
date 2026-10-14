"""PROGRESS.md (plan §10.1): one table regenerated every 5 minutes.

  python3 -I status.py [--loop 300]
Columns: trial, phase, % done, last event, rollouts used, optimizer tokens and proxy USD, playbook size,
ETA, last checkpoint number, its age, pushed or not. Flags a live runner with no `result` entry for 75 min.
"""

from __future__ import annotations

import datetime as dt
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import awpaths as P  # noqa: E402
import status_doc as S  # noqa: E402


def last_line(name: str) -> str:
    p = P.PROGRESS / f"{name}.log"
    if not p.exists():
        return "-"
    lines = p.read_text().strip().splitlines()
    return lines[-1].split(" | ", 3)[-1] if lines else "-"


def render() -> str:
    last = S.last_entry()
    now = dt.datetime.now(dt.timezone.utc)
    t = dt.datetime.strptime(last["utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    age = int((now - t).total_seconds() // 60)
    ps = P.read_json(S.PUSH_STATE, {}) or {}
    prog = P.read_json(P.PUSHED / "ace" / "progress.json") or {}
    rows = prog.get("rows", [])
    sp = prog.get("spend", {})
    tin = sum(v["input"] for v in sp.values()) / 1e6
    tout = sum(v["output"] for v in sp.values()) / 1e6
    pb = f"{rows[-1]['pb_bullets']} b / {rows[-1]['pb_chars']:,} ch / {rows[-1]['pb_tokens']:,} tok" if rows else "-"
    eta = "-"
    if len(rows) >= 2:
        es = [x for x in S.entries() if "ACE step" in x[1]]
        if len(es) >= 2:
            first = dt.datetime.strptime(S.JSON_RE.search(es[0][1]) and __import__("json").loads(
                S.JSON_RE.search(es[0][1]).group(1))["utc"], "%Y-%m-%dT%H:%M:%SZ")
            per = (t.replace(tzinfo=None) - first).total_seconds() / max(1, len(es) - 1)
            eta = f"{int(per * (90 - len(rows)) / 60)} min (P4)"
    pid = S.runner_pid()
    stale = ""
    res = [x for x in S.entries() if "· result" in x[1].splitlines()[1] or "· phase_done" in x[1].splitlines()[1]]
    if res and S.pid_alive(pid):
        js = S.JSON_RE.search(res[-1][1])
        if js:
            lt = dt.datetime.strptime(__import__("json").loads(js.group(1))["utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
            if (now - lt).total_seconds() > 75 * 60:
                stale = " ⚠ no result entry for 75 min"
    hdr = "| trial | phase | % done | last event | rollouts | optimizer tok (proxy $) | playbook | ETA | last CP | age | pushed |\n" \
          "|---|---|---|---|---|---|---|---|---|---|---|\n"
    ace_pct = f"{100 * len(rows) // 90}%" if rows else "0%"
    line_ace = (f"| ace | {last.get('phase')} | {ace_pct} | {last_line('ace')} | {prog.get('rollouts', 0)} | "
                f"{tin:.2f}M / {tout:.2f}M (${tin * 2 + tout * 10:.2f}) | {pb} | {eta} | CP-{last['cp']:04d} | {age} min | "
                f"{'no, unpushed ' + str(ps.get('unpushed')) if ps.get('unpushed') else 'yes'} |\n")
    line_dev = f"| dev | P6 | - | {last_line('dev')} | - | - | - | - | | | |\n"
    line_fin = f"| final | P8 | - | {last_line('final')} | - | - | - | - | | | |\n"
    return (f"# PROGRESS ({now.strftime('%Y-%m-%dT%H:%MZ')})\n\nRunner: "
            f"{'alive pid ' + str(pid) if S.pid_alive(pid) else 'not running'}{stale}. Next: {last.get('next')}.\n\n"
            + hdr + line_ace + line_dev + line_fin)


def main() -> int:
    loop = int(sys.argv[sys.argv.index("--loop") + 1]) if "--loop" in sys.argv else 0
    while True:
        P.atomic_write(P.PROGRESS / "PROGRESS.md", render())
        if not loop:
            print((P.PROGRESS / "PROGRESS.md").read_text())
            return 0
        time.sleep(loop)


if __name__ == "__main__":
    sys.exit(main())
