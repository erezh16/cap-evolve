"""Interim progress comments on skillberry-ai/cap-evolve#804 (user instruction 2026-10-14; ledger CP-0003).

  python3 -I post_update.py --title "..." --body-file body.md     # any milestone
  post_ace_progress(step, n)                                     # called by run_ace.py every N steps

Every body passes the publishing content filter of plan §10.2 (no task id, .env string, instruction
8-gram or supervisor contact) before it is posted. Each post is recorded in a ledger entry
(kind `posted`, `post: interim-<k>`) with its URL. The final results comment (P10) is separate.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import awpaths as P  # noqa: E402
import status_doc  # noqa: E402

REPO_SLUG = "skillberry-ai/cap-evolve"
ISSUE = "804"
COUNTER = P.AW_STATE / "interim_posts.json"


def next_k() -> int:
    c = P.read_json(COUNTER, {"k": 0}) or {"k": 0}
    return c["k"] + 1


def post(title: str, body: str) -> str:
    k = next_k()
    full = f"## ACE smoke test, interim update {k}: {title} (partial, do not cite)\n\n{body.strip()}\n\n" \
           f"Ledger: `docs/EVAL_SMOKE_TEST_ACE_STATUS.md` on branch `{P.BRANCH}` of the `erezh16` fork. " \
           f"Plan: `docs/EVAL_SMOKE_TEST_ACE.md`.\n"
    v = status_doc.violations(full)
    if v:
        raise status_doc.Refused(f"interim post refused by the content filter: {v}")
    tmp = P.AW_STATE / f".post-{k}.md"
    tmp.write_text(full)
    r = subprocess.run(["gh", "issue", "comment", ISSUE, "-R", REPO_SLUG, "--body-file", str(tmp)],
                       capture_output=True, text=True, check=True)
    url = r.stdout.strip().splitlines()[-1]
    tmp.unlink()
    P.write_json(COUNTER, {"k": k})
    prev = status_doc.last_entry()
    status_doc.append("posted", prev.get("phase", "?"), "interim #804",
                      f"Interim update {k} posted on #804: {url} ({title}).",
                      extra={"post": f"interim-{k}", "url": url}, subject=f"posted interim {k}")
    return url


def post_ace_progress(step: int, n: int) -> str:
    prog = P.read_json(P.PUSHED / "ace" / "progress.json")
    rows = prog["rows"]
    last = rows[-1]
    spend = prog["spend"]
    tin = sum(v["input"] for v in spend.values()) / 1e6
    tout = sum(v["output"] for v in spend.values()) / 1e6
    usd = tin * 2 + tout * 10
    passed = sum(1 for r in rows if r.get("success"))
    curated = sum(1 for r in rows if r.get("curated"))
    lint = sum(r.get("lint_drop", 0) for r in rows)
    cap = sum(r.get("cap_drop", 0) for r in rows)
    dedup = sum(1 for r in rows if r.get("dedup"))
    ctx = sum(1 for r in rows if r.get("context_exceeded"))
    term = {}
    for r in rows:
        term[r.get("termination")] = term.get(r.get("termination"), 0) + 1
    body = (f"ACE offline no-GT adaptation on the official `train` split: **{step} of {n} steps done** "
            f"(batch size 1, Generator = gpt-oss-120b in the common harness, Reflector / Curator = "
            f"`aws/claude-sonnet-5-5`).\n\n"
            f"| item | value |\n|---|---|\n"
            f"| playbook | {last['pb_bullets']} bullets, {last['pb_chars']:,} chars, {last['pb_tokens']:,} tokens "
            f"(cap {prog['m_cap']:,}) |\n"
            f"| steps curated (episode ended by `complete_task` / cost cap) | {curated} of {step} |\n"
            f"| episode terminations | {', '.join(f'{k} {v}' for k, v in sorted(term.items()))} |\n"
            f"| training episodes passing (search-time, train, not a result) | {passed} of {step} |\n"
            f"| lint_drop / cap_drop bullets, dedup runs | {lint} / {cap}, {dedup} |\n"
            f"| context_exceeded episodes | {ctx} |\n"
            f"| optimizer tokens (non-cache-read) | {tin:.2f}M in / {tout:.2f}M out (≈ ${usd:.2f} at proxy list prices) |\n"
            f"| counted rollouts | {prog['rollouts']} |\n\n"
            f"No test data has been touched (test root locked; per-step isolation scan counts are in the "
            f"pushed `progress.json`).")
    return post(f"ACE adaptation {step}/{n}", body)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--body-file", required=True)
    a = ap.parse_args()
    print(post(a.title, Path(a.body_file).read_text()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
