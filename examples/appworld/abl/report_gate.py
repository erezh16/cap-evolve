"""P9 of the gate arms (docs/ABLATIONS_GATE.md G7): RESULTS.md per gate arm, then the results post on its issue.

  python3 -I report_gate.py draft      # docs/ABLATION_STATUS_STATE/<arm>/RESULTS.md for abl_nogate, abl_naivegate
  python3 -I report_gate.py post       # posts each draft on its issue (#938, #939), keyed "results"

Built only from final_gate/analysis.json, the pushed state (progress, FREEZE, scan, same.json, manifest) and the
ledger's counts. Counts and aggregates only: no task id, task text or per-task outcome.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EX = HERE.parent
sys.path[:0] = [str(EX / "scripts"), str(EX / "common"), str(HERE)]
import awrest as P  # noqa: E402

_spec = importlib.util.spec_from_file_location("report_ce2", EX / "ce2" / "report_ce2.py")
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)
pct, ci = R.pct, R.ci

A = P.read_json(P.PUSHED / "final_gate" / "analysis.json", {}) or {}
A1 = P.read_json(P.PUSHED / "final" / "analysis.json", {}) or {}
M = P.manifest()
GATE = tuple(P.GATE_ARMS)
LABEL = {"abl_nogate": "no gate", "abl_naivegate": "naive gate (any gain)"}
RULE = {"abl_nogate": "`gate_k_se: -100000`: every scored candidate is kept and becomes the next parent, even if worse",
        "abl_naivegate": "`gate_k_se: 0`: a candidate is kept iff its mean paired gain Δ̄ is above 0 (no noise margin)"}
OTHER = {"abl_nogate": "abl_naivegate", "abl_naivegate": "abl_nogate"}


def main_table(c: str) -> str:
    a = A["arms"]
    rows = ["| arm | window | TGC | SGC | Δ TGC vs abl_ref [95% CI] | Δ TGC vs seed [95% CI] | missing |",
            "|---|---|---|---|---|---|---|"]
    for arm, win in (("seed", "first (reused)"), ("abl_ref", "first (reused)"), (c, "gate"), (OTHER[c], "gate")):
        vr, vs = A["vs_ref"].get(arm), A["vs_seed"].get(arm)
        b = "**" if arm == c else ""
        rows.append(f"| {b}{arm}{b} | {win} | {b}{pct(a[arm]['tgc'])}{b} | {pct(a[arm]['sgc'])} | "
                    f"{ci(vr, 'tgc') if vr else '—'} | {ci(vs, 'tgc') if vs else '—'} | {a[arm]['missing']} |")
    vr = A["vs_ref"][c]
    out = "\n".join(rows)
    out += (f"\n\nPrimary contrast `{c} − abl_ref` (cross-window): Δ TGC {ci(vr, 'tgc')}, Δ SGC {ci(vr, 'sgc')}; "
            f"bootstrap p {vr['p_raw']:.4f} raw, **{vr['p_holm']:.4f} Holm** (over the 2 gate contrasts). "
            f"Joint Holm over all 7 primary contrasts (5 first-wave + 2 gate; secondary): "
            f"{A['joint_holm_7']['p_holm'].get(c, float('nan')):.4f}.")
    for lab, d in A["pairs"].items():
        out += f"\n\nSecondary `{lab}` (in-window): Δ TGC {ci(d, 'tgc')}, Δ SGC {ci(d, 'sgc')}."
    return out


def first_window_context() -> str:
    a = A1.get("arms") or {}
    keep = [x for x in ("seed", "abl_ref", "abl_cc", "abl_prompt", "abl_tools", "abl_notrace", "abl_tracescore") if x in a]
    L = ["| arm (first window, 2026-10-27) | TGC | SGC |", "|---|---|---|"]
    L += [f"| {x} | {pct(a[x]['tgc'])} | {pct(a[x]['sgc'])} |" for x in keep]
    return "\n".join(L)


def diff_table() -> str:
    D = ["| arm | Easy (57) | Medium (48) | Hard (63) |", "|---|---|---|---|"]
    for arm, r in A["arms"].items():
        b = r["by_difficulty"]
        D.append(f"| {arm} | {pct(b['Easy']['tgc'])} | {pct(b['Medium']['tgc'])} | {pct(b['Hard']['tgc'])} |")
    return "\n".join(D)


def test_cost_table() -> str:
    T = ["| arm | prompt tok / ep | completion tok / ep | steps | s / ep | ctx-exceeded | infra retries | pass fraction | trials agree |",
         "|---|---|---|---|---|---|---|---|---|"]
    for arm, r in A["arms"].items():
        T.append(f"| {arm} | {r['prompt_tokens_per_task']:,.0f} | {r['completion_tokens_per_task']:,.0f} | "
                 f"{r['steps_per_task']:.1f} | {r['episode_seconds']:.0f} | {r['context_exceeded']} | {r['infra_retries']} | "
                 f"{r['pass_fraction']:.3f} | {100 * r['trials_agree_share']:.0f}% |")
    return "\n".join(T)


def iteration_table(c: str) -> str:
    pr = P.read_json(P.PUSHED / c / "progress.json", {}) or {}
    L = ["| iteration | val (fit) | parent | paired Δ̄ | SE | kept | `abl_ref`'s rule (Δ̄ > 0.2·SE) |",
         "|---|---|---|---|---|---|---|"]
    n_diff = 0
    for i, r in enumerate(pr.get("iterations") or [], 1):
        if "delta" not in r:
            L.append(f"| {i} | {r.get('val')} | {r.get('parent_val')} | — | — | {r.get('kind')} | — |")
            continue
        ref = r["delta"] > 0.2 * r["se"]
        n_diff += int(ref != bool(r.get("accept")))
        L.append(f"| {i} | {r['val']:.4f} | {r['parent_val']:.4f} | {r['delta']:+.4f} | {r['se']:.4f} | "
                 f"{'yes' if r.get('accept') else 'no'} | {'keep' if ref else 'reject'}"
                 f"{' **(differs)**' if ref != bool(r.get('accept')) else ''} |")
    return "\n".join(L) + f"\n\nDecisions that differ from `abl_ref`'s rule: **{n_diff} of {len(pr.get('iterations') or [])}**."


def search_rows(c: str) -> str:
    pr = P.read_json(P.PUSHED / c / "progress.json", {}) or {}
    fz = P.read_json(P.PUSHED / c / "artifact" / "FREEZE.json", {}) or {}
    s = (A.get("search") or {}).get(c) or {}
    o = s.get("optimizer") or {}
    return "\n".join([
        f"- iterations scored / accepted: {pr.get('iterations_done')} / {pr.get('accepted')}; counted rollouts "
        f"{pr.get('counted_rollouts')} of {P.BUDGET_ROLLOUTS}; metric calls {pr.get('metric_calls')} of 1,029",
        f"- champion `{fz.get('best_id')}` (the last accepted candidate): search score **{fz.get('champion_val'):.4f}**; "
        f"best score seen during the search {fz.get('best_val'):.4f} (fit metrics, train ∪ dev, selection-biased)",
        f"- optimizer: {o.get('calls')} sessions; **${o.get('proxy_usd')}** proxy (Sonnet 5.5 list price); "
        f"CLI-reported ${o.get('cli_reported_usd', 'see analysis.json')}",
        "- agent cost: n/a (RITS, unpriced); tokens per episode in the test table"])


def body(c: str) -> str:
    iso = (P.read_json(P.PUSHED / "isolation_scan.json", {}) or {}).get(c) or {}
    sess = (P.read_json(P.PUSHED / "isolation_scan.json", {}) or {}).get("_orchestrating_sessions") or {}
    same = (P.read_json(P.PUSHED / "abl" / "same.json", {}) or {}).get("arms", {}).get(c) or {}
    rst = P.read_json(P.AW_STATE / c / "reset_check.json", {}) or {}
    go = M.get("gate_order") or {}
    dc = A.get("drift_check") or {}
    return f"""**Final results — {P.METHOD_NAMES[c]} ({LABEL[c]}), AppWorld test_normal.**

