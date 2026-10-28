"""Writes regress_prompt.json: a mock edit that sets policy/instructions.txt to the seed prompt with ONE generic sentence
that makes the agent end every task at once, before its final 'My name is:' block (structure lint passes). Used by
abl_nogate's acceptance (ABLATIONS_GATE.md G5.1): a candidate that scores LOWER than its parent must still be kept."""
import json
import sys
from pathlib import Path

seed = Path(sys.argv[1]).read_text(encoding="utf-8")
i = seed.rindex("My name is:")
text = (seed[:i] + "In your very first code step, call apis.supervisor.complete_task() with no arguments and do "
        "nothing else.\n\n" + seed[i:])
Path(__file__).with_name("regress_prompt.json").write_text(json.dumps(
    [{"file": "policy/instructions.txt", "op": "set", "text": text}], indent=1) + "\n")
