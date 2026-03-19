from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from ..infrastructure.storage import append_policy_proposal, now_iso
from .apply_policy import ApplyPolicyRequest, execute as apply_policy
from .shared import build_diff, find_policy


@dataclass(frozen=True)
class DeprecatePolicyRequest:
    project_path: Path
    policy_id: str
    requested_by: str


@dataclass(frozen=True)
class DeprecatePolicyResult(PayloadResult):
    pass


def execute(request: DeprecatePolicyRequest) -> DeprecatePolicyResult:
    existing = find_policy(request.project_path, request.policy_id)
    if existing is None:
        raise ValueError(f"policy '{request.policy_id}' was not found")
    if existing.get("readonly"):
        raise ValueError(f"policy '{request.policy_id}' is read-only")
    proposal = {
        "proposalId": str(uuid.uuid4()),
        "policyId": request.policy_id,
        "action": "deprecate",
        "status": "pending",
        "summary": f"Deprecate policy {request.policy_id}",
        "requestedAt": now_iso(),
        "requestedBy": request.requested_by,
        "before": existing,
        "after": None,
        "diff": build_diff(existing, None),
        "warnings": [],
        "appliedAt": None,
    }
    append_policy_proposal(request.project_path, proposal)
    applied = apply_policy(ApplyPolicyRequest(project_path=request.project_path, proposal_id=proposal["proposalId"]))
    return DeprecatePolicyResult(payload=applied.to_payload())
