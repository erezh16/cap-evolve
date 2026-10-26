"""Driver of the five cap-evolve ablation arms (docs/ABLATIONS.md §9, §10.1, §10.3 to §10.6), from CE2's run_ce2.py.
Source abl/env.sh first.

  python -I run_abl.py setup --arm A [--project-root DIR] [--split-ids dev4]   # scaffold the arm's project
  python -I run_abl.py imp-check --arm A [--level launch|full] [--run-dir RUN]  # A-ABL-CORE items 1-7 + switch check
  python -I run_abl.py accept --arm A [--mock-edit FILE]   # cap-evolve check, gate unit check, 1-iteration mock dry run
  python -I run_abl.py same               # A-ABL-SAME: each arm's rendered spec / INSTRUCTIONS / env vs abl_ref
  python -I run_abl.py search --arm A     # launch_abl.sh: the counted run (or its resume)
  python -I run_abl.py freeze --arm A     # champion -> AW_STATE/<arm>/champion + pushed artifact (all surfaces)

Every arm is cap-evolve main 75b3bcd (venv-abl, CAPEVOLVE_SKILLS_DIR = abl-main/skills, the PATH shim
``sandbox_cc/claude``) and differs from abl_ref ONLY in its row of ARM_CONFIG (rule Q4): capabilities,
protected_paths, the instructions file, AW_ABL_FEEDBACK and AW_ABL_TOOLS_LINT. The project adapter is
``abl/adapter.py`` (the shared evaluator + the feedback filter).
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
sys.path[:0] = [str(HERE), str(EX / "scripts"), str(EX / "common")]
import awrest as P  # noqa: E402

if P.LEDGER_ID != "ABL":
    raise SystemExit("run_abl.py: source examples/appworld/abl/env.sh first (AW_PROFILE=abl)")
PIN = P.CAPE_TREE
PIN_COMMIT = P.CAPE_COMMIT
SKILLS = PIN / "skills"
VENV_CAPE = P.VENVS / "venv-abl"
CAPE_PY = VENV_CAPE / "bin" / "python"
CAPE_BIN = VENV_CAPE / "bin" / "cap-evolve"
# set by select_arm(): the arm, its K, its state dir, its counted run's project root (NOT under AW_STATE: the
# optimizer's workdir is <run dir>/work/<cid>, and AW_STATE is denied to it, §12), its accept root and run ts
CAND = K = STATE = SEARCH_ROOT = ACCEPT_ROOT = RUN_TS = PUSHED = None

# §10: the ONLY per-arm differences (rule Q4, A-ABL-SAME). protected_paths: D13 seals memory/* in every arm.
ARM_CONFIG = {
    "abl_ref":        {"capabilities": "[system-prompt, tools]", "protected": '[default, "memory/*"]',
                       "feedback": "full", "tools_lint": False},
    "abl_prompt":     {"capabilities": "[system-prompt]", "protected": '[default, "memory/*", "tools/*"]',
                       "feedback": "full", "tools_lint": False},
    "abl_tools":      {"capabilities": "[tools]", "protected": '[default, "memory/*", "policy/*"]',
                       "feedback": "full", "tools_lint": True},
    "abl_notrace":    {"capabilities": "[system-prompt, tools]", "protected": '[default, "memory/*"]',
                       "feedback": "eval_only", "tools_lint": False},
    "abl_tracescore": {"capabilities": "[system-prompt, tools]", "protected": '[default, "memory/*"]',
                       "feedback": "trace_score", "tools_lint": False},
}


def arm_switches(arm: str) -> dict:
    """The arm's launcher variables (§9.2 step 3): AW_ABL_FEEDBACK always, AW_ABL_TOOLS_LINT=1 only for abl_tools."""
    c = ARM_CONFIG[arm]
    return {"AW_ABL_FEEDBACK": c["feedback"], **({"AW_ABL_TOOLS_LINT": "1"} if c["tools_lint"] else {})}


def kfmt(k: float) -> str:
    """K as written in the spec and the reports: 1 and 2 stay "1" and "2" (CE2), 0.2 stays "0.2" (CE3). Never int()."""
    return f"{k:g}"


