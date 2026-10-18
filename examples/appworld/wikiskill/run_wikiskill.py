"""The `wikiskill` arm: WikiSkill (kenhuangus/wikiskill @ 0363334, a third-party reimplementation) — skills
co-evolved with an optimizer-side wiki, all active skills rendered into the M slot (§7.3).

  venv-aw/bin/python -I run_wikiskill.py search    # resumable per iteration (run_state + workspace + episode records)
  venv-aw/bin/python -I run_wikiskill.py accept    # A-wikiskill: 2 iterations on a few dev tasks, throwaway, not counted
  venv-aw/bin/python -I run_wikiskill.py freeze    # accepted skills -> memory/playbook.md, lint, artifact

The vendored loop (vendor/, unmodified) is driven as written — Algorithm 1: baseline val; per iteration
roll out ALL train tasks with the current skills; stratified sample (≤5 fail / ≤3 pass, 15k chars each);
one Wiki Maintainer call; a ReAct Skill Proposer (≤20 turns, read_file over the workspace only); apply;
re-run ALL val; accept iff strictly better, else roll back the skills (wiki kept); early stop at val 1.0.
What this driver adds (the plan's list, §7.3):
* the gateway LLM (shared shim; the vendored temperatures are dropped, G1; max_tokens 8,000);
* AppWorldInference.run(task) -> Trajectory: renders the active skills into memory/playbook.md and runs the
  shared harness; correct = AppWorld success; messages = the agent transcript + a final
  {"role":"user","content":"EVALUATION: <F1 failed checks>"}; prediction = that F1 string. Rollouts of a
  split run in parallel (AW_WORKERS) through one evaluator call;
* the outcome summary: PASS/FAIL + one-line failure reason + trace path (AppWorld has no `y`);
* the paper's Appendix E Maintainer and Proposer prompts (prompts/*.paper.txt) in place of the condensed
  ones, the paper's finish() format (name / skill_md / purpose_md; edits; no_action) mapped onto the
  vendored apply_proposal, `traces/<task_id>` resolved to the iteration's raw trace, and the full proposal
  text recorded in skill-impact.md (the paper: "includes full content of rejected proposals");
* the skills budget: the proposer is told the 30,000-char / M_cap budget for all skills together; an
  over-budget proposal is rejected before any rollout (recorded as invalid);
* K = 5 iterations instead of 8 so counted rollouts stay ≤ B = 900: 57 + 5·(90 + 57) = 792 (K = 6 would be
  939). An invalid / no_action proposal skips its val run (as the vendored loop does).
* never evaluate_test(). Resume: run_state per iteration (the vendored run() writes it only at the end).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE.parent / "common"))
sys.path.insert(0, str(HERE))
import aw5 as P  # noqa: E402

P.setup_env()
import evaluator as E  # noqa: E402
import opt_llm  # noqa: E402
from vendor import agents as VA  # noqa: E402
from vendor import orchestrator as VO  # noqa: E402
from vendor.datasets import Dataset, Task, Trajectory  # noqa: E402
from vendor.skills import SkillsLayer  # noqa: E402
from vendor.workspace import Workspace  # noqa: E402

CAND = os.environ.get("AW_CAND", "wikiskill")
STATE = P.AW_STATE / CAND
WS_ROOT = Path(os.environ.get("AW_WIKISKILL_WS", P.AW_STATE / CAND / "workspace"))
K = int(os.environ.get("AW_WIKISKILL_K", 5))
STEP_OUT = 2000
TASK_DESC = ("multi-step day-to-day tasks for a supervisor by writing Python code in a REPL that calls the APIs "
             "of simulated apps (e-mail, messaging, music, notes, payments, shopping, file system, and more), "
             "ending each task with apis.supervisor.complete_task(...)")
WM_SYSTEM = (HERE / "prompts" / "wiki_maintainer.paper.txt").read_text()
SP_SYSTEM = (HERE / "prompts" / "skill_proposer.paper.txt").read_text().replace("{task_desc}", TASK_DESC)


TOOL_FORMAT = """
## How to call the tools

