from __future__ import annotations

from pathlib import Path
from typing import Any

from .architecture_state import (
    ARCHITECTURE_STAGE,
    load_architecture_state,
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
    save_architecture_state,
    update_architecture_state,
)
from .concept_state import (
    CONCEPT_STAGE,
    load_concept_state,
    parse_feature_value,
    save_concept_state,
    update_concept_state,
)
from .design_state import (
    DESIGN_STAGE,
    load_design_state,
    parse_flow_alternative_value,
    parse_flow_step_value,
    parse_flow_value,
    parse_navigation_value,
    parse_screen_data_value,
    parse_screen_feature_value,
    parse_screen_value,
    parse_zone_value,
    save_design_state,
    update_design_state,
)
from .tech_state import (
    TECH_STAGE,
    load_tech_state,
    parse_alternative_value,
    parse_code_organization_value,
    parse_library_value,
    parse_stack_component_value,
    save_tech_state,
    update_tech_state,
)
from .records import make_record
from .storage import (
    _default_active_session,
    append_jsonl,
    ensure_memory_layout,
    get_memory_paths,
    now_iso,
    read_json,
    write_json,
)
from .validation import validate_branch_memory
from .views import consolidate_branch_memory

CAPTURE_STAGES = {
    "mvp.concept",
    "mvp.design",
    "mvp.tech",
    "mvp.architecture",
    "review",
    "security",
}


def _normalize_text_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    return [value.strip() for value in values if value and value.strip()]


def _snapshot_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _restore_file(path: Path, content: str | None) -> None:
    if content is None:
        if path.exists():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _append_unique(existing: list[str], values: list[str]) -> list[str]:
    result = list(existing)
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _filter_non_blocking_design_validation_errors(errors: list[str]) -> list[str]:
    non_blocking_prefixes = (
        "design coverage missing ",
        "design references missing prototype file ",
        "design screen ",
        "design flow ",
        "design navigation ",
    )
    return [error for error in errors if not error.startswith(non_blocking_prefixes)]


def _filter_non_blocking_architecture_validation_errors(errors: list[str]) -> list[str]:
    non_blocking_prefixes = (
        "architecture entity '",
        "architecture endpoint '",
        "architecture must link at least one endpoint to design screen ",
        "architecture screen '",
    )
    return [error for error in errors if not error.startswith(non_blocking_prefixes)]


