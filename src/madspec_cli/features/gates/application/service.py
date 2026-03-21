from __future__ import annotations

from pathlib import Path
from typing import Any

from madspec_cli.memory.shared.storage import (
    _default_progress_state,
    get_memory_paths,
    normalize_progress_state,
    read_json,
)
from madspec_cli.memory.shared.system_store.constants import SYSTEM_SESSION_KEY
from madspec_cli.memory.shared.system_store.sessions import load_runtime_session

from ..domain.status import aggregate_status, apply_waivers, dedupe_gates
from ..infrastructure.storage import ensure_gate_layout, load_gate_state
from .context import normalize_gate_operation, normalize_gate_stage, resolve_step_id
from .evaluators.integrity import collect_integrity_gates
from .evaluators.policy import collect_policy_gates
from .evaluators.ratification import build_ratification_gate
from .evaluators.runtime import collect_runtime_and_dependency_gates
from .history import record_gate_run


def gate_failure_messages(payload: dict[str, Any]) -> list[str]:
    return [
        gate["message"]
        for gate in payload.get("gates", [])
        if gate.get("status") == "failed" and gate.get("blocking") is True
    ]


def evaluate_gate_context(
    project_path: Path,
    branch_name: str,
    *,
    stage: str | None,
    operation: str | None,
    session_key: str = SYSTEM_SESSION_KEY,
    step_id: str | None = None,
    overrides: dict[str, Any] | None = None,
    include_ratification: bool = True,
    record_history: bool = False,
) -> dict[str, Any]:
    ensure_gate_layout(project_path, branch_name)
    normalized_stage = normalize_gate_stage(
        stage,
        project_path=project_path,
        branch_name=branch_name,
        session_key=session_key,
    )
    normalized_operation = normalize_gate_operation(operation)
    overrides = dict(overrides or {})

    paths = get_memory_paths(project_path, branch_name)
    progress = read_json(paths.progress, _default_progress_state())
    if not isinstance(progress, dict):
        progress = _default_progress_state()
    progress, _ = normalize_progress_state(progress)
    active_session = load_runtime_session(
        project_path,
        branch_name=branch_name,
        session_key=session_key,
    )

    resolved_step_id = resolve_step_id(
        progress=progress,
        session_payload=active_session,
        stage=normalized_stage,
        operation=normalized_operation,
        explicit_step_id=step_id or overrides.get("step_id"),
    )

    gates: list[dict[str, Any]] = []
    gates.extend(
        collect_integrity_gates(
            project_path=project_path,
            branch_name=branch_name,
            progress=progress,
            stage=normalized_stage,
            operation=normalized_operation,
            step_id=resolved_step_id,
        )
    )
    gates.extend(
        collect_runtime_and_dependency_gates(
            project_path=project_path,
            branch_name=branch_name,
            progress=progress,
            active_session=active_session,
            stage=normalized_stage,
            operation=normalized_operation,
            step_id=resolved_step_id,
            overrides=overrides,
        )
    )
    gates.extend(
        collect_policy_gates(
            project_path=project_path,
            branch_name=branch_name,
            stage=normalized_stage,
            operation=normalized_operation,
            step_id=resolved_step_id,
            overrides=overrides,
        )
    )
    if include_ratification and normalized_stage in {"review", "security"}:
        gates.append(
            build_ratification_gate(
                project_path=project_path,
                branch_name=branch_name,
                stage=normalized_stage,
            )
        )

    gates = dedupe_gates(gates)
    state = load_gate_state(project_path, branch_name)
    waivers = [item for item in state.get("waivers", []) if isinstance(item, dict)]
    gates = apply_waivers(gates, waivers)
    active_waivers = [item for item in waivers if item.get("gateId") in {gate["gateId"] for gate in gates}]

    overall_status = aggregate_status(gates)
    payload = {
        "branch": branch_name,
        "stage": normalized_stage,
        "session_key": session_key,
        "operation": normalized_operation,
        "step_id": resolved_step_id,
        "overall_status": overall_status,
        "blocking_count": sum(1 for gate in gates if gate["status"] == "failed" and gate["blocking"]),
        "warning_count": sum(1 for gate in gates if gate["status"] == "warning"),
        "pending_count": sum(1 for gate in gates if gate["status"] == "pending"),
        "gates": gates,
        "active_waivers": active_waivers,
        "valid": overall_status != "blocked",
        "revision": state.get("revision", 1),
    }
    if record_history:
        record_gate_run(
            project_path,
            branch_name,
            stage=normalized_stage,
            operation=normalized_operation,
            step_id=resolved_step_id,
            overall_status=overall_status,
            blocking_count=payload["blocking_count"],
            warning_count=payload["warning_count"],
            pending_count=payload["pending_count"],
            gate_count=len(gates),
        )
    return payload
