# Vendored / derived files of the CE2 arms

| file | source | commit | source sha256 | derived sha256 |
|---|---|---|---|---|
| INSTRUCTIONS.template.md | cap-evolve-impr2 `templates/project/optimizer/INSTRUCTIONS.md` | 3db96a08ef77d7701f21771d389c6471a5d88344 | 84de4f00a5254c47f0627a9e753129375ce12d20ecdcbeeb0e266d6106de2fce | 220d3ea7f9c9eb72b26ae6a753ae055e02f767883f3ae4dddd4bf48af276ce14 |

Derivation (plan §9.4): byte copy of the pinned template with ONE inserted section, `## AppWorld facts for THIS
run`, immediately before `## PREPARATION:`. Its content is REST's block of that name
(`eval-rest:examples/appworld/cape_improve/INSTRUCTIONS.template.md`), unchanged, with one paragraph added first:
"**Objective score for this run.** ...". It states no K, no other arm, no REST and no result. No other line is changed
or removed: `docs/EVAL_APPWORLD_CE2_STATUS_STATE/ce2/instructions.diff` is the `diff -u` and shows insertions only.
Placeholders `{AW_LINT_PY}`, `{AW_LINTS}`, `{AW_LINT_CACHE}` are filled by `run_ce2.py setup` (the optimizer's
lint venv and copies of lints.py and the lint cache under /workspace/aw_ce2/opt/); every cap-evolve `{{…}}`
placeholder is kept for the harness. Both arms point `optimizer_instructions_file` at one rendered file,
/workspace/aw_ce2/state/ce2/INSTRUCTIONS.md.

Pin history: first derived from `8194578`; re-derived from `3db96a0` (2026-10-23, user decisions recorded in the
ledger). `3db96a0` = `8194578` + `a09e48d` + `3db96a0`: two wording fixes in the template's Self-check lines, both
"reward" -> "objective score" (lines 142 and 143). core/ and skills/ are byte-identical between 8194578 and 3db96a0.
