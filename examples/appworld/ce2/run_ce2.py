"""Driver of the CE2 arms: cap-evolve impr2 @ 8194578, stock hill-climb, gate K = 1 (ce2_k1) or 2 (ce2_k2)
(docs/EVAL_APPWORLD_CE2.md §9-11; adapted from REST's run_cape_improve.py). Source ce2/env.sh first.

  python -I run_ce2.py setup --arm A [--project-root DIR] [--split-ids dev4]   # scaffold the arm's project
  python -I run_ce2.py imp-check --arm A [--level launch|full] [--run-dir RUN]  # A-CE2 items 1-7
  python -I run_ce2.py accept --arm A     # cap-evolve check, gate unit check, 1-iteration mock dry run (A-CE2 4-7)
  python -I run_ce2.py same               # A-CE2-SAME: the two arms' rendered spec / INSTRUCTIONS differ only in K etc.
  python -I run_ce2.py search --arm A     # launch_ce2.sh: the counted run (or its resume)
  python -I run_ce2.py freeze --arm A     # champion -> AW_STATE/<arm>/champion + pushed artifact (all surfaces)

Everything cap-evolve does runs through ``launch_ce2.sh`` (venv-ce2's cap-evolve, CAPEVOLVE_SKILLS_DIR = the
pinned skills, the PATH shim ``sandbox_cc/claude``). The project adapter is ``ce2/adapter.py``: every rollout goes
through the shared evaluator (cache, reused seed baseline, slots, PAUSE, B = 900). Optimizer usage: the shim appends
each claude result's modelUsage to AW_STATE/<arm>/optimizer_usage.jsonl; cap-evolve's state.json spend is a
cross-check. Search progress (counts and aggregates only) goes to the pushed <arm>/progress.json.
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

if P.LEDGER_PREFIX != "CE2":
    raise SystemExit("run_ce2.py: source examples/appworld/ce2/env.sh first (AW_PROFILE=ce2)")
PIN = P.CAPE_TREE
PIN_COMMIT = P.CAPE_COMMIT
SKILLS = PIN / "skills"
VENV_CAPE = P.VENVS / "venv-ce2"
CAPE_PY = VENV_CAPE / "bin" / "python"
CAPE_BIN = VENV_CAPE / "bin" / "cap-evolve"
# set by select_arm(): the arm, its K, its state dir, its counted run's project root (NOT under AW_STATE: the
# optimizer's workdir is <run dir>/work/<cid>, and AW_STATE is denied to it, §12), its accept root and run ts
CAND = K = STATE = SEARCH_ROOT = ACCEPT_ROOT = RUN_TS = PUSHED = None


def select_arm(arm: str) -> None:
    global CAND, K, STATE, SEARCH_ROOT, ACCEPT_ROOT, RUN_TS, PUSHED
    if arm not in P.CANDIDATES:
        raise SystemExit(f"--arm must be one of {P.CANDIDATES}")
    CAND, K = arm, float(P.K_SE[arm])
    STATE = P.cand_state(arm)
    SEARCH_ROOT = P.RUN_ROOTS[arm]
    ACCEPT_ROOT = STATE / "accept"              # throwaway dry-run projects (not counted)
    RUN_TS = P.RUN_TS[arm]
    PUSHED = P.PUSHED / arm
    os.environ["AW_CAPE_ARM"] = arm


DIFF_OUT = P.PUSHED / "ce2" / "instructions.diff"
SHARED_INSTRUCTIONS = P.AW_STATE / "ce2" / "INSTRUCTIONS.md"
PINNED_TEMPLATE = PIN / "templates" / "project" / "optimizer" / "INSTRUCTIONS.md"
REQUIRED_STRINGS = ["# Optimize the capability — ship the edit with the largest expected objective score gain",
                    "## PREPARATION:", "### 1. Understand the objective score", "## Strategies for constructing edits:",
                    "### 4. Make capabilities that are SOFT and allow JUDGEMENT CALLS",
                    "### 6. On code surfaces (tools, MCP): prefer code over prose", "## AppWorld facts for THIS run",
                    "**Objective score for this run.**"]
FORBIDDEN_STRINGS = ["## Strategies for selecting improvements", "largest expected reward gain", "THREE TESTS",
                     "VERIFY-THE-FIX", "{AW_"]
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
    """The environment of every cap-evolve command (launch_ce2.sh sets the same)."""
    env = P.setup_env(dict(os.environ))
    for k in ("RITS_API_KET", "RITS_API_KEY"):
        env.pop(k, None)
    env.update({"CAPEVOLVE_SKILLS_DIR": str(SKILLS), "AW_CAPE_PHASE": phase, "AW_EXAMPLE": str(EX), "AW_CAPE_ARM": CAND,
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
    tools = SB.OPT_ROOT / "lint"           # identical for both arms (rule Q4); not under a denied path
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
    DIFF_OUT.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["diff", "-u", "--label", "pinned:templates/project/optimizer/INSTRUCTIONS.md",
                        "--label", "examples/appworld/ce2/INSTRUCTIONS.template.md",
                        str(PINNED_TEMPLATE), str(HERE / "INSTRUCTIONS.template.md")], capture_output=True, text=True)
    out = DIFF_OUT
    P.atomic_write(out, r.stdout)
    return out


def diff_only_insertion(diff_text: str) -> bool:
    body = [x for x in diff_text.splitlines() if not x.startswith(("---", "+++", "@@"))]
    return not any(x.startswith("-") for x in body) and any(x.startswith("+## AppWorld facts for THIS run") for x in body)


def setup(root: Path, split_ids: str = "full", force: bool = False) -> Path:
    """Scaffold <root>/.capevolve/project with the PINNED intake script, then add the arm's files.
    split_ids: "full" = train = val = train ∪ dev (147), test = [] (§13 S2); "dev4" = the first 4 dev ids (A dry run)."""
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
    # plan §9.4 step 4: both arms point optimizer_instructions_file at the SAME rendered file. It lives in AW_STATE,
    # which the optimizer's sandbox denies; the harness (unsandboxed) reads it and writes work/<cid>/INSTRUCTIONS.md.
    instr = SHARED_INSTRUCTIONS if split_ids == "full" else proj / "optimizer" / "INSTRUCTIONS.md"
    render_instructions(instr)
    if instr != proj / "optimizer" / "INSTRUCTIONS.md":
        (proj / "optimizer").mkdir(parents=True, exist_ok=True)
        (proj / "optimizer" / "INSTRUCTIONS.md").write_text(instr.read_text(encoding="utf-8"), encoding="utf-8")
    spec = (HERE / "capevolve.yaml").read_text().replace("@INSTRUCTIONS@", str(instr)).replace(
        "@REFERENCE@", str(proj / "reference")).replace("@K_SE@", f"{int(K)}")
    (proj / "capevolve.yaml").write_text(spec)
    (proj / "PROJECT.md").write_text(
        f"# {CAND}: AppWorld (official splits), gpt-oss-120b on RITS, cap-evolve impr2 @ 8194578, hill-climb --focus all\n\n"
        "Plan: docs/EVAL_APPWORLD_CE2.md §9-11. Resolved inputs:\n"
        "- capability: system-prompt + tools (seed: stock AppWorld ReAct prompt @ 42b5bcf, empty helpers, no notes)\n"
        "- target: openai/gpt-oss-120b-a100 on RITS, reasoning medium, temperature 0\n"
        f"- optimizer: claude-code, {P.OPT_MODEL}, sandboxed by examples/appworld/ce2/sandbox_cc/claude; "
        f"instructions: {instr} (re-derived from the pinned template)\n"
        f"- data: adapter tasks(); split_ids.json train = val = {len(ids)} ids, test = []\n"
        "- rollouts: through the shared evaluator (cache, seed baseline reused from REST P3, global slots, PAUSE, B = 900)\n"
        f"- gate: paired, K = {int(K)} (gate_k_se, explicit); 1 trial; 6 iterations; max_metric_calls 1029; "
        "max_optimizer_usd 120\n"
        "- objective score = reward (single objective; no objectives: block)\n")
    return proj


# ---------------------------------------------------------------- IMP checks (A-CE2 items 1-7)

def _imp_launch(proj: Path | None) -> dict:
    """IMP checks 1, 2, 3 (spec level). launch_ce2.sh re-runs these before every run / resume."""
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
        out["3_spec_k_se"] = {"ok": bool(m) and float(m.group(1)) == K, "value": m and float(m.group(1)), "expected": K}
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
    out["3_run_config"] = {"ok": bool(rc) and kse == K, "run_config_events": len(rc), "spec_k_se": kse}
    cmdlog = STATE / f"proc_cmdlines_{run_dir.name}.jsonl"     # one log per run dir (dry run vs search)
    hc = [x for x in P.read_jsonl(cmdlog) if str(HC_RUN) in x.get("cmd", "")]
    ks = sorted({m.group(1) for x in hc for m in [re.search(r"--k-se (\S+)", x["cmd"])] if m})
    gates = [e for e in ev if (e.get("kind") or e.get("event")) in ("gate", "step") and "k_se" in json.dumps(e)]
    out["4_effective_k_se"] = {"ok": ks == [str(float(K))] or ks == [str(int(K))], "hill_climb_cmdlines": len(hc),
                               "k_se_values": ks, "expected": K,
                               "gate_events_mentioning_k_se": len(gates)}
    works = sorted((run_dir / "work").glob("*/INSTRUCTIONS.md"))
    inst = []
    for w in works:
        t = w.read_text(encoding="utf-8")
        inst.append({"cid": w.parent.name, "has": {s: (s in t) for s in REQUIRED_STRINGS},
                     "forbidden": [s for s in FORBIDDEN_STRINGS if s in t] + sorted(set(UNFILLED_RE.findall(t)))})
    diff = DIFF_OUT.read_text() if DIFF_OUT.exists() else ""
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
    res = _imp_launch(proj if (proj / "capevolve.yaml").exists() else None)
    if "3_spec_k_se" not in res:              # CE2: a launch with no scaffolded spec fails item 3 (REST CP-0031/0034)
        res["3_spec_k_se"] = {"ok": False, "value": None, "expected": K, "reason": f"no capevolve.yaml in {proj}"}
    if level == "full" and run_dir:
        res.update(_imp_run(proj, run_dir))
    res["all_ok"] = all(v.get("ok") for k, v in res.items() if isinstance(v, dict))
    return res


# ---------------------------------------------------------------- running cap-evolve

def run_capevolve(proj: Path, *, ts: str, phase: str, extra: list[str] | None = None,
                  log: Path | None = None) -> int:
    """`cap-evolve run` via launch_ce2.sh, with a sampler that records the hill-climb command line (IMP 4, 7)."""
    log = log or (P.PROGRESS / f"{CAND}.out")
    env = cape_env(phase)
    env["AW_CAPE_TS"] = ts
    global _RUN_NAME
    _RUN_NAME = f"run_{ts}"
    # the cap-evolve project's adapter wiring is evaluator code: hidden from the optimizer too (§10 DENY)
    env["AW_CAPE_EXTRA_DENY"] = str(proj / "adapters")
    p = subprocess.Popen(["bash", str(HERE / "launch_ce2.sh"), CAND, str(proj), ts, *(extra or [])], env=env,
                         stdout=open(log, "a"), stderr=subprocess.STDOUT, start_new_session=True)
    seen: set[str] = set()
    while p.poll() is None:
        _sample_cmdlines(seen)
        time.sleep(2)
    _sample_cmdlines(seen)
    return p.returncode


_RUN_NAME = "run_unknown"


def _sample_cmdlines(seen: set[str]) -> None:
    """Record command lines of the run's hill-climb and run-optimizer processes (by /proc, never pgrep -f)."""
    for d in Path("/proc").iterdir():
        if not d.name.isdigit():
            continue
        try:
            cmd = (d / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="ignore").strip()
        except OSError:
            continue
        if (str(HC_RUN) in cmd or "run-optimizer/scripts/run.py" in cmd) and _RUN_NAME in cmd and cmd not in seen:
            seen.add(cmd)
            P.append_jsonl(STATE / f"proc_cmdlines_{_RUN_NAME}.jsonl",
                           {"t": P.utcnow(), "pid": int(d.name), "cmd": cmd[:4000]})


