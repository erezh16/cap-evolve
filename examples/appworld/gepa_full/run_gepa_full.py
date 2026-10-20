"""The `gepa_full` arm: GEPA 0.1.4 in full mode, prompt AND tool descriptions (docs/EVAL_APPWORLD_REST.md §9.4).

  venv-aw/bin/python -I run_gepa_full.py search     # resumable: GEPA's run_dir state + the evaluator's episode cache
  venv-aw/bin/python -I run_gepa_full.py accept     # A-gepa_full: offline checks + a few dev episodes, never counted
  venv-aw/bin/python -I run_gepa_full.py freeze     # result.best_candidate -> the three surfaces, lint, published artifact

Components (the MCPAdapter pattern: one component per tool description, plus the prompt), all seeded from
seed_capability:
  policy/instructions.txt      the prompt template (stock)
  tools/helpers.py             the helper module (the seed's docstring-only module)
  api_notes:<app>              one per app in root_opt/data/api_docs/standard (empty): lines `<app>: <note>` and
                               `<app>.<api>: <note>`, each note <= 400 chars, merged into tools/api_notes.json.
An empty notes set renders to the seed's `{}` file byte for byte, so the seed candidate's tree hash is SEED_HASH
and its records come from the shared seed baseline (P3, rule Q4).

Engine settings as eval 5's GEPA (the component set is the only change): module_selector round_robin,
reflection_minibatch_size 3, pareto candidate selection, skip_perfect_score, perfect_score 1.0, strict
improvement, no merge, cache_evaluation False (our evaluator caches), seed 0, track_best_outputs.
trainset = train (90, minibatches), valset = dev (57, Pareto front and final choice). max_metric_calls 894:
GEPA counts the seed's 57 cached dev evaluations, and checks the stop condition only at the top of an
iteration, which adds at most 3 + 3 + 57 = 63 more calls, so fresh <= 893 + 63 - 57 = 899 <= B = 900.

Reflection: a custom proposer (the stock prompt has ~45 ``` fences, which break GEPA's fence extractor) that
renders GEPA's InstructionProposalSignature with a per-component-type template asking for <new_text>…</new_text>,
states the lint rules, validates and lints the result, and re-reflects up to 2x with the errors. A component
whose proposal still fails is left out of the child (its parent text is kept); with nothing left, GEPA skips
the child. Every reflection is one opt_llm.chat call (no temperature).

Reflective datasets: the prompt and helpers get eval 5's (instruction, rendered steps, F1 feedback). An
api_notes:<app> component gets, per minibatch task, only the steps that looked up that app's docs or called
apis.<app>.* (code, the doc text or output seen, truncated) plus the task's F1 feedback. If no minibatch task
touched the app, it falls back to the whole-trajectory records (as MCPAdapter does); fallbacks are counted.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE.parent / "common"))
import awrest as P  # noqa: E402

P.setup_env()
import evaluator as E  # noqa: E402
import opt_llm  # noqa: E402

CAND = os.environ.get("AW_CAND", "gepa_full")
STATE = P.AW_STATE / CAND
RUN_DIR = STATE / "gepa_run"
MAX_METRIC_CALLS = 894
SEED_VAL_CALLS = 57
MINIBATCH = 3
TRUNC_OUT = 1000
TRUNC_APP_OUT = 1500
MAX_RELINT = 2
NOTE_MAX = 400
P_COMP, H_COMP = "policy/instructions.txt", "tools/helpers.py"
NOTES_PREFIX = "api_notes:"
API_DOCS = P.ROOT_OPT / "data" / "api_docs" / "standard"


def apps() -> dict[str, set[str]]:
    """App -> API names, from the public API docs (no task data)."""
    return {f.stem: set(json.loads(f.read_text()).keys()) for f in sorted(API_DOCS.glob("*.json"))}


APPS = apps()
COMPONENTS = (P_COMP, H_COMP) + tuple(NOTES_PREFIX + a for a in APPS)


# ---------------------------------------------------------------- candidate <-> surfaces

def seed_candidate() -> dict[str, str]:
    s = E.read_surfaces(P.SEED_CAP)
    c = {P_COMP: s[P_COMP], H_COMP: s.get(H_COMP, "")}
    seed_notes = json.loads(s.get("tools/api_notes.json", "{}") or "{}")
    for a in APPS:
        c[NOTES_PREFIX + a] = notes_to_block(a, {k: v for k, v in seed_notes.items() if k.split(".")[0] == a})
    return c


def notes_to_block(app: str, notes: dict[str, str]) -> str:
    return "\n".join(f"{k}: {v}" for k, v in sorted(notes.items()))


def parse_block(app: str, text: str) -> tuple[dict[str, str], list[str]]:
    """Parse an api_notes:<app> block. Returns (notes, errors); a block with any error is invalid."""
    notes, errs = {}, []
    for i, raw in enumerate((text or "").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)?)\s*:\s*(.+)$", line)
        if not m:
            errs.append(f"line {i}: not of the form `{app}: <note>` or `{app}.<api>: <note>`")
            continue
        key, note = m.group(1), m.group(2).strip()
        a, _, api = key.partition(".")
        if a != app:
            errs.append(f"line {i}: key {key!r} is not this app ({app}); notes for other apps are not allowed here")
        elif api and api not in APPS[app]:
            errs.append(f"line {i}: {key!r} is not an API of {app}")
        elif len(note) > NOTE_MAX:
            errs.append(f"line {i}: note for {key!r} has {len(note)} chars > {NOTE_MAX}")
        elif key in notes:
            errs.append(f"line {i}: duplicate key {key!r}")
        else:
            notes[key] = note
    return notes, errs


def render(candidate: dict[str, str]) -> dict[str, str]:
    """Candidate dict -> the three surface files. The empty notes set renders to the seed's `{}` file."""
    merged: dict[str, str] = {}
    for a in APPS:
        notes, errs = parse_block(a, candidate.get(NOTES_PREFIX + a, ""))
        if not errs:                      # the proposer keeps invalid blocks out; never truncate or guess
            merged.update(notes)
    seed_notes = E.read_surfaces(P.SEED_CAP).get("tools/api_notes.json", "{}\n")
    notes_txt = seed_notes if not merged else json.dumps(dict(sorted(merged.items())), indent=1, ensure_ascii=False) + "\n"
    return {P_COMP: candidate[P_COMP], H_COMP: candidate[H_COMP], "tools/api_notes.json": notes_txt}


