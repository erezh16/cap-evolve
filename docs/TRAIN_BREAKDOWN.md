# Training breakdown of an evaluation run: procedure

A per-candidate report of the training (search) phase of one evaluation run. It shows reward and
cost for each candidate that the method built during training. It writes `data/train_breakdown.json`
and `data/train_breakdown.md` in that run's folder, next to `metrics_full` and `metrics_summary`.

**This procedure runs only when the owner asks for it, for a run the owner names.** It is not part
of the Box backup (`docs/BACKUP_BOX.md`) or of the verification scan (`docs/VERIFICATION_SCAN.md`),
and neither of those runs it.

**Rules for the executing agent**
- **This document is read-only.** Never edit it.
- Work only on the run the owner pointed to. If the pointer is ambiguous (several attempts, several
  copies of the folder), ask before starting.
- The run's data is read-only. Write only the two output files, plus the manifest entries described
  under "Output".
- Take every figure from **evidence**: per-episode records, optimizer call or session logs, run state
  and events. Do not take a total from a plan, post or README on trust. A published total is used
  only to check your figure.
- A figure that cannot be measured or attributed is `null` with a reason. Never write `0` for an
  unknown. An average over zero items is `null` too.
- Name the source of every figure: the file and its sha256. For a directory of records, give the
  file count and the sha256 of its sorted list of `<path> <sha256>` lines.

## 1. Inputs

Start from `data/metrics_full.jsonl` and `data/metrics_summary.json`, if present. They usually give
the run's totals but not the full per-candidate detail. Then find the method's own records:
- **search episodes:** one record per agent episode, with its task, trial, reward or success, and
  token usage, and a way to tell which candidate it scored (a candidate id, hash or tag in the record
  or its path);
- **optimizer usage:** per call, per session or per round: model, tokens (prompt, completion, cache
  read) and USD with its source;
- **lineage:** the method's run state, events, ledger or history, which give each candidate's parent,
  round and verdict (accepted, rejected, errored, frozen).

Record which files you used, and any you looked for and did not find.

## 2. What a candidate is

A **candidate** is every artifact the method produced or scored during training. That includes the
seed, every rejected or errored proposal, and the frozen champion. List them all, including ones
that were never scored, each with its status. Use the method's own id. If it uses a content hash,
give the hash and any label it attached.

## 3. Per candidate

For each candidate:
1. **Identity:** id, label, parent, round or iteration, the time it was created, status (seed,
   accepted, rejected, errored, frozen champion) and the reason the method gave for that status.
2. **Reward:** one row per scoring of the candidate (split × occasion). Each row gives TGC, SGC, the
   number of tasks, scenarios and trials, the split's name, and whether the scoring covered the whole
   split or a subset (a minibatch, a sample).
   - TGC = mean over tasks of the mean over trials of success.
   - SGC = a scenario passes in trial k when all its tasks pass in trial k, averaged over trials and
     scenarios. Compute SGC only over scenarios whose tasks were **all** scored. Give the number of
     scenarios used. If none were complete (for example a minibatch of three tasks), SGC is `null`
     with the reason "no complete scenario".
   - Also report the method's own score for the candidate, if it logged one, labelled as such. If it
     differs from your recomputed TGC, report both and the reason, if one can be found.
   - Every search reward is a fit metric (`docs/VERIFICATION_SCAN.md` §C2). Label it so.
3. **Agent cost:** the episodes that scored this candidate. Give the number of episodes and tasks,
   prompt and completion tokens, and USD with its source. Show this for all episodes, successful ones
   and failed ones: totals, and averages per episode.
4. **Optimizer cost:** the optimizer work that **produced** this candidate. Give calls or sessions,
   tokens (prompt, completion, cache read) and USD with its source, and also by model and role if the
   logs give them (main loop, subagent, helper). The seed has no optimizer cost: `null`, with the
   reason "not applicable: seed".
5. **Cumulative cost:** optimizer and agent cost up to and including this candidate, in creation
   order. This answers "what did it cost to get here".

## 4. Attribution rules

- **Agent episodes** go to the candidate they scored. An episode that scored several candidates at
  once, or whose candidate cannot be told, goes to a row named **unattributed (agent)**, with the
  reason.
