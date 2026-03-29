from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..shared.records import make_record
from .capture_models import CaptureInputs, ParsedStageBundle


@dataclass(frozen=True)
class RecordBuildContext:
    branch_name: str
    ts: str
    inputs: CaptureInputs
    parsed: ParsedStageBundle


def build_stage_note_record(
    context: RecordBuildContext,
    summary: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return make_record(
        context.branch_name,
        context.inputs.stage,
        "memory.capture",
        summary,
        status=context.inputs.status,
        evidence=context.inputs.evidence,
        scope="project",
        record_type="stage_note",
        metadata=metadata,
        ts=context.ts,
    )


def build_semantic_record(
    context: RecordBuildContext,
    summary: str,
    *,
    semantic_kind: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return make_record(
        context.branch_name,
        context.inputs.stage,
        "memory.capture",
        summary,
        status=context.inputs.status,
        evidence=context.inputs.evidence,
        scope="project",
        semantic_kind=semantic_kind,
        record_type=semantic_kind,
        metadata=metadata,
        ts=context.ts,
    )