# ---------------------------------------------------------------- trajectories and reflective datasets

def _render_steps(steps: list[dict], trunc: int = TRUNC_OUT) -> str:
    out = []
    for st in steps or []:
        o = st.get("output") or ""
        o = o[:trunc] + ("…[truncated]" if len(o) > trunc else "")
        out.append(f"[step {st.get('step')}] thought: {(st.get('thought') or '').strip()[:600]}\n"
                   f"code:\n{(st.get('code') or '').strip()}\noutput:\n{o}")
    return "\n\n".join(out) or "(no steps)"


def app_step_re(app: str) -> re.Pattern:
    """A step touches `app` if it looks up that app's docs or calls apis.<app>.*."""
    q = re.escape(app)
    return re.compile(rf"apis\.{q}\.|show_api_(?:doc|descriptions)\(\s*(?:app_name\s*=\s*)?['\"]{q}['\"]")


def app_steps(steps: list[dict], app: str) -> list[dict]:
    r = app_step_re(app)
    return [s for s in steps or [] if r.search(s.get("code") or "")]


def build_reflective_dataset(trajectories: list[dict], components: list[str], stats: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for comp in components:
        if not comp.startswith(NOTES_PREFIX):
            out[comp] = [{"Inputs": {"Task": t["instruction"]}, "Generated Outputs": _render_steps(t["steps"]),
                          "Feedback": t["feedback"]} for t in trajectories]
            continue
        app = comp[len(NOTES_PREFIX):]
        recs = []
        for t in trajectories:
            st = app_steps(t["steps"], app)
            if st:
                recs.append({"Inputs": {"Task": t["instruction"]},
                             "Generated Outputs": f"Steps of this attempt that used the {app} app or its docs "
                                                  f"({len(st)} of {len(t['steps'])} steps):\n\n"
                                                  + _render_steps(st, TRUNC_APP_OUT),
                             "Feedback": t["feedback"]})
        c = stats.setdefault("components", {}).setdefault(comp, {"visits": 0, "accepts": 0, "fallbacks": 0,
                                                                  "proposals": 0, "invalid": 0})
        if not recs:   # the app does not appear in the minibatch: whole-trajectory summary (MCPAdapter fallback)
            c["fallbacks"] += 1
            recs = [{"Inputs": {"Task": t["instruction"]},
                     "Generated Outputs": f"(This attempt did not use the {app} app.) Whole attempt:\n\n"
                                          + _render_steps(t["steps"]),
                     "Feedback": t["feedback"]} for t in trajectories]
        out[comp] = recs
    return out


# ---------------------------------------------------------------- reflection templates

# GEPA's InstructionProposalSignature.default_prompt_template (0.1.4) with the output delimiter changed from ```
# blocks to <new_text>, and the lint rules added (eval 5's template for the prompt and the helpers).
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
    P_COMP: ("instructions (a Jinja prompt template that is split into chat messages)", "instruction template"),
    H_COMP: ("Python helper module (its functions are pre-defined in the assistant's REPL)", "helper module"),
}
RULES = {
    P_COMP: """Hard rules for the new instruction template (a template that breaks any of them is rejected without being run):
- It is a Jinja template. Keep the variables {{ main_user.first_name }}, {{ main_user.last_name }}, {{ main_user.email }}, {{ main_user.phone_number }} and {{ instruction }}; you may use {{ app_descriptions }}; no other variables exist.
- It is split into chat messages on lines that are exactly `USER:` or `ASSISTANT:`. It must start with `USER:`, keep the worked-demo message structure, and end with the final USER message whose last two lines are `My name is: {{ main_user.first_name }} {{ main_user.last_name }}. My personal email is {{ main_user.email }} and phone number is {{ main_user.phone_number }}.` and `Task: {{ instruction }}`.
- At most 8,000 tokens.
- General guidance only: do not copy any task instruction, person name, email, phone number or other specific value from the examples into the template.""",
    H_COMP: """Hard rules for the new helper module (a module that breaks any of them is rejected without being run):
- Plain Python. At top level only imports, constants and function definitions (no top-level calls). At most 400 lines.
- Imports only from re, json, math, datetime, itertools, collections, functools. No file, network, exec/eval or __import__ access.
- Helpers take the `apis` object and app/API names as parameters: no string literal equal to an AppWorld app or API name and no `apis.<app>.` attribute chains (use getattr(apis, app_name)).
- Give each public function a short docstring; the assistant is told their names and signatures.
- General helpers only: no task instruction text, person name, email, phone number or other specific value from the examples.
- An empty module (just a docstring) is allowed.""",
}


