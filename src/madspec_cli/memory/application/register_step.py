from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.features.gates.application.common import evaluate_gate_context, gate_failure_messages
from madspec_cli.shared.kernel.result import PayloadResult

from ..shared.storage import ensure_memory_layout, get_memory_paths
from ..workflow.planning import register_planned_step


@dataclass(frozen=True)
class RegisterStepRequest:
    project_path: Path
    branch_name: str
    stage: str
    session_key: str
    step_id: str
    covers: list[str]
    step_kind: str
    tdd_policy: str | None
    waiver_reason: str | None
    depends_on: list[str]
    summary: str | None
    title: str | None
    related_artifacts: list[str]
    size: str | None
    complexity: str | None


@dataclass(frozen=True)
class RegisterStepResult(PayloadResult):
    @property
    def accepted(self) -> bool:
        return bool(self.payload.get("accepted"))


def execute(request: RegisterStepRequest) -> RegisterStepResult:
    ensure_memory_layout(request.project_path, request.branch_name, stage=request.stage)
    gate_payload = evaluate_gate_context(
        request.project_path,
        request.branch_name,
        stage=request.stage,
        operation="register-step",
        session_key=request.session_key,
        step_id=request.step_id,
        overrides={
            "step_kind": request.step_kind,
            "tdd_policy": request.tdd_policy,
            "waiver_reason": request.waiver_reason,
            "depends_on": request.depends_on,
            "covers": request.covers,
        },
        include_ratification=False,
        record_history=False,
    )
    if gate_payload["overall_status"] == "blocked":
        return RegisterStepResult(
            payload={
                "accepted": False,
                "step_id": request.step_id,
                "errors": gate_failure_messages(gate_payload),
                "gate_summary": gate_payload,
            }
        )
    paths = get_memory_paths(request.project_path, request.branch_name)
    payload = register_planned_step(
        request.project_path,
        request.branch_name,
        request.stage,
        session_key=request.session_key,
        step_id=request.step_id,
        covers=request.covers,
        step_kind=request.step_kind,
        tdd_policy=request.tdd_policy,
        waiver_reason=request.waiver_reason,
        depends_on=request.depends_on,
        summary=request.summary,
        title=request.title,
        related_artifacts=request.related_artifacts,
        size=request.size,
        complexity=request.complexity,
    )
    return RegisterStepResult(payload=payload)
