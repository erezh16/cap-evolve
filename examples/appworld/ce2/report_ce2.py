"""P9 of eval CE2: one results comment per arm (docs/EVAL_APPWORLD_CE2.md §16). Source ce2/env.sh first.

  python3 -I report_ce2.py draft     # writes docs/EVAL_APPWORLD_CE2_STATUS_STATE/<arm>/RESULTS.md
  python3 -I report_ce2.py post      # posts each draft once on the arm's issue (content filter in post.post)

Built only from final/analysis.json, the pushed state (progress, FREEZE, scan, acceptance, manifest) and the pushed
artifacts. Counts and aggregates only: no task id, task or supervisor text, trajectory or per-task outcome.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EX = HERE.parent
sys.path[:0] = [str(EX / "scripts"), str(EX / "common")]
import awrest as P  # noqa: E402
import evaluator as E  # noqa: E402

A = P.read_json(P.PUSHED / "final" / "analysis.json", {}) or {}
M = P.manifest()


def pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}"


def ci(v, k):
    return f"{pct(v['d_' + k])} [{pct(v['ci_' + k][0])}, {pct(v['ci_' + k][1])}]"


def main_table(c: str) -> str:
    a = A["arms"]
    if A.get("pairs"):    # CE3: one new arm; the seed, K = 1 and K = 2 are reused from CE2's window
        L = ["| arm | window | TGC | SGC | Δ TGC vs seed [95% CI] | Δ SGC vs seed [95% CI] | missing cells |",
             "|---|---|---|---|---|---|---|", f"| seed | CE2 (reused) | {pct(a['seed']['tgc'])} | {pct(a['seed']['sgc'])} | "
             f"— | — | {a['seed']['missing']} |"]
        for arm in [x for x in P.REUSED_WINDOW_ARMS if x != "seed"]:
            L.append(f"| {arm} | CE2 (reused) | {pct(a[arm]['tgc'])} | {pct(a[arm]['sgc'])} | (CE2 within-window: see #909, #910) | "
                     f"| {a[arm]['missing']} |")
        v = A["vs_seed"][c]
        L.append(f"| **{P.METHOD_NAMES[c]}** | **this (CE3)** | **{pct(a[c]['tgc'])}** | **{pct(a[c]['sgc'])}** | "
                 f"**{ci(v, 'tgc')}** (cross-window) | {ci(v, 'sgc')} (cross-window) | {a[c]['missing']} |")
        L += ["", "| comparison (cross-window) | Δ TGC [95% CI] | Δ SGC [95% CI] |", "|---|---|---|",
              f"| {c} − seed | {ci(v, 'tgc')} | {ci(v, 'sgc')} |"]
        L += [f"| {lab} | {ci(d, 'tgc')} | {ci(d, 'sgc')} |" for lab, d in A["pairs"].items()]
        L += ["", "**Cross-window.** The new arm ran in this window (2026-10-24); the seed and both CE2 champions are "
                  "CE2's window records (2026-10-23), reused by user decision. Identical artifacts drifted 4–6 TGC points "
                  "between windows in earlier runs, so these Δ include window drift and are weaker than within-window "
                  "comparisons."]
        return "\n".join(L)
    L = ["| arm | TGC | SGC | Δ TGC vs seed [95% CI] | Δ SGC vs seed [95% CI] | missing cells |",
         "|---|---|---|---|---|---|", f"| seed | {pct(a['seed']['tgc'])} | {pct(a['seed']['sgc'])} | — | — | "
         f"{a['seed']['missing']} |"]
    for arm in P.CANDIDATES:
        v = A["vs_seed"][arm]
        b = "**" if arm == c else ""
        L.append(f"| {b}{P.METHOD_NAMES[arm]}{b} | {b}{pct(a[arm]['tgc'])}{b} | {b}{pct(a[arm]['sgc'])}{b} | "
                 f"{b}{ci(v, 'tgc')}{b} | {ci(v, 'sgc')} | {a[arm]['missing']} |")
    k = A.get("k2_vs_k1")
    if k:
        L += ["", f"`ce2_k2 − ce2_k1`: Δ TGC {ci(k, 'tgc')}, Δ SGC {ci(k, 'sgc')}. One search seed per arm, so this "
                  "difference confounds the gate K with search randomness."]
    return "\n".join(L)


def diff_table() -> str:
    a = A["arms"]
    D = ["| arm | Easy (57) | Medium (48) | Hard (63) |", "|---|---|---|---|"]
    for arm in a:
        b = a[arm]["by_difficulty"]
        D.append(f"| {arm} | {pct(b['Easy']['tgc'])} | {pct(b['Medium']['tgc'])} | {pct(b['Hard']['tgc'])} |")
    return "\n".join(D)


def test_cost_table() -> str:
    T = ["| arm | prompt tok / ep (mean, p50, p90) | completion tok / ep (mean, p90) | steps | s / ep (mean, p50, p90) | "
         "step-cap | token-cap | ctx-exceeded | pass fraction | trials agree |", "|---|---|---|---|---|---|---|---|---|---|"]
    for arm in A["arms"]:
        r = A["arms"][arm]
        T.append(f"| {arm} | {r['prompt_tokens_per_task']:,.0f}, {r['prompt_tokens_p50']:,.0f}, {r['prompt_tokens_p90']:,.0f} | "
                 f"{r['completion_tokens_per_task']:,.0f}, {r['completion_tokens_p90']:,.0f} | {r['steps_per_task']:.1f} | "
                 f"{r['episode_seconds']:.0f}, {r['episode_seconds_p50']:.0f}, {r['episode_seconds_p90']:.0f} | "
                 f"{r['step_cap_hits']} | {r['token_cap_hits']} | {r['context_exceeded']} | {r['pass_fraction']:.3f} | "
                 f"{100 * r['trials_agree_share']:.0f}% |")
    return "\n".join(T)


def search_table(c: str) -> str:
    s = A["search"][c]
    o, ro = s["optimizer"], s["rollouts"]
    mu = s.get("model_usage_by_model") or {}
    sb = A.get("seed_baseline") or {}
    rows = [
        ("seed baseline (reused from REST P3, not re-run, not counted)",
         f"val = train ∪ dev {sb.get('union', {}).get('tgc')}; train {sb.get('train', {}).get('tgc')}; "
         f"dev {sb.get('dev', {}).get('tgc')} (147 records, 1 trial, seed 100)"),
        ("champion's search score", f"{s.get('best_search_score')} (fit metric: train = val = train ∪ dev, selection-biased)"),
        ("iterations scored / consumed / accepted", f"{s.get('iterations_done')} / {s.get('iterations_consumed')} / {s.get('accepted')}"),
        ("counted search rollouts", f"{ro['counted']} of B = 900 (cache hits {ro['cache_hits']}, lint-reject batches "
         f"{ro['lint_reject_batches']}, infra {ro['infra']})"),
        ("cap-evolve metric calls", f"{s.get('metric_calls')} of 1,029"),
        ("mean reward of counted rollouts", f"{ro['mean_reward_counted']} (search set; selection-biased)"),
        ("agent tokens / search episode", f"prompt mean {ro['prompt_tokens']['mean']:,.0f}, p50 {ro['prompt_tokens']['p50']:,.0f}, "
         f"p90 {ro['prompt_tokens']['p90']:,.0f}; completion mean {ro['completion_tokens']['mean']:,.0f}; max prompt "
         f"{ro['max_prompt_tokens']:,}"),
        ("search episode steps / seconds", f"steps mean {ro['steps']['mean']}; seconds mean {ro['episode_seconds']['mean']}, "
         f"p50 {ro['episode_seconds']['p50']}, p90 {ro['episode_seconds']['p90']}; step-cap {ro['step_cap_hits']}, "
         f"token-cap {ro['token_cap_hits']}, ctx-exceeded {ro['context_exceeded']}"),
        ("optimizer sessions", f"{o['calls']} ({o['errors']} errors); models in modelUsage: "
         + ", ".join(f"`{m}` ({v['results']} sessions)" for m, v in mu.items())),
        ("optimizer tokens (modelUsage, main loop + sub-agents)", f"{o['input_tokens']:,} input (non-cache-read, incl. cache "
         f"writes) / {o['output_tokens']:,} output / {o['cache_read_tokens']:,} cache-read / {o['cache_write_tokens']:,} "
         "cache-write"),
        ("optimizer cost (gateway)", f"**${o['proxy_usd']}** proxy at Sonnet 5.5 list price ($2 in, $10 out, $0.20 cache "
         f"read, $2.50 cache write per MTok); CLI-reported ${o.get('cli_reported_usd')}; cap-evolve's own tally "
         f"${s.get('capevolve_optimizer_usd')}"),
        ("optimizer time", f"{o['optimizer_seconds_total']:,} s in sessions (mean {o['call_seconds_mean']} s, p90 "
         f"{o['call_seconds_p90']} s)"),
        ("search wall time", f"{ro['search_wall'][0]} → {ro['search_wall'][1]}" if ro.get("search_wall") else "n/a"),
        ("dev diagnostic (57 dev, 1 trial; dev ⊂ val)", f"{A.get('dev_diagnostic_tgc', {}).get(c)} (seed "
         f"{A.get('dev_diagnostic_tgc', {}).get('seed')})"),
        ("agent cost (RITS)", "n/a (unpriced); tokens above"),
    ]
    return "\n".join(["| | value |", "|---|---|"] + [f"| {k} | {v} |" for k, v in rows])


def iteration_table(c: str) -> str:
    rows = A["search"][c].get("iterations") or []
    pr = P.read_json(P.PUSHED / c / "progress.json", {}) or {}
    rows = rows or pr.get("iterations") or []
    k = P.K_SE[c]
    H = ["| iter | val (fit metric) | parent val | paired Δ̄ | SE | K·SE (K = %d) | verdict |%s" % (
        k, " would pass at K = 1 |" if c == "ce2_k2" else ""), "|---|---|---|---|---|---|---|" + ("---|" if c == "ce2_k2" else "")]
    for i, r in enumerate(rows, 1):
        if r.get("indecisive"):
            H.append(f"| {i} | — | — | — | — | — | evaluation error (indecisive) |" + (" — |" if c == "ce2_k2" else ""))
            continue
        H.append(f"| {i} | {r.get('val'):.4f} | {r.get('parent_val'):.4f} | {r.get('delta', 0):+.4f} | {r.get('se', 0):.4f} | "
                 f"{r.get('bar', 0):.4f} | {'**accept**' if r.get('accept') else 'reject'} |"
                 + (f" {'yes' if r.get('would_pass_k1') else 'no'} |" if c == "ce2_k2" else ""))
    return "\n".join(H)


def artifact_summary(c: str) -> str:
    seed = E.read_surfaces(P.SEED_CAP)
    art = P.PUSHED / c / "artifact"
    s = E.read_surfaces(art)
    fz = P.read_json(art / "FREEZE.json", {}) or {}
    out = []
    for k in ("policy/instructions.txt", "tools/helpers.py", "tools/api_notes.json"):
        v, b = s.get(k, ""), seed.get(k, "")
        if v == b:
            out.append(f"- `{k}`: unchanged from the seed")
            continue
        extra = ""
        if k == "policy/instructions.txt":
            extra = f", {E.memory_tokens(v):,} tokens (seed {E.memory_tokens(b):,})"
        if k == "tools/helpers.py":
            extra = (f", {sum(1 for n in ast.parse(v).body if isinstance(n, ast.FunctionDef))} helper functions, "
                     f"{len(v.splitlines())} lines")
        if k == "tools/api_notes.json":
            extra = f", {len(json.loads(v or '{}'))} notes, {sum(len(x) for x in json.loads(v or '{}').values()):,} chars"
        out.append(f"- `{k}`: changed ({len(b):,} → {len(v):,} chars{extra})")
    out.append(f"- champion `{fz.get('best_id')}`{' (INERT: nothing accepted; frozen as the seed)' if fz.get('inert') else ''}; "
               f"tree sha256 `{(fz.get('tree_sha256') or '')[:16]}` = the run's own candidate; lint-clean; published in "
               f"`docs/{P.PUSHED.name}/{c}/artifact/` on branch `eval-ce2`")
    return "\n".join(out)


def evidence(c: str) -> str:
    fz = P.read_json(P.PUSHED / c / "artifact" / "FREEZE.json", {}) or {}
    imp = fz.get("imp") or {}
    sc = (P.read_json(P.PUSHED / "isolation_scan.json", {}) or {}).get(c, {}).get("ce2") or {}
    ok = lambda k: "pass" if (imp.get(k) or {}).get("ok") else "FAIL (see FREEZE.json)"  # noqa: E731
    ks = (imp.get("4_effective_k_se") or {}).get("k_se_values")
    return (f"- J3 code pin: core imported from the `{P.CAPE_COMMIT[:7]}` worktree, clean: {ok('1_code_pin')}\n"
            f"- J2/J4 skills pin: `CAPEVOLVE_SKILLS_DIR` resolves to the pinned skills, not `~/.claude/skills`: {ok('2_skills_pin')}\n"
            f"- J5 `gate_k_se: {P.K_SE[c]}` in the spec and the run_config event: {ok('3_spec_k_se')} / {ok('3_run_config')}; "
            f"`--k-se {', '.join(ks or ['?'])}` on the hill-climb command line: {ok('4_effective_k_se')}\n"
            f"- J1 Improvement 2's instructions (objective score, PREPARATION, Strategies for constructing edits incl. SOFT / "
            f"JUDGEMENT CALLS, AppWorld facts) in every iteration's `INSTRUCTIONS.md` "
            f"({(imp.get('5_instructions') or {}).get('iterations')} iterations), no old-template marker: {ok('5_instructions')}\n"
            f"- J2 guidance SKILL.md files equal the pinned skills (diagnose: head lines): {ok('6_guidance')}\n"
            f"- J3 the pinned hill-climb `run.py` ran (sha256 `{((imp.get('7_hill_climb_script') or {}).get('sha256') or '')[:8]}`): "
            f"{ok('7_hill_climb_script')}\n"
            f"- optimizer models seen in modelUsage after the search: {sorted(sc.get('model_usage_keys') or {})}; other models: "
            f"{sc.get('other_models')}\n"
            "- `instructions.diff` (pinned template vs the run's template) shows only the inserted AppWorld section; the two "
            "arms' specs differ only in `gate_k_se` and their instructions are identical (A-CE2-SAME)\n")


def body(c: str) -> str:
    iso = A["isolation"].get(c) or {}
    sess = (P.read_json(P.PUSHED / "isolation_scan.json", {}) or {}).get("_orchestrating_sessions") or {}
    k = P.K_SE[c]
    fo = M.get("final_order") or {}
    ce3 = P.LEDGER_ID == "CE3"
    other = ("CE2's arms (K = 1, K = 2; #909, #910) are identical except K and the money caps" if ce3
             else "the other CE2 arm is identical except K")
    caps = ("**no money or token cap** (CE3 plan §2: no `optimizer_usd_per_iter`, `max_optimizer_usd` 0 = off, no "
            "token cap; spend recorded exactly)" if ce3 else
            "`optimizer_usd_per_iter` 40 and `max_optimizer_usd` 300 (raised from 15 / 120 by user decision, CE2-0022)")
    window = (f"final window: **this arm only**, 168 test_normal × 2 trials (seeds 5000 + k) = {fo.get('cells', 336):,} cells "
              f"(order seed {fo.get('seed')}), 24 global slots. The seed, K = 1 and K = 2 test records are **reused from CE2's "
              "window** (2026-10-23, 1,008 cells, 0 missing), by user decision: every comparison below is cross-window"
              if ce3 else
              f"final window: 168 test_normal × 3 arms (seed, K = 1, K = 2) × 2 trials (seeds 5000 + k) = "
              f"{fo.get('cells', 1008):,} cells, one shuffled order (seed {fo.get('seed')}), 24 global slots; all three arms "
              "run fresh in this window")
    return f"""**Final results — {P.METHOD_NAMES[c]} (gate K = {k}) vs the seed agent, AppWorld test_normal.**

