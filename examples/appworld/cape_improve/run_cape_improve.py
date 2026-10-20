"""Driver of the cape_improve arm: cap-evolve-improve @ 470f3fa, stock hill-climb (docs/EVAL_APPWORLD_REST.md §9.5).

  venv-aw/bin/python -I run_cape_improve.py setup [--project-root DIR] [--split-ids dev4]   # scaffold the project
  venv-aw/bin/python -I run_cape_improve.py imp-check [--level launch|full] [--run-dir RUN]  # A-cape_improve-IMP
  venv-aw/bin/python -I run_cape_improve.py accept     # cap-evolve check, gate unit check, 1-iteration mock dry run
  venv-aw/bin/python -I run_cape_improve.py search     # launch.sh: the counted run (or its resume)
  venv-aw/bin/python -I run_cape_improve.py freeze     # champion -> AW_STATE/cape_improve/champion + pushed artifact

Everything cap-evolve does runs through ``launch.sh`` (venv-cape's cap-evolve, CAPEVOLVE_SKILLS_DIR = the
pinned skills, the PATH shim ``sandbox_cc/claude`` for the optimizer). The cap-evolve project's adapter is
``cape_improve/adapter.py``: every rollout goes through the shared evaluator (cache, seed reuse, slots, PAUSE,
B = 900). Optimizer usage: the shim appends each claude result's usage to
AW_STATE/cape_improve/optimizer_usage.jsonl (§5.2 fields); cap-evolve's own state.json spend is kept as a
cross-check. Search progress (counts and aggregates only) goes to the pushed progress.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EX = HERE.parent
sys.path[:0] = [str(EX / "scripts"), str(EX / "common")]
import awrest as P  # noqa: E402

CAND = "cape_improve"
PIN = P.CAPE_IMPROVE_TREE
PIN_COMMIT = P.CAPE_IMPROVE_COMMIT
SKILLS = PIN / "skills"
VENV_CAPE = P.VENVS / "venv-cape"
CAPE_PY = VENV_CAPE / "bin" / "python"
CAPE_BIN = VENV_CAPE / "bin" / "cap-evolve"
STATE = P.cand_state(CAND)
# The counted run's project root (.capevolve/ lives under it). NOT under AW_STATE: the optimizer's workdir is
# <run dir>/work/<cid>, and AW_STATE is denied to it (§10); /workspace keeps it durable across a pod restart.
SEARCH_ROOT = P.AW_HOME / "cape_run"
ACCEPT_ROOT = STATE / "accept"                 # throwaway dry-run projects (not counted)
RUN_TS = "cape_improve_s0"
PUSHED = P.PUSHED / CAND
PINNED_TEMPLATE = PIN / "templates" / "project" / "optimizer" / "INSTRUCTIONS.md"
REQUIRED_STRINGS = ["## Strategies for selecting improvements", "**Optimize code before prompts.**",
                    "**On tools, use the whole tools skill.**",
                    "# Optimize the capability — ship the edit with the largest expected reward gain",
                    "## AppWorld facts for THIS run"]
FORBIDDEN_STRINGS = ["THREE TESTS", "VERIFY-THE-FIX", "{AW_"]
# an unfilled cap-evolve placeholder ({{FAILURES}}, {{PARALLEL_NOTE}}, ...). The prompt's own Jinja variables
# ({{ instruction }}), quoted on purpose in the AppWorld facts block, are lower case with spaces.
UNFILLED_RE = re.compile(r"\{\{[A-Z][A-Z0-9_]*\}\}")
GUIDANCE = {"tools": SKILLS / "capabilities" / "tools" / "SKILL.md",
            "system-prompt": SKILLS / "capabilities" / "system-prompt" / "SKILL.md",
            "diagnose": SKILLS / "phases" / "diagnose" / "SKILL.md"}
HC_RUN = SKILLS / "algorithms" / "hill-climb" / "scripts" / "run.py"


def sh256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def cape_env(phase: str = "search") -> dict:
    """The environment of every cap-evolve command (launch.sh sets the same)."""
    env = P.setup_env(dict(os.environ))
    for k in ("RITS_API_KET", "RITS_API_KEY"):
        env.pop(k, None)
    env.update({"CAPEVOLVE_SKILLS_DIR": str(SKILLS), "AW_CAPE_PHASE": phase, "AW_EXAMPLE": str(EX),
                "APPWORLD_ROOT": str(P.ROOT_OPT), "AW_KEY_ENV": "RITS_API_KET",
                "PATH": f"{HERE / 'sandbox_cc'}:{VENV_CAPE / 'bin'}:{env.get('PATH', '')}"})
    env.pop("CLAUDECODE", None)
    return env


# ---------------------------------------------------------------- setup

def lint_cmd_parts() -> dict:
    """The lint the optimizer runs inside its sandbox: the small lint venv (jinja2 + tiktoken, no AppWorld) on a
    copy of lints.py and of the lint cache staged next to the project's reference files (not under AW_STATE)."""
    import sandbox as SB
    py = SB.ensure_lint_venv()
    tools = SB.OPT_ROOT / CAND / "lint"
    tools.mkdir(parents=True, exist_ok=True)
    shutil.copy2(EX / "adapters" / "lints.py", tools / "lints.py")
    shutil.copy2(P.LINT_CACHE, tools / "lint_cache.json")
    return {"AW_LINT_PY": f"TIKTOKEN_CACHE_DIR={SB.TIKTOKEN_CACHE} {py} -I", "AW_LINTS": str(tools / "lints.py"),
            "AW_LINT_CACHE": str(tools / "lint_cache.json")}


