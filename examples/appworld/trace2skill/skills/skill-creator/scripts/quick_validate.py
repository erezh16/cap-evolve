#!/usr/bin/env python3
"""Skill format checker for the trace2skill arm (docs/EVAL_APPWORLD_REST.md §9.3).

Trace2Skill calls ``skills/skill-creator/scripts/quick_validate.py <skill_dir>`` (a cwd-relative path,
``skill_evolver/skill_evolving_agent.py:59``) but the script is not in the repository at 3d0b52a. This
replacement checks exactly the rules the vendored verification prompt states, plus the AppWorld rules:
  - SKILL.md exists and starts with a YAML frontmatter block delimited by '---' lines;
  - fields: name and description required; only name, description, license, allowed-tools, metadata,
    compatibility allowed; name kebab-case [a-z0-9-]+ (no leading/trailing/double hyphen), <= 64 chars;
    description a plain one-line string without '<' or '>', <= 1024 chars; compatibility <= 500 chars;
  - SKILL.md under 500 lines;
  - no references/ directory and no other file (the agent under test cannot open files);
  - the body (after the frontmatter) is <= T2S_MAX_BODY_TOKENS tokens (o200k_base) and <= 30,000 chars,
    unless T2S_VALIDATE_SIZE=0 (used only around the condensation pass, whose size is checked by the driver).
Exit 0 and print "Skill is valid!" when valid; otherwise exit 1 and print one line per problem.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ALLOWED = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}


def tokens(text: str) -> int:
    try:
        import tiktoken
        return len(tiktoken.get_encoding("o200k_base").encode(text))
    except Exception:  # noqa: BLE001
        return len(text) // 3


def split_frontmatter(text: str) -> tuple[dict[str, str] | None, str, list[str]]:
    errs: list[str] = []
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, text, ["SKILL.md must begin with a YAML frontmatter block delimited by '---'"]
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return None, text, ["YAML frontmatter is not closed by a '---' line"]
    fields: dict[str, str] = {}
    for ln in lines[1:end]:
        if not ln.strip() or ln.startswith((" ", "\t")):
            if ln.strip():
                errs.append("frontmatter values must be plain one-line strings (no nested or block values)")
            continue
        if ":" not in ln:
            errs.append(f"frontmatter line is not 'key: value': {ln[:60]!r}")
            continue
        k, v = ln.split(":", 1)
        fields[k.strip()] = v.strip().strip('"').strip("'")
    return fields, "\n".join(lines[end + 1:]), errs


def validate(skill_dir: Path) -> list[str]:
    errs: list[str] = []
    md = skill_dir / "SKILL.md"
    if not md.is_file():
        return ["SKILL.md not found"]
    text = md.read_text(encoding="utf-8")
    fm, body, e = split_frontmatter(text)
    errs += e
    if fm is not None:
        for k in fm:
            if k not in ALLOWED:
                errs.append(f"frontmatter key {k!r} is not allowed (allowed: {sorted(ALLOWED)})")
        name, desc = fm.get("name", ""), fm.get("description", "")
        if not name:
            errs.append("frontmatter field 'name' is required")
        elif (not re.fullmatch(r"[a-z0-9-]+", name) or name.startswith("-") or name.endswith("-")
              or "--" in name or len(name) > 64):
            errs.append("name must be kebab-case [a-z0-9-]+, no leading/trailing/double hyphen, <= 64 chars")
        if not desc:
            errs.append("frontmatter field 'description' is required")
        else:
            if desc in ("|", ">", "|-", ">-"):
                errs.append("description must be a plain string, not a YAML block scalar")
            if "<" in desc or ">" in desc:
                errs.append("description cannot contain angle brackets")
            if len(desc) > 1024:
                errs.append("description is longer than 1024 characters")
        if len(fm.get("compatibility", "")) > 500:
            errs.append("compatibility is longer than 500 characters")
    n_lines = text.count("\n") + 1
    if n_lines >= 500:
        errs.append(f"SKILL.md has {n_lines} lines; it must remain under 500 lines")
    others = [p.relative_to(skill_dir).as_posix() for p in skill_dir.rglob("*") if p.is_file() and p != md]
    if others or (skill_dir / "references").exists():
        errs.append("only SKILL.md is allowed; remove references/ and every other file "
                    f"(found: {', '.join(sorted(others)[:5]) or 'references/'}) and fold needed content into SKILL.md")
    if os.environ.get("T2S_VALIDATE_SIZE", "1") != "0":
        cap = int(os.environ.get("T2S_MAX_BODY_TOKENS", "0") or 0)
        n = tokens(body)
        if cap and n > cap:
            errs.append(f"SKILL.md body is {n} tokens; it must be at most {cap} tokens: shorten and merge guidance")
        if len(body) > 30000:
            errs.append(f"SKILL.md body is {len(body)} characters; it must be at most 30000")
    return errs


if __name__ == "__main__":
    problems = validate(Path(sys.argv[1]))
    if problems:
        print("\n".join(problems))
        raise SystemExit(1)
    print("Skill is valid!")
