from __future__ import annotations

from pathlib import Path
from typing import Any

from ..stages.design.state import design_main_prototype_path
from .projections import format_record_lines


def render_project_context(
    branch_name: str,
    progress: dict[str, Any],
    active_session: dict[str, Any],
    concept_state: dict[str, Any],
    design_state: dict[str, Any],
    tech_state: dict[str, Any],
    architecture_state: dict[str, Any],
    plan_state: dict[str, Any],
    feature_init_state: dict[str, Any] | None,
    feature_plan_state: dict[str, Any] | None,
    policy_summary: dict[str, Any],
    generated_at: str,
    current_gate_summary: dict[str, Any] | None = None,
    review_gate_summary: dict[str, Any] | None = None,
    security_gate_summary: dict[str, Any] | None = None,
) -> str:
    planned_steps = progress.get("plannedSteps", [])
    completed_steps = progress.get("completedSteps", [])
    step_metadata = progress.get("stepMetadata", {})
    step_status = progress.get("stepStatus", {})
    current_stage = active_session.get("stage", "idle") or "idle"
    current_step = active_session.get("current_step") or progress.get("currentImplementStep") or "N/A"
    lines = [
        f"# Project Context ({branch_name})",
        "",
        "> Generated from structured memory. Do not treat this file as the canonical source of truth.",
        "",
        f"- Last generated: `{generated_at}`",
        f"- Current stage: `{current_stage}`",
        f"- Current step: `{current_step}`",
        f"- Active goal: `{active_session.get('active_goal', '') or 'N/A'}`",
        f"- Progress: `{len(completed_steps)}/{len(planned_steps)}` completed",
        "",
        "## Planned Steps",
    ]
    lines.extend(
        f"- `{step}`"
        + (
            " "
            f"[{step_metadata.get(step, {}).get('kind', 'unknown')}/"
            f"{step_metadata.get(step, {}).get('tddPolicy', 'unknown')}/"
            f"{step_status.get(step, {}).get('tddPhase', 'unknown')}]"
        )
        + (" [completed]" if step in completed_steps else "")
        for step in planned_steps
    )
    if not planned_steps:
        lines.append("- No planned steps yet")
    feature_mode = bool(feature_init_state and any(feature_init_state.get("features", {}).get(priority) for priority in ("p1", "p2", "p3")))
    lines.extend(
        [
            "",
            "## Canonical Memory",
            f"- `.madspec/{branch_name}/memory/progress.json`",
            f"- `.madspec/{branch_name}/memory/stages/mvp.concept.json`",
            f"- `.madspec/{branch_name}/memory/stages/mvp.design.json`",
            f"- `.madspec/{branch_name}/memory/stages/mvp.tech.json`",
            f"- `.madspec/{branch_name}/memory/stages/mvp.architecture.json`",
            f"- `.madspec/{branch_name}/memory/stages/mvp.plan.json`",
            f"- `.madspec/{branch_name}/memory/stages/feature.init.json`",
            f"- `.madspec/{branch_name}/memory/stages/feature.plan.json`",
            f"- `.madspec/{branch_name}/memory/working/active-session.json`",
            f"- `.madspec/{branch_name}/memory/working/decision-log.jsonl`",
            f"- `.madspec/{branch_name}/memory/episodes/events.jsonl`",
            f"- `.madspec/{branch_name}/memory/semantic/*.jsonl`",
            f"- `.madspec/system/policy/state.json`",
            "",
            "## Generated Artifacts",
            f"- `.madspec/{branch_name}/concept.md` (generated from structured memory)",
            f"- `.madspec/{branch_name}/ui-design.md` (generated from structured memory)",
            f"- `.madspec/{branch_name}/tech-stack.md` (generated from structured memory)",
            f"- `.madspec/{branch_name}/architecture.md` (generated from structured memory)",
            f"- `.madspec/{branch_name}/data-model.md` (generated from structured memory)",
            f"- `.madspec/{branch_name}/contracts/openapi.yaml` (generated from structured memory)",
            f"- `.madspec/{branch_name}/implementation-plan.md` (generated from structured memory)",
            f"- `.madspec/{branch_name}/project-analysis.md` (generated from structured memory)",
            f"- `.madspec/{branch_name}/feature-context.md` (generated from structured memory)",
            f"- Concept checkpoint summary: `{concept_state.get('checkpointSummary') or 'N/A'}`",
            f"- Design checkpoint summary: `{design_state.get('checkpointSummary') or 'N/A'}`",
            f"- Tech checkpoint summary: `{tech_state.get('checkpointSummary') or 'N/A'}`",
            f"- Architecture checkpoint summary: `{architecture_state.get('checkpointSummary') or 'N/A'}`",
            f"- Plan checkpoint summary: `{plan_state.get('checkpointSummary') or 'N/A'}`",
            (
                f"- Design inventory: `{len(design_state.get('screens', []))}` screens, "
                f"`{len(design_state.get('flows', []))}` review journeys, storyboard entrypoint "
                f"`{design_main_prototype_path(branch_name).as_posix()}`"
            ),
            "- Tech slots: `"
            + (
                ", ".join(
                    sorted({item.get("slot", "") for item in tech_state.get("components", []) if item.get("slot", "")})
                )
                or "N/A"
            )
            + "`",
            (
                f"- Architecture inventory: `{len(architecture_state.get('projectStructure', {}).get('directories', []))}` directories, "
                f"`{len(architecture_state.get('dataModel', {}).get('entities', []))}` entities, "
                f"`{len(architecture_state.get('contracts', {}).get('endpoints', []))}` endpoints"
            ),
            (
                f"- Planning inventory: `{len(plan_state.get('stepCatalog', []))}` catalog steps, "
                f"`{len(plan_state.get('planningPrinciples', []))}` principles"
            ),
            (
                f"- Policy inventory: revision `{policy_summary.get('revision', 1)}`, "
                f"`{policy_summary.get('activeCount', 0)}` active, "
                f"`{policy_summary.get('deprecatedCount', 0)}` deprecated, "
                f"`{policy_summary.get('pendingProposalsCount', 0)}` pending proposals"
            ),
            "- Global policy artifact: `.madspec/system/policy.md`",
        ]
    )
    lines.extend(_render_gate_section("Current Gate Status", current_gate_summary))
    lines.extend(_render_gate_section("Review Gates", review_gate_summary))
    lines.extend(_render_gate_section("Security Gates", security_gate_summary))
    if feature_mode:
        lines.extend(
            [
                f"- Feature init checkpoint summary: `{(feature_init_state or {}).get('checkpointSummary') or 'N/A'}`",
                f"- Feature plan checkpoint summary: `{(feature_plan_state or {}).get('checkpointSummary') or 'N/A'}`",
            ]
        )
    return "\n".join(lines) + "\n"


