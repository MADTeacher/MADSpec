from __future__ import annotations

from pathlib import Path
from typing import Any

from ...shared.storage import PRIORITIES
from .shared import append_unique_strings


def design_main_prototype_path(branch_name: str) -> Path:
    return Path(".madspec") / branch_name / "ui-prototype" / "index.html"


def extract_design_feature_coverage(state: dict[str, Any]) -> dict[str, list[str]]:
    from .state import normalize_design_state

    normalized, _ = normalize_design_state(state)
    coverage = {priority: [] for priority in PRIORITIES}
    for screen in normalized["screens"]:
        for priority in PRIORITIES:
            coverage[priority] = append_unique_strings(
                coverage[priority],
                screen.get("covers", {}).get(priority, []),
            )
    return coverage


def uncovered_design_features(
    state: dict[str, Any],
    concept_state: dict[str, Any],
) -> dict[str, list[str]]:
    design_coverage = extract_design_feature_coverage(state)
    uncovered: dict[str, list[str]] = {}
    for priority in PRIORITIES:
        concept_features = [
            item.get("name", "").strip()
            for item in concept_state.get("features", {}).get(priority, [])
            if item.get("name", "").strip()
        ]
        uncovered[priority] = [
            feature_name for feature_name in concept_features if feature_name not in design_coverage[priority]
        ]
    return uncovered


def missing_prototype_files(
    state: dict[str, Any],
    project_path: Path,
    branch_name: str,
) -> list[str]:
    from .state import normalize_design_state

    normalized, _ = normalize_design_state(state)
    missing: list[str] = []
    index_path = project_path / design_main_prototype_path(branch_name)
    if not index_path.exists():
        missing.append(design_main_prototype_path(branch_name).as_posix())
    for screen in normalized["screens"]:
        prototype = screen.get("prototype", "")
        if not prototype:
            continue
        if not (project_path / prototype).exists() and prototype not in missing:
            missing.append(prototype)
    return missing


def design_reference_errors(
    state: dict[str, Any],
    *,
    project_path: Path | None = None,
    branch_name: str | None = None,
) -> list[str]:
    from .state import normalize_design_state

    normalized, _ = normalize_design_state(state)
    errors: list[str] = []
    zone_ids = {zone.get("id", "") for zone in normalized["zones"] if zone.get("id", "")}
    screen_ids = {screen.get("id", "") for screen in normalized["screens"] if screen.get("id", "")}

    for screen in normalized["screens"]:
        screen_id = screen.get("id", "")
        if screen.get("zone") and screen["zone"] not in zone_ids:
            errors.append(f"design screen '{screen_id}' references unknown zone '{screen['zone']}'")
        if not screen.get("prototype"):
            errors.append(f"design screen '{screen_id}' must include a prototype path")

    for flow in normalized["flows"]:
        flow_id = flow.get("id", "")
        steps = flow.get("steps", [])
        if not steps:
            errors.append(f"design flow '{flow_id}' must include at least one step")
        for step in steps:
            screen_id = step.get("screenId", "")
            if not screen_id:
                errors.append(f"design flow '{flow_id}' contains a step without screenId")
            elif screen_id not in screen_ids:
                errors.append(f"design flow '{flow_id}' references unknown screen '{screen_id}'")

    for item in normalized["navigation"]:
        if item.get("from") not in screen_ids:
            errors.append(f"design navigation references unknown screen '{item.get('from', '')}'")
        if item.get("to") not in screen_ids:
            errors.append(f"design navigation references unknown screen '{item.get('to', '')}'")

    if project_path is not None and branch_name is not None:
        for missing in missing_prototype_files(normalized, project_path, branch_name):
            errors.append(f"design references missing prototype file '{missing}'")

    return errors


def design_completeness_errors(
    state: dict[str, Any],
    *,
    concept_state: dict[str, Any],
    project_path: Path,
    branch_name: str,
) -> list[str]:
    from .state import normalize_design_state

    normalized, _ = normalize_design_state(state)
    errors: list[str] = []
    if not normalized["designOverview"]:
        errors.append("design state must include a design overview before checkpoint")
    if not normalized["platforms"]:
        errors.append("design state must include at least one platform before checkpoint")
    if not normalized["screens"]:
        errors.append("design state must include at least one screen before checkpoint")
    if not normalized["flows"]:
        errors.append("design state must include at least one user flow before checkpoint")
    if not normalized["navigation"]:
        errors.append("design state must include navigation links before checkpoint")
    uncovered = uncovered_design_features(normalized, concept_state)
    for priority in PRIORITIES:
        if uncovered[priority]:
            errors.append(
                f"design state must cover all {priority.upper()} concept features before checkpoint: "
                + ", ".join(uncovered[priority])
            )
    errors.extend(
        design_reference_errors(
            normalized,
            project_path=project_path,
            branch_name=branch_name,
        )
    )
    return errors


def design_schema_errors(state: Any) -> list[str]:
    from .state import DESIGN_SCHEMA_VERSION, normalize_design_state

    if not isinstance(state, dict):
        return ["design state must be a JSON object"]
    normalized, _ = normalize_design_state(state)
    errors: list[str] = []
    if normalized["schemaVersion"] != DESIGN_SCHEMA_VERSION:
        errors.append(f"design state schemaVersion must equal {DESIGN_SCHEMA_VERSION}")
    for key in ("designOverview", "createdAt", "checkpointSummary"):
        if not isinstance(normalized[key], str):
            errors.append(f"design state field '{key}' must be a string")
    for key in ("ratifiedAt", "updatedAt"):
        value = normalized[key]
        if value is not None and not isinstance(value, str):
            errors.append(f"design state field '{key}' must be a string or null")
    if not isinstance(normalized["revision"], int) or normalized["revision"] < 0:
        errors.append("design state field 'revision' must be a non-negative integer")
    for key in ("platforms", "zones", "screens", "flows", "navigation", "platformConstraints", "nextActions"):
        if not isinstance(normalized[key], list):
            errors.append(f"design state field '{key}' must be a list")
    return errors