- **Optimizer cost** goes to a candidate only when the logs tie it to that candidate (for example
  one session per round that produced one candidate). Cost the logs do not tie to one candidate goes
  to a row named **unattributed (optimizer)**: for example a reflection call that produced several
  candidates, a session title call, or a whole-run overhead. Never split it in proportion to anything.
  If you also give a proportional split, label it as an estimate and keep it apart.
- **Reused evaluations:** if the method reused a scoring from earlier (for example a baseline taken
  from an earlier attempt), show it on the candidate with the flag "reused", and do not count its
  cost in this run's totals.
- **Infra-errored episodes:** score them as failed in TGC and SGC, as the run's published results do.
  They have no usage, so leave them out of the token and cost totals and averages. Show their count
  next to each figure.
- **Unpriced endpoints:** if a model's calls are not priced (for example IBM RITS), its USD is `null`
  with the reason. You may add a separate `usd_estimated` at a named public rate, but never add it
  into a measured or reported USD.
- Keep agent and optimizer cost apart everywhere. Totals show each of the two, then their sum, and
  that sum covers known USD only. The sum with estimates included is shown separately.

## 5. Totals and reconciliation

- Sum every candidate row plus the unattributed rows, for agent and for optimizer.
- Compare those sums with the run's training totals: `metrics_summary.json` (train phase) if present,
  otherwise `metrics_full.jsonl` (`run_total` or the search rows). Report each comparison as
  `figure | breakdown sum | run total | match?`. A mismatch is reported with its size and the reason,
  if one can be found. Do not adjust a row to make the sums match.
- Check that the frozen champion's own search reward in this report equals the train reward in
  `metrics_summary.json`.

## 6. Output

Write both files to `<run>/data/`. They hold the same content.

`train_breakdown.json`:
```
{ "schema": "train_breakdown v1 (docs/TRAIN_BREAKDOWN.md)",
  "run": <run folder name>, "attempt": <attempt, if the run has several>,
  "generated_utc": <UTC time>, "requested_by": <who asked, and when>,
  "definitions": <TGC, SGC, task, attribution rules as applied>,
  "prices": <every rate used for an estimate, with its source>,
  "candidates": [ { "id", "label", "parent", "round", "created", "status", "status_reason",
                    "rewards": [ {split, occasion, coverage, tgc, sgc, tasks, scenarios_used, trials,
                                  method_score, fit_metric, source} ],
                    "agent": {all, successful, failed: {episodes, tasks, prompt_tokens, completion_tokens,
                              usd, usd_null_reason, usd_estimated, averages}, infra_errored, source},
                    "optimizer": {calls, prompt_tokens, completion_tokens, cache_read_tokens, usd,
                                  usd_source, by_model_role, source},
                    "cumulative": {optimizer_usd, optimizer_tokens, agent_tokens, agent_usd_estimated} } ],
  "unattributed": { "agent": {...}, "optimizer": {...} },
  "totals": { "agent": {...}, "optimizer": {...}, "sum": {...} },
  "reconciliation": [ {figure, breakdown, run_total, match, note} ],
  "sources": [ {path, sha256 | files + sha256_of_sorted_file_hashes} ],
  "not_found": [ <inputs looked for and not found> ] }
```

`train_breakdown.md`, in this order:
1. a header: run, attempt, sources with sha256, when it was generated and on whose request;
2. one overview table with one row per candidate, in creation order: id, parent, round, status,
   search TGC / SGC (main scoring), agent episodes and tokens, optimizer tokens and USD, cumulative
   USD;
3. the unattributed rows and the totals;
4. the reconciliation table;
5. per candidate: every reward row, the agent cost by all / successful / failed, the optimizer cost
   by model and role;
6. the lineage (parent → child, with verdicts), as a list or a table.

`null` values are shown with their reason, never as `0`.

If the run folder is archived on Box, upload the two files to `<run>/data/` with `rclone copy`
(never `sync`) and verify them with `rclone check --one-way`. If the folder has a `MANIFEST.json`,
append the two files' entries (path, bytes, sha256) and update its file and byte counts. Change no
other entry. Do not edit `SCAN_RESULTS_*.md`. Tell the owner what was added.
