from __future__ import annotations

from ..stages.architecture.state import ARCHITECTURE_STAGE
from ..stages.design.state import DESIGN_STAGE
from ..stages.tech.state import TECH_STAGE
from .record_context import RecordBuildContext, build_semantic_record


def build_contract_records(context: RecordBuildContext) -> list[dict[str, Any]]:
    inputs = context.inputs
    parsed = context.parsed
    contract_records = [
        build_semantic_record(
            context,
            item,
            semantic_kind="contract",
        )
        for item in inputs.contracts
    ]
    contract_records.extend(_slot_records(context, inputs.constraints, slot="constraint"))
    if inputs.stage == DESIGN_STAGE:
        contract_records.extend(_slot_records(context, inputs.platform_constraints, slot="platformConstraint"))
    if inputs.stage == TECH_STAGE:
        contract_records.extend(_slot_records(context, inputs.tech_constraints, slot="techConstraint"))
    if inputs.stage == ARCHITECTURE_STAGE:
        contract_records.extend(
            build_semantic_record(
                context,
                f"Endpoint error {item['operationId']} {item['error']['status']} "
                f"{item['error']['code']}: {item['error']['description']}",
                semantic_kind="contract",
                metadata={"slot": "endpointError", **item},
            )
            for item in parsed.architecture_endpoint_error_updates
        )
    return contract_records


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
            semantic_kind="contract",
            metadata={"slot": slot},
        )
        for item in items
    ]
