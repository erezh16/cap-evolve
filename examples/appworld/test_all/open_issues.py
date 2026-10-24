#!/usr/bin/env python3
"""B0 / §12.1 (docs/TEST_ALL.md): open the 13 tracking issues, one per arm, each with its projected plan as the body.

  . examples/appworld/test_all/env.sh && python3 -I examples/appworld/test_all/open_issues.py [--dry-run]

Idempotent: an arm whose number is already in manifest.json `issues`, or whose exact title is already an issue on
the repo, is not opened again (its number is adopted). Each number is written to manifest.json at once, so a crash
never opens a duplicate. Also records `hourly_offset_s` (§12.2). Bodies come from issue_bodies.py and pass the
content filter; issues are opened one at a time, 3 s apart. Exit non-zero unless all 13 exist.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "scripts"))
sys.path.insert(0, str(HERE))
import awrest as P  # noqa: E402
import issue_bodies as IB  # noqa: E402
import status_doc as S  # noqa: E402

LABELS = ("paper-experiment", "algorithm")


def title(arm: str) -> str:
    return f"AppWorld TEST_ALL: {P.METHOD_NAMES[arm]} ({arm}), test_normal × 5 trials (gpt-oss-120b)"


def existing() -> dict[str, int]:
    r = subprocess.run(["gh", "issue", "list", "-R", P.ISSUE_REPO, "--state", "all", "--limit", "200", "--search",
                        "\"AppWorld TEST_ALL\" in:title", "--json", "number,title"], capture_output=True, text=True,
                       check=True)
    return {x["title"]: x["number"] for x in json.loads(r.stdout)}


def main() -> int:
    dry = "--dry-run" in sys.argv
    P.update_manifest(hourly_offset_s=dict(P.HOURLY_OFFSET_S))
    res = IB.build(P.AW_STATE / "issue_bodies")
    bad = {a: v for a, v in res.items() if v["violations"] or v["chars"] > IB.LIMIT}
    if bad:
        print(json.dumps({"refused": bad}))
        return 1
    have = dict(P.manifest().get("issues") or {})
    ex = existing()
    for arm in P.ARMS:
        if arm in have:
            continue
        t = title(arm)
        if t in ex:
            have[arm] = ex[t]
            P.update_manifest(issues=have)
            print(json.dumps({"arm": arm, "issue": ex[t], "adopted": True}))
            continue
        if dry:
            print(json.dumps({"arm": arm, "would_open": t, "chars": res[arm]["chars"]}))
            continue
        cmd = ["gh", "issue", "create", "-R", P.ISSUE_REPO, "--title", t,
               "--body-file", str(P.AW_STATE / "issue_bodies" / f"{arm}.md")]
        for lab in LABELS:
            cmd += ["--label", lab]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(json.dumps({"arm": arm, "error": r.stderr.strip().splitlines()[-1:]}))
            return 1
        url = r.stdout.strip().splitlines()[-1]
        have[arm] = int(url.rstrip("/").rsplit("/", 1)[-1])
        P.update_manifest(issues=have)
        print(json.dumps({"arm": arm, "issue": have[arm], "url": url}))
        time.sleep(3)
    ok = all(a in have for a in P.ARMS)
    print(json.dumps({"issues": have, "all_13": ok}))
    return 0 if ok or dry else 1


if __name__ == "__main__":
    raise SystemExit(main())