def notes_what(app: str) -> tuple[str, str, str]:
    what = (f"API notes for the `{app}` app. This text is appended to the API documentation the assistant reads "
            f"for app `{app}`: a note keyed `{app}` is added to the output of "
            f"apis.api_docs.show_api_descriptions(app_name='{app}'), and a note keyed `{app}.<api>` is added to the "
            f"output of apis.api_docs.show_api_doc(app_name='{app}', api_name='<api>')")
    rules = f"""Format and hard rules for the new API notes (notes that break any of them are rejected without being run):
- One note per line, either `{app}: <note>` (about the app as a whole) or `{app}.<api_name>: <note>` (about one API; <api_name> must be a real API of {app}). No other lines, no JSON, no notes for other apps.
- Each note is at most {NOTE_MAX} characters, on one line.
- General usage guidance only (how the API behaves, what to call first, common mistakes): no task instruction text, person name, email, phone number or other specific value from the examples.
- An empty text (no notes) is allowed.
The current notes are shown between <current_text> tags (empty if there are none)."""
    return what, f"API notes for {app}", rules


# ---------------------------------------------------------------- adapter

class AppWorldGEPAAdapter:
    """GEPAAdapter over the shared evaluator. Trajectories keep the raw gold-free steps for the per-app datasets."""

    propose_new_texts = None

    def __init__(self, cand: str, phase: str, stats: dict, eval_fn=None):
        self.cand, self.phase, self.stats = cand, phase, stats
        self.tag = "seed"
        self._eval_fn = eval_fn or self._eval

    def _eval(self, batch: list[dict], candidate: dict[str, str]) -> list[dict]:
        cdir = E.materialize(self.cand, render(candidate))
        return E.evaluate(self.cand, cdir, [b["id"] for b in batch], phase=self.phase, tag=self.tag)

    def evaluate(self, batch, candidate, capture_traces=False):
        from gepa.core.adapter import EvaluationBatch
        recs = self._eval_fn(batch, candidate)
        hits = sum(1 for r in recs if r.get("cache_hit"))
        self.stats["gepa_calls"] = self.stats.get("gepa_calls", 0) + len(recs)
        self.stats["cache_hits"] = self.stats.get("cache_hits", 0) + hits
        self.stats["lint_rejects"] = self.stats.get("lint_rejects", 0) + sum(1 for r in recs if r.get("lint_reject"))
        scores = [float(r["reward"]) for r in recs]
        traj = [{"instruction": b["instruction"], "steps": r.get("steps") or [], "feedback": r["feedback"]}
                for b, r in zip(batch, recs)] if capture_traces else None
        return EvaluationBatch(outputs=[r.get("termination") for r in recs], scores=scores, trajectories=traj)

    def batch_evaluate(self, items):
        # one (candidate, batch) at a time; the episodes of a batch run in parallel in the global slot pool
        return [self.evaluate(b, c, capture_traces=True) for c, b in items]

    def make_reflective_dataset(self, candidate, eval_batch, components_to_update):
        return build_reflective_dataset(eval_batch.trajectories or [], list(components_to_update), self.stats)

    # persisted in gepa_state.bin by the engine, so the counters survive a resume
    def get_adapter_state(self):
        return {"stats": json.loads(json.dumps(self.stats))}

    def set_adapter_state(self, st):
        if st and st.get("stats"):
            self.stats.clear()
            self.stats.update(st["stats"])


def _lint_child(comp: str, text: str, candidate: dict[str, str], cand: str) -> list[str]:
    files = render({**candidate, comp: text})
    v = E.lint(E.materialize(cand + "_lintprobe", files))
    target = "tools/api_notes.json" if comp.startswith(NOTES_PREFIX) else comp
    return [x for x in v if x.startswith(target)]


def make_proposer(cand: str, stats: dict, lm=None):
    """Custom candidate proposer: one reflection per selected component, <new_text> delimiters, validation and lint
    inside, <= 2 re-reflections with the errors. `lm(messages, role) -> str` defaults to opt_llm.chat."""
    from gepa.strategies.instruction_proposal import InstructionProposalSignature as Sig

    def chat(msgs, role):
        if lm is not None:
            return lm(msgs, role)
        return opt_llm.chat(msgs, cand=cand, role=role, max_tokens=16000)

    def propose(candidate, reflective_dataset, components_to_update):
        # looked up per call: on resume set_adapter_state replaces stats["proposer"] with the saved counters
        pc = stats.setdefault("proposer", {"lint_reject": 0, "invalid_block": 0, "parse_fail": 0, "refusals": 0,
                                           "gave_up": 0, "calls": 0})
        out = {}
        for comp in components_to_update:
            records = reflective_dataset.get(comp) or []
            if not records:
                continue
            if comp.startswith(NOTES_PREFIX):
                app = comp[len(NOTES_PREFIX):]
                what, short, rules = notes_what(app)
                role = "reflect:api_notes"
            else:
                app = None
                (what, short), rules = WHAT[comp], RULES[comp]
                role = f"reflect:{comp}"
            tmpl = REFLECT.format(what=what, what_short=short, rules=rules)
            prompt = Sig.prompt_renderer({"current_instruction_doc": candidate[comp], "dataset_with_feedback": records,
                                          "prompt_template": tmpl})
            msgs = [{"role": "user", "content": prompt}]
            cs = stats.setdefault("components", {}).setdefault(comp, {"visits": 0, "accepts": 0, "fallbacks": 0,
                                                                      "proposals": 0, "invalid": 0})
            for _attempt in range(MAX_RELINT + 1):
                try:
                    pc["calls"] += 1
                    resp = chat(msgs, role)
                except opt_llm.Refusal:
                    pc["refusals"] += 1
                    break
                m = re.search(r"<new_text>\s*(.*?)\s*</new_text>", resp, re.S)
                if not m:
                    pc["parse_fail"] += 1
                    msgs += [{"role": "assistant", "content": resp},
                             {"role": "user", "content": "Your reply had no <new_text>…</new_text> block. "
                                                         "Reply with the complete new text inside those tags."}]
                    continue
                text = m.group(1).strip("\n")
                errs = parse_block(app, text)[1] if app else []
                if errs:
                    pc["invalid_block"] += 1
                    cs["invalid"] += 1
                    v = errs
                else:
                    v = _lint_child(comp, text, candidate, cand)
                    if v:
                        pc["lint_reject"] += 1
                if not v:
                    out[comp] = text
                    cs["proposals"] += 1
                    break
                msgs += [{"role": "assistant", "content": resp},
                         {"role": "user", "content": "That text was rejected:\n- " + "\n- ".join(v)
                          + "\nFix every problem and reply with the complete corrected text inside <new_text>…</new_text>."}]
            else:
                pc["gave_up"] += 1   # parent text kept for this component
        return out
    return propose