def latest_run_dir(root: Path, ts: str) -> Path:
    return root / ".capevolve" / f"run_{ts}"


# ---------------------------------------------------------------- acceptance

def gate_unit_check() -> dict:
    """A-CE2 item 4 with the PINNED gate.py (decide, mode paired): a delta vector with mean = 1.5·SE is accepted at
    k_se 1 and rejected at 2; 2.5·SE is accepted by both; 0.7·SE is rejected by both."""
    code = r"""
import json, math
from cap_evolve import gate
n = 147
e = [0.1 if i % 2 else -0.1 for i in range(n - 1)] + [0.0]   # zero-mean spread; a shift leaves the SE unchanged
mu = sum(e) / n; e = [x - mu for x in e]
se0 = math.sqrt(sum(x * x for x in e) / (n - 1) / n)
out = {"gate_file": gate.__file__, "cases": {}}
for f in (0.7, 1.5, 2.5):
    d = [x + f * se0 for x in e]
    m = sum(d) / n; se = math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1) / n)
    r = {"mean_over_se": round(m / se, 6)}
    for k in (1.0, 2.0):
        g = gate.decide(0.0, m, mode="paired", k_se=k, paired_deltas=d)
        r[f"accept_k{int(k)}"] = g.accept
        r[f"reason_k{int(k)}"] = g.reason
    out["cases"][str(f)] = r
print(json.dumps(out))
"""
    r = subprocess.run([str(CAPE_PY), "-c", code], capture_output=True, text=True, env=cape_env("accept"))
    d = json.loads(r.stdout.strip().splitlines()[-1])
    c = d["cases"]
    d["ok"] = (c["1.5"]["accept_k1"] is True and c["1.5"]["accept_k2"] is False
               and c["2.5"]["accept_k1"] is True and c["2.5"]["accept_k2"] is True
               and c["0.7"]["accept_k1"] is False and c["0.7"]["accept_k2"] is False
               and d["gate_file"].startswith(str(PIN / "core")))
    return d


