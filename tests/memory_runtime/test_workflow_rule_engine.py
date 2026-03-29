from __future__ import annotations

from typing import Any

from madspec_cli.features.gates.application.service import evaluate_gate_context, gate_failure_messages
from madspec_cli.memory.domain.workflow_rules import (
    validate_complete_step_rules,
    validate_register_step_rules,
)
from madspec_cli.memory.implementation import (
    checkpoint_implementation_step,
    complete_implementation_step,
    start_implementation_step,
)
from madspec_cli.memory.workflow.planning import register_planned_step
from tests.memory_runtime.support import step_metadata, step_status


def _always_pass_gate(*args: Any, **kwargs: Any) -> dict[str, Any]:
    step_id = kwargs.get("step_id")
    return {
        "overall_status": "passed",
        "gates": [],
        "step_id": step_id,
    }


def _no_gate_errors(payload: dict[str, Any]) -> list[str]:
    del payload
    return []


def test_validate_register_step_rules_normalizes_policy_and_reports_completed_dependency() -> None:
    progress = {
        "plannedSteps": ["step-01-bootstrap"],
        "completedSteps": ["step-01-bootstrap"],
        "planningMetadata": {"stepDependencies": {}},
    }

    report = validate_register_step_rules(
        progress=progress,
        step_id="step-02-docs-refresh",
        step_kind="non-code",
        tdd_policy=None,
        waiver_reason="Documentation change only.",
        depends_on=["step-01-bootstrap"],
        covers=["  **Authentication**  "],
        catalog={"p1": ["Authentication"], "p2": [], "p3": []},
        catalog_source="mvp.concept.json",
        include_completed_dependency_findings=True,
    )

    assert report.errors == []
    assert report.normalized["effective_tdd_policy"] == "waived"
    assert report.normalized["normalized_covers"] == ["Authentication"]
    assert any(
        finding.status == "passed" and "already completed" in finding.message
        for finding in report.findings
    )


def test_validate_complete_step_rules_merges_effective_runtime_state() -> None:
    progress = {
        "plannedSteps": ["step-01-authentication"],
        "completedSteps": [],
        "stepStatus": {
            "step-01-authentication": step_status(
                status="in_progress",
                tdd_phase="green",
                red=["uv run pytest tests/test_auth.py -q"],
                refactor_note="Refactor kept service boundaries intact.",
            )
        },
        "stepMetadata": {
            "step-01-authentication": step_metadata("code", "required")
        },
        "planningMetadata": {
            "stepDependencies": {"step-01-authentication": []}
        },
    }

    report = validate_complete_step_rules(
        progress=progress,
        step_id="step-01-authentication",
        summary="Authentication finished",
        red_evidence=[],
        green_evidence=["uv run pytest tests/test_auth.py -q"],
        refactor_note=None,
    )

    assert report.errors == []
    assert report.normalized["combined_red_evidence"] == [
        "uv run pytest tests/test_auth.py -q"
    ]
    assert report.normalized["combined_green_evidence"] == [
        "uv run pytest tests/test_auth.py -q"
    ]
    assert report.normalized["effective_refactor_note"] == "Refactor kept service boundaries intact."
    assert report.normalized["effective_tdd_phase"] == "completed"


def test_register_step_workflow_matches_gate_errors_for_unknown_cover(memory_project) -> None:
    memory_project.write_mvp_concept(variant="auth_short")
    memory_project.create_step_artifacts("step-01-auth")
    memory_project.sync(stage="mvp.plan")

    gate_payload = evaluate_gate_context(
        memory_project.project_path,
        "main",
        stage="mvp.plan",
        operation="register-step",
        step_id="step-01-auth",
        overrides={
            "step_kind": "code",
            "tdd_policy": "required",
            "depends_on": [],
            "covers": ["Unknown capability"],
        },
        include_ratification=False,
        record_history=False,
    )
    workflow_payload = register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        step_id="step-01-auth",
        covers=["Unknown capability"],
        step_kind="code",
    )

    assert gate_failure_messages(gate_payload) == workflow_payload["errors"]


def test_start_step_workflow_matches_gate_errors_for_incomplete_dependencies(memory_project) -> None:
    memory_project.write_mvp_concept(variant="auth_sessions")
    memory_project.create_step_artifacts("step-01-authentication")
    memory_project.create_step_artifacts("step-02-session-persistence")

    assert register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        step_id="step-01-authentication",
        covers=["Authentication"],
        step_kind="code",
    )["accepted"] is True
    assert register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        step_id="step-02-session-persistence",
        covers=["Sessions"],
        step_kind="code",
        depends_on=["step-01-authentication"],
    )["accepted"] is True
    memory_project.sync(stage="mvp.implement")

    gate_payload = evaluate_gate_context(
        memory_project.project_path,
        "main",
        stage="mvp.implement",
        operation="start-step",
        step_id="step-02-session-persistence",
        include_ratification=False,
        record_history=False,
    )
    workflow_payload = start_implementation_step(
        memory_project.project_path,
        "main",
        "mvp.implement",
        step_id="step-02-session-persistence",
        _evaluate_gate_context=_always_pass_gate,
        _gate_failure_messages=_no_gate_errors,
    )

    assert gate_failure_messages(gate_payload) == workflow_payload["errors"]


def test_checkpoint_step_workflow_matches_gate_errors_for_invalid_phase(memory_project) -> None:
    memory_project.write_mvp_concept(variant="auth")
    memory_project.create_step_artifacts("step-01-doc-refresh")

    assert register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        step_id="step-01-doc-refresh",
        covers=[],
        step_kind="non-code",
        tdd_policy="not-applicable",
    )["accepted"] is True
    memory_project.sync(stage="mvp.implement")

    gate_payload = evaluate_gate_context(
        memory_project.project_path,
        "main",
        stage="mvp.implement",
        operation="checkpoint-step",
        step_id="step-01-doc-refresh",
        overrides={
            "summary": "Documentation updated",
            "tdd_phase": "red",
            "red_evidence": [],
            "green_evidence": [],
            "refactor_note": None,
        },
        include_ratification=False,
        record_history=False,
    )
    workflow_payload = checkpoint_implementation_step(
        memory_project.project_path,
        "main",
        "mvp.implement",
        step_id="step-01-doc-refresh",
        summary="Documentation updated",
        tdd_phase="red",
        _evaluate_gate_context=_always_pass_gate,
        _gate_failure_messages=_no_gate_errors,
    )

    assert gate_failure_messages(gate_payload) == workflow_payload["errors"]


def test_complete_step_workflow_matches_gate_errors_for_missing_tdd_evidence(memory_project) -> None:
    memory_project.write_mvp_concept(variant="auth")
    memory_project.create_step_artifacts("step-01-authentication")

    assert register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        step_id="step-01-authentication",
        covers=["Authentication"],
        step_kind="code",
    )["accepted"] is True
    memory_project.sync(stage="mvp.implement")

    gate_payload = evaluate_gate_context(
        memory_project.project_path,
        "main",
        stage="mvp.implement",
        operation="complete-step",
        step_id="step-01-authentication",
        overrides={
            "summary": "Authentication implemented",
            "red_evidence": [],
            "green_evidence": [],
            "refactor_note": None,
        },
        include_ratification=False,
        record_history=False,
    )
    workflow_payload = complete_implementation_step(
        memory_project.project_path,
        "main",
        "mvp.implement",
        step_id="step-01-authentication",
        summary="Authentication implemented",
        _evaluate_gate_context=_always_pass_gate,
        _gate_failure_messages=_no_gate_errors,
    )

    assert gate_failure_messages(gate_payload) == workflow_payload["errors"]
