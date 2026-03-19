from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from .waivers import propose_waiver


@dataclass(frozen=True)
class ProposeWaiverRequest:
    project_path: Path
    branch_name: str
    stage: str | None
    operation: str | None
    step_id: str | None
    gate_id: str
    reason: str
    requested_by: str


@dataclass(frozen=True)
class ProposeWaiverResult(PayloadResult):
    pass


def execute(request: ProposeWaiverRequest) -> ProposeWaiverResult:
    return ProposeWaiverResult(
        payload=propose_waiver(
            request.project_path,
            request.branch_name,
            stage=request.stage,
            operation=request.operation,
            step_id=request.step_id,
            gate_id=request.gate_id,
            reason=request.reason,
            requested_by=request.requested_by,
        )
    )
