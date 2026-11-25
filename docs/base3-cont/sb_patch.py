"""Project-local deviation for skillsbench (docs/base3.md §3 'Agent model'): BenchFlow 0.6.4 sets only
ANTHROPIC_MODEL (to its proxy alias) for Claude Code. Pin every other Claude Code model slot to the same
alias via --agent-env so no call can fall back to a default Claude model."""
import sys
p = sys.argv[1]; s = open(p).read()
old = '    env["OPENAI_BASE_URL"] = os.environ.get("OPENAI_BASE_URL", base.rstrip("/") + "/v1")\n    return env\n'
assert s.count(old) == 1
new = old.replace("    return env\n",
'    # base3: every Claude Code model slot -> BenchFlow\'s LiteLLM alias for MODEL (safe_model_alias).\n'
'    import re as _re\n'
'    _alias = "benchflow-" + _re.sub(r"[^a-zA-Z0-9._-]+", "-", MODEL).strip("-").replace("--", "-")\n'
'    for _k in ("ANTHROPIC_SMALL_FAST_MODEL", "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL",\n'
'               "ANTHROPIC_DEFAULT_HAIKU_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL"):\n'
'        env[_k] = _alias\n'
'    return env\n')
s = s.replace(old, new); open(p, "w").write(s); print("patched", p)
