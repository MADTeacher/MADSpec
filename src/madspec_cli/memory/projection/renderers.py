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
    generated_at: str,
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
    lines.extend(
        [
            "",
            "## Canonical Memory",
            f"- `.madspec/{branch_name}/memory/progress.json`",
            f"- `.madspec/{branch_name}/memory/stages/mvp.concept.json`",
            f"- `.madspec/{branch_name}/memory/stages/mvp.design.json`",
            f"- `.madspec/{branch_name}/memory/stages/mvp.tech.json`",
            f"- `.madspec/{branch_name}/memory/stages/mvp.architecture.json`",
            f"- `.madspec/{branch_name}/memory/working/active-session.json`",
            f"- `.madspec/{branch_name}/memory/working/decision-log.jsonl`",
            f"- `.madspec/{branch_name}/memory/episodes/events.jsonl`",
            f"- `.madspec/{branch_name}/memory/semantic/*.jsonl`",
            "",
            "## Generated Artifacts",
            f"- `.madspec/{branch_name}/concept.md` (generated from structured memory)",
            f"- `.madspec/{branch_name}/ui-design.md` (generated from structured memory)",
            f"- `.madspec/{branch_name}/tech-stack.md` (generated from structured memory)",
            f"- `.madspec/{branch_name}/architecture.md` (generated from structured memory)",
            f"- `.madspec/{branch_name}/data-model.md` (generated from structured memory)",
            f"- `.madspec/{branch_name}/contracts/openapi.yaml` (generated from structured memory)",
            f"- Concept checkpoint summary: `{concept_state.get('checkpointSummary') or 'N/A'}`",
            f"- Design checkpoint summary: `{design_state.get('checkpointSummary') or 'N/A'}`",
            f"- Tech checkpoint summary: `{tech_state.get('checkpointSummary') or 'N/A'}`",
            f"- Architecture checkpoint summary: `{architecture_state.get('checkpointSummary') or 'N/A'}`",
            (
                f"- Design inventory: `{len(design_state.get('screens', []))}` screens, "
                f"`{len(design_state.get('flows', []))}` flows, main prototype "
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
        "",
        "## Records",
    ]
    lines.extend(format_record_lines(records))
    return "\n".join(lines) + "\n"


def render_review_artifacts(
    review_records: list[dict[str, Any]],
    improvement_records: list[dict[str, Any]],
    generated_at: str,
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


def render_security_artifact(security_records: list[dict[str, Any]], generated_at: str) -> str:
    lines = [
        "# Security Audit",
        "",
        "> Generated from security-stage structured memory.",
        "",
        f"- Last generated: `{generated_at}`",
        "",
        "## Findings And Notes",
    ]
    lines.extend(format_record_lines(security_records))
    return "\n".join(lines) + "\n"
