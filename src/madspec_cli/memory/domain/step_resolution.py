from __future__ import annotations

from typing import Any

from .progress import select_next_executable_step


def resolve_runtime_step_id(
    *,
    progress: dict[str, Any],
    session_payload: dict[str, Any] | None,
    stage: str,
    explicit_step_id: str | None,
    require_ready: bool = False,
) -> str | None:
    session_payload = session_payload or {}
    for candidate in (
        explicit_step_id,
        session_payload.get("current_step"),
        progress.get("currentImplementStep"),
    ):
        normalized_candidate = _normalized_step_id(candidate)
        if not normalized_candidate:
            continue
        if not require_ready or _is_ready_candidate(progress, normalized_candidate):
            return normalized_candidate

    if "implement" in stage.lower():
        return select_next_executable_step(progress)
    return None


def _normalized_step_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _is_ready_candidate(progress: dict[str, Any], step_id: str) -> bool:
    planned_steps = progress.get("plannedSteps", [])
    if step_id not in planned_steps:
        return False
    if step_id in set(progress.get("completedSteps", [])):
        return False
    dependencies = progress.get("planningMetadata", {}).get("stepDependencies", {}).get(step_id, [])
    completed_steps = set(progress.get("completedSteps", []))
    return all(dependency in completed_steps for dependency in dependencies)