def render_planning_cache(
    branch_name: str,
    progress: dict[str, Any],
    facts: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    contracts: list[dict[str, Any]],
    generated_at: str,
) -> str:
    lines = [
        f"# Planning Context Cache ({branch_name})",
        "",
        "> Generated from semantic memory and workflow state.",
        "",
        f"- Last generated: `{generated_at}`",
        "",
        "## Progress Metrics",
    ]
    metrics = progress.get("planningMetadata", {}).get("progressMetrics", {})
    for key in ("p1Coverage", "p2Coverage", "p3Coverage"):
        metric = metrics.get(key, {"covered": 0, "total": 0, "percentage": 0})
        lines.append(f"- `{key}`: {metric.get('covered', 0)}/{metric.get('total', 0)} ({metric.get('percentage', 0)}%)")
    lines.append(f"- `overallProgress`: {metrics.get('overallProgress', 0)}%")
    lines.extend(["", "## Semantic Facts"])
    lines.extend(format_record_lines(facts))
    lines.extend(["", "## Validated Decisions"])
    lines.extend(format_record_lines(decisions))
    lines.extend(["", "## Contracts"])
    lines.extend(format_record_lines(contracts))
    return "\n".join(lines) + "\n"


def render_step_context(
    step_id: str,
    title: str,
    records: list[dict[str, Any]],
    generated_at: str,
    *,
    step_metadata: dict[str, Any] | None = None,
    status_info: dict[str, Any] | None = None,
    gate_summary: dict[str, Any] | None = None,
) -> str:
    lines = [
        f"# {title}: {step_id}",
        "",
        "> Generated from structured memory records.",
        "",
        f"- Last generated: `{generated_at}`",
        f"- Step kind: `{(step_metadata or {}).get('kind', 'unknown')}`",
        f"- TDD policy: `{(step_metadata or {}).get('tddPolicy', 'unknown')}`",
        f"- TDD phase: `{(status_info or {}).get('tddPhase', 'unknown')}`",
        f"- Gate status: `{(gate_summary or {}).get('overall_status', 'unknown')}`",
        "",
    ]
    lines.extend(_render_gate_section("Gate Summary", gate_summary))
    lines.extend(
        [
        "## Records",
        ]
    )
    lines.extend(format_record_lines(records))
    return "\n".join(lines) + "\n"


