"""Progress and results posts on the five tracking issues (docs/EVAL_APPWORLD_REST.md §8, §14).

  python3 -I post.py --cand gepa --key accept --title "..." --body-file body.md     # one issue
  python3 -I post.py --cand all  --key accept --title "..." --body-file body.md     # the same body on all five

Every body passes the publishing content filter (§12.2: no task id, .env value, train/dev instruction 8-gram
or supervisor contact) before it is posted. A post is keyed (cand, key) in AW_STATE/posts.json and recorded
in a `posted` ledger entry with its URL; a key that was already posted is never posted again.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import awrest as P  # noqa: E402
import status_doc as S  # noqa: E402

POSTS = P.AW_STATE / "posts.json"
QUEUE = P.AW_STATE / "post_queue"           # drafts waiting for the user's go-ahead to post (§5)


def post(cand: str, key: str, title: str, body: str) -> str | None:
    done = P.read_json(POSTS, {}) or {}
    if f"{cand}/{key}" in done:
        return None
    if P.LEDGER_ID == "ABL":
        ref = (f"Plan: `docs/ABLATIONS.md`; ledger: `docs/{P.LEDGER.name}` on branch `{P.BRANCH}` of the "
               f"`erezh16/cap-evolve` fork.")
    elif P.LEDGER_PREFIX == "CE2":
        plan = "EVAL_APPWORLD_CE3.md` (base plan `docs/EVAL_APPWORLD_CE2.md`)" if P.LEDGER_ID == "CE3" else "EVAL_APPWORLD_CE2.md`"
        ref = (f"Plan: `docs/{plan}; ledger: `docs/{P.LEDGER.name}` on branch `{P.BRANCH}` of the "
               f"`erezh16/cap-evolve` fork.")
    else:
        ref = (f"Ledger and plan: `docs/EVAL_APPWORLD_REST.md` (section 18) on branch `{P.BRANCH}` of the "
               f"`erezh16/cap-evolve` fork.")
    full = f"## AppWorld {P.EVAL_NAME} — {title}\n\n{body.strip()}\n\n{ref}\n"
    v = S.violations(full)
    if v:
        raise S.Refused(f"post refused by the content filter: {v}")
    tmp = P.AW_STATE / f".post-{cand}-{key}.md"
    tmp.write_text(full)
    r = subprocess.run(["gh", "issue", "comment", str(P.ISSUES[cand]), "-R", P.ISSUE_REPO, "--body-file", str(tmp)],
                       capture_output=True, text=True, check=True)
    tmp.unlink()
    url = r.stdout.strip().splitlines()[-1]
    done[f"{cand}/{key}"] = url
    P.write_json(POSTS, done)
    prev = S.last_entry()
    S.append("posted", prev.get("phase", "?"), f"posted {cand}",
             f"Posted '{title}' on #{P.ISSUES[cand]} ({cand}): {url}", extra={"post": f"{cand}/{key}", "url": url},
             subject=f"posted {cand} {key}")
    return url


def queue(cand: str, key: str, title: str, body: str) -> Path:
    """Write a filtered draft to the local queue instead of posting (used until posting is authorized)."""
    v = S.violations(body)
    if v:
        raise S.Refused(f"draft refused by the content filter: {v}")
    QUEUE.mkdir(parents=True, exist_ok=True)
    p = QUEUE / f"{len(list(QUEUE.glob('*.json'))):03d}_{cand}_{key}.json"
    P.write_json(p, {"cand": cand, "key": key, "title": title, "body": body})
    return p


def flush() -> int:
    """Post every queued draft in order (each once), then remove it from the queue."""
    for p in sorted(QUEUE.glob("*.json")) if QUEUE.exists() else []:
        d = P.read_json(p)
        print(d["cand"], d["key"], post(d["cand"], d["key"], d["title"], d["body"]) or "(already posted)")
        p.unlink()
    return 0


def main() -> int:
    if sys.argv[1:] == ["flush"]:
        return flush()
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--body-file", required=True)
    ap.add_argument("--queue", action="store_true", help="write a draft to the local queue instead of posting")
    a = ap.parse_args()
    body = Path(a.body_file).read_text()
    for c in (P.CANDIDATES if a.cand == "all" else [a.cand]):
        if a.queue:
            print(c, "queued", queue(c, a.key, a.title, body.replace("{CAND}", c)))
        else:
            print(c, post(c, a.key, a.title, body.replace("{CAND}", c)) or "(already posted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
