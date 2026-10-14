"""A1: OPT_MODEL answers through ace_llm.py; one Reflector and one Curator call on a toy message list
return parseable JSON (plan §11). Uses no task data. Calls go to AW_STATE/acceptance/a1_calls.jsonl.
Prints a JSON summary (no response text).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "scripts"))
import awpaths as P  # noqa: E402

os.environ["ACE_CALLS_LOG"] = str(P.AW_STATE / "acceptance" / "a1_calls.jsonl")
sys.path.insert(0, str(EX / "ace"))
sys.path.insert(0, str(EX))
import ace_llm  # noqa: E402
ace_llm.CALLS_LOG = Path(os.environ["ACE_CALLS_LOG"])
import run_ace  # noqa: E402
from ace.vendor.playbook import extract_json_from_text  # noqa: E402

TOY = [
    {"role": "user", "content": "Task: tell me how many notes I have in the SimpleNote app.\n\n"},
    {"role": "assistant", "content": "```python\nprint(apis.api_docs.show_api_descriptions(app_name='simple_note'))\n```\n\n"},
    {"role": "user", "content": "Output:\n```\n[{\"name\": \"search_notes\", \"description\": \"Search notes, paginated.\"}]\n```\n\n"},
    {"role": "assistant", "content": "```python\nnotes = apis.simple_note.search_notes(access_token=token)\napis.supervisor.complete_task(answer=len(notes))\n```\n\n"},
    {"role": "user", "content": "Output:\n```\nExecution successful.\n```\n\n"},
]


def main() -> int:
    pb = run_ace.INITIAL_PLAYBOOK
    r = ace_llm.generate([{"role": "user", "content": run_ace.render_reflector(pb, TOY)}], role="reflector", step="A1")
    refl_json = extract_json_from_text(r["content"])
    c = ace_llm.generate([{"role": "user", "content": run_ace.render_curator(pb, r["content"], TOY[0]["content"], TOY)}],
                         role="curator", step="A1")
    ops, skipped, err = run_ace.validate_curator(c["content"])
    res = {"model": ace_llm.OPT_MODEL, "reflector": {"json": isinstance(refl_json, dict),
           "keys": sorted(refl_json) if isinstance(refl_json, dict) else None, "usage": r["usage"],
           "finish_reason": r["finish_reason"],
           "empty_fields": [k for k, v in (refl_json or {}).items() if isinstance(v, str) and not v.strip()]},
           "curator": {"valid": ops is not None, "n_ops": len(ops or []), "off_whitelist": len(skipped),
                       "error": err, "usage": c["usage"], "finish_reason": c["finish_reason"]},
           "response_format_sent": False, "tools_sent": False}
    res["ok"] = bool(res["reflector"]["json"] and res["curator"]["valid"] and not res["reflector"]["empty_fields"])
    print(json.dumps(res))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
