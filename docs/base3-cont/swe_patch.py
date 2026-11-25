"""Project-local deviation for swe_bench/Harbor (docs/base3.md §4): _build_agent_env() sets only
ANTHROPIC_MODEL and ANTHROPIC_DEFAULT_{SONNET,HAIKU,OPUS}_MODEL; also pin ANTHROPIC_SMALL_FAST_MODEL
and CLAUDE_CODE_SUBAGENT_MODEL to HARBOR_MODEL."""
import sys
p = sys.argv[1]; s = open(p).read()
old = '        ae["ANTHROPIC_DEFAULT_OPUS_MODEL"] = HARBOR_MODEL\n'
assert s.count(old) == 1
s = s.replace(old, old + '        ae["ANTHROPIC_SMALL_FAST_MODEL"] = HARBOR_MODEL\n        ae["CLAUDE_CODE_SUBAGENT_MODEL"] = HARBOR_MODEL\n')
open(p, "w").write(s); print("patched", p)
