"""Vendored verbatim from HarnessLens 369a5c8:harnesslens/evolution/main_agent.py (see VENDORED.md)."""
from __future__ import annotations

from typing import Any
from typing import Mapping
from .channel_preflight import PREFLIGHT_CREATION_COST
from typing import Sequence
from .train_protocol import TRAIN_ROLLOUT_REPEATS
from .analyzer import _validate_candidate
from .analyzer import canonicalize_analyzer_output
from .artifacts import content_digest
from dataclasses import dataclass
import json
import math
import os


MIN_ROLLOUT_CREATIONS = 5 * TRAIN_ROLLOUT_REPEATS


MIN_STANDARD_ROLLOUT_TASKS = 5


MIN_RESIDUAL_ROLLOUT_TASKS = 2


DEFAULT_EXPLORATION_ROLLOUT_TASKS = 6


ITERATION_RETRY_BUFFER_CREATIONS = 3


PROMOTION_METRICS = frozenset({"pass_at_1", "pass_at_2"})


GLOBAL_INSTRUCTION_CHANNELS = frozenset(
    {
        "developer_instructions",
        "hooks",
        "instructions_rules",
        "project_instructions",
        "system_prompt",
    }
)


def iteration_creation_cost(task_count: int) -> int:
    count = int(task_count)
    if count < 5:
        raise ValueError("an iteration requires at least five tasks")
    return (
        2
        + PREFLIGHT_CREATION_COST
        + count * TRAIN_ROLLOUT_REPEATS
        + math.ceil(count / 3) * 2
        + 2
        + 1
    )


MIN_CANDIDATE_ITERATION_CREATIONS = iteration_creation_cost(5)


def normalize_promotion_metric(value: str) -> str:
    metric = str(value).strip()
    if metric not in PROMOTION_METRICS:
        raise ValueError(
            "promotion metric must be one of " + ", ".join(sorted(PROMOTION_METRICS))
        )
    return metric


def paired_screen_creation_cost(task_count: int, *, parent_version: str) -> int:
    count = int(task_count)
    if count < MIN_RESIDUAL_ROLLOUT_TASKS:
        raise ValueError("a paired screen requires at least two tasks")
    candidate_rollout = count * TRAIN_ROLLOUT_REPEATS
    parent_rollout = count * TRAIN_ROLLOUT_REPEATS if str(parent_version) != "v0" else 0
    comparison = math.ceil(count / 3) * 2
    return (
        2
        + PREFLIGHT_CREATION_COST
        + candidate_rollout
        + parent_rollout
        + comparison
        + 2
        + 1
    )


def paired_confirmation_creation_cost(task_count: int) -> int:
    count = int(task_count)
    if count < MIN_STANDARD_ROLLOUT_TASKS:
        raise ValueError("confirmation requires at least five tasks")
    rollouts = count * TRAIN_ROLLOUT_REPEATS * 2
    comparison = math.ceil(count / 3) * 2
    return rollouts + comparison + 2 + 1


def confirmation_mode() -> str:
    mode = os.environ.get("HAI_CONFIRMATION_MODE", "always").strip().lower()
    if mode not in {"always", "off"}:
        raise ValueError("HAI_CONFIRMATION_MODE must be 'always' or 'off'")
    return mode


def build_rollout_budget_plan(
    *,
    remaining_creations: int,
    parent_version: str,
    unattempted_batch_count: int,
    max_task_count: int,
) -> dict[str, Any]:
    """Pack one evidence screen against its exact promotion cost.

    When confirmation is enabled, a standard screen reserves enough budget to
    independently confirm a pass.
    A terminal screen evaluates one full-size hypothesis when a separate confirmation
    cycle is no longer affordable, but its evidence remains provisional.
    """

    remaining = max(0, int(remaining_creations))
    task_cap = max(0, int(max_task_count))

    def max_affordable(minimum: int, cost) -> int:
        if task_cap < minimum:
            return 0
        affordable = 0
        for count in range(minimum, task_cap + 1):
            if cost(count) + ITERATION_RETRY_BUFFER_CREATIONS > remaining:
                break
            affordable = count
        return affordable

    screen_cost = lambda count: paired_screen_creation_cost(
        count, parent_version=parent_version
    )
    confirmation_required = confirmation_mode() == "always"
    full_cycle_cost = lambda count: screen_cost(count) + (
        paired_confirmation_creation_cost(count) if confirmation_required else 0
    )
    confirmable_limit = max_affordable(MIN_STANDARD_ROLLOUT_TASKS, full_cycle_cost)
    minimum_next_screen = (
        screen_cost(MIN_STANDARD_ROLLOUT_TASKS) + ITERATION_RETRY_BUFFER_CREATIONS
    )

    if confirmable_limit:
        rollout_limit = min(DEFAULT_EXPLORATION_ROLLOUT_TASKS, confirmable_limit)
        reserved_future = 0
        compact_limit = min(DEFAULT_EXPLORATION_ROLLOUT_TASKS, confirmable_limit)
        compact_cycle_cost = (
            full_cycle_cost(compact_limit) + ITERATION_RETRY_BUFFER_CREATIONS
        )
        if (
            int(unattempted_batch_count) > 1
            and remaining - compact_cycle_cost >= minimum_next_screen
        ):
            rollout_limit = compact_limit
            reserved_future = minimum_next_screen
        return {
            "mode": "standard",
            "promotion_eligible": True,
            "minimum_rollout_tasks": MIN_STANDARD_ROLLOUT_TASKS,
            "rollout_task_limit": rollout_limit,
            "recommended_rollout_tasks": rollout_limit,
            "reserved_future_iteration_creations": reserved_future,
            "screen_creation_cost_at_limit": screen_cost(rollout_limit),
            "confirmation_creation_cost_at_limit": (
                paired_confirmation_creation_cost(rollout_limit)
                if confirmation_required
                else None
            ),
            "remaining_creations": remaining,
        }

    screen_limit = min(
        DEFAULT_EXPLORATION_ROLLOUT_TASKS,
        max_affordable(MIN_STANDARD_ROLLOUT_TASKS, screen_cost),
    )
    if screen_limit:
        return {
            "mode": "terminal_screen",
            "promotion_eligible": True,
            "minimum_rollout_tasks": MIN_STANDARD_ROLLOUT_TASKS,
            "rollout_task_limit": screen_limit,
            "recommended_rollout_tasks": screen_limit,
            "reserved_future_iteration_creations": 0,
            "screen_creation_cost_at_limit": screen_cost(screen_limit),
            "confirmation_creation_cost_at_limit": None,
            "remaining_creations": remaining,
        }

    return {
        "mode": "stop",
        "promotion_eligible": False,
        "minimum_rollout_tasks": 0,
        "rollout_task_limit": 0,
        "recommended_rollout_tasks": 0,
        "reserved_future_iteration_creations": 0,
        "screen_creation_cost_at_limit": None,
        "confirmation_creation_cost_at_limit": None,
        "remaining_creations": remaining,
    }


