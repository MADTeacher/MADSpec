from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.features.agents.infrastructure.storage import ensure_agents_layout
from madspec_cli.features.policy.infrastructure.storage import ensure_policy_layout
from madspec_cli.project_state import create_madspec_config

from ..projection.materialize import consolidate_branch_memory
from ..shared.storage import ensure_memory_layout
from ..shared.validation import validate_branch_memory


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
    created = ensure_memory_layout(request.project_path, request.branch_name, full=True)
    created.extend(ensure_policy_layout(request.project_path))
    created.extend(ensure_agents_layout(request.project_path)[1])
    generated = consolidate_branch_memory(request.project_path, request.branch_name, full=True)
    errors = validate_branch_memory(request.project_path, request.branch_name, full=True)
    return BootstrapBranchMemoryResult(
        branch=request.branch_name,
        created_count=len(created),
        generated_count=len(generated),
        errors=errors,
    )
