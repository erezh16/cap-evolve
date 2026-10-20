"""P10: one results comment per candidate (docs/EVAL_APPWORLD_5.md §12), built only from the pushed aggregates.

  python3 -I report5.py draft    # writes docs/EVAL_APPWORLD_5_STATE/<cand>/RESULTS.md for each candidate
  python3 -I report5.py post     # posts each draft on its issue (post5: content filter, once only)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aw5 as P  # noqa: E402

NAMES = {"gepa": "GEPA", "skillopt": "SkillOpt", "wikiskill": "WikiSkill", "evoskill": "EvoSkill",
         "metaharness": "Meta-Harness"}
PIN = {"gepa": "PyPI `gepa==0.1.4` (`8b0ce6c`)", "skillopt": "`microsoft/skillopt` @ `ae2f766`",
       "wikiskill": "`kenhuangus/wikiskill` @ `0363334` (third-party reimplementation)",
       "evoskill": "`sentient-agi/EvoSkill` `v1.3.0` (`1d7dc3e`)",
       "metaharness": "`stanford-iris-lab/meta-harness` @ `8123cca`"}
SURFACE = {"gepa": "P + T (prompt template, helpers, API notes)", "skillopt": "M (static memory playbook)",
           "wikiskill": "M (static memory playbook)", "evoskill": "M (static memory playbook)",
           "metaharness": "P + T (+ optional M); the champion uses P + T"}

SEARCH = {
    "gepa": """GEPA 0.1.4 reflective evolution over three text components (`policy/instructions.txt`, `tools/helpers.py`, `tools/api_notes.json`).
- Settings: round_robin module selection, minibatch 3, Pareto candidate selection, strict improvement, no merge, max_metric_calls 987, seed 0.
- Data: trainset = official train (90 tasks, reflection minibatches); valset = official dev (57 tasks, Pareto front and final choice).
- Reflection used GEPA's instruction-proposal text with two changes: the new text is delimited by `<new_text>` (the stock prompt contains about 45 ``` fences), and the lint rules are stated in the prompt. Over the whole search the reflector's output was lint-rejected 7 times and failed to parse once; each time it was re-asked with the lint or parse error, and it never gave up. There were 0 refusals.
- Search end: the evaluator's hard cap B = 900 counted rollouts was hit 3 calls before GEPA's own 987. The result is GEPA's state saved before the abandoned iteration.
- Outcome: 13 candidates in the pool. The champion is candidate 12 (dev 0.719; the seed scored 0.421 in the same search). In the frozen artifact the prompt is rewritten (about 22K chars, adding a section of general app/API facts and answer rules); helpers and API notes are unchanged from the seed.""",
    "skillopt": """SkillOpt `ReflACTTrainer` evolving one Markdown skill document injected into the memory slot.
