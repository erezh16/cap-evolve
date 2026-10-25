# Vendored files of the ablations driver (docs/ABLATIONS.md §9.4)

| file | source | sha256 |
|---|---|---|
| `INSTRUCTIONS.base.md` | `skillberry-ai/cap-evolve` `main` `75b3bcd`, `templates/project/optimizer/INSTRUCTIONS.md` (byte copy; equal to the CE2/CE3 pin `3db96a0`) | `84de4f00a5254c47f0627a9e753129375ce12d20ecdcbeeb0e266d6106de2fce` |
| `facts_ref.md` | `fork/eval-ce3` `examples/appworld/ce2/INSTRUCTIONS.template.md`, the `## AppWorld facts for THIS run` section (from `**Objective score for this run.**` to the lint command), unchanged | `8a7b9ce94954c98e8c6d834d163c7182694ea060fe23eb098354ee8aa825dfa5` |

`instructions.py render` inserts the arm's facts section before `## PREPARATION:`; the stored diffs are in
`docs/ABLATION_STATUS_STATE/abl/`.
