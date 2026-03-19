from __future__ import annotations

from pathlib import Path
from typing import Any

from madspec_cli.memory.domain.progress import select_next_executable_step
from madspec_cli.memory.shared.storage import (
    _default_active_session,
    get_memory_paths,
    read_json,
)
from madspec_cli.memory.workflow.implementation_shared import IMPLEMENTATION_STAGES


SUPPORTED_GATE_STAGES = {
    "mvp.plan",
    "feature.plan",
    "mvp.implement",
    "feature.implement",
    "review",
    "security",
}


def normalize_gate_stage(value: str | None, *, project_path: Path | None = None, branch_name: str | None = None) -> str:
    normalized = (value or "").strip().lower()
    if normalized in SUPPORTED_GATE_STAGES:
        return normalized
    if project_path is not None and branch_name is not None:
        paths = get_memory_paths(project_path, branch_name)
        active_session = read_json(paths.active_session, _default_active_session(branch_name))
        candidate = str(active_session.get("stage", "")).strip().lower()
        if candidate in SUPPORTED_GATE_STAGES:
            return candidate
    return "review"


def normalize_gate_operation(value: str | None) -> str:
    normalized = (value or "validate").strip().lower()
    return normalized or "validate"


def resolve_step_id(
    *,
    progress: dict[str, Any],
    active_session: dict[str, Any],
    stage: str,
    operation: str,
    explicit_step_id: str | None,
) -> str | None:
    if explicit_step_id:
        return explicit_step_id
    if operation == "register-step":
        return explicit_step_id
    if stage in IMPLEMENTATION_STAGES:
        if operation == "start-step":
            return select_next_executable_step(progress)
        return progress.get("currentImplementStep") or active_session.get("current_step")
    return active_session.get("current_step") or progress.get("currentImplementStep")
