"""HarnessLens ported to the AppWorld harness (docs/EVAL_APPWORLD_REST.md §9.1). Runs in venv-hl.

  venv-hl/bin/python -I run_harnesslens.py accept [--item NAME]   # acceptance A-harnesslens (dev ids, not counted)
  venv-hl/bin/python -I run_harnesslens.py search                 # the counted search (resumable)
  venv-hl/bin/python -I run_harnesslens.py freeze                 # the last accepted parent's four files

What is HarnessLens and what is new here (state it in the issue, §9.1 "Maturity"):
- Kept from the pinned code (369a5c8), vendored byte-for-byte in hl_vendor/ (see hl_vendor/VENDORED.md): every
  role prompt (Task Explorer, Experience, Experience synthesis, Comparison, Comparison review, Reusable planner,
  Reusable / Adjustment Analyzers, Post-reusable / Post-adjustment Analyzers, Main Agent, review Main Agent,
  Harness Editor), every output validator and canonicaliser, the portfolio rules (promotion headroom,
  failure-only deferral), rollout-role assignment, the creation-cost formulas and rollout budget plan,
  select_confirmation_task_ids, assert_confirmed_promotion, advance_cumulative_version, the revision / replan
  rules, the deterministic-reject fallback and parse_json_object.
- Written new (the runtime layer, which in HarnessLens is opencode/codex/pi + tau2/docker): this controller loop
  (a line-by-line port of IterationController._run_locked), the AppWorld trial packet, the rollout service
  run_pair() over the shared evaluator, role calls as plain chat through opt_llm.py with the bundle inlined
  (HarnessLens's own codex-mode transport, runner._inline_controller_read_files), the Harness Editor as a
  sandboxed `claude -p` (no shell), the fixed channel description replacing the Harness Query role, the channel
  preflight (shared lint + render checks, no rollout), and the budget ledger (B = 900 rollouts, enforced by the
  evaluator, + 10M optimizer tokens) replacing core/budget.py's 200 LLM-session units.

Settings (§9.1, verified against the code): HAI_TRAIN_ROLLOUT_REPEATS=1, HAI_CONFIRMATION_MODE=always, promotion
metric pass_at_1 (strict improvement on the confirmation), one revision per candidate, Experience batches of
MAX_TASKS_PER_EXPERIENCE_JOB = 5, at most 4 analyzer groups per side, comparison groups of 3. Screens: the plan
fixes 10 TRAIN tasks (the code minimum is 5, its default exploration size 6); confirmation selects 10 tasks with
the vendored select_confirmation_task_ids. TRAIN = the official train split (90); dev is not used in search.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

os.environ["HAI_TRAIN_ROLLOUT_REPEATS"] = "1"       # §9.1: one trial per task (Q1); read at hl_vendor import
os.environ["HAI_CONFIRMATION_MODE"] = "always"      # §9.1: the code default, set explicitly

HERE = Path(__file__).resolve().parent
EX = HERE.parent
sys.path[:0] = [str(HERE), str(EX / "scripts"), str(EX / "common")]
import awrest as P  # noqa: E402
import evaluator as E  # noqa: E402
import opt_llm  # noqa: E402
import sandbox as SB  # noqa: E402

from hl_vendor import analyzer as HA  # noqa: E402
from hl_vendor import controller as HC  # noqa: E402
from hl_vendor import discovery as HD  # noqa: E402
from hl_vendor import experience as HX  # noqa: E402
from hl_vendor import harness_editor as HE  # noqa: E402
from hl_vendor import main_agent as HM  # noqa: E402
from hl_vendor import task_data as HT  # noqa: E402
from hl_vendor.runner import parse_json_object  # noqa: E402

CAND = "harnesslens"
SURFACES = ("policy/instructions.txt", "tools/helpers.py", "tools/api_notes.json", "memory/playbook.md")
SCREEN_TASKS = 10                       # §9.1: screen batches of 10 TRAIN tasks (code minimum 5)
CONFIRM_TASKS = 10                      # §9.1: confirmation = 10 tasks (select_confirmation_task_ids)
PROMOTION_METRIC = "pass_at_1"
ROLE_MAX_TOKENS = 32_000                # HarnessLens's DEFAULT_OUTPUT_LIMIT is 24,576; post-analyzers 49,152
POST_MAX_TOKENS = HA.POST_ANALYZER_OUTPUT_LIMIT
ROLE_WORKERS = 4                        # parallel role calls (HarnessLens: analysis_workers, cap 20)
EDITOR_MAX_TURNS = 40                   # HarnessEditor(max_steps=40)
EDITOR_TOOLS = "Read,Write,Edit,Glob,Grep"  # HarnessLens EDITOR_TOOLS for opencode/pi: file tools, no shell
STATE_DIR = P.AW_STATE / CAND
RUN = STATE_DIR / "run"                 # the HarnessLens run root (local only)


# =============================================================================================== utilities

def utc() -> str:
    return P.utcnow()


def wj(path: Path, obj: Any) -> Path:
    P.write_json(path, obj)
    return path


def rj(path: Path, default: Any = None) -> Any:
    return P.read_json(path, default)


def clip(text: Any, limit: int) -> str:
    return HX._clip_text(text, limit)


def log(phase: str, detail: str) -> None:
    P.progress_log(CAND, phase, detail)


class Ctx:
    """Everything the port needs that differs between acceptance and search."""

    def __init__(self, *, run: Path, phase: str, train_ids: Sequence[str], editor_mode: str = "claude",
                 evaluate: Callable | None = None, chat: Callable | None = None, label_prefix: str = ""):
        self.run = Path(run)
        self.phase = phase                                # "search" (counted) or "accept"
        self.train_ids = tuple(train_ids)
        self.editor_mode = editor_mode                    # "claude" | "stub"
        self._evaluate = evaluate or E.evaluate
        self._chat = chat or opt_llm.chat
        self.prefix = label_prefix
        self.run.mkdir(parents=True, exist_ok=True)

    def evaluate(self, cdir: Path, task_ids: Sequence[str], tag: str) -> list[dict]:
        return self._evaluate(CAND, cdir, list(task_ids), phase=self.phase, tag=tag)

    def chat(self, role: str, system: str, payload: Mapping[str, Any], max_tokens: int = ROLE_MAX_TOKENS) -> str:
        user = ("Return exactly one JSON object and no markdown.\nINPUT:\n"
                + json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return self._chat(user, cand=CAND, role=role, system=system, max_tokens=max_tokens)


# ===================================================================== AppWorld task data (instructions only)

def task_query(rec: Mapping[str, Any]) -> dict[str, Any]:
    """HarnessLens's per-task `query` (task instruction). The supervisor is not exposed (lint rule)."""
    return {"instruction": str(rec.get("instruction") or "")}


EVALUATION_CONTRACT = HT.evaluation_contract("authoritative")   # AppWorld's evaluator decides pass/fail


def public_environment() -> dict[str, Any]:
    """The public environment block of task_explorer_input: AppWorld's public API index and the agent notes."""
    return {
        "benchmark": "AppWorld (simplified ReAct code agent, gpt-oss-120b)",
        "api_index": (P.REFERENCE / "api_index.md").read_text(encoding="utf-8"),
        "agent_runtime": (P.REFERENCE / "react_agent_notes.md").read_text(encoding="utf-8"),
    }


# ============================================================================= the trial packet (gold-free)

def evidence_id(version: str, task_id: str, seed: int, label: str) -> str:
    """Stable evidence id per (rollout, task, trial). Hashes never reveal the task id."""
    return "ev_" + hashlib.sha256(f"{version}|{task_id}|{seed}|{label}".encode()).hexdigest()[:24]


def trial_packet(rec: Mapping[str, Any], *, ev: str) -> dict[str, Any]:
    """AppWorld analogue of experience._visible_trial_packet: the model-visible behavior of one episode.

    user_messages = the task instruction; each agent step = one assistant observation (thought, clipped) and one
    tool interaction (the REPL code as `execute_python`, the REPL output as observed_result, clipped to 1,200 chars
    as _clip_text in _compact_tool_result). grader_diagnostic carries feedback tier F1 only: pass fraction, the
    texts of failed requirements, collateral damage, complete_task called, API errors, termination. No gold."""
    steps = list(rec.get("steps") or [])
    observations, interactions = [], []
    for i, s in enumerate(steps):
        thought = s.get("thought") or ""
        if thought:
            observations.append({"sequence": 2 * i, "content": clip(thought, 900)})
        interactions.append({"sequence": 2 * i, "call_id": f"step{i + 1}", "tool": "execute_python",
                             "arguments": {"code": clip(s.get("code") or "", 1500)},
                             "observed_result": clip(s.get("output") or "", 1200)})
    final = next((clip(s.get("thought") or "", 1200) for s in reversed(steps) if s.get("thought")), "")
    return {
        "evidence_id": ev,
        "trial": 0,
        "reward": float(rec.get("reward") or 0.0),
        "termination": str(rec.get("termination") or ""),
        "execution_summary": {"status": "lint_reject" if rec.get("lint_reject") else "completed",
                              "n_messages": 1 + 2 * len(steps), "n_tool_calls": len(steps),
                              "worker_error": str(rec.get("error") or "")[:300],
                              "infrastructure_error": bool(rec.get("error")),
                              "verifier_completed": not rec.get("error"), "verifier_timed_out": False},
        "grader_diagnostic": {
            "pass_count": rec.get("pass_count"), "num_tests": rec.get("num_tests"),
            "failed_requirements": [clip(x, 400) for x in (rec.get("failed_requirements") or [])[:12]],
            "collateral_damage": bool(rec.get("collateral_damage")),
            "complete_task_called": bool(rec.get("complete_task_called")),
            "api_errors": rec.get("api_errors"),
        },
        "channel_usage": {"skills_available": [], "skills_invoked": []},
        "user_messages": [{"sequence": 0, "content": clip(rec.get("instruction") or "", 900)}],
        "assistant_observations": observations[-12:],
        "tool_interactions": interactions if len(interactions) <= 20 else interactions[:8] + interactions[-12:],
        "final_response": final,
    }


# ============================================================================ channels (fixed Harness Query)

def harness_query() -> dict[str, Any]:
    """The fixed channel description that replaces the Harness Query role (§9.1, written once, recorded).

    The four AppWorld surfaces, mapped to HarnessLens's channel ids so the vendored validators, channel-routing
    rules and GLOBAL_INSTRUCTION_CHANNELS apply unchanged: system_prompt (global), tool_description, local
    extension code, skills."""
    lint = ("A candidate that violates any lint rule is rejected before any rollout. Never put task ids, "
            "supervisor names, emails, phone numbers or any 8 consecutive words of a training task instruction "
            "in any file.")
    return {
        "harness": "appworld",
        "harness_version": "appworld-42b5bcf-simplified-react",
        "summary": ("AppWorld's official simplified ReAct code agent. The model writes one Python block per step that "
                    "runs in a persistent REPL holding `apis`; four candidate files are editable. " + lint),
        "modifiable_modules": [
            {"id": "system_prompt", "status": "modifiable", "evidence_level": "runtime_observed",
             "visibility": "Startup-visible in every step of every task: the whole first prompt and worked demo.",
             "use": "Global behavior rules and the worked example (widest blast radius; needs preservation canaries).",
             "edit_contract": {"scope": "project", "path": "policy/instructions.txt", "mechanism": "file"},
             "runtime_constraints": [
                 "Jinja template rendered with instruction, main_user, app_descriptions (no other variables)",
                 "must start with 'USER:' and keep the USER:/ASSISTANT: message structure",
                 "must end with the 'My name is: ... Task: {{ instruction }}' block",
                 "at most 8,000 tokens"],
             "risks": "Changes reach every task; can break unrelated behavior.", "evidence_refs": ["runtime:prompt"]},
            {"id": "tool_description", "status": "modifiable", "evidence_level": "runtime_observed",
             "visibility": ("Shown only when the agent calls apis.api_docs.show_api_doc / show_api_descriptions "
                            "for that app or API: the note is appended to the original documentation."),
             "use": "Tool-local guidance about one app or one API (parameters, pagination, pitfalls).",
             "edit_contract": {"scope": "project", "path": "tools/api_notes.json", "mechanism": "file"},
             "runtime_constraints": [
                 "JSON object mapping 'app' or 'app.api' (existing AppWorld names) to a note string",
                 "each note at most 400 characters; all notes together at most 20,000 tokens"],
             "risks": "Narrow: only visible after a doc lookup for that app/API.", "evidence_refs": ["runtime:notes"]},
            {"id": "extension_code", "status": "modifiable", "evidence_level": "runtime_observed",
             "visibility": ("Executed once in the REPL before step 1; every public function is callable and is "
                            "listed by name in one line appended to the prompt."),
             "use": "Reusable local helper code (pagination, search, retries) the agent may call.",
             "edit_contract": {"scope": "project", "path": "tools/helpers.py", "mechanism": "extension"},
             "runtime_constraints": [
                 "helpers take `apis` and app/API names as parameters: no 'apis.<app>.' attribute chains, no "
                 "string literal equal to an app or API name (use getattr(apis, app_name))",
                 "imports only re, json, math, datetime, itertools, collections, functools",
                 "only imports, constants and function definitions at top level (no top-level calls)",
                 "no open/exec/eval/compile/__import__/input/globals/locals/vars; at most 400 lines"],
             "risks": "Bugs surface as REPL errors; unused helpers are inert.", "evidence_refs": ["runtime:helpers"]},
            {"id": "skills", "status": "modifiable", "evidence_level": "runtime_observed",
             "visibility": ("Static playbook inserted into the final USER message just before 'My name is:' under "
                            "the heading 'Guidelines learned from past task attempts:'; visible in every task."),
             "use": "Ordered procedures with branches and checks (skill-like guidance; always loaded, no trigger).",
             "edit_contract": {"scope": "project", "path": "memory/playbook.md", "mechanism": "file"},
             "runtime_constraints": [f"at most {E.m_cap_tokens() or 14000} tokens and 30,000 characters",
                                     "plain Markdown; no YAML frontmatter needed"],
             "risks": "Startup-visible like instructions: long playbooks crowd the 40K context.",
             "evidence_refs": ["runtime:memory"]},
        ],
        "unavailable_modules": [
            {"id": "model_and_decoding", "status": "forbidden", "reason": "fixed by the experiment",
             "runtime_constraints": [], "evidence_refs": ["runtime:fixed"]},
            {"id": "task_tools_and_permissions", "status": "forbidden",
             "reason": "AppWorld's APIs, the REPL allowlist, step and token caps are fixed",
             "runtime_constraints": [], "evidence_refs": ["runtime:fixed"]},
        ],
        "base_profile": {"shared_rules": [lint, "Helpers must not hardcode app or API names."],
                         "role_isolation": "The editor sees only the four candidate files and this description."},
    }