def select_arm(arm: str) -> None:
    global CAND, K, STATE, SEARCH_ROOT, ACCEPT_ROOT, RUN_TS, PUSHED
    if arm not in ARM_CONFIG:
        raise SystemExit(f"--arm must be one of {tuple(ARM_CONFIG)} (abl_cc has its own driver, abl/cc/)")
    CAND, K = arm, float(P.K_SE[arm])
    STATE = P.cand_state(arm)
    SEARCH_ROOT = P.RUN_ROOTS[arm]
    ACCEPT_ROOT = STATE / "accept"              # throwaway dry-run projects (not counted)
    RUN_TS = P.RUN_TS[arm]
    PUSHED = P.PUSHED / arm
    os.environ["AW_CAPE_ARM"] = arm


ABL_PUSHED = P.PUSHED / "abl"


def diff_out() -> Path:
    return ABL_PUSHED / f"instructions_{CAND}.diff"


def rendered_instructions() -> Path:
    """The arm's rendered INSTRUCTIONS (lint command filled). In AW_STATE, which the optimizer's sandbox denies; the
    harness (unsandboxed) reads it and writes work/<cid>/INSTRUCTIONS.md."""
    return P.AW_STATE / "abl" / f"INSTRUCTIONS.{CAND}.md"
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
    """The environment of every cap-evolve command (launch_abl.sh sets the same)."""
    env = P.setup_env(dict(os.environ))
    for k in ("RITS_API_KET", "RITS_API_KEY"):
        env.pop(k, None)
    for k in [k for k in env if k.startswith(("CAPEVOLVE_", "AW_ABL_"))]:   # no inherited switch (§9.2 step 5)
        env.pop(k)
    env.update({"CAPEVOLVE_SKILLS_DIR": str(SKILLS), "AW_CAPE_PHASE": phase, "AW_EXAMPLE": str(EX), "AW_CAPE_ARM": CAND,
                "APPWORLD_ROOT": str(P.ROOT_OPT), "AW_KEY_ENV": "RITS_API_KET",
                "PATH": f"{HERE / 'sandbox_cc'}:{VENV_CAPE / 'bin'}:{env.get('PATH', '')}", **arm_switches(CAND)})
    env.pop("CLAUDECODE", None)
    return env


# ---------------------------------------------------------------- setup

def lint_cmd_parts() -> dict:
    """The lint the optimizer runs inside its sandbox: the small lint venv (jinja2 + tiktoken, no AppWorld) on a
    copy of lints.py and of the lint cache staged next to the project's reference files (not under AW_STATE)."""
    import sandbox as SB
    py = SB.ensure_lint_venv()
    tools = SB.OPT_ROOT / "lint"           # identical for every arm (rule Q4); not under a denied path
    tools.mkdir(parents=True, exist_ok=True)
    shutil.copy2(EX / "adapters" / "lints.py", tools / "lints.py")
    shutil.copy2(P.LINT_CACHE, tools / "lint_cache.json")
    return {"AW_LINT_PY": f"TIKTOKEN_CACHE_DIR={SB.TIKTOKEN_CACHE} {py} -I", "AW_LINTS": str(tools / "lints.py"),
            "AW_LINT_CACHE": str(tools / "lint_cache.json")}


def render_instructions(dst: Path) -> str:
    import instructions
    text = instructions.render(CAND)
    for k, v in lint_cmd_parts().items():
        text = text.replace("{" + k + "}", v)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")
    return text


