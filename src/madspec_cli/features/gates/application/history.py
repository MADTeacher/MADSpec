from __future__ import annotations

import uuid
from pathlib import Path

from madspec_cli.memory.shared.storage import now_iso

from ..domain.models import GateHistoryEvent
from ..infrastructure.storage import append_gate_history


def record_gate_run(
    project_path: Path,
    branch_name: str,
    *,
    stage: str,
    operation: str,
    step_id: str | None,
    overall_status: str,
    blocking_count: int,
    warning_count: int,
    pending_count: int,
    gate_count: int,
) -> None:
    append_gate_history(
        project_path,
        branch_name,
        GateHistoryEvent(
            event_id=str(uuid.uuid4()),
            event_type="gate_run",
            stage=stage,
            operation=operation,
            step_id=step_id,
            ts=now_iso(),
            summary=f"Evaluated gates for {stage}/{operation}",
            payload={
                "overallStatus": overall_status,
                "blockingCount": blocking_count,
                "warningCount": warning_count,
                "pendingCount": pending_count,
                "gateCount": gate_count,
            },
        ).to_payload(),
    )


def record_waiver_proposed(
    project_path: Path,
    branch_name: str,
    *,
    stage: str,
    operation: str,
    step_id: str | None,
    proposal_id: str,
    gate_id: str,
    ts: str,
) -> None:
    append_gate_history(
        project_path,
        branch_name,
        GateHistoryEvent(
            event_id=str(uuid.uuid4()),
            event_type="gate_waiver_proposed",
            stage=stage,
            operation=operation,
            step_id=step_id,
            ts=ts,
            summary=f"Proposed waiver for {gate_id}",
            payload={"proposalId": proposal_id, "gateId": gate_id},
        ).to_payload(),
    )


def record_waiver_applied(
    project_path: Path,
    branch_name: str,
    *,
    stage: str,
    operation: str,
    step_id: str | None,
    proposal_id: str,
    gate_id: str,
    waiver_id: str,
    ts: str,
) -> None:
    append_gate_history(
        project_path,
        branch_name,
        GateHistoryEvent(
            event_id=str(uuid.uuid4()),
            event_type="gate_waiver_applied",
            stage=stage,
            operation=operation,
            step_id=step_id,
            ts=ts,
            summary=f"Applied waiver for {gate_id}",
            payload={"proposalId": proposal_id, "gateId": gate_id, "waiverId": waiver_id},
        ).to_payload(),
    )
