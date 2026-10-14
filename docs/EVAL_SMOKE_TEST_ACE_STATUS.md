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
