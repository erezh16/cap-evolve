# Vendored / derived files of the cape_improve arm

| file | source | commit | source sha256 | derived sha256 |
|---|---|---|---|---|
| INSTRUCTIONS.template.md | cap-evolve-improve `templates/project/optimizer/INSTRUCTIONS.md` | 470f3fabdad780a2a791037067a73ae9b0295473 | 932ca20b449004f27a5993a13f5d5b93a7e6411e9716458228042686fc49ac98 | d528e1345c1696ad1a95192b79cf2142f0e38a144ccefee7327ac7f71a3fb10e |

Derivation (plan §9.5 Deploy): byte copy of the pinned template with ONE inserted section,
`## AppWorld facts for THIS run`, between "## On code surfaces …" and "## Read these first …". No other line
is changed or removed. `docs/EVAL_APPWORLD_REST_STATE/cape_improve/instructions.diff` is the `diff -u` and
shows insertions only. Placeholders `{AW_LINT_PY}`, `{AW_LINTS}`, `{AW_LINT_CACHE}` are filled by
`run_cape_improve.py setup` (the optimizer's sandbox-runnable lint venv, a copy of lints.py and of the lint cache
under /tmp/aw_rest/opt/cape_improve/lint/); every cap-evolve `{{…}}` placeholder is kept for the harness.
