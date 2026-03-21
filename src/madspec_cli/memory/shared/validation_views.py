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
from ..stages.deploy.state import (
    deploy_schema_errors,
    load_deploy_state,
    render_deployment_markdown,
)
from ..stages.feature_init.state import (
    load_feature_init_state,
    render_feature_architecture_markdown,
    render_feature_context_markdown,
    render_feature_tech_stack_markdown,
    render_project_analysis_markdown,
)
from ..stages.feature_plan.state import (
    feature_plan_reference_errors,
    is_empty_plan_state as is_empty_feature_plan_state,
    load_feature_plan_state,
    render_feature_implementation_plan_markdown,
)
from ..stages.tech.state import load_tech_state, render_tech_stack_markdown, tech_schema_errors
from ..stages.plan.state import (
    is_empty_plan_state,
    load_plan_state,
    plan_reference_errors,
    plan_schema_errors,
    render_implementation_plan_markdown,
)
from .stage_scope import resolve_stage_scope
from .storage import read_json


def validate_generated_stage_views(
    paths,
    *,
    project_path: Path,
    branch_name: str,
    stage: str | None = None,
    full: bool = False,
) -> list[str]:
    scope = resolve_stage_scope(stage, full=full)
    errors: list[str] = []

    concept_state = load_concept_state(paths.concept_state)
    feature_init_state = load_feature_init_state(paths.feature_init_state)
    feature_mode = not (
        not feature_init_state.get("featureGoal")
        and not any(feature_init_state.get("features", {}).get(priority, []) for priority in ("p1", "p2", "p3"))
    )
    design_state = load_design_state(paths.design_state)
    tech_state = load_tech_state(paths.tech_state)
    deploy_state = load_deploy_state(paths.deploy_state)
    architecture_state = load_architecture_state(paths.architecture_state)
    plan_state = load_plan_state(paths.plan_state)
    feature_plan_state = load_feature_plan_state(paths.feature_plan_state)

    if "mvp.concept" in scope.stage_snapshot_keys:
        concept_state_raw = read_json(paths.concept_state, None)
        errors.extend(f"{paths.concept_state.name}: {item}" for item in concept_schema_errors(concept_state_raw))
    if "concept" in scope.view_keys:
        concept_text = render_concept_markdown(concept_state)
        concept_path = paths.branch_dir / "concept.md"
        if not concept_path.exists():
            errors.append("concept.md is missing; rebuild generated views with `madspec memory consolidate`")
        elif concept_path.read_text(encoding="utf-8") != concept_text:
            errors.append("concept.md is out of sync with memory/stages/mvp.concept.json")

    if "mvp.design" in scope.stage_snapshot_keys:
        design_state_raw = read_json(paths.design_state, None)
        errors.extend(f"{paths.design_state.name}: {item}" for item in design_schema_errors(design_state_raw))
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
    if "ui-design" in scope.view_keys:
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

    if "mvp.tech" in scope.stage_snapshot_keys:
        tech_state_raw = read_json(paths.tech_state, None)
        errors.extend(f"{paths.tech_state.name}: {item}" for item in tech_schema_errors(tech_state_raw))
    if "tech-stack" in scope.view_keys:
        tech_text = (
            render_feature_tech_stack_markdown(feature_init_state, branch_name=branch_name)
            if feature_mode
            else render_tech_stack_markdown(
                tech_state,
                branch_name=branch_name,
                project_name=concept_state.get("projectName", ""),
            )
        )
        tech_path = paths.branch_dir / "tech-stack.md"
        if not tech_path.exists():
            errors.append("tech-stack.md is missing; rebuild generated views with `madspec memory consolidate`")
        elif tech_path.read_text(encoding="utf-8") != tech_text:
            errors.append("tech-stack.md is out of sync with memory/stages/mvp.tech.json")

    if "deploy" in scope.stage_snapshot_keys:
        deploy_state_raw = read_json(paths.deploy_state, None)
        errors.extend(f"{paths.deploy_state.name}: {item}" for item in deploy_schema_errors(deploy_state_raw))
    if "deployment" in scope.view_keys:
        deployment_text = render_deployment_markdown(
            deploy_state,
            branch_name=branch_name,
            project_name=concept_state.get("projectName", ""),
        )
        deployment_path = paths.branch_dir / "deployment.md"
        if not deployment_path.exists():
            errors.append("deployment.md is missing; rebuild generated views with `madspec memory consolidate`")
        elif deployment_path.read_text(encoding="utf-8") != deployment_text:
            errors.append("deployment.md is out of sync with memory/stages/deploy.json")

    if "mvp.architecture" in scope.stage_snapshot_keys:
        architecture_state_raw = read_json(paths.architecture_state, None)
        errors.extend(
            f"{paths.architecture_state.name}: {item}"
            for item in architecture_schema_errors(architecture_state_raw)
        )
        if not is_empty_architecture_state(architecture_state):
            errors.extend(architecture_reference_errors(architecture_state, design_state=design_state))
    if "architecture" in scope.view_keys:
        architecture_text = (
            render_feature_architecture_markdown(feature_init_state, branch_name=branch_name)
            if feature_mode
            else render_architecture_markdown(
                architecture_state,
                branch_name=branch_name,
                project_name=concept_state.get("projectName", ""),
            )
        )
        architecture_path = paths.branch_dir / "architecture.md"
        if not architecture_path.exists():
            errors.append("architecture.md is missing; rebuild generated views with `madspec memory consolidate`")
        elif architecture_path.read_text(encoding="utf-8") != architecture_text:
            errors.append("architecture.md is out of sync with memory/stages/mvp.architecture.json")
    if "data-model" in scope.view_keys:
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
    if "openapi" in scope.view_keys:
        openapi_text = render_openapi_yaml(architecture_state, branch_name=branch_name)
        openapi_path = paths.branch_dir / "contracts" / "openapi.yaml"
        if not openapi_path.exists():
            errors.append("contracts/openapi.yaml is missing; rebuild generated views with `madspec memory consolidate`")
        elif openapi_path.read_text(encoding="utf-8") != openapi_text:
            errors.append("contracts/openapi.yaml is out of sync with memory/stages/mvp.architecture.json")

    if "feature.init" in scope.stage_snapshot_keys:
        feature_analysis_path = paths.branch_dir / "project-analysis.md"
        feature_analysis_text = render_project_analysis_markdown(feature_init_state)
        if "project-analysis" in scope.view_keys:
            if not feature_analysis_path.exists():
                errors.append("project-analysis.md is missing; rebuild generated views with `madspec memory consolidate`")
            elif feature_analysis_path.read_text(encoding="utf-8") != feature_analysis_text:
                errors.append("project-analysis.md is out of sync with memory/stages/feature.init.json")
        feature_context_path = paths.branch_dir / "feature-context.md"
        feature_context_text = render_feature_context_markdown(feature_init_state)
        if "feature-context" in scope.view_keys:
            if not feature_context_path.exists():
                errors.append("feature-context.md is missing; rebuild generated views with `madspec memory consolidate`")
            elif feature_context_path.read_text(encoding="utf-8") != feature_context_text:
                errors.append("feature-context.md is out of sync with memory/stages/feature.init.json")

    if "mvp.plan" in scope.stage_snapshot_keys:
        plan_state_raw = read_json(paths.plan_state, None)
        errors.extend(f"{paths.plan_state.name}: {item}" for item in plan_schema_errors(plan_state_raw))
        if not is_empty_plan_state(plan_state):
            errors.extend(
                plan_reference_errors(
                    plan_state,
                    project_path=project_path,
                    branch_name=branch_name,
                    progress=read_json(paths.progress, {}),
                )
            )
    if "feature.plan" in scope.stage_snapshot_keys:
        if feature_mode or not is_empty_feature_plan_state(feature_plan_state):
            errors.extend(
                feature_plan_reference_errors(
                    feature_plan_state,
                    project_path=project_path,
                    branch_name=branch_name,
                    progress=read_json(paths.progress, {}),
                )
            )
    if "implementation-plan" in scope.view_keys:
        implementation_plan_text = render_implementation_plan_markdown(
            plan_state,
            branch_name=branch_name,
            progress=read_json(paths.progress, {}),
            project_name=concept_state.get("projectName", ""),
        )
        if feature_mode:
            implementation_plan_text = render_feature_implementation_plan_markdown(
                feature_plan_state,
                branch_name=branch_name,
                progress=read_json(paths.progress, {}),
                feature_goal=feature_init_state.get("featureGoal", ""),
            )
        implementation_plan_path = paths.branch_dir / "implementation-plan.md"
        if not implementation_plan_path.exists():
            errors.append("implementation-plan.md is missing; rebuild generated views with `madspec memory consolidate`")
        elif (
            (feature_mode and not is_empty_feature_plan_state(feature_plan_state))
            or (not feature_mode and not is_empty_plan_state(plan_state))
        ) and implementation_plan_path.read_text(encoding="utf-8") != implementation_plan_text:
            errors.append(
                "implementation-plan.md is out of sync with memory/stages/feature.plan.json"
                if feature_mode
                else "implementation-plan.md is out of sync with memory/stages/mvp.plan.json"
            )

    return errors
