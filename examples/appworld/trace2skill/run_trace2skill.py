"""The `trace2skill` arm: Trace2Skill 3d0b52a, trajectory -> skill distillation (docs/EVAL_APPWORLD_REST.md §9.3).

  venv-t2s/bin/python -I run_trace2skill.py accept   # A-trace2skill: dev ids only, phase "accept", not counted
  venv-t2s/bin/python -I run_trace2skill.py search   # analysts -> 3 evolution seeds -> packaging -> selection on train
  venv-t2s/bin/python -I run_trace2skill.py freeze   # selected playbook -> lint -> docs/..._STATE/trace2skill/artifact/

Pipeline (combined mode, `skill_evolver.run_parallel_combined_skill_evolution` with the README's reproduction
settings, driven from Python):
 1. Trajectories: the shared seed's 90 train records (P3), read through the evaluator's cache (0 counted), each
    rendered as `<prefix><task-id with _ -> ->_(SUCCEED|FAILED).md` in Trace2Skill's markdown log layout. A FAILED
    log carries an "Evaluator report: failed requirements" section (gold-free feedback tier F1) before the
    `## RESULT` block that `strip_log_metadata` removes.
 2. Single-call analysts (`analysis/run_error_analysis_llm.py` on FAILED logs, `run_success_analysis_llm.py` on
    SUCCEED logs; their prompts with AppWorld wording), parsed by the vendored `report_parsing`. The agentic analyst
    (`analysis/run_error_analysis.py`, which copies the gold file into its workspace) is NOT used (rule R1).
    The analysis runs once and is shared by the three evolution seeds, as in the README.
 3. Per evolution seed (41, 42, 43): `CombinedParallelSkillEvolver.run` (MAP batch 1, merge batch 5, <= 5 merge
    levels + forced final merge, translation on, programmatic APPLY, verification <= 3 rounds, patch pipeline json)
    on a starting skill with frontmatter and an empty body ("creation" mode; the starting agent is the seed).
    No temperature, top_p or seed is ever sent (the gateway rejects them), so the three runs differ only by the
    optimizer model's default sampling.
 4. Packaging: SKILL.md body (frontmatter stripped) -> `memory/playbook.md`; over M_cap -> the sequential evolver's
    `final_consolidation` pass (up to 2, each recorded), then the shared lint.
 5. Selection (README): each packaged playbook is scored on train (90 counted each, 270 in all) and compared with
    the seed's train score; the best strictly better one wins (tie -> shorter playbook); none better -> "inert".

Every optimizer call goes through common/opt_llm.py (`AnthropicGatewayClient`), logged per role.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EX = HERE.parent
sys.path[:0] = [str(EX / "scripts"), str(EX / "common")]
import awrest as P  # noqa: E402

P.setup_env()
import evaluator as E  # noqa: E402
import opt_llm  # noqa: E402

CAND = "trace2skill"
STATE = P.AW_STATE / CAND
VENDOR = HERE / "vendor"
PROMPTS = HERE / "prompts"
VALIDATOR = HERE / "skills" / "skill-creator" / "scripts" / "quick_validate.py"
EVOLUTION_SEEDS = (41, 42, 43)
LOG_PREFIX = "appworld_react_agent_"
TRUNC = 2000                     # §9.3: per-step output truncated to 2,000 chars
MAX_WORKERS = 8                  # MAP/REDUCE/translation threads (gateway calls); every call waits on PAUSE
MAX_TOKENS = 16000
MAX_CONDENSATIONS = 2
MEMORY_MAX_CHARS = 30000
START_SKILL = ("---\nname: appworld-agent\ndescription: Guidelines for completing AppWorld tasks by calling app "
               "APIs from the Python REPL on the supervisor's behalf.\n---\n")
# Settings of §9.3 (combined mode, README reproduction command, runner defaults), recorded in every run.
SETTINGS = {"mode": "combined", "input_mode": "records", "batch_size": 1, "merge_batch_size": 5,
            "max_merge_levels": 5, "skip_translation": False, "max_verification_rounds": 3,
            "patch_pipeline": "json", "semantic_item_marker_format": "bracket", "json_format_self_fix": True,
            "max_skill_lines": 500, "max_references": 0, "max_workers": MAX_WORKERS, "max_tokens": MAX_TOKENS,
            "temperature": None, "generation_config": None, "seed_param": None, "cache": False,
            "evolution_seeds": list(EVOLUTION_SEEDS), "analysts": "single-call (llm) error + success"}


def m_cap() -> int:
    c = E.m_cap_tokens()
    if not c:
        raise SystemExit("M_cap is not in manifest.json (acceptance A8 computes it): refusing to run trace2skill")
    return int(c)


# ---------------------------------------------------------------- vendored Trace2Skill, with our prompt copies

_loaded = False


def load_trace2skill():
    """Import the vendored modules so every prompt comes from prompts/ (AppWorld wording, M_cap filled in)."""
    global _loaded
    if not _loaded:
        sys.path.insert(0, str(VENDOR))
        # skill_evolver/__init__.py imports the evolver modules, which load their prompts at import time; a bare
        # package object lets prompt_loader be patched first, so every module binds our prompt copies.
        import types
        pkg = types.ModuleType("skill_evolver")
        pkg.__path__ = [str(VENDOR / "skill_evolver")]
        sys.modules.setdefault("skill_evolver", pkg)
        import skill_evolver.prompt_loader as PL
        cap = m_cap()
        repl = {"@@M_CAP_TOKENS@@": str(cap), "@@M_CAP_CHARS@@": str(min(MEMORY_MAX_CHARS, cap * 3))}
        orig = PL.load_prompt_template

        def load(key: str) -> str:
            p = PROMPTS / f"{key}.txt"
            if not p.is_file():
                return orig(key)
            text = p.read_text(encoding="utf-8")
            if key in PL._STRIP_FINAL_NEWLINE_KEYS and text.endswith("\n"):
                text = text[:-1]
            for a, b in repl.items():
                text = text.replace(a, b)
            return text

        PL.load_prompt_template = load          # bound by every module imported below
        import skill_evolver.skill_evolving_agent as SEA
        SEA.QUICK_VALIDATE_SCRIPT = VALIDATOR   # the code expects a cwd-relative path the repo does not ship
        _loaded = True
    import skill_evolver.skill_evolving_agent as SEA
    import skill_evolver.parallel_success_evolving_agent as PSA
    import skill_evolver.parallel_evolving_agent as PEA
    return SEA, PSA, PEA


def validator_env() -> None:
    os.environ["T2S_MAX_BODY_TOKENS"] = str(m_cap())
    os.environ.setdefault("T2S_VALIDATE_SIZE", "1")


class AnthropicGatewayClient:
    """Trace2Skill's LLMClient interface over common/opt_llm.py: `chat(messages, settings=None,
    return_reasoning=False) -> str`. ModelSettings.to_dict() always holds a temperature; it is dropped here, as is
    max_tokens (fixed at 16,000). No generation config, no seed, no disk cache."""

    def __init__(self, cand: str, roles: dict[str, str] | None = None):
        self.cand, self.roles = cand, dict(roles or {})
        self.model = P.OPT_MODEL

    def role_of(self, system: str) -> str:
        for prefix, role in self.roles.items():
            if system.startswith(prefix):
                return role
        return "other"

    def chat(self, messages, settings=None, return_reasoning: bool = False):
        msgs = [{"role": m.role, "content": m.content} for m in messages]
        system = "\n\n".join(m["content"] for m in msgs if m["role"] == "system")
        reply = opt_llm.chat([m for m in msgs if m["role"] != "system"], cand=self.cand, role=self.role_of(system),
                             system=system or None, max_tokens=MAX_TOKENS)
        return (reply, "") if return_reasoning else reply

    async def chat_async(self, messages, settings=None):
        return self.chat(messages, settings)


# ---------------------------------------------------------------- 1. trajectories

def log_id(task_id: str) -> str:
    return task_id.replace("_", "-")


def log_filename(rec: dict) -> str:
    return f"{LOG_PREFIX}{log_id(rec['task_id'])}_{'SUCCEED' if rec['reward'] == 1.0 else 'FAILED'}.md"


def render_log(rec: dict) -> str:
    """Trace2Skill's markdown chat-log layout (spreadsheet_agent/agents/base.py) for one gold-free record."""
    out = [f"# Chat History: {LOG_PREFIX.rstrip('_')}\n\n", "**Timestamp**: 2026-01-01T00:00:00\n\n", "---\n\n"]
    n = 0

    def msg(role: str, content: str) -> None:
        nonlocal n
        n += 1
        out.append(f"## [{n}] {role.upper()}\n\n{content}\n\n---\n\n")

    msg("user", rec["instruction"])
    for s in rec.get("steps") or []:
        parts = []
        if (s.get("reasoning") or "").strip():
            parts.append("Reasoning: " + s["reasoning"][:TRUNC].strip())
        if (s.get("thought") or "").strip():
            parts.append(s["thought"][:TRUNC].strip())
        parts.append("```python\n" + (s.get("code") or "")[:TRUNC] + "\n```")
        msg("assistant", "\n\n".join(parts))
        obs = (s.get("output") or "")[:TRUNC]
        fence = "```"
        while fence in obs:
            fence += "`"
        msg("user", f"Observation:\n{fence}\n{obs}\n{fence}")
    ok = rec["reward"] == 1.0
    if not ok:
        reqs = [r.strip() for r in (rec.get("failed_requirements") or []) if r and r.strip()]
        lines = ["## Evaluator report: failed requirements", ""]
        lines += [f"- {r}" for r in reqs] or ["- (no requirement text available)"]
        lines += ["", f"Requirement checks passed: {rec.get('pass_count') or 0}/{rec.get('num_tests') or 0}.",
                  f"Collateral damage (changed state the task did not ask for): "
                  f"{'yes' if rec.get('collateral_damage') else 'no'}.",
                  f"complete_task called: {'yes' if rec.get('complete_task_called') else 'no'}; "
                  f"API/execution errors: {rec.get('api_errors') or 0}; termination: {rec.get('termination')}."]
        out.append("\n".join(lines) + "\n\n---\n\n")
    out.append(f"## RESULT\n\n- Success: {ok}\n- Total Turns: {rec.get('n_steps') or 0}\n")
    return "".join(out)


