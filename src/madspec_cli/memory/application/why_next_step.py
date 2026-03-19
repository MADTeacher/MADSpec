from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.features.gates.application.common import evaluate_gate_context
from madspec_cli.memory.domain.progress import explain_next_executable_step
from madspec_cli.memory.shared.storage import _default_progress_state, get_memory_paths, read_json
from madspec_cli.shared.kernel.result import PayloadResult


@dataclass(frozen=True)
class WhyNextStepRequest:
    project_path: Path
    branch_name: str
    stage: str


@dataclass(frozen=True)
class WhyNextStepResult(PayloadResult):
    pass


def execute(request: WhyNextStepRequest) -> WhyNextStepResult:
    paths = get_memory_paths(request.project_path, request.branch_name)
    progress = read_json(paths.progress, _default_progress_state())
    if not isinstance(progress, dict):
        progress = _default_progress_state()

    analysis = explain_next_executable_step(progress)
    steps: list[dict[str, object]] = []
    for item in analysis["steps"]:
        step_id = item["step_id"]
        gate_summary = evaluate_gate_context(
            request.project_path,
            request.branch_name,
            stage=request.stage,
            operation="validate",
            step_id=step_id,
            overrides={},
        )
        steps.append(
            {
                **item,
                "gate_summary": gate_summary,
            }
        )

    return WhyNextStepResult(
        payload={
            "branch": request.branch_name,
            "stage": request.stage,
            "selected_step": analysis["selected_step"],
            "reason": analysis["reason"],
            "executable_steps": analysis["executable_steps"],
            "steps": steps,
        }
    )
