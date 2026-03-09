from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .planning import _compute_progress_metrics, extract_function_catalog
from .records import MEMORY_STATUSES, SEMANTIC_KINDS
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
    covers_functions = progress["coversFunctions"]
    planning_metadata = progress["planningMetadata"]

    if not isinstance(completed_steps, list) or not all(isinstance(item, str) for item in completed_steps):
        errors.append("completedSteps must be a list of strings")
    if not isinstance(planned_steps, list) or not all(isinstance(item, str) for item in planned_steps):
        errors.append("plannedSteps must be a list of strings")
    if not isinstance(step_status, dict):
        errors.append("stepStatus must be an object")
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
                for priority, values in coverage.items():
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
