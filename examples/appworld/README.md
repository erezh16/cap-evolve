# AppWorld smoke test: ACE vs the seed agent

Code for `docs/EVAL_SMOKE_TEST_ACE.md` (the plan; section numbers below refer to it). The live state is
the checkpoint ledger `docs/EVAL_SMOKE_TEST_ACE_STATUS.md`; resume with
`python3 -I examples/appworld/scripts/resume.py` (`--dry-run` prints the plan).

| path | role |
|---|---|
| `patches/appworld-extra-headers.patch` | §5.2: `extra_headers` / `extra_headers_env` in AppWorld's LM client, scrubbed from logs |
| `adapters/aw_agent.py` | `CapReActAgent` (memory slot, §6.1) and the one-episode worker (F1 hardening, F2 token cap) |
| `adapters/adapter.py` | episode runner and scorer (§7): seal, subprocess per episode, 30-min wall cap, infra retries |
| `adapters/lints.py` | memory cap in o200k_harmony tokens, per-bullet lint (§6.2, §8.3) |
| `seed_capability/` | the stock prompt (byte copy at `42b5bcf`), empty tools, empty memory |
| `ace/vendor/` | ACE files, unmodified (`VENDORED.md`) |
| `ace/prompts/` | our copies of ACE's Reflector / Curator prompts minus one phrase the gateway refuses (finding G2, `gateway-filter.diff`) |
| `ace/ace_llm.py` | Reflector / Curator / merge client to the gateway, every call logged |
| `ace/run_ace.py` | the ACE loop (§8.2–§8.4) with per-step checkpoints |
| `scripts/status_doc.py` | the only ledger writer: append (content filter), commit, push, heartbeat, abort |
| `scripts/pipeline.py`, `resume.py`, `build.py`, `status.py` | detached phase runner, resume, rebuild, PROGRESS.md |
| `scripts/window.py`, `dev_diag.py`, `final_window.py`, `freeze.py`, `scan_isolation.py`, `analyze.py` | P5–P9 |
| `scripts/make_splits.py`, `make_roots.py`, `awpaths.py` | B3, B4, shared paths |
| `scripts/check_*.py` | acceptance checks A1–A10 (§11) |
| `scripts/post_update.py` | interim progress comments on #804 |
