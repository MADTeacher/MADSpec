from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from ..infrastructure.catalog_store import append_agent_proposal
from .common import build_proposal


@dataclass(frozen=True)
class ProposeProfileRequest:
    project_path: Path
    environment_id: str | None
    profile_id: str
    enabled_subagents: list[str] | None
    requested_by: str


@dataclass(frozen=True)
class ProposeProfileResult(PayloadResult):
    pass


def execute(request: ProposeProfileRequest) -> ProposeProfileResult:
    proposal = build_proposal(
        request.project_path,
        environment_id=request.environment_id,
        profile_id=request.profile_id,
        enabled_subagents=request.enabled_subagents,
        requested_by=request.requested_by,
    )
    append_agent_proposal(request.project_path, proposal)
    return ProposeProfileResult(payload=proposal)
