from __future__ import annotations

from dataclasses import dataclass

from ..stages.architecture.state import ARCHITECTURE_STAGE
from ..stages.concept.state import CONCEPT_STAGE
from ..stages.deploy.state import DEPLOY_STAGE
from ..stages.design.state import DESIGN_STAGE
from ..stages.feature_init.state import FEATURE_INIT_STAGE
from ..stages.feature_plan.state import FEATURE_PLAN_STAGE
from ..stages.plan.state import PLAN_STAGE
from ..stages.tech.state import TECH_STAGE
from .capture_models import CaptureInputs, ParsedStageBundle


@dataclass(frozen=True)
class CaptureScopeUsage:
    concept: bool
    design: bool
    tech: bool
    architecture: bool
    plan: bool
    deploy: bool
    project_type: bool
    feature_init: bool
    next_actions: bool


def validate_capture_scope(
    *,
    inputs: CaptureInputs,
    parsed: ParsedStageBundle,
) -> list[str]:
    usage = _scope_usage(inputs, parsed)
    validators = {
        CONCEPT_STAGE: _validate_concept_scope,
        DESIGN_STAGE: _validate_design_scope,
        TECH_STAGE: _validate_tech_scope,
        ARCHITECTURE_STAGE: _validate_architecture_scope,
        PLAN_STAGE: _validate_plan_scope,
        FEATURE_PLAN_STAGE: _validate_feature_plan_scope,
        DEPLOY_STAGE: _validate_deploy_scope,
        FEATURE_INIT_STAGE: _validate_feature_init_scope,
    }
    validator = validators.get(inputs.stage, _validate_generic_scope)
    return validator(usage)


def _validate_concept_scope(usage: CaptureScopeUsage) -> list[str]:
    return _common_scope_errors(
        usage,
        allow_concept=True,
        allow_next_actions=True,
    )


def _validate_design_scope(usage: CaptureScopeUsage) -> list[str]:
    return _common_scope_errors(
        usage,
        allow_design=True,
        allow_next_actions=True,
    )


def _validate_tech_scope(usage: CaptureScopeUsage) -> list[str]:
    return _common_scope_errors(
        usage,
        allow_tech=True,
        allow_project_type=True,
        allow_next_actions=True,
    )


def _validate_architecture_scope(usage: CaptureScopeUsage) -> list[str]:
    return _common_scope_errors(
        usage,
        allow_architecture=True,
        allow_next_actions=True,
    )


def _validate_plan_scope(usage: CaptureScopeUsage) -> list[str]:
    return _common_scope_errors(
        usage,
        allow_plan=True,
        allow_next_actions=True,
    )


def _validate_feature_plan_scope(usage: CaptureScopeUsage) -> list[str]:
    return _common_scope_errors(
        usage,
        allow_plan=True,
        allow_next_actions=True,
    )


def _validate_deploy_scope(usage: CaptureScopeUsage) -> list[str]:
    return _common_scope_errors(
        usage,
        allow_deploy=True,
        allow_next_actions=True,
    )


def _validate_feature_init_scope(usage: CaptureScopeUsage) -> list[str]:
    return _common_scope_errors(
        usage,
        allow_feature_init=True,
        allow_project_type=True,
        allow_next_actions=True,
    )


def _validate_generic_scope(usage: CaptureScopeUsage) -> list[str]:
    return _common_scope_errors(usage)


