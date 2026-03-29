from __future__ import annotations

from ..stages.architecture.state import ARCHITECTURE_STAGE
from ..stages.concept.state import CONCEPT_STAGE
from ..stages.design.state import DESIGN_STAGE
from ..stages.plan.state import PLAN_STAGE
from ..stages.tech.state import TECH_STAGE
from .record_context import RecordBuildContext, build_semantic_record


def build_fact_records(context: RecordBuildContext) -> list[dict[str, Any]]:
    inputs = context.inputs
    parsed = context.parsed
    fact_records = [
        build_semantic_record(
            context,
            item,
            semantic_kind="fact",
        )
        for item in inputs.facts
    ]
    if inputs.plan_overview and inputs.stage == PLAN_STAGE:
        fact_records.append(
            build_semantic_record(
                context,
                f"Plan overview: {inputs.plan_overview}",
                semantic_kind="fact",
                metadata={"slot": "planOverview"},
            )
        )
    if inputs.system_overview and inputs.stage == CONCEPT_STAGE:
        fact_records.append(
            build_semantic_record(
                context,
                f"System overview: {inputs.system_overview}",
                semantic_kind="fact",
                metadata={"slot": "systemOverview"},
            )
        )
    if inputs.project_name and inputs.stage == CONCEPT_STAGE:
        fact_records.append(
            build_semantic_record(
                context,
                f"Project name: {inputs.project_name}",
                semantic_kind="fact",
                metadata={"slot": "projectName"},
            )
        )
    fact_records.extend(_slot_records(context, inputs.audiences, slot="audience"))
    fact_records.extend(_slot_records(context, inputs.scenarios, slot="scenario"))
    fact_records.extend(_slot_records(context, inputs.pain_points, slot="painPoint"))
    fact_records.extend(_slot_records(context, inputs.assumptions, slot="assumption"))
    if inputs.design_overview and inputs.stage == DESIGN_STAGE:
        fact_records.append(
            build_semantic_record(
                context,
                f"Design overview: {inputs.design_overview}",
                semantic_kind="fact",
                metadata={"slot": "designOverview"},
            )
        )
    if inputs.stage == DESIGN_STAGE:
        fact_records.extend(_slot_records(context, inputs.platforms, slot="platform"))
    if inputs.project_type and inputs.stage == TECH_STAGE:
        fact_records.append(
            build_semantic_record(
                context,
                f"Project type: {inputs.project_type}",
                semantic_kind="fact",
                metadata={"slot": "projectType"},
            )
        )
    if inputs.stack_overview and inputs.stage == TECH_STAGE:
        fact_records.append(
            build_semantic_record(
                context,
                f"Stack overview: {inputs.stack_overview}",
                semantic_kind="fact",
                metadata={"slot": "stackOverview"},
            )
        )
    if inputs.stage == TECH_STAGE:
        fact_records.extend(_slot_records(context, inputs.requirements, slot="requirement"))
    if inputs.architecture_overview and inputs.stage == ARCHITECTURE_STAGE:
        fact_records.append(
            build_semantic_record(
                context,
                f"Architecture overview: {inputs.architecture_overview}",
                semantic_kind="fact",
                metadata={"slot": "architectureOverview"},
            )
        )
    if inputs.stage == ARCHITECTURE_STAGE and parsed.architecture_project_structure is not None:
        fact_records.append(
            build_semantic_record(
                context,
                "Project structure: "
                f"{parsed.architecture_project_structure['strategy']} - "
                f"{parsed.architecture_project_structure['rationale']}",
                semantic_kind="fact",
                metadata={"slot": "projectStructure", **parsed.architecture_project_structure},
            )
        )
    if inputs.stage == ARCHITECTURE_STAGE:
        fact_records.extend(
            build_semantic_record(
                context,
                f"Directory {item['path']}: {item['purpose']}",
                semantic_kind="fact",
                metadata={"slot": "directory", **item},
            )
            for item in parsed.architecture_directory_updates
        )
        fact_records.extend(
            build_semantic_record(
                context,
                f"Entity {item['name']}: {item['description']}",
                semantic_kind="fact",
                metadata={"slot": "entity", **item},
            )
            for item in parsed.architecture_entity_updates
        )
        fact_records.extend(
            build_semantic_record(
                context,
                f"Entity field {item['entity']}.{item['field']['name']}: "
                f"{item['field']['type']} - {item['field']['description']}",
                semantic_kind="fact",
                metadata={"slot": "entityField", **item},
            )
            for item in parsed.architecture_entity_field_updates
        )
        fact_records.extend(
            build_semantic_record(
                context,
                f"Integration {item['name']} ({item['kind']}): {item['purpose']}",
                semantic_kind="fact",
                metadata={"slot": "integration", **item},
            )
            for item in parsed.architecture_integration_updates
        )
        fact_records.extend(_slot_records(context, inputs.code_principles, slot="codePrinciple"))
        fact_records.extend(_slot_records(context, inputs.security_notes, slot="securityNote"))
        fact_records.extend(_slot_records(context, inputs.performance_notes, slot="performanceNote"))
    if inputs.stage == TECH_STAGE:
        fact_records.extend(_slot_records(context, inputs.preferences, slot="preference"))
    if inputs.stage == DESIGN_STAGE:
        fact_records.extend(
            build_semantic_record(
                context,
                f"Zone {item['id']}: {item['title']} - {item['description']}",
                semantic_kind="fact",
                metadata={"slot": "zone", **item},
            )
            for item in parsed.design_zone_updates
        )
        fact_records.extend(
            build_semantic_record(
                context,
                f"Screen {item['id']}: {item['title']} ({item['prototype']}) - {item['purpose']}",
                semantic_kind="fact",
                metadata={
                    "slot": "screen",
                    "screenId": item["id"],
                    "title": item["title"],
                    "zone": item["zone"],
                    "prototype": item["prototype"],
                    "purpose": item["purpose"],
                },
            )
            for item in parsed.design_screen_updates
        )
        fact_records.extend(
            build_semantic_record(
                context,
                f"Flow {item['id']}: {item['title']} - {item['goal']}",
                semantic_kind="fact",
                metadata={"slot": "flow", "flowId": item["id"], "title": item["title"], "goal": item["goal"]},
            )
            for item in parsed.design_flow_updates
        )
        fact_records.extend(
            build_semantic_record(
                context,
                f"Flow step {item['flowId']}: {item['screenId']} -> {item['action']} -> {item['result']}",
                semantic_kind="fact",
                metadata={"slot": "flowStep", **item},
            )
            for item in parsed.design_flow_step_updates
        )
        fact_records.extend(
            build_semantic_record(
                context,
                f"Screen data {item['screenId']} ({item['dataKind']}): {item['name']}",
                semantic_kind="fact",
                metadata={"slot": "screenData", **item},
            )
            for item in parsed.design_screen_data_updates
        )
    return fact_records


def _slot_records(
    context: RecordBuildContext,
    items: list[str],
    *,
    slot: str,
) -> list[dict[str, Any]]:
    return [
        build_semantic_record(
            context,
            item,
            semantic_kind="fact",
            metadata={"slot": slot},
        )
        for item in items
    ]
