"""Vendor HarnessLens's prompt constants and pure helpers verbatim (plan §9.1 "Deploy").

  venv-hl/bin/python -I vendor_extract.py CLONE_DIR OUT_DIR

For each source module, copies the named top-level definitions (functions, classes, constants) and
everything they reference inside the vendored set (transitive closure), byte-for-byte from the pinned
clone, in source order. Imports between vendored modules are rewritten to the vendor package; any name
that resolves to a non-vendored module is listed in VENDORED.md as external and must be provided by
hl_vendor/_external.py (only names on code paths the port never takes). Writes VENDORED.md with the source
path, commit and sha256 of every source file.
"""

from __future__ import annotations

import ast
import hashlib
import subprocess
import sys
from pathlib import Path

ROOTS = {
    "harnesslens/harnesses/runner.py": ["parse_json_object"],
    "harnesslens/core/train_protocol.py": [],
    "harnesslens/evolution/discovery.py": ["TASK_EXPLORER_SYSTEM", "HARNESS_QUERY_SYSTEM", "validate_task_explorer"],
    "harnesslens/evolution/experience.py": [
        "EXPERIENCE_SYSTEM", "EXPERIENCE_SYNTHESIS_SYSTEM", "MAX_TASKS_PER_EXPERIENCE_JOB", "COMPARISON_SYSTEM",
        "COMPARISON_REVIEW_SYSTEM", "_clip_text", "_compact_value", "_compact_tool_result", "_select_user_messages",
        "normalize_experience", "_normalize_in_place", "_ensure_authoritative_failure_dispositions", "_draft_catalog",
        "validate_experience_merge_plan", "canonicalize_experience_merge_plan", "materialize_experience_merge_plan",
        "_comparison_passage", "validate_comparison", "canonicalize_comparison", "validate_experience",
        "_outcome_authority", "_authoritative_comparison_status", "_comparison_outcome_summary", "_slug"],
    "harnesslens/evolution/analyzer.py": [
        "MAX_REUSABLE_COMPILATION_GROUPS", "MAX_ADJUSTMENT_ANALYSIS_GROUPS", "POST_ANALYZER_OUTPUT_LIMIT",
        "REUSABLE_PLANNER_SYSTEM", "REUSABLE_ANALYZER_SYSTEM", "ADJUSTMENT_ANALYZER_SYSTEM",
        "POST_REUSABLE_ANALYZER_SYSTEM", "POST_ADJUSTMENT_ANALYZER_SYSTEM", "validate_reusable_plan",
        "combine_reusable_outputs", "partition_adjustment_experiences", "combine_adjustment_outputs",
        "validate_analyzer_output", "analyzer_retry_context", "canonicalize_analyzer_output", "analyzer_candidates",
        "build_experience_dispositions", "_post_candidate_context", "validate_post_analyzer_output",
        "conservative_post_analyzer_fallback", "canonicalize_post_analyzer_output", "_query_channel_contracts"],
    "harnesslens/evolution/main_agent.py": [
        "MIN_ROLLOUT_CREATIONS", "MIN_STANDARD_ROLLOUT_TASKS", "MIN_RESIDUAL_ROLLOUT_TASKS",
        "DEFAULT_EXPLORATION_ROLLOUT_TASKS", "ITERATION_RETRY_BUFFER_CREATIONS", "iteration_creation_cost",
        "MIN_CANDIDATE_ITERATION_CREATIONS", "normalize_promotion_metric", "paired_screen_creation_cost",
        "paired_confirmation_creation_cost", "confirmation_mode", "build_rollout_budget_plan",
        "normalize_budget_disposition", "MAIN_AGENT_SYSTEM", "FINAL_MAIN_AGENT_SYSTEM", "MainDecision",
        "CandidateMaterializationError", "selectable_portfolio", "defer_failure_only_portfolio",
        "promotion_headroom_portfolio", "assign_rollout_roles", "prioritize_incumbent_controls",
        "canonicalize_main_decision", "validate_main_decision", "build_exploration_status",
        "_baseline_evidence_summary", "validate_final_decision", "canonicalize_final_decision",
        "_attributable_positive_task_ids", "uncertain_recovery_task_ids", "_required_metric",
        "deterministic_reject_decision", "_final_review_attempts", "GLOBAL_INSTRUCTION_CHANNELS",
        "validate_candidate_channel_combination"],
    "harnesslens/evolution/controller.py": [
        "reference_metrics_from_comparison_index", "select_confirmation_task_ids", "_evaluation_requires_confirmation",
        "advance_cumulative_version", "assert_candidate_extends_champion", "assert_confirmed_promotion",
        "minimum_screen_start_creations", "confirmation_creation_cost", "reject_unconfirmed_candidate",
        "defer_residual_candidate", "revision_candidate_from_review", "replan_candidate_from_review"],
    "harnesslens/evolution/harness_editor.py": ["EDITOR_SYSTEM_PROMPT", "EDITOR_TOOLS"],
    "harnesslens/harnesses/channel_preflight.py": ["PREFLIGHT_CREATION_COST"],
    "harnesslens/core/artifacts.py": ["write_json", "write_text", "read_json", "content_digest"],
    "harnesslens/benchmarks/task_data.py": ["evaluation_contract"],
}


