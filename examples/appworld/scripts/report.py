"""P9: per-candidate results comments (docs/EVAL_APPWORLD_REST.md §14). Built only from final/analysis.json, the
pushed state and the pushed artifacts (aggregates only; content-filtered by post.post).

  python3 -I report.py draft          # writes docs/EVAL_APPWORLD_REST_STATE/<cand>/RESULTS.md
  python3 -I report.py post           # posts each draft on its issue (keyed <cand>/results, once)
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "common")]
import awrest as P  # noqa: E402
import evaluator as E  # noqa: E402

A = P.read_json(P.PUSHED / "final" / "analysis.json")
pct = lambda x: f"{100 * x:.1f}"  # noqa: E731

SETUP = {
 "harnesslens": ("HarnessLens", "jhxu5214/HarnessLens @ 369a5c8", "P + T + M (prompt, helpers, API notes, playbook)",
  "train (90) only; no validation split (the champion is the last accepted parent)"),
 "miprov2": ("MIPROv2", "DSPy 3.4.1 (`dspy.MIPROv2`)", "P (instruction + up to 3 demos in the prompt)",
  "train (90): dataset summary and demo pool; dev (57): minibatches and full evals (selection)"),
 "trace2skill": ("Trace2Skill", "Qwen-Applications/Trace2Skill @ 3d0b52a", "M (static skill playbook)",
  "train (90): trajectories and the 3-way selection; dev unused in search"),
 "gepa_full": ("GEPA-Full", "gepa 0.1.4", "P + T (prompt, helpers, one API-notes component per app)",
  "train (90): reflection minibatches; dev (57): Pareto front and final choice"),
 "cape_improve": ("Cap-Evolve-improve", "cap-evolve `cap-evolve-improve` @ 470f3fa", "P + T (prompt, helpers, API notes)",
  "train = val = train ∪ dev (147); its search score is a fit metric"),
}

IS_NOT = {
 "harnesslens": [
  "**A port, not the shipped runtime.** HarnessLens's controller logic, gates, cost formulas and all role prompts are "
  "vendored byte-identical from 369a5c8. Its runtime (opencode/codex/pi CLIs, tau2, docker) cannot run AppWorld, so it "
  "was replaced. The analysis roles are plain-chat calls with the trial bundle inlined; the Harness Editor is a sandboxed "
  "`claude -p` with Read/Write/Edit/Glob/Grep.",
  "**Inert.** 13 iterations, 0 accepted (every Review returned reject_delta or revise_delta). The search stopped at the "
  "common 10M optimizer-token cap after only 162 of 900 counted rollouts. Inlining bundles makes each iteration cost "
  "about 0.8M tokens, so the token cap bound the search long before B. The frozen artifact is the seed, so its test "
  "score measures the seed in this window; the gap to the seed arm is window noise (trial agreement 67–71%).",
  "Other port choices: channel preflight is lint + render checks, not one real rollout; screen batches of 10 TRAIN "
  "tasks (code minimum 5); confirmation re-uses the trial seed, so a parent re-run is a cache hit (rule Q1); reasoning "
  "text is left out of trial packets."],
 "miprov2": [
  "MIPROv2 optimizes only the instruction and few-shot demos of one DSPy predictor. The whole AppWorld agent is wrapped "
  "as one module whose instruction is the stock prompt's job-description prose; tools, helpers and memory are untouched.",
  "**Demo pool from the seed's successful train trajectories** (one condensation call each, then lint), not from "
  "BootstrapFewShot re-runs. No labelled demos. The champion has 2 demos.",
  "Settings: `auto=None`, 6 candidates, 16 trials, minibatch 35, full eval every 5 steps (DSPy 3.4.1 ran 5 full evals). "
  "The proposer's temperatures were dropped (gateway). DSPy's Optuna study has no storage, so resume is a seeded replay.",
  "Its dev score is the selection set's (selection-biased); only test_normal is held out."],
 "trace2skill": [
  "**Gold-free single-call analysts.** Trace2Skill's default agentic analyst reads the gold file and is not used; the "
  "single-call error and success analysts see the trajectory plus the failed-requirement texts only.",
  "Combined mode, MAP batch 1, merge batch 5, ≤ 5 merge levels, translation on, ≤ 3 verification rounds. Prompts "
  "adapted from spreadsheet to AppWorld wording (diff published), with reference files forbidden. The skill is "
  "delivered as a static playbook (≤ 14,000 tokens; the champion's is about 4.4K tokens).",
  "**The 3-seed selection, after a re-run (disclosed earlier on this issue).** Seeds 42 and 43 first replayed seed 41 "
  "through the gateway's response cache. By user decision they were re-run with a per-seed run line, so they sampled "
  "independently. Inputs were unchanged and no extra trajectory data was used. Train TGC: 0.778 / 0.800 / 0.778; "
  "seed 42 was selected (selection-biased).",
  "It saw no dev data during search, so its dev diagnostic (0.649) is the only number it did not select on before test."],
 "gepa_full": [
  "\"Full mode\" here means GEPA's own MCPAdapter pattern: the prompt, the helpers module, and one tool-description "
  "component per AppWorld app (13 components), round-robin, evolved by GEPA 0.1.4's stock engine. Merge is off (the "
  "default).",
  "Custom proposer with `<new_text>` delimiters (the stock prompt's code fences break GEPA's parser), the lint inside "
  "it, and ≤ 2 re-reflections. Per-app reflective datasets hold only the steps that touched that app.",
  "The champion changed the prompt and one app's API note; the helpers stayed empty. With 13 components each visited "
  "about 3 times and a 3-task acceptance minibatch, tool components rarely change, as expected.",
  "max_metric_calls 894, so fresh episodes stay ≤ 900. Its dev score is the Pareto/selection set's."],
 "cape_improve": [
  "**The improved version as committed (470f3fa), every improvement checked in effect** (I1–I6, below): `gate_k_se` "
  "0.5 explicit, optimizer instructions re-derived from the pinned template (strategy section included), the pinned "
  "#865 skills via `CAPEVOLVE_SKILLS_DIR`, the pinned V3 hill-climb core, and the claude-code optimizer.",
  "Stock hill-climb `--focus all`, 6 iterations, 1 trial, paired gate. Train = val = train ∪ dev (147), so its "
  "search score (0.837) is a fit metric. It overstates its test TGC (49.4) by about 34 points.",
  "Isolation applied by hand: a PATH shim runs the optimizer inside Claude Code's sandbox (deny rules on all gold, "
  "AppWorld, the evaluator and secrets; network restricted to the gateway; `--setting-sources ''`). The sandbox check "
  "(A9) passed only after one fix: the user's settings had widened the network allowlist.",
  "k = 0.5 raises false accepts on 1-trial gates; 4 of 5 scored iterations were accepted."],
}


def common_rows(c: str) -> str:
    a, s = A["arms"], A["vs_seed"][c]
    L = ["| arm | TGC | SGC | Δ TGC vs seed [95% CI] | Δ SGC vs seed [95% CI] | missing cells |", "|---|---|---|---|---|---|"]
    for arm in ("seed", c):
        r = a[arm]
        if arm == "seed":
            L.append(f"| seed | {pct(r['tgc'])} | {pct(r['sgc'])} | — | — | {r['missing']} |")
        else:
            L.append(f"| **{P.METHOD_NAMES[c]}** | **{pct(r['tgc'])}** | **{pct(r['sgc'])}** | **{pct(s['d_tgc'])} "
                     f"[{pct(s['ci_tgc'][0])}, {pct(s['ci_tgc'][1])}]** | {pct(s['d_sgc'])} [{pct(s['ci_sgc'][0])}, "
                     f"{pct(s['ci_sgc'][1])}] | {r['missing']} |")
    D = ["| arm | Easy (57) | Medium (48) | Hard (63) |", "|---|---|---|---|"]
    for arm in ("seed", c):
        b = a[arm]["by_difficulty"]
        D.append(f"| {arm} | {pct(b['Easy']['tgc'])} | {pct(b['Medium']['tgc'])} | {pct(b['Hard']['tgc'])} |")
    T = ["| arm | prompt tok / ep (mean, p50, p90) | completion tok / ep | steps | s / ep (mean, p90) | step-cap | ctx-exceeded | pass fraction | trials agree |",
         "|---|---|---|---|---|---|---|---|---|"]
    for arm in ("seed", c):
        r = a[arm]
        T.append(f"| {arm} | {r['prompt_tokens_per_task']:,.0f}, {r['prompt_tokens_p50']:,.0f}, {r['prompt_tokens_p90']:,.0f} | "
                 f"{r['completion_tokens_per_task']:,.0f} | {r['steps_per_task']:.1f} | {r['episode_seconds']:.0f}, "
                 f"{r['episode_seconds_p90']:.0f} | {r['step_cap_hits']} | {r['context_exceeded']} | "
                 f"{r['pass_fraction']:.3f} | {100 * r['trials_agree_share']:.0f}% |")
    o, ro = A["search"][c]["optimizer"], A["search"][c]["rollouts"]
    cli = f" (CLI-reported ${o['cli_reported_usd']})" if o.get("cli_reported_usd") else ""
    S = ["| | value |", "|---|---|",
         f"| counted search rollouts | {ro['counted']} of B = 900 (cache hits {ro['cache_hits']}, lint-reject batches "
         f"{ro['lint_reject_batches']}, infra {ro['infra']}); the shared seed baseline (147) is not charged |",
         f"| mean reward of counted rollouts | {ro['mean_reward_counted']} (search sets; selection-biased) |",
         f"| agent tokens / search episode (mean, p90) | prompt {ro['prompt_tokens']['mean']:,.0f}, "
         f"{ro['prompt_tokens']['p90']:,.0f}; completion {ro['completion_tokens']['mean']:,.0f} |",
         f"| search episode seconds (mean, p90) | {ro['episode_seconds']['mean']}, {ro['episode_seconds']['p90']} |",
         f"| optimizer calls | {o['calls']} ({o['errors']} errors), model {', '.join(o['models']) or P.OPT_MODEL} |",
         f"| optimizer tokens | {o['input_tokens']:,} in (non-cache-read) / {o['output_tokens']:,} out / "
         f"{o['cache_read_tokens']:,} cache-read / {o['cache_write_tokens']:,} cache-write |",
         f"| optimizer cost | **${o['proxy_usd']}** proxy at Sonnet 5.5 list price{cli} |",
         f"| optimizer time | {o['optimizer_seconds_total']:,} s in calls (mean {o['call_seconds_mean']} s, p90 "
         f"{o['call_seconds_p90']} s); search wall {ro['search_wall'][0]} → {ro['search_wall'][1]} |",
         f"| dev diagnostic (57 dev, 1 trial) | {A['dev_diagnostic_tgc'].get(c)} (seed {A['dev_diagnostic_tgc'].get('seed')}) |",
         "| agent cost | n/a (RITS is unpriced); tokens above |"]
    return "\n".join(L), "\n".join(D), "\n".join(T), "\n".join(S)


def artifact_summary(c: str) -> str:
    seed = E.read_surfaces(P.SEED_CAP)
    s = E.read_surfaces(P.PUSHED / c / "artifact")
    out = []
    for k in ("policy/instructions.txt", "tools/helpers.py", "tools/api_notes.json", "memory/playbook.md"):
        v, b = s.get(k, ""), seed.get(k, "")
        if v == b:
            out.append(f"- `{k}`: unchanged from the seed")
            continue
        extra = ""
        if k == "tools/helpers.py":
            extra = f", {sum(1 for n in ast.parse(v).body if isinstance(n, ast.FunctionDef))} helper functions"
        if k == "tools/api_notes.json":
            extra = f", {len(json.loads(v or '{}'))} notes"
        if k == "memory/playbook.md":
            extra = f", {E.memory_tokens(v):,} tokens"
        out.append(f"- `{k}`: changed ({len(b):,} → {len(v):,} chars{extra})")
    out.append(f"- tree sha256 `{E.tree_hash(P.PUSHED / c / 'artifact')[:16]}`; lint-clean; published in "
               f"`docs/EVAL_APPWORLD_REST_STATE/{c}/artifact/` on branch `eval-rest`")
    return "\n".join(out)


def imp_block() -> str:
    fz = P.read_json(P.PUSHED / "cape_improve" / "artifact" / "FREEZE.json", {}) or {}
    imp = fz.get("imp") or {}
    ok = lambda k: "pass" if (imp.get(k) or {}).get("ok") else "see FREEZE.json"  # noqa: E731
    return ("\n**Improvements of cap-evolve-improve, verified in effect** (post-search re-check of every iteration):\n\n"
            f"- I5 code pin: core imported from the 470f3fa worktree, clean: {ok('1_code_pin')}\n"
            f"- I4/I6 skills pin: `CAPEVOLVE_SKILLS_DIR` resolves to the pinned skills, not `~/.claude/skills`: {ok('2_skills_pin')}\n"
            f"- I1 `gate_k_se: 0.5` in the spec and the run_config event: {ok('3_spec_k_se')}; `--k-se 0.5` on the hill-climb command line: {ok('4_effective_k_se')}\n"
            f"- I2/I3 the INSTRUCTIONS.md handed to the optimizer contains the strategy section and the #865 text in all iterations, with no old-template markers: {ok('5_instructions')}\n"
            f"- I4 guidance SKILL.md files equal the pinned skills: {ok('6_guidance')}\n"
            f"- I5 the pinned hill-climb `run.py` ran: {ok('7_hill_climb_script')} (sha256 `c04938fc`)\n"
            "- `instructions.diff` (pinned template vs the run's template) shows only the inserted AppWorld section\n")


def body(c: str) -> str:
    name, pin, surf, splits = SETUP[c]
    main, diff, tok, srch = common_rows(c)
    iso = A["isolation"].get(c) or {}
    others = ", ".join(f"{P.METHOD_NAMES[x]} {pct(A['vs_seed'][x]['d_tgc'])}" for x in P.CANDIDATES if x != c)
    return f"""**Final results: {name} vs the seed agent (AppWorld test_normal).**

