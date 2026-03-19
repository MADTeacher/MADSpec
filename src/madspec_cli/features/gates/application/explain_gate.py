from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from ..infrastructure.storage import list_gate_history, list_gate_proposals
from .common import evaluate_gate_context


@dataclass(frozen=True)
class ExplainGateRequest:
    project_path: Path
    branch_name: str
    stage: str | None
    operation: str | None
    step_id: str | None
    gate_id: str | None


@dataclass(frozen=True)
class ExplainGateResult(PayloadResult):
    pass


def execute(request: ExplainGateRequest) -> ExplainGateResult:
    payload = evaluate_gate_context(
        request.project_path,
        request.branch_name,
        stage=request.stage,
        operation=request.operation,
        step_id=request.step_id,
        overrides={},
        include_ratification=True,
        record_history=False,
    )
    gates = payload["gates"]
    if request.gate_id:
        gates = [gate for gate in gates if gate["gateId"] == request.gate_id]
    history = list_gate_history(request.project_path, request.branch_name)
    proposals = list_gate_proposals(request.project_path, request.branch_name)
    if request.gate_id:
        history = [
            item
            for item in history
            if item.get("payload", {}).get("gateId") == request.gate_id
            or item.get("payload", {}).get("gateIds", []) and request.gate_id in item.get("payload", {}).get("gateIds", [])
        ]
        proposals = [item for item in proposals if item.get("gateId") == request.gate_id]
    payload.update(
        {
            "gates": gates,
            "history": history[-10:],
            "proposals": proposals[-10:],
        }
    )
    return ExplainGateResult(payload=payload)
