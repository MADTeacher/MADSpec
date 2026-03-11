from __future__ import annotations

from pathlib import Path
from typing import Any

from ..stages.architecture.state import (
    architecture_completeness_errors,
    load_architecture_state,
    render_architecture_markdown,
    render_data_model_markdown,
    render_openapi_yaml,
)
from ..stages.concept.state import concept_completeness_errors, load_concept_state, render_concept_markdown
from ..stages.design.state import (
    load_design_state,
    render_ui_design_markdown,
)
from ..stages.tech.state import (
    load_tech_state,
    render_tech_stack_markdown,
)
from ..domain.progress import select_next_executable_step
from .projections import (
    build_architecture_status,
    build_concept_status,
    build_design_status,
    build_tech_status,
    group_records_by_step,
    load_semantic_record_sets,
)
from .renderers import (
    render_planning_cache,
    render_project_context,
    render_review_artifacts,
    render_security_artifact,
    render_step_context,
)
from ..shared.storage import (
    _default_active_session,
    _default_progress_state,
    get_memory_paths,
    now_iso,
    read_json,
    read_jsonl,
)


def consolidate_branch_memory(project_path: Path, branch_name: str) -> list[Path]:
    paths = get_memory_paths(project_path, branch_name)
    progress = read_json(paths.progress, _default_progress_state())
    active_session = read_json(paths.active_session, _default_active_session(branch_name))
    concept_state = load_concept_state(paths.concept_state)
    design_state = load_design_state(paths.design_state)
    tech_state = load_tech_state(paths.tech_state)
    architecture_state = load_architecture_state(paths.architecture_state)
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

    architecture_path = paths.branch_dir / "architecture.md"
    architecture_path.write_text(
        render_architecture_markdown(
            architecture_state,
            branch_name=branch_name,
            project_name=concept_state.get("projectName", ""),
        ),
        encoding="utf-8",
    )
    generated.append(architecture_path)

    data_model_path = paths.branch_dir / "data-model.md"
    data_model_path.write_text(
        render_data_model_markdown(
            architecture_state,
            branch_name=branch_name,
            project_name=concept_state.get("projectName", ""),
        ),
        encoding="utf-8",
    )
    generated.append(data_model_path)

    contracts_dir = paths.branch_dir / "contracts"
    contracts_dir.mkdir(parents=True, exist_ok=True)
    openapi_path = contracts_dir / "openapi.yaml"
    openapi_path.write_text(
        render_openapi_yaml(architecture_state, branch_name=branch_name),
        encoding="utf-8",
    )
    generated.append(openapi_path)

    project_context_path = paths.branch_dir / "project-context.md"
    project_context_path.write_text(
        render_project_context(
            branch_name,
            progress,
            active_session,
            concept_state,
            design_state,
            tech_state,
            architecture_state,
            generated_at,
        ),
        encoding="utf-8",
    )
    generated.append(project_context_path)

    planning_cache_path = paths.branch_dir / "planning-context-cache.md"
    planning_cache_path.write_text(
        render_planning_cache(branch_name, progress, facts, decisions, contracts, generated_at),
        encoding="utf-8",
    )
    generated.append(planning_cache_path)

    all_records = decision_log + events + facts + decisions + contracts
    grouped_records = group_records_by_step(all_records)
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
            render_step_context(
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
            render_step_context(
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
    review_text, improvements_text = render_review_artifacts(
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
        render_security_artifact(security_records, generated_at),
        encoding="utf-8",
    )
    generated.append(security_path)
    return generated


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
    is_architecture_stage = stage_lower == "mvp.architecture"
    concept_state = load_concept_state(paths.concept_state)
    design_state = load_design_state(paths.design_state) if is_design_stage else None
    tech_state = load_tech_state(paths.tech_state) if is_tech_stage else None
    architecture_state = load_architecture_state(paths.architecture_state) if is_architecture_stage else None
    if limit is None:
        resolved_limit = 3 if (is_concept_stage or is_design_stage or is_tech_stage or is_architecture_stage) else 5
    elif limit <= 0:
        resolved_limit = 3 if (is_concept_stage or is_design_stage or is_tech_stage or is_architecture_stage) else 5
    else:
        resolved_limit = limit
    include_history_records = include_history or not (is_concept_stage or is_design_stage or is_tech_stage or is_architecture_stage)
    decision_log = read_jsonl(paths.decision_log) if include_history_records else []
    events = read_jsonl(paths.events) if include_history_records else []
    semantic_sets = load_semantic_record_sets(
        paths,
        include_obsolete=include_obsolete,
        include_conflicted=include_conflicted,
        read_records=read_jsonl,
    )
    semantic_facts = semantic_sets["validated"]["facts"]
    semantic_decisions = semantic_sets["validated"]["decisions"]
    semantic_contracts = semantic_sets["validated"]["contracts"]
    resolved_step_id = step_id or active_session.get("current_step") or progress.get("currentImplementStep")
    if not resolved_step_id and "implement" in stage_lower:
        resolved_step_id = select_next_executable_step(progress)
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
            "nextExecutableStep": select_next_executable_step(progress) if "implement" in stage_lower else None,
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
        "concept_status": build_concept_status(concept_state) if is_concept_stage else None,
        "design_status": (
            build_design_status(
                design_state,
                concept_state,
                project_path=project_path,
                branch_name=branch_name,
            )
            if is_design_stage and design_state is not None
            else None
        ),
        "tech_status": build_tech_status(tech_state) if is_tech_stage and tech_state is not None else None,
        "architecture_status": (
            build_architecture_status(
                architecture_state,
                design_state=load_design_state(paths.design_state),
            )
            if is_architecture_stage and architecture_state is not None
            else None
        ),
        "episodes": trimmed_events if include_history_records else [],
        "decision_log": trimmed_decisions if include_history_records else [],
        "artifact_state": {
            "concept": concept_state if (is_concept_stage and full_artifact) else None,
            "design": design_state if (is_design_stage and full_artifact) else None,
            "tech": tech_state if (is_tech_stage and full_artifact) else None,
            "architecture": architecture_state if (is_architecture_stage and full_artifact) else None,
        },
    }
