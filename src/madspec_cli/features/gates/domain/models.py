from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GateResult:
    gate_id: str
    family: str
    scope: str
    subject_id: str
    blocking: bool
    waivable: bool
    status: str
    message: str
    source_ids: list[str] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {
            "gateId": self.gate_id,
            "family": self.family,
            "scope": self.scope,
            "subjectId": self.subject_id,
            "blocking": self.blocking,
            "waivable": self.waivable,
            "status": self.status,
            "message": self.message,
            "sourceIds": list(self.source_ids),
        }


@dataclass(frozen=True)
class GateWaiver:
    waiver_id: str
    gate_id: str
    stage: str
    operation: str
    step_id: str | None
    reason: str
    requested_by: str
    created_at: str
    applied_at: str
    payload: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return {
            "waiverId": self.waiver_id,
            "gateId": self.gate_id,
            "stage": self.stage,
            "operation": self.operation,
            "stepId": self.step_id,
            "reason": self.reason,
            "requestedBy": self.requested_by,
            "createdAt": self.created_at,
            "appliedAt": self.applied_at,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True)
class GateWaiverProposal:
    proposal_id: str
    gate_id: str
    stage: str
    operation: str
    step_id: str | None
    status: str
    summary: str
    reason: str
    requested_at: str
    requested_by: str
    before: dict[str, Any] | None
    after: dict[str, Any]
    diff: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    applied_at: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "proposalId": self.proposal_id,
            "gateId": self.gate_id,
            "stage": self.stage,
            "operation": self.operation,
            "stepId": self.step_id,
            "status": self.status,
            "summary": self.summary,
            "reason": self.reason,
            "requestedAt": self.requested_at,
            "requestedBy": self.requested_by,
            "before": self.before,
            "after": self.after,
            "diff": self.diff,
            "warnings": list(self.warnings),
            "appliedAt": self.applied_at,
        }


@dataclass(frozen=True)
class GateHistoryEvent:
    event_id: str
    event_type: str
    stage: str
    operation: str
    step_id: str | None
    ts: str
    summary: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "eventId": self.event_id,
            "eventType": self.event_type,
            "stage": self.stage,
            "operation": self.operation,
            "stepId": self.step_id,
            "ts": self.ts,
            "summary": self.summary,
            "payload": dict(self.payload),
        }
