"""P7: the post-search isolation scan of eval 5 (docs/EVAL_APPWORLD_5.md §9, §8).

  venv-aw/bin/python -I scan5.py [cand ...]      # default: all five; writes AW_STATE/scan.json + pushed counts

Greps every optimizer-side record of each candidate — the optimizer prompt/response log (llm_calls.jsonl),
the proposer session logs (claude_sessions/*: meta.json files_read + tool_summary, events.jsonl, tools/*),
the optimizer workspaces (/tmp/aw5_opt/<cand>, the WikiSkill workspace, the SkillOpt out_root, the GEPA run
dir) and the frozen artifact — for: test ids (test_normal + test_challenge), the strings test_normal,
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
import aw5 as P  # noqa: E402
import sandbox5 as SB  # noqa: E402

LITERALS = ("test_normal", "test_challenge", "root_full", "ground_truth", "answer.json", "compiled_solution",
            "generate/tasks", "src/appworld/apps")


def locations(c: str) -> dict[str, Path]:
    st = P.AW_STATE / c
    return {"optimizer calls": st / "llm_calls.jsonl", "proposer sessions": st / "claude_sessions",
            "optimizer workspace (/tmp)": SB.OPT_ROOT / c, "wikiskill workspace": st / "workspace",
            "skillopt out_root": st / "out_root", "gepa run dir": st / "gepa_run",
            "frozen artifact": P.PUSHED / c / "artifact"}


def scan(c: str, id_re: re.Pattern) -> dict:
    out = {}
    for name, root in locations(c).items():
        if not root.exists():
            continue
        # the harness's own sandbox settings name the denied paths; they are not optimizer output
        files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()
                                                and not p.name.endswith("settings.json")]
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
    # the Meta-Harness wrapper's own record of every file the proposer Read
    reads: Counter = Counter()
    for meta in (P.AW_STATE / c / "claude_sessions").glob("*/meta.json") if (P.AW_STATE / c / "claude_sessions").exists() else []:
        m = json.loads(meta.read_text())
        for path in (m.get("files_read") or {}):
            top = path.split("/")[0] if not path.startswith("/") else "ABSOLUTE:" + "/".join(path.split("/")[:4])
            reads[top] += 1
    res = {"locations": out, "proposer_files_read_by_top_dir": dict(reads),
           "test_id_hits": sum(v["counts"].get("test_id", 0) for v in out.values())}
    res["isolation_breach"] = res["test_id_hits"] > 0
    return res


def main() -> int:
    cands = sys.argv[1:] or list(P.CANDIDATES)
    c = json.loads(P.PUBLISH_CACHE.read_text())
    id_re = re.compile("|".join(re.escape(t) for t in c["test_ids"]))
    res = {cand: scan(cand, id_re) for cand in cands}
    # merge: a per-candidate scan updates its own entry and keeps the others
    merged = {**(P.read_json(P.PUSHED / "isolation_scan.json", {}) or {}), **res}
    P.write_json(P.AW_STATE / "scan.json", merged)
    P.write_json(P.PUSHED / "isolation_scan.json", merged)
    import status_doc
    status_doc.append("result", "P7", "isolation scan",
                      "Post-search isolation scan (counts only): " + "; ".join(
                          f"{k}: test-id hits {v['test_id_hits']}" + (" — ISOLATION BREACH" if v["isolation_breach"] else "")
                          for k, v in res.items()) + ". Literal-string counts per location are in the pushed scan file.",
                      done_through="P7/scan" if not sys.argv[1:] else None,
                      next_unit="P8/final" if not sys.argv[1:] else None, extra={"candidate": None},
                      artifacts=["STATE/isolation_scan.json"], subject="P7 scan")
    print(json.dumps({k: {"test_id_hits": v["test_id_hits"]} for k, v in res.items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