def accept() -> int:
    """A-CE2 items 3-7 for the arm (the mock dry run on 4 dev ids is not counted; phase accept)."""
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
                           "counted_search": len(P.read_jsonl(STATE / "rollouts.jsonl")),
                           "accept_rollouts": len(P.read_jsonl(STATE / "accept_rollouts.jsonl")),
                           "cache_hits": len(P.read_jsonl(STATE / "cache_hits.jsonl"))}
    res["imp"] = imp_check("full", rd, proj)
    P.write_json(STATE / "accept_result.json", res)
    print(json.dumps(res, indent=1)[:20000])
    return 0 if all(v.get("ok") for k, v in res.items() if k != "imp") and res["imp"]["all_ok"] else 1


# ---------------------------------------------------------------- search / freeze

_GATE_RE = re.compile(r"paired Δ̄=([+-][0-9.]+) (?:>|<=) ([0-9.]+)·SE=([0-9.]+) \(SE=([0-9.]+)")


def iteration_rows(rd: Path) -> list[dict]:
    """Per-iteration verdicts (counts and aggregates only): val, paired Δ̄, SE, K·SE, accept; for every arm also
    whether the same Δ̄ / SE would clear K = 1 (a reporting column for ce2_k2, never used to accept; plan §11)."""
    rows = []
    for e in _run_events(rd):
        if (e.get("kind") or e.get("event")) != "step":
            continue
        reason = str(e.get("reason") or "")
        m = _GATE_RE.search(reason)
        row = {"candidate": e.get("candidate"), "accept": e.get("accept"), "val": e.get("val"),
               "parent_val": e.get("parent_val"), "indecisive": bool(e.get("indecisive"))}
        if m:
            d, k, bar, se = (float(x) for x in m.groups())
            row.update(delta=d, se=se, k_se=k, bar=bar, would_pass_k1=d > 1.0 * se)
        rows.append(row)
    return rows


