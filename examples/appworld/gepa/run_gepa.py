"""The `gepa` arm: GEPA 0.1.4 reflective evolution of the P + T surfaces (docs/EVAL_APPWORLD_5.md §7.1).

  venv-aw/bin/python -I run_gepa.py search     # resumable (GEPA's run_dir state + the evaluator's episode cache)
  venv-aw/bin/python -I run_gepa.py accept     # A-gepa: 4 dev tasks into a throwaway run dir, not counted
  venv-aw/bin/python -I run_gepa.py freeze     # result.best_candidate -> surfaces, lint, docs/..._STATE/gepa/artifact/

Candidate = {"policy/instructions.txt", "tools/helpers.py", "tools/api_notes.json"}, seeded from
seed_capability (helpers "", notes "{}"); module_selector round_robin; trainset = train (90) for reflection
minibatches of 3, valset = dev (57) for the Pareto front and the final choice; strict improvement; no merge;
max_metric_calls 987; seed 0. The evaluator is the shared adapter (1 trial, seed 100, gold-free F1 feedback).

Reflection: the stock prompt holds ~45 ``` fences, which break GEPA's first-to-last ``` extractor, so a
custom_candidate_proposer reflects once per selected component with GEPA's own instruction-proposal text,
asks for the new text inside <new_text>…</new_text>, states the lint rules, lints the result and re-reflects
up to 2× with the lint feedback before giving up on that component (an empty proposal skips the child,
as GEPA does). Every reflection goes through the shared gateway shim (no temperature, G1).
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE.parent / "common"))
import aw5 as P  # noqa: E402

P.setup_env()
import evaluator as E  # noqa: E402
import opt_llm  # noqa: E402

CAND = os.environ.get("AW_CAND", "gepa")
STATE = P.AW_STATE / CAND
RUN_DIR = STATE / "gepa_run"
COMPONENTS = ("policy/instructions.txt", "tools/helpers.py", "tools/api_notes.json")
MAX_METRIC_CALLS = 987
MINIBATCH = 3
TRUNC_OUT = 1000
MAX_RELINT = 2

# GEPA's InstructionProposalSignature.default_prompt_template (gepa 0.1.4), with the output delimiter
# changed from ``` blocks to <new_text> (the prompt itself is full of ``` fences) and the lint rules added.
REFLECT = """I provided an assistant with the following {what} to perform a task for me:
<current_text>
<curr_param>
</current_text>

The following are examples of different task inputs provided to the assistant along with the assistant's response for each of them, and some feedback on how the assistant's response could be better:
<examples>
<side_info>
</examples>

Your task is to write a new {what_short} for the assistant.

Read the inputs carefully and identify the input format and infer detailed task description about the task I wish to solve with the assistant.

Read all the assistant responses and the corresponding feedback. Identify all niche and domain specific factual information about the task and include it in the {what_short}, as a lot of it may not be available to the assistant in the future. The assistant may have utilized a generalizable strategy to solve the task, if so, include that in the {what_short} as well.

{rules}

Provide the complete new {what_short} inside <new_text> and </new_text> tags, and nothing after the closing tag."""

WHAT = {
    "policy/instructions.txt": ("instructions (a Jinja prompt template that is split into chat messages)", "instruction template"),
    "tools/helpers.py": ("Python helper module (its functions are pre-defined in the assistant's REPL)", "helper module"),
    "tools/api_notes.json": ("API notes (a JSON object; each note is appended to the matching API documentation lookup)", "API notes JSON"),
}
RULES = {
    "policy/instructions.txt": """Hard rules for the new instruction template (a template that breaks any of them is rejected without being run):
- It is a Jinja template. Keep the variables {{ main_user.first_name }}, {{ main_user.last_name }}, {{ main_user.email }}, {{ main_user.phone_number }} and {{ instruction }}; you may use {{ app_descriptions }}; no other variables exist.
- It is split into chat messages on lines that are exactly `USER:` or `ASSISTANT:`. It must start with `USER:`, keep the worked-demo message structure, and end with the final USER message whose last two lines are `My name is: {{ main_user.first_name }} {{ main_user.last_name }}. My personal email is {{ main_user.email }} and phone number is {{ main_user.phone_number }}.` and `Task: {{ instruction }}`.
- At most 8,000 tokens.
- General guidance only: do not copy any task instruction, person name, email, phone number or other specific value from the examples into the template.""",
    "tools/helpers.py": """Hard rules for the new helper module (a module that breaks any of them is rejected without being run):
