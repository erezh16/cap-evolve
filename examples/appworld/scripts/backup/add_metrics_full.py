"""Add data/metrics_full.jsonl (+ README) to every run folder: reward, tokens, latency and cost in one place.

    python add_metrics_full.py BACKUP_DIR

Rows (one JSON object per line, field `level` says which kind):
  - level "episode": one per held-out final-window episode the run owns. reward (1/0), prompt/completion
    tokens, latency (episode_seconds), steps, termination. Agent cost: unpriced (IBM RITS does not price
    calls): cost_usd null, cost_source "unpriced".
  - level "search_round": one per optimizer round (cap-evolve) or pipeline step (ALTK). reward on the search
    set, optimizer tokens, optimizer USD, optimizer and evaluation seconds, accepted.
  - level "optimizer_call" (ALTK only): one per litellm call: tokens, seconds, and an ESTIMATED USD at the
    Claude Sonnet 5.5 list price ($2 / $10 per MTok in/out, no caching); cost_source "estimated_list_price".
  - level "run_total": one per training run/attempt: summed tokens, USD and time.
All values are read from files already in the run folder; nothing is recomputed from scratch.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

B = Path(sys.argv[1])
SONNET55 = {"input_per_mtok": 2.00, "output_per_mtok": 10.00, "source": "Anthropic list price, cached 2026-10-06"}
R1, R2, R3 = sorted(p.name for p in B.glob("20*") if "breach" in p.name), None, None
RUNS = {p.name: p for p in B.glob("20*")}
NAME = {k: ("R1" if "breach" in k else "R2" if "altkevolve" in k else "R3") for k in RUNS}


def jl(path: Path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def episode_rows(results: Path, arms: set[str], window: str) -> list[dict]:
    out = []
    for r in jl(results):
        if r["arm"] not in arms:
            continue
        out.append({"level": "episode", "window": window, "arm": r["arm"], "task_id": r["task_id"], "trial": r["trial"],
                    "reward": None if r.get("infra_error") else (1.0 if r.get("success") else 0.0),
                    "infra_error": r.get("infra_error"), "prompt_tokens": r.get("prompt_tokens"),
                    "completion_tokens": r.get("completion_tokens"), "max_prompt_tokens": r.get("max_prompt_tokens"),
                    "latency_seconds": r.get("episode_seconds"), "steps": r.get("n_steps"),
                    "termination": r.get("termination"), "cost_usd": None, "cost_source": "unpriced (IBM RITS)"})
    return out


def cape_rows(run_dir: Path, attempt: str) -> list[dict]:
    ev = jl(run_dir / "events.jsonl")
    st = json.loads((run_dir / "state.json").read_text())
    rows = []
    base = next((e for e in ev if e.get("kind") in ("baseline", "baseline_reused")), {})
    rows.append({"level": "search_round", "attempt": attempt, "round": 0, "candidate": "seed", "kind": base.get("kind"),
                 "reward_search_set": base.get("val"), "search_set": "train = val = official train ∪ dev (147)",
                 "accepted": True, "optimizer_usd": 0.0, "optimizer_tokens": 0, "optimizer_seconds": 0.0})
    for i, e in enumerate((e for e in ev if e.get("kind") == "step"), 1):
        rows.append({"level": "search_round", "attempt": attempt, "round": i, "candidate": e["candidate"],
                     "parent": e.get("parent"), "accepted": e.get("accept"), "reason": e.get("reason"),
                     "reward_search_set": e.get("val"), "parent_reward_search_set": e.get("parent_val"),
                     "optimizer_usd": e.get("opt_cost_usd"), "optimizer_tokens": e.get("opt_tokens"),
                     "optimizer_seconds": e.get("optimizer_seconds"), "eval_seconds": e.get("runner_seconds"),
                     "agent_tokens": e.get("tokens"), "agent_cost_usd": None, "agent_cost_source": "unpriced (IBM RITS)",
                     "optimizer_cost_source": "claude-code CLI report (total_cost_usd)"})
    sp = st["spent"]
    rows.append({"level": "run_total", "attempt": attempt, "champion": st["best_id"], "reward_search_set": sp.get("best_val"),
                 "metric_calls": sp.get("metric_calls"), "optimizer_usd": sp.get("optimizer_usd"),
                 "optimizer_tokens": sp.get("optimizer_tokens"), "optimizer_seconds": sp.get("optimizer_seconds"),
                 "agent_tokens": sp.get("runner_tokens"), "agent_seconds": sp.get("runner_seconds"),
                 "agent_cost_usd": None, "agent_cost_source": "unpriced (IBM RITS)"})
    return rows


def altk_rows(root: Path) -> list[dict]:
    a = root / "altk"
    rows = []
    usd_tot = pt_tot = ct_tot = sec_tot = 0.0
    for i, u in enumerate(jl(a / "optimizer_usage.jsonl")):
        pt, ct = u.get("prompt_tokens") or 0, u.get("completion_tokens") or 0
        usd = round(pt / 1e6 * SONNET55["input_per_mtok"] + ct / 1e6 * SONNET55["output_per_mtok"], 6)
        rows.append({"level": "optimizer_call", "call": i, "t": u.get("t"), "model": u.get("model"),
                     "prompt_tokens": pt, "completion_tokens": ct, "latency_seconds": u.get("seconds"),
                     "error": u.get("error"), "cost_usd": usd, "cost_source": "estimated_list_price"})
        usd_tot += usd; pt_tot += pt; ct_tot += ct; sec_tot += u.get("seconds") or 0
    ms = json.loads((a / "mining_summary.json").read_text())
    ds = json.loads((a / "dose_selection.json").read_text())
    dev = list((a / "dev_altk-ret").glob("*.json"))
    dev_tok = sum(json.loads(f.read_text())["rollout"].get("tokens", 0) for f in dev)
    dev_sec = sum(json.loads(f.read_text())["rollout"]["metadata"].get("episode_seconds") or 0 for f in dev)
    rows.append({"level": "search_round", "step": "mine+consolidate", "guidelines_before": ms["guidelines_before"],
                 "guidelines_after": ms["guidelines_after"], "optimizer_calls": ms["optimizer_usage"]["calls"],
                 "optimizer_tokens": int(pt_tot + ct_tot), "optimizer_usd": round(usd_tot, 4),
                 "optimizer_cost_source": "estimated_list_price", "optimizer_seconds": round(sec_tot, 1)})
    rows.append({"level": "search_round", "step": "dose_selection_dev", "dose": ds["chosen"],
                 "reward_search_set": ds["altk-ret"]["dev_tgc"], "search_set": "official dev (57)",
                 "agent_tokens": dev_tok, "eval_seconds": round(dev_sec, 1), "agent_cost_usd": None,
                 "agent_cost_source": "unpriced (IBM RITS)", "altk_full": "infeasible (memory lint)"})
    rows.append({"level": "run_total", "optimizer_calls": len([r for r in rows if r["level"] == "optimizer_call"]),
                 "optimizer_tokens": int(pt_tot + ct_tot), "optimizer_prompt_tokens": int(pt_tot),
                 "optimizer_completion_tokens": int(ct_tot), "optimizer_usd": round(usd_tot, 2),
                 "optimizer_cost_source": "estimated_list_price", "optimizer_seconds": round(sec_tot, 1),
                 "search_rollouts": 147, "agent_cost_usd": None, "agent_cost_source": "unpriced (IBM RITS)"})
    return rows


README = """# metrics_full.jsonl

