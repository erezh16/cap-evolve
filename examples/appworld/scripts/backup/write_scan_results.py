"""Write SCAN_RESULTS_<TS>.md into each run folder (docs/VERIFICATION_SCAN.md format), from this session's evidence."""

import json
import sys
from pathlib import Path

TS = sys.argv[1]
B = Path("/tmp/aw_eval/backup")
COMMIT = sys.argv[2]
MB = json.load(open("/tmp/aw_eval/backup_tools/models_by_role.json"))
R1 = "2026-10-13-appworld-capevolve-hillclimb-gptoss120b-sonnet55-original-breach"
R2 = "2026-10-13-appworld-altkevolve-v130-retrieval-gptoss120b-sonnet55-original"
R3 = "2026-10-15-appworld-capevolve-hillclimb-gptoss120b-sonnet55-fix-clean"


def models_rows(run):
    m, t = MB[run]["messages"], MB[run]["output_tokens"]
    tot = sum(t.values())
    return "\n".join(f"| {k.split('|')[0]} | {k.split('|')[1]} | {m[k]:,} | {t[k]:,} ({100 * t[k] / tot:.1f}%) |"
                     for k in sorted(m))


HEAD = """# Verification scan: {name}
Scan started: {ts}   ·   Procedure: `docs/VERIFICATION_SCAN.md` @ `{commit}` (branch `erezh-eval1`, erezh16/cap-evolve)
Status: **{status}** — {why}

Evidence was collected during the evaluation and its archiving (13–19 Oct 2026). The scan record is the session
transcript in `reproduce/orchestrator/`. Finding ids `F<n>` refer to Appendix A of `docs/EVAL_SMOKE_TEST.md`
(copy in `docs/`).
"""

COMMON_ENV = """| Claude Code CLI version | not stated | 2.1.270 in every session (from the transcripts) | n/a (now recorded) |
| CLI flags | `claude -p … --permission-mode acceptEdits --allowedTools Bash --disallowedTools Monitor --max-turns 200 --max-budget-usd 15` (registry row + spec) | permissionMode `acceptEdits` in every session; flags as rendered by run-optimizer | yes |
| inherited CLI settings | none intended | `effortLevel: high`, `alwaysThinkingEnabled: true`, plugins (pyright-lsp, context7, playwright) and `CLAUDE_CODE_SUBAGENT_MODEL=aws/claude-opus-5-5[1m]` inherited from `~/.claude/settings.json` | **no** (see F21) |
| agent model | `openai/gpt-oss-120b-a100`, IBM RITS, reasoning medium, temperature 0 (plan §0, §5.1) | same; litellm route `hosted_vllm/…`; `max_completion_tokens` 6000, `drop_reasoning_content`, `use_cache` false; RITS `max_model_len` 40,144 | yes |
| agent seeds | `random_seed` 100 + trial (search), 5000 + trial (final) (§5.1, §12) | same (`aw_agent.py`, `final_window.py`) | yes |
| agent limits | 50 steps; 100,000 completion tokens/task; history trimmed at 60,000 chars (§5.1) | 50 steps; token cap **enforced by our loop** (AppWorld never enforces it, F2); trimming never fired (max prompt 18–24K tokens) | yes, with F2 fix |
| AppWorld code | PyPI 0.1.3.post1 + head ReAct agent (design) → source `42b5bcf` + pydantic 2.12 (decision D2) | `42b5bcf3…` + 18-line header patch; pydantic 2.12.5; litellm 1.80.0 | yes (D2) |
| data | AppWorld data, official splits 90/57/168/417 (§1.1, S1) | data 0.2.0, counts 90/57/168/417, split hashes and `sha256_tree` recorded | yes |
| split rule | train = val = train ∪ dev (147), test sealed (S2) | `split_ids.json` train = val = 147, test = []; root_opt has 0 test-id hits | yes |
| final window | 168 × 3 arms × 2 trials, one interleaved order, 48 workers (§12) | same, order seed 20261013, 0 infra errors, 0 missing cells | yes |
"""


