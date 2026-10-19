"""Add reproduce/ to every assembled run folder (docs/BACKUP_BOX.md §3a), then refresh MANIFEST.json.

    python add_reproduce.py BACKUP_DIR

Everything a repeat of the run needs that is not already in the run folder: the code as a git bundle
with the exact commits per run, the AppWorld data identity, the exact environments, every model and
the optimizer CLI as actually used (from the transcripts), the redacted inherited config, the host
facts, the orchestrating session's record, and a step-by-step REPRODUCE.md. Secrets are redacted and
the secret scan is re-run. Timing is added to BACKUP_DIR/timing.json under "reproduce".
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_backup as bb  # noqa: E402

B = Path(sys.argv[1])
AW, RUNS, REPO, HOME = bb.AW, bb.RUNS, bb.REPO, bb.HOME
ORCH_SESSION = "7eb1b74e-69fc-4fba-a5a0-43b0292e1088"   # the session that ran the evaluation

COMMITS = {
    bb.R1: {"cape_hc_s0": {"repo": "32df0f147", "note": "examples/appworld was not committed yet. The adapter, aw_agent and "
            "lints in effect are rebuilt in code/r1_adapters_reconstructed/ (v1 launch, v2 round 4+, v3 resume; v3 is "
            "byte-identical to the run's own copy). The other example files as of the first final window are in "
            "code/r1_adapters_reconstructed/scripts_at_first_window/ (rebuilt from the Write/Edit/heredoc record; in-place "
            "shell patches to them are in the session transcript). make_roots/make_splits equal commit 95433f39a; "
            "awpaths/setup_project/capevolve.yaml differ from it only by later path and secret-name configurability."}},
    bb.R2: {"altk": {"repo": "32df0f147", "note": "ALTK driver code: host/driver_code (examples/appworld/altk)."}},
    bb.R3: {"cape_hc_s1": {"repo": "95433f39a", "sandbox_wrapper": "95433f39a (allowlist: whole appworld clone)"},
            "cape_hc_s2": {"repo": "95433f39a", "sandbox_wrapper": "ec30d13ae (allowlist: appworld/src + experiments)",
                           "note": "the wrapper is read on every call, so attempt 2 ran with the ec30d13 version"},
            "final_window_2": {"repo": "ec30d13ae"}},
}


def sha_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def redact(obj):
    """Drop anything secret-looking from a settings structure."""
    if isinstance(obj, dict):
        return {k: ("<redacted>" if re.search(r"TOKEN|KEY|SECRET|HEADERS|PASSWORD", k, re.I) else redact(v))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    return obj


def redact_text(text: str) -> str:
    for s in bb.SECRETS:
        text = text.replace(s, "<redacted>")
    return text


def models_from_transcripts(run_name: str) -> dict:
    pats = {"cape_hc_s0": str(HOME / ".claude/projects/-tmp-aw-eval-runs-cape-hc-s0*/**/*.jsonl"),
            "cape_hc_s1": str(RUNS / "optimizer_transcripts/cape_hc_s1/**/*.jsonl"),
            "cape_hc_s2": str(RUNS / "optimizer_transcripts/cape_hc_s2/**/*.jsonl")}
    main, sub, ver = Counter(), Counter(), Counter()
    for f in glob.glob(pats[run_name], recursive=True):
        c = sub if "/subagents/" in f else main
        for line in open(f, errors="replace"):
            try:
                d = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            if not isinstance(d, dict):
                continue
            if d.get("version"):
                ver[d["version"]] += 1
            m = d.get("message")
            if isinstance(m, dict) and m.get("role") == "assistant" and m.get("model"):
                c[m["model"]] += 1
    return {"main_loop_model_messages": dict(main), "subagent_model_messages": dict(sub),
            "claude_code_versions": dict(ver)}


def freeze(py: str) -> str:
    return bb.sh(str(HOME / ".local/bin/uv"), "pip", "freeze", "-p", py)


def build_common(tmp: Path) -> dict:
    """Files shared by every run's reproduce/ (built once, copied into each)."""
    c = tmp / "common"
    (c / "code").mkdir(parents=True, exist_ok=True)
    (c / "env").mkdir(parents=True, exist_ok=True)
    bundle = c / "code" / "capevolve_erezh-eval1.bundle"
    bb.sh("git", "-C", str(REPO), "bundle", "create", str(bundle), "erezh-eval1")
    bb.sh("git", "-C", str(REPO), "bundle", "verify", str(bundle))
    head = bb.sh("git", "-C", str(REPO), "rev-parse", "HEAD").strip()
    commits = {}
    for c_ in ("32df0f147", "95433f39a", "ec30d13ae", "9d756bc62", head[:9]):
        full = bb.sh("git", "-C", str(REPO), "rev-parse", c_).strip()
        bb.sh("git", "-C", str(REPO), "merge-base", "--is-ancestor", full, "erezh-eval1")
        commits[c_] = {"sha": full, "date": bb.sh("git", "-C", str(REPO), "show", "-s", "--format=%cI", full).strip(),
                       "subject": bb.sh("git", "-C", str(REPO), "show", "-s", "--format=%s", full).strip()}
    (c / "env" / "requirements-venv-aw.txt").write_text(freeze(str(AW / "venv-aw/bin/python")))
    (c / "env" / "requirements-venv-altk.txt").write_text(freeze(str(REPO / ".venv/bin/python")))
    settings = json.loads((HOME / ".claude/settings.json").read_text())
    bb.jdump(redact(settings), c / "env" / "claude_settings.redacted.json")
    plug = HOME / ".claude/plugins/installed_plugins.json"
    if plug.is_file():
        bb.cp(plug, c / "env" / "claude_installed_plugins.json")
    rclone_ver = bb.sh(str(HOME / ".local/bin/rclone"), "version").splitlines()[0]
    mount_dev_null = next((l for l in open("/proc/self/mountinfo") if " /dev/null " in l), "").strip()
    host = {"os": Path("/etc/os-release").read_text().splitlines()[0], "kernel": platform.release(),
            "machine": platform.machine(),
            "container": "rootless podman (overlay root; /dev and /dev/null bound from the host)",
            "dev_null_mount": mount_dev_null.split(" - ")[1] if " - " in mount_dev_null else mount_dev_null,
            "max_user_namespaces": Path("/proc/sys/user/max_user_namespaces").read_text().strip(),
            "python_venv_aw": bb.sh(str(AW / "venv-aw/bin/python"), "-c", "import sys;print(sys.version)").strip(),
            "python_venv_altk": bb.sh(str(REPO / ".venv/bin/python"), "-c", "import sys;print(sys.version)").strip(),
            "uv": bb.sh(str(HOME / ".local/bin/uv"), "--version").strip(),
            "claude_code": bb.sh("claude", "--version").strip(),
            "node": bb.sh("node", "--version").strip(), "git": bb.sh("git", "--version").strip(),
            "git_lfs": bb.sh("git", "lfs", "version").strip(), "rclone": rclone_ver,
            "bubblewrap": bb.sh(str(HOME / ".local/bin/bwrap"), "--version").strip()
                          if (HOME / ".local/bin/bwrap").exists() else None,
            "cpus": os.cpu_count()}
    bb.jdump(host, c / "env" / "host.json")
    m = json.loads((RUNS / "manifest.json").read_text())
    data = {"appworld_data_version": "0.2.0", "download": "appworld download data --root <ROOT>   (mode: minimal)",
            "bundle_url": "https://s3.us-west-2.amazonaws.com/appworld.dev/data-0.2.0.bundle",
            "root_full_data_sha256_tree": m["data_root_full"]["sha256_tree"],
            "root_opt": m["root_opt"], "split_files": m["split_files"],
            "license": "Apache 2.0 + public redistribution must be encrypted; the data is not in this archive",
            "verify": "python examples/appworld/scripts/awpaths.py-based sha256_tree(root/data) must equal the hash above"}
    bb.jdump(data, c / "appworld_data.json")
    emb = sorted(glob.glob(str(AW / "hf/hub/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/*")))
    models_common = {
        "agent": {"id": "openai/gpt-oss-120b-a100", "provider": "IBM RITS (vLLM, OpenAI-compatible)",
                  "endpoint": "$RITS_URL/gpt-oss-120b-a100/v1", "auth": "header RITS_API_KEY: <key>",
                  "max_model_len": 40144, "litellm_route": "hosted_vllm/openai/gpt-oss-120b-a100",
                  "params": {"reasoning_effort": "medium", "temperature": 0, "max_completion_tokens": 6000,
                             "drop_reasoning_content": True, "use_cache": False, "retry_after_n_seconds": 15,
                             "max_retries": 20},
                  "agent": {"max_steps": 50, "max_output_length_chars": 60000, "max_output_tokens_per_task": 100000,
                            "ignore_multiple_calls": True, "raise_on_extra_parameters": True},
                  "seeds": {"search": "random_seed = 100 + trial index", "final_window": "5000 + trial"},
                  "limit": "the RITS backend's vLLM/model build is not visible to the client"},
        "optimizer_gateway": {"base_url_env": "ANTHROPIC_BASE_URL (IBM context-guru gateway)",
                              "auth": "ANTHROPIC_AUTH_TOKEN + ANTHROPIC_CUSTOM_HEADERS (x-context-guru-token)"},
        "embedding_altk": {"id": "sentence-transformers/all-MiniLM-L6-v2",
                           "revision": Path(emb[0]).name if emb else None},
    }
    bb.jdump(models_common, c / "models_common.json")
    return {"commits": commits, "bundle": bundle}


