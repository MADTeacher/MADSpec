from __future__ import annotations

import json

from madspec_cli.memory import (
    consolidate_branch_memory,
    ensure_memory_layout,
    register_planned_step,
    retrieve_memory_context,
    validate_branch_memory,
)
from madspec_cli.memory.implementation import (
    checkpoint_implementation_step,
    complete_implementation_step,
    start_implementation_step,
)
from madspec_cli.memory.shared.storage import write_json
from tests.memory_runtime.support import step_metadata, step_status


def test_implementation_lifecycle_updates_memory_incrementally(memory_project) -> None:
    paths = memory_project.paths
    memory_project.write_mvp_concept()
    memory_project.create_step_artifacts("step-01-authentication")
    memory_project.create_step_artifacts("step-02-session-persistence")

    register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        step_id="step-01-authentication",
        covers=["User authentication"],
        step_kind="code",
    )
    register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        step_id="step-02-session-persistence",
        covers=["Session persistence"],
        step_kind="code",
        depends_on=["step-01-authentication"],
    )

    started = start_implementation_step(memory_project.project_path, "main", "mvp.implement")
    red = checkpoint_implementation_step(
        memory_project.project_path,
        "main",
        "mvp.implement",
        step_id="step-01-authentication",
        summary="Focused auth test is red",
        tdd_phase="red",
        red_evidence=["uv run pytest tests/test_auth.py -q"],
    )
    green = checkpoint_implementation_step(
        memory_project.project_path,
        "main",
        "mvp.implement",
        step_id="step-01-authentication",
        summary="Auth test is green",
        tdd_phase="green",
        green_evidence=["uv run pytest tests/test_auth.py -q"],
        refactor_note="No refactor needed.",
    )
    completed = complete_implementation_step(
        memory_project.project_path,
        "main",
        "mvp.implement",
        step_id="step-01-authentication",
        summary="Authentication flow implemented and validated",
        facts=["Authentication now persists session cookies"],
        decisions=["Keep session middleware in the HTTP layer"],
        evidence=["tests/test_auth.py"],
    )

    progress = json.loads(paths["progress"].read_text(encoding="utf-8"))
    active_session = json.loads(paths["active_session"].read_text(encoding="utf-8"))
    retrieved = retrieve_memory_context(
        memory_project.project_path,
        "main",
        "mvp.implement",
        step_id="step-01-authentication",
    )
    implementation_context = paths["branch_dir"] / "steps" / "step-01-authentication" / "implementation-context.md"

    assert started["accepted"] is True
    assert started["step_id"] == "step-01-authentication"
    assert red["accepted"] is True
    assert green["accepted"] is True
    assert completed["accepted"] is True
    assert completed["next_step"] == "step-02-session-persistence"
    assert progress["completedSteps"] == ["step-01-authentication"]
    assert progress["currentImplementStep"] == "step-02-session-persistence"
    assert progress["stepStatus"]["step-01-authentication"]["status"] == "completed"
    assert progress["stepStatus"]["step-01-authentication"]["tddPhase"] == "completed"
    assert progress["stepStatus"]["step-01-authentication"]["redEvidence"] == [
        "uv run pytest tests/test_auth.py -q"
    ]
    assert progress["stepStatus"]["step-01-authentication"]["greenEvidence"] == [
        "uv run pytest tests/test_auth.py -q"
    ]
    assert active_session["current_step"] == "step-02-session-persistence"
    assert retrieved["step"]["status"]["status"] == "completed"
    assert retrieved["semantic"]["facts"][0]["summary"] == "Authentication now persists session cookies"
    assert retrieved["semantic"]["decisions"][0]["summary"] == "Keep session middleware in the HTTP layer"
    assert implementation_context.exists()
    implementation_text = implementation_context.read_text(encoding="utf-8")
    assert "# Implementation Context: step-01-authentication" in implementation_text
    assert "Generated from structured memory records." in implementation_text
    assert "TDD phase: `completed`" in implementation_text
    assert validate_branch_memory(memory_project.project_path, "main") == []


def test_ensure_memory_layout_normalizes_legacy_tdd_fields(memory_project) -> None:
    paths = memory_project.paths
    memory_project.write_mvp_concept()
    write_json(
        paths["progress"],
        {
            "currentImplementStep": None,
            "completedSteps": ["step-01-bootstrap"],
            "plannedSteps": ["step-01-bootstrap", "step-02-auth"],
            "stepStatus": {
                "step-01-bootstrap": {"status": "completed", "completedAt": "2026-03-10"},
                "step-02-auth": {"status": "planned", "completedAt": None},
            },
            "coversFunctions": {
                "step-01-bootstrap": {"p1": ["User authentication"], "p2": [], "p3": []},
                "step-02-auth": {"p1": ["Session persistence"], "p2": [], "p3": []},
            },
            "planningMetadata": {
                "lastPlannedStep": "step-02-auth",
                "planningPhase": "incremental",
                "totalStepsEstimated": 2,
                "stepDependencies": {"step-02-auth": ["step-01-bootstrap"]},
                "progressMetrics": {
                    "p1Coverage": {"covered": 1, "total": 2, "percentage": 50},
                    "p2Coverage": {"covered": 0, "total": 1, "percentage": 0},
                    "p3Coverage": {"covered": 0, "total": 1, "percentage": 0},
                    "overallProgress": 25,
                },
            },
        },
    )

    ensure_memory_layout(memory_project.project_path, "main")
    progress = json.loads(paths["progress"].read_text(encoding="utf-8"))

    assert progress["stepMetadata"]["step-01-bootstrap"] == {
        "kind": "non-code",
        "tddPolicy": "waived",
        "waiverReason": "Legacy step migrated without recorded TDD evidence.",
    }
    assert progress["stepMetadata"]["step-02-auth"] == {
        "kind": "code",
        "tddPolicy": "required",
        "waiverReason": None,
    }
    assert progress["stepStatus"]["step-01-bootstrap"]["tddPhase"] == "waived"
    assert progress["stepStatus"]["step-02-auth"]["tddPhase"] == "not_started"


