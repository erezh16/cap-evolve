"""§12.2 milestone "build and acceptance done", on all 13 issues (sequential, 3 s apart, keyed `accept_done`).

  . examples/appworld/test_all/env.sh && python3 -I examples/appworld/test_all/milestone_accept.py [--dry-run]

Each body names its arm and gives that arm's fetch source, hash check, lint result and T4 injection line, plus the
T1 to T10 summary and the status fields (so it also counts as that hour's status). Flags and counts only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "scripts"))
import autopost  # noqa: E402
import awrest as P  # noqa: E402
import post  # noqa: E402

ACC = P.AW_STATE / "acceptance"


def summary() -> list[str]:
    g = lambda n: P.read_json(ACC / f"{n}.json", {}) or {}  # noqa: E731
    t1, t3, t5, t10 = g("t1"), g("t3"), g("t5"), g("t10")
    t78 = g("a10")
    return [
        f"- T1 RITS: max_model_len {t1.get('max_model_len')}; 1 dev seed episode through the window's episode path "
        f"({t1.get('seed_episode', {}).get('termination')}, {t1.get('seed_episode', {}).get('n_steps')} steps); RITS key "
        f"hits under the state, scratch and pushed files: {t1.get('key_hits')} — {'PASS' if t1.get('ok') else 'FAIL'}",
        f"- T2 REPL hardening (import os, open(answer.json), pathlib read all fail), root_opt clean, root_full unreadable "
        f"— {'PASS' if g('a3a5').get('ok') else 'FAIL'}",
        f"- T3 order: {t3.get('cells')} cells, each (arm, task, trial) once, regenerated sha256 identical "
        f"(`{(t3.get('sha256') or '')[:16]}…`) — {'PASS' if t3.get('ok') else 'FAIL'}",
        f"- T4 injection for all 13 arms (dev task, no model call) — {'PASS' if g('t4').get('ok') else 'FAIL'}",
        "- T5 context: the 3 largest first requests (ace, skillopt, evoskill) completed 1 dev episode each, max prompt "
        + ", ".join(f"{e['arm']} {e['max_prompt_tokens']:,}" for e in t5.get("episodes", []))
        + f" tokens, no context_exceeded — {'PASS' if t5.get('ok') else 'FAIL'}",
        f"- T6 memory guard: period 5 s, PAUSE within {g('a11').get('pause_latency_s_upper_bound')} s of a synthetic "
        f"allocation, no slot taken while paused — {'PASS' if g('a11').get('ok') else 'FAIL'}",
        f"- T7 ledger: concurrent appends all land with unique numbers; the content filter refuses a task id and an .env "
        f"value — {'PASS' if t78.get('concurrent_appends_landed') and t78.get('filter_refused_task_id') and t78.get('filter_refused_env_value') else 'FAIL'}",
        f"- T8 resume: a 6-cell dev mini window SIGKILLed after {t78.get('killed_after_cells')} cells resumed with "
        f"{t78.get('cells_rerun')} cells re-run — {'PASS' if t78.get('all_done') and t78.get('cells_rerun') == 0 else 'FAIL'}",
        f"- T9 deny rules: Read of root_full and of the window records refused; Read of the progress log and of a scored "
        f"artifact allowed; a nohup script read root_full (T1/T3) — {'PASS' if g('t9').get('ok') else 'FAIL'}",
        f"- T10 posting schedule: 13 distinct slots 276 s apart, unchanged across an autopost restart "
        f"— {'PASS' if t10.get('ok') else 'FAIL'}"]


def body(arm: str) -> str:
    a = (P.manifest().get("artifacts") or {}).get(arm, {})
    lint = (P.manifest().get("lint") or {}).get(arm, {})
    t4 = (P.read_json(ACC / "t4.json", {}) or {}).get(arm, {})
    lines = [f"**{P.METHOD_NAMES[arm]} (`{arm}`): build and acceptance done.** Nothing scored yet; the window is next.",
             "", "**This arm:**",
             f"- fetched from {'the local copy' if a.get('source') == 'local' else 'Box'} (`{a.get('source_path')}`); "
             f"hash rule {a.get('rule')}: expected `{(a.get('expected') or '')[:16]}…`, computed "
             f"`{(a.get('computed') or '')[:16]}…`, **{'match' if a.get('expected') == a.get('computed') else 'MISMATCH'}**",
             f"- lint: " + ("pass" if not lint.get("violations") else
                            "pass except the disclosed exception D6 (" + "; ".join(lint["violations"]) + ")"),
             f"- surfaces searched {P.SURFACES_OF[arm]}; surfaces changed vs the seed {P.SURFACES_CHANGED[arm]}",
             f"- T4 injection (first request for one dev task, no model call): {t4.get('messages')} messages, "
             f"{t4.get('prompt_tokens_o200k'):,} prompt tokens (o200k), memory block "
             f"{'present, before `My name is:`' if t4.get('memory_before_my_name_is') else 'none'}, helpers "
             f"{'defined' if t4.get('helpers_defined') else 'none'}, notes {t4.get('notes')}"
             + (" (appended to the API docs)" if t4.get("note_appended") else "")
             + ("; byte-identical to the stock first request" if t4.get("byte_identical_to_stock") else "") + ".",
             "", "**Acceptance (all arms, dev ids only, nothing counted):**", *summary(), "",
             "**Status:**", *autopost.ta_status_lines(arm)]
    return "\n".join(lines)


if __name__ == "__main__":
    if "--dry-run" in sys.argv:
        print(body(sys.argv[sys.argv.index("--dry-run") + 1] if len(sys.argv) > 2 else "altk"))
        raise SystemExit(0)
    out = post.post_all("accept_done", "{NAME}: build and acceptance done", body)
    for a, u in out.items():
        if u:
            autopost.mark_posted(a)
    print(json.dumps(out))