def modname(rel: str) -> str:
    return rel[:-3].replace("/", ".")


def top_defs(tree: ast.Module) -> dict[str, ast.stmt]:
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[node.name] = node
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Name):
                    out[t.id] = node
    return out


def names_used(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)} | \
           {n.value.id for n in ast.walk(node) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}


def main() -> int:
    clone, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    trees, srcs, imports = {}, {}, {}
    rels = list(ROOTS)
    for rel in rels:
        srcs[rel] = (clone / rel).read_text(encoding="utf-8")
        trees[rel] = ast.parse(srcs[rel])
        imp = {}
        for node in trees[rel].body:
            if isinstance(node, ast.ImportFrom) and node.module:
                for a in node.names:
                    imp[a.asname or a.name] = (node.module, a.name)
            elif isinstance(node, ast.Import):
                for a in node.names:
                    imp[a.asname or a.name.split(".")[0]] = (None, a.name)
        imports[rel] = imp
    by_mod = {modname(r): r for r in rels}
    need: dict[str, set[str]] = {r: set(ROOTS[r]) for r in rels}
    external: set[tuple[str, str]] = set()
    changed = True
    while changed:
        changed = False
        for rel in rels:
            defs = top_defs(trees[rel])
            for name in list(need[rel]):
                if name not in defs:
                    raise SystemExit(f"{rel}: {name} not found")
                for used in names_used(defs[name]):
                    if used in defs and used not in need[rel]:
                        need[rel].add(used)
                        changed = True
                    elif used in imports[rel]:
                        mod, orig = imports[rel][used]
                        if mod in by_mod:
                            r2 = by_mod[mod]
                            if orig not in need[r2]:
                                need[r2].add(orig)
                                changed = True
                        elif mod and mod.startswith("harnesslens"):
                            external.add((mod, orig))
    commit = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    md = ["# Vendored from HarnessLens", "", f"Source: https://github.com/jhxu5214/HarnessLens at `{commit}` (MIT License, "
          "Copyright (c) 2026 Jinghan Xu). Extracted by `../vendor_extract.py`: each listed top-level definition is "
          "copied byte-for-byte from the source file, plus every definition it references inside the vendored set. "
          "Imports between vendored modules are rewritten to this package. Nothing else is changed.", "",
          "| vendored module | source path | source sha256 | definitions |", "|---|---|---|---|"]
    (out / "__init__.py").write_text('"""HarnessLens pure helpers and prompts, vendored verbatim (see VENDORED.md)."""\n')
    for rel in rels:
        tree, src = trees[rel], srcs[rel]
        lines = src.splitlines(keepends=True)
        keep = need[rel]
        body = []
        for node in tree.body:
            names = [n for n, d in top_defs(ast.Module(body=[node], type_ignores=[])).items()]
            if names and any(n in keep for n in names):
                start = (node.decorator_list[0].lineno if getattr(node, "decorator_list", None) else node.lineno) - 1
                body.append("".join(lines[start:node.end_lineno]))
        hdr = ["from __future__ import annotations", ""]
        used_all = set().union(*[names_used(top_defs(tree)[n]) for n in keep]) if keep else set()
        for name, (mod, orig) in sorted(imports[rel].items()):
            if name not in used_all or name == "annotations":
                continue
            if mod is None:
                hdr.append(f"import {orig}" + (f" as {name}" if name != orig.split('.')[0] else ""))
            elif mod in by_mod:
                hdr.append(f"from .{Path(by_mod[mod]).stem} import {orig}" + (f" as {name}" if name != orig else ""))
            elif mod.startswith("harnesslens"):
                hdr.append(f"from ._external import {orig}" + (f" as {name}" if name != orig else ""))
            else:
                hdr.append(f"from {mod} import {orig}" + (f" as {name}" if name != orig else ""))
        text = f'"""Vendored verbatim from HarnessLens {commit[:7]}:{rel} (see VENDORED.md)."""\n' + "\n".join(hdr) + "\n\n\n" + "\n\n".join(body)
        (out / Path(rel).name).write_text(text, encoding="utf-8")
        md.append(f"| `{Path(rel).name}` | `{rel}` | `{hashlib.sha256(src.encode()).hexdigest()}` | "
                  f"{len(keep)}: {', '.join(sorted(keep))} |")
    md += ["", "External names (resolved to non-vendored HarnessLens modules; provided by `_external.py`, used only "
           "on code paths the AppWorld port never takes):", ""]
    md += [f"- `{m}.{n}`" for m, n in sorted(external)] or ["- none"]
    (out / "VENDORED.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("external:", sorted(external))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
