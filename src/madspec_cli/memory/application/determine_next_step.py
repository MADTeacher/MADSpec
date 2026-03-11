from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.memory import determine_next_step, ensure_memory_layout
from madspec_cli.shared.kernel.result import PayloadResult


@dataclass(frozen=True)
class DetermineNextStepRequest:
    project_path: Path
    branch_name: str
    stage: str
    candidate_step: str | None
    depends_on: list[str]


@dataclass(frozen=True)
class DetermineNextStepResult(PayloadResult):
    @property
    def accepted(self) -> bool:
        return bool(self.payload.get("accepted"))


def execute(request: DetermineNextStepRequest) -> DetermineNextStepResult:
    ensure_memory_layout(request.project_path, request.branch_name)
    payload = determine_next_step(
        request.project_path,
        request.branch_name,
        request.stage,
        candidate_step=request.candidate_step,
        candidate_dependencies=request.depends_on,
    )
    return DetermineNextStepResult(payload=payload)
