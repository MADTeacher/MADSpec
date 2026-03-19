from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from madspec_cli.shared.kernel.result import PayloadResult

from ..semantic.capture import capture_stage_memory


@dataclass(frozen=True)
class CaptureStageRequest:
    project_path: Path
    branch_name: str
    stage: str
    options: dict[str, Any]


@dataclass(frozen=True)
class CaptureStageResult(PayloadResult):
    @property
    def accepted(self) -> bool:
        return bool(self.payload.get("accepted"))


def execute(request: CaptureStageRequest) -> CaptureStageResult:
    payload = capture_stage_memory(
        request.project_path,
        request.branch_name,
        request.stage,
        **request.options,
    )
    return CaptureStageResult(payload=payload)
