from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class PolicyScope:
    stages: list[str] = field(default_factory=list)
    operations: list[str] = field(default_factory=list)
    step_kinds: list[str] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PolicyRule:
    rule_type: str | None = None
    options: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {"ruleType": self.rule_type, "options": dict(self.options)}


@dataclass(frozen=True)
class PolicyDefinition:
    policy_id: str
    title: str
    description: str
    kind: str
    enforcement: str
    status: str
    source: str
    readonly: bool
    scope: PolicyScope = field(default_factory=PolicyScope)
    rule: PolicyRule | None = None
    created_at: str = ""
    updated_at: str = ""
    deprecated_at: str | None = None
    revision: int = 1

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "policyId": self.policy_id,
            "title": self.title,
            "description": self.description,
            "kind": self.kind,
            "enforcement": self.enforcement,
            "status": self.status,
            "source": self.source,
            "readonly": self.readonly,
            "scope": self.scope.to_payload(),
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "deprecatedAt": self.deprecated_at,
            "revision": self.revision,
        }
        if self.rule is not None:
            payload["rule"] = self.rule.to_payload()
        else:
            payload["rule"] = None
        return payload


@dataclass(frozen=True)
class PolicyProposal:
    proposal_id: str
    policy_id: str
    action: str
    status: str
    summary: str
    requested_at: str
    requested_by: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    diff: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    applied_at: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "proposalId": self.proposal_id,
            "policyId": self.policy_id,
            "action": self.action,
            "status": self.status,
            "summary": self.summary,
            "requestedAt": self.requested_at,
            "requestedBy": self.requested_by,
            "before": self.before,
            "after": self.after,
            "diff": self.diff,
            "warnings": list(self.warnings),
            "appliedAt": self.applied_at,
        }


@dataclass(frozen=True)
class PolicyEvent:
    event_id: str
    event_type: str
    policy_id: str | None
    proposal_id: str | None
    ts: str
    summary: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "eventId": self.event_id,
            "eventType": self.event_type,
            "policyId": self.policy_id,
            "proposalId": self.proposal_id,
            "ts": self.ts,
            "summary": self.summary,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True)
class PolicyValidationResult:
    policy_id: str
    title: str
    enforcement: str
    status: str
    message: str
    stage: str | None
    operation: str | None
    details: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "policyId": self.policy_id,
            "title": self.title,
            "enforcement": self.enforcement,
            "status": self.status,
            "message": self.message,
            "stage": self.stage,
            "operation": self.operation,
            "details": dict(self.details),
        }
