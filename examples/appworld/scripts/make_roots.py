"""B4: build root_opt from root_full (train + dev ids and _base_), check it holds no test id, lock root_full.

  python3 -I make_roots.py            # build + check + chmod 000 root_full
  python3 -I make_roots.py --check    # check only (used by resume.py)
Prints counts only.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import awpaths as P  # noqa: E402


def check() -> dict:
    cache = json.loads(P.LINT_CACHE.read_text())
    test_ids = cache["test_ids"]
    pat = P.AW_STATE / ".test_ids.pat"
    pat.write_text("\n".join(test_ids) + "\n")
    r = subprocess.run(["grep", "-rlF", "-f", str(pat), str(P.ROOT_OPT)], capture_output=True, text=True)
    pat.unlink()
    hits = [x for x in r.stdout.splitlines() if x]
    tasks = sorted(p.name for p in (P.ROOT_OPT / "data" / "tasks").iterdir())
    datasets = sorted(p.name for p in (P.ROOT_OPT / "data" / "datasets").iterdir())
    names_hit = [t for t in tasks if t in set(test_ids)]
    return {"task_dirs": len(tasks), "datasets": datasets, "test_id_hits": len(hits) + len(names_hit),
            "root_full_mode": oct(os.stat(P.ROOT_FULL).st_mode & 0o777)}


def build() -> None:
    src = P.ROOT_FULL / "data"
    dst = P.ROOT_OPT / "data"
    if P.ROOT_OPT.exists():
        shutil.rmtree(P.ROOT_OPT)
    (dst / "tasks").mkdir(parents=True)
    (dst / "datasets").mkdir()
    for name in ("api_docs", "base_dbs"):
        shutil.copytree(src / name, dst / name)
    for f in ("version.txt", "LICENSE", "README_BEFORE_SHARING.md", "CHANGELOG.md"):
        if (src / f).exists():
            shutil.copy2(src / f, dst / f)
    ids = []
    for split in ("train", "dev"):
        shutil.copy2(src / "datasets" / f"{split}.txt", dst / "datasets" / f"{split}.txt")
        ids += [x for x in (src / "datasets" / f"{split}.txt").read_text().split() if x]
    for t in ids + ["_base_"]:
        shutil.copytree(src / "tasks" / t, dst / "tasks" / t)


def main() -> int:
    if "--check" not in sys.argv:
        os.chmod(P.ROOT_FULL, 0o755)
        build()
        os.chmod(P.ROOT_FULL, 0o000)
    res = check()
    ok = res["task_dirs"] == 148 and res["datasets"] == ["dev.txt", "train.txt"] and res["test_id_hits"] == 0 \
        and res["root_full_mode"] == "0o0"
    res["ok"] = ok
    if "--check" not in sys.argv and ok:
        P.update_manifest(root_opt={"tree_sha256": P.sha256_tree(P.ROOT_OPT), **{k: res[k] for k in
                                    ("task_dirs", "datasets", "test_id_hits")}})
    print(json.dumps(res))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