def write_logs(records: list[dict], logs_dir: Path) -> dict[str, str]:
    """Write one log per record; returns {log id: task id}. Refuses ids that do not round-trip."""
    sys.path.insert(0, str(VENDOR))
    from analysis.run_error_analysis_llm import parse_log_filename
    logs_dir.mkdir(parents=True, exist_ok=True)
    back: dict[str, str] = {}
    for rec in records:
        name = log_filename(rec)
        parsed = parse_log_filename(name)
        if not parsed or parsed[0] != log_id(rec["task_id"]):
            raise RuntimeError("a log filename does not parse back to its id")
        (logs_dir / name).write_text(render_log(rec), encoding="utf-8")
        back[parsed[0]] = rec["task_id"]
    return back


# ---------------------------------------------------------------- 2. single-call analysts

def analyze(logs_dir: Path, out_dir: Path, cand: str) -> tuple[list[dict], list[dict]]:
    """The two single-call analysts over logs_dir (resumable: an existing report is not redone)."""
    sys.path.insert(0, str(VENDOR))
    from analysis.run_error_analysis_llm import find_logs, strip_log_metadata
    from analysis.run_success_analysis_llm import find_logs as find_success_logs
    from analysis.report_parsing import collect_error_records, collect_success_records
    from concurrent.futures import ThreadPoolExecutor
    jobs = []
    for kind, logs in (("error", find_logs(str(logs_dir), failed_only=True)),
                       ("success", find_success_logs(str(logs_dir), succeed_only=True))):
        system = (PROMPTS / "analysis" / f"{kind}_analysis_system_llm.txt").read_text(encoding="utf-8")
        user_t = (VENDOR / "analysis" / f"{kind}_analysis_user_llm.txt").read_text(encoding="utf-8")
        d = out_dir / kind
        d.mkdir(parents=True, exist_ok=True)
        for iid, path in logs.items():
            out = d / f"{kind}_analysis_{iid}.md"
            if not out.is_file():
                jobs.append((kind, system, user_t, path, out))

    def one(job):
        kind, system, user_t, path, out = job
        agent_log = strip_log_metadata(Path(path).read_text(encoding="utf-8", errors="replace"))
        rep = opt_llm.chat(user_t.replace("{agent_log}", agent_log), cand=cand, role=f"{kind}_analyst",
                           system=system, max_tokens=MAX_TOKENS)
        P.atomic_write(out, rep)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        list(pool.map(one, jobs))
    err, _, _ = collect_error_records(str(out_dir / "error"))
    suc = collect_success_records(str(out_dir / "success"))
    return err, suc


