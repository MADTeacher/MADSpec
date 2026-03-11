from __future__ import annotations

from pathlib import Path
from typing import Any

from .concept_state import concept_completeness_errors, load_concept_state, render_concept_markdown
from .design_state import (
    design_completeness_errors,
    design_main_prototype_path,
    load_design_state,
    missing_prototype_files,
    render_ui_design_markdown,
    uncovered_design_features,
)
from .tech_state import (
    load_tech_state,
    render_tech_stack_markdown,
    tech_completeness_errors,
)
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


def _design_missing_required_fields(
    design_state: dict[str, Any],
    concept_state: dict[str, Any],
    *,
    project_path: Path,
    branch_name: str,
) -> list[str]:
    error_map = {
        "design state must include a design overview before checkpoint": "designOverview",
        "design state must include at least one platform before checkpoint": "platforms",
        "design state must include at least one screen before checkpoint": "screens",
        "design state must include at least one user flow before checkpoint": "flows",
        "design state must include navigation links before checkpoint": "navigation",
    }
    missing: list[str] = []
    for error in design_completeness_errors(
        design_state,
        concept_state=concept_state,
        project_path=project_path,
        branch_name=branch_name,
    ):
        field_name = error_map.get(error)
        if field_name and field_name not in missing:
            missing.append(field_name)
    return missing


def _design_filled_fields(design_state: dict[str, Any]) -> list[str]:
    field_checks = (
        ("designOverview", bool(design_state.get("designOverview"))),
        ("platforms", bool(design_state.get("platforms"))),
        ("zones", bool(design_state.get("zones"))),
        ("screens", bool(design_state.get("screens"))),
        ("flows", bool(design_state.get("flows"))),
        ("navigation", bool(design_state.get("navigation"))),
        ("platformConstraints", bool(design_state.get("platformConstraints"))),
        ("nextActions", bool(design_state.get("nextActions"))),
        ("checkpointSummary", bool(design_state.get("checkpointSummary"))),
    )
    return [field_name for field_name, is_filled in field_checks if is_filled]


def _build_design_status(
    design_state: dict[str, Any],
    concept_state: dict[str, Any],
    *,
    project_path: Path,
    branch_name: str,
) -> dict[str, Any]:
    missing_required_fields = _design_missing_required_fields(
        design_state,
        concept_state,
        project_path=project_path,
        branch_name=branch_name,
    )
    uncovered = uncovered_design_features(design_state, concept_state)
    missing_files = missing_prototype_files(design_state, project_path, branch_name)
    return {
        "is_complete": not missing_required_fields and not any(uncovered.values()) and not missing_files,
        "missing_required_fields": missing_required_fields,
        "filled_fields": _design_filled_fields(design_state),
        "uncovered_features": uncovered,
        "missing_prototype_files": missing_files,
        "counts": {
            "platforms": len(design_state.get("platforms", [])),
            "zones": len(design_state.get("zones", [])),
            "screens": len(design_state.get("screens", [])),
            "flows": len(design_state.get("flows", [])),
            "navigation_links": len(design_state.get("navigation", [])),
            "platform_constraints": len(design_state.get("platformConstraints", [])),
        },
        "last_checkpoint_summary": design_state.get("checkpointSummary") or None,
        "revision": design_state.get("revision", 0),
        "ratified_at": design_state.get("ratifiedAt"),
        "updated_at": design_state.get("updatedAt"),
    }


def _tech_missing_required_fields(tech_state: dict[str, Any]) -> list[str]:
    error_map = {
        "tech state must include a project type before checkpoint": "projectType",
        "tech state must include a stack overview before checkpoint": "stackOverview",
        "tech state must include at least one language component before checkpoint": "components.language",
        "tech state must include at least one build component before checkpoint": "components.build",
        "tech state must include at least one testing component before checkpoint": "components.testing",
        "tech state must include code organization before checkpoint": "codeOrganization",
    }
    missing: list[str] = []
    for error in tech_completeness_errors(tech_state):
        field_name = error_map.get(error)
        if field_name and field_name not in missing:
            missing.append(field_name)
    return missing


