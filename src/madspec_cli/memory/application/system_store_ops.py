from __future__ import annotations

from pathlib import Path
from typing import Any

from ..shared.system_store import build_db_status as _build_db_status
from ..shared.system_store import run_reindex as _run_reindex


def build_db_status(project_path: Path, branch_name: str | None = None) -> dict[str, Any]:
    return _build_db_status(project_path, branch_name)


def run_reindex(project_path: Path, branch_name: str | None = None, *, limit: int = 200) -> dict[str, Any]:
    return _run_reindex(project_path, branch_name, limit=limit)
