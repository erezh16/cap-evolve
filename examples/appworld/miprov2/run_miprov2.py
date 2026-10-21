"""MIPROv2 (DSPy 3.4.1) on AppWorld, arm `miprov2` of docs/EVAL_APPWORLD_REST.md §9.2.

  venv-mipro/bin/python -I run_miprov2.py accept     # A-miprov2 (phase "accept": nothing counted)
  venv-mipro/bin/python -I run_miprov2.py search     # the counted search (needs P3); resumable
  venv-mipro/bin/python -I run_miprov2.py freeze     # best full-eval program -> policy/instructions.txt

The whole AppWorld agent is ONE DSPy module with ONE predictor (option "A"): `AppWorldAgent.agent`
(`dspy.Predict(AppWorldTask)`). Its `signature.instructions` is the stock first-USER prose before the first
```python block, and its `demos` render as extra USER/ASSISTANT pairs after the stock demo. `forward` never calls
an LM: it renders instructions + demos into a candidate dir and runs the episode through the shared evaluator.
MIPROv2 itself is used unchanged except for the substitutions §9.2 names:
  * the demo pool comes from the shared seed's successful train records, condensed by one Sonnet call each
    (`_bootstrap_fewshot_examples` override; the set layout and rng use of `create_n_fewshot_demo_sets` are kept);
  * every proposed instruction is linted; a failing one is re-proposed (<= 2), else replaced by candidate 0;
  * `Evaluate` is replaced by `BatchEvaluate`: same score formula (round(100 * mean, 2)) and the same devsets,
    but one evaluator call per (candidate, devset) so the episodes run in parallel in the global slot pool;
  * every LM call goes through `GatewayLM` -> common/opt_llm.py (no temperature/top_p/top_k/n, no
    response_format; usage logged per role).
Resume: DSPy 3.4.1's MIPROv2 builds its Optuna study in memory (no storage argument). Steps 1-2 (demo sets,
instruction candidates) and the rng state after them are saved to AW_STATE/miprov2/proposals.json; on resume they
are loaded and step 3 replays deterministically (seeded TPE, restored rng, scores from the evaluator cache), so
finished trials cost nothing and only the in-flight evaluation is redone.
"""

from __future__ import annotations

import copy
import json
import os
import random
import re
import sys
import tempfile
import time
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(EX / "scripts"), str(EX / "common")]
import awrest as P  # noqa: E402
import evaluator as E  # noqa: E402
import opt_llm  # noqa: E402

import dspy  # noqa: E402
from dspy.evaluate.evaluate import EvaluationResult  # noqa: E402
from dspy.teleprompt import mipro_optimizer_v2 as MV2  # noqa: E402
from dspy.propose.grounded_proposer import GroundedProposer, TIPS  # noqa: E402
from dspy.teleprompt.utils import get_signature  # noqa: E402

CAND = os.environ.get("AW_MIPRO_CAND", "miprov2")   # acceptance runs as "miprov2_accept"
ST = P.cand_state(CAND)
PUSHED = P.PUSHED / CAND
STOCK = (P.SEED_CAP / "policy" / "instructions.txt").read_text(encoding="utf-8")
# Instruction slot: the first USER message's prose before the first ```python block (§9.2). The span ends just
# before "# To get a list of apps", the comment that introduces that block.
_SLOT_A = len("USER:\n")
_SLOT_B = STOCK.index("\n# To get a list of apps") + 1
assert STOCK.startswith("USER:\n") and STOCK[_SLOT_A:_SLOT_B].endswith("\n\n")
STOCK_INSTRUCTION = STOCK[_SLOT_A:_SLOT_B].strip()
# Demo slot: after the stock Spotify demo (its last turn ends "Marked the active task complete.") and before the
# USER message with the key instructions, which precedes the final "My name is: ... Task:" block.
_DEMO_ANCHOR = "USER:\n**Key instructions**"
assert STOCK.count(_DEMO_ANCHOR) == 1
ROLE_MARKER = re.compile(r"(USER|ASSISTANT|SYSTEM):\n", re.I)   # the agent splits the prompt on these
DEMO_MAX_TOKENS = 400

