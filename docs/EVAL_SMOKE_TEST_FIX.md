# AppWorld smoke test: what to fix and what to run again

Follow-up to the [summary](EVAL_SMOKE_TEST_SUMMARY.html) and the plan
([EVAL_SMOKE_TEST.md](EVAL_SMOKE_TEST.md)). Codes like "F14" point to the findings in its Appendix A.

## In short

- **Run cap-evolve's training again**, with the answers kept out of the assistant's reach from the
  first round. The current cap-evolve result was built on a round that saw practice answers.
- **Run the final test window again** for all three methods, so they are compared in one run.
- **Keep the rest.** The baseline, ALTK-Evolve's training and the test setup are not affected.

## 1. Run cap-evolve's training again (required)

**Why.** In training round 2, cap-evolve's AI assistant read the answers and reference solutions of
some practice tasks, and ran the official grader (F14: 36 commands, all in round 2). The final
cap-evolve agent descends from that round: round 2's changes were kept and built on in round 3, and
round 6 built on round 3. So the leak is inside the result and cannot be removed afterwards.

**How.**
- Start again from the original agent. Reuse no cap-evolve change from the first run.
- Keep the answers out of the assistant's reach from round 1, as described in section 4. Run
  check A9 first; it must pass.
- Keep the log scan after training as the final proof. In the first run, rounds 6–8, which ran
  under a lock, show no access to answers (F16).
- Keep all other settings: 6 scored rounds, same model, same practice tasks, same acceptance rule.

## 2. Run the final test window again (required)

**Why.** The new cap-evolve agent has to be scored on the 168 test tasks. The plan scores all methods
in one mixed run, so any change in the hosted model over time affects them equally (plan §12, §15).
Scoring the new agent alone, later, would tie the comparison to when each run happened. Such a shift
would be hard to spot, because results already vary a lot: running the same task twice gave a
different outcome on 24–38% of tasks (F10).

**How.** Score the new cap-evolve agent, the baseline and the unchanged ALTK-Evolve agent together:
168 tasks × 3 methods × 2 runs, as before. Keep the first run's baseline and ALTK-Evolve scores as two
extra runs per task. They show how stable those numbers are.

## 3. What does not need to run again

| part | keep it? | evidence |
|---|---|---|
| Baseline scores on the practice tasks | yes: pass the old run to `cap-evolve run --reuse-baseline` | finished at 16:22:02 on 13 Oct, the same second the first assistant call started; nothing had been changed yet |
| ALTK-Evolve training and its chosen mode | yes | its 1,031 model calls run inside the library, with no shell access; the log scan found nothing in its data (F16) |
| ALTK-Evolve's reduced mode | yes | not an error: the full set of lessons (~83K tokens) is twice what the model can read at once (F11) |
| Test setup and safety changes | yes | applied the same way to every method (F1, F2); acceptance checks A1–A8 passed |

## 4. Fix before the re-run

### Keep the answers out of the assistant's reach

The first run's lock was only a file permission, which the assistant could have undone. Two stronger
options were tried. Check A9 (`examples/appworld/scripts/check_optimizer_isolation.sh`) plants secret
values where the answers are stored. It then asks a real assistant call to find them in every way
round 2 did: reading the files, searching the disk, copying the data, and retrying outside the sandbox.

| option | result of A9 on this machine (15 Oct) |
|---|---|
| **Claude Code's built-in sandbox** (`bubblewrap` + `socat`, settings in `examples/appworld/sandbox/optimizer-sandbox.template.json`) | **cannot start.** No secret leaked, but every shell command failed, so the assistant could not test its code. The sandbox has to place `/dev/null` over protected paths, and this container does not allow that. A newer `bubblewrap` and the documented "weaker nested sandbox" option did not help. |
| **Namespace wrapper** (`examples/appworld/sandbox/claude`) | **pass.** 0 of 6 secrets found. The assistant still wrote files and ran the lint. |

**Use the namespace wrapper on this machine.** It runs each assistant call in a private view of the
file system. That view contains only an allowlist: the Python environment, the reference docs, and
the assistant's own working folder. The answers, other sessions' logs and the API key file are
simply not there. The assistant cannot undo it: unmounting is refused, and it cannot reach the real
files through other processes. **Also pass the settings file**: its file-access rules work without
`bubblewrap`, and A9 showed they block Claude's own Read and Grep tools. **Switch to Claude Code's
sandbox** on any machine where A9 passes in `sandbox` mode.

### Other fixes

1. **Commit the evaluation code** (`examples/appworld/`). It is not in git yet, so the run cannot be
   reproduced from the repository.
2. **Start the training with the wrapper on the PATH** (`examples/appworld/sandbox` first), so it is
   active from round 1.
3. **Keep the "do not look for answers" rule in the assistant's instructions, but do not rely on it.**
   It was in place in the first run, and the helper processes ignored it (F14).

## Cost of the re-run

| step | time | optimizer cost |
|---|---|---|
| cap-evolve training, 6 scored rounds (baseline reused) | about 4.5–5 h | about $50–70 (first run: $67.84, of which about $15 was lost to the broken lock) |
| final test window, 1,008 runs | about 2.2 h (first run: 10:32–12:43) | none (the test model has no usage cost) |
