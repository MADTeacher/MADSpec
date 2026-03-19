from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from ..infrastructure.storage import load_agents_state, load_effective_subagents


@dataclass(frozen=True)
class ListSubagentsRequest:
    project_path: Path
    enabled_only: bool


@dataclass(frozen=True)
class ListSubagentsResult(PayloadResult):
    pass


def execute(request: ListSubagentsRequest) -> ListSubagentsResult:
    state = load_agents_state(request.project_path)
    subagents = load_effective_subagents(request.project_path, state=state)
    if request.enabled_only:
        subagents = [item for item in subagents if item.get("enabled")]
    return ListSubagentsResult(
        payload={
            "environmentId": state.get("environmentId"),
            "profileId": state.get("profileId"),
            "subagents": subagents,
        }
    )