def r1():
    return HEAD.format(name=R1, ts=TS, commit=COMMIT, status="invalid (discarded)",
                       why="train/dev answers read by the optimizer in round 2 (A1, INVALIDATES); the comparison is also not same-model (B1, INVALIDATES)") + f"""
## Summary
| check | result | severity |
|---|---|---|
| A1 answer/gold access | round 2: 36 subagent tool calls read train/dev `solution.py`, `private_data.json`, `evaluation.py`, ran the grader with gold traces (F14) | **INVALIDATES** |
| A2 test access | 0 test-id hits in all transcripts, workdirs and run dir; `root_full` locked (`chmod 000`) all search long | PASS |
| A3 copies | `/tmp/diag/root`: copy of `root_opt` made in round 2; kept sealed as evidence (`isolation/diag_root_SEALED.tar`) | INFO |
| A4 beyond intended context | round 1 listed one train task dir (saw `ground_truth/` exists, opened nothing); round 4 (unguarded 18:27–18:37) directory listings only | INFO |
| A5 isolation mechanism | rounds 1–3: none (file permissions only on `root_full`); round 4: a 1-s polling lock (raced, broke rounds 4–6, F15); rounds 6–8: synchronous lock shim on `root_opt` (4 lock/unlock pairs in the guard log) | **QUALIFIES** |
| A6 agent under test | REPL hardened (os/pathlib/io/shutil/glob blocked, F1); `fs_probe` = 0 in all 1,008 window-1 episodes | PASS |
| B1 models as used | optimizer main loop Sonnet 5.5; **subagents: Sonnet 5.5 and Opus 5.5** (table below); ALTK arm used Sonnet 5.5 only | **INVALIDATES** (same-model claim) |
| B2 intent vs actual | see table; 3 mismatches (subagent model, inherited settings, iteration budget raised 6 → 8) | QUALIFIES |
| B3 budgets | 1,029 search episodes vs ALTK 147; optimizer $67.84 vs ALTK ≈$18 (estimated) | QUALIFIES (unmatched, disclosed) |
| B4 one window | all three arms in window 1, frozen artifact hashes recorded | PASS |
| B5 drift | identical seed artifact: TGC 35.1 (window 1) vs 31.5 (window 2) | INFO |
| C1 splits | official only, disjoint, test sealed | PASS |
| C2 search vs held-out | search val 0.884 (fit metric) vs test TGC 0.536 | INFO (labelled) |
| C3 infra errors | 0 in window 1; one 30-min wall-cap hit in search, retried (F13) | PASS |
| C4 harness limits | AppWorld does not enforce the per-task token cap (F2) — enforced by our loop; REPL guard gaps (F1) closed | PASS (after fixes) |
| C5 interruptions | rounds 4–5 and the first try of 6 lost to the guard race (F15); run resumed with `--max-iterations 8`; 6 scored rounds | QUALIFIES (disclosed) |
| C6 gate decisions | 4 accepts (r1, r2, r3, r6), 2 rejects (r7, r8), each consistent with paired Δ vs k·SE in `events.jsonl` | PASS |
| C7 determinism | trials disagree on 64/168 (seed), 42/168 (cape-hc), 40/168 (altk) tasks (F10, corrected) | INFO |
| C8 feasibility | n/a for this arm | PASS |
| D1–D8 completeness | 0 missing of 3,445 source files; LEDGER ×10, JOURNAL ×21, 1,051 rollouts; posts 10 + full thread; metrics_full complete; 8 symlinks listed; tools load the copy; 0 secret hits; NOTICE.md present, owner decided private upload | PASS |
| E1–E4 reproducibility | bundle verifies; R1 code never committed → rebuilt from the session (v3 byte-identical to the run copy); RITS backend build not visible | QUALIFIES (known gap) |
| F published claims | "optimizer Sonnet 5.5 for both methods" contradicted by B1 | **corrected** on #804 (2026-10-19) |

## Intent versus actual (B2)
| item | intended | actual | match? |
|---|---|---|---|
| optimizer main loop | `aws/claude-sonnet-5-5` (plan §0, D1) | Sonnet 5.5 in all 9 sessions | yes |
| optimizer subagents | Sonnet 5.5 (implied: "optimizer model, both methods") | see models table: Opus 5.5 in round 1 | **no** |
| iterations | 6 (`max_iterations: 6`) | 8 counted, 6 scored (budget raised on resume, F15) | qualified |
| gate | paired, k = 1.0, 1 trial | same | yes |
| optimizer caps | $15/iter, $120 total, 200 turns | $67.84 total; no cap hit | yes |
| isolation | data-root separation + adapter seal + REPL guards (§9) | as intended, **but the optimizer could read `root_opt` gold** (F8, F14) | **no** |
{COMMON_ENV}
### Optimizer models by role (assistant messages; output tokens)
| role | model | messages | output tokens |
|---|---|---|---|
{models_rows("cape_hc_s0")}

## Findings
### F14. Train/dev gold read in round 2 (INVALIDATES)
Evidence: 36 tool calls, all in `host/transcripts/*cand-0002*/subagents/`; `isolation/diag_round2_scripts/`.
Effect: the champion descends from round 2; know-how from answers may be in it. Disclosed: #804 update 1, plan F14.
### F21. Optimizer subagents on Opus 5.5 (INVALIDATES the same-model claim)
Evidence: models table above; `reproduce/models.json`. Cause: inherited `CLAUDE_CODE_SUBAGENT_MODEL`.
Effect: cap-evolve had a stronger model in its diagnosis than ALTK-Evolve. Disclosed: #804 correction 2026-10-19, plan F21.
### F15. Guard race lost 3 optimizer calls (QUALIFIES)
Evidence: `events.jsonl` (3 `evaluate_error`), guard log. ≈$15 spent on unscored candidates. Disclosed: #804 update 1.
### F1, F2, F13, F16: harness gaps found and closed, wall-cap retry, release-wide canary (INFO). Disclosed in the plan.

## Known gaps
- R1's adapter code is reconstructed, not committed. The rebuilt v3 is byte-identical to the run's copy; v1/v2 are replayed from the transcript.
- The RITS backend build of the agent model cannot be seen by the client.

## Open decisions (for the owner)
- None for this run: it is already discarded.
"""


