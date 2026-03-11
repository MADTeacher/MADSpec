from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..stages.architecture.state import ARCHITECTURE_STAGE
from ..stages.architecture.parsers import (
    parse_directory_value,
    parse_endpoint_error_value,
    parse_endpoint_field_value,
    parse_endpoint_screen_value,
    parse_endpoint_value,
    parse_entity_field_value,
    parse_entity_relationship_value,
    parse_entity_state_value,
    parse_entity_value,
    parse_integration_value,
    parse_pattern_value,
    parse_project_structure_value,
)
from ..stages.concept.state import CONCEPT_STAGE, parse_feature_value
from ..stages.design.state import (
    DESIGN_STAGE,
    parse_flow_alternative_value,
    parse_flow_step_value,
    parse_flow_value,
    parse_navigation_value,
    parse_screen_data_value,
    parse_screen_feature_value,
    parse_screen_value,
    parse_zone_value,
)
from ..stages.plan.state import PLAN_STAGE
from ..stages.tech.state import (
    TECH_STAGE,
    parse_alternative_value,
    parse_code_organization_value,
    parse_library_value,
    parse_stack_component_value,
)
from .shared import normalize_text_list


@dataclass(frozen=True)
class ConceptCaptureParse:
    feature_updates: dict[str, list[dict[str, str]]]
    errors: list[str]


@dataclass(frozen=True)
class DesignCaptureParse:
    zone_updates: list[dict[str, str]]
    screen_updates: list[dict[str, Any]]
    screen_feature_links: list[dict[str, str]]
    flow_updates: list[dict[str, Any]]
    flow_step_updates: list[dict[str, str]]
    flow_alternative_updates: list[dict[str, str]]
    navigation_updates: list[dict[str, str]]
    screen_data_updates: list[dict[str, str]]
    errors: list[str]


@dataclass(frozen=True)
class TechCaptureParse:
    component_updates: list[dict[str, str]]
    library_updates: list[dict[str, str]]
    alternative_updates: list[dict[str, str]]
    code_organization: dict[str, str] | None
    errors: list[str]


@dataclass(frozen=True)
class ArchitectureCaptureParse:
    project_structure: dict[str, str] | None
    directory_updates: list[dict[str, str]]
    entity_updates: list[dict[str, str]]
    entity_field_updates: list[dict[str, Any]]
    entity_relationship_updates: list[dict[str, Any]]
    entity_state_updates: list[dict[str, Any]]
    endpoint_updates: list[dict[str, Any]]
    endpoint_screen_updates: list[dict[str, str]]
    endpoint_field_updates: list[dict[str, Any]]
    endpoint_error_updates: list[dict[str, Any]]
    integration_updates: list[dict[str, Any]]
    pattern_updates: list[dict[str, str]]
    errors: list[str]


def parse_concept_capture(
    *,
    feature_p1: list[str] | None,
    feature_p2: list[str] | None,
    feature_p3: list[str] | None,
) -> ConceptCaptureParse:
    feature_updates: dict[str, list[dict[str, str]]] = {"p1": [], "p2": [], "p3": []}
    errors: list[str] = []
    for priority, values in {
        "p1": normalize_text_list(feature_p1),
        "p2": normalize_text_list(feature_p2),
        "p3": normalize_text_list(feature_p3),
    }.items():
        for value in values:
            parsed = parse_feature_value(value)
            if parsed is None:
                errors.append(f"{priority} feature must use '<name>::<description>' format: {value}")
                continue
            feature_updates[priority].append(parsed)
    return ConceptCaptureParse(feature_updates=feature_updates, errors=errors)


