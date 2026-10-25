"""Driver of the abl_cc arm (docs/ABLATIONS.md §10.2): plain Claude Code, one session, no cap-evolve code.
Source abl/env.sh first; run in venv-abl.

  python -I run_cc.py setup [--root DIR]     # the working directory: seed surfaces, reference docs, eval scripts, git
  python -I run_cc.py check-config           # the config dir is empty and PROMPT.txt has the plan's sha256
  python -I run_cc.py freeze                 # champion = the workdir's three surfaces (or the last lint-clean one)
  python -I run_cc.py progress               # pushed progress.json (evaluations, rollouts, best evaluated val)

The session itself is started by launch_cc.sh through the same PATH shim as every arm (sandbox_cc/claude).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ABL = HERE.parent
EX = ABL.parent
sys.path[:0] = [str(ABL), str(EX / "common"), str(EX / "scripts")]
import awrest as P  # noqa: E402

ARM = "abl_cc"
ROOT = P.RUN_ROOTS[ARM]
WORK = ROOT / "work"
CONFIG = ROOT / "config"
STATE = P.AW_STATE / ARM
PUSHED = P.PUSHED / ARM
PROMPT = HERE / "PROMPT.txt"
PROMPT_SHA256 = "12e145ec240640337157fa4172ffe914c138c2e6e4942fc9f2b2e4313a3d7456"   # plan §10.2, the three lines
MAX_TURNS = 1200                                    # 6 × the 200 turns of a cap-evolve session (§10.2)
SURFACES = ("policy/instructions.txt", "tools/helpers.py", "tools/api_notes.json")


def setup(root: Path = ROOT) -> Path:
    work = root / "work"
    if (work / ".git").exists():
        return work
    work.mkdir(parents=True, exist_ok=True)
    for rel in SURFACES:
        (work / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(P.SEED_CAP / rel, work / rel)
    (work / "reference").mkdir(exist_ok=True)
    for f in ("api_index.md", "react_agent_notes.md"):
        shutil.copy2(P.REFERENCE / f, work / "reference" / f)
    for f in ("eval_candidate", "eval_status"):
        shutil.copy2(HERE / f, work / f)
        (work / f).chmod(0o755)
    (work / ".eval" / "requests").mkdir(parents=True, exist_ok=True)
    (work / ".eval" / "results").mkdir(parents=True, exist_ok=True)
    git = ["git", "-C", str(work), "-c", "user.name=abl_cc", "-c", "user.email=abl_cc@localhost"]
    subprocess.run(["git", "init", "-q", str(work)], check=True)
    (work / ".git" / "info" / "exclude").write_text(".eval/\n")
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "seed"], check=True)
    (root / "config").mkdir(exist_ok=True)
    return work


def check_config() -> dict:
    sha = hashlib.sha256(PROMPT.read_bytes()).hexdigest()
    entries = sorted(p.name for p in CONFIG.iterdir()) if CONFIG.exists() else None
    forbidden = [p.name for p in WORK.iterdir() if p.name in ("CLAUDE.md", ".claude", ".mcp.json")] if WORK.exists() else []
    res = {"prompt_sha256": sha, "prompt_ok": sha == PROMPT_SHA256, "config_dir_empty": entries == [],
           "config_entries": len(entries or []), "workdir_forbidden_entries": forbidden,
           "ok": sha == PROMPT_SHA256 and entries == [] and not forbidden}
    return res


def _sh(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def progress(stage: str = "") -> dict:
    ev = P.read_jsonl(STATE / "evals.jsonl")
    done = [e for e in ev if e.get("state") == "done"]
    best = max((e["mean_reward"] for e in done if e.get("lint") == "ok"), default=None)
    import opt_llm
    t = opt_llm.totals(ARM)
    pr = {"stage": stage or "plain Claude Code session", "arm": ARM,
          "evaluations_done": len(done), "evaluation_requests": len(ev),
          "refused": sum(1 for e in ev if e.get("state") == "refused"),
          "lint_rejects": sum(1 for e in done if e.get("lint") == "rejected"),
          "counted_rollouts": len(P.read_jsonl(STATE / "rollouts.jsonl")),
          "cache_hits": len(P.read_jsonl(STATE / "cache_hits.jsonl")),
          "evaluations": [{k: e.get(k) for k in ("t", "cand", "lint", "mean_reward", "fresh", "rollouts_used")}
                          for e in done],
          "best_search_score": best, "best_search_label": "best evaluated mean val = train ∪ dev (147), a fit "
                                                          "metric, selection-biased; not necessarily the champion",
          "optimizer": {"calls": t["calls"], "prompt_tokens": t["prompt_tokens"],
                        "completion_tokens": t["completion_tokens"], "cache_read": t["cache_read"],
                        "cache_write": t["cache_write"], "proxy_usd": opt_llm.proxy_usd(t), "seconds": t["seconds"]},
          "max_turns": MAX_TURNS}
    P.write_json(PUSHED / "progress.json", pr)
    return pr


def freeze() -> int:
    """§10.2 champion: the workdir's three surfaces when the session ends; if they fail the lint, the last lint-clean
    candidate the daemon evaluated (a deviation, recorded). The best-evaluated candidate is a secondary artifact."""
    import evaluator as E
    files = {rel: (WORK / rel).read_text(encoding="utf-8") for rel in SURFACES if (WORK / rel).is_file()}
    cdir = E.materialize(ARM, files)
    v = E.lint(cdir)
    deviation = None
    if v:
        done = [e for e in P.read_jsonl(STATE / "evals.jsonl") if e.get("state") == "done" and e.get("lint") == "ok"]
        if not done:
            raise SystemExit("abl_cc freeze: the workdir fails the lint and no lint-clean candidate was evaluated")
        cdir = next(d for d in (STATE / "cands").iterdir() if d.name == done[-1]["cand"])
        deviation = f"workdir failed the lint ({len(v)} violations); champion = last lint-clean evaluated candidate"
    th = E.tree_hash(cdir)
    inert = th == E.seed_hash()
    dst, art = STATE / "champion", PUSHED / "artifact"
    for d in (dst, art):
        shutil.rmtree(d, ignore_errors=True)
        shutil.copytree(cdir, d, ignore=shutil.ignore_patterns(".done"))
    done = [e for e in P.read_jsonl(STATE / "evals.jsonl") if e.get("state") == "done" and e.get("lint") == "ok"]
    best = max(done, key=lambda e: e["mean_reward"], default=None)
    cc = [x for x in P.read_jsonl(STATE / "optimizer_usage.jsonl")]
    fz = {"arm": ARM, "tree_sha256": th, "seed_tree_sha256": E.seed_hash(), "inert": inert,
          "label": "inert" if inert else "", "deviation": deviation,
          "champion_evaluated": any(e["cand"] == th[:12] for e in done),
          "champion_val": next((e["mean_reward"] for e in reversed(done) if e["cand"] == th[:12]), None),
          "best_evaluated": best and {"cand": best["cand"], "val": best["mean_reward"]},
          "sessions": len(cc), "session_stop": cc[-1].get("finish_reason") if cc else None,
          "workdir_commits": int(subprocess.run(["git", "-C", str(WORK), "rev-list", "--count", "HEAD"],
                                                capture_output=True, text=True).stdout.strip() or 0)}
    P.write_json(art / "FREEZE.json", fz)
    progress("frozen" + (" (inert)" if inert else ""))
    print(json.dumps({k: fz[k] for k in ("tree_sha256", "inert", "deviation", "best_evaluated")}))
    return 0


def main() -> int:
    if P.LEDGER_ID != "ABL":
        raise SystemExit("run_cc.py: source abl/env.sh first")
    cmd = sys.argv[1]
    if cmd == "setup":
        root = Path(sys.argv[sys.argv.index("--root") + 1]) if "--root" in sys.argv else ROOT
        print(setup(root))
        return 0
    if cmd == "check-config":
        r = check_config()
        print(json.dumps(r))
        return 0 if r["ok"] else 1
    if cmd == "progress":
        print(json.dumps(progress(), indent=1)[:4000])
        return 0
    if cmd == "freeze":
        return freeze()
    raise SystemExit(f"unknown command {cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
