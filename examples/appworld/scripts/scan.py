"""The isolation scan of eval REST (docs/EVAL_APPWORLD_REST.md §4.1 rule 6): after each search (P4, per candidate)
and once more before the final window (P6, all five + the orchestrating sessions).

  venv-aw/bin/python -I scan.py cand [cand ...]   # P4 per-candidate scan
  venv-aw/bin/python -I scan.py --full            # P6: all five + the orchestrating sessions' own transcripts

Greps every optimizer-side record of each candidate — the optimizer prompt/response log (llm_calls.jsonl),
the claude -p result JSONs (claude_calls/), the CLI transcripts of the sandboxed roles under ~/.claude/projects,
every file under AW_STATE/<cand> other than the evaluator's own episode records, the optimizer workspaces
(/tmp/aw_rest/opt/<cand>) and the frozen artifact — for: test ids (test_normal + test_challenge), the strings test_normal,
test_challenge, root_full, ground_truth, answer.json, compiled_solution, generate/tasks, and AppWorld app
source paths (src/appworld/apps). Counts only (no matched text) go to the pushed state. A test-id hit labels
the arm "isolation breach". root_full is read once for the test ids and relocked (it is already locked by P7).
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "common"))
import awrest as P  # noqa: E402
import sandbox as SB  # noqa: E402

LITERALS = ("test_normal", "test_challenge", "root_full", "ground_truth", "answer.json", "compiled_solution",
            "generate/tasks", "src/appworld/apps", "solution.py")
if P.LEDGER_ID == "ABL":       # ABLATIONS R1.5: earlier evaluations' homes; other arms' roots are added per arm below
    LITERALS = LITERALS + ("aw_rest", "aw_ce2", "aw_ce3")
elif P.LEDGER_PREFIX == "CE2":   # CE2 §4.1 rule 5: REST's run data and the other arm's run dir as well
    LITERALS = LITERALS + ("aw_rest/cape_run", "aw_rest/state", "aw_ce2/run_k1", "aw_ce2/run_k2")
    if P.LEDGER_ID == "CE3":   # CE3: CE2's state and opt dirs are another arm's run too
        LITERALS = LITERALS + ("aw_ce2/state", "aw_ce2/opt")


def locations(c: str) -> dict[str, Path]:
    st = P.AW_STATE / c
    if c == "abl_cc":                       # ABLATIONS R1.5: the session's workdir, its config dir (the transcripts,
        root = P.RUN_ROOTS[c]               # main loop and sub-agents), the eval-daemon spool and the artifact
        out = {"claude -p results": st / "claude_calls", "arm state (driver, daemon log)": st,
               "session workdir (incl. .eval spool)": root / "work", "session config dir (transcripts)": root / "config",
               "archived config dir": P.AW_STATE / "archive" / c, "frozen artifact": P.PUSHED / c / "artifact"}
        for d in (Path(f"/tmp/claude-{__import__('os').getuid()}")).glob(str(root).replace("/", "-").replace("_", "-") + "*"):
            out[f"claude tmp {d.name[-48:]}"] = d
        return out
    if P.LEDGER_PREFIX == "CE2":
        rd = P.RUN_ROOTS[c] / ".capevolve" / f"run_{P.RUN_TS[c]}"
        out = {"claude -p results": st / "claude_calls", "arm state (driver)": st,
               "optimizer workdirs (run dir work/)": rd / "work", "run dir events": rd / "events.jsonl",
               "frozen artifact": P.PUSHED / c / "artifact"}
        # the CLI's own transcripts (main loop and sub-agents) of sessions run with cwd under the arm's run dir
        tag = str(P.RUN_ROOTS[c]).replace("/", "-").replace("_", "-")
        for root in (Path.home() / ".claude" / "projects", Path(f"/tmp/claude-{__import__('os').getuid()}")):
            for d in root.glob(f"{tag}*"):
                out[f"claude transcripts {d.parent.name[:12]}/{d.name[-48:]}"] = d
        return out
    out = {"optimizer calls": st / "llm_calls.jsonl", "claude -p results": st / "claude_calls",
           "candidate state (driver, method)": st, "optimizer workspace (/tmp)": SB.OPT_ROOT / c,
           "frozen artifact": P.PUSHED / c / "artifact"}
    # the CLI's own transcripts of the sandboxed roles run with cwd under /tmp/aw_rest/opt/<cand>/
    for d in (Path.home() / ".claude" / "projects").glob(f"-tmp-aw-rest-opt-{c.replace('_', '-')}*"):
        out[f"claude transcripts {d.name[:40]}"] = d
    return out


SKIP_DIRS = ("episodes", "cache", "cands", "inflight", "evalreq")   # the evaluator's own records and candidate dirs


def scan(c: str, id_re: re.Pattern) -> dict:
    out = {}
    for name, root in locations(c).items():
        if not root.exists():
            continue
        # the harness's own sandbox settings name the denied paths; they are not optimizer output
        files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()
                                                and not p.name.endswith("settings.json")
                                                and not any(x in p.relative_to(root).parts[:1] for x in SKIP_DIRS)
                                                and p.name not in ("rollouts.jsonl", "cache_hits.jsonl")]
        counts: Counter = Counter()
        n_hit = 0
        own = (None if P.LEDGER_ID in ("CE3", "ABL") else f"aw_ce2/run_k{c[-1]}") if P.LEDGER_PREFIX == "CE2" else None
        lits = LITERALS + (tuple(f"aw_abl/arms/{o}" for o in P.CANDIDATES if o != c) if P.LEDGER_ID == "ABL" else ())
        for p in files:
            if p.stat().st_size > 200_000_000:
                continue
            text = p.read_bytes().decode("utf-8", "ignore")
            hit = Counter({"test_id": len(id_re.findall(text))})
            for lit in lits:
                if lit != own:                # the arm's own run dir path is everywhere in its own records
                    hit[lit] = text.count(lit)
            hit = +hit
            if hit:
                counts.update(hit)
                n_hit += 1
        out[name] = {"files": len(files), "files_hit": n_hit, "counts": dict(counts)}
    res = {"locations": out,
           "test_id_hits": sum(v["counts"].get("test_id", 0) for v in out.values())}
    res["isolation_breach"] = res["test_id_hits"] > 0
    return res


def ce2_extras(c: str) -> dict:
    """CE2 Q3 and §9.6.9: every modelUsage key in the arm's claude result JSONs (any model other than the optimizer
    model is an error), and every iteration's work/<cid>/INSTRUCTIONS.md has J1 (required strings, none forbidden)
    and every gate record the arm's K."""
    import subprocess
    models: Counter = Counter()
    for f in (P.AW_STATE / c / "claude_calls").glob("*.json"):
        try:
            for k in (json.loads(f.read_text()).get("modelUsage") or {}):
                models[k] += 1
        except json.JSONDecodeError:
            models["<unparsable result>"] += 1
    if c == "abl_cc":                       # no cap-evolve loop: no J1/K to check; the model check still applies
        return {"model_usage_keys": dict(models), "other_models": sorted(k for k in models if k != P.OPT_MODEL),
                "j1_iterations": None, "j1_all_ok": None, "k_se_cmdline": None, "k_ok": None, "imp_all_ok": None}
    abl = P.LEDGER_ID == "ABL"
    drv = HERE.parent / ("abl/run_abl.py" if abl else "ce2/run_ce2.py")
    env = dict(__import__("os").environ)
    if abl:                                 # the imp check's switch item reads the arm's switches from the env
        sw = {"abl_tools": {"AW_ABL_FEEDBACK": "full", "AW_ABL_TOOLS_LINT": "1"},
              "abl_notrace": {"AW_ABL_FEEDBACK": "eval_only"}, "abl_tracescore": {"AW_ABL_FEEDBACK": "trace_score"}}
        env.update(sw.get(c, {"AW_ABL_FEEDBACK": "full"}))
    r = subprocess.run([str(P.VENVS / ("venv-abl" if abl else "venv-ce2") / "bin" / "python"), "-I", str(drv),
                        "imp-check", "--arm", c, "--level", "full", "--run-dir",
                        str(P.RUN_ROOTS[c] / ".capevolve" / f"run_{P.RUN_TS[c]}")], capture_output=True, text=True,
                       env=env)
    try:
        imp = json.loads(r.stdout)
    except json.JSONDecodeError:
        imp = {"all_ok": False, "error": r.stderr[-400:]}
    ins = imp.get("5_instructions", {})
    return {"model_usage_keys": dict(models), "other_models": sorted(k for k in models if k != P.OPT_MODEL),
            "j1_iterations": ins.get("iterations"), "j1_all_ok": ins.get("ok"),
            "k_se_cmdline": imp.get("4_effective_k_se", {}).get("k_se_values"),
            "k_ok": imp.get("4_effective_k_se", {}).get("ok") and imp.get("3_run_config", {}).get("ok"),
            "imp_all_ok": imp.get("all_ok")}


