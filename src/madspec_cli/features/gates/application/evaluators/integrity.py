from __future__ import annotations

from pathlib import Path
from typing import Any

from madspec_cli.memory.shared.storage import get_memory_paths
from madspec_cli.memory.shared.validation_progress import validate_progress

from .shared import build_gate


def collect_integrity_gates(
    *,
    project_path: Path,
    branch_name: str,
    progress: dict[str, Any],
    stage: str,
    operation: str,
    step_id: str | None,
) -> list[dict[str, Any]]:
    from madspec_cli.memory.shared.validation_runtime import (
        validate_active_session_file,
        validate_progress_runtime,
    )

    paths = get_memory_paths(project_path, branch_name)
    errors = validate_progress_runtime(
        progress,
        project_path=project_path,
        branch_name=branch_name,
        validate_progress=validate_progress,
    )
    errors.extend(validate_active_session_file(paths.active_session, branch_name=branch_name))
    results: list[dict[str, Any]] = []
    for message in errors:
        results.append(
            build_gate(
                family="runtime_validity",
                scope="branch",
                subject_id=step_id or stage or branch_name,
                blocking=True,
                waivable=False,
                status="failed",
                message=message,
                source_ids=["memory.progress", "memory.active_session"],
                stage=stage,
                operation=operation,
            )
        )
    return results