# ---------------------------------------------------------------- 3. evolution (one seed)

def evolve(records: list[dict], skill_dir: Path, inter: Path, cand: str) -> dict:
    SEA, PSA, PEA = load_trace2skill()
    validator_env()
    shutil.rmtree(skill_dir, ignore_errors=True)
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(START_SKILL, encoding="utf-8")
    shutil.rmtree(inter, ignore_errors=True)
    inter.mkdir(parents=True)
    client = AnthropicGatewayClient(cand)
    ev = PSA.CombinedParallelSkillEvolver(
        client=client, skill_dir=skill_dir, batch_size=SETTINGS["batch_size"],
        merge_batch_size=SETTINGS["merge_batch_size"], max_workers=MAX_WORKERS,
        max_merge_levels=SETTINGS["max_merge_levels"], max_tokens=MAX_TOKENS, verbose=False, dry_run=False,
        output_dir=inter, parse_failure_dir=inter / "parse_failures", max_skill_lines=SETTINGS["max_skill_lines"],
        max_references=SETTINGS["max_references"], max_verification_rounds=SETTINGS["max_verification_rounds"],
        skip_translation=False, patch_pipeline="json", semantic_item_marker_format="bracket",
        enable_json_format_self_fix=True)
    ev._evolver._parse_failure_dir = inter / "parse_failures"
    client.roles = {ev._map_system_prompt[:200]: "map", ev._merge_system_prompt[:200]: "merge",
                    ev._translation_system_prompt[:200]: "translation",
                    ev._verification_system_prompt[:200]: "verification"}
    payload = PSA.normalize_mixed_records(*records)
    n0 = opt_llm.totals(cand)["calls"]
    res = ev.run(payload, input_mode="records")
    valid, msg = ev._evolver.validate_skill()
    return {"map_patches": len(res.get("patches") or []), "edits": len(res.get("edits") or []),
            "changelog": [str(x)[:300] for x in res.get("changelog") or []], "valid": valid,
            "validation": msg[:500], "llm_calls": opt_llm.totals(cand)["calls"] - n0,
            "records": {"error": len(records[0]), "success": len(records[1])}}


