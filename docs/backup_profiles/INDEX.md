# Backup profiles: index

One profile per benchmark id. A profile holds every benchmark-specific fact that the Box backup
procedure (`docs/BACKUP_BOX.md`) needs. Its format, and how to create or correct one, are in
`docs/BACKUP_BOX.md` Appendix B.

**Lookup.** Find the run's bench name (CI bench, record `bench`, repo directory or run-dir name) in
the table below. It gives the profile file. Values shared by every benchmark are in
[`_core.md`](_core.md). A bench name that is not in the table needs a new profile
(`docs/BACKUP_BOX.md` §4).

**Status.** Every profile listed here is a draft. Each was written from the benchmark's adapter,
configs, CI tiers and committed results (for retired benchmarks, from their code at the last commit
that had it, and from their records). The first backup (20261113T135349Z, git and GitHub-API sources only) checked the profiles marked below.
The first backup of each benchmark does that check (`docs/BACKUP_BOX.md` §4), and records the result
in the Status column. Paths are relative to the cap-evolve repo unless stated otherwise.

| Bench name (CI, records, run dirs) | Profile |
|---|---|
| `appworld` | [`appworld`](appworld.md) |
| `tau2` | [`tau2-airline`](tau2-airline.md) |
| `tau2_sierra`, `tau2_sierra_blackbox`, `tau2_blackbox`, `sierra`, `direct`, `blackbox` (run-dir names under the sierra example) | [`tau2-sierra-airline`](tau2-sierra-airline.md) |
| `skillsbench` | [`skillsbench`](skillsbench.md) |
| `spreadsheetbench` | [`spreadsheetbench`](spreadsheetbench.md) |
| `swe_bench` (local template) | [`swebench-lite`](swebench-lite.md) |
| `swebench` (CI), `swebench-verified` | [`swebench-verified-harbor`](swebench-verified-harbor.md) |
| any other Harbor dataset | [`harbor-<dataset>`](swebench-verified-harbor.md) |
| `rfe-creator`, `rfe_creator` | [`rfe-creator`](rfe-creator.md) |
| `parsec` | [`parsec-rca`](parsec-rca.md) |
| `toy` | [`toy`](toy.md) |
| `jsonl_litellm`, `huggingface_litellm` | [`generic-jsonl`, `generic-hf`](generic.md) |
| `tau2_custom_direct`, `tau2_custom_blackbox`, `tau2_custom_spa`, `skillberry_tau2_direct`, `skillberry_tau2_spa`, `spa` | [`tau2-custom-airline`](tau2-custom-airline.md) |
| `epic-creator` | [`epic-creator`](epic-creator.md) |
| `epic-decompose` | [`epic-decompose`](epic-decompose.md) |
| `rh-swebench`, `rh-swebench-v4` | [`rh-swebench`](rh-swebench.md) |

A bench name not in this table gets a new profile (`docs/BACKUP_BOX.md` §4) before its runs are captured.

| Profile | Status |
|---|---|
| [`appworld.md`](appworld.md) | draft, not yet checked against a real run |
| [`tau2-airline.md`](tau2-airline.md) | checked against `2026-10-13-tau2-airline-capevolve-15102fc-smoke-s0-gptoss120b-claudeopus48` (backup 20261113T135349Z), corrected |
| [`tau2-sierra-airline.md`](tau2-sierra-airline.md) | checked against `2026-10-13-tau2-sierra-airline-capevolve-none-blackbox-s0-claudehaiku45-claudeopus55` (backup 20261113T135349Z), corrected |
| [`skillsbench.md`](skillsbench.md) | checked against `2026-07-30-skillsbench-capevolve-762994d-smoke-s0-claudesonnet45-claudesonnet46` (backup 20261113T135349Z), corrected |
| [`spreadsheetbench.md`](spreadsheetbench.md) | checked against `2026-08-02-spreadsheetbench-capevolve-221df0b-full-s0-gpt5.5-claudeopus48` (backup 20261113T135349Z), corrected |
| [`swebench-lite.md`](swebench-lite.md) | draft, not yet checked against a real run |
| [`swebench-verified-harbor.md`](swebench-verified-harbor.md) | checked against `2026-10-08-swebench-verified-harbor-capevolve-none-full-s0.r200-none-none` (backup 20261113T135349Z), corrected |
| [`rfe-creator.md`](rfe-creator.md) | checked against `2026-09-15-rfe-creator-capevolve-none-local-s0-none-none` (backup 20261113T135349Z), corrected |
| [`parsec-rca.md`](parsec-rca.md) | checked against `2026-10-16-parsec-rca-capevolve-none-v6g2e1-s0-claudesonnet46-claudeopus5` (backup 20261113T135349Z) |
| [`toy.md`](toy.md) | checked against `2026-06-16-toy-capevolve-none-none-s0-none-none` (backup 20261113T135349Z) |
| [`generic.md`](generic.md) | checked against `2026-08-22-generic-capevolve-none-agentopt-s0-gptoss120b-none` (backup 20261113T135349Z), corrected |
| [`tau2-custom-airline.md`](tau2-custom-airline.md) | checked against `2026-09-29-tau2-custom-airline-capevolve-none-full-s0-none-none` (backup 20261113T135349Z), corrected |
| [`epic-creator.md`](epic-creator.md) | checked against `2026-10-28-epic-creator-capevolve-none-full-s0-none-none` (backup 20261113T135349Z), corrected |
| [`epic-decompose.md`](epic-decompose.md) | checked against `2026-10-13-epic-decompose-capevolve-none-full-s0-none-none` (backup 20261113T135349Z), corrected |
| [`rh-swebench.md`](rh-swebench.md) | checked against `2026-08-05-rh-swebench-capevolve-none-full-s0-none-none` (backup 20261113T135349Z), corrected |
