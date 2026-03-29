from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from ..infrastructure.service import append_policy_proposal
from .shared import build_set_proposal_payload, find_policy


@dataclass(frozen=True)
class ProposePolicyRequest:
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
class ProposePolicyResult(PayloadResult):
    pass


def execute(request: ProposePolicyRequest) -> ProposePolicyResult:
    existing = find_policy(request.project_path, request.policy_id)
    if existing and existing.get("readonly"):
        raise ValueError(f"policy '{request.policy_id}' is read-only")
    proposal, _ = build_set_proposal_payload(
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
        existing=existing,
    )
    append_policy_proposal(request.project_path, proposal)
    return ProposePolicyResult(payload=proposal)
