from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentEnvironmentProfile:
    environment_id: str
    display_name: str
    supports_native_subagents: bool
    command_dir: str
    command_extension: str
    subagents_dir: str | None
    subagent_extension: str | None
    subagent_frontmatter_profile: dict[str, Any] | None = None
    fallback_strategy: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "environmentId": self.environment_id,
            "displayName": self.display_name,
            "supportsNativeSubagents": self.supports_native_subagents,
            "commandDir": self.command_dir,
            "commandExtension": self.command_extension,
            "subagentsDir": self.subagents_dir,
            "subagentExtension": self.subagent_extension,
            "subagentFrontmatterProfile": self.subagent_frontmatter_profile,
            "fallbackStrategy": self.fallback_strategy,
        }


@dataclass(frozen=True)
class SubagentProfile:
    subagent_id: str
    title: str
    description: str
    purpose: str
    default_stage: str
    execution_mode_hint: str
    dependencies: list[str] = field(default_factory=list)
    tool_policy: dict[str, Any] = field(default_factory=dict)
    output_contract: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    render_mode: str = "native"
    origin: str = "builtin"
    body_source: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "subagentId": self.subagent_id,
            "title": self.title,
            "description": self.description,
            "purpose": self.purpose,
            "defaultStage": self.default_stage,
            "executionModeHint": self.execution_mode_hint,
            "dependencies": list(self.dependencies),
            "toolPolicy": dict(self.tool_policy),
            "outputContract": dict(self.output_contract),
            "enabled": self.enabled,
            "renderMode": self.render_mode,
            "origin": self.origin,
            "bodySource": self.body_source,
        }


@dataclass(frozen=True)
class AgentRecommendation:
    environment: AgentEnvironmentProfile
    profile_id: str
    summary: str
    recommended_subagents: list[SubagentProfile]

    def to_payload(self) -> dict[str, Any]:
        return {
            "environment": self.environment.to_payload(),
            "profileId": self.profile_id,
            "summary": self.summary,
            "recommendedSubagents": [item.to_payload() for item in self.recommended_subagents],
        }


@dataclass(frozen=True)
class AgentProfileProposal:
    proposal_id: str
    profile_id: str
    environment_id: str
    status: str
    requested_at: str
    requested_by: str
    summary: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    diff: dict[str, Any]
    applied_at: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "proposalId": self.proposal_id,
            "profileId": self.profile_id,
            "environmentId": self.environment_id,
            "status": self.status,
            "requestedAt": self.requested_at,
            "requestedBy": self.requested_by,
            "summary": self.summary,
            "before": self.before,
            "after": self.after,
            "diff": self.diff,
            "appliedAt": self.applied_at,
        }


@dataclass(frozen=True)
class AgentEvent:
    event_id: str
    event_type: str
    ts: str
    summary: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "eventId": self.event_id,
            "eventType": self.event_type,
            "ts": self.ts,
            "summary": self.summary,
            "payload": dict(self.payload),
        }
