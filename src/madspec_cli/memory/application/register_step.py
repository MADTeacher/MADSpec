from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.features.gates.application.common import evaluate_gate_context, gate_failure_messages
from madspec_cli.shared.kernel.result import PayloadResult

from ..projection.materialize import consolidate_branch_memory
from ..shared.storage import ensure_memory_layout, get_memory_paths
from ..shared.validation import validate_branch_memory
from ..workflow.planning import register_planned_step


@dataclass(frozen=True)
class RegisterStepRequest:
    project_path: Path
    branch_name: str
    stage: str
    step_id: str
    covers: list[str]
    step_kind: str
    tdd_policy: str | None
    waiver_reason: str | None
    depends_on: list[str]
    summary: str | None
    title: str | None
    related_artifacts: list[str]
    size: str | None
    complexity: str | None


@dataclass(frozen=True)
class RegisterStepResult(PayloadResult):
    @property
    def accepted(self) -> bool:
        return bool(self.payload.get("accepted"))


def execute(request: RegisterStepRequest) -> RegisterStepResult:
    ensure_memory_layout(request.project_path, request.branch_name, stage=request.stage)
    gate_payload = evaluate_gate_context(
        request.project_path,
        request.branch_name,
        stage=request.stage,
        operation="register-step",
        step_id=request.step_id,
        overrides={
            "step_kind": request.step_kind,
            "tdd_policy": request.tdd_policy,
            "waiver_reason": request.waiver_reason,
            "depends_on": request.depends_on,
            "covers": request.covers,
        },
        include_ratification=False,
        record_history=False,
    )
    if gate_payload["overall_status"] == "blocked":
        return RegisterStepResult(
            payload={
                "accepted": False,
                "step_id": request.step_id,
                "errors": gate_failure_messages(gate_payload),
                "gate_summary": gate_payload,
            }
        )
    paths = get_memory_paths(request.project_path, request.branch_name)
    branch_dir = paths.branch_dir
    snapshot_targets = [
        paths.progress,
        paths.plan_state,
        paths.feature_plan_state,
        paths.active_session,
        paths.decision_log,
        branch_dir / "concept.md",
        branch_dir / "ui-design.md",
        branch_dir / "tech-stack.md",
        branch_dir / "architecture.md",
        branch_dir / "data-model.md",
        branch_dir / "implementation-plan.md",
        branch_dir / "project-analysis.md",
        branch_dir / "feature-context.md",
        branch_dir / "planning-context-cache.md",
        branch_dir / "project-context.md",
        branch_dir / "contracts" / "openapi.yaml",
    ]
    snapshots = {
        path: path.read_text(encoding="utf-8") if path.exists() else None
        for path in snapshot_targets
    }
    payload = register_planned_step(
        request.project_path,
        request.branch_name,
        request.stage,
        step_id=request.step_id,
        covers=request.covers,
        step_kind=request.step_kind,
        tdd_policy=request.tdd_policy,
        waiver_reason=request.waiver_reason,
        depends_on=request.depends_on,
        summary=request.summary,
        title=request.title,
        related_artifacts=request.related_artifacts,
        size=request.size,
        complexity=request.complexity,
    )
    if payload.get("accepted"):
        consolidate_branch_memory(request.project_path, request.branch_name, stage=request.stage)
        validation_errors = validate_branch_memory(request.project_path, request.branch_name, stage=request.stage)
        if validation_errors:
            for path, content in snapshots.items():
                if content is None:
                    if path.exists():
                        path.unlink()
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content, encoding="utf-8")
            payload = {"accepted": False, "step_id": request.step_id, "errors": validation_errors}
    return RegisterStepResult(payload=payload)