class CountingSelector:
    """Round-robin (GEPA's own selector), counting visits per component. `force` pins one component (A-check only)."""

    def __init__(self, stats: dict, force: str | None = None):
        from gepa.strategies.component_selector import RoundRobinReflectionComponentSelector
        self.rr, self.stats, self.force, self.last = RoundRobinReflectionComponentSelector(), stats, force, None

    def __call__(self, state, trajectories, subsample_scores, candidate_idx, candidate):
        names = [self.force] if self.force else self.rr(state, trajectories, subsample_scores, candidate_idx, candidate)
        for n in names:
            self.stats.setdefault("components", {}).setdefault(n, {"visits": 0, "accepts": 0, "fallbacks": 0,
                                                                   "proposals": 0, "invalid": 0})["visits"] += 1
        self.last = names
        return names


# ---------------------------------------------------------------- progress, ledger, posts

class Progress:
    """GEPA callback: progress line + pushed progress.json per iteration; ledger and issue milestones (§8)."""

    def __init__(self, cand: str, adapter: AppWorldGEPAAdapter, selector: CountingSelector, ledger: bool):
        self.cand, self.adapter, self.selector, self.ledger = cand, adapter, selector, ledger
        self.stats = adapter.stats
        self.last_cp = 0.0
        self.t0 = time.time()
        self.calls0: int | None = None

    def on_iteration_start(self, ev):
        self.adapter.tag = f"it{ev['iteration']}"
        self.selector.last = None

    def on_valset_evaluated(self, ev):
        P.progress_log(self.cand, "P4", f"val: candidate {ev['candidate_idx']} dev mean {ev['average_score']:.3f} "
                                        f"({ev['num_examples_evaluated']}/{ev['total_valset_size']}) best={ev['is_best_program']}")

    def on_iteration_end(self, ev):
        st = ev["state"]
        if ev["proposal_accepted"] and self.selector.last:
            for n in self.selector.last:
                self.stats["components"][n]["accepts"] += 1
        scores = [sum(v.values()) / len(v) for v in st.prog_candidate_val_subscores if v]
        best = max(scores) if scores else None
        rows = self.stats.setdefault("rows", [])
        row = {"iteration": ev["iteration"], "accepted": bool(ev["proposal_accepted"]),
               "component": (self.selector.last or [None])[0], "n_candidates": len(scores),
               "best_dev": round(best, 4) if best is not None else None, "metric_calls": st.total_num_evals,
               "counted_rollouts": E.counted(self.cand), "utc": P.utcnow()}
        rows.append(row)
        if self.calls0 is None:
            self.calls0 = st.total_num_evals
        P.progress_log(self.cand, "P4", f"iter {row['iteration']} comp={row['component']} accepted={row['accepted']} "
                                        f"candidates={row['n_candidates']} best_dev={row['best_dev']} "
                                        f"metric_calls={row['metric_calls']} counted={row['counted_rollouts']}")
        if not self.ledger:
            return
        write_progress(self.cand, self.stats, st.total_num_evals, self._eta(st.total_num_evals))
        quarter = (row["counted_rollouts"] * 4) // P.BUDGET_ROLLOUTS
        crossed = quarter > self.stats.get("quarters_posted", 0)
        if row["accepted"] or crossed or time.time() - self.last_cp >= 300:
            checkpoint(self.cand, self.stats, f"iteration {row['iteration']}")
            self.last_cp = time.time()
        if row["accepted"]:
            milestone(self.cand, f"accept_it{row['iteration']}", "accepted candidate",
                      f"GEPA iteration {row['iteration']}: a child (component `{row['component']}`) passed the minibatch "
                      f"gate and was added to the Pareto front.\n\n" + summary_lines(self.cand, self.stats))
        if crossed:
            self.stats["quarters_posted"] = quarter
            milestone(self.cand, f"budget_q{quarter}", f"{25 * quarter}% of B",
                      f"{row['counted_rollouts']} of B = {P.BUDGET_ROLLOUTS} counted search rollouts used.\n\n"
                      + summary_lines(self.cand, self.stats))

    def _eta(self, calls: int) -> str:
        done = calls - (self.calls0 or calls)
        el = time.time() - self.t0
        if done <= 0 or el < 600:
            return "estimating"
        h = (MAX_METRIC_CALLS - calls) / (done / el) / 3600
        return f"about {max(0.0, h):.1f} h of search left at the current rate"