# ---------------------------------------------------------------- 4. packaging

def split_frontmatter(text: str) -> str:
    m = re.match(r"\A---\s*\n.*?\n---\s*\n?", text, flags=re.S)
    return (text[m.end():] if m else text).strip() + "\n"


def search_ids_any_form() -> list[str]:
    ids = E.split_ids("train") + E.split_ids("dev")
    return ids + [log_id(t) for t in ids]


def package(skill_dir: Path, work: Path, cand: str) -> dict:
    """SKILL.md body -> playbook; condensation (final_consolidation) while over M_cap; then the shared lint."""
    SEA, _, _ = load_trace2skill()
    cap = m_cap()
    info = {"condensations": []}
    cur = skill_dir
    body = split_frontmatter((cur / "SKILL.md").read_text(encoding="utf-8"))
    for k in range(MAX_CONDENSATIONS):
        n = E.memory_tokens(body)
        if n <= cap and len(body) <= MEMORY_MAX_CHARS:
            break
        nxt = work / f"condensed_{k + 1}"
        shutil.rmtree(nxt, ignore_errors=True)
        nxt.mkdir(parents=True)
        shutil.copy2(cur / "SKILL.md", nxt / "SKILL.md")
        se = SEA.SkillEvolver(client=AnthropicGatewayClient(cand), skill_dir=nxt, max_tokens=MAX_TOKENS,
                              verbose=False, prompt_variant="generic", parse_failure_dir=work / "parse_failures",
                              max_references=0)
        se.system_prompt = se.system_prompt.replace("refine a spreadsheet\nskill folder",
                                                    "refine an AppWorld\nskill folder")
        se.client.roles = {se.system_prompt[:200]: "condense"}
        os.environ["T2S_VALIDATE_SIZE"] = "0"     # rollback only on format errors; the size is checked here
        try:
            step = se.run_consolidation_pass([])
        finally:
            os.environ["T2S_VALIDATE_SIZE"] = "1"
        new_body = split_frontmatter((nxt / "SKILL.md").read_text(encoding="utf-8"))
        info["condensations"].append({"before_tokens": n, "after_tokens": E.memory_tokens(new_body),
                                      "before_chars": len(body), "after_chars": len(new_body),
                                      "rolled_back": any("ROLLED BACK" in c for c in step.changelog_entries)})
        cur, body = nxt, new_body
    if body.strip() == "":
        body = ""
    hits = [t for t in search_ids_any_form() if t and t in body]
    cdir = E.materialize(cand, {"memory/playbook.md": body})
    v = E.lint(cdir)
    if hits:
        v.append(f"memory/playbook.md: contains {len(hits)} train/dev task id(s)")
    info.update({"tokens": E.memory_tokens(body), "chars": len(body), "lint": v, "cdir": str(cdir),
                 "tree": E.tree_hash(cdir)[:12], "is_seed": E.tree_hash(cdir) == E.seed_hash(),
                 "dropped_reference_files": len([p for p in (skill_dir / "references").glob("*")])
                 if (skill_dir / "references").exists() else 0})
    return info


