#!/usr/bin/env python3
"""TEST_ABL: count infra-error kinds in a window's records (trusted script, rule R1). Prints counts and the first
120 characters of each distinct error kind only after the content filter passes it; never a task id or outcome.

  . examples/appworld/test_abl/env.sh && python3 -I examples/appworld/test_abl/infra_counts.py final2
"""
import collections, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import awrest as P  # noqa: E402
import status_doc as S  # noqa: E402

d = P.AW_STATE / sys.argv[1] / "records"
kinds, arms = collections.Counter(), collections.Counter()
for p in d.glob("*.json"):
    r = json.loads(p.read_text())
    e = r.get("infra_error")
    if e:
        k = re.sub(r"\d+", "N", str(e))[:120]
        kinds[k] += 1
        arms[r.get("arm")] += 1
out = {}
for k, n in kinds.most_common(8):
    out[k if not S.violations(k) else "<withheld by the content filter>"] = n
print(json.dumps({"records": len(list(d.glob('*.json'))), "infra_by_arm": arms, "kinds": out}, indent=1))
