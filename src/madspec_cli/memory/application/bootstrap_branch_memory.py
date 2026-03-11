from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.memory import consolidate_branch_memory, ensure_memory_layout, validate_branch_memory
from madspec_cli.project_state import create_madspec_config


@dataclass(frozen=True)
class BootstrapBranchMemoryRequest:
    project_path: Path
    branch_name: str


@dataclass(frozen=True)
class BootstrapBranchMemoryResult:
    branch: str
    created_count: int
    generated_count: int
    errors: list[str]

    @property
    def accepted(self) -> bool:
        return not self.errors

    def to_payload(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "branch": self.branch,
            "created_count": self.created_count,
            "generated_count": self.generated_count,
            "errors": self.errors,
        }


def execute(request: BootstrapBranchMemoryRequest) -> BootstrapBranchMemoryResult:
    create_madspec_config(request.project_path, request.branch_name)
    created = ensure_memory_layout(request.project_path, request.branch_name)
    generated = consolidate_branch_memory(request.project_path, request.branch_name)
    errors = validate_branch_memory(request.project_path, request.branch_name)
    return BootstrapBranchMemoryResult(
        branch=request.branch_name,
        created_count=len(created),
        generated_count=len(generated),
        errors=errors,
    )