def r2():
    return HEAD.format(name=R2, ts=TS, commit=COMMIT, status="qualified",
                       why="clean, but ran in its reduced retrieval mode (full playbook infeasible), and its optimizer cost is an estimate") + f"""
## Summary
| check | result | severity |
|---|---|---|
| A1 answer/gold access | no shell, no file access: 1,031 litellm calls on trajectories only; store scan 0 hits | PASS |
| A2 test access | 0 test-id hits in the ALTK store and outputs; test retrieval blocks built from instruction text only | PASS |
| A3–A5 | n/a (in-process library, no agent with a shell) | PASS |
| A6 agent under test | `fs_probe` = 0 in all altk episodes (both windows) | PASS |
| B1 models as used | guideline/consolidation model `anthropic/aws/claude-sonnet-5-5` in 1,031 of 1,031 calls (`altk/optimizer_usage.jsonl`) | PASS |
| B2 intent vs actual | see table; 2 deviations (gateway shims F5, reduced mode F11) | QUALIFIES |
| B3 budgets | 147 search episodes, 3.81M optimizer tokens, ≈$18.04 estimated, vs cap-evolve 1,029 / 47.5M / $67.84 | QUALIFIES (unmatched, disclosed) |
| B4 one window | scored with seed and cape-hc in window 1; **byte-identical** artifact re-scored in window 2 (tree hash `b2b37037…` both times) | PASS |
| B5 drift | identical artifact: TGC 41.1 (window 1) vs 47.3 (window 2), pooled 44.2 | INFO |
| C1 splits | mined on official train (90), dose on official dev (57), scored on test_normal | PASS |
| C3 infra errors | 0; 2 of 90 trajectories failed inside the library's conflict resolution (logged, skipped) | INFO |
| C8 feasibility | full playbook 1,715 guidelines / 402,775 chars ≈ 83K tokens > 40K context → infeasible; retrieval dose used (F11) | **QUALIFIES** |
| D1–D8 completeness | 0 missing of 182 source files; store, mining, renders, 57 dev rollouts; posts; metrics_full; 0 secret hits | PASS |
| E reproducibility | ALTK venv freeze (Python 3.12.15, altk-evolve 1.3.0, litellm 1.105.0, torch 2.14.1+cpu, sentence-transformers 6.1.0); embedding model revision `1110a243…` | PASS |
| F published claims | "optimizer Sonnet 5.5": correct for this arm | PASS |

## Intent versus actual (B2)
| item | intended | actual | match? |
|---|---|---|---|
| version | ALTK-Evolve v1.3.0 (D4) | v1.3.0 (`703d033`) | yes |
| optimizer model | `aws/claude-sonnet-5-5` via litellm (§5.3) | `anthropic/aws/claude-sonnet-5-5` ×1,031 | yes |
| gateway access | wrapper adds base URL/headers (§5.3) | as intended **plus** `supports_response_schema=False` shim, because the gateway rejects forced `tool_choice` (F5) | qualified |
| mining | standard mode, segmentation on, 8 in parallel, lossless consolidation 0.80 | same; 88/90 mined, 1,867 → 1,715 guidelines, support conserved | yes |
| dose selection | full vs retrieval on dev, higher TGC (§8) | full infeasible (lint); retrieval chosen as the only feasible dose (dev 0.456) | **no** (F11) |
| embedding model | `all-MiniLM-L6-v2` | same, revision `1110a243…` | yes |
| cost accounting | exact tokens (§14) | tokens exact; USD **not reported** by litellm → estimated at list price | qualified |
{COMMON_ENV}
## Findings
### F11. Full playbook infeasible; retrieval dose only (QUALIFIES). Disclosed: #804 update 1, summary page.
### F5. Structured-output shim for the gateway (INFO). Library unmodified. Disclosed: plan F5.
### F12. Lossless consolidation is slow (53 min, 282 sequential calls) (INFO).
### Cost is an estimate (QUALIFIES): $18.04 = 2.50M in × $2/M + 1.30M out × $10/M (Sonnet 5.5 list price).

## Known gaps
- Exact optimizer USD (not reported by the gateway through litellm).

## Open decisions (for the owner)
- None.
"""