def write_diff() -> Path:
    """§9.4 step 4: diff -u pinned template vs the arm's facts-inserted template (lint placeholders unfilled)."""
    import instructions
    out = diff_out()
    out.parent.mkdir(parents=True, exist_ok=True)
    P.atomic_write(out, instructions.udiff(PINNED_TEMPLATE.read_text(encoding="utf-8"), instructions.render(CAND),
                                           "pinned:templates/project/optimizer/INSTRUCTIONS.md", f"INSTRUCTIONS.{CAND}.md"))
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
    instr = rendered_instructions() if split_ids == "full" else proj / "optimizer" / "INSTRUCTIONS.md"
    render_instructions(instr)
    if instr != proj / "optimizer" / "INSTRUCTIONS.md":
        (proj / "optimizer").mkdir(parents=True, exist_ok=True)
        (proj / "optimizer" / "INSTRUCTIONS.md").write_text(instr.read_text(encoding="utf-8"), encoding="utf-8")
    cfg = ARM_CONFIG[CAND]
    spec = ((HERE / "capevolve.yaml").read_text().replace("@INSTRUCTIONS@", str(instr))
            .replace("@REFERENCE@", str(proj / "reference")).replace("@K_SE@", kfmt(K))
            .replace("@CAPABILITIES@", cfg["capabilities"]).replace("@PROTECTED@", cfg["protected"]))
    if "@" in "".join(x.split("#")[0] for x in spec.splitlines()):
        raise SystemExit("setup: an unfilled @...@ placeholder is left in the spec")
    (proj / "capevolve.yaml").write_text(spec)
    (proj / "PROJECT.md").write_text(
        f"# {CAND}: AppWorld (official splits), gpt-oss-120b on RITS, cap-evolve main @ {P.CAPE_COMMIT[:7]}, "
        "hill-climb --focus all\n\n"
        f"Plan: docs/ABLATIONS.md §9, §10 ({P.METHOD_NAMES[CAND]}). Resolved inputs:\n"
        f"- capabilities: {cfg['capabilities']}; protected_paths: {cfg['protected']} (seed: stock AppWorld ReAct prompt "
        "@ 42b5bcf, empty helpers, no notes)\n"
        f"- proposer feedback: AW_ABL_FEEDBACK={cfg['feedback']}; tools-only smuggling lint: "
        f"{'on' if cfg['tools_lint'] else 'off'}\n"
        "- target: openai/gpt-oss-120b-a100 on RITS, reasoning medium, temperature 0\n"
        f"- optimizer: claude-code, {P.OPT_MODEL}, sandboxed by examples/appworld/abl/sandbox_cc/claude; "
        f"instructions: {instr} (main's template + the arm's AppWorld facts section)\n"
        f"- data: adapter tasks(); split_ids.json train = val = {len(ids)} ids, test = []\n"
        f"- rollouts: through the shared evaluator (cache, shared seed baseline P3, global slots, PAUSE, B = {P.BUDGET_ROLLOUTS})\n"
        f"- gate: paired, k = {kfmt(K)} (gate_k_se, explicit); 1 trial; 6 iterations; max_metric_calls 1029; "
        "no optimizer USD or token cap (D12); 200 turns per session\n"
        "- objective score = reward (single objective; no objectives: block)\n")
    return proj


# ---------------------------------------------------------------- IMP checks (A-ABL-CORE items 1-7)

