# Status ledger: AppWorld smoke test, ACE vs the seed agent

This is the checkpoint ledger of the evaluation planned in
[EVAL_SMOKE_TEST_ACE.md](EVAL_SMOKE_TEST_ACE.md) (section 10). It is cumulative: each checkpoint
appends one entry below the earlier ones, and no earlier entry is ever edited, reordered or deleted.
The last entry is the current state. After every checkpoint this file is committed and pushed to
branch `erezh-eval2-ace`.

- **Resume:** `python3 -I examples/appworld/scripts/resume.py` (`--dry-run` to only print the plan).
  It reads the `json` block of the last entry (plan section 10.4).
- **Detail records** behind each entry are in `AW_STATE=/workspace/aw_eval_ace/`, referenced by sha256.
  They are not in git.
- **Content rules:** this file is published by every push. It holds no secrets, no gold values, no task
  ids, no task or supervisor text, no trajectory text and no playbook text. Units are named by phase
  and index only.
- **Cadence:** a result is checkpointed at once (results that come faster than every 5 minutes are
  coalesced into one entry per 5 minutes), plus a heartbeat entry whenever 25 minutes pass without one.

Phases: P0 decisions · P1 build · P2 acceptance · P3 ACE start · P4 ACE adaptation · P5 freeze ·
P6 dev diagnostic · P7 isolation scan · P8 final window · P9 analysis · P10 report.

---

## CP-0000 · 2026-10-14T12:49Z · P0 decisions · phase_start

Plan written: `docs/EVAL_SMOKE_TEST_ACE.md`. Nothing has run. The host is fresh: no `AW_STATE`, no
scratch, no `.env`, no `examples/appworld/` code.
Open decisions: D5 (playbook size rule), D6 (adaptation set), D7 (batch size), plus plan section 16
items 11 (push playbook snapshots?) and 13 (fork visibility).
Next: P0, record the user's answers to D5–D7.

```json
{"cp": 0, "prev_cp": null, "prev_commit": null, "utc": "2026-10-14T12:49:59Z",
 "kind": "phase_start", "phase": "P0", "done_through": null, "next": "P0/decisions",
 "counts": {"rollouts_counted": 0}, "spend": {"opt_in_tok": 0, "opt_out_tok": 0, "usd_proxy": 0},
 "artifacts": {}, "code": null, "open_decisions": ["D5", "D6", "D7", "issue-11", "issue-13"]}
```

## CP-0001 · 2026-10-14T13:27Z · P0 decisions · decision, phase_done

User answers to the plan review (verbatim summary): 1 accepted all recommendations (D5 (a), D6 (a),
D7 (a)); 2 install uv if missing and create a venv; 3 push whatever is needed to enable continuation
and minimize redo; 4 accepted (publishing at every checkpoint); 5 update the report as needed;
6 set the limit per the #804 opening post and the scope limits in EVAL_SMOKE_TEST.md §0 and §13;
7 accepted.
Plan updated accordingly: pushed continuation state `docs/EVAL_SMOKE_TEST_ACE_STATE/` (plan §10.3),
uv venv on /workspace (B2), memory cap `M_cap` = min(30,000, 34,000 − P_max − H_max) tokens, about 13K,
fixed in A8 (plan §6.2), optimizer cap 10M non-cache-read tokens, B = 900, report confounds paragraph (plan §12).
Nothing has run. Next: P1, build step B1.

```json
{"cp": 1, "prev_cp": 0, "prev_commit": "c06102be098202aa4db2797b493127355296a5f4", "utc": "2026-10-14T13:27:45Z",
 "kind": "decision", "phase": "P0", "done_through": "P0/decisions", "next": "P1/B1",
 "decisions": {"D5": "a", "D6": "a", "D7": "a", "memory_cap": "min(30000, 34000 - P_max - H_max) tokens, fixed in A8", "optimizer_cap_tokens": 10000000, "rollout_cap": 900},
 "counts": {"rollouts_counted": 0}, "spend": {"opt_in_tok": 0, "opt_out_tok": 0, "usd_proxy": 0},
 "artifacts": {}, "code": null, "open_decisions": []}
```

## CP-0002 · 2026-10-14T14:01Z · P0 decisions · decision

