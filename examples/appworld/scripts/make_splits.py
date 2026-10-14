"""B3 / rule S1: check the official splits and build the local lint cache (plan §4 B3, §9 S1, §8.3).

Run with the venv python and APPWORLD_ROOT=root_full (before B4 locks it):
  APPWORLD_ROOT=$AW_BUILD/root_full venv-aw/bin/python -I make_splits.py
Refuses (exit 1) on any count mismatch. Prints counts and hashes only (no ids).
"""

from __future__ import annotations

import collections
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import awpaths as P  # noqa: E402

SCENARIOS = {"train": 30, "dev": 19, "test_normal": 56, "test_challenge": 139}
DIFFICULTY = {"train": [36, 36, 18], "dev": [30, 24, 3], "test_normal": [57, 48, 63],
              "test_challenge": [72, 150, 195]}


def contacts(sup: dict) -> list[str]:
    out = [f"{sup['first_name']} {sup['last_name']}", sup["email"]]
    if sup.get("phone_number"):
        out.append(str(sup["phone_number"]))
    return out


def main() -> int:
    root = Path(os.environ.get("APPWORLD_ROOT", P.ROOT_FULL))
    from appworld.task import load_task_ids  # noqa: E402

    data = root / "data"
    ids, errors = {}, []
    for split, n in P.SPLIT_COUNTS.items():
        lst = load_task_ids(split)
        raw = [x for x in (data / "datasets" / f"{split}.txt").read_text().split() if x]
        if lst != raw:
            errors.append(f"{split}: load_task_ids differs from the file")
        if len(lst) != n or len(set(lst)) != n:
            errors.append(f"{split}: {len(lst)} ids, expected {n}")
        scen = {x.split("_")[0] for x in lst}
        if len(scen) != SCENARIOS[split]:
            errors.append(f"{split}: {len(scen)} scenarios, expected {SCENARIOS[split]}")
        diff = collections.Counter(
            json.loads((data / "tasks" / t / "ground_truth" / "metadata.json").read_text())["difficulty"]
            for t in lst)
        got = [diff.get(k, 0) for k in (1, 2, 3)]
        if got != DIFFICULTY[split]:
            errors.append(f"{split}: difficulty {got}, expected {DIFFICULTY[split]}")
        ids[split] = lst
    allids = [x for s in ids.values() for x in s]
    if len(set(allids)) != 732:
        errors.append("splits are not pairwise disjoint")
    if {x.split("_")[0] for x in ids["train"]} & {x.split("_")[0] for x in ids["dev"]}:
        errors.append("train and dev share a scenario")
    if errors:
        print("REFUSED:", errors)
        return 1

    grams, cons = set(), set()
    from status_doc import ngrams8  # same tokenizer as the publishing filter
    for t in ids["train"] + ids["dev"]:
        spec = json.loads((data / "tasks" / t / "specs.json").read_text())
        grams |= ngrams8(spec["instruction"])
        cons |= set(contacts(spec["supervisor"]))
    P.write_json(P.LINT_CACHE, {"task_ids": sorted(allids), "test_ids": sorted(ids["test_normal"] + ids["test_challenge"]),
                                "instruction_8grams": sorted(grams), "contacts": sorted(cons)})
    os.chmod(P.LINT_CACHE, 0o600)
    split_sha = {s: P.sha256_file(data / "datasets" / f"{s}.txt") for s in P.SPLIT_COUNTS}
    tree = P.sha256_tree(data)
    P.update_manifest(data={"root_full_tree_sha256": tree, "split_file_sha256": split_sha,
                            "counts": {s: len(v) for s, v in ids.items()}, "scenarios": SCENARIOS,
                            "difficulty_1_2_3": DIFFICULTY})
    print(json.dumps({"counts": {s: len(v) for s, v in ids.items()}, "scenarios": SCENARIOS,
                      "difficulty": DIFFICULTY, "tree_sha256": tree, "lint_cache": {
                          "ids": len(allids), "8grams": len(grams), "contacts": len(cons)}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