def _imp_launch(proj: Path | None) -> dict:
    """IMP checks 1, 2, 3 (spec level) and the arm's switch check. launch_abl.sh re-runs these before every run / resume."""
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
        cfg = ARM_CONFIG[CAND]
        caps = re.search(r"^capabilities:\s*(.+)$", spec, re.M)
        prot = re.search(r"^protected_paths:\s*(\[[^\]]*\])", spec, re.M)
        out["switch_spec"] = {"ok": bool(caps and prot) and caps.group(1).split("#")[0].strip() == cfg["capabilities"]
                              and prot.group(1) == cfg["protected"],
                              "capabilities": caps and caps.group(1).split("#")[0].strip(), "protected": prot and prot.group(1)}
    want = arm_switches(CAND)
    have = {k: os.environ.get(k) for k in ("AW_ABL_FEEDBACK", "AW_ABL_TOOLS_LINT")}
    out["switch_env"] = {"ok": all(have[k] == want.get(k) for k in have), "env": have, "expected": want,
                         "note": "the launcher's environment (os.environ of this check) must carry exactly the arm's switches"}
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
    out["4_effective_k_se"] = {"ok": len(ks) == 1 and float(ks[0]) == K, "hill_climb_cmdlines": len(hc),
                               "k_se_values": ks, "expected": K,
                               "gate_events_mentioning_k_se": len(gates)}
    works = sorted((run_dir / "work").glob("*/INSTRUCTIONS.md"))
    inst = []
    for w in works:
        t = w.read_text(encoding="utf-8")
        inst.append({"cid": w.parent.name, "has": {s: (s in t) for s in REQUIRED_STRINGS},
                     "forbidden": [s for s in FORBIDDEN_STRINGS if s in t] + sorted(set(UNFILLED_RE.findall(t)))})
    diff = diff_out().read_text() if diff_out().exists() else ""
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
    # §9.6.6: a capability's guidance exists ONLY where the arm's capabilities put it, and equals the pin there
    caps = {c.strip() for c in ARM_CONFIG[CAND]["capabilities"].strip("[]").split(",")}
    want = {"tools": "sha_match" if "tools" in caps else "missing",
            "system-prompt": "sha_match" if "system-prompt" in caps else "missing", "diagnose": "head_match"}
    out["6_guidance"] = {"ok": bool(g) and all(all(r.get(k) == v for k, v in want.items()) for r in g), "detail": g,
                         "expected": want, "pinned_sha256": {k: sh256(v) for k, v in GUIDANCE.items()}}
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
    """`cap-evolve run` via launch_abl.sh, with a sampler that records the hill-climb command line (IMP 4, 7)."""
    log = log or (P.PROGRESS / f"{CAND}.out")
    env = cape_env(phase)
    env["AW_CAPE_TS"] = ts
    global _RUN_NAME
    _RUN_NAME = f"run_{ts}"
    # the cap-evolve project's adapter wiring is evaluator code: hidden from the optimizer too (§10 DENY)
    env["AW_CAPE_EXTRA_DENY"] = str(proj / "adapters")
    p = subprocess.Popen(["bash", str(HERE / "launch_abl.sh"), CAND, str(proj), ts, *(extra or [])], env=env,
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
    """A-CE2 item 4 / A-CE3 item 4 with the PINNED gate.py (decide, mode paired). CE2: a delta vector with mean =
    1.5·SE is accepted at k_se 1 and rejected at 2; 2.5·SE is accepted by both; 0.7·SE is rejected by both.
    CE3: 0.3·SE is accepted at k_se 0.2 and rejected at 1; 0.1·SE is rejected at 0.2."""
    ce3 = True                                     # ABLATIONS 9.6.4: the K = 0.2 cases
    facs, ks = ((0.1, 0.3), (0.2, 1.0)) if ce3 else ((0.7, 1.5, 2.5), (1.0, 2.0))
    code = r"""
import json, math, sys
from cap_evolve import gate
facs, ks = json.loads(sys.argv[1]), json.loads(sys.argv[2])
n = 147
e = [0.1 if i % 2 else -0.1 for i in range(n - 1)] + [0.0]   # zero-mean spread; a shift leaves the SE unchanged
mu = sum(e) / n; e = [x - mu for x in e]
se0 = math.sqrt(sum(x * x for x in e) / (n - 1) / n)
out = {"gate_file": gate.__file__, "cases": {}}
for f in facs:
    d = [x + f * se0 for x in e]
    m = sum(d) / n; se = math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1) / n)
    r = {"mean_over_se": round(m / se, 6)}
    for k in ks:
        g = gate.decide(0.0, m, mode="paired", k_se=k, paired_deltas=d)
        r[f"accept_k{k:g}"] = g.accept
        r[f"reason_k{k:g}"] = g.reason
    out["cases"][f"{f:g}"] = r
print(json.dumps(out))
"""
    r = subprocess.run([str(CAPE_PY), "-c", code, json.dumps(facs), json.dumps(ks)], capture_output=True, text=True,
                       env=cape_env("accept"))
    d = json.loads(r.stdout.strip().splitlines()[-1])
    c = d["cases"]
    if ce3:
        d["ok"] = (c["0.3"]["accept_k0.2"] is True and c["0.3"]["accept_k1"] is False
                   and c["0.1"]["accept_k0.2"] is False and d["gate_file"].startswith(str(PIN / "core")))
    else:
        d["ok"] = (c["1.5"]["accept_k1"] is True and c["1.5"]["accept_k2"] is False
                   and c["2.5"]["accept_k1"] is True and c["2.5"]["accept_k2"] is True
                   and c["0.7"]["accept_k1"] is False and c["0.7"]["accept_k2"] is False
                   and d["gate_file"].startswith(str(PIN / "core")))
    return d


def accept(mock_edit: str | None = None) -> int:
    """A-ABL-CORE items 3-7 for the arm (the mock dry run on 4 dev ids is not counted; phase accept)."""
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
    edits = (json.loads(Path(mock_edit).read_text()) if mock_edit else
             [{"file": "tools/api_notes.json", "op": "set",
               "text": json.dumps({"api_docs": "Call show_api_doc before calling an API for the first time."})}])
    P.write_json(proj.parent.parent / "mock_script.json", {"edits": edits})
    env_ts = f"dry_{root.name}"
    # passed as AW_MOCK_SCRIPT: the launcher strips inherited CAPEVOLVE_* (§9.2 step 5) and re-exports it only in the
    # accept phase, so no counted search can ever see a mock script
    os.environ["AW_MOCK_SCRIPT"] = str(proj.parent.parent / "mock_script.json")
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
    evs = _run_events(rd)
    # a step whose optimizer session failed (e.g. a gateway 429) scored the parent unchanged: a LOST iteration, not
    # a real proposal (ABL-0180); it is reported as such and re-run on resume
    opt_failed = {e.get("candidate") for e in evs if (e.get("kind") or e.get("event")) == "optimizer_error"}
    for e in evs:
        kind = e.get("kind") or e.get("event")
        # step_indecisive = an evaluation error, a tampered surface (a voided step, §10.3/10.4) or an invalid
        # capability: an iteration consumed with no rollout
        if kind not in ("step", "step_indecisive", "tamper", "capability_invalid"):
            continue
        reason = str(e.get("reason") or "")
        m = _GATE_RE.search(reason)
        row = {"candidate": e.get("candidate"), "accept": bool(e.get("accept")) and kind == "step", "val": e.get("val"),
               "parent_val": e.get("parent_val"), "indecisive": kind != "step" or bool(e.get("indecisive")),
               "kind": kind}
        if kind == "step" and e.get("candidate") in opt_failed:
            row.update(indecisive=True, accept=False, kind="optimizer_failed")
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
          "baseline_val": base.get("val") or base.get("score"), "baseline_label": "seed, shared P3 baseline",
          "best_search_score": best,
          "best_search_label": "val = train ∪ dev (147), a fit metric, selection-biased",
          "metric_calls": st.get("spent", {}).get("metric_calls"),
          "capevolve_optimizer_usd": st.get("spent", {}).get("optimizer_usd"),
          "optimizer": {"calls": t["calls"], "prompt_tokens": t["prompt_tokens"],
                        "completion_tokens": t["completion_tokens"], "cache_read": t["cache_read"],
                        "cache_write": t["cache_write"], "proxy_usd": opt_llm.proxy_usd(t), "seconds": t["seconds"]},
          "voided_steps": sum(1 for r in rows if r.get("kind") in ("tamper", "capability_invalid")),
          "feedback_mode": ARM_CONFIG[CAND]["feedback"],
          "eta": f"{max(0, 6 - len(scored))} of 6 iterations left (CE2/CE3: about 45 to 70 min each)"}
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
        # 6 SCORED iterations stay the target; every lost step also used 147 metric calls (cached parent re-score)
        extra += ["--max-iterations", str(6 + lost), "--max-metric-calls", str(1029 + 147 * lost)] if lost else []
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
    fz = {"arm": CAND, "k_se": K, "switches": arm_switches(CAND), "best_id": best, "inert": inert, "label": "inert" if inert else "",
          "tree_sha256": th, "run_candidate_tree_sha256": src_hash, "seed_tree_sha256": E.seed_hash(),
          "best_val": st.get("spent", {}).get("best_val"), "imp": imp_check("full", rd)}
    P.write_json(art / "FREEZE.json", fz)
    _progress(rd, "frozen" + (" (inert: nothing accepted)" if inert else ""))
    print(json.dumps({k: fz[k] for k in ("arm", "best_id", "inert", "tree_sha256", "best_val")}))
    return 0