def orchestrator_record(dst: Path) -> int:
    """The session that ran the evaluation: transcript, subagents, tool outputs (secrets redacted)."""
    n = 0
    src_dir = HOME / ".claude/projects/-workspace-worktrees-base"
    for f in [src_dir / f"{ORCH_SESSION}.jsonl", *sorted((src_dir / ORCH_SESSION).rglob("*"))]:
        if not f.is_file():
            continue
        rel = f.relative_to(src_dir)
        out = dst / "orchestrator" / "session" / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(redact_text(f.read_text(errors="replace")))
        n += 1
    tdir = bb.CTMP / "-workspace-worktrees-base" / ORCH_SESSION
    if tdir.is_dir():
        for f in sorted(tdir.rglob("*")):
            if f.is_file() and not f.is_symlink():
                out = dst / "orchestrator" / "task_outputs" / f.relative_to(tdir)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(redact_text(f.read_text(errors="replace")))
                n += 1
    # the host's own record of the same session (stream journal + audit), secrets redacted
    dev = Path("/workspace/.devagent/agents") / ORCH_SESSION
    for name in ("journal.jsonl", "audit.jsonl", "agentd.log", "proxy.log", "state.json"):
        f = dev / name
        if f.is_file():
            out = dst / "orchestrator" / "host_agent" / name
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(redact_text(f.read_text(errors="replace")))
            n += 1
    mem = HOME / ".claude/projects/-workspace-src-cap-evolve-git/memory"
    if mem.is_dir():
        bb.cp(mem, dst / "orchestrator" / "memory")
    return n


