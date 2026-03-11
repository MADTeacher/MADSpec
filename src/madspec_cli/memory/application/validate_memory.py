from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.memory import ensure_memory_layout, validate_branch_memory


@dataclass(frozen=True)
class ValidateMemoryRequest:
    project_path: Path
    branch_name: str


@dataclass(frozen=True)
class ValidateMemoryResult:
    branch: str
    valid: bool
    errors: list[str]

    def to_payload(self) -> dict[str, object]:
        return {"branch": self.branch, "valid": self.valid, "errors": self.errors}


def execute(request: ValidateMemoryRequest) -> ValidateMemoryResult:
    ensure_memory_layout(request.project_path, request.branch_name)
    errors = validate_branch_memory(request.project_path, request.branch_name)
    return ValidateMemoryResult(branch=request.branch_name, valid=not errors, errors=errors)