Reply with exactly ONE tool call per message, as a single JSON object and nothing else:
- read a file: {"tool": "read_file", "path": "<relative path>"}
- finish: {"tool": "finish", "action": "create", "name": "...", "skill_md": "...", "purpose_md": "..."}
  (or "action": "patch" with "name" and "edits", or "action": "no_action").
The file content comes back in the next message.
"""


def budget_text() -> str:
    cap = E.m_cap_tokens()
    return (TOOL_FORMAT + f"\n## Budget and AppWorld rules\n\n- All active skills together are injected verbatim into the agent's "
            f"prompt and must fit in 30,000 characters"
            + (f" and {cap:,} tokens" if cap else "") + "; a proposal that would exceed it is rejected without "
            "being evaluated. Current total: {used} characters.\n- Skills are general guidance for AppWorld tasks: "
            "no task instruction text, person names, emails, phone numbers or other specific values from the "
            "traces.\n")


class GatewayLLM:
    """The vendored LLM protocol over the shared gateway shim; `temperature` is dropped (G1)."""

    def __init__(self, cand: str):
        self.cand = cand
        self.role = "llm"

    def chat(self, messages, temperature=None, max_tokens=8000, **kw):
        sysmsg = messages[0]["content"] if messages and messages[0]["role"] == "system" else ""
        role = ("maintainer" if "Wiki Maintainer" in sysmsg else "proposer" if "Skill Proposer" in sysmsg
                else self.role)
        try:
            return opt_llm.chat(messages, cand=self.cand, role=role, max_tokens=max_tokens)
        except opt_llm.Refusal:
            P.progress_log(self.cand, "P3", f"refusal in {role} (G2)")
            return ""


def _transcript(rec: dict) -> list[dict]:
    msgs = [{"role": "user", "content": f"Task: {rec['instruction']}"}]
    for s in rec.get("steps") or []:
        o = (s.get("output") or "")[:STEP_OUT]
        th = (s.get("thought") or "").strip()
        msgs.append({"role": "assistant", "content": (th + "\n" if th else "") + f"```python\n{(s.get('code') or '').strip()}\n```"})
        msgs.append({"role": "user", "content": f"Output:\n{o}"})
    msgs.append({"role": "user", "content": "EVALUATION: " + rec["feedback"]})
    return msgs


def _reason(rec: dict) -> str:
    if rec["reward"] >= 1.0:
        return "all requirement checks passed"
    if rec.get("lint_reject"):
        return "skills rejected by the length lint (not run)"
    n, p = int(rec.get("num_tests") or 0), int(rec.get("pass_count") or 0)
    reqs = rec.get("failed_requirements") or []
    first = (reqs[0].strip().splitlines() or [""])[0][:160] if reqs else ""
    return f"{n - p}/{n} requirement checks failed" + (f"; first: {first}" if first else "") + \
        f"; termination {rec.get('termination')}"


class AppWorldOrchestrator(VO.EvolutionOrchestrator):
    """The vendored Algorithm 1 with the AppWorld inference, outcome summary, parallel rollouts and resume."""

    def __init__(self, *a, cand: str, hard_cap: int, **kw):
        super().__init__(*a, **kw)
        self.cand, self.hard_cap = cand, hard_cap
        self.reasons: dict[str, str] = {}
        self.proposer = PaperProposer(self.llm, self.ws, self.skills, max_turns=kw.get("max_react_turns", 20))
        self.maintainer = PaperMaintainer(self.llm, self.ws)
        self.start_k = 1

    def _rollout(self, tasks, iteration, split):
        playbook = playbook_text(self.skills)
        cdir = E.materialize(self.cand, {"memory/playbook.md": playbook})
        recs = E.evaluate(self.cand, cdir, [t.id for t in tasks], phase="P3", split=split, reuse=True,
                          hard_cap=self.hard_cap, tag=f"iter{iteration}_{split}")
        trajs = []
        for t, r in zip(tasks, recs):
            tr = Trajectory(task_id=t.id, messages=_transcript(r), tool_calls=[], final_answer=None,
                            correct=r["reward"] >= 1.0, prediction=r["feedback"])
            self.reasons[t.id] = _reason(r)
            rel = os.path.join("raw", f"iter_{iteration:03d}", f"{t.id}.json")
            if not os.path.exists(os.path.join(self.ws.root, rel)):  # a resumed iteration re-adopts its traces
                self.ws.add_raw_trace(iteration, t.id, {**tr.to_dict(), "split": split, "iteration": str(iteration)})
            trajs.append(tr)
        P.progress_log(self.cand, "P3", f"iter {iteration} {split}: {sum(t.correct for t in trajs)}/{len(trajs)} passed")
        return trajs

    def _outcome_summary(self, trajs, tasks, iteration):
        return "\n".join(f"{tr.task_id}: {'PASS' if tr.correct else 'FAIL'} | {self.reasons.get(tr.task_id, '')} "
                         f"| trace: traces/{tr.task_id}" for tr in trajs)

    def _baseline_validation(self):
        st = P.read_json(STATE / "run_state.json")
        if st:  # resume: the baseline and every finished iteration are on record
            self.r_best, self.history, self.start_k = st["r_best"], st["history"], st["next_k"]
            self.log(f"resume at iteration {self.start_k}, R_best={self.r_best:.4f}")
            return
        super()._baseline_validation()
        self._save(1)

    def _save(self, next_k: int):
        P.write_json(STATE / "run_state.json", {"r_best": self.r_best, "history": self.history, "next_k": next_k,
                                                "skills": self.skills.list_skills(), "utc": P.utcnow()})

    def run(self):
        """The vendored run() (orchestrator.py:81-159), iteration body unchanged, resumable per iteration."""
        self._baseline_validation()
        for k in range(self.start_k, self.K + 1):
            if self.r_best >= 1.0:
                self.log("R_best reached 1.0; early stop.")
                break
            self.log(f"\n=== Iteration {k}/{self.K} ===")
            train_trajs = self._rollout(self.dataset.train, k, "train")
            sampled = VA.stratified_sample(train_trajs)
            update = self.maintainer.consolidate(sampled, k)
            report = self.ws.apply_maintainer_update(update) if update else {}
            self.log(f"Wiki: created={report.get('created')} updated={report.get('updated')} "
                     f"errors={report.get('errors')}")
            proposal = self.proposer.propose(self._outcome_summary(train_trajs, self.dataset.train, k), k)
            entry = {"iteration": k, "proposal": None, "val_score": None, "accepted": False}
            if proposal:
                snap = self.skills.snapshot()
                try:
                    applied = self.skills.apply_proposal(proposal)
                except Exception as e:  # invalid proposal → skip iteration gracefully
                    self.log(f"Proposal invalid, skipped: {e}")
                    applied = None
                if applied is not None:
                    val_trajs = self._rollout(self.dataset.val, k, "val")
                    score = self._score(val_trajs)
                    accepted = score > self.r_best
                    if accepted:
                        self.r_best = score
                    else:
                        self.skills.restore(snap)
                    self.log(f"Proposal {applied['action']} '{applied['skill']}' -> "
                             f"val={score:.4f} ({'ACCEPTED' if accepted else 'REJECTED'})")
                    entry.update({"proposal": applied.get("skill"), "action": applied["action"],
                                  "val_score": score, "accepted": accepted})
                    diff = applied.get("diff", "(new skill)")
                    self.ws.record_skill_impact(
                        f"\n## Iteration {k} — {applied['action']} '{applied['skill']}'\n"
                        f"- validation score: {score:.4f}\n- outcome: {'Accepted' if accepted else 'Rejected'}\n"
                        f"- purpose: {proposal.get('purpose', '')}\n- diff:\n```diff\n{diff}\n```\n")
                else:
                    self.skills.restore(snap)
                    entry["action"] = "invalid"
                    self.ws.record_skill_impact(
                        f"\n## Iteration {k} — invalid proposal (discarded)\n- outcome: Rejected\n"
                        f"- reason: proposal could not be applied\n- purpose: {proposal.get('purpose', '')}\n")
            else:
                self.log("No proposal produced this iteration.")
                entry["action"] = "none"
                self.ws.apply_maintainer_update({
                    "append_log": f"Iteration {k}: proposer emitted no valid proposal; "
                                  f"no skill change was evaluated."})
            self.history.append(entry)
            self._save(k + 1)
            checkpoint(self, k)
        res = {"r_best": self.r_best, "history": self.history, "final_skills": self.skills.list_skills()}
        P.write_json(Path(self.ws.root) / "run_state.json", res)
        self.log(f"Evolution complete. R_best={self.r_best:.4f}, skills={res['final_skills']}")
        return res


class PaperMaintainer(VA.WikiMaintainer):
    """The vendored consolidate() with the paper's Appendix E.2 system prompt."""

    def consolidate(self, sampled_traces, iteration):
        old = VA.WIKI_MAINTAINER_SYSTEM
        VA.WIKI_MAINTAINER_SYSTEM = WM_SYSTEM
        try:
            return super().consolidate(sampled_traces, iteration)
        finally:
            VA.WIKI_MAINTAINER_SYSTEM = old


