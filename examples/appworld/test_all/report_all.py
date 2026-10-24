"""P5 (docs/TEST_ALL.md §12.3): the combined RESULTS.md and one results comment per arm, from final/analysis.json only.

  . examples/appworld/test_all/env.sh && python3 -I examples/appworld/test_all/report_all.py      # drafts only
  ... report_all.py --post                                                                       # post the 13 comments
  ... report_all.py --pointers                                                                   # courtesy pointers (§12.3)

Drafts go to docs/TEST_ALL_STATE/<arm>/RESULTS.md. Aggregates only; every body passes the content filter in post.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "scripts"))
import awrest as P  # noqa: E402

RESULTS_URL = "https://github.com/erezh16/cap-evolve/blob/test-all/docs/TEST_ALL_STATE/final/RESULTS.md"
LIMITS = ("**What these numbers cannot support.** Each champion came from **one** search with one search seed; the "
          "methods differ in the surfaces they may change, in search budget and in their own settings; and this is a "
          "**single** test window (window-to-window drift of identical artifacts was 4 to 6 TGC points in earlier "
          "evaluations; here the `harnesslens − seed` noise check measures the within-window part). So the ranking "
          "compares 13 **artifacts** under one test condition. It does not rank the methods in general.")
DEVIATIONS = ("**Deviations and disclosures.** ACE's playbook (55,513 chars) is over the shared lint's 30,000-char "
              "memory limit and was scored as frozen (D6). Surfaces: §3's column is 'surfaces searched'; the measured "
              "'surfaces changed vs the seed' differ for gepa (P only), skillopt, wikiskill and evoskill (M only) (D10). "
              "The executing session's deny rules were merged into the base worktree's settings, since the session ran "
              "from there (D11). Other deviations, if any, are in the ledger (`docs/TEST_ALL_STATUS.md`).")


def pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}"


def ci(c):
    return f"[{pct(c[0])}, {pct(c[1])}]"


def setup(res: dict) -> str:
    m = res.get("manifest", {})
    rows = ["| arm | method (source evaluation) | surfaces searched | surfaces changed vs seed | hash rule | hash | source |",
            "|---|---|---|---|---|---|---|"]
    for a in P.ARMS:
        v = res["artifacts"].get(a, {})
        rows.append(f"| `{a}` | {P.SOURCE_EVAL[a]} | {v.get('surfaces_searched')} | {v.get('surfaces_changed')} | "
                    f"{v.get('rule')} | `{(v.get('computed') or '')[:16]}…` | {v.get('source')} |")
    fo = m.get("final_order") or {}
    return ("**Setup.** AppWorld `42b5bcf`, `test_normal` (168 tasks, 56 scenarios; Easy 57 / Medium 48 / Hard 63); "
            f"agent `{P.AGENT_MODEL}` on RITS (reasoning medium, temperature 0, the official simplified ReAct code agent, "
            "50 steps, 100K completion tokens per task, 30-min wall cap); no optimizer. One shuffled window of "
            f"{res['cells']:,} cells (13 arms × 168 × {res['trials']} trials, trial seeds {P.FINAL_SEED_BASE}+k, order seed "
            f"{fo.get('seed')}, order sha256 `{(fo.get('sha256') or '')[:16]}…`). Code: branch `test-all`.\n\n"
            + "\n".join(rows))


def main_table(res: dict) -> str:
    L = ["| rank | arm | TGC [95% CI] | SGC | Δ TGC vs seed [95% CI] | Δ SGC vs seed [95% CI] | Holm (78 pairs) | not separable from top | missing |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in res["ranking"]:
        a = r["arm"]
        x, v = res["arms"][a], res["vs_seed"].get(a)
        L.append(f"| {r['rank']} | `{a}` | {pct(x['tgc'])} {ci(r['ci_tgc'])} | {pct(x['sgc'])} | "
                 + (f"{pct(v['d_tgc'])} {ci(v['ci_tgc'])} | {pct(v['d_sgc'])} {ci(v['ci_sgc'])} | "
                    f"{'yes' if v['holm_significant_tgc'] else 'no'}" if v else "— | — | —")
                 + f" | {'yes' if r['not_separable_from_top'] else 'no'} | {x['missing']} |")
    return "\n".join(L)


def difficulty_table(res: dict) -> str:
    L = ["| arm | Easy TGC | Medium TGC | Hard TGC | Easy SGC | Medium SGC | Hard SGC |", "|---|---|---|---|---|---|---|"]
    for a in P.ARMS:
        b = res["arms"][a]["by_difficulty"]
        L.append(f"| `{a}` | " + " | ".join(pct(b[n]["tgc"]) for n in ("Easy", "Medium", "Hard")) + " | "
                 + " | ".join(pct(b[n]["sgc"]) for n in ("Easy", "Medium", "Hard")) + " |")
    return "\n".join(L)


def cost_table(res: dict) -> str:
    L = ["| arm | prompt tok/ep (mean / p50 / p90) | completion tok/ep (mean / p50 / p90) | steps (mean) | s/ep (mean / p50 / p90) | max prompt | step-cap | token-cap | ctx-exceeded | collateral | infra retries | pass fraction |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    f = lambda d: f"{d['mean']:,.0f} / {d['p50']:,.0f} / {d['p90']:,.0f}" if d["mean"] is not None else "n/a"  # noqa: E731
    for a in P.ARMS:
        x = res["arms"][a]
        L.append(f"| `{a}` | {f(x['prompt_tokens'])} | {f(x['completion_tokens'])} | {x['steps']['mean']:.1f} | "
                 f"{f(x['episode_seconds'])} | {x['max_prompt_tokens']:,} | {x['step_cap_hits']} | {x['token_cap_hits']} | "
                 f"{x['context_exceeded']} | {x['collateral_damage']} | {x['infra_retries']} | {pct(x['pass_fraction'])} |")
    return "\n".join(L) + "\n\nAgent cost: n/a (RITS is unpriced); agent tokens above stand in for it. No optimizer was called."


def stoch_table(res: dict) -> str:
    K = res["trials"]
    L = ["| arm | tasks passing 0/1/2/3/4/5 of 5 | stable | flaky | pass@1 … pass@5 | pass^1 … pass^5 | within-task var share |",
         "|---|---|---|---|---|---|---|"]
    for a in P.ARMS:
        s = res["stochastic"][a]
        L.append(f"| `{a}` | {'/'.join(str(s['pass_count_distribution'][str(i)]) for i in range(K + 1))} | "
                 f"{pct(s['stable_share'])} | {pct(s['flaky_share'])} | "
                 f"{' / '.join(pct(s['pass_at_k'][str(k)]) for k in range(1, K + 1))} | "
                 f"{' / '.join(pct(s['pass_hat_k'][str(k)]) for k in range(1, K + 1))} | "
                 f"{pct(s['within_share_of_variance'])} |")
    return "\n".join(L)


def sensitivity_table(res: dict) -> str:
    K = res["trials"]
    L = ["| arm | " + " | ".join(f"TGC, first {n} | Δ vs seed, first {n} [95% CI]" for n in range(1, K + 1)) + " |",
         "|---|" + "---|" * (2 * K)]
    for a in P.ARMS:
        cells = []
        for n in range(1, K + 1):
            r = res["trial_sensitivity"][str(n)]
            v = r["vs_seed"].get(a)
            cells += [pct(r["tgc"][a]), f"{pct(v['d_tgc'])} {ci(v['ci_tgc'])}" if v else "—"]
        L.append(f"| `{a}` | " + " | ".join(cells) + " |")
    return "\n".join(L) + "\n\n(The trial-count CIs use 2,000 bootstrap resamples; the main tables use 10,000.)"


def pair_matrix(res: dict) -> str:
    L = ["| pair | Δ TGC [95% CI] | Δ SGC [95% CI] | bootstrap p | Holm |", "|---|---|---|---|---|"]
    for k, v in res["pairs"].items():
        L.append(f"| {k} | {pct(v['d_tgc'])} {ci(v['ci_tgc'])} | {pct(v['d_sgc'])} {ci(v['ci_sgc'])} | "
                 f"{v['p_tgc']:.4f} | {'yes' if v['holm_significant_tgc'] else 'no'} |")
    return "\n".join(L)


def earlier_table(res: dict) -> str:
    L = ["| arm | this window TGC (5 trials) | other window TGC (2 trials) | other window |", "|---|---|---|---|"]
    for a in P.ARMS:
        e = res["earlier_windows"].get(a, {})
        L.append(f"| `{a}` | {pct(res['arms'][a]['tgc'])} | {pct(e.get('tgc'))} | {e.get('label', '')} |")
    s = res["earlier_windows"].get("_seed_in_other_windows", {})
    return ("\n".join(L) + "\n\nContext only, never a paired comparison. The seed's TGC in the other windows: "
            + ", ".join(f"{k} {pct(v)}" for k, v in s.items()) + ".")


def noise(res: dict) -> str:
    v = res["noise_check"]["harnesslens − seed"]
    return (f"**Window noise check (`harnesslens − seed`, two byte-identical artifacts):** Δ TGC {pct(v['d_tgc'])} "
            f"{ci(v['ci_tgc'])}, Δ SGC {pct(v['d_sgc'])} {ci(v['ci_sgc'])}.")


def flaky_summary(res: dict) -> str:
    f = res["flakiness_across_arms"]
    return ("**Flakiness across arms.** Pearson correlation of TGC with flaky share over the 13 arms: "
            f"{f['pearson_tgc_vs_flaky_share']:.2f}. Mean flaky share by surface changed: "
            + ", ".join(f"{k} {pct(v)} (n={f['n_arms_by_surface_changed'][k]})"
                        for k, v in f["mean_flaky_share_by_surface_changed"].items())
            + ". By difficulty (mean over arms): "
            + ", ".join(f"{n} {pct(sum(d.values()) / len(d))}" for n, d in f["flaky_share_by_difficulty"].items()) + ".")


def combined(res: dict) -> str:
    return "\n\n".join([
        f"# AppWorld TEST_ALL results: 13 arms, test_normal × {res['trials']} trials, one window", setup(res),
        "## Main table (ranked by TGC; % of tasks / scenarios)", main_table(res), noise(res),
        "## By difficulty", difficulty_table(res),
        "## Stochastic behaviour (§11.3)", stoch_table(res), flaky_summary(res),
        "## Trial-count sensitivity", sensitivity_table(res),
        "## All 78 pairs (row − column; Holm over the 78 Δ TGC)", pair_matrix(res),
        "## Agent tokens, steps, latency and infra (per episode)", cost_table(res),
        "## Earlier windows (context)", earlier_table(res), DEVIATIONS, LIMITS]) + "\n"


def arm_body(res: dict, a: str) -> str:
    x, s = res["arms"][a], res["stochastic"][a]
    r = next(r for r in res["ranking"] if r["arm"] == a)
    v = res["vs_seed"].get(a)
    K = res["trials"]
    rows = ["| vs | Δ TGC [95% CI] | Δ SGC [95% CI] | Holm |", "|---|---|---|---|"]
    for o in P.ARMS:
        if o == a:
            continue
        k, sign = (f"{a} − {o}", 1) if f"{a} − {o}" in res["pairs"] else (f"{o} − {a}", -1)
        p = res["pairs"][k]
        c = p["ci_tgc"] if sign == 1 else [-p["ci_tgc"][1], -p["ci_tgc"][0]]
        cs = p["ci_sgc"] if sign == 1 else [-p["ci_sgc"][1], -p["ci_sgc"][0]]
        rows.append(f"| `{o}` | {pct(sign * p['d_tgc'])} {ci(c)} | {pct(sign * p['d_sgc'])} {ci(cs)} | "
                    f"{'yes' if p['holm_significant_tgc'] else 'no'} |")
    b = x["by_difficulty"]
    e = res["earlier_windows"].get(a, {})
    parts = [f"## Results — {P.METHOD_NAMES[a]} (`{a}`)",
             setup(res),
             f"**This arm.** TGC **{pct(x['tgc'])}** {ci(r['ci_tgc'])}, SGC **{pct(x['sgc'])}**; rank **{r['rank']} of 13** "
             f"({'not separable from the top arm' if r['not_separable_from_top'] else 'separable from the top arm'}). "
             + (f"Δ vs seed: TGC {pct(v['d_tgc'])} {ci(v['ci_tgc'])}, SGC {pct(v['d_sgc'])} {ci(v['ci_sgc'])} "
                f"(Holm over 78 pairs: {'significant' if v['holm_significant_tgc'] else 'not significant'})."
                if v else "This is the baseline arm."),
             "| difficulty | TGC | SGC |\n|---|---|---|\n" + "\n".join(
                 f"| {n} (n={b[n]['n']}) | {pct(b[n]['tgc'])} | {pct(b[n]['sgc'])} |" for n in ("Easy", "Medium", "Hard")),
             "**Δ vs every other arm** (unadjusted 95% CI; Holm over the 78 pairs):\n\n" + "\n".join(rows),
             f"**Stochastic behaviour (5 trials).** Tasks passing 0/1/2/3/4/5 of 5: "
             f"{'/'.join(str(s['pass_count_distribution'][str(i)]) for i in range(K + 1))}; stable {pct(s['stable_share'])}%, "
             f"flaky {pct(s['flaky_share'])}%. pass@k: {' / '.join(pct(s['pass_at_k'][str(k)]) for k in range(1, K + 1))}; "
             f"pass^k: {' / '.join(pct(s['pass_hat_k'][str(k)]) for k in range(1, K + 1))}. Within-task share of "
             f"variance {pct(s['within_share_of_variance'])}%. TGC from the first 1..5 trials: "
             + ", ".join(pct(res["trial_sensitivity"][str(n)]["tgc"][a]) for n in range(1, K + 1)) + ".",
             f"**Agent cost.** Prompt tokens/episode {x['prompt_tokens']['mean']:,.0f} (p90 {x['prompt_tokens']['p90']:,.0f}), "
             f"completion {x['completion_tokens']['mean']:,.0f}, steps {x['steps']['mean']:.1f}, "
             f"{x['episode_seconds']['mean']:.0f} s/episode (p90 {x['episode_seconds']['p90']:.0f}); max prompt "
             f"{x['max_prompt_tokens']:,}; step-cap {x['step_cap_hits']}, token-cap {x['token_cap_hits']}, context-exceeded "
             f"{x['context_exceeded']}; infra retries {x['infra_retries']}, missing cells {x['missing']}. Cost: n/a (unpriced).",
             f"**Other window (context, not paired):** TGC {pct(e.get('tgc'))} ({e.get('label', 'n/a')}).",
             noise(res)]
    if a == "seed":
        parts.insert(5, "**All 13 arms**\n\n" + main_table(res))
    if a == "harnesslens":
        parts.insert(3, "**Result for this arm:** HarnessLens's artifact is byte-identical to the seed, so its Δ vs the "
                        "seed is the window's noise check. " + noise(res))
    parts += [f"Full tables (all arms, the 78-pair matrix): [`docs/TEST_ALL_STATE/final/RESULTS.md`]({RESULTS_URL}).",
              DEVIATIONS, LIMITS]
    return "\n\n".join(parts) + "\n"


def main() -> int:
    res = P.read_json(P.PUSHED / "final" / "analysis.json")
    for a in P.ARMS:
        P.atomic_write(P.PUSHED / a / "RESULTS.md", arm_body(res, a))
    print(json.dumps({a: len((P.PUSHED / a / "RESULTS.md").read_text()) for a in P.ARMS}))
    if "--post" in sys.argv:
        import post
        out = post.post_all("results", "{NAME} results", lambda a: (P.PUSHED / a / "RESULTS.md").read_text())
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
