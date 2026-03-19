from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from madspec_cli.shared.kernel.result import PayloadResult

from .common import evaluate_branch_policies


@dataclass(frozen=True)
class ValidatePolicyRequest:
    project_path: Path
    branch_name: str
    stage: str | None
    operation: str | None
    step_id: str | None
    overrides: dict[str, Any]
    include_system_policies: bool = True
    policy_id: str | None = None


@dataclass(frozen=True)
class ValidatePolicyResult(PayloadResult):
    pass


def execute(request: ValidatePolicyRequest) -> ValidatePolicyResult:
    payload = evaluate_branch_policies(
        request.project_path,
        request.branch_name,
        stage=request.stage,
        operation=request.operation,
        step_id=request.step_id,
        overrides=request.overrides,
        include_system_policies=request.include_system_policies,
        policy_id=request.policy_id,
    )
    payload.update(
        {
            "branch": request.branch_name,
            "stage": request.stage,
            "operation": request.operation,
            "step_id": request.step_id,
            "valid": not payload["violations"],
        }
    )
    return ValidatePolicyResult(payload=payload)
