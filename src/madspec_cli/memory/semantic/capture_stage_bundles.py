from __future__ import annotations

from .capture_models import CaptureInputs, ParsedStageBundle
from .parsers import (
    parse_architecture_capture,
    parse_concept_capture,
    parse_design_capture,
    parse_feature_init_capture,
    parse_tech_capture,
)
from ..stages.feature_init.state import FEATURE_INIT_STAGE


def build_parsed_stage_bundle(inputs: CaptureInputs) -> ParsedStageBundle:
    if inputs.stage == FEATURE_INIT_STAGE:
        concept_feature_updates = {"p1": [], "p2": [], "p3": []}
        concept_errors: list[str] = []
        feature_init_parse = parse_feature_init_capture(
            feature_p1=inputs.feature_p1,
            feature_p2=inputs.feature_p2,
            feature_p3=inputs.feature_p3,
            existing_modules=inputs.existing_modules,
            modified_files=inputs.modified_files,
            new_files=inputs.new_files,
            dependencies=inputs.dependencies,
        )
        feature_init_feature_updates = feature_init_parse.feature_updates
        feature_existing_modules = feature_init_parse.existing_modules
        feature_modified_files = feature_init_parse.modified_files
        feature_new_files = feature_init_parse.new_files
        feature_dependencies = feature_init_parse.dependencies
        feature_init_errors = feature_init_parse.errors
    else:
        concept_parse = parse_concept_capture(
            feature_p1=inputs.feature_p1,
            feature_p2=inputs.feature_p2,
            feature_p3=inputs.feature_p3,
        )
        concept_feature_updates = concept_parse.feature_updates
        concept_errors = concept_parse.errors
        feature_init_feature_updates = {"p1": [], "p2": [], "p3": []}
        feature_existing_modules = []
        feature_modified_files = []
        feature_new_files = []
        feature_dependencies = []
        feature_init_errors = []

    design_parse = parse_design_capture(
        zones=inputs.zones,
        screens=inputs.screens,
        screen_features=inputs.screen_features,
        flows=inputs.flows,
        flow_steps=inputs.flow_steps,
        flow_alternatives=inputs.flow_alternatives,
        navigation=inputs.navigation,
        screen_data=inputs.screen_data,
    )
    tech_parse = parse_tech_capture(
        stack_components=inputs.stack_components,
        libraries=inputs.libraries,
        alternatives=inputs.alternatives,
        code_organization=inputs.code_organization,
    )
    architecture_parse = parse_architecture_capture(
        project_structure=inputs.project_structure,
        directories=inputs.directories,
        entities=inputs.entities,
        entity_fields=inputs.entity_fields,
        entity_relationships=inputs.entity_relationships,
        entity_states=inputs.entity_states,
        endpoints=inputs.endpoints,
        endpoint_screens=inputs.endpoint_screens,
        endpoint_fields=inputs.endpoint_fields,
        endpoint_errors=inputs.endpoint_errors,
        integrations=inputs.integrations,
        architecture_patterns=inputs.architecture_patterns,
    )

    return ParsedStageBundle(
        concept_feature_updates=concept_feature_updates,
        concept_errors=concept_errors,
        feature_init_feature_updates=feature_init_feature_updates,
        feature_existing_modules=feature_existing_modules,
        feature_modified_files=feature_modified_files,
        feature_new_files=feature_new_files,
        feature_dependencies=feature_dependencies,
        feature_init_errors=feature_init_errors,
        design_zone_updates=design_parse.zone_updates,
        design_screen_updates=design_parse.screen_updates,
        design_screen_feature_links=design_parse.screen_feature_links,
        design_flow_updates=design_parse.flow_updates,
        design_flow_step_updates=design_parse.flow_step_updates,
        design_flow_alternative_updates=design_parse.flow_alternative_updates,
        design_navigation_updates=design_parse.navigation_updates,
        design_screen_data_updates=design_parse.screen_data_updates,
        design_errors=design_parse.errors,
        tech_component_updates=tech_parse.component_updates,
        tech_library_updates=tech_parse.library_updates,
        tech_alternative_updates=tech_parse.alternative_updates,
        tech_code_organization=tech_parse.code_organization,
        tech_errors=tech_parse.errors,
        architecture_project_structure=architecture_parse.project_structure,
        architecture_directory_updates=architecture_parse.directory_updates,
        architecture_entity_updates=architecture_parse.entity_updates,
        architecture_entity_field_updates=architecture_parse.entity_field_updates,
        architecture_entity_relationship_updates=architecture_parse.entity_relationship_updates,
        architecture_entity_state_updates=architecture_parse.entity_state_updates,
        architecture_endpoint_updates=architecture_parse.endpoint_updates,
        architecture_endpoint_screen_updates=architecture_parse.endpoint_screen_updates,
        architecture_endpoint_field_updates=architecture_parse.endpoint_field_updates,
        architecture_endpoint_error_updates=architecture_parse.endpoint_error_updates,
        architecture_integration_updates=architecture_parse.integration_updates,
        architecture_pattern_updates=architecture_parse.pattern_updates,
        architecture_errors=architecture_parse.errors,
    )