CHANNEL_FILE = {"system_prompt": "policy/instructions.txt", "tool_description": "tools/api_notes.json",
                "extension_code": "tools/helpers.py", "skills": "memory/playbook.md"}
FILE_CHANNEL = {v: k for k, v in CHANNEL_FILE.items()}


# ===================================================================================== versions and rollouts

class Repo:
    """Versions v0 (the seed), candidate-NN: materialized candidate dirs (content-addressed by the evaluator)."""

    def __init__(self, run: Path):
        self.path = run / "versions.json"

    def all(self) -> dict[str, str]:
        return rj(self.path, {}) or {"v0": str(P.SEED_CAP)}

    def dir(self, version: str) -> Path:
        return Path(self.all()[version])

    def add(self, version: str, cdir: Path) -> None:
        d = self.all()
        d[version] = str(cdir)
        wj(self.path, d)

    def surfaces(self, version: str) -> dict[str, str]:
        files = E.read_surfaces(self.dir(version))
        return {rel: files.get(rel, "") for rel in SURFACES}


def run_version(ctx: Ctx, repo: Repo, version: str, task_ids: Sequence[str], label: str) -> Path:
    """One rollout of `version` on `task_ids` (1 trial each), saved as HarnessLens's rollout payload."""
    out = ctx.run / "rollout" / f"{label}.json"
    if out.exists():
        return out
    recs = ctx.evaluate(repo.dir(version), task_ids, tag=label)
    tdir = ctx.run / "rollout_records" / label
    records, per_task, rewards = [], {}, []
    for tid, rec in zip(task_ids, recs):
        p = tdir / f"{hashlib.sha256(tid.encode()).hexdigest()[:16]}.json"
        wj(p, rec)
        r = float(rec.get("reward") or 0.0)
        rewards.append(r)
        ev = evidence_id(version, tid, P.SEARCH_SEED_BASE, label)
        summary = {"trial": 0, "reward": r, "error": str(rec.get("error") or ""),
                   "infrastructure_error": bool(rec.get("error"))}
        records.append({"task_id": tid, "rewards": [r], "harness_version": version, "trajectory_paths": [str(p)],
                        "evidence_ids": [ev], "worker_errors": [], "trial_summaries": [summary],
                        "pass_at_1": int(r >= 1.0), "pass_at_2": int(r >= 1.0)})
        per_task[tid] = {"rewards": [r], "trajectory_paths": [str(p)], "trial_summaries": [summary]}
    n = len(rewards)
    infra = sum(1 for x in recs if x.get("error"))
    metrics = {"task_count": n, "trial_count": n, "trial_success_count": int(sum(x >= 1.0 for x in rewards)),
               "trial_success_rate": (sum(x >= 1.0 for x in rewards) / n) if n else 0.0,
               "pass_at_1": (sum(x >= 1.0 for x in rewards) / n) if n else 0.0,
               "pass_at_2": (sum(x >= 1.0 for x in rewards) / n) if n else 0.0,
               "worker_error_count": infra, "infrastructure_failure_count": infra, "charged_trial_count": n - infra,
               "cache_hits": sum(1 for x in recs if x.get("cache_hit")),
               "lint_rejects": sum(1 for x in recs if x.get("lint_reject"))}
    wj(out, {"harness_version": version, "label": label, "requested_task_ids": list(task_ids), "records": records,
             "per_task": per_task, "metrics": metrics})
    return out


def run_pair(ctx: Ctx, repo: Repo, parent: str, child: str, task_ids: Sequence[str], label: str,
             *, pairing_offset: int = 0) -> tuple[Path, Path | None]:
    """RolloutModule.run_pair_from_main: v0 parent at offset 0 → no parent run (the frozen baseline is the
    reference). Otherwise the exact parent runs on the same tasks (cache hit when already run). Infra validity
    annotated as annotate_paired_validity."""
    if parent == "v0" and int(pairing_offset) == 0:
        return run_version(ctx, repo, child, task_ids, label), None
    with ThreadPoolExecutor(max_workers=2) as ex:
        fp = ex.submit(run_version, ctx, repo, parent, task_ids, f"{label}-parent-{parent}")
        fc = ex.submit(run_version, ctx, repo, child, task_ids, label)
        pp, cp = fp.result(), fc.result()
    failures = sum(rj(x)["metrics"]["infrastructure_failure_count"] for x in (pp, cp))
    for x in (pp, cp):
        d = rj(x)
        d["metrics"]["paired_infrastructure_valid"] = failures == 0
        d["metrics"]["paired_infrastructure_failure_count"] = failures
        wj(x, d)
    return cp, pp


def records_of(path: Path) -> dict[str, dict]:
    return {r["task_id"]: r for r in rj(path)["records"]}


# ========================================================================================= role invocation

def call_role(ctx: Ctx, *, job: str, system: str, payload: Mapping[str, Any], validator: Callable | None,
              attempts: int = 3, retry: Callable[[str], dict] | None = None, max_tokens: int = ROLE_MAX_TOKENS
              ) -> dict | None:
    """IntelligentHarnessRunner.run_json as one plain-chat call per attempt; cached per job on disk (resume)."""
    cache = ctx.run / "intelligent_jobs" / f"{job}.json"
    if cache.exists():
        return rj(cache)
    err = ""
    for attempt in range(attempts):
        body = dict(payload)
        if attempt:
            body.update(retry(err) if retry else {"retry_context": "Previous output failed validation: " + err})
        try:
            text = ctx.chat(role_of(job), system, body, max_tokens=max_tokens)
        except opt_llm.Refusal as e:
            err = f"refusal: {e}"
            continue
        try:
            out = dict(parse_json_object(text))
            if validator is not None:
                validator(out)
        except Exception as e:  # noqa: BLE001 — the vendored validators raise ValueError/KeyError/TypeError
            err = str(e)[:800]
            wj(ctx.run / "intelligent_jobs" / f"{job}.attempt{attempt}.invalid.json", {"error": err})
            continue
        wj(cache, out)
        return out
    wj(ctx.run / "intelligent_jobs" / f"{job}.failed.json", {"error": err})
    return None


def role_of(job: str) -> str:
    """Usage-log role per HarnessLens role (§5.2 'per role')."""
    head, _, rest = job.partition(".")
    if head == "main":
        return "main.review" if "review" in rest else "main.select"
    if head == "analyzer":
        return "analyzer." + ("post-" + rest.split("-")[1] if rest.startswith("post-") else rest.split("-")[0])
    if head == "experience":
        return "experience." + rest.split("-")[0]
    return head


def parallel(fns: Sequence[Callable[[], Any]]) -> list[Any]:
    with ThreadPoolExecutor(max_workers=max(1, min(ROLE_WORKERS, len(fns)))) as ex:
        futs = [ex.submit(f) for f in fns]
        return [f.result() for f in futs]


# ===================================================================================== discovery (TRAIN)

def run_discovery(ctx: Ctx, baseline_recs: Mapping[str, dict]) -> dict:
    root = ctx.run / "discovery"
    hq = harness_query()
    wj(root / "harness_query.json", hq)
    task_input = {"scope": "TRAIN", "domain": "appworld", "benchmark_kind": "appworld",
                  "tasks": [{"task_id": t, "query": task_query(baseline_recs[t])} for t in ctx.train_ids],
                  "environment": public_environment(), "evaluation_contract": EVALUATION_CONTRACT}
    wj(root / "task_explorer_input.json", task_input)
    out = root / "task_explorer.json"
    if out.exists():
        return rj(out)
    model_payload = {k: v for k, v in task_input.items() if k != "environment"}
    model_payload["environment"] = {"benchmark": task_input["environment"]["benchmark"]}
    res = call_role(ctx, job="discovery-task-explorer", system=HD.TASK_EXPLORER_SYSTEM, payload=model_payload,
                    validator=lambda o: HD.validate_task_explorer(o, tuple(ctx.train_ids)), attempts=2,
                    retry=lambda e: {"retry_context": (
                        "Previous task classification failed validation. Return a partition: each TRAIN task ID "
                        "must appear exactly once across all primary category task_ids. For multi-intent tasks, "
                        "choose one dominant primary category and mention secondary aspects only in notes.")})
    if res is None:
        raise RuntimeError("task explorer did not produce a required output")
    wj(out, res)
    return res


# ============================================================================== experience (baseline, TRAIN)

def baseline_source_index(ctx: Ctx, baseline: Path) -> dict:
    """experience._write_baseline_bundles: one bundle per TRAIN task with its baseline trial packets."""
    path = ctx.run / "experience" / "baseline_source_index.json"
    if path.exists():
        return rj(path)
    recs = records_of(baseline)
    bundles, ev_refs, outcomes, ev_by_task = {}, [], {}, {}
    for tid in ctx.train_ids:
        r = recs[tid]
        rec = rj(Path(r["trajectory_paths"][0]))
        ev = r["evidence_ids"][0]
        packet = trial_packet(rec, ev=ev)
        bundles[tid] = {"task_id": tid, "query": task_query(rec), "trials": [packet],
                        "evaluation_contract": EVALUATION_CONTRACT}
        ev_refs.append(ev)
        ev_by_task[tid] = [ev]
        outcomes[ev] = "pass" if packet["reward"] >= 1.0 else "fail"
    wj(ctx.run / "experience" / "baseline_bundles.json", bundles)
    idx = {"task_ids": list(ctx.train_ids), "evidence_refs": ev_refs, "evidence_by_task": ev_by_task,
           "outcomes": outcomes, "evaluation_contract": EVALUATION_CONTRACT}
    wj(path, idx)
    return idx


def task_groups(ctx: Ctx, task_ids: Sequence[str]) -> list[dict]:
    """ExperienceModule._task_groups: categories of the Task Explorer, chunked by MAX_TASKS_PER_EXPERIENCE_JOB."""
    n = HX.MAX_TASKS_PER_EXPERIENCE_JOB
    if len(task_ids) <= n:
        return [{"id": "selected-01", "task_ids": list(task_ids)}]
    explorer = rj(ctx.run / "discovery" / "task_explorer.json", {}) or {}
    selected = set(task_ids)
    cats = []
    for c in explorer.get("categories") or []:
        members = [str(x) for x in c.get("task_ids") or [] if str(x) in selected]
        if members:
            cats.append((HX._slug(c.get("id") or "category"), members))
    covered = {x for _, m in cats for x in m}
    missing = [x for x in task_ids if x not in covered]
    if missing:
        cats.append(("uncategorized", missing))
    groups = []
    for cid, members in cats:
        for off in range(0, len(members), n):
            groups.append({"id": f"{cid}-{off // n + 1:02d}", "task_ids": members[off:off + n]})
    return groups


