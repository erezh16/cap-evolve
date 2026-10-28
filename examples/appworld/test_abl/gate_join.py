#!/usr/bin/env python3
"""TEST_ABL §3.2: add the gate arms when they are ready, then open their issues and verify their artifacts. nohup.

  . examples/appworld/test_abl/env.sh && nohup python3 -I examples/appworld/test_abl/gate_join.py &

Polls every 2 minutes (counts and flags only) until both gate arms are ready:
  - the arm's search process is not alive (its pid file under the ablation AW_STATE/p4, never pgrep -f);
  - its frozen champion is pushed: fork/eval-abl:docs/ABLATION_STATUS_STATE/<arm>/artifact/FREEZE.json with tree_sha256,
    and the local copy in the eval-abl worktree reproduces that hash under rule S;
  - its reset check passed (AW_STATE/<arm>/reset_check.json ok) and its pushed isolation scan has 0 test-id hits.
Then: records `window2_arms`, `gate_artifacts`, `gate_surfaces_changed` in this run's manifest (awtestabl reads them),
opens the two issues (open_issues.py), fetches and lints them as window 2 (AW_WINDOW=2), runs T4 and T5 for them, and
writes ledger entries. Window 2 itself is launched by launch_when_clear.py --window 2 after window 1 (plan §8).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EX = HERE.parent
sys.path.insert(0, str(EX / "scripts"))
import awrest as P  # noqa: E402
import status_doc as S  # noqa: E402

ABL = Path("/workspace/aw_abl/state")
ABL_PUSHED = Path("/workspace/worktrees/eval-abl/docs/ABLATION_STATUS_STATE")
GATE = ("abl_nogate", "abl_naivegate")
SURF = ("policy/instructions.txt", "tools/helpers.py", "tools/api_notes.json")
LOG = P.PROGRESS / "gate_join.log"


def log(msg: str) -> None:
    with open(LOG, "a") as f:
        f.write(f"{P.utcnow()} {msg}\n")


def git_json(spec: str) -> dict:
    r = subprocess.run(["git", "-C", str(P.REPO), "show", spec], capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 else {}


def rule_s(d: Path) -> str:
    c = {r: (d / r).read_text(encoding="utf-8") for r in SURF + ("memory/playbook.md",) if (d / r).is_file()}
    c = {k: v for k, v in c.items() if not (k == "memory/playbook.md" and not v.strip())}
    return hashlib.sha256(json.dumps(sorted(c.items())).encode()).hexdigest()


def sha(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


def ready(arm: str) -> tuple[bool, dict]:
    try:
        pid = int((ABL / "p4" / f"{arm}.pid").read_text().split()[0])
    except (FileNotFoundError, ValueError, IndexError):
        pid = None
    fz = git_json(f"fork/eval-abl:docs/ABLATION_STATUS_STATE/{arm}/artifact/FREEZE.json")
    scan = git_json("fork/eval-abl:docs/ABLATION_STATUS_STATE/isolation_scan.json").get(arm) or {}
    rc = P.read_json(ABL / arm / "reset_check.json", {}) or {}
    local = ABL_PUSHED / arm / "artifact"
    h = rule_s(local) if (local / "policy" / "instructions.txt").is_file() else None
    st = {"search_alive": S.pid_alive(pid), "freeze_hash": fz.get("tree_sha256"), "local_hash_ok": h == fz.get("tree_sha256"),
          "reset_ok": bool(rc.get("ok")), "scan_hits": scan.get("test_id_hits"), "inert": fz.get("inert"),
          "label": fz.get("label")}
    ok = (not st["search_alive"] and bool(st["freeze_hash"]) and st["local_hash_ok"] and st["reset_ok"]
          and st["scan_hits"] == 0)
    return ok, st


def main() -> int:
    (P.AW_STATE / "GATE_JOIN.pid").write_text(f"{os.getpid()}\n")
    last = None
    while True:
        subprocess.run(["git", "-C", str(P.REPO), "fetch", "-q", "fork", "eval-abl"], capture_output=True)
        subprocess.run(["git", "-C", "/workspace/worktrees/eval-abl", "fetch", "-q", "fork", "eval-abl"], capture_output=True)
        res = {a: ready(a) for a in GATE}
        if any(v[1]["scan_hits"] for v in res.values()):
            S.append("error", "W", "gate arm scan hits", "A gate arm's isolation scan reports test-id hits: it does "
                     "not join (addendum A8).", extra={"gate": {a: v[1] for a, v in res.items()}}, subject="gate scan hits")
            return 3
        summary = json.dumps({a: v[1] | {"ready": v[0]} for a, v in res.items()})
        if summary != last:
            log(summary)
            last = summary
        if all(v[0] for v in res.values()):
            break
        time.sleep(120)
    seed = Path("/workspace/worktrees/eval-abl/examples/appworld/seed_capability")
    arts, surf = {}, {}
    for a in GATE:
        d = ABL_PUSHED / a / "artifact"
        ch = [r for r in SURF if sha(d / r) != sha(seed / r)]
        surf[a] = " + ".join(x for x, ok in (("P", "policy/instructions.txt" in ch),
                                            ("T", any(r.startswith("tools/") for r in ch))) if ok) or "none"
        arts[a] = {"local": str(d), "box": None, "hash": res[a][1]["freeze_hash"], "rule": "S"}
    P.update_manifest(window2_arms=list(GATE), gate_artifacts=arts, gate_surfaces_changed=surf)
    S.append("decision", "W", "gate arms ready",
             "Both gate arms are ready (plan §3.2): searches ended, champions frozen and pushed, local copies reproduce "
             "their freeze hash under rule S, reset checks ok, isolation scans 0 test-id hits. They join window 2. "
             f"Surfaces changed vs the seed: {surf}. Opening their issues next.",
             extra={"gate": {a: v[1] for a, v in res.items()}}, subject="gate arms ready")
    env = dict(os.environ)
    r = subprocess.run([sys.executable, "-I", str(EX / "test_all" / "issue_bodies.py"), "--out",
                        str(P.AW_STATE / "issue_bodies")], env=env, capture_output=True, text=True, cwd=str(P.REPO))
    r = subprocess.run([sys.executable, "-I", str(EX / "test_all" / "open_issues.py")], env=env, capture_output=True,
                       text=True, cwd=str(P.REPO))
    log(f"open_issues rc {r.returncode}: {r.stdout.strip().splitlines()[-1:]}")
    issues = {a: n for a, n in (P.read_json(P.PUSHED / "manifest.json", {}) or {}).get("issues", {}).items() if a in GATE}
    S.append("result" if r.returncode == 0 else "error", "W", "gate issues opened",
             f"Gate-arm tracking issues: {', '.join(f'{a} #{n}' for a, n in issues.items()) or 'NOT opened'}. Their "
             "hourly timers start now (autopost reads the open issues).", extra={"issues_gate": issues},
             subject="gate issues")
    env2 = dict(env, AW_WINDOW="2")
    out = {}
    for name, cmd in (("fetch", [sys.executable, "-I", str(EX / "test_all" / "fetch_artifacts.py")]),
                      ("lint", [str(P.VENV_PY), "-I", str(EX / "test_all" / "lint_arms.py")]),
                      ("t4", [str(P.VENV_PY), "-I", str(EX / "test_all" / "check_t4.py")]),
                      ("t5", [str(P.VENV_PY), "-I", str(EX / "test_all" / "check_t1t5.py"), *GATE])):
        e = dict(env2, APPWORLD_ROOT=str(P.ROOT_OPT)) if name == "t4" else env2
        rr = subprocess.run(cmd, env=e, capture_output=True, text=True, cwd=str(EX))
        out[name] = rr.returncode
        log(f"{name} rc {rr.returncode}")
    ok = all(v == 0 for v in out.values())
    S.append("result" if ok else "error", "W", "gate arms fetch, lint, T4, T5",
             f"Window 2 arms ({', '.join(GATE)}): fetch + rule-S hash check, lint, T4 injection and T5 context "
             f"(1 dev episode each): {'PASS' if ok else 'FAIL ' + json.dumps(out)}. Window 2 runs after window 1.",
             extra={"gate_accept": out}, subject="gate accept")
    if ok:
        import post
        t4 = P.read_json(P.AW_STATE / "acceptance" / "t4_w2.json", {}) or {}
        post.post_all("accept_done", "{NAME}: build and acceptance done", lambda a: (
            f"**{P.METHOD_NAMES[a]} (`{a}`): ready, build and acceptance done.** Its champion was frozen by the gate "
            f"run; fetched from the pushed copy, rule-S hash `{arts[a]['hash'][:16]}…` verified; lint pass; T4 "
            f"injection {'PASS' if (t4.get(a) or {}).get('expected_ok') else 'see ledger'}; T5 context PASS. It is "
            "scored in **window 2** (1,680 cells, after window 1). Comparisons with window-1 arms are cross-window.\n\n"
            "Counts only. No test score is posted before the window completes and the analysis has run."),
            arms=list(GATE))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
