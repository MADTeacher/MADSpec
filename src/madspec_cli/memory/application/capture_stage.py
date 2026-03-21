from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from madspec_cli.shared.kernel.result import PayloadResult

from .proposal_guard import guard_direct_runtime_write
from ..semantic.capture import capture_stage_memory


@dataclass(frozen=True)
class CaptureStageRequest:
    project_path: Path
    branch_name: str
    stage: str
    session_key: str
    expected_revision: int | None
    options: dict[str, Any]


@dataclass(frozen=True)
class CaptureStageResult(PayloadResult):
    @property
    def accepted(self) -> bool:
        return bool(self.payload.get("accepted"))


def execute(request: CaptureStageRequest) -> CaptureStageResult:
    blocked = guard_direct_runtime_write(
        request.project_path,
        branch_name=request.branch_name,
        session_key=request.session_key,
        command_name="capture",
    )
    if blocked is not None:
        return CaptureStageResult(payload=blocked)
    payload = capture_stage_memory(
        request.project_path,
        request.branch_name,
        request.stage,
        session_key=request.session_key,
        expected_revision=request.expected_revision,
        **request.options,
    )
    return CaptureStageResult(payload=payload)
