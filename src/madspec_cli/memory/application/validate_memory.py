from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..shared.storage import ensure_memory_layout
from ..shared.validation import validate_branch_memory


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
    ensure_memory_layout(request.project_path, request.branch_name, full=True)
    errors = validate_branch_memory(request.project_path, request.branch_name, full=True)
    return ValidateMemoryResult(branch=request.branch_name, valid=not errors, errors=errors)
