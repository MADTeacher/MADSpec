from __future__ import annotations

from pathlib import Path

from ..stages.architecture.state import (
    architecture_reference_errors,
    architecture_schema_errors,
    is_empty_architecture_state,
    load_architecture_state,
    render_architecture_markdown,
    render_data_model_markdown,
    render_openapi_yaml,
)
from ..stages.concept.state import concept_schema_errors, load_concept_state, render_concept_markdown
from ..stages.design.state import (
    design_reference_errors,
    design_schema_errors,
    is_empty_design_state,
    load_design_state,
    render_ui_design_markdown,
    uncovered_design_features,
)
from ..stages.tech.state import load_tech_state, render_tech_stack_markdown, tech_schema_errors
from .storage import read_json


def validate_generated_stage_views(paths, *, project_path: Path, branch_name: str) -> list[str]:
    errors: list[str] = []

    concept_state_raw = read_json(paths.concept_state, None)
    errors.extend(f"{paths.concept_state.name}: {item}" for item in concept_schema_errors(concept_state_raw))
    concept_state = load_concept_state(paths.concept_state)
    concept_text = render_concept_markdown(concept_state)
    concept_path = paths.branch_dir / "concept.md"
    if not concept_path.exists():
        errors.append("concept.md is missing; rebuild generated views with `madspec memory consolidate`")
    elif concept_path.read_text(encoding="utf-8") != concept_text:
        errors.append("concept.md is out of sync with memory/stages/mvp.concept.json")

    design_state_raw = read_json(paths.design_state, None)
    errors.extend(f"{paths.design_state.name}: {item}" for item in design_schema_errors(design_state_raw))
    design_state = load_design_state(paths.design_state)
    design_path = paths.branch_dir / "ui-design.md"
    design_text = render_ui_design_markdown(
        design_state,
        branch_name=branch_name,
        project_name=concept_state.get("projectName", ""),
    )
    if not design_path.exists():
        errors.append("ui-design.md is missing; rebuild generated views with `madspec memory consolidate`")
    elif not is_empty_design_state(design_state) and design_path.read_text(encoding="utf-8") != design_text:
        errors.append("ui-design.md is out of sync with memory/stages/mvp.design.json")

    if not is_empty_design_state(design_state):
        errors.extend(
            design_reference_errors(
                design_state,
                project_path=project_path,
                branch_name=branch_name,
            )
        )
        uncovered_features = uncovered_design_features(design_state, concept_state)
        for priority, values in uncovered_features.items():
            for value in values:
                errors.append(f"design coverage missing {priority.upper()} concept feature '{value}'")

    tech_state_raw = read_json(paths.tech_state, None)
    errors.extend(f"{paths.tech_state.name}: {item}" for item in tech_schema_errors(tech_state_raw))
    tech_state = load_tech_state(paths.tech_state)
    tech_text = render_tech_stack_markdown(
        tech_state,
        branch_name=branch_name,
        project_name=concept_state.get("projectName", ""),
    )
    tech_path = paths.branch_dir / "tech-stack.md"
    if not tech_path.exists():
        errors.append("tech-stack.md is missing; rebuild generated views with `madspec memory consolidate`")
    elif tech_path.read_text(encoding="utf-8") != tech_text:
        errors.append("tech-stack.md is out of sync with memory/stages/mvp.tech.json")

    architecture_state_raw = read_json(paths.architecture_state, None)
    errors.extend(
        f"{paths.architecture_state.name}: {item}"
        for item in architecture_schema_errors(architecture_state_raw)
    )
    architecture_state = load_architecture_state(paths.architecture_state)
    architecture_text = render_architecture_markdown(
        architecture_state,
        branch_name=branch_name,
        project_name=concept_state.get("projectName", ""),
    )
    architecture_path = paths.branch_dir / "architecture.md"
    if not architecture_path.exists():
        errors.append("architecture.md is missing; rebuild generated views with `madspec memory consolidate`")
    elif architecture_path.read_text(encoding="utf-8") != architecture_text:
        errors.append("architecture.md is out of sync with memory/stages/mvp.architecture.json")

    data_model_text = render_data_model_markdown(
        architecture_state,
        branch_name=branch_name,
        project_name=concept_state.get("projectName", ""),
    )
    data_model_path = paths.branch_dir / "data-model.md"
    if not data_model_path.exists():
        errors.append("data-model.md is missing; rebuild generated views with `madspec memory consolidate`")
    elif data_model_path.read_text(encoding="utf-8") != data_model_text:
        errors.append("data-model.md is out of sync with memory/stages/mvp.architecture.json")

    openapi_text = render_openapi_yaml(architecture_state, branch_name=branch_name)
    openapi_path = paths.branch_dir / "contracts" / "openapi.yaml"
    if not openapi_path.exists():
        errors.append("contracts/openapi.yaml is missing; rebuild generated views with `madspec memory consolidate`")
    elif openapi_path.read_text(encoding="utf-8") != openapi_text:
        errors.append("contracts/openapi.yaml is out of sync with memory/stages/mvp.architecture.json")
    if not is_empty_architecture_state(architecture_state):
        errors.extend(architecture_reference_errors(architecture_state, design_state=design_state))

    return errors
