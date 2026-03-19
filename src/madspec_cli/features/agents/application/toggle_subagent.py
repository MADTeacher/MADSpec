from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from ..infrastructure.storage import (
    append_agent_history,
    enabled_subagents_for_output,
    load_agents_state,
    now_iso,
    render_workspace_agents,
    save_agents_state,
    unique_role_ids,
)
from .common import find_subagent


@dataclass(frozen=True)
class ToggleSubagentRequest:
    project_path: Path
    subagent_id: str
    enabled: bool


@dataclass(frozen=True)
class ToggleSubagentResult(PayloadResult):
    pass


def execute(request: ToggleSubagentRequest) -> ToggleSubagentResult:
    target = find_subagent(request.project_path, request.subagent_id)
    if target is None:
        raise ValueError(f"subagent '{request.subagent_id}' was not found")
    state = load_agents_state(request.project_path)
    enabled_ids = unique_role_ids(list(state.get("enabledSubagentIds") or []))
    changed = (request.subagent_id in enabled_ids) != request.enabled
    if not changed:
        return ToggleSubagentResult(
            payload={
                "accepted": True,
                "changed": False,
                "profile": enabled_subagents_for_output(request.project_path, state),
                "rendered": {"created": [], "removed": []},
            }
        )
    if request.enabled:
        state["enabledSubagentIds"] = unique_role_ids(enabled_ids + [request.subagent_id])
    else:
        state["enabledSubagentIds"] = [item for item in enabled_ids if item != request.subagent_id]
    state["revision"] = int(state.get("revision") or 0) + 1
    state["updatedAt"] = now_iso()
    saved = save_agents_state(request.project_path, state)
    rendered = render_workspace_agents(request.project_path, saved)
    append_agent_history(
        request.project_path,
        {
            "eventId": str(uuid.uuid4()),
            "eventType": "subagent_toggled",
            "ts": now_iso(),
            "summary": f"{'Enabled' if request.enabled else 'Disabled'} subagent {request.subagent_id}",
            "payload": {
                "subagentId": request.subagent_id,
                "enabled": request.enabled,
                "rendered": rendered,
            },
        },
    )
    return ToggleSubagentResult(
        payload={
            "accepted": True,
            "changed": True,
            "profile": enabled_subagents_for_output(request.project_path, saved),
            "rendered": rendered,
        }
    )