def run_experience_baseline(ctx: Ctx, idx: dict) -> dict:
    current = ctx.run / "experience" / "current.json"
    if current.exists():
        return rj(current)
    bundles = rj(ctx.run / "experience" / "baseline_bundles.json")
    authority = HX._outcome_authority(idx)

    def group_job(g: dict) -> dict:
        sel = tuple(g["task_ids"])
        ev = tuple(r for t in sel for r in idx["evidence_by_task"][t])
        outcomes = {r: idx["outcomes"][r] for r in ev}

        def validate(o):
            HX.validate_experience(HX._normalize_in_place(o, ev, outcomes, outcome_authority=authority),
                                   task_ids=sel, evidence_refs=ev, outcomes=outcomes, outcome_authority=authority)

        payload = {"mode": "baseline_group", "group_id": g["id"], "task_ids": list(sel), "evidence_refs": list(ev),
                   "evaluation_contract": EVALUATION_CONTRACT,
                   "instruction": "The controller inlined every task bundle; inspect every one.",
                   "task_bundles": [bundles[t] for t in sel]}
        res = call_role(ctx, job=f"experience.baseline-{g['id']}", system=HX.EXPERIENCE_SYSTEM, payload=payload,
                        validator=validate)
        if res is None:
            raise RuntimeError(f"Experience group {g['id']} failed")
        return HX._ensure_authoritative_failure_dispositions(HX.normalize_experience(res), outcomes=outcomes,
                                                             outcome_authority=authority)

    groups = task_groups(ctx, idx["task_ids"])
    drafts = parallel([lambda g=g: group_job(g) for g in groups])
    if len(drafts) == 1:
        output = drafts[0]
    else:
        catalog = HX._draft_catalog(drafts)
        payload = {"mode": "all_baseline_draft_passages",
                   "passages": [{"source_key": k, "section": v["section"], "text": v["passage"]["text"]}
                                for k, v in catalog.items()],
                   "evaluation_contract": EVALUATION_CONTRACT,
                   "instruction": ("Analyze every passage. Return only justified merges and explicit discards; all "
                                   "other passages are retained automatically.")}
        plan = call_role(ctx, job="experience.baseline-synthesis", system=HX.EXPERIENCE_SYNTHESIS_SYSTEM,
                         payload=payload,
                         validator=lambda o: HX.validate_experience_merge_plan(
                             HX.canonicalize_experience_merge_plan(o), catalog),
                         retry=lambda e: {"retry_context": "Previous merge plan failed validation: " + e})
        if plan is None:
            plan = {"reusable_merges": [], "needs_adjustment_merges": [], "discard_source_keys": []}
            wj(ctx.run / "experience" / "synthesis_fallback.json", {"fallback": "retain_all_validated_drafts"})
        output = HX.materialize_experience_merge_plan(plan, catalog=catalog, task_ids=tuple(idx["task_ids"]),
                                                      evidence_refs=tuple(idx["evidence_refs"]),
                                                      outcomes=idx["outcomes"], outcome_authority=authority)
        output = HX._ensure_authoritative_failure_dispositions(output, outcomes=idx["outcomes"],
                                                               outcome_authority=authority)
        HX.validate_experience(output, task_ids=tuple(idx["task_ids"]), evidence_refs=tuple(idx["evidence_refs"]),
                               outcomes=idx["outcomes"], outcome_authority=authority)
    wj(ctx.run / "experience" / "baseline.json", output)
    wj(current, output)
    return output


# ==================================================================================== analyzer (baseline)

def discovery_bundle(ctx: Ctx) -> dict:
    return {"task_categories": rj(ctx.run / "discovery" / "task_explorer.json"),
            "harness_query": rj(ctx.run / "discovery" / "harness_query.json"),
            "public_environment": rj(ctx.run / "discovery" / "task_explorer_input.json")["environment"]}


def analyzer_side(ctx: Ctx, *, label: str, side: str, experiences: list, disc: dict) -> dict:
    ids = tuple(str(x["id"]) for x in experiences)
    hq = disc["harness_query"]
    contracts = HA._query_channel_contracts(hq)

    def canon(o):
        return HA.canonicalize_analyzer_output(o, harness_query=hq, expected_experience_ids=ids)

    def validate(o):
        HA.validate_analyzer_output(canon(o), side=side, experience_ids=ids, channel_ids=set(contracts),
                                    channel_contracts=contracts, harness="appworld")

    extra = (" Cover every reusable experience with adapter-valid candidates while preserving distinct behavior "
             "hypotheses as distinct candidates. If the previous response was malformed JSON, reduce the number of "
             "candidates and keep skill/instruction text concise; valid JSON is more important than long prose."
             if side == "reusable" else
             " Describe each proposed adjustment as one concrete, evidence-backed Editor brief with observable "
             "checks; omit hypotheses that are not ready for a bounded edit. Do not write manifest_delta or "
             "harness files.")
    payload = {"side": side, "experiences": list(experiences), "task_categories": disc["task_categories"],
               "harness_query": hq, "public_environment": disc["public_environment"],
               "current_harness": {"version": "v0", "candidate_history": []}}
    res = call_role(ctx, job=f"analyzer.{side}-{label}", system=(HA.REUSABLE_ANALYZER_SYSTEM if side == "reusable"
                                                                  else HA.ADJUSTMENT_ANALYZER_SYSTEM),
                    payload=payload, validator=validate,
                    retry=lambda e: {"retry_context": HA.analyzer_retry_context(e) + extra})
    if res is None:
        raise RuntimeError(f"Analyzer {side} failed")
    return canon(res)


def run_analyzer_baseline(ctx: Ctx, experience: dict) -> None:
    root = ctx.run / "analyzer"
    reusable_p, adjust_p = root / "baseline_reusable.json", root / "baseline_adjustment.json"
    disc = discovery_bundle(ctx)
    contracts = HA._query_channel_contracts(disc["harness_query"])

    def reusable() -> dict:
        if reusable_p.exists():
            return rj(reusable_p)
        exps = experience["reusable"]
        if not exps:
            combined = {"coverage": {"experience_ids": [], "public_environment_reviewed": True}, "candidates": [],
                        "compilation_plan": {"groups": []}}
            wj(reusable_p, combined)
            return combined
        ids = tuple(str(x["id"]) for x in exps)
        plan = call_role(ctx, job="analyzer.reusable-plan-baseline", system=HA.REUSABLE_PLANNER_SYSTEM,
                         payload={"experiences": exps, "task_categories": disc["task_categories"],
                                  "maximum_groups": HA.MAX_REUSABLE_COMPILATION_GROUPS},
                         validator=lambda o: HA.validate_reusable_plan(o, experience_ids=ids),
                         retry=lambda e: {"retry_context": HA.analyzer_retry_context(e)})
        if plan is None:
            raise RuntimeError("Reusable Analyzer plan failed")
        by_id = {str(x["id"]): x for x in exps}
        groups = list(plan["groups"])
        outs = parallel([lambda g=g: (str(g["id"]), analyzer_side(
            ctx, label=f"baseline-{g['id']}", side="reusable", experiences=[by_id[str(i)] for i in g["experience_ids"]],
            disc=disc)) for g in groups])
        combined = HA.combine_reusable_outputs(plan=plan, outputs=outs)
        HA.validate_analyzer_output(combined, side="reusable", experience_ids=ids, channel_ids=set(contracts),
                                    channel_contracts=contracts, harness="appworld")
        wj(reusable_p, combined)
        return combined

    def adjustment() -> dict:
        if adjust_p.exists():
            return rj(adjust_p)
        exps = experience["needs_adjustment"]
        ids = tuple(str(x["id"]) for x in exps)
        if not exps:   # partition_adjustment_experiences raises on an empty side (only on an all-pass TRAIN set)
            combined = {"coverage": {"experience_ids": []}, "problems": [], "candidates": [],
                        "analysis_partitions": []}
            wj(adjust_p, combined)
            return combined
        groups = HA.partition_adjustment_experiences(exps)
        outs = parallel([lambda gid=gid, ge=ge: (gid, analyzer_side(ctx, label=f"baseline-{gid}", side="adjustment",
                                                                    experiences=ge, disc=disc)) for gid, ge in groups])
        combined = HA.combine_adjustment_outputs(experience_ids=ids, outputs=outs)
        HA.validate_analyzer_output(combined, side="adjustment", experience_ids=ids, channel_ids=set(contracts),
                                    channel_contracts=contracts, harness="appworld")
        wj(adjust_p, combined)
        return combined

    r, a = parallel([reusable, adjustment])
    wj(root / "baseline_experience_dispositions.json",
       HA.build_experience_dispositions(experience=experience, reusable=r, adjustment=a))


# ============================================================================================ the Main Agent

class Budget:
    """core/budget.py replaced (§9.1): rollouts are what B counts, role and editor calls are tokens.

    The vendored plan/cost functions are written in "creations" (one rollout trial = one creation, one LLM session
    = one creation). Here `remaining` = remaining counted rollouts of B, so the plan sizes screens and
    confirmations by rollouts; LLM sessions cost no rollout (they are bounded by the 10M-token cap)."""

    def __init__(self, ctx: Ctx, cap: int = P.BUDGET_ROLLOUTS):
        self.ctx, self.cap = ctx, cap

    def used(self) -> int:
        return E.counted(CAND) if self.ctx.phase == "search" else 0

    def status(self) -> dict:
        used = self.used()
        tok = opt_llm.totals(CAND)
        return {"total": self.cap, "created": used, "remaining": max(0, self.cap - used), "unit": "counted rollouts",
                "optimizer_tokens": tok["prompt_tokens"] + tok["completion_tokens"],
                "optimizer_token_cap": P.BUDGET_OPT_TOKENS}


def screen_creation_cost(n: int, parent: str) -> int:
    """Rollouts of a paired screen (HM.paired_screen_creation_cost without its LLM-session terms)."""
    return n * 1 + (n if parent != "v0" else 0)


def confirmation_rollouts(n: int) -> int:
    return 2 * n


def rollout_plan(remaining: int, parent: str, unattempted: int) -> dict:
    """HM.build_rollout_budget_plan with SCREEN_TASKS fixed by the plan and rollouts as the unit (§9.1)."""
    buf = 0
    n = SCREEN_TASKS
    full = screen_creation_cost(n, parent) + confirmation_rollouts(n)
    if remaining >= full + buf:
        return {"mode": "standard", "promotion_eligible": True, "minimum_rollout_tasks": n, "rollout_task_limit": n,
                "recommended_rollout_tasks": n, "reserved_future_iteration_creations": 0,
                "screen_creation_cost_at_limit": screen_creation_cost(n, parent),
                "confirmation_creation_cost_at_limit": confirmation_rollouts(n), "remaining_creations": remaining,
                "unit": "counted rollouts"}
    if remaining >= screen_creation_cost(n, parent) + buf:
        return {"mode": "terminal_screen", "promotion_eligible": True, "minimum_rollout_tasks": n,
                "rollout_task_limit": n, "recommended_rollout_tasks": n, "reserved_future_iteration_creations": 0,
                "screen_creation_cost_at_limit": screen_creation_cost(n, parent),
                "confirmation_creation_cost_at_limit": None, "remaining_creations": remaining,
                "unit": "counted rollouts"}
    return {"mode": "stop", "promotion_eligible": False, "minimum_rollout_tasks": 0, "rollout_task_limit": 0,
            "recommended_rollout_tasks": 0, "reserved_future_iteration_creations": 0,
            "screen_creation_cost_at_limit": None, "confirmation_creation_cost_at_limit": None,
            "remaining_creations": remaining, "unit": "counted rollouts"}


class MainDecision:
    def __init__(self, output: dict, path: Path, version: str):
        self.output, self.output_path, self.harness_version = output, str(path), version


class MaterializationError(RuntimeError):
    def __init__(self, cid: str, reason: str):
        self.candidate_id, self.reason = cid, reason
        super().__init__(f"candidate {cid!r} could not be materialized: {reason}")


def portfolio(ctx: Ctx, additional: Sequence[Mapping[str, Any]]) -> tuple[list, dict, dict, dict]:
    """The candidate portfolio of MainAgentModule.decide_and_materialize (lines 1062-1180 of the pin)."""
    idx = rj(ctx.run / "experience" / "baseline_source_index.json")
    ev_to_task = {str(r): str(t) for t, refs in idx["evidence_by_task"].items() for r in refs}
    analyzer = {"reusable": rj(ctx.run / "analyzer" / "baseline_reusable.json"),
                "adjustment": rj(ctx.run / "analyzer" / "baseline_adjustment.json")}
    exp = rj(ctx.run / "experience" / "current.json")
    passages = [*exp["reusable"], *exp["needs_adjustment"]]
    by_id = {str(x["id"]): x for x in passages}
    port = []
    for side in ("reusable", "adjustment"):
        for c in HA.analyzer_candidates(analyzer[side]):
            refs = sorted({str(e) for p in c.get("channel_plan") or [] for e in p.get("experience_ids") or []})
            evs = sorted({str(r) for e in refs for r in by_id.get(e, {}).get("evidence_refs", [])})
            port.append({"side": side, "candidate": c, "experience_ids": refs, "evidence_refs": evs})
    for raw in additional:
        c = dict(raw)
        side = str(c.pop("_portfolio_side", "revision"))
        direct = sorted({str(x) for x in c.pop("_direct_task_ids", ())})
        declared = sorted({str(x) for x in c.pop("_conversion_task_ids", ())})
        prior = dict(c.pop("_prior_train_evidence", {}) or {})
        refs = sorted({str(e) for p in c.get("channel_plan") or [] for e in p.get("experience_ids") or []})
        port.append({"side": side, "candidate": c, "experience_ids": refs,
                     "evidence_refs": sorted({str(r) for e in refs for r in by_id.get(e, {}).get("evidence_refs", [])}),
                     "direct_task_ids": direct, "declared_conversion_task_ids": declared,
                     "prior_train_evidence": prior})
    ids = [str(x["candidate"]["id"]) for x in port]
    if len(ids) != len(set(ids)):
        raise ValueError("Analyzer portfolio candidate IDs must be globally unique")
    port = HM.prioritize_incumbent_controls(port)
    outs = idx.get("outcomes") or {}
    base_outcomes = {str(t): ("pass" if refs and all(str(outs.get(str(r)) or "") == "pass" for r in refs) else "fail")
                     for t, refs in idx["evidence_by_task"].items()}
    port = [{**dict(x), "evidence_profile": HM._baseline_evidence_summary(
        evidence_refs=x.get("evidence_refs") or [], evidence_to_task=ev_to_task, evidence_outcomes=outs)}
            for x in port]
    port = HM.promotion_headroom_portfolio(port, baseline_task_outcomes=base_outcomes)
    return port, ev_to_task, base_outcomes, by_id


