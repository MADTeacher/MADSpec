from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from .apply_policy import ApplyPolicyRequest, execute as apply_policy
from .propose_policy import ProposePolicyRequest, execute as propose_policy


@dataclass(frozen=True)
class SetPolicyRequest:
    project_path: Path
    policy_id: str
    title: str
    description: str
    kind: str
    enforcement: str
    stages: list[str]
    operations: list[str]
    step_kinds: list[str]
    rule_type: str | None
    requested_by: str


@dataclass(frozen=True)
class SetPolicyResult(PayloadResult):
    pass


def execute(request: SetPolicyRequest) -> SetPolicyResult:
    proposal = propose_policy(
        ProposePolicyRequest(
            project_path=request.project_path,
            policy_id=request.policy_id,
            title=request.title,
            description=request.description,
            kind=request.kind,
            enforcement=request.enforcement,
            stages=request.stages,
            operations=request.operations,
            step_kinds=request.step_kinds,
            rule_type=request.rule_type,
            requested_by=request.requested_by,
        )
    ).to_payload()
    applied = apply_policy(
        ApplyPolicyRequest(project_path=request.project_path, proposal_id=proposal["proposalId"])
    ).to_payload()
    return SetPolicyResult(payload={"proposal": proposal, "applied": applied})
