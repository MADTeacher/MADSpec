from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from madspec_cli.memory import checkpoint_stage_memory
from madspec_cli.shared.kernel.result import PayloadResult


@dataclass(frozen=True)
class CheckpointStageRequest:
    project_path: Path
    branch_name: str
    stage: str
    summary: str
    options: dict[str, Any]


@dataclass(frozen=True)
class CheckpointStageResult(PayloadResult):
    @property
    def accepted(self) -> bool:
        return bool(self.payload.get("accepted"))


def execute(request: CheckpointStageRequest) -> CheckpointStageResult:
    payload = checkpoint_stage_memory(
        request.project_path,
        request.branch_name,
        request.stage,
        request.summary,
        **request.options,
    )
    return CheckpointStageResult(payload=payload)
