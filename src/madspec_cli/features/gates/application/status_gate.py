from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from madspec_cli.memory.shared.system_store.constants import SYSTEM_SESSION_KEY
from madspec_cli.shared.kernel.result import PayloadResult

from .common import evaluate_gate_context


@dataclass(frozen=True)
class GateStatusRequest:
    project_path: Path
    branch_name: str
    stage: str | None
    operation: str | None
    step_id: str | None
    overrides: dict[str, Any]
    session_key: str = SYSTEM_SESSION_KEY


@dataclass(frozen=True)
class GateStatusResult(PayloadResult):
    pass


def execute(request: GateStatusRequest) -> GateStatusResult:
    payload = evaluate_gate_context(
        request.project_path,
        request.branch_name,
        stage=request.stage,
        operation=request.operation,
        session_key=request.session_key,
        step_id=request.step_id,
        overrides=request.overrides,
        include_ratification=True,
        record_history=False,
    )
    return GateStatusResult(payload=payload)
