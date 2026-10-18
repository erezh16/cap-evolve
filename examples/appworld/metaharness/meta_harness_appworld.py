"""The `metaharness` arm: Meta-Harness (stanford-iris-lab/meta-harness @ 8123cca) on AppWorld (§7.5).

  venv-aw/bin/python -I meta_harness_appworld.py search      # Phase 0 + N counted iterations (resumable per iteration)
  venv-aw/bin/python -I meta_harness_appworld.py debug [n]   # n debugging iterations to tune SKILL.md (not counted, paper App. D)
  venv-aw/bin/python -I meta_harness_appworld.py accept      # A-metaharness (b)+(c) and a 1-iteration proposer smoke
  venv-aw/bin/python -I meta_harness_appworld.py freeze      # frontier _best -> artifact

The TB2 outer loop ported to AppWorld (reference_examples/terminal_bench_2/meta_harness.py):
Phase 0 scores the seed; then per iteration the proposer (the vendored claude_wrapper running `claude -p`,
one hypothesis / candidate per iteration, driven by skill/SKILL.md) writes logs/pending_eval.json →
validate (outside the proposer) → smoke (1 task) → evaluate (train ∪ dev, 147 tasks, 1 trial) → update
logs/frontier_val.json (per-task best + `_best`, strict >, token tie-break) and logs/evolution_summary.jsonl.

Proposer call (the method's defining component, kept): claude_wrapper.run(prompt, model=aws/claude-sonnet-5-5,
allowed_tools=[Read, Glob, Grep, Agent, Write, Edit, Bash], skills=[skill/SKILL.md], cwd=workspace,
log_dir=logs/claude_sessions) — with three changes, all for the gateway or isolation (§7.5, §8):
* the model id is the eval's optimizer (D1); ANTHROPIC_DEFAULT_*_MODEL and CLAUDE_CODE_SUBAGENT_MODEL are the
  same id; the wrapper's ANTHROPIC_API_KEY pop is not needed (the gateway authenticates with
  ANTHROPIC_AUTH_TOKEN, which is kept); `--effort` is dropped (not accepted for this id here);
* the wrapper's `--dangerously-skip-permissions` is replaced by `--permission-mode acceptEdits` plus
  `--settings <sandbox>` (common/sandbox5.py): Claude Code's sandbox with denyRead on every gold / test /
  AppWorld / evaluator / secrets / transcript path and the network restricted to the gateway. This is the
  configuration A9 checked; no permission bypass is used;
* the proposer's workspace (/tmp/aw5_opt/metaharness/ws) holds only candidates/, the gold-free per-task
  trajectories and scores of evaluated candidates (runs/), logs/, the public API reference and the lint
  with its cached data (tools/). AppWorld is not in view (F19/F20): the validator imports happen outside.
Budget: B = 900 counted rollouts and 10M optimizer tokens; each counted iteration = 1 smoke + 147 = 148,
Phase 0 = 147, so at most 5 counted iterations (147 + 5·148 = 887). Proposer tokens are taken from the
wrapper's session logs (input + cache creation + output; cache reads reported separately).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE.parent / "common"))
sys.path.insert(0, str(HERE / "vendor"))
import aw5 as P  # noqa: E402
import sandbox5 as SB  # noqa: E402

P.setup_env()
import evaluator as E  # noqa: E402

CAND = os.environ.get("AW_CAND", "metaharness")
STATE = P.AW_STATE / CAND
WS = Path(os.environ.get("AW_MH_WS", SB.OPT_ROOT / CAND / "ws"))
LOGS = WS / "logs"
MAX_ITERS = int(os.environ.get("AW_MH_ITERS", 5))
PROPOSE_TIMEOUT = 2400
TOOLS = ["Read", "Glob", "Grep", "Agent", "Write", "Edit", "Bash"]
SURFACES = E.SURFACES
SMOKE_TASKS = 1
TRAJ_OUT = 3000


# ------------------------------------------------------------------ workspace

def setup_workspace(fresh: bool) -> None:
    if fresh:
        shutil.rmtree(WS, ignore_errors=True)
    for d in ("candidates", "runs", "logs", "reference", "tools"):
        (WS / d).mkdir(parents=True, exist_ok=True)
    if not (WS / "candidates" / "seed").exists():  # the four harness files only
        for rel in SURFACES:
            if (P.SEED_CAP / rel).is_file():
                (WS / "candidates" / "seed" / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(P.SEED_CAP / rel, WS / "candidates" / "seed" / rel)
    for f in ("api_index.md", "react_agent_notes.md"):
        shutil.copy2(P.REFERENCE / f, WS / "reference" / f)
    shutil.copy2(HERE.parent / "adapters" / "lints.py", WS / "tools" / "lints.py")
    shutil.copy2(P.LINT_CACHE, WS / "tools" / "lint_cache.json")
    # the lint inside the workspace reads its own copy of the lint data (instruction 8-grams, contacts, names)
    (WS / "tools" / "README.md").write_text("Run the lint with: AW_LINT_CACHE=tools/lint_cache.json python3 -I "
                                            "tools/lints.py candidates/<name>\n")


def task_label(i: int) -> str:
    return f"t{i:03d}"


def search_ids() -> list[str]:
    return E.split_ids("train") + E.split_ids("dev")


# ------------------------------------------------------------------ validator (outside the proposer)

def forbidden_strings() -> list[str]:
    c = json.loads(P.PUBLISH_CACHE.read_text())
    return list(c["task_ids"]) + ["test_normal", "test_challenge", "ground_truth", "answer.json", "root_full",
                                  "root_opt", "compiled_solution", "/data/tasks"]


def validate(name: str) -> list[str]:
    """The TB2 validator's role (import/interface check) + controller.validate_source's forbidden-string scan,
    then the shared lint. Returns reasons (empty = valid)."""
    d = WS / "candidates" / name
    out = []
    if not re.fullmatch(r"[a-z0-9_]{1,64}", name) or not d.is_dir():
        return [f"candidate dir candidates/{name} missing or not snake_case"]
    extra = [str(p.relative_to(d)) for p in d.rglob("*") if p.is_file() and str(p.relative_to(d)) not in SURFACES
             and p.name != ".gitkeep"]
    if extra:
        out.append(f"files outside the four harness files: {sorted(extra)[:5]}")
    if not (d / "policy" / "instructions.txt").is_file():
        out.append("policy/instructions.txt missing")
    bad = forbidden_strings()
    for rel in SURFACES:
        p = d / rel
        if p.is_file():
            low = p.read_text(encoding="utf-8", errors="replace").lower()
            hits = [s for s in bad if s.lower() in low]
            if hits:
                out.append(f"{rel}: forbidden reference ({len(hits)} hit(s))")
    if (d / "tools" / "api_notes.json").is_file():
        try:
            json.loads((d / "tools" / "api_notes.json").read_text() or "{}")
        except json.JSONDecodeError as e:
            out.append(f"tools/api_notes.json does not parse: {e}")
    if (d / "tools" / "helpers.py").is_file():
        import subprocess
        r = subprocess.run([sys.executable, "-I", "-c", "import ast,sys; ast.parse(open(sys.argv[1]).read())",
                            str(d / "tools" / "helpers.py")], capture_output=True, text=True)
        if r.returncode:
            out.append("tools/helpers.py does not parse")
    if (d / "policy" / "instructions.txt").is_file():
        try:
            from jinja2 import Template
            Template((d / "policy" / "instructions.txt").read_text()).render(
                instruction="x", main_user={"first_name": "a", "last_name": "b", "email": "c", "phone_number": "d"},
                app_descriptions="[]")
        except Exception as e:  # noqa: BLE001
            out.append(f"policy/instructions.txt does not render: {e}")
    if not out:
        out += E.lint(materialize(name))
    return out


def materialize(name: str) -> Path:
    d = WS / "candidates" / name
    return E.materialize(CAND, {rel: (d / rel).read_text(encoding="utf-8") for rel in SURFACES if (d / rel).is_file()},
                         base=P.SEED_CAP / "_none_")


# ------------------------------------------------------------------ evaluator (gold-free per-task dirs)

def write_runs(name: str, ids: list[str], recs: list[dict]) -> dict:
    root = WS / "runs" / name
    shutil.rmtree(root, ignore_errors=True)
    per = {}
    for i, (tid, r) in enumerate(zip(ids, recs)):
        lab = task_label(i)
        d = root / lab
        d.mkdir(parents=True, exist_ok=True)
        lines = [f"# Task\n\n{r.get('instruction', '')}\n"]
        for s in r.get("steps") or []:
            o = (s.get("output") or "")[:TRAJ_OUT]
            lines.append(f"## Step {s.get('step')}\n\n{(s.get('thought') or '').strip()}\n\n```python\n"
                         f"{(s.get('code') or '').strip()}\n```\n\nOutput:\n```\n{o}\n```\n")
        (d / "trajectory.md").write_text("\n".join(lines))
        ev = {"reward": r["reward"], "feedback": r["feedback"], "steps": r.get("n_steps"),
              "prompt_tokens": r.get("prompt_tokens"), "completion_tokens": r.get("completion_tokens"),
              "termination": r.get("termination"), "lint_reject": r.get("lint_reject", False),
              "split": "train" if i < 90 else "dev"}
        (d / "eval.json").write_text(json.dumps(ev, indent=1))
        per[lab] = r["reward"]
    n = len(recs)
    summ = {"candidate": name, "tasks": n, "tgc": sum(per.values()) / max(1, n),
            "tgc_train": sum(per[task_label(i)] for i in range(min(90, n))) / max(1, min(90, n)),
            "tgc_dev": (sum(per[task_label(i)] for i in range(90, n)) / max(1, n - 90)) if n > 90 else None,
            "sgc": _sgc(ids, recs),
            "avg_prompt_tokens": sum(int(r.get("prompt_tokens") or 0) for r in recs) / max(1, n),
            "avg_completion_tokens": sum(int(r.get("completion_tokens") or 0) for r in recs) / max(1, n),
            "avg_steps": sum(int(r.get("n_steps") or 0) for r in recs) / max(1, n)}
    (root / "summary.json").write_text(json.dumps(summ, indent=1))
    return {"per_task": per, **summ}


def _sgc(ids, recs) -> float:
    sc: dict[str, list[float]] = {}
    for t, r in zip(ids, recs):
        sc.setdefault(t.split("_")[0], []).append(r["reward"])
    return sum(1.0 for v in sc.values() if all(x == 1.0 for x in v)) / max(1, len(sc))


def evaluate(name: str, ids: list[str], tag: str, hard_cap: int, lint_reasons: list[str] | None = None) -> dict:
    cdir = materialize(name)
    recs = E.evaluate(CAND, cdir, ids, phase="P3", split="train+dev", reuse=True, hard_cap=hard_cap, tag=tag)
    return write_runs(name, ids, recs)


# ------------------------------------------------------------------ frontier + summary (TB2 semantics)

def update_frontier(name: str, res: dict) -> None:
    fp = LOGS / "frontier_val.json"
    fr = P.read_json(fp, {}) or {}
    for lab, v in res["per_task"].items():
        if lab not in fr or v > fr[lab]["pass_rate"]:
            fr[lab] = {"best_agent": name, "pass_rate": v}
    b = fr.get("_best")
    tok = res["avg_prompt_tokens"] + res["avg_completion_tokens"]
    if b is None or res["tgc"] > b["avg_pass_rate"] or (res["tgc"] == b["avg_pass_rate"] and tok < b.get("avg_tokens", 1e18)):
        fr["_best"] = {"agent": name, "avg_pass_rate": res["tgc"], "avg_tokens": tok}
    P.write_json(fp, fr)


def append_summary(it: int, cand: dict, res: dict | None, outcome: str, timing: dict | None) -> None:
    fr = P.read_json(LOGS / "frontier_val.json", {}) or {}
    best = (fr.get("_best") or {}).get("avg_pass_rate", 0.0)
    row = {"iteration": it, "agent": cand.get("name"), "path": cand.get("path"), "parent": cand.get("parent"),
           "avg_pass_rate": res["tgc"] if res else None, "hypothesis": cand.get("hypothesis"),
           "changes": cand.get("changes"), "delta": (res["tgc"] - best) if res else None, "outcome": outcome}
    if res:
        row["rollout_metrics"] = {k: res[k] for k in ("tgc_train", "tgc_dev", "sgc", "avg_prompt_tokens",
                                                      "avg_completion_tokens", "avg_steps")}
    if timing:
        row["timing_s"] = timing
    P.append_jsonl(LOGS / "evolution_summary.jsonl", row)


# ------------------------------------------------------------------ proposer

def render_task_prompt(it: int) -> str:
    fr = P.read_json(LOGS / "frontier_val.json", {}) or {}
    parent = (fr.get("_best") or {}).get("agent", "seed")
    return f"""Run iteration {it} of the harness evolution loop. Target model: gpt-oss-120b (AppWorld ReAct code agent). Start from candidates/{parent} as the parent (the current best).