def normalize_budget_disposition(
    output: Mapping[str, Any], *, remaining_after_decision: int
) -> dict[str, Any]:
    """Return a decision with controller-owned budget fields normalized.

    The Main Agent chooses accept/reject/revise and candidate content; the
    creation ledger is owned by the controller.  Keep the budget_disposition
    contract visible in prompts, but do not let an LLM arithmetic mismatch turn
    an otherwise valid review decision into malformed output.
    """

    normalized = dict(output)
    disposition = dict(normalized.get("budget_disposition") or {})
    remaining = int(remaining_after_decision)
    disposition.update(
        {
            "remaining_creations_after_this_decision": remaining,
            "minimum_next_rollout_creations": MIN_ROLLOUT_CREATIONS,
            "rollout_possible": remaining >= MIN_ROLLOUT_CREATIONS,
            "minimum_next_iteration_creations": MIN_CANDIDATE_ITERATION_CREATIONS,
            "iteration_possible": remaining >= MIN_CANDIDATE_ITERATION_CREATIONS,
        }
    )
    normalized["budget_disposition"] = disposition
    return normalized


MAIN_AGENT_SYSTEM = """
You are the Main Agent for one cumulative harness iteration. You allocate the remaining creation
budget and select one evidence-grounded behavior problem for a separate Harness Editor; you do not
write harness files or re-analyze trajectories. Review the ranked Analyzer portfolio, public policy,
frozen task categories, evidence-to-task mapping, prior attempts, accepted history, exploration
status, and the current parent state.

Use the remaining budget to maximize expected final harness quality. At the start, identify the
small set of open behavior problems worth exploring. First test several distinct, high-potential
behavior hypotheses with the smallest valid experiments. Continue, scale up, or revise a hypothesis
only after it shows attributable positive evidence; otherwise stop that line and move to the next
promising problem. Do not spend iterations merely to balance candidate types, and reserve enough
budget to evaluate alternatives before committing to refinement.
The supplied `promotion_metric` is the experiment objective; prioritize candidates whose direct
evidence can improve that metric rather than a different repeat-derived score.

Select exactly one unattempted candidate with the best marginal evidence, pass-conversion potential,
and regression-risk tradeoff. A pending revision competes with the other open problems and is preferred
only when its parent showed attributable benefit and a localized repair has better expected value than
switching problems. A tested revision must then be accepted or rejected, never revised again. Keep
each change focused on one behavior question. A passed candidate becomes the next parent, so preserve
and regression-check previously accepted behavior.
Failure density alone is not pass-conversion potential: prefer an observed passing contrast, and do
not edit a failure-only pattern whose evidence establishes no feasible recovery action.
Treat revisions sharing an origin as repeated tests of one hypothesis. If a bounded revision does not improve attributable recoveries or reduce attributable regressions, turn to another open
problem instead of continuing cosmetic rewrites.
The controller admits only candidates with explicit baseline failure headroom. Every rollout must
include at least one supplied conversion task for the selected candidate; passing evidence and
preservation canaries alone cannot justify spending a promotion iteration.
An explicitly supplied incumbent is the current TRAIN-accepted champion and appears as the parent
manifest and accepted history. Improve it through cumulative deltas; do not reconstruct or replace
its independent artifacts unless the tested delta specifically changes them.
Use channel appropriateness as part of the decision: detailed ordered SOPs with branches and
parameters should remain skill candidates; concise global behavior can use instructions; guidance
local to one tool can use its description. Do not select an instruction merely because it is
always visible, and do not select a skill merely to create channel diversity.

Select distinct TRAIN task IDs directly, never category labels, within the range in
`rollout_budget_plan`. Use compact screens while the plan reserves another problem, and use the
recommended capacity when this is the last affordable screen and additional cases are informative.
    A terminal screen has no affordable confirmation, so use it only for an informative
    provisional result; the controller will keep the champion even if that screen is positive.
    Cover direct evidence for the chosen problem's distinct artifacts and
retain success-preservation cases for accepted behavior. The controller owns the fixed training
repeat count supplied in the input; do not specify repeats. The local success criteria must test
behavior, not reward alone.
Before choosing rollout task IDs, use the initial task categories and harness-query channel
descriptions to reflect on the changed channel's blast radius. Treat system instructions, tool
descriptions, tool parameter descriptions, MCP tool descriptions, and skill names/descriptions as
startup-visible/global enough to affect unrelated behavior. For these channels, do not validate only
on the narrow evidence tasks: broaden the rollout across target tasks, nearby categories, and a few
preservation canaries from supplied accepted/baseline evidence or unrelated task categories, or
choose/revise toward a more triggered/tool-scoped artifact. If the changed channel is truly
triggered, tool-scoped, or MCP tool-specific, focus rollout on tasks where that trigger/tool should
appear while keeping a small preservation check for nearby non-trigger tasks.
The controller will classify the selected IDs into conversion_tasks, positive_controls,
preservation_canaries, and diagnostic_tasks from frozen baseline evidence. Do not invent those
roles in your response.

Return exactly:
{"decision":"materialize_and_rollout","selected_candidate_id":"...","exploration_plan":{"open_problem_ids":["..."],"chosen_problem_id":"...","budget_strategy":"...","turning_point":"..."},"rollout_request":{"task_ids":["..."],"rationale":"...","local_success_criteria":["..."]}}
""".strip()