def parse_design_capture(
    *,
    zones: list[str] | None,
    screens: list[str] | None,
    screen_features: list[str] | None,
    flows: list[str] | None,
    flow_steps: list[str] | None,
    flow_alternatives: list[str] | None,
    navigation: list[str] | None,
    screen_data: list[str] | None,
) -> DesignCaptureParse:
    zone_updates: list[dict[str, str]] = []
    screen_updates: list[dict[str, Any]] = []
    screen_feature_links: list[dict[str, str]] = []
    flow_updates: list[dict[str, Any]] = []
    flow_step_updates: list[dict[str, str]] = []
    flow_alternative_updates: list[dict[str, str]] = []
    navigation_updates: list[dict[str, str]] = []
    screen_data_updates: list[dict[str, str]] = []
    errors: list[str] = []

    for value in normalize_text_list(zones):
        parsed = parse_zone_value(value)
        if parsed is None:
            errors.append(f"zone must use '<id>::<title>::<description>' format: {value}")
            continue
        zone_updates.append(parsed)

    for value in normalize_text_list(screens):
        parsed = parse_screen_value(value)
        if parsed is None:
            errors.append(f"screen must use '<id>::<title>::<zone>::<prototype>::<purpose>' format: {value}")
            continue
        screen_updates.append(parsed)

    for value in normalize_text_list(screen_features):
        parsed = parse_screen_feature_value(value)
        if parsed is None:
            errors.append(f"screen-feature must use '<screen-id>::<priority>::<feature-name>' format: {value}")
            continue
        screen_feature_links.append(parsed)

    for value in normalize_text_list(flows):
        parsed = parse_flow_value(value)
        if parsed is None:
            errors.append(f"flow must use '<id>::<title>::<goal>' format: {value}")
            continue
        flow_updates.append(parsed)

    for value in normalize_text_list(flow_steps):
        parsed = parse_flow_step_value(value)
        if parsed is None:
            errors.append(f"flow-step must use '<flow-id>::<screen-id>::<action>::<result>' format: {value}")
            continue
        flow_step_updates.append(parsed)

    for value in normalize_text_list(flow_alternatives):
        parsed = parse_flow_alternative_value(value)
        if parsed is None:
            errors.append(f"flow-alternative must use '<flow-id>::<description>' format: {value}")
            continue
        flow_alternative_updates.append(parsed)

    for value in normalize_text_list(navigation):
        parsed = parse_navigation_value(value)
        if parsed is None:
            errors.append(f"nav must use '<from-screen>::<to-screen>::<trigger>' format: {value}")
            continue
        navigation_updates.append(parsed)

    for value in normalize_text_list(screen_data):
        parsed = parse_screen_data_value(value)
        if parsed is None:
            errors.append(f"screen-data must use '<screen-id>::<displayed|input>::<name>' format: {value}")
            continue
        screen_data_updates.append(parsed)

    return DesignCaptureParse(
        zone_updates=zone_updates,
        screen_updates=screen_updates,
        screen_feature_links=screen_feature_links,
        flow_updates=flow_updates,
        flow_step_updates=flow_step_updates,
        flow_alternative_updates=flow_alternative_updates,
        navigation_updates=navigation_updates,
        screen_data_updates=screen_data_updates,
        errors=errors,
    )


def parse_tech_capture(
    *,
    stack_components: list[str] | None,
    libraries: list[str] | None,
    alternatives: list[str] | None,
    code_organization: str | None,
) -> TechCaptureParse:
    component_updates: list[dict[str, str]] = []
    library_updates: list[dict[str, str]] = []
    alternative_updates: list[dict[str, str]] = []
    parsed_code_organization: dict[str, str] | None = None
    errors: list[str] = []

    for value in normalize_text_list(stack_components):
        parsed = parse_stack_component_value(value)
        if parsed is None:
            errors.append(f"stack-component must use '<slot>::<name>::<version>::<rationale>' format: {value}")
            continue
        component_updates.append(parsed)

    for value in normalize_text_list(libraries):
        parsed = parse_library_value(value)
        if parsed is None:
            errors.append(f"library must use '<scope>::<name>::<version>::<purpose>' format: {value}")
            continue
        library_updates.append(parsed)

    for value in normalize_text_list(alternatives):
        parsed = parse_alternative_value(value)
        if parsed is None:
            errors.append(f"alternative must use '<slot>::<option>::<reason-rejected>' format: {value}")
            continue
        alternative_updates.append(parsed)

    if code_organization:
        parsed_code_organization = parse_code_organization_value(code_organization)
        if parsed_code_organization is None:
            errors.append(
                "code-organization must use '<repo-strategy>::<source-layout>::<modularity>::<rationale>' format"
            )

    return TechCaptureParse(
        component_updates=component_updates,
        library_updates=library_updates,
        alternative_updates=alternative_updates,
        code_organization=parsed_code_organization,
        errors=errors,
    )


