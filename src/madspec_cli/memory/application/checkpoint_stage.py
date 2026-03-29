from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from madspec_cli.shared.kernel.result import PayloadResult

if TYPE_CHECKING:
    from madspec_cli.shared.kernel.ports import GateEvaluator, GateFailureExtractor

from .branch_state import refresh_branch_state
from .proposal_guard import guard_direct_runtime_write
from ..semantic.checkpoint import checkpoint_stage_memory


@dataclass(frozen=True)
class CheckpointStageRequest:
    project_path: Path
    branch_name: str
    stage: str
    summary: str
    session_key: str
    expected_revision: int | None
    options: dict[str, Any]


@dataclass(frozen=True)
class CheckpointStageResult(PayloadResult):
    @property
    def accepted(self) -> bool:
        return bool(self.payload.get("accepted"))


def execute(
    request: CheckpointStageRequest,
    *,
    _evaluate_gate_context: GateEvaluator | None = None,
    _gate_failure_messages: GateFailureExtractor | None = None,
) -> CheckpointStageResult:
    if _evaluate_gate_context is None or _gate_failure_messages is None:
        from madspec_cli.features.gates.application.common import (
            evaluate_gate_context as _egc,
            gate_failure_messages as _gfm,
        )
        if _evaluate_gate_context is None:
            _evaluate_gate_context = _egc
        if _gate_failure_messages is None:
            _gate_failure_messages = _gfm

    blocked = guard_direct_runtime_write(
        request.project_path,
        branch_name=request.branch_name,
        session_key=request.session_key,
        command_name="checkpoint",
    )
    if blocked is not None:
        return CheckpointStageResult(payload=blocked)
    if request.stage.strip().lower() in {"review", "security"}:
        gate_payload = _evaluate_gate_context(
            request.project_path,
            request.branch_name,
            stage=request.stage,
            operation="validate",
            session_key=request.session_key,
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
                    "errors": _gate_failure_messages(gate_payload),
                    "gate_summary": gate_payload,
                }
            )
    payload = checkpoint_stage_memory(
        request.project_path,
        request.branch_name,
        request.stage,
        request.summary,
        session_key=request.session_key,
        expected_revision=request.expected_revision,
        **request.options,
    )
    if payload.get("accepted", True):
        refresh_branch_state(
            request.project_path,
            request.branch_name,
            stage=request.stage,
        )
    return CheckpointStageResult(payload=payload)
