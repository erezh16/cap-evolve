#!/usr/bin/env python3
"""Idempotent build steps B1–B5 of AppWorld eval REST (docs/EVAL_APPWORLD_REST.md §6.2; B1–B4 as eval 5 §4).

  python3 -I build.py check            # json: which B steps are missing or mismatched
  python3 -I build.py b1|b2|b3|b4|b5   # run one step (each records its hashes in manifest.json)
Prints counts and hashes only (no task ids). resume.py calls check() and re-runs missing steps.
"""

from __future__ import annotations

import collections
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import awrest as P  # noqa: E402

UV = shutil.which("uv") or "/usr/local/bin/uv"
SCENARIOS = {"train": 30, "dev": 19, "test_normal": 56, "test_challenge": 139}
DIFFICULTY = {"train": [36, 36, 18], "dev": [30, 24, 3], "test_normal": [57, 48, 63],
              "test_challenge": [72, 150, 195]}
# B5: one venv per candidate whose deps clash with venv-aw (§4 B5). gepa lives in venv-aw (zero deps);
# wikiskill and metaharness are stdlib-only drivers that also run in venv-aw.
CAND_VENVS = {
    "skillopt": ("3.11", lambda c: [f"-e {c}", "anthropic", "tiktoken"]),
    "evoskill": ("3.12", lambda c: [f"-e {c}", "anthropic", "tiktoken"]),
}


def sh(cmd: str, cwd: Path | None = None, env: dict | None = None) -> str:
    r = subprocess.run(cmd, shell=True, cwd=str(cwd) if cwd else None, capture_output=True, text=True,
                       env={**os.environ, **(env or {})})
    if r.returncode:
        raise SystemExit(f"command failed ({r.returncode}): {cmd}\n{r.stderr[-2000:]}")
    return r.stdout


def _git(d: Path, *a: str) -> str:
    return subprocess.run(["git", "-C", str(d), *a], capture_output=True, text=True).stdout


def check() -> dict:
    m = P.manifest()
    out = {}
    a = P.APPWORLD_SRC
    if not (a / ".git").exists():
        out["b1"] = "missing"
    elif _git(a, "rev-parse", "HEAD").strip() != P.APPWORLD_COMMIT or \
            P.sha256_bytes(_git(a, "diff").encode()) != m.get("appworld", {}).get("git_diff_sha256"):
        out["b1"] = "mismatch"
    if not P.VENV_PY.exists():
        out["b2"] = "missing"
    if not P.ROOT_FULL.exists() or not P.PUBLISH_CACHE.exists():
        out["b3"] = "missing"
    if not (P.ROOT_OPT / "data").exists() or not P.LINT_CACHE.exists() or not P.PUBLISH_CACHE.exists() \
            or not (P.REFERENCE / "api_index.md").exists():
        out["b4"] = "missing"
    for c, (url, commit) in P.PINS.items():
        d = P.CLONES / c
        if not (d / ".git").exists() or _git(d, "rev-parse", "HEAD").strip() != commit:
            out["b5"] = f"clone {c}"
    for c in CAND_VENVS:
        if not (P.VENVS / f"venv-{c}" / "bin" / "python").exists():
            out["b5"] = f"venv {c}"
    return out


def b1() -> None:
    a = P.APPWORLD_SRC
    if not (a / ".git").exists():
        sh(f"git clone -q https://github.com/StonyBrookNLP/appworld.git {a}")
    sh(f"git checkout -q {P.APPWORLD_COMMIT} && git lfs install --local && git lfs pull", a)
    sh("git checkout -- .", a)
    sh(f"git apply {P.EXAMPLE / 'patches' / 'appworld-extra-headers.patch'}", a)
    diff = _git(a, "diff")
    P.update_manifest(appworld={"commit": P.APPWORLD_COMMIT, "git_diff_sha256": P.sha256_bytes(diff.encode()),
                                "patch_sha256": P.sha256_file(P.EXAMPLE / "patches" / "appworld-extra-headers.patch")})
    print(json.dumps({"b1": "ok", "diff_sha256": P.sha256_bytes(diff.encode())}))


