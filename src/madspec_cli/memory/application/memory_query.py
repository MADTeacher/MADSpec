from __future__ import annotations

from pathlib import Path
from typing import Any

from ..shared.system_store import search_memory_store as _search_memory_store
from ..shared.system_store.sessions import load_runtime_session as _load_runtime_session


def search_memory_store(
    project_path: Path,
    *,
    branch_name: str,
    stage: str,
    step_id: str | None,
    query: str | None,
    scope: str = "branch",
    recall_limit: int = 5,
    disable_semantic: bool = False,
    include_obsolete: bool = False,
    include_conflicted: bool = False,
    active_session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _search_memory_store(
        project_path,
        branch_name=branch_name,
        stage=stage,
        step_id=step_id,
        query=query,
        scope=scope,
        recall_limit=recall_limit,
        disable_semantic=disable_semantic,
        include_obsolete=include_obsolete,
        include_conflicted=include_conflicted,
        active_session=active_session,
    )


def load_runtime_session(
    project_path: Path,
    *,
    branch_name: str,
    session_key: str = "active",
    create_if_missing: bool = True,
) -> dict[str, Any]:
    return _load_runtime_session(
        project_path,
        branch_name=branch_name,
        session_key=session_key,
        create_if_missing=create_if_missing,
    )