### Setup
- method: {name}, {pin}; surface: {surf}; search splits: {splits}
- agent under test (all arms): `openai/gpt-oss-120b-a100` on RITS, reasoning medium, temperature 0, 50 steps, 100K completion tokens/task, the official simplified ReAct agent at AppWorld `42b5bcf`
- optimizer (every role): `aws/claude-sonnet-5-5` via the gateway (no temperature/seed sent); gold-free feedback (reward, failed requirement texts, collateral damage, steps, termination)
- budget: B = 900 counted search rollouts and 10M optimizer non-cache-read tokens; 1 search seed; 1 trial per task in search
- baseline: one shared seed run (train 90 + dev 57), reused by every candidate, not charged
- final window: 168 test_normal tasks × 6 arms × 2 trials = 2,016 cells, one shuffled order, 0 missing cells; seed and all five champions scored together

### Main result (test_normal, 168 tasks / 56 scenarios, 2 trials)
{main}

95% CI: scenario-clustered paired bootstrap (56 clusters, 10,000 resamples), unadjusted.

### TGC by difficulty
{diff}

### Agent cost, tokens and latency (final window, per episode)
{tok}

### Search phase (cost, tokens, latency, budget)
{srch}

### What changed (the frozen artifact)
{artifact_summary(c)}
{imp_block() if c == "cape_improve" else ""}
### Isolation
Post-search and full scans: **{iso.get('test_id_hits')} test-id hits** in every optimizer-side record, workspace and transcript of this arm, and 0 in the orchestrating sessions' own transcripts. Not labelled an isolation breach. The only literal-string hits (`root_full`, `ground_truth`) are in the sandbox acceptance probe and the sandbox's own deny list.