def r3():
    return HEAD.format(name=R3, ts=TS, commit=COMMIT, status="qualified — same-model claim INVALID (pending owner decision)",
                       why="attempt 2 is clean of answers, generators and test data, but its optimizer subagents ran on Opus 5.5 (B1) and it read app source (A4)") + f"""
## Summary
| check | attempt 1 `cape_hc_s1` | attempt 2 `cape_hc_s2` (scored) | severity |
|---|---|---|---|
| A1 answer/gold access | round 1 read the **task generators** of 6 train/dev scenarios (solution and evaluation logic), 5 tool calls (F19) | 0 of 566 tool calls touch answers, solutions, grader or generators | attempt 1 **INVALIDATES** · attempt 2 PASS |
| A2 test access | 0 test-id hits | 0 test-id hits | PASS |
| A3 copies | none | none (`/tmp/diag` hidden by the wrapper) | PASS |
| A4 beyond intended context | (generators, above) | rounds 4–6 read AppWorld **app implementation** source (`src/appworld/apps/*/apis.py`, `models.py`): environment code shared by all tasks (F20) | attempt 2 **QUALIFIES** |
| A5 isolation mechanism | namespace wrapper, allowlist = whole AppWorld clone (generators visible); 6/6 calls through the wrapper; A9 passed (0/5 secrets) | wrapper allowlist = `appworld/src` + `experiments`; 6/6 calls through the wrapper (guard log); A9 passed (0/6 secrets, incl. the generator dir); Claude Code sandbox cannot start in this container (F17) | QUALIFIES (allowlist too wide for app source) |
| A6 agent under test | — | `fs_probe` = 0 in all 1,008 window-2 episodes | PASS |
| B1 models as used | main Sonnet 5.5; subagents Opus 5.5 (+2 Haiku 4.5) | main Sonnet 5.5; **subagents Opus 5.5 in rounds 1, 4, 6** (round 4 = champion) | **INVALIDATES** (same-model claim vs ALTK) |
| B2 intent vs actual | see table | see table | QUALIFIES |
| B3 budgets | 882 episodes, $44.23 | 882 episodes, $54.16 (37.5M tokens) vs ALTK 147 / ≈$18 | QUALIFIES |
| B4 one window | — | window 2 scores cape-hc (attempt 2), seed and altk together; seed and altk byte-identical to window 1 | PASS |
| B5 drift | — | identical seed 35.1 → 31.5, altk 41.1 → 47.3; the cape − altk gap is +9.8 [+1.2, +18.5] | INFO (gap near drift size) |
| C1 splits | same as R1 | same as R1 | PASS |
| C2 search vs held-out | val 0.769 (fit) | val 0.789 (fit) vs test TGC 0.571 | INFO |
| C3 infra errors | 0 | 0 in search; window 2: 0 infra errors, 0 missing cells | PASS |
| C5 interruptions | none | none | PASS |
| C6 gate decisions | r1 accept; r2–r6 reject | r1, r3, r4 accept; r2, r5, r6 reject (each consistent with Δ vs SE) | PASS |
| C7 determinism | — | trials disagree on 38/168 (seed), 32/168 (cape-hc), 51/168 (altk) tasks | INFO |
| D completeness | 0 missing (5,147 source files for the run); LEDGER ×12, JOURNAL ×26, 2,062 rollouts; posts 20 + full thread; metrics_full per attempt; 1 symlink listed; tools load both copies; 0 secret hits | | PASS |
| E reproducibility | commit `95433f3`, wrapper at `95433f3` | commit `95433f3`, wrapper at `ec30d13` (read at call time); bundle verifies | PASS |
| F published claims | — | "optimizer Sonnet 5.5 for both methods" contradicted (B1); "fix-clean" folder name overstates (B1, A4) | **corrected** on #804; folder name pending |

## Intent versus actual (B2)
| item | intended | actual | match? |
|---|---|---|---|
| optimizer main loop | `aws/claude-sonnet-5-5` | Sonnet 5.5 in all 12 sessions | yes |
| optimizer subagents | Sonnet 5.5 (implied) | Opus 5.5 (tables below) | **no** |
| iterations | 6 | 6 scored, each attempt | yes |
| gate / trials / caps | paired k = 1.0, 1 trial, $15/iter, $120 | same; no cap hit | yes |
| baseline | reused from R1, scored before any optimizer call (fix plan §3) | `baseline_reused` 0.361 | yes |
| isolation | answers out of reach from round 1 (fix plan §1) | attempt 1: generators reachable (F19); attempt 2: answers, generators, test hidden, app source reachable (F20) | attempt 2 qualified |
| final window | all three arms together, seed/altk unchanged (fix plan §2) | same; tree hashes equal | yes |
{COMMON_ENV}
### Optimizer models by role: attempt 1 (assistant messages; output tokens)
| role | model | messages | output tokens |
|---|---|---|---|
{models_rows("cape_hc_s1")}

### Optimizer models by role: attempt 2, scored
| role | model | messages | output tokens |
|---|---|---|---|
{models_rows("cape_hc_s2")}

## Findings
### F21. Subagents on Opus 5.5 in the scored attempt (INVALIDATES the same-model claim)
Evidence: tables above; 8 Opus subagents in rounds 1, 4, 6; 0 subagent edits to candidate files (the main loop wrote all 5).
Effect: cap-evolve's diagnosis used a stronger model than ALTK-Evolve's optimizer. Disclosed: #804 correction 2026-10-19.
### F19. Attempt 1 read task generators (INVALIDATES attempt 1). Discarded. Disclosed: #804 update 13.
### F20. Attempt 2 read app implementation source (QUALIFIES). Disclosed: #804 update 20.
### F17. Claude Code's sandbox cannot start here (INFO); the namespace wrapper was used instead.

## Known gaps
- The RITS backend build of the agent model cannot be seen.

## Open decisions (for the owner)
- Does F21 invalidate the scored result? If yes: rename this folder (status `invalid` instead of `fix-clean`),
  update the summary page, and decide on a re-run with `CLAUDE_CODE_SUBAGENT_MODEL=aws/claude-sonnet-5-5` and
  AppWorld removed from the wrapper's allowlist.
"""


for name, fn in ((R1, r1), (R2, r2), (R3, r3)):
    (B / name / f"SCAN_RESULTS_{TS}.md").write_text(fn())
    print("wrote", name[:60])
