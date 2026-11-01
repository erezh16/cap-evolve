#!/usr/bin/env python3
"""TEST_ABL A20: move an invalid window's records aside (trusted script, rule R1; nothing is opened or printed but
counts), so a relaunch re-runs every cell. The order file is kept: it is regenerated from the same seed and must
match its recorded sha256.

  . examples/appworld/test_abl/env.sh && python3 -I examples/appworld/test_abl/set_aside.py final2
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import awrest as P  # noqa: E402

d = P.AW_STATE / sys.argv[1]
src = d / "records"
dst = d / f"records_invalid_{P.utcnow().replace(':', '')}"
n = len(list(src.glob("*.json")))
src.rename(dst)
src.mkdir()
pr = P.PUSHED / sys.argv[1] / "progress.json"
if pr.exists():
    pr.rename(pr.with_name("progress_invalid.json"))
print(json.dumps({"moved_records": n, "to": dst.name, "records_now": len(list(src.glob('*.json')))}))
