from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from ..semantic.learning import learn_from_outcomes, promote_validated_records
from ..shared.storage import ensure_memory_layout
from .branch_state import refresh_branch_state


@dataclass(frozen=True)
class PromoteMemoryRequest:
    project_path: Path
    branch_name: str


@dataclass(frozen=True)
class PromoteMemoryResult(PayloadResult):
    pass


@dataclass(frozen=True)
class LearnFromOutcomesRequest:
    project_path: Path
    branch_name: str
    input_path: Path


@dataclass(frozen=True)
class LearnFromOutcomesResult(PayloadResult):
    pass


def promote(request: PromoteMemoryRequest) -> PromoteMemoryResult:
    ensure_memory_layout(request.project_path, request.branch_name, full=True)
    payload = promote_validated_records(request.project_path, request.branch_name)
    refresh_branch_state(request.project_path, request.branch_name, full=True)
    return PromoteMemoryResult(payload={"branch": request.branch_name, "promoted": payload})


def learn(request: LearnFromOutcomesRequest) -> LearnFromOutcomesResult:
    ensure_memory_layout(request.project_path, request.branch_name, full=True)
    payload = learn_from_outcomes(request.project_path, request.branch_name, request.input_path)
    refresh_branch_state(request.project_path, request.branch_name, full=True)
    return LearnFromOutcomesResult(payload={"branch": request.branch_name, **payload})
