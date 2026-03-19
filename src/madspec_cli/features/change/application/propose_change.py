from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from .shared import create_change_proposal


@dataclass(frozen=True)
class ProposeChangeRequest:
    project_path: Path
    branch_name: str
    title: str
    summary: str
    requested_by: str


@dataclass(frozen=True)
class ProposeChangeResult(PayloadResult):
    pass


def execute(request: ProposeChangeRequest) -> ProposeChangeResult:
    proposal = create_change_proposal(
        request.project_path,
        request.branch_name,
        title=request.title,
        summary=request.summary,
        requested_by=request.requested_by,
    )
    return ProposeChangeResult(payload=proposal)
