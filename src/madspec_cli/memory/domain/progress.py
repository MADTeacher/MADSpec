from __future__ import annotations

from typing import Any


def explain_next_executable_step(progress: dict[str, Any]) -> dict[str, Any]:
    planned_steps = [
        step_id
        for step_id in progress.get("plannedSteps", [])
        if isinstance(step_id, str) and step_id.strip()
    ]
    completed_steps = {
        step_id
        for step_id in progress.get("completedSteps", [])
        if isinstance(step_id, str) and step_id.strip()
    }
    raw_dependencies = progress.get("planningMetadata", {}).get("stepDependencies", {})
    step_dependencies = raw_dependencies if isinstance(raw_dependencies, dict) else {}
    raw_status = progress.get("stepStatus", {})
    step_status = raw_status if isinstance(raw_status, dict) else {}
    raw_metadata = progress.get("stepMetadata", {})
    step_metadata = raw_metadata if isinstance(raw_metadata, dict) else {}

    steps: list[dict[str, Any]] = []
    executable_steps: list[str] = []
    selected_step: str | None = None

    for position, step_id in enumerate(planned_steps, start=1):
        dependencies = [
            dependency
            for dependency in step_dependencies.get(step_id, [])
            if isinstance(dependency, str) and dependency.strip()
        ]
        missing_dependencies = [
            dependency for dependency in dependencies if dependency not in completed_steps
        ]
        status_info = step_status.get(step_id, {})
        if not isinstance(status_info, dict):
            status_info = {}
        metadata = step_metadata.get(step_id, {})
        if not isinstance(metadata, dict):
            metadata = {}

        completed = step_id in completed_steps or status_info.get("status") == "completed"
        if completed:
            state = "completed"
            reason = "step is already completed"
        elif missing_dependencies:
            state = "blocked"
            reason = "step is waiting for unfinished dependencies"
        else:
            state = "ready"
            reason = "all dependencies are satisfied"
            executable_steps.append(step_id)
            if selected_step is None:
                selected_step = step_id

        steps.append(
            {
                "step_id": step_id,
                "position": position,
                "state": state,
                "completed": completed,
                "dependencies": dependencies,
                "missing_dependencies": missing_dependencies,
                "status": status_info,
                "metadata": metadata,
                "is_selected": step_id == selected_step,
                "reason": reason,
            }
        )

    if not planned_steps:
        reason = "no planned steps are registered"
    elif selected_step is not None:
        reason = "selected the first ready step in planning order"
    elif any(item["state"] == "blocked" for item in steps):
        reason = "no executable step is available because all remaining steps are blocked"
    else:
        reason = "no executable step is available because all planned steps are already completed"

    if selected_step is not None:
        for item in steps:
            item["is_selected"] = item["step_id"] == selected_step

    return {
        "selected_step": selected_step,
        "executable_steps": executable_steps,
        "reason": reason,
        "steps": steps,
    }


def select_next_executable_step(progress: dict[str, Any]) -> str | None:
    return explain_next_executable_step(progress)["selected_step"]