def render_instructions(dst: Path) -> str:
    text = (HERE / "INSTRUCTIONS.template.md").read_text(encoding="utf-8")
    for k, v in lint_cmd_parts().items():
        text = text.replace("{" + k + "}", v)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")
    return text


def write_diff() -> Path:
    PUSHED.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["diff", "-u", "--label", "pinned:templates/project/optimizer/INSTRUCTIONS.md",
                        "--label", "examples/appworld/cape_improve/INSTRUCTIONS.template.md",
                        str(PINNED_TEMPLATE), str(HERE / "INSTRUCTIONS.template.md")], capture_output=True, text=True)
    out = PUSHED / "instructions.diff"
    P.atomic_write(out, r.stdout)
    return out


def diff_only_insertion(diff_text: str) -> bool:
    body = [x for x in diff_text.splitlines() if not x.startswith(("---", "+++", "@@"))]
    return not any(x.startswith("-") for x in body) and any(x.startswith("+## AppWorld facts for THIS run") for x in body)


def setup(root: Path, split_ids: str = "full", force: bool = False) -> Path:
    """Scaffold <root>/.capevolve/project with the PINNED intake script, then add the arm's files.
    split_ids: "full" = train = val = train ∪ dev (147), test = [] (§9.5); "dev4" = the first 4 dev ids (A dry run)."""
    proj = root / ".capevolve" / "project"
    if (proj / "capevolve.yaml").exists() and not force:   # a scaffolded project, not just a dir (A9 plants in adapters/)
        return proj
    root.mkdir(parents=True, exist_ok=True)
    env = cape_env()
    r = subprocess.run([str(CAPE_PY), str(SKILLS / "phases" / "intake" / "scripts" / "run.py"), "--base",
                        str(root / ".capevolve"), "--workdir", str(HERE), "--force"], env=env, capture_output=True,
                       text=True)
    if r.returncode:
        raise SystemExit(f"intake failed: {r.stderr[-1500:]}")
    (proj / "adapters").mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / "adapter.py", proj / "adapters" / "adapter.py")
    shutil.rmtree(proj / "seed_capability", ignore_errors=True)
    shutil.copytree(P.SEED_CAP, proj / "seed_capability")
    (proj / "reference").mkdir(exist_ok=True)
    for f in ("api_index.md", "react_agent_notes.md"):
        shutil.copy2(P.REFERENCE / f, proj / "reference" / f)
    ids = P.read_split("train") + P.read_split("dev") if split_ids == "full" else P.read_split("dev")[:4]
    if split_ids == "full" and len(ids) != 147:
        raise SystemExit(f"train ∪ dev has {len(ids)} ids, expected 147")
    P.write_json(proj / "split_ids.json", {"train": ids, "val": ids, "test": []})
    instr = proj / "optimizer" / "INSTRUCTIONS.md"
    render_instructions(instr)
    spec = (HERE / "capevolve.yaml").read_text().replace("@INSTRUCTIONS@", str(instr)).replace(
        "@REFERENCE@", str(proj / "reference"))
    (proj / "capevolve.yaml").write_text(spec)
    (proj / "PROJECT.md").write_text(
        "# cape_improve: AppWorld (official splits), gpt-oss-120b on RITS, cap-evolve-improve @ 470f3fa, hill-climb --focus all\n\n"
        "Plan: docs/EVAL_APPWORLD_REST.md §9.5. Resolved inputs:\n"
        "- capability: system-prompt + tools (seed: stock AppWorld ReAct prompt @ 42b5bcf, empty helpers, no notes)\n"
        "- target: openai/gpt-oss-120b-a100 on RITS, reasoning medium, temperature 0\n"
        f"- optimizer: claude-code, {P.OPT_MODEL}, sandboxed by examples/appworld/cape_improve/sandbox_cc/claude; "
        f"instructions: {instr} (re-derived from the pinned template)\n"
        f"- data: adapter tasks(); split_ids.json train = val = {len(ids)} ids, test = []\n"
        "- rollouts: through the shared evaluator (cache, shared seed baseline, global slots, PAUSE, B = 900)\n"
        "- gate: paired, k = 0.5 (cap-evolve-improve default, explicit); 1 trial; 6 iterations; "
        "max_metric_calls 1029; max_optimizer_usd 120\n")
    return proj


