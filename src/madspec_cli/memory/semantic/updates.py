from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..stages.architecture.state import ARCHITECTURE_STAGE, update_architecture_state
from ..stages.concept.state import CONCEPT_STAGE, update_concept_state
from ..stages.design.state import DESIGN_STAGE, update_design_state
from ..stages.tech.state import TECH_STAGE, update_tech_state


@dataclass(frozen=True)
class StageSummaryBundles:
    concept_fact_summaries: list[str]
    concept_decision_summaries: list[str]
    concept_contract_summaries: list[str]
    design_fact_summaries: list[str]
    design_decision_summaries: list[str]
    design_contract_summaries: list[str]
    tech_fact_summaries: list[str]
    tech_decision_summaries: list[str]
    tech_contract_summaries: list[str]
    architecture_fact_summaries: list[str]
    architecture_decision_summaries: list[str]
    architecture_contract_summaries: list[str]


def build_stage_summary_bundles(
    *,
    normalized_project_name: str,
    normalized_system_overview: str,
    normalized_audiences: list[str],
    normalized_scenarios: list[str],
    normalized_pain_points: list[str],
    normalized_assumptions: list[str],
    concept_feature_updates: dict[str, list[dict[str, str]]],
    normalized_constraints: list[str],
    normalized_design_overview: str,
    normalized_platforms: list[str],
    design_zone_updates: list[dict[str, str]],
    design_screen_updates: list[dict[str, Any]],
    design_flow_updates: list[dict[str, Any]],
    design_flow_step_updates: list[dict[str, str]],
    design_screen_data_updates: list[dict[str, str]],
    design_screen_feature_links: list[dict[str, str]],
    design_navigation_updates: list[dict[str, str]],
    design_flow_alternative_updates: list[dict[str, str]],
    normalized_platform_constraints: list[str],
    normalized_project_type: str,
    normalized_stack_overview: str,
    normalized_requirements: list[str],
    normalized_preferences: list[str],
    tech_component_updates: list[dict[str, str]],
    tech_library_updates: list[dict[str, str]],
    tech_code_organization: dict[str, str] | None,
    tech_alternative_updates: list[dict[str, str]],
    normalized_tech_constraints: list[str],
    normalized_architecture_overview: str,
    architecture_project_structure: dict[str, str] | None,
    architecture_directory_updates: list[dict[str, str]],
    architecture_entity_updates: list[dict[str, str]],
    architecture_entity_field_updates: list[dict[str, Any]],
    architecture_integration_updates: list[dict[str, Any]],
    normalized_code_principles: list[str],
    normalized_security_notes: list[str],
    normalized_performance_notes: list[str],
    architecture_entity_relationship_updates: list[dict[str, Any]],
    architecture_entity_state_updates: list[dict[str, Any]],
    architecture_endpoint_updates: list[dict[str, Any]],
    architecture_endpoint_screen_updates: list[dict[str, str]],
    architecture_endpoint_field_updates: list[dict[str, Any]],
    architecture_pattern_updates: list[dict[str, str]],
    architecture_endpoint_error_updates: list[dict[str, Any]],
) -> StageSummaryBundles:
    return StageSummaryBundles(
        concept_fact_summaries=(
            ([f"Project name: {normalized_project_name}"] if normalized_project_name else [])
            + ([f"System overview: {normalized_system_overview}"] if normalized_system_overview else [])
            + normalized_audiences
            + normalized_scenarios
            + normalized_pain_points
            + normalized_assumptions
        ),
        concept_decision_summaries=[
            f"{priority.upper()} feature: {feature['name']} - {feature['description']}"
            for priority in ("p1", "p2", "p3")
            for feature in concept_feature_updates[priority]
        ],
        concept_contract_summaries=normalized_constraints,
        design_fact_summaries=(
            ([f"Design overview: {normalized_design_overview}"] if normalized_design_overview else [])
            + [f"Platform: {item}" for item in normalized_platforms]
            + [f"Zone {item['id']}: {item['title']} - {item['description']}" for item in design_zone_updates]
            + [
                f"Screen {item['id']}: {item['title']} ({item['prototype']}) - {item['purpose']}"
                for item in design_screen_updates
            ]
            + [f"Flow {item['id']}: {item['title']} - {item['goal']}" for item in design_flow_updates]
            + [
                f"Flow step {item['flowId']}: {item['screenId']} -> {item['action']} -> {item['result']}"
                for item in design_flow_step_updates
            ]
            + [
                f"Screen data {item['screenId']} ({item['dataKind']}): {item['name']}"
                for item in design_screen_data_updates
            ]
        ),
        design_decision_summaries=(
            [
                f"Screen {item['screenId']} covers {item['priority'].upper()} feature {item['featureName']}"
                for item in design_screen_feature_links
            ]
            + [
                f"Navigation {item['from']} -> {item['to']} via {item['trigger']}"
                for item in design_navigation_updates
            ]
            + [
                f"Alternative path for {item['flowId']}: {item['description']}"
                for item in design_flow_alternative_updates
            ]
        ),
        design_contract_summaries=normalized_platform_constraints,
        tech_fact_summaries=(
            ([f"Project type: {normalized_project_type}"] if normalized_project_type else [])
            + ([f"Stack overview: {normalized_stack_overview}"] if normalized_stack_overview else [])
            + normalized_requirements
            + normalized_preferences
        ),
        tech_decision_summaries=(
            [
                f"Stack component {item['slot']}: {item['name']} {item['version']} - {item['rationale']}"
                for item in tech_component_updates
            ]
            + [
                f"Library {item['scope']}: {item['name']} {item['version']} - {item['purpose']}"
                for item in tech_library_updates
            ]
            + (
                [
                    "Code organization: "
                    f"{tech_code_organization['repoStrategy']} / "
                    f"{tech_code_organization['sourceLayout']} / "
                    f"{tech_code_organization['modularity']} - "
                    f"{tech_code_organization['rationale']}"
                ]
                if tech_code_organization is not None
                else []
            )
            + [
                f"Rejected alternative for {item['slot']}: {item['option']} - {item['reasonRejected']}"
                for item in tech_alternative_updates
            ]
        ),
        tech_contract_summaries=normalized_tech_constraints,
        architecture_fact_summaries=(
            ([f"Architecture overview: {normalized_architecture_overview}"] if normalized_architecture_overview else [])
            + (
                [
                    "Project structure: "
                    f"{architecture_project_structure['strategy']} - "
                    f"{architecture_project_structure['rationale']}"
                ]
                if architecture_project_structure is not None
                else []
            )
            + [f"Directory {item['path']}: {item['purpose']}" for item in architecture_directory_updates]
            + [f"Entity {item['name']}: {item['description']}" for item in architecture_entity_updates]
            + [
                f"Entity field {item['entity']}.{item['field']['name']}: "
                f"{item['field']['type']} - {item['field']['description']}"
                for item in architecture_entity_field_updates
            ]
            + [f"Integration {item['name']} ({item['kind']}): {item['purpose']}" for item in architecture_integration_updates]
            + normalized_code_principles
            + normalized_security_notes
            + normalized_performance_notes
        ),
        architecture_decision_summaries=(
            [
                f"Entity relationship {item['entity']} -> {item['relationship']['target']} "
                f"({item['relationship']['kind']}): {item['relationship']['description']}"
                for item in architecture_entity_relationship_updates
            ]
            + [
                f"Entity state {item['entity']}: {item['state']['name']} - {item['state']['description']}"
                for item in architecture_entity_state_updates
            ]
            + [
                f"Endpoint {item['operationId']}: {item['method']} {item['path']} - {item['summary']}"
                for item in architecture_endpoint_updates
            ]
            + [
                f"Endpoint {item['operationId']} linked to screen {item['screenId']}"
                for item in architecture_endpoint_screen_updates
            ]
            + [
                f"Endpoint field {item['operationId']} {item['field']['section']} "
                f"{item['field']['name']}: {item['field']['type']} - {item['field']['description']}"
                for item in architecture_endpoint_field_updates
            ]
            + [f"Pattern {item['name']}: {item['rationale']}" for item in architecture_pattern_updates]
        ),
        architecture_contract_summaries=[
            f"Endpoint error {item['operationId']} {item['error']['status']} "
            f"{item['error']['code']}: {item['error']['description']}"
            for item in architecture_endpoint_error_updates
        ],
    )


