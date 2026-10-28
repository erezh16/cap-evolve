#!/usr/bin/env python3
"""B2 (docs/TEST_ABL.md §7): copy the ablation run's lint and publishing caches into this run's AW_STATE.

  . examples/appworld/test_abl/env.sh && python3 -I examples/appworld/test_abl/copy_caches.py

A trusted script (rule R1): the caches hold test ids, 8-grams and contacts, so only sha256 values, sizes and entry
counts are printed. Both copies are mode 600. Nothing else is copied.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

SRC = Path("/workspace/aw_abl/state")
FILES = ("lint_cache.json", "publish_cache.json")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    dst_root = Path(os.environ.get("AW_STATE", ""))
    if os.environ.get("AW_PROFILE") != "testabl" or dst_root.resolve() == SRC.resolve():
        sys.exit("copy_caches: source test_abl/env.sh first")
    out = {}
    for name in FILES:
        src, dst = SRC / name, dst_root / name
        shutil.copyfile(src, dst)
        os.chmod(dst, 0o600)
        d = json.loads(dst.read_text())
        out[name] = {"sha256_src": sha(src), "sha256_dst": sha(dst), "equal": sha(src) == sha(dst),
                     "bytes": dst.stat().st_size, "counts": {k: len(v) for k, v in d.items() if isinstance(v, (list, dict))}}
    print(json.dumps(out, indent=1))
    return 0 if all(v["equal"] for v in out.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