def decide_and_materialize(ctx: Ctx, repo: Repo, budget: Budget, *, label: str, candidate_label: str,
                           parent: str, attempted: Sequence[str], accepted: Sequence[Mapping],
                           additional: Sequence[Mapping], history: Sequence[Mapping]) -> MainDecision:
    out_path = ctx.run / "main_agent" / f"{label}.json"
    if out_path.exists():                                   # resume: the materialized decision of this iteration
        d = rj(out_path)
        return MainDecision(d, out_path, d["harness_version"])
    port, ev_to_task, base_outcomes, by_id = portfolio(ctx, additional)
    idx = rj(ctx.run / "experience" / "baseline_source_index.json")
    outs = idx.get("outcomes") or {}
    att = {str(x) for x in attempted}
    all_unattempted = HM.selectable_portfolio(port, attempted_candidate_ids=att)
    available = HM.defer_failure_only_portfolio(HM.selectable_portfolio(port, attempted_candidate_ids=att))
    if not available:
        raise RuntimeError("Analyzer portfolio has no unattempted candidate")
    plan = rollout_plan(budget.status()["remaining"], parent, len(all_unattempted))
    if plan["mode"] == "stop":
        raise RuntimeError("creation budget cannot fund a complete cumulative iteration")
    limit, minimum = int(plan["rollout_task_limit"]), int(plan["minimum_rollout_tasks"])
    status = HM.build_exploration_status(available=available, iteration_history=history, evidence_to_task=ev_to_task,
                                         evidence_outcomes=outs, budget_status=budget.status(),
                                         rollout_task_limit=limit, rollout_budget_plan=plan)
    cand_ev = {str(x["candidate"]["id"]): x["evidence_refs"] for x in available}
    cand_side = {str(x["candidate"]["id"]): str(x["side"]) for x in available}
    cand_direct = {str(x["candidate"]["id"]): x.get("direct_task_ids") or [] for x in available}
    cand_conv = {str(x["candidate"]["id"]): x.get("conversion_task_ids") or [] for x in available}

    def validated(raw: Mapping) -> Mapping:
        n = HM.canonicalize_main_decision(dict(raw))
        sid = str(n.get("selected_candidate_id") or "")
        req = n.get("rollout_request")
        if isinstance(req, Mapping):
            direct = {str(t) for t in cand_direct.get(sid, ())}
            direct.update(str(ev_to_task[r]) for r in cand_ev.get(sid, ()) if r in ev_to_task)
            n["rollout_request"] = {**dict(req), "task_roles": HM.assign_rollout_roles(
                task_ids=req.get("task_ids") or [], conversion_task_ids=cand_conv.get(sid, ()),
                direct_task_ids=direct, baseline_task_outcomes=base_outcomes)}
        HM.validate_main_decision(n, train_task_ids=ctx.train_ids, candidate_evidence=cand_ev,
                                  candidate_sides=cand_side, candidate_direct_tasks=cand_direct,
                                  candidate_conversion_tasks=cand_conv, evidence_to_task=ev_to_task,
                                  baseline_task_outcomes=base_outcomes, min_rollout_tasks=minimum,
                                  max_rollout_tasks=limit)
        return n

    disc = discovery_bundle(ctx)
    relevant_ids = {e for x in available for e in x["experience_ids"]}
    exp = rj(ctx.run / "experience" / "current.json")
    payload = {"candidate_portfolio": available, "discovery": disc,
               "relevant_experiences": [x for x in [*exp["reusable"], *exp["needs_adjustment"]]
                                        if str(x["id"]) in relevant_ids],
               "evidence_to_task": ev_to_task, "train_task_ids": list(ctx.train_ids),
               "promotion_metric": PROMOTION_METRIC, "budget": budget.status(),
               "attempted_candidate_ids": sorted(att), "accepted_candidates": list(accepted),
               "pending_revision_candidate_ids": [str(x.get("id")) for x in additional
                                                  if str(x.get("_portfolio_side", "revision")) == "revision"],
               "incumbent_candidate_ids": [], "exploration_status": status, "parent_version": parent,
               "parent_manifest": repo.surfaces(parent), "rollout_task_limit": limit,
               "minimum_rollout_tasks": minimum, "rollout_budget_plan": plan, "training_rollout_repeats": 1,
               "reserved_future_iteration_creations": plan["reserved_future_iteration_creations"]}
    res = call_role(ctx, job=f"main.{label}", system=HM.MAIN_AGENT_SYSTEM, payload=payload,
                    validator=lambda o: validated(o), attempts=2,
                    retry=lambda e: {"retry_context": ("Previous output was invalid. Select one listed candidate ID "
                                                       "and a budget-bounded set of evidence-grounded task IDs. "
                                                       f"Validation error: {e}")})
    if res is None:
        raise RuntimeError("Main Agent failed")
    decision = dict(validated(res))
    sid = str(decision.pop("selected_candidate_id"))
    rec = next(x for x in available if str(x["candidate"]["id"]) == sid)
    cand = dict(rec["candidate"])
    evidence = [dict(by_id[e]) for e in rec["experience_ids"] if e in by_id]
    try:
        cdir, meta = materialize_selected(ctx, repo, parent=parent, label=label, candidate=cand, evidence=evidence)
    except (RuntimeError, ValueError) as e:
        raise MaterializationError(sid, str(e)) from e
    repo.add(candidate_label, cdir)
    decision["candidate"] = {
        "label": candidate_label, "parent_version": parent, "objective": str(cand.get("objective") or ""),
        "validation": dict(cand.get("validation") or {}),
        **{f: str(cand.get(f) or "") for f in ("observed_terminal_failure", "causal_hypothesis", "intervention_point",
                                               "expected_runtime_event", "falsifying_observation") if cand.get(f)},
        "source_candidate_ids": [sid], "origin_candidate_id": cand.get("origin_candidate_id", sid),
        "micro_adjustments": [], "manifest_delta": {}, **meta, "portfolio_side": rec["side"],
        "prior_train_evidence": dict(rec.get("prior_train_evidence") or {}),
        "conversion_task_ids": list(rec.get("conversion_task_ids") or [])}
    decision["selected_candidate_side"] = rec["side"]
    decision["selected_candidate_priority"] = cand.get("priority")
    decision["evaluation_mode"] = str(plan["mode"])
    decision["promotion_eligible"] = bool(plan["promotion_eligible"])
    decision["rollout_budget_plan"] = plan
    decision["promotion_metric"] = PROMOTION_METRIC
    decision["harness_version"] = candidate_label
    wj(out_path, decision)
    return MainDecision(decision, out_path, candidate_label)


# ========================================================================================= the Harness Editor

def lint_rules_text() -> str:
    hq = harness_query()
    lines = ["Lint rules (the controller rejects a candidate that breaks any of them, without running it):"]
    for m in hq["modifiable_modules"]:
        lines.append(f"- {m['edit_contract']['path']}: " + "; ".join(m["runtime_constraints"]))
    lines.append("- in every file: no task ids, no supervisor names/emails/phone numbers, no 8 consecutive words "
                 "copied from a training task instruction; express learned behavior as a general principle.")
    return "\n".join(lines)


def editor_system_append() -> str:
    """The vendored EDITOR_SYSTEM_PROMPT, verbatim, plus the AppWorld workspace mapping and the lint rules."""
    return (HE.EDITOR_SYSTEM_PROMPT + "\n\nAppWorld port: the isolated candidate tree is `./candidate/` (its four files "
            "are the only harness channels; `home/` does not exist and `project/` is `./candidate/`). The scratch tree "
            "is `./scratch/`. There is no shell; you cannot run the agent, AppWorld or the lint, so check the rules "
            "below by reading your files. Do not create files other than the four channel files.\n\n"
            + lint_rules_text())


def editor_call_args(workspace: Path, prompt: str) -> dict:
    """The exact SB.claude_call arguments of the Harness Editor (for the main session's A9 check)."""
    return {"cand": CAND, "role": "editor", "prompt": prompt, "workspace": workspace, "allowed_tools": EDITOR_TOOLS,
            "max_turns": EDITOR_MAX_TURNS, "system_append": editor_system_append()}


def editor_workspace(job: str, parent_files: Mapping[str, str]) -> Path:
    ws = SB.OPT_ROOT / CAND / job
    shutil.rmtree(ws, ignore_errors=True)
    for rel in SURFACES:
        p = ws / "candidate" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(parent_files.get(rel, ""), encoding="utf-8")
    (ws / "scratch").mkdir(parents=True)
    (ws / "CHANNELS.json").write_text(json.dumps(harness_query(), indent=1), encoding="utf-8")
    return ws


def run_editor(ctx: Ctx, job: str, payload: Mapping[str, Any], parent_files: Mapping[str, str]) -> tuple[dict, dict]:
    """One Harness Editor session; returns (new surface files, summary). Stub mode applies a scripted edit."""
    ws = editor_workspace(job, parent_files)
    prompt = ("INPUT:\n" + json.dumps(payload, ensure_ascii=False, sort_keys=True)
              + "\n\nEdit the files under ./candidate/ now (read ./CHANNELS.json for the channel map), then end with "
                "one JSON object summarizing changed paths, rationale and checks.")
    if ctx.editor_mode == "stub":
        stub = payload.get("_stub_edit") or {"tools/api_notes.json": json.dumps(
            {"api_docs": "Call show_api_doc for an API before its first use to learn its exact parameters."})}
        for rel, text in stub.items():
            (ws / "candidate" / rel).write_text(text, encoding="utf-8")
        summary = {"changed_paths": sorted(stub), "rationale": "stub", "checks": []}
    else:
        res = SB.claude_call(**editor_call_args(ws, prompt))
        if res.get("is_error"):
            raise RuntimeError(f"Harness Editor failed: {res.get('subtype') or res.get('stderr', '')[:300]}")
        try:
            summary = dict(parse_json_object(str(res.get("result") or "")))
        except ValueError:
            summary = {}
    files = {}
    for p in sorted((ws / "candidate").rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(ws / "candidate"))
            files[rel] = p.read_text(encoding="utf-8")
    extra = sorted(set(files) - set(SURFACES))
    wj(ctx.run / "harness_editor" / f"{job}.json", {"files": files, "summary": summary, "extra_files": extra})
    if extra:
        raise ValueError("Harness Editor created files outside the four channels: " + ", ".join(extra))
    return {rel: files.get(rel, "") for rel in SURFACES}, summary


def generalization_check(changed: Mapping[str, str], evidence: Sequence[Mapping]) -> None:
    """harness_editor.validate_editor_candidate_artifacts: changed files must not name experience/evidence ids or
    mixed-case-digit identifiers from the evidence text."""
    forbidden = {str(v) for e in evidence for v in [e.get("id"), *(e.get("evidence_refs") or [])] if str(v or "").strip()}
    text = "\n".join(str(e.get("text") or "") for e in evidence)
    forbidden |= {t for t in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", text)
                  if any(c.islower() for c in t) and any(c.isupper() for c in t) and any(c.isdigit() for c in t)}
    bad = [f"{rel}: {', '.join(sorted(i for i in forbidden if i in body))}" for rel, body in changed.items()
           if any(i in body for i in forbidden)]
    if bad:
        raise ValueError("candidate artifacts must generalize evidence instead of naming it: " + "; ".join(bad))


def preflight(cdir: Path) -> list[str]:
    """Channel preflight (harnesses/channel_preflight.py): the shared lint (prompt renders with its three variables,
    message structure and final block; helper AST lint; notes parse; playbook within M_cap) plus a parse check that
    every public helper is a function. No rollout."""
    v = list(E.lint(cdir))
    hp = Path(cdir) / "tools" / "helpers.py"
    if hp.is_file():
        import ast
        try:
            ast.parse(hp.read_text(encoding="utf-8"))
        except SyntaxError as e:
            v.append(f"tools/helpers.py: does not parse: {e}")
    return v


def materialize_selected(ctx: Ctx, repo: Repo, *, parent: str, label: str, candidate: Mapping,
                         evidence: Sequence[Mapping]) -> tuple[Path, dict]:
    """main_agent.materialize_selected_problem: up to 2 editor attempts, the second with the materialization error."""
    base = {k: candidate[k] for k in ("id", "objective", "channel_plan", "validation") if k in candidate}
    parent_files = repo.surfaces(parent)
    retry = ""
    for attempt in range(2):
        problem = dict(base)
        if retry:
            problem["previous_materialization_error"] = retry
        job = f"editor-{label}" + ("" if attempt == 0 else f"-repair-{attempt + 1:02d}")
        payload = {"target_harness": "appworld",
                   "candidate_tree": {"project": "./candidate", "home": None, "home_maps_to": None},
                   "scratch_tree": "./scratch", "harness_query": harness_query(), "selected_problem": problem,
                   "evidence": [dict(e) for e in evidence], "current_legacy_manifest": {},
                   "current_workspace": {"files": [{"scope": "project", "path": rel, "content": body}
                                                   for rel, body in parent_files.items()]}}
        if isinstance(candidate.get("_stub_edit"), Mapping):
            payload["_stub_edit"] = candidate["_stub_edit"]
        try:
            files, summary = run_editor(ctx, job, payload, parent_files)
            changed = {rel: body for rel, body in files.items() if body != parent_files.get(rel, "")}
            if not changed:
                raise ValueError("Harness Editor completed without changing the candidate workspace")
            generalization_check(changed, evidence)
            actual = {FILE_CHANNEL[rel] for rel in changed}
            HM.validate_candidate_channel_combination(actual)
            declared = {str(p.get("channel_id") or "") for p in candidate.get("channel_plan") or []}
            if declared and declared.isdisjoint(actual):
                raise ValueError("Harness Editor did not implement any declared channel; actual changes="
                                 + ",".join(sorted(actual)))
            cdir = E.materialize(CAND, files, base=repo.dir(parent))
            refs = {c: sorted({str(e) for p in candidate.get("channel_plan") or [] if p.get("channel_id") == c
                               for e in p.get("experience_ids") or []} or
                              {str(e) for p in candidate.get("channel_plan") or [] for e in p.get("experience_ids") or []})
                    for c in actual}
            return cdir, {
                "workspace_diff": [{"scope": "project", "path": rel, "change": "modified"} for rel in sorted(changed)],
                "workspace_delta": {"files": [{"scope": "project", "path": rel, "content": changed[rel]}
                                              for rel in sorted(changed)]},
                "channel_diffs": [{"channel_id": c, "experience_ids": refs[c]} for c in sorted(actual)],
                "workspace_sha256": E.tree_hash(cdir), "editor_summary": summary or None,
                "editor_root": str(SB.OPT_ROOT / CAND / job)}
        except (RuntimeError, ValueError) as e:
            if attempt:
                raise
            retry = str(e)[:1500]
    raise AssertionError("unreachable")


