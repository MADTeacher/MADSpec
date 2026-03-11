from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .concept_state import concept_schema_errors, load_concept_state, render_concept_markdown
from .design_state import (
    design_reference_errors,
    design_schema_errors,
    is_empty_design_state,
    load_design_state,
    render_ui_design_markdown,
    uncovered_design_features,
)
from .planning import _compute_progress_metrics, extract_function_catalog
from .records import MEMORY_STATUSES, SEMANTIC_KINDS
from .storage import STEP_KINDS, TDD_PHASES, TDD_POLICIES
from .storage import get_memory_paths, read_json, read_jsonl


def _validate_record(record: dict[str, Any], *, allow_semantic_kind: bool = True) -> list[str]:
    errors: list[str] = []
    for key in ("id", "ts", "branch", "stage", "status", "source", "summary", "evidence"):
        if key not in record:
            errors.append(f"missing field '{key}'")
    if "status" in record and record["status"] not in MEMORY_STATUSES:
        errors.append(f"invalid status '{record['status']}'")
    if "evidence" in record and not isinstance(record["evidence"], list):
        errors.append("evidence must be a list")
    if "step_id" in record and record["step_id"] is not None and not isinstance(record["step_id"], str):
        errors.append("step_id must be a string or null")
    if "scope" in record and record["scope"] not in {"project", "branch", "step", "feature"}:
        errors.append(f"invalid scope '{record['scope']}'")
    if not allow_semantic_kind and "semantic_kind" in record:
        errors.append("semantic_kind is not allowed in this record set")
    if "semantic_kind" in record and record["semantic_kind"] not in SEMANTIC_KINDS:
        errors.append(f"invalid semantic_kind '{record['semantic_kind']}'")
    return errors