class PaperProposer(VA.SkillProposer):
    """The vendored ReAct propose() with the paper's Appendix E.3 prompt and finish() format."""

    def propose(self, outcome_summary, iteration):
        used = len(playbook_text(self.skills))
        old = VA.SKILL_PROPOSER_SYSTEM
        VA.SKILL_PROPOSER_SYSTEM = SP_SYSTEM + budget_text().replace("{used}", f"{used:,}")
        ws = self.ws
        orig_read = ws.read_file

        def read_file(rel):  # paper: traces/<task_id> resolves to the iteration's raw trace; never raise
            rel = rel.strip().lstrip("/")
            m = re.match(r"^traces/([^/]+?)(?:\.json)?$", rel)
            if m:
                rel = os.path.join("raw", f"iter_{iteration:03d}", f"{m.group(1)}.json")
            try:
                return orig_read(rel)
            except ValueError:
                return f"ERROR: path is outside the workspace: {rel}"
        ws.read_file = read_file
        orig_chat = self.llm.chat
        last = {"raw": None}

        def chat(messages, **kw):
            text = orig_chat(messages, **kw)
            # an XML-style call (<invoke name="read_file"><parameter name="path">…) is read like the JSON form
            m = re.search(r'<parameter name="path">\s*([^<\s]+)\s*</parameter>', text)
            if m and not re.search(r'"path"\s*:\s*"', text):
                text = json.dumps({"tool": "read_file", "path": m.group(1)})
            p = VA.extract_json(text)
            if isinstance(p, dict) and isinstance(p.get("proposal"), dict):  # finish({"proposal": {...}})
                p = p["proposal"]
            if isinstance(p, dict) and p.get("action") in ("create", "patch", "no_action"):
                last["raw"] = p
                if p["action"] == "no_action":
                    return '{"action": "no_action_sentinel"}'
                q = dict(p)
                q["skill"] = q.get("skill") or q.get("name")
                if q["action"] == "create":
                    q["content"] = q.get("content") or q.get("skill_md") or ""
                q["purpose"] = q.get("purpose") or q.get("purpose_md") or ""
                return json.dumps(q)
            return text
        self.llm.chat = chat
        try:
            prop = super().propose(outcome_summary, iteration)
        finally:
            VA.SKILL_PROPOSER_SYSTEM = old
            ws.read_file = orig_read
            self.llm.chat = orig_chat
        raw = last["raw"]
        if prop is None:
            ws.record_skill_impact(f"\n## Iteration {iteration} — "
                                   f"{'no_action' if raw and raw.get('action') == 'no_action' else 'no proposal'}\n")
            return None
        # budget: reject an over-budget proposal before any rollout (raises -> invalid proposal path)
        snap = self.skills.snapshot()
        try:
            self.skills.apply_proposal(prop)
            pb = playbook_text(self.skills)
            v = E.lint(E.materialize(CAND + "_lintprobe", {"memory/playbook.md": pb}))
        except Exception as e:  # noqa: BLE001 — the vendored loop records an invalid proposal
            v = [f"invalid: {e}"]
        finally:
            self.skills.restore(snap)
        ws.record_skill_impact(f"\n## Iteration {iteration} — proposal (full text)\n```json\n"
                               f"{json.dumps(raw or prop, ensure_ascii=False, indent=1)[:20000]}\n```\n")
        if v:
            P.progress_log(CAND, "P3", f"iter {iteration} proposal rejected before evaluation: {v[0][:200]}")
            return {"action": "create", "skill": "__invalid__", "content": "", "purpose": "; ".join(v)[:500],
                    "_invalid": True}
        return prop


