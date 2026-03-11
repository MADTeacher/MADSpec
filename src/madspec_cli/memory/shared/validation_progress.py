from __future__ import annotations

from typing import Any

from .storage import STEP_KINDS, TDD_PHASES, TDD_POLICIES


def validate_progress(progress: dict[str, Any]) -> list[str]:
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