FINAL_MAIN_AGENT_SYSTEM = """
You are the cumulative-delta review Main Agent. You do not inspect or re-analyze trajectories. Read
the two post-rollout Analyzer decisions, rollout metrics, exact tested delta, its direct parent,
and creation budget. Accept the tested delta, keep its parent, or create one bounded revision for
the next iteration when the Analyzers have localized a failure to changed channels.

Judge the tested delta by causal evidence, not by aggregate rollout score alone. Prefer changes
whose intended local behavior is visibly recovered and whose failures are not attributable to the
changed channels. Low overall pass rates or unrelated rollout failures should reduce confidence or
motivate a smaller revision, but they are not by themselves a reason to reject a locally effective
delta. When a candidate mixes helpful, unresolved, and harmful changes, prefer the smallest
isolatable revision that keeps the helpful attributed change and drops the rest. Budget exhaustion
does not lower the acceptance standard, but unrelated unresolved failures do not raise it. Judge the
completed paired evidence for the changed behavior: accept an attributable net pass gain with no
attributable regression even when an Analyzer asks for more confidence or reports failures it
classifies as not attributed. Keep the parent when follow-up is still required for a failure
attributed to the changed channel and that follow-up is unaffordable. A possibly-related failure
does not justify spending the next iteration on a revision without stronger causal evidence.
`further_rollout_needed` is advisory rather than a veto when the completed evidence already satisfies
the attribution and preservation gates. A
controller-marked residual probe is diagnostic-only and cannot be accepted. An actual changed
channel named `workspace_file:*` was not explained by Harness Query; remove it in a revision and
retest before promotion.
The supplied `promotion_metric` is authoritative when `require_primary_metric_improvement` is true:
the candidate must strictly improve it over the paired reference. When that flag is false, apply the
attribution and preservation gates; the controller decides whether acceptance promotes immediately
or requests independent confirmation. Improvements only in another
pass@k metric are diagnostic evidence. When two or more independent trials are available, pass@1 is
estimated from all of them rather than privileging the first trial's arbitrary ordering.

Acceptance requires attributable positive evidence. An attributed `stable_success` counts when the
comparison shows that the target behavior became more consistent even though the reference already
had one successful branch, but only when the candidate also increases the recorded pass count.
Behavioral completion without a recorded-pass gain remains diagnostic evidence, not promotion
evidence. Mere preservation of behavior already present in the reference is not a
benefit and cannot justify accepting a new parent. Once an atomic candidate has attributable positive
evidence and no attributable regression, unrelated low aggregate scores are not a reason to reject it.
For a prior TRAIN-accepted incumbent, do not discard independently validated artifacts merely because
this small rollout did not exercise them. Preserve the full control when it reproduces a pass gain
without attributable regression; revise it only for a localized harmful changed channel.

An attributable regression is a reason to reject. A remaining local failure is not evidence of
regression, but must remain visible in unresolved_findings. A revision is never accepted directly:
it is a new complete candidate relative to the same parent and must receive its own rollout. Prefer
revision over terminal rejection when the evidence identifies removable or narrowable changed
channels while leaving useful, unimplicated artifacts. The revision must not expand the evidence
scope. It may add a discovered channel only when post-rollout channel usage shows that an existing
artifact was unavailable or not invoked and the added channel only makes that same artifact
reachable; it must not introduce unrelated domain logic. Distinguish whether ten rollout
trials alone are affordable from whether a
complete next iteration (selection, rollout, comparison+review, post-analysis, review) is affordable.
List a recovered task only when its post-Analyzer relation is attributed. A possibly-related recorded
pass gain is uncertainty, not promotion evidence; choose `confirm_delta` when an independent paired
rerun can resolve it and there is no attributable regression. If the post-adjustment Analyzer exposes
a distinct evidence-grounded `replan_candidate`, choose `replan_problem` to return that hypothesis to
the portfolio instead of silently moving through the stale baseline list. Do not use replan merely
because the tested hypothesis failed. Evidence task-ID sets are copied from the post-Analyzers;
do not reinterpret their preservation semantics.
The reusable preservation Analyzer owns the regression gate: if its
`preservation.attributable_regressions` list is nonempty, `accept_delta` is forbidden even when the
needs-adjustment Analyzer disagrees. Analyzer disagreement is uncertainty to resolve through a
bounded revision or rejection, never permission to erase a preservation regression. A revision may
remove, narrow, or rewrite implicated channels to address the observed failure while retaining other
useful evidence-grounded content. Choosing `revise_delta` adds one bounded revision to the open
portfolio; it does not reserve the next iteration. A tested revision must be accepted or rejected,
never revised again. Choose `reject_delta` when the evidence instead warrants switching to another behavior problem. Do
not revise a changed channel to chase failures that both Analyzers classify as non-attributed or
unresolved.
For `revise_delta`, include an Editor brief with id, objective, channel_plan, and
validation.local_behavior_checks. Describe the bounded repair; do not write harness files or a
manifest_delta. The next iteration's Harness Editor owns concrete native changes. Omit
revision_candidate for accept/reject.

Return exactly:
{"decision":"accept_delta|reject_delta|revise_delta|confirm_delta|replan_problem","selected_version":"tested child or direct parent","rationale":"...","evidence":{"recovered_task_ids":["..."],"uncertain_recovery_task_ids":["..."],"preserved_task_ids":["..."],"attributable_regression_task_ids":["..."],"unresolved_findings":["..."]},"revision_candidate":{"id":"...","objective":"...","channel_plan":[{"channel_id":"...","operation":"...","experience_ids":["..."],"rationale":"..."}],"validation":{"local_behavior_checks":["..."]}},"budget_disposition":{"remaining_creations_after_this_decision":0,"minimum_next_rollout_creations":10,"rollout_possible":false,"minimum_next_iteration_creations":19,"iteration_possible":false}}
""".strip()


@dataclass(frozen=True)
class MainDecision:
    output: Mapping[str, Any]
    output_path: str
    harness_version: str


class CandidateMaterializationError(RuntimeError):
    def __init__(self, *, candidate_id: str, reason: str):
        self.candidate_id = str(candidate_id)
        self.reason = str(reason)
        super().__init__(
            f"candidate {self.candidate_id!r} could not be materialized: {self.reason}"
        )


def validate_candidate_channel_combination(channel_ids: set[str]) -> None:
    global_channels = set(channel_ids) & GLOBAL_INSTRUCTION_CHANNELS
    if len(global_channels) > 1:
        raise ValueError(
            "candidate may change at most one global instruction channel: "
            + ",".join(sorted(global_channels))
        )


def _final_review_attempts(decision_output: Mapping[str, Any] | None) -> range:
    return range(2) if decision_output is None else range(0)


def selectable_portfolio(
    portfolio: Sequence[Mapping[str, Any]],
    *,
    attempted_candidate_ids: Sequence[str],
    pending_revision_candidate_ids: Sequence[str] = (),
) -> list[Mapping[str, Any]]:
    attempted = {str(item) for item in attempted_candidate_ids}
    return [
        item
        for item in portfolio
        if str((item.get("candidate") or {}).get("id") or "") not in attempted
    ]