- Settings: SkillOpt's own defaults (its `configs/_base_`), with batch 40, minibatch 8, merge 8, learning rate 4→2 cosine, slow update on, meta skill on, strict gate on full dev (`gate_metric=hard`), seed 42.
- Every optimizer stage (analyst, merge, ranking, slow update, meta skill) went through the gateway shim: no temperature, max_tokens 16384.
- Epochs: **3 instead of 4**, the least-distorting change that fits B = 900 (§7.2). The evaluator cap was reached during the last step.
- Data: train = official train (90 tasks); the gate is the official dev set (57 tasks).
- Rollouts give the optimizer compacted conversations (outputs ≤ 2,000 chars, total ≤ 60,000) with the gold-free failed-check report. `reference_text` was never set.
- Gate results: steps 1, 2 and 8 accepted (dev hard 0.649 → 0.719 → 0.754; seed baseline on the same gate 18/57 = 0.316). The frozen skill is step 8's: 24,118 chars, about 5.7K tokens.""",
    "wikiskill": """WikiSkill (Algorithm 1) as reimplemented by the vendored `kenhuangus/wikiskill` loop. Each iteration:
- roll out **all** 90 train tasks with the current skills;
- sample 5 failing and 3 passing traces (15k chars each);
- make one Wiki Maintainer call;
- run a ReAct Skill Proposer (≤ 20 turns, `read_file` over the workspace only);
- validate on **all** 57 dev tasks and accept the change only on strict improvement, rolling back skills (not the wiki) otherwise.

Prompts: the paper's Appendix E Maintainer and Proposer prompts replace the repository's condensed ones, plus a one-paragraph tool-call syntax note. Accepted skills are rendered into the memory slot with no retrieval.

**K = 5 iterations instead of 8**, to fit B = 900 (57 + 5 × 147 = 792).

Trajectory: baseline 0.333 → it1 create 0.456 (accepted) → it2 patch 0.456 (rejected) → it3 patch 0.561 (accepted) → it4 patch 0.614 (accepted) → it5 second skill 0.596 (rejected). The frozen playbook is one skill: 7,859 chars, about 1.9K tokens.""",
    "evoskill": """EvoSkill `SelfImprovingLoop` (skill_only), driven from Python.
- Settings: frontier size 3, selection "best", failure threshold 0.8, no_improvement_limit 5, and 6 train samples per iteration (3 difficulty categories × 2).
- Val per iteration: a fixed stratified **20-task dev subset** (§7.4 budget rule). At freeze, the 3 frontier programs were re-scored on the full 57-task dev set (counted).
- **De-fanged:**
  - the Proposer gets a withheld sentinel instead of ground truth, and a copy of its prompt with the ground-truth phrases replaced by "evaluation feedback (failed checks)";
  - the Proposer's tools are Read/Glob/Grep and the Skill Builder's are Read/Write/Edit/Glob/Grep, with Bash and web tools removed. A write gate allows only program-skill files;
  - the project root is a scratch git repo;
  - both agents ran in Claude Code's sandbox (A9 passed).
- Search ran to its iteration cap (22 in all; the resumed run did iterations 5–22; 17 children scored, one lint-rejected). Base 0.30 on the val subset; best children 0.75. At freeze, `iter-skill-25` scored 0.754 on full dev (iter-skill-26 0.737, iter-skill-17 0.702) and is the champion: an 18.3K-char playbook, about 4.5K tokens.
- One crash (a driver bug on a lint-rejected child, iteration 4) was fixed and resumed with EvoSkill's own continue mode.""",
    "metaharness": """Meta-Harness ported from its Terminal-Bench-2 reference.
- **Outer loop:** Phase 0 scores the seed on the search set (train ∪ dev, 147 tasks). Each iteration then runs the proposer → `pending_eval.json` → validator (outside the proposer: forbidden strings, file allowlist, render and parse checks, shared lint) → 1-task smoke test → 147-task evaluation → frontier with token tie-break.
- **Proposer:** the vendored `claude_wrapper` (`claude -p`, `aws/claude-sonnet-5-5`, Read/Glob/Grep/Agent/Write/Edit/Bash) driven by an AppWorld adaptation of the TB2 SKILL.md, with the "do not run the agent or AppWorld" rule. Its workspace held only candidates, gold-free per-task trajectories and scores, the public API reference and a lint.
- **Iterations:** 7 (5 producing candidates). Iterations 2 and 4 were lost: `claude -p` ended their analysis sub-agents at 600 s. After the fix, user decision D11 ran 2 replacement iterations within B (887/900 counted rollouts).
- **Search-set TGC:** seed 0.401; it1 `no_answer_on_action_tasks` 0.558; **it3 `fetch_all_pages_helper` 0.585 (champion)**; it5 0.544; it6 0.578; it7 0.571.
- **The champion changes P + T:** prompt edits plus a page-fetching helper and API notes.""",
}

ISNOT = {
    "gepa": "the optimizer is Sonnet, not the target model; the feedback is gold-free F1 (the ACE paper's GEPA baseline had gold labels); one search seed; 0/1 rewards with minibatch 3 make acceptance noisy",
    "skillopt": "the optimizer is Sonnet, not GPT-5.5 as in the paper; the skill sits in the memory slot (USER turn), not in the system prompt; 3 epochs instead of 4; no Hidden Reference; compacted trajectories",
    "wikiskill": "**a third-party, AI-assisted reimplementation** (no official code exists), with the paper's Appendix E prompts restored; the gateway LLM wrapper, AppWorld inference adapter, outcome summary, parallel rollouts, cost logging, tool-call syntax note and skills→playbook export are ours; K = 5 instead of 8; the optimizer is a fixed Sonnet",
    "evoskill": "ground truth was withheld and the Proposer's gold comparisons were de-fanged; no Bash or web tools; val on a 20-task dev subset (the full dev re-score happens at freeze only); the optimizer is Sonnet, not Opus; skills are rendered into a static playbook in the memory slot (the agent cannot read skill files)",
    "metaharness": "the proposer ran with `--permission-mode acceptEdits` inside Claude Code's sandbox instead of the wrapper's `--dangerously-skip-permissions` (**user decision D10**); Sonnet instead of Opus (no `--effort`); search restricted to the four injectable harness files, not arbitrary agent code; 1 trial per task in search (TB2 uses 2); 2 of 7 iterations were lost to the CLI's 600 s sub-agent limit, and 2 replacements were run (D11); AppWorld was kept out of the proposer's view",
}