# Faithful settings (§9.2)
SETTINGS = dict(auto=None, num_candidates=6, num_trials=16, minibatch=True, minibatch_size=35,
                minibatch_full_eval_steps=5, max_bootstrapped_demos=3, max_labeled_demos=0,
                program_aware_proposer=True, data_aware_proposer=True, tip_aware_proposer=True,
                fewshot_aware_proposer=True, seed=9)
REPROPOSE = 2


class StopSearch(BaseException):
    """Budget cap or seed-rerun guard: must not be swallowed by DSPy's / Optuna's `except Exception`."""


# ---------------------------------------------------------------- rendering

def _tok(text: str) -> int:
    import tiktoken
    return len(tiktoken.get_encoding("o200k_base").encode(text))


def render_demo(demo) -> str:
    return (f"USER:\nHere is another example task, solved the same way (names and values are placeholders):\n\n"
            f"Task: {demo['task'].strip()}\n\n"
            f"ASSISTANT:\n```python\n{demo['solution'].strip()}\n```\n\n")


def render(instruction: str, demos=()) -> str:
    """The prompt template with `instruction` in the instruction slot and `demos` in the demo slot."""
    text = STOCK[:_SLOT_A] + instruction.strip() + "\n\n" + STOCK[_SLOT_B:]
    if demos:
        i = text.index(_DEMO_ANCHOR)
        text = text[:i] + "".join(render_demo(d) for d in demos) + text[i:]
    return text


def program_files(instruction: str, demos=()) -> dict[str, str]:
    return {"policy/instructions.txt": render(instruction, demos)}


def lint_text(instruction: str, demos=()) -> list[str]:
    """The shared lint on the rendered prompt (venv-aw), plus the role-marker rule of this slot."""
    v = []
    for what, text in [("instruction", instruction)] + [(f"demo {k}", d["task"] + "\n" + d["solution"])
                                                        for k, d in enumerate(demos)]:
        if ROLE_MARKER.search(text):
            v.append(f"{what}: contains a USER:/ASSISTANT:/SYSTEM: line, which would split the prompt")
    d = Path(tempfile.mkdtemp(prefix="lint_", dir=ST))
    try:
        (d / "policy").mkdir()
        (d / "policy" / "instructions.txt").write_text(render(instruction, demos), encoding="utf-8")
        for rel in ("tools/helpers.py", "tools/api_notes.json"):
            src = P.SEED_CAP / rel
            if src.is_file():
                (d / rel).parent.mkdir(parents=True, exist_ok=True)
                (d / rel).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        v += E.lint(d)
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)
    return v


# ---------------------------------------------------------------- LMs

class GatewayLM(dspy.BaseLM):
    """dspy LM over common/opt_llm.py. Every generation parameter DSPy sets (temperature on the proposer's
    `copy(temperature=init_temperature)` and on the dataset summary's `Predict(..., temperature=1.0)`, top_p,
    top_k, n) is dropped here; only messages and max_tokens reach the gateway (G1). No response_format is ever
    built (ChatAdapter with use_json_adapter_fallback=False)."""

    DROP = ("temperature", "top_p", "top_k", "n", "seed", "response_format", "rollout_id", "tools", "tool_choice")

    def __init__(self, cand: str = CAND, max_tokens: int = 4096, **kw):
        super().__init__(model=P.OPT_MODEL, model_type="chat", temperature=None, max_tokens=max_tokens, cache=False)
        self.cand = cand
        self.kwargs = {"max_tokens": max_tokens}

    def copy(self, **kwargs):
        new = super().copy(**{k: v for k, v in kwargs.items() if k not in self.DROP})
        new.kwargs = {k: v for k, v in new.kwargs.items() if k not in self.DROP}
        return new

    @staticmethod
    def role_of(messages) -> str:
        sys_text = " ".join(m.get("content") or "" for m in messages if m.get("role") == "system")
        if "Given several examples from a dataset" in sys_text:
            return "dataset_summary"
        if "series of observations" in sys_text:
            return "dataset_summary"
        if "describe the purpose of one of the specified module" in sys_text:
            return "describe_module"
        if "pseudo-code for a pipeline" in sys_text:
            return "describe_program"
        if "generate a new instruction" in sys_text:
            return "propose_instruction"
        return "proposer_other"

    def forward(self, prompt=None, messages=None, **kwargs):
        messages = messages or [{"role": "user", "content": prompt}]
        role = self.role_of(messages)
        text = opt_llm.chat(messages, cand=self.cand, role=role,
                            max_tokens=int(kwargs.get("max_tokens") or self.kwargs.get("max_tokens") or 4096))
        return {"choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
                "usage": {}, "model": self.model}

    async def aforward(self, prompt=None, messages=None, **kwargs):
        return self.forward(prompt=prompt, messages=messages, **kwargs)


