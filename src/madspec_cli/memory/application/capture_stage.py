from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from madspec_cli.shared.kernel.result import PayloadResult

from .branch_state import refresh_branch_state
from .proposal_guard import guard_direct_runtime_write
from ..semantic.capture import capture_stage_memory
from ..semantic.capture_payloads import build_stage_capture_payload


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
    status = request.options.get("status", "validated")
    payload_options = {key: value for key, value in request.options.items() if key != "status"}
    payload = capture_stage_memory(
        request.project_path,
        request.branch_name,
        request.stage,
        payload=build_stage_capture_payload(request.stage, **payload_options),
        session_key=request.session_key,
        expected_revision=request.expected_revision,
        status=str(status),
    )
    if payload.get("accepted", True):
        refresh_branch_state(
            request.project_path,
            request.branch_name,
            stage=request.stage,
        )
    return CaptureStageResult(payload=payload)