def capture_stage_memory(
    project_path: Path,
    branch_name: str,
    stage: str,
    *,
    summary: str | None = None,
    facts: list[str] | None = None,
    decisions: list[str] | None = None,
    contracts: list[str] | None = None,
    evidence: list[str] | None = None,
    questions: list[str] | None = None,
    pending_actions: list[str] | None = None,
    project_name: str | None = None,
    system_overview: str | None = None,
    audiences: list[str] | None = None,
    scenarios: list[str] | None = None,
    pain_points: list[str] | None = None,
    feature_p1: list[str] | None = None,
    feature_p2: list[str] | None = None,
    feature_p3: list[str] | None = None,
    constraints: list[str] | None = None,
    assumptions: list[str] | None = None,
    next_actions: list[str] | None = None,
    design_overview: str | None = None,
    platforms: list[str] | None = None,
    zones: list[str] | None = None,
    screens: list[str] | None = None,
    screen_features: list[str] | None = None,
    flows: list[str] | None = None,
    flow_steps: list[str] | None = None,
    flow_alternatives: list[str] | None = None,
    navigation: list[str] | None = None,
    platform_constraints: list[str] | None = None,
    screen_data: list[str] | None = None,
    stack_overview: str | None = None,
    project_type: str | None = None,
    requirements: list[str] | None = None,
    preferences: list[str] | None = None,
    tech_constraints: list[str] | None = None,
    stack_components: list[str] | None = None,
    libraries: list[str] | None = None,
    code_organization: str | None = None,
    alternatives: list[str] | None = None,
    architecture_overview: str | None = None,
    project_structure: str | None = None,
    directories: list[str] | None = None,
    entities: list[str] | None = None,
    entity_fields: list[str] | None = None,
    entity_relationships: list[str] | None = None,
    entity_states: list[str] | None = None,
    endpoints: list[str] | None = None,
    endpoint_screens: list[str] | None = None,
    endpoint_fields: list[str] | None = None,
    endpoint_errors: list[str] | None = None,
    integrations: list[str] | None = None,
    code_principles: list[str] | None = None,
    architecture_patterns: list[str] | None = None,
    security_notes: list[str] | None = None,
    performance_notes: list[str] | None = None,
    status: str = "validated",
) -> dict[str, Any]:
    normalized_stage = stage.strip().lower()
    if normalized_stage not in CAPTURE_STAGES:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": ["stage must be one of: " + ", ".join(sorted(CAPTURE_STAGES))],
        }

    normalized_status = status.strip().lower()
    if normalized_status not in {"proposed", "validated", "conflicted", "obsolete"}:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": ["status must be one of: conflicted, obsolete, proposed, validated"],
        }

    normalized_summary = (summary or "").strip()
    normalized_facts = _normalize_text_list(facts)
    normalized_decisions = _normalize_text_list(decisions)
    normalized_contracts = _normalize_text_list(contracts)
    normalized_evidence = _normalize_text_list(evidence)
    normalized_questions = _normalize_text_list(questions)
    normalized_pending_actions = _normalize_text_list(pending_actions)
    normalized_audiences = _normalize_text_list(audiences)
    normalized_scenarios = _normalize_text_list(scenarios)
    normalized_pain_points = _normalize_text_list(pain_points)
    normalized_constraints = _normalize_text_list(constraints)
    normalized_assumptions = _normalize_text_list(assumptions)
    normalized_next_actions = _normalize_text_list(next_actions)
    normalized_project_name = (project_name or "").strip()
    normalized_system_overview = (system_overview or "").strip()
    normalized_design_overview = (design_overview or "").strip()
    normalized_platforms = _normalize_text_list(platforms)
    normalized_platform_constraints = _normalize_text_list(platform_constraints)
    normalized_stack_overview = (stack_overview or "").strip()
    normalized_project_type = (project_type or "").strip()
    normalized_requirements = _normalize_text_list(requirements)
    normalized_preferences = _normalize_text_list(preferences)
    normalized_tech_constraints = _normalize_text_list(tech_constraints)
    normalized_architecture_overview = (architecture_overview or "").strip()
    normalized_code_principles = _normalize_text_list(code_principles)
    normalized_security_notes = _normalize_text_list(security_notes)
    normalized_performance_notes = _normalize_text_list(performance_notes)
    concept_feature_updates: dict[str, list[dict[str, str]]] = {"p1": [], "p2": [], "p3": []}
    concept_feature_errors: list[str] = []
    for priority, values in {
        "p1": _normalize_text_list(feature_p1),
        "p2": _normalize_text_list(feature_p2),
        "p3": _normalize_text_list(feature_p3),
    }.items():
        for value in values:
            parsed = parse_feature_value(value)
            if parsed is None:
                concept_feature_errors.append(
                    f"{priority} feature must use '<name>::<description>' format: {value}"
                )
                continue
            concept_feature_updates[priority].append(parsed)

    design_zone_updates: list[dict[str, str]] = []
    design_screen_updates: list[dict[str, Any]] = []
    design_screen_feature_links: list[dict[str, str]] = []
    design_flow_updates: list[dict[str, Any]] = []
    design_flow_step_updates: list[dict[str, str]] = []
    design_flow_alternative_updates: list[dict[str, str]] = []
    design_navigation_updates: list[dict[str, str]] = []
    design_screen_data_updates: list[dict[str, str]] = []
    tech_component_updates: list[dict[str, str]] = []
    tech_library_updates: list[dict[str, str]] = []
    tech_alternative_updates: list[dict[str, str]] = []
    tech_code_organization: dict[str, str] | None = None
    architecture_project_structure: dict[str, str] | None = None
    architecture_directory_updates: list[dict[str, str]] = []
    architecture_entity_updates: list[dict[str, str]] = []
    architecture_entity_field_updates: list[dict[str, Any]] = []
    architecture_entity_relationship_updates: list[dict[str, Any]] = []
    architecture_entity_state_updates: list[dict[str, Any]] = []
    architecture_endpoint_updates: list[dict[str, Any]] = []
    architecture_endpoint_screen_updates: list[dict[str, str]] = []
    architecture_endpoint_field_updates: list[dict[str, Any]] = []
    architecture_endpoint_error_updates: list[dict[str, Any]] = []
    architecture_integration_updates: list[dict[str, Any]] = []
    architecture_pattern_updates: list[dict[str, str]] = []
    design_errors: list[str] = []
    tech_errors: list[str] = []
    architecture_errors: list[str] = []

    for value in _normalize_text_list(zones):
        parsed = parse_zone_value(value)
        if parsed is None:
            design_errors.append(f"zone must use '<id>::<title>::<description>' format: {value}")
            continue
        design_zone_updates.append(parsed)

    for value in _normalize_text_list(screens):
        parsed = parse_screen_value(value)
        if parsed is None:
            design_errors.append(
                f"screen must use '<id>::<title>::<zone>::<prototype>::<purpose>' format: {value}"
            )
            continue
        design_screen_updates.append(parsed)

    for value in _normalize_text_list(screen_features):
        parsed = parse_screen_feature_value(value)
        if parsed is None:
            design_errors.append(
                f"screen-feature must use '<screen-id>::<priority>::<feature-name>' format: {value}"
            )
            continue
        design_screen_feature_links.append(parsed)

    for value in _normalize_text_list(flows):
        parsed = parse_flow_value(value)
        if parsed is None:
            design_errors.append(f"flow must use '<id>::<title>::<goal>' format: {value}")
            continue
        design_flow_updates.append(parsed)

    for value in _normalize_text_list(flow_steps):
        parsed = parse_flow_step_value(value)
        if parsed is None:
            design_errors.append(
                f"flow-step must use '<flow-id>::<screen-id>::<action>::<result>' format: {value}"
            )
            continue
        design_flow_step_updates.append(parsed)

    for value in _normalize_text_list(flow_alternatives):
        parsed = parse_flow_alternative_value(value)
        if parsed is None:
            design_errors.append(f"flow-alternative must use '<flow-id>::<description>' format: {value}")
            continue
        design_flow_alternative_updates.append(parsed)

    for value in _normalize_text_list(navigation):
        parsed = parse_navigation_value(value)
        if parsed is None:
            design_errors.append(f"nav must use '<from-screen>::<to-screen>::<trigger>' format: {value}")
            continue
        design_navigation_updates.append(parsed)

    for value in _normalize_text_list(screen_data):
        parsed = parse_screen_data_value(value)
        if parsed is None:
            design_errors.append(
                f"screen-data must use '<screen-id>::<displayed|input>::<name>' format: {value}"
            )
            continue
        design_screen_data_updates.append(parsed)

    for value in _normalize_text_list(stack_components):
        parsed = parse_stack_component_value(value)
        if parsed is None:
            tech_errors.append(
                f"stack-component must use '<slot>::<name>::<version>::<rationale>' format: {value}"
            )
            continue
        tech_component_updates.append(parsed)

    for value in _normalize_text_list(libraries):
        parsed = parse_library_value(value)
        if parsed is None:
            tech_errors.append(
                f"library must use '<scope>::<name>::<version>::<purpose>' format: {value}"
            )
            continue
        tech_library_updates.append(parsed)

    for value in _normalize_text_list(alternatives):
        parsed = parse_alternative_value(value)
        if parsed is None:
            tech_errors.append(
                f"alternative must use '<slot>::<option>::<reason-rejected>' format: {value}"
            )
            continue
        tech_alternative_updates.append(parsed)

    if code_organization:
        tech_code_organization = parse_code_organization_value(code_organization)
        if tech_code_organization is None:
            tech_errors.append(
                "code-organization must use '<repo-strategy>::<source-layout>::<modularity>::<rationale>' format"
            )

    if project_structure:
        architecture_project_structure = parse_project_structure_value(project_structure)
        if architecture_project_structure is None:
            architecture_errors.append(
                "project-structure must use '<strategy>::<rationale>' format"
            )

    for value in _normalize_text_list(directories):
        parsed = parse_directory_value(value)
        if parsed is None:
            architecture_errors.append(f"directory must use '<path>::<purpose>' format: {value}")
            continue
        architecture_directory_updates.append(parsed)

    for value in _normalize_text_list(entities):
        parsed = parse_entity_value(value)
        if parsed is None:
            architecture_errors.append(f"entity must use '<name>::<description>' format: {value}")
            continue
        architecture_entity_updates.append(parsed)

    for value in _normalize_text_list(entity_fields):
        parsed = parse_entity_field_value(value)
        if parsed is None:
            architecture_errors.append(
                f"entity-field must use '<entity>::<field>::<type>::<required|optional>::<description>' format: {value}"
            )
            continue
        architecture_entity_field_updates.append(parsed)

    for value in _normalize_text_list(entity_relationships):
        parsed = parse_entity_relationship_value(value)
        if parsed is None:
            architecture_errors.append(
                f"entity-relationship must use '<entity>::<target>::<kind>::<description>' format: {value}"
            )
            continue
        architecture_entity_relationship_updates.append(parsed)

    for value in _normalize_text_list(entity_states):
        parsed = parse_entity_state_value(value)
        if parsed is None:
            architecture_errors.append(
                f"entity-state must use '<entity>::<state>::<description>' format: {value}"
            )
            continue
        architecture_entity_state_updates.append(parsed)

    for value in _normalize_text_list(endpoints):
        parsed = parse_endpoint_value(value)
        if parsed is None:
            architecture_errors.append(
                f"endpoint must use '<operation-id>::<METHOD>::</path>::<summary>' format: {value}"
            )
            continue
        architecture_endpoint_updates.append(parsed)

    for value in _normalize_text_list(endpoint_screens):
        parsed = parse_endpoint_screen_value(value)
        if parsed is None:
            architecture_errors.append(
                f"endpoint-screen must use '<operation-id>::<screen-id>' format: {value}"
            )
            continue
        architecture_endpoint_screen_updates.append(parsed)

    for value in _normalize_text_list(endpoint_fields):
        parsed = parse_endpoint_field_value(value)
        if parsed is None:
            architecture_errors.append(
                f"endpoint-field must use '<operation-id>::<section>::<name>::<type>::<required|optional>::<description>' format: {value}"
            )
            continue
        architecture_endpoint_field_updates.append(parsed)

    for value in _normalize_text_list(endpoint_errors):
        parsed = parse_endpoint_error_value(value)
        if parsed is None:
            architecture_errors.append(
                f"endpoint-error must use '<operation-id>::<status>::<code>::<description>' format: {value}"
            )
            continue
        architecture_endpoint_error_updates.append(parsed)

    for value in _normalize_text_list(integrations):
        parsed = parse_integration_value(value)
        if parsed is None:
            architecture_errors.append(
                f"integration must use '<name>::<kind>::<purpose>::<touchpoints>' format: {value}"
            )
            continue
        architecture_integration_updates.append(parsed)

    for value in _normalize_text_list(architecture_patterns):
        parsed = parse_pattern_value(value)
        if parsed is None:
            architecture_errors.append(
                f"pattern must use '<name>::<rationale>' format: {value}"
            )
            continue
        architecture_pattern_updates.append(parsed)

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
    if used_concept_fields and normalized_stage != CONCEPT_STAGE:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": ["concept-specific capture options are only supported for stage mvp.concept"],
        }
    if used_design_fields and normalized_stage != DESIGN_STAGE:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": ["design-specific capture options are only supported for stage mvp.design"],
        }
    if used_tech_fields and normalized_stage != TECH_STAGE:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": ["tech-specific capture options are only supported for stage mvp.tech"],
        }
    if used_architecture_fields and normalized_stage != ARCHITECTURE_STAGE:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": ["architecture-specific capture options are only supported for stage mvp.architecture"],
        }
    if normalized_next_actions and normalized_stage not in {CONCEPT_STAGE, DESIGN_STAGE, TECH_STAGE, ARCHITECTURE_STAGE}:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": ["--next-action is only supported for stages mvp.concept, mvp.design, mvp.tech, and mvp.architecture"],
        }
    if concept_feature_errors:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": concept_feature_errors,
        }
    if design_errors:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": design_errors,
        }
    if tech_errors:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": tech_errors,
        }
    if architecture_errors:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": architecture_errors,
        }
    normalized_pending_actions = _append_unique(normalized_pending_actions, normalized_next_actions)
    concept_fact_summaries = (
        ([f"Project name: {normalized_project_name}"] if normalized_project_name else [])
        + ([f"System overview: {normalized_system_overview}"] if normalized_system_overview else [])
        + normalized_audiences
        + normalized_scenarios
        + normalized_pain_points
        + normalized_assumptions
    )
    concept_decision_summaries = [
        f"{priority.upper()} feature: {feature['name']} - {feature['description']}"
        for priority in ("p1", "p2", "p3")
        for feature in concept_feature_updates[priority]
    ]
    concept_contract_summaries = normalized_constraints
    design_fact_summaries = (
        ([f"Design overview: {normalized_design_overview}"] if normalized_design_overview else [])
        + [f"Platform: {item}" for item in normalized_platforms]
        + [
            f"Zone {item['id']}: {item['title']} - {item['description']}"
            for item in design_zone_updates
        ]
        + [
            f"Screen {item['id']}: {item['title']} ({item['prototype']}) - {item['purpose']}"
            for item in design_screen_updates
        ]
        + [
            f"Flow {item['id']}: {item['title']} - {item['goal']}"
            for item in design_flow_updates
        ]
        + [
            f"Flow step {item['flowId']}: {item['screenId']} -> {item['action']} -> {item['result']}"
            for item in design_flow_step_updates
        ]
        + [
            f"Screen data {item['screenId']} ({item['dataKind']}): {item['name']}"
            for item in design_screen_data_updates
        ]
    )
    design_decision_summaries = (
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
    )
    design_contract_summaries = normalized_platform_constraints
    tech_fact_summaries = (
        ([f"Project type: {normalized_project_type}"] if normalized_project_type else [])
        + ([f"Stack overview: {normalized_stack_overview}"] if normalized_stack_overview else [])
        + normalized_requirements
        + normalized_preferences
    )
    tech_decision_summaries = (
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
    )
    tech_contract_summaries = normalized_tech_constraints
    architecture_fact_summaries = (
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
        + [
            f"Directory {item['path']}: {item['purpose']}"
            for item in architecture_directory_updates
        ]
        + [
            f"Entity {item['name']}: {item['description']}"
            for item in architecture_entity_updates
        ]
        + [
            f"Entity field {item['entity']}.{item['field']['name']}: {item['field']['type']} - {item['field']['description']}"
            for item in architecture_entity_field_updates
        ]
        + [
            f"Integration {item['name']} ({item['kind']}): {item['purpose']}"
            for item in architecture_integration_updates
        ]
        + normalized_code_principles
        + normalized_security_notes
        + normalized_performance_notes
    )
    architecture_decision_summaries = (
        [
            f"Entity relationship {item['entity']} -> {item['relationship']['target']} ({item['relationship']['kind']}): {item['relationship']['description']}"
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
            f"Endpoint field {item['operationId']} {item['field']['section']} {item['field']['name']}: {item['field']['type']} - {item['field']['description']}"
            for item in architecture_endpoint_field_updates
        ]
        + [
            f"Pattern {item['name']}: {item['rationale']}"
            for item in architecture_pattern_updates
        ]
    )
    architecture_contract_summaries = (
        [
            f"Endpoint error {item['operationId']} {item['error']['status']} {item['error']['code']}: {item['error']['description']}"
            for item in architecture_endpoint_error_updates
        ]
    )
    if not any(
        [
            normalized_summary,
            normalized_facts,
            normalized_decisions,
            normalized_contracts,
            normalized_questions,
            normalized_pending_actions,
            concept_fact_summaries,
            concept_decision_summaries,
            concept_contract_summaries,
            design_fact_summaries,
            design_decision_summaries,
            design_contract_summaries,
            tech_fact_summaries,
            tech_decision_summaries,
            tech_contract_summaries,
            architecture_fact_summaries,
            architecture_decision_summaries,
            architecture_contract_summaries,
        ]
    ):
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": ["capture payload must include summary, fact, decision, contract, question, or pending action"],
        }

    ensure_memory_layout(project_path, branch_name)
    paths = get_memory_paths(project_path, branch_name)
    snapshots = {
        paths.active_session: _snapshot_file(paths.active_session),
        paths.decision_log: _snapshot_file(paths.decision_log),
        paths.facts: _snapshot_file(paths.facts),
        paths.decisions: _snapshot_file(paths.decisions),
        paths.contracts: _snapshot_file(paths.contracts),
        paths.concept_state: _snapshot_file(paths.concept_state),
        paths.design_state: _snapshot_file(paths.design_state),
        paths.tech_state: _snapshot_file(paths.tech_state),
        paths.architecture_state: _snapshot_file(paths.architecture_state),
    }

    ts = now_iso()
    active_session = read_json(paths.active_session, _default_active_session(branch_name))
    active_session["branch"] = branch_name
    active_session["stage"] = normalized_stage
    if normalized_summary:
        active_session["active_goal"] = normalized_summary
    active_session["open_questions"] = _append_unique(
        active_session.get("open_questions", []),
        normalized_questions,
    )[:20]
    active_session["pending_actions"] = _append_unique(
        active_session.get("pending_actions", []),
        normalized_pending_actions,
    )[:20]
    active_session["current_hypotheses"] = _append_unique(
        active_session.get("current_hypotheses", []),
        concept_decision_summaries
        or design_decision_summaries
        or tech_decision_summaries
        or architecture_decision_summaries
        or normalized_decisions
        or concept_fact_summaries
        or design_fact_summaries
        or tech_fact_summaries
        or architecture_fact_summaries
        or normalized_facts,
    )[:20]
    active_session["last_checkpoint_at"] = ts
    active_session["updated_at"] = ts

    note_records = []
    if normalized_summary or normalized_questions or normalized_pending_actions:
        note_records.append(
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                normalized_summary or f"Captured stage update for {normalized_stage}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                record_type="stage_note",
                metadata={
                    "questions": normalized_questions,
                    "pendingActions": normalized_pending_actions,
                },
                ts=ts,
            )
        )

    concept_state = load_concept_state(paths.concept_state)
    design_state = load_design_state(paths.design_state)
    tech_state = load_tech_state(paths.tech_state)
    architecture_state = load_architecture_state(paths.architecture_state)
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

    fact_records = [
        make_record(
            branch_name,
            normalized_stage,
            "memory.capture",
            item,
            status=normalized_status,
            evidence=normalized_evidence,
            scope="project",
            semantic_kind="fact",
            record_type="fact",
            ts=ts,
        )
        for item in normalized_facts
    ]
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"System overview: {normalized_system_overview}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "systemOverview"},
                ts=ts,
            )
        ]
        if normalized_system_overview and normalized_stage == CONCEPT_STAGE
        else []
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Project name: {normalized_project_name}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "projectName"},
                ts=ts,
            )
        ]
        if normalized_project_name and normalized_stage == CONCEPT_STAGE
        else []
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                item,
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "audience"},
                ts=ts,
            )
            for item in normalized_audiences
        ]
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                item,
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "scenario"},
                ts=ts,
            )
            for item in normalized_scenarios
        ]
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                item,
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "painPoint"},
                ts=ts,
            )
            for item in normalized_pain_points
        ]
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                item,
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "assumption"},
                ts=ts,
            )
            for item in normalized_assumptions
        ]
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Design overview: {normalized_design_overview}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "designOverview"},
                ts=ts,
            )
        ]
        if normalized_design_overview and normalized_stage == DESIGN_STAGE
        else []
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                item,
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "platform"},
                ts=ts,
            )
            for item in normalized_platforms
        ]
        if normalized_stage == DESIGN_STAGE
        else []
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Project type: {normalized_project_type}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "projectType"},
                ts=ts,
            )
        ]
        if normalized_project_type and normalized_stage == TECH_STAGE
        else []
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Stack overview: {normalized_stack_overview}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "stackOverview"},
                ts=ts,
            )
        ]
        if normalized_stack_overview and normalized_stage == TECH_STAGE
        else []
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                item,
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "requirement"},
                ts=ts,
            )
            for item in normalized_requirements
        ]
        if normalized_stage == TECH_STAGE
        else []
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Architecture overview: {normalized_architecture_overview}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "architectureOverview"},
                ts=ts,
            )
        ]
        if normalized_architecture_overview and normalized_stage == ARCHITECTURE_STAGE
        else []
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                "Project structure: "
                f"{architecture_project_structure['strategy']} - {architecture_project_structure['rationale']}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "projectStructure", **architecture_project_structure},
                ts=ts,
            )
        ]
        if normalized_stage == ARCHITECTURE_STAGE and architecture_project_structure is not None
        else []
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Directory {item['path']}: {item['purpose']}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "directory", **item},
                ts=ts,
            )
            for item in architecture_directory_updates
        ]
        if normalized_stage == ARCHITECTURE_STAGE
        else []
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Entity {item['name']}: {item['description']}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "entity", **item},
                ts=ts,
            )
            for item in architecture_entity_updates
        ]
        if normalized_stage == ARCHITECTURE_STAGE
        else []
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Entity field {item['entity']}.{item['field']['name']}: {item['field']['type']} - {item['field']['description']}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "entityField", **item},
                ts=ts,
            )
            for item in architecture_entity_field_updates
        ]
        if normalized_stage == ARCHITECTURE_STAGE
        else []
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Integration {item['name']} ({item['kind']}): {item['purpose']}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "integration", **item},
                ts=ts,
            )
            for item in architecture_integration_updates
        ]
        if normalized_stage == ARCHITECTURE_STAGE
        else []
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                item,
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "codePrinciple"},
                ts=ts,
            )
            for item in normalized_code_principles
        ]
        if normalized_stage == ARCHITECTURE_STAGE
        else []
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                item,
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "securityNote"},
                ts=ts,
            )
            for item in normalized_security_notes
        ]
        if normalized_stage == ARCHITECTURE_STAGE
        else []
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                item,
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "performanceNote"},
                ts=ts,
            )
            for item in normalized_performance_notes
        ]
        if normalized_stage == ARCHITECTURE_STAGE
        else []
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                item,
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "preference"},
                ts=ts,
            )
            for item in normalized_preferences
        ]
        if normalized_stage == TECH_STAGE
        else []
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Zone {item['id']}: {item['title']} - {item['description']}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "zone", **item},
                ts=ts,
            )
            for item in design_zone_updates
        ]
        if normalized_stage == DESIGN_STAGE
        else []
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Screen {item['id']}: {item['title']} ({item['prototype']}) - {item['purpose']}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={
                    "slot": "screen",
                    "screenId": item["id"],
                    "title": item["title"],
                    "zone": item["zone"],
                    "prototype": item["prototype"],
                    "purpose": item["purpose"],
                },
                ts=ts,
            )
            for item in design_screen_updates
        ]
        if normalized_stage == DESIGN_STAGE
        else []
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Flow {item['id']}: {item['title']} - {item['goal']}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "flow", "flowId": item["id"], "title": item["title"], "goal": item["goal"]},
                ts=ts,
            )
            for item in design_flow_updates
        ]
        if normalized_stage == DESIGN_STAGE
        else []
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Flow step {item['flowId']}: {item['screenId']} -> {item['action']} -> {item['result']}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "flowStep", **item},
                ts=ts,
            )
            for item in design_flow_step_updates
        ]
        if normalized_stage == DESIGN_STAGE
        else []
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Screen data {item['screenId']} ({item['dataKind']}): {item['name']}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "screenData", **item},
                ts=ts,
            )
            for item in design_screen_data_updates
        ]
        if normalized_stage == DESIGN_STAGE
        else []
    )
    decision_records = [
        make_record(
            branch_name,
            normalized_stage,
            "memory.capture",
            item,
            status=normalized_status,
            evidence=normalized_evidence,
            scope="project",
            semantic_kind="decision",
            record_type="decision",
            ts=ts,
        )
        for item in normalized_decisions
    ]
    decision_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"{priority.upper()} feature: {feature['name']} - {feature['description']}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="decision",
                record_type="decision",
                metadata={"slot": "feature", "priority": priority, **feature},
                ts=ts,
            )
            for priority in ("p1", "p2", "p3")
            for feature in concept_feature_updates[priority]
        ]
    )
    decision_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Screen {item['screenId']} covers {item['priority'].upper()} feature {item['featureName']}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="decision",
                record_type="decision",
                metadata={"slot": "screenFeature", **item},
                ts=ts,
            )
            for item in design_screen_feature_links
        ]
        if normalized_stage == DESIGN_STAGE
        else []
    )
    decision_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Entity relationship {item['entity']} -> {item['relationship']['target']} ({item['relationship']['kind']}): {item['relationship']['description']}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="decision",
                record_type="decision",
                metadata={"slot": "entityRelationship", **item},
                ts=ts,
            )
            for item in architecture_entity_relationship_updates
        ]
        if normalized_stage == ARCHITECTURE_STAGE
        else []
    )
    decision_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Entity state {item['entity']}: {item['state']['name']} - {item['state']['description']}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="decision",
                record_type="decision",
                metadata={"slot": "entityState", **item},
                ts=ts,
            )
            for item in architecture_entity_state_updates
        ]
        if normalized_stage == ARCHITECTURE_STAGE
        else []
    )
    decision_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Endpoint {item['operationId']}: {item['method']} {item['path']} - {item['summary']}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="decision",
                record_type="decision",
                metadata={"slot": "endpoint", **item},
                ts=ts,
            )
            for item in architecture_endpoint_updates
        ]
        if normalized_stage == ARCHITECTURE_STAGE
        else []
    )
    decision_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Endpoint {item['operationId']} linked to screen {item['screenId']}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="decision",
                record_type="decision",
                metadata={"slot": "endpointScreen", **item},
                ts=ts,
            )
            for item in architecture_endpoint_screen_updates
        ]
        if normalized_stage == ARCHITECTURE_STAGE
        else []
    )
    decision_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Endpoint field {item['operationId']} {item['field']['section']} {item['field']['name']}: {item['field']['type']} - {item['field']['description']}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="decision",
                record_type="decision",
                metadata={"slot": "endpointField", **item},
                ts=ts,
            )
            for item in architecture_endpoint_field_updates
        ]
        if normalized_stage == ARCHITECTURE_STAGE
        else []
    )
    decision_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Pattern {item['name']}: {item['rationale']}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="decision",
                record_type="decision",
                metadata={"slot": "pattern", **item},
                ts=ts,
            )
            for item in architecture_pattern_updates
        ]
        if normalized_stage == ARCHITECTURE_STAGE
        else []
    )
    decision_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Stack component {item['slot']}: {item['name']} {item['version']} - {item['rationale']}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="decision",
                record_type="decision",
                metadata={"slot": "stackComponent", **item},
                ts=ts,
            )
            for item in tech_component_updates
        ]
        if normalized_stage == TECH_STAGE
        else []
    )
    decision_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Library {item['scope']}: {item['name']} {item['version']} - {item['purpose']}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="decision",
                record_type="decision",
                metadata={"slot": "library", **item},
                ts=ts,
            )
            for item in tech_library_updates
        ]
        if normalized_stage == TECH_STAGE
        else []
    )
    decision_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                "Code organization: "
                f"{tech_code_organization['repoStrategy']} / "
                f"{tech_code_organization['sourceLayout']} / "
                f"{tech_code_organization['modularity']} - "
                f"{tech_code_organization['rationale']}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="decision",
                record_type="decision",
                metadata={"slot": "codeOrganization", **tech_code_organization},
                ts=ts,
            )
        ]
        if normalized_stage == TECH_STAGE and tech_code_organization is not None
        else []
    )
    decision_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Rejected alternative for {item['slot']}: {item['option']} - {item['reasonRejected']}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="decision",
                record_type="decision",
                metadata={"slot": "alternative", **item},
                ts=ts,
            )
            for item in tech_alternative_updates
        ]
        if normalized_stage == TECH_STAGE
        else []
    )
    decision_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Navigation {item['from']} -> {item['to']} via {item['trigger']}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="decision",
                record_type="decision",
                metadata={"slot": "navigation", **item},
                ts=ts,
            )
            for item in design_navigation_updates
        ]
        if normalized_stage == DESIGN_STAGE
        else []
    )
    decision_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Alternative path for {item['flowId']}: {item['description']}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="decision",
                record_type="decision",
                metadata={"slot": "flowAlternative", **item},
                ts=ts,
            )
            for item in design_flow_alternative_updates
        ]
        if normalized_stage == DESIGN_STAGE
        else []
    )
    contract_records = [
        make_record(
            branch_name,
            normalized_stage,
            "memory.capture",
            item,
            status=normalized_status,
            evidence=normalized_evidence,
            scope="project",
            semantic_kind="contract",
            record_type="contract",
            ts=ts,
        )
        for item in normalized_contracts
    ]
    contract_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                item,
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="contract",
                record_type="contract",
                metadata={"slot": "constraint"},
                ts=ts,
            )
            for item in normalized_constraints
        ]
    )
    contract_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                item,
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="contract",
                record_type="contract",
                metadata={"slot": "platformConstraint"},
                ts=ts,
            )
            for item in normalized_platform_constraints
        ]
        if normalized_stage == DESIGN_STAGE
        else []
    )
    contract_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                item,
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="contract",
                record_type="contract",
                metadata={"slot": "techConstraint"},
                ts=ts,
            )
            for item in normalized_tech_constraints
        ]
        if normalized_stage == TECH_STAGE
        else []
    )
    contract_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Endpoint error {item['operationId']} {item['error']['status']} {item['error']['code']}: {item['error']['description']}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="contract",
                record_type="contract",
                metadata={"slot": "endpointError", **item},
                ts=ts,
            )
            for item in architecture_endpoint_error_updates
        ]
        if normalized_stage == ARCHITECTURE_STAGE
        else []
    )

    try:
        if normalized_stage == CONCEPT_STAGE:
            save_concept_state(paths.concept_state, concept_state)
        elif normalized_stage == DESIGN_STAGE:
            save_design_state(paths.design_state, design_state)
        elif normalized_stage == TECH_STAGE:
            save_tech_state(paths.tech_state, tech_state)
        elif normalized_stage == ARCHITECTURE_STAGE:
            save_architecture_state(paths.architecture_state, architecture_state)
        write_json(paths.active_session, active_session)
        append_jsonl(paths.decision_log, note_records)
        append_jsonl(paths.facts, fact_records)
        append_jsonl(paths.decisions, decision_records)
        append_jsonl(paths.contracts, contract_records)

        generated = consolidate_branch_memory(project_path, branch_name)
        ensure_memory_layout(project_path, branch_name)
        validation_errors = validate_branch_memory(project_path, branch_name)
        if normalized_stage == DESIGN_STAGE:
            validation_errors = _filter_non_blocking_design_validation_errors(validation_errors)
        if normalized_stage == ARCHITECTURE_STAGE:
            validation_errors = _filter_non_blocking_architecture_validation_errors(validation_errors)
        if validation_errors:
            raise ValueError("; ".join(validation_errors))
    except Exception as exc:
        for path, content in snapshots.items():
            _restore_file(path, content)
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": [str(exc)],
        }

    return {
        "accepted": True,
        "branch": branch_name,
        "stage": normalized_stage,
        "status": normalized_status,
        "written": {
            "notes": len(note_records),
            "facts": len(fact_records),
            "decisions": len(decision_records),
            "contracts": len(contract_records),
            "questions": len(normalized_questions),
            "pending_actions": len(normalized_pending_actions),
        },
        "generated_views": [str(path.relative_to(project_path)) for path in generated],
    }