class NeverLM(dspy.BaseLM):
    """task_model= (required by MIPROv2's constructor). The program never calls an LM, so this must never run."""

    def __init__(self):
        super().__init__(model="never", cache=False)

    def forward(self, *a, **k):
        raise AssertionError("the AppWorld program never calls the task LM")


def configure(lm=None):
    dspy.configure(lm=lm or GatewayLM(), adapter=dspy.ChatAdapter(use_json_adapter_fallback=False))


# ---------------------------------------------------------------- the program

class AppWorldTask(dspy.Signature):
    """(replaced by the stock instruction prose)"""

    task: str = dspy.InputField(desc="The supervisor's task, given in natural language.")
    solution: str = dspy.OutputField(desc="The Python code the assistant writes in the AppWorld REPL, "
                                          "step by step, calling app APIs until it calls apis.supervisor.complete_task.")


class AppWorldAgent(dspy.Module):
    """An AppWorld assistant: a ReAct code agent (gpt-oss-120b) that completes a supervisor's day-to-day task by
    writing Python in a REPL, one small block per turn, calling the APIs of simulated apps (spotify, venmo, gmail,
    file system, phone, ...) through `apis.<app>.<api>(...)`, reading each output, and finally calling
    `apis.supervisor.complete_task(answer=...)`. The predictor's instructions are the first user message of the
    agent's prompt (its job description); its demos are extra worked examples (task -> code) shown after the
    built-in example. The task is scored by AppWorld's unit tests on the final app state (reward 1 = all pass).
    """

    def __init__(self, task_ids_by_instruction: dict[str, list[str]] | None = None, phase: str = "search"):
        super().__init__()
        self.agent = dspy.Predict(AppWorldTask.with_instructions(STOCK_INSTRUCTION))
        self._ids = task_ids_by_instruction or {}
        self._phase = phase

    def candidate_dir(self) -> Path:
        return E.materialize(CAND, program_files(self.agent.signature.instructions, self.agent.demos))

    def forward(self, task: str):
        try:
            ids = self._ids.get(task) or []
            if len(ids) != 1:
                P.append_jsonl(ST / "forward_ambiguous.jsonl", {"t": P.utcnow(), "n_ids": len(ids)})
                raise KeyError(f"FORWARD_AMBIGUOUS: instruction maps to {len(ids)} task ids")
            rec = E.evaluate(CAND, self.candidate_dir(), ids, phase=self._phase, tag="forward")[0]
            return dspy.Prediction(reward=float(rec["reward"]))
        except (E.BudgetExceeded, E.SeedRerunRefused) as e:
            raise StopSearch(str(e)) from e
        except Exception as e:  # noqa: BLE001 — infrastructure is reward 0, never a DSPy error (max_errors)
            P.progress_log(CAND, self._phase, f"forward error {type(e).__name__}: {str(e)[:200]}")
            return dspy.Prediction(reward=0.0)


def metric(example, prediction, trace=None) -> float:
    return float(getattr(prediction, "reward", 0.0) or 0.0)


# ---------------------------------------------------------------- batch evaluation (replaces dspy Evaluate)