### Setup
- plan: `docs/ABLATIONS.md` + addendum `docs/ABLATIONS_GATE.md` (branch `ablations`, erezh16/cap-evolve); reference arm `abl_ref` (#930)
- code under test: cap-evolve `main` `{P.CAPE_COMMIT[:7]}`, core and skills unmodified (D4); stock hill-climb `--focus all`, paired gate, `main`'s optimizer template plus one AppWorld facts section, 6 scored iterations
- this arm's only difference from `abl_ref`: {RULE[c]}, and the one sentence of the AppWorld facts section that states the acceptance rule (A-ABL-SAME: {'pass' if same.get('ok') else 'see same.json'})
- agent under test: `openai/gpt-oss-120b-a100` on RITS, reasoning medium, temperature 0, 50 steps; optimizer `aws/claude-sonnet-5-5` (every role), Claude Code CLI 2.1.270 in its sandbox
- search: 147 tasks (train ∪ dev), 1 trial, B = 882 counted rollouts, baseline = the shared seed run (cache)
- gate window (2026-10-28): 168 test_normal × the 2 gate arms × 2 trials = {go.get('cells', 672)} cells, one shuffled order (seed {go.get('seed')}), trial seeds 5000 + k as the first window, 12 slots; the seed's and `abl_ref`'s cells are reused from the first window (2026-10-27)

### Main result (test_normal, 168 tasks / 56 scenarios, 2 trials)
{main_table(c)}

95% CI: scenario-clustered paired bootstrap (56 clusters, 10,000 resamples); per-task pairs line up by (task, trial) across the two windows.

**Cross-window caveat (D16).** The gate arms ran about a day after the first window. Any change in RITS serving between the two windows is mixed into every contrast with `abl_ref` or the seed. Drift check: infra-retry and context-exceeded rates, first window {dc.get('first_window_rate')}, gate window {dc.get('gate_window_rate')}; flagged: {dc.get('flag') or 'none'}. The `{GATE[0]} − {GATE[1]}` contrast is in-window.

Context (first window, all arms):
{first_window_context()}

### TGC by difficulty
{diff_table()}

### Test phase: agent tokens and latency (per episode)
{test_cost_table()}

### Search phase: every iteration's decision
{iteration_table(c)}

{search_rows(c)}

### What changed (the frozen artifact)
{R.artifact_summary(c)}

### Isolation and reset
Scans: **{iso.get('test_id_hits')} test-id hits** in this arm's optimizer records, workdirs, transcripts and artifact; optimizer models only `aws/claude-sonnet-5-5`. {'**ISOLATION BREACH**' if iso.get('isolation_breach') else 'Not labelled an isolation breach.'} Reset check (§9.8): {'pass' if rst.get('ok') else 'see the ledger'}. Orchestrating sessions: {sess.get('test_id_hits')} test-id hits over {sess.get('files')} files, all in one command output of the previous orchestrating session on 2026-10-27 18:35 UTC, after the first window's results were posted (an id only, no task content or outcome; no optimizer can read those transcripts; ledger ABL-0796).

### Deviations
- the gate window runs only the two gate champions; `abl_ref` and the seed are reused from the first window (D16, user decision)
- the optimizer is told this arm's acceptance rule in the AppWorld facts section, and that core's fixed "How your edit is judged" paragraph (which describes a significance bar) does not apply (D17, user decision)
- 12 episode slots instead of 24 from 12:10 UTC on 2026-10-28 (ABL-0732, user request: another workload in the pod); this slows the run and does not change any result
- see the ledger `docs/{P.LEDGER.name}` (entries ABL-0716 onwards, kinds error, repair, decision)

### What the numbers cannot support
- One search seed per arm: each contrast mixes the gate with search randomness. A difference under about 8 TGC points is not resolved; a null result is a bound.
- Search scores are fit metrics (train = val, selection-biased); only the test_normal numbers are held out.
- Contrasts with `abl_ref` and the seed are cross-window (see above).

Full numbers: `docs/{P.PUSHED.name}/final_gate/analysis.json`.
"""


def main() -> int:
    import post
    for c in GATE:
        p = P.PUSHED / c / "RESULTS.md"
        if sys.argv[1] == "draft":
            P.atomic_write(p, body(c))
            print("drafted", p)
        else:
            print(c, post.post(c, "results", f"{P.METHOD_NAMES[c]} results", p.read_text()) or "(already posted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