# ---------------------------------------------------------------- shared helpers

def wait_memory() -> None:
    while True:
        m = P.memstate()
        if m.get("state") == "OK" and not m.get("stale"):
            return
        P.progress_log(CAND, "-", f"waiting: memguard {m.get('state')} stale={m.get('stale')}")
        time.sleep(30)


def seed_train_records(cand: str) -> list[dict]:
    if not E.SEED_DONE.exists():
        raise SystemExit("the shared seed baseline (P3) is not done: trace2skill needs its 90 train records")
    seed_dir = E.materialize(cand, {})
    recs = E.evaluate(cand, seed_dir, E.split_ids("train"), phase="search", tag="seed_trajectories")
    if not all(r.get("cache_hit") for r in recs):
        raise RuntimeError("seed trajectories were not all served from the cache")
    return recs


def write_progress(stage: str, **kw) -> None:
    u = opt_llm.totals(CAND)
    pr = {"stage": stage, "counted_rollouts": E.counted(CAND), "cache_hits": E.cache_hits(CAND),
          "optimizer": {**u, "proxy_usd": opt_llm.proxy_usd(u)}, **kw}
    P.write_json(P.PUSHED / CAND / "progress.json", pr)


def milestone(label: str, prose: str, nxt: str, done: str, post_key: str | None = None) -> None:
    import status_doc as S
    u = opt_llm.totals(CAND)
    S.append("result", "P4", f"{CAND} {label}", prose, done_through=done, next_unit=nxt,
             extra={"candidate": CAND, "counts": {CAND: {"counted_rollouts": E.counted(CAND),
                                                         "cache_hits": E.cache_hits(CAND)}},
                    "spend": {CAND: {"in": u["prompt_tokens"], "out": u["completion_tokens"],
                                     "usd": opt_llm.proxy_usd(u)}}},
             artifacts=[f"STATE/{CAND}/progress.json"], subject=f"{CAND} {label}")
    if post_key:
        import post
        post.post(CAND, post_key, f"{P.METHOD_NAMES[CAND]}: {label}", prose)