def reproduce_md(run: str, attempts: dict, commits: dict) -> str:
    att = "\n".join(f"- `{k}`: repo `{v['repo']}`" + (f", wrapper `{v['sandbox_wrapper']}`" if v.get("sandbox_wrapper") else "")
                    + (f". {v['note']}" if v.get("note") else "") for k, v in attempts.items())
    steps_cape = """```bash
# 0. code
git clone capevolve_erezh-eval1.bundle cap-evolve && cd cap-evolve && git checkout <repo commit above>
# 1. AppWorld at 42b5bcf + the patch, both venvs (exact pins in env/requirements-*.txt)
git clone https://github.com/StonyBrookNLP/appworld $AW_EVAL/appworld && cd $AW_EVAL/appworld \\
  && git checkout 42b5bcf3cd334fee33f0c37c02070a9f5807add5 && git lfs install --local && git lfs pull \\
  && git apply <run>/env/appworld_git_diff.patch && cd -
python3.11 -m venv $AW_EVAL/venv-aw && $AW_EVAL/venv-aw/bin/pip install -r reproduce/env/requirements-venv-aw.txt
#    (or as in examples/appworld/README.md: -e appworld -e appworld/experiments[simplified] pydantic<2.13 -e core)
(cd $AW_EVAL/appworld && ../venv-aw/bin/appworld install --repo)
$AW_EVAL/venv-aw/bin/appworld download data --root $AW_EVAL/root_full      # data 0.2.0
#    check: sha256_tree(root_full/data) == reproduce/appworld_data.json
python examples/appworld/scripts/make_roots.py && python examples/appworld/scripts/make_reference.py $AW_EVAL/reference
# 2. optimizer: Claude Code 2.1.270, main model aws/claude-sonnet-5-5, CLAUDE_CODE_SUBAGENT_MODEL=aws/claude-opus-5-5,
#    the other settings in reproduce/env/claude_settings.redacted.json; the gateway variables
# 3. project + run (spec and seed are in capevolve/project/; or rebuild them:)
bash examples/appworld/scripts/setup_project.sh $AW_EVAL/runs/<name>
bash examples/appworld/scripts/check_optimizer_isolation.sh namespace       # fix runs: must PASS
bash examples/appworld/scripts/launch_cape_hc.sh $AW_EVAL/runs/<name> [--reuse-baseline <seed baseline run>]
# 4. final window (all arms together)
python examples/appworld/scripts/final_window.py freeze && python examples/appworld/scripts/final_window.py run
python examples/appworld/scripts/analyze.py
```"""
    steps_altk = """```bash
# 0–1 as for cap-evolve (code bundle, AppWorld 42b5bcf + patch, data 0.2.0, roots)
# 2. ALTK venv: Python 3.12.15, altk-evolve==1.3.0, CPU torch (exact pins: reproduce/env/requirements-venv-altk.txt)
uv venv -p 3.12 .venv && uv pip install -p .venv -r reproduce/env/requirements-venv-altk.txt
#    embedding model sentence-transformers/all-MiniLM-L6-v2 @ the revision in models.json (HF_HOME=$AW_EVAL/hf)
# 3. seed train rollouts: the cape-hc baseline's 90 official-train rollouts (rollouts/val/<id>__seed__t0.json),
#    produced by the seed capability with the same adapter; then:
bash examples/appworld/altk/run_altk.sh        # mine -> consolidate (lossless) -> render -> dose on dev
# 4. final window as for cap-evolve (the altk arm = the chosen dose, rendered for test from instructions only)
```"""
    body = steps_altk if run == bb.R2 else steps_cape
    return f"""# Reproduce: {run}

Repeating this run needs the items below. Model sampling is not deterministic, so a repeat gives the
same procedure, not the same numbers. In particular, the agent endpoint (IBM RITS) does not expose its
backend build.

## Code
{att}

All commits are in `code/capevolve_erezh-eval1.bundle` (`git bundle verify` passes; see `code_commits.json`).

## Inputs and environment
- AppWorld `42b5bcf3…` + `env/appworld_git_diff.patch`; data `0.2.0`: `appworld_data.json` (tree and split hashes).
- Python: `env/requirements-venv-aw.txt` (3.11.2), `env/requirements-venv-altk.txt` (3.12.15); `env/host.json`.
- Models and optimizer exactly as used: `models.json` (from the transcripts), `optimizer_cli.json`.
- Inherited Claude Code config: `env/claude_settings.redacted.json` (secrets removed; set your own gateway).
- Secrets needed: an agent-model key (`RITS_API_KEY` header), optimizer gateway credentials. Both are **not** in the archive.

## Steps
{body}

## How it was actually done
`orchestrator/`: the full session that ran the evaluation (every command, check and decision), with
subagent transcripts and task outputs (secrets redacted). The issue-#804 thread is in `../posts/`.
"""