# ============================================================================ comparison, post-analysis, review

def run_comparison(ctx: Ctx, *, label: str, rollout: Path, reference: Path | None) -> tuple[dict, dict]:
    """ExperienceModule.run_comparison: per-task bundles (reference trials vs candidate trials), groups of 3,
    each a draft + a review pass. Reference = the direct parent when it ran, else the frozen v0 baseline."""
    out = ctx.run / "experience" / f"{label}.json"
    idxp = ctx.run / "experience" / f"{label}_source_index.json"
    if out.exists() and idxp.exists():
        return rj(out), rj(idxp)
    base_idx = rj(ctx.run / "experience" / "baseline_source_index.json")
    base_bundles = rj(ctx.run / "experience" / "baseline_bundles.json")
    ro = rj(rollout)
    recs = {r["task_id"]: r for r in ro["records"]}
    ref_recs = {r["task_id"]: r for r in rj(reference)["records"]} if reference else {}
    ref_version = rj(reference)["harness_version"] if reference else ""
    task_ids = tuple(ro["requested_task_ids"])
    idx = {"task_ids": list(task_ids), "bundles": {}, "baseline_by_task": {}, "candidate_by_task": {},
           "outcomes": {}, "reference_versions": {}, "reference_rollout_output": str(reference) if reference else None,
           "evaluation_contract": EVALUATION_CONTRACT}
    for tid in task_ids:
        if tid in ref_recs:
            r = ref_recs[tid]
            refs = list(r["evidence_ids"])
            trials = [trial_packet(rj(Path(r["trajectory_paths"][0])), ev=refs[0])]
            rv = ref_version
        elif ref_version:
            raise ValueError(f"exact parent rollout {ref_version!r} lacks a task")
        else:
            refs = list(base_idx["evidence_by_task"][tid])
            trials = list(base_bundles[tid]["trials"])
            rv = "v0"
        for t in trials:
            idx["outcomes"][t["evidence_id"]] = "pass" if t["reward"] >= 1.0 else "fail"
        c = recs[tid]
        cev = list(c["evidence_ids"])
        crec = rj(Path(c["trajectory_paths"][0]))
        ctrials = [trial_packet(crec, ev=cev[0])]
        idx["outcomes"][cev[0]] = "pass" if ctrials[0]["reward"] >= 1.0 else "fail"
        idx["bundles"][tid] = {"task_id": tid, "query": task_query(crec), "reference_version": rv,
                               "baseline_trials": trials, "candidate_trials": ctrials,
                               "evaluation_contract": EVALUATION_CONTRACT}
        idx["baseline_by_task"][tid] = refs
        idx["candidate_by_task"][tid] = cev
        idx["reference_versions"][tid] = rv
    wj(idxp, idx)

    def group(tids: tuple[str, ...]) -> dict:
        def canon(o):
            return HX.canonicalize_comparison(o, task_ids=tids, index=idx)

        def validate(o):
            HX.validate_comparison(canon(o), task_ids=tids, index=idx)

        suffix = hashlib.sha256("-".join(tids).encode()).hexdigest()[:10]
        draft = call_role(ctx, job=f"experience.compare-{label}-{suffix}", system=HX.COMPARISON_SYSTEM,
                          payload={"task_ids": list(tids), "task_bundles": [idx["bundles"][t] for t in tids],
                                   "instruction": "Read every bundle; channel changes are intentionally hidden.",
                                   "evaluation_contract": EVALUATION_CONTRACT}, validator=validate)
        if draft is None:
            if len(tids) > 1:
                parts = [group((t,)) for t in tids]
                return {k: [x for p in parts for x in p[k]] for k in ("task_comparisons", "reusable",
                                                                      "needs_adjustment")}
            raise RuntimeError("Experience comparison failed")
        draft = canon(draft)
        rev = call_role(ctx, job=f"experience.review-{label}-{suffix}", system=HX.COMPARISON_REVIEW_SYSTEM,
                        payload={"task_ids": list(tids), "draft": draft,
                                 "task_bundles": [idx["bundles"][t] for t in tids],
                                 "evaluation_contract": EVALUATION_CONTRACT}, validator=validate)
        return canon(rev) if rev is not None else draft

    groups = [task_ids[i:i + 3] for i in range(0, len(task_ids), 3)]
    outs = parallel([lambda g=g: group(tuple(g)) for g in groups])
    used: set[str] = set()
    combined = {"task_comparisons": [x for o in outs for x in o["task_comparisons"]],
                "reusable": [HX._comparison_passage(x, used) for o in outs for x in o["reusable"]],
                "needs_adjustment": [HX._comparison_passage(x, used) for o in outs for x in o["needs_adjustment"]],
                "coverage": {"task_ids": list(task_ids),
                             "baseline_refs": [r for t in task_ids for r in idx["baseline_by_task"][t]],
                             "candidate_refs": [r for t in task_ids for r in idx["candidate_by_task"][t]],
                             "reference_versions": dict(idx["reference_versions"])}}
    HX.validate_comparison(combined, task_ids=task_ids, index=idx)
    wj(out, combined)
    return combined, idx


def run_post(ctx: Ctx, *, comparison_label: str, decision: MainDecision, rollout: Path, label: str) -> dict:
    """AnalyzerModule.run_post_rollout: the two post-analyzers; conservative fallback after 3 invalid attempts."""
    baseline = rj(ctx.run / "experience" / "current.json")
    comparison = rj(ctx.run / "experience" / f"{comparison_label}.json")
    d = decision.output
    changed = tuple(str(x["channel_id"]) for x in d["candidate"]["channel_diffs"])
    ro = rj(rollout)
    hq = rj(ctx.run / "discovery" / "harness_query.json")
    available = set(HA._query_channel_contracts(hq))
    common = {"task_comparisons": comparison["task_comparisons"],
              "reference_versions": dict((comparison.get("coverage") or {}).get("reference_versions") or {}),
              "candidate": HA._post_candidate_context(d), "rollout_metrics": dict(ro.get("metrics") or {}),
              "channel_usage": [], "available_channel_ids": sorted(available)}
    statuses = {str(x["task_id"]): str(x["status"]) for x in comparison["task_comparisons"]}
    task_out = {str(x["task_id"]): dict(x.get("outcome_summary") or {}) for x in comparison["task_comparisons"]}

    def side(name: str, bexp: list, cexp: list) -> dict:
        path = ctx.run / "analyzer" / f"{label}_{name}.json"
        if path.exists():
            return rj(path)
        bids, cids = tuple(str(x["id"]) for x in bexp), tuple(str(x["id"]) for x in cexp)
        kw = dict(side=name, baseline_ids=bids, comparison_ids=cids, task_statuses=statuses,
                  changed_channels=set(changed), task_outcomes=task_out)

        def canon(o):
            return HA.canonicalize_post_analyzer_output(o, **kw, available_channel_ids=available)

        cov = {"baseline_experience_ids": list(bids), "comparison_experience_ids": list(cids),
               "task_ids": list(statuses), "channel_usage_reviewed": True}
        res = call_role(ctx, job=f"analyzer.post-{name}-{label}",
                        system=HA.POST_REUSABLE_ANALYZER_SYSTEM if name == "reusable" else HA.POST_ADJUSTMENT_ANALYZER_SYSTEM,
                        payload={"side": name, "baseline_experiences": bexp, "comparison_experiences": cexp,
                                 "expected_coverage": cov, "expected_task_statuses": dict(statuses),
                                 "expected_task_outcomes": task_out, "changed_channel_ids": list(changed), **common},
                        validator=lambda o: HA.validate_post_analyzer_output(canon(o), **kw),
                        retry=lambda e: {"retry_context": (
                            "Previous output failed validation. Copy expected_coverage exactly into coverage. For "
                            "task_assessments, copy each status exactly from expected_task_statuses; do not rename "
                            "statuses to improved, preserved, recovered, or failed. channel_attribution.channel_ids "
                            "may only contain IDs from changed_channel_ids and must name at least one changed channel "
                            "unless the relation is random. Review channel usage and distinguish availability from "
                            "invocation.")},
                        max_tokens=POST_MAX_TOKENS)
        if res is not None:
            out = canon(res)
        else:
            out = HA.conservative_post_analyzer_fallback(
                side=name, baseline_ids=bids, comparison_ids=cids, task_statuses=statuses, changed_channels=changed,
                task_outcomes=task_out, task_comparisons=comparison["task_comparisons"], failure="3 invalid outputs")
            wj(ctx.run / "analyzer" / f"{label}_{name}_fallback.json", {"attempts": 3})
        wj(path, out)
        return out

    r, a = parallel([lambda: side("reusable", baseline["reusable"], comparison["reusable"]),
                     lambda: side("adjustment", baseline["needs_adjustment"], comparison["needs_adjustment"])])
    return {"reusable": r, "adjustment": a}


def reference_metrics(idx: Mapping) -> dict:
    """controller.reference_metrics_from_comparison_index on the in-memory index."""
    outcomes, by_task = idx.get("outcomes") or {}, idx.get("baseline_by_task") or {}
    ok = n = p2 = 0
    for refs in by_task.values():
        ordered = [str(outcomes.get(str(r)) or "") for r in refs]
        if not ordered or set(ordered) - {"pass", "fail"}:
            raise ValueError("comparison reference outcomes are incomplete")
        ok += sum(o == "pass" for o in ordered)
        n += len(ordered)
        p2 += int("pass" in ordered[:2])
    return {"pass_at_1": ok / n, "pass_at_2": p2 / len(by_task)}


def finalize_review(ctx: Ctx, budget: Budget, *, decision: MainDecision, post: dict, post_label: str,
                    rollout: Path, ref_metrics: dict, require_improvement: bool, label: str,
                    base_version: str) -> MainDecision:
    """MainAgentModule.finalize (publish=False): the review Main Agent, validated; deterministic reject fallback."""
    out_path = ctx.run / "main_agent" / f"{label}.json"
    if out_path.exists():
        d = rj(out_path)
        return MainDecision(d, out_path, d["selected_version"])
    tested = decision.output
    reusable, adjustment = post["reusable"], post["adjustment"]
    hq = rj(ctx.run / "discovery" / "harness_query.json")
    revision_channels = set(HA._query_channel_contracts(hq))
    cand_v = str(tested["harness_version"])
    ro = rj(rollout)
    task_ids = tuple(ro["requested_task_ids"])
    st = budget.status()
    remaining = st["remaining"]

    def canon(o):
        return HM.normalize_budget_disposition(HM.canonicalize_final_decision(
            dict(o), candidate_version=cand_v, base_version=base_version, reusable=reusable, adjustment=adjustment,
            tested_candidate=tested["candidate"]), remaining_after_decision=remaining)

    def validate(o):
        HM.validate_final_decision(canon(o), candidate_version=cand_v, task_ids=task_ids, reusable=reusable,
                                   adjustment=adjustment, budget_status=st, base_version=base_version,
                                   remaining_after_decision=remaining, tested_candidate=tested["candidate"],
                                   revision_channel_ids=revision_channels, rollout_metrics=ro["metrics"],
                                   reference_rollout_metrics=ref_metrics, promotion_metric=PROMOTION_METRIC,
                                   require_primary_metric_improvement=require_improvement,
                                   promotion_eligible=bool(tested.get("promotion_eligible", True)))

    allowed_exp = ", ".join(sorted({str(i) for p in tested["candidate"].get("channel_diffs") or []
                                    for i in p.get("experience_ids") or []}))
    payload = {"post_analyzer": {"reusable": reusable, "adjustment": adjustment},
               "tested_candidate": {"version": cand_v, "parent_version": base_version,
                                    "channel_diffs": tested["candidate"]["channel_diffs"],
                                    "manifest_delta": tested["candidate"]["manifest_delta"],
                                    "workspace_diff": tested["candidate"].get("workspace_diff", []),
                                    "workspace_delta": tested["candidate"].get("workspace_delta", {"files": []}),
                                    "workspace_sha256": tested["candidate"].get("workspace_sha256", ""),
                                    "editor_summary": tested["candidate"].get("editor_summary"),
                                    "portfolio_side": tested["candidate"].get("portfolio_side"),
                                    "prior_train_evidence": dict(tested["candidate"].get("prior_train_evidence") or {}),
                                    "evaluation_mode": str(tested.get("evaluation_mode") or "standard"),
                                    "promotion_eligible": bool(tested.get("promotion_eligible", True))},
               "rollout_metrics": ro["metrics"], "reference_rollout_metrics": dict(ref_metrics),
               "promotion_metric": PROMOTION_METRIC,
               "promotion_metric_values": {"candidate": HM._required_metric(ro["metrics"], PROMOTION_METRIC, side="c"),
                                           "reference": HM._required_metric(ref_metrics, PROMOTION_METRIC, side="r")},
               "require_primary_metric_improvement": require_improvement, "rolled_out_task_ids": list(task_ids),
               "budget": st, "remaining_after_this_main_creation": remaining,
               "next_iteration_budget_plans": {"if_parent_kept": rollout_plan(remaining, base_version, 2),
                                               "if_candidate_promoted": rollout_plan(remaining, cand_v, 2)},
               "discovered_revision_channel_ids": sorted(revision_channels)}
    res = call_role(ctx, job=f"main.{label}", system=HM.FINAL_MAIN_AGENT_SYSTEM, payload=payload, validator=validate,
                    attempts=2, retry=lambda e: {"retry_context": (
                        "Previous output failed validation: " + e + " Follow the preservation regression gate and do "
                        "not invent an untested accepted version. selected_version must be exactly "
                        f"{cand_v!r} for accept_delta or {base_version!r} for reject_delta/revise_delta. If you return "
                        "revise_delta, every revision_candidate.channel_plan[].experience_ids item must be copied from "
                        "the tested candidate's channel_diffs only: " + allowed_exp
                        + ". Do not introduce new experience IDs.")})
    if res is not None:
        out = dict(canon(res))
    else:
        out = HM.deterministic_reject_decision(base_version=base_version, reusable=reusable, adjustment=adjustment,
                                               remaining=remaining, failure_reason="no valid review decision")
    out["tested_candidate_version"] = cand_v
    out["rollout_output"] = str(rollout)
    wj(out_path, out)
    return MainDecision(out, out_path, str(out["selected_version"]))


