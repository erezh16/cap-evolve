"""Vendored verbatim from HarnessLens 369a5c8:harnesslens/evolution/discovery.py (see VENDORED.md)."""
from __future__ import annotations

from typing import Any
from typing import Mapping


TASK_EXPLORER_SYSTEM = """
You are the task-definition explorer for a harness optimization run.
Classify the supplied TRAIN tasks mainly by user goal. Use at most ten primary categories.
You may use a few auxiliary angles only when they clarify important behavioral differences.
Do not infer expected actions, grader logic, hidden answers, or harness modifications.
Every task must appear exactly once in a primary category.
If a task contains multiple goals, choose the dominant user-facing outcome as
the primary category. Do not list the same task in any second category; record
secondary interpretations only in auxiliary_angles or notes.

Return:
{"categories":[{"id":"short-id","name":"name","purpose":"one precise sentence","task_ids":["..."],"auxiliary_angles":["..."]}],"notes":["..."]}
""".strip()


HARNESS_QUERY_SYSTEM = """
You are the harness-query explorer for a harness optimization run.
Query the supplied architecture probe, documentation evidence, runtime observations, and candidate
workspace contract to determine what this exact harness can actually customize in this experiment.
The supplied surface hypotheses are leads, not conclusions: account for each one, and add a newly
discovered native harness surface when the evidence supports it. Do not analyze task trajectories
or propose domain-specific behavior. Connected MCP tools and parameters are environment facts that
the controller attaches after your response; do not discover, assess, or return MCP editable points.

A surface is currently modifiable only when the candidate can implement the exact mechanism using
captured files under `home/` or `project/`, the fixed runtime will load it, and cited evidence
supports the claim. A CLI-only switch, legacy manifest field, disabled feature, overwritten setting,
or unselected integration is conditional or unavailable, not modifiable. Distinguish documented,
materialized, and request-observed evidence; do not upgrade one into another. The controller owns
only harness identity, experimental safety constraints, and exact MCP server/tool/parameter bindings.
When an exact request-observed workspace edit contract agrees with the candidate runtime loader,
treat that surface as established modifiable unless a fixed override explicitly makes it ineffective;
disabled automatic discovery does not negate an explicit candidate-loading path.

For a modifiable surface, provide its visibility and use, a concrete workspace `edit_contract`, the
runtime conditions required for it to work, evidence references, and regression risk. Put every
supplied hypothesis that is not currently writable and effective in `unavailable_modules` with a
reason. Each edit contract must choose one preferred scope
and one path relative to that scope; do not combine alternatives or repeat `home/` or `project/` in
the path. Before classifying, compare every hypothesis with every fixed override and disabled
behavior in the candidate workspace contract. Produce a compact base profile for downstream roles.

Return:
{"harness":"...","harness_version":"...","summary":"...","modifiable_modules":[{"id":"stable-id","status":"modifiable","evidence_level":"runtime_observed|materialized|documented","visibility":"...","use":"...","edit_contract":{"scope":"project","path":"relative/path-or-pattern","mechanism":"file|config|extension"},"runtime_constraints":["..."],"risks":"...","evidence_refs":["exact-ref"]}],"unavailable_modules":[{"id":"stable-id","status":"conditional|unsupported|forbidden","reason":"...","runtime_constraints":["..."],"evidence_refs":["exact-ref"]}],"base_profile":{"shared_rules":["..."],"role_isolation":"..."}}
""".strip()


def validate_task_explorer(
    output: Mapping[str, Any], task_ids: tuple[str, ...]
) -> None:
    categories = output.get("categories")
    if not isinstance(categories, list) or not 1 <= len(categories) <= 10:
        raise ValueError("task explorer must return between one and ten categories")
    seen: list[str] = []
    category_ids: set[str] = set()
    for category in categories:
        if not isinstance(category, Mapping):
            raise ValueError("task category must be an object")
        category_id = str(category.get("id") or "").strip()
        if not category_id or category_id in category_ids:
            raise ValueError("task category IDs must be unique and nonempty")
        if (
            not str(category.get("name") or "").strip()
            or not str(category.get("purpose") or "").strip()
        ):
            raise ValueError("task category requires name and purpose")
        members = category.get("task_ids")
        if not isinstance(members, list) or not members:
            raise ValueError("task category must contain task IDs")
        category_ids.add(category_id)
        seen.extend(str(item) for item in members)
    if len(seen) != len(set(seen)):
        raise ValueError("each TRAIN task must have exactly one primary category")
    if set(seen) != set(task_ids):
        raise ValueError(
            f"task explorer coverage must exactly equal the {len(task_ids)} TRAIN tasks"
        )
