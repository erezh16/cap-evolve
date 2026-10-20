"""Vendored verbatim from HarnessLens 369a5c8:harnesslens/evolution/experience.py (see VENDORED.md)."""
from __future__ import annotations

from typing import Any
from typing import Mapping
from typing import Sequence
from difflib import get_close_matches
import hashlib
import json
import re


EXPERIENCE_SYSTEM = """
You are the Experience module. Read every task bundle listed in the input index before
writing the result. You summarize model-visible TRAIN behavior; you do not design or modify
the harness and you do not infer hidden expected actions, evaluator logic, or reward causes.
Trial packets include compact channel usage recorded by the runtime. Use it only to distinguish
availability from invocation; never infer loading from behavior.

Produce two collections of natural-language passages:

1. reusable: primarily successful behavior. Preserve concrete context, ordered actions,
tool/parameter details, observed results, confirmation and branching logic. Compare all available
trials of the same task. Merge only clearly equivalent routes by adding evidence references;
when meaningful success branches differ, keep separate passages. Do not replace procedures
with abstract principles.

2. needs_adjustment: primarily repeated or concrete failure behavior. Merge failures only
when both their observable trigger and problematic behavior match. Use successful contrasts
to narrow the boundary. A single failed trajectory is only a bounded candidate observation,
not a proven reward cause. When every comparison trial fails, label the pattern as unresolved
and state the observed trigger, actions, results, omissions, and differences without declaring
a cause or fix.
Include both the failing and successful evidence references whenever the text uses a contrast.
For a failure-only unresolved passage, distinguish an observed missing action after an explicit
request or confirmation from a proposed correction that no trajectory demonstrates.

Follow the supplied evaluation_contract. Under authoritative outcomes, pass/fail decides task
completion: failed trials may explain useful local actions but cannot alone support a reusable
successful procedure. Under behavioral outcomes, pass/fail is weak whole-trajectory metadata and
an explicit visible completion disagreement must be retained. Preserve who proposed and accepted
each branch; do not rewrite a user-selected fallback as an assistant-imposed action.
Needs_adjustment is optional: if no visible user request, confirmation, policy condition, or tool
contract remains unmet, emit no adjustment passage for that branch. Do not turn the absence of an
untried workaround into a gap, and do not treat wording differences as errors when the selected
item, parameters, and observed result are the same.
Under an authoritative evaluation contract, every failed evidence reference must still appear in
needs_adjustment. When no visible cause or demonstrated correction exists, retain a bounded
unresolved passage instead of silently accounting for the failure only in coverage.
When reusing a local segment from a failed trajectory, report the exact observed tool result;
do not turn API acceptance into a general policy or correctness claim.
Whenever a passage compares trajectories, include every compared trajectory in evidence_refs.

Return:
{
  "reusable":[{"id":"stable-slug","text":"detailed natural language","evidence_refs":["ev_..."]}],
  "needs_adjustment":[{"id":"stable-slug","text":"bounded natural language","evidence_refs":["ev_..."]}],
  "coverage":{"task_ids":["..."],"evidence_refs":["ev_..."]}
}
""".strip()


