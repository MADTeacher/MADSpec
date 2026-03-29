from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from madspec_cli.shared.kernel.ports import (
        AgentsLayoutEnsurer,
        BranchPolicyEvaluator,
        PolicyLayoutEnsurer,
    )

from ..shared.validation import validate_branch_memory
from .branch_state import (
    BootstrapBranchStateRequest,
    bootstrap_branch_state,
    refresh_branch_state,
)


@dataclass(frozen=True)
class BootstrapBranchMemoryRequest:
    project_path: Path
    branch_name: str


@dataclass(frozen=True)
class BootstrapBranchMemoryResult:
    branch: str
    created_count: int
    generated_count: int
    errors: list[str]

    @property
    def accepted(self) -> bool:
        return not self.errors

    def to_payload(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "branch": self.branch,
            "created_count": self.created_count,
            "generated_count": self.generated_count,
            "errors": self.errors,
        }


def execute(
    request: BootstrapBranchMemoryRequest,
    *,
    _ensure_agents_layout: AgentsLayoutEnsurer | None = None,
    _evaluate_branch_policies: BranchPolicyEvaluator | None = None,
    _ensure_policy_layout: PolicyLayoutEnsurer | None = None,
) -> BootstrapBranchMemoryResult:
    if _ensure_agents_layout is None:
        from madspec_cli.features.agents.infrastructure.storage import ensure_agents_layout
        _ensure_agents_layout = ensure_agents_layout
    if _evaluate_branch_policies is None:
        from madspec_cli.features.policy.application.common import evaluate_branch_policies
        _evaluate_branch_policies = evaluate_branch_policies
    if _ensure_policy_layout is None:
        from madspec_cli.features.policy.infrastructure.storage import ensure_policy_layout
        _ensure_policy_layout = ensure_policy_layout

    bootstrap = bootstrap_branch_state(
        BootstrapBranchStateRequest(
            project_path=request.project_path,
            branch_name=request.branch_name,
        )
    )
    created = list(bootstrap.created_paths)
    created.extend(_ensure_policy_layout(request.project_path))
    created.extend(_ensure_agents_layout(request.project_path)[1])
    generated = refresh_branch_state(request.project_path, request.branch_name, full=True)
    policy_payload = _evaluate_branch_policies(
        request.project_path,
        request.branch_name,
        stage=None,
        operation="validate",
        include_system_policies=False,
        create_policy_if_missing=False,
    )
    errors = validate_branch_memory(
        request.project_path, request.branch_name, full=True,
        policy_violations=policy_payload["violations"],
    )
    return BootstrapBranchMemoryResult(
        branch=request.branch_name,
        created_count=len(created),
        generated_count=len(generated),
        errors=errors,
    )
