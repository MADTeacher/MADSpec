from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .storage import get_memory_paths, read_json, read_jsonl
from .validation_progress import validate_progress as _validate_progress
from .validation_records import validate_record as _validate_record
from .validation_runtime import validate_active_session_file, validate_progress_runtime
from .validation_views import validate_generated_stage_views


def validate_branch_memory(
    project_path: Path,
    branch_name: str,
    *,
    stage: str | None = None,
    full: bool = False,
    policy_violations: list[dict[str, Any]] | None = None,
) -> list[str]:
    paths = get_memory_paths(project_path, branch_name)
    errors: list[str] = []
    active_session = read_json(paths.active_session, {})
    inferred_stage = stage
    if not full and inferred_stage is None and isinstance(active_session, dict):
        candidate = str(active_session.get("stage", "")).strip().lower()
        if candidate and candidate != "idle":
            inferred_stage = candidate

    progress = read_json(paths.progress, None)
    if not isinstance(progress, dict):
        errors.append("progress.json must contain a JSON object")
    else:
        errors.extend(
            validate_progress_runtime(
                progress,
                project_path=project_path,
                branch_name=branch_name,
                validate_progress=_validate_progress,
            )
        )

    errors.extend(validate_active_session_file(paths.active_session, branch_name=branch_name))
    errors.extend(
        validate_generated_stage_views(
            paths,
            project_path=project_path,
            branch_name=branch_name,
            stage=inferred_stage,
            full=full or inferred_stage is None,
        )
    )

    for path in (
        paths.decision_log,
        paths.events,
        paths.facts,
        paths.decisions,
        paths.contracts,
    ):
        try:
            records = read_jsonl(path)
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name} contains invalid JSONL: {exc}")
            continue
        for index, record in enumerate(records, start=1):
            record_errors = _validate_record(record)
            errors.extend(f"{path.name}:{index}: {item}" for item in record_errors)

    if policy_violations is not None:
        errors.extend(item["message"] for item in policy_violations)

    return errors
