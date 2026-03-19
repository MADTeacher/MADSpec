from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from ..infrastructure.storage import (
    append_policy_history,
    append_policy_proposal,
    load_policy_state,
    now_iso,
    save_policy_state,
)
from .shared import find_policy, find_proposal


@dataclass(frozen=True)
class ApplyPolicyRequest:
    project_path: Path
    proposal_id: str


@dataclass(frozen=True)
class ApplyPolicyResult(PayloadResult):
    pass


def execute(request: ApplyPolicyRequest) -> ApplyPolicyResult:
    proposal = find_proposal(request.project_path, request.proposal_id)
    if proposal is None:
        raise ValueError(f"proposal '{request.proposal_id}' was not found")
    if proposal.get("status") == "applied":
        raise ValueError(f"proposal '{request.proposal_id}' is already applied")

    state = load_policy_state(request.project_path)
    policies = list(state.get("policies", []))
    action = proposal.get("action")
    policy_id = proposal.get("policyId")
    ts = now_iso()

    if action == "set":
        after = dict(proposal.get("after") or {})
        if not after:
            raise ValueError(f"proposal '{request.proposal_id}' has no normalized policy payload")
        existing = find_policy(request.project_path, policy_id)
        if existing and existing.get("readonly"):
            raise ValueError(f"policy '{policy_id}' is read-only")
        updated = False
        for index, item in enumerate(policies):
            if item.get("policyId") == policy_id:
                after["createdAt"] = item.get("createdAt") or after.get("createdAt") or ts
                after["updatedAt"] = ts
                after["revision"] = int(item.get("revision") or 0) + 1
                policies[index] = after
                updated = True
                break
        if not updated:
            after["createdAt"] = after.get("createdAt") or ts
            after["updatedAt"] = ts
            after["revision"] = int(after.get("revision") or 1)
            policies.append(after)
    elif action == "deprecate":
        updated = False
        for index, item in enumerate(policies):
            if item.get("policyId") != policy_id:
                continue
            if item.get("readonly"):
                raise ValueError(f"policy '{policy_id}' is read-only")
            replacement = dict(item)
            replacement["status"] = "deprecated"
            replacement["deprecatedAt"] = ts
            replacement["updatedAt"] = ts
            replacement["revision"] = int(item.get("revision") or 0) + 1
            policies[index] = replacement
            updated = True
            break
        if not updated:
            raise ValueError(f"policy '{policy_id}' was not found")
    else:
        raise ValueError(f"unsupported proposal action '{action}'")

    state["policies"] = policies
    state["revision"] = int(state.get("revision") or 0) + 1
    saved_state = save_policy_state(request.project_path, state)

    applied_proposal = dict(proposal)
    applied_proposal["status"] = "applied"
    applied_proposal["appliedAt"] = ts
    append_policy_proposal(request.project_path, applied_proposal)
    event_type = "policy_applied" if action == "set" else "policy_deprecated"
    append_policy_history(
        request.project_path,
        {
            "eventId": str(uuid.uuid4()),
            "eventType": event_type,
            "policyId": policy_id,
            "proposalId": request.proposal_id,
            "ts": ts,
            "summary": applied_proposal["summary"],
            "payload": {"action": action},
        },
    )
    return ApplyPolicyResult(
        payload={
            "proposal": applied_proposal,
            "policy": find_policy(request.project_path, policy_id),
            "revision": saved_state.get("revision", 1),
        }
    )
