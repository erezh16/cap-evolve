# Vendored / derived files of the CE2 arms

| file | source | commit | source sha256 | derived sha256 |
|---|---|---|---|---|
| INSTRUCTIONS.template.md | cap-evolve-impr2 `templates/project/optimizer/INSTRUCTIONS.md` | 819457804eff4658a1582318e2b067562522d1a1 | df486563172cdab9cc3ceaa9d764f0ee35dfa08fb3e004fe79ae209ae86a9d36 | 30b22a6ed339a1bc61f875685677c2e9b08fb33de84ac9622cffa966fecb98b0 |

Derivation (plan §9.4): byte copy of the pinned template with ONE inserted section, `## AppWorld facts for THIS
run`, immediately before `## PREPARATION:`. Its content is REST's block of that name
(`eval-rest:examples/appworld/cape_improve/INSTRUCTIONS.template.md`), unchanged, with one paragraph added first:
"**Objective score for this run.** ...". It states no K, no other arm, no REST and no result. No other line is changed
or removed: `docs/EVAL_APPWORLD_CE2_STATUS_STATE/ce2/instructions.diff` is the `diff -u` and shows insertions only.
Placeholders `{AW_LINT_PY}`, `{AW_LINTS}`, `{AW_LINT_CACHE}` are filled by `run_ce2.py setup` (the optimizer's
lint venv and copies of lints.py and the lint cache under /workspace/aw_ce2/opt/); every cap-evolve `{{…}}`
placeholder is kept for the harness. Both arms point `optimizer_instructions_file` at one rendered file,
/workspace/aw_ce2/state/ce2/INSTRUCTIONS.md.