def scan_sessions(id_re: re.Pattern) -> dict:
    """R1.6: the orchestrating sessions' own transcripts (main session and its build sub-agents)."""
    roots = [p for p in (Path.home() / ".claude" / "projects").glob("-workspace-worktrees-*") if p.is_dir()]
    roots += [p for p in Path(f"/tmp/claude-{__import__('os').getuid()}").glob("-workspace-worktrees-*") if p.is_dir()]
    counts: Counter = Counter()
    files = 0
    excluded: dict = {}
    # CE2 user decision (CE2-0078): the orchestrating sessions are THIS run's sessions, identified by AW_SESSION_IDS;
    # any other session's files are counted separately (out of scope) and disclosed, never silently dropped
    keep = [x for x in __import__("os").environ.get("AW_SESSION_IDS", "").split(",") if x]
    for r in roots:
        for p in r.rglob("*"):
            if not p.is_file() or p.stat().st_size > 500_000_000:
                continue
            if keep and not any(k in str(p) for k in keep):
                n = len(id_re.findall(p.read_bytes().decode("utf-8", "ignore")))
                if n:
                    sid = next((part[:8] for part in p.parts if len(part) >= 36 and part[8:9] == "-"), p.name[:8])
                    excluded[sid] = excluded.get(sid, 0) + n
                continue
            files += 1
            text = p.read_bytes().decode("utf-8", "ignore")
            counts["test_id"] += len(id_re.findall(text))
            for lit in LITERALS:
                counts[lit] += text.count(lit)
    return {"files": files, "counts": dict(+counts), "test_id_hits": counts["test_id"],
            "scope": f"sessions {keep}" if keep else "all -workspace-worktrees-* sessions",
            "out_of_scope_test_id_hits_by_session": excluded}


