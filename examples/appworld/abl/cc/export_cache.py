"""Trusted export of the evaluator-cache records abl_cc needs at a remote host (docs/ABLATIONS.md §10.2; ABL-0361).
Copies, byte for byte, the main-namespace cache records of the seed tree (the shared P3 baseline: a seed copy must
stay free) and of every candidate tree abl_cc has evaluated (resubmissions stay free). Records are gold-free
(the evaluator drops the failure trace). Prints counts and hashes only.

  python -I export_cache.py OUT_DIR
"""
import hashlib, json, shutil, sys
from pathlib import Path
EX = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(EX / "scripts"), str(EX / "common")]
import awrest as P  # noqa: E402
import evaluator as E  # noqa: E402

out = Path(sys.argv[1]) / "cache" / "main"
trees = {E.seed_hash()[:16]}
for l in (P.AW_STATE / "abl_cc" / "evals.jsonl").read_text().splitlines():
    d = json.loads(l)
    if d.get("state") == "done" and d.get("cand"):
        for c in (P.AW_STATE / "abl_cc" / "cands").glob(d["cand"] + "*"):
            trees.add(E.tree_hash(c)[:16])
lst, n = [], 0
for t in sorted(trees):
    src = E.CACHE / "main" / t
    if not src.is_dir():
        continue
    shutil.copytree(src, out / t, dirs_exist_ok=True)
    for f in sorted((out / t).glob("*.json")):
        lst.append(f"{t}/{f.name} {hashlib.sha256(f.read_bytes()).hexdigest()}")
        n += 1
(out.parent / "LISTING.sha256").write_text("\n".join(lst) + "\n")
print(json.dumps({"trees": len(trees), "records": n,
                  "listing_sha256": hashlib.sha256(("\n".join(lst) + "\n").encode()).hexdigest()}))