def _progress(rd: Path, stage: str) -> dict:
    import opt_llm
    st = P.read_json(rd / "state.json", {}) or {}
    ev = _run_events(rd)
    rows = iteration_rows(rd)
    base = next((e for e in ev if (e.get("kind") or e.get("event")) == "baseline"), {})
    t = opt_llm.totals(CAND)
    best = st.get("spent", {}).get("best_val")
    scored = [r for r in rows if not r["indecisive"]]
    pr = {"stage": stage, "arm": CAND, "k_se": K, "counted_rollouts": len(P.read_jsonl(STATE / "rollouts.jsonl")),
          "cache_hits": len(P.read_jsonl(STATE / "cache_hits.jsonl")),
          "lint_rejects": len(P.read_jsonl(STATE / "lint_rejects.jsonl")),
          "iterations_done": len(scored), "iterations_consumed": len(rows),
          "accepted": sum(1 for r in rows if r.get("accept")), "iterations": rows,
          "baseline_val": base.get("val") or base.get("score"), "baseline_label": "seed, reused from REST P3",
          "best_search_score": best,
          "best_search_label": "val = train ∪ dev (147), a fit metric, selection-biased",
          "metric_calls": st.get("spent", {}).get("metric_calls"),
          "capevolve_optimizer_usd": st.get("spent", {}).get("optimizer_usd"),
          "optimizer": {"calls": t["calls"], "prompt_tokens": t["prompt_tokens"],
                        "completion_tokens": t["completion_tokens"], "cache_read": t["cache_read"],
                        "cache_write": t["cache_write"], "proxy_usd": opt_llm.proxy_usd(t), "seconds": t["seconds"]},
          "eta": f"{max(0, 6 - len(scored))} of 6 iterations left (about 45 min each in REST)"}
    P.write_json(PUSHED / "progress.json", pr)
    return pr


