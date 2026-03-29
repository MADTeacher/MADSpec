from __future__ import annotations

from ..stages.architecture.state import ARCHITECTURE_STAGE
from ..stages.design.state import DESIGN_STAGE
from ..stages.plan.state import PLAN_STAGE
from ..stages.tech.state import TECH_STAGE
from .record_context import RecordBuildContext, build_semantic_record


def build_decision_records(context: RecordBuildContext) -> list[dict[str, Any]]:
    inputs = context.inputs
    parsed = context.parsed
    decision_records = [
        build_semantic_record(
            context,
            item,
            semantic_kind="decision",
        )
        for item in inputs.decisions
    ]
    if inputs.stage == PLAN_STAGE:
        decision_records.extend(
            build_semantic_record(
                context,
                item,
                semantic_kind="decision",
                metadata={"slot": "planningPrinciple"},
            )
            for item in inputs.planning_principles
        )
    decision_records.extend(
        build_semantic_record(
            context,
            f"{priority.upper()} feature: {feature['name']} - {feature['description']}",
            semantic_kind="decision",
            metadata={"slot": "feature", "priority": priority, **feature},
        )
        for priority in ("p1", "p2", "p3")
        for feature in parsed.concept_feature_updates[priority]
    )
    if inputs.stage == DESIGN_STAGE:
        decision_records.extend(
            build_semantic_record(
                context,
                f"Screen {item['screenId']} covers {item['priority'].upper()} feature {item['featureName']}",
                semantic_kind="decision",
                metadata={"slot": "screenFeature", **item},
            )
            for item in parsed.design_screen_feature_links
        )
        decision_records.extend(
            build_semantic_record(
                context,
                f"Navigation {item['from']} -> {item['to']} via {item['trigger']}",
                semantic_kind="decision",
                metadata={"slot": "navigation", **item},
            )
            for item in parsed.design_navigation_updates
        )
        decision_records.extend(
            build_semantic_record(
                context,
                f"Alternative path for {item['flowId']}: {item['description']}",
                semantic_kind="decision",
                metadata={"slot": "flowAlternative", **item},
            )
            for item in parsed.design_flow_alternative_updates
        )
    if inputs.stage == ARCHITECTURE_STAGE:
        decision_records.extend(
            build_semantic_record(
                context,
                f"Entity relationship {item['entity']} -> {item['relationship']['target']} "
                f"({item['relationship']['kind']}): {item['relationship']['description']}",
                semantic_kind="decision",
                metadata={"slot": "entityRelationship", **item},
            )
            for item in parsed.architecture_entity_relationship_updates
        )
        decision_records.extend(
            build_semantic_record(
                context,
                f"Entity state {item['entity']}: {item['state']['name']} - {item['state']['description']}",
                semantic_kind="decision",
                metadata={"slot": "entityState", **item},
            )
            for item in parsed.architecture_entity_state_updates
        )
        decision_records.extend(
            build_semantic_record(
                context,
                f"Endpoint {item['operationId']}: {item['method']} {item['path']} - {item['summary']}",
                semantic_kind="decision",
                metadata={"slot": "endpoint", **item},
            )
            for item in parsed.architecture_endpoint_updates
        )
        decision_records.extend(
            build_semantic_record(
                context,
                f"Endpoint {item['operationId']} linked to screen {item['screenId']}",
                semantic_kind="decision",
                metadata={"slot": "endpointScreen", **item},
            )
            for item in parsed.architecture_endpoint_screen_updates
        )
        decision_records.extend(
            build_semantic_record(
                context,
                f"Endpoint field {item['operationId']} {item['field']['section']} {item['field']['name']}: "
                f"{item['field']['type']} - {item['field']['description']}",
                semantic_kind="decision",
                metadata={"slot": "endpointField", **item},
            )
            for item in parsed.architecture_endpoint_field_updates
        )
        decision_records.extend(
            build_semantic_record(
                context,
                f"Pattern {item['name']}: {item['rationale']}",
                semantic_kind="decision",
                metadata={"slot": "pattern", **item},
            )
            for item in parsed.architecture_pattern_updates
        )
    if inputs.stage == TECH_STAGE:
        decision_records.extend(
            build_semantic_record(
                context,
                f"Stack component {item['slot']}: {item['name']} {item['version']} - {item['rationale']}",
                semantic_kind="decision",
                metadata={"slot": "stackComponent", **item},
            )
            for item in parsed.tech_component_updates
        )
        decision_records.extend(
            build_semantic_record(
                context,
                f"Library {item['scope']}: {item['name']} {item['version']} - {item['purpose']}",
                semantic_kind="decision",
                metadata={"slot": "library", **item},
            )
            for item in parsed.tech_library_updates
        )
        if parsed.tech_code_organization is not None:
            decision_records.append(
                build_semantic_record(
                    context,
                    "Code organization: "
                    f"{parsed.tech_code_organization['repoStrategy']} / "
                    f"{parsed.tech_code_organization['sourceLayout']} / "
                    f"{parsed.tech_code_organization['modularity']} - "
                    f"{parsed.tech_code_organization['rationale']}",
                    semantic_kind="decision",
                    metadata={"slot": "codeOrganization", **parsed.tech_code_organization},
                )
            )
        decision_records.extend(
            build_semantic_record(
                context,
                f"Rejected alternative for {item['slot']}: {item['option']} - {item['reasonRejected']}",
                semantic_kind="decision",
                metadata={"slot": "alternative", **item},
            )
            for item in parsed.tech_alternative_updates
        )
    return decision_records