def pct(x):
    return f"{100 * x:.1f}"


def body(c: str, A: dict) -> str:
    a, s, v = A["arms"][c], A["arms"]["seed"], A["vs_seed"][c]
    o = A["optimizer"][c]
    iso = A["isolation"][c]
    dev = A["dev_diagnostic_tgc"]
    usd = (f"${o['reported_usd']} (reported by the {'CLI' if c == 'metaharness' else 'Agent SDK'})"
           if o.get("reported_usd") else f"${o['proxy_usd']} (proxy at list price $3/$15 per MTok)")
    diff = "\n".join(f"| {n} ({A['arms']['seed']['by_difficulty'][n]['n']}) | {pct(s['by_difficulty'][n]['tgc'])} | "
                     f"{pct(a['by_difficulty'][n]['tgc'])} | {100 * (a['by_difficulty'][n]['tgc'] - s['by_difficulty'][n]['tgc']):+.1f} |"
                     for n in ("Easy", "Medium", "Hard"))
    cost = "\n".join(f"| {arm} | {x['prompt_tokens_per_task']:,.0f} | {x['completion_tokens_per_task']:,.0f} | "
                     f"{x['steps_per_task']:.1f} | {x['episode_seconds']:.0f} | {x['step_cap_hits']} | {x['context_exceeded']} | "
                     f"{x['collateral_damage']} | {x['max_prompt_tokens']:,} | {100 * x['trials_agree_share']:.0f}% |"
                     for arm, x in (("seed", s), (c, a)))
    side = " · ".join(f"{NAMES[k]} {100 * A['vs_seed'][k]['d_tgc']:+.1f}" for k in P.CANDIDATES)
    return f"""# Results: {NAMES[c]} vs seed on AppWorld test_normal (gpt-oss-120b)

**Headline.** On the 168 held-out test_normal tasks (2 trials each), the {NAMES[c]} champion scores **TGC {pct(a['tgc'])} vs {pct(s['tgc'])}** for the unmodified seed, **Δ {100 * v['d_tgc']:+.1f} points, 95% CI [{100 * v['ci_tgc'][0]:+.1f}, {100 * v['ci_tgc'][1]:+.1f}]**. SGC is **{pct(a['sgc'])} vs {pct(s['sgc'])}**, Δ {100 * v['d_sgc']:+.1f} [{100 * v['ci_sgc'][0]:+.1f}, {100 * v['ci_sgc'][1]:+.1f}]. Both intervals exclude 0. The isolation scan found {iso['test_id_hits']} test-id hits.

## Setup
- **Method:** {NAMES[c]}, {PIN[c]}. Surface learned: {SURFACE[c]}.
- **Agent under test (all 6 arms):** `openai/gpt-oss-120b` on RITS. The official AppWorld simplified ReAct code agent (`42b5bcf`), reasoning effort medium, temperature 0, 50 steps, 40K context. The same harness, worker, decoding and evaluator are used for every arm; only each arm's surface files differ.
- **Optimizer:** `aws/claude-sonnet-5-5` via the gateway (D1). The same model for all five candidates.
- **Splits:** official only. Search used train (90) and dev (57). **test_normal (168) was sealed and locked (`chmod 000`) during every search** and scored once, in the final window. test_challenge was not used.
- **Feedback:** gold-free tier F1 (failed requirement texts, collateral flag, steps, errors), never the gold answer or trace.
- **Budget:** ≤ B = 900 counted search rollouts and ≤ 10M optimizer tokens per candidate, 1 trial per task in search, 1 search seed.
- **Final window:** **one** interleaved window of 168 tasks × 6 arms (seed + 5 candidates) × 2 trials = 2,016 episodes, in one shuffled order (recorded seed). Trial seeds 5000 + trial. 0 missing cells; infra retries: {a['infra_retries']} for this arm, {s['infra_retries']} for the seed.

## Main result (test_normal, 168 tasks / 56 scenarios × 2 trials)

| arm | TGC | SGC |
|---|---|---|
| seed | {pct(s['tgc'])} | {pct(s['sgc'])} |
| **{c}** | **{pct(a['tgc'])}** | **{pct(a['sgc'])}** |
| Δ vs seed [95% CI] | {100 * v['d_tgc']:+.1f} [{100 * v['ci_tgc'][0]:+.1f}, {100 * v['ci_tgc'][1]:+.1f}] | {100 * v['d_sgc']:+.1f} [{100 * v['ci_sgc'][0]:+.1f}, {100 * v['ci_sgc'][1]:+.1f}] |

CIs come from a scenario-clustered paired bootstrap (56 clusters, 10,000 resamples), unadjusted for multiplicity. Every cell ran, so dropping missing cells changes nothing.

## TGC by difficulty

| difficulty (n) | seed | {c} | Δ |
|---|---|---|---|
{diff}

## Cost, tokens and latency

Agent side, final window, per episode:

| arm | prompt tok | completion tok | steps | s | step-cap hits | ctx exceeded | collateral damage | max prompt tok | trials agree |
|---|---|---|---|---|---|---|---|---|---|
{cost}

The agent runs on RITS, which is unpriced, so agent tokens have no dollar cost.

Optimizer side (search): {o['calls']} calls, {o['input_tokens'] / 1e6:.2f}M input / {o['output_tokens'] / 1e6:.2f}M output tokens{f", {o['cache_read_tokens'] / 1e6:.1f}M cache-read" if o['cache_read_tokens'] else ""}, **{usd}**, {o['optimizer_seconds'] / 60:.0f} min of optimizer wall time. **{o['counted_search_rollouts']} counted search rollouts** (of 900).

## What the search did and what changed
{SEARCH[c]}

The frozen artifact passed the lint (no train/dev instruction 8-grams, no supervisor contacts, no hardcoded `apis.<app>` chains). It is published in `docs/EVAL_APPWORLD_5_STATE/{c}/artifact/`.

## Isolation
- {iso['test_id_hits']} test-id hits across every optimizer-side record, workspace and the frozen artifact.{" The only literal `root_full` / `ground_truth` strings in the optimizer area are in the A9 acceptance transcript (my planted-secret probe, which names those paths), not in any search session." if c == "metaharness" else ""}
- test_normal was locked during the search. AppWorld's REPL was hardened (no `os`, `pathlib`, `io`, `shutil` or `glob`). Feedback was gold-free.
- {"The proposer ran in Claude Code's sandbox (A9: 0 of 11 planted secrets leaked; network restricted to the gateway; AF_UNIX blocked). Its own logs show every file read and write inside the optimizer workspace." if c == "metaharness" else "Both Claude agents ran in Claude Code's sandbox with the de-fanged tool sets (A9 via the Agent SDK: 0 of 11 planted secrets leaked)." if c == "evoskill" else "The optimizer makes plain chat calls with no shell or file access."}
- Dev diagnostic (57 dev tasks, 1 trial, selection-biased): {c} {dev.get(c)} vs seed {dev.get('seed')}.

## What this {NAMES[c]} is and is not
This is a statement about **one artifact from one search seed** in this configuration, not about {NAMES[c]} as published. Deviations from the published method: {ISNOT[c]}. Common to all five arms: the optimizer is `aws/claude-sonnet-5-5`; the stock AppWorld template plus an injectable memory slot; a fixed rollout budget (B = 900); gold-free F1 feedback; and the memory cap (30,000 chars / M_cap 13,500 tokens).

## What the numbers cannot support
- **No ranking between candidates.** Budgets and surfaces differ, and with one search seed per method these are artifact-level results.
- Two identical artifacts scored in different windows have drifted by about 4–6 TGC points (base plan F10), and within this window the two trials of a task agreed on only {100 * a['trials_agree_share']:.0f}% of tasks for this arm. Gaps of a few points between candidates are within noise.
- For context only, Δ TGC vs seed for all five candidates in this window: {side}.
- Search-time scores (dev and the search set) are selection-biased and overstate test performance.

## Deviations from the plan, all recorded in the ledger (`docs/EVAL_APPWORLD_5.md` §15)
- One voided final window (stopped at 1,001 cells when Meta-Harness was re-run; never used for results).
- A container restart during this window (no data lost; resumed at 24 workers instead of 48).
- Memory watermarks at 90/80%.
- Code: `examples/appworld/` @ `e313482` and later fix commits on branch `eval5`.
"""


def main() -> int:
    A = P.read_json(P.PUSHED / "final" / "analysis.json")
    if sys.argv[1] == "draft":
        for c in P.CANDIDATES:
            P.atomic_write(P.PUSHED / c / "RESULTS.md", body(c, A))
            print(c, len(body(c, A)))
        return 0
    import post5
    for c in P.CANDIDATES:
        print(c, post5.post(c, "results", f"{NAMES[c]} results", (P.PUSHED / c / "RESULTS.md").read_text()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
