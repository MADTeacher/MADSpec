from __future__ import annotations

from pathlib import Path
from typing import Any

from ..shared.storage import (
    _default_progress_state,
    get_memory_paths,
    read_json,
)
from ..shared.system_store.constants import SYSTEM_SESSION_KEY
from ..shared.system_store.sessions import load_runtime_session

IMPLEMENTATION_STAGES = {"mvp.implement", "feature.implement"}


def normalize_text_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    return [value.strip() for value in values if value and value.strip()]


def snapshot_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def restore_file(path: Path, content: str | None) -> None:
    if content is None:
        if path.exists():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def validate_implementation_stage(stage: str) -> str:
    normalized_stage = stage.strip().lower()
    if normalized_stage not in IMPLEMENTATION_STAGES:
        raise ValueError(
            "stage must be one of: " + ", ".join(sorted(IMPLEMENTATION_STAGES))
        )
    return normalized_stage


def load_progress(
    project_path: Path,
    branch_name: str,
    *,
    session_key: str = SYSTEM_SESSION_KEY,
) -> tuple[Any, Any]:
    paths = get_memory_paths(project_path, branch_name)
    progress = read_json(paths.progress, _default_progress_state())
    active_session = load_runtime_session(
        project_path,
        branch_name=branch_name,
        session_key=session_key,
    )
    return progress, active_session


def step_dependencies(progress: dict[str, Any], step_id: str) -> list[str]:
    return progress.get("planningMetadata", {}).get("stepDependencies", {}).get(step_id, [])


def is_step_ready(progress: dict[str, Any], step_id: str) -> bool:
    completed_steps = set(progress.get("completedSteps", []))
    return all(dependency in completed_steps for dependency in step_dependencies(progress, step_id))


def set_active_step(progress: dict[str, Any], step_id: str) -> None:
    for candidate, status_info in progress.get("stepStatus", {}).items():
        if not isinstance(status_info, dict):
            continue
        if candidate == step_id:
            status_info["status"] = "in_progress"
        elif status_info.get("status") == "in_progress":
            status_info["status"] = "planned"
    progress["currentImplementStep"] = step_id


def append_unique(existing: list[str], values: list[str]) -> list[str]:
    result = list(existing)
    for value in values:
        if value not in result:
            result.append(value)
    return result


def validate_start_step(progress: dict[str, Any], step_id: str) -> list[str]:
    errors: list[str] = []
    planned_steps = progress.get("plannedSteps", [])
    completed_steps = set(progress.get("completedSteps", []))
    if step_id not in planned_steps:
        errors.append(f"step '{step_id}' is not present in plannedSteps")
        return errors
    if step_id in completed_steps:
        errors.append(f"step '{step_id}' is already completed")
    if not is_step_ready(progress, step_id):
        errors.append(
            f"step '{step_id}' has incomplete dependencies: {', '.join(step_dependencies(progress, step_id))}"
        )
    return errors