# ---------------------------------------------------------------- IMP checks (A-cape_improve-IMP)

def _imp_launch(proj: Path | None) -> dict:
    """IMP checks 1, 2, 3 (spec level). launch.sh re-runs these before every run / resume."""
    out = {}
    env = cape_env()
    r = subprocess.run([str(CAPE_PY), "-c", "import cap_evolve, pathlib; print(pathlib.Path(cap_evolve.__file__).resolve())"],
                       env=env, capture_output=True, text=True)
    loc = r.stdout.strip()
    head = subprocess.run(["git", "-C", str(PIN), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(PIN), "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
    out["1_code_pin"] = {"ok": loc.startswith(str(PIN / "core")) and head == PIN_COMMIT and not dirty,
                         "cap_evolve_file": loc, "head": head, "clean": not dirty}
    r = subprocess.run([str(CAPE_PY), "-c", "from cap_evolve import cli; print(cli._find_skills_dir())"],
                       env=env, capture_output=True, text=True, cwd=str(proj.parent.parent) if proj else None)
    sd = r.stdout.strip()
    out["2_skills_pin"] = {"ok": sd == str(SKILLS) and sd != os.path.expanduser("~/.claude/skills"),
                           "resolved": sd, "home_skills_exists": Path("~/.claude/skills").expanduser().is_dir()}
    if proj:
        spec = (proj / "capevolve.yaml").read_text()
        m = re.search(r"^gate_k_se:\s*([0-9.]+)", spec, re.M)
        out["3_spec_k_se"] = {"ok": bool(m) and float(m.group(1)) == 0.5, "value": m and float(m.group(1))}
    return out


def _run_events(run_dir: Path) -> list[dict]:
    return P.read_jsonl(run_dir / "events.jsonl")


def _imp_run(proj: Path, run_dir: Path) -> dict:
    """IMP checks 3 (run_config), 4 (effective k-se), 5, 6, 7 on a run dir."""
    out = {}
    ev = _run_events(run_dir)
    rc = [e for e in ev if e.get("kind") == "run_config" or e.get("event") == "run_config"]
    spec_path = Path(rc[0]["spec"]) if rc and rc[0].get("spec") else None
    if spec_path and not spec_path.is_absolute():
        spec_path = proj.parent.parent / spec_path
    kse = None
    if spec_path and spec_path.is_file():
        m = re.search(r"^gate_k_se:\s*([0-9.]+)", spec_path.read_text(), re.M)
        kse = m and float(m.group(1))
    out["3_run_config"] = {"ok": bool(rc) and kse == 0.5, "run_config_events": len(rc), "spec_k_se": kse}
    cmdlog = STATE / "proc_cmdlines.jsonl"
    hc = [x for x in P.read_jsonl(cmdlog) if str(HC_RUN) in x.get("cmd", "")]
    ks = sorted({m.group(1) for x in hc for m in [re.search(r"--k-se (\S+)", x["cmd"])] if m})
    gates = [e for e in ev if (e.get("kind") or e.get("event")) in ("gate", "step") and "k_se" in json.dumps(e)]
    out["4_effective_k_se"] = {"ok": ks == ["0.5"], "hill_climb_cmdlines": len(hc), "k_se_values": ks,
                               "gate_events_mentioning_k_se": len(gates)}
    works = sorted((run_dir / "work").glob("*/INSTRUCTIONS.md"))
    inst = []
    for w in works:
        t = w.read_text(encoding="utf-8")
        inst.append({"cid": w.parent.name, "has": {s: (s in t) for s in REQUIRED_STRINGS},
                     "forbidden": [s for s in FORBIDDEN_STRINGS if s in t] + sorted(set(UNFILLED_RE.findall(t)))})
    diff = (PUSHED / "instructions.diff").read_text() if (PUSHED / "instructions.diff").exists() else ""
    out["5_instructions"] = {"ok": bool(inst) and all(all(i["has"].values()) and not i["forbidden"] for i in inst)
                             and diff_only_insertion(diff), "iterations": len(inst),
                             "diff_only_insertion": diff_only_insertion(diff), "detail": inst}
    g = []
    for w in sorted((run_dir / "work").glob("*/guidance")):
        row = {"cid": w.parent.name}
        for name, src in GUIDANCE.items():
            f = w / name / "SKILL.md"
            if not f.is_file():
                row[name] = "missing"
            elif name == "diagnose":
                head_src = src.read_text().splitlines()[:5]
                row[name] = "head_match" if f.read_text().splitlines()[:5] == head_src else "head_differs"
            else:
                row[name] = "sha_match" if sh256(f) == sh256(src) else "sha_differs"
        g.append(row)
    out["6_guidance"] = {"ok": bool(g) and all(r.get("tools") == "sha_match" and r.get("system-prompt") == "sha_match"
                                               and r.get("diagnose") == "head_match" for r in g), "detail": g,
                         "pinned_sha256": {k: sh256(v) for k, v in GUIDANCE.items()}}
    out["7_hill_climb_script"] = {"ok": bool(hc), "path": str(HC_RUN), "sha256": sh256(HC_RUN)}
    return out


def imp_check(level: str, run_dir: Path | None = None, proj: Path | None = None) -> dict:
    proj = proj or (SEARCH_ROOT / ".capevolve" / "project")
    res = _imp_launch(proj if proj.exists() else None)
    if level == "full" and run_dir:
        res.update(_imp_run(proj, run_dir))
    res["all_ok"] = all(v.get("ok") for k, v in res.items() if isinstance(v, dict))
    return res


# ---------------------------------------------------------------- running cap-evolve

def run_capevolve(proj: Path, *, ts: str, phase: str, extra: list[str] | None = None,
                  log: Path | None = None) -> int:
    """`cap-evolve run` via launch.sh, with a sampler that records the hill-climb command line (IMP 4, 7)."""
    log = log or (P.PROGRESS / f"{CAND}.out")
    env = cape_env(phase)
    env["AW_CAPE_TS"] = ts
    # the cap-evolve project's adapter wiring is evaluator code: hidden from the optimizer too (§10 DENY)
    env["AW_CAPE_EXTRA_DENY"] = str(proj / "adapters")
    p = subprocess.Popen(["bash", str(HERE / "launch.sh"), str(proj), ts, *(extra or [])], env=env,
                         stdout=open(log, "a"), stderr=subprocess.STDOUT, start_new_session=True)
    seen: set[str] = set()
    while p.poll() is None:
        _sample_cmdlines(seen)
        time.sleep(2)
    _sample_cmdlines(seen)
    return p.returncode


def _sample_cmdlines(seen: set[str]) -> None:
    """Record command lines of the run's hill-climb and run-optimizer processes (by /proc, never pgrep -f)."""
    for d in Path("/proc").iterdir():
        if not d.name.isdigit():
            continue
        try:
            cmd = (d / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="ignore").strip()
        except OSError:
            continue
        if (str(HC_RUN) in cmd or "run-optimizer/scripts/run.py" in cmd) and cmd not in seen:
            seen.add(cmd)
            P.append_jsonl(STATE / "proc_cmdlines.jsonl", {"t": P.utcnow(), "pid": int(d.name), "cmd": cmd[:4000]})


def latest_run_dir(root: Path, ts: str) -> Path:
    return root / ".capevolve" / f"run_{ts}"


# ---------------------------------------------------------------- acceptance

def gate_unit_check() -> dict:
    """With the PINNED gate.py: a paired delta vector whose mean is 0.7·SE is accepted at k_se 0.5, rejected at 1.0."""
    code = r"""
import json, math
from cap_evolve import gate
n = 100
e = [0.1 if i % 2 else -0.1 for i in range(n)]      # zero-mean spread; a shift leaves the SE unchanged
se0 = math.sqrt(sum(x * x for x in e) / (n - 1) / n)
d = [x + 0.7 * se0 for x in e]                      # mean = 0.7 * SE exactly
m = sum(d) / n; se = math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1) / n)
a = gate.decide(0.0, m, mode="paired", k_se=0.5, paired_deltas=d)
b = gate.decide(0.0, m, mode="paired", k_se=1.0, paired_deltas=d)
print(json.dumps({"mean_over_se": round(m / se, 6), "accept_k05": a.accept, "accept_k10": b.accept,
                  "reason_k05": a.reason, "reason_k10": b.reason, "gate_file": gate.__file__}))
"""
    r = subprocess.run([str(CAPE_PY), "-c", code], capture_output=True, text=True, env=cape_env("accept"))
    d = json.loads(r.stdout.strip().splitlines()[-1])
    d["ok"] = d["accept_k05"] is True and d["accept_k10"] is False and d["gate_file"].startswith(str(PIN / "core"))
    return d


def accept() -> int:
    """A-cape_improve items that need neither A9 nor a finished P3 (the mock dry run is not counted)."""
    res = {}
    root = ACCEPT_ROOT / f"dry_{time.strftime('%Y%m%dT%H%M%S')}"
    proj = setup(root, split_ids="dev4", force=True)
    write_diff()
    env = cape_env("accept")
    r = subprocess.run([str(CAPE_BIN), "check", str(proj)], env=env, capture_output=True, text=True,
                       cwd=str(proj.parent.parent))
    try:
        chk = json.loads(r.stdout)
    except json.JSONDecodeError:
        chk = {"ok": False, "stdout": r.stdout[-800:], "stderr": r.stderr[-800:]}
    res["capevolve_check"] = {"ok": chk.get("ok") is True, "report": chk}
    res["gate_unit"] = gate_unit_check()
    # 1-iteration mock dry run on 4 dev ids: optimizer_skill mock, the mock edit appends a generic API note
    spec = (proj / "capevolve.yaml").read_text()
    spec = re.sub(r"^optimizer_skill:.*$", "optimizer_skill: mock", spec, flags=re.M)
    spec = re.sub(r"^max_iterations:.*$", "max_iterations: 1", spec, flags=re.M)
    spec = re.sub(r"^max_metric_calls:.*$", "max_metric_calls: 8", spec, flags=re.M)
    (proj / "capevolve.yaml").write_text(spec)
    P.write_json(proj.parent.parent / "mock_script.json", {"edits": [{"file": "tools/api_notes.json", "op": "set",
                 "text": json.dumps({"api_docs": "Call show_api_doc before calling an API for the first time."})}]})
    env_ts = f"dry_{root.name}"
    (STATE / "proc_cmdlines.jsonl").unlink(missing_ok=True)
    os.environ["CAPEVOLVE_MOCK_SCRIPT"] = str(proj.parent.parent / "mock_script.json")
    rc = run_capevolve(proj, ts=env_ts, phase="accept", log=STATE / "accept_dry_run.log")
    rd = latest_run_dir(root, env_ts)
    st = P.read_json(rd / "state.json", {}) or {}
    ev = _run_events(rd)
    kinds = {}
    for e in ev:
        k = e.get("kind") or e.get("event")
        kinds[k] = kinds.get(k, 0) + 1
    steps = [e for e in ev if (e.get("kind") or e.get("event")) == "step"]
    res["mock_dry_run"] = {"ok": rc == 0 and bool(steps), "returncode": rc, "run_dir": str(rd),
                           "spent": st.get("spent"), "best_id": st.get("best_id"), "event_kinds": kinds,
                           "steps": [{k: s.get(k) for k in ("candidate", "accept", "val", "parent_val", "reason")}
                                     for s in steps],
                           "counted_cape_improve_search": len(P.read_jsonl(STATE / "rollouts.jsonl")),
                           "accept_rollouts": len(P.read_jsonl(STATE / "accept_rollouts.jsonl")),
                           "cache_hits": len(P.read_jsonl(STATE / "cache_hits.jsonl"))}
    res["imp"] = imp_check("full", rd, proj)
    P.write_json(STATE / "accept_result.json", res)
    print(json.dumps(res, indent=1)[:20000])
    return 0 if all(v.get("ok") for k, v in res.items() if k != "imp") and res["imp"]["all_ok"] else 1


# ---------------------------------------------------------------- search / freeze

def _progress(rd: Path, stage: str) -> dict:
    import opt_llm
    st = P.read_json(rd / "state.json", {}) or {}
    ev = _run_events(rd)
    steps = [e for e in ev if (e.get("kind") or e.get("event")) == "step"]
    base = next((e for e in ev if (e.get("kind") or e.get("event")) == "baseline"), {})
    t = opt_llm.totals(CAND)
    best = st.get("spent", {}).get("best_val")
    pr = {"stage": stage, "counted_rollouts": len(P.read_jsonl(STATE / "rollouts.jsonl")),
          "cache_hits": len(P.read_jsonl(STATE / "cache_hits.jsonl")),
          "lint_rejects": len(P.read_jsonl(STATE / "lint_rejects.jsonl")),
          "iterations_done": len(steps), "accepted": sum(1 for s in steps if s.get("accept")),
          "iteration_vals": [s.get("val") for s in steps], "baseline_val": base.get("val") or base.get("score"),
          "best_search_score": best,
          "best_search_label": "val = train ∪ dev (147), a fit metric, selection-biased",
          "metric_calls": st.get("spent", {}).get("metric_calls"),
          "capevolve_optimizer_usd": st.get("spent", {}).get("optimizer_usd"),
          "optimizer": {"calls": t["calls"], "prompt_tokens": t["prompt_tokens"],
                        "completion_tokens": t["completion_tokens"], "cache_read": t["cache_read"],
                        "proxy_usd": opt_llm.proxy_usd(t)},
          "eta": f"{max(0, 6 - len(steps))} of 6 iterations left (about 40-60 min each)"}
    P.write_json(PUSHED / "progress.json", pr)
    return pr


def search() -> int:
    proj = setup(SEARCH_ROOT, "full")
    write_diff()
    rd = latest_run_dir(SEARCH_ROOT, RUN_TS)
    extra = ["--resume"] if (rd / "state.json").exists() else []
    if extra:
        # #876: evaluation-error steps consume iterations; keep 6 SCORED iterations as the target
        steps = [e for e in _run_events(rd) if (e.get("kind") or e.get("event")) == "step"]
        lost = sum(1 for e in _run_events(rd) if (e.get("kind") or e.get("event")) == "step_indecisive")
        extra += ["--max-iterations", str(6 + lost)] if lost else []
        P.progress_log(CAND, "search", f"resume: {len(steps)} steps on record, {lost} indecisive")
    rc = run_capevolve(proj, ts=RUN_TS, phase="search", extra=extra)
    _progress(rd, "search finished" if rc == 0 else f"search stopped (exit {rc})")
    return rc


def freeze() -> int:
    import evaluator as E
    rd = latest_run_dir(SEARCH_ROOT, RUN_TS)
    st = P.read_json(rd / "state.json", {}) or {}
    best = st.get("best_id")
    src = rd / "candidates" / best if best else None
    inert = not best or best == "seed" or not (src and src.is_dir())
    files = {} if inert else E.read_surfaces(src)
    cdir = E.materialize(CAND, files)
    v = E.lint(cdir)
    if v:
        raise SystemExit(f"champion fails the lint: {v}")
    dst = STATE / "champion"
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(cdir, dst, ignore=shutil.ignore_patterns(".done"))
    art = PUSHED / "artifact"
    shutil.rmtree(art, ignore_errors=True)
    shutil.copytree(cdir, art, ignore=shutil.ignore_patterns(".done"))
    fz = {"best_id": best, "inert": inert, "tree_sha256": E.tree_hash(cdir), "seed_tree_sha256": E.seed_hash(),
          "best_val": st.get("spent", {}).get("best_val"), "imp": imp_check("full", rd)}
    P.write_json(art / "FREEZE.json", fz)
    _progress(rd, "frozen" + (" (inert: nothing accepted)" if inert else ""))
    print(json.dumps({k: fz[k] for k in ("best_id", "inert", "tree_sha256", "best_val")}))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["setup", "imp-check", "accept", "search", "freeze"])
    ap.add_argument("--project-root")
    ap.add_argument("--split-ids", default="full")
    ap.add_argument("--level", default="launch")
    ap.add_argument("--run-dir")
    ap.add_argument("--project")
    a = ap.parse_args()
    if a.cmd == "setup":
        print(setup(Path(a.project_root) if a.project_root else SEARCH_ROOT, a.split_ids, force=True))
        print(write_diff())
        return 0
    if a.cmd == "imp-check":
        r = imp_check(a.level, Path(a.run_dir) if a.run_dir else None, Path(a.project) if a.project else None)
        print(json.dumps(r, indent=1))
        return 0 if r["all_ok"] else 1
    return {"accept": accept, "search": search, "freeze": freeze}[a.cmd]()


if __name__ == "__main__":
    raise SystemExit(main())
