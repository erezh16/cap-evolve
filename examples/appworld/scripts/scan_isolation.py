"""P7 isolation scan (plan §9): grep everything the optimizer saw or produced for test-access signals.

Scanned: every Reflector / Curator / merge call (full prompt and response in llm_calls.jsonl), every
ace/steps/* file and every playbook snapshot. Patterns: the 585 test ids (the test-access signal, F16),
`test_normal`, `root_full`, `answer.json`, `ground_truth`; the release-wide canary is counted and reported
but is not a test signal. Also counts episode `fs_probe` hits per arm (adaptation, dev diagnostic and,
when present, the final window). Writes AW_STATE/isolation_scan.json and the pushed counts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "scripts"))
import awpaths as P  # noqa: E402

PATTERNS = ["test_normal", "root_full", "answer.json", "ground_truth"]
CANARY = "appworld:d17ac3f"


def counts(text: str, test_ids: set[str]) -> dict:
    import re
    out = {"test_id": sum(1 for m in re.findall(r"\b[0-9a-f]{7}_[0-9]+\b", text) if m in test_ids)}
    for p in PATTERNS:
        out[p] = text.count(p)
    out["canary"] = text.count(CANARY)
    return out


def add(a: dict, b: dict) -> dict:
    return {k: a.get(k, 0) + b.get(k, 0) for k in set(a) | set(b)}


def fs_probe(records: list[Path], order: list | None = None) -> dict:
    per = {}
    for p in records:
        r = json.loads(p.read_text())
        arm = (order[int(p.stem)]["arm"] if order else "ace")
        per.setdefault(arm, {"episodes": 0, "fs_probe_hits": 0})
        per[arm]["episodes"] += 1
        per[arm]["fs_probe_hits"] += int(bool(r.get("fs_probe")))
    return per


def main() -> int:
    test_ids = set(json.loads(P.LINT_CACHE.read_text())["test_ids"])
    ace = P.AW_STATE / "ace"
    res = {"llm_calls": {}, "steps_files": {}, "playbooks": {}}
    n_calls = 0
    calls = ace / "llm_calls.jsonl"
    if calls.exists():
        for line in calls.read_text().splitlines():
            c = json.loads(line)
            n_calls += 1
            res["llm_calls"] = add(res["llm_calls"], counts(json.dumps(c["messages"]) + (c["response"] or ""), test_ids))
    files = [p for p in (ace / "steps").rglob("*") if p.is_file() and "cap" not in p.relative_to(ace / "steps").parts]
    for p in files:
        res["steps_files"] = add(res["steps_files"], counts(p.read_text(errors="replace"), test_ids))
    pbs = sorted((ace / "playbooks").glob("pb_*.txt"))
    for p in pbs:
        res["playbooks"] = add(res["playbooks"], counts(p.read_text(), test_ids))
    res["scanned"] = {"llm_calls": n_calls, "steps_files": len(files), "playbooks": len(pbs)}
    res["fs_probe"] = {"adaptation": fs_probe(sorted((ace / "steps").glob("*/episode.json")))}
    dev_order = P.read_json(P.AW_STATE / "dev" / "order.json")
    if dev_order:
        res["fs_probe"]["dev"] = fs_probe(sorted((P.AW_STATE / "dev" / "records").glob("*.json")), dev_order)
    fin_order = P.read_json(P.AW_STATE / "final" / "order.json")
    if fin_order and (P.AW_STATE / "final" / "records").exists():
        res["fs_probe"]["final"] = fs_probe(sorted((P.AW_STATE / "final" / "records").glob("*.json")), fin_order)
    test_signal = sum(res[k].get("test_id", 0) + res[k].get("test_normal", 0) + res[k].get("root_full", 0)
                      for k in ("llm_calls", "steps_files", "playbooks"))
    gold_signal = sum(res[k].get("answer.json", 0) + res[k].get("ground_truth", 0)
                      for k in ("llm_calls", "steps_files", "playbooks"))
    fs = sum(v["fs_probe_hits"] for ph in res["fs_probe"].values() for v in ph.values())
    res["breach"] = bool(test_signal or gold_signal or fs)
    P.write_json(P.AW_STATE / "isolation_scan.json", res)
    P.write_json(P.PUSHED / "isolation_scan.json", res)
    print(json.dumps(res))
    if "--checkpoint" in sys.argv:
        import status_doc
        status_doc.append("phase_done", "P7", "isolation scan",
                          f"Isolation scan done over {n_calls} optimizer calls, {len(files)} ACE step files and "
                          f"{len(pbs)} playbook snapshots: test ids {sum(res[k].get('test_id', 0) for k in ('llm_calls','steps_files','playbooks'))}, "
                          f"`test_normal`/`root_full` {test_signal - sum(res[k].get('test_id', 0) for k in ('llm_calls','steps_files','playbooks'))}, "
                          f"`answer.json`/`ground_truth` {gold_signal}; canary (release-wide, reported only) "
                          f"{sum(res[k].get('canary', 0) for k in ('llm_calls','steps_files','playbooks'))}; "
                          f"episode fs_probe hits {fs}. Breach: {res['breach']}.\nNext: P8 final window.",
                          done_through="P7/scan", next_unit="P8/final", extra={"scan": {"breach": res["breach"]}},
                          artifacts=["STATE/isolation_scan.json"], subject="isolation scan")
    return 0


if __name__ == "__main__":
    sys.exit(main())