Plan revised at the user's request to align with the base plan, the design and #804 in every aspect
the user did not change (plan §16 item 8). Reverted self-introduced deviations; restored dropped base
and design rules (difficulty-count check, RITS probes in A2, new trial seeds on infra retries, soft
optimizer guard 8.5M, task-id lint and lint of merged bullets, A7 transcript scan); fixed counts,
times, paths and references; phases P0–P10 now defined in plan §10. Per-task final-window outcomes
are not pushed (content rules, plan §10.2); a host loss during P8 restarts the final window.
Note on CP-0000: plan §16 items 11 and 13 cited there are now items 3 and 4.
Nothing has run. Next: P1, build step B1.

```json
{"cp": 2, "prev_cp": 1, "prev_commit": "275da6860575672272664092aa48a106513bb79b", "utc": "2026-10-14T14:01:08Z",
 "kind": "decision", "phase": "P0", "done_through": "P0/decisions", "next": "P1/B1",
 "decisions": {"plan_alignment": "plan §16 item 8", "optimizer_guard_tokens": {"soft": 8500000, "hard": 10000000}, "final_cells_pushed": false},
 "counts": {"rollouts_counted": 0}, "spend": {"opt_in_tok": 0, "opt_out_tok": 0, "usd_proxy": 0},
 "artifacts": {}, "code": null, "open_decisions": []}
```

## CP-0001 · 2026-10-14T14:46Z · P1 build · decision

User instruction (2026-10-14, verbatim): "Be sure to post updates periodically to issue 804 and not just wait for the final results".
Applied: interim progress comments on skillberry-ai/cap-evolve#804 at milestones (build done, acceptance done, about every 15 ACE steps, freeze and dev diagnostic, final-window progress, any blocker), each recorded in a ledger entry with its URL. Content rules of plan §10.2 apply to every comment (counts only; no ids, task text or per-task test outcome). The final results comment (P10) is still posted once.
Execution started: P1 build, AW_HOME=/workspace/aw_eval_ace. .env is not present yet (B7, to be supplied by the user before A2).
Next: P1/B1.

```json
{"cp": 1, "prev_cp": 2, "prev_commit": "d460d9700755e0e6fc3f160b6eb0b429a86ed281", "utc": "2026-10-14T14:46:46Z", "kind": "decision", "phase": "P1", "done_through": "P0/decisions", "next": "P1/B1", "counts": {"rollouts_counted": 0}, "spend": {"opt_in_tok": 0, "opt_out_tok": 0, "usd_proxy": 0}, "artifacts": {}, "code": null, "open_decisions": [], "decisions": {"issue_804_interim_updates": true}}
```

## CP-0004 · 2026-10-14T14:49Z · P1 build · repair

Repair: the entry above headed "CP-0001 · 2026-10-14T14:46Z · P1 build · decision" (json `cp`: 1) is the fourth entry of this ledger and should have been numbered **CP-0003**. Cause: an off-by-one slice in the ledger writer's header parser (`status_doc.py`), now fixed; the writer now numbers entries by their count and refuses a non-increasing number. The entry is left unedited (append-only rule); its content stands. This entry is CP-0004.
Next: P1/B1.

```json
{"cp": 4, "prev_cp": 1, "prev_commit": "cbfb164442379f3ee5026738071938ec0a942644", "utc": "2026-10-14T14:49:01Z", "kind": "repair", "phase": "P1", "done_through": "P0/decisions", "next": "P1/B1", "counts": {"rollouts_counted": 0}, "spend": {"opt_in_tok": 0, "opt_out_tok": 0, "usd_proxy": 0}, "artifacts": {}, "code": "cbfb164442379f3ee5026738071938ec0a942644", "open_decisions": []}
```

## CP-0005 · 2026-10-14T14:49Z · P1 build · result

B1 done: StonyBrookNLP/appworld cloned at 42b5bcf3 into AW_BUILD, git lfs pull (4 LFS files), patch `appworld-extra-headers.patch` applied (17 added lines in `experiments/code/simplified/language_model.py`: `extra_headers` forwarding, `extra_headers_env`, both scrubbed from logged calls). Patch and git-diff sha256 in manifest.json.
Also: uv 0.13.0 installed at ~/.local/bin/uv (B2 started: venv-aw with CPython 3.11.2, CPU torch installing).
Next: P1/B2.

