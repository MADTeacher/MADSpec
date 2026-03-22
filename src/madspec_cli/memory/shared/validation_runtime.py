from __future__ import annotations

from pathlib import Path
from typing import Any

from .progress_utils import _compute_progress_metrics, extract_function_catalog
from .storage import read_json


def validate_progress_runtime(
    progress: dict[str, Any],
    *,
    project_path: Path,
    branch_name: str,
    validate_progress: callable,
) -> list[str]:
    errors = list(validate_progress(progress))
    catalog: dict[str, list[str]] = {}
    for stage_name in ("mvp.plan", "feature.plan"):
        stage_catalog = extract_function_catalog(project_path, branch_name, stage_name)
        if any(stage_catalog.values()):
            catalog = stage_catalog
            break
    if not catalog:
        return errors

    known_functions = {item for values in catalog.values() for item in values}
    for step_id, coverage in progress.get("coversFunctions", {}).items():
        if not isinstance(coverage, dict):
            continue
        for priority, values in coverage.items():
            if not isinstance(values, list):
                continue
            for value in values:
                if value not in known_functions:
                    errors.append(
                        f"coversFunctions['{step_id}']['{priority}'] references unknown function '{value}'"
                    )
    expected_metrics = _compute_progress_metrics(catalog, progress.get("coversFunctions", {}))
    current_metrics = progress.get("planningMetadata", {}).get("progressMetrics", {})
    if current_metrics != expected_metrics:
        errors.append("planningMetadata.progressMetrics is out of sync with coversFunctions")
    return errors


def validate_active_session_file(path: Path, *, branch_name: str) -> list[str]:
    active_session = read_json(path, None)
    if not isinstance(active_session, dict):
        return ["active-session.json must contain a JSON object"]

    errors: list[str] = []
    for key in (
        "branch",
        "active_goal",
        "stage",
        "current_step",
        "pending_actions",
        "open_questions",
        "current_hypotheses",
        "last_checkpoint_at",
        "updated_at",
    ):
        if key not in active_session:
            errors.append(f"active-session.json missing '{key}'")
    if active_session.get("branch") != branch_name:
        errors.append("active-session.json branch does not match target branch")
    for key in ("pending_actions", "open_questions", "current_hypotheses"):
        if key in active_session and not isinstance(active_session[key], list):
            errors.append(f"active-session.json field '{key}' must be a list")
    return errors