def parse_architecture_capture(
    *,
    project_structure: str | None,
    directories: list[str] | None,
    entities: list[str] | None,
    entity_fields: list[str] | None,
    entity_relationships: list[str] | None,
    entity_states: list[str] | None,
    endpoints: list[str] | None,
    endpoint_screens: list[str] | None,
    endpoint_fields: list[str] | None,
    endpoint_errors: list[str] | None,
    integrations: list[str] | None,
    architecture_patterns: list[str] | None,
) -> ArchitectureCaptureParse:
    parsed_project_structure: dict[str, str] | None = None
    directory_updates: list[dict[str, str]] = []
    entity_updates: list[dict[str, str]] = []
    entity_field_updates: list[dict[str, Any]] = []
    entity_relationship_updates: list[dict[str, Any]] = []
    entity_state_updates: list[dict[str, Any]] = []
    endpoint_updates: list[dict[str, Any]] = []
    endpoint_screen_updates: list[dict[str, str]] = []
    endpoint_field_updates: list[dict[str, Any]] = []
    endpoint_error_updates: list[dict[str, Any]] = []
    integration_updates: list[dict[str, Any]] = []
    pattern_updates: list[dict[str, str]] = []
    errors: list[str] = []

    if project_structure:
        parsed_project_structure = parse_project_structure_value(project_structure)
        if parsed_project_structure is None:
            errors.append("project-structure must use '<strategy>::<rationale>' format")

    for value in normalize_text_list(directories):
        parsed = parse_directory_value(value)
        if parsed is None:
            errors.append(f"directory must use '<path>::<purpose>' format: {value}")
            continue
        directory_updates.append(parsed)

    for value in normalize_text_list(entities):
        parsed = parse_entity_value(value)
        if parsed is None:
            errors.append(f"entity must use '<name>::<description>' format: {value}")
            continue
        entity_updates.append(parsed)

    for value in normalize_text_list(entity_fields):
        parsed = parse_entity_field_value(value)
        if parsed is None:
            errors.append(
                f"entity-field must use '<entity>::<field>::<type>::<required|optional>::<description>' format: {value}"
            )
            continue
        entity_field_updates.append(parsed)

    for value in normalize_text_list(entity_relationships):
        parsed = parse_entity_relationship_value(value)
        if parsed is None:
            errors.append(
                f"entity-relationship must use '<entity>::<target>::<kind>::<description>' format: {value}"
            )
            continue
        entity_relationship_updates.append(parsed)

    for value in normalize_text_list(entity_states):
        parsed = parse_entity_state_value(value)
        if parsed is None:
            errors.append(f"entity-state must use '<entity>::<state>::<description>' format: {value}")
            continue
        entity_state_updates.append(parsed)

    for value in normalize_text_list(endpoints):
        parsed = parse_endpoint_value(value)
        if parsed is None:
            errors.append(f"endpoint must use '<operation-id>::<METHOD>::</path>::<summary>' format: {value}")
            continue
        endpoint_updates.append(parsed)

    for value in normalize_text_list(endpoint_screens):
        parsed = parse_endpoint_screen_value(value)
        if parsed is None:
            errors.append(f"endpoint-screen must use '<operation-id>::<screen-id>' format: {value}")
            continue
        endpoint_screen_updates.append(parsed)

    for value in normalize_text_list(endpoint_fields):
        parsed = parse_endpoint_field_value(value)
        if parsed is None:
            errors.append(
                f"endpoint-field must use '<operation-id>::<section>::<name>::<type>::<required|optional>::<description>' format: {value}"
            )
            continue
        endpoint_field_updates.append(parsed)

    for value in normalize_text_list(endpoint_errors):
        parsed = parse_endpoint_error_value(value)
        if parsed is None:
            errors.append(
                f"endpoint-error must use '<operation-id>::<status>::<code>::<description>' format: {value}"
            )
            continue
        endpoint_error_updates.append(parsed)

    for value in normalize_text_list(integrations):
        parsed = parse_integration_value(value)
        if parsed is None:
            errors.append(f"integration must use '<name>::<kind>::<purpose>::<touchpoints>' format: {value}")
            continue
        integration_updates.append(parsed)

    for value in normalize_text_list(architecture_patterns):
        parsed = parse_pattern_value(value)
        if parsed is None:
            errors.append(f"pattern must use '<name>::<rationale>' format: {value}")
            continue
        pattern_updates.append(parsed)

    return ArchitectureCaptureParse(
        project_structure=parsed_project_structure,
        directory_updates=directory_updates,
        entity_updates=entity_updates,
        entity_field_updates=entity_field_updates,
        entity_relationship_updates=entity_relationship_updates,
        entity_state_updates=entity_state_updates,
        endpoint_updates=endpoint_updates,
        endpoint_screen_updates=endpoint_screen_updates,
        endpoint_field_updates=endpoint_field_updates,
        endpoint_error_updates=endpoint_error_updates,
        integration_updates=integration_updates,
        pattern_updates=pattern_updates,
        errors=errors,
    )