- Plain Python. At top level only imports, constants and function definitions (no top-level calls). At most 400 lines.
- Imports only from re, json, math, datetime, itertools, collections, functools. No file, network, exec/eval or __import__ access.
- Helpers take the `apis` object and app/API names as parameters: no string literal equal to an AppWorld app or API name and no `apis.<app>.` attribute chains (use getattr(apis, app_name)).
- Give each public function a short docstring; the assistant is told their names and signatures.
- General helpers only: no task instruction text, person name, email, phone number or other specific value from the examples.
- An empty module (just a docstring) is allowed.""",
    "tools/api_notes.json": """Hard rules for the new API notes (notes that break any of them are rejected without being run):
- A JSON object mapping "app" or "app.api" (real AppWorld app / API names) to a note string.
- Each note at most 400 characters. General usage guidance only: no task instruction text, person name, email, phone number or other specific value from the examples.
- `{}` (no notes) is allowed.""",
}
NEW_TEXT_RE = re.compile(r"<new_text>\s*(.*?)\s*</new_text>", re.S)


def seed_candidate() -> dict[str, str]:
    s = E.read_surfaces(P.SEED_CAP)
    return {"policy/instructions.txt": s["policy/instructions.txt"],
            "tools/helpers.py": s.get("tools/helpers.py", ""), "tools/api_notes.json": s.get("tools/api_notes.json", "{}")}


def _render_steps(rec: dict) -> str:
    out = []
    for st in rec.get("steps") or []:
        o = st.get("output") or ""
        o = o[:TRUNC_OUT] + ("…[truncated]" if len(o) > TRUNC_OUT else "")
        out.append(f"[step {st.get('step')}] thought: {(st.get('thought') or '').strip()[:600]}\n"
                   f"code:\n{(st.get('code') or '').strip()}\noutput:\n{o}")
    return "\n\n".join(out) or "(no steps)"


class AppWorldGEPAAdapter:
    """GEPAAdapter: evaluate = shared evaluator; trajectories = instruction + steps + F1 feedback."""

    propose_new_texts = None

    def __init__(self, cand: str, hard_cap: int):
        self.cand, self.hard_cap = cand, hard_cap
        self.lock = threading.Lock()

    def _eval(self, batch: list[dict], candidate: dict[str, str]) -> list[dict]:
        cdir = E.materialize(self.cand, dict(candidate))
        split = batch[0]["split"] if batch else "?"
        # an identical (candidate, task, seed) cell is replayed rather than re-run: GEPA re-evaluates the
        # seed on every resume (engine.py) and that must not spend counted rollouts twice
        return E.evaluate(self.cand, cdir, [b["id"] for b in batch], phase="P3", split=split, reuse=True,
                          hard_cap=self.hard_cap)

    def evaluate(self, batch, candidate, capture_traces=False):
        from gepa.core.adapter import EvaluationBatch
        recs = self._eval(batch, candidate)
        scores = [float(r["reward"]) for r in recs]
        traj = [{"instruction": b["instruction"], "steps": _render_steps(r), "feedback": r["feedback"]}
                for b, r in zip(batch, recs)] if capture_traces else None
        return EvaluationBatch(outputs=[r.get("termination") for r in recs], scores=scores, trajectories=traj)

    def batch_evaluate(self, items):
        # one candidate × batch at a time; the episodes of a batch run in parallel inside the evaluator
        return [self.evaluate(b, c, capture_traces=True) for c, b in items]

    def make_reflective_dataset(self, candidate, eval_batch, components_to_update):
        recs = [{"Inputs": {"Task": t["instruction"]},
                 "Generated Outputs": t["steps"],
                 "Feedback": t["feedback"]} for t in (eval_batch.trajectories or [])]
        return {c: recs for c in components_to_update}


def _lint_component(comp: str, text: str, candidate: dict[str, str]) -> list[str]:
    cdir = E.materialize(CAND + "_lintprobe", {**candidate, comp: text})
    return [v for v in E.lint(cdir) if v.startswith(comp)]


def make_proposer(cand: str, counters: dict):
    from gepa.strategies.instruction_proposal import InstructionProposalSignature as Sig

    def propose(candidate, reflective_dataset, components_to_update):
        out = {}
        for comp in components_to_update:
            records = reflective_dataset.get(comp) or []
            if not records:
                continue
            what, short = WHAT[comp]
            tmpl = REFLECT.format(what=what, what_short=short, rules=RULES[comp])
            prompt = Sig.prompt_renderer({"current_instruction_doc": candidate[comp], "dataset_with_feedback": records,
                                          "prompt_template": tmpl})
            msgs = [{"role": "user", "content": prompt}]
            for attempt in range(MAX_RELINT + 1):
                try:
                    resp = opt_llm.chat(msgs, cand=cand, role=f"reflect:{comp}", max_tokens=16000)
                except opt_llm.Refusal:
                    counters["refusals"] += 1
                    break
                m = NEW_TEXT_RE.search(resp)
                if not m:
                    counters["parse_fail"] += 1
                    msgs += [{"role": "assistant", "content": resp},
                             {"role": "user", "content": "Your reply had no <new_text>…</new_text> block. "
                                                         "Reply with the complete new text inside those tags."}]
                    continue
                text = m.group(1).strip("\n")
                if comp == "tools/api_notes.json" and not text.strip():
                    text = "{}"
                v = _lint_component(comp, text, candidate)
                if not v:
                    out[comp] = text
                    break
                counters["lint_reject"] += 1
                msgs += [{"role": "assistant", "content": resp},
                         {"role": "user", "content": "That text was rejected by the linter:\n- " + "\n- ".join(v)
                          + "\nFix every violation and reply with the complete corrected text inside "
                            "<new_text>…</new_text>."}]
            else:
                counters["gave_up"] += 1
        P.write_json(STATE / "proposer_counters.json", counters)
        return out
    return propose


class Progress:
    """GEPA callback: one progress line + a pushed progress.json + a ledger checkpoint per iteration."""

    def __init__(self, cand: str, ledger: bool):
        self.cand, self.ledger = cand, ledger
        self.rows = (P.read_json(P.PUSHED / cand / "progress.json", {}) or {}).get("rows", []) if ledger else []

    def on_valset_evaluated(self, ev):
        P.progress_log(self.cand, "P3", f"val: candidate {ev['candidate_idx']} dev mean {ev['average_score']:.3f}"
                                         f" ({ev['num_examples_evaluated']}/{ev['total_valset_size']}) best={ev['is_best_program']}")

    def on_iteration_end(self, ev):
        st = ev["state"]
        scores = [sum(v.values()) / len(v) for v in st.prog_candidate_val_subscores if v]
        best = max(scores) if scores else None
        row = {"iteration": ev["iteration"], "accepted": bool(ev["proposal_accepted"]), "n_candidates": len(scores),
               "best_dev": round(best, 4) if best is not None else None, "metric_calls": st.total_num_evals,
               "counted_rollouts": E.counted(self.cand), "utc": P.utcnow()}
        self.rows.append(row)
        P.progress_log(self.cand, "P3", f"iter {row['iteration']} accepted={row['accepted']} candidates={row['n_candidates']} "
                                         f"best_dev={row['best_dev']} metric_calls={row['metric_calls']} counted={row['counted_rollouts']}")
        if self.ledger:
            checkpoint(self.cand, self.rows, f"iteration {row['iteration']}")


def checkpoint(cand: str, rows: list, what: str, kind: str = "result", next_unit: str | None = None) -> None:
    import status_doc
    t = opt_llm.totals(cand)
    counters = P.read_json(STATE / "proposer_counters.json", {}) or {}
    prog = {"candidate": cand, "rows": rows, "counted_rollouts": E.counted(cand), "cap": P.BUDGET_ROLLOUTS,
            "optimizer": {**t, "proxy_usd": opt_llm.proxy_usd(t)}, "proposer": counters}
    P.write_json(P.PUSHED / cand / "progress.json", prog)
    last = rows[-1] if rows else {}
    status_doc.append(kind, "P3", f"{cand} search",
                      f"GEPA {what}: accepted={last.get('accepted')}, candidates {last.get('n_candidates')}, best dev "
                      f"{last.get('best_dev')}, metric calls {last.get('metric_calls')}/{MAX_METRIC_CALLS}.\n"
                      f"Counted rollouts {prog['counted_rollouts']}/{P.BUDGET_ROLLOUTS}; optimizer {t['calls']} calls, "
                      f"{t['prompt_tokens'] / 1e6:.2f}M in / {t['completion_tokens'] / 1e6:.2f}M out tok, "
                      f"${opt_llm.proxy_usd(t)} proxy; reflection lint rejects {counters.get('lint_reject', 0)}, "
                      f"parse fails {counters.get('parse_fail', 0)}, refusals {counters.get('refusals', 0)}.",
                      done_through=f"{cand}/search/{what}", next_unit=next_unit or f"{cand}/search",
                      extra={"candidate": cand, "counts": {cand: {"counted_rollouts": prog["counted_rollouts"]}},
                             "spend": {cand: {"in": t["prompt_tokens"], "out": t["completion_tokens"],
                                              "proxy_usd": opt_llm.proxy_usd(t)}}},
                      artifacts=[f"STATE/{cand}/progress.json"], subject=f"{cand} {what}")


def _data(split: str, ids: list[str]) -> list[dict]:
    root = P.ROOT_OPT / "data" / "tasks"
    return [{"id": t, "split": split, "instruction": json.loads((root / t / "specs.json").read_text())["instruction"]}
            for t in ids]


def run(train_ids, val_ids, run_dir: Path, max_calls: int, hard_cap: int, ledger: bool):
    import gepa
    counters = P.read_json(STATE / "proposer_counters.json", None) or {"lint_reject": 0, "parse_fail": 0,
                                                                        "refusals": 0, "gave_up": 0}
    run_dir.mkdir(parents=True, exist_ok=True)
    return gepa.optimize(
        seed_candidate=seed_candidate(), trainset=_data("train", train_ids), valset=_data("dev", val_ids),
        adapter=AppWorldGEPAAdapter(CAND, hard_cap), custom_candidate_proposer=make_proposer(CAND, counters),
        candidate_selection_strategy="pareto", skip_perfect_score=True, perfect_score=1.0,
        reflection_minibatch_size=MINIBATCH, module_selector="round_robin", use_merge=False,
        max_metric_calls=max_calls, run_dir=str(run_dir), callbacks=[Progress(CAND, ledger)],
        use_wandb=False, use_mlflow=False, track_best_outputs=True, display_progress_bar=False,
        cache_evaluation=False, seed=0, raise_on_exception=True, acceptance_criterion="strict_improvement")


def search() -> int:
    pidf = P.AW_STATE / "RUNNING.pid"
    pidf.write_text(f"{os.getpid()} {CAND} search\n")
    try:
        res = run(E.split_ids("train"), E.split_ids("dev"), RUN_DIR, MAX_METRIC_CALLS, 1100, ledger=True)
        P.write_json(STATE / "result.json", {"best_idx": res.best_idx, "val_aggregate_scores": res.val_aggregate_scores,
                                             "total_metric_calls": res.total_metric_calls,
                                             "num_candidates": res.num_candidates, "parents": res.parents,
                                             "best_candidate": res.best_candidate})
        return 0
    finally:
        pidf.unlink(missing_ok=True)


def accept() -> int:
    """A-gepa on 4 dev tasks (throwaway: AW_CAND=acc_gepa, never counted)."""
    dev = E.split_ids("dev")
    rd = STATE / "gepa_accept_run"
    import shutil
    shutil.rmtree(rd, ignore_errors=True)
    res = run(dev[:3], dev[3:4], rd, 14, 100, ledger=False)
    counters = P.read_json(STATE / "proposer_counters.json", {})
    calls = P.read_jsonl(opt_llm.usage_path(CAND))
    out = {"metric_calls": res.total_metric_calls, "candidates": res.num_candidates, "counters": counters,
           "reflection_calls": sum(1 for c in calls if c["role"].startswith("reflect")),
           "errors": sum(1 for c in calls if c.get("error")), "refusals": counters.get("refusals", 0),
           "best_lints_clean": not E.lint(E.materialize(CAND, res.best_candidate))}
    out["ok"] = out["reflection_calls"] >= 1 and out["best_lints_clean"] and out["errors"] == 0
    P.write_json(P.AW_STATE / "acceptance" / "a_gepa.json", out)
    print(json.dumps(out))
    return 0 if out["ok"] else 1


def freeze() -> int:
    import shutil
    r = P.read_json(STATE / "result.json")
    best = r["best_candidate"]
    seed_score = r["val_aggregate_scores"][0]
    inert = r["best_idx"] == 0
    cdir = E.materialize(CAND, best)
    v = E.lint(cdir)
    if v:
        raise SystemExit(f"best candidate fails the lint: {v}")
    art = P.PUSHED / CAND / "artifact"
    shutil.rmtree(art, ignore_errors=True)
    for rel, text in E.read_surfaces(cdir).items():
        (art / rel).parent.mkdir(parents=True, exist_ok=True)
        (art / rel).write_text(text)
    (art / "memory").mkdir(exist_ok=True)
    (art / "memory" / ".gitkeep").write_text("")
    P.write_json(art / "FREEZE.json", {"candidate": CAND, "label": "inert" if inert else "",
                                       "best_idx": r["best_idx"], "best_dev": r["val_aggregate_scores"][r["best_idx"]],
                                       "seed_dev": seed_score, "num_candidates": r["num_candidates"],
                                       "metric_calls": r["total_metric_calls"], "tree_sha256": P.sha256_tree(cdir)})
    print(json.dumps(P.read_json(art / "FREEZE.json")))
    return 0


if __name__ == "__main__":
    raise SystemExit({"search": search, "accept": accept, "freeze": freeze}[sys.argv[1]]())