```json
{"cp": 5, "prev_cp": 4, "prev_commit": "2a7044e668fe4c4a2d99cfa5d0ecbd16b45cb041", "utc": "2026-10-14T14:49:43Z", "kind": "result", "phase": "P1", "done_through": "P1/B1", "next": "P1/B2", "counts": {"rollouts_counted": 0}, "spend": {"opt_in_tok": 0, "opt_out_tok": 0, "usd_proxy": 0}, "artifacts": {"STATE/manifest.json": "82d7e68e86b8ff65a93f822feefd8d5355715729c690520076b8dd9e0a19fe8d"}, "code": "2a7044e668fe4c4a2d99cfa5d0ecbd16b45cb041", "open_decisions": []}
```

## CP-0006 · 2026-10-14T14:52Z · P1 build · result

B2 done: uv 0.13.0 (installed, was missing); venv-aw with CPython 3.11.2 (system interpreter, found by uv); CPU torch 2.14.1 first, then appworld + appworld-agents (-e, 42b5bcf), pydantic 2.12.5, fastapi 0.143.1, litellm 1.80.0, cap-evolve core (-e), sentence-transformers, faiss-cpu, and tiktoken (needed for the token counts of plan §6.2; not in the B2 list, recorded in manifest). `appworld install --repo` done. `uv pip freeze` (129 packages) pushed as `STATE/venv_freeze.txt`, sha256 in manifest.
Next: P1/B3 data download and count checks.

```json
{"cp": 6, "prev_cp": 5, "prev_commit": "1c4ff1e7ab8ff7ca0342e3dd099274490637a2c4", "utc": "2026-10-14T14:52:43Z", "kind": "result", "phase": "P1", "done_through": "P1/B2", "next": "P1/B3", "counts": {"rollouts_counted": 0}, "spend": {"opt_in_tok": 0, "opt_out_tok": 0, "usd_proxy": 0}, "artifacts": {"STATE/manifest.json": "77ff293eccd21fcaccb225709edd2b8027953f072439f56abf52a0e25b5e9052", "STATE/venv_freeze.txt": "9a267f5f8fb43e32fc42a0a4b145b598c2b3c5abd268112c0ca13e073d939283"}, "code": "2a7044e668fe4c4a2d99cfa5d0ecbd16b45cb041", "open_decisions": []}
```

## CP-0007 · 2026-10-14T14:57Z · P1 build · result

B3 done: `appworld download data --root root_full` (198 MB). Split counts 90 / 57 / 168 / 417 via `load_task_ids` (identical to the split files), pairwise disjoint, train and dev share no scenario; scenarios 30 / 19 / 56 / 139; difficulty levels 1/2/3: train 36/36/18, dev 30/24/3, test_normal 57/48/63, test_challenge 72/150/195. All match design §2. Data tree and split-file sha256 in manifest.json.
Local lint cache built (AW_STATE, not pushed): 732 task ids, 1,528 train/dev instruction 8-grams, 249 train/dev supervisor contacts. The publishing filter of plan §10.2 is now fully active.
Next: P1/B4 root_opt and lock root_full.

```json
{"cp": 7, "prev_cp": 6, "prev_commit": "2f3ac2b1527423d2f7054b2df09e8c2047ff532d", "utc": "2026-10-14T14:57:13Z", "kind": "result", "phase": "P1", "done_through": "P1/B3", "next": "P1/B4", "counts": {"rollouts_counted": 0}, "spend": {"opt_in_tok": 0, "opt_out_tok": 0, "usd_proxy": 0}, "artifacts": {"STATE/manifest.json": "bbe7c9e4095ffc40fe79761a3a8c0cf9a9cf0d55a9b1d87ee29a29aed807765c"}, "code": "2a7044e668fe4c4a2d99cfa5d0ecbd16b45cb041", "open_decisions": []}
```

## CP-0008 · 2026-10-14T14:59Z · P1 build · result

B4 done: `make_roots.py` built root_opt = api_docs, base_dbs, 147 train + dev task dirs and `_base_` (148 dirs), datasets `train.txt` and `dev.txt` only. grep for the 585 test ids under root_opt: 0 hits (file contents and dir names). root_full is `chmod 000` (verified: unreadable) until P8. root_opt tree sha256 in manifest.json.
Next: P1/B5 ACE clones, vendoring, HF model.

