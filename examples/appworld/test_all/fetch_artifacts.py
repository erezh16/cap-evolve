#!/usr/bin/env python3
"""B3 (docs/TEST_ALL.md §6.1): fetch the 13 arms' artifacts, verify each by its own hash rule, keep only the surfaces.

  . examples/appworld/test_all/env.sh && python3 -I examples/appworld/test_all/fetch_artifacts.py [--verify-only]

A trusted script (rule R1), stdlib only. For each arm of §3: copy the local path if it exists and its hash matches,
else `rclone copy` the Box path (never sync/move/delete; nothing is written to Box), into a fetch dir; hash a scratch
copy without FREEZE.json / README.md / capability.diff (rule F) or the whole dir (rules S and B); compare with the
expected hash. The scored copy, AW_STATE/final/artifacts/<arm>/, holds only the surfaces the harness reads. Writes
AW_STATE/final/artifacts_manifest.json and manifest.json `artifacts`; prints arm, source, rule, match, file sizes and
hashes only. Exit non-zero on any mismatch: nothing is scored then (§6.1 step 3).

--verify-only re-checks the scored copies against the hashes recorded at freeze (§6.3; used at window start and by
resume.py): rule S on the scored copy for S arms; for F and B arms, the sha256 of every scored file must equal the
manifest's (the scored copy is a subset of the verified tree, so its whole-tree rule cannot be recomputed on it).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "scripts"))
import awrest as P  # noqa: E402

SCORED = ("policy/instructions.txt", "tools/helpers.py", "tools/api_notes.json", "memory/playbook.md",
          "memory/retrieval.json")
S_SURFACES = ("policy/instructions.txt", "tools/helpers.py", "tools/api_notes.json", "memory/playbook.md")
F_EXCLUDE = ("FREEZE.json", "README.md", "capability.diff")
ART = P.AW_STATE / "final" / "artifacts"
FETCH = P.AW_STATE / "fetch"
MANIFEST = P.AW_STATE / "final" / "artifacts_manifest.json"


# ---------------------------------------------------------------- the three hash rules of §3

def rule_s(d: Path) -> str:
    """common/evaluator.py tree_hash: sha256 of json.dumps(sorted((path, text))) over the four surfaces; an empty
    playbook counts as absent; every other file (memory/retrieval.json included) is ignored."""
    content = {}
    for rel in S_SURFACES:
        p = d / rel
        if p.is_file():
            content[rel] = p.read_text(encoding="utf-8")
    content = {k: v for k, v in content.items() if not (k == "memory/playbook.md" and not v.strip())}
    return hashlib.sha256(json.dumps(sorted(content.items())).encode()).hexdigest()


def rule_f(d: Path) -> str:
    """awrest.sha256_tree over a copy without FREEZE.json, README.md and capability.diff (top level)."""
    with tempfile.TemporaryDirectory(dir=P.SCRATCH) as t:
        c = Path(t) / "c"
        shutil.copytree(d, c)
        for n in F_EXCLUDE:
            (c / n).unlink(missing_ok=True)
        return P.sha256_tree(c)


def rule_b(d: Path) -> str:
    """Every file sorted by relative path: relpath + NUL + raw 32-byte sha256 digest, no newline; whole dir."""
    h = hashlib.sha256()
    for p in sorted(x for x in d.rglob("*") if x.is_file()):
        h.update(str(p.relative_to(d)).encode() + b"\0" + hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


RULES = {"S": rule_s, "F": rule_f, "B": rule_b}


# ---------------------------------------------------------------- fetch

def _files(d: Path) -> list[dict]:
    return [{"path": str(p.relative_to(d)), "bytes": p.stat().st_size, "sha256": P.sha256_file(p)}
            for p in sorted(x for x in d.rglob("*") if x.is_file())]


def fetch_one(arm: str, spec: dict) -> dict:
    exp, rule = spec["hash"], spec["rule"]
    tried = []
    for kind in ("local", "box"):
        src = spec[kind]
        if not src:
            continue
        dst = FETCH / arm / kind
        shutil.rmtree(dst, ignore_errors=True)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if kind == "local":
            if not Path(src).is_dir():
                tried.append({"source": "local", "path": str(src), "present": False})
                continue
            shutil.copytree(src, dst)
            label = str(src)
        else:
            label = P.BOX_ROOT + src
            r = subprocess.run(["rclone", "copy", label, str(dst)], capture_output=True, text=True, timeout=900)
            if r.returncode != 0 or not dst.is_dir():
                tried.append({"source": "box", "path": label, "rclone_exit": r.returncode,
                              "stderr_tail": r.stderr.strip().splitlines()[-1:]})
                continue
        got = RULES[rule](dst)
        tried.append({"source": kind, "path": label, "present": True, "computed": got, "match": got == exp})
        if got == exp:
            return {"arm": arm, "rule": rule, "expected": exp, "computed": got, "match": True, "source": kind,
                    "source_path": label, "fetched_files": _files(dst), "tried": tried, "_dir": dst}
    return {"arm": arm, "rule": rule, "expected": exp, "match": False, "tried": tried}


def make_scored(arm: str, src: Path) -> dict:
    dst = ART / arm
    shutil.rmtree(dst, ignore_errors=True)
    for rel in SCORED:
        p = src / rel
        if p.is_file():
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, dst / rel)
    (dst / "memory").mkdir(parents=True, exist_ok=True)   # the seed has none; the harness tolerates an empty dir
    files = _files(dst)
    present = {"P": any(f["path"] == "policy/instructions.txt" for f in files),
               "T_helpers": any(f["path"] == "tools/helpers.py" for f in files),
               "T_notes": any(f["path"] == "tools/api_notes.json" for f in files),
               "M_playbook": any(f["path"] == "memory/playbook.md" for f in files),
               "M_retrieval": any(f["path"] == "memory/retrieval.json" for f in files)}
    return {"scored_files": files, "surfaces_present": present, "scored_rule_s": rule_s(dst)}


def fetch_all() -> int:
    ART.mkdir(parents=True, exist_ok=True)
    out, ok = {}, True
    for arm in P.ARMS:
        r = fetch_one(arm, P.ARTIFACTS[arm])
        if r["match"]:
            r.update(make_scored(arm, r.pop("_dir")))
        ok &= r["match"]
        out[arm] = r
        print(json.dumps({"arm": arm, "rule": r["rule"], "source": r.get("source"), "match": r["match"],
                          "computed": (r.get("computed") or "")[:16], "files": len(r.get("scored_files", []))}))
    # §6.1 step 5: seed and harnesslens scored copies byte-identical, file by file
    # TEST_ABL has no seed-identical arm (plan §6): the check does not apply, recorded as None
    same = None if "harnesslens" not in P.ARMS else (ok and [(f["path"], f["sha256"]) for f in out["seed"]["scored_files"]]
                                                       == [(f["path"], f["sha256"]) for f in out["harnesslens"]["scored_files"]])
    m = {"utc": P.utcnow(), "arms": out, "seed_equals_harnesslens_bytewise": same, "all_match": ok}
    P.write_json(MANIFEST, m)
    if ok:
        P.update_manifest(artifacts={a: {k: v[k] for k in ("rule", "expected", "computed", "source", "source_path",
                                                           "surfaces_present", "scored_rule_s")}
                                     | {"scored_files": {f["path"]: f["sha256"] for f in v["scored_files"]}}
                                     for a, v in out.items()},
                          seed_equals_harnesslens_bytewise=same)
    print(json.dumps({"all_match": ok, "seed_equals_harnesslens_bytewise": same}))
    return 0 if ok and same is not False else 1


def verify_only() -> int:
    """§6.3: re-check every scored copy with its arm's rule (as recorded at freeze); print flags only."""
    arts = P.manifest().get("artifacts") or {}
    bad = check_scored(arts)
    print(json.dumps({"verified": len(P.ARMS) - len(bad), "mismatch": bad}))
    return 0 if not bad else 1


def check_scored(arts: dict) -> list[str]:
    bad = []
    for arm in P.ARMS:
        a, d = arts.get(arm), ART / arm
        if not a or not d.is_dir():
            bad.append(arm)
            continue
        files = {f["path"]: f["sha256"] for f in _files(d)}
        if files != a["scored_files"] or rule_s(d) != a["scored_rule_s"]:
            bad.append(arm)
        elif a["rule"] == "S" and rule_s(d) != a["expected"]:
            bad.append(arm)
    return bad


if __name__ == "__main__":
    raise SystemExit(verify_only() if "--verify-only" in sys.argv else fetch_all())