# A-ABL-SAME (rule Q4, §5.4): what each arm may differ in from abl_ref, besides run dir, run ts and its own paths
SAME_ALLOWED_SPEC = {"abl_ref": (), "abl_prompt": ("capabilities:", "protected_paths:"),
                     "abl_tools": ("capabilities:", "protected_paths:"), "abl_notrace": (), "abl_tracescore": ()}
SAME_ALLOWED_ENV = {"abl_ref": (), "abl_prompt": (), "abl_tools": ("AW_ABL_TOOLS_LINT",),
                    "abl_notrace": ("AW_ABL_FEEDBACK",), "abl_tracescore": ("AW_ABL_FEEDBACK",)}
_ARM_ENV_KEYS = ("AW_CAPE_ARM", "AW_EXPERIMENT", "AW_CAPE_EXTRA_DENY", "AW_CAPE_TS")   # the arm's own name and paths


def _norm(text: str, arm: str) -> list[str]:
    root = str(P.RUN_ROOTS[arm])
    return [x.replace(root, "<RUN_ROOT>").replace(f"INSTRUCTIONS.{arm}.md", "INSTRUCTIONS.<ARM>.md")
            .replace(f"({P.METHOD_NAMES[arm]})", "(<ARM NAME>)").replace(arm, "<ARM>")
            for x in text.splitlines()]


