## Results: AppWorld smoke test, ACE vs the seed agent, gpt-oss-120b (held-out test_normal)

168 test_normal tasks / 56 scenarios × 2 trials per arm, one interleaved window, 0 missing cells. Plan `docs/EVAL_SMOKE_TEST_ACE.md`, ledger `docs/EVAL_SMOKE_TEST_ACE_STATUS.md` (branch `erezh-eval2-ace`, `erezh16` fork).

**Setup.** Agent under test (both arms): `openai/gpt-oss-120b-a100` on RITS, reasoning medium, temperature 0, AppWorld `42b5bcf` simplified ReAct code agent, stock prompt, 50 steps, 6,000 completion tokens per step. ACE (`ace@82709de0`, `ace-appworld@928e8687`): offline adaptation without ground truth, 1 epoch over the official `train` split (90 tasks, ACE's order), batch size 1, Generator = the common-harness agent, Reflector and Curator = `aws/claude-sonnet-5-5`; the playbook goes in the memory slot of the stock prompt. Memory cap M_cap = 13,500 tokens (measured, A8). Decisions: D1 Sonnet 5.5 optimizer; D2 AppWorld from source; D3 2 final trials; D4 the design's ACE pins; D5 (a) lazy dedup at the cap, `cap_drop` beyond it; D6 (a) adapt on train, dev as a diagnostic; D7 (a) batch size 1.

| arm | TGC | SGC | Δ TGC vs seed [95% CI] | Δ SGC vs seed [95% CI] |
|---|---|---|---|---|
| seed | 34.2 | 13.4 | — | — |
| ace | **64.0** | **46.4** | +29.8 [+21.4, +38.1] | +33.0 [+20.5, +45.5] |

CI: scenario-clustered paired bootstrap (56 clusters, 10,000 resamples). One contrast, one search seed: an artifact-level statement about this one ACE playbook.

**What this ACE is and is not.** This is ACE's released Reflector, Curator and playbook code, run under choices that differ from the paper's and from the colleagues' runs; any of them could explain the result as well as ACE itself could:
1. the common template (the stock AppWorld prompt with a memory slot), not ACE's 27K-character Generator prompt;
2. Sonnet 5.5 as Reflector and Curator, a stronger model than the target (the paper uses the target), and, because the gateway requires it, at the model's default temperature and with one phrase removed from both prompts (findings G1, G2 below);
3. 1 epoch and 1 reflection per task (the paper allows up to 5 of each);
4. the M_cap size rule (D5): 56 dedup runs, 135 `cap_drop` bullets;
5. the no-GT Reflector, which is never told whether a task passed;
6. 50 steps instead of ACE's 40.
A null or small result would be a result about *this configuration*, not evidence that ACE does not work; in the same way, the gain below is a result about this configuration (in particular a stronger optimizer model than the target, item 2), not a measurement of ACE as published.

**Side by side** (compared only as gains over each side's own no-memory baseline, design §9.2 rule 1; harness, template, Reflector model and epochs differ, so the levels are not comparable):

| source | baseline TGC / SGC | with ACE TGC / SGC | gain TGC / SGC |
|---|---|---|---|
| this smoke test (common harness, Sonnet 5.5 Reflector / Curator, 1 epoch, M_cap) | 34.2 / 13.4 | 64.0 / 46.4 | +29.8 / +33.0 |
| colleagues' gpt-oss-120b (no memory → ReAct + ACE) | 39.9 / 21.4 | 54.8 / 35.7 | +14.9 / +14.3 |
| ACE paper, gpt-oss-120b (ReAct → ACE offline, no GT) | 54.8 / 33.9 | 58.3 / 41.1 | +3.5 / +7.2 |

**By difficulty (TGC / SGC).**

| arm | Easy (57) | Medium (48) | Hard (63) |
|---|---|---|---|
| seed | 51.8 / 21.1 | 32.3 / 12.5 | 19.8 / 7.1 |
| ace | 87.7 / 78.9 | 69.8 / 46.9 | 38.1 / 16.7 |

**Cost.**

| item | seed | ace |
|---|---|---|
| target prompt tokens per task (mean) | 96,878 | 233,513 |
| target completion tokens per task (mean) | 6,173 | 4,887 |
| steps per task (mean) | 13 | 11.44 |
| step-cap hits / token-cap hits | 2 / 0 | 0 / 0 |
| context_exceeded | 0 | 0 |
| max prompt tokens | 19,764 | 32,828 |
| memory tokens per step | 0 | 13,430 |
| trials agreeing (both pass or both fail) | 73.2% | 80.4% |
| infra retries / missing cells | 0 / 0 | 0 / 0 |
| counted rollouts | 57 dev + 336 test | 90 train + 57 dev + 336 test |

Optimizer (ACE only): 8.39M input / 0.27M output non-cache-read tokens (≈ $19.50 at proxy list prices $2 / $10 per Mtok; cap 10M); calls: reflector 90, curator 90, merge 1; responses cut at max_tokens: 0; Curator invalid-JSON (update skipped): 0. Agent tokens are on RITS (no price; reported as unknown).

Dev diagnostic (search-time, 57 dev tasks × 1 trial, not a result): seed 38.6, ace 70.2 TGC; context_exceeded seed 0, ace 0.

**What changed (the ACE artifact).** pb_090: 82 bullets, 55,513 characters, 13,430 tokens (initial playbook: 8 bullets, 365 tokens; `identical_to_own_seed`: False). Bullets by section: strategies and hard rules 10; apis to use for specific information 16; useful code snippets and templates 9; common mistakes and correct strategies 18; problem-solving heuristics and workflows 2; verification checklist 11; others 16. Adaptation: 90 of 90 steps curated (episode terminations: completed 90); 18 bullets dropped by the per-bullet lint (task data such as supervisor phone numbers), 56 dedup runs, 135 `cap_drop` bullets. The playbook reached the cap at step 33 and did not change afterwards: from then on ACE's dedup at threshold 0.90 found almost no merges, so the later steps' bullets were all `cap_drop`ped; the artifact is the step-33 playbook. With it, ACE's longest prompt in the test window was 32,828 tokens (limit 34,000; 0 context overflows); ACE's agent reads about 2.4× the seed's prompt tokens per task. Training episodes passing during adaptation: 65 of 90 (search-time, not a result). Three example bullets:
- `[shr-00042]` When a task says 'reply/respond ... as per their request' (text message, email, etc.), FIRST read the incoming message from that contact to get the criteria (genre, director, count, etc.). Do this before building the reply. Never send an irreversible message (send_text_message, send_email, etc.) until you have seen both the request and the full source data. Sending an unfiltered 'everything' list …
- `[code-00010]` Full pagination template: `page_index=0; items=[]; while True: page=apis.spotify.show_playlist_library(access_token=tok, page_index=page_index, page_limit=20); if not page: break; items.extend(page); page_index+=1`. Use `while True` until an empty page, with no fixed cap such as `page_index < 10`. page_limit max is 20. Check that `page` is a list, since an error dict {'message':...} is truthy.
- `[vc-00037]` Before ANY irreversible account deletion (delete_account) after a backup/export, you must do a separate read-only step: call apis.file_system.show_file(file_path=..., access_token=fs_token) and print the first lines, the line count (unique songs + 1 header) and the header line, and compare them with the expected count. A 'File created.' message is not proof of correct content. Once the Spotify dat…

**Isolation.** Scan of all 182 optimizer calls, 451 step files and 91 playbook snapshots: 0 test ids, 0 `answer.json` / `ground_truth` mentions; agent `fs_probe` hits: adaptation and dev 0, final window 0. Test root locked until the final window; the optimizer has no tools.

**Resume history.** 189 ledger entries; aborts 0, resumes 1, restores 0, errors 1, repairs 6 (5 code fixes before any counted rollout; 1 correcting the P7 scan counts, a scanner false positive), heartbeats 29. The one error and resume: the optimizer gateway's shared team budget ran out at the step-54 Reflector call (HTTP 429 `budget_exceeded`); the run resumed about 8 h later from the saved episode, with no repeated episode or paid call. Wall time: adaptation 12.49 h including that stop (about 4.4 h running), dev diagnostic 0.46 h, final window 1.36 h.

**Deviations** (plan §13; new in execution):
- G1: the gateway rejects `temperature` for `aws/claude-sonnet-5-5`; Reflector, Curator and merge ran at the model default instead of ACE's 0.
- G2: ACE's Reflector and Curator prompts verbatim end every response with `finish_reason: refusal` on this gateway; the phrase "chain of thought / reasoning / thinking process," (4 lines) was removed from our copies; JSON fields unchanged.
- As in ACE's no-GT code, an episode that hit the step cap (or ended on an LM error) gets no Reflector / Curator call; that step leaves the playbook unchanged.
- From the base plan and the design (unchanged here): the common template; 50 steps; `max_completion_tokens` 6,000 with trimming; chat completions via `hosted_vllm` with reasoning not resent; `M_cap` instead of the design's 30,000 tokens; 2 trials and one window instead of the design's panel; no test_challenge.

**What the numbers cannot support:** one search seed, one method, no matched-budget comparison with other methods, no equivalence test (no TOST); the dev diagnostic and train pass rates are search-time numbers. No task text, ids, solutions or gold values are posted (AppWorld redistribution rule).
