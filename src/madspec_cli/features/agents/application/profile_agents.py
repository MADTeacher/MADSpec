from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from ..infrastructure.storage import (
    build_environment_profile,
    enabled_subagents_for_output,
    get_agents_paths,
    load_agents_state,
)


@dataclass(frozen=True)
class AgentProfileRequest:
    project_path: Path


@dataclass(frozen=True)
class AgentProfileResult(PayloadResult):
    pass


def execute(request: AgentProfileRequest) -> AgentProfileResult:
    state = load_agents_state(request.project_path)
    environment_id = state.get("environmentId")
    paths = get_agents_paths(request.project_path)
    return AgentProfileResult(
        payload={
            "environment": build_environment_profile(environment_id),
            "profile": enabled_subagents_for_output(request.project_path, state),
            "state_file": str(paths.state_file.relative_to(request.project_path)),
            "catalog_file": str(paths.catalog_file.relative_to(request.project_path)),
            "bodies_dir": str(paths.bodies_dir.relative_to(request.project_path)),
            "artifact_file": str(paths.artifact_file.relative_to(request.project_path)),
        }
    )
