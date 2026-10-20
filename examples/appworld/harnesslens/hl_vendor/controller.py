"""Vendored verbatim from HarnessLens 369a5c8:harnesslens/evolution/controller.py (see VENDORED.md)."""
from __future__ import annotations

from typing import Any
from .main_agent import ITERATION_RETRY_BUFFER_CREATIONS
from .main_agent import MIN_STANDARD_ROLLOUT_TASKS
from .main_agent import MainDecision
from typing import Mapping
from pathlib import Path
from typing import Sequence
from .main_agent import confirmation_mode
import json
from .main_agent import paired_confirmation_creation_cost
from .main_agent import paired_screen_creation_cost
from .artifacts import write_json


def reference_metrics_from_comparison_index(path: str | Path) -> dict[str, float]:
    index = json.loads(Path(path).read_text(encoding="utf-8"))
    outcomes = index.get("outcomes") or {}
    by_task = index.get("baseline_by_task") or {}
    if not isinstance(by_task, Mapping) or not by_task:
        raise ValueError("comparison index has no paired reference tasks")
    pass_at_1_successes = 0
    pass_at_1_trials = 0
    pass_at_2 = 0
    for refs in by_task.values():
        ordered = [str(outcomes.get(str(ref)) or "") for ref in refs]
        if not ordered or set(ordered) - {"pass", "fail"}:
            raise ValueError("comparison reference outcomes are incomplete")
        pass_at_1_successes += sum(outcome == "pass" for outcome in ordered)
        pass_at_1_trials += len(ordered)
        pass_at_2 += int("pass" in ordered[:2])
    task_count = len(by_task)
    return {
        "pass_at_1": pass_at_1_successes / pass_at_1_trials,
        "pass_at_2": pass_at_2 / task_count,
    }