EXPERIENCE_SYNTHESIS_SYSTEM = """
You are the final pass of the Experience module. The input contains experience drafts made
from every baseline trajectory. Analyze every draft, not a sample.

For reusable experience, preserve concrete successful branches and their tool/parameter,
confirmation, order, and observed-result details. Merge only genuinely equivalent routes;
do not turn different successful procedures into abstract principles. For needs_adjustment,
prioritize common observable error patterns and merge only when trigger and problematic
behavior match. Use successful contrasts to narrow conditions. A single failure remains a
bounded observation, never a hidden evaluator or reward-cause claim. Do not propose an
unobserved correction. If no successful contrast supports a correction, retain an unresolved
candidate pattern for Analyzer diagnosis instead of declaring a cause or fix.

Return only justified merge operations. Unmentioned source passages remain unchanged, so do
not list them. Use discard_source_keys only for passages that explicitly contain no visible
success/failure experience, rely on a hypothetical untried workaround, or contradict their own
observed behavior. Never merge merely to shorten the result. A reusable merge requires genuinely
equivalent procedures; a needs_adjustment merge requires the same observable trigger and problem
behavior. Each source_key may occur in at most one merge or discard list.

In particular, discard a needs_adjustment passage when its own evidence says the selected item,
parameters, and tool result satisfy the user's visible request and the only difference is wording;
when it says the assistant appropriately transferred because visible constraints made the request
unavailable and identifies no unmet visible obligation; or when its only proposed gap is a
hypothetical workaround that no trajectory, policy, or tool contract establishes. A reward label
or incomplete task alone is not a reason to retain an adjustment passage.

Return exactly:
{"reusable_merges":[{"source_keys":["...","..."],"id":"stable-slug","text":"detailed merged natural language"}],"needs_adjustment_merges":[{"source_keys":["...","..."],"id":"stable-slug","text":"bounded merged natural language"}],"discard_source_keys":["..."]}
""".strip()


MAX_TASKS_PER_EXPERIENCE_JOB = 5


COMPARISON_SYSTEM = """
You are the rollout-comparison mode of the Experience module. Read every supplied task bundle.
For each task, compare its reference trial set with its candidate trial set;
do not align trial numbers mechanically. Describe only visible behavior, tool calls/results, and
reward/termination. You are not given channel changes and must not infer them.
The reference is the direct parent rollout when available for that task, otherwise the frozen v0
baseline. Each task bundle states `reference_version`; name that version accurately in the text.
Channel usage is retained for downstream attribution; do not guess which harness change caused a
behavior difference.

Follow the supplied evaluation_contract. With authoritative outcomes, derive completion status from
recorded pass/fail and use behavior only to explain it. With behavioral outcomes, classify from
visible task completion and retain reward disagreement. Use stable_success when the candidate set
consistently completes the core task and the reference has at least one completed branch; this also
captures a reference mixed-to-candidate-consistent improvement. Use still_failing when neither set
contains a completed branch; recovered when the baseline has
no completed branch and the candidate introduces at least one; regressed when the baseline has at
least one completed branch and the candidate has none; mixed for other split or partial outcomes.
A user's explicitly accepted change of item or plan is visible behavior; under behavioral outcomes
it may make a trajectory locally complete when reward remains zero. Do not infer hidden evaluator
logic.

For reusable passages, preserve successful procedures without unioning every action seen in a
successful trajectory. Include a step as common procedure only when it is shared by the supporting
successful trajectories or its necessity is established by a visible tool result. Keep distinct
successful branches separate. Explicitly omit incidental calls that another successful trajectory
skips. Every evidence reference on a reusable passage must support every tool invocation written in
that passage; otherwise split the branch or remove the unsupported step. Never generalize a
task-provided value into a guessing policy.
Use the exact observed payment-method selection rule; do not rename it a default unless visible
account or order data explicitly marks it as default.

For needs_adjustment passages, retain only observed failure behavior and a correction demonstrated
by a successful contrast. If no successful contrast establishes a correction, mark it unresolved.
Mixed task status does not absorb its failed branch: every candidate branch that remains visibly
incomplete must contribute a bounded or unresolved needs_adjustment passage.
Do not invent product capabilities, account-setting actions, policy rules, or hypothetical tool
support that no supplied trajectory or visible policy demonstrates. A passage that states a
correction demonstrated by contrast must cite both the failing trajectory and at least one successful
contrast trajectory.
Treat capability claims made by rollout agents as observations, not system facts. Write that the
agent stated or reported a limitation unless the supplied bundle itself contains an explicit tool
result or policy establishing it.

Return exactly:
{"task_comparisons":[{"task_id":"...","status":"...","text":"detailed comparison","baseline_refs":["..."],"candidate_refs":["..."]}],"reusable":[{"id":"...","text":"...","evidence_refs":["..."]}],"needs_adjustment":[{"id":"...","text":"...","evidence_refs":["..."]}],"coverage":{"task_ids":["..."],"baseline_refs":["..."],"candidate_refs":["..."]}}
""".strip()


