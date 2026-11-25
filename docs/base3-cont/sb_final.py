"""Final-attempt table for skillsbench from BenchFlow's own result.json files (latest-mtime attempt per seed/task)."""
import glob, json, os, sys, collections
root = sys.argv[1]
by = collections.defaultdict(list)
for f in glob.glob(f"{root}/seed/seed*/*/*/result.json"):
    parts = f.split("/"); seed = parts[-4]; task = parts[-2].rsplit("__", 1)[0]
    by[(seed, task)].append(f)
rows = {}
for (seed, task), fs in by.items():
    fs.sort(key=lambda p: os.path.getmtime(os.path.dirname(p)))
    d = json.load(open(fs[-1])); a = d.get("agent_result") or {}
    r = (d.get("rewards") or {}).get("reward")
    rows[(seed, task)] = dict(attempts=len(fs), reward=r, error=(d.get("error") or "")[:60],
                             nin=a.get("n_input_tokens"), nout=a.get("n_output_tokens"),
                             start=d.get("started_at"), end=d.get("finished_at"),
                             name_order_pick_same=(sorted(fs)[-1] == fs[-1]))
print(json.dumps({f"{s}|{t}": v for (s, t), v in sorted(rows.items())}, indent=0))