_orig_apply = SkillsLayer.apply_proposal


def _apply(self, proposal):
    if proposal.get("_invalid"):
        raise ValueError(proposal.get("purpose") or "proposal rejected by the budget / lint")
    return _orig_apply(self, proposal)


SkillsLayer.apply_proposal = _apply


def playbook_text(skills: SkillsLayer) -> str:
    """active_skills_context() of the accepted skill set (the M-slot text); empty when no skill exists."""
    return "" if not skills.list_skills() else skills.active_skills_context()


def _tasks(split: str, ids: list[str]) -> list[Task]:
    root = P.ROOT_OPT / "data" / "tasks"
    return [Task(id=t, x=json.loads((root / t / "specs.json").read_text())["instruction"], y="") for t in ids]


def checkpoint(orch, k: int) -> None:
    import status_doc
    rows = [{k2: h.get(k2) for k2 in ("iteration", "action", "val_score", "accepted")} for h in orch.history]
    t = opt_llm.totals(orch.cand)
    prog = {"candidate": orch.cand, "K": K, "rows": rows, "r_best": orch.r_best, "skills": len(orch.skills.list_skills()),
            "playbook_chars": len(playbook_text(orch.skills)), "counted_rollouts": E.counted(orch.cand),
            "cap": P.BUDGET_ROLLOUTS, "optimizer": {**t, "proxy_usd": opt_llm.proxy_usd(t)}}
    P.write_json(P.PUSHED / orch.cand / "progress.json", prog)
    last = rows[-1] if rows else {}
    status_doc.append("result", "P3", f"{orch.cand} search",
                      f"WikiSkill iteration {k}/{K}: proposal {last.get('action')} → val {last.get('val_score')} "
                      f"({'accepted' if last.get('accepted') else 'not accepted'}); R_best {orch.r_best:.3f}; "
                      f"{prog['skills']} active skill(s), {prog['playbook_chars']:,} chars.\n"
                      f"Counted rollouts {prog['counted_rollouts']}/{P.BUDGET_ROLLOUTS}; optimizer {t['calls']} calls, "
                      f"{t['prompt_tokens'] / 1e6:.2f}M in / {t['completion_tokens'] / 1e6:.2f}M out tok, "
                      f"${opt_llm.proxy_usd(t)} proxy.",
                      done_through=f"{orch.cand}/search/iter{k}", next_unit=f"{orch.cand}/search",
                      extra={"candidate": orch.cand, "counts": {orch.cand: {"counted_rollouts": prog["counted_rollouts"]}},
                             "spend": {orch.cand: {"in": t["prompt_tokens"], "out": t["completion_tokens"],
                                                   "proxy_usd": opt_llm.proxy_usd(t)}}},
                      artifacts=[f"STATE/{orch.cand}/progress.json"], subject=f"{orch.cand} iter {k}")


