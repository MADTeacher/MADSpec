from __future__ import annotations

from typing import Any

from ..stages.deploy.state import DEPLOY_STAGE
from ..stages.feature_init.state import FEATURE_INIT_STAGE
from .capture_models import CaptureInputs, ParsedStageBundle, PreparedCapture
from .capture_scope import validate_capture_scope
from .shared import append_unique
from .updates import build_stage_summary_bundles, has_capture_payload


def prepare_capture(
    *,
    branch_name: str,
    inputs: CaptureInputs,
    parsed: ParsedStageBundle,
) -> PreparedCapture | dict[str, Any]:
    _enrich_feature_init(inputs, parsed)
    _enrich_deploy(inputs, parsed)

    scope_errors = validate_capture_scope(inputs=inputs, parsed=parsed)
    if scope_errors:
        return _error_payload(branch_name, inputs.stage, scope_errors)

    for errors in (
        parsed.concept_errors,
        parsed.feature_init_errors,
        parsed.design_errors,
        parsed.tech_errors,
        parsed.deploy_errors,
        parsed.architecture_errors,
    ):
        if errors:
            return _error_payload(branch_name, inputs.stage, errors)

    inputs.pending_actions = append_unique(inputs.pending_actions, inputs.next_actions)
    bundles = build_stage_summary_bundles(
        normalized_project_name=inputs.project_name,
        normalized_system_overview=inputs.system_overview,
        normalized_audiences=inputs.audiences,
        normalized_scenarios=inputs.scenarios,
        normalized_pain_points=inputs.pain_points,
        normalized_assumptions=inputs.assumptions,
        concept_feature_updates=parsed.concept_feature_updates,
        normalized_constraints=inputs.constraints,
        normalized_design_overview=inputs.design_overview,
        normalized_platforms=inputs.platforms,
        design_zone_updates=parsed.design_zone_updates,
        design_screen_updates=parsed.design_screen_updates,
        design_flow_updates=parsed.design_flow_updates,
        design_flow_step_updates=parsed.design_flow_step_updates,
        design_screen_data_updates=parsed.design_screen_data_updates,
        design_screen_feature_links=parsed.design_screen_feature_links,
        design_navigation_updates=parsed.design_navigation_updates,
        design_flow_alternative_updates=parsed.design_flow_alternative_updates,
        normalized_platform_constraints=inputs.platform_constraints,
        normalized_project_type=inputs.project_type,
        normalized_stack_overview=inputs.stack_overview,
        normalized_requirements=inputs.requirements,
        normalized_preferences=inputs.preferences,
        tech_component_updates=parsed.tech_component_updates,
        tech_library_updates=parsed.tech_library_updates,
        tech_code_organization=parsed.tech_code_organization,
        tech_alternative_updates=parsed.tech_alternative_updates,
        normalized_tech_constraints=inputs.tech_constraints,
        normalized_architecture_overview=inputs.architecture_overview,
        architecture_project_structure=parsed.architecture_project_structure,
        architecture_directory_updates=parsed.architecture_directory_updates,
        architecture_entity_updates=parsed.architecture_entity_updates,
        architecture_entity_field_updates=parsed.architecture_entity_field_updates,
        architecture_integration_updates=parsed.architecture_integration_updates,
        normalized_code_principles=inputs.code_principles,
        normalized_security_notes=inputs.security_notes,
        normalized_performance_notes=inputs.performance_notes,
        normalized_plan_overview=inputs.plan_overview,
        normalized_planning_principles=inputs.planning_principles,
        architecture_entity_relationship_updates=parsed.architecture_entity_relationship_updates,
        architecture_entity_state_updates=parsed.architecture_entity_state_updates,
        architecture_endpoint_updates=parsed.architecture_endpoint_updates,
        architecture_endpoint_screen_updates=parsed.architecture_endpoint_screen_updates,
        architecture_endpoint_field_updates=parsed.architecture_endpoint_field_updates,
        architecture_pattern_updates=parsed.architecture_pattern_updates,
        architecture_endpoint_error_updates=parsed.architecture_endpoint_error_updates,
    )
    if not has_capture_payload(
        normalized_summary=inputs.summary,
        normalized_facts=inputs.facts,
        normalized_decisions=inputs.decisions,
        normalized_contracts=inputs.contracts,
        normalized_questions=inputs.questions,
        normalized_pending_actions=inputs.pending_actions,
        bundles=bundles,
    ):
        return _error_payload(
            branch_name,
            inputs.stage,
            ["capture payload must include summary, fact, decision, contract, question, or pending action"],
        )

    return PreparedCapture(inputs=inputs, parsed=parsed, bundles=bundles)


