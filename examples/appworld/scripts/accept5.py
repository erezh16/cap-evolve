"""Common acceptance checks of eval 5 (docs/EVAL_APPWORLD_5.md §11). Run with venv-aw:

  venv-aw/bin/python -I accept5.py a1|a2|a3a5|a4|a6|a7|a8
Each prints one json line of flags and counts (no ids, no secrets) and writes AW_STATE/acceptance/<id>.json.
None of these rollouts are counted (S1): they run under the throwaway candidate names ``acc_*``.
"""

from __future__ import annotations

import concurrent.futures as cf
import json
import os
import random
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "scripts"))
sys.path.insert(0, str(EX / "common"))
sys.path.insert(0, str(EX / "adapters"))
import aw5 as P  # noqa: E402

P.setup_env()
ACC = P.AW_STATE / "acceptance"
ACC.mkdir(parents=True, exist_ok=True)


def done(name: str, res: dict) -> int:
    P.write_json(ACC / f"{name}.json", res)
    print(json.dumps(res))
    return 0 if res.get("ok") else 1


def a1() -> int:
    """The gateway shim (header, no temperature, no refusal) and the claude CLI answer."""
    import opt_llm
    t0 = time.time()
    txt = opt_llm.chat("Reply with the single word ok.", cand="acc_a1", role="a1", max_tokens=20)
    shim = {"reply_ok": "ok" in txt.lower(), "seconds": round(time.time() - t0, 1)}
    js = opt_llm.chat("Return a JSON object {\"a\": 1} inside a ```json fence and nothing else.", cand="acc_a1",
                      role="a1-json", max_tokens=100)
    shim["json_parse"] = '"a"' in js
    td = Path(os.environ.get("TMPDIR", "/tmp")) / "aw5_a1"
    td.mkdir(exist_ok=True)
    r = subprocess.run(["claude", "-p", "Reply with the single word ok.", "--model", P.OPT_MODEL,
                        "--output-format", "json"], capture_output=True, text=True, cwd=td, timeout=300)
    cli = {"exit": r.returncode}
    try:
        j = json.loads(r.stdout)
        cli.update(reply_ok="ok" in (j.get("result") or "").lower(), models=sorted(j.get("modelUsage", {})))
    except json.JSONDecodeError:
        cli["reply_ok"] = False
    return done("a1", {"shim": shim, "cli": cli, "ok": shim["reply_ok"] and shim["json_parse"] and
                       cli["exit"] == 0 and cli.get("reply_ok") and P.OPT_MODEL in cli.get("models", [])})