def _common_scope_errors(
    usage: CaptureScopeUsage,
    *,
    allow_concept: bool = False,
    allow_design: bool = False,
    allow_tech: bool = False,
    allow_architecture: bool = False,
    allow_plan: bool = False,
    allow_deploy: bool = False,
    allow_project_type: bool = False,
    allow_feature_init: bool = False,
    allow_next_actions: bool = False,
) -> list[str]:
    if usage.concept and not allow_concept:
        return ["concept-specific capture options are only supported for stage mvp.concept"]
    if usage.design and not allow_design:
        return ["design-specific capture options are only supported for stage mvp.design"]
    if usage.tech and not allow_tech:
        return ["tech-specific capture options are only supported for stage mvp.tech"]
    if usage.project_type and not allow_project_type:
        return ["--project-type is only supported for stages mvp.tech and feature.init"]
    if usage.architecture and not allow_architecture:
        return ["architecture-specific capture options are only supported for stage mvp.architecture"]
    if usage.feature_init and not allow_feature_init:
        return ["feature-init-specific capture options are only supported for stage feature.init"]
    if usage.plan and not allow_plan:
        return ["plan-specific capture options are only supported for stages mvp.plan and feature.plan"]
    if usage.deploy and not allow_deploy:
        return ["deploy-specific capture options are only supported for stage deploy"]
    if usage.next_actions and not allow_next_actions:
        return [
            "--next-action is only supported for stages mvp.concept, mvp.design, mvp.tech, deploy, mvp.architecture, mvp.plan, feature.init, and feature.plan"
        ]
    return []


def _scope_usage(inputs: CaptureInputs, parsed: ParsedStageBundle) -> CaptureScopeUsage:
    return CaptureScopeUsage(
        concept=any(
            [
                inputs.project_name,
                inputs.system_overview,
                inputs.audiences,
                inputs.scenarios,
                inputs.pain_points,
                parsed.concept_feature_updates["p1"],
                parsed.concept_feature_updates["p2"],
                parsed.concept_feature_updates["p3"],
                inputs.constraints,
                inputs.assumptions,
            ]
        ),
        design=any(
            [
                inputs.design_overview,
                inputs.platforms,
                parsed.design_zone_updates,
                parsed.design_screen_updates,
                parsed.design_screen_feature_links,
                parsed.design_flow_updates,
                parsed.design_flow_step_updates,
                parsed.design_flow_alternative_updates,
                parsed.design_navigation_updates,
                inputs.platform_constraints,
                parsed.design_screen_data_updates,
            ]
        ),
        tech=any(
            [
                inputs.stack_overview,
                inputs.requirements,
                inputs.preferences,
                inputs.tech_constraints,
                parsed.tech_component_updates,
                parsed.tech_library_updates,
                parsed.tech_code_organization,
                parsed.tech_alternative_updates,
            ]
        ),
        architecture=any(
            [
                inputs.architecture_overview,
                parsed.architecture_project_structure,
                parsed.architecture_directory_updates,
                parsed.architecture_entity_updates,
                parsed.architecture_entity_field_updates,
                parsed.architecture_entity_relationship_updates,
                parsed.architecture_entity_state_updates,
                parsed.architecture_endpoint_updates,
                parsed.architecture_endpoint_screen_updates,
                parsed.architecture_endpoint_field_updates,
                parsed.architecture_endpoint_error_updates,
                parsed.architecture_integration_updates,
                inputs.code_principles,
                parsed.architecture_pattern_updates,
                inputs.security_notes,
                inputs.performance_notes,
            ]
        ),
        plan=any([inputs.plan_overview, inputs.planning_principles]),
        deploy=any(
            [
                inputs.deploy_overview,
                inputs.deploy_goals,
                parsed.deploy_environment_updates,
                parsed.deploy_unit_updates,
                inputs.config_notes,
                inputs.secret_notes,
                inputs.cicd_triggers,
                inputs.cicd_steps,
                inputs.release_artifacts,
                inputs.migration_notes,
                inputs.backup_notes,
                inputs.recovery_checks,
                inputs.observability_notes,
                inputs.security_controls,
                inputs.release_strategy,
                inputs.rollback_strategy,
            ]
        ),
        project_type=bool(inputs.project_type),
        feature_init=any(
            [
                inputs.feature_goal,
                inputs.problem,
                inputs.expected_outcome,
                inputs.framework,
                inputs.structure_notes,
                inputs.interface_contracts,
                inputs.risks,
                inputs.recommendations,
                inputs.tech_notes,
                inputs.architecture_notes,
                parsed.feature_existing_modules,
                parsed.feature_modified_files,
                parsed.feature_new_files,
                parsed.feature_dependencies,
            ]
        ),
        next_actions=bool(inputs.next_actions),
    )


__all__ = ["validate_capture_scope"]