def _tech_filled_fields(tech_state: dict[str, Any]) -> list[str]:
    slots = {item.get("slot", "") for item in tech_state.get("components", [])}
    field_checks = (
        ("projectType", bool(tech_state.get("projectType"))),
        ("stackOverview", bool(tech_state.get("stackOverview"))),
        ("requirements", bool(tech_state.get("requirements"))),
        ("preferences", bool(tech_state.get("preferences"))),
        ("constraints", bool(tech_state.get("constraints"))),
        ("components", bool(tech_state.get("components"))),
        ("libraries", bool(tech_state.get("libraries"))),
        ("codeOrganization", bool(tech_state.get("codeOrganization"))),
        ("alternatives", bool(tech_state.get("alternatives"))),
        ("nextActions", bool(tech_state.get("nextActions"))),
        ("checkpointSummary", bool(tech_state.get("checkpointSummary"))),
        ("components.language", "language" in slots),
        ("components.build", "build" in slots),
        (
            "components.testing",
            any(slot in slots for slot in {"unit-testing", "integration-testing", "e2e-testing", "testing"}),
        ),
    )
    return [field_name for field_name, is_filled in field_checks if is_filled]


def _build_tech_status(tech_state: dict[str, Any]) -> dict[str, Any]:
    missing_required_fields = _tech_missing_required_fields(tech_state)
    selected_slots = sorted(
        {item.get("slot", "") for item in tech_state.get("components", []) if item.get("slot", "")}
    )
    return {
        "is_complete": not missing_required_fields,
        "missing_required_fields": missing_required_fields,
        "filled_fields": _tech_filled_fields(tech_state),
        "counts": {
            "requirements": len(tech_state.get("requirements", [])),
            "preferences": len(tech_state.get("preferences", [])),
            "constraints": len(tech_state.get("constraints", [])),
            "components": len(tech_state.get("components", [])),
            "libraries": len(tech_state.get("libraries", [])),
            "alternatives": len(tech_state.get("alternatives", [])),
            "next_actions": len(tech_state.get("nextActions", [])),
        },
        "selected_slots": selected_slots,
        "last_checkpoint_summary": tech_state.get("checkpointSummary") or None,
        "revision": tech_state.get("revision", 0),
        "ratified_at": tech_state.get("ratifiedAt"),
        "updated_at": tech_state.get("updatedAt"),
    }


