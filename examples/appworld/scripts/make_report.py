"""P10 report (plan §12): draft the #804 results comment into the pushed final/RESULTS.md.

  python3 -I make_report.py            # write the draft (no posting)
  python3 -I make_report.py --post     # post it once (refuses if a `posted` final entry exists)
Sources: analysis.json, ace/progress.json, manifest.json, isolation_scan.json, dev/cells.csv and the
ledger (resume history, phase times). Only aggregates are written; no task id, text or per-task outcome.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import re
import subprocess
import sys
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "scripts"))
sys.path.insert(0, str(EX / "adapters"))
import awpaths as P  # noqa: E402
import status_doc as S  # noqa: E402

OUT = P.PUSHED / "final" / "RESULTS.md"


def ledger_facts() -> dict:
    es = S.entries()
    kinds, times = {}, {}
    for n, chunk in es:
        m = S.JSON_RE.search(chunk)
        if not m:
            continue
        j = json.loads(m.group(1))
        kinds[j["kind"]] = kinds.get(j["kind"], 0) + 1
        t = dt.datetime.strptime(j["utc"], "%Y-%m-%dT%H:%M:%SZ")
        if j["kind"] in ("phase_start", "phase_done") or j.get("phase") not in times:
            times.setdefault(j["phase"], [t, t])
        times.setdefault(j["phase"], [t, t])
        times[j["phase"]][0] = min(times[j["phase"]][0], t)
        times[j["phase"]][1] = max(times[j["phase"]][1], t)
    return {"kinds": kinds, "n": len(es), "times": {k: round((v[1] - v[0]).total_seconds() / 3600, 2) for k, v in times.items()}}


def dev_summary() -> dict:
    p = P.PUSHED / "dev" / "cells.csv"
    if not p.exists():
        return {}
    rows = list(csv.DictReader(io.StringIO(p.read_text())))
    out = {}
    for arm in ("seed", "ace"):
        r = [x for x in rows if x["arm"] == arm]
        out[arm] = {"n": len(r), "tgc": round(100 * sum(float(x["reward"]) for x in r) / max(1, len(r)), 1),
                    "context_exceeded": sum(1 for x in r if x["termination"] == "context_exceeded"),
                    "infra": sum(1 for x in r if x["infra_error"] == "True")}
    return out


def example_bullets(pb: str, k: int = 3) -> list[str]:
    import lints
    bs = lints.bullets(pb)
    init = set(lints.bullets((EX / "ace/vendor/playbooks/appworld_initial_playbook.txt").read_text()))
    new = [b for b in bs if b not in init]
    new = [b for b in new if len(b[1]) >= 120]  # skip multi-line bullets whose first line is a heading
    pick = [new[len(new) * i // k] for i in range(k)] if len(new) >= k else new
    return [f"`[{i}]` {c[:400]}{'…' if len(c) > 400 else ''}" for i, c in pick]


def render() -> str:
    a = json.loads((P.PUSHED / "final" / "analysis.json").read_text())
    prog = json.loads((P.PUSHED / "ace" / "progress.json").read_text())
    m = P.manifest()
    scan = P.read_json(P.PUSHED / "isolation_scan.json") or {}
    fr = m["freeze"]
    pb = (P.PUSHED / "final" / "artifacts" / "ace" / "memory" / "playbook.md").read_text()
    s, c = a["arms"]["seed"], a["arms"]["ace"]
    d = a["delta"]
    rows = prog["rows"]
    sp = prog["spend"]
    tin = sum(v["input"] for v in sp.values())
    tout = sum(v["output"] for v in sp.values())
    lint = sum(r.get("lint_drop", 0) for r in rows)
    capd = sum(r.get("cap_drop", 0) for r in rows)
    dedup = [r["dedup"] for r in rows if r.get("dedup")]
    cur = sum(1 for r in rows if r.get("curated"))
    term = {}
    for r in rows:
        term[r["termination"]] = term.get(r["termination"], 0) + 1
    parse_err = sum(1 for r in rows if r.get("parse_error"))
    trunc = sum(v.get("truncated", 0) for v in sp.values())
    led = ledger_facts()
    dev = dev_summary()
    by = lambda arm, lvl: a["arms"][arm]["by_difficulty"].get(lvl, {})  # noqa: E731
    secs = "; ".join(f"{k.rstrip(':').lower()} {v}" for k, v in fr["sections"].items() if v)
    last_add = max((r["step"] for r in rows if r.get("ops_applied")), default=0)
    rt = led["times"]
    lines = [
        "## Results: AppWorld smoke test, ACE vs the seed agent, gpt-oss-120b (held-out test_normal)",
        "",
        f"{a['n_tasks']} test_normal tasks / {a['n_scenarios']} scenarios × {a['trials']} trials per arm, one interleaved "
        f"window, {s['missing_infra'] + c['missing_infra']} missing cells. Plan `docs/EVAL_SMOKE_TEST_ACE.md`, ledger "
        f"`docs/EVAL_SMOKE_TEST_ACE_STATUS.md` (branch `{P.BRANCH}`, `erezh16` fork).",
        "",
        "**Setup.** Agent under test (both arms): `openai/gpt-oss-120b-a100` on RITS, reasoning medium, temperature 0, "
        "AppWorld `42b5bcf` simplified ReAct code agent, stock prompt, 50 steps, 6,000 completion tokens per step. ACE "
        f"(`ace@82709de0`, `ace-appworld@928e8687`): offline adaptation without ground truth, 1 epoch over the official "
        f"`train` split (90 tasks, ACE's order), batch size 1, Generator = the common-harness agent, Reflector and Curator "
        f"= `aws/claude-sonnet-5-5`; the playbook goes in the memory slot of the stock prompt. Memory cap M_cap = "
        f"{m['m_cap']['value']:,} tokens (measured, A8). Decisions: D1 Sonnet 5.5 optimizer; D2 AppWorld from source; "
        f"D3 2 final trials; D4 the design's ACE pins; D5 (a) lazy dedup at the cap, `cap_drop` beyond it; D6 (a) adapt "
        f"on train, dev as a diagnostic; D7 (a) batch size 1.",
        "",
        "| arm | TGC | SGC | Δ TGC vs seed [95% CI] | Δ SGC vs seed [95% CI] |",
        "|---|---|---|---|---|",
        f"| seed | {s['tgc']} | {s['sgc']} | — | — |",
        f"| ace | **{c['tgc']}** | **{c['sgc']}** | {d['tgc']:+} [{d['ci95']['tgc'][0]:+}, {d['ci95']['tgc'][1]:+}] | "
        f"{d['sgc']:+} [{d['ci95']['sgc'][0]:+}, {d['ci95']['sgc'][1]:+}] |",
        "",
        "CI: scenario-clustered paired bootstrap (56 clusters, 10,000 resamples). One contrast, one search seed: an "
        "artifact-level statement about this one ACE playbook.",
        "",
        "**What this ACE is and is not.** This is ACE's released Reflector, Curator and playbook code, run under choices "
        "that differ from the paper's and from the colleagues' runs; any of them could explain the result as well as ACE "
        "itself could:",
        "1. the common template (the stock AppWorld prompt with a memory slot), not ACE's 27K-character Generator prompt;",
        "2. Sonnet 5.5 as Reflector and Curator, a stronger model than the target (the paper uses the target), and, "
        "because the gateway requires it, at the model's default temperature and with one phrase removed from both prompts "
        "(findings G1, G2 below);",
        "3. 1 epoch and 1 reflection per task (the paper allows up to 5 of each);",
        f"4. the M_cap size rule (D5): {len(dedup)} dedup runs, {capd} `cap_drop` bullets;",
        "5. the no-GT Reflector, which is never told whether a task passed;",
        "6. 50 steps instead of ACE's 40.",
        "A null or small result would be a result about *this configuration*, not evidence that ACE does not work; "
        "in the same way, the gain below is a result about this configuration (in particular a stronger optimizer "
        "model than the target, item 2), not a measurement of ACE as published.",
        "",
        "**Side by side** (compared only as gains over each side's own no-memory baseline, design §9.2 rule 1; "
        "harness, template, Reflector model and epochs differ, so the levels are not comparable):",
        "",
        "| source | baseline TGC / SGC | with ACE TGC / SGC | gain TGC / SGC |",
        "|---|---|---|---|",
        f"| this smoke test (common harness, Sonnet 5.5 Reflector / Curator, 1 epoch, M_cap) | {s['tgc']} / {s['sgc']} | "
        f"{c['tgc']} / {c['sgc']} | {d['tgc']:+} / {d['sgc']:+} |",
        "| colleagues' gpt-oss-120b (no memory → ReAct + ACE) | 39.9 / 21.4 | 54.8 / 35.7 | +14.9 / +14.3 |",
        "| ACE paper, gpt-oss-120b (ReAct → ACE offline, no GT) | 54.8 / 33.9 | 58.3 / 41.1 | +3.5 / +7.2 |",
        "",
        "**By difficulty (TGC / SGC).**",
        "",
        "| arm | Easy (57) | Medium (48) | Hard (63) |",
        "|---|---|---|---|",
    ]
    for arm in ("seed", "ace"):
        lines.append(f"| {arm} | " + " | ".join(f"{by(arm, l).get('tgc', '–')} / {by(arm, l).get('sgc', '–')}"
                                                for l in ("easy", "medium", "hard")) + " |")
    lines += [
        "",
        "**Cost.**",
        "",
        "| item | seed | ace |",
        "|---|---|---|",
        f"| target prompt tokens per task (mean) | {s['mean_prompt_tokens_per_task']:,} | {c['mean_prompt_tokens_per_task']:,} |",
        f"| target completion tokens per task (mean) | {s['mean_completion_tokens_per_task']:,} | {c['mean_completion_tokens_per_task']:,} |",
        f"| steps per task (mean) | {s['mean_steps']} | {c['mean_steps']} |",
        f"| step-cap hits / token-cap hits | {s['step_cap']} / {s['token_cap']} | {c['step_cap']} / {c['token_cap']} |",
        f"| context_exceeded | {s['context_exceeded']} | {c['context_exceeded']} |",
        f"| max prompt tokens | {s['max_prompt_tokens']:,} | {c['max_prompt_tokens']:,} |",
        f"| memory tokens per step | 0 | {fr['tokens']:,} |",
        f"| trials agreeing (both pass or both fail) | {s['trial_agreement']}% | {c['trial_agreement']}% |",
        f"| infra retries / missing cells | {s['infra_retries']} / {s['missing_infra']} | {c['infra_retries']} / {c['missing_infra']} |",
        f"| counted rollouts | 57 dev + 336 test | 90 train + 57 dev + 336 test |",
        "",
        f"Optimizer (ACE only): {tin / 1e6:.2f}M input / {tout / 1e6:.2f}M output non-cache-read tokens "
        f"(≈ ${tin / 1e6 * 2 + tout / 1e6 * 10:.2f} at proxy list prices $2 / $10 per Mtok; cap 10M); calls: "
        + ", ".join(f"{k} {v['calls']}" for k, v in sp.items()) + f"; responses cut at max_tokens: {trunc}; "
        f"Curator invalid-JSON (update skipped): {parse_err}. Agent tokens are on RITS (no price; reported as unknown).",
    ]
    if dev:
        lines += ["", f"Dev diagnostic (search-time, 57 dev tasks × 1 trial, not a result): seed {dev['seed']['tgc']}, "
                      f"ace {dev['ace']['tgc']} TGC; context_exceeded seed {dev['seed']['context_exceeded']}, ace "
                      f"{dev['ace']['context_exceeded']}."]
    lines += [
        "",
        "**What changed (the ACE artifact).** "
        f"pb_{fr['ace_step']:03d}: {fr['bullets']} bullets, {fr['chars']:,} characters, {fr['tokens']:,} tokens "
        f"(initial playbook: 8 bullets, 365 tokens; `identical_to_own_seed`: {fr['identical_to_own_seed']}). Bullets by "
        f"section: {secs}. Adaptation: {cur} of {len(rows)} steps curated (episode terminations: "
        + ", ".join(f"{k} {v}" for k, v in sorted(term.items())) + f"); {lint} bullets dropped by the per-bullet lint "
        f"(task data such as supervisor phone numbers), {len(dedup)} dedup runs, {capd} `cap_drop` bullets. "
        f"The playbook reached the cap at step {last_add} and did not change afterwards: from then on ACE's dedup at "
        f"threshold 0.90 found almost no merges, so the later steps' bullets were all `cap_drop`ped; the artifact is the "
        f"step-{last_add} playbook. With it, ACE's longest prompt in the test window was {c['max_prompt_tokens']:,} tokens "
        f"(limit 34,000; 0 context overflows); ACE's agent reads about {c['mean_prompt_tokens_per_task'] / max(1, s['mean_prompt_tokens_per_task']):.1f}× "
        f"the seed's prompt tokens per task. Training episodes passing during adaptation: "
        f"{sum(1 for r in rows if r.get('success'))} of {len(rows)} (search-time, not a result). Three example bullets:",
    ]
    lines += [f"- {b}" for b in example_bullets(pb)]
    ts = sum(scan.get(k, {}).get("test_id", 0) for k in ("llm_calls", "steps_files", "playbooks"))
    gs = sum(scan.get(k, {}).get("answer.json", 0) + scan.get(k, {}).get("ground_truth", 0) for k in ("llm_calls", "steps_files", "playbooks"))
    fsp = s["fs_probe_hits"] + c["fs_probe_hits"]
    lines += [
        "",
        f"**Isolation.** Scan of all {scan.get('scanned', {}).get('llm_calls', '?')} optimizer calls, "
        f"{scan.get('scanned', {}).get('steps_files', '?')} step files and {scan.get('scanned', {}).get('playbooks', '?')} "
        f"playbook snapshots: {ts} test ids, {gs} `answer.json` / `ground_truth` mentions; agent `fs_probe` hits: "
        f"adaptation and dev {sum(v['fs_probe_hits'] for ph in scan.get('fs_probe', {}).values() for v in ph.values())}, "
        f"final window {fsp}. Test root locked until the final window; the optimizer has no tools.",
        "",
        f"**Resume history.** {led['n']} ledger entries; aborts {led['kinds'].get('abort', 0)}, resumes "
        f"{led['kinds'].get('resume', 0)}, restores {led['kinds'].get('restore', 0)}, errors {led['kinds'].get('error', 0)}, "
        f"repairs {led['kinds'].get('repair', 0)} (5 code fixes before any counted rollout; 1 correcting the P7 scan "
        f"counts, a scanner false positive), heartbeats {led['kinds'].get('heartbeat', 0)}. The one error and resume: the "
        f"optimizer gateway's shared team budget ran out at the step-54 Reflector call (HTTP 429 `budget_exceeded`); the "
        f"run resumed about 8 h later from the saved episode, with no repeated episode or paid call. Wall time: "
        f"adaptation {rt.get('P4', 0)} h including that stop (about 4.4 h running), dev diagnostic {rt.get('P6', 0)} h, "
        f"final window {rt.get('P8', 0)} h.",
        "",
        "**Deviations** (plan §13; new in execution):",
        "- G1: the gateway rejects `temperature` for `aws/claude-sonnet-5-5`; Reflector, Curator and merge ran at the "
        "model default instead of ACE's 0.",
        "- G2: ACE's Reflector and Curator prompts verbatim end every response with `finish_reason: refusal` on this "
        "gateway; the phrase \"chain of thought / reasoning / thinking process,\" (4 lines) was removed from our copies; "
        "JSON fields unchanged.",
        "- As in ACE's no-GT code, an episode that hit the step cap (or ended on an LM error) gets no Reflector / Curator "
        "call; that step leaves the playbook unchanged.",
        "- From the base plan and the design (unchanged here): the common template; 50 steps; `max_completion_tokens` "
        "6,000 with trimming; chat completions via `hosted_vllm` with reasoning not resent; `M_cap` instead of the "
        "design's 30,000 tokens; 2 trials and one window instead of the design's panel; no test_challenge.",
        "",
        "**What the numbers cannot support:** one search seed, one method, no matched-budget comparison with other "
        "methods, no equivalence test (no TOST); the dev diagnostic and train pass rates are search-time numbers. No "
        "task text, ids, solutions or gold values are posted (AppWorld redistribution rule).",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    body = render()
    v = S.violations(body)
    if v:
        raise SystemExit(f"report refused by the content filter: {v}")
    P.atomic_write(OUT, body)
    print(body)
    if "--post" in sys.argv:
        if any('"post": "final"' in c for _, c in S.entries()):
            raise SystemExit("a final results comment was already posted (never post twice)")
        r = subprocess.run(["gh", "issue", "comment", "804", "-R", "skillberry-ai/cap-evolve", "--body-file", str(OUT)],
                           capture_output=True, text=True, check=True)
        url = r.stdout.strip().splitlines()[-1]
        S.append("posted", "P10", "report", f"Results comment posted on #804: {url}. Draft: `STATE/final/RESULTS.md`.",
                 done_through="P10/posted", next_unit="done", extra={"post": "final", "url": url},
                 artifacts=["STATE/final/RESULTS.md"], subject="P10 posted")
        print(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
