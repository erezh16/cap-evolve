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


def locations(c: str) -> dict[str, Path]:
    st = P.AW_STATE / c
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
        for p in files:
            if p.stat().st_size > 200_000_000:
                continue
            text = p.read_bytes().decode("utf-8", "ignore")
            hit = Counter({"test_id": len(id_re.findall(text))})
            for lit in LITERALS:
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


def scan_sessions(id_re: re.Pattern) -> dict:
    """R1.6: the orchestrating sessions' own transcripts (main session and its build sub-agents)."""
    roots = [p for p in (Path.home() / ".claude" / "projects").glob("-workspace-worktrees-*") if p.is_dir()]
    roots += [p for p in Path(f"/tmp/claude-{__import__('os').getuid()}").glob("-workspace-worktrees-*") if p.is_dir()]
    counts: Counter = Counter()
    files = 0
    for r in roots:
        for p in r.rglob("*"):
            if not p.is_file() or p.stat().st_size > 500_000_000:
                continue
            files += 1
            text = p.read_bytes().decode("utf-8", "ignore")
            counts["test_id"] += len(id_re.findall(text))
            for lit in LITERALS:
                counts[lit] += text.count(lit)
    return {"files": files, "counts": dict(+counts), "test_id_hits": counts["test_id"]}


def main() -> int:
    full = "--full" in sys.argv
    cands = [a for a in sys.argv[1:] if not a.startswith("--")] or list(P.CANDIDATES)
    c = json.loads(P.PUBLISH_CACHE.read_text())
    id_re = re.compile("|".join(re.escape(t) for t in c["test_ids"]))
    res = {cand: scan(cand, id_re) for cand in cands}
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
