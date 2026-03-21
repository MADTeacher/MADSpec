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
TERMINAL_WORK_ITEM_STATUSES = {"completed", "cancelled"}


def normalize_scheduling_hints(payload: dict[str, Any] | None) -> dict[str, Any]:
    source = dict(payload or {})
    return {
        "default_stage": _normalize_optional_text(source.get("default_stage")),
        "execution_mode_hint": _normalize_optional_text(source.get("execution_mode_hint")),
        "subagent_dependencies": _normalize_list(source.get("subagent_dependencies")),
    }


def build_work_item_readiness(
    *,
    work_item: dict[str, Any],
    dependencies: list[dict[str, Any]] | None,
    active_claim: dict[str, Any] | None,
    related_proposals: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    dependency_items = list(dependencies or [])
    proposal_items = list(related_proposals or [])
    status = str(work_item.get("status") or "open")
    blocked_reasons: list[dict[str, Any]] = []
    unmet_dependencies: list[dict[str, Any]] = []
    for item in dependency_items:
        dependency_status = str(item.get("status") or "open")
        if dependency_status not in TERMINAL_WORK_ITEM_STATUSES:
            unmet_dependencies.append(
                {
                    "work_item_id": item.get("work_item_id"),
                    "title": item.get("title"),
                    "status": dependency_status,
                }
            )
    if unmet_dependencies:
        blocked_reasons.append(
            {
                "code": "dependencies_unfinished",
                "message": "work item is waiting for explicit dependency work items to finish",
                "dependencies": unmet_dependencies,
            }
        )
    if active_claim is not None and str(active_claim.get("session_key") or "") != str(work_item.get("session_key") or ""):
        blocked_reasons.append(
            {
                "code": "claimed_by_other_session",
                "message": "work item is already claimed by another session",
                "claim": {
                    "session_key": active_claim.get("session_key"),
                    "subagent_id": active_claim.get("subagent_id"),
                    "owner_id": active_claim.get("owner_id"),
                },
            }
        )
    pending_proposals = [
        {
            "proposal_id": item.get("proposal_id"),
            "proposal_type": item.get("proposal_type"),
            "status": item.get("status"),
        }
        for item in proposal_items
        if item.get("status") == "pending"
    ]

    if status in TERMINAL_WORK_ITEM_STATUSES:
        readiness_status = status
    elif status in {"claimed", "in_progress"}:
        readiness_status = "active"
    elif blocked_reasons:
        readiness_status = "blocked"
    else:
        readiness_status = "ready"

    return {
        "readiness_status": readiness_status,
        "blocked_reasons": blocked_reasons,
        "dependency_state": {
            "dependencies": dependency_items,
            "unmet_dependencies": unmet_dependencies,
            "pending_proposals": pending_proposals,
        },
        "related_proposals": proposal_items[:10],
        "scheduler_hints": normalize_scheduling_hints(work_item.get("scheduling_hints")),
    }


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
