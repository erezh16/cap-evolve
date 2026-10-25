"""Writes prompt_only.json: a mock edit that sets policy/instructions.txt to the seed prompt with ONE generic sentence
inserted before its final 'My name is:' block, so the structure lint passes (A-ABL-CORE dry runs, §10.3/10.4)."""
import json
import sys
from pathlib import Path

seed = Path(sys.argv[1]).read_text(encoding="utf-8")
i = seed.rindex("My name is:")
text = seed[:i] + "Before calling an API for the first time, read its documentation.\n\n" + seed[i:]
Path(__file__).with_name("prompt_only.json").write_text(json.dumps(
    [{"file": "policy/instructions.txt", "op": "set", "text": text}], indent=1) + "\n")
