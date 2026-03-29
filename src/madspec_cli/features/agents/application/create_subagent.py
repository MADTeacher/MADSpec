from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from madspec_cli.memory.shared.storage import now_iso
from madspec_cli.shared.kernel.result import PayloadResult

from ..infrastructure.artifact_export import export_agents_artifact
from ..infrastructure.catalog_store import (
    append_agent_history,
    enabled_subagents_for_output,
    find_effective_subagent,
    upsert_catalog_role,
)
from ..infrastructure.render_workspace import render_workspace_agents
from ..infrastructure.state_store import load_agents_state


@dataclass(frozen=True)
class CreateSubagentRequest:
    project_path: Path
    subagent_id: str
    payload: dict[str, object]
    body_text: str


@dataclass(frozen=True)
class CreateSubagentResult(PayloadResult):
    pass


def execute(request: CreateSubagentRequest) -> CreateSubagentResult:
    catalog, _definition = upsert_catalog_role(
        request.project_path,
        subagent_id=request.subagent_id,
        payload=request.payload,
        body_text=request.body_text,
        allow_create=True,
    )
    state = load_agents_state(request.project_path)
    effective_subagent = find_effective_subagent(request.project_path, request.subagent_id, state=state)
    export_agents_artifact(request.project_path, state)
    rendered = render_workspace_agents(request.project_path, state)
    append_agent_history(
        request.project_path,
        {
            "eventId": str(uuid.uuid4()),
            "eventType": "subagent_created",
            "ts": now_iso(),
            "summary": f"Создан проектный субагент {request.subagent_id}",
            "payload": {"subagentId": request.subagent_id, "catalog": catalog, "rendered": rendered},
        },
    )
    return CreateSubagentResult(
        payload={
            "accepted": True,
            "catalog": catalog,
            "subagent": effective_subagent,
            "profile": enabled_subagents_for_output(request.project_path, state),
            "rendered": rendered,
        }
    )
