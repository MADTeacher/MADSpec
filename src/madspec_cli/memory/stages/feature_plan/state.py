from __future__ import annotations

from pathlib import Path
from typing import Any

from ..plan.state import (
    default_plan_state,
    is_empty_plan_state,
    load_plan_state as load_shared_plan_state,
    normalize_plan_state,
    plan_completeness_errors,
    plan_schema_errors,
    save_plan_state as save_shared_plan_state,
    update_plan_state,
)
from ...shared.storage import PRIORITIES

FEATURE_PLAN_STAGE = "feature.plan"


def load_feature_plan_state(path: Path) -> dict[str, Any]:
    return load_shared_plan_state(path)


def save_feature_plan_state(path: Path, state: dict[str, Any]) -> None:
    save_shared_plan_state(path, state)


def feature_plan_schema_errors(state: Any) -> list[str]:
    return [item.replace("plan step", "feature plan step") for item in plan_schema_errors(state)]


def feature_plan_completeness_errors(state: dict[str, Any]) -> list[str]:
    return [
        item.replace("plan state", "feature plan state")
        for item in plan_completeness_errors(state)
    ]


def feature_plan_reference_errors(
    state: dict[str, Any],
    *,
    project_path: Path,
    branch_name: str,
    progress: dict[str, Any],
) -> list[str]:
    normalized, _ = normalize_plan_state(state)
    errors: list[str] = []
    step_catalog = {item["stepId"]: item for item in normalized["stepCatalog"]}
    planned_steps = progress.get("plannedSteps", [])
    step_metadata = progress.get("stepMetadata", {})
    step_dependencies = progress.get("planningMetadata", {}).get("stepDependencies", {})
    covers_functions = progress.get("coversFunctions", {})
    branch_dir = project_path / ".madspec" / branch_name

    for step_id in planned_steps:
        if step_id not in step_catalog:
            errors.append(f"feature.plan.json is missing planned step '{step_id}' from progress.json")

    for step_id, item in step_catalog.items():
        step_dir = branch_dir / "steps" / step_id
        if not step_dir.exists():
            errors.append(f"feature plan step '{step_id}' is missing steps/{step_id}/ directory")
            continue
        for file_name in ("description.md", "tasks.md", "tests.md", "validation.md"):
            if not (step_dir / file_name).exists():
                errors.append(f"feature plan step '{step_id}' is missing steps/{step_id}/{file_name}")

        progress_metadata = step_metadata.get(step_id, {})
        if progress_metadata:
            if item["stepKind"] != progress_metadata.get("kind"):
                errors.append(f"feature plan step '{step_id}' stepKind is out of sync with progress.json")
            if item["tddPolicy"] != progress_metadata.get("tddPolicy"):
                errors.append(f"feature plan step '{step_id}' tddPolicy is out of sync with progress.json")
            if item["waiverReason"] != progress_metadata.get("waiverReason"):
                errors.append(f"feature plan step '{step_id}' waiverReason is out of sync with progress.json")

        if item["dependsOn"] != step_dependencies.get(step_id, []):
            errors.append(f"feature plan step '{step_id}' dependsOn is out of sync with progress.json")
        if item["covers"] != covers_functions.get(step_id, {priority: [] for priority in PRIORITIES}):
            errors.append(f"feature plan step '{step_id}' covers is out of sync with progress.json")
    return errors


def render_feature_implementation_plan_markdown(
    state: dict[str, Any],
    *,
    branch_name: str,
    progress: dict[str, Any],
    feature_goal: str,
) -> str:
    normalized, _ = normalize_plan_state(state)
    title = feature_goal or "Feature"
    from ..plan.state import render_implementation_plan_markdown

    text = render_implementation_plan_markdown(
        normalized,
        branch_name=branch_name,
        progress=progress,
        project_name=title,
    )
    return text.replace("memory/stages/mvp.plan.json", "memory/stages/feature.plan.json", 1)


from madspec_cli.memory.shared.stage_registry import register_stage_default, register_stage_loader, register_stage_validators, register_stage_renderers

register_stage_default("feature.plan", default_plan_state)
register_stage_loader("feature.plan", load_feature_plan_state)
register_stage_validators("feature.plan", reference_errors=feature_plan_reference_errors)
register_stage_renderers("feature.plan", implementation_plan=render_feature_implementation_plan_markdown)