def render_review_artifacts(
    review_records: list[dict[str, Any]],
    improvement_records: list[dict[str, Any]],
    generated_at: str,
    *,
    change_context: dict[str, Any] | None = None,
    gate_summary: dict[str, Any] | None = None,
) -> tuple[str, str]:
    review_lines = [
        "# Review",
        "",
        "> Generated from review-stage structured memory.",
        "",
        f"- Last generated: `{generated_at}`",
        "",
        "## Findings",
    ]
    review_lines.extend(_render_change_context(change_context))
    review_lines.extend(_render_gate_section("Gate Summary", gate_summary))
    review_lines.extend(format_record_lines(review_records))
    improvement_lines = [
        "# Improvements",
        "",
        "> Generated from structured memory. Use semantic memory as source of truth.",
        "",
        f"- Last generated: `{generated_at}`",
        "",
        "## Candidate Improvements",
    ]
    improvement_lines.extend(format_record_lines(improvement_records))
    return "\n".join(review_lines) + "\n", "\n".join(improvement_lines) + "\n"


def render_security_artifact(
    security_records: list[dict[str, Any]],
    generated_at: str,
    *,
    change_context: dict[str, Any] | None = None,
    gate_summary: dict[str, Any] | None = None,
) -> str:
    lines = [
        "# Security Audit",
        "",
        "> Generated from security-stage structured memory.",
        "",
        f"- Last generated: `{generated_at}`",
        "",
        "## Findings And Notes",
    ]
    lines.extend(_render_change_context(change_context))
    lines.extend(_render_gate_section("Gate Summary", gate_summary))
    lines.extend(format_record_lines(security_records))
    return "\n".join(lines) + "\n"


def _render_change_context(change_context: dict[str, Any] | None) -> list[str]:
    if not change_context or not change_context.get("initialized") or not change_context.get("title"):
        return []
    return [
        "",
        "## Active Change Bundle",
        f"- Bundle ID: `{change_context.get('bundle_id')}`",
        f"- Title: {change_context.get('title')}",
        f"- Base branch: `{change_context.get('base_branch')}`",
        f"- Workflow mode: `{change_context.get('workflow_mode')}`",
        f"- Summary: {change_context.get('summary') or 'No summary recorded.'}",
        f"- Impacted steps: {', '.join(change_context.get('impacted_steps', [])) or 'none'}",
        "",
    ]


def _render_gate_section(title: str, gate_summary: dict[str, Any] | None) -> list[str]:
    if not gate_summary:
        return []
    lines = [
        "",
        f"## {title}",
        f"- Overall: `{gate_summary.get('overall_status', 'unknown')}`",
        f"- Blocking: `{gate_summary.get('blocking_count', 0)}`",
        f"- Warnings: `{gate_summary.get('warning_count', 0)}`",
        f"- Pending: `{gate_summary.get('pending_count', 0)}`",
    ]
    active_waivers = gate_summary.get("active_waivers", [])
    if active_waivers:
        lines.append(f"- Active waivers: `{len(active_waivers)}`")
    for gate in gate_summary.get("gates", [])[:5]:
        lines.append(f"- [{gate['status']}] {gate['message']}")
    lines.append("")
    return lines