def build(train_ids, val_ids, ws_root: Path, k: int, hard_cap: int, ledger: bool):
    ws = Workspace(str(ws_root))
    ds = Dataset(train=_tasks("train", train_ids), val=_tasks("dev", val_ids), test=[], name="appworld")
    orch = AppWorldOrchestrator(GatewayLLM(CAND), ds, ws, tools=[], K=k, max_react_turns=20,
                                log=lambda s: P.progress_log(CAND, "P3", s.strip()[:300]) if s.strip() else None,
                                cand=CAND, hard_cap=hard_cap)
    if not ledger:
        globals()["checkpoint"] = lambda *a, **kw: None
    return orch


def search() -> int:
    pidf = P.AW_STATE / "RUNNING.pid"
    pidf.write_text(f"{os.getpid()} {CAND} search\n")
    try:
        orch = build(E.split_ids("train"), E.split_ids("dev"), WS_ROOT, K, P.BUDGET_ROLLOUTS, True)
        res = orch.run()
        P.write_json(STATE / "result.json", res)
        import status_doc
        status_doc.append("phase_done", "P3", f"{CAND} search", f"WikiSkill search finished: R_best "
                          f"{res['r_best']:.3f}, {len(res['final_skills'])} accepted skill(s). Next: freeze.",
                          done_through=f"{CAND}/search", next_unit=f"{CAND}/freeze", extra={"candidate": CAND},
                          subject=f"{CAND} search done")
        return 0
    finally:
        pidf.unlink(missing_ok=True)


