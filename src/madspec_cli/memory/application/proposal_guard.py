from __future__ import annotations

from pathlib import Path
from typing import Any

from .parallel_runtime import is_phase2_enabled
from ..shared.system_store.store import MemoryStore


PROPOSAL_REQUIRED_COMMANDS = {
    "capture": "madspec memory proposals publish --type semantic_update",
    "checkpoint": "madspec memory proposals publish --type semantic_update",
    "register-step": "madspec memory proposals publish --type plan_change",
    "start-step": "madspec memory proposals publish --type runtime_step_update",
    "checkpoint-step": "madspec memory proposals publish --type runtime_step_update",
    "complete-step": "madspec memory proposals publish --type runtime_step_update",
}


def guard_direct_runtime_write(
    project_path: Path,
    *,
    branch_name: str,
    session_key: str,
    command_name: str,
    allow_proposal_guidance: bool = True,
    blocked_guidance: str | None = None,
) -> dict[str, Any] | None:
    if not is_phase2_enabled(project_path):
        return None
    coordination = MemoryStore(project_path).fetch_session_coordination(
        branch=branch_name,
        session_key=session_key,
    )
    if coordination.get("claim") is None or coordination.get("work_item") is None:
        return None
    work_item = coordination["work_item"]
    claim = coordination["claim"]
    primary_error = (
        f"session '{session_key}' is bound to claimed work item '{work_item['work_item_id']}' and must use proposal-based writes"
        if allow_proposal_guidance
        else f"session '{session_key}' is bound to claimed work item '{work_item['work_item_id']}' and cannot run direct {command_name} writes"
    )
    payload = {
        "accepted": False,
        "errors": [primary_error],
        "coordination": coordination,
    }
    if allow_proposal_guidance:
        guidance = blocked_guidance or PROPOSAL_REQUIRED_COMMANDS.get(command_name, "madspec memory proposals publish")
        payload["errors"].append(
            f"publish a proposal via `{guidance}` and apply it through `madspec memory proposals apply`"
        )
        payload["proposal_required"] = {
            "session_key": session_key,
            "work_item_id": work_item["work_item_id"],
            "task_id": work_item["task_id"],
            "owner_id": claim.get("owner_id"),
            "recommended_command": guidance,
        }
    elif blocked_guidance:
        payload["errors"].append(blocked_guidance)
    return payload
