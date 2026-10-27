"""P9 of the ablations: one results comment per arm (docs/ABLATIONS.md §15). Source abl/env.sh first.

  python3 -I report_abl.py draft     # writes docs/ABLATION_STATUS_STATE/<arm>/RESULTS.md
  python3 -I report_abl.py post      # posts each draft once on the arm's issue (content filter in post.post)

Built only from final/analysis.json, the pushed state (progress, FREEZE, scan, same.json, manifest) and the pushed
artifacts. Counts and aggregates only: no task id, task or supervisor text, trajectory or per-task outcome. The
table helpers (difficulty, test cost, artifact sizes) are CE2's report_ce2.py, loaded by path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EX = HERE.parent
sys.path[:0] = [str(HERE), str(EX / "scripts"), str(EX / "common")]
import awrest as P  # noqa: E402

_spec = importlib.util.spec_from_file_location("report_ce2", EX / "ce2" / "report_ce2.py")
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)
A, M, pct, ci = R.A, R.M, R.pct, R.ci

LABEL = {"abl_ref": "reference", "abl_cc": "plain Claude Code: no cap-evolve loop, instructions or gate",
         "abl_prompt": "prompt only", "abl_tools": "tools only", "abl_notrace": "no traces (evaluation feedback only)",
         "abl_tracescore": "traces + score only (no evaluation feedback)",
         "abl_cc_best": "abl_cc's best-evaluated candidate (secondary, ABL-0485)"}
ACTIVATE = {
    "abl_ref": "`capabilities: [system-prompt, tools]`, `protected_paths: [default, \"memory/*\"]`, `AW_ABL_FEEDBACK=full`",
    "abl_prompt": "`capabilities: [system-prompt]`, `protected_paths: [default, \"memory/*\", \"tools/*\"]`, `AW_ABL_FEEDBACK=full`",
    "abl_tools": "`capabilities: [tools]`, `protected_paths: [default, \"memory/*\", \"policy/*\"]`, `AW_ABL_FEEDBACK=full`, "
                 "`AW_ABL_TOOLS_LINT=1`",
    "abl_notrace": "as the reference, plus `AW_ABL_FEEDBACK=eval_only`",
    "abl_tracescore": "as the reference, plus `AW_ABL_FEEDBACK=trace_score`",
    "abl_cc": "one `claude -p` session with the 3-line prompt, `--max-turns 1200`, an empty `CLAUDE_CONFIG_DIR`, the same "
              "sandbox shim, the eval daemon `abl/cc/evald.py` (B = 882, reference feedback content)"}


def main_table(c: str) -> str:
    a = A["arms"]
    rows = ["| arm | TGC | SGC | Δ TGC vs abl_ref [95% CI] | Δ TGC vs seed [95% CI] | missing |", "|---|---|---|---|---|---|"]
    extra = tuple(x for x in getattr(P, "EXTRA_WINDOW_ARMS", ()) if c == "abl_cc" and x in a)
    for arm in (("seed", "abl_ref", c) + extra) if c != "abl_ref" else ("seed", "abl_ref"):
        vr = (A.get("vs_ref") or {}).get(arm)
        vs = (A.get("vs_seed") or {}).get(arm)
        b = "**" if arm == c else ""
        rows.append(f"| {b}{arm}{b} | {b}{pct(a[arm]['tgc'])}{b} | {pct(a[arm]['sgc'])} | "
                    f"{ci(vr, 'tgc') if vr else '—'} | {ci(vs, 'tgc') if vs else '—'} | {a[arm]['missing']} |")
    out = "\n".join(rows)
    vr = (A.get("vs_ref") or {}).get(c)
    if vr:
        out += (f"\n\nPrimary contrast `{c} − abl_ref`: Δ TGC {ci(vr, 'tgc')}, Δ SGC {ci(vr, 'sgc')}; bootstrap p "
                f"{vr['p_raw']:.4f} raw, **{vr['p_holm']:.4f} Holm** (over the 5 primary contrasts).")
    for lab, d in (A.get("pairs") or {}).items():
        if c in lab.split(" − "):
            out += f"\n\nSecondary `{lab}`: Δ TGC {ci(d, 'tgc')}, Δ SGC {ci(d, 'sgc')}."
    return out


def all_arms_table() -> str:
    a = A["arms"]
    L = ["| arm | TGC | SGC | Δ TGC vs abl_ref | p Holm |", "|---|---|---|---|---|"]
    for arm in a:
        vr = (A.get("vs_ref") or {}).get(arm)
        holm = f"{vr['p_holm']:.4f}" if vr else "—"
        L.append(f"| {arm} | {pct(a[arm]['tgc'])} | {pct(a[arm]['sgc'])} | {ci(vr, 'tgc') if vr else '—'} | {holm} |")
    return "\n".join(L)


def search_rows(c: str) -> str:
    pr = P.read_json(P.PUSHED / c / "progress.json", {}) or {}
    s = (A.get("search") or {}).get(c) or {}
    o = s.get("optimizer") or pr.get("optimizer") or {}
    ro = s.get("rollouts") or {}
    sb = A.get("seed_baseline") or {}
    if c == "abl_cc":
        fz = P.read_json(P.PUSHED / c / "artifact" / "FREEZE.json", {}) or {}
        L = [f"- evaluations run: {pr.get('evaluations_done')} (requests {pr.get('evaluation_requests')}, refused "
             f"{pr.get('refused')}, lint rejects {pr.get('lint_rejects')}); rollouts used {pr.get('counted_rollouts')} of "
             f"{P.BUDGET_ROLLOUTS}; cache hits {pr.get('cache_hits')}",
             "- per evaluation (mean val = train ∪ dev, fit metric): " + ", ".join(
                 f"{e.get('mean_reward')}" for e in pr.get("evaluations") or []),
             f"- champion (the workdir when the session ended): evaluated {fz.get('champion_evaluated')}, val "
             f"{fz.get('champion_val')}; best evaluated {fz.get('best_evaluated')} (secondary artifact, not in the window)",
             f"- session: {fz.get('sessions')} session(s), stop reason `{fz.get('session_stop')}` (turn cap 1,200)"
             + (f"; deviation: {fz.get('deviation')}" if fz.get("deviation") else "")]
    else:
        L = [f"- iterations scored / consumed / accepted: {pr.get('iterations_done')} / {pr.get('iterations_consumed')} / "
             f"{pr.get('accepted')}; voided steps (sealed surface changed): {pr.get('voided_steps')}; lint rejects "
             f"{pr.get('lint_rejects')}",
             f"- counted rollouts {pr.get('counted_rollouts')} of {P.BUDGET_ROLLOUTS}; metric calls {pr.get('metric_calls')} "
             "of 1,029; cache hits " + str(pr.get("cache_hits")),
             f"- champion search score {pr.get('best_search_score')} (fit metric, selection-biased)"]
    L += [f"- seed baseline (shared P3, not counted): val {sb.get('union', {}).get('tgc')}",
          f"- optimizer: {o.get('calls')} sessions; {o.get('prompt_tokens', o.get('input_tokens'))} input / "
          f"{o.get('completion_tokens', o.get('output_tokens'))} output / {o.get('cache_read', o.get('cache_read_tokens'))} "
          f"cache-read tokens; **${o.get('proxy_usd')}** proxy (Sonnet 5.5 list price); CLI-reported "
          f"${o.get('cli_reported_usd', 'see analysis.json')}",
          "- agent cost: n/a (RITS, unpriced); tokens per episode in the test table" + (
              f"; search episodes: prompt mean {ro['prompt_tokens']['mean']:,.0f}" if ro.get("prompt_tokens") else "")]
    return "\n".join(L)


def body(c: str) -> str:
    iso = (A.get("isolation") or {}).get(c) or {}
    sess = (P.read_json(P.PUSHED / "isolation_scan.json", {}) or {}).get("_orchestrating_sessions") or {}
    fo = M.get("final_order") or {}
    same = (P.read_json(P.PUSHED / "abl" / "same.json", {}) or {}).get("arms", {}).get(c)
    rst = P.read_json(P.AW_STATE / c / "reset_check.json", {}) or {}
    return f"""**Final results — {P.METHOD_NAMES[c]} ({LABEL[c]}), AppWorld test_normal.**