def defer_failure_only_portfolio(
    portfolio: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    """Keep failure-only hypotheses available after supported options are exhausted."""

    candidates = list(portfolio)
    preferred = [
        item
        for item in candidates
        if str(item.get("side") or "") in {"revision", "incumbent"}
        or str((item.get("evidence_profile") or {}).get("support_tier") or "")
        != "failure_only"
    ]
    return preferred or candidates


def promotion_headroom_portfolio(
    portfolio: Sequence[Mapping[str, Any]],
    *,
    baseline_task_outcomes: Mapping[str, str] | None = None,
) -> list[Mapping[str, Any]]:
    """Admit only hypotheses that can convert a recorded TRAIN failure."""

    task_outcomes = baseline_task_outcomes or {}
    admitted: list[Mapping[str, Any]] = []
    for raw_item in portfolio:
        item = dict(raw_item)
        profile = item.get("evidence_profile") or {}
        prior = item.get("prior_train_evidence") or {}
        conversion_tasks = sorted(
            {
                str(task_id)
                for task_id in profile.get("all_failed_task_ids") or []
                if str(task_id)
            }
            | {
                str(task_id)
                for task_id in prior.get("recovered_task_ids") or []
                if str(task_id)
            }
            | {
                str(task_id)
                for task_id in item.get("declared_conversion_task_ids") or []
                if str(task_id)
            }
        )
        if str(item.get("side") or "") == "reusable":
            conversion_tasks = sorted(
                set(conversion_tasks)
                | {
                    str(task_id)
                    for task_id in profile.get("all_passed_task_ids") or []
                    if str(task_outcomes.get(str(task_id)) or "") == "fail"
                }
            )
        if not conversion_tasks:
            continue
        item["conversion_task_ids"] = conversion_tasks
        admitted.append(item)
    return admitted


def assign_rollout_roles(
    *,
    task_ids: Sequence[str],
    conversion_task_ids: Sequence[str],
    direct_task_ids: Sequence[str],
    baseline_task_outcomes: Mapping[str, str],
) -> dict[str, list[str]]:
    """Assign every requested TRAIN task one controller-owned validation role."""

    requested = [str(item) for item in task_ids]
    conversions = {str(item) for item in conversion_task_ids}
    direct = {str(item) for item in direct_task_ids}
    roles = {
        "conversion_tasks": [],
        "positive_controls": [],
        "preservation_canaries": [],
        "diagnostic_tasks": [],
    }
    for task_id in requested:
        outcome = str(baseline_task_outcomes.get(task_id) or "fail")
        if task_id in conversions:
            role = "conversion_tasks"
        elif outcome == "pass" and task_id in direct:
            role = "positive_controls"
        elif outcome == "pass":
            role = "preservation_canaries"
        else:
            role = "diagnostic_tasks"
        roles[role].append(task_id)
    return roles


def prioritize_incumbent_controls(
    portfolio: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    return sorted(
        portfolio,
        key=lambda item: 0 if str(item.get("side") or "") == "incumbent" else 1,
    )


def canonicalize_main_decision(output: Mapping[str, Any]) -> Mapping[str, Any]:
    normalized = dict(output)
    raw_plan = normalized.get("exploration_plan")
    if isinstance(raw_plan, Mapping):
        plan = dict(raw_plan)
        chosen = str(plan.get("chosen_problem_id") or "")
        open_ids = [str(item) for item in plan.get("open_problem_ids") or []]
        if chosen and chosen not in open_ids:
            plan["open_problem_ids"] = [chosen, *open_ids]
        normalized["exploration_plan"] = plan
    if isinstance(output, dict):
        output.clear()
        output.update(normalized)
        return output
    return normalized


def validate_main_decision(
    output: Mapping[str, Any],
    *,
    train_task_ids: Sequence[str],
    candidate_evidence: Mapping[str, Sequence[str]],
    candidate_direct_tasks: Mapping[str, Sequence[str]] | None = None,
    candidate_conversion_tasks: Mapping[str, Sequence[str]] | None = None,
    candidate_sides: Mapping[str, str] | None = None,
    evidence_to_task: Mapping[str, str],
    baseline_task_outcomes: Mapping[str, str] | None = None,
    min_rollout_tasks: int = MIN_STANDARD_ROLLOUT_TASKS,
    max_rollout_tasks: int | None = None,
) -> None:
    if output.get("decision") != "materialize_and_rollout":
        raise ValueError("Main Agent must materialize and request rollout")
    candidate_id = str(output.get("selected_candidate_id") or "")
    if candidate_id not in candidate_evidence:
        raise ValueError("Main Agent selected an unavailable candidate")
    plan = output.get("exploration_plan")
    if not isinstance(plan, Mapping):
        raise ValueError("Main Agent requires an exploration_plan")
    open_problem_ids = [str(item) for item in plan.get("open_problem_ids") or []]
    chosen_problem_id = str(plan.get("chosen_problem_id") or "")
    if not open_problem_ids or not chosen_problem_id:
        raise ValueError("exploration_plan requires open and chosen problem IDs")
    if chosen_problem_id not in open_problem_ids:
        raise ValueError("chosen problem must be listed as open")
    if not str(plan.get("budget_strategy") or "").strip():
        raise ValueError("exploration_plan requires a budget strategy")
    if not str(plan.get("turning_point") or "").strip():
        raise ValueError("exploration_plan requires a turning point")
    request = output.get("rollout_request")
    if not isinstance(request, Mapping):
        raise ValueError("Main Agent requires rollout_request")
    task_ids = [str(item) for item in request.get("task_ids") or []]
    minimum = int(min_rollout_tasks)
    if len(task_ids) < minimum or len(task_ids) != len(set(task_ids)):
        raise ValueError(f"rollout requires at least {minimum} distinct task IDs")
    if set(task_ids) - set(train_task_ids):
        raise ValueError("rollout selected a task outside TRAIN")
    if max_rollout_tasks is not None and len(task_ids) > int(max_rollout_tasks):
        raise ValueError("rollout request exceeds the complete-iteration task limit")
    evidence_tasks = {
        str(evidence_to_task[ref])
        for ref in candidate_evidence[candidate_id]
        if ref in evidence_to_task
    }
    evidence_tasks.update(
        str(task_id)
        for task_id in (candidate_direct_tasks or {}).get(candidate_id, ())
        if str(task_id) in set(train_task_ids)
    )
    if evidence_tasks and not (set(task_ids) & evidence_tasks):
        raise ValueError("rollout tasks lack primary-problem evidence support")
    if candidate_conversion_tasks is not None:
        conversion_tasks = {
            str(task_id)
            for task_id in candidate_conversion_tasks.get(candidate_id, ())
        }
        if not conversion_tasks or not (set(task_ids) & conversion_tasks):
            raise ValueError(
                "rollout tasks must include a declared baseline conversion task"
            )
    if baseline_task_outcomes is not None:
        direct_tasks = set(
            str(task_id)
            for task_id in (candidate_direct_tasks or {}).get(candidate_id, ())
        ) | evidence_tasks
        expected_roles = assign_rollout_roles(
            task_ids=task_ids,
            conversion_task_ids=(candidate_conversion_tasks or {}).get(
                candidate_id, ()
            ),
            direct_task_ids=direct_tasks,
            baseline_task_outcomes=baseline_task_outcomes,
        )
        roles = request.get("task_roles")
        if not isinstance(roles, Mapping) or {
            str(key): [str(item) for item in value]
            for key, value in roles.items()
            if isinstance(value, list)
        } != expected_roles:
            raise ValueError("rollout task roles differ from controller assignment")
    if not request.get("rationale") or not request.get("local_success_criteria"):
        raise ValueError(
            "rollout request requires rationale and local success criteria"
        )
    if "repeats" in request:
        raise ValueError("rollout repeats are fixed by the controller")


def build_exploration_status(
    *,
    available: Sequence[Mapping[str, Any]],
    iteration_history: Sequence[Mapping[str, Any]],
    evidence_to_task: Mapping[str, str],
    evidence_outcomes: Mapping[str, str] | None = None,
    budget_status: Mapping[str, Any],
    rollout_task_limit: int,
    rollout_budget_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compact controller state for budget-aware issue exploration."""

    outcomes = {
        str(ref): str(outcome) for ref, outcome in (evidence_outcomes or {}).items()
    }
    revision_signals = {
        str(record.get("revision_candidate_id")): {
            "attributed_recovery_count": len(
                (record.get("review_evidence") or {}).get("recovered_task_ids") or []
            ),
            "attributable_regression_count": len(
                (record.get("review_evidence") or {}).get(
                    "attributable_regression_task_ids"
                )
                or []
            ),
        }
        for record in iteration_history
        if str(record.get("revision_candidate_id") or "")
    }
    open_problems = []
    for item in available:
        candidate = item["candidate"]
        candidate_id = str(candidate["id"])
        evidence_tasks = sorted(
            {
                str(evidence_to_task[ref])
                for ref in item.get("evidence_refs") or []
                if ref in evidence_to_task
            }
            | {str(task_id) for task_id in item.get("direct_task_ids") or []}
        )
        plans = candidate.get("channel_plan") or []
        manifest = candidate.get("manifest_delta") or {}
        file_count = len(manifest.get("files") or [])
        channel_ids = sorted({str(plan.get("channel_id") or "") for plan in plans})
        side = str(item.get("side") or "")
        baseline_evidence = dict(
            item.get("evidence_profile")
            or _baseline_evidence_summary(
                evidence_refs=item.get("evidence_refs") or [],
                evidence_to_task=evidence_to_task,
                evidence_outcomes=outcomes,
            )
        )
        risk_flags = []
        if len(channel_ids) > 1:
            risk_flags.append("multi_channel_delta")
        if len(item.get("experience_ids") or []) > 4:
            risk_flags.append("large_experience_batch")
        if file_count > 1:
            risk_flags.append("multi_file_delta")
        if not evidence_tasks:
            risk_flags.append("no_direct_evidence_task")
        if baseline_evidence["support_tier"] == "failure_only":
            risk_flags.append("failure_only_without_passing_contrast")
        if (
            side == "reusable"
            and baseline_evidence["trial_count"]
            and not baseline_evidence["passed_trial_count"]
        ):
            risk_flags.append("reusable_without_passing_evidence_support")
        if (
            side == "reusable"
            and baseline_evidence["trial_count"]
            and not baseline_evidence["failed_trial_count"]
        ):
            risk_flags.append("no_observed_failure_headroom")
        revision_signal = (
            revision_signals.get(candidate_id) if side == "revision" else None
        )
        if revision_signal and not revision_signal["attributed_recovery_count"]:
            risk_flags.append("revision_without_positive_parent_evidence")
        problem = {
            "problem_id": candidate_id,
            "side": side,
            "objective": str(candidate.get("objective") or ""),
            "experience_count": len(item.get("experience_ids") or []),
            "evidence_task_ids": evidence_tasks,
            "baseline_evidence": baseline_evidence,
            "changed_channel_count": len(channel_ids),
            "changed_file_count": file_count,
            "risk_flags": risk_flags,
        }
        if item.get("prior_train_evidence"):
            problem["prior_train_evidence"] = dict(item["prior_train_evidence"])
        if revision_signal is not None:
            problem["revision_parent_signal"] = revision_signal
        open_problems.append(problem)

    recent_results = []
    for record in iteration_history[-4:]:
        evidence = record.get("review_evidence") or {}
        metrics = record.get("rollout_metrics") or {}
        recent_results.append(
            {
                "problem_id": str(
                    record.get("candidate_id")
                    or record.get("revision_candidate_id")
                    or ""
                ),
                "candidate_version": str(record.get("candidate_version") or ""),
                "review_decision": str(record.get("review_decision") or ""),
                "selected_version": str(record.get("selected_version") or ""),
                "rollout_task_count": len(record.get("rollout_task_ids") or []),
                "pass_at_1": metrics.get("pass_at_1"),
                "pass_at_2": metrics.get("pass_at_2"),
                "recovered_count": len(evidence.get("recovered_task_ids") or []),
                "attributable_regression_count": len(
                    evidence.get("attributable_regression_task_ids") or []
                ),
                "revision_candidate_id": record.get("revision_candidate_id"),
                "evaluation_mode": str(record.get("evaluation_mode") or "standard"),
                "promotion_eligible": bool(record.get("promotion_eligible", True)),
            }
        )
    hypothesis_attempts: dict[str, list[dict[str, int]]] = {}
    for record in iteration_history:
        origin = str(
            record.get("origin_candidate_id") or record.get("candidate_id") or ""
        )
        if not origin:
            continue
        evidence = record.get("review_evidence") or {}
        hypothesis_attempts.setdefault(origin, []).append(
            {
                "recovered_count": len(evidence.get("recovered_task_ids") or []),
                "regression_count": len(
                    evidence.get("attributable_regression_task_ids") or []
                ),
            }
        )
    hypothesis_history = []
    for origin, attempts in hypothesis_attempts.items():
        latest = attempts[-1]
        previous = attempts[-2] if len(attempts) > 1 else None
        hypothesis_history.append(
            {
                "origin_candidate_id": origin,
                "attempt_count": len(attempts),
                "latest_recovered_count": latest["recovered_count"],
                "latest_attributable_regression_count": latest["regression_count"],
                "latest_revision_improved": (
                    None
                    if previous is None
                    else (
                        latest["recovered_count"] > previous["recovered_count"]
                        or latest["regression_count"] < previous["regression_count"]
                    )
                ),
            }
        )
    open_side_counts = {
        side: sum(1 for item in open_problems if item["side"] == side)
        for side in ("reusable", "adjustment", "revision", "incumbent")
    }
    remaining = int(budget_status.get("remaining") or 0)
    legacy_budget_summary = {
        "remaining": remaining,
        "rollout_task_limit": int(rollout_task_limit),
        "minimum_complete_iteration_creations": MIN_CANDIDATE_ITERATION_CREATIONS,
        "compact_iteration_creations": iteration_creation_cost(
            DEFAULT_EXPLORATION_ROLLOUT_TASKS
        ),
        "affordable_minimum_iterations": max(
            0, remaining - ITERATION_RETRY_BUFFER_CREATIONS
        )
        // MIN_CANDIDATE_ITERATION_CREATIONS,
        "affordable_compact_iterations": (
            max(0, remaining - ITERATION_RETRY_BUFFER_CREATIONS)
            // iteration_creation_cost(DEFAULT_EXPLORATION_ROLLOUT_TASKS)
        ),
        "small_batch_default_task_limit": DEFAULT_EXPLORATION_ROLLOUT_TASKS,
    }
    budget_summary = (
        {"remaining": remaining, **dict(rollout_budget_plan)}
        if rollout_budget_plan is not None
        else legacy_budget_summary
    )
    return {
        "budget": budget_summary,
        "policy": {
            "prefer_small_batches": len(open_problems) > 1,
            "switch_problem_when": [
                "the candidate has attributable preservation regressions",
                "the rollout shows no attributed recovery for the chosen problem",
                "a narrow revision is unaffordable or would expand scope",
                "the latest comparable revision does not improve recovery or regression evidence",
            ],
            "scale_up_when": [
                "a small rollout shows attributed recovery",
                "preservation checks remain stable",
                "remaining budget still covers final review or another complete iteration",
            ],
        },
        "candidate_type_counts": open_side_counts,
        "open_problems": open_problems,
        "recent_results": recent_results,
        "hypothesis_history": hypothesis_history,
    }


def _baseline_evidence_summary(
    *,
    evidence_refs: Sequence[str],
    evidence_to_task: Mapping[str, str],
    evidence_outcomes: Mapping[str, str],
) -> dict[str, Any]:
    by_task: dict[str, list[str]] = {}
    for raw_ref in evidence_refs:
        ref = str(raw_ref)
        task_id = evidence_to_task.get(ref)
        outcome = evidence_outcomes.get(ref)
        if task_id is None or outcome not in {"pass", "fail"}:
            continue
        by_task.setdefault(str(task_id), []).append(str(outcome))
    flat = [outcome for values in by_task.values() for outcome in values]
    failed = sum(outcome == "fail" for outcome in flat)
    mixed_task_ids = sorted(
        task_id
        for task_id, values in by_task.items()
        if "pass" in values and "fail" in values
    )
    passed = len(flat) - failed
    support_tier = (
        "within_task_contrast"
        if mixed_task_ids
        else (
            "mixed_evidence"
            if passed and failed
            else "success_only" if passed else "failure_only" if failed else "unknown"
        )
    )
    return {
        "trial_count": len(flat),
        "failed_trial_count": failed,
        "passed_trial_count": passed,
        "task_count": len(by_task),
        "support_tier": support_tier,
        "failure_density": (failed / len(flat) if flat else None),
        "all_failed_task_ids": sorted(
            task_id
            for task_id, values in by_task.items()
            if values and all(value == "fail" for value in values)
        ),
        "mixed_task_ids": mixed_task_ids,
        "all_passed_task_ids": sorted(
            task_id
            for task_id, values in by_task.items()
            if values and all(value == "pass" for value in values)
        ),
    }


def validate_final_decision(
    output: Mapping[str, Any],
    *,
    candidate_version: str,
    task_ids: Sequence[str],
    reusable: Mapping[str, Any],
    adjustment: Mapping[str, Any],
    budget_status: Mapping[str, Any],
    base_version: str = "v0",
    remaining_after_decision: int | None = None,
    tested_candidate: Mapping[str, Any] | None = None,
    revision_channel_ids: set[str] | None = None,
    rollout_metrics: Mapping[str, Any] | None = None,
    reference_rollout_metrics: Mapping[str, Any] | None = None,
    promotion_metric: str | None = None,
    require_primary_metric_improvement: bool = True,
    promotion_eligible: bool = True,
) -> None:
    decision = str(output.get("decision") or "")
    selected = str(output.get("selected_version") or "")
    expected = candidate_version if decision == "accept_delta" else base_version
    if (
        decision
        not in {
            "accept_delta",
            "reject_delta",
            "revise_delta",
            "confirm_delta",
            "replan_problem",
        }
        or selected != expected
    ):
        raise ValueError(
            "review Main Agent must choose the tested candidate or its parent"
        )
    if decision == "accept_delta" and not promotion_eligible:
        raise ValueError("a residual probe is not promotion eligible")
    unclassified_channels = {
        str(item.get("channel_id") or "")
        for item in (tested_candidate or {}).get("channel_diffs") or []
        if str(item.get("channel_id") or "").startswith("workspace_file:")
    }
    if decision == "accept_delta" and unclassified_channels:
        raise ValueError(
            "candidate acceptance requires removing unclassified workspace changes"
        )
    if not str(output.get("rationale") or "").strip():
        raise ValueError("final Main Agent requires a rationale")
    evidence = output.get("evidence")
    if not isinstance(evidence, Mapping):
        raise ValueError("final Main Agent requires evidence")
    recovered = {str(item) for item in evidence.get("recovered_task_ids") or []}
    preserved = {str(item) for item in evidence.get("preserved_task_ids") or []}
    regressions = {
        str(item) for item in evidence.get("attributable_regression_task_ids") or []
    }
    if (recovered | preserved | regressions) - set(str(item) for item in task_ids):
        raise ValueError("final evidence references an unrolled task")
    expected_recovered = _attributable_positive_task_ids(adjustment)
    expected_uncertain = uncertain_recovery_task_ids(adjustment)
    expected_preserved = {
        str(item) for item in reusable["preservation"]["preserved_task_ids"]
    }
    expected_regressions = {
        str(item["task_id"])
        for item in reusable["preservation"]["attributable_regressions"]
    }
    if (
        recovered != expected_recovered
        or preserved != expected_preserved
        or regressions != expected_regressions
    ):
        raise ValueError("final evidence differs from reusable Analyzer")
    if decision == "accept_delta" and expected_regressions:
        raise ValueError("candidate with attributable regressions cannot be submitted")
    if decision == "accept_delta" and not expected_recovered:
        raise ValueError("candidate acceptance requires attributable positive evidence")
    uncertain = {
        str(item) for item in evidence.get("uncertain_recovery_task_ids") or []
    }
    if uncertain != expected_uncertain:
        raise ValueError("final uncertain recovery evidence differs from Analyzer")
    if (
        decision == "accept_delta"
        and promotion_metric is not None
        and require_primary_metric_improvement
    ):
        if (rollout_metrics or {}).get("paired_infrastructure_valid") is False:
            raise ValueError(
                "candidate acceptance requires infrastructure-valid paired evidence"
            )
        metric = normalize_promotion_metric(promotion_metric)
        candidate_value = _required_metric(rollout_metrics, metric, side="candidate")
        reference_value = _required_metric(
            reference_rollout_metrics, metric, side="reference"
        )
        if candidate_value <= reference_value:
            raise ValueError(f"candidate acceptance requires positive {metric} delta")
    unresolved = evidence.get("unresolved_findings")
    if not isinstance(unresolved, list):
        raise ValueError("final decision must preserve unresolved findings")
    has_revision = decision == "revise_delta" and isinstance(
        output.get("revision_candidate"), Mapping
    )
    has_replan = decision == "replan_problem" and isinstance(
        adjustment.get("replan_candidate"), Mapping
    )
    if (
        adjustment["primary_problem"]["recommendation"] == "refine"
        and not unresolved
        and not (has_revision or has_replan)
    ):
        raise ValueError("final decision dropped a requested refinement")
    disposition = output.get("budget_disposition")
    if not isinstance(disposition, Mapping):
        raise ValueError("final Main Agent requires budget disposition")
    remaining_after = (
        int(remaining_after_decision)
        if remaining_after_decision is not None
        else int(budget_status["remaining"]) - 1
    )
    if (
        int(disposition.get("remaining_creations_after_this_decision", -1))
        != remaining_after
    ):
        raise ValueError("final Main Agent changed the creation budget")
    if (
        int(disposition.get("minimum_next_rollout_creations", -1))
        != MIN_ROLLOUT_CREATIONS
    ):
        raise ValueError(
            "next rollout minimum must remain five tasks times the training repeat count"
        )
    if bool(disposition.get("rollout_possible")) != (
        remaining_after >= MIN_ROLLOUT_CREATIONS
    ):
        raise ValueError("final Main Agent misreported rollout feasibility")
    if int(disposition.get("minimum_next_iteration_creations", -1)) != (
        MIN_CANDIDATE_ITERATION_CREATIONS
    ):
        raise ValueError("next iteration minimum does not cover every required module")
    if bool(disposition.get("iteration_possible")) != (
        remaining_after >= MIN_CANDIDATE_ITERATION_CREATIONS
    ):
        raise ValueError("final Main Agent misreported iteration feasibility")
    primary = adjustment["primary_problem"]
    if decision == "confirm_delta":
        if require_primary_metric_improvement:
            raise ValueError("confirmation evidence cannot request another confirmation")
        if expected_recovered or expected_regressions or not expected_uncertain:
            raise ValueError(
                "confirm_delta requires only an uncertain recorded pass gain"
            )
    if decision == "replan_problem":
        if not isinstance(adjustment.get("replan_candidate"), Mapping):
            raise ValueError("replan_problem requires a post-Analyzer candidate")
        if remaining_after < MIN_CANDIDATE_ITERATION_CREATIONS:
            raise ValueError("replan_problem requires budget for another iteration")
    if (
        decision == "accept_delta"
        and remaining_after < MIN_CANDIDATE_ITERATION_CREATIONS
        and _localized_followup_task_ids(adjustment)
    ):
        raise ValueError(
            "budget-exhausted review cannot accept a candidate with unresolved "
            "failures attributed to the changed channel"
        )
    revision = output.get("revision_candidate")
    if decision != "revise_delta":
        if revision is not None:
            raise ValueError(
                "non-revision decision must not include a revision candidate"
            )
        return
    if remaining_after < MIN_CANDIDATE_ITERATION_CREATIONS:
        raise ValueError("revision requires budget for another complete iteration")
    if not isinstance(tested_candidate, Mapping):
        raise ValueError("revision validation requires the tested candidate")
    if str(tested_candidate.get("portfolio_side") or "") == "revision":
        raise ValueError("a tested revision must be accepted or rejected")
    if not isinstance(revision, Mapping):
        raise ValueError("revise decision requires a complete revision candidate")
    localized_revision_failure = bool(expected_regressions) or bool(
        _localized_followup_task_ids(adjustment)
    )
    if not localized_revision_failure:
        raise ValueError("revision requires a failure localized to the changed channel")
    original_plans = tested_candidate.get("channel_diffs") or []
    experience_ids = {
        str(item)
        for plan in original_plans
        for item in plan.get("experience_ids") or []
    }
    channel_ids = (
        set(revision_channel_ids)
        if revision_channel_ids is not None
        else {str(plan.get("channel_id") or "") for plan in original_plans}
    )
    _validate_candidate(
        revision,
        experience_ids=experience_ids,
        channel_ids=channel_ids,
    )
    revision_delta = revision.get("manifest_delta")
    tested_delta = tested_candidate.get("manifest_delta")
    if (
        isinstance(revision_delta, Mapping)
        and revision_delta
        and isinstance(tested_delta, Mapping)
        and content_digest(revision_delta) == content_digest(tested_delta)
    ):
        raise ValueError("revision candidate must change the tested manifest")


def _localized_followup_task_ids(
    adjustment: Mapping[str, Any],
) -> set[str]:
    primary = adjustment.get("primary_problem") or {}
    return {
        str(item.get("task_id") or "")
        for item in primary.get("task_assessments") or []
        if isinstance(item, Mapping)
        and str(item.get("status") or "") in {"regressed", "mixed", "still_failing"}
        and str(item.get("relation") or "") == "attributed"
        and str(item.get("task_id") or "")
    }


def canonicalize_final_decision(
    output: Mapping[str, Any],
    *,
    candidate_version: str,
    base_version: str,
    reusable: Mapping[str, Any],
    adjustment: Mapping[str, Any],
    tested_candidate: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    if isinstance(output, dict):
        decision = str(output.get("decision") or "")
        if decision == "accept_delta":
            output["selected_version"] = str(candidate_version)
        elif decision in {
            "reject_delta",
            "revise_delta",
            "confirm_delta",
            "replan_problem",
        }:
            output["selected_version"] = str(base_version)
        if (
            decision == "revise_delta"
            and isinstance(output.get("revision_candidate"), Mapping)
            and isinstance(output["revision_candidate"].get("manifest_delta"), Mapping)
        ):
            _canonicalize_revision_manifest_delta(output["revision_candidate"])
            allowed_experience_ids = sorted(
                {
                    str(item)
                    for plan in (
                        tested_candidate.get("channel_diffs") or []
                        if isinstance(tested_candidate, Mapping)
                        else []
                    )
                    for item in plan.get("experience_ids") or []
                }
            )
            holder = canonicalize_analyzer_output(
                {
                    "coverage": {"experience_ids": allowed_experience_ids},
                    "candidates": [dict(output["revision_candidate"])],
                }
            )
            revision = dict(holder["candidates"][0])
            revision["id"] = f"revision-{candidate_version}"
            if isinstance(tested_candidate, Mapping):
                source_ids = tested_candidate.get("source_candidate_ids") or []
                if source_ids:
                    revision["origin_candidate_id"] = str(source_ids[0])
            output["revision_candidate"] = revision
        elif decision != "revise_delta":
            output.pop("revision_candidate", None)
    evidence = output.get("evidence")
    if not isinstance(evidence, dict):
        return output
    evidence["recovered_task_ids"] = sorted(_attributable_positive_task_ids(adjustment))
    evidence["uncertain_recovery_task_ids"] = sorted(
        uncertain_recovery_task_ids(adjustment)
    )
    evidence["preserved_task_ids"] = sorted(
        str(item) for item in reusable["preservation"]["preserved_task_ids"]
    )
    evidence["attributable_regression_task_ids"] = sorted(
        str(item["task_id"])
        for item in reusable["preservation"]["attributable_regressions"]
    )
    return output


def _attributable_positive_task_ids(
    adjustment: Mapping[str, Any],
) -> set[str]:
    result = set()
    for item in adjustment["primary_problem"]["task_assessments"]:
        if str(item.get("status") or "") not in {"recovered", "stable_success"}:
            continue
        if str(item.get("relation") or "") != "attributed":
            continue
        summary = item.get("outcome_summary")
        if isinstance(summary, Mapping) and int(
            summary.get("candidate_pass_count") or 0
        ) <= int(summary.get("reference_pass_count") or 0):
            continue
        result.add(str(item["task_id"]))
    return result


def uncertain_recovery_task_ids(
    adjustment: Mapping[str, Any],
) -> set[str]:
    """Return recorded pass gains whose causal relation still needs confirmation."""

    result: set[str] = set()
    primary = adjustment.get("primary_problem") or {}
    for item in primary.get("task_assessments") or []:
        if str(item.get("status") or "") not in {"recovered", "stable_success"}:
            continue
        if str(item.get("relation") or "") != "possibly_related":
            continue
        summary = item.get("outcome_summary") or {}
        if int(summary.get("candidate_pass_count") or 0) <= int(
            summary.get("reference_pass_count") or 0
        ):
            continue
        result.add(str(item.get("task_id") or ""))
    return {item for item in result if item}


def _required_metric(
    metrics: Mapping[str, Any] | None, metric: str, *, side: str
) -> float:
    if not isinstance(metrics, Mapping):
        raise ValueError(f"{side} rollout metrics are missing {metric}")
    if metric == "pass_at_1" and "estimated_pass_at_1" in metrics:
        value = float(metrics["estimated_pass_at_1"])
    elif metric == "pass_at_1" and "trial_success_rate" in metrics:
        value = float(metrics["trial_success_rate"])
    elif metric in metrics:
        value = float(metrics[metric])
    else:
        raise ValueError(f"{side} rollout metrics are missing {metric}")
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{side} rollout metric {metric} is outside [0, 1]")
    return value


def deterministic_reject_decision(
    *,
    base_version: str,
    reusable: Mapping[str, Any],
    adjustment: Mapping[str, Any],
    remaining: int,
    failure_reason: str,
) -> dict[str, Any]:
    regressions = [
        str(item["task_id"])
        for item in reusable["preservation"]["attributable_regressions"]
    ]
    preserved = [str(item) for item in reusable["preservation"]["preserved_task_ids"]]
    payload = {
        "decision": "reject_delta",
        "selected_version": str(base_version),
        "rationale": (
            "Keep the current champion because the proposed promotion did not satisfy "
            f"the deterministic admission gate: {str(failure_reason)}"
        ),
        "evidence": {
            "recovered_task_ids": sorted(_attributable_positive_task_ids(adjustment)),
            "preserved_task_ids": sorted(preserved),
            "attributable_regression_task_ids": sorted(regressions),
            "unresolved_findings": [
                "The Main Agent did not produce a valid admissible decision; the "
                "controller retained the direct parent."
            ],
        },
    }
    return normalize_budget_disposition(
        payload, remaining_after_decision=int(remaining)
    )


def _canonicalize_revision_manifest_delta(candidate: Mapping[str, Any]) -> None:
    if not isinstance(candidate, dict):
        return
    delta = candidate.get("manifest_delta")
    if not isinstance(delta, dict):
        return
    instructions = _normalize_instruction_entries(delta.get("instructions") or [])
    tool_desc_patches = dict(delta.get("tool_desc_patches") or {})
    files = []
    for raw_file in delta.get("files") or []:
        if not isinstance(raw_file, Mapping):
            files.append(raw_file)
            continue
        path = str(raw_file.get("path") or "").strip()
        content = raw_file.get("content")
        if path in {
            "instructions",
            "instructions_rules",
            "instructions_rules.md",
            ".opencode/instructions_rules.md",
        } or path.startswith("instructions/"):
            if isinstance(content, list):
                instructions.extend(_normalize_instruction_entries(content))
            elif str(content or "").strip():
                instructions.extend(_normalize_instruction_entries([content]))
            continue
        if path.rsplit("/", 1)[-1].lower() in {
            "tool_desc_patches",
            "tool_desc_patches.json",
            "tool_description_patches",
            "tool_description_patches.json",
        }:
            parsed = content
            if isinstance(content, str):
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError:
                    parsed = None
            if isinstance(parsed, Mapping):
                tool_desc_patches = _merge_tool_description_patches(
                    tool_desc_patches,
                    parsed,
                )
                continue
        files.append(raw_file)
    if instructions:
        delta["instructions"] = instructions
    if tool_desc_patches:
        delta["tool_desc_patches"] = tool_desc_patches
    if files:
        delta["files"] = files
    else:
        delta.pop("files", None)


def _merge_tool_description_patches(
    existing: Mapping[str, Any], incoming: Mapping[str, Any]
) -> dict[str, Any]:
    merged = dict(existing)
    for raw_tool, raw_patch in incoming.items():
        tool = str(raw_tool)
        if not isinstance(raw_patch, Mapping):
            merged[tool] = raw_patch
            continue
        existing_patch = merged.get(tool)
        patch = dict(existing_patch) if isinstance(existing_patch, Mapping) else {}
        patch.update(dict(raw_patch))
        if (
            isinstance(existing_patch, Mapping)
            and isinstance(existing_patch.get("params"), Mapping)
            and isinstance(raw_patch.get("params"), Mapping)
        ):
            patch["params"] = {
                **dict(existing_patch["params"]),
                **dict(raw_patch["params"]),
            }
        merged[tool] = patch
    return merged


def _normalize_instruction_entries(raw_entries: Sequence[Any]) -> list[str]:
    normalized: list[str] = []
    for raw_entry in raw_entries:
        text = str(raw_entry or "").strip()
        if not text:
            continue
        parsed = None
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
        if isinstance(parsed, list):
            normalized.extend(str(item).strip() for item in parsed if str(item).strip())
        else:
            normalized.append(text)
    return normalized
