from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.memory.shared.system_store.store import MemoryStore
from madspec_cli.memory.shared.validation import validate_branch_memory
from madspec_cli.shared.kernel.result import PayloadResult

from .diagnostics_shared import simplify_record


@dataclass(frozen=True)
class MemoryConflictsRequest:
    project_path: Path
    branch_name: str
    stage: str | None
    step_id: str | None
    limit: int


@dataclass(frozen=True)
class MemoryConflictsResult(PayloadResult):
    pass


def execute(request: MemoryConflictsRequest) -> MemoryConflictsResult:
    store = MemoryStore(request.project_path)
    record_conflicts = [
        simplify_record(item)
        for item in store.list_records(
            branch=request.branch_name,
            stage=request.stage,
            step_id=request.step_id,
            statuses=["conflicted"],
            limit=request.limit,
        )
    ]
    integrity_conflicts = [
        {"message": message}
        for message in validate_branch_memory(request.project_path, request.branch_name)
    ]

    return MemoryConflictsResult(
        payload={
            "branch": request.branch_name,
            "stage": request.stage,
            "step_id": request.step_id,
            "record_conflicts": record_conflicts,
            "integrity_conflicts": integrity_conflicts[: request.limit],
        }
    )