def review_pair(ctx: Ctx, budget: Budget, *, decision: MainDecision, rollout: Path, parent_rollout: Path | None,
                comparison_label: str, post_label: str, review_label: str, base_version: str,
                require_improvement: bool) -> MainDecision:
    _, idx = run_comparison(ctx, label=comparison_label, rollout=rollout, reference=parent_rollout)
    post = run_post(ctx, comparison_label=comparison_label, decision=decision, rollout=rollout, label=post_label)
    return finalize_review(ctx, budget, decision=decision, post=post, post_label=post_label, rollout=rollout,
                           ref_metrics=reference_metrics(idx), require_improvement=require_improvement,
                           label=review_label, base_version=base_version)


# ============================================================================================= the controller

class Review:
    """MainDecision-compatible wrapper for the vendored controller helpers (.output / .harness_version)."""

    def __init__(self, md: MainDecision):
        self.output, self.output_path, self.harness_version = md.output, md.output_path, md.harness_version


def checkpoint(ctx: Ctx, stage: str, details: dict, budget: Budget) -> None:
    wj(ctx.run / "controller_state.json", {"stage": stage, "details": details, "budget": budget.status(), "t": utc()})


def confirmation_tasks(ctx: Ctx, decision: MainDecision, screen_review: MainDecision, screen_ids: Sequence[str],
                       count: int) -> tuple[str, ...]:
    """controller.select_confirmation_task_ids on the port's run root (it reads the same three files)."""
    return HC.select_confirmation_task_ids(run_root=ctx.run, decision=decision, screen_review=screen_review,
                                           screen_task_ids=screen_ids, task_count=count)


def write_progress(ctx: Ctx, budget: Budget, history: list, accepted: list, current: str, stage: str) -> None:
    if ctx.phase != "search":
        return
    tok = opt_llm.totals(CAND)
    st = budget.status()
    rate = None
    try:
        rows = P.read_jsonl(P.AW_STATE / CAND / "rollouts.jsonl")
        if len(rows) >= 20:
            import datetime as dt
            t0 = dt.datetime.strptime(rows[0]["t"], "%Y-%m-%dT%H:%M:%SZ")
            t1 = dt.datetime.strptime(rows[-1]["t"], "%Y-%m-%dT%H:%M:%SZ")
            rate = len(rows) / max(60.0, (t1 - t0).total_seconds())
    except (KeyError, ValueError):
        rate = None
    best = None
    for h in history:
        if h.get("review_decision") == "accept_delta":
            best = (h.get("rollout_metrics") or {}).get("pass_at_1")
    P.write_json(P.PUSHED / CAND / "progress.json", {
        "stage": stage, "iteration": len(history), "accepted": len(accepted),
        "rejected": sum(1 for h in history if h.get("selected_version") == h.get("parent_version")),
        "materialization_or_preflight_failures": sum(1 for h in history if h.get("evaluation_mode") in
                                                     ("materialization", "channel_preflight")),
        "current_version": current, "counted_rollouts": st["created"], "budget_rollouts": P.BUDGET_ROLLOUTS,
        "cache_hits": E.cache_hits(CAND), "optimizer_calls": tok["calls"],
        "optimizer_tokens_in": tok["prompt_tokens"], "optimizer_tokens_out": tok["completion_tokens"],
        "optimizer_cache_read": tok["cache_read"], "proxy_usd": opt_llm.proxy_usd(tok),
        "best_search_score": best, "best_search_label": "pass@1 of the last accepted confirmation (10 TRAIN tasks; "
                                                        "selection-biased)",
        "eta": (f"about {(st['remaining'] / rate) / 3600:.1f} h of rollouts left at the current rate" if rate else None),
        "t": utc()})


def controller(ctx: Ctx, *, budget: Budget, max_iterations: int | None = None) -> dict:
    """A line-by-line port of IterationController._run_locked (pin controller.py:119-606)."""
    repo = Repo(ctx.run)
    if not (ctx.run / "versions.json").exists():
        repo.add("v0", P.SEED_CAP)
    baseline = run_version(ctx, repo, "v0", ctx.train_ids, "baseline")          # the shared seed (cache)
    checkpoint(ctx, "baseline_ready", {"baseline": str(baseline)}, budget)
    base_recs = {r["task_id"]: rj(Path(r["trajectory_paths"][0])) for r in rj(baseline)["records"]}
    run_discovery(ctx, base_recs)
    checkpoint(ctx, "discovery_complete", {}, budget)
    idx = baseline_source_index(ctx, baseline)
    exp = run_experience_baseline(ctx, idx)
    checkpoint(ctx, "experience_complete", {}, budget)
    run_analyzer_baseline(ctx, exp)
    checkpoint(ctx, "analyzer_complete", {}, budget)

    st = rj(ctx.run / "loop_state.json", None) or {"attempted": [], "accepted": [], "revisions": [], "history": [],
                                                   "iteration": 1, "current": "v0"}
    attempted, accepted, revisions, history = st["attempted"], st["accepted"], st["revisions"], st["history"]
    current, it = st["current"], st["iteration"]

    def save():
        wj(ctx.run / "loop_state.json", {"attempted": attempted, "accepted": accepted, "revisions": revisions,
                                         "history": history, "iteration": it, "current": current})

    write_progress(ctx, budget, history, accepted, current, "search running")
    stop_reason = None
    while True:
        if max_iterations is not None and it > max_iterations:
            stop_reason = "max_iterations (acceptance dry run)"
            break
        if opt_llm.totals(CAND)["prompt_tokens"] + opt_llm.totals(CAND)["completion_tokens"] >= P.BUDGET_OPT_TOKENS:
            stop_reason = "optimizer token cap"
            break
        label = f"iteration-{it:02d}"
        resuming = (ctx.run / "main_agent" / f"{label}.json").exists()
        if not resuming and budget.status()["remaining"] < screen_creation_cost(SCREEN_TASKS, current):
            stop_reason = "budget below one screen"
            break
        try:
            decision = decide_and_materialize(ctx, repo, budget, label=label, candidate_label=f"candidate-{it:02d}",
                                              parent=current, attempted=attempted, accepted=accepted,
                                              additional=revisions, history=history)
        except MaterializationError as e:
            attempted.append(e.candidate_id)
            history.append({"iteration": it, "candidate_id": e.candidate_id, "origin_candidate_id": e.candidate_id,
                            "parent_version": current, "candidate_version": "", "evaluation_mode": "materialization",
                            "promotion_eligible": False, "promotion_metric": PROMOTION_METRIC,
                            "rollout_task_ids": [], "rollout_metrics": {}, "review_decision": "materialization_failed",
                            "selected_version": current, "review_rationale": e.reason[:2000],
                            "review_evidence": {"recovered_task_ids": [], "preserved_task_ids": [],
                                                "attributable_regression_task_ids": [],
                                                "unresolved_findings": [e.reason[:2000]]},
                            "revision_candidate_id": None})
            it += 1
            save()
            log("search", f"{label}: materialization failed")
            write_progress(ctx, budget, history, accepted, current, "search running")
            continue
        except RuntimeError as e:
            if "no unattempted candidate" in str(e) or "cannot fund a complete cumulative iteration" in str(e):
                stop_reason = str(e)
                break
            raise
        HC.assert_candidate_extends_champion(current_version=current, decision=decision)
        source_id = str(decision.output["candidate"]["source_candidate_ids"][0])
        if source_id not in attempted:
            attempted.append(source_id)
        save()
        pre = preflight(repo.dir(decision.harness_version))       # channel preflight: no rollout (§9.1)
        wj(ctx.run / "channel_preflight" / f"{label}-{decision.harness_version}.json", {"violations": pre})
        if pre:
            history.append({"iteration": it, "candidate_id": source_id, "origin_candidate_id": source_id,
                            "parent_version": current, "candidate_version": decision.harness_version,
                            "evaluation_mode": "channel_preflight", "promotion_eligible": False,
                            "promotion_metric": PROMOTION_METRIC, "rollout_task_ids": [], "rollout_metrics": {},
                            "review_decision": "channel_preflight_failed", "selected_version": current,
                            "review_rationale": "; ".join(pre)[:2000],
                            "review_evidence": {"recovered_task_ids": [], "preserved_task_ids": [],
                                                "attributable_regression_task_ids": [],
                                                "unresolved_findings": pre[:20]},
                            "revision_candidate_id": None})
            P.append_jsonl(STATE_DIR / "preflight_rejects.jsonl", {"t": utc(), "iteration": it,
                                                                    "violations": len(pre)})
            it += 1
            save()
            log("search", f"{label}: channel preflight failed ({len(pre)} violation(s)), no rollout")
            write_progress(ctx, budget, history, accepted, current, "search running")
            continue
        screen_ids = list(decision.output["rollout_request"]["task_ids"])
        rollout, parent_rollout = run_pair(ctx, repo, current, decision.harness_version, screen_ids,
                                           f"{label}-{decision.harness_version}")
        checkpoint(ctx, f"{label}_rollout_complete", {"rollout": str(rollout)}, budget)
        mode = str(decision.output.get("evaluation_mode") or "standard")
        post_label = f"{label}-post"
        screen = review_pair(ctx, budget, decision=decision, rollout=rollout, parent_rollout=parent_rollout,
                             comparison_label=f"{label}-comparison", post_label=post_label,
                             review_label=f"{label}-review", base_version=current,
                             require_improvement=(mode == "terminal_screen"))
        review = screen
        confirm = None
        if str(screen.output.get("decision") or "") in {"accept_delta", "confirm_delta"} and \
                HC._evaluation_requires_confirmation(mode):
            need = confirmation_rollouts(CONFIRM_TASKS)
            clabel = f"{label}-confirm-{decision.harness_version}"
            cached = (ctx.run / "rollout" / f"{clabel}.json").exists()
            if cached or budget.status()["remaining"] >= need:
                cids = confirmation_tasks(ctx, decision, screen, screen_ids, CONFIRM_TASKS)
                # pairing_offset = TRAIN_ROLLOUT_REPEATS: the parent always reruns (even v0) on the confirmation set
                crollout, cparent = run_pair(ctx, repo, current, decision.harness_version, list(cids), clabel,
                                             pairing_offset=1)
                confirm = (crollout, cparent)
                checkpoint(ctx, f"{label}_confirmation_rollout_complete", {"rollout": str(crollout)}, budget)
                post_label = f"{label}-confirmation-post"
                review = review_pair(ctx, budget, decision=decision, rollout=crollout, parent_rollout=cparent,
                                     comparison_label=f"{label}-confirmation-comparison", post_label=post_label,
                                     review_label=f"{label}-confirmation-review", base_version=current,
                                     require_improvement=True)
            else:
                review = MainDecision(*_reject_unconfirmed(ctx, screen, current, label))
        if HC._evaluation_requires_confirmation(mode):
            HC.assert_confirmed_promotion(decision=decision, review=Review(review), confirmation_pair=confirm)
        eff = confirm[0] if confirm else rollout
        effo = rj(eff)
        record = {"iteration": it, "candidate_id": source_id,
                  "origin_candidate_id": decision.output["candidate"].get("origin_candidate_id", source_id),
                  "parent_version": current, "candidate_version": decision.harness_version,
                  "candidate_side": decision.output.get("selected_candidate_side"), "evaluation_mode": mode,
                  "promotion_eligible": bool(decision.output.get("promotion_eligible", True)),
                  "promotion_metric": PROMOTION_METRIC, "channel_diffs": decision.output["candidate"]["channel_diffs"],
                  "workspace_sha256": decision.output["candidate"].get("workspace_sha256", ""),
                  "editor_summary": decision.output["candidate"].get("editor_summary"),
                  "rollout_task_ids": effo["requested_task_ids"],
                  "rollout_task_roles": dict((decision.output.get("rollout_request") or {}).get("task_roles") or {}),
                  "review_decision": review.output["decision"], "selected_version": review.harness_version,
                  "post_label": post_label, "rollout_metrics": dict(effo["metrics"]),
                  "review_rationale": review.output.get("rationale"), "review_evidence": review.output.get("evidence"),
                  "screen_rollout_task_ids": rj(rollout)["requested_task_ids"],
                  "screen_rollout_metrics": dict(rj(rollout)["metrics"]),
                  "screen_review_decision": screen.output.get("decision"),
                  "confirmation_rollout_task_ids": effo["requested_task_ids"] if confirm else None,
                  "confirmation_review_decision": review.output.get("decision") if confirm else None,
                  "revision_candidate_id": (review.output.get("revision_candidate") or {}).get("id"),
                  "replan_candidate_id": None}
        history.append(record)
        current, advanced = HC.advance_cumulative_version(current_version=current, decision=decision,
                                                          review=Review(review))
        if advanced:
            accepted.append({**record, "manifest_delta": {}, "origin_candidate_id": record["origin_candidate_id"]})
        rev = HC.revision_candidate_from_review(review.output, rollout_task_ids=effo["requested_task_ids"])
        if rev is not None:
            revisions.append(rev)
        adj = rj(ctx.run / "analyzer" / f"{post_label}_adjustment.json")
        rep = HC.replan_candidate_from_review(review.output, adjustment=adj,
                                              rollout_task_ids=effo["requested_task_ids"])
        if rep is not None:
            revisions.append(rep)
            record["replan_candidate_id"] = rep["id"]
        it += 1
        save()
        checkpoint(ctx, f"{label}_reviewed", {"accepted_count": len(accepted)}, budget)
        log("search", f"{label}: {review.output['decision']} -> {current}; counted {budget.status()['created']}")
        write_progress(ctx, budget, history, accepted, current, "search running")
        _milestones(ctx, budget, history, accepted, current, advanced)
    final = {"selected_version": current, "selected_dir": str(repo.dir(current)), "iterations": len(history),
             "accepted": len(accepted), "stop_reason": stop_reason, "budget": budget.status(), "t": utc()}
    wj(ctx.run / "final.json", final)
    checkpoint(ctx, "finalized", final, budget)
    write_progress(ctx, budget, history, accepted, current, f"search finished ({stop_reason})")
    return final


