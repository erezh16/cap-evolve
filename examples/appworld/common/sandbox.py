"""Claude Code sandbox settings for the sandboxed optimizer roles of eval REST (docs/EVAL_APPWORLD_REST.md §10):
the harnesslens Editor and the cape_improve claude-code optimizer (and its sub-agents).

  settings_file(cand, workspace) -> Path     the --settings JSON for one optimizer call
  claude_env() -> dict                       the gateway env for the CLI / Agent SDK (from ~/.claude/settings.json)

The optimizer runs in its own workspace under /tmp/aw_rest/opt/<cand>/ that holds only what the method needs
(gold-free traces, candidates, public API docs). Its shell commands run in Claude Code's sandbox
(devagent-bwrap → landrun + proot here) with enabled / failIfUnavailable / allowUnsandboxedCommands=false;
``filesystem.denyRead`` + ``permissions.deny Read(...)`` cover every place that holds gold, test data, AppWorld
itself, the evaluator, the secrets and other sessions' transcripts; the network is restricted
(DEVAGENT_BWRAP_NETWORK=restrict) with only the gateway host allowlisted. The evaluator never runs inside
the optimizer's process: drivers score candidates in separate, unsandboxed subprocesses (§8 "preferred").
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import awrest as P  # noqa: E402

# CE2 §12: /tmp/aw_ce2 is denied as a whole, so the optimizers' lint venv and tools live under AW_HOME/opt instead
OPT_ROOT = (P.AW_HOME / "opt") if P.LEDGER_PREFIX == "CE2" else P.SCRATCH / "opt"
HOME = Path.home()


def deny_paths() -> list[Path]:
    """Every location an optimizer must not read (§8): gold, test data, AppWorld, the evaluator, secrets, transcripts."""
    return [
        P.ROOT_OPT, P.ROOT_FULL, P.APPWORLD_SRC, P.AW_STATE, P.CLONES, P.REFERENCE.parent / "hf", P.VENVS,
        P.SCRATCH / "scratch",                      # AppWorld's native per-episode outputs (evaluation reports)
        P.CAPE_IMPROVE_TREE,                        # the pinned cap-evolve-improve checkout (code under test)
        Path("/tmp/plan_ref"), Path("/tmp/aw_rest_ref"),   # the plan's read-only research clones and notes
        P.REPO.parent,                              # every checkout: the evaluator, adapters, ledger, .env
        Path("/workspace/src"), Path("/workspace/inbox"), Path("/workspace/.devagent"),
        HOME / ".claude" / "projects", HOME / ".claude" / "todos", HOME / ".config" / "gh",
        Path("/tmp/data-gym-cache"),
        OPT_ROOT / "_probe",                        # A9's planted secrets outside every workspace
        CAPE_RUN / ".capevolve" / "project" / "adapters",   # cape_improve's adapter code (calls the evaluator)
    ] + _other_session_tmp()


# cape_improve's cap-evolve run dir: the optimizer's workdirs are <run>/work/<cid> inside it (decision CP-0014)
CAPE_RUN = P.AW_HOME / "cape_run"


def _ce2_deny(cand: str) -> list[Path]:
    """CE2 §12 DENY, added to deny_paths(): every symlink of AW_BUILD AND its target (the symlinks point into REST's
    build), REST's whole home, /tmp/aw_rest, every repo checkout, the other arm's project root, the arm's own
    adapters dir, and the build venvs (the lint venv lives under OPT_ROOT, not under AW_BUILD/venvs)."""
    out = [P.REST_HOME, Path("/tmp/aw_rest"), P.SCRATCH, Path("/workspace/worktrees"), P.AW_BUILD / "venvs",
           P.AW_BUILD / "root_opt", P.AW_BUILD / "root_full", P.AW_BUILD / "appworld", P.AW_BUILD / "clones",
           P.AW_BUILD / "reference"]
    out += [p.resolve() for p in list(out) if p.is_symlink()]
    for b in ("root_opt", "root_full", "appworld", "clones", "reference", "venvs/venv-aw"):
        q = P.AW_BUILD / b
        out += [q, Path(os.path.realpath(q))]
    if cand in P.CANDIDATES:
        out += [P.RUN_ROOTS[c] for c in P.CANDIDATES if c != cand]
        out += [P.RUN_ROOTS[cand] / ".capevolve" / "project" / "adapters"]
    if P.LEDGER_ID == "ABL":                # ABLATIONS §11 / R1: every earlier evaluation's home and scratch
        out += [*P.EARLIER_HOMES, Path("/tmp/aw_ce2"), Path("/tmp/aw_ce3")]
    if P.LEDGER_ID == "CE3":                # CE3 plan section 2: CE2's searches, state and artifacts are another arm's run
        out += [*P.CE2_RUN_ROOTS, P.CE2_HOME / "state", P.CE2_HOME / "opt", P.CE2_PUSHED, Path("/tmp/aw_ce2")]
    return out


def deny_paths_for(cand: str) -> list[Path]:
    """deny_paths() plus every other candidate's optimizer workspaces (§10: AW_SCRATCH except the call's own)."""
    if P.LEDGER_PREFIX == "CE2":
        seen, out = set(), []
        for p in deny_paths() + _ce2_deny(cand) + [OPT_ROOT / c for c in P.CANDIDATES if c != cand]:
            if str(p) not in seen:
                seen.add(str(p))
                out.append(p)
        return out
    return deny_paths() + [OPT_ROOT / c for c in P.CANDIDATES if c != cand] + ([CAPE_RUN] if cand != "cape_improve" else [])


def _other_session_tmp() -> list[Path]:
    """Other sessions' dirs under Claude's temp root (sub-agent transcripts). The root itself stays readable:
    the CLI keeps its per-command cwd file there."""
    root = Path(f"/tmp/claude-{os.getuid()}")
    own = (("-workspace-aw-abl-opt", "-workspace-aw-abl-arms") if P.LEDGER_ID == "ABL" else
           ("-workspace-aw-ce3-opt", "-workspace-aw-ce3-run-k") if P.LEDGER_ID == "CE3" else
           ("-workspace-aw-ce2-opt", "-workspace-aw-ce2-run-k") if P.LEDGER_PREFIX == "CE2" else ("-tmp-aw-rest-opt",))
    return [p for p in root.iterdir() if p.is_dir() and not p.name.startswith(own)] if root.exists() else []


LINT_VENV = OPT_ROOT / "venv-lint"           # jinja2 + tiktoken only: the optimizers' own lint runs here
TIKTOKEN_CACHE = OPT_ROOT / "tiktoken_cache"


def ensure_lint_venv() -> Path:
    """A small venv for the workspace lint (no AppWorld), and a tiktoken cache (the network is closed)."""
    import shutil
    import subprocess
    py = LINT_VENV / "bin" / "python"
    if not py.exists():
        uv = shutil.which("uv") or "/usr/local/bin/uv"
        subprocess.run([uv, "venv", "-q", "-p", "3.11", str(LINT_VENV)], check=True)
        subprocess.run([uv, "pip", "install", "-q", "-p", str(LINT_VENV), "jinja2", "tiktoken"], check=True)
    if not TIKTOKEN_CACHE.exists():
        TIKTOKEN_CACHE.mkdir(parents=True)
        for f in Path("/tmp/data-gym-cache").glob("*"):
            shutil.copy2(f, TIKTOKEN_CACHE / f.name)
        subprocess.run([str(py), "-c", "import tiktoken; tiktoken.get_encoding('o200k_base')"], check=True,
                       env={**os.environ, "TIKTOKEN_CACHE_DIR": str(TIKTOKEN_CACHE)})
    return py


def claude_env(extra: dict | None = None) -> dict:
    s = json.loads((HOME / ".claude" / "settings.json").read_text()).get("env", {})
    env = {k: v for k, v in os.environ.items() if k not in ("RITS_API_KET", "RITS_API_KEY")}
    for k in ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_CUSTOM_HEADERS",
              "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS"):
        if k in s:
            env[k] = s[k]
    for k in ("ANTHROPIC_MODEL", "ANTHROPIC_SMALL_FAST_MODEL", "ANTHROPIC_DEFAULT_OPUS_MODEL",
              "ANTHROPIC_DEFAULT_SONNET_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL"):
        env[k] = P.OPT_MODEL                         # every role of the optimizer is the one optimizer model (Q3)
    env["DEVAGENT_BWRAP_NETWORK"] = "restrict"
    env["TIKTOKEN_CACHE_DIR"] = str(TIKTOKEN_CACHE)
    env.pop("CLAUDECODE", None)
    env.update(extra or {})
    return env


def gateway_host() -> str:
    s = json.loads((HOME / ".claude" / "settings.json").read_text()).get("env", {})
    return urlparse(s["ANTHROPIC_BASE_URL"]).hostname or ""


def settings(workspace: Path, extra_deny: list[Path] | None = None, cand: str = "") -> dict:
    deny = [str(p) for p in deny_paths_for(cand) + list(extra_deny or [])]
    assert all(p.startswith("/") for p in deny), "every rule must be absolute (//...)"
    return {
        "permissions": {"deny": [f"Read(/{p}/**)" for p in deny] + [f"Edit(/{p}/**)" for p in deny]
                        + ["WebFetch", "WebSearch"]},
        "sandbox": {
            "enabled": True,
            "failIfUnavailable": True,
            "allowUnsandboxedCommands": False,
            "filesystem": {"denyRead": deny},
            "network": {"allowedDomains": [gateway_host()]},
        },
        "env": {"DEVAGENT_BWRAP_NETWORK": "restrict"},
    }


def settings_file(cand: str, workspace: Path, extra_deny: list[Path] | None = None) -> Path:
    workspace = Path(workspace)
    if any(str(workspace.resolve()).startswith(str(p) + "/") or str(workspace.resolve()) == str(p)
           for p in deny_paths_for(cand) + list(extra_deny or [])):
        raise ValueError("an optimizer workspace may not sit under a denied path")
    p = OPT_ROOT / f"{cand}.settings.json"
    P.atomic_write(p, json.dumps(settings(workspace, extra_deny, cand), indent=1))
    return p


PRINT_BG_WAIT_MS = str(4 * 3600 * 1000)      # eval 5 D11: print mode otherwise ends sub-agents after 600 s


def claude_call(cand: str, role: str, prompt: str, workspace: Path, *, allowed_tools: str, max_turns: int,
                system_append: str | None = None, timeout_s: int = 3 * 3600, extra_args: list[str] | None = None,
                extra_deny: list[Path] | None = None) -> dict:
    """One sandboxed ``claude -p --output-format json`` call in ``workspace`` (§10). Its usage JSON is appended to
    AW_STATE/<cand>/optimizer_usage.jsonl with the opt_llm.py fields (§5.2); the full result JSON goes to
    AW_STATE/<cand>/claude_calls/. Waits while AW_STATE/PAUSE exists (R2). Returns the parsed result JSON."""
    import shutil
    import subprocess
    import time
    P.wait_unpaused(cand)
    sf = settings_file(cand, workspace, extra_deny)
    cli = shutil.which("claude", path=os.environ.get("AW_REAL_CLAUDE_PATH")) or shutil.which("claude")
    args = [cli, "-p", prompt, "--output-format", "json", "--model", P.OPT_MODEL, "--settings", str(sf),
            "--setting-sources", "", "--allowedTools", allowed_tools, "--max-turns", str(max_turns),
            "--permission-mode", "acceptEdits"]
    if system_append:
        args += ["--append-system-prompt", system_append]
    args += list(extra_args or [])
    env = claude_env({"CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS": PRINT_BG_WAIT_MS})
    t0 = time.time()
    r = subprocess.run(args, cwd=str(workspace), env=env, capture_output=True, text=True, timeout=timeout_s)
    secs = round(time.time() - t0, 2)
    try:
        d = json.loads(r.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        d = {"is_error": True, "result": None, "stderr": r.stderr[-1500:], "returncode": r.returncode}
    log_cli_usage(cand, role, d, secs)
    out = P.AW_STATE / cand / "claude_calls"
    out.mkdir(parents=True, exist_ok=True)
    P.atomic_write(out / f"{P.utcnow().replace(':', '')}_{role}.json", json.dumps(d))
    return d


def cli_tokens(d: dict) -> dict:
    """Token counts of one CLI result. `modelUsage` sums every model call of the session (sub-agents included);
    the top-level `usage` covers only part of it (CP-0327), so modelUsage is used whenever present."""
    mu = d.get("modelUsage") or {}
    if mu:
        g = lambda k: sum(int(v.get(k) or 0) for v in mu.values())  # noqa: E731
        inp, out, cr, cw = g("inputTokens"), g("outputTokens"), g("cacheReadInputTokens"), g("cacheCreationInputTokens")
    else:
        u = d.get("usage") or {}
        inp, out = int(u.get("input_tokens") or 0), int(u.get("output_tokens") or 0)
        cr, cw = int(u.get("cache_read_input_tokens") or 0), int(u.get("cache_creation_input_tokens") or 0)
    return {"model": ",".join(mu) or P.OPT_MODEL, "prompt_tokens": inp + cw, "completion_tokens": out,
            "cache_read": cr, "cache_write": cw}


def log_cli_usage(cand: str, role: str, d: dict, seconds: float) -> None:
    """One usage line per CLI result JSON, same fields as opt_llm.py, plus total_cost_usd (CLI-reported)."""
    P.append_jsonl(P.AW_STATE / cand / "optimizer_usage.jsonl", {
        "t": P.utcnow(), "seconds": seconds, "role": role, **cli_tokens(d),
        "error": (d.get("subtype") if d.get("is_error") else None), "finish_reason": d.get("subtype"),
        "total_cost_usd": d.get("total_cost_usd"), "num_turns": d.get("num_turns"), "source": "claude-cli"})
