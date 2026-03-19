from __future__ import annotations

from pathlib import Path
from typing import Any

from .materialize import consolidate_branch_memory as _consolidate_branch_memory
from .retrieve import retrieve_memory_context as _retrieve_memory_context


def consolidate_branch_memory(
    project_path: Path,
    branch_name: str,
    *,
    stage: str | None = None,
    full: bool = False,
) -> list[Path]:
    return _consolidate_branch_memory(project_path, branch_name, stage=stage, full=full)


def retrieve_memory_context(
    project_path: Path,
    branch_name: str,
    stage: str,
    *,
    step_id: str | None = None,
    limit: int | None = None,
    query: str | None = None,
    disable_semantic: bool = False,
    recall_limit: int | None = None,
    scope: str = "branch",
    include_obsolete: bool = False,
    include_conflicted: bool = False,
    full_artifact: bool = False,
    include_history: bool = False,
) -> dict[str, Any]:
    return _retrieve_memory_context(
        project_path,
        branch_name,
        stage,
        step_id=step_id,
        limit=limit,
        query=query,
        disable_semantic=disable_semantic,
        recall_limit=recall_limit,
        scope=scope,
        include_obsolete=include_obsolete,
        include_conflicted=include_conflicted,
        full_artifact=full_artifact,
        include_history=include_history,
    )
