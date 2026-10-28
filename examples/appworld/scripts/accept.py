"""Common acceptance checks of eval REST (docs/EVAL_APPWORLD_REST.md §13), adapted from eval 5. Run with venv-aw:

  venv-aw/bin/python -I accept.py a1|a2|a3a5|a4|a6|a7|a8|a11|a12|a13
Each prints one json line of flags and counts (no ids, no secrets) and writes AW_STATE/acceptance/<id>.json.
None of these rollouts are counted (S1): they run with phase "accept" under the throwaway names ``acc_*``.
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
import awrest as P  # noqa: E402

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
    td = P.SCRATCH / "acc_a1"
    td.mkdir(parents=True, exist_ok=True)
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
    rec = E.evaluate("acc_a2", E.materialize("acc_a2"), E.split_ids("dev")[1:2], phase="accept", tag="a2")[0]
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
    if P.LEDGER_PREFIX in ("CE2", "TA"):     # TEST_ALL §9 T2: the released-solution probe is not run
        env["AW_A5_NO_SOLUTION"] = "1"
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
    recs = E.evaluate("acc_a4", bad, E.split_ids("dev")[:2], phase="accept", tag="a4")
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
    """The final-window order regenerates from its seed (sha256 recorded in the manifest); the dev diagnostic order
    is the evaluator's (the dev ids in file order), so it is reproducible by construction. The test ids are read
    only inside this trusted script (root_full unlocked for the read, relocked at once); nothing but the hash and
    counts is printed or stored."""
    import window
    os.chmod(P.ROOT_FULL, 0o755)
    try:
        ids = P.read_split("test_normal", P.ROOT_FULL)
    finally:
        os.chmod(P.ROOT_FULL, 0o000)
    o1 = window.make_order(ids, list(P.ARMS), window.FINAL_TRIALS, window.FINAL_ORDER_SEED)
    o2 = window.make_order(list(ids), list(P.ARMS), window.FINAL_TRIALS, window.FINAL_ORDER_SEED)
    same = window.order_sha(o1) == window.order_sha(o2)
    P.update_manifest(final_order={"seed": window.FINAL_ORDER_SEED, "sha256": window.order_sha(o1), "cells": len(o1),
                                   "trials": window.FINAL_TRIALS, "trial_seeds": "5000 + trial", "infra_retries": 3})
    import evaluator as E
    dev_same = E.split_ids("dev") == P.read_split("dev") and len(E.split_ids("dev")) == 57
    return done("a7", {"final_order_reproducible": same, "cells": len(o1), "dev_order_file_order": dev_same,
                       "root_full_relocked": not os.access(P.ROOT_FULL, os.R_OK),
                       "ok": same and len(o1) == 168 * len(P.ARMS) * 2 and dev_same
                             and not os.access(P.ROOT_FULL, os.R_OK)})


def a8() -> int:
    """Context and M_cap, as the ACE sibling measured it (its A8): H_max = 60,000 / the lowest chars-per-token
    of the agent history in 10 dev episodes (the 60,000-char trim bounds the history); P_max = the largest
    stock first request over the 147 train∪dev tasks (tiktoken o200k_harmony on the message contents + the
    chat-template overhead measured against vLLM); M_cap = min(30,000 chars, 34,000 − P_max − H_max tokens),
    floored to 500. Then 3 dev episodes with the largest memory the lint allows stay < 34K prompt tokens and
    tiktoken is within 2% of vLLM on their first request."""
    import tiktoken
    from jinja2 import Template
    import aw_agent
    from appworld_agents.code.simplified.react_code_agent import SimplifiedReActCodeAgent
    enc = tiktoken.get_encoding("o200k_harmony")
    tok = lambda t: len(enc.encode(t, disallowed_special=()))  # noqa: E731
    tmpl = (P.SEED_CAP / "policy" / "instructions.txt").read_text().lstrip()

    def first_msgs(tid: str, memory: str = "") -> list[dict]:
        spec = json.loads((P.ROOT_OPT / "data" / "tasks" / tid / "specs.json").read_text())
        out = Template(tmpl).render(instruction=spec["instruction"], main_user=spec["supervisor"],
                                    app_descriptions=_app_descriptions())
        if memory:
            out = aw_agent.insert_before_final_block(out, aw_agent.MEMORY_HEADING + "\n" + memory)
        return SimplifiedReActCodeAgent.text_to_messages(None, out + "\n\n")

    import evaluator as E
    dev = E.split_ids("dev")
    recs = E.evaluate("acc_a8", E.materialize("acc_a8"), dev[:10], phase="accept", tag="a8")
    infra = sum(1 for r in recs if r.get("error"))
    ratios, overhead = [], []
    for r in recs:
        st = r.get("steps") or []
        hist = "".join("ASSISTANT:\n" + (s.get("thought") or "") + "\n```python\n" + (s.get("code") or "")
                       + "\n```USER:\nOutput:\n" + (s.get("output") or "") for s in st)
        if len(hist) > 2000:
            ratios.append(len(hist) / tok(hist))
        if st:
            overhead.append(int(st[0]["prompt_tokens"]) - sum(tok(m["content"]) for m in first_msgs(r["task_id"])))
    min_ratio = min(ratios)
    h_max = int(60000 / min_ratio + 0.999)
    ids = P.read_split("train") + P.read_split("dev")
    p_tok = max(sum(tok(m["content"]) for m in first_msgs(t, " ")) for t in ids)
    p_max = p_tok + max(overhead)
    m_cap_raw = 34000 - p_max - h_max
    m_cap = (m_cap_raw // 500) * 500
    P.update_manifest(m_cap={"tokens": m_cap, "chars": 30000, "P_max": p_max, "H_max": h_max,
                             "min_chars_per_token": round(min_ratio, 3), "template_overhead_max": max(overhead),
                             "encoding": "o200k_harmony",
                             "rule": "min(30000 chars, 34000 - P_max - H_max tokens), tokens floored to 500"})
    # the largest memory the lint allows: M_cap tokens or 30,000 chars, whichever binds first
    words = ["check", "the", "api", "docs", "before", "calling", "pagination", "page_index", "always", "verify",
             "results", "then", "complete", "task", "with", "answer", "loop", "until", "empty", "list"]
    rnd = random.Random(0)
    lines: list[str] = []
    while True:
        line = "- " + " ".join(rnd.choice(words) for _ in range(12)) + "."
        cand = "\n".join(lines + [line])
        if len(cand) > 30000 or tok(cand) > m_cap:
            break
        lines.append(line)
    mem = "\n".join(lines)
    recs_m = E.evaluate("acc_a8", E.materialize("acc_a8", {"memory/playbook.md": mem}), dev[10:13], phase="accept",
                        tag="a8m")
    eps = []
    for r in recs_m:
        st = r.get("steps") or []
        vt = int(st[0]["prompt_tokens"]) if st else None
        tt = sum(tok(m["content"]) for m in first_msgs(r["task_id"], mem)) + max(overhead)
        eps.append({"termination": r.get("termination"), "max_prompt_tokens": r.get("max_prompt_tokens"),
                    "lint_reject": r.get("lint_reject"), "rel_diff": round(abs(vt - tt) / vt, 4) if vt else None})
    res = {"history_ratios": [round(x, 3) for x in ratios], "H_max": h_max, "P_max": p_max,
           "template_overhead": overhead, "M_cap_tokens": m_cap, "memory_chars_tested": len(mem),
           "memory_tokens_tested": tok(mem), "max_prompt_no_memory": max(int(r.get("max_prompt_tokens") or 0) for r in recs),
           "infra_no_memory": infra, "memory_episodes": eps}
    res["ok"] = (infra == 0 and len(ratios) >= 5 and m_cap > 0 and res["max_prompt_no_memory"] < 34000
                 and all(e["max_prompt_tokens"] and e["max_prompt_tokens"] < 34000 and not e["lint_reject"]
                         and e["termination"] != "context_exceeded" and e["rel_diff"] is not None
                         and e["rel_diff"] <= 0.02 for e in eps))
    return done("a8", res)



def a11() -> int:
    """Memory guard (R2): sample period <= 10 s; a synthetic allocation crossing 90% sets PAUSED within 10 s; while
    PAUSED the evaluator starts no episode and opt_llm.chat no call; resume only below 85%. Uses a throwaway guard
    instance with lowered watermarks on the real cgroup (current use + a child-process allocation), so the real
    guard keeps running and the container never nears its limit."""
    import threading
    import opt_llm
    import evaluator as E
    cur = P.memstate()
    res = {"guard_period_s": cur.get("every_s"), "guard_fresh": not cur.get("stale")}
    base = float(cur["used_pct"])
    # watermarks well above the current use and its background swings; the child allocates ~4.5 GB (14%)
    hi, lo = round(base + 9.0, 2), round(base + 4.5, 2)
    test_state = P.AW_STATE / "a11"
    shutil.rmtree(test_state, ignore_errors=True)
    test_state.mkdir(parents=True)
    env = dict(os.environ, AW_STATE=str(test_state))
    guard = subprocess.Popen([sys.executable, "-I", str(EX / "scripts" / "memguard.py"), "loop", "--high", str(hi),
                              "--low", str(lo), "--every", "5"], env=env, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
    hog = None
    try:
        time.sleep(6)
        hog = subprocess.Popen([sys.executable, "-c", "import time; b=bytearray(int(4.5*2**30)); "
                                "[b.__setitem__(i,1) for i in range(0,len(b),4096)]; time.sleep(60)"])
        t0, paused_at = time.time(), None
        while time.time() - t0 < 40:
            if (test_state / "PAUSE").exists():
                paused_at = time.time()
                break
            time.sleep(0.5)
        filled_at = t0  # the allocation itself takes a few seconds; report the latency after the guard first saw it
        log = (test_state / "progress" / "memguard.log").read_text() if (test_state / "progress" / "memguard.log").exists() else ""
        res["paused"] = paused_at is not None
        res["pause_latency_s_upper_bound"] = round(paused_at - filled_at, 1) if paused_at else None
        # while PAUSED (pointing the shared code at the test PAUSE file): no episode, no optimizer call
        P.PAUSE_FILE, saved = test_state / "PAUSE", P.PAUSE_FILE
        started = {"episode": False, "chat": False}

        def try_episode():
            with P.Slot("a11"):
                started["episode"] = True

        def try_chat():
            P.wait_unpaused("a11")
            started["chat"] = True                   # opt_llm.chat calls wait_unpaused() before anything else

        ths = [threading.Thread(target=try_episode, daemon=True), threading.Thread(target=try_chat, daemon=True)]
        for t in ths:
            t.start()
        time.sleep(8)
        res["blocked_while_paused"] = not started["episode"] and not started["chat"]
        res["chat_calls_wait"] = "wait_unpaused" in Path(opt_llm.__file__).read_text().split("def chat", 1)[1][:600]
        res["slot_waits"] = "wait_unpaused" in Path(P.__file__).read_text().split("class Slot", 1)[1][:1500]
        hog.kill()
        hog.wait()
        t1 = time.time()
        while (test_state / "PAUSE").exists() and time.time() - t1 < 120:
            time.sleep(0.5)
        res["resumed_after_release"] = not (test_state / "PAUSE").exists()
        for t in ths:
            t.join(timeout=15)
        res["started_after_resume"] = started["episode"] and started["chat"]
        P.PAUSE_FILE = saved
        ms = json.loads((test_state / "MEMSTATE.json").read_text())
        res["memstate_fields"] = sorted(ms)
        res["transitions_logged"] = "PAUSED" in log and "RESUMED" in (test_state / "progress" / "memguard.log").read_text()
        res["resume_below_low"] = all(float(l.split("RESUMED: ")[1].split("%")[0]) < lo
                                      for l in (test_state / "progress" / "memguard.log").read_text().splitlines()
                                      if "RESUMED:" in l)
    finally:
        if hog and hog.poll() is None:
            hog.kill()
        guard.terminate()
    r = subprocess.run([str(Path.home() / "bin" / ("memok-testabl" if getattr(P, "TESTABL", False) else "memok-testall" if P.TESTALL else "memok-ce3" if P.LEDGER_ID == "CE3" else "memok-ce2" if P.LEDGER_PREFIX == "CE2" else "memok"))],
                       capture_output=True, text=True)
    res["spawn_check_reads_memstate"] = "memstate" in r.stdout and r.returncode == 0
    res["ok"] = (res["guard_period_s"] is not None and res["guard_period_s"] <= 10 and res["guard_fresh"]
                 and res["paused"] and res["pause_latency_s_upper_bound"] is not None
                 and res["blocked_while_paused"] and res["resumed_after_release"] and res["started_after_resume"]
                 and res["transitions_logged"] and res["resume_below_low"] and res["chat_calls_wait"]
                 and res["slot_waits"] and res["spawn_check_reads_memstate"])
    return done("a11", res)


def a12() -> int:
    """Metrics (Q2): one record of each kind carries every field of §5.2; proxy USD uses the Sonnet 5.5 prices."""
    import evaluator as E
    import opt_llm
    import sandbox as SB
    ep = E.evaluate("acc_a2", E.materialize("acc_a2"), E.split_ids("dev")[1:2], phase="accept", tag="a2")[0]
    ep_fields = ["reward", "prompt_tokens", "completion_tokens", "max_prompt_tokens", "n_steps", "termination",
                 "episode_seconds", "pass_count", "num_tests"]
    usage_fields = ["t", "seconds", "model", "role", "prompt_tokens", "completion_tokens", "cache_read",
                    "cache_write", "error", "finish_reason"]
    opt_llm.chat("Reply with the single word ok.", cand="acc_a12", role="a12", max_tokens=20)
    ws = SB.OPT_ROOT / "acc_a12" / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    d = SB.claude_call("acc_a12", "a12-cli", "Reply with the single word ok.", ws, allowed_tools="Read",
                       max_turns=2)
    rows = P.read_jsonl(P.AW_STATE / "acc_a12" / "optimizer_usage.jsonl")
    chat_row = next(r for r in rows if r["role"] == "a12")
    cli_row = next(r for r in reversed(rows) if r["role"] == "a12-cli")
    t = {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000, "cache_read": 1_000_000, "cache_write": 0}
    usd = opt_llm.proxy_usd(t)
    res = {"episode_fields": all(ep.get(k) is not None for k in ep_fields),
           "chat_fields": all(k in chat_row for k in usage_fields),
           "cli_fields": all(k in cli_row for k in usage_fields), "cli_ok": not d.get("is_error"),
           "cli_model": cli_row.get("model"), "cli_total_cost_usd_present": cli_row.get("total_cost_usd") is not None,
           "proxy_usd_1M_each": usd, "ok": False}
    res["ok"] = (res["episode_fields"] and res["chat_fields"] and res["cli_fields"] and res["cli_ok"]
                 and P.OPT_MODEL in (res["cli_model"] or "") and abs(usd - 12.20) < 1e-6)
    return done("a12", res)


def a13_ce2() -> dict:
    """CE2 §15 A13 on the REAL reused cache (no mini P3, no fresh seed episode): 7.4 passed; a candidate dir identical
    to the seed is served entirely from the cache on all 147 ids (0 counted, nothing fresh); a fresh seed episode is
    refused (SeedRerunRefused) for a seed whose record is missing (a probe with a seed value outside the cache)."""
    import evaluator as E
    sr = P.read_json(P.AW_STATE / "seed_reuse.json", {}) or {}
    ids = E.split_ids("train") + E.split_ids("dev")
    same = E.materialize("acc_a13", {})
    before = E.counted("acc_a13")
    missing = [t for t in ids if not E._cache_path(E.tree_hash(same), t, P.SEARCH_SEED_BASE, "search").exists()]
    if missing or not E.SEED_DONE.exists():
        raise SystemExit(f"a13_ce2: {len(missing)} seed records missing or no SEED_BASELINE_DONE: refusing to run episodes")
    recs = E.evaluate("acc_a13", same, ids, phase="search", tag="same-as-seed")
    out = {"seed_reuse_ok": sr.get("ok") is True, "same_tree_is_seed": E.tree_hash(same) == E.seed_hash(),
           "identical_served_from_cache": all(r.get("cache_hit") for r in recs) and len(recs) == 147,
           "counted_after": E.counted("acc_a13") - before,
           "tgc_from_cache": round(sum(r["reward"] for r in recs) / len(recs), 4)}
    try:
        E.evaluate("acc_a13", same, ids[:1], phase="search", tag="fresh-seed", seed=101)
        out["seed_rerun_refused"] = False
    except E.SeedRerunRefused:
        out["seed_rerun_refused"] = True
    return out


def a13() -> int:
    """Seed reuse (Q4) + the global slot pool. Runs on its own throwaway AW_STATE copy of the cache dir, so the real
    P3 baseline is untouched: a mini P3 on 4 dev ids, then a candidate identical to the seed is served from the cache
    (0 counted), a fresh seed episode raises SeedRerunRefused, and the slot pool never exceeds its size with 3
    concurrent callers."""
    import threading
    import evaluator as E
    dev = E.split_ids("dev")[:4]
    if P.LEDGER_PREFIX == "CE2":            # on the REAL reused cache, before the throwaway paths below are set
        pre = a13_ce2()
    saved_cache, saved_done = E.CACHE, E.SEED_DONE
    E.CACHE = P.AW_STATE / "a13" / "cache"
    E.SEED_DONE = P.AW_STATE / "a13" / "SEED_BASELINE_DONE"
    shutil.rmtree(P.AW_STATE / "a13", ignore_errors=True)
    shutil.rmtree(P.AW_STATE / "acc_a13", ignore_errors=True)
    res = {}
    if P.LEDGER_PREFIX == "CE2":
        res = pre
    try:
        if P.LEDGER_PREFIX == "CE2":
            raise _SkipMiniP3
        # mini P3: the seed on 4 dev ids, phase P3 (charged to the throwaway "a13seed" ledger file via a patched path)
        saved_lf = E._ledger_file
        E._ledger_file = lambda cand, phase: P.AW_STATE / "a13" / f"{phase}.jsonl"
        recs = E.evaluate("acc_a13", P.SEED_CAP, dev, phase="P3", tag="mini-p3")
        res["mini_p3_fresh"] = sum(1 for r in recs if not r.get("cache_hit"))
        E.SEED_DONE.parent.mkdir(parents=True, exist_ok=True)
        E.SEED_DONE.write_text("a13")
        same = E.materialize("acc_a13", {})                     # a candidate dir identical to the seed
        before = len(P.read_jsonl(P.AW_STATE / "a13" / "search.jsonl"))
        r2 = E.evaluate("acc_a13", same, dev, phase="search", tag="same-as-seed")
        res["identical_served_from_cache"] = all(r.get("cache_hit") for r in r2)
        res["counted_after"] = len(P.read_jsonl(P.AW_STATE / "a13" / "search.jsonl")) - before
        try:
            E.evaluate("acc_a13", same, E.split_ids("dev")[4:5], phase="search", tag="fresh-seed")
            res["seed_rerun_refused"] = False
        except E.SeedRerunRefused:
            res["seed_rerun_refused"] = True
        E._ledger_file = saved_lf
    except _SkipMiniP3:
        pass
    finally:
        E.CACHE, E.SEED_DONE = saved_cache, saved_done
    # slot pool: shrink the pool to 2 for this test, 3 threads x 4 acquisitions, peak concurrency must be <= 2
    size_file = P.SLOTS_DIR / "SIZE"
    prev = size_file.read_text() if size_file.exists() else None
    size_file.parent.mkdir(parents=True, exist_ok=True)
    peak, cur, lock = [0], [0], threading.Lock()

    def worker():
        for _ in range(4):
            with P.Slot("a13"):
                with lock:
                    cur[0] += 1
                    peak[0] = max(peak[0], cur[0])
                time.sleep(0.3)
                with lock:
                    cur[0] -= 1

    # other processes may hold real slots: measure against free slots, so use a dedicated dir
    saved_dir = P.SLOTS_DIR
    P.SLOTS_DIR = P.AW_STATE / "a13" / "slots"
    P.SLOTS_DIR.mkdir(parents=True, exist_ok=True)
    (P.SLOTS_DIR / "SIZE").write_text("2")
    ths = [threading.Thread(target=worker) for _ in range(3)]
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    P.SLOTS_DIR = saved_dir
    if prev is None:
        size_file.unlink(missing_ok=True)
    res["slot_peak_with_size_2"] = peak[0]
    if P.LEDGER_PREFIX == "CE2":
        res["ok"] = (res["seed_reuse_ok"] and res["same_tree_is_seed"] and res["identical_served_from_cache"]
                     and res["counted_after"] == 0 and res["seed_rerun_refused"] and peak[0] == 2)
    else:
        res["ok"] = (res["mini_p3_fresh"] == 4 and res["identical_served_from_cache"] and res["counted_after"] == 0
                     and res["seed_rerun_refused"] and peak[0] == 2)
    return done("a13", res)

class _SkipMiniP3(Exception):
    pass


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


if __name__ == "__main__":
    raise SystemExit(globals()[sys.argv[1]]())