### Setup
- method: cap-evolve "Improvement 2", commit `{P.CAPE_COMMIT[:7]}` (= `8194578` + two Self-check wording fixes in the optimizer template, user decision, ledger CE2-0012; core and skills byte-identical to `8194578`), stock hill-climb `--focus all`, deterministic orchestration, `capabilities: [system-prompt, tools]`, paired gate with **`gate_k_se: {k}`**; {other}
- agent under test (all arms): `openai/gpt-oss-120b-a100` on RITS, `hosted_vllm/` route, reasoning medium, temperature 0, 50 steps, 6,000 max completion tokens per call, 100K completion tokens per task, the official simplified ReAct agent at AppWorld `42b5bcf`
- optimizer (main loop and every sub-agent): `aws/claude-sonnet-5-5` via the gateway, Claude Code CLI 2.1.270 in Claude Code's sandbox (landrun + proot), `--setting-sources ''`, no temperature/seed sent; gold-free feedback (reward, failed requirement texts, collateral damage, steps, termination)
- search: train = val = official train ∪ dev (147), 1 trial per task (seed 100), 6 scored iterations, B = 900 counted rollouts, `max_metric_calls` 1029, {caps}; seed baseline **reused** from REST's P3 run (147 records, verified by hash and code identity, not re-run)
- {window}

