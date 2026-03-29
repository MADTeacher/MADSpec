from __future__ import annotations

from dataclasses import fields
from typing import Any

from ..shared.text_lists import normalize_plain_text_list_with_repairs
from .capture_models import CaptureInputs
from .capture_payloads import CapturePayload, build_legacy_capture_payload
from .shared import normalize_text_list


def build_capture_inputs(
    *,
    stage: str,
    status: str,
    payload: CapturePayload | None = None,
    **legacy_kwargs: Any,
) -> CaptureInputs:
    warnings: list[dict[str, str]] = []
    resolved_payload = payload or build_legacy_capture_payload(**legacy_kwargs)
    payload_fields = {
        field.name: getattr(resolved_payload, field.name, None)
        for field in fields(CaptureInputs)
        if field.name not in {"stage", "status", "warnings"}
    }

    def normalize_plain(field_name: str, values: list[str] | None) -> list[str]:
        normalized, field_warnings = normalize_plain_text_list_with_repairs(values, field_name=field_name)
        warnings.extend(field_warnings)
        return normalized

    def normalize_scalar(value: Any) -> str:
        return value.strip() if isinstance(value, str) else ""

    return CaptureInputs(
        stage=stage,
        status=status,
        summary=normalize_scalar(payload_fields.get("summary")),
        warnings=warnings,
        facts=normalize_plain("facts", payload_fields.get("facts")),
        decisions=normalize_plain("decisions", payload_fields.get("decisions")),
        contracts=normalize_plain("contracts", payload_fields.get("contracts")),
        evidence=normalize_plain("evidence", payload_fields.get("evidence")),
        questions=normalize_plain("questions", payload_fields.get("questions")),
        pending_actions=normalize_plain("pending_actions", payload_fields.get("pending_actions")),
        project_name=normalize_scalar(payload_fields.get("project_name")),
        system_overview=normalize_scalar(payload_fields.get("system_overview")),
        audiences=normalize_plain("audiences", payload_fields.get("audiences")),
        scenarios=normalize_plain("scenarios", payload_fields.get("scenarios")),
        pain_points=normalize_plain("pain_points", payload_fields.get("pain_points")),
        feature_p1=normalize_text_list(payload_fields.get("feature_p1")),
        feature_p2=normalize_text_list(payload_fields.get("feature_p2")),
        feature_p3=normalize_text_list(payload_fields.get("feature_p3")),
        constraints=normalize_plain("constraints", payload_fields.get("constraints")),
        assumptions=normalize_plain("assumptions", payload_fields.get("assumptions")),
        next_actions=normalize_plain("next_actions", payload_fields.get("next_actions")),
        design_overview=normalize_scalar(payload_fields.get("design_overview")),
        platforms=normalize_plain("platforms", payload_fields.get("platforms")),
        zones=normalize_text_list(payload_fields.get("zones")),
        screens=normalize_text_list(payload_fields.get("screens")),
        screen_features=normalize_text_list(payload_fields.get("screen_features")),
        flows=normalize_text_list(payload_fields.get("flows")),
        flow_steps=normalize_text_list(payload_fields.get("flow_steps")),
        flow_alternatives=normalize_text_list(payload_fields.get("flow_alternatives")),
        navigation=normalize_text_list(payload_fields.get("navigation")),
        platform_constraints=normalize_plain(
            "platform_constraints", payload_fields.get("platform_constraints")
        ),
        screen_data=normalize_text_list(payload_fields.get("screen_data")),
        stack_overview=normalize_scalar(payload_fields.get("stack_overview")),
        project_type=normalize_scalar(payload_fields.get("project_type")),
        framework=normalize_scalar(payload_fields.get("framework")),
        requirements=normalize_plain("requirements", payload_fields.get("requirements")),
        structure_notes=normalize_plain("structure_notes", payload_fields.get("structure_notes")),
        preferences=normalize_plain("preferences", payload_fields.get("preferences")),
        tech_constraints=normalize_plain("tech_constraints", payload_fields.get("tech_constraints")),
        stack_components=normalize_text_list(payload_fields.get("stack_components")),
        libraries=normalize_text_list(payload_fields.get("libraries")),
        code_organization=normalize_scalar(payload_fields.get("code_organization")),
        alternatives=normalize_text_list(payload_fields.get("alternatives")),
        architecture_overview=normalize_scalar(payload_fields.get("architecture_overview")),
        project_structure=normalize_scalar(payload_fields.get("project_structure")),
        directories=normalize_text_list(payload_fields.get("directories")),
        entities=normalize_text_list(payload_fields.get("entities")),
        entity_fields=normalize_text_list(payload_fields.get("entity_fields")),
        entity_relationships=normalize_text_list(payload_fields.get("entity_relationships")),
        entity_states=normalize_text_list(payload_fields.get("entity_states")),
        endpoints=normalize_text_list(payload_fields.get("endpoints")),
        endpoint_screens=normalize_text_list(payload_fields.get("endpoint_screens")),
        endpoint_fields=normalize_text_list(payload_fields.get("endpoint_fields")),
        endpoint_errors=normalize_text_list(payload_fields.get("endpoint_errors")),
        integrations=normalize_text_list(payload_fields.get("integrations")),
        code_principles=normalize_plain("code_principles", payload_fields.get("code_principles")),
        architecture_patterns=normalize_text_list(payload_fields.get("architecture_patterns")),
        security_notes=normalize_plain("security_notes", payload_fields.get("security_notes")),
        performance_notes=normalize_plain("performance_notes", payload_fields.get("performance_notes")),
        plan_overview=normalize_scalar(payload_fields.get("plan_overview")),
        planning_principles=normalize_plain(
            "planning_principles", payload_fields.get("planning_principles")
        ),
        deploy_overview=normalize_scalar(payload_fields.get("deploy_overview")),
        deploy_goals=normalize_plain("deploy_goals", payload_fields.get("deploy_goals")),
        environments=normalize_text_list(payload_fields.get("environments")),
        deployment_units=normalize_text_list(payload_fields.get("deployment_units")),
        config_notes=normalize_plain("config_notes", payload_fields.get("config_notes")),
        secret_notes=normalize_plain("secret_notes", payload_fields.get("secret_notes")),
        cicd_triggers=normalize_plain("cicd_triggers", payload_fields.get("cicd_triggers")),
        cicd_steps=normalize_plain("cicd_steps", payload_fields.get("cicd_steps")),
        release_artifacts=normalize_plain(
            "release_artifacts", payload_fields.get("release_artifacts")
        ),
        migration_notes=normalize_plain("migration_notes", payload_fields.get("migration_notes")),
        backup_notes=normalize_plain("backup_notes", payload_fields.get("backup_notes")),
        recovery_checks=normalize_plain("recovery_checks", payload_fields.get("recovery_checks")),
        observability_notes=normalize_plain(
            "observability_notes", payload_fields.get("observability_notes")
        ),
        security_controls=normalize_plain(
            "security_controls", payload_fields.get("security_controls")
        ),
        release_strategy=normalize_scalar(payload_fields.get("release_strategy")),
        rollback_strategy=normalize_scalar(payload_fields.get("rollback_strategy")),
        feature_goal=normalize_scalar(payload_fields.get("feature_goal")),
        problem=normalize_scalar(payload_fields.get("problem")),
        expected_outcome=normalize_scalar(payload_fields.get("expected_outcome")),
        existing_modules=normalize_text_list(payload_fields.get("existing_modules")),
        modified_files=normalize_text_list(payload_fields.get("modified_files")),
        new_files=normalize_text_list(payload_fields.get("new_files")),
        interface_contracts=normalize_plain(
            "interface_contracts", payload_fields.get("interface_contracts")
        ),
        dependencies=normalize_text_list(payload_fields.get("dependencies")),
        risks=normalize_plain("risks", payload_fields.get("risks")),
        recommendations=normalize_plain("recommendations", payload_fields.get("recommendations")),
        tech_notes=normalize_plain("tech_notes", payload_fields.get("tech_notes")),
        architecture_notes=normalize_plain(
            "architecture_notes", payload_fields.get("architecture_notes")
        ),
    )