def _reject_unconfirmed(ctx: Ctx, screen: MainDecision, parent: str, label: str):
    payload = dict(screen.output)
    payload["decision"] = "reject_delta"
    payload["selected_version"] = str(parent)
    payload["rationale"] = ("The screen passed, but independent confirmation was not affordable. "
                            "Keep the current champion rather than promote provisional evidence.")
    ev = dict(payload.get("evidence") or {})
    ev["unresolved_findings"] = list(ev.get("unresolved_findings") or []) + [
        "Fresh-seed confirmation was not run within the remaining budget."]
    payload["evidence"] = ev
    payload.pop("revision_candidate", None)
    p = ctx.run / "main_agent" / f"{label}-confirmation-unavailable.json"
    wj(p, payload)
    return payload, p, str(parent)


def _milestones(ctx: Ctx, budget: Budget, history: list, accepted: list, current: str, advanced: bool) -> None:
    """Ledger entries and issue posts at an accepted candidate and every 25% of B (§8). Search only."""
    if ctx.phase != "search":
        return
    import post as POST
    import status_doc as S
    used = budget.status()["created"]
    q = int(4 * used / P.BUDGET_ROLLOUTS)
    st = rj(STATE_DIR / "milestones.json", {}) or {}
    tok = opt_llm.totals(CAND)
    counts = {"harnesslens": {"counted_rollouts": used, "iterations": len(history), "accepted": len(accepted),
                              "cache_hits": E.cache_hits(CAND)}}
    spend = {"harnesslens": {"in": tok["prompt_tokens"], "out": tok["completion_tokens"],
                             "cache_read": tok["cache_read"], "usd": opt_llm.proxy_usd(tok)}}
    msgs = []
    if advanced:
        msgs.append(("accepted", f"accept_{len(accepted)}",
                     f"Iteration {len(history)} accepted a candidate ({current}); {len(accepted)} accepted so far."))
    for k in range(1, 5):
        if q >= k and not st.get(f"q{k}"):
            st[f"q{k}"] = True
            msgs.append(("budget", f"budget_{25 * k}", f"{25 * k}% of B reached: {used} of {P.BUDGET_ROLLOUTS} "
                                                         f"counted rollouts after {len(history)} iterations."))
    P.write_json(STATE_DIR / "milestones.json", st)
    for kind, key, text in msgs:
        try:
            S.append("result", "P4", "harnesslens search", f"HarnessLens: {text} Accepted {len(accepted)}; optimizer "
                     f"{tok['calls']} calls, proxy ${opt_llm.proxy_usd(tok)}.", extra={"candidate": CAND,
                     "counts": counts, "spend": spend}, subject=f"harnesslens {key}")
            POST.post(CAND, key, f"HarnessLens search: {kind}", text + " Counts only; search-time scores are "
                      "selection-biased (10-task TRAIN confirmations).")
        except Exception as e:  # noqa: BLE001 — never kill the search for a post; the failure is logged
            log("search", f"milestone {key} not published: {type(e).__name__}: {e}"[:300])


# ======================================================================================== sub-commands

def cmd_search() -> int:
    if not (P.AW_STATE / "SEED_BASELINE_DONE").exists():
        raise SystemExit("P3 (the shared seed baseline) is not done; refusing to start the search (rule Q4)")
    train = E.split_ids("train")
    ctx = Ctx(run=RUN, phase="search", train_ids=train)
    budget = Budget(ctx)
    lock = open(STATE_DIR / "search.lock", "a")
    import fcntl
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("another harnesslens search is running")
    log("search", f"start; counted so far {budget.status()['created']}")
    try:
        final = controller(ctx, budget=budget)
    except (E.BudgetExceeded, opt_llm.BudgetExceeded) as e:
        # §7.4: the hard cap fired first; freeze the last accepted parent (saved before the abandoned step)
        st = rj(RUN / "loop_state.json", {}) or {}
        final = {"selected_version": st.get("current", "v0"),
                 "selected_dir": str(Repo(RUN).dir(st.get("current", "v0"))), "stop_reason": f"BudgetExceeded: {e}",
                 "budget": budget.status(), "t": utc()}
        wj(RUN / "final.json", final)
        write_progress(ctx, budget, st.get("history", []), st.get("accepted", []), final["selected_version"],
                       "search finished (hard cap)")
    log("search", f"done: {final.get('stop_reason')}; selected {final['selected_version']}")
    print(json.dumps({k: final[k] for k in ("selected_version", "stop_reason")}))
    return 0


def cmd_freeze() -> int:
    final = rj(RUN / "final.json")
    if not final:
        raise SystemExit("no finished search (run/final.json missing)")
    src = Path(final["selected_dir"])
    v = E.lint(src)
    if v:
        raise SystemExit(f"selected candidate fails the lint: {v}")
    out = P.PUSHED / CAND / "artifact"
    shutil.rmtree(out, ignore_errors=True)
    files = E.read_surfaces(src)
    for rel, text in files.items():
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_text(text, encoding="utf-8")
    inert = final["selected_version"] == "v0"
    seed = E.read_surfaces(P.SEED_CAP)
    P.write_json(out / "FREEZE.json", {
        "selected_version": final["selected_version"], "inert": inert, "stop_reason": final.get("stop_reason"),
        "tree_sha256": E.tree_hash(src), "files_changed_vs_seed": sorted(r for r in set(files) | set(seed)
                                                                         if files.get(r) != seed.get(r)),
        "iterations": final.get("iterations"), "accepted": final.get("accepted"), "t": utc()})
    print(json.dumps({"frozen": final["selected_version"], "inert": inert, "tree": E.tree_hash(src)[:16]}))
    return 0


# ======================================================================================== acceptance

def _accept_ctx(name: str, **kw) -> Ctx:
    return Ctx(run=STATE_DIR / "accept" / name, phase="accept", **kw)


def accept_offline() -> dict:
    """Offline unit test: stub evaluator and stub LM through the whole controller (1 iteration, confirmation)."""
    import random
    rng = random.Random(0)
    train = [f"t{i:03d}" for i in range(20)]
    seed_reward = {t: float(i % 3 == 0) for i, t in enumerate(train)}
    calls = {"eval": 0, "chat": 0}

    def fake_eval(cand, cdir, task_ids, *, phase, tag):
        calls["eval"] += len(task_ids)
        is_seed = Path(cdir) == P.SEED_CAP
        out = []
        for t in task_ids:
            r = seed_reward.get(t, 0.0) if is_seed else 1.0
            out.append({"task_id": t, "instruction": f"do thing {t}", "reward": r, "error": None, "lint_reject": False,
                        "steps": [{"thought": "think", "code": "print(1)", "output": "1"}], "pass_count": int(r),
                        "num_tests": 1, "failed_requirements": [] if r else ["requirement text"],
                        "collateral_damage": False, "complete_task_called": True, "termination": "completed",
                        "api_errors": 0})
        return out

    def fake_chat(user, *, cand, role, system, max_tokens):
        calls["chat"] += 1
        inp = json.loads(user.split("INPUT:\n", 1)[1])
        return json.dumps(_stub_role(system, inp, rng))

    ctx = _accept_ctx("offline" + ("-reject" if os.environ.get("HL_STUB_REVIEW") == "reject" else ""), train_ids=train, editor_mode="stub", evaluate=fake_eval, chat=fake_chat)
    shutil.rmtree(ctx.run, ignore_errors=True)
    ctx.run.mkdir(parents=True)
    final = controller(ctx, budget=Budget(ctx, cap=900), max_iterations=1)
    hist = rj(ctx.run / "loop_state.json")["history"]
    return {"final": final["selected_version"], "iterations": len(hist), "review": hist[0]["review_decision"],
            "screen_review": hist[0]["screen_review_decision"],
            "confirmation_ran": hist[0]["confirmation_rollout_task_ids"] is not None,
            "eval_episode_requests": calls["eval"], "chat_calls": calls["chat"]}


