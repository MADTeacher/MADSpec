from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from madspec_cli.features.gates.application.common import evaluate_gate_context, gate_failure_messages
from madspec_cli.shared.kernel.result import PayloadResult

from ..semantic.checkpoint import checkpoint_stage_memory


@dataclass(frozen=True)
class CheckpointStageRequest:
    project_path: Path
    branch_name: str
    stage: str
    summary: str
    options: dict[str, Any]


@dataclass(frozen=True)
class CheckpointStageResult(PayloadResult):
    @property
    def accepted(self) -> bool:
        return bool(self.payload.get("accepted"))


def execute(request: CheckpointStageRequest) -> CheckpointStageResult:
    if request.stage.strip().lower() in {"review", "security"}:
        gate_payload = evaluate_gate_context(
            request.project_path,
            request.branch_name,
            stage=request.stage,
            operation="validate",
            overrides={"summary": request.summary},
            include_ratification=False,
            record_history=False,
        )
        if gate_payload["overall_status"] == "blocked":
            return CheckpointStageResult(
                payload={
                    "accepted": False,
                    "branch": request.branch_name,
                    "stage": request.stage,
                    "errors": gate_failure_messages(gate_payload),
                    "gate_summary": gate_payload,
                }
            )
    payload = checkpoint_stage_memory(
        request.project_path,
        request.branch_name,
        request.stage,
        request.summary,
        **request.options,
    )
    return CheckpointStageResult(payload=payload)
