from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..shared.storage import ensure_memory_layout
from ..shared.system_store.canonical_state import refresh_branch_projections


@dataclass(frozen=True)
class ConsolidateMemoryRequest:
    project_path: Path
    branch_name: str


@dataclass(frozen=True)
class ConsolidateMemoryResult:
    branch: str
    generated_paths: list[Path]

    def to_payload(self) -> dict[str, object]:
        return {"branch": self.branch, "generated_paths": [str(path) for path in self.generated_paths]}


def execute(request: ConsolidateMemoryRequest) -> ConsolidateMemoryResult:
    ensure_memory_layout(request.project_path, request.branch_name, full=True)
    _, generated = refresh_branch_projections(
        request.project_path,
        request.branch_name,
        full=True,
    )
    return ConsolidateMemoryResult(branch=request.branch_name, generated_paths=generated)
