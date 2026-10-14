"""P5 freeze (plan §8.5, §12): lint the final playbook, render both arms' artifacts, record tree hashes.

  venv-aw/bin/python -I freeze.py
The ACE artifact is pb_<last applied step> (pb_090, or the playbook at a guard stop).
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "scripts"))
sys.path.insert(0, str(EX / "adapters"))
import awpaths as P  # noqa: E402
import lints  # noqa: E402
import status_doc  # noqa: E402

ART = P.AW_STATE / "final" / "artifacts"


def main() -> int:
    prog = P.read_json(P.PUSHED / "ace" / "progress.json")
    last = prog["last_applied_step"]
    m_cap = int(P.manifest()["m_cap"]["value"])
    pb = (P.AW_STATE / "ace" / "playbooks" / f"pb_{last:03d}.txt").read_text()
    if P.sha256_bytes(pb.encode()) != P.sha256_file(P.PUSHED / "ace" / "playbook.txt"):
        raise SystemExit("local pb and pushed playbook.txt differ")
    ml = lints.memory_lint(pb, m_cap)
    if not ml["ok"]:
        raise SystemExit(f"final playbook fails the memory lint: {ml}")
    initial = (EX / "ace" / "vendor" / "playbooks" / "appworld_initial_playbook.txt").read_text()
    for arm in ("seed", "ace"):
        d = ART / arm
        if d.exists():
            shutil.rmtree(d)
        shutil.copytree(EX / "seed_capability", d)
        (d / "memory" / ".gitkeep").unlink(missing_ok=True)
    (ART / "ace" / "memory" / "playbook.md").write_text(pb)
    pushed = P.PUSHED / "final" / "artifacts" / "ace" / "memory" / "playbook.md"
    pushed.parent.mkdir(parents=True, exist_ok=True)
    P.atomic_write(pushed, pb)
    hashes = {arm: P.sha256_tree(ART / arm) for arm in ("seed", "ace")}
    info = {"ace_step": last, "guard_stop": bool(prog.get("hard_stop")), "tree_sha256": hashes,
            "playbook_sha256": P.sha256_bytes(pb.encode()), "tokens": ml["tokens"], "chars": ml["chars"],
            "bullets": ml["bullets"], "sections": lints.sections(pb),
            "identical_to_own_seed": pb.strip() == initial.strip(), "inert": not pb.strip()}
    P.update_manifest(freeze=info)
    status_doc.append(
        "phase_done", "P5", "freeze",
        f"Freeze done: ACE artifact = pb_{last:03d}{' (optimizer guard stop, disclosed)' if info['guard_stop'] else ''}, "
        f"{ml['bullets']} bullets, {ml['chars']:,} chars, {ml['tokens']:,} tokens (M_cap {m_cap:,}); lint passed. "
        f"identical_to_own_seed: {info['identical_to_own_seed']}; inert: {info['inert']}.\n"
        f"Artifacts rendered for both arms (seed = stock capability, ace = stock + memory/playbook.md); tree sha256 "
        f"seed {hashes['seed'][:12]}…, ace {hashes['ace'][:12]}… (manifest.json).\nNext: P6 dev diagnostic.",
        done_through="P5/freeze", next_unit="P6/dev", extra={"freeze": info},
        artifacts=["STATE/manifest.json", "STATE/final/artifacts/ace/memory/playbook.md"], subject="freeze")
    print(json.dumps(info))
    return 0


if __name__ == "__main__":
    sys.exit(main())
