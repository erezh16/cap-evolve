#!/usr/bin/env python3
"""B2: copy REST's lint cache and publishing cache into the CE2 AW_STATE (docs/EVAL_APPWORLD_CE2.md §6.2 B2).

  . examples/appworld/ce2/env.sh && python3 -I examples/appworld/ce2/copy_caches.py

A trusted script (rule R1): REST's AW_STATE is sealed for every agent, so the copy is done here, byte for byte,
and only sha256 values, sizes and the caches' entry counts are printed (never ids, 8-grams or contacts). Both
files stay mode 600. Nothing else is copied from REST's state.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

REST_STATE = Path("/workspace/aw_rest/state")
FILES = ("lint_cache.json", "publish_cache.json")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    dst_root = Path(os.environ.get("AW_STATE", ""))
    if os.environ.get("AW_PROFILE") not in ("ce2", "ce3", "testall") or dst_root.resolve() == REST_STATE.resolve():
        sys.exit("copy_caches: source ce2/env.sh or test_all/env.sh first (AW_STATE must not be REST's)")
    dst_root.mkdir(parents=True, exist_ok=True)
    out = {}
    for name in FILES:
        src, dst = REST_STATE / name, dst_root / name
        before = sha(src)
        shutil.copyfile(src, dst)
        os.chmod(dst, 0o600)
        after = sha(dst)
        d = json.loads(dst.read_text())
        counts = {k: len(v) for k, v in d.items() if isinstance(v, (list, dict))}
        out[name] = {"sha256_src": before, "sha256_dst": after, "equal": before == after,
                     "bytes": dst.stat().st_size, "counts": counts}
    print(json.dumps(out, indent=1))
    return 0 if all(v["equal"] for v in out.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
