from __future__ import annotations

from pathlib import Path
from typing import Any

from madspec_cli.memory.domain.step_resolution import resolve_runtime_step_id
from madspec_cli.memory.shared import SYSTEM_SESSION_KEY, load_runtime_session
from madspec_cli.memory.workflow.implementation_shared import IMPLEMENTATION_STAGES


SUPPORTED_GATE_STAGES = {
    "mvp.plan",
    "feature.plan",
    "mvp.implement",
    "feature.implement",
    "review",
    "security",
}


def normalize_gate_stage(
    value: str | None,
    *,
    project_path: Path | None = None,
    branch_name: str | None = None,
    session_key: str = SYSTEM_SESSION_KEY,
) -> str:
    normalized = (value or "").strip().lower()
    if normalized in SUPPORTED_GATE_STAGES:
        return normalized
    if project_path is not None and branch_name is not None:
        active_session = load_runtime_session(
            project_path,
            branch_name=branch_name,
            session_key=session_key,
        )
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
    session_payload: dict[str, Any],
    stage: str,
    operation: str,
    explicit_step_id: str | None,
) -> str | None:
    if operation == "register-step":
        return explicit_step_id
    return resolve_runtime_step_id(
        progress=progress,
        session_payload=session_payload,
        stage=stage if stage in IMPLEMENTATION_STAGES else "",
        explicit_step_id=explicit_step_id,
        require_ready=operation == "start-step" and stage in IMPLEMENTATION_STAGES,
    )
