from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from ..infrastructure.storage import build_policy_context, get_policy_paths
from .shared import find_policy, find_proposal
from .validate_policy import ValidatePolicyRequest, execute as validate_policy


@dataclass(frozen=True)
class ExplainPolicyRequest:
    project_path: Path
    branch_name: str
    stage: str | None
    operation: str | None
    step_id: str | None
    policy_id: str | None
    proposal_id: str | None


@dataclass(frozen=True)
class ExplainPolicyResult(PayloadResult):
    pass


def execute(request: ExplainPolicyRequest) -> ExplainPolicyResult:
    proposal = find_proposal(request.project_path, request.proposal_id) if request.proposal_id else None
    policy_id = request.policy_id or (proposal or {}).get("policyId")
    if not policy_id:
        raise ValueError("policy_id or proposal_id is required")
    policy = find_policy(request.project_path, policy_id)
    if policy is None and proposal is None:
        raise ValueError(f"policy '{policy_id}' was not found")
    validation = validate_policy(
        ValidatePolicyRequest(
            project_path=request.project_path,
            branch_name=request.branch_name,
            stage=request.stage,
            operation=request.operation,
            step_id=request.step_id,
            overrides={},
            policy_id=policy_id,
        )
    ).to_payload()
    return ExplainPolicyResult(
        payload={
            "policy": policy,
            "proposal": proposal,
            "validation": validation,
            "policy_context": build_policy_context(request.project_path, stage=request.stage),
            "artifact": str(get_policy_paths(request.project_path).artifact_file.relative_to(request.project_path)),
        }
    )
