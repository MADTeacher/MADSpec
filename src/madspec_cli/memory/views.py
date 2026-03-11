from __future__ import annotations

from pathlib import Path
from typing import Any

from .records import make_record
from .storage import (
    _default_active_session,
    _default_progress_state,
    get_memory_paths,
    now_iso,
    read_json,
    read_jsonl,
)


def _group_records_by_step(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        step_id = record.get("step_id")
        if not step_id:
            continue
        grouped.setdefault(step_id, []).append(record)
    return grouped


def _format_record_lines(records: list[dict[str, Any]]) -> list[str]:
    if not records:
        return ["- Нет релевантных записей"]
    lines = []
    for record in sorted(records, key=lambda item: (item.get("ts", ""), item.get("id", ""))):
        status = record.get("status", "unknown")
        source = record.get("source", "unknown")
        summary = record.get("summary", "")
        lines.append(f"- `{status}` {summary} (source: `{source}`)")
    return lines


def _select_next_executable_step(progress: dict[str, Any]) -> str | None:
    completed_steps = set(progress.get("completedSteps", []))
    step_dependencies = progress.get("planningMetadata", {}).get("stepDependencies", {})
    step_status = progress.get("stepStatus", {})
    for step_id in progress.get("plannedSteps", []):
        if step_id in completed_steps:
            continue
        if step_status.get(step_id, {}).get("status") == "completed":
            continue
        if all(dependency in completed_steps for dependency in step_dependencies.get(step_id, [])):
            return step_id
    return None


def _render_project_context(
    branch_name: str,
    progress: dict[str, Any],
    active_session: dict[str, Any],
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
            f"- `.madspec/{branch_name}/memory/working/active-session.json`",
            f"- `.madspec/{branch_name}/memory/working/decision-log.jsonl`",
            f"- `.madspec/{branch_name}/memory/episodes/events.jsonl`",
            f"- `.madspec/{branch_name}/memory/semantic/*.jsonl`",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_planning_cache(
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
        lines.append(
            f"- `{key}`: {metric.get('covered', 0)}/{metric.get('total', 0)} ({metric.get('percentage', 0)}%)"
        )
    lines.append(f"- `overallProgress`: {metrics.get('overallProgress', 0)}%")
    lines.extend(["", "## Semantic Facts"])
    lines.extend(_format_record_lines(facts))
    lines.extend(["", "## Validated Decisions"])
    lines.extend(_format_record_lines(decisions))
    lines.extend(["", "## Contracts"])
    lines.extend(_format_record_lines(contracts))
    return "\n".join(lines) + "\n"


def _render_step_context(
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
    lines.extend(_format_record_lines(records))
    return "\n".join(lines) + "\n"


def _render_review_artifacts(
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
    review_lines.extend(_format_record_lines(review_records))

    improvement_lines = [
        "# Improvements",
        "",
        "> Generated from structured memory. Use semantic memory as source of truth.",
        "",
        f"- Last generated: `{generated_at}`",
        "",
        "## Candidate Improvements",
    ]
    improvement_lines.extend(_format_record_lines(improvement_records))
    return "\n".join(review_lines) + "\n", "\n".join(improvement_lines) + "\n"


def _render_security_artifact(
    security_records: list[dict[str, Any]],
    generated_at: str,
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
    lines.extend(_format_record_lines(security_records))
    return "\n".join(lines) + "\n"


def consolidate_branch_memory(project_path: Path, branch_name: str) -> list[Path]:
    paths = get_memory_paths(project_path, branch_name)
    progress = read_json(paths.progress, _default_progress_state())
    active_session = read_json(paths.active_session, _default_active_session(branch_name))
    generated_at = active_session.get("updated_at") or active_session.get("last_checkpoint_at") or now_iso()
    decision_log = read_jsonl(paths.decision_log)
    events = read_jsonl(paths.events)
    facts = [record for record in read_jsonl(paths.facts) if record.get("status") == "validated"]
    decisions = [record for record in read_jsonl(paths.decisions) if record.get("status") == "validated"]
    contracts = [record for record in read_jsonl(paths.contracts) if record.get("status") == "validated"]

    generated: list[Path] = []

    project_context_path = paths.branch_dir / "project-context.md"
    project_context_path.write_text(
        _render_project_context(branch_name, progress, active_session, generated_at),
        encoding="utf-8",
    )
    generated.append(project_context_path)

    planning_cache_path = paths.branch_dir / "planning-context-cache.md"
    planning_cache_path.write_text(
        _render_planning_cache(branch_name, progress, facts, decisions, contracts, generated_at),
        encoding="utf-8",
    )
    generated.append(planning_cache_path)

    all_records = decision_log + events + facts + decisions + contracts
    grouped_records = _group_records_by_step(all_records)
    step_metadata = progress.get("stepMetadata", {})
    step_status = progress.get("stepStatus", {})
    for step_id, step_records in sorted(grouped_records.items()):
        step_dir = paths.branch_dir / "steps" / step_id
        if not step_dir.exists():
            continue
        planning_records = [record for record in step_records if "plan" in str(record.get("stage", "")).lower()]
        implementation_records = [
            record for record in step_records if "implement" in str(record.get("stage", "")).lower()
        ]
        planning_path = step_dir / "planning-context.md"
        planning_path.write_text(
            _render_step_context(
                step_id,
                "Planning Context",
                planning_records,
                generated_at,
                step_metadata=step_metadata.get(step_id),
                status_info=step_status.get(step_id),
            ),
            encoding="utf-8",
        )
        implementation_path = step_dir / "implementation-context.md"
        implementation_path.write_text(
            _render_step_context(
                step_id,
                "Implementation Context",
                implementation_records,
                generated_at,
                step_metadata=step_metadata.get(step_id),
                status_info=step_status.get(step_id),
            ),
            encoding="utf-8",
        )
        generated.extend([planning_path, implementation_path])

    review_records = [record for record in all_records if record.get("stage") == "review"]
    improvement_records = [
        record
        for record in review_records
        if record.get("record_type") in {"improvement", "review_finding", "question"}
    ]
    review_text, improvements_text = _render_review_artifacts(
        review_records,
        improvement_records,
        generated_at,
    )
    review_path = paths.branch_dir / "review.md"
    review_path.write_text(review_text, encoding="utf-8")
    improvements_path = paths.branch_dir / "improvements.md"
    improvements_path.write_text(improvements_text, encoding="utf-8")
    generated.extend([review_path, improvements_path])

    security_records = [record for record in all_records if record.get("stage") == "security"]
    security_path = paths.branch_dir / "security-audit.md"
    security_path.write_text(
        _render_security_artifact(security_records, generated_at),
        encoding="utf-8",
    )
    generated.append(security_path)
    return generated


def _filtered_semantic_records(
    path: Path,
    *,
    include_obsolete: bool,
    include_conflicted: bool,
    include_proposed: bool = False,
) -> list[dict[str, Any]]:
    records = read_jsonl(path)
    filtered: list[dict[str, Any]] = []
    for record in records:
        status = record.get("status")
        if status == "proposed" and not include_proposed:
            continue
        if status == "obsolete" and not include_obsolete:
            continue
        if status == "conflicted" and not include_conflicted:
            continue
        if status == "validated" or include_proposed or include_conflicted or include_obsolete:
            filtered.append(record)
    return filtered


def retrieve_memory_context(
    project_path: Path,
    branch_name: str,
    stage: str,
    *,
    step_id: str | None = None,
    limit: int = 5,
    include_obsolete: bool = False,
    include_conflicted: bool = False,
) -> dict[str, Any]:
    paths = get_memory_paths(project_path, branch_name)
    progress = read_json(paths.progress, _default_progress_state())
    active_session = read_json(paths.active_session, _default_active_session(branch_name))
    events = read_jsonl(paths.events)
    decision_log = read_jsonl(paths.decision_log)

    semantic_facts = _filtered_semantic_records(
        paths.facts,
        include_obsolete=include_obsolete,
        include_conflicted=include_conflicted,
    )
    semantic_decisions = _filtered_semantic_records(
        paths.decisions,
        include_obsolete=include_obsolete,
        include_conflicted=include_conflicted,
    )
    semantic_contracts = _filtered_semantic_records(
        paths.contracts,
        include_obsolete=include_obsolete,
        include_conflicted=include_conflicted,
    )
    stage_lower = stage.lower()
    resolved_step_id = step_id or active_session.get("current_step") or progress.get("currentImplementStep")
    if not resolved_step_id and "implement" in stage_lower:
        resolved_step_id = _select_next_executable_step(progress)
    stage_facts = [
        record
        for record in _filtered_semantic_records(
            paths.facts,
            include_obsolete=include_obsolete,
            include_conflicted=include_conflicted,
            include_proposed=True,
        )
        if stage_lower in str(record.get("stage", "")).lower()
        and (not resolved_step_id or record.get("step_id") == resolved_step_id)
    ]
    stage_decisions = [
        record
        for record in _filtered_semantic_records(
            paths.decisions,
            include_obsolete=include_obsolete,
            include_conflicted=include_conflicted,
            include_proposed=True,
        )
        if stage_lower in str(record.get("stage", "")).lower()
        and (not resolved_step_id or record.get("step_id") == resolved_step_id)
    ]
    stage_contracts = [
        record
        for record in _filtered_semantic_records(
            paths.contracts,
            include_obsolete=include_obsolete,
            include_conflicted=include_conflicted,
            include_proposed=True,
        )
        if stage_lower in str(record.get("stage", "")).lower()
        and (not resolved_step_id or record.get("step_id") == resolved_step_id)
    ]
    scoped_events = [
        record
        for record in events
        if (not resolved_step_id or record.get("step_id") == resolved_step_id)
        and stage_lower in str(record.get("stage", "")).lower()
    ]
    scoped_decisions = [
        record
        for record in decision_log
        if (not resolved_step_id or record.get("step_id") == resolved_step_id)
        and stage_lower in str(record.get("stage", "")).lower()
    ]

    if "plan" in stage_lower:
        relevant_facts = semantic_facts
        relevant_decisions = [
            record
            for record in semantic_decisions
            if "plan" in record.get("stage", "") or record.get("scope") == "project"
        ]
        relevant_contracts = semantic_contracts
    elif "implement" in stage_lower:
        relevant_facts = [
            record
            for record in semantic_facts
            if record.get("scope") in {"project", "branch", "step"}
        ]
        relevant_decisions = [
            record
            for record in semantic_decisions
            if "implement" in record.get("stage", "") or record.get("step_id") == step_id
        ]
        relevant_contracts = semantic_contracts
    else:
        relevant_facts = semantic_facts
        relevant_decisions = semantic_decisions
        relevant_contracts = semantic_contracts

    def _trim(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            records,
            key=lambda item: (item.get("ts", ""), item.get("id", "")),
            reverse=True,
        )[:limit]

    return {
        "branch": branch_name,
        "stage": stage,
        "step_id": resolved_step_id,
        "active_session": {
            "active_goal": active_session.get("active_goal"),
            "stage": active_session.get("stage"),
            "current_step": active_session.get("current_step"),
            "open_questions": active_session.get("open_questions", [])[:limit],
            "current_hypotheses": active_session.get("current_hypotheses", [])[:limit],
        },
        "workflow": {
            "currentImplementStep": progress.get("currentImplementStep"),
            "plannedSteps": progress.get("plannedSteps", [])[:limit],
            "completedSteps": progress.get("completedSteps", [])[:limit],
            "stepDependencies": progress.get("planningMetadata", {}).get("stepDependencies", {}),
            "nextExecutableStep": _select_next_executable_step(progress) if "implement" in stage_lower else None,
        },
        "step": {
            "step_id": resolved_step_id,
            "metadata": progress.get("stepMetadata", {}).get(resolved_step_id, {}) if resolved_step_id else {},
            "status": progress.get("stepStatus", {}).get(resolved_step_id, {}) if resolved_step_id else {},
            "dependencies": progress.get("planningMetadata", {}).get("stepDependencies", {}).get(resolved_step_id, [])
            if resolved_step_id
            else [],
            "covers": progress.get("coversFunctions", {}).get(resolved_step_id, {}) if resolved_step_id else {},
        },
        "stage_memory": {
            "facts": _trim(stage_facts),
            "decisions": _trim(stage_decisions),
            "contracts": _trim(stage_contracts),
            "notes": _trim(scoped_decisions + scoped_events),
        },
        "semantic": {
            "facts": _trim(relevant_facts),
            "decisions": _trim(relevant_decisions),
            "contracts": _trim(relevant_contracts),
        },
        "episodes": _trim(scoped_events),
        "decision_log": _trim(scoped_decisions),
    }