def _stub_role(system: str, inp: dict, rng) -> dict:
    """Deterministic minimal valid outputs for each vendored role prompt (offline test only)."""
    if system == HD.TASK_EXPLORER_SYSTEM:
        ids = [t["task_id"] for t in inp["tasks"]]
        return {"categories": [{"id": "all", "name": "all", "purpose": "everything", "task_ids": ids}], "notes": []}
    if system == HX.EXPERIENCE_SYSTEM:
        ev = inp["evidence_refs"]
        outcomes = {b["trials"][0]["evidence_id"]: b["trials"][0]["reward"] for b in inp["task_bundles"]}
        good = [e for e in ev if outcomes[e] >= 1] or ev[:1]
        bad = [e for e in ev if outcomes[e] < 1]
        return {"reusable": [{"id": f"r-{inp['group_id']}", "text": "x" * 90, "evidence_refs": good}] if any(
            outcomes[e] >= 1 for e in ev) else [],
                "needs_adjustment": [{"id": f"a-{inp['group_id']}", "text": "y" * 90, "evidence_refs": bad}] if bad
                else [], "coverage": {"task_ids": inp["task_ids"], "evidence_refs": ev}}
    if system == HX.EXPERIENCE_SYNTHESIS_SYSTEM:
        return {"reusable_merges": [], "needs_adjustment_merges": [], "discard_source_keys": []}
    if system == HA.REUSABLE_PLANNER_SYSTEM:
        return {"groups": [{"id": "g1", "experience_ids": [e["id"] for e in inp["experiences"]]}]}
    if system == HA.REUSABLE_ANALYZER_SYSTEM:
        ids = [e["id"] for e in inp["experiences"]]
        return {"coverage": {"experience_ids": ids, "public_environment_reviewed": True},
                "candidates": [{"id": "c1", "priority": 1, "objective": "o", "channel_plan": [
                    {"channel_id": "tool_description", "operation": "add", "experience_ids": ids, "rationale": "r"}],
                                "validation": {"local_behavior_checks": ["k"]}}]}
    if system == HA.ADJUSTMENT_ANALYZER_SYSTEM:
        ids = [e["id"] for e in inp["experiences"]]
        refs = [r for e in inp["experiences"] for r in e["evidence_refs"]]
        return {"coverage": {"experience_ids": ids}, "problems": [
            {"id": "p1", "priority": 1, "summary": "s", "experience_ids": ids, "evidence_refs": refs,
             "channel_hypotheses": [{"channel_id": "tool_description", "reason": "r"}], "modification_direction": "d",
             "diagnostic_rollout_needed": True, "local_success_criteria": ["c"], "candidate_id": "ca1"}],
                "candidates": [{"id": "ca1", "priority": 1, "objective": "o", "observed_terminal_failure": "f",
                                "causal_hypothesis": "h", "intervention_point": "i", "expected_runtime_event": "e",
                                "falsifying_observation": "x", "channel_plan": [
                        {"channel_id": "tool_description", "operation": "add", "experience_ids": ids, "rationale": "r"}],
                                "validation": {"local_behavior_checks": ["k"]}}]}
    if system == HM.MAIN_AGENT_SYSTEM:
        c = inp["candidate_portfolio"][0]
        conv = c["conversion_task_ids"]
        ids = list(dict.fromkeys(conv + inp["train_task_ids"]))[:inp["rollout_task_limit"]]
        cid = c["candidate"]["id"]
        return {"decision": "materialize_and_rollout", "selected_candidate_id": cid,
                "exploration_plan": {"open_problem_ids": [cid], "chosen_problem_id": cid, "budget_strategy": "b",
                                     "turning_point": "t"},
                "rollout_request": {"task_ids": ids, "rationale": "r", "local_success_criteria": ["c"]}}
    if system in (HX.COMPARISON_SYSTEM, HX.COMPARISON_REVIEW_SYSTEM):
        b = inp["task_bundles"]
        return {"task_comparisons": [{"task_id": x["task_id"], "status": "recovered", "text": "z" * 90,
                                      "baseline_refs": [], "candidate_refs": []} for x in b],
                "reusable": [], "needs_adjustment": [], "coverage": {}}
    if system == HA.POST_REUSABLE_ANALYZER_SYSTEM:
        return {"coverage": inp["expected_coverage"], "preservation": {
            "attributable_regressions": [], "preserved_task_ids": list(inp["expected_task_statuses"]),
            "candidate_recommendation": "accept", "rationale": "r"}}
    if system == HA.POST_ADJUSTMENT_ANALYZER_SYSTEM:
        ch = inp["changed_channel_ids"]
        return {"coverage": inp["expected_coverage"], "primary_problem": {
            "summary": "s", "task_assessments": [
                {"task_id": t, "status": s, "relation": "attributed" if s in ("recovered", "stable_success")
                 else "not_attributed", "evidence_refs": ["e"], "reason": "r"}
                for t, s in inp["expected_task_statuses"].items()],
            "channel_attribution": {"relation": "attributed", "channel_ids": ch, "reason": "r"},
            "local_recovery": "l", "recommendation": "accept", "further_rollout_needed": False},
                "replan_candidate": None}
    if system == HM.FINAL_MAIN_AGENT_SYSTEM:
        v = inp["tested_candidate"]["version"]
        if os.environ.get("HL_STUB_REVIEW") == "reject":
            return {"decision": "reject_delta", "selected_version": inp["tested_candidate"]["parent_version"],
                    "rationale": "r", "evidence": {}, "budget_disposition": {}}
        return {"decision": "accept_delta", "selected_version": v, "rationale": "r",
                "evidence": {"recovered_task_ids": [], "uncertain_recovery_task_ids": [], "preserved_task_ids": [],
                             "attributable_regression_task_ids": [], "unresolved_findings": []},
                "budget_disposition": {}}
    raise AssertionError("unknown role")


def accept_items() -> dict:
    """A-harnesslens on dev ids, phase 'accept' (not counted). At most 10 real episodes."""
    out: dict[str, Any] = {}
    dev = E.split_ids("dev")
    # (4) run_pair on 3 dev tasks + parent = v0 served from the cache
    ctx = _accept_ctx("real", train_ids=dev[:5])
    shutil.rmtree(ctx.run, ignore_errors=True)
    ctx.run.mkdir(parents=True)
    repo = Repo(ctx.run)
    repo.add("v0", P.SEED_CAP)
    p1 = run_version(ctx, repo, "v0", dev[:3], "pair-a")
    p2 = run_version(ctx, repo, "v0", dev[:3], "pair-b")
    m1, m2 = rj(p1)["metrics"], rj(p2)["metrics"]
    out["run_pair_v0_cache"] = {"records": m1["task_count"], "first_cache_hits": m1["cache_hits"],
                                "second_cache_hits": m2["cache_hits"], "pass": m2["cache_hits"] == 3}
    # (1) Experience + Analyzer calls through the gateway (dev stands in for TRAIN here). The probe set is the 3
    # tasks above plus one more dev task, so that it holds a failure (both Analyzer sides run); all are cache hits.
    probe = list(dev[:3]) + [dev[9]]
    ctx.train_ids = tuple(probe)
    base = run_version(ctx, repo, "v0", probe, "baseline")
    out["probe_cache_hits"] = rj(base)["metrics"]["cache_hits"]
    recs = {r["task_id"]: rj(Path(r["trajectory_paths"][0])) for r in rj(base)["records"]}
    run_discovery(ctx, recs)
    idx = baseline_source_index(ctx, base)
    exp = run_experience_baseline(ctx, idx)
    out["experience_call"] = {"reusable": len(exp["reusable"]), "needs_adjustment": len(exp["needs_adjustment"]),
                              "pass": True}
    try:
        run_analyzer_baseline(ctx, exp)
        r = rj(ctx.run / "analyzer" / "baseline_reusable.json")
        a = rj(ctx.run / "analyzer" / "baseline_adjustment.json")
        out["analyzer_call"] = {"reusable_candidates": len(r["candidates"]), "adjustment_candidates":
                                len(a["candidates"]), "pass": True}
    except Exception as e:  # noqa: BLE001
        out["analyzer_call"] = {"pass": False, "error": f"{type(e).__name__}: {e}"[:400]}
    # (2) one real Editor session in the sandbox; only allowed files; lint clean
    cand = None
    for side in ("adjustment", "reusable"):
        p = ctx.run / "analyzer" / f"baseline_{side}.json"
        if p.exists() and rj(p)["candidates"]:
            cand = rj(p)["candidates"][0]
            break
    if cand is None:
        cand = {"id": "accept-editor", "objective": "Add one concise tool note that tells the agent to read an API's "
                "documentation before its first call.", "channel_plan": [{"channel_id": "tool_description",
                "operation": "add", "experience_ids": [], "rationale": "tool-local"}],
                "validation": {"local_behavior_checks": ["the note appears in show_api_doc output"]}}
    ev_by = {str(x["id"]): x for x in [*exp["reusable"], *exp["needs_adjustment"]]}
    evidence = [ev_by[e] for p in cand.get("channel_plan") or [] for e in p.get("experience_ids") or [] if e in ev_by]
    if (P.AW_STATE / CAND / "accept" / "real" / "harness_editor" / "editor-accept-editor.json").exists() and \
            os.environ.get("HL_ACCEPT_KEEP_EDITOR") == "1":
        cand = None
    try:
        if cand is None:
            raise RuntimeError("editor item skipped (HL_ACCEPT_KEEP_EDITOR=1)")
        cdir, meta = materialize_selected(ctx, repo, parent="v0", label="accept-editor", candidate=cand,
                                          evidence=evidence)
        ws = SB.OPT_ROOT / CAND / "editor-accept-editor"
        extra = [str(p.relative_to(ws)) for p in ws.rglob("*") if p.is_file() and not (
            str(p.relative_to(ws)).startswith("candidate/") or str(p.relative_to(ws)).startswith("scratch/")
            or p.name == "CHANNELS.json")]
        out["editor_sandbox"] = {"changed": [d["path"] for d in meta["workspace_diff"]], "lint": E.lint(cdir),
                                 "files_outside_tree": extra, "pass": not E.lint(cdir) and not extra}
    except Exception as e:  # noqa: BLE001
        out["editor_sandbox"] = {"pass": False, "error": f"{type(e).__name__}: {e}"[:600]}
    # (3) preflight rejects a broken helper without a rollout
    before = len(P.read_jsonl(P.AW_STATE / CAND / "accept_rollouts.jsonl"))
    broken = E.materialize(CAND, {"tools/helpers.py": "import os\n\ndef f(apis):\n    return apis.spotify.login()\n"})
    v = preflight(broken)
    after = len(P.read_jsonl(P.AW_STATE / CAND / "accept_rollouts.jsonl"))
    out["preflight_rejects_broken_helper"] = {"violations": len(v), "rollouts_run": after - before,
                                              "pass": bool(v) and after == before}
    return out


USAGE_FILES = ("optimizer_usage.jsonl", "llm_calls.jsonl", "cache_hits.jsonl")


def _relocate_accept_usage() -> dict:
    """Acceptance is run before the search: move its optimizer usage out of AW_STATE/harnesslens/ so the search's
    10M-token cap and the reported search spend start at 0. Acceptance spend is kept in accept/usage/."""
    dst = STATE_DIR / "accept" / "usage"
    dst.mkdir(parents=True, exist_ok=True)
    moved = {}
    for name in USAGE_FILES:
        src = STATE_DIR / name
        if src.exists():
            with open(dst / name, "a") as f:
                f.write(src.read_text())
            moved[name] = len(src.read_text().splitlines())
            src.unlink()
    cc = STATE_DIR / "claude_calls"
    if cc.exists():
        (dst / "claude_calls").mkdir(exist_ok=True)
        for f in cc.iterdir():
            shutil.move(str(f), str(dst / "claude_calls" / f.name))
        cc.rmdir()
    return moved


def accept_dryrun() -> dict:
    """1-iteration dry run with a MOCK REWARD and the REAL roles (gateway + sandboxed Editor), so the vendored
    validators see real Sonnet outputs for Main / Comparison / Post-analyzers / Review. No episode runs: the mock
    evaluator serves the seed's cached dev records (gold-free, acceptance cache) and, for any other version, the same
    records with reward 1 and no failed requirements (a 'recovery' of the one failing task). Dev stands in for TRAIN."""
    dev = E.split_ids("dev")[:10]
    sh = E.seed_hash()[:16]
    cache = {t: json.loads((E.CACHE / "accept" / sh / f"{t}__s{P.SEARCH_SEED_BASE}.json").read_text()) for t in dev}

    mock_fail = set(dev[0::2])          # mock reward: the seed fails half the probe tasks (headroom to convert)

    def mock_eval(cand, cdir, task_ids, *, phase, tag):
        is_seed = E.tree_hash(cdir) == E.seed_hash()
        out = []
        for t in task_ids:
            r = dict(cache[t], cache_hit=True)
            if is_seed and t in mock_fail:
                r.update(reward=0.0, success=False, pass_count=0,
                         failed_requirements=["(mock) the task's requested end state was not reached"],
                         feedback="FAILED (mock reward)")
            if not is_seed:
                r.update(reward=1.0, success=True, failed_requirements=[], pass_count=r.get("num_tests") or 1,
                         feedback="PASSED (mock reward)")
            out.append(r)
        return out

    ctx = _accept_ctx("dryrun", train_ids=dev, evaluate=mock_eval)
    shutil.rmtree(ctx.run, ignore_errors=True)
    ctx.run.mkdir(parents=True)
    t0 = time.time()
    try:
        final = controller(ctx, budget=Budget(ctx, cap=900), max_iterations=1)
    except Exception as e:  # noqa: BLE001
        return {"pass": False, "error": f"{type(e).__name__}: {e}"[:800], "trace": traceback.format_exc()[-1500:]}
    hist = (rj(ctx.run / "loop_state.json", {}) or {}).get("history") or []
    h = hist[0] if hist else {}
    fallbacks = sorted(p.name for p in (ctx.run / "analyzer").glob("*_fallback.json")) + \
        sorted(p.name for p in (ctx.run / "intelligent_jobs").glob("*.failed.json"))
    invalid = len(list((ctx.run / "intelligent_jobs").glob("*.invalid.json")))
    return {"final": final["selected_version"], "evaluation_mode": h.get("evaluation_mode"),
            "screen_review": h.get("screen_review_decision"), "review": h.get("review_decision"),
            "confirmation_ran": h.get("confirmation_rollout_task_ids") is not None,
            "channels": [c["channel_id"] for c in h.get("channel_diffs") or []], "fallbacks": fallbacks,
            "invalid_attempts_retried": invalid, "minutes": round((time.time() - t0) / 60, 1),
            "stop_reason": final.get("stop_reason"),
            "pass": bool(hist) and h.get("review_decision") in {"accept_delta", "reject_delta", "revise_delta",
                                                                 "replan_problem", "materialization_failed",
                                                                 "channel_preflight_failed"}}


def cmd_accept(item: str | None) -> int:
    if (STATE_DIR / "rollouts.jsonl").exists() or (RUN / "loop_state.json").exists():
        raise SystemExit("the counted search has started; acceptance must not run now (its usage would mix in)")
    res: dict[str, Any] = {}
    if item in (None, "offline"):
        res["offline_dry_run"] = accept_offline()
    if item in (None, "real"):
        res.update(accept_items())
    if item in (None, "dryrun"):
        res["mock_reward_dry_run"] = accept_dryrun()
    res["acceptance_usage_relocated"] = _relocate_accept_usage()
    prev = rj(STATE_DIR / "accept_result.json", {}) or {}
    P.write_json(STATE_DIR / "accept_result.json", {**prev, **res})
    print(json.dumps(res, indent=1, default=str))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("accept")
    a.add_argument("--item", choices=["offline", "real", "dryrun"])
    sub.add_parser("search")
    sub.add_parser("freeze")
    args = ap.parse_args()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if args.cmd == "accept":
        return cmd_accept(args.item)
    if args.cmd == "search":
        return cmd_search()
    return cmd_freeze()


if __name__ == "__main__":
    raise SystemExit(main())
