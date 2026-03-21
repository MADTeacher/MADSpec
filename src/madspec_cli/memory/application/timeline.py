from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
        stage=request.stage,
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
        items.append(
            {
                "timestamp": row.get("ts"),
                "source_type": "record",
                "source_id": row.get("record_id"),
                "stage": row.get("stage"),
                "step_id": row.get("step_id"),
                "status": row.get("status"),
                "summary": row.get("summary"),
                "kind": row.get("kind"),
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
            }
        )

    for row in proposal_rows:
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
            "items": items[: request.limit],
        }
    )
