from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from ..infrastructure.storage import (
    append_agent_history,
    append_agent_proposal,
    enabled_subagents_for_output,
    load_agents_state,
    now_iso,
    render_workspace_agents,
    save_agents_state,
)
from .common import find_agent_proposal


@dataclass(frozen=True)
class ApplyProfileRequest:
    project_path: Path
    proposal_id: str


@dataclass(frozen=True)
class ApplyProfileResult(PayloadResult):
    pass


def execute(request: ApplyProfileRequest) -> ApplyProfileResult:
    proposal = find_agent_proposal(request.project_path, request.proposal_id)
    if proposal is None:
        raise ValueError(f"proposal '{request.proposal_id}' was not found")
    if proposal.get("status") == "applied":
        raise ValueError(f"proposal '{request.proposal_id}' is already applied")

    current_state = load_agents_state(request.project_path)
    next_state = dict(proposal.get("after") or {})
    if not next_state:
        raise ValueError(f"proposal '{request.proposal_id}' has no target profile payload")
    next_state["revision"] = int(current_state.get("revision") or 0) + 1
    next_state["createdAt"] = current_state.get("createdAt") or now_iso()
    next_state["updatedAt"] = now_iso()
    saved = save_agents_state(request.project_path, next_state)
    rendered = render_workspace_agents(request.project_path, saved)

    applied_proposal = dict(proposal)
    applied_proposal["status"] = "applied"
    applied_proposal["appliedAt"] = now_iso()
    append_agent_proposal(request.project_path, applied_proposal)
    append_agent_history(
        request.project_path,
        {
            "eventId": str(uuid.uuid4()),
            "eventType": "profile_applied",
            "ts": now_iso(),
            "summary": applied_proposal["summary"],
            "payload": {
                "profileId": saved.get("profileId"),
                "environmentId": saved.get("environmentId"),
                "rendered": rendered,
            },
        },
    )
    return ApplyProfileResult(
        payload={
            "proposal": applied_proposal,
            "profile": enabled_subagents_for_output(request.project_path, saved),
            "rendered": rendered,
        }
    )