# ---------------------------------------------------------------- search

def search() -> int:
    os.chdir(STATE.mkdir(parents=True, exist_ok=True) or STATE)
    st = P.read_json(STATE / "search_state.json", {}) or {}
    st.setdefault("settings", SETTINGS)
    P.write_json(STATE / "search_state.json", st)
    records = seed_train_records(CAND)
    seed_score = sum(r["reward"] for r in records) / len(records)
    write_progress("search: analysts", seed_train_tgc=round(seed_score, 4))
    if not st.get("started"):
        st["started"] = P.utcnow()
        P.write_json(STATE / "search_state.json", st)
        milestone("search started", f"Trace2Skill search started: analysts over the shared seed's 90 train "
                  f"trajectories, then 3 evolution seeds and selection on train (270 counted rollouts).",
                  f"{CAND}/search", f"{CAND}/search-start", post_key="m_search_start")
    back = write_logs(records, STATE / "logs")
    wait_memory()
    err, suc = analyze(STATE / "logs", STATE / "analysis", CAND)
    st["analysis"] = {"logs": len(back), "error_records": len(err), "success_records": len(suc),
                      "failed_logs": sum(1 for r in records if r["reward"] != 1.0)}
    P.write_json(STATE / "search_state.json", st)
    for k in EVOLUTION_SEEDS:
        d = STATE / "seeds" / str(k)
        if (d / "DONE.json").exists():
            continue
        wait_memory()
        write_progress(f"search: evolution seed {k}", seed_train_tgc=round(seed_score, 4))
        info = evolve((err, suc), d / "skill", d / "intermediates", CAND)
        info["package"] = package(d / "skill", d, CAND)
        P.write_json(d / "DONE.json", info)
        milestone(f"evolution seed {k}", f"Trace2Skill evolution seed {k} done: {info['map_patches']} MAP patches, "
                  f"{info['edits']} file edits, {info['llm_calls']} optimizer calls; playbook "
                  f"{info['package']['tokens']} tokens, {len(info['package']['condensations'])} condensation(s), "
                  f"lint {'clean' if not info['package']['lint'] else 'REJECT'}.", f"{CAND}/search",
                  f"{CAND}/evolution/{k}")
    # 5. selection on train (README): each playbook vs the seed's train score
    sel = {"seed_train_tgc": seed_score, "per_seed": {}}
    for k in EVOLUTION_SEEDS:
        info = P.read_json(STATE / "seeds" / str(k) / "DONE.json")
        pk = info["package"]
        recs = E.evaluate(CAND, Path(pk["cdir"]), E.split_ids("train"), phase="search", tag=f"select/{k}")
        tgc = sum(r["reward"] for r in recs) / len(recs)
        sel["per_seed"][str(k)] = {"train_tgc": tgc, "chars": pk["chars"], "tokens": pk["tokens"],
                                   "lint_reject": bool(pk["lint"]), "cdir": pk["cdir"]}
        write_progress(f"search: selection ({len(sel['per_seed'])}/3 scored)", seed_train_tgc=round(seed_score, 4),
                       best_search_score=round(max(x["train_tgc"] for x in sel["per_seed"].values()), 4),
                       best_search_label="train TGC (90), selection-biased")
    better = [(v["train_tgc"], -v["chars"], k) for k, v in sel["per_seed"].items()
              if v["train_tgc"] > seed_score and not v["lint_reject"]]
    sel["selected"] = max(better)[2] if better else None
    sel["inert"] = not better
    P.write_json(STATE / "selection.json", sel)
    best = max(v["train_tgc"] for v in sel["per_seed"].values())
    write_progress("search done; waiting for freeze", seed_train_tgc=round(seed_score, 4),
                   best_search_score=round(best, 4), best_search_label="train TGC (90), selection-biased",
                   selected_seed=sel["selected"], inert=sel["inert"],
                   per_seed_train_tgc={k: round(v["train_tgc"], 4) for k, v in sel["per_seed"].items()})
    milestone("search finished", f"Trace2Skill search finished: {E.counted(CAND)} counted rollouts; seed train TGC "
              f"{seed_score:.3f}; evolved playbooks' train TGC "
              + ", ".join(f"seed {k}: {v['train_tgc']:.3f}" for k, v in sel["per_seed"].items())
              + (f"; selected evolution seed {sel['selected']}." if sel["selected"] else "; none beats the seed: inert.")
              + " Train scores are selection-biased.", f"{CAND}/freeze", f"{CAND}/search", post_key="m_search_end")
    return 0


