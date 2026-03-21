from __future__ import annotations

from typing import Any


WORK_ITEM_TYPES = {
    "research",
    "architecture",
    "implementation",
    "testing",
    "docs",
    "security",
}

WORK_ITEM_STATUSES = {
    "open",
    "claimed",
    "in_progress",
    "completed",
    "blocked",
    "cancelled",
}

TASK_STATUSES = {"open", "active", "completed", "blocked", "cancelled"}


def make_work_item_owner_id(*, subagent_id: str, session_key: str) -> str:
    return f"work-item:{subagent_id}:{session_key}"


def normalize_scope_descriptor(payload: dict[str, Any] | None) -> dict[str, Any]:
    source = dict(payload or {})
    step_id = _normalize_optional_text(source.get("step_id"))
    paths = _normalize_list(source.get("paths"))
    artifacts = _normalize_list(source.get("artifacts"))
    concerns = _normalize_list(source.get("concerns"))
    normalized = {
        "step_id": step_id,
        "paths": paths,
        "artifacts": artifacts,
        "concerns": concerns,
    }
    if step_id and not any((paths, artifacts, concerns)):
        raise ValueError("step-bound work item requires at least one scope entry in paths, artifacts, or concerns")
    return normalized


def validate_work_item_type(work_item_type: str) -> str:
    normalized = str(work_item_type or "").strip().lower()
    if normalized not in WORK_ITEM_TYPES:
        raise ValueError(
            "work item type must be one of: " + ", ".join(sorted(WORK_ITEM_TYPES))
        )
    return normalized


def validate_work_item_status(status: str) -> str:
    normalized = str(status or "").strip().lower()
    if normalized not in WORK_ITEM_STATUSES:
        raise ValueError(
            "work item status must be one of: " + ", ".join(sorted(WORK_ITEM_STATUSES))
        )
    return normalized


def step_scope_overlaps(
    left: dict[str, Any] | None,
    right: dict[str, Any] | None,
) -> bool:
    left_scope = normalize_scope_descriptor(left)
    right_scope = normalize_scope_descriptor(right)
    if left_scope.get("step_id") != right_scope.get("step_id"):
        return False
    for key in ("paths", "artifacts", "concerns"):
        if set(left_scope.get(key, [])) & set(right_scope.get(key, [])):
            return True
    return False


def coordination_binding_from_session(session_payload: dict[str, Any] | None) -> dict[str, str | None]:
    payload = dict(session_payload or {})
    return {
        "task_id": _normalize_optional_text(payload.get("task_id")),
        "work_item_id": _normalize_optional_text(payload.get("work_item_id")),
        "subagent_id": _normalize_optional_text(payload.get("subagent_id")),
    }


def _normalize_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    unique: list[str] = []
    seen: set[str] = set()
    for item in value:
        normalized = str(item or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


def _normalize_optional_text(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None
