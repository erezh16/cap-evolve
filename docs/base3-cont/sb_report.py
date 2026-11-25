import json, glob, os, statistics as st, collections, datetime as dt, sys
R = os.path.expanduser("~/b3/sb/run_base/run_real")
final = json.load(open(f"{R}/final.json"))
base = json.load(open(f"{R}/baseline.json"))
splits = json.load(open(f"{R}/splits.json"))
def ms(v): return (round(st.mean(v), 4), round(st.stdev(v), 4) if len(v) > 1 else 0.0)
out = {"final_keys": list(final.keys()), "base_keys": list(base.keys()), "splits": {k: (len(v) if isinstance(v, list) else v) for k, v in splits.items()}}
# bench results, latest attempt per (seed, task)
by = collections.defaultdict(list)
for f in glob.glob(f"{R}/bench_jobs/seed/seed*/*/*/result.json"):
    p = f.split("/"); by[(int(p[-4][4:]), p[-2].rsplit("__", 1)[0])].append(f)
recs = {}
for k, fs in by.items():
    fs.sort(key=lambda x: os.path.getmtime(os.path.dirname(x)))
    d = json.load(open(fs[-1])); a = d.get("agent_result") or {}
    t0 = dt.datetime.fromisoformat(d["started_at"]); t1 = dt.datetime.fromisoformat(d["finished_at"])
    models = set()
    for g in glob.glob(os.path.dirname(fs[-1]) + "/**/*", recursive=True):
        if os.path.isfile(g) and os.path.getsize(g) < 50_000_000:
            try:
                import re
                models |= set(re.findall(r'"model"\s*:\s*"([^"]+)"', open(g, errors="ignore").read()))
            except Exception: pass
    recs[k] = dict(reward=(d.get("rewards") or {}).get("reward"), attempts=len(fs), err=(d.get("error") or ""),
                   nin=a.get("n_input_tokens") or 0, ncache=a.get("n_cache_read_tokens") or 0, nout=a.get("n_output_tokens") or 0,
                   sec=(t1 - t0).total_seconds(), tool_calls=a.get("n_tool_calls"), skills=a.get("n_skill_invocations"),
                   models=sorted(models))
allmodels = set().union(*[set(r["models"]) for r in recs.values()])
out["models_seen"] = sorted(allmodels)
for split in ("val", "test"):
    ids = splits[split]; res = {}
    trial = {k: [] for k in range(5)}; trial0 = {k: [] for k in range(5)}
    rows = {}
    for t in ids:
        rows[t] = [recs.get((k, t), {}).get("reward") for k in range(5)]
        for k in range(5):
            r = rows[t][k]
            trial0[k].append(0.0 if r is None else r)
            if r is not None: trial[k].append(r)
    tm = [st.mean(trial[k]) for k in range(5)]; tm0 = [st.mean(trial0[k]) for k in range(5)]
    sel = [recs[(k, t)] for t in ids for k in range(5) if (k, t) in recs]
    ok = [r for r in sel if r["reward"] is not None]
    res["rows"] = rows
    res["trial_means_excl"] = [round(x, 4) for x in tm]; res["headline_excl"] = ms(tm)
    res["trial_means_as0"] = [round(x, 4) for x in tm0]; res["headline_as0"] = ms(tm0)
    res["n_trials"] = len(sel); res["errored"] = len(sel) - len(ok)
    res["attempts_total"] = sum(r["attempts"] for r in sel)
    res["budget_900s_hits"] = sum("wall-clock budget" in r["err"] for r in sel)
    res["tokens"] = dict(input=sum(r["nin"] for r in sel), cache_read=sum(r["ncache"] for r in sel), output=sum(r["nout"] for r in sel))
    res["serial_seconds"] = round(sum(r["sec"] for r in sel), 1)
    res["per_episode"] = dict(reward=ms([r["reward"] for r in ok]), seconds=ms([r["sec"] for r in sel]),
                             input_tokens=ms([r["nin"] for r in sel]), output_tokens=ms([r["nout"] for r in sel]),
                             tool_calls=ms([r["tool_calls"] or 0 for r in sel]), skill_invocations=sum(r["skills"] or 0 for r in sel))
    # pass^k over tasks: fraction of tasks where all k first trials pass (unbiased estimator via combos)
    from math import comb
    pk = {}
    for kk in range(1, 6):
        vals = []
        for t in ids:
            v = [r for r in rows[t] if r is not None]
            if len(v) >= kk:
                c = sum(1 for r in v if r >= 1.0); vals.append(comb(c, kk) / comb(len(v), kk))
        pk[kk] = round(st.mean(vals), 4) if vals else None
    res["pass_hat_k"] = pk
    out[split] = res
out["final_test_reward"] = final["test"]["reward"]; out["final_pass_k"] = final["test"].get("pass_k"); out["final_n_scored"] = final["test"].get("n_scored")
out["final_seconds"] = final["test"].get("seconds")
out["baseline_val"] = {k: base.get(k) for k in ("val", "val_reward", "reward", "stderr", "n_scored") if k in base}
print(json.dumps(out, indent=1, default=str))