### Main result (test_normal, 168 tasks / 56 scenarios, 2 trials)
{main_table(c)}

95% CI: scenario-clustered paired bootstrap (56 clusters, 10,000 resamples), unadjusted. TGC = mean over tasks of the mean over trials; SGC = scenario passes in a trial iff all its tasks pass.

### TGC by difficulty
{diff_table()}

### Test phase: agent cost, tokens and latency (final window, per episode)
{test_cost_table()}

Agent cost: n/a (RITS is unpriced). Final window wall: {' → '.join(A.get('window_wall') or ['n/a'])}.

### Train (search) phase: per-iteration verdicts
{iteration_table(c)}

### Train (search) phase: cost, tokens, latency, budget
{search_table(c)}

### What changed (the frozen artifact)
{artifact_summary(c)}

### Evidence that the evaluated system is Improvement 2 with K = {k}
{evidence(c)}
### Isolation
Post-search and full scans: **{iso.get('test_id_hits')} test-id hits** in every optimizer-side record, workdir, transcript and the frozen artifact of this arm; {sess.get('test_id_hits')} in the orchestrating sessions' own transcripts ({sess.get('files')} files). {'**ISOLATION BREACH**' if iso.get('breach') else 'Not labelled an isolation breach.'} Literal-string counts per location are in `docs/{P.PUSHED.name}/isolation_scan.json`.

