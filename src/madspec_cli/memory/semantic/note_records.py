from __future__ import annotations

from typing import Any

from .record_context import RecordBuildContext, build_stage_note_record


def build_note_records(context: RecordBuildContext) -> list[dict[str, Any]]:
    inputs = context.inputs
    if not (inputs.summary or inputs.questions or inputs.pending_actions):
        return []
    return [
        build_stage_note_record(
            context,
            inputs.summary or f"Captured stage update for {inputs.stage}",
            metadata={
                "questions": inputs.questions,
                "pendingActions": inputs.pending_actions,
            },
        )
    ]
