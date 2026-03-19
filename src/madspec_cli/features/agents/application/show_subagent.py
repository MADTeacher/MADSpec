from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from .common import find_subagent


@dataclass(frozen=True)
class ShowSubagentRequest:
    project_path: Path
    subagent_id: str


@dataclass(frozen=True)
class ShowSubagentResult(PayloadResult):
    pass


def execute(request: ShowSubagentRequest) -> ShowSubagentResult:
    subagent = find_subagent(request.project_path, request.subagent_id)
    if subagent is None:
        raise ValueError(f"subagent '{request.subagent_id}' was not found")
    return ShowSubagentResult(payload=subagent)
