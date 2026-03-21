from __future__ import annotations

from pathlib import Path
from typing import Any

from .canonical_state import refresh_branch_projections
from .layout import ensure_system_memory_layout
from .store import MemoryStore


def commit_runtime_mutation(
    project_path: Path,
    *,
    branch_name: str,
    stage: str | None,
    stage_snapshots: list[dict[str, Any]],
    sessions: list[dict[str, Any]],
    records: list[dict[str, Any]],
    full: bool = False,
) -> dict[str, Any]:
    ensure_system_memory_layout(project_path)
    MemoryStore(project_path).commit_runtime_mutation(
        branch=branch_name,
        stage_snapshots=stage_snapshots,
        sessions=sessions,
        records=records,
    )

    generated_views: list[str] = []
    warnings: list[str] = []
    projection_status = "synced"
    projection_refresh_required = False
    try:
        _, generated_paths = refresh_branch_projections(
            project_path,
            branch_name,
            stage=stage,
            full=full,
        )
        generated_views = [str(path.relative_to(project_path)) for path in generated_paths]
        from ..validation import validate_branch_memory

        validation_errors = validate_branch_memory(project_path, branch_name, stage=stage)
        if validation_errors:
            raise ValueError("; ".join(validation_errors))
    except Exception as exc:
        projection_status = "stale"
        projection_refresh_required = True
        warnings.append(f"projection refresh failed: {exc}")

    return {
        "generated_views": generated_views,
        "projection_status": projection_status,
        "projection_refresh_required": projection_refresh_required,
        "warnings": warnings,
    }
