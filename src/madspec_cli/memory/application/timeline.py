from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .observability import build_runtime_observability
from madspec_cli.memory.shared.system_store.store import MemoryStore
from madspec_cli.shared.kernel.result import PayloadResult


@dataclass(frozen=True)
class TimelineRequest:
    project_path: Path
    branch_name: str
    stage: str | None
    step_id: str | None
    limit: int


@dataclass(frozen=True)
class TimelineResult(PayloadResult):
    pass


def execute(request: TimelineRequest) -> TimelineResult:
    store = MemoryStore(request.project_path)

    record_rows = store.list_records(
        branch=request.branch_name,
        stage=None,
        step_id=request.step_id,
        limit=max(request.limit * 4, 50),
    )
    snapshot_rows = store.list_stage_snapshots(
        branch=request.branch_name,
        limit=max(request.limit * 2, 20),
    )
    retrieval_rows = store.list_retrieval_runs(
        branch=request.branch_name,
        stage=request.stage,
        step_id=request.step_id,
        limit=max(request.limit * 2, 20),
    )
    proposal_rows = store.list_runtime_proposal_events(
        branch=request.branch_name,
        limit=max(request.limit * 2, 20),
    )

    items: list[dict[str, Any]] = []
    for row in record_rows:
        if row.get("source") == "memory.proposal":
            continue
        row_stage = row.get("stage")
        if request.stage and row_stage not in {request.stage, "coordination"}:
            continue
        normalized = _normalize_record_event(row)
        items.append(
            {
                "timestamp": row.get("ts"),
                "source_type": "record",
                "source_id": row.get("record_id"),
                "stage": row_stage,
                "step_id": row.get("step_id"),
                "status": row.get("status"),
                "summary": row.get("summary"),
                "kind": row.get("kind"),
                **normalized,
            }
        )

    for row in snapshot_rows:
        if request.stage and row["stage"] not in {request.stage, "runtime.progress"}:
            continue
        items.append(
            {
                "timestamp": row.get("updated_at"),
                "source_type": "snapshot",
                "source_id": f"{row['branch']}:{row['snapshot_key']}",
                "stage": row.get("stage"),
                "step_id": None,
                "status": "validated",
                "summary": row.get("summary") or row.get("snapshot_key"),
                "kind": "snapshot",
                "event_type": "shared.commit",
                "category": "shared_commit",
                "reason": "Canonical snapshot was committed and projected for the branch.",
                "owner_id": None,
                "session_key": None,
                "task_id": None,
                "work_item_id": None,
                "proposal_id": None,
                "scope": "branch",
            }
        )

    for row in retrieval_rows:
        if request.stage and row["stage"] != request.stage:
            continue
        if request.step_id and row.get("step_id") != request.step_id:
            continue
        summary = f"Recall query: {row['query'] or '<auto>'}"
        items.append(
            {
                "timestamp": row.get("created_at"),
                "source_type": "retrieval_run",
                "source_id": row.get("run_id"),
                "stage": row.get("stage"),
                "step_id": row.get("step_id"),
                "status": "validated",
                "summary": summary,
                "kind": "retrieval_run",
                "event_type": "retrieval.run",
                "category": "session_event",
                "reason": "Runtime retrieval context was materialized for a session or stage query.",
                "owner_id": None,
                "session_key": None,
                "task_id": None,
                "work_item_id": None,
                "proposal_id": None,
                "scope": "branch",
            }
        )

    for row in proposal_rows:
        normalized = _normalize_proposal_event(row)
        items.append(
            {
                "timestamp": row.get("ts"),
                "source_type": "proposal_event",
                "source_id": row.get("event_id"),
                "stage": "coordination",
                "step_id": (row.get("payload") or {}).get("step_id"),
                "status": row.get("event_type"),
                "summary": row.get("summary"),
                "kind": "proposal_event",
                **normalized,
            }
        )

    items.sort(
        key=lambda item: (
            item.get("timestamp") or "",
            item.get("source_type") or "",
            item.get("source_id") or "",
        ),
        reverse=True,
    )

    return TimelineResult(
        payload={
            "branch": request.branch_name,
            "stage": request.stage,
            "step_id": request.step_id,
            "observability": build_runtime_observability(
                request.project_path,
                branch_name=request.branch_name,
                stage=request.stage,
                step_id=request.step_id,
                limit=request.limit,
            ),
            "items": items[: request.limit],
        }
    )


def _normalize_record_event(row: dict[str, Any]) -> dict[str, Any]:
    payload = row.get("payload") or {}
    event_type = payload.get("event_type") or row.get("source") or "record.updated"
    category = "session_event"
    reason = "Runtime event was recorded in the canonical event stream."
    if row.get("status") == "conflicted":
        category = "conflict"
        reason = "Canonical record was marked as conflicted."
    elif str(event_type).startswith("work-item."):
        category = "session_event"
        reason = "Coordinator session ownership changed for a work item."
    work_item = payload.get("work_item") or {}
    task = payload.get("task") or {}
    return {
        "event_type": event_type,
        "category": category,
        "reason": reason,
        "owner_id": payload.get("owner_id") or work_item.get("owner_id"),
        "session_key": payload.get("session_key") or work_item.get("session_key"),
        "task_id": payload.get("task_id") or work_item.get("task_id") or task.get("task_id"),
        "work_item_id": payload.get("work_item_id") or work_item.get("work_item_id"),
        "proposal_id": payload.get("proposal_id"),
        "scope": row.get("scope"),
    }


def _normalize_proposal_event(row: dict[str, Any]) -> dict[str, Any]:
    event_type = row.get("event_type") or "proposal.unknown"
    category = "proposal_event"
    reason = "Proposal lifecycle changed."
    if event_type == "proposal.applied":
        category = "auto_merge"
        reason = "Proposal was applied cleanly to canonical runtime state."
    elif event_type == "proposal.conflict":
        category = "conflict"
        reason = "Proposal could not be applied cleanly and moved to conflict state."
    elif event_type == "proposal.rejected":
        category = "conflict"
        reason = "Proposal was rejected because ownership, readiness, or runtime state no longer matched."
    payload = row.get("payload") or {}
    return {
        "event_type": event_type,
        "category": category,
        "reason": reason,
        "owner_id": payload.get("owner_id"),
        "session_key": payload.get("session_key"),
        "task_id": row.get("task_id"),
        "work_item_id": row.get("work_item_id"),
        "proposal_id": row.get("proposal_id"),
        "scope": (payload.get("result") or {}).get("conflict", {}).get("scope") or "work-item",
    }