def has_capture_payload(
    *,
    normalized_summary: str,
    normalized_facts: list[str],
    normalized_decisions: list[str],
    normalized_contracts: list[str],
    normalized_questions: list[str],
    normalized_pending_actions: list[str],
    bundles: StageSummaryBundles,
) -> bool:
    return any(
        [
            normalized_summary,
            normalized_facts,
            normalized_decisions,
            normalized_contracts,
            normalized_questions,
            normalized_pending_actions,
            bundles.concept_fact_summaries,
            bundles.concept_decision_summaries,
            bundles.concept_contract_summaries,
            bundles.design_fact_summaries,
            bundles.design_decision_summaries,
            bundles.design_contract_summaries,
            bundles.tech_fact_summaries,
            bundles.tech_decision_summaries,
            bundles.tech_contract_summaries,
            bundles.architecture_fact_summaries,
            bundles.architecture_decision_summaries,
            bundles.architecture_contract_summaries,
        ]
    )


def apply_stage_state_update(
    *,
    normalized_stage: str,
    concept_state: dict[str, Any],
    design_state: dict[str, Any],
    tech_state: dict[str, Any],
    architecture_state: dict[str, Any],
    normalized_project_name: str,
    normalized_system_overview: str,
    normalized_audiences: list[str],
    normalized_scenarios: list[str],
    normalized_pain_points: list[str],
    normalized_assumptions: list[str],
    concept_feature_updates: dict[str, list[dict[str, str]]],
    normalized_constraints: list[str],
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
    normalized_project_type: str,
    normalized_stack_overview: str,
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
    normalized_next_actions: list[str],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    if normalized_stage == CONCEPT_STAGE:
        concept_state = update_concept_state(
            concept_state,
            project_name=normalized_project_name or None,
            system_overview=normalized_system_overview or None,
            audiences=normalized_audiences,
            scenarios=normalized_scenarios,
            pain_points=normalized_pain_points,
            features=concept_feature_updates,
            constraints=normalized_constraints,
            assumptions=normalized_assumptions,
            next_actions=normalized_next_actions,
        )
    elif normalized_stage == DESIGN_STAGE:
        design_state = update_design_state(
            design_state,
            design_overview=normalized_design_overview or None,
            platforms=normalized_platforms,
            zones=design_zone_updates,
            screens=design_screen_updates,
            screen_feature_links=design_screen_feature_links,
            flows=design_flow_updates,
            flow_steps=design_flow_step_updates,
            flow_alternatives=design_flow_alternative_updates,
            navigation=design_navigation_updates,
            platform_constraints=normalized_platform_constraints,
            screen_data_entries=design_screen_data_updates,
            next_actions=normalized_next_actions,
        )
    elif normalized_stage == TECH_STAGE:
        tech_state = update_tech_state(
            tech_state,
            project_type=normalized_project_type or None,
            stack_overview=normalized_stack_overview or None,
            requirements=normalized_requirements,
            preferences=normalized_preferences,
            constraints=normalized_tech_constraints,
            components=tech_component_updates,
            libraries=tech_library_updates,
            code_organization=tech_code_organization,
            alternatives=tech_alternative_updates,
            next_actions=normalized_next_actions,
        )
    elif normalized_stage == ARCHITECTURE_STAGE:
        architecture_state = update_architecture_state(
            architecture_state,
            architecture_overview=normalized_architecture_overview or None,
            project_structure=architecture_project_structure,
            directories=architecture_directory_updates,
            entities=architecture_entity_updates,
            entity_fields=architecture_entity_field_updates,
            entity_relationships=architecture_entity_relationship_updates,
            entity_states=architecture_entity_state_updates,
            endpoints=architecture_endpoint_updates,
            endpoint_screens=architecture_endpoint_screen_updates,
            endpoint_fields=architecture_endpoint_field_updates,
            endpoint_errors=architecture_endpoint_error_updates,
            integrations=architecture_integration_updates,
            code_principles=normalized_code_principles,
            patterns=architecture_pattern_updates,
            security_notes=normalized_security_notes,
            performance_notes=normalized_performance_notes,
            next_actions=normalized_next_actions,
        )
    return concept_state, design_state, tech_state, architecture_state
