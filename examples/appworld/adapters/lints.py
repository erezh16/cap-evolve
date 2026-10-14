"""Lints (plan §6.2) and the per-bullet filter (plan §8.3).

- count_tokens(text): gpt-oss encoding (tiktoken o200k_harmony).
- bullet_violations(text): rule names for one bullet: `instruction_8gram` (any 8-gram of a train or
  dev instruction), `task_id`, `supervisor_contact` (name, email or phone of a train/dev supervisor).
- memory_lint(playbook, m_cap): whole-memory check used before any rollout and at freeze.
- prompt_lint(capability_dir): the prompt renders with the three Jinja variables.
The data come from the local lint cache (AW_STATE/lint_cache.json, built by make_splits.py), so no
task file is read while the optimizer runs.
"""

from __future__ import annotations

import json
import os
import re
import sys
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import awpaths as P  # noqa: E402
from status_doc import ID_RE, ngrams8  # noqa: E402  (same tokenizer as the publishing filter)

os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(P.AW_BUILD / "tiktoken"))
BULLET_RE = re.compile(r"^\[([^\]]+)\]\s*(.*)$")


@lru_cache(maxsize=1)
def _enc():
    import tiktoken
    return tiktoken.get_encoding("o200k_harmony")


def count_tokens(text: str) -> int:
    return len(_enc().encode(text, disallowed_special=()))


@lru_cache(maxsize=1)
def _cache() -> dict:
    c = json.loads(P.LINT_CACHE.read_text())
    return {"ids": set(c["task_ids"]), "grams": set(c["instruction_8grams"]),
            "contacts": [x.lower() for x in c["contacts"]]}


def bullet_violations(text: str) -> list[str]:
    c = _cache()
    out = []
    if ngrams8(text) & c["grams"]:
        out.append("instruction_8gram")
    if any(m in c["ids"] for m in ID_RE.findall(text)):
        out.append("task_id")
    low = text.lower()
    if any(x in low for x in c["contacts"]):
        out.append("supervisor_contact")
    return out


def bullets(playbook: str) -> list[tuple[str, str]]:
    out = []
    for line in playbook.splitlines():
        m = BULLET_RE.match(line.strip())
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def sections(playbook: str) -> dict[str, int]:
    """Bullets per `## ` section, in order."""
    out, cur = {}, "general"
    for line in playbook.splitlines():
        if line.strip().startswith("##"):
            cur = line.strip()[2:].strip()
            out.setdefault(cur, 0)
        elif BULLET_RE.match(line.strip()):
            out[cur] = out.get(cur, 0) + 1
    return out


def memory_lint(playbook: str, m_cap: int) -> dict:
    """Whole-memory lint: token cap plus the per-bullet rules on every line."""
    tok = count_tokens(playbook)
    viol = {}
    for i, line in enumerate(playbook.splitlines()):
        v = bullet_violations(line)
        if v:
            viol[i] = v
    return {"ok": tok <= m_cap and not viol, "tokens": tok, "m_cap": m_cap, "chars": len(playbook),
            "bullets": len(bullets(playbook)), "violating_lines": len(viol),
            "rules": sorted({r for v in viol.values() for r in v})}


def prompt_lint(capability_dir: Path | str) -> dict:
    from jinja2 import Template
    t = (Path(capability_dir) / "policy" / "instructions.txt").read_text()
    try:
        out = Template(t).render(instruction="X", app_descriptions="[]",
                                 main_user={"first_name": "A", "last_name": "B", "email": "e", "phone_number": "p"})
        ok = "My name is: A B." in out and "Task: X" in out
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}
    return {"ok": ok}
