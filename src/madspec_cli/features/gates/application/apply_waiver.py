from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from .waivers import apply_waiver


@dataclass(frozen=True)
class ApplyWaiverRequest:
    project_path: Path
    branch_name: str
    proposal_id: str


@dataclass(frozen=True)
class ApplyWaiverResult(PayloadResult):
    pass


def execute(request: ApplyWaiverRequest) -> ApplyWaiverResult:
    return ApplyWaiverResult(
        payload=apply_waiver(
            request.project_path,
            request.branch_name,
            proposal_id=request.proposal_id,
        )
    )