def _launch_env(arm: str) -> dict:
    global CAND
    keep = CAND
    select_arm(arm)
    env = {k: v for k, v in cape_env().items() if k.startswith(("AW_", "CAPEVOLVE_", "APPWORLD_"))}
    select_arm(keep) if keep else None
    return env


def same(projects: dict[str, Path] | None = None) -> int:
    """A-ABL-SAME (§5.4): every cap-evolve arm's rendered capevolve.yaml, PROJECT.md-free spec, INSTRUCTIONS.md and
    launcher environment, compared with abl_ref's after normalizing the arm's own name and paths, differ only in the
    arm's allowed rows. The INSTRUCTIONS differences must be exactly instructions_ref_vs_<arm>.diff (the facts
    sentences). The sandbox settings are compared by sandbox.same_settings (the arm's own deny entry and the
    other-arm deny list are the only allowed differences)."""
    import difflib
    import instructions
    ref = "abl_ref"
    rp = P.RUN_ROOTS[ref] / ".capevolve" / "project"
    out = {"reference": ref, "arms": {}}
    ref_env = _launch_env(ref)
    for arm in ARM_CONFIG:
        if arm == ref:
            continue
        q = P.RUN_ROOTS[arm] / ".capevolve" / "project"
        res = {}
        ta, tb = _norm((rp / "capevolve.yaml").read_text(), ref), _norm((q / "capevolve.yaml").read_text(), arm)
        d = [x for x in difflib.unified_diff(ta, tb, lineterm="", n=0) if x[:1] in "+-" and x[:3] not in ("+++", "---")]
        res["capevolve.yaml"] = {"diff_lines": d, "ok": all(x[1:].startswith(SAME_ALLOWED_SPEC[arm]) for x in d)
                                 and bool(d) == bool(SAME_ALLOWED_SPEC[arm])}
        ia = (P.AW_STATE / "abl" / f"INSTRUCTIONS.{ref}.md").read_text()
        ib = (P.AW_STATE / "abl" / f"INSTRUCTIONS.{arm}.md").read_text()
        expect = instructions.udiff(instructions.render(ref), instructions.render(arm), "a", "b")
        got = instructions.udiff(ia, ib, "a", "b")
        res["INSTRUCTIONS.md"] = {"ok": got == expect and bool(got), "changed_lines": sum(
            1 for x in got.splitlines() if x[:1] in "+-" and x[:3] not in ("+++", "---"))}
        env = _launch_env(arm)
        keys = sorted((set(env) | set(ref_env)) - set(_ARM_ENV_KEYS))
        diff_keys = [k for k in keys if env.get(k) != ref_env.get(k)]
        res["launcher_env"] = {"differing_keys": diff_keys, "ok": set(diff_keys) == set(SAME_ALLOWED_ENV[arm])}
        res["ok"] = all(v["ok"] for v in res.values())
        out["arms"][arm] = res
    out["ok"] = all(v["ok"] for v in out["arms"].values())
    dst = ABL_PUSHED / "same.json"
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
    ap.add_argument("--mock-edit")
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
    if a.cmd == "accept":
        return accept(a.mock_edit)
    return {"search": search, "freeze": freeze}[a.cmd]()


if __name__ == "__main__":
    raise SystemExit(main())
