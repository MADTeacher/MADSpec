from __future__ import annotations

from typing import Any

from ..stages.architecture.state import ARCHITECTURE_STAGE
from ..stages.concept.state import CONCEPT_STAGE
from ..stages.design.state import DESIGN_STAGE
from ..shared.records import make_record
from ..stages.tech.state import TECH_STAGE


def build_note_records(
    *,
    branch_name: str,
    normalized_stage: str,
    normalized_status: str,
    normalized_summary: str,
    normalized_questions: list[str],
    normalized_pending_actions: list[str],
    normalized_evidence: list[str],
    ts: str,
) -> list[dict[str, Any]]:
    if not (normalized_summary or normalized_questions or normalized_pending_actions):
        return []
    return [
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
    ]


def build_fact_records(
    *,
    branch_name: str,
    normalized_stage: str,
    normalized_status: str,
    normalized_evidence: list[str],
    normalized_facts: list[str],
    normalized_system_overview: str,
    normalized_project_name: str,
    normalized_audiences: list[str],
    normalized_scenarios: list[str],
    normalized_pain_points: list[str],
    normalized_assumptions: list[str],
    normalized_design_overview: str,
    normalized_platforms: list[str],
    normalized_project_type: str,
    normalized_stack_overview: str,
    normalized_requirements: list[str],
    normalized_architecture_overview: str,
    architecture_project_structure: dict[str, str] | None,
    architecture_directory_updates: list[dict[str, str]],
    architecture_entity_updates: list[dict[str, str]],
    architecture_entity_field_updates: list[dict[str, Any]],
    architecture_integration_updates: list[dict[str, Any]],
    normalized_code_principles: list[str],
    normalized_security_notes: list[str],
    normalized_performance_notes: list[str],
    normalized_preferences: list[str],
    design_zone_updates: list[dict[str, str]],
    design_screen_updates: list[dict[str, Any]],
    design_flow_updates: list[dict[str, Any]],
    design_flow_step_updates: list[dict[str, str]],
    design_screen_data_updates: list[dict[str, str]],
    ts: str,
) -> list[dict[str, Any]]:
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
                f"Entity field {item['entity']}.{item['field']['name']}: "
                f"{item['field']['type']} - {item['field']['description']}",
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
    return fact_records


def build_decision_records(
    *,
    branch_name: str,
    normalized_stage: str,
    normalized_status: str,
    normalized_evidence: list[str],
    normalized_decisions: list[str],
    concept_feature_updates: dict[str, list[dict[str, str]]],
    design_screen_feature_links: list[dict[str, str]],
    architecture_entity_relationship_updates: list[dict[str, Any]],
    architecture_entity_state_updates: list[dict[str, Any]],
    architecture_endpoint_updates: list[dict[str, Any]],
    architecture_endpoint_screen_updates: list[dict[str, str]],
    architecture_endpoint_field_updates: list[dict[str, Any]],
    architecture_pattern_updates: list[dict[str, str]],
    tech_component_updates: list[dict[str, str]],
    tech_library_updates: list[dict[str, str]],
    tech_code_organization: dict[str, str] | None,
    tech_alternative_updates: list[dict[str, str]],
    design_navigation_updates: list[dict[str, str]],
    design_flow_alternative_updates: list[dict[str, str]],
    ts: str,
) -> list[dict[str, Any]]:
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
                f"Entity relationship {item['entity']} -> {item['relationship']['target']} "
                f"({item['relationship']['kind']}): {item['relationship']['description']}",
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
                f"Endpoint field {item['operationId']} {item['field']['section']} {item['field']['name']}: "
                f"{item['field']['type']} - {item['field']['description']}",
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
    return decision_records


def build_contract_records(
    *,
    branch_name: str,
    normalized_stage: str,
    normalized_status: str,
    normalized_evidence: list[str],
    normalized_contracts: list[str],
    normalized_constraints: list[str],
    normalized_platform_constraints: list[str],
    normalized_tech_constraints: list[str],
    architecture_endpoint_error_updates: list[dict[str, Any]],
    ts: str,
) -> list[dict[str, Any]]:
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
                f"Endpoint error {item['operationId']} {item['error']['status']} "
                f"{item['error']['code']}: {item['error']['description']}",
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
    return contract_records
