#!/usr/bin/env python3
"""B4: reuse REST's shared seed baseline (docs/EVAL_APPWORLD_CE2.md §7.4, decision D5). Trusted script (rule R1).

  . examples/appworld/ce2/env.sh && python3 -I examples/appworld/ce2/seed_reuse.py

1. the tree hash of examples/appworld/seed_capability/ on eval-ce2 equals SEED_HASH (REST CP-0020/0022);
2. adapters/aw_agent.py (it holds the model config), seed_capability/, common/evaluator.py and the AppWorld patch
   are byte-identical to REST commit a0c85b4 (the P3 code);
3. copies /workspace/aw_rest/state/cache/main/<SEED_HASH[:16]>/ (147 files) byte for byte into the CE2 AW_STATE;
   the sha256 of the sorted "<file> <sha256>" list is recorded before and after (equal). Nothing else is copied;
4. checks: 147 records, ids = train.txt ∪ dev.txt exactly, trial seed 100, no infra error, no `trace` key at any
   depth, and train / dev / union TGC equal REST's pushed seed/baseline.json;
5. creates AW_STATE/SEED_BASELINE_DONE. The ledger entry is written by the caller.

Prints flags, counts, aggregates and hashes only (no ids, no record content).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(EX / "scripts"), str(EX / "common")]
import awrest as P  # noqa: E402

SEED_HASH = "85a0da9cec2206a7bc683c11d60b5cb0acac7328d43c6e9197324d1e45971f3c"
P3_COMMIT = "a0c85b4"
SRC = Path("/workspace/aw_rest/state/cache/main") / SEED_HASH[:16]
IDENTICAL = ("examples/appworld/adapters/aw_agent.py", "examples/appworld/seed_capability",
             "examples/appworld/common/evaluator.py", "examples/appworld/patches/appworld-extra-headers.patch")


def listing_sha(d: Path) -> tuple[str, int]:
    rows = sorted(f"{p.name} {hashlib.sha256(p.read_bytes()).hexdigest()}" for p in d.iterdir() if p.is_file())
    return hashlib.sha256("\n".join(rows).encode()).hexdigest(), len(rows)


def has_key(o, key: str) -> bool:
    if isinstance(o, dict):
        return key in o or any(has_key(v, key) for v in o.values())
    if isinstance(o, list):
        return any(has_key(v, key) for v in o)
    return False


def main() -> int:
    if os.environ.get("AW_PROFILE") != "ce2" or str(P.AW_STATE) != "/workspace/aw_ce2/state":
        sys.exit("seed_reuse: source ce2/env.sh first")
    import evaluator as E
    res: dict = {}
    h = E.seed_hash()
    res["1_seed_hash_ok"] = h == SEED_HASH
    res["2_code_identical_to_a0c85b4"] = {
        f: subprocess.run(["git", "-C", str(P.REPO), "diff", "--quiet", P3_COMMIT, "HEAD", "--", f]).returncode == 0
        for f in IDENTICAL}
    if not res["1_seed_hash_ok"] or not all(res["2_code_identical_to_a0c85b4"].values()):
        print(json.dumps(res, indent=1))
        return 1
    dst = E.CACHE / "main" / SEED_HASH[:16]
    before, n_src = listing_sha(SRC)
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    for p in SRC.iterdir():
        if p.is_file():
            shutil.copyfile(p, dst / p.name)
    after, n_dst = listing_sha(dst)
    res["3_copy"] = {"files_src": n_src, "files_dst": n_dst, "listing_sha256_before": before,
                     "listing_sha256_after": after, "equal": before == after}
    other = [x.name for x in (E.CACHE / "main").iterdir() if x.name != SEED_HASH[:16]] + \
            ([x.name for x in (E.CACHE / "accept").iterdir()] if (E.CACHE / "accept").exists() else [])
    tr, dv = P.read_split("train"), P.read_split("dev")
    recs = {}
    for p in dst.iterdir():
        tid, s = p.stem.rsplit("__s", 1)
        recs[tid] = (int(s), json.loads(p.read_text()))
    rew = lambda ids: round(sum(recs[t][1]["reward"] for t in ids) / len(ids), 4)  # noqa: E731
    r = subprocess.run(["git", "-C", str(P.REPO), "show", "origin/eval-rest:docs/EVAL_APPWORLD_REST_STATE/seed/baseline.json"],
                       capture_output=True, text=True, check=True)
    bl = json.loads(r.stdout)
    res["4_checks"] = {
        "records": len(recs), "ids_equal_train_union_dev": set(recs) == set(tr) | set(dv) and len(recs) == 147,
        "all_seed_100": all(s == 100 for s, _ in recs.values()),
        "infra_errors": sum(1 for _, x in recs.values() if x.get("error")),
        "trace_key_present": sum(1 for _, x in recs.values() if has_key(x, "trace")),
        "tgc": {"train": rew(tr), "dev": rew(dv), "union": rew(tr + dv)},
        "rest_baseline_tgc": {"train": bl["train"]["tgc"], "dev": bl["dev"]["tgc"], "union": bl["union"]["tgc"]},
        "other_cache_dirs_in_ce2": len(other)}
    c = res["4_checks"]
    c["tgc_match"] = all(abs(c["tgc"][k] - c["rest_baseline_tgc"][k]) < 1e-4 for k in ("train", "dev", "union"))
    res["ok"] = (res["3_copy"]["equal"] and n_src == 147 and c["ids_equal_train_union_dev"] and c["all_seed_100"]
                 and c["infra_errors"] == 0 and c["trace_key_present"] == 0 and c["tgc_match"]
                 and c["other_cache_dirs_in_ce2"] == 0)
    if res["ok"]:
        P.atomic_write(E.SEED_DONE, f"reused from REST P3 (2026-10-20), 147 records, {P.utcnow()}\n")
        P.update_manifest(seed={"SEED_HASH": SEED_HASH, "reused_from": "REST P3, commit a0c85b4",
                                "records": 147, "listing_sha256": after, "tgc": c["tgc"]})
    res["5_seed_baseline_done"] = E.SEED_DONE.exists()
    P.write_json(P.AW_STATE / "seed_reuse.json", res)
    print(json.dumps(res, indent=1))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
