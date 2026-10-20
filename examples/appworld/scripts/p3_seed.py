"""P3: the shared seed baseline, run exactly once (docs/EVAL_APPWORLD_REST.md §5.4 rule Q4, §12.1).

  venv-aw/bin/python -I p3_seed.py

The seed (seed_capability, SEED_HASH) on all 90 train and 57 dev tasks, 1 trial, trial seed 100, through the
shared evaluator with phase "P3" (charged to "seed", not to any candidate). Resumable: the evaluator cache holds
every finished episode, so a re-run after a crash runs only the missing ones. Infra failures are retried once by
the worker; any still missing after that are re-requested once more here (they are never cached). When all 147
records exist it writes AW_STATE/SEED_BASELINE_DONE (from then on a fresh seed episode raises SeedRerunRefused),
pushes STATE/seed/baseline.json (aggregates only) and appends the P3 phase_done entry.
"""

from __future__ import annotations

import os
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "common")]
import awrest as P  # noqa: E402
import evaluator as E  # noqa: E402
import status_doc as S  # noqa: E402


def main() -> int:
    if E.SEED_DONE.exists():
        print("P3 already done")
        return 0
    (P.AW_STATE / "RUNNING.pid").write_text(f"{os.getpid()} p3_seed\n")
    try:
        tr, dv = E.split_ids("train"), E.split_ids("dev")
        out = {}
        for attempt in range(2):
            todo = [t for t in tr + dv if t not in out or out[t].get("error")]
            if not todo:
                break
            recs = E.evaluate("seed", P.SEED_CAP, todo, phase="P3", tag="p3-seed-baseline")
            out.update({r["task_id"]: r for r in recs})
        missing = [t for t in tr + dv if out.get(t, {}).get("error")]
        if missing:
            S.append("error", "P3", "seed baseline", f"P3: {len(missing)} of 147 seed episodes still failed "
                     "(infrastructure) after the retries; P3 is not marked done. Next: re-run p3_seed.py.",
                     subject="P3 infra failures")
            return 1

        def agg(ids):
            rs = [out[t] for t in ids]
            return {"n": len(rs), "tgc": round(sum(r["reward"] for r in rs) / len(rs), 4),
                    "pass_fraction": round(sum(int(r.get("pass_count") or 0) for r in rs)
                                           / max(1, sum(int(r.get("num_tests") or 0) for r in rs)), 4),
                    "prompt_tokens_mean": round(statistics.mean(int(r.get("prompt_tokens") or 0) for r in rs)),
                    "completion_tokens_mean": round(statistics.mean(int(r.get("completion_tokens") or 0) for r in rs)),
                    "max_prompt_tokens": max(int(r.get("max_prompt_tokens") or 0) for r in rs),
                    "steps_mean": round(statistics.mean(int(r.get("n_steps") or 0) for r in rs), 2),
                    "episode_seconds_mean": round(statistics.mean(float(r.get("episode_seconds") or 0) for r in rs), 1),
                    "step_cap_hits": sum(1 for r in rs if r.get("termination") == "max_steps"),
                    "token_cap_hits": sum(1 for r in rs if r.get("termination") == "token_cap"),
                    "context_exceeded": sum(1 for r in rs if r.get("termination") == "context_exceeded"),
                    "fs_probe": sum(1 for r in rs if r.get("fs_probe"))}
        ro = P.read_jsonl(P.AW_STATE / "seed" / "rollouts.jsonl")
        base = {"seed_hash": E.seed_hash(), "train": agg(tr), "dev": agg(dv), "union": agg(tr + dv),
                "fresh_episodes_on_record": len(ro), "infra_rows": sum(1 for r in ro if r.get("infra")),
                "wall": [ro[0]["t"], ro[-1]["t"]] if ro else None}
        P.write_json(P.PUSHED / "seed" / "baseline.json", base)
        P.update_manifest(seed={"SEED_HASH": E.seed_hash(), "baseline": "STATE/seed/baseline.json"})
        E.SEED_DONE.write_text(P.utcnow() + "\n")
        S.append("phase_done", "P3", "shared seed baseline",
                 f"P3 done: the seed (SEED_HASH {E.seed_hash()[:16]}) on 90 train + 57 dev tasks, 1 trial, seed 100. "
                 f"Train TGC {base['train']['tgc']}, dev TGC {base['dev']['tgc']} (selection sets, 1 trial). "
                 f"{len(ro)} fresh episode rows ({base['infra_rows']} infra rows retried), counted once as the shared "
                 "seed baseline and charged to no candidate. From now on a fresh seed episode raises "
                 "SeedRerunRefused. Next: P4 candidate searches.",
                 done_through="P3/seed", next_unit="P4/searches",
                 extra={"counts": {"seed_baseline": 147}},
                 artifacts=["STATE/seed/baseline.json", "STATE/manifest.json"], subject="P3 shared seed baseline")
        return 0
    finally:
        (P.AW_STATE / "RUNNING.pid").unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