def _enrich_feature_init(inputs: CaptureInputs, parsed: ParsedStageBundle) -> None:
    if inputs.stage != FEATURE_INIT_STAGE:
        return
    inputs.facts = append_unique(
        inputs.facts,
        [item for item in [inputs.feature_goal, inputs.problem, inputs.expected_outcome] if item]
        + [f"Existing module: {item['name']} ({item['path']})" for item in parsed.feature_existing_modules]
        + [f"Risk: {item}" for item in inputs.risks]
        + [f"Tech note: {item}" for item in inputs.tech_notes]
        + [f"Architecture note: {item}" for item in inputs.architecture_notes],
    )
    inputs.decisions = append_unique(
        inputs.decisions,
        [
            f"{priority.upper()} feature {item['id']}: {item['title']} - {item['description']}"
            for priority in ("p1", "p2", "p3")
            for item in parsed.feature_init_feature_updates[priority]
        ]
        + [f"Modify file {item['path']}: {item['reason']}" for item in parsed.feature_modified_files]
        + [f"Create file {item['path']}: {item['reason']}" for item in parsed.feature_new_files]
        + [f"Recommendation: {item}" for item in inputs.recommendations],
    )
    inputs.contracts = append_unique(
        inputs.contracts,
        inputs.interface_contracts
        + [f"{item['scope']} {item['name']}: {item['description']}" for item in parsed.feature_dependencies],
    )


def _enrich_deploy(inputs: CaptureInputs, parsed: ParsedStageBundle) -> None:
    if inputs.stage != DEPLOY_STAGE:
        return
    inputs.facts = append_unique(
        inputs.facts,
        ([f"Обзор развертывания: {inputs.deploy_overview}"] if inputs.deploy_overview else [])
        + [f"Цель развертывания: {item}" for item in inputs.deploy_goals]
        + [
            f"Окружение {item['name']}: {item['purpose']} — {item['notes']}"
            for item in parsed.deploy_environment_updates
        ]
        + [f"Конфигурация: {item}" for item in inputs.config_notes]
        + [f"Секреты: {item}" for item in inputs.secret_notes]
        + [f"Миграции: {item}" for item in inputs.migration_notes]
        + [f"Резервное копирование: {item}" for item in inputs.backup_notes]
        + [f"Проверка восстановления: {item}" for item in inputs.recovery_checks]
        + [f"Наблюдаемость: {item}" for item in inputs.observability_notes]
        + [f"Контроль безопасности: {item}" for item in inputs.security_controls],
    )
    inputs.decisions = append_unique(
        inputs.decisions,
        [
            f"Единица развертывания {item['name']}: {item['kind']} / {item['runtime']} — {item['notes']}"
            for item in parsed.deploy_unit_updates
        ]
        + [f"Триггер CI/CD: {item}" for item in inputs.cicd_triggers]
        + [f"Шаг CI/CD: {item}" for item in inputs.cicd_steps]
        + [f"Артефакт релиза: {item}" for item in inputs.release_artifacts]
        + ([f"Стратегия релиза: {inputs.release_strategy}"] if inputs.release_strategy else [])
        + ([f"Стратегия отката: {inputs.rollback_strategy}"] if inputs.rollback_strategy else []),
    )


def _error_payload(branch_name: str, stage: str, errors: list[str]) -> dict[str, Any]:
    return {
        "accepted": False,
        "branch": branch_name,
        "stage": stage,
        "errors": errors,
    }
