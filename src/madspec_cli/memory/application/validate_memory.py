from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..shared.storage import ensure_memory_layout
from ..shared.validation import validate_branch_memory

if TYPE_CHECKING:
    from madspec_cli.shared.kernel.ports import BranchPolicyEvaluator


@dataclass(frozen=True)
class ValidateMemoryRequest:
    project_path: Path
    branch_name: str


@dataclass(frozen=True)
class ValidateMemoryResult:
    branch: str
    valid: bool
    errors: list[str]

    def to_payload(self) -> dict[str, object]:
        return {"branch": self.branch, "valid": self.valid, "errors": self.errors}


def _get_policy_violations(
    project_path: Path,
    branch_name: str,
    _evaluate_branch_policies: BranchPolicyEvaluator | None = None,
) -> list[dict[str, object]]:
    if _evaluate_branch_policies is None:
        from madspec_cli.features.policy.application.common import evaluate_branch_policies
        _evaluate_branch_policies = evaluate_branch_policies
    payload = _evaluate_branch_policies(
        project_path,
        branch_name,
        stage=None,
        operation="validate",
        include_system_policies=False,
        create_policy_if_missing=False,
    )
    return payload["violations"]


def execute(request: ValidateMemoryRequest) -> ValidateMemoryResult:
    ensure_memory_layout(request.project_path, request.branch_name, full=True)
    violations = _get_policy_violations(request.project_path, request.branch_name)
    errors = validate_branch_memory(
        request.project_path, request.branch_name, full=True, policy_violations=violations,
    )
    return ValidateMemoryResult(branch=request.branch_name, valid=not errors, errors=errors)
