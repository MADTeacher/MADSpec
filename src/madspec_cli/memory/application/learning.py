from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.memory import consolidate_branch_memory, ensure_memory_layout, learn_from_outcomes, promote_validated_records
from madspec_cli.shared.kernel.result import PayloadResult


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
    ensure_memory_layout(request.project_path, request.branch_name)
    payload = promote_validated_records(request.project_path, request.branch_name)
    consolidate_branch_memory(request.project_path, request.branch_name)
    return PromoteMemoryResult(payload={"branch": request.branch_name, "promoted": payload})


def learn(request: LearnFromOutcomesRequest) -> LearnFromOutcomesResult:
    ensure_memory_layout(request.project_path, request.branch_name)
    payload = learn_from_outcomes(request.project_path, request.branch_name, request.input_path)
    consolidate_branch_memory(request.project_path, request.branch_name)
    return LearnFromOutcomesResult(payload={"branch": request.branch_name, **payload})
