"""A2: RITS probes (plan §11): max_model_len = 40,144 (stop if not); 48 concurrent short requests all
200 with no 429; one dev episode through the patched client (lm_calls logging on); the RITS key
appears nowhere under AW_HOME, /tmp/aw_eval_ace or the pushed files. Prints flags and counts only.
"""

from __future__ import annotations

import concurrent.futures as cf
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "scripts"))
sys.path.insert(0, str(EX / "adapters"))
import awpaths as P  # noqa: E402


def req(url, key, body=None, timeout=300):
    r = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                               headers={"RITS_API_KEY": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, None


def main() -> int:
    env = P.read_env_file()
    base = env["RITS_URL"].rstrip("/") + "/gpt-oss-120b-a100/v1"
    key = env["RITS_API_KET"]
    res = {}
    st, models = req(base + "/models", key)
    res["models_status"] = st
    res["max_model_len"] = models["data"][0].get("max_model_len") if models else None
    res["model_id"] = models["data"][0].get("id") if models else None
    body = {"model": res["model_id"] or "openai/gpt-oss-120b", "messages": [{"role": "user", "content": "Say hi in one word."}],
            "max_tokens": 200, "reasoning_effort": "medium", "temperature": 0}
    t0 = time.time()
    with cf.ThreadPoolExecutor(48) as ex:
        sts = list(ex.map(lambda _: req(base + "/chat/completions", key, body)[0], range(48)))
    res["concurrency"] = {"n": 48, "status_200": sts.count(200), "status_429": sts.count(429),
                          "other": sorted({s for s in sts if s not in (200, 429)}), "wall_s": round(time.time() - t0, 1)}
    import adapter
    dev0 = adapter.tasks("dev")[0]
    out = P.AW_STATE / "acceptance" / "a2_episode.json"
    spec = adapter.episode_spec(dev0, "accept/a2/seed/t0", EX / "seed_capability", 100, log_lm_calls=True)
    # keep AppWorld's native output dir for the grep below: run the worker directly
    sp = P.AW_STATE / "acceptance" / "a2_spec.json"
    sp.write_text(json.dumps(spec))
    subprocess.run([str(P.VENV_PY), "-I", str(EX / "adapters" / "aw_agent.py"), str(sp), str(out)],
                   env={"APPWORLD_ROOT": str(P.ROOT_OPT), "HF_HOME": str(P.HF_HOME), "PATH": "/usr/bin:/bin"},
                   cwd=str(P.AW_STATE), timeout=1800)
    rec = json.loads(out.read_text())
    res["episode"] = {k: rec.get(k) for k in ("termination", "success", "steps", "prompt_tokens_max", "infra_error", "wall_s")}
    lm_logs = list((P.SCRATCH / "root_opt" / "accept" / "a2").rglob("lm_calls.jsonl"))
    res["episode"]["lm_calls_logged"] = sum(len(p.read_text().splitlines()) for p in lm_logs)
    pat = P.AW_STATE / ".k.pat"
    pat.write_text(key + "\n")
    hits = []
    for d in (P.AW_HOME, Path("/tmp/aw_eval_ace"), P.PUSHED, EX):
        r = subprocess.run(["grep", "-rlF", "-f", str(pat), str(d)], capture_output=True, text=True)
        hits += [x for x in r.stdout.splitlines() if x and not x.endswith(".k.pat")]
    pat.unlink()
    res["key_hits"] = len(hits)
    import shutil
    shutil.rmtree(P.SCRATCH / "root_opt" / "accept" / "a2", ignore_errors=True)
    res["ok"] = res["max_model_len"] == 40144 and res["concurrency"]["status_200"] == 48 and \
        res["concurrency"]["status_429"] == 0 and rec.get("termination") in ("completed", "step_cap", "token_cap") \
        and not rec.get("infra_error") and res["key_hits"] == 0 and res["episode"]["lm_calls_logged"] > 0
    P.write_json(P.AW_STATE / "acceptance" / "a2.json", res)
    print(json.dumps(res))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