def search() -> int:
    proj = setup(SEARCH_ROOT, "full")
    write_diff()
    rd = latest_run_dir(SEARCH_ROOT, RUN_TS)
    extra = ["--resume"] if (rd / "state.json").exists() else []
    if extra:
        # #876: evaluation-error steps consume iterations; keep 6 SCORED iterations as the target (plan §9.7)
        rows = iteration_rows(rd)
        lost = sum(1 for r in rows if r["indecisive"])
        extra += ["--max-iterations", str(6 + lost)] if lost else []
        P.progress_log(CAND, "search", f"resume: {len(rows)} steps on record, {lost} indecisive")
    _progress(rd, "search running")
    rc = run_capevolve(proj, ts=RUN_TS, phase="search", extra=extra)
    _progress(rd, "search finished" if rc == 0 else f"search stopped (exit {rc})")
    return rc


def freeze() -> int:
    """Plan §9.7: copy candidates/<best_id>/ (all three surfaces), lint, tree-hash, check against the run's record."""
    import evaluator as E
    rd = latest_run_dir(SEARCH_ROOT, RUN_TS)
    st = P.read_json(rd / "state.json", {}) or {}
    best = st.get("best_id")
    src = rd / "candidates" / best if best else None
    inert = not best or best == "seed" or not (src and src.is_dir())
    files = {} if inert else {k: v for k, v in E.read_surfaces(src).items() if k != "memory/playbook.md"}
    if not inert:
        missing = [f for f in ("policy/instructions.txt", "tools/helpers.py", "tools/api_notes.json")
                   if f not in files]
        if missing:
            raise SystemExit(f"champion {best} lacks surfaces {missing} (REST CP-0206)")
    cdir = E.materialize(CAND, files)
    v = E.lint(cdir)
    if v:
        raise SystemExit(f"champion fails the lint: {v}")
    th = E.tree_hash(cdir)
    src_hash = E.tree_hash(src) if not inert else E.seed_hash()
    if th != src_hash:
        raise SystemExit(f"frozen tree hash {th[:12]} differs from the run's candidate {src_hash[:12]}")
    dst = STATE / "champion"
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(cdir, dst, ignore=shutil.ignore_patterns(".done"))
    art = PUSHED / "artifact"
    shutil.rmtree(art, ignore_errors=True)
    shutil.copytree(cdir, art, ignore=shutil.ignore_patterns(".done"))
    fz = {"arm": CAND, "k_se": K, "best_id": best, "inert": inert, "label": "inert" if inert else "",
          "tree_sha256": th, "run_candidate_tree_sha256": src_hash, "seed_tree_sha256": E.seed_hash(),
          "best_val": st.get("spent", {}).get("best_val"), "imp": imp_check("full", rd)}
    P.write_json(art / "FREEZE.json", fz)
    _progress(rd, "frozen" + (" (inert: nothing accepted)" if inert else ""))
    print(json.dumps({k: fz[k] for k in ("arm", "best_id", "inert", "tree_sha256", "best_val")}))
    return 0