class BatchEvaluate:
    """Drop-in for dspy.Evaluate inside MIPROv2: same devset semantics and the same score formula as
    Evaluate.__call__ (round(100 * sum / n, 2)), but the devset is scored with ONE evaluator call."""

    log = ST / "evals.jsonl"
    ids_of: dict[int, str] = {}           # id(example) -> task id, filled by the driver
    phase = "search"
    on_eval = None                        # callback(kind, score, n, cdir)

    def __init__(self, *, devset, metric=None, num_threads=None, max_errors=None, **kw):
        self.devset = devset

    def __call__(self, program, metric=None, devset=None, callback_metadata=None, **kw):
        devset = devset if devset is not None else self.devset
        tids = [self.ids_of[id(ex)] for ex in devset]
        pred = program.predictors()[0]
        cdir = E.materialize(CAND, program_files(pred.signature.instructions, pred.demos))
        try:
            recs = E.evaluate(CAND, cdir, tids, phase=self.phase, tag=(callback_metadata or {}).get("metric_key", ""))
        except (E.BudgetExceeded, E.SeedRerunRefused) as e:
            raise StopSearch(str(e)) from e
        results = [(ex, dspy.Prediction(reward=float(r["reward"])), float(r["reward"])) for ex, r in zip(devset, recs)]
        score = round(100 * sum(s for *_, s in results) / len(results), 2)
        kind = (callback_metadata or {}).get("metric_key", "eval")
        P.append_jsonl(self.log, {"t": P.utcnow(), "kind": kind, "n": len(tids), "cand": cdir.name, "score": score,
                                  "fresh": sum(1 for r in recs if not r.get("cache_hit")),
                                  "lint_reject": sum(1 for r in recs if r.get("lint_reject")),
                                  "infra": sum(1 for r in recs if r.get("error"))})
        if BatchEvaluate.on_eval:
            BatchEvaluate.on_eval(kind, score, len(tids), cdir)
        return EvaluationResult(score=score, results=results)


# ---------------------------------------------------------------- demo pool (option "A2")

CONDENSE_SYSTEM = """You turn one solved task of an AI assistant into a short, reusable worked example for the \
assistant's prompt. The assistant works in a Python REPL and calls the APIs of simulated apps as \
apis.<app>.<api>(...); apis.api_docs.show_api_doc(app_name=..., api_name=...) shows an API's spec; \
apis.supervisor.* gives the user's account passwords and personal data; apis.supervisor.complete_task(...) ends the task.

Rules for the example:
- "task": a paraphrase of the task as a generic template. Replace EVERY name, person, email, phone number, \
amount, date, title, item and other concrete value with a placeholder in angle brackets, e.g. <song title>, \
<friend's name>, <amount>. Do not copy any phrase of 5 or more words from the original task text.
- "solution": only the decisive code steps, as one Python block body (no ``` fences), compact: login via the \
supervisor's passwords, the key API calls, pagination loops where needed, the final complete_task call. Use the \
same placeholders, never a concrete value from the original. Short comments are fine.
- No line may start with "USER:", "ASSISTANT:" or "SYSTEM:".
- At most 300 words in total.
Answer with one JSON object {"task": "...", "solution": "..."} and nothing else."""


def _condense_prompt(rec: dict, feedback: str | None) -> str:
    steps = []
    for s in rec.get("steps") or []:
        code = (s.get("code") or "").strip()
        out = (s.get("output") or "").strip()
        if code:
            steps.append(f"# step {s.get('step')}\n{code}\n# output (truncated):\n{out[:400]}")
    body = (f"Original task:\n{rec['instruction']}\n\nThe assistant's code, step by step (it passed all checks):\n\n"
            + "\n\n".join(steps)[:12000])
    if feedback:
        body += f"\n\nYour previous example was rejected: {feedback}\nWrite a new one that fixes this."
    return body