def accept() -> int:
    """A-wikiskill: 2 iterations, 3 dev tasks as train and 2 as val, throwaway workspace (AW_CAND=acc_wikiskill)."""
    dev = E.split_ids("dev")
    ws_root = STATE / "accept_ws"
    shutil.rmtree(ws_root, ignore_errors=True)
    (STATE / "run_state.json").unlink(missing_ok=True)
    orch = build(dev[:3], dev[3:5], ws_root, 2, 100, False)
    res = orch.run()
    calls = P.read_jsonl(opt_llm.usage_path(CAND))
    roles = sorted({c["role"] for c in calls})
    imp = (ws_root / "wiki" / "skill-impact.md").read_text() if (ws_root / "wiki" / "skill-impact.md").exists() else ""
    raw = list((ws_root / "raw").rglob("*.json"))
    last_msg = json.loads(raw[0].read_text())["messages"][-1]["content"] if raw else ""
    pb = playbook_text(orch.skills)
    out = {"iterations": len(res["history"]), "roles": roles, "calls": len(calls),
           "errors": sum(1 for c in calls if c.get("error")), "wiki_pages": len(list((ws_root / "wiki" / "patterns").glob("*.md"))),
           "skills": res["final_skills"], "proposals_recorded": imp.count("proposal (full text)"),
           "evaluation_message": last_msg.startswith("EVALUATION:"), "playbook_chars": len(pb),
           "playbook_lints": not E.lint(E.materialize(CAND, {"memory/playbook.md": pb}))}
    out["ok"] = ("maintainer" in roles and "proposer" in roles and out["errors"] == 0 and out["wiki_pages"] >= 1
                 and out["evaluation_message"] and out["playbook_lints"] and out["proposals_recorded"] >= 1)
    P.write_json(P.AW_STATE / "acceptance" / "a_wikiskill.json", out)
    print(json.dumps(out))
    return 0 if out["ok"] else 1


def freeze() -> int:
    ws = Workspace(str(WS_ROOT))
    skills = SkillsLayer(ws)
    st = P.read_json(STATE / "run_state.json", {}) or {}
    pb = playbook_text(skills)
    inert = not pb.strip()
    cdir = E.materialize(CAND, {"memory/playbook.md": pb})
    v = E.lint(cdir)
    if v:
        raise SystemExit(f"playbook fails the lint: {v}")
    art = P.PUSHED / CAND / "artifact"
    shutil.rmtree(art, ignore_errors=True)
    for rel, t in E.read_surfaces(cdir).items():
        (art / rel).parent.mkdir(parents=True, exist_ok=True)
        (art / rel).write_text(t)
    (art / "memory").mkdir(exist_ok=True)
    P.write_json(art / "FREEZE.json", {"candidate": CAND, "label": "inert" if inert else "", "r_best": st.get("r_best"),
                                       "skills": skills.list_skills(), "memory_chars": len(pb),
                                       "memory_tokens": E.memory_tokens(pb), "iterations": len(st.get("history", [])),
                                       "tree_sha256": P.sha256_tree(cdir)})
    print(json.dumps(P.read_json(art / "FREEZE.json")))
    return 0


if __name__ == "__main__":
    raise SystemExit({"search": search, "accept": accept, "freeze": freeze}[sys.argv[1]]())