# ---------------------------------------------------------------- freeze

def freeze() -> int:
    sel = P.read_json(STATE / "selection.json")
    if sel is None:
        raise SystemExit("no selection.json: run search first")
    cdir = E.materialize(CAND, {}) if sel["inert"] else Path(sel["per_seed"][sel["selected"]]["cdir"])
    v = E.lint(cdir)
    if v:
        raise SystemExit(f"selected candidate fails the lint: {v}")
    art = P.PUSHED / CAND / "artifact"
    shutil.rmtree(art, ignore_errors=True)
    for rel, text in E.read_surfaces(cdir).items():
        (art / rel).parent.mkdir(parents=True, exist_ok=True)
        (art / rel).write_text(text)
    (art / "memory").mkdir(parents=True, exist_ok=True)
    pb = cdir / "memory" / "playbook.md"
    P.write_json(art / "FREEZE.json", {
        "candidate": CAND, "label": "inert" if sel["inert"] else "", "selected_evolution_seed": sel["selected"],
        "seed_train_tgc": sel["seed_train_tgc"],
        "per_seed_train_tgc": {k: x["train_tgc"] for k, x in sel["per_seed"].items()},
        "playbook_tokens": E.memory_tokens(pb.read_text()) if pb.is_file() else 0,
        "playbook_chars": len(pb.read_text()) if pb.is_file() else 0,
        "counted_rollouts": E.counted(CAND), "tree_sha256": E.tree_hash(cdir)})
    print(json.dumps(P.read_json(art / "FREEZE.json")))
    return 0


# ---------------------------------------------------------------- accept (A-trace2skill)