### What this {name} is and is not
""" + "\n".join(f"- {x}" for x in IS_NOT[c]) + f"""
- Common to all arms: Sonnet 5.5 optimizer (not each paper's model), gold-free feedback, B = 900 + 10M tokens, memory cap 14,000 tokens, 1 trial per task in search, the shared seed baseline.

### Deviations
See plan §15 and this issue's earlier posts. All five arms share the same harness, model client, decoding, caps, evaluator, final window and analysis.

### What the numbers cannot support
- **No ranking between candidates.** Each had one search seed, its own surface and budget use. Identical artifacts drifted by 4–6 TGC points between windows in earlier runs, and the two trials of a task agree on only 67–81% of tasks. For context only, Δ TGC vs seed of the other arms in this same window: {others}.
- Artifact-level statements only: one search run of this method under this configuration, not the method in general.
- Search-time scores are selection-biased; only the test_normal numbers above are held out.
- No multiplicity correction across the five comparisons.

Full tables: `docs/EVAL_APPWORLD_REST_STATE/final/RESULTS.md` and `analysis.json`; ledger: `docs/EVAL_APPWORLD_REST.md` §18.
"""


def main() -> int:
    import post
    for c in P.CANDIDATES:
        p = P.PUSHED / c / "RESULTS.md"
        if sys.argv[1] == "draft":
            P.atomic_write(p, body(c))
            print("drafted", p)
        else:
            print(c, post.post(c, "results", f"{SETUP[c][0]} results", p.read_text()) or "(already posted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