def main() -> int:
    full = "--full" in sys.argv
    cands = [a for a in sys.argv[1:] if not a.startswith("--")] or list(P.CANDIDATES)
    c = json.loads(P.PUBLISH_CACHE.read_text())
    id_re = re.compile("|".join(re.escape(t) for t in c["test_ids"]))
    res = {cand: scan(cand, id_re) for cand in cands}
    if P.LEDGER_PREFIX == "CE2":
        for cand in cands:
            res[cand]["ce2"] = ce2_extras(cand)
    merged = {**(P.read_json(P.PUSHED / "isolation_scan.json", {}) or {}), **res}
    if full:
        merged["_orchestrating_sessions"] = scan_sessions(id_re)
    P.write_json(P.AW_STATE / "scan.json", merged)
    P.write_json(P.PUSHED / "isolation_scan.json", merged)
    import status_doc
    sess = merged.get("_orchestrating_sessions") if full else None
    status_doc.append("result", "P6" if full else "P4", "isolation scan",
                      "Isolation scan (counts only): " + "; ".join(
                          f"{k}: test-id hits {v['test_id_hits']}" + (" — ISOLATION BREACH" if v["isolation_breach"] else "")
                          + (f"; models {sorted(v['ce2']['model_usage_keys'])}, other models {v['ce2']['other_models']}"
                             f"; J1 in {v['ce2']['j1_iterations']} iteration(s) ok={v['ce2']['j1_all_ok']}"
                             f"; K on the command line {v['ce2']['k_se_cmdline']} ok={v['ce2']['k_ok']}"
                             if "ce2" in v else "")
                          for k, v in res.items())
                      + (f"; orchestrating sessions: test-id hits {sess['test_id_hits']} over {sess['files']} files"
                         if sess else "")
                      + ". Literal-string counts per location are in the pushed scan file.",
                      done_through="P6/scan" if full else None, next_unit="P7/final" if full else None,
                      extra={"candidate": None if full else cands[0]},
                      artifacts=["STATE/isolation_scan.json"], subject="P6 scan" if full else f"P4 scan {cands[0]}")
    print(json.dumps({k: {"test_id_hits": v["test_id_hits"]} for k, v in merged.items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