def _parse_json(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if isinstance(d, dict) and isinstance(d.get("task"), str) and isinstance(d.get("solution"), str):
        return {"task": d["task"].strip(), "solution": d["solution"].strip().strip("`")}
    return None


def condense(rec: dict) -> tuple[dict | None, list[str]]:
    """One Sonnet call; lint; one re-condensation with the violations; else dropped (§9.2)."""
    feedback, notes = None, []
    for attempt in range(2):
        d = _parse_json(opt_llm.chat(_condense_prompt(rec, feedback), cand=CAND, role="demo_condense",
                                     system=CONDENSE_SYSTEM, max_tokens=1500))
        if d is None:
            v = ["not a JSON object with task and solution"]
        else:
            v = lint_text(STOCK_INSTRUCTION, [d])
            n = _tok(render_demo(d))
            if n > DEMO_MAX_TOKENS:
                v.append(f"demo has {n} tokens > {DEMO_MAX_TOKENS}")
        if not v:
            return d, notes
        notes.append(f"attempt {attempt}: {len(v)} violation(s)")
        feedback = "; ".join(v)[:1500]
    return None, notes


def build_demo_pool(records: list[dict], path: Path) -> dict[str, dict]:
    """task id -> condensed demo, for every successful record; resumable through `path`."""
    pool = P.read_json(path, {}) or {}
    stats = pool.pop("_stats", {"condensed": 0, "dropped": 0, "recondensed": 0})
    for rec in records:
        if rec.get("reward") != 1.0 or rec["task_id"] in pool or rec["task_id"] in stats.get("dropped_ids", []):
            continue
        d, notes = condense(rec)
        if d is None:
            stats["dropped"] += 1
            stats.setdefault("dropped_ids", []).append(rec["task_id"])
        else:
            pool[rec["task_id"]] = d
            stats["condensed"] += 1
        stats["recondensed"] += int(bool(notes))
        P.write_json(path, {**pool, "_stats": stats})
    P.write_json(path, {**pool, "_stats": stats})
    return pool


# ---------------------------------------------------------------- the MIPROv2 subclass

class AWMIPROv2(MV2.MIPROv2):
    """MIPROv2 with the §9.2 substitutions in steps 1 and 2, and resumable through proposals.json."""

    def __init__(self, *a, demo_pool: dict[str, dict], ids_of: dict[int, str], proposals_path: Path, **kw):
        super().__init__(*a, **kw)
        self.demo_pool, self.ids_of, self.proposals_path = demo_pool, ids_of, proposals_path
        self.proposal_stats = {"proposed": 0, "lint_rejected": 0, "reproposed": 0, "replaced_by_0": 0, "errors": 0}

    # step 1: demo sets from the pool, same layout and rng use as create_n_fewshot_demo_sets with
    # max_labeled_demos=0: [-3] zero-shot, [-2] shuffled (the labeled branch needs max_labeled_demos > 0),
    # [-1] unshuffled with max_bootstrapped_demos, [0..N-4] shuffled with size randint(1, max_bootstrapped_demos).
    def _bootstrap_fewshot_examples(self, program, trainset, seed, teacher, *, num_fewshot_candidates,
                                    max_bootstrapped_demos, max_labeled_demos, max_errors, metric_threshold):
        saved = self._load_proposals()
        if saved:
            return saved["demo_candidates"]
        rng = self.rng

        def take(examples, k):
            out = []
            for ex in examples:
                d = self.demo_pool.get(self.ids_of[id(ex)])
                if d is not None:
                    out.append(dspy.Example(augmented=True, task=d["task"], solution=d["solution"]))
                    if len(out) >= k:
                        break
            return out

        sets = []
        for s in range(-3, num_fewshot_candidates - 3):
            tc = list(trainset)
            if s == -3:
                sets.append([])
            elif s == -1:
                sets.append(take(tc, max_bootstrapped_demos))
            else:
                rng.shuffle(tc)
                size = rng.randint(1, max_bootstrapped_demos)
                sets.append(take(tc, size))
        return {i: list(sets) for i, _ in enumerate(program.predictors())}

    # step 2: GroundedProposer as MIPROv2 builds it, plus the lint and re-proposal of §9.2
    def _propose_instructions(self, program, trainset, demo_candidates, view_data_batch_size, program_aware_proposer,
                              data_aware_proposer, tip_aware_proposer, fewshot_aware_proposer, num_instruct_candidates):
        saved = self._load_proposals()
        if saved:
            self.proposal_stats = saved["stats"]
            return saved["instruction_candidates"]
        proposer = GroundedProposer(
            program=program, trainset=trainset, prompt_model=self.prompt_model,
            view_data_batch_size=view_data_batch_size, program_aware=program_aware_proposer,
            use_dataset_summary=data_aware_proposer, use_task_demos=fewshot_aware_proposer,
            num_demos_in_context=MV2.BOOTSTRAPPED_FEWSHOT_EXAMPLES_IN_CONTEXT, use_tip=tip_aware_proposer,
            set_tip_randomly=tip_aware_proposer, use_instruct_history=False, set_history_randomly=False,
            verbose=self.verbose, rng=self.rng, init_temperature=self.init_temperature)
        self.data_summary = proposer.data_summary
        try:
            cands = proposer.propose_instructions_for_program(trainset=trainset, program=program,
                                                              demo_candidates=demo_candidates,
                                                              N=num_instruct_candidates, trial_logs={})
        except Exception as e:  # noqa: BLE001 — a failed proposal round leaves only candidate 0
            self.proposal_stats["errors"] += 1
            P.progress_log(CAND, "propose", f"proposal round failed: {type(e).__name__}: {str(e)[:200]}")
            cands = {i: [None] * num_instruct_candidates for i, _ in enumerate(program.predictors())}
        for i, pred in enumerate(program.predictors()):
            cands[i][0] = get_signature(pred).instructions          # candidate 0 = the original (MIPROv2)
            for j in range(1, len(cands[i])):
                self.proposal_stats["proposed"] += 1
                text, tries = cands[i][j], 0
                while True:
                    v = lint_text(text) if text else ["no proposal"]
                    if not v:
                        break
                    self.proposal_stats["lint_rejected"] += 1
                    if tries >= REPROPOSE:
                        text = cands[i][0]
                        self.proposal_stats["replaced_by_0"] += 1
                        break
                    tries += 1
                    self.proposal_stats["reproposed"] += 1
                    try:
                        tip = TIPS[self.rng.choice(list(TIPS.keys()))] if tip_aware_proposer else None
                        proposer.use_tip = bool(tip)
                        text = proposer.propose_instruction_for_predictor(
                            program=program, predictor=pred, pred_i=i, demo_candidates=demo_candidates,
                            demo_set_i=j % max(1, len(demo_candidates[i]) if demo_candidates else 1),
                            trial_logs={}, tip=tip)
                    except Exception as e:  # noqa: BLE001
                        self.proposal_stats["errors"] += 1
                        P.progress_log(CAND, "propose", f"re-proposal failed: {type(e).__name__}")
                        text = None
                cands[i][j] = text
        self._save_proposals(demo_candidates, cands)
        return cands

    def _save_proposals(self, demo_candidates, cands):
        P.write_json(self.proposals_path, {
            "demo_candidates": {str(i): [[dict(d.toDict()) for d in s] for s in sets] for i, sets in demo_candidates.items()},
            "instruction_candidates": {str(i): v for i, v in cands.items()},
            "rng_state": _rng_to_json(self.rng.getstate()), "stats": self.proposal_stats,
            "data_summary": getattr(self, "data_summary", None)})

    def _load_proposals(self):
        d = P.read_json(self.proposals_path)
        if not d:
            return None
        if not getattr(self, "_rng_restored", False):
            self.rng.setstate(_rng_from_json(d["rng_state"]))
            self._rng_restored = True
        return {"demo_candidates": {int(i): [[dspy.Example(**x) for x in s] for s in sets]
                                    for i, sets in d["demo_candidates"].items()},
                "instruction_candidates": {int(i): v for i, v in d["instruction_candidates"].items()},
                "stats": d["stats"]}


def _rng_to_json(state):
    return [state[0], list(state[1]), state[2]]


def _rng_from_json(s):
    return (s[0], tuple(s[1]), s[2])


def expected_eval_calls(num_trials: int, full_eval_steps: int, minibatch_size: int, n_val: int) -> dict:
    """MIPROv2 3.4.1's eval schedule, step 3: default full eval, `num_trials` minibatch trials, and a full eval of
    the best-mean unevaluated combo after trial t whenever (t + 1) % (full_eval_steps + 1) == 0 or
    t + 1 == adjusted - 1, where t is the Optuna trial number (the default trial and each full eval are added
    to the study as trials too, so they shift the numbering)."""
    adjusted = num_trials + num_trials // full_eval_steps + 1 + (1 if num_trials % full_eval_steps else 0)
    nxt, fulls = 1, 0
    for _ in range(num_trials):
        tn = nxt + 1
        nxt += 1
        if tn % (full_eval_steps + 1) == 0 or tn == adjusted - 1:
            fulls += 1
            nxt += 1
    return {"adjusted_num_trials": adjusted, "full_evals_after_default": fulls,
            "upper_bound_episodes": num_trials * minibatch_size + fulls * n_val,
            "dspy_total_eval_calls": n_val + num_trials * minibatch_size + fulls * n_val}


# ---------------------------------------------------------------- data

def seed_records(split: str, phase: str) -> list[dict]:
    """The shared seed's records (P3) for a split: cache hits only (rule Q4); never starts an episode."""
    ids = E.split_ids(split)
    h = E.seed_hash()
    missing = [t for t in ids if not E._cache_path(h, t, P.SEARCH_SEED_BASE, phase).exists()]
    if missing:
        raise RuntimeError(f"{len(missing)} {split} seed records are not in the cache: run P3 first")
    return E.evaluate(CAND, E.materialize(CAND, {}), ids, phase=phase, tag=f"seed_{split}")


def examples_for(records: list[dict], ids_of: dict[int, str]) -> tuple[list, dict[str, list[str]]]:
    by_ins: dict[str, list[str]] = {}
    exs = []
    for r in records:
        ex = dspy.Example(task=r["instruction"]).with_inputs("task")
        ids_of[id(ex)] = r["task_id"]
        by_ins.setdefault(r["instruction"], []).append(r["task_id"])
        exs.append(ex)
    # AppWorld repeats instruction texts within a split (same text, different supervisor/world state). Scoring never
    # uses this text map: BatchEvaluate maps each Example object to its own task id (ids_of). Only a direct
    # program(task=...) call would use by_ins; it refuses an ambiguous text (FORWARD_AMBIGUOUS) instead of scoring 0.
    dup = sum(1 for v in by_ins.values() if len(v) > 1)
    P.progress_log(CAND, "search", f"instruction map: {len(records)} records, {len(by_ins)} distinct texts, "
                                   f"{dup} repeated (scored per example object, unaffected)")
    return exs, by_ins


# ---------------------------------------------------------------- progress

def write_progress(**kw) -> None:
    pr = P.read_json(PUSHED / "progress.json", {}) or {}
    t = opt_llm.totals(CAND)
    pr.update({"counted_rollouts": E.counted(CAND), "cache_hits": E.cache_hits(CAND),
               "optimizer": {**t, "proxy_usd": opt_llm.proxy_usd(t)}, "updated": P.utcnow()}, **kw)
    P.write_json(PUSHED / "progress.json", pr)


class Milestones:
    """Ledger milestones (§8): new best full eval, every 25% of B; coalesced to one result entry per 5 min."""

    def __init__(self):
        self.last_entry, self.quarter = 0.0, E.counted(CAND) * 4 // P.BUDGET_ROLLOUTS
        self.best, self.n_mb, self.n_full = None, 0, 0

    def __call__(self, kind, score, n, cdir):
        import status_doc as S
        if kind == "eval_full":
            self.n_full += 1
        elif kind == "eval_minibatch":
            self.n_mb += 1
        new_best = kind == "eval_full" and (self.best is None or score > self.best)
        if new_best:
            self.best = score
        q = E.counted(CAND) * 4 // P.BUDGET_ROLLOUTS
        write_progress(stage="search running", minibatch_trials=self.n_mb, full_evals=self.n_full,
                       best_search_score=None if self.best is None else round(self.best / 100, 4),
                       best_search_label="dev TGC of the best full-eval program (selection-biased)")
        due = new_best or q > self.quarter
        if due and time.time() - self.last_entry >= 300:
            self.quarter, self.last_entry = q, time.time()
            S.append("result", "P4", f"{CAND} search",
                     f"MIPROv2 search: {self.n_mb} minibatch trials, {self.n_full} full evals after the default; best "
                     f"full-eval dev score {self.best}; counted rollouts {E.counted(CAND)} of {P.BUDGET_ROLLOUTS}.",
                     extra={"candidate": CAND, "counts": {CAND: {"counted_rollouts": E.counted(CAND)}}},
                     subject=f"{CAND} search progress")


# ---------------------------------------------------------------- commands

def search() -> int:
    if not E.SEED_DONE.exists():
        raise SystemExit("P3 (the shared seed baseline) is not done")
    configure()
    ids_of: dict[int, str] = {}
    train_recs, dev_recs = seed_records("train", "search"), seed_records("dev", "search")
    trainset, _ = examples_for(train_recs, ids_of)
    valset, by_ins = examples_for(dev_recs, ids_of)
    pool = build_demo_pool(train_recs, ST / "demo_pool.json")
    write_progress(stage="search running (proposals)", demo_pool=len(pool))
    BatchEvaluate.ids_of, BatchEvaluate.phase, BatchEvaluate.on_eval = ids_of, "search", Milestones()
    MV2.Evaluate = BatchEvaluate
    opt = AWMIPROv2(metric=metric, prompt_model=GatewayLM(), task_model=NeverLM(),
                    max_bootstrapped_demos=SETTINGS["max_bootstrapped_demos"],
                    max_labeled_demos=SETTINGS["max_labeled_demos"], auto=None,
                    num_candidates=SETTINGS["num_candidates"], num_threads=P.global_slots(), seed=SETTINGS["seed"],
                    demo_pool=pool, ids_of=ids_of, proposals_path=ST / "proposals.json", log_dir=str(ST / "dspy_log"))
    student = AppWorldAgent(by_ins, phase="search")
    try:
        best = opt.compile(student, trainset=trainset, valset=valset, num_trials=SETTINGS["num_trials"],
                           minibatch=True, minibatch_size=SETTINGS["minibatch_size"],
                           minibatch_full_eval_steps=SETTINGS["minibatch_full_eval_steps"],
                           program_aware_proposer=True, data_aware_proposer=True, tip_aware_proposer=True,
                           fewshot_aware_proposer=True)
        stop = None
    except StopSearch as e:
        best, stop = None, str(e)
    pred = best.predictors()[0] if best is not None else None
    full = [r for r in P.read_jsonl(BatchEvaluate.log) if r["kind"] == "eval_full"]
    if pred is None:   # hard cap fired first (§7.4): the best full eval saved before the abandoned step
        top = max(full, key=lambda r: r["score"]) if full else None
        res = {"stopped": stop, "best_cand": top["cand"] if top else E.materialize(CAND, {}).name,
               "best_score": top["score"] if top else None}
    else:
        res = {"stopped": None, "best_cand": E.materialize(CAND, program_files(pred.signature.instructions,
                                                                              pred.demos)).name,
               "best_score": getattr(best, "score", None),
               "instruction": pred.signature.instructions,
               "demos": [{"task": d["task"], "solution": d["solution"]} for d in pred.demos]}
    res.update({"full_evals": len(full), "proposal_stats": opt.proposal_stats, "counted": E.counted(CAND)})
    P.write_json(ST / "result.json", res)
    write_progress(stage="search finished", proposal_stats=opt.proposal_stats)
    print(json.dumps({k: v for k, v in res.items() if k not in ("instruction", "demos")}))
    return 0


def freeze() -> int:
    res = P.read_json(ST / "result.json")
    if not res:
        raise SystemExit("no result.json: run search first")
    cdir = P.AW_STATE / CAND / "cands" / res["best_cand"]
    v = E.lint(cdir)
    if v:
        raise SystemExit(f"best program fails the lint: {v}")
    art = PUSHED / "artifact"
    for rel, text in E.read_surfaces(cdir).items():   # every surface, so the frozen tree equals the champion's
        P.atomic_write(art / rel, text)
    (art / "memory").mkdir(parents=True, exist_ok=True)
    inert = E.tree_hash(cdir) == E.seed_hash()
    P.write_json(art / "FREEZE.json", {
        "tree_sha256": E.tree_hash(cdir), "inert": inert, "best_full_eval_dev_score": res.get("best_score"),
        "full_evals": res.get("full_evals"), "counted_rollouts": E.counted(CAND),
        "demos": len(res.get("demos") or []), "instruction_changed": res.get("instruction") not in (None, STOCK_INSTRUCTION),
        "stopped_early": res.get("stopped"), "proposal_stats": res.get("proposal_stats")})
    write_progress(stage="frozen" + (" (inert)" if inert else ""))
    print(json.dumps({"frozen": res["best_cand"], "inert": inert}))
    return 0


def accept() -> int:
    import subprocess
    return subprocess.run([sys.executable, "-I", str(Path(__file__).resolve().parent / "accept_miprov2.py")],
                          env={**os.environ, "AW_MIPRO_CAND": "miprov2_accept"}).returncode


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "search":
        raise SystemExit(search())
    if cmd == "freeze":
        raise SystemExit(freeze())
    if cmd == "accept":
        raise SystemExit(accept())
    raise SystemExit(__doc__)
