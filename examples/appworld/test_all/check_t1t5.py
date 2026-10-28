"""T1 + T5 (docs/TEST_ALL.md §9), dev ids only, nothing counted. Run in venv-aw:

  . examples/appworld/test_all/env.sh && $VENV_AW/bin/python -I examples/appworld/test_all/check_t1t5.py ARM [ARM...]

T1: RITS /models reports max_model_len 40,144; 1 dev episode with the seed completes through Adapter()._episode
(the window's own path, root_opt, one global slot); the RITS key appears nowhere under /workspace/aw_testall,
/tmp/aw_testall or the pushed files (grep -F of the key, inside this script; never printed).
T5: for each ARM given (the 3 largest first requests of T4), 1 dev episode completes without context_exceeded;
max prompt tokens recorded. Prints flags and counts only; writes AW_STATE/acceptance/t1.json and t5.json.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "scripts"))
sys.path.insert(0, str(EX / "adapters"))
import awrest as P  # noqa: E402

P.setup_env()
import adapter as A  # noqa: E402

ART = P.AW_STATE / "final" / "artifacts"


def episode(arm: str, tid: str, scratch: Path) -> dict:
    ad = A.Adapter()
    task = A._task(tid, P.ROOT_OPT)
    with P.Slot(f"accept/{arm}"):
        r = ad._episode(task, ART / arm, seed=0, root=P.ROOT_OPT, workdir=scratch, random_seed=P.FINAL_SEED_BASE)
    m = r.metadata or {}
    return {"arm": arm, "infra_error": bool(r.error), "termination": m.get("termination"), "n_steps": m.get("n_steps"),
            "max_prompt_tokens": m.get("max_prompt_tokens"), "episode_seconds": m.get("episode_seconds"),
            "success": m.get("success")}


def main(arms: list[str]) -> int:
    env = P.read_env_file()
    key = env["RITS_API_KET"]
    req = urllib.request.Request(env["RITS_URL"].rstrip("/") + "/gpt-oss-120b-a100/v1/models",
                                 headers={"RITS_API_KEY": key})
    with urllib.request.urlopen(req, timeout=60) as resp:
        mml = json.loads(resp.read())["data"][0].get("max_model_len")
    os.environ["AW_EXPERIMENT"] = "acc_testabl" if getattr(P, "TESTABL", False) else "acc_testall"
    os.environ["AW_INFRA_RETRIES"] = "1"
    dev = P.read_split("dev")
    (P.SCRATCH / "scratch").mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="acc_", dir=P.SCRATCH / "scratch"))
    jobs = [("seed", dev[1])] + [(a, dev[2 + i]) for i, a in enumerate(arms)]
    with ThreadPoolExecutor(len(jobs)) as ex:
        recs = list(ex.map(lambda j: episode(j[0], j[1], scratch), jobs))
    pat = P.AW_STATE / ".k.pat"
    pat.write_text(key + "\n")
    hits = 0
    for d in (P.AW_HOME, P.SCRATCH, P.PUSHED, EX):
        g = subprocess.run(["grep", "-rlF", "--exclude=.k.pat", "-f", str(pat), str(d)], capture_output=True, text=True)
        hits += len([x for x in g.stdout.splitlines() if x and "/build/" not in x])
    pat.unlink()
    t1 = {"max_model_len": mml, "seed_episode": recs[0], "key_hits": hits,
          "ok": mml == 40144 and not recs[0]["infra_error"] and recs[0]["termination"] is not None and hits == 0}
    t5 = {"episodes": recs[1:], "ok": all(not r["infra_error"] and r["termination"] != "context_exceeded" for r in recs[1:])}
    P.write_json(P.AW_STATE / "acceptance" / ("t1_w2.json" if getattr(P, "WINDOW", "1") == "2" else "t1.json"), t1)
    P.write_json(P.AW_STATE / "acceptance" / ("t5_w2.json" if getattr(P, "WINDOW", "1") == "2" else "t5.json"), t5)
    print(json.dumps({"t1": t1, "t5": t5}))
    return 0 if t1["ok"] and t5["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
