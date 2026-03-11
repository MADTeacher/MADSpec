from __future__ import annotations

from pathlib import Path
from typing import Any

from .concept_state import concept_completeness_errors, load_concept_state, render_concept_markdown
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


def _concept_missing_required_fields(concept_state: dict[str, Any]) -> list[str]:
    error_map = {
        "concept state must include a system overview before checkpoint": "systemOverview",
        "concept state must include at least one audience before checkpoint": "audiences",
        "concept state must include at least one scenario before checkpoint": "scenarios",
        "concept state must include at least one pain point before checkpoint": "painPoints",
        "concept state must include at least one P1 feature before checkpoint": "features.p1",
    }
    missing: list[str] = []
    for error in concept_completeness_errors(concept_state):
        field_name = error_map.get(error)
        if field_name and field_name not in missing:
            missing.append(field_name)
    return missing


def _concept_filled_fields(concept_state: dict[str, Any]) -> list[str]:
    field_checks = (
        ("projectName", bool(concept_state.get("projectName"))),
        ("systemOverview", bool(concept_state.get("systemOverview"))),
        ("audiences", bool(concept_state.get("audiences"))),
        ("scenarios", bool(concept_state.get("scenarios"))),
        ("painPoints", bool(concept_state.get("painPoints"))),
        ("features.p1", bool(concept_state.get("features", {}).get("p1"))),
        ("features.p2", bool(concept_state.get("features", {}).get("p2"))),
        ("features.p3", bool(concept_state.get("features", {}).get("p3"))),
        ("constraints", bool(concept_state.get("constraints"))),
        ("assumptions", bool(concept_state.get("assumptions"))),
        ("nextActions", bool(concept_state.get("nextActions"))),
        ("checkpointSummary", bool(concept_state.get("checkpointSummary"))),
    )
    return [field_name for field_name, is_filled in field_checks if is_filled]


def _build_concept_status(concept_state: dict[str, Any]) -> dict[str, Any]:
    missing_required_fields = _concept_missing_required_fields(concept_state)
    return {
        "is_complete": not missing_required_fields,
        "missing_required_fields": missing_required_fields,
        "filled_fields": _concept_filled_fields(concept_state),
        "counts": {
            "audiences": len(concept_state.get("audiences", [])),
            "scenarios": len(concept_state.get("scenarios", [])),
            "pain_points": len(concept_state.get("painPoints", [])),
            "p1_features": len(concept_state.get("features", {}).get("p1", [])),
            "p2_features": len(concept_state.get("features", {}).get("p2", [])),
            "p3_features": len(concept_state.get("features", {}).get("p3", [])),
            "constraints": len(concept_state.get("constraints", [])),
            "assumptions": len(concept_state.get("assumptions", [])),
            "next_actions": len(concept_state.get("nextActions", [])),
        },
        "last_checkpoint_summary": concept_state.get("checkpointSummary") or None,
        "revision": concept_state.get("revision", 0),
        "ratified_at": concept_state.get("ratifiedAt"),
        "updated_at": concept_state.get("updatedAt"),
    }


def _render_project_context(
    branch_name: str,
    progress: dict[str, Any],
    active_session: dict[str, Any],
    concept_state: dict[str, Any],
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
            f"- `.madspec/{branch_name}/memory/working/active-session.json`",
            f"- `.madspec/{branch_name}/memory/working/decision-log.jsonl`",
            f"- `.madspec/{branch_name}/memory/episodes/events.jsonl`",
            f"- `.madspec/{branch_name}/memory/semantic/*.jsonl`",
            "",
            "## Generated Artifacts",
            f"- `.madspec/{branch_name}/concept.md` (generated from structured memory)",
            f"- Concept checkpoint summary: `{concept_state.get('checkpointSummary') or 'N/A'}`",
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
    concept_state = load_concept_state(paths.concept_state)
    generated_at = active_session.get("updated_at") or active_session.get("last_checkpoint_at") or now_iso()
    decision_log = read_jsonl(paths.decision_log)
    events = read_jsonl(paths.events)
    facts = [record for record in read_jsonl(paths.facts) if record.get("status") == "validated"]
    decisions = [record for record in read_jsonl(paths.decisions) if record.get("status") == "validated"]
    contracts = [record for record in read_jsonl(paths.contracts) if record.get("status") == "validated"]

    generated: list[Path] = []

    concept_path = paths.branch_dir / "concept.md"
    concept_path.write_text(render_concept_markdown(concept_state), encoding="utf-8")
    generated.append(concept_path)

    project_context_path = paths.branch_dir / "project-context.md"
    project_context_path.write_text(
        _render_project_context(branch_name, progress, active_session, concept_state, generated_at),
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
    limit: int | None = None,
    include_obsolete: bool = False,
    include_conflicted: bool = False,
    full_artifact: bool = False,
    include_history: bool = False,
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
    is_concept_stage = stage_lower == "mvp.concept"
    concept_state = load_concept_state(paths.concept_state) if is_concept_stage else None
    if limit is None:
        resolved_limit = 3 if is_concept_stage else 5
    elif limit <= 0:
        resolved_limit = 3 if is_concept_stage else 5
    else:
        resolved_limit = limit
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
        )[:resolved_limit]

    trimmed_events = _trim(scoped_events)
    trimmed_decisions = _trim(scoped_decisions)

    return {
        "branch": branch_name,
        "stage": stage,
        "step_id": resolved_step_id,
        "active_session": {
            "active_goal": active_session.get("active_goal"),
            "stage": active_session.get("stage"),
            "current_step": active_session.get("current_step"),
            "open_questions": active_session.get("open_questions", [])[:resolved_limit],
            "current_hypotheses": active_session.get("current_hypotheses", [])[:resolved_limit],
        },
        "workflow": {
            "currentImplementStep": progress.get("currentImplementStep"),
            "plannedSteps": progress.get("plannedSteps", [])[:resolved_limit],
            "completedSteps": progress.get("completedSteps", [])[:resolved_limit],
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
        "concept_status": _build_concept_status(concept_state) if is_concept_stage else None,
        "episodes": trimmed_events if (include_history or not is_concept_stage) else [],
        "decision_log": trimmed_decisions if (include_history or not is_concept_stage) else [],
        "artifact_state": {
            "concept": concept_state if (is_concept_stage and full_artifact) else None,
        },
    }