def write_progress(cand: str, stats: dict, metric_calls: int | None = None, eta: str | None = None,
                   stage: str = "search running") -> dict:
    t = opt_llm.totals(cand)
    rows = stats.get("rows", [])
    best = max((r["best_dev"] for r in rows if r.get("best_dev") is not None), default=stats.get("seed_dev"))
    prog = {"candidate": cand, "stage": stage, "counted_rollouts": E.counted(cand), "cap": P.BUDGET_ROLLOUTS,
            "cache_hits": E.cache_hits(cand), "metric_calls": metric_calls, "max_metric_calls": MAX_METRIC_CALLS,
            "iterations": len(rows), "accepted": sum(1 for r in rows if r.get("accepted")),
            "best_search_score": best, "best_search_label": "dev TGC of the best Pareto candidate (57 dev tasks, "
                                                           "the selection set: selection-biased)",
            "eta": eta, "components": stats.get("components", {}), "proposer": stats.get("proposer", {}),
            "lint_rejects": stats.get("lint_rejects", 0),
            "optimizer": {**t, "proxy_usd": opt_llm.proxy_usd(t)}}
    P.write_json(P.PUSHED / cand / "progress.json", prog)
    return prog


def summary_lines(cand: str, stats: dict) -> str:
    prog = P.read_json(P.PUSHED / cand / "progress.json", {}) or {}
    comps = stats.get("components", {})
    tool = [c for c in comps if c.startswith(NOTES_PREFIX)]
    return "\n".join([
        f"- counted rollouts: {prog.get('counted_rollouts')} of {P.BUDGET_ROLLOUTS}; GEPA metric calls "
        f"{prog.get('metric_calls')} of {MAX_METRIC_CALLS}",
        f"- iterations {prog.get('iterations')}, accepted children {prog.get('accepted')}",
        f"- best dev TGC so far (selection set, selection-biased): {prog.get('best_search_score')}",
        f"- component visits / accepts: prompt {comps.get(P_COMP, {}).get('visits', 0)}/{comps.get(P_COMP, {}).get('accepts', 0)}, "
        f"helpers {comps.get(H_COMP, {}).get('visits', 0)}/{comps.get(H_COMP, {}).get('accepts', 0)}, "
        f"per-app API notes {sum(comps[c]['visits'] for c in tool)}/{sum(comps[c]['accepts'] for c in tool)} "
        f"(dataset fallbacks {sum(comps[c]['fallbacks'] for c in tool)})",
        f"- optimizer: {(prog.get('optimizer') or {}).get('calls', 0)} calls, proxy ${(prog.get('optimizer') or {}).get('proxy_usd', 0)}"])


def checkpoint(cand: str, stats: dict, what: str, kind: str = "result", next_unit: str | None = None) -> None:
    import status_doc
    prog = P.read_json(P.PUSHED / cand / "progress.json", {}) or write_progress(cand, stats)
    o = prog.get("optimizer") or {}
    status_doc.append(kind, "P4", f"{cand} search",
                      f"GEPA-Full {what}: iterations {prog.get('iterations')}, accepted {prog.get('accepted')}, best dev "
                      f"{prog.get('best_search_score')} (selection-biased), metric calls {prog.get('metric_calls')}/"
                      f"{MAX_METRIC_CALLS}. Counted rollouts {prog.get('counted_rollouts')}/{P.BUDGET_ROLLOUTS}, cache hits "
                      f"{prog.get('cache_hits')}; optimizer {o.get('calls', 0)} calls, proxy ${o.get('proxy_usd', 0)}.",
                      done_through=f"{cand}/search/{what}", next_unit=next_unit or f"{cand}/search",
                      extra={"candidate": cand, "counts": {cand: {"counted_rollouts": prog.get("counted_rollouts")}},
                             "spend": {cand: {"in": o.get("prompt_tokens"), "out": o.get("completion_tokens"),
                                              "proxy_usd": o.get("proxy_usd")}}},
                      artifacts=[f"STATE/{cand}/progress.json"], subject=f"{cand} {what}")


def milestone(cand: str, key: str, title: str, body: str) -> None:
    try:
        import post
        post.post(cand, key, f"{P.METHOD_NAMES[cand]}: {title}", body)
        try:
            import autopost
            autopost.mark_posted(cand)
        except Exception:  # noqa: BLE001
            pass
    except Exception as e:  # noqa: BLE001 — a failed post never stops the search; it is in the local log
        P.progress_log(cand, "P4", f"post {key} failed: {type(e).__name__}: {e}"[:300])


# ---------------------------------------------------------------- run

def _data(split: str, ids: list[str]) -> list[dict]:
    """Inputs carry the instruction (gold-free; specs.json is the task statement, not ground truth)."""
    root = P.ROOT_OPT / "data" / "tasks"
    return [{"id": t, "split": split, "instruction": json.loads((root / t / "specs.json").read_text())["instruction"]}
            for t in ids]


def run(trainset, valset, run_dir: Path, max_calls: int, *, cand: str, phase: str, ledger: bool,
        force: str | None = None, eval_fn=None, lm=None, stats: dict | None = None):
    import gepa
    stats = stats if stats is not None else {}
    run_dir.mkdir(parents=True, exist_ok=True)
    adapter = AppWorldGEPAAdapter(cand, phase, stats, eval_fn)
    selector = CountingSelector(stats, force)
    res = gepa.optimize(
        seed_candidate=seed_candidate(), trainset=trainset, valset=valset, adapter=adapter,
        custom_candidate_proposer=make_proposer(cand, stats, lm),
        candidate_selection_strategy="pareto", skip_perfect_score=True, perfect_score=1.0,
        reflection_minibatch_size=MINIBATCH, module_selector=selector, use_merge=False,
        max_metric_calls=max_calls, run_dir=str(run_dir), callbacks=[Progress(cand, adapter, selector, ledger)],
        use_wandb=False, use_mlflow=False, track_best_outputs=True, display_progress_bar=False,
        cache_evaluation=False, seed=0, raise_on_exception=True, acceptance_criterion="strict_improvement")
    return res, stats