```json
{"cp": 8, "prev_cp": 7, "prev_commit": "c37e6a38342f2cab42b579e95347adde119c5d9a", "utc": "2026-10-14T14:59:04Z", "kind": "result", "phase": "P1", "done_through": "P1/B4", "next": "P1/B5", "counts": {"rollouts_counted": 0}, "spend": {"opt_in_tok": 0, "opt_out_tok": 0, "usd_proxy": 0}, "artifacts": {"STATE/manifest.json": "8cf33d27302f78a833049ed150426693a214a587c74aed900ce5a8a22d67819c"}, "code": "c37e6a38342f2cab42b579e95347adde119c5d9a", "open_decisions": []}
```

## CP-0009 · 2026-10-14T15:05Z · P1 build · result

B5 done: `ace` cloned at 82709de0 and `ace-appworld` at 928e8687 (the D4 pins) into AW_BUILD/ace-src. Vendored unmodified into `examples/appworld/ace/vendor/`: the no-GT reflector and curator prompts, the initial playbook (1,469 chars, 8 bullets, next id 9), `playbook.py`, `utils.py`, `bulletpoint_analyzer.py`, and the Apache-2.0 LICENSE; `VENDORED.md` lists source path, commit and sha256 of each. `all-mpnet-base-v2` pre-fetched into HF_HOME (419 MB); sentence-transformers + faiss available.
Port notes recorded for run_ace.py (from `adaptation_react.py` / `adaptation_agent.py`): Reflector prompt filled with `.replace` (its JSON examples keep literal double braces), Curator with `.format`; a non-ADD operation makes ACE skip the whole update, an off-whitelist section skips that op only; in the no-GT path Reflector + Curator run only when the episode ends by `task_completed()` or the cost limit, not at the step cap.
Next: P1/B6 code.

```json
{"cp": 9, "prev_cp": 8, "prev_commit": "a0e0b0af778427c73f9ac702034b7816ba203650", "utc": "2026-10-14T15:05:17Z", "kind": "result", "phase": "P1", "done_through": "P1/B5", "next": "P1/B6", "counts": {"rollouts_counted": 0}, "spend": {"opt_in_tok": 0, "opt_out_tok": 0, "usd_proxy": 0}, "artifacts": {"STATE/manifest.json": "97240f02e49a4d03a677d819edd3925e7ac7e79f933abf381e89085bb5eb2dc1"}, "code": "a0e0b0af778427c73f9ac702034b7816ba203650", "open_decisions": []}
```

## CP-0010 · 2026-10-14T15:26Z · P2 acceptance · result

A1 passed (run early: it needs no RITS; B6 code continues, B7 .env still missing): `aws/claude-sonnet-5-5` answers through `ace/ace_llm.py` (gateway header sent, no `response_format`, no tools). On a toy message list (no task data) one Reflector call returned JSON with all 5 fields, one Curator call returned valid ACE JSON (2 ADD ops, 1 off-whitelist op skipped as in ACE). Usage 6.7K in / 1.9K out tokens.
**Finding G1:** the gateway rejects `temperature` for this model (HTTP 400 "`temperature` is deprecated for this model"). The plan's temperature 0 for Reflector / Curator / merge cannot be sent; the client omits it (model default). Deterministic 4xx errors other than 429 are no longer retried 50 times.
**Finding G2 (plan §15 risk, A7 remedy):** with ACE's prompts verbatim, both the Reflector and the Curator response end with `finish_reason: refusal` (Reflector cut after ~100 tokens, Curator empty), reproducibly. A 4-variant diagnosis isolated the trigger: the phrase "chain of thought / reasoning / thinking process, " in the description of the `reasoning` field (2× per prompt). Removing only that phrase fixes it (`stop`, full JSON); renaming the key alone does not. Applied: our copies `examples/appworld/ace/prompts/` drop the phrase (4 lines, diff `ace/prompts/gateway-filter.diff`); JSON field names and every other byte are unchanged; `ace/vendor/` stays unmodified. A7 re-checks this on real prompts. Both findings are deviations to be listed in the report.
Next: P1/B6 code, then P1/B7 (.env from the user).