def accept() -> int:
    """A-trace2skill on dev ids, phase "accept" (not counted), optimizer usage under trace2skill_accept."""
    import urllib.request
    acand = "trace2skill_accept"
    work = P.AW_STATE / acand / "run"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    os.chdir(work)
    bodies: list[dict] = []
    real = urllib.request.urlopen

    def hook(req, *a, **kw):                     # request hook: record each gateway body's keys
        try:
            bodies.append({"keys": sorted(json.loads(req.data).keys()),
                           "header": any(k.lower() == "x-context-guru-token" for k in req.headers)
                           or any(k.lower() == "x-context-guru-token" for k in getattr(req, "unredirected_hdrs", {}))})
        except Exception:  # noqa: BLE001
            pass
        return real(req, *a, **kw)

    urllib.request.urlopen = hook
    out: dict = {}
    dev = E.split_ids("dev")
    seed_dir = E.materialize(acand, {})
    wait_memory()
    recs = E.evaluate(acand, seed_dir, dev[:4], phase="accept", tag="t2s_accept")
    if len({r["reward"] for r in recs}) < 2:
        recs += E.evaluate(acand, seed_dir, dev[4:5], phase="accept", tag="t2s_accept")
    out["episodes"] = {"records": len(recs), "passed": sum(1 for r in recs if r["reward"] == 1.0),
                       "infra": sum(1 for r in recs if r["error"])}
    # (1) converter round trip on 3 dev records
    back = write_logs(recs[:3], work / "rt")
    sys.path.insert(0, str(VENDOR))
    from analysis.run_error_analysis_llm import parse_log_filename, strip_log_metadata
    rt = all(back.get(parse_log_filename(log_filename(r))[0]) == r["task_id"] for r in recs[:3])
    stripped_ok = all("## RESULT" not in strip_log_metadata(render_log(r)) and "# Chat History"
                      not in strip_log_metadata(render_log(r))[:20] for r in recs)
    failed_keeps_report = all("Evaluator report: failed requirements" in strip_log_metadata(render_log(r))
                              for r in recs if r["reward"] != 1.0)
    out["A1_converter_roundtrip"] = rt and stripped_ok and failed_keeps_report
    # (2) one error and one success analysis call; (3) the 4-record MAP -> REDUCE -> APPLY -> VERIFY dry run
    back = write_logs(recs[:5], work / "logs")
    err, suc = analyze(work / "logs", work / "analysis", acand)
    out["A2_analysts"] = {"error_records": len(err), "success_records": len(suc),
                          "error_items": sum(len(r["items"]) for r in err),
                          "success_items": sum(len(r["items"]) for r in suc),
                          "pass": bool(err and suc and all(r["items"] for r in err + suc))}
    mixed = (err[:2], suc[:2]) if len(err) >= 2 and len(suc) >= 2 else (err[:4 - min(2, len(suc))], suc[:2])
    info = evolve(mixed, work / "skill", work / "intermediates", acand)
    body = split_frontmatter((work / "skill" / "SKILL.md").read_text())
    out["A3_dry_run"] = {**{k: info[k] for k in ("map_patches", "edits", "valid", "llm_calls", "records")},
                         "body_tokens": E.memory_tokens(body), "pass": bool(info["valid"] and body.strip())}
    # (4) packaging: lint-clean playbook <= M_cap, placed before 'My name is:'; one real dev episode with it
    pk = package(work / "skill", work, acand)
    inj = subprocess.run([str(P.VENV_PY), "-I", str(HERE / "accept_injection.py"), pk["cdir"]],
                         capture_output=True, text=True, env=P.setup_env(dict(os.environ)))
    try:
        inj_res = json.loads(inj.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        inj_res = {"ok": False, "stderr": inj.stderr[-500:]}
    wait_memory()
    ep = E.evaluate(acand, Path(pk["cdir"]), dev[5:6], phase="accept", tag="t2s_accept_playbook")[0]
    out["A4_packaging"] = {"tokens": pk["tokens"], "m_cap": m_cap(), "lint": pk["lint"],
                           "condensations": len(pk["condensations"]), "injection": inj_res,
                           "episode": {"lint_reject": ep["lint_reject"], "error": bool(ep["error"]),
                                       "n_steps": ep["n_steps"], "termination": ep["termination"]},
                           "pass": bool(not pk["lint"] and pk["tokens"] <= m_cap() and inj_res.get("ok")
                                        and not ep["lint_reject"] and not ep["error"])}
    # (5) no request carries temperature
    out["A5_no_temperature"] = {"requests": len(bodies),
                                "with_temperature": sum(1 for b in bodies if "temperature" in b["keys"]),
                                "with_top_p_top_k_seed": sum(1 for b in bodies
                                                             if {"top_p", "top_k", "seed"} & set(b["keys"])),
                                "header_sent": all(b["header"] for b in bodies),
                                "body_keys": sorted({k for b in bodies for k in b["keys"]})}
    out["A5_no_temperature"]["pass"] = bool(bodies) and out["A5_no_temperature"]["with_temperature"] == 0 \
        and out["A5_no_temperature"]["with_top_p_top_k_seed"] == 0 and out["A5_no_temperature"]["header_sent"]
    u = opt_llm.totals(acand)
    out["optimizer"] = {**u, "proxy_usd": opt_llm.proxy_usd(u)}
    out["PASS"] = all(out[k] if isinstance(out[k], bool) else out[k].get("pass", True)
                      for k in ("A1_converter_roundtrip", "A2_analysts", "A3_dry_run", "A4_packaging",
                                "A5_no_temperature"))
    P.write_json(P.AW_STATE / acand / "accept_result.json", out)
    print(json.dumps(out, indent=1))
    return 0 if out["PASS"] else 1


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd not in ("accept", "search", "freeze"):
        raise SystemExit(__doc__)
    raise SystemExit({"accept": accept, "search": search, "freeze": freeze}[cmd]())
