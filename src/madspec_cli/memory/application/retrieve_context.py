from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from ..projection.retrieve import retrieve_memory_context
from ..shared.storage import ensure_memory_layout


@dataclass(frozen=True)
class RetrieveMemoryContextRequest:
    project_path: Path
    branch_name: str
    stage: str
    session_key: str
    step_id: str | None
    limit: int
    query: str | None
    disable_semantic: bool
    recall_limit: int
    scope: str
    include_obsolete: bool
    include_conflicted: bool
    full_artifact: bool
    include_history: bool


@dataclass(frozen=True)
class RetrieveMemoryContextResult(PayloadResult):
    pass


def execute(request: RetrieveMemoryContextRequest) -> RetrieveMemoryContextResult:
    ensure_memory_layout(request.project_path, request.branch_name, stage=request.stage)
    payload = retrieve_memory_context(
        request.project_path,
        request.branch_name,
        request.stage,
        session_key=request.session_key,
        step_id=request.step_id,
        limit=request.limit,
        query=request.query,
        disable_semantic=request.disable_semantic,
        recall_limit=request.recall_limit,
        scope=request.scope,
        include_obsolete=request.include_obsolete,
        include_conflicted=request.include_conflicted,
        full_artifact=request.full_artifact,
        include_history=request.include_history,
    )
    return RetrieveMemoryContextResult(payload=payload)
