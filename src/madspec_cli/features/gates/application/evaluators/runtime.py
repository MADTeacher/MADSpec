from __future__ import annotations

from pathlib import Path
from typing import Any

from madspec_cli.memory.domain.workflow_rules import (
    WorkflowRuleReport,
    validate_checkpoint_step_rules,
    validate_complete_step_rules,
    validate_register_step_rules,
    validate_start_step_rules,
)
from madspec_cli.memory.shared.progress_utils import extract_function_catalog
from madspec_cli.memory.workflow.implementation_shared import IMPLEMENTATION_STAGES

from .shared import build_gate


def collect_runtime_and_dependency_gates(
    *,
    project_path: Path,
    branch_name: str,
    progress: dict[str, Any],
    active_session: dict[str, Any],
    stage: str,
    operation: str,
    step_id: str | None,
    overrides: dict[str, Any],
) -> list[dict[str, Any]]:
    report = _build_runtime_report(
        project_path=project_path,
        branch_name=branch_name,
        progress=progress,
        stage=stage,
        operation=operation,
        step_id=step_id,
        overrides=overrides,
    )
    if report is None:
        return []
    subject_id = _subject_id_for(operation=operation, step_id=step_id)
    return [
        build_gate(
            family=finding.family,
            scope=finding.scope,
            subject_id=finding.subject_id or subject_id,
            blocking=finding.blocking,
            waivable=finding.waivable,
            status=finding.status,
            message=finding.message,
            source_ids=list(finding.source_ids),
            stage=stage,
            operation=operation,
        )
        for finding in report.findings
    ]


def _build_runtime_report(
    *,
    project_path: Path,
    branch_name: str,
    progress: dict[str, Any],
    stage: str,
    operation: str,
    step_id: str | None,
    overrides: dict[str, Any],
) -> WorkflowRuleReport | None:
    if operation == "register-step":
        return validate_register_step_rules(
            progress=progress,
            step_id=step_id,
            step_kind=overrides.get("step_kind"),
            tdd_policy=overrides.get("tdd_policy"),
            waiver_reason=overrides.get("waiver_reason"),
            depends_on=overrides.get("depends_on"),
            covers=overrides.get("covers"),
            catalog=extract_function_catalog(project_path, branch_name, stage),
            catalog_source=_catalog_source_name(stage),
            include_completed_dependency_findings=True,
        )
    if stage not in IMPLEMENTATION_STAGES:
        return None
    if operation == "start-step":
        return validate_start_step_rules(
            progress=progress,
            step_id=step_id,
            include_dependency_pass_finding=True,
        )
    if operation == "validate":
        return validate_start_step_rules(
            progress=progress,
            step_id=step_id,
            include_dependency_pass_finding=True,
        )
    if operation == "checkpoint-step":
        return validate_checkpoint_step_rules(
            progress=progress,
            step_id=step_id,
            summary=overrides.get("summary"),
            tdd_phase=overrides.get("tdd_phase"),
            red_evidence=overrides.get("red_evidence"),
            green_evidence=overrides.get("green_evidence"),
            refactor_note=overrides.get("refactor_note"),
        )
    if operation == "complete-step":
        return validate_complete_step_rules(
            progress=progress,
            step_id=step_id,
            summary=overrides.get("summary"),
            red_evidence=overrides.get("red_evidence"),
            green_evidence=overrides.get("green_evidence"),
            refactor_note=overrides.get("refactor_note"),
            include_dependency_pass_finding=True,
        )
    return None


def _catalog_source_name(stage: str) -> str:
    return "feature.init.json" if "feature." in stage.lower() else "mvp.concept.json"


def _subject_id_for(*, operation: str, step_id: str | None) -> str:
    if operation == "register-step":
        return step_id or "planned-step"
    return step_id or "step"