One file with reward, tokens, latency and cost for this run. Each row has a `level`:

| level | one row per | reward | tokens | latency | cost |
|---|---|---|---|---|---|
| `episode` | held-out final-window episode | `reward` (1/0; null if infra error) | `prompt_tokens`, `completion_tokens` | `latency_seconds` | agent: `cost_usd` null, **unpriced** (IBM RITS does not price calls) |
| `search_round` | optimizer round (cap-evolve) / pipeline step (ALTK) | `reward_search_set` (train ∪ dev = fit metric; ALTK dose: dev) | `optimizer_tokens`, `agent_tokens` | `optimizer_seconds`, `eval_seconds` | `optimizer_usd` |
| `optimizer_call` | ALTK litellm call | — | prompt / completion | `latency_seconds` | `cost_usd` **estimated** at Claude Sonnet 5.5 list price ($2 / $10 per MTok) |
| `run_total` | training run / attempt | champion's search reward | totals | totals | totals |

Cost sources: cap-evolve optimizer USD is the claude-code CLI's own report (it includes the Opus 5.5 subagents,
finding F21). ALTK optimizer USD is an estimate (litellm did not price gateway calls). The agent model's cost is
not measured anywhere. Use tokens for the agent side.
The CI-format `metrics.jsonl` next to this file is the CI tool's train-fit output; it has no optimized-side
values because these runs score held-out results in a separate final window.
"""


def main() -> int:
    for name, root in sorted(RUNS.items()):
        tag = NAME[name]
        if tag == "R1":
            rows = episode_rows(root / "final_window/results.jsonl", {"cape-hc", "seed"}, "window_1")
            rows += cape_rows(root / "capevolve/run_cape_hc_s0", "cape_hc_s0")
            targets = [root / "data"]
            sets = [rows]
        elif tag == "R2":
            rows = episode_rows(root / "final_window/results.jsonl", {"altk"}, "window_1")
            rows += episode_rows(root / "final_window_2_rescored/results.jsonl", {"altk"}, "window_2")
            rows += altk_rows(root)
            targets, sets = [root / "data"], [rows]
        else:
            win = episode_rows(root / "final_window/results.jsonl", {"cape-hc", "seed", "altk"}, "window_2")
            targets, sets = [root / "data"], [win]
            for att in sorted(root.glob("attempt*")):
                rd = next(att.glob("capevolve/run_*"))
                arows = cape_rows(rd, rd.name.removeprefix("run_"))
                if "SCORED" in att.name:
                    arows = [r for r in win if r["arm"] == "cape-hc"] + arows
                targets.append(att / "data")
                sets.append(arows)
        for t, rows in zip(targets, sets):
            t.mkdir(parents=True, exist_ok=True)
            (t / "metrics_full.jsonl").write_text("".join(json.dumps(r, default=str) + "\n" for r in rows))
            (t / "metrics_full.README.md").write_text(README)
            lv = {}
            for r in rows:
                lv[r["level"]] = lv.get(r["level"], 0) + 1
            print(f"{tag} {t.relative_to(root)}: {lv}")
        # refresh MANIFEST.json
        files = []
        for p in sorted(root.rglob("*")):
            if p.is_file() and not p.is_symlink() and p.name != "MANIFEST.json":
                b = p.read_bytes()
                files.append({"path": str(p.relative_to(root)), "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()})
        (root / "MANIFEST.json").write_text(json.dumps({"run": name, "generated_utc": datetime.now(timezone.utc).isoformat(),
                                                        "files": len(files), "bytes": sum(f["bytes"] for f in files),
                                                        "entries": files}, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
