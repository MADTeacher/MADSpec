from __future__ import annotations

from typing import Any


def select_next_executable_step(progress: dict[str, Any]) -> str | None:
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
