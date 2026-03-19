from __future__ import annotations

import uuid
from typing import Any

from ..infrastructure.storage import load_policy_state, list_policy_proposals, normalize_policy_payload, now_iso


def find_policy(project_path, policy_id: str) -> dict[str, Any] | None:
    state = load_policy_state(project_path)
    for policy in state.get("policies", []):
        if policy.get("policyId") == policy_id:
            return policy
    return None


def find_proposal(project_path, proposal_id: str) -> dict[str, Any] | None:
    for proposal in list_policy_proposals(project_path):
        if proposal.get("proposalId") == proposal_id:
            return proposal
    return None


def build_diff(before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, Any]:
    before = before or {}
    after = after or {}
    changes: list[dict[str, Any]] = []
    keys = sorted(set(before) | set(after))
    for key in keys:
        if before.get(key) != after.get(key):
            changes.append({"field": key, "before": before.get(key), "after": after.get(key)})
    return {"changedFields": [item["field"] for item in changes], "changes": changes}


def build_set_proposal_payload(
    *,
    policy_id: str,
    title: str,
    description: str,
    kind: str,
    enforcement: str,
    stages: list[str],
    operations: list[str],
    step_kinds: list[str],
    rule_type: str | None,
    requested_by: str,
    existing: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    now = now_iso()
    normalized, warnings = normalize_policy_payload(
        {
            "policyId": policy_id,
            "title": title,
            "description": description,
            "kind": kind,
            "enforcement": enforcement,
            "scope": {
                "stages": stages,
                "operations": operations,
                "stepKinds": step_kinds,
            },
            "rule": {"ruleType": rule_type, "options": {}} if rule_type else None,
            "source": "user",
            "status": "active",
            "createdAt": (existing or {}).get("createdAt") or now,
            "updatedAt": now,
            "revision": int((existing or {}).get("revision") or 0) + 1,
        },
        existing=existing,
    )
    proposal = {
        "proposalId": str(uuid.uuid4()),
        "policyId": normalized["policyId"],
        "action": "set",
        "status": "pending",
        "summary": f"Set policy {normalized['policyId']}",
        "requestedAt": now,
        "requestedBy": requested_by,
        "before": existing,
        "after": normalized,
        "diff": build_diff(existing, normalized),
        "warnings": warnings,
        "appliedAt": None,
    }
    return proposal, warnings