def b2() -> None:
    v = P.VENV_AW
    if not P.VENV_PY.exists():
        sh(f"{UV} venv -q -p 3.11 {v}")
    sh(f"{UV} pip install -q -p {v} torch --index-url https://download.pytorch.org/whl/cpu")
    sh(f"{UV} pip install -q -p {v} -e {P.APPWORLD_SRC} -e '{P.APPWORLD_SRC}/experiments[simplified]' "
       f"'pydantic>=2.12,<2.13' 'fastapi==0.143.0' -e {P.REPO / 'core'} tiktoken 'gepa==0.1.4' anthropic")  # fastapi 0.156 breaks AppWorld's Path(embed=)
    sh(f"{v / 'bin' / 'appworld'} install --repo", P.APPWORLD_SRC)
    freeze = sh(f"{UV} pip freeze -p {v}")
    P.atomic_write(P.AW_STATE / "venv-aw.freeze.txt", freeze)
    P.update_manifest(venv_aw={"python": "3.11", "freeze_sha256": P.sha256_bytes(freeze.encode()),
                               "uv": sh(f"{UV} --version").strip()})
    print(json.dumps({"b2": "ok", "packages": len(freeze.splitlines())}))


def _contacts(sup: dict) -> list[str]:
    out = [f"{sup['first_name']} {sup['last_name']}", sup["email"]]
    if sup.get("phone_number"):
        out.append(str(sup["phone_number"]))
    return out


def b3() -> None:
    """Download data into root_full (if missing), check splits (S1), build the publishing cache."""
    if P.ROOT_FULL.exists():
        os.chmod(P.ROOT_FULL, 0o755)
    if not (P.ROOT_FULL / "data" / "datasets").exists():
        P.ROOT_FULL.mkdir(parents=True, exist_ok=True)
        sh(f"{P.VENV_AW / 'bin' / 'appworld'} download data --root {P.ROOT_FULL}")
    code = ("import json,sys; from appworld.task import load_task_ids; "
            "print(json.dumps({s: load_task_ids(s) for s in sys.argv[1:]}))")
    r = subprocess.run([str(P.VENV_PY), "-I", "-c", code, *P.SPLIT_COUNTS], capture_output=True, text=True,
                       env={**os.environ, "APPWORLD_ROOT": str(P.ROOT_FULL)}, check=True)
    ids = json.loads(r.stdout.strip().splitlines()[-1])
    data = P.ROOT_FULL / "data"
    errors = []
    for split, n in P.SPLIT_COUNTS.items():
        lst = ids[split]
        if lst != P.read_split(split, P.ROOT_FULL):
            errors.append(f"{split}: load_task_ids differs from the file")
        if len(lst) != n or len(set(lst)) != n:
            errors.append(f"{split}: {len(lst)} ids, expected {n}")
        if len({x.split('_')[0] for x in lst}) != SCENARIOS[split]:
            errors.append(f"{split}: scenario count")
        diff = collections.Counter(json.loads((data / "tasks" / t / "ground_truth" / "metadata.json").read_text())
                                   ["difficulty"] for t in lst)
        if [diff.get(k, 0) for k in (1, 2, 3)] != DIFFICULTY[split]:
            errors.append(f"{split}: difficulty {[diff.get(k, 0) for k in (1, 2, 3)]}")
    allids = [x for s in ids.values() for x in s]
    if len(set(allids)) != 732:
        errors.append("splits are not pairwise disjoint")
    if {x.split("_")[0] for x in ids["train"]} & {x.split("_")[0] for x in ids["dev"]}:
        errors.append("train and dev share a scenario")
    if errors:
        print("REFUSED:", errors)
        raise SystemExit(1)
    from status_doc import ngrams8
    grams, cons = set(), set()
    for t in ids["train"] + ids["dev"]:
        spec = json.loads((data / "tasks" / t / "specs.json").read_text())
        grams |= ngrams8(spec["instruction"])
        cons |= set(_contacts(spec["supervisor"]))
    P.write_json(P.PUBLISH_CACHE, {"task_ids": sorted(allids),
                                   "test_ids": sorted(ids["test_normal"] + ids["test_challenge"]),
                                   "instruction_8grams": sorted(grams), "contacts": sorted(cons)})
    os.chmod(P.PUBLISH_CACHE, 0o600)
    split_sha = {s: P.sha256_file(data / "datasets" / f"{s}.txt") for s in P.SPLIT_COUNTS}
    tree = P.sha256_tree(data)
    P.update_manifest(data={"root_full_tree_sha256": tree, "split_file_sha256": split_sha,
                            "counts": {s: len(v) for s, v in ids.items()}, "scenarios": SCENARIOS,
                            "difficulty_1_2_3": DIFFICULTY})
    print(json.dumps({"b3": "ok", "counts": {s: len(v) for s, v in ids.items()}, "tree_sha256": tree,
                      "publish_cache": {"ids": len(allids), "8grams": len(grams), "contacts": len(cons)}}))


