from __future__ import annotations

import json

from madspec_cli.features.gates.application.service import evaluate_gate_context
from madspec_cli.memory import ensure_memory_layout, get_memory_paths
from madspec_cli.memory.shared.storage import write_json

from tests.support import write_concept_markdown, write_madspec_config


def test_register_step_gate_reports_unknown_function_labels(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    write_madspec_config(project_path, "main")
    ensure_memory_layout(project_path, "main")
    paths = get_memory_paths(project_path, "main")
    write_concept_markdown(paths.branch_dir, variant="auth_short")

    payload = evaluate_gate_context(
        project_path,
        "main",
        stage="mvp.plan",
        operation="register-step",
        step_id="step-01-auth",
        overrides={
            "step_kind": "code",
            "tdd_policy": "required",
            "depends_on": [],
            "covers": ["Unknown function"],
        },
        include_ratification=False,
        record_history=False,
    )

    assert payload["overall_status"] == "blocked"
    assert any("unknown covered functions" in gate["message"] for gate in payload["gates"])


def test_complete_step_gate_requires_full_tdd_evidence_for_required_policy(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    write_madspec_config(project_path, "main")
    ensure_memory_layout(project_path, "main")
    paths = get_memory_paths(project_path, "main")
    write_json(
        paths.progress,
        {
            "currentImplementStep": "step-01-auth",
            "completedSteps": [],
            "plannedSteps": ["step-01-auth"],
            "stepStatus": {"step-01-auth": {"status": "in_progress", "completedAt": None, "tddPhase": "green", "redEvidence": [], "greenEvidence": [], "refactorNote": None}},
            "stepMetadata": {"step-01-auth": {"kind": "code", "tddPolicy": "required", "waiverReason": None}},
            "coversFunctions": {},
            "planningMetadata": {
                "lastPlannedStep": None,
                "planningPhase": "initial",
                "totalStepsEstimated": None,
                "stepDependencies": {},
                "progressMetrics": {
                    "p1Coverage": {"covered": 0, "total": 0, "percentage": 0},
                    "p2Coverage": {"covered": 0, "total": 0, "percentage": 0},
                    "p3Coverage": {"covered": 0, "total": 0, "percentage": 0},
                    "overallProgress": 0,
                },
            },
        },
    )

    payload = evaluate_gate_context(
        project_path,
        "main",
        stage="mvp.implement",
        operation="complete-step",
        step_id="step-01-auth",
        overrides={"summary": "Complete implementation"},
        include_ratification=False,
        record_history=False,
    )

    messages = [gate["message"] for gate in payload["gates"]]
    assert payload["overall_status"] == "blocked"
    assert any("must record redEvidence" in message for message in messages)
    assert any("must record greenEvidence" in message for message in messages)
    assert any("must record refactorNote" in message for message in messages)


def test_ratification_gate_is_added_separately_from_other_evaluators(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    write_madspec_config(project_path, "main")
    ensure_memory_layout(project_path, "main")
    paths = get_memory_paths(project_path, "main")
    paths.decision_log.write_text(
        json.dumps(
            {
                "stage": "review",
                "record_type": "checkpoint",
                "status": "validated",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    without_ratification = evaluate_gate_context(
        project_path,
        "main",
        stage="review",
        operation="validate",
        include_ratification=False,
        record_history=False,
    )
    with_ratification = evaluate_gate_context(
        project_path,
        "main",
        stage="review",
        operation="validate",
        include_ratification=True,
        record_history=False,
    )

    assert not any(gate["family"] == "stage_ratification" for gate in without_ratification["gates"])
    ratification_gate = next(gate for gate in with_ratification["gates"] if gate["family"] == "stage_ratification")
    assert ratification_gate["status"] == "passed"