```json
{"cp": 10, "prev_cp": 9, "prev_commit": "a9d6fd3b8282801889c6ae4d4fde70dc41cd9949", "utc": "2026-10-14T15:26:44Z", "kind": "result", "phase": "P2", "done_through": "P2/A1", "next": "P1/B6", "counts": {"rollouts_counted": 0}, "spend": {"opt_in_tok": 0, "opt_out_tok": 0, "usd_proxy": 0}, "artifacts": {}, "code": "a9d6fd3b8282801889c6ae4d4fde70dc41cd9949", "open_decisions": [], "findings": {"G1": "temperature rejected by gateway for OPT_MODEL; omitted", "G2": "CoT phrase in reasoning-field description triggers refusal; phrase removed in our prompt copies"}}
```

## CP-0011 · 2026-10-14T15:28Z · P2 interim #804 · posted

Interim update 1 posted on #804: https://github.com/skillberry-ai/cap-evolve/issues/804#issuecomment-6171928617 (build done, two optimizer findings).

```json
{"cp": 11, "prev_cp": 10, "prev_commit": "89253d9d368632aa55c3db0ee0cdba5be5f97bd2", "utc": "2026-10-14T15:28:15Z", "kind": "posted", "phase": "P2", "done_through": "P2/A1", "next": "P1/B6", "counts": {"rollouts_counted": 0}, "spend": {"opt_in_tok": 0, "opt_out_tok": 0, "usd_proxy": 0}, "artifacts": {}, "code": "89253d9d368632aa55c3db0ee0cdba5be5f97bd2", "open_decisions": [], "post": "interim-1", "url": "https://github.com/skillberry-ai/cap-evolve/issues/804#issuecomment-6171928617"}
```

## CP-0012 · 2026-10-14T15:50Z · P2 acceptance · result

A6 passed: `tasks("train")` equals `train.txt` exactly (90 ids, same order as `load_task_ids`); `tasks("test_normal")` and a test id are refused by the seal without `AW_ALLOW_SEALED=final-eval-only`.
Next: P1/B6 (code), B7 (.env).

```json
{"cp": 12, "prev_cp": 11, "prev_commit": "5472b0b6470a69822000b0ef56f4d1f36e467462", "utc": "2026-10-14T15:50:25Z", "kind": "result", "phase": "P2", "done_through": "P2/A6", "next": "P1/B6", "counts": {"rollouts_counted": 0}, "spend": {"opt_in_tok": 0, "opt_out_tok": 0, "usd_proxy": 0}, "artifacts": {}, "code": "5472b0b6470a69822000b0ef56f4d1f36e467462", "open_decisions": []}
```

## CP-0013 · 2026-10-14T15:50Z · P2 acceptance · result

A3 passed (no model call; one dev task world): with F1's hardening (`os`, `pathlib`, `io`, `shutil`, `glob` removed from AppWorld's import allowlist) `import os`, `open(answer.json)`, a `pathlib` read and an `io.open` read all fail. Without the hardening, for reference, `import os` and the `pathlib` read succeed (base finding F1 reproduced at 42b5bcf). root_opt: 148 task dirs, train/dev split files only, 0 test-id hits. root_full unreadable.
Next: P1/B6, B7.

```json
{"cp": 13, "prev_cp": 12, "prev_commit": "3e5bba131e128f2f87481b1ab8d3932309ec4d34", "utc": "2026-10-14T15:50:29Z", "kind": "result", "phase": "P2", "done_through": "P2/A3", "next": "P1/B6", "counts": {"rollouts_counted": 0}, "spend": {"opt_in_tok": 0, "opt_out_tok": 0, "usd_proxy": 0}, "artifacts": {}, "code": "3e5bba131e128f2f87481b1ab8d3932309ec4d34", "open_decisions": []}
```

## CP-0014 · 2026-10-14T15:50Z · P2 acceptance · result

A5 passed: on a train task the released compiled solution scores reward 1 (twice, identical), a no-op scores 0; the records hold no evaluator `trace`.
Also A4 (part, no model call): the seed's first request (23 messages) is byte-identical to the stock agent's; a playbook lands in the final USER message under the memory heading, before `My name is:`. The M_cap refusal part of A4 waits for A8.
Next: P1/B6, B7.