### Setup
- code under test: cap-evolve `main` `{P.CAPE_COMMIT[:7]}`, core and skills unmodified (D4); stock hill-climb `--focus all`, paired gate `gate_k_se: 0.2` explicit, `main`'s optimizer template plus one AppWorld facts section, 6 scored iterations (cap-evolve arms)
- this arm: {ACTIVATE[c]}
- agent under test (all arms): `openai/gpt-oss-120b-a100` on RITS, `hosted_vllm/`, reasoning medium, temperature 0, 50 steps, AppWorld `42b5bcf` simplified ReAct agent
- optimizer (every role, every arm): `aws/claude-sonnet-5-5` via the gateway, Claude Code CLI 2.1.270 in Claude Code's sandbox, `--setting-sources ''`
- search: train = val = train ∪ dev (147), 1 trial (seed 100), B = 882 counted rollouts, no money or token cap (D12); the seed baseline is one shared P3 run (147, not counted)
- final window: 168 test_normal × 7 arms × 2 trials (seeds 5000 + k) = {fo.get('cells', 2352):,} cells, one shuffled order (seed {fo.get('seed')}), 24 slots
{"- A-ABL-SAME vs abl_ref: " + ("pass" if same and same.get("ok") else "see same.json") if c != "abl_ref" else ""}