def same(projects: dict[str, Path] | None = None) -> int:
    """A-CE2-SAME (plan §5.4, §9.6.8): the two arms' rendered capevolve.yaml and INSTRUCTIONS.md differ only in
    gate_k_se, the run dir and ts and the issue number (the latter two are not in these files at all)."""
    projects = projects or {c: P.RUN_ROOTS[c] / ".capevolve" / "project" for c in P.CANDIDATES}
    p, q = (projects[c] for c in P.CANDIDATES)
    out = {}
    import difflib
    for rel in ("capevolve.yaml", "optimizer/INSTRUCTIONS.md"):
        ta, tb = (p / rel).read_text().splitlines(), (q / rel).read_text().splitlines()
        # the arm's own project path appears in paths of the spec: normalize it before comparing
        na = [x.replace(str(P.RUN_ROOTS[P.CANDIDATES[0]]), "<RUN_ROOT>") for x in ta]
        nb = [x.replace(str(P.RUN_ROOTS[P.CANDIDATES[1]]), "<RUN_ROOT>") for x in tb]
        d = [x for x in difflib.unified_diff(na, nb, lineterm="", n=0) if x[:1] in "+-" and x[:3] not in ("+++", "---")]
        out[rel] = {"diff_lines": d, "only_gate_k_se": all(x[1:].startswith("gate_k_se:") for x in d)}
    out["ok"] = (out["capevolve.yaml"]["only_gate_k_se"] and len(out["capevolve.yaml"]["diff_lines"]) == 2
                 and not out["optimizer/INSTRUCTIONS.md"]["diff_lines"])
    dst = P.PUSHED / "ce2" / "same.json"
    P.write_json(dst, out)
    print(json.dumps(out, indent=1))
    return 0 if out["ok"] else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["setup", "imp-check", "accept", "search", "freeze", "same", "progress"])
    ap.add_argument("--arm")
    ap.add_argument("--project-root")
    ap.add_argument("--split-ids", default="full")
    ap.add_argument("--level", default="launch")
    ap.add_argument("--run-dir")
    ap.add_argument("--project")
    a = ap.parse_args()
    if a.cmd == "same":
        return same()
    select_arm(a.arm)
    if a.cmd == "setup":
        print(setup(Path(a.project_root) if a.project_root else SEARCH_ROOT, a.split_ids, force=True))
        print(write_diff())
        return 0
    if a.cmd == "imp-check":
        r = imp_check(a.level, Path(a.run_dir) if a.run_dir else None, Path(a.project) if a.project else None)
        print(json.dumps(r, indent=1))
        return 0 if r["all_ok"] else 1
    if a.cmd == "progress":
        print(json.dumps(_progress(latest_run_dir(SEARCH_ROOT, RUN_TS), a.level), indent=1))
        return 0
    return {"accept": accept, "search": search, "freeze": freeze}[a.cmd]()


if __name__ == "__main__":
    raise SystemExit(main())
