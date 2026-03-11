from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.memory import ensure_memory_layout, retrieve_memory_context
from madspec_cli.shared.kernel.result import PayloadResult


@dataclass(frozen=True)
class RetrieveMemoryContextRequest:
    project_path: Path
    branch_name: str
    stage: str
    step_id: str | None
    limit: int
    include_obsolete: bool
    include_conflicted: bool
    full_artifact: bool
    include_history: bool


@dataclass(frozen=True)
class RetrieveMemoryContextResult(PayloadResult):
    pass


def execute(request: RetrieveMemoryContextRequest) -> RetrieveMemoryContextResult:
    ensure_memory_layout(request.project_path, request.branch_name)
    payload = retrieve_memory_context(
        request.project_path,
        request.branch_name,
        request.stage,
        step_id=request.step_id,
        limit=request.limit,
        include_obsolete=request.include_obsolete,
        include_conflicted=request.include_conflicted,
        full_artifact=request.full_artifact,
        include_history=request.include_history,
    )
    return RetrieveMemoryContextResult(payload=payload)