def select_confirmation_task_ids(
    *,
    run_root: str | Path,
    decision: Any,
    screen_review: Any,
    screen_task_ids: Sequence[str],
    task_count: int,
) -> tuple[str, ...]:
    """Mix direct effect anchors with fresh, diverse preservation canaries."""

    root = Path(run_root)
    screen = tuple(dict.fromkeys(str(item) for item in screen_task_ids))
    count = int(task_count)
    if count < MIN_STANDARD_ROLLOUT_TASKS or len(screen) < count:
        raise ValueError("confirmation selection requires a complete standard screen")

    source = json.loads(
        (root / "experience" / "baseline_source_index.json").read_text(encoding="utf-8")
    )
    experiences = json.loads(
        (root / "experience" / "current.json").read_text(encoding="utf-8")
    )
    explorer = json.loads(
        (root / "discovery" / "task_explorer.json").read_text(encoding="utf-8")
    )
    evidence_by_task = {
        str(task_id): tuple(str(ref) for ref in refs)
        for task_id, refs in (source.get("evidence_by_task") or {}).items()
    }
    outcomes = {
        str(ref): str(outcome)
        for ref, outcome in (source.get("outcomes") or {}).items()
    }
    evidence_to_task = {
        ref: task_id for task_id, refs in evidence_by_task.items() for ref in refs
    }
    passage_by_id = {
        str(item.get("id") or ""): item
        for section in ("reusable", "needs_adjustment")
        for item in experiences.get(section) or []
        if isinstance(item, Mapping) and item.get("id")
    }
    experience_ids = {
        str(experience_id)
        for channel in decision.output["candidate"].get("channel_diffs") or []
        for experience_id in channel.get("experience_ids") or []
    }
    direct_tasks = {
        evidence_to_task[str(ref)]
        for experience_id in experience_ids
        for ref in passage_by_id.get(experience_id, {}).get("evidence_refs") or []
        if str(ref) in evidence_to_task
    }
    recovered = tuple(
        str(item)
        for item in (
            (screen_review.output.get("evidence") or {}).get("recovered_task_ids") or []
        )
    )
    uncertain = tuple(
        str(item)
        for item in (
            (screen_review.output.get("evidence") or {}).get(
                "uncertain_recovery_task_ids"
            )
            or []
        )
    )

    anchor_limit = min(2, count - 1)
    selected: list[str] = []
    for task_id in (
        *recovered,
        *uncertain,
        *(task for task in screen if task in direct_tasks),
        *screen,
    ):
        if task_id in screen and task_id not in selected:
            selected.append(task_id)
        if len(selected) >= anchor_limit:
            break

    fresh = [
        task_id
        for task_id in source.get("task_ids") or []
        if str(task_id) not in screen
    ]

    def preservation_rank(task_id: str) -> tuple[float, int, str]:
        refs = evidence_by_task.get(str(task_id), ())
        passes = sum(outcomes.get(ref) == "pass" for ref in refs)
        rate = passes / len(refs) if refs else 0.0
        return (-rate, -passes, str(task_id))

    fresh_set = {str(item) for item in fresh}
    stable_set = {
        task_id
        for task_id in fresh_set
        if evidence_by_task.get(task_id)
        and all(outcomes.get(ref) == "pass" for ref in evidence_by_task[task_id])
    }
    categories = [
        (
            str(category.get("id") or f"category-{index}"),
            {str(task_id) for task_id in category.get("task_ids") or []},
        )
        for index, category in enumerate(explorer.get("categories") or [])
        if isinstance(category, Mapping)
    ]
    categories_by_task: dict[str, set[str]] = {}
    for category_id, category_tasks in categories:
        for task_id in category_tasks:
            categories_by_task.setdefault(task_id, set()).add(category_id)
    represented_categories = {
        category_id
        for task_id in selected
        for category_id in categories_by_task.get(task_id, ())
    }
    for pool in (stable_set, fresh_set):
        while len(selected) < count:
            candidates = [task_id for task_id in pool if task_id not in selected]
            if not candidates:
                break
            task_id = min(
                candidates,
                key=lambda item: (
                    -len(categories_by_task.get(item, set()) - represented_categories),
                    *preservation_rank(item),
                ),
            )
            selected.append(task_id)
            represented_categories.update(categories_by_task.get(task_id, ()))
        if len(selected) >= count:
            break
    for task_id in sorted(fresh_set, key=preservation_rank):
        if len(selected) >= count:
            break
        if task_id not in selected:
            selected.append(task_id)
    for task_id in screen:
        if len(selected) >= count:
            break
        if task_id not in selected:
            selected.append(task_id)
    if len(selected) != count:
        raise ValueError("could not construct a complete confirmation task set")
    return tuple(selected)


def _evaluation_requires_confirmation(mode: str) -> bool:
    return (
        confirmation_mode() == "always" and str(mode or "standard") != "residual_probe"
    )


def advance_cumulative_version(
    *, current_version: str, decision: Any, review: Any
) -> tuple[str, bool]:
    parent = str(decision.output["candidate"]["parent_version"])
    child = str(decision.harness_version)
    selected = str(review.harness_version)
    if parent != str(current_version):
        raise RuntimeError(
            "cumulative iteration parent differs from the last accepted version"
        )
    if selected == child:
        return child, True
    if selected == parent:
        return parent, False
    raise RuntimeError(
        "cumulative review selected neither the child nor its direct parent"
    )


def assert_candidate_extends_champion(*, current_version: str, decision: Any) -> None:
    parent = str(decision.output["candidate"]["parent_version"])
    child = str(decision.harness_version)
    if parent != str(current_version) or child in {"", parent, "v0"}:
        raise RuntimeError(
            "candidate must extend the current champion before rollout: "
            f"champion={current_version} parent={parent} child={child}"
        )


def assert_confirmed_promotion(
    *, decision: Any, review: Any, confirmation_pair: Any | None
) -> None:
    if (
        str(review.harness_version) == str(decision.harness_version)
        and confirmation_pair is None
    ):
        raise RuntimeError(
            "candidate promotion requires independent confirmation against its direct parent"
        )