def _rits(url, key, body=None, timeout=300):
    r = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                               headers={"RITS_API_KEY": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, None


def a2() -> int:
    """RITS: max_model_len, 48 concurrent requests, 1 dev episode with lm_calls logging, key nowhere."""
    env = P.read_env_file()
    base = env["RITS_URL"].rstrip("/") + "/gpt-oss-120b-a100/v1"
    key = env["RITS_API_KET"]
    res: dict = {}
    st, models = _rits(base + "/models", key)
    res["max_model_len"] = models["data"][0].get("max_model_len") if models else None
    body = {"model": models["data"][0]["id"] if models else "openai/gpt-oss-120b",
            "messages": [{"role": "user", "content": "Say hi in one word."}], "max_tokens": 200,
            "reasoning_effort": "medium", "temperature": 0}
    t0 = time.time()
    with cf.ThreadPoolExecutor(48) as ex:
        sts = list(ex.map(lambda _: _rits(base + "/chat/completions", key, body)[0], range(48)))
    res["concurrency"] = {"n": 48, "status_200": sts.count(200), "status_429": sts.count(429),
                          "wall_s": round(time.time() - t0, 1)}
    import evaluator as E
    os.environ["AW_LOG_LM_CALLS"] = "1"
    os.environ["AW_KEEP_OUTPUTS"] = "1"
    os.environ["AW_EXPERIMENT"] = "acc_a2"
    rec = E.evaluate("acc_a2", E.materialize("acc_a2"), E.split_ids("dev")[1:2], phase="A2", split="dev")[0]
    res["episode"] = {k: rec.get(k) for k in ("termination", "reward", "n_steps", "max_prompt_tokens", "error")}
    out_dir = P.ROOT_OPT / "experiments" / "outputs" / "acc_a2"
    res["episode"]["lm_calls_logged"] = sum(len(p.read_text().splitlines()) for p in out_dir.rglob("lm_calls.jsonl"))
    pat = P.AW_STATE / ".k.pat"
    pat.write_text(key + "\n")
    hits = []
    for d in (P.AW_HOME, P.SCRATCH, P.PUSHED, EX, P.ROOT_OPT / "experiments"):
        r = subprocess.run(["grep", "-rlF", "-f", str(pat), str(d)], capture_output=True, text=True)
        hits += [x for x in r.stdout.splitlines() if x and not x.endswith(".k.pat") and "build/root_full" not in x]
    pat.unlink()
    shutil.rmtree(out_dir, ignore_errors=True)
    res["key_hits"] = len(hits)
    res["ok"] = (res["max_model_len"] == 40144 and res["concurrency"]["status_200"] == 48
                 and not rec.get("error") and res["key_hits"] == 0 and res["episode"]["lm_calls_logged"] > 0)
    return done("a2", res)


def _run_base_check(script: str, *args: str) -> tuple[int, str]:
    env = P.setup_env(dict(os.environ))
    env["APPWORLD_ROOT"] = str(P.ROOT_OPT)
    env.setdefault("AW_EVAL", str(P.AW_BUILD))
    r = subprocess.run([str(P.VENV_PY), "-I", str(EX / "scripts" / script), *args], capture_output=True, text=True,
                       env=env, cwd=str(P.SCRATCH))
    shutil.rmtree(P.ROOT_OPT / "experiments" / "outputs" / "probes", ignore_errors=True)
    return r.returncode, r.stdout + r.stderr[-1500:]


def a3a5() -> int:
    """Base A3 (REPL hardening, root_opt) + A5 (scoring) + root_full unreadable during search."""
    sp = ACC / "split_ids.json"
    tr, dv = P.read_split("train"), P.read_split("dev")
    P.write_json(sp, {"train": tr + dv, "val": tr + dv, "test": []})
    # the base script reads test split names from awpaths.ROOT_FULL, which is locked during search:
    # it is unlocked only for the duration of this read-only check, then relocked (logged).
    os.chmod(P.ROOT_FULL, 0o755)
    try:
        rc, out = _run_base_check("check_scoring_isolation.py", str(sp))
    finally:
        os.chmod(P.ROOT_FULL, 0o000)
    sp.unlink()
    locked = not os.access(P.ROOT_FULL, os.R_OK)
    flags = [l.split(":")[0] + ":" + l.rsplit(":", 1)[-1].strip() for l in out.splitlines() if l.startswith("A")]
    return done("a3a5", {"base_check": "PASS" in out and rc == 0, "lines": flags, "root_full_locked": locked,
                         "ok": rc == 0 and "PASS" in out and locked})


def a4() -> int:
    """Base A4 (seed byte-identical, memory slot, helpers+notes) + lint reject without a rollout."""
    rc, out = _run_base_check("check_injection.py", str(P.SEED_CAP))
    import evaluator as E
    bad = E.materialize("acc_a4", {"tools/helpers.py": "import os\napis.spotify.login()\n"})
    before = E.counted("acc_a4")
    recs = E.evaluate("acc_a4", bad, E.split_ids("dev")[:2], phase="A4", split="dev")
    rejected = all(r.get("lint_reject") and r["reward"] == 0 for r in recs) and E.counted("acc_a4") == before
    flags = [l for l in out.splitlines() if l.startswith("A4")]
    return done("a4", {"lines": flags, "lint_reject_without_rollout": rejected,
                       "ok": rc == 0 and "A4 PASS" in out and rejected})


def a6() -> int:
    """tasks("train") == train.txt in load_task_ids order; a test id refused without AW_ALLOW_SEALED."""
    code = ("import json,sys; from appworld.task import load_task_ids; print(json.dumps(load_task_ids('train')))")
    r = subprocess.run([str(P.VENV_PY), "-I", "-c", code], capture_output=True, text=True,
                       env={**os.environ, "APPWORLD_ROOT": str(P.ROOT_OPT)})
    lt = json.loads(r.stdout.strip().splitlines()[-1])
    import evaluator as E
    same = E.split_ids("train") == lt == P.read_split("train") and len(lt) == 90
    import adapter as A
    from cap_evolve import Task
    refused = False
    os.environ.pop("AW_ALLOW_SEALED", None)
    fake = Task(id="0000000_9", input={"instruction": "x", "supervisor": "x"})
    try:
        A.Adapter().run_trials([fake], P.SEED_CAP, n_trials=1, base_seed=0)
    except PermissionError:
        refused = True
    try:
        E.split_ids("test_normal")
        sealed_split = False
    except PermissionError:
        sealed_split = True
    return done("a6", {"train_order_matches": same, "outside_id_refused": refused, "test_split_refused": sealed_split,
                       "ok": same and refused and sealed_split})


def a7() -> int:
    """The window orders regenerate from their seeds (sha256 recorded in the manifest)."""
    import window5
    tr, dv = P.read_split("train"), P.read_split("dev")
    o1 = window5.make_order(dv, list(P.ARMS), 1, window5.DEV_ORDER_SEED)
    o2 = window5.make_order(dv, list(P.ARMS), 1, window5.DEV_ORDER_SEED)
    same = window5.order_sha(o1) == window5.order_sha(o2)
    P.update_manifest(dev_order={"seed": window5.DEV_ORDER_SEED, "sha256": window5.order_sha(o1), "cells": len(o1)})
    return done("a7", {"dev_order_reproducible": same, "cells": len(o1), "ok": same and len(o1) == 57 * 6})


def a8() -> int:
    """Context and M_cap: P_max over the 147 train∪dev stock prompts, H_max from 10 dev episodes,
    M_cap = min(30,000 chars, 34,000 − P_max − H_max tokens); then 3 dev episodes with an M_cap memory."""
    import tiktoken
    enc = tiktoken.get_encoding("o200k_base")
    from jinja2 import Template
    tmpl = (P.SEED_CAP / "policy" / "instructions.txt").read_text()
    import adapter as A
    ids = P.read_split("train") + P.read_split("dev")
    p_max = 0
    for tid in ids:
        spec = json.loads((P.ROOT_OPT / "data" / "tasks" / tid / "specs.json").read_text())
        sup = spec["supervisor"]
        # app_descriptions: the same json the agent renders (AppWorld's app descriptions)
        descr = _app_descriptions()
        text = Template(tmpl).render(instruction=spec["instruction"], main_user=sup, app_descriptions=descr)
        p_max = max(p_max, len(enc.encode(text)))
    import evaluator as E
    dev = E.split_ids("dev")
    recs = E.evaluate("acc_a8", E.materialize("acc_a8"), dev[:10], phase="A8", split="dev")
    infra = sum(1 for r in recs if r.get("error"))
    # history = the largest per-step prompt minus the stock prompt of that episode
    h_max = 0
    for r in recs:
        spec = json.loads((P.ROOT_OPT / "data" / "tasks" / r["task_id"] / "specs.json").read_text())
        stock = len(enc.encode(Template(tmpl).render(instruction=spec["instruction"], main_user=spec["supervisor"],
                                                     app_descriptions=_app_descriptions())))
        h_max = max(h_max, int(r.get("max_prompt_tokens") or 0) - stock)
    max_prompt_nomem = max(int(r.get("max_prompt_tokens") or 0) for r in recs)
    cap_tokens = min(34000 - p_max - h_max, 30000 // 3)
    # a 30,000-char memory is ~6–8K tokens; the token rule binds only if smaller
    filler = _filler_memory(enc, cap_tokens)
    mem_tokens = len(enc.encode(filler))
    cd = E.materialize("acc_a8", {"memory/playbook.md": filler})
    recs_m = E.evaluate("acc_a8", cd, dev[10:13], phase="A8m", split="dev")
    vllm_first = []
    for r in recs_m:
        st = r.get("steps") or []
        if st:
            vllm_first.append(int(st[0]["prompt_tokens"]))
    # tiktoken vs vLLM on the first request of a memory episode (prompt + memory + heading)
    spec = json.loads((P.ROOT_OPT / "data" / "tasks" / recs_m[0]["task_id"] / "specs.json").read_text())
    import aw_agent
    rendered = Template(tmpl).render(instruction=spec["instruction"], main_user=spec["supervisor"],
                                     app_descriptions=_app_descriptions())
    rendered = aw_agent.insert_before_final_block(rendered, aw_agent.MEMORY_HEADING + "\n" + filler)
    tk = len(enc.encode(rendered))
    ratio = (vllm_first[0] / tk) if vllm_first and tk else None
    max_prompt_mem = max(int(r.get("max_prompt_tokens") or 0) for r in recs_m)
    m_cap = {"tokens": cap_tokens, "chars": 30000, "p_max": p_max, "h_max": h_max,
             "rule": "min(30000 chars, 34000 - P_max - H_max tokens)"}
    P.update_manifest(m_cap=m_cap)
    res = {"p_max": p_max, "h_max": h_max, "m_cap_tokens": cap_tokens, "max_prompt_no_memory": max_prompt_nomem,
           "infra_no_memory": infra, "memory_tokens_tested": mem_tokens, "max_prompt_with_memory": max_prompt_mem,
           "vllm_over_tiktoken_first_request": round(ratio, 4) if ratio else None,
           "ok": max_prompt_nomem < 34000 and max_prompt_mem < 34000 and ratio is not None and abs(ratio - 1) <= 0.02
           and infra == 0}
    return done("a8", res)


_APPS = None


def _app_descriptions() -> str:
    """The exact app_descriptions json the agent renders (AppWorld's own description table, all apps)."""
    global _APPS
    if _APPS is None:
        from appworld.apps import get_all_apps
        from appworld.task import get_app_to_description
        d = get_app_to_description()
        _APPS = json.dumps([{"name": k, "description": d[k]} for k in get_all_apps(skip_admin=True)], indent=1)
    return _APPS


def _filler_memory(enc, tokens: int) -> str:
    rnd = random.Random(0)
    words = ["check", "the", "api", "docs", "before", "calling", "pagination", "page_index", "always", "verify",
             "results", "then", "complete", "task", "with", "answer", "loop", "until", "empty", "list"]
    lines, n = [], 0
    while n < tokens - 30:
        line = "- " + " ".join(rnd.choice(words) for _ in range(12)) + "."
        lines.append(line)
        n += len(enc.encode(line)) + 1
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(globals()[sys.argv[1]]())