def _render_project_context(
    branch_name: str,
    progress: dict[str, Any],
    active_session: dict[str, Any],
    concept_state: dict[str, Any],
    design_state: dict[str, Any],
    tech_state: dict[str, Any],
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
            f"- `.madspec/{branch_name}/memory/working/active-session.json`",
            f"- `.madspec/{branch_name}/memory/working/decision-log.jsonl`",
            f"- `.madspec/{branch_name}/memory/episodes/events.jsonl`",
            f"- `.madspec/{branch_name}/memory/semantic/*.jsonl`",
            "",
            "## Generated Artifacts",
            f"- `.madspec/{branch_name}/concept.md` (generated from structured memory)",
            f"- `.madspec/{branch_name}/ui-design.md` (generated from structured memory)",
            f"- `.madspec/{branch_name}/tech-stack.md` (generated from structured memory)",
            f"- Concept checkpoint summary: `{concept_state.get('checkpointSummary') or 'N/A'}`",
            f"- Design checkpoint summary: `{design_state.get('checkpointSummary') or 'N/A'}`",
            f"- Tech checkpoint summary: `{tech_state.get('checkpointSummary') or 'N/A'}`",
            (
                f"- Design inventory: `{len(design_state.get('screens', []))}` screens, "
                f"`{len(design_state.get('flows', []))}` flows, main prototype "
                f"`{design_main_prototype_path(branch_name).as_posix()}`"
            ),
            "- Tech slots: `"
            + (
                ", ".join(
                    sorted(
                        {
                            item.get("slot", "")
                            for item in tech_state.get("components", [])
                            if item.get("slot", "")
                        }
                    )
                )
                or "N/A"
            )
            + "`",
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
    design_state = load_design_state(paths.design_state)
    tech_state = load_tech_state(paths.tech_state)
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

    design_path = paths.branch_dir / "ui-design.md"
    design_path.write_text(
        render_ui_design_markdown(
            design_state,
            branch_name=branch_name,
            project_name=concept_state.get("projectName", ""),
        ),
        encoding="utf-8",
    )
    generated.append(design_path)

    tech_path = paths.branch_dir / "tech-stack.md"
    tech_path.write_text(
        render_tech_stack_markdown(
            tech_state,
            branch_name=branch_name,
            project_name=concept_state.get("projectName", ""),
        ),
        encoding="utf-8",
    )
    generated.append(tech_path)

    project_context_path = paths.branch_dir / "project-context.md"
    project_context_path.write_text(
        _render_project_context(
            branch_name,
            progress,
            active_session,
            concept_state,
            design_state,
            tech_state,
            generated_at,
        ),
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


def _filter_records_by_status(
    records: list[dict[str, Any]],
    *,
    include_obsolete: bool,
    include_conflicted: bool,
    include_proposed: bool = False,
) -> list[dict[str, Any]]:
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


def _load_semantic_record_sets(
    paths,
    *,
    include_obsolete: bool,
    include_conflicted: bool,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    facts_records = read_jsonl(paths.facts)
    decisions_records = read_jsonl(paths.decisions)
    contracts_records = read_jsonl(paths.contracts)

    return {
        "validated": {
            "facts": _filter_records_by_status(
                facts_records,
                include_obsolete=include_obsolete,
                include_conflicted=include_conflicted,
            ),
            "decisions": _filter_records_by_status(
                decisions_records,
                include_obsolete=include_obsolete,
                include_conflicted=include_conflicted,
            ),
            "contracts": _filter_records_by_status(
                contracts_records,
                include_obsolete=include_obsolete,
                include_conflicted=include_conflicted,
            ),
        },
        "stage": {
            "facts": _filter_records_by_status(
                facts_records,
                include_obsolete=include_obsolete,
                include_conflicted=include_conflicted,
                include_proposed=True,
            ),
            "decisions": _filter_records_by_status(
                decisions_records,
                include_obsolete=include_obsolete,
                include_conflicted=include_conflicted,
                include_proposed=True,
            ),
            "contracts": _filter_records_by_status(
                contracts_records,
                include_obsolete=include_obsolete,
                include_conflicted=include_conflicted,
                include_proposed=True,
            ),
        },
    }


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
    stage_lower = stage.lower()
    is_concept_stage = stage_lower == "mvp.concept"
    is_design_stage = stage_lower == "mvp.design"
    is_tech_stage = stage_lower == "mvp.tech"
    concept_state = load_concept_state(paths.concept_state)
    design_state = load_design_state(paths.design_state) if is_design_stage else None
    tech_state = load_tech_state(paths.tech_state) if is_tech_stage else None
    if limit is None:
        resolved_limit = 3 if (is_concept_stage or is_design_stage or is_tech_stage) else 5
    elif limit <= 0:
        resolved_limit = 3 if (is_concept_stage or is_design_stage or is_tech_stage) else 5
    else:
        resolved_limit = limit
    include_history_records = include_history or not (is_concept_stage or is_design_stage or is_tech_stage)
    decision_log = read_jsonl(paths.decision_log) if include_history_records else []
    events = read_jsonl(paths.events) if include_history_records else []
    semantic_sets = _load_semantic_record_sets(
        paths,
        include_obsolete=include_obsolete,
        include_conflicted=include_conflicted,
    )
    semantic_facts = semantic_sets["validated"]["facts"]
    semantic_decisions = semantic_sets["validated"]["decisions"]
    semantic_contracts = semantic_sets["validated"]["contracts"]
    resolved_step_id = step_id or active_session.get("current_step") or progress.get("currentImplementStep")
    if not resolved_step_id and "implement" in stage_lower:
        resolved_step_id = _select_next_executable_step(progress)
    stage_facts = [
        record
        for record in semantic_sets["stage"]["facts"]
        if stage_lower in str(record.get("stage", "")).lower()
        and (not resolved_step_id or record.get("step_id") == resolved_step_id)
    ]
    stage_decisions = [
        record
        for record in semantic_sets["stage"]["decisions"]
        if stage_lower in str(record.get("stage", "")).lower()
        and (not resolved_step_id or record.get("step_id") == resolved_step_id)
    ]
    stage_contracts = [
        record
        for record in semantic_sets["stage"]["contracts"]
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
        "design_status": (
            _build_design_status(
                design_state,
                concept_state,
                project_path=project_path,
                branch_name=branch_name,
            )
            if is_design_stage and design_state is not None
            else None
        ),
        "tech_status": _build_tech_status(tech_state) if is_tech_stage and tech_state is not None else None,
        "episodes": trimmed_events if include_history_records else [],
        "decision_log": trimmed_decisions if include_history_records else [],
        "artifact_state": {
            "concept": concept_state if (is_concept_stage and full_artifact) else None,
            "design": design_state if (is_design_stage and full_artifact) else None,
            "tech": tech_state if (is_tech_stage and full_artifact) else None,
        },
    }
