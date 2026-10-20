"""Vendored verbatim from HarnessLens 369a5c8:harnesslens/benchmarks/task_data.py (see VENDORED.md)."""
from __future__ import annotations



def evaluation_contract(outcome_authority: str) -> dict[str, str]:
    authority = str(outcome_authority)
    if authority == "authoritative":
        interpretation = (
            "Recorded pass/fail is authoritative for task completion. Trajectories "
            "explain the mechanism but cannot relabel a failed trial as successful."
        )
    elif authority == "behavioral":
        interpretation = (
            "Recorded pass/fail is supporting whole-task metadata. Preserve explicit "
            "visible completion disagreements for downstream review."
        )
    else:
        raise ValueError(f"unsupported outcome authority: {authority}")
    return {
        "outcome_authority": authority,
        "interpretation": interpretation,
    }