### Main result (test_normal, 168 tasks / 56 scenarios, 2 trials)
{main_table(c)}

All seven arms:
{all_arms_table()}

95% CI: scenario-clustered paired bootstrap (56 clusters, 10,000 resamples).

### TGC by difficulty
{R.diff_table()}

### Test phase: agent tokens and latency (per episode)
{R.test_cost_table()}

### Search phase
{search_rows(c)}

### What changed (the frozen artifact)
{R.artifact_summary(c) if c != "abl_cc" else _cc_artifact()}

### Isolation and reset
Scans: **{iso.get('test_id_hits')} test-id hits** in this arm's optimizer records, workdirs, transcripts and artifact; {sess.get('test_id_hits')} in the orchestrating sessions' transcripts ({sess.get('files')} files). {'**ISOLATION BREACH**' if iso.get('breach') else 'Not labelled an isolation breach.'} Reset check (§9.8): {'pass' if rst.get('ok') else 'see the ledger'}.

### Deviations
- see the ledger `docs/{P.LEDGER.name}` (entries of kind error, repair, decision); none affects a counted rollout unless stated there.

### What the numbers cannot support
- Artifact-level statements only: one search seed per arm, so each contrast confounds the ablated factor with search randomness. Earlier windows measured an SE of about 3 to 4 TGC points per arm, so a difference under about 8 TGC points is not resolved; a null result is a bound ("less than about X").
- Search scores are fit metrics (train = val, selection-biased); only the test_normal numbers are held out.
- No test number of an earlier evaluation is compared here (other windows).

Full tables: `docs/{P.PUSHED.name}/final/RESULTS.md` and `analysis.json`.
"""


def _cc_artifact() -> str:
    fz = P.read_json(P.PUSHED / "abl_cc" / "artifact" / "FREEZE.json", {}) or {}
    s = R.artifact_summary("abl_cc").splitlines()[:-1]
    return "\n".join(s + [f"- champion tree sha256 `{(fz.get('tree_sha256') or '')[:16]}`"
                          f"{' (INERT: identical to the seed)' if fz.get('inert') else ''}; workdir commits "
                          f"{fz.get('workdir_commits')}; published in `docs/{P.PUSHED.name}/abl_cc/artifact/`"])


def main() -> int:
    import post
    for c in P.CANDIDATES:
        p = P.PUSHED / c / "RESULTS.md"
        if sys.argv[1] == "draft":
            P.atomic_write(p, body(c))
            print("drafted", p)
        else:
            print(c, post.post(c, "results", f"{P.METHOD_NAMES[c]} results", p.read_text()) or "(already posted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