def b4() -> None:
    """root_opt (train + dev + _base_), 0 test-id hits, lint cache, optimizer reference dir, chmod 000 root_full."""
    os.chmod(P.ROOT_FULL, 0o755)
    src, dst = P.ROOT_FULL / "data", P.ROOT_OPT / "data"
    if P.ROOT_OPT.exists():
        shutil.rmtree(P.ROOT_OPT)
    (dst / "tasks").mkdir(parents=True)
    (dst / "datasets").mkdir()
    for item in src.iterdir():
        if item.name not in ("tasks", "datasets"):
            (shutil.copytree if item.is_dir() else shutil.copy2)(item, dst / item.name)
    keep = P.read_split("train", P.ROOT_FULL) + P.read_split("dev", P.ROOT_FULL)
    for s in ("train", "dev"):
        shutil.copy2(src / "datasets" / f"{s}.txt", dst / "datasets" / f"{s}.txt")
    for t in keep + ["_base_"]:
        shutil.copytree(src / "tasks" / t, dst / "tasks" / t)
    test_ids = json.loads(P.PUBLISH_CACHE.read_text())["test_ids"]
    pat = P.AW_STATE / ".test_ids.pat"
    pat.write_text("\n".join(test_ids) + "\n")
    r = subprocess.run(["grep", "-rlF", "-f", str(pat), str(P.ROOT_OPT)], capture_output=True, text=True)
    pat.unlink()
    hits = [x for x in r.stdout.splitlines() if x]
    names = [p.name for p in (dst / "tasks").iterdir()]
    hits += [n for n in names if n in set(test_ids)]
    if hits or len(names) != 148:
        print(json.dumps({"b4": "REFUSED", "test_id_hits": len(hits), "task_dirs": len(names)}))
        raise SystemExit(1)
    env = P.setup_env(dict(os.environ))
    env["APPWORLD_ROOT"] = str(P.ROOT_OPT)
    subprocess.run([str(P.VENV_PY), "-I", str(P.EXAMPLE / "adapters" / "lints.py"), "--write-cache"], env=env,
                   check=True)
    os.chmod(P.LINT_CACHE, 0o600)
    subprocess.run([str(P.VENV_PY), "-I", str(P.EXAMPLE / "scripts" / "make_reference.py"), str(P.REFERENCE)],
                   env={**env, "AW_EVAL": str(P.AW_BUILD)}, check=True, capture_output=True)
    os.chmod(P.ROOT_FULL, 0o000)
    P.update_manifest(root_opt={"tree_sha256": P.sha256_tree(P.ROOT_OPT), "task_dirs": len(names),
                                "datasets": sorted(p.name for p in (dst / "datasets").iterdir()),
                                "test_id_hits": 0},
                      reference={"tree_sha256": P.sha256_tree(P.REFERENCE)})
    print(json.dumps({"b4": "ok", "task_dirs": len(names), "test_id_hits": 0,
                      "root_full_mode": oct(os.stat(P.ROOT_FULL).st_mode & 0o777)}))


def b5() -> None:
    """Clone the five candidate repos at their D4 pins (read-only) and build the per-candidate venvs."""
    out = {}
    for c, (url, commit) in P.PINS.items():
        d = P.CLONES / c
        if not (d / ".git").exists():
            sh(f"git clone -q {url} {d}")
        sh(f"git checkout -q {commit}", d)
        out[c] = _git(d, "rev-parse", "HEAD").strip()
    venvs = {}
    for c, (py, deps) in CAND_VENVS.items():
        v = P.VENVS / f"venv-{c}"
        if not (v / "bin" / "python").exists():
            sh(f"{UV} venv -q -p {py} {v}")
        sh(f"{UV} pip install -q -p {v} " + " ".join(deps(P.CLONES / c)))
        freeze = sh(f"{UV} pip freeze -p {v}")
        P.atomic_write(P.AW_STATE / f"venv-{c}.freeze.txt", freeze)
        venvs[c] = {"python": py, "freeze_sha256": P.sha256_bytes(freeze.encode())}
    P.update_manifest(candidates={c: {"url": P.PINS[c][0], "commit": out[c], **({"venv": venvs[c]} if c in venvs
                                                                                 else {"venv": "venv-aw"})}
                                  for c in P.PINS})
    print(json.dumps({"b5": "ok", "clones": {c: h[:7] for c, h in out.items()}, "venvs": sorted(venvs)}))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "check":
        print(json.dumps(check()))
    else:
        globals()[cmd]()
