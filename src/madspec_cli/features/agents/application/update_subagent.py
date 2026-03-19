from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from ..infrastructure.storage import (
    append_agent_history,
    enabled_subagents_for_output,
    export_agents_artifact,
    find_effective_subagent,
    load_agents_state,
    now_iso,
    render_workspace_agents,
    upsert_catalog_role,
)


@dataclass(frozen=True)
class UpdateSubagentRequest:
    project_path: Path
    subagent_id: str
    payload: dict[str, object]
    body_text: str | None


@dataclass(frozen=True)
class UpdateSubagentResult(PayloadResult):
    pass


def execute(request: UpdateSubagentRequest) -> UpdateSubagentResult:
    catalog, _definition = upsert_catalog_role(
        request.project_path,
        subagent_id=request.subagent_id,
        payload=request.payload,
        body_text=request.body_text,
        allow_create=False,
    )
    state = load_agents_state(request.project_path)
    effective_subagent = find_effective_subagent(request.project_path, request.subagent_id, state=state)
    export_agents_artifact(request.project_path, state)
    rendered = render_workspace_agents(request.project_path, state)
    append_agent_history(
        request.project_path,
        {
            "eventId": str(uuid.uuid4()),
            "eventType": "subagent_updated",
            "ts": now_iso(),
            "summary": f"Updated subagent {request.subagent_id}",
            "payload": {"subagentId": request.subagent_id, "catalog": catalog, "rendered": rendered},
        },
    )
    return UpdateSubagentResult(
        payload={
            "accepted": True,
            "catalog": catalog,
            "subagent": effective_subagent,
            "profile": enabled_subagents_for_output(request.project_path, state),
            "rendered": rendered,
        }
    )
