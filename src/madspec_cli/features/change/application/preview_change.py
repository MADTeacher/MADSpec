from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from .shared import find_proposal


@dataclass(frozen=True)
class PreviewChangeRequest:
    project_path: Path
    branch_name: str
    proposal_id: str


@dataclass(frozen=True)
class PreviewChangeResult(PayloadResult):
    pass


def execute(request: PreviewChangeRequest) -> PreviewChangeResult:
    proposal = find_proposal(request.project_path, request.branch_name, request.proposal_id)
    if proposal is None:
        raise ValueError(f"proposal '{request.proposal_id}' was not found")
    return PreviewChangeResult(payload=proposal)