def validate_capture_scope(
    *,
    normalized_stage: str,
    normalized_project_name: str,
    normalized_system_overview: str,
    normalized_audiences: list[str],
    normalized_scenarios: list[str],
    normalized_pain_points: list[str],
    concept_feature_updates: dict[str, list[dict[str, str]]],
    normalized_constraints: list[str],
    normalized_assumptions: list[str],
    normalized_design_overview: str,
    normalized_platforms: list[str],
    design_zone_updates: list[dict[str, str]],
    design_screen_updates: list[dict[str, Any]],
    design_screen_feature_links: list[dict[str, str]],
    design_flow_updates: list[dict[str, Any]],
    design_flow_step_updates: list[dict[str, str]],
    design_flow_alternative_updates: list[dict[str, str]],
    design_navigation_updates: list[dict[str, str]],
    normalized_platform_constraints: list[str],
    design_screen_data_updates: list[dict[str, str]],
    normalized_stack_overview: str,
    normalized_project_type: str,
    normalized_requirements: list[str],
    normalized_preferences: list[str],
    normalized_tech_constraints: list[str],
    tech_component_updates: list[dict[str, str]],
    tech_library_updates: list[dict[str, str]],
    tech_code_organization: dict[str, str] | None,
    tech_alternative_updates: list[dict[str, str]],
    normalized_architecture_overview: str,
    architecture_project_structure: dict[str, str] | None,
    architecture_directory_updates: list[dict[str, str]],
    architecture_entity_updates: list[dict[str, str]],
    architecture_entity_field_updates: list[dict[str, Any]],
    architecture_entity_relationship_updates: list[dict[str, Any]],
    architecture_entity_state_updates: list[dict[str, Any]],
    architecture_endpoint_updates: list[dict[str, Any]],
    architecture_endpoint_screen_updates: list[dict[str, str]],
    architecture_endpoint_field_updates: list[dict[str, Any]],
    architecture_endpoint_error_updates: list[dict[str, Any]],
    architecture_integration_updates: list[dict[str, Any]],
    normalized_code_principles: list[str],
    architecture_pattern_updates: list[dict[str, str]],
    normalized_security_notes: list[str],
    normalized_performance_notes: list[str],
    normalized_plan_overview: str,
    normalized_planning_principles: list[str],
    normalized_next_actions: list[str],
) -> list[str]:
    used_concept_fields = any(
        [
            normalized_project_name,
            normalized_system_overview,
            normalized_audiences,
            normalized_scenarios,
            normalized_pain_points,
            concept_feature_updates["p1"],
            concept_feature_updates["p2"],
            concept_feature_updates["p3"],
            normalized_constraints,
            normalized_assumptions,
        ]
    )
    used_design_fields = any(
        [
            normalized_design_overview,
            normalized_platforms,
            design_zone_updates,
            design_screen_updates,
            design_screen_feature_links,
            design_flow_updates,
            design_flow_step_updates,
            design_flow_alternative_updates,
            design_navigation_updates,
            normalized_platform_constraints,
            design_screen_data_updates,
        ]
    )
    used_tech_fields = any(
        [
            normalized_stack_overview,
            normalized_project_type,
            normalized_requirements,
            normalized_preferences,
            normalized_tech_constraints,
            tech_component_updates,
            tech_library_updates,
            tech_code_organization,
            tech_alternative_updates,
        ]
    )
    used_architecture_fields = any(
        [
            normalized_architecture_overview,
            architecture_project_structure,
            architecture_directory_updates,
            architecture_entity_updates,
            architecture_entity_field_updates,
            architecture_entity_relationship_updates,
            architecture_entity_state_updates,
            architecture_endpoint_updates,
            architecture_endpoint_screen_updates,
            architecture_endpoint_field_updates,
            architecture_endpoint_error_updates,
            architecture_integration_updates,
            normalized_code_principles,
            architecture_pattern_updates,
            normalized_security_notes,
            normalized_performance_notes,
        ]
    )
    used_plan_fields = any([normalized_plan_overview, normalized_planning_principles])

    if used_concept_fields and normalized_stage != CONCEPT_STAGE:
        return ["concept-specific capture options are only supported for stage mvp.concept"]
    if used_design_fields and normalized_stage != DESIGN_STAGE:
        return ["design-specific capture options are only supported for stage mvp.design"]
    if used_tech_fields and normalized_stage != TECH_STAGE:
        return ["tech-specific capture options are only supported for stage mvp.tech"]
    if used_architecture_fields and normalized_stage != ARCHITECTURE_STAGE:
        return ["architecture-specific capture options are only supported for stage mvp.architecture"]
    if used_plan_fields and normalized_stage != PLAN_STAGE:
        return ["plan-specific capture options are only supported for stage mvp.plan"]
    if normalized_next_actions and normalized_stage not in {CONCEPT_STAGE, DESIGN_STAGE, TECH_STAGE, ARCHITECTURE_STAGE, PLAN_STAGE}:
        return ["--next-action is only supported for stages mvp.concept, mvp.design, mvp.tech, mvp.architecture, and mvp.plan"]
    return []
