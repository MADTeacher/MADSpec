from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.memory import consolidate_branch_memory, ensure_memory_layout, register_planned_step, validate_branch_memory
from madspec_cli.shared.kernel.result import PayloadResult


@dataclass(frozen=True)
class RegisterStepRequest:
    project_path: Path
    branch_name: str
    stage: str
    step_id: str
    covers: list[str]
    step_kind: str
    tdd_policy: str | None
    waiver_reason: str | None
    depends_on: list[str]
    summary: str | None


@dataclass(frozen=True)
class RegisterStepResult(PayloadResult):
    @property
    def accepted(self) -> bool:
        return bool(self.payload.get("accepted"))


def execute(request: RegisterStepRequest) -> RegisterStepResult:
    ensure_memory_layout(request.project_path, request.branch_name)
    payload = register_planned_step(
        request.project_path,
        request.branch_name,
        request.stage,
        step_id=request.step_id,
        covers=request.covers,
        step_kind=request.step_kind,
        tdd_policy=request.tdd_policy,
        waiver_reason=request.waiver_reason,
        depends_on=request.depends_on,
        summary=request.summary,
    )
    if payload.get("accepted"):
        consolidate_branch_memory(request.project_path, request.branch_name)
        validation_errors = validate_branch_memory(request.project_path, request.branch_name)
        if validation_errors:
            payload = {"accepted": False, "step_id": request.step_id, "errors": validation_errors}
    return RegisterStepResult(payload=payload)