### Deviations
- candidate pin `{P.CAPE_COMMIT[:7]}` instead of the plan's `8194578` (two wording fixes in the template's Self-check, user decision; CE2-0012);
- the seed baseline is REST's P3 run, reused (plan D5); the released-solution scoring probe was not repeated (plan §17);
{"- no money or token cap, and the window ran this arm only with the seed, K = 1 and K = 2 records reused from CE2 (CE3 plan §2, user decisions 2026-10-24);" + chr(10) if ce3 else ""}- other incidents and repairs are in the ledger (`docs/{P.LEDGER.name}`), none affecting a counted rollout unless stated there.

### What the numbers cannot support
- Artifact-level statements only: one search run of this configuration, not the method in general.
{"- Every comparison with the seed, K = 1 or K = 2 is cross-window (their records are CE2's window), so it includes window drift; and each K had one search seed, so K is confounded with search randomness." if ce3 else "- `ce2_k2 − ce2_k1` confounds the gate K with search randomness (one search seed per arm)."}
- Search scores are fit metrics (train = val, selection-biased); only the test_normal numbers above are held out.
- REST's Improvement 1 numbers come from another window (identical artifacts drifted 4–6 TGC points between windows) and are not compared here.
- No multiplicity correction.

Full tables: `docs/{P.PUSHED.name}/final/RESULTS.md` and `analysis.json`; ledger: `docs/{P.LEDGER.name}`.
"""


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
