from __future__ import annotations

from pathlib import Path
from typing import Any

from ..stages.architecture.state import (
    ARCHITECTURE_STAGE,
    load_architecture_state,
    save_architecture_state,
)
from ..stages.concept.state import (
    CONCEPT_STAGE,
    load_concept_state,
    save_concept_state,
)
from ..stages.design.state import (
    DESIGN_STAGE,
    load_design_state,
    save_design_state,
)
from ..stages.tech.state import (
    TECH_STAGE,
    load_tech_state,
    save_tech_state,
)
from .parsers import (
    parse_architecture_capture,
    parse_concept_capture,
    parse_design_capture,
    parse_tech_capture,
    validate_capture_scope,
)
from .records import (
    build_contract_records,
    build_decision_records,
    build_fact_records,
    build_note_records,
)
from .shared import append_unique, normalize_text_list, restore_file, snapshot_file
from .updates import (
    apply_stage_state_update,
    build_stage_summary_bundles,
    has_capture_payload,
)
from ..shared.storage import (
    _default_active_session,
    append_jsonl,
    ensure_memory_layout,
    get_memory_paths,
    now_iso,
    read_json,
    write_json,
)
from ..shared.validation import validate_branch_memory
from ..views import consolidate_branch_memory

CAPTURE_STAGES = {
    "mvp.concept",
    "mvp.design",
    "mvp.tech",
    "mvp.architecture",
    "review",
    "security",
}


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
    normalized_facts = normalize_text_list(facts)
    normalized_decisions = normalize_text_list(decisions)
    normalized_contracts = normalize_text_list(contracts)
    normalized_evidence = normalize_text_list(evidence)
    normalized_questions = normalize_text_list(questions)
    normalized_pending_actions = normalize_text_list(pending_actions)
    normalized_audiences = normalize_text_list(audiences)
    normalized_scenarios = normalize_text_list(scenarios)
    normalized_pain_points = normalize_text_list(pain_points)
    normalized_constraints = normalize_text_list(constraints)
    normalized_assumptions = normalize_text_list(assumptions)
    normalized_next_actions = normalize_text_list(next_actions)
    normalized_project_name = (project_name or "").strip()
    normalized_system_overview = (system_overview or "").strip()
    normalized_design_overview = (design_overview or "").strip()
    normalized_platforms = normalize_text_list(platforms)
    normalized_platform_constraints = normalize_text_list(platform_constraints)
    normalized_stack_overview = (stack_overview or "").strip()
    normalized_project_type = (project_type or "").strip()
    normalized_requirements = normalize_text_list(requirements)
    normalized_preferences = normalize_text_list(preferences)
    normalized_tech_constraints = normalize_text_list(tech_constraints)
    normalized_architecture_overview = (architecture_overview or "").strip()
    normalized_code_principles = normalize_text_list(code_principles)
    normalized_security_notes = normalize_text_list(security_notes)
    normalized_performance_notes = normalize_text_list(performance_notes)

    concept_parse = parse_concept_capture(
        feature_p1=feature_p1,
        feature_p2=feature_p2,
        feature_p3=feature_p3,
    )
    concept_feature_updates = concept_parse.feature_updates
    concept_feature_errors = concept_parse.errors

    design_parse = parse_design_capture(
        zones=zones,
        screens=screens,
        screen_features=screen_features,
        flows=flows,
        flow_steps=flow_steps,
        flow_alternatives=flow_alternatives,
        navigation=navigation,
        screen_data=screen_data,
    )
    design_zone_updates = design_parse.zone_updates
    design_screen_updates = design_parse.screen_updates
    design_screen_feature_links = design_parse.screen_feature_links
    design_flow_updates = design_parse.flow_updates
    design_flow_step_updates = design_parse.flow_step_updates
    design_flow_alternative_updates = design_parse.flow_alternative_updates
    design_navigation_updates = design_parse.navigation_updates
    design_screen_data_updates = design_parse.screen_data_updates
    design_errors = design_parse.errors

    tech_parse = parse_tech_capture(
        stack_components=stack_components,
        libraries=libraries,
        alternatives=alternatives,
        code_organization=code_organization,
    )
    tech_component_updates = tech_parse.component_updates
    tech_library_updates = tech_parse.library_updates
    tech_alternative_updates = tech_parse.alternative_updates
    tech_code_organization = tech_parse.code_organization
    tech_errors = tech_parse.errors

    architecture_parse = parse_architecture_capture(
        project_structure=project_structure,
        directories=directories,
        entities=entities,
        entity_fields=entity_fields,
        entity_relationships=entity_relationships,
        entity_states=entity_states,
        endpoints=endpoints,
        endpoint_screens=endpoint_screens,
        endpoint_fields=endpoint_fields,
        endpoint_errors=endpoint_errors,
        integrations=integrations,
        architecture_patterns=architecture_patterns,
    )
    architecture_project_structure = architecture_parse.project_structure
    architecture_directory_updates = architecture_parse.directory_updates
    architecture_entity_updates = architecture_parse.entity_updates
    architecture_entity_field_updates = architecture_parse.entity_field_updates
    architecture_entity_relationship_updates = architecture_parse.entity_relationship_updates
    architecture_entity_state_updates = architecture_parse.entity_state_updates
    architecture_endpoint_updates = architecture_parse.endpoint_updates
    architecture_endpoint_screen_updates = architecture_parse.endpoint_screen_updates
    architecture_endpoint_field_updates = architecture_parse.endpoint_field_updates
    architecture_endpoint_error_updates = architecture_parse.endpoint_error_updates
    architecture_integration_updates = architecture_parse.integration_updates
    architecture_pattern_updates = architecture_parse.pattern_updates
    architecture_errors = architecture_parse.errors
    scope_errors = validate_capture_scope(
        normalized_stage=normalized_stage,
        normalized_project_name=normalized_project_name,
        normalized_system_overview=normalized_system_overview,
        normalized_audiences=normalized_audiences,
        normalized_scenarios=normalized_scenarios,
        normalized_pain_points=normalized_pain_points,
        concept_feature_updates=concept_feature_updates,
        normalized_constraints=normalized_constraints,
        normalized_assumptions=normalized_assumptions,
        normalized_design_overview=normalized_design_overview,
        normalized_platforms=normalized_platforms,
        design_zone_updates=design_zone_updates,
        design_screen_updates=design_screen_updates,
        design_screen_feature_links=design_screen_feature_links,
        design_flow_updates=design_flow_updates,
        design_flow_step_updates=design_flow_step_updates,
        design_flow_alternative_updates=design_flow_alternative_updates,
        design_navigation_updates=design_navigation_updates,
        normalized_platform_constraints=normalized_platform_constraints,
        design_screen_data_updates=design_screen_data_updates,
        normalized_stack_overview=normalized_stack_overview,
        normalized_project_type=normalized_project_type,
        normalized_requirements=normalized_requirements,
        normalized_preferences=normalized_preferences,
        normalized_tech_constraints=normalized_tech_constraints,
        tech_component_updates=tech_component_updates,
        tech_library_updates=tech_library_updates,
        tech_code_organization=tech_code_organization,
        tech_alternative_updates=tech_alternative_updates,
        normalized_architecture_overview=normalized_architecture_overview,
        architecture_project_structure=architecture_project_structure,
        architecture_directory_updates=architecture_directory_updates,
        architecture_entity_updates=architecture_entity_updates,
        architecture_entity_field_updates=architecture_entity_field_updates,
        architecture_entity_relationship_updates=architecture_entity_relationship_updates,
        architecture_entity_state_updates=architecture_entity_state_updates,
        architecture_endpoint_updates=architecture_endpoint_updates,
        architecture_endpoint_screen_updates=architecture_endpoint_screen_updates,
        architecture_endpoint_field_updates=architecture_endpoint_field_updates,
        architecture_endpoint_error_updates=architecture_endpoint_error_updates,
        architecture_integration_updates=architecture_integration_updates,
        normalized_code_principles=normalized_code_principles,
        architecture_pattern_updates=architecture_pattern_updates,
        normalized_security_notes=normalized_security_notes,
        normalized_performance_notes=normalized_performance_notes,
        normalized_next_actions=normalized_next_actions,
    )
    if scope_errors:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": scope_errors,
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
    normalized_pending_actions = append_unique(normalized_pending_actions, normalized_next_actions)
    bundles = build_stage_summary_bundles(
        normalized_project_name=normalized_project_name,
        normalized_system_overview=normalized_system_overview,
        normalized_audiences=normalized_audiences,
        normalized_scenarios=normalized_scenarios,
        normalized_pain_points=normalized_pain_points,
        normalized_assumptions=normalized_assumptions,
        concept_feature_updates=concept_feature_updates,
        normalized_constraints=normalized_constraints,
        normalized_design_overview=normalized_design_overview,
        normalized_platforms=normalized_platforms,
        design_zone_updates=design_zone_updates,
        design_screen_updates=design_screen_updates,
        design_flow_updates=design_flow_updates,
        design_flow_step_updates=design_flow_step_updates,
        design_screen_data_updates=design_screen_data_updates,
        design_screen_feature_links=design_screen_feature_links,
        design_navigation_updates=design_navigation_updates,
        design_flow_alternative_updates=design_flow_alternative_updates,
        normalized_platform_constraints=normalized_platform_constraints,
        normalized_project_type=normalized_project_type,
        normalized_stack_overview=normalized_stack_overview,
        normalized_requirements=normalized_requirements,
        normalized_preferences=normalized_preferences,
        tech_component_updates=tech_component_updates,
        tech_library_updates=tech_library_updates,
        tech_code_organization=tech_code_organization,
        tech_alternative_updates=tech_alternative_updates,
        normalized_tech_constraints=normalized_tech_constraints,
        normalized_architecture_overview=normalized_architecture_overview,
        architecture_project_structure=architecture_project_structure,
        architecture_directory_updates=architecture_directory_updates,
        architecture_entity_updates=architecture_entity_updates,
        architecture_entity_field_updates=architecture_entity_field_updates,
        architecture_integration_updates=architecture_integration_updates,
        normalized_code_principles=normalized_code_principles,
        normalized_security_notes=normalized_security_notes,
        normalized_performance_notes=normalized_performance_notes,
        architecture_entity_relationship_updates=architecture_entity_relationship_updates,
        architecture_entity_state_updates=architecture_entity_state_updates,
        architecture_endpoint_updates=architecture_endpoint_updates,
        architecture_endpoint_screen_updates=architecture_endpoint_screen_updates,
        architecture_endpoint_field_updates=architecture_endpoint_field_updates,
        architecture_pattern_updates=architecture_pattern_updates,
        architecture_endpoint_error_updates=architecture_endpoint_error_updates,
    )
    if not has_capture_payload(
        normalized_summary=normalized_summary,
        normalized_facts=normalized_facts,
        normalized_decisions=normalized_decisions,
        normalized_contracts=normalized_contracts,
        normalized_questions=normalized_questions,
        normalized_pending_actions=normalized_pending_actions,
        bundles=bundles,
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
        paths.active_session: snapshot_file(paths.active_session),
        paths.decision_log: snapshot_file(paths.decision_log),
        paths.facts: snapshot_file(paths.facts),
        paths.decisions: snapshot_file(paths.decisions),
        paths.contracts: snapshot_file(paths.contracts),
        paths.concept_state: snapshot_file(paths.concept_state),
        paths.design_state: snapshot_file(paths.design_state),
        paths.tech_state: snapshot_file(paths.tech_state),
        paths.architecture_state: snapshot_file(paths.architecture_state),
    }

    ts = now_iso()
    active_session = read_json(paths.active_session, _default_active_session(branch_name))
    active_session["branch"] = branch_name
    active_session["stage"] = normalized_stage
    if normalized_summary:
        active_session["active_goal"] = normalized_summary
    active_session["open_questions"] = append_unique(
        active_session.get("open_questions", []),
        normalized_questions,
    )[:20]
    active_session["pending_actions"] = append_unique(
        active_session.get("pending_actions", []),
        normalized_pending_actions,
    )[:20]
    active_session["current_hypotheses"] = append_unique(
        active_session.get("current_hypotheses", []),
        bundles.concept_decision_summaries
        or bundles.design_decision_summaries
        or bundles.tech_decision_summaries
        or bundles.architecture_decision_summaries
        or normalized_decisions
        or bundles.concept_fact_summaries
        or bundles.design_fact_summaries
        or bundles.tech_fact_summaries
        or bundles.architecture_fact_summaries
        or normalized_facts,
    )[:20]
    active_session["last_checkpoint_at"] = ts
    active_session["updated_at"] = ts

    note_records = build_note_records(
        branch_name=branch_name,
        normalized_stage=normalized_stage,
        normalized_status=normalized_status,
        normalized_summary=normalized_summary,
        normalized_questions=normalized_questions,
        normalized_pending_actions=normalized_pending_actions,
        normalized_evidence=normalized_evidence,
        ts=ts,
    )

    concept_state = load_concept_state(paths.concept_state)
    design_state = load_design_state(paths.design_state)
    tech_state = load_tech_state(paths.tech_state)
    architecture_state = load_architecture_state(paths.architecture_state)
    concept_state, design_state, tech_state, architecture_state = apply_stage_state_update(
        normalized_stage=normalized_stage,
        concept_state=concept_state,
        design_state=design_state,
        tech_state=tech_state,
        architecture_state=architecture_state,
        normalized_project_name=normalized_project_name,
        normalized_system_overview=normalized_system_overview,
        normalized_audiences=normalized_audiences,
        normalized_scenarios=normalized_scenarios,
        normalized_pain_points=normalized_pain_points,
        normalized_assumptions=normalized_assumptions,
        concept_feature_updates=concept_feature_updates,
        normalized_constraints=normalized_constraints,
        normalized_design_overview=normalized_design_overview,
        normalized_platforms=normalized_platforms,
        design_zone_updates=design_zone_updates,
        design_screen_updates=design_screen_updates,
        design_screen_feature_links=design_screen_feature_links,
        design_flow_updates=design_flow_updates,
        design_flow_step_updates=design_flow_step_updates,
        design_flow_alternative_updates=design_flow_alternative_updates,
        design_navigation_updates=design_navigation_updates,
        normalized_platform_constraints=normalized_platform_constraints,
        design_screen_data_updates=design_screen_data_updates,
        normalized_project_type=normalized_project_type,
        normalized_stack_overview=normalized_stack_overview,
        normalized_requirements=normalized_requirements,
        normalized_preferences=normalized_preferences,
        normalized_tech_constraints=normalized_tech_constraints,
        tech_component_updates=tech_component_updates,
        tech_library_updates=tech_library_updates,
        tech_code_organization=tech_code_organization,
        tech_alternative_updates=tech_alternative_updates,
        normalized_architecture_overview=normalized_architecture_overview,
        architecture_project_structure=architecture_project_structure,
        architecture_directory_updates=architecture_directory_updates,
        architecture_entity_updates=architecture_entity_updates,
        architecture_entity_field_updates=architecture_entity_field_updates,
        architecture_entity_relationship_updates=architecture_entity_relationship_updates,
        architecture_entity_state_updates=architecture_entity_state_updates,
        architecture_endpoint_updates=architecture_endpoint_updates,
        architecture_endpoint_screen_updates=architecture_endpoint_screen_updates,
        architecture_endpoint_field_updates=architecture_endpoint_field_updates,
        architecture_endpoint_error_updates=architecture_endpoint_error_updates,
        architecture_integration_updates=architecture_integration_updates,
        normalized_code_principles=normalized_code_principles,
        architecture_pattern_updates=architecture_pattern_updates,
        normalized_security_notes=normalized_security_notes,
        normalized_performance_notes=normalized_performance_notes,
        normalized_next_actions=normalized_next_actions,
    )

    fact_records = build_fact_records(
        branch_name=branch_name,
        normalized_stage=normalized_stage,
        normalized_status=normalized_status,
        normalized_evidence=normalized_evidence,
        normalized_facts=normalized_facts,
        normalized_system_overview=normalized_system_overview,
        normalized_project_name=normalized_project_name,
        normalized_audiences=normalized_audiences,
        normalized_scenarios=normalized_scenarios,
        normalized_pain_points=normalized_pain_points,
        normalized_assumptions=normalized_assumptions,
        normalized_design_overview=normalized_design_overview,
        normalized_platforms=normalized_platforms,
        normalized_project_type=normalized_project_type,
        normalized_stack_overview=normalized_stack_overview,
        normalized_requirements=normalized_requirements,
        normalized_architecture_overview=normalized_architecture_overview,
        architecture_project_structure=architecture_project_structure,
        architecture_directory_updates=architecture_directory_updates,
        architecture_entity_updates=architecture_entity_updates,
        architecture_entity_field_updates=architecture_entity_field_updates,
        architecture_integration_updates=architecture_integration_updates,
        normalized_code_principles=normalized_code_principles,
        normalized_security_notes=normalized_security_notes,
        normalized_performance_notes=normalized_performance_notes,
        normalized_preferences=normalized_preferences,
        design_zone_updates=design_zone_updates,
        design_screen_updates=design_screen_updates,
        design_flow_updates=design_flow_updates,
        design_flow_step_updates=design_flow_step_updates,
        design_screen_data_updates=design_screen_data_updates,
        ts=ts,
    )
    decision_records = build_decision_records(
        branch_name=branch_name,
        normalized_stage=normalized_stage,
        normalized_status=normalized_status,
        normalized_evidence=normalized_evidence,
        normalized_decisions=normalized_decisions,
        concept_feature_updates=concept_feature_updates,
        design_screen_feature_links=design_screen_feature_links,
        architecture_entity_relationship_updates=architecture_entity_relationship_updates,
        architecture_entity_state_updates=architecture_entity_state_updates,
        architecture_endpoint_updates=architecture_endpoint_updates,
        architecture_endpoint_screen_updates=architecture_endpoint_screen_updates,
        architecture_endpoint_field_updates=architecture_endpoint_field_updates,
        architecture_pattern_updates=architecture_pattern_updates,
        tech_component_updates=tech_component_updates,
        tech_library_updates=tech_library_updates,
        tech_code_organization=tech_code_organization,
        tech_alternative_updates=tech_alternative_updates,
        design_navigation_updates=design_navigation_updates,
        design_flow_alternative_updates=design_flow_alternative_updates,
        ts=ts,
    )
    contract_records = build_contract_records(
        branch_name=branch_name,
        normalized_stage=normalized_stage,
        normalized_status=normalized_status,
        normalized_evidence=normalized_evidence,
        normalized_contracts=normalized_contracts,
        normalized_constraints=normalized_constraints,
        normalized_platform_constraints=normalized_platform_constraints,
        normalized_tech_constraints=normalized_tech_constraints,
        architecture_endpoint_error_updates=architecture_endpoint_error_updates,
        ts=ts,
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
            restore_file(path, content)
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