def minimum_screen_start_creations(parent_version: str) -> int:
    return (
        paired_screen_creation_cost(
            MIN_STANDARD_ROLLOUT_TASKS, parent_version=parent_version
        )
        + ITERATION_RETRY_BUFFER_CREATIONS
    )


def confirmation_creation_cost(task_count: int, *, parent_version: str) -> int:
    del parent_version
    return paired_confirmation_creation_cost(task_count)


def reject_unconfirmed_candidate(
    *, screen_review: MainDecision, parent_version: str, output_path: Path
) -> MainDecision:
    payload = dict(screen_review.output)
    payload["decision"] = "reject_delta"
    payload["selected_version"] = str(parent_version)
    payload["rationale"] = (
        "The screen passed, but independent confirmation was not affordable. "
        "Keep the current champion rather than promote provisional evidence."
    )
    evidence = dict(payload.get("evidence") or {})
    unresolved = list(evidence.get("unresolved_findings") or [])
    unresolved.append(
        "Fresh-seed confirmation was not run within the remaining budget."
    )
    evidence["unresolved_findings"] = unresolved
    payload["evidence"] = evidence
    payload.pop("revision_candidate", None)
    written = write_json(output_path, payload)
    return MainDecision(payload, str(written), str(parent_version))


def defer_residual_candidate(
    *, screen_review: MainDecision, parent_version: str, output_path: Path
) -> MainDecision:
    payload = dict(screen_review.output)
    payload["decision"] = "reject_delta"
    payload["selected_version"] = str(parent_version)
    payload["rationale"] = (
        "The residual probe is diagnostic-only. Keep the current champion until "
        "the candidate receives a standard screen and independent confirmation."
    )
    payload["evidence_disposition"] = "diagnostic_only"
    evidence = dict(payload.get("evidence") or {})
    unresolved = list(evidence.get("unresolved_findings") or [])
    unresolved.append("Residual probe evidence cannot satisfy the promotion contract.")
    evidence["unresolved_findings"] = unresolved
    payload["evidence"] = evidence
    payload.pop("revision_candidate", None)
    written = write_json(output_path, payload)
    return MainDecision(payload, str(written), str(parent_version))


def revision_candidate_from_review(
    review_output: Mapping[str, Any],
    *,
    rollout_task_ids: list[str] | tuple[str, ...] = (),
) -> dict[str, Any] | None:
    if str(review_output.get("decision") or "") != "revise_delta":
        return None
    revision = review_output.get("revision_candidate")
    if not isinstance(revision, Mapping):
        raise RuntimeError("revise_delta review is missing its revision candidate")
    result = dict(revision)
    if rollout_task_ids:
        result["_direct_task_ids"] = sorted({str(item) for item in rollout_task_ids})
        result["_prior_train_evidence"] = dict(review_output.get("evidence") or {})
    return result


def replan_candidate_from_review(
    review_output: Mapping[str, Any],
    *,
    adjustment: Mapping[str, Any],
    rollout_task_ids: Sequence[str] = (),
) -> dict[str, Any] | None:
    if str(review_output.get("decision") or "") != "replan_problem":
        return None
    candidate = adjustment.get("replan_candidate")
    if not isinstance(candidate, Mapping):
        raise RuntimeError("replan_problem review is missing the Analyzer candidate")
    result = dict(candidate)
    result["_portfolio_side"] = "adjustment"
    result["_direct_task_ids"] = sorted(
        {str(item) for item in rollout_task_ids if str(item)}
    )
    result["_conversion_task_ids"] = sorted(
        {
            str(item.get("task_id") or "")
            for item in (adjustment.get("primary_problem") or {}).get(
                "task_assessments"
            )
            or []
            if isinstance(item, Mapping)
            and str(item.get("status") or "")
            in {"still_failing", "mixed", "regressed"}
            and int((item.get("outcome_summary") or {}).get("candidate_pass_count") or 0)
            == 0
            and str(item.get("task_id") or "")
        }
    )
    result["_prior_train_evidence"] = dict(review_output.get("evidence") or {})
    return result