def main() -> int:
    t0 = time.time()
    bb.load_secrets()
    tmp = B / "_reproduce_common"
    common = build_common(tmp)
    for run in (bb.R1, bb.R2, bb.R3):
        root = B / run
        rp = root / "reproduce"
        bb.cp(tmp / "common", rp)
        attempts = COMMITS[run]
        bb.jdump({"attempts": attempts, "commits": common["commits"]}, rp / "code_commits.json")
        models = json.loads((rp / "models_common.json").read_text())
        if run == bb.R2:
            models["optimizer"] = {"library": "altk-evolve 1.3.0 via litellm (in-process)",
                                   "model": "anthropic/aws/claude-sonnet-5-5 (EVOLVE_GUIDELINES_MODEL = EVOLVE_MODEL_NAME)",
                                   "custom_llm_provider": "anthropic",
                                   "shims": "examples/appworld/altk/altk_common.py: gateway base URL/headers on every call; "
                                            "supports_response_schema=False for this model (F5)",
                                   "settings": {"EVOLVE_GUIDELINES_MODE": "standard", "segmentation": True,
                                                "consolidation": "lossless, threshold 0.80", "retrieval_top_k": 10,
                                                "core_support": 3, "mining_parallelism": 8}}
        else:
            names = [k for k in attempts if k.startswith("cape_hc")]
            models["optimizer"] = {n: {"cli": "claude-code", **models_from_transcripts(n)} for n in names}
            models["optimizer"]["configured"] = {"optimizer_model": "aws/claude-sonnet-5-5",
                                                 "CLAUDE_CODE_SUBAGENT_MODEL": "aws/claude-opus-5-5[1m]",
                                                 "ANTHROPIC_DEFAULT_HAIKU_MODEL": "aws/claude-haiku-4-5",
                                                 "source": "user settings inherited by `claude -p`"}
            bb.jdump({"cli": "claude-code 2.1.270",
                      "argv": "claude -p <INSTRUCTIONS.md text> --permission-mode acceptEdits --allowedTools Bash "
                              "--disallowedTools Monitor --model aws/claude-sonnet-5-5 --max-turns 200 --max-budget-usd 15 "
                              "--output-format json" + ("  [via examples/appworld/sandbox/claude, + --settings <deny rules>]"
                                                        if run == bb.R3 else ""),
                      "registry_row": "skills/optimizers/registry.yaml: claude-code", "parallel_subagents": True,
                      "effort_level": "high (user settings)", "thinking": "alwaysThinkingEnabled (user settings)"},
                     rp / "optimizer_cli.json")
        (rp / "models_common.json").unlink()
        bb.jdump(models, rp / "models.json")
        (rp / "REPRODUCE.md").write_text(reproduce_md(run, attempts, common["commits"]))
        n = orchestrator_record(rp)
        if run == bb.R1:
            # R1's adapter code was never committed: rebuild it from the session (byte-checked against the run copy)
            r = subprocess.run([sys.executable, str(Path(__file__).with_name("reconstruct_r1_code.py")),
                                str(HOME / ".claude/projects/-workspace-worktrees-base" / f"{ORCH_SESSION}.jsonl"),
                                str(rp / "code" / "r1_adapters_reconstructed")], capture_output=True, text=True)
            if r.returncode != 0:
                bb.log(f"R1 code reconstruction FAILED: {r.stdout[-400:]} {r.stderr[-400:]}")
                return 5
        # consistency checks: data hash, split files, champion hashes, bundle commits
        d = json.loads((rp / "appworld_data.json").read_text())
        assert d["root_full_data_sha256_tree"] == json.loads((RUNS / "manifest.json").read_text())["data_root_full"]["sha256_tree"]
        for split, info in d["split_files"].items():
            assert info["sha256"] == sha_file(AW / "root_full/data/datasets" / f"{split}.txt"), split
        bb.log(f"{run}: reproduce/ written ({n} orchestrator files)")
    # re-scan + re-manifest every run (reproduce/ is new content)
    for run in (bb.R1, bb.R2, bb.R3):
        res = bb.scan_and_manifest(B / run)
        if res["secret_hits"]:
            bb.log(f"SECRET HITS in {run}: {res['secret_hits'][:10]}")
            return 3
        tot = sum(f["bytes"] for f in res["files"])
        bb.jdump({"run": run, "generated_utc": datetime.now(timezone.utc).isoformat(), "files": len(res["files"]),
                  "bytes": tot, "entries": res["files"]}, B / run / "MANIFEST.json")
        bb.log(f"{run}: {len(res['files']) + 1} files, {tot / 1e6:.1f} MB, 0 secret hits")
    for f in sorted(tmp.rglob("*"), reverse=True):
        f.unlink() if f.is_file() else f.rmdir()
    tmp.rmdir()
    t = json.loads((B / "timing.json").read_text())
    t["reproduce"] = {"start_utc": datetime.fromtimestamp(t0, timezone.utc).isoformat(),
                      "seconds": round(time.time() - t0, 2)}
    bb.jdump(t, B / "timing.json")
    bb.log(f"reproduce/ added in {t['reproduce']['seconds']} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
