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
    if getattr(P, "TESTABL", False):
        ref = (f"Plan: `docs/TEST_ABL.md` and ledger `docs/{P.LEDGER.name}`, both on branch `{P.BRANCH}` of the "
               f"`erezh16/cap-evolve` fork.")
    elif P.TESTALL:
        ref = (f"Plan: `docs/TEST_ALL.md` (branch `cap-evolve-impr2`); ledger: `docs/{P.LEDGER.name}` on branch "
               f"`{P.BRANCH}` of the `erezh16/cap-evolve` fork.")
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
    url = _comment(cand, tmp) if P.TESTALL else subprocess.run(
        ["gh", "issue", "comment", str(P.ISSUES[cand]), "-R", P.ISSUE_REPO, "--body-file", str(tmp)],
        capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1]
    tmp.unlink()
    done[f"{cand}/{key}"] = url
    P.write_json(POSTS, done)
    prev = S.last_entry()
    S.append("posted", prev.get("phase", "?"), f"posted {cand}",
             f"Posted '{title}' on #{P.ISSUES[cand]} ({cand}): {url}", extra={"post": f"{cand}/{key}", "url": url},
             subject=f"posted {cand} {key}")
    return url


def _post_arms() -> list[str]:
    """TEST_ABL: the arms whose issue is open; TEST_ALL: all arms."""
    return [a for a in P.TIMER_ORDER if a in P.ISSUES] if getattr(P, "TESTABL", False) else list(P.ARMS)


class PostFailed(RuntimeError):
    pass


def _comment(cand: str, body_file: Path) -> str:
    """TEST_ALL §12.2: one comment through the REST API; on HTTP 403 or 429 wait for Retry-After (60 s if absent) and
    retry, up to 5 times. A post that still fails raises PostFailed (the caller records an `error` entry)."""
    import json
    import time
    payload = P.AW_STATE / f".post-{cand}.json"
    payload.write_text(json.dumps({"body": body_file.read_text()}))
    try:
        for attempt in range(6):
            r = subprocess.run(["gh", "api", "-i", "-X", "POST", f"repos/{P.ISSUE_REPO}/issues/{P.ISSUES[cand]}/comments",
                                "--input", str(payload)], capture_output=True, text=True)
            head, _, rest = r.stdout.partition("\r\n\r\n") if "\r\n\r\n" in r.stdout else r.stdout.partition("\n\n")
            status = int((head.split() or ["0", "0"])[1]) if head.startswith("HTTP") else 0
            if r.returncode == 0 and 200 <= status < 300:
                return json.loads(rest)["html_url"]
            if status in (403, 429) and attempt < 5:
                ra = [l.split(":", 1)[1].strip() for l in head.splitlines() if l.lower().startswith("retry-after:")]
                wait = int(ra[0]) if ra and ra[0].isdigit() else 60
                P.progress_log("autopost", "-", f"HTTP {status} on #{P.ISSUES[cand]} ({cand}); retry {attempt + 1}/5 in {wait}s")
                time.sleep(wait)
                continue
            raise PostFailed(f"comment on #{P.ISSUES[cand]} ({cand}) failed: HTTP {status}, exit {r.returncode}")
        raise PostFailed(f"comment on #{P.ISSUES[cand]} ({cand}) failed after 5 retries")
    finally:
        payload.unlink(missing_ok=True)


def post_all(key: str, title: str, body: str, arms=None, gap_s: float = 3.0) -> dict:
    """TEST_ALL §12.2 milestones: the same keyed post on every arm's issue, sequentially, 3 s apart. ``body`` may use
    {CAND} (the arm id) and {NAME} (its method name); it may also be a callable arm -> body. Failures become `error`
    entries and do not stop the remaining arms."""
    import time
    out = {}
    for i, c in enumerate(arms or _post_arms()):
        b = body(c) if callable(body) else body.replace("{CAND}", c).replace("{NAME}", P.METHOD_NAMES[c])
        try:
            out[c] = post(c, key, title.replace("{NAME}", P.METHOD_NAMES[c]), b)
        except PostFailed as e:
            prev = S.last_entry()
            S.append("error", prev.get("phase", "?"), f"post failed {c}", f"Milestone post '{key}' on {c}: {e}.",
                     extra={"arm": c, "post": f"{c}/{key}"}, subject=f"post failed {c} {key}")
            out[c] = None
        if out[c] and i < len(arms or _post_arms()) - 1:
            time.sleep(gap_s)
    return out


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
    if a.cand == "all" and P.TESTALL and not a.queue:
        for c, u in post_all(a.key, a.title, body).items():
            print(c, u or "(already posted or failed)")
        return 0
    for c in ((_post_arms() if P.TESTALL else P.CANDIDATES) if a.cand == "all" else [a.cand]):
        if a.queue:
            print(c, "queued", queue(c, a.key, a.title, body.replace("{CAND}", c)))
        else:
            print(c, post(c, a.key, a.title, body.replace("{CAND}", c)) or "(already posted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
