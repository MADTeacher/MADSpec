from __future__ import annotations

from pathlib import Path
from typing import Any

from .projection import views as _impl

read_jsonl = _impl.read_jsonl


def consolidate_branch_memory(project_path: Path, branch_name: str) -> list[Path]:
    return _impl.consolidate_branch_memory(project_path, branch_name)


def retrieve_memory_context(
    project_path: Path,
    branch_name: str,
    stage: str,
    *,
    step_id: str | None = None,
    limit: int | None = None,
    include_obsolete: bool = False,
    include_conflicted: bool = False,
    full_artifact: bool = False,
    include_history: bool = False,
) -> dict[str, Any]:
    _impl.read_jsonl = read_jsonl
    return _impl.retrieve_memory_context(
        project_path,
        branch_name,
        stage,
        step_id=step_id,
        limit=limit,
        include_obsolete=include_obsolete,
        include_conflicted=include_conflicted,
        full_artifact=full_artifact,
        include_history=include_history,
    )