def _result_json(res, end: str) -> dict:
    return {"end": end, "best_idx": res.best_idx, "val_aggregate_scores": res.val_aggregate_scores,
            "total_metric_calls": res.total_metric_calls, "num_candidates": res.num_candidates,
            "parents": res.parents, "best_candidate": res.best_candidate}


def search() -> int:
    """GEPA's stopper is max_metric_calls = 894; the evaluator's hard cap is B = 900. If the cap (or the 10M optimizer
    token cap) fires inside an iteration, that iteration is abandoned and the result is GEPA's state as saved at the
    top of it (gepa_state.bin is written before every iteration)."""
    if not E.SEED_DONE.exists():
        raise SystemExit("the shared seed baseline (P3) is not done: GEPA's seed evaluation must come from its cache (Q4)")
    pidf = STATE / "RUNNING.pid"
    STATE.mkdir(parents=True, exist_ok=True)
    pidf.write_text(f"{os.getpid()} {CAND} search\n")
    fresh_start = not (RUN_DIR / "gepa_state.bin").exists()
    stats = (P.read_json(STATE / "stats.json", {}) or {})
    try:
        if fresh_start:
            write_progress(CAND, stats, 0, "estimating")
            milestone(CAND, "m_search_start", "search started",
                      f"GEPA 0.1.4 full mode: prompt + helpers + {len(APPS)} per-app API-note components "
                      f"({len(COMPONENTS)} components, round-robin). trainset = train (90, minibatches of 3), valset = dev "
                      f"(57). max_metric_calls {MAX_METRIC_CALLS} (fresh rollouts <= 899 of B = {P.BUDGET_ROLLOUTS}); "
                      f"merge off; seed 0; gold-free F1 feedback. The seed's dev evaluation is the shared seed baseline.")
        try:
            res, stats = run(_data("train", E.split_ids("train")), _data("dev", E.split_ids("dev")), RUN_DIR,
                             MAX_METRIC_CALLS, cand=CAND, phase="search", ledger=True, stats=stats)
            end = "max_metric_calls reached"
        except (E.BudgetExceeded, opt_llm.BudgetExceeded) as e:
            from gepa.core.result import GEPAResult
            from gepa.core.state import GEPAState
            res = GEPAResult.from_state(GEPAState.load(str(RUN_DIR)), run_dir=str(RUN_DIR), seed=0)
            end = f"cap reached ({e}); result = GEPA state saved before the abandoned iteration"
        finally:
            P.write_json(STATE / "stats.json", stats)
        P.progress_log(CAND, "P4", f"search end: {end}")
        P.write_json(STATE / "result.json", _result_json(res, end))
        write_progress(CAND, stats, res.total_metric_calls, "done", stage="search finished; freeze next")
        checkpoint(CAND, stats, "search finished: " + end.split(" (")[0], kind="phase_done", next_unit=f"{CAND}/freeze")
        milestone(CAND, "m_search_end", "search finished", f"Stop: {end.split(' (')[0]}.\n\n" + summary_lines(CAND, stats))
        return 0
    finally:
        pidf.unlink(missing_ok=True)


def freeze() -> int:
    import shutil
    r = P.read_json(STATE / "result.json")
    best = r["best_candidate"]
    inert = r["best_idx"] == 0
    files = render(best)
    cdir = E.materialize(CAND, files)
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
    seed = seed_candidate()
    changed = sorted(c for c in COMPONENTS if best.get(c) != seed.get(c))
    fz = {"candidate": CAND, "label": "inert" if inert else "", "best_idx": r["best_idx"],
          "best_dev": r["val_aggregate_scores"][r["best_idx"]], "seed_dev": r["val_aggregate_scores"][0],
          "num_candidates": r["num_candidates"], "metric_calls": r["total_metric_calls"], "end": r["end"].split(" (")[0],
          "changed_components": changed, "n_notes": len(json.loads(files["tools/api_notes.json"])),
          "tree_sha256": E.tree_hash(cdir), "seed_tree_sha256": E.seed_hash()}
    P.write_json(art / "FREEZE.json", fz)
    print(json.dumps(fz))
    if os.environ.get("AW_NO_POST") != "1":
        milestone(CAND, "m_freeze", "champion frozen",
                  f"Champion = GEPA candidate {fz['best_idx']} ({'inert: the seed' if inert else 'not the seed'}); dev TGC "
                  f"{fz['best_dev']} vs seed {fz['seed_dev']} (selection set, selection-biased). Changed components: "
                  f"{', '.join(changed) or 'none'}; {fz['n_notes']} API notes. Lint-clean artifact in "
                  f"`docs/EVAL_APPWORLD_REST_STATE/{CAND}/artifact/`.")
    return 0


# ---------------------------------------------------------------- acceptance (A-gepa_full)

def _stub_world(seed_cache: dict, fresh: list, hits: list):
    """A stub evaluator that mimics the shared evaluator's cache: one record per (rendered tree, task)."""
    import random
    cache = dict(seed_cache)

    def ev(batch, candidate):
        h = json.dumps(sorted(render(candidate).items()))
        out = []
        for b in batch:
            k = (h, b["id"])
            if k in cache:
                hits.append(k)
                out.append(dict(cache[k], cache_hit=True))
                continue
            rng = random.Random(hash(k) & 0xffff)
            rec = {"reward": float(rng.random() < 0.4), "feedback": "FAILED: 1/3 requirement checks passed. Failed "
                   "requirements: stub", "termination": "completed",
                   "steps": [{"step": 1, "thought": "look up docs", "code": "print(apis.api_docs.show_api_descriptions("
                              "app_name='spotify'))", "output": "[...]"},
                             {"step": 2, "thought": "call", "code": "apis.spotify.login()", "output": "ok"}]}
            cache[k] = rec
            fresh.append(k)
            out.append(rec)
        return out
    return ev


