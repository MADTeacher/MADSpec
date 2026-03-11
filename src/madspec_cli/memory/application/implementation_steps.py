from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from madspec_cli.memory import ensure_memory_layout
from madspec_cli.memory.workflow.implementation import (
    checkpoint_implementation_step,
    complete_implementation_step,
    start_implementation_step,
)
from madspec_cli.shared.kernel.result import PayloadResult


@dataclass(frozen=True)
class ImplementationStepRequest:
    project_path: Path
    branch_name: str
    stage: str
    options: dict[str, Any]


@dataclass(frozen=True)
class ImplementationStepResult(PayloadResult):
    @property
    def accepted(self) -> bool:
        return bool(self.payload.get("accepted"))


def start(request: ImplementationStepRequest) -> ImplementationStepResult:
    ensure_memory_layout(request.project_path, request.branch_name)
    payload = start_implementation_step(request.project_path, request.branch_name, request.stage, **request.options)
    return ImplementationStepResult(payload=payload)


def checkpoint(request: ImplementationStepRequest) -> ImplementationStepResult:
    ensure_memory_layout(request.project_path, request.branch_name)
    payload = checkpoint_implementation_step(request.project_path, request.branch_name, request.stage, **request.options)
    return ImplementationStepResult(payload=payload)


def complete(request: ImplementationStepRequest) -> ImplementationStepResult:
    ensure_memory_layout(request.project_path, request.branch_name)
    payload = complete_implementation_step(request.project_path, request.branch_name, request.stage, **request.options)
    return ImplementationStepResult(payload=payload)