COMPARISON_REVIEW_SYSTEM = """
You are the review pass of the rollout-comparison Experience module. Read every supplied task
bundle and the complete draft. Return a corrected full comparison object in the same schema.

Check the draft against the trajectories, not against its own prose. In particular:
- obey evaluation_contract: authoritative outcomes determine completion labels, while behavioral
  outcomes permit explicit visible-completion disagreement; recovered means a new
  completed candidate branch when baseline had none; regressed means no completed candidate branch
  remains when baseline had one; mixed covers the remaining partial combinations;
- preserve who initiated a choice or branch (user versus agent);
- keep successful branches concrete and separate instead of converting a single example into policy;
- remove incidental calls from common procedures;
- keep agent-stated limitations attributed to the observed agent unless a tool result establishes
  the capability;
- retain every remaining failed branch as bounded or unresolved needs_adjustment;
- cite all evidence used for a contrast.

Do not add fields, channel attribution, hidden evaluator explanations, or hypothetical capabilities.
Return exactly the same JSON shape as the draft, with any necessary semantic corrections applied.
""".strip()


def _select_user_messages(messages: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    if len(messages) <= 8:
        return list(messages)
    chosen = set(range(min(2, len(messages))))
    chosen.update(range(max(0, len(messages) - 4), len(messages)))
    confirmation = re.compile(r"\b(yes|confirm|proceed|go ahead|do it|please do)\b", re.I)
    for index, item in enumerate(messages):
        if confirmation.search(str(item.get("content") or "")):
            chosen.add(index)
    ordered = sorted(chosen)
    if len(ordered) > 10:
        ordered = ordered[:3] + ordered[-7:]
    return [messages[index] for index in ordered]


def _clip_text(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 20].rstrip() + " ...[truncated]"


def _compact_tool_result(value: Any) -> Any:
    parsed: Any = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return _clip_text(value, 1200)
    compact = _compact_value(parsed, depth=0)
    return _clip_text(
        json.dumps(compact, ensure_ascii=False, sort_keys=True, default=str),
        1800,
    )


def _compact_value(value: Any, *, depth: int) -> Any:
    if depth >= 4:
        return _clip_text(json.dumps(value, ensure_ascii=False, default=str), 400)
    if isinstance(value, Mapping):
        items = list(value.items())
        result = {
            str(key): _compact_value(item, depth=depth + 1)
            for key, item in items[:16]
        }
        if len(items) > 16:
            result["_omitted_fields"] = len(items) - 16
        return result
    if isinstance(value, list):
        result = [_compact_value(item, depth=depth + 1) for item in value[:12]]
        if len(value) > 12:
            result.append({"_omitted_items": len(value) - 12})
        return result
    if isinstance(value, str):
        return _clip_text(value, 600)
    return value


def _slug(value: Any) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-")
    return slug or "group"


def normalize_experience(
    output: Mapping[str, Any],
    evidence_refs: Sequence[str] = (),
) -> dict[str, Any]:
    normalized = {
        "reusable": [dict(item) for item in output.get("reusable") or []],
        "needs_adjustment": [dict(item) for item in output.get("needs_adjustment") or []],
        "coverage": dict(output.get("coverage") or {}),
    }
    allowed = set(str(item) for item in evidence_refs)
    if allowed:
        for section in ("reusable", "needs_adjustment"):
            for passage in normalized[section]:
                text = str(passage.get("text") or "")
                listed = [str(item) for item in passage.get("evidence_refs") or []]
                mentioned = [item for item in evidence_refs if str(item) in text]
                passage["evidence_refs"] = list(dict.fromkeys([*listed, *mentioned]))
    return normalized


def _normalize_in_place(
    output: Mapping[str, Any],
    evidence_refs: Sequence[str],
    outcomes: Mapping[str, str],
    *,
    outcome_authority: str = "behavioral",
) -> Mapping[str, Any]:
    normalized = normalize_experience(output, evidence_refs)
    normalized = _ensure_authoritative_failure_dispositions(
        normalized,
        outcomes=outcomes,
        outcome_authority=outcome_authority,
    )
    if isinstance(output, dict):
        output.clear()
        output.update(normalized)
        return output
    return normalized


def _ensure_authoritative_failure_dispositions(
    output: Mapping[str, Any],
    *,
    outcomes: Mapping[str, str],
    outcome_authority: str,
) -> dict[str, Any]:
    normalized = normalize_experience(output)
    if str(outcome_authority) != "authoritative":
        return normalized
    assigned = {
        str(ref)
        for passage in normalized["needs_adjustment"]
        for ref in passage.get("evidence_refs") or []
    }
    used_ids = {
        str(passage.get("id") or "")
        for section in ("reusable", "needs_adjustment")
        for passage in normalized[section]
    }
    for ref in sorted(
        str(ref)
        for ref, outcome in outcomes.items()
        if str(outcome) == "fail" and str(ref) not in assigned
    ):
        suffix = hashlib.sha256(ref.encode("utf-8")).hexdigest()[:12]
        passage_id = f"unresolved-authoritative-failure-{suffix}"
        while passage_id in used_ids:
            passage_id += "-x"
        used_ids.add(passage_id)
        normalized["needs_adjustment"].append(
            {
                "id": passage_id,
                "text": (
                    "Authoritative evaluation marked this trajectory as failed, but the "
                    "model-visible evidence establishes no specific correctable cause or "
                    "successful contrast. Retain it as unresolved diagnostic evidence; do "
                    "not infer hidden evaluator logic or an unsupported fix."
                ),
                "evidence_refs": [ref],
            }
        )
    return normalized


def _draft_catalog(
    drafts: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for draft_index, draft in enumerate(drafts, start=1):
        for section in ("reusable", "needs_adjustment"):
            code = "r" if section == "reusable" else "a"
            for passage_index, passage in enumerate(draft.get(section) or [], start=1):
                key = f"d{draft_index:02d}-{code}{passage_index:02d}"
                catalog[key] = {
                    "section": section,
                    "passage": dict(passage),
                }
    return catalog


def validate_experience_merge_plan(
    output: Mapping[str, Any], catalog: Mapping[str, Mapping[str, Any]]
) -> None:
    seen_sources: set[str] = set()
    seen_ids: set[str] = set()
    sections = {
        "reusable_merges": "reusable",
        "needs_adjustment_merges": "needs_adjustment",
    }
    for field, expected_section in sections.items():
        merges = output.get(field)
        if not isinstance(merges, list):
            raise ValueError(f"Experience merge plan requires {field}")
        for merge in merges:
            if not isinstance(merge, Mapping):
                raise ValueError("Experience merge must be an object")
            source_keys = [str(item) for item in merge.get("source_keys") or []]
            merge_id = str(merge.get("id") or "").strip()
            text = str(merge.get("text") or "").strip()
            if len(source_keys) < 2 or len(source_keys) != len(set(source_keys)):
                raise ValueError("Experience merge requires at least two unique sources")
            if any(key not in catalog for key in source_keys):
                raise ValueError("Experience merge references an unknown source")
            if any(catalog[key]["section"] != expected_section for key in source_keys):
                raise ValueError("Experience merge crosses reusable/adjustment sections")
            if seen_sources.intersection(source_keys):
                raise ValueError("Experience source appears in more than one merge")
            if not merge_id or merge_id in seen_ids or len(text) < 80:
                raise ValueError("Experience merge requires a unique ID and detailed text")
            seen_sources.update(source_keys)
            seen_ids.add(merge_id)
    discard = output.get("discard_source_keys") or []
    if not isinstance(discard, list):
        raise ValueError("Experience merge plan discard_source_keys must be an array")
    discard_keys = [str(item) for item in discard]
    if len(discard_keys) != len(set(discard_keys)):
        raise ValueError("Experience discard sources must be unique")
    if any(key not in catalog for key in discard_keys):
        raise ValueError("Experience discard references an unknown source")
    if seen_sources.intersection(discard_keys):
        raise ValueError("Experience source cannot be merged and discarded")


def canonicalize_experience_merge_plan(output: Mapping[str, Any]) -> Mapping[str, Any]:
    """Keep ambiguous source passages unchanged instead of assigning them arbitrarily."""
    fields = ("reusable_merges", "needs_adjustment_merges")
    counts: dict[str, int] = {}
    for field in fields:
        for merge in output.get(field) or []:
            if not isinstance(merge, Mapping):
                continue
            for source_key in {str(item) for item in merge.get("source_keys") or []}:
                counts[source_key] = counts.get(source_key, 0) + 1
    ambiguous = {key for key, count in counts.items() if count > 1}
    normalized = dict(output)
    for field in fields:
        merges = []
        for raw_merge in output.get(field) or []:
            if not isinstance(raw_merge, Mapping):
                merges.append(raw_merge)
                continue
            merge = dict(raw_merge)
            merge["source_keys"] = [
                str(item)
                for item in merge.get("source_keys") or []
                if str(item) not in ambiguous
            ]
            if len(merge["source_keys"]) >= 2:
                merges.append(merge)
        normalized[field] = merges
    if isinstance(output, dict):
        output.clear()
        output.update(normalized)
        return output
    return normalized


def materialize_experience_merge_plan(
    plan: Mapping[str, Any],
    *,
    catalog: Mapping[str, Mapping[str, Any]],
    task_ids: Sequence[str],
    evidence_refs: Sequence[str],
    outcomes: Mapping[str, str],
    outcome_authority: str = "behavioral",
) -> dict[str, Any]:
    merged_sources: set[str] = {
        str(item) for item in plan.get("discard_source_keys") or []
    }
    merged_passages: dict[str, list[dict[str, Any]]] = {
        "reusable": [],
        "needs_adjustment": [],
    }
    for field, section in (
        ("reusable_merges", "reusable"),
        ("needs_adjustment_merges", "needs_adjustment"),
    ):
        for merge in plan.get(field) or []:
            source_keys = [str(item) for item in merge["source_keys"]]
            merged_sources.update(source_keys)
            refs = [
                str(ref)
                for key in source_keys
                for ref in catalog[key]["passage"].get("evidence_refs") or []
            ]
            merged_passages[section].append(
                {
                    "id": str(merge["id"]),
                    "text": str(merge["text"]),
                    "evidence_refs": list(dict.fromkeys(refs)),
                }
            )
    output: dict[str, Any] = {
        "reusable": [],
        "needs_adjustment": [],
        "coverage": {
            "task_ids": list(task_ids),
            "evidence_refs": list(evidence_refs),
        },
    }
    used_ids: set[str] = set()
    for key, item in catalog.items():
        if key in merged_sources:
            continue
        passage = dict(item["passage"])
        passage["id"] = _unique_passage_id(str(passage.get("id") or key), used_ids)
        output[item["section"]].append(passage)
    for section in ("reusable", "needs_adjustment"):
        for passage in merged_passages[section]:
            passage["id"] = _unique_passage_id(str(passage["id"]), used_ids)
            output[section].append(passage)
    return dict(_normalize_in_place(output, evidence_refs, outcomes))


def _unique_passage_id(value: str, used: set[str]) -> str:
    base = _slug(value)
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _comparison_passage(item: Mapping[str, Any], used: set[str]) -> dict[str, Any]:
    passage = dict(item)
    passage["id"] = _unique_passage_id(str(passage.get("id") or "comparison"), used)
    passage["evidence_refs"] = list(
        dict.fromkeys(str(ref) for ref in passage.get("evidence_refs") or [])
    )
    return passage


def validate_comparison(
    output: Mapping[str, Any],
    *,
    task_ids: Sequence[str],
    index: Mapping[str, Any],
) -> None:
    expected_tasks = tuple(str(item) for item in task_ids)
    baseline_by_task = {
        task: tuple(str(ref) for ref in index["baseline_by_task"][task])
        for task in expected_tasks
    }
    candidate_by_task = {
        task: tuple(str(ref) for ref in index["candidate_by_task"][task])
        for task in expected_tasks
    }
    all_baseline = {ref for refs in baseline_by_task.values() for ref in refs}
    all_candidate = {ref for refs in candidate_by_task.values() for ref in refs}
    all_refs = all_baseline | all_candidate
    authority = _outcome_authority(index)

    coverage = output.get("coverage")
    if not isinstance(coverage, Mapping):
        raise ValueError("comparison requires coverage")
    if set(str(item) for item in coverage.get("task_ids") or []) != set(expected_tasks):
        raise ValueError("comparison task coverage is incomplete")
    if set(str(item) for item in coverage.get("baseline_refs") or []) != all_baseline:
        raise ValueError("comparison baseline coverage is incomplete")
    if set(str(item) for item in coverage.get("candidate_refs") or []) != all_candidate:
        raise ValueError("comparison candidate coverage is incomplete")

    comparisons = output.get("task_comparisons")
    if not isinstance(comparisons, list) or len(comparisons) != len(expected_tasks):
        raise ValueError("comparison requires exactly one record per task")
    seen_tasks: set[str] = set()
    allowed_statuses = {
        "recovered",
        "stable_success",
        "regressed",
        "still_failing",
        "mixed",
    }
    for item in comparisons:
        if not isinstance(item, Mapping):
            raise ValueError("task comparison must be an object")
        task = str(item.get("task_id") or "")
        if task not in expected_tasks or task in seen_tasks:
            raise ValueError("task comparison IDs must be exact and unique")
        status = str(item.get("status") or "")
        if status not in allowed_statuses:
            raise ValueError("task comparison has an invalid status")
        if authority == "authoritative" and status != _authoritative_comparison_status(
            task=task,
            baseline_by_task=baseline_by_task,
            candidate_by_task=candidate_by_task,
            outcomes=index.get("outcomes") or {},
        ):
            raise ValueError("comparison status conflicts with authoritative outcomes")
        if set(str(ref) for ref in item.get("baseline_refs") or []) != set(
            baseline_by_task[task]
        ):
            raise ValueError("task comparison has incorrect baseline references")
        if set(str(ref) for ref in item.get("candidate_refs") or []) != set(
            candidate_by_task[task]
        ):
            raise ValueError("task comparison has incorrect candidate references")
        outcome_summary = item.get("outcome_summary")
        if outcome_summary is not None:
            expected_summary = _comparison_outcome_summary(
                task=task,
                baseline_by_task=baseline_by_task,
                candidate_by_task=candidate_by_task,
                outcomes=index.get("outcomes") or {},
            )
            if not isinstance(outcome_summary, Mapping) or dict(
                outcome_summary
            ) != expected_summary:
                raise ValueError("task comparison has incorrect outcome summary")
        if len(str(item.get("text") or "").strip()) < 80:
            raise ValueError("task comparison lacks behavioral detail")
        seen_tasks.add(task)

    ids: set[str] = set()
    for section in ("reusable", "needs_adjustment"):
        passages = output.get(section)
        if not isinstance(passages, list):
            raise ValueError(f"comparison {section} must be an array")
        for passage in passages:
            if not isinstance(passage, Mapping):
                raise ValueError("comparison passage must be an object")
            passage_id = str(passage.get("id") or "").strip()
            text = str(passage.get("text") or "").strip()
            refs = {str(ref) for ref in passage.get("evidence_refs") or []}
            if not passage_id or passage_id in ids:
                raise ValueError("comparison passage IDs must be unique")
            if len(text) < 80 or not refs or refs - all_refs:
                raise ValueError("comparison passage lacks detail or valid evidence")
            if (
                section == "reusable"
                and authority == "authoritative"
                and not any(str((index.get("outcomes") or {}).get(ref)) == "pass" for ref in refs)
            ):
                raise ValueError(
                    "comparison reusable passage requires authoritative passing evidence"
                )
            ids.add(passage_id)


def canonicalize_comparison(
    output: Mapping[str, Any],
    *,
    task_ids: Sequence[str],
    index: Mapping[str, Any],
) -> Mapping[str, Any]:
    if not isinstance(output, dict):
        return output
    expected_tasks = tuple(str(item) for item in task_ids)
    baseline_by_task = {
        task: [str(ref) for ref in index["baseline_by_task"][task]]
        for task in expected_tasks
    }
    candidate_by_task = {
        task: [str(ref) for ref in index["candidate_by_task"][task]]
        for task in expected_tasks
    }
    output["coverage"] = {
        "task_ids": list(expected_tasks),
        "baseline_refs": [
            ref for task in expected_tasks for ref in baseline_by_task[task]
        ],
        "candidate_refs": [
            ref for task in expected_tasks for ref in candidate_by_task[task]
        ],
    }
    comparisons = output.get("task_comparisons")
    if isinstance(comparisons, list):
        for item in comparisons:
            if not isinstance(item, dict):
                continue
            task = str(item.get("task_id") or "")
            if task not in baseline_by_task:
                continue
            item["baseline_refs"] = list(baseline_by_task[task])
            item["candidate_refs"] = list(candidate_by_task[task])
            outcome_summary = _comparison_outcome_summary(
                task=task,
                baseline_by_task=baseline_by_task,
                candidate_by_task=candidate_by_task,
                outcomes=index.get("outcomes") or {},
            )
            if outcome_summary is None:
                item.pop("outcome_summary", None)
            else:
                item["outcome_summary"] = outcome_summary
            if _outcome_authority(index) == "authoritative":
                item["status"] = _authoritative_comparison_status(
                    task=task,
                    baseline_by_task=baseline_by_task,
                    candidate_by_task=candidate_by_task,
                    outcomes=index.get("outcomes") or {},
                )
    allowed_refs = set(output["coverage"]["baseline_refs"]) | set(
        output["coverage"]["candidate_refs"]
    )
    for section in ("reusable", "needs_adjustment"):
        passages = output.get(section)
        if not isinstance(passages, list):
            continue
        for passage in passages:
            if isinstance(passage, dict):
                passage["evidence_refs"] = _canonicalize_evidence_refs(
                    passage.get("evidence_refs") or [],
                    allowed_refs=allowed_refs,
                )
    return output


def _canonicalize_evidence_refs(
    refs: Sequence[Any], *, allowed_refs: set[str]
) -> list[str]:
    normalized: list[str] = []
    for raw_ref in refs:
        ref = str(raw_ref)
        if ref in allowed_refs:
            candidate = ref
        elif ref.startswith("ev_harnesslens_") and f"ev_{ref.removeprefix('ev_harnesslens_')}" in allowed_refs:
            candidate = f"ev_{ref.removeprefix('ev_harnesslens_')}"
        else:
            matches = get_close_matches(ref, allowed_refs, n=1, cutoff=0.96)
            if not matches:
                continue
            candidate = matches[0]
        if candidate not in normalized:
            normalized.append(candidate)
    return normalized


def validate_experience(
    output: Mapping[str, Any],
    *,
    task_ids: Sequence[str],
    evidence_refs: Sequence[str],
    outcomes: Mapping[str, str],
    outcome_authority: str = "behavioral",
) -> None:
    expected_evidence = set(str(item) for item in evidence_refs)
    coverage = output.get("coverage")
    if not isinstance(coverage, Mapping):
        raise ValueError("Experience output requires coverage")
    if set(str(item) for item in coverage.get("task_ids") or []) != set(task_ids):
        raise ValueError("Experience task coverage is incomplete")
    if set(str(item) for item in coverage.get("evidence_refs") or []) != expected_evidence:
        raise ValueError("Experience evidence coverage is incomplete")
    ids: set[str] = set()
    for section in ("reusable", "needs_adjustment"):
        passages = output.get(section)
        if not isinstance(passages, list):
            raise ValueError(f"Experience {section} must be an array")
        for passage in passages:
            if not isinstance(passage, Mapping):
                raise ValueError(f"Experience {section} passage must be an object")
            passage_id = str(passage.get("id") or "").strip()
            text = str(passage.get("text") or "").strip()
            refs = {str(item) for item in passage.get("evidence_refs") or []}
            if not passage_id or passage_id in ids:
                raise ValueError("Experience passage IDs must be unique and nonempty")
            if len(text) < 80:
                raise ValueError("Experience passage is too short to retain behavioral detail")
            if not refs or refs - expected_evidence:
                raise ValueError("Experience passage has invalid evidence references")
            if (
                section == "reusable"
                and str(outcome_authority) == "authoritative"
                and not any(str(outcomes.get(ref)) == "pass" for ref in refs)
            ):
                raise ValueError(
                    "Experience reusable passage requires authoritative passing evidence"
                )
            ids.add(passage_id)
    if str(outcome_authority) == "authoritative":
        adjustment_refs = {
            str(ref)
            for passage in output.get("needs_adjustment") or []
            for ref in passage.get("evidence_refs") or []
        }
        missing_failures = {
            ref
            for ref in expected_evidence
            if str(outcomes.get(ref)) == "fail" and ref not in adjustment_refs
        }
        if missing_failures:
            raise ValueError(
                "authoritative failed evidence requires needs_adjustment disposition: "
                + ",".join(sorted(missing_failures))
            )


def _outcome_authority(index: Mapping[str, Any]) -> str:
    contract = index.get("evaluation_contract") or {}
    authority = str(contract.get("outcome_authority") or "behavioral")
    if authority not in {"behavioral", "authoritative"}:
        raise ValueError(f"invalid outcome authority: {authority}")
    return authority


def _authoritative_comparison_status(
    *,
    task: str,
    baseline_by_task: Mapping[str, Sequence[str]],
    candidate_by_task: Mapping[str, Sequence[str]],
    outcomes: Mapping[str, Any],
) -> str:
    baseline = [str(outcomes.get(ref) or "") for ref in baseline_by_task[task]]
    candidate = [str(outcomes.get(ref) or "") for ref in candidate_by_task[task]]
    if not baseline or not candidate or set([*baseline, *candidate]) - {"pass", "fail"}:
        raise ValueError("authoritative comparison is missing pass/fail outcomes")
    baseline_has_pass = "pass" in baseline
    candidate_has_pass = "pass" in candidate
    if baseline_has_pass and all(item == "pass" for item in candidate):
        return "stable_success"
    if not baseline_has_pass and not candidate_has_pass:
        return "still_failing"
    if not baseline_has_pass and candidate_has_pass:
        return "recovered"
    if baseline_has_pass and not candidate_has_pass:
        return "regressed"
    return "mixed"


def _comparison_outcome_summary(
    *,
    task: str,
    baseline_by_task: Mapping[str, Sequence[str]],
    candidate_by_task: Mapping[str, Sequence[str]],
    outcomes: Mapping[str, Any],
) -> dict[str, int] | None:
    baseline = [str(outcomes.get(ref) or "") for ref in baseline_by_task[task]]
    candidate = [str(outcomes.get(ref) or "") for ref in candidate_by_task[task]]
    if set([*baseline, *candidate]) - {"pass", "fail"}:
        return None
    return {
        "reference_pass_count": sum(item == "pass" for item in baseline),
        "reference_trial_count": len(baseline),
        "candidate_pass_count": sum(item == "pass" for item in candidate),
        "candidate_trial_count": len(candidate),
    }
