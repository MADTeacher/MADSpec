from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from ..infrastructure.storage import build_change_context
from .shared import require_change_state


@dataclass(frozen=True)
class SummaryChangeRequest:
    project_path: Path
    branch_name: str


@dataclass(frozen=True)
class SummaryChangeResult(PayloadResult):
    pass


def execute(request: SummaryChangeRequest) -> SummaryChangeResult:
    state = require_change_state(request.project_path, request.branch_name)
    bundle = state.get("activeBundle")
    if not isinstance(bundle, dict):
        raise ValueError("no active change bundle is applied; run 'madspec change apply' first")
    return SummaryChangeResult(
        payload={
            "bundle": bundle,
            "highlights": build_change_context(request.project_path, request.branch_name),
        }
    )
