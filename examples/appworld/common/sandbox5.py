"""Claude Code sandbox settings for the two agentic optimizers of eval 5 (docs/EVAL_APPWORLD_5.md §8).

  settings_file(cand, workspace) -> Path     the --settings JSON for one optimizer call
  claude_env() -> dict                       the gateway env for the CLI / Agent SDK (from ~/.claude/settings.json)

The optimizer runs in its own workspace under /tmp/aw5_opt/<cand>/ that holds only what the method needs
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
import aw5 as P  # noqa: E402

OPT_ROOT = Path("/tmp/aw5_opt")
HOME = Path.home()


def deny_paths() -> list[Path]:
    """Every location an optimizer must not read (§8): gold, test data, AppWorld, the evaluator, secrets, transcripts."""
    return [
        P.ROOT_OPT, P.ROOT_FULL, P.APPWORLD_SRC, P.AW_STATE, P.CLONES, P.REFERENCE.parent / "hf", P.VENVS,
        P.SCRATCH,                                  # AppWorld's native per-episode outputs (evaluation reports)
        P.REPO.parent,                              # every checkout: the evaluator, adapters, ledger, .env
        Path("/workspace/src"), Path("/workspace/inbox"), Path("/workspace/.devagent"),
        HOME / ".claude" / "projects", HOME / ".claude" / "todos", HOME / ".config" / "gh",
        Path("/tmp/ace_ex"), Path("/tmp/data-gym-cache"),
        OPT_ROOT / "_probe",                        # A9's planted secrets outside every workspace
    ] + _other_session_tmp()


def _other_session_tmp() -> list[Path]:
    """Other sessions' dirs under Claude's temp root (sub-agent transcripts). The root itself stays readable:
    the CLI keeps its per-command cwd file there."""
    root = Path(f"/tmp/claude-{os.getuid()}")
    return [p for p in root.iterdir() if p.is_dir() and not p.name.startswith("-tmp-aw5-opt")] if root.exists() else []


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
        env[k] = P.OPT_MODEL                         # every role of the optimizer is the one optimizer model (D1)
    env["DEVAGENT_BWRAP_NETWORK"] = "restrict"
    env["TIKTOKEN_CACHE_DIR"] = str(TIKTOKEN_CACHE)
    env.pop("CLAUDECODE", None)
    env.update(extra or {})
    return env


def gateway_host() -> str:
    s = json.loads((HOME / ".claude" / "settings.json").read_text()).get("env", {})
    return urlparse(s["ANTHROPIC_BASE_URL"]).hostname or ""


def settings(workspace: Path, extra_deny: list[Path] | None = None) -> dict:
    deny = [str(p) for p in deny_paths() + list(extra_deny or [])]
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
    if any(str(workspace.resolve()).startswith(str(p)) for p in deny_paths()):
        raise ValueError("an optimizer workspace may not sit under a denied path")
    p = OPT_ROOT / f"{cand}.settings.json"
    P.atomic_write(p, json.dumps(settings(workspace, extra_deny), indent=1))
    return p
