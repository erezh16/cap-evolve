"""B2-B4 read-only re-check of the ablations' fresh build (docs/ABLATIONS.md §6.2 B2-B4, re-run by resume). Trusted
script (rule R1): it opens task files only to count them, prints counts, booleans and hashes only (no task id).

Checks against this run's own pushed manifest (docs/ABLATION_STATUS_STATE/manifest.json, written by build.py b1-b4):
AppWorld at 42b5bcf with the patch; fastapi 0.143.0 and pydantic 2.12.5 in venv-aw and venv-abl; venv-abl's only
cap-evolve core is abl-main; split, scenario and difficulty counts and split-file sha256; root_opt 148 dirs, only
train/dev split files, 0 test-id hits; root_full mode 000 before and after; lint and publish caches present. root_full is unlocked only for this read and relocked at once.

  . examples/appworld/abl/env.sh && python3 -I examples/appworld/abl/verify_build.py

Exit 0 iff everything matches. Records the result in AW_STATE/build_check.json.
"""

from __future__ import annotations

import collections
import json
import os
import subprocess
import sys
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "scripts"))
import awrest as P  # noqa: E402

SCEN = {"train": 30, "dev": 19, "test_normal": 56, "test_challenge": 139}
DIFF = {"train": [36, 36, 18], "dev": [30, 24, 3], "test_normal": [57, 48, 63], "test_challenge": [72, 150, 195]}


VENV_ABL_PY = P.VENVS / "venv-abl" / "bin" / "python"


def main() -> int:
    if os.environ.get("AW_PROFILE") != "abl":
        sys.exit("verify_build: source abl/env.sh first")
    m = P.manifest()
    res: dict = {}
    links = {}                                 # a fresh build: nothing in AW_BUILD may point outside it
    for name in ("appworld", "root_opt", "root_full", "reference", "venvs/venv-aw", "venvs/venv-abl"):
        p = P.AW_BUILD / name
        links[name] = {"exists": p.exists() or p.is_symlink(), "is_symlink": p.is_symlink(),
                       "ok": (p.exists() or p.is_symlink()) and not p.is_symlink()}
    res["no_symlinks"] = links
    a = P.APPWORLD_SRC
    head = subprocess.run(["git", "-C", str(a), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    diff = subprocess.run(["git", "-C", str(a), "diff"], capture_output=True, text=True).stdout
    res["appworld"] = {"head_ok": head == P.APPWORLD_COMMIT,
                       "diff_sha256_ok": P.sha256_bytes(diff.encode()) == m["appworld"]["git_diff_sha256"],
                       "patch_sha256_ok": P.sha256_file(EX / "patches" / "appworld-extra-headers.patch")
                       == m["appworld"]["patch_sha256"]}
    r = subprocess.run([str(P.VENV_PY), "-I", "-c", "import fastapi,pydantic;print(fastapi.__version__,pydantic.__version__)"],
                       capture_output=True, text=True)
    fa, pd = r.stdout.split()
    res["venv_aw"] = {"fastapi": fa, "pydantic": pd, "ok": fa == "0.143.0" and pd == "2.12.5"}
    code = ("import cap_evolve,fastapi,pydantic,pathlib;"
            "print(pathlib.Path(cap_evolve.__file__).resolve(),fastapi.__version__,pydantic.__version__)")
    r = subprocess.run([str(VENV_ABL_PY), "-I", "-c", code], capture_output=True, text=True)
    core, fa2, pd2 = (r.stdout.split() + ["", "", ""])[:3]
    fr = subprocess.run(["uv", "pip", "freeze", "-p", str(P.VENVS / "venv-abl")], capture_output=True, text=True).stdout
    cores = [x for x in fr.splitlines() if x.startswith("-e") and x.rstrip("/").endswith("/core")]
    res["venv_abl"] = {"core_in_abl_main": core.startswith(str(P.CAPE_TREE / "core") + "/"), "editable_cores": len(cores),
                       "fastapi": fa2, "pydantic": pd2}
    res["venv_abl"]["ok"] = (res["venv_abl"]["core_in_abl_main"] and len(cores) == 1 and fa2 == "0.143.0"
                             and pd2 == "2.12.5")
    mode_before = os.stat(P.ROOT_FULL).st_mode & 0o777
    res["root_full_mode_before"] = oct(mode_before)
    os.chmod(P.ROOT_FULL, 0o755)
    try:
        code = ("import json,sys; from appworld.task import load_task_ids; "
                "print(json.dumps({s: load_task_ids(s) for s in sys.argv[1:]}))")
        r = subprocess.run([str(P.VENV_PY), "-I", "-c", code, *P.SPLIT_COUNTS], capture_output=True, text=True,
                           env={**os.environ, "APPWORLD_ROOT": str(P.ROOT_FULL)}, check=True)
        ids = json.loads(r.stdout.strip().splitlines()[-1])
        data = P.ROOT_FULL / "data"
        splits = {}
        for s, n in P.SPLIT_COUNTS.items():
            lst = ids[s]
            dif = collections.Counter(json.loads((data / "tasks" / t / "ground_truth" / "metadata.json").read_text())
                                      ["difficulty"] for t in lst)
            splits[s] = {"count": len(lst), "count_ok": len(lst) == n and len(set(lst)) == n,
                         "scenarios_ok": len({x.split("_")[0] for x in lst}) == SCEN[s],
                         "difficulty_ok": [dif.get(k, 0) for k in (1, 2, 3)] == DIFF[s],
                         "split_sha256_ok": P.sha256_file(data / "datasets" / f"{s}.txt")
                         == m["data"]["split_file_sha256"][s]}
        test_ids = set(ids["test_normal"]) | set(ids["test_challenge"])
    finally:
        os.chmod(P.ROOT_FULL, 0o000)
    res["splits"] = splits
    res["root_full_mode_after"] = oct(os.stat(P.ROOT_FULL).st_mode & 0o777)
    names = [p.name for p in (P.ROOT_OPT / "data" / "tasks").iterdir()]
    pat = P.AW_STATE / ".test_ids.pat"
    pat.write_text("\n".join(sorted(test_ids)) + "\n")
    g = subprocess.run(["grep", "-rlF", "-f", str(pat), str(P.ROOT_OPT / "data")], capture_output=True, text=True)
    pat.unlink()
    hits = len([x for x in g.stdout.splitlines() if x]) + len(set(names) & test_ids)
    res["root_opt"] = {"task_dirs": len(names), "datasets": sorted(p.name for p in (P.ROOT_OPT / "data" / "datasets").iterdir()),
                       "test_id_hits": hits}
    res["root_opt"]["ok"] = len(names) == 148 and res["root_opt"]["datasets"] == ["dev.txt", "train.txt"] and hits == 0
    res["caches"] = {"lint_cache": P.LINT_CACHE.exists(), "publish_cache": P.PUBLISH_CACHE.exists()}
    res["ok"] = (all(v["ok"] for v in links.values()) and all(res["appworld"].values()) and res["venv_aw"]["ok"]
                 and res["venv_abl"]["ok"]
                 and all(all(v[k] for k in v if k.endswith("_ok")) for v in splits.values())
                 and res["root_opt"]["ok"] and res["root_full_mode_after"] == "0o0" and all(res["caches"].values()))
    P.write_json(P.AW_STATE / "build_check.json", res)
    print(json.dumps(res, indent=1))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