def accept() -> int:
    import random
    import shutil
    results: dict[str, object] = {}
    acc_cand = "gepa_full_accept"
    seed = seed_candidate()
    # 1. the seed dict has every api_notes key, and renders to SEED_HASH
    results["1_seed_components"] = {"n": len(seed), "apps": sorted(APPS),
                                    "all_notes_keys": all(NOTES_PREFIX + a in seed for a in APPS),
                                    "renders_to_seed_hash": E.tree_hash(E.materialize(acc_cand, render(seed))) == E.seed_hash()}
    # 2. budget identity with a cache-mimicking stub: total_num_evals - cache hits == fresh (counted)
    fresh, hits = [], []
    tr = [{"id": f"tr{i}", "split": "train", "instruction": f"stub train task {i}"} for i in range(9)]
    va = [{"id": f"va{i}", "split": "dev", "instruction": f"stub dev task {i}"} for i in range(5)]
    h0 = json.dumps(sorted(render(seed).items()))
    seed_cache = {(h0, x["id"]): {"reward": float(random.Random(i).random() < 0.3), "feedback": "FAILED: stub",
                                  "termination": "completed", "steps": []} for i, x in enumerate(tr + va)}

    def stub_lm(msgs, role):
        comp_text = msgs[0]["content"]
        if "API notes for" in comp_text:
            app = re.search(r"API notes for the `([a-z_]+)` app", comp_text).group(1)
            return f"<new_text>{app}: stub note {random.random():.6f}</new_text>"
        cur = re.search(r"<current_text>\n(.*)\n</current_text>", comp_text, re.S).group(1)
        return f"<new_text>{cur}\n# stub {random.random():.6f}</new_text>" if "helper" in role else f"<new_text>{cur}</new_text>"
    rd = STATE / "accept_stub_run"
    shutil.rmtree(rd, ignore_errors=True)
    os.environ["AW_STUB"] = "1"
    res, st = run(tr, va, rd, 60, cand=acc_cand, phase="accept", ledger=False, eval_fn=_stub_world(seed_cache, fresh, hits),
                  lm=stub_lm, stats={})
    results["2_budget_identity"] = {"total_num_evals": res.total_metric_calls, "cache_hits": len(hits), "fresh": len(fresh),
                                    "ok": res.total_metric_calls - len(hits) == len(fresh),
                                    "overshoot": res.total_metric_calls - 60, "overshoot_bound": 2 * MINIBATCH + len(va),
                                    "visits": {c: v["visits"] for c, v in st.get("components", {}).items()}}
    # 3. oversize note and invalid helper: rejected with no rollout and no crash
    big = "spotify: " + "x" * 450
    pr_stats: dict = {}
    calls = []
    prop = make_proposer(acc_cand, pr_stats, lm=lambda m, r: (calls.append(r), f"<new_text>{big}</new_text>")[1])
    out_n = prop(seed, {NOTES_PREFIX + "spotify": [{"Inputs": {"Task": "t"}, "Generated Outputs": "o", "Feedback": "f"}]},
                 [NOTES_PREFIX + "spotify"])
    bad_helper = '"""h."""\nimport os\n\ndef f(apis):\n    return apis.spotify.login()\n'
    prop2 = make_proposer(acc_cand, pr_stats, lm=lambda m, r: f"<new_text>{bad_helper}</new_text>")
    out_h = prop2(seed, {H_COMP: [{"Inputs": {"Task": "t"}, "Generated Outputs": "o", "Feedback": "f"}]}, [H_COMP])
    n_before = E.counted(acc_cand)
    lr = E.evaluate(acc_cand, E.materialize(acc_cand, {**render(seed), H_COMP: bad_helper}),
                    E.split_ids("dev")[:1], phase="accept", tag="a_badhelper")[0]
    results["3_rejections"] = {"oversize_note_dropped": out_n == {}, "oversize_attempts": len(calls),
                               "invalid_helper_dropped": out_h == {}, "proposer": pr_stats.get("proposer"),
                               "evaluator_lint_reject": lr["lint_reject"], "evaluator_fresh_episodes": E.counted(acc_cand) - n_before,
                               "accept_rollouts_logged": len(P.read_jsonl(P.AW_STATE / acc_cand / "accept_rollouts.jsonl"))}
    P.write_json(STATE / "accept_partial.json", results)
    if os.environ.get("AW_ACCEPT_OFFLINE") == "1":
        print(json.dumps(results, indent=1))
        return 0
    # 4. real dev episodes (phase accept, not counted): the seed on 4 dev tasks (1 already cached by the A2 smoke test)
    dev = E.split_ids("dev")[:4]
    data = _data("dev", dev)
    seed_dir = E.materialize(acc_cand, render(seed))
    recs = E.evaluate(acc_cand, seed_dir, dev, phase="accept", tag="a_seed")
    used = {a: sum(1 for r in recs if app_steps(r["steps"], a)) for a in APPS}
    trajs = [{"instruction": d["instruction"], "steps": r["steps"], "feedback": r["feedback"]} for d, r in zip(data, recs)]
    touched = [a for a in APPS if a not in ("api_docs", "supervisor") and used[a]]
    untouched = [a for a in APPS if not used[a]]
    dstats: dict = {}
    ds = build_reflective_dataset(trajs[:3], [NOTES_PREFIX + touched[0], NOTES_PREFIX + untouched[0]], dstats)
    results["4_datasets"] = {"apps_used_per_task_count": used, "touched_app_records": len(ds[NOTES_PREFIX + touched[0]]),
                             "untouched_app": untouched[0], "untouched_fallback": dstats["components"][NOTES_PREFIX + untouched[0]]["fallbacks"],
                             "touched_fallback": dstats["components"][NOTES_PREFIX + touched[0]]["fallbacks"],
                             "seed_rewards": [r["reward"] for r in recs]}
    # 5. forced one-component GEPA run with the real evaluator and a real reflection: trainset = 3 dev, valset = 1 dev
    app = touched[0]
    # GEPA skips a parent whose minibatch is all-perfect, so the minibatch needs a seed failure: take cached seed
    # records among the first 10 dev ids (no fresh seed episode), at least one failed, as trainset (3) + valset (1)
    sh = E.seed_hash()
    cached = [t for t in E.split_ids("dev")[:10] if E._cache_path(sh, t, P.SEARCH_SEED_BASE, "accept").exists()]
    crec = {t: json.loads(E._cache_path(sh, t, P.SEARCH_SEED_BASE, "accept").read_text()) for t in cached}
    fails = [t for t in cached if crec[t]["reward"] < 1]
    if not fails:
        raise SystemExit("no cached seed failure among the first 10 dev ids; cannot exercise reflection")
    passes = [t for t in cached if t not in fails]
    pick = (fails[:1] + passes)[:4]
    data5 = _data("dev", pick)
    rd = STATE / "accept_real_run"
    shutil.rmtree(rd, ignore_errors=True)
    n0 = len(P.read_jsonl(P.AW_STATE / acc_cand / "accept_rollouts.jsonl"))
    h0n = E.cache_hits(acc_cand)
    res, st = run(data5[:3], data5[3:4], rd, 5, cand=acc_cand, phase="accept", ledger=False, force=NOTES_PREFIX + app, stats={})
    from gepa.core.state import GEPAState
    gs = GEPAState.load(str(rd))
    child_texts = [c[NOTES_PREFIX + app] for c in gs.program_candidates[1:]]
    usage = [u for u in P.read_jsonl(opt_llm.usage_path(acc_cand)) if u["role"].startswith("reflect")]
    fresh_n = len(P.read_jsonl(P.AW_STATE / acc_cand / "accept_rollouts.jsonl")) - n0
    hits_n = E.cache_hits(acc_cand) - h0n
    results["5_forced_component"] = {"component": NOTES_PREFIX + app, "visits": st["components"][NOTES_PREFIX + app]["visits"],
                                     "proposals": st["components"][NOTES_PREFIX + app]["proposals"],
                                     "proposer": st.get("proposer"), "reflection_calls": len(usage),
                                     "reflection_errors": sum(1 for u in usage if u.get("error")),
                                     "minibatch_seed_rewards": [crec[t]["reward"] for t in pick[:3]],
                                     "num_candidates": res.num_candidates, "child_text_reaches_candidate": bool(child_texts) and all(
                                         t and t != seed[NOTES_PREFIX + app] for t in child_texts),
                                     "total_metric_calls": res.total_metric_calls, "fresh_episodes": fresh_n, "cache_hits": hits_n,
                                     "identity_ok": res.total_metric_calls - hits_n == fresh_n}
    # if GEPA rejected the child (not added), show the mutated text reached the child via the proposer metadata
    if not child_texts:
        lines = (rd / "run_log.txt").read_text() if (rd / "run_log.txt").exists() else ""
        results["5_forced_component"]["child_text_reaches_candidate"] = f"Proposed new text for {NOTES_PREFIX}{app}" in lines
        results["5_forced_component"]["child_rejected_by_gate"] = True
    # 6. canary: a note for `app` appears in that app's doc-lookup outputs only (1 real episode)
    canary = "CANARYNOTE" + "".join(random.choice("QXZJKV") for _ in range(10))
    block = "\n".join([f"{app}: {canary} app note."] + [f"{app}.{api}: {canary} api note." for api in sorted(APPS[app])])
    cand_files = render({**seed, NOTES_PREFIX + app: block})
    cdir = E.materialize(acc_cand, cand_files)
    lv = E.lint(cdir)
    # the task whose seed trajectory looked up this app's docs
    ti = next(i for i, r in enumerate(recs) if any("show_api_doc" in (s.get("code") or "") and app in (s.get("code") or "")
                                                     for s in r["steps"]))
    cr = E.evaluate(acc_cand, cdir, [dev[ti]], phase="accept", tag="a_canary")[0]
    doc_re = re.compile(r"show_api_(?:doc|descriptions)\(\s*(?:app_name\s*=\s*)?['\"]([a-z_]+)['\"]")
    in_app = in_other = lookups_app = lookups_other = 0
    for s in cr["steps"]:
        for m in doc_re.finditer(s.get("code") or ""):
            same = m.group(1) == app
            lookups_app += same
            lookups_other += not same
        apps_in = {m.group(1) for m in doc_re.finditer(s.get("code") or "")}
        if canary in (s.get("output") or ""):
            if apps_in == {app}:
                in_app += 1
            else:
                in_other += 1
    results["6_canary"] = {"app": app, "lint": lv, "episode_error": cr.get("error"), "steps": len(cr["steps"]),
                           "lookups_of_app": lookups_app, "lookups_of_other_apps": lookups_other,
                           "steps_with_canary_from_app_lookup": in_app, "steps_with_canary_elsewhere": in_other,
                           "ok": in_app >= 1 and in_other == 0}
    results["real_episodes_this_check"] = len(P.read_jsonl(P.AW_STATE / acc_cand / "accept_rollouts.jsonl"))
    P.write_json(P.AW_STATE / "acceptance" / "a_gepa_full.json", results)
    print(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit({"search": search, "accept": accept, "freeze": freeze}[sys.argv[1]]())
