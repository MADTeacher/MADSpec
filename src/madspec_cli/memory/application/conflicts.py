from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from madspec_cli.memory.shared.system_store.store import MemoryStore
from madspec_cli.memory.shared.validation import validate_branch_memory
from madspec_cli.shared.kernel.result import PayloadResult

if TYPE_CHECKING:
    from madspec_cli.shared.kernel.ports import BranchPolicyEvaluator

from .observability import build_runtime_observability

from .diagnostics_shared import simplify_record


@dataclass(frozen=True)
class MemoryConflictsRequest:
    project_path: Path
    branch_name: str
    stage: str | None
    step_id: str | None
    limit: int


@dataclass(frozen=True)
class MemoryConflictsResult(PayloadResult):
    pass


def execute(
    request: MemoryConflictsRequest,
    *,
    _evaluate_branch_policies: BranchPolicyEvaluator | None = None,
) -> MemoryConflictsResult:
    if _evaluate_branch_policies is None:
        from madspec_cli.features.policy.application.common import evaluate_branch_policies
        _evaluate_branch_policies = evaluate_branch_policies

    store = MemoryStore(request.project_path)
    observability = build_runtime_observability(
        request.project_path,
        branch_name=request.branch_name,
        stage=request.stage,
        step_id=request.step_id,
        limit=request.limit,
    )
    record_conflicts = [
        simplify_record(item)
        for item in store.list_records(
            branch=request.branch_name,
            stage=request.stage,
            step_id=request.step_id,
            statuses=["conflicted"],
            limit=request.limit,
        )
    ]
    integrity_conflicts = [
        {"message": message}
        for message in validate_branch_memory(
            request.project_path, request.branch_name,
            policy_violations=_evaluate_branch_policies(
                request.project_path,
                request.branch_name,
                stage=None,
                operation="validate",
                include_system_policies=False,
                create_policy_if_missing=False,
            )["violations"],
        )
    ]

    return MemoryConflictsResult(
        payload={
            "branch": request.branch_name,
            "stage": request.stage,
            "step_id": request.step_id,
            "record_conflicts": record_conflicts,
            "integrity_conflicts": integrity_conflicts[: request.limit],
            "conflict_dashboard": observability.get("conflict_state"),
            "observability": observability,
        }
    )
