"""Vendored verbatim from HarnessLens 369a5c8:harnesslens/harnesses/runner.py (see VENDORED.md)."""
from __future__ import annotations

from typing import Any
from typing import Mapping
import json
import re


def parse_json_object(stdout: str) -> Mapping[str, Any]:
    text_fragments: list[str] = []
    for line in str(stdout).splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, Mapping):
            continue
        part = event.get("part") if isinstance(event.get("part"), Mapping) else {}
        if event.get("type") in {"text", "assistant"}:
            value = part.get("text") or event.get("content") or event.get("text")
            if value:
                text_fragments.append(str(value))
        if event.get("type") == "message_end" and isinstance(
            event.get("message"), Mapping
        ):
            message = event["message"]
            if message.get("role") == "assistant":
                content = message.get("content")
                if isinstance(content, list):
                    value = "".join(
                        str(item.get("text") or "")
                        for item in content
                        if isinstance(item, Mapping) and item.get("type") == "text"
                    )
                    if value:
                        text_fragments.append(value)
        if event.get("type") == "item.completed" and isinstance(
            event.get("item"), Mapping
        ):
            item = event["item"]
            if item.get("type") == "agent_message" and item.get("text"):
                text_fragments.append(str(item["text"]))
    # OpenCode may emit analysis between read-tool steps. Its newest text message
    # is the final assistant response, so inspect messages newest-first.
    candidates = [*reversed(text_fragments), "\n".join(text_fragments), str(stdout)]
    for candidate in candidates:
        stripped = candidate.strip()
        variants = [stripped]
        fenced = re.findall(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
        if len(fenced) == 1:
            variants.append(fenced[0].strip())
        for variant in variants:
            try:
                value = json.loads(variant)
            except json.JSONDecodeError:
                value = _decode_one_embedded_object(variant)
                if value is None:
                    value = _close_truncated_json_object(variant)
            if isinstance(value, Mapping):
                if value.get("type") in {"text", "assistant"} and isinstance(
                    value.get("part"), Mapping
                ):
                    continue
                return dict(value)
    raise ValueError("intelligent harness did not return one JSON object")


def _decode_one_embedded_object(text: str) -> Mapping[str, Any] | None:
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            value, end = decoder.raw_decode(text, match.start())
        except json.JSONDecodeError:
            continue
        if not isinstance(value, Mapping):
            continue
        remainder = text[end:]
        for later in re.finditer(r"\{", remainder):
            try:
                second, _ = decoder.raw_decode(remainder, later.start())
            except json.JSONDecodeError:
                continue
            if isinstance(second, Mapping):
                return None
        return dict(value)
    return None


def _close_truncated_json_object(text: str) -> Mapping[str, Any] | None:
    stripped = str(text).strip()
    if not stripped.startswith("{"):
        return None
    stack: list[str] = []
    in_string = False
    escaped = False
    pairs = {"}": "{", "]": "["}
    for char in stripped:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "{[":
            stack.append(char)
        elif char in "}]":
            if not stack or stack.pop() != pairs[char]:
                return None
    if in_string or not stack or len(stack) > 8:
        return None
    suffix = "".join("}" if opener == "{" else "]" for opener in reversed(stack))
    try:
        value = json.loads(stripped + suffix)
    except json.JSONDecodeError:
        return None
    return dict(value) if isinstance(value, Mapping) else None