```json
{"cp": 14, "prev_cp": 13, "prev_commit": "ed852d660069f32bc1b2bac9267a19b0a0ad559e", "utc": "2026-10-14T15:50:32Z", "kind": "result", "phase": "P2", "done_through": "P2/A5", "next": "P1/B6", "counts": {"rollouts_counted": 0}, "spend": {"opt_in_tok": 0, "opt_out_tok": 0, "usd_proxy": 0}, "artifacts": {}, "code": "3e5bba131e128f2f87481b1ab8d3932309ec4d34", "open_decisions": []}
```

## CP-0015 · 2026-10-14T16:00Z · P1 build · result

B6 done: the code of plan §4.1 is written and committed under `examples/appworld/` (README lists the files): episode worker and runner, lints, ACE loop with the ported Reflector / Curator logic and the D5 rule, optimizer client, ledger writer, phase pipeline, resume, rebuild, status page, windows (P6, P8), freeze, isolation scan, analysis, interim-post helper, acceptance checks A1–A10.
Unit checks passed so far: A1 (optimizer), A7 offline part (ported prompts byte-identical to ACE's own `reflector_call` / `curator_call` on a fixed message list, with both the vendored and our filtered templates; ACE's validation semantics; planted 8-gram `lint_drop`; D5 on a synthetic 1.3·M_cap playbook: 628 → 7 bullets, 6 merge calls), A3, A4 (prompt part), A5, A6. The episode loop's model path is checked by A2 and A8, which need B7.
Fixes made while writing: `resume.py` resets uncommitted pushed-state files together with a torn ledger tail (they are regenerated from local records).
Next: P1/B7: the user puts `.env` (`RITS_URL`, `RITS_API_KET`) in the worktree; then A2, A8, A4 (cap part), A7 loop, A9, A10.

```json
{"cp": 15, "prev_cp": 14, "prev_commit": "b7fab33381907f51cbc217582b82614abef19e67", "utc": "2026-10-14T16:00:36Z", "kind": "result", "phase": "P1", "done_through": "P1/B6", "next": "P1/B7", "counts": {"rollouts_counted": 0}, "spend": {"opt_in_tok": 0, "opt_out_tok": 0, "usd_proxy": 0}, "artifacts": {}, "code": "3e5bba131e128f2f87481b1ab8d3932309ec4d34", "open_decisions": []}
```

## CP-0016 · 2026-10-14T16:25Z · P1 heartbeat · heartbeat

No checkpoint for 25 min. Phase P1, last result: P1/B6.
Runner: no runner. Last log line: ` + typing-extensions==4.16.0`.
Next: P1/B7.

```json
{"cp": 16, "prev_cp": 15, "prev_commit": "57f63c9ed9516f28843ac69b4248424a1c21b6a5", "utc": "2026-10-14T16:25:41Z", "kind": "heartbeat", "phase": "P1", "done_through": "P1/B6", "next": "P1/B7", "counts": {"rollouts_counted": 0}, "spend": {"opt_in_tok": 0, "opt_out_tok": 0, "usd_proxy": 0}, "artifacts": {}, "code": "57f63c9ed9516f28843ac69b4248424a1c21b6a5", "open_decisions": [], "runner": "none"}
```

## CP-0017 · 2026-10-14T16:50Z · P1 heartbeat · heartbeat

No checkpoint for 25 min. Phase P1, last result: P1/B6.
Runner: no runner. Last log line: ` + typing-extensions==4.16.0`.
Next: P1/B7.

```json
{"cp": 17, "prev_cp": 16, "prev_commit": "dfb8b8901e61376dea12ef2b0ce708ce28159e63", "utc": "2026-10-14T16:50:44Z", "kind": "heartbeat", "phase": "P1", "done_through": "P1/B6", "next": "P1/B7", "counts": {"rollouts_counted": 0}, "spend": {"opt_in_tok": 0, "opt_out_tok": 0, "usd_proxy": 0}, "artifacts": {}, "code": "57f63c9ed9516f28843ac69b4248424a1c21b6a5", "open_decisions": [], "runner": "none"}
```