## Search set: AppWorld train + dev, 147 tasks x 1 trial

Each task is labelled t000..t146 (t000-t089 train, t090-t146 dev). Focus on harness changes that help the agent solve many unfamiliar multi-app tasks.

## Run directories
All logs and results for this run are under `logs/` and `runs/` in this workspace.
- `logs/evolution_summary.jsonl` — past results
- `logs/frontier_val.json` — frontier
- `runs/<candidate>/<task>/{{trajectory.md,eval.json}}` and `runs/<candidate>/summary.json` — per-task trajectories and scores
- Write pending_eval.json to: `logs/pending_eval.json`"""


def proposer_tokens(meta: dict) -> tuple[int, int, int]:
    u = meta.get("token_usage") or {}
    return (int(u.get("input_tokens") or 0) + int(u.get("cache_creation_input_tokens") or 0),
            int(u.get("output_tokens") or 0), int(u.get("cache_read_input_tokens") or 0))


def propose(it: int, name: str) -> tuple[int, Path | None, dict]:
    import claude_wrapper as CW
    import subprocess
    (LOGS / "pending_eval.json").unlink(missing_ok=True)
    sf = SB.settings_file(CAND, WS)
    orig_build = CW.build_command

    def build_command(*a, **kw):  # the wrapper's command, with the sandbox in place of the permission bypass
        cmd = orig_build(*a, **kw)
        cmd = [c for c in cmd if c != "--dangerously-skip-permissions"]
        return cmd[:1] + ["--permission-mode", "acceptEdits", "--settings", str(sf)] + cmd[1:]
    CW.build_command = build_command
    old_env, new_env = dict(os.environ), SB.claude_env()
    os.environ.clear()
    os.environ.update(new_env)
    try:
        t0 = time.time()
        res = CW.run(render_task_prompt(it), model=P.OPT_MODEL, allowed_tools=TOOLS, cwd=str(WS),
                     log_dir=str(LOGS / "claude_sessions"), name=name, skills=[str(HERE / "skill" / "SKILL.md")],
                     timeout_seconds=PROPOSE_TIMEOUT, progress=False)
        session_dir = Path(res.log_dir)
    finally:
        os.environ.clear()
        os.environ.update(old_env)
        CW.build_command = orig_build
    meta = json.loads((session_dir / "meta.json").read_text())
    pin, pout, pcache = proposer_tokens(meta)
    P.append_jsonl(STATE / "optimizer_usage.jsonl", {
        "t": P.utcnow(), "seconds": round(time.time() - t0, 1), "model": P.OPT_MODEL, "role": f"proposer:{name}",
        "prompt_tokens": pin, "completion_tokens": pout, "cache_read": pcache, "cost_usd": meta.get("cost_usd"),
        "error": None if meta.get("exit_code") == 0 else f"exit {meta.get('exit_code')}", "finish_reason": None,
        "tool_calls": len(meta.get("tool_summary") or [])})
    # keep a local copy of the session log outside the proposer's workspace (scan + audit)
    shutil.copytree(session_dir, STATE / "claude_sessions" / session_dir.name, dirs_exist_ok=True)
    return int(meta.get("exit_code") or 0), (LOGS / "pending_eval.json") if (LOGS / "pending_eval.json").exists() else None, meta


# ------------------------------------------------------------------ the loop

def opt_tokens() -> int:
    return sum(int(r["prompt_tokens"]) + int(r["completion_tokens"]) for r in P.read_jsonl(STATE / "optimizer_usage.jsonl"))


def loop(n_iters: int, hard_cap: int, counted: bool, ledger: bool, label: str = "") -> dict:
    ids = search_ids()
    st = P.read_json(STATE / f"loop_state{label}.json", {"done_iters": 0}) or {"done_iters": 0}
    if "phase0" not in st:
        r0 = evaluate("seed", ids, "phase0", hard_cap)
        update_frontier("seed", r0)
        append_summary(0, {"name": "seed", "path": "candidates/seed", "hypothesis": "baseline"}, r0, f"{r0['tgc']:.1%}", None)
        st["phase0"] = {"tgc": r0["tgc"]}
        P.write_json(STATE / f"loop_state{label}.json", st)
        if ledger:
            checkpoint(f"phase 0 (seed) TGC {r0['tgc']:.3f}", st)
    for it in range(st["done_iters"] + 1, n_iters + 1):
        if opt_tokens() >= P.BUDGET_OPT_TOKENS:
            P.progress_log(CAND, "P3", "optimizer token cap reached; stop")
            break
        if E.counted(CAND) + SMOKE_TASKS + len(ids) > hard_cap:
            P.progress_log(CAND, "P3", "rollout cap would be exceeded by one more iteration; stop")
            break
        t0 = time.time()
        rc, pend, meta = propose(it, f"iter{it}{label}")
        tp = round(time.time() - t0, 1)
        cands = []
        if pend is not None:
            try:
                cands = json.loads(pend.read_text()).get("candidates") or []
            except json.JSONDecodeError:
                cands = []
        if rc != 0 or not cands:
            append_summary(it, {"name": None}, None, f"proposer failed (exit {rc}, pending_eval {'ok' if pend else 'missing'})",
                           {"propose": tp})
        for c in cands[:1]:  # one candidate per iteration (the TB2 skill)
            name = str(c.get("name") or "")
            c.setdefault("path", f"candidates/{name}")
            reasons = validate(name)
            if reasons:
                append_summary(it, c, None, "failed (validation): " + "; ".join(reasons)[:300], {"propose": tp})
                continue
            t1 = time.time()
            smoke = E.evaluate(CAND, materialize(name), ids[:SMOKE_TASKS], phase="P3", split="smoke", reuse=True,
                               hard_cap=hard_cap, tag=f"smoke_it{it}")
            if smoke[0].get("error"):
                append_summary(it, c, None, "failed (smoke: infrastructure error)", {"propose": tp})
                continue
            res = evaluate(name, ids, f"it{it}", hard_cap)
            update_frontier(name, res)
            append_summary(it, c, res, f"{res['tgc']:.1%}", {"propose": tp, "bench": round(time.time() - t1, 1)})
        st["done_iters"] = it
        P.write_json(STATE / f"loop_state{label}.json", st)
        if ledger:
            checkpoint(f"iteration {it}", st)
    return st


def checkpoint(what: str, st: dict, kind: str = "result", next_unit: str | None = None) -> None:
    import status_doc
    rows = [{k: r.get(k) for k in ("iteration", "avg_pass_rate", "outcome", "delta")}
            for r in P.read_jsonl(LOGS / "evolution_summary.jsonl")]
    fr = P.read_json(LOGS / "frontier_val.json", {}) or {}
    u = P.read_jsonl(STATE / "optimizer_usage.jsonl")
    t = {"calls": len(u), "prompt_tokens": sum(r["prompt_tokens"] for r in u),
         "completion_tokens": sum(r["completion_tokens"] for r in u), "cache_read": sum(r.get("cache_read", 0) for r in u),
         "cost_usd": round(sum(float(r.get("cost_usd") or 0) for r in u), 2)}
    prog = {"candidate": CAND, "rows": rows, "best": {k: (fr.get("_best") or {}).get(k) for k in ("avg_pass_rate", "avg_tokens")},
            "counted_rollouts": E.counted(CAND), "cap": P.BUDGET_ROLLOUTS, "optimizer": t}
    P.write_json(P.PUSHED / CAND / "progress.json", prog)
    status_doc.append(kind, "P3", f"{CAND} search",
                      f"Meta-Harness {what}: best search-set TGC {prog['best']['avg_pass_rate']}. Counted rollouts "
                      f"{prog['counted_rollouts']}/{P.BUDGET_ROLLOUTS}; proposer {t['calls']} session(s), "
                      f"{t['prompt_tokens'] / 1e6:.2f}M in / {t['completion_tokens'] / 1e6:.2f}M out tok "
                      f"(+{t['cache_read'] / 1e6:.2f}M cache reads), ${t['cost_usd']:.2f} (CLI-reported).",
                      done_through=f"{CAND}/search/{what}", next_unit=next_unit or f"{CAND}/search",
                      extra={"candidate": CAND, "counts": {CAND: {"counted_rollouts": prog["counted_rollouts"]}},
                             "spend": {CAND: {"in": t["prompt_tokens"], "out": t["completion_tokens"], "usd": t["cost_usd"]}}},
                      artifacts=[f"STATE/{CAND}/progress.json"], subject=f"{CAND} {what}")


def search() -> int:
    pidf = P.AW_STATE / "RUNNING.pid"
    pidf.write_text(f"{os.getpid()} {CAND} search\n")
    try:
        setup_workspace(fresh=not (WS / "logs" / "evolution_summary.jsonl").exists())
        st = loop(MAX_ITERS, P.BUDGET_ROLLOUTS, counted=True, ledger=True)
        checkpoint(f"search finished after {st['done_iters']} iteration(s)", st, kind="phase_done",
                   next_unit=f"{CAND}/freeze")
        return 0
    finally:
        pidf.unlink(missing_ok=True)


def accept() -> int:
    """(b) validator rejects a disallowed file / an embedded task id; (c) the evaluator writes gold-free per-task
    dirs; (a) one real proposer iteration on a 4-task search set writes a valid pending_eval.json and only
    allowed files. Throwaway (AW_CAND=acc_metaharness)."""
    global search_ids
    setup_workspace(fresh=True)
    (STATE / "loop_state.json").unlink(missing_ok=True)
    shutil.rmtree(STATE / "claude_sessions", ignore_errors=True)
    out: dict = {}
    bad1 = WS / "candidates" / "bad_extra"
    shutil.copytree(WS / "candidates" / "seed", bad1)
    (bad1 / "evil.py").write_text("x = 1\n")
    bad2 = WS / "candidates" / "bad_id"
    shutil.copytree(WS / "candidates" / "seed", bad2)
    tid = P.read_split("dev")[0]
    (bad2 / "memory").mkdir(exist_ok=True)
    (bad2 / "memory" / "playbook.md").write_text(f"- remember task {tid}\n")
    out["rejects_extra_file"] = bool(validate("bad_extra"))
    out["rejects_task_id"] = bool(validate("bad_id"))
    out["accepts_seed"] = not validate("seed")
    shutil.rmtree(bad1)
    shutil.rmtree(bad2)
    dev = E.split_ids("dev")
    search_ids = lambda: dev[:4]  # noqa: E731
    before = {str(p) for p in WS.rglob("*") if p.is_file()}
    st = loop(1, 100, counted=False, ledger=False)
    runs = list((WS / "runs").rglob("eval.json"))
    rtext = "\n".join(p.read_text() for p in (WS / "runs").rglob("*") if p.is_file())
    out["per_task_dirs"] = len(runs)
    out["gold_free_runs"] = not any(s in rtext for s in ("ground_truth", "answer.json", "compiled_solution"))
    after = {str(p) for p in WS.rglob("*") if p.is_file()}
    new = sorted(p for p in after - before)
    allowed = re.compile(rf"^{re.escape(str(WS))}/(candidates/[a-z0-9_]+/(policy/instructions\.txt|tools/helpers\.py|"
                         rf"tools/api_notes\.json|memory/playbook\.md)|logs/.*|runs/.*)$")
    out["new_files_outside_allowed"] = [p.replace(str(WS), "") for p in new if not allowed.match(p)][:10]
    summ = P.read_jsonl(LOGS / "evolution_summary.jsonl")
    out["iterations"] = st.get("done_iters")
    out["pending_eval_valid"] = any(r.get("iteration") == 1 and r.get("agent") for r in summ)
    out["outcome_iter1"] = next((r.get("outcome") for r in summ if r.get("iteration") == 1), None)
    sess = sorted((STATE / "claude_sessions").glob("*/meta.json"))
    meta = json.loads(sess[-1].read_text()) if sess else {}
    out["proposer_exit"] = meta.get("exit_code")
    out["proposer_tool_calls"] = len(meta.get("tool_summary") or [])
    out["ok"] = (out["rejects_extra_file"] and out["rejects_task_id"] and out["accepts_seed"] and out["per_task_dirs"] >= 4
                 and out["gold_free_runs"] and not out["new_files_outside_allowed"] and out["pending_eval_valid"]
                 and out["proposer_exit"] == 0)
    P.write_json(P.AW_STATE / "acceptance" / "a_metaharness.json", out)
    print(json.dumps(out))
    return 0 if out["ok"] else 1


def freeze() -> int:
    fr = P.read_json(LOGS / "frontier_val.json", {}) or {}
    best = (fr.get("_best") or {}).get("agent", "seed")
    cdir = materialize(best)
    v = E.lint(cdir)
    if v:
        raise SystemExit(f"best candidate fails the lint: {v}")
    art = P.PUSHED / CAND / "artifact"
    shutil.rmtree(art, ignore_errors=True)
    for rel, t in E.read_surfaces(cdir).items():
        (art / rel).parent.mkdir(parents=True, exist_ok=True)
        (art / rel).write_text(t)
    (art / "memory").mkdir(exist_ok=True)
    summ = P.read_jsonl(LOGS / "evolution_summary.jsonl")
    P.write_json(art / "FREEZE.json", {"candidate": CAND, "label": "inert" if best == "seed" else "", "best": best,
                                       "search_tgc": fr["_best"]["avg_pass_rate"],
                                       "seed_search_tgc": next((r["avg_pass_rate"] for r in summ if r["iteration"] == 0), None),
                                       "iterations": max((r["iteration"] for r in summ), default=0),
                                       "tree_sha256": P.sha256_tree(cdir)})
    print(json.dumps(P.read_json(art / "FREEZE.json")))
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "debug":
        setup_workspace(fresh=True)
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 2
        raise SystemExit(0 if loop(n, 10**6, counted=False, ledger=False, label="_debug") else 1)
    raise SystemExit({"search": search, "accept": accept, "freeze": freeze}[cmd]())
