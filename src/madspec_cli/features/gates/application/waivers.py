from __future__ import annotations

import uuid
from pathlib import Path

from madspec_cli.memory.shared.storage import now_iso

from ..domain.models import GateWaiver, GateWaiverProposal
from ..infrastructure.storage import (
    append_gate_proposal,
    list_gate_proposals,
    load_gate_state,
    save_gate_proposals,
    save_gate_state,
)
from .history import record_waiver_applied, record_waiver_proposed
from .service import evaluate_gate_context


def propose_waiver(
    project_path: Path,
    branch_name: str,
    *,
    stage: str | None,
    operation: str | None,
    step_id: str | None,
    gate_id: str,
    reason: str,
    requested_by: str,
) -> dict[str, object]:
    normalized_reason = reason.strip()
    if not normalized_reason:
        return {"accepted": False, "error": "waiver reason must not be empty"}

    payload = evaluate_gate_context(
        project_path,
        branch_name,
        stage=stage,
        operation=operation,
        step_id=step_id,
        overrides={},
        include_ratification=True,
        record_history=False,
    )
    target_gate = next((gate for gate in payload["gates"] if gate["gateId"] == gate_id), None)
    if target_gate is None:
        return {"accepted": False, "error": f"gate '{gate_id}' was not found in the current context"}
    if not target_gate["waivable"]:
        return {"accepted": False, "error": f"gate '{gate_id}' is not waivable"}

    state = load_gate_state(project_path, branch_name)
    if any(item.get("gateId") == gate_id for item in state.get("waivers", [])):
        return {"accepted": False, "error": f"gate '{gate_id}' already has an active waiver"}
    proposals = list_gate_proposals(project_path, branch_name)
    if any(item.get("gateId") == gate_id and item.get("status") == "pending" for item in proposals):
        return {"accepted": False, "error": f"gate '{gate_id}' already has a pending waiver proposal"}

    ts = now_iso()
    after = {
        "gateId": gate_id,
        "stage": payload["stage"],
        "operation": payload["operation"],
        "stepId": payload["step_id"],
        "reason": normalized_reason,
        "requestedBy": requested_by,
        "status": "active",
    }
    proposal = GateWaiverProposal(
        proposal_id=f"gwaiver-{uuid.uuid4().hex[:10]}",
        gate_id=gate_id,
        stage=payload["stage"],
        operation=payload["operation"],
        step_id=payload["step_id"],
        status="pending",
        summary=f"Waive gate {gate_id} for {payload['stage']}/{payload['operation']}",
        reason=normalized_reason,
        requested_at=ts,
        requested_by=requested_by,
        before=None,
        after=after,
        diff={"changedFields": ["activeWaivers"]},
    ).to_payload()
    append_gate_proposal(project_path, branch_name, proposal)
    record_waiver_proposed(
        project_path,
        branch_name,
        stage=payload["stage"],
        operation=payload["operation"],
        step_id=payload["step_id"],
        proposal_id=proposal["proposalId"],
        gate_id=gate_id,
        ts=ts,
    )
    return {"accepted": True, **proposal}


def apply_waiver(project_path: Path, branch_name: str, *, proposal_id: str) -> dict[str, object]:
    proposals = list_gate_proposals(project_path, branch_name)
    proposal = next((item for item in proposals if item.get("proposalId") == proposal_id), None)
    if proposal is None:
        return {"accepted": False, "error": f"proposal '{proposal_id}' was not found"}
    if proposal.get("status") != "pending":
        return {"accepted": False, "error": f"proposal '{proposal_id}' is already applied"}

    state = load_gate_state(project_path, branch_name)
    ts = now_iso()
    waiver = GateWaiver(
        waiver_id=f"waiver-{uuid.uuid4().hex[:10]}",
        gate_id=proposal["gateId"],
        stage=proposal["stage"],
        operation=proposal["operation"],
        step_id=proposal.get("stepId"),
        reason=proposal["reason"],
        requested_by=proposal["requestedBy"],
        created_at=proposal["requestedAt"],
        applied_at=ts,
        payload=proposal["after"],
    ).to_payload()
    state.setdefault("waivers", []).append(waiver)
    state["revision"] = int(state.get("revision", 1)) + 1
    state["updatedAt"] = ts
    save_gate_state(project_path, branch_name, state)

    updated: list[dict[str, object]] = []
    for item in proposals:
        current = dict(item)
        if current.get("proposalId") == proposal_id:
            current["status"] = "applied"
            current["appliedAt"] = ts
        updated.append(current)
    save_gate_proposals(project_path, branch_name, updated)
    record_waiver_applied(
        project_path,
        branch_name,
        stage=proposal["stage"],
        operation=proposal["operation"],
        step_id=proposal.get("stepId"),
        proposal_id=proposal_id,
        gate_id=proposal["gateId"],
        waiver_id=waiver["waiverId"],
        ts=ts,
    )
    return {
        "accepted": True,
        "revision": state["revision"],
        "proposal": next(item for item in updated if item["proposalId"] == proposal_id),
        "waiver": waiver,
    }
