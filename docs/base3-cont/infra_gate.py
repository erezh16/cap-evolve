"""Exit 1 if more than half of the rollouts in a dir are errored (infra) - base3 §1.3. (~/b3/infra_gate.py)"""
import json, sys, glob
fs = glob.glob(sys.argv[1] + "/*.json")
err = sum(1 for f in fs if (json.load(open(f)).get("rollout") or {}).get("error"))
print(f"infra_gate: {err}/{len(fs)} errored rollouts")
sys.exit(1 if not fs or err * 2 > len(fs) else 0)
