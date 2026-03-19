from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.memory.shared.system_store.store import MemoryStore
from madspec_cli.shared.kernel.result import PayloadResult

from .diagnostics_shared import locate_record_source, simplify_record


@dataclass(frozen=True)
class InspectRecordRequest:
    project_path: Path
    branch_name: str
    record_id: str
    related_limit: int


@dataclass(frozen=True)
class InspectRecordResult(PayloadResult):
    @property
    def found(self) -> bool:
        return bool(self.payload.get("found"))


def execute(request: InspectRecordRequest) -> InspectRecordResult:
    store = MemoryStore(request.project_path)
    record = store.fetch_record_details(request.record_id)
    if record is None:
        return InspectRecordResult(
            payload={
                "found": False,
                "record_id": request.record_id,
                "error": f"record '{request.record_id}' was not found",
            }
        )

    related_rows = store.list_records(
        branch=record["branch"],
        stage=record["stage"],
        step_id=record["step_id"],
        limit=max(request.related_limit + 1, 6),
    )
    related = [
        simplify_record(item)
        for item in related_rows
        if item["record_id"] != request.record_id
    ][: request.related_limit]

    return InspectRecordResult(
        payload={
            "found": True,
            "record": {
                "payload": record["payload"],
                "search_text": record["search_text"],
                "content_hash": record["content_hash"],
                "kind": record["kind"],
                "semantic_kind": record["semantic_kind"],
                "scope": record["scope"],
                "summary": record["summary"],
                "ts": record["ts"],
            },
            "source_file": locate_record_source(
                request.project_path,
                request.branch_name,
                request.record_id,
            ),
            "indexed": store.describe_record_index(request.record_id),
            "related": related,
        }
    )