def test_ensure_memory_layout_normalizes_legacy_coverage_shape(memory_project) -> None:
    paths = memory_project.paths
    memory_project.write_mvp_concept()
    write_json(
        paths["progress"],
        {
            "currentImplementStep": None,
            "completedSteps": [],
            "plannedSteps": ["step-01-bootstrap"],
            "stepStatus": {
                "step-01-bootstrap": {"status": "planned", "tddPhase": "not_started"}
            },
            "stepMetadata": {
                "step-01-bootstrap": step_metadata("non-code", "not-applicable")
            },
            "coversFunctions": {
                "step-01-bootstrap": []
            },
            "planningMetadata": {
                "lastPlannedStep": "step-01-bootstrap",
                "planningPhase": "initial",
                "totalStepsEstimated": 1,
                "stepDependencies": {},
                "progressMetrics": {
                    "p1Coverage": {"covered": 99, "total": 0, "percentage": 99},
                    "p2Coverage": {"covered": 99, "total": 0, "percentage": 99},
                    "p3Coverage": {"covered": 99, "total": 0, "percentage": 99},
                    "overallProgress": 99,
                },
            },
        },
    )

    ensure_memory_layout(memory_project.project_path, "main")
    memory_project.sync()
    progress = json.loads(paths["progress"].read_text(encoding="utf-8"))

    assert progress["coversFunctions"]["step-01-bootstrap"] == {"p1": [], "p2": [], "p3": []}
    assert progress["planningMetadata"]["progressMetrics"] == {
        "p1Coverage": {"covered": 0, "total": 2, "percentage": 0},
        "p2Coverage": {"covered": 0, "total": 1, "percentage": 0},
        "p3Coverage": {"covered": 0, "total": 1, "percentage": 0},
        "overallProgress": 0,
    }
    assert validate_branch_memory(memory_project.project_path, "main") == []


def test_validate_requires_completed_code_step_to_finish_tdd_cycle(memory_project) -> None:
    paths = memory_project.paths
    memory_project.write_mvp_concept()
    write_json(
        paths["progress"],
        {
            "currentImplementStep": None,
            "completedSteps": ["step-01-authentication"],
            "plannedSteps": ["step-01-authentication"],
            "stepStatus": {
                "step-01-authentication": step_status(
                    status="completed",
                    completed_at="2026-03-10",
                    tdd_phase="green",
                    red=["uv run pytest tests/test_auth.py -q"],
                    green=["uv run pytest tests/test_auth.py -q"],
                    refactor_note="No refactor needed.",
                )
            },
            "stepMetadata": {
                "step-01-authentication": step_metadata("code", "required")
            },
            "coversFunctions": {
                "step-01-authentication": {"p1": ["User authentication"], "p2": [], "p3": []}
            },
            "planningMetadata": {
                "lastPlannedStep": "step-01-authentication",
                "planningPhase": "incremental",
                "totalStepsEstimated": 1,
                "stepDependencies": {"step-01-authentication": []},
                "progressMetrics": {
                    "p1Coverage": {"covered": 1, "total": 2, "percentage": 50},
                    "p2Coverage": {"covered": 0, "total": 1, "percentage": 0},
                    "p3Coverage": {"covered": 0, "total": 1, "percentage": 0},
                    "overallProgress": 25,
                },
            },
        },
    )

    errors = validate_branch_memory(memory_project.project_path, "main")

    assert any("must have tddPhase='completed'" in error for error in errors)


def test_validate_requires_waiver_reason_for_waived_step(memory_project) -> None:
    paths = memory_project.paths
    memory_project.write_mvp_concept()
    write_json(
        paths["progress"],
        {
            "currentImplementStep": None,
            "completedSteps": [],
            "plannedSteps": ["step-01-ui-polish"],
            "stepStatus": {
                "step-01-ui-polish": step_status(
                    status="planned",
                    tdd_phase="waived",
                )
            },
            "stepMetadata": {
                "step-01-ui-polish": step_metadata("non-code", "waived")
            },
            "coversFunctions": {
                "step-01-ui-polish": {"p1": ["User authentication"], "p2": [], "p3": []}
            },
            "planningMetadata": {
                "lastPlannedStep": "step-01-ui-polish",
                "planningPhase": "incremental",
                "totalStepsEstimated": 1,
                "stepDependencies": {"step-01-ui-polish": []},
                "progressMetrics": {
                    "p1Coverage": {"covered": 1, "total": 2, "percentage": 50},
                    "p2Coverage": {"covered": 0, "total": 1, "percentage": 0},
                    "p3Coverage": {"covered": 0, "total": 1, "percentage": 0},
                    "overallProgress": 25,
                },
            },
        },
    )

    errors = validate_branch_memory(memory_project.project_path, "main")

    assert any("waiverReason is required" in error for error in errors)
