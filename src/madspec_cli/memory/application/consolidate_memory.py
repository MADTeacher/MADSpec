from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.memory import consolidate_branch_memory, ensure_memory_layout


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
    ensure_memory_layout(request.project_path, request.branch_name)
    generated = consolidate_branch_memory(request.project_path, request.branch_name)
    return ConsolidateMemoryResult(branch=request.branch_name, generated_paths=generated)
