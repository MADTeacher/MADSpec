from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.features.change.application.summary_change import SummaryChangeRequest, execute as summary_change
from madspec_cli.features.gates.application.status_gate import GateStatusRequest, execute as gate_status
from madspec_cli.features.policy.application.show_policy import ShowPolicyRequest, execute as show_policy
from madspec_cli.memory import retrieve_memory_context
from madspec_cli.memory.domain.branch_layout import resolve_target_branch
from madspec_cli.shared.kernel.result import PayloadResult

from .common import find_subagent


@dataclass(frozen=True)
class SubagentContextRequest:
    project_path: Path
    subagent_id: str
    branch_name: str | None
    stage: str | None
    session_key: str
    step_id: str | None


@dataclass(frozen=True)
class SubagentContextResult(PayloadResult):
    pass


def execute(request: SubagentContextRequest) -> SubagentContextResult:
    subagent = find_subagent(request.project_path, request.subagent_id)
    if subagent is None:
        raise ValueError(f"subagent '{request.subagent_id}' was not found")
    branch_name = resolve_target_branch(request.project_path, request.branch_name)
    stage = request.stage or str(subagent.get("defaultStage") or "feature.plan")
    memory_context = retrieve_memory_context(
        request.project_path,
        branch_name,
        stage,
        session_key=request.session_key,
        step_id=request.step_id,
        full_artifact=False,
        include_history=True,
    )
    policy = show_policy(
        ShowPolicyRequest(project_path=request.project_path, stage=stage, status="active")
    ).to_payload()
    gate_stage = "security" if request.subagent_id == "security" else stage
    gates = gate_status(
        GateStatusRequest(
            project_path=request.project_path,
            branch_name=branch_name,
            stage=gate_stage,
            operation="validate",
            step_id=request.step_id,
            overrides={},
            session_key=request.session_key,
        )
    ).to_payload()
    try:
        change = summary_change(
            SummaryChangeRequest(project_path=request.project_path, branch_name=branch_name)
        ).to_payload()
    except Exception:
        change = {"bundle": None, "highlights": None}
    return SubagentContextResult(
        payload={
            "subagent": subagent,
            "origin": subagent.get("origin"),
            "bodySource": subagent.get("bodySource"),
            "branch": branch_name,
            "stage": stage,
            "session_key": request.session_key,
            "memory": memory_context,
            "policy": policy,
            "gates": gates,
            "change": change,
        }
    )
