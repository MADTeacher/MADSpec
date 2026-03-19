from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from ..infrastructure.storage import (
    append_agent_history,
    enabled_subagents_for_output,
    export_agents_artifact,
    load_agents_state,
    now_iso,
    remove_catalog_role,
    render_workspace_agents,
)


@dataclass(frozen=True)
class RemoveSubagentRequest:
    project_path: Path
    subagent_id: str
    force: bool


@dataclass(frozen=True)
class RemoveSubagentResult(PayloadResult):
    pass


def execute(request: RemoveSubagentRequest) -> RemoveSubagentResult:
    catalog, removed = remove_catalog_role(
        request.project_path,
        subagent_id=request.subagent_id,
        force=request.force,
    )
    state = load_agents_state(request.project_path)
    export_agents_artifact(request.project_path, state)
    rendered = render_workspace_agents(request.project_path, state)
    append_agent_history(
        request.project_path,
        {
            "eventId": str(uuid.uuid4()),
            "eventType": "subagent_removed",
            "ts": now_iso(),
            "summary": f"Удален субагент {request.subagent_id}",
            "payload": {"subagentId": request.subagent_id, "removed": removed, "rendered": rendered},
        },
    )
    return RemoveSubagentResult(
        payload={
            "accepted": True,
            "catalog": catalog,
            "removed": removed,
            "profile": enabled_subagents_for_output(request.project_path, state),
            "rendered": rendered,
        }
    )