def _validate_progress(progress: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in (
        "currentImplementStep",
        "completedSteps",
        "plannedSteps",
        "stepStatus",
        "stepMetadata",
        "coversFunctions",
        "planningMetadata",
    ):
        if key not in progress:
            errors.append(f"progress.json missing '{key}'")
    if errors:
        return errors

    completed_steps = progress["completedSteps"]
    planned_steps = progress["plannedSteps"]
    step_status = progress["stepStatus"]
    step_metadata = progress["stepMetadata"]
    covers_functions = progress["coversFunctions"]
    planning_metadata = progress["planningMetadata"]

    if not isinstance(completed_steps, list) or not all(isinstance(item, str) for item in completed_steps):
        errors.append("completedSteps must be a list of strings")
    if not isinstance(planned_steps, list) or not all(isinstance(item, str) for item in planned_steps):
        errors.append("plannedSteps must be a list of strings")
    if not isinstance(step_status, dict):
        errors.append("stepStatus must be an object")
    if not isinstance(step_metadata, dict):
        errors.append("stepMetadata must be an object")
    if not isinstance(covers_functions, dict):
        errors.append("coversFunctions must be an object")
    if not isinstance(planning_metadata, dict):
        errors.append("planningMetadata must be an object")
    if errors:
        return errors

    current_step = progress["currentImplementStep"]
    if current_step is not None and current_step not in planned_steps:
        errors.append("currentImplementStep must be null or reference a planned step")
    for completed in completed_steps:
        if completed not in planned_steps:
            errors.append(f"completed step '{completed}' is not present in plannedSteps")

    step_dependencies = planning_metadata.get("stepDependencies", {})
    if not isinstance(step_dependencies, dict):
        errors.append("planningMetadata.stepDependencies must be an object")
        step_dependencies = {}

    for step_id, dependencies in step_dependencies.items():
        if step_id not in planned_steps:
            errors.append(f"dependency key '{step_id}' is not present in plannedSteps")
        if not isinstance(dependencies, list):
            errors.append(f"dependencies for '{step_id}' must be a list")
            continue
        for dependency in dependencies:
            if dependency not in planned_steps:
                errors.append(f"dependency '{dependency}' for '{step_id}' is not present in plannedSteps")

    for step_id, status_info in step_status.items():
        if step_id not in planned_steps and step_id not in completed_steps:
            errors.append(f"stepStatus key '{step_id}' is not present in planned/completed steps")
        if not isinstance(status_info, dict):
            errors.append(f"stepStatus['{step_id}'] must be an object")
            continue
        status = status_info.get("status")
        if status not in {"planned", "in_progress", "completed"}:
            errors.append(f"stepStatus['{step_id}'].status must be planned/in_progress/completed")
        tdd_phase = status_info.get("tddPhase")
        if tdd_phase not in TDD_PHASES:
            errors.append(
                f"stepStatus['{step_id}'].tddPhase must be one of: {', '.join(sorted(TDD_PHASES))}"
            )
        red_evidence = status_info.get("redEvidence")
        if not isinstance(red_evidence, list) or not all(isinstance(item, str) for item in red_evidence):
            errors.append(f"stepStatus['{step_id}'].redEvidence must be a list of strings")
        green_evidence = status_info.get("greenEvidence")
        if not isinstance(green_evidence, list) or not all(isinstance(item, str) for item in green_evidence):
            errors.append(f"stepStatus['{step_id}'].greenEvidence must be a list of strings")
        refactor_note = status_info.get("refactorNote")
        if refactor_note is not None and not isinstance(refactor_note, str):
            errors.append(f"stepStatus['{step_id}'].refactorNote must be a string or null")

    for step_id, metadata in step_metadata.items():
        if step_id not in planned_steps:
            errors.append(f"stepMetadata key '{step_id}' is not present in plannedSteps")
        if not isinstance(metadata, dict):
            errors.append(f"stepMetadata['{step_id}'] must be an object")
            continue
        kind = metadata.get("kind")
        if kind not in STEP_KINDS:
            errors.append(f"stepMetadata['{step_id}'].kind must be one of: {', '.join(sorted(STEP_KINDS))}")
        tdd_policy = metadata.get("tddPolicy")
        if tdd_policy not in TDD_POLICIES:
            errors.append(
                f"stepMetadata['{step_id}'].tddPolicy must be one of: {', '.join(sorted(TDD_POLICIES))}"
            )
        waiver_reason = metadata.get("waiverReason")
        if waiver_reason is not None and not isinstance(waiver_reason, str):
            errors.append(f"stepMetadata['{step_id}'].waiverReason must be a string or null")
        if kind == "code" and tdd_policy != "required":
            errors.append(f"code step '{step_id}' must use tddPolicy='required'")
        if kind == "non-code" and tdd_policy == "required":
            errors.append(f"non-code step '{step_id}' cannot use tddPolicy='required'")
        if tdd_policy == "waived" and not waiver_reason:
            errors.append(f"stepMetadata['{step_id}'].waiverReason is required when tddPolicy='waived'")

    for step_id in planned_steps:
        if step_id not in step_status:
            errors.append(f"planned step '{step_id}' is missing stepStatus")
        if step_id not in step_metadata:
            errors.append(f"planned step '{step_id}' is missing stepMetadata")

    for step_id in planned_steps:
        metadata = step_metadata.get(step_id)
        status_info = step_status.get(step_id)
        if not isinstance(metadata, dict) or not isinstance(status_info, dict):
            continue
        tdd_policy = metadata.get("tddPolicy")
        tdd_phase = status_info.get("tddPhase")
        is_completed = step_id in completed_steps or status_info.get("status") == "completed"
        if tdd_policy in {"waived", "not-applicable"} and tdd_phase != "waived":
            errors.append(f"step '{step_id}' must use tddPhase='waived' for non-required TDD policy")
        if is_completed and metadata.get("kind") == "code" and tdd_policy == "required":
            if tdd_phase != "completed":
                errors.append(f"completed code step '{step_id}' must have tddPhase='completed'")
            if not status_info.get("redEvidence"):
                errors.append(f"completed code step '{step_id}' must record redEvidence")
            if not status_info.get("greenEvidence"):
                errors.append(f"completed code step '{step_id}' must record greenEvidence")
            refactor_note = status_info.get("refactorNote")
            if not isinstance(refactor_note, str) or not refactor_note.strip():
                errors.append(f"completed code step '{step_id}' must record refactorNote")

    for step_id, coverage in covers_functions.items():
        if step_id not in planned_steps:
            errors.append(f"coversFunctions key '{step_id}' is not present in plannedSteps")
        if not isinstance(coverage, dict):
            errors.append(f"coversFunctions['{step_id}'] must be an object")
            continue
        for priority in ("p1", "p2", "p3"):
            if priority not in coverage:
                errors.append(f"coversFunctions['{step_id}'] missing '{priority}'")
                continue
            values = coverage[priority]
            if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
                errors.append(f"coversFunctions['{step_id}']['{priority}'] must be a list of strings")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visited or node not in step_dependencies:
            return
        if node in visiting:
            errors.append(f"dependency cycle detected at '{node}'")
            return
        visiting.add(node)
        for child in step_dependencies.get(node, []):
            visit(child)
        visiting.remove(node)
        visited.add(node)

    for step_id in step_dependencies:
        visit(step_id)

    return errors


def validate_branch_memory(project_path: Path, branch_name: str) -> list[str]:
    paths = get_memory_paths(project_path, branch_name)
    errors: list[str] = []

    progress = read_json(paths.progress, None)
    if not isinstance(progress, dict):
        errors.append("progress.json must contain a JSON object")
    else:
        errors.extend(_validate_progress(progress))
        catalog: dict[str, list[str]] = {}
        for stage_name in ("mvp.plan", "feature.plan"):
            stage_catalog = extract_function_catalog(project_path, branch_name, stage_name)
            if any(stage_catalog.values()):
                catalog = stage_catalog
                break
        if catalog:
            known_functions = {item for values in catalog.values() for item in values}
            for step_id, coverage in progress.get("coversFunctions", {}).items():
                if not isinstance(coverage, dict):
                    continue
                for priority, values in coverage.items():
                    if not isinstance(values, list):
                        continue
                    for value in values:
                        if value not in known_functions:
                            errors.append(
                                f"coversFunctions['{step_id}']['{priority}'] references unknown function '{value}'"
                            )
            expected_metrics = _compute_progress_metrics(catalog, progress.get("coversFunctions", {}))
            current_metrics = progress.get("planningMetadata", {}).get("progressMetrics", {})
            if current_metrics != expected_metrics:
                errors.append("planningMetadata.progressMetrics is out of sync with coversFunctions")

    active_session = read_json(paths.active_session, None)
    if not isinstance(active_session, dict):
        errors.append("active-session.json must contain a JSON object")
    else:
        for key in (
            "branch",
            "active_goal",
            "stage",
            "current_step",
            "pending_actions",
            "open_questions",
            "current_hypotheses",
            "last_checkpoint_at",
            "updated_at",
        ):
            if key not in active_session:
                errors.append(f"active-session.json missing '{key}'")
        if active_session.get("branch") != branch_name:
            errors.append("active-session.json branch does not match target branch")
        for key in ("pending_actions", "open_questions", "current_hypotheses"):
            if key in active_session and not isinstance(active_session[key], list):
                errors.append(f"active-session.json field '{key}' must be a list")

    concept_state_raw = read_json(paths.concept_state, None)
    errors.extend(f"{paths.concept_state.name}: {item}" for item in concept_schema_errors(concept_state_raw))
    concept_state = load_concept_state(paths.concept_state)
    concept_text = render_concept_markdown(concept_state)
    concept_path = paths.branch_dir / "concept.md"
    if not concept_path.exists():
        errors.append("concept.md is missing; rebuild generated views with `madspec memory consolidate`")
    elif concept_path.read_text(encoding="utf-8") != concept_text:
        errors.append("concept.md is out of sync with memory/stages/mvp.concept.json")

    design_state_raw = read_json(paths.design_state, None)
    errors.extend(f"{paths.design_state.name}: {item}" for item in design_schema_errors(design_state_raw))
    design_state = load_design_state(paths.design_state)
    design_path = paths.branch_dir / "ui-design.md"
    design_text = render_ui_design_markdown(
        design_state,
        branch_name=branch_name,
        project_name=concept_state.get("projectName", ""),
    )
    if not design_path.exists():
        errors.append("ui-design.md is missing; rebuild generated views with `madspec memory consolidate`")
    elif not is_empty_design_state(design_state) and design_path.read_text(encoding="utf-8") != design_text:
        errors.append("ui-design.md is out of sync with memory/stages/mvp.design.json")

    if not is_empty_design_state(design_state):
        errors.extend(
            design_reference_errors(
                design_state,
                project_path=project_path,
                branch_name=branch_name,
            )
        )
        uncovered_features = uncovered_design_features(design_state, concept_state)
        for priority, values in uncovered_features.items():
            for value in values:
                errors.append(f"design coverage missing {priority.upper()} concept feature '{value}'")

    for path in (
        paths.decision_log,
        paths.events,
        paths.facts,
        paths.decisions,
        paths.contracts,
    ):
        try:
            records = read_jsonl(path)
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name} contains invalid JSONL: {exc}")
            continue
        for index, record in enumerate(records, start=1):
            record_errors = _validate_record(record)
            errors.extend(f"{path.name}:{index}: {item}" for item in record_errors)

    return errors
