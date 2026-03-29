from __future__ import annotations

import json

from madspec_cli.memory import (
    capture_stage_memory,
    checkpoint_stage_memory,
    determine_next_step,
    ensure_memory_layout,
    register_planned_step,
    retrieve_memory_context,
    validate_branch_memory,
)
from madspec_cli.memory.shared.storage import write_json
from tests.memory_runtime.support import step_metadata, step_status


def test_determine_next_step_validates_candidate_and_selects_ready_step(memory_project) -> None:
    paths = memory_project.paths
    write_json(
        paths["progress"],
        {
            "currentImplementStep": None,
            "completedSteps": ["step-01-bootstrap"],
            "plannedSteps": ["step-01-bootstrap", "step-02-api", "step-03-ui"],
            "stepStatus": {
                "step-01-bootstrap": step_status(
                    status="completed",
                    completed_at="2026-03-10",
                    tdd_phase="completed",
                    red=["uv run pytest tests/test_bootstrap.py -q"],
                    green=["uv run pytest tests/test_bootstrap.py -q"],
                    refactor_note="No refactor needed.",
                ),
                "step-02-api": step_status(status="planned"),
                "step-03-ui": step_status(status="planned", tdd_phase="waived"),
            },
            "stepMetadata": {
                "step-01-bootstrap": step_metadata("code", "required"),
                "step-02-api": step_metadata("code", "required"),
                "step-03-ui": step_metadata("non-code", "waived", "UI polish step."),
            },
            "coversFunctions": {
                "step-01-bootstrap": {"p1": ["User authentication"], "p2": [], "p3": []},
                "step-02-api": {"p1": ["Session persistence"], "p2": [], "p3": []},
                "step-03-ui": {"p1": [], "p2": ["Profile customization"], "p3": []},
            },
            "planningMetadata": {
                "lastPlannedStep": "step-03-ui",
                "planningPhase": "incremental",
                "totalStepsEstimated": 3,
                "stepDependencies": {
                    "step-02-api": ["step-01-bootstrap"],
                    "step-03-ui": ["step-02-api"],
                },
                "progressMetrics": {
                    "p1Coverage": {"covered": 1, "total": 2, "percentage": 50},
                    "p2Coverage": {"covered": 0, "total": 1, "percentage": 0},
                    "p3Coverage": {"covered": 0, "total": 0, "percentage": 0},
                    "overallProgress": 40,
                },
            },
        },
    )
    memory_project.sync()

    candidate = determine_next_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        candidate_step="step-04-auth-flow",
        candidate_dependencies=["step-02-api"],
    )
    invalid_candidate = determine_next_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        candidate_step="bad-step-name",
        candidate_dependencies=["step-99-missing"],
    )
    selected = determine_next_step(memory_project.project_path, "main", "mvp.implement")

    assert candidate["accepted"] is True
    assert invalid_candidate["accepted"] is False
    assert any("must match step-XX-kebab-case" in error for error in invalid_candidate["errors"])
    assert selected["selected_step"] == "step-02-api"
    assert "step-03-ui" not in selected["executable_steps"]


def test_register_planned_step_updates_coverage_metrics(memory_project) -> None:
    paths = memory_project.paths
    memory_project.write_mvp_concept()
    memory_project.create_step_artifacts("step-01-authentication")
    memory_project.create_step_artifacts("step-02-session-persistence")

    first = register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        step_id="step-01-authentication",
        covers=["User authentication"],
        step_kind="code",
        summary="Plan authentication bootstrap",
    )
    second = register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        step_id="step-02-session-persistence",
        covers=["Session persistence", "Profile customization"],
        step_kind="code",
        depends_on=["step-01-authentication"],
    )

    progress = json.loads(paths["progress"].read_text(encoding="utf-8"))

    assert first["accepted"] is True
    assert second["accepted"] is True
    assert first["stepMetadata"] == {
        "kind": "code",
        "tddPolicy": "required",
        "waiverReason": None,
    }
    assert progress["planningMetadata"]["lastPlannedStep"] == "step-02-session-persistence"
    assert progress["planningMetadata"]["progressMetrics"]["p1Coverage"] == {
        "covered": 2,
        "total": 2,
        "percentage": 100,
    }
    assert progress["planningMetadata"]["progressMetrics"]["p2Coverage"] == {
        "covered": 1,
        "total": 1,
        "percentage": 100,
    }
    assert progress["planningMetadata"]["progressMetrics"]["overallProgress"] == 80
    assert progress["stepStatus"]["step-02-session-persistence"]["tddPhase"] == "not_started"
    assert progress["stepMetadata"]["step-02-session-persistence"]["tddPolicy"] == "required"
    assert progress["coversFunctions"]["step-02-session-persistence"]["p2"] == ["Profile customization"]
    assert validate_branch_memory(memory_project.project_path, "main") == []


def test_register_planned_step_supports_non_code_waiver(memory_project) -> None:
    paths = memory_project.paths
    memory_project.write_mvp_concept()
    memory_project.create_step_artifacts("step-01-design-polish")

    payload = register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        step_id="step-01-design-polish",
        covers=["User authentication"],
        step_kind="non-code",
        tdd_policy="waived",
        waiver_reason="UI polish does not add executable product logic.",
    )

    progress = json.loads(paths["progress"].read_text(encoding="utf-8"))

    assert payload["accepted"] is True
    assert progress["stepMetadata"]["step-01-design-polish"] == {
        "kind": "non-code",
        "tddPolicy": "waived",
        "waiverReason": "UI polish does not add executable product logic.",
    }
    assert progress["stepStatus"]["step-01-design-polish"]["tddPhase"] == "waived"


def test_register_planned_step_supports_non_code_without_coverage(memory_project) -> None:
    paths = memory_project.paths
    memory_project.write_mvp_concept()
    memory_project.create_step_artifacts("step-01-project-setup")

    payload = register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        step_id="step-01-project-setup",
        covers=[],
        step_kind="non-code",
        tdd_policy="not-applicable",
        summary="Bootstrap project structure before functional slices.",
    )

    progress = json.loads(paths["progress"].read_text(encoding="utf-8"))

    assert payload["accepted"] is True
    assert payload["covers"] == {"p1": [], "p2": [], "p3": []}
    assert progress["coversFunctions"]["step-01-project-setup"] == {"p1": [], "p2": [], "p3": []}
    assert progress["stepStatus"]["step-01-project-setup"]["tddPhase"] == "waived"


def test_register_planned_step_normalizes_markdown_catalog_labels(memory_project) -> None:
    paths = memory_project.paths
    (paths["branch_dir"] / "concept.md").write_text(
        """# Concept

### Приоритет 1
- **Создание поста в CRM**
""",
        encoding="utf-8",
    )
    memory_project.create_step_artifacts("step-01-posting-foundation")

    payload = register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        step_id="step-01-posting-foundation",
        covers=["Создание поста в CRM"],
        step_kind="code",
    )

    progress = json.loads(paths["progress"].read_text(encoding="utf-8"))

    assert payload["accepted"] is True
    assert progress["coversFunctions"]["step-01-posting-foundation"] == {
        "p1": ["Создание поста в CRM"],
        "p2": [],
        "p3": [],
    }


def test_register_planned_step_reports_known_labels_for_unknown_cover(memory_project) -> None:
    memory_project.write_mvp_concept()
    memory_project.create_step_artifacts("step-01-authentication")

    payload = register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        step_id="step-01-authentication",
        covers=["Unknown capability"],
        step_kind="code",
    )

    assert payload["accepted"] is False
    assert "mvp.concept.json" in payload["errors"][0]
    assert "User authentication" in payload["errors"][0]


def test_capture_retrieve_and_checkpoint_plan_stage(memory_project) -> None:
    paths = memory_project.paths
    memory_project.write_mvp_concept()
    memory_project.create_step_artifacts("step-01-authentication")

    register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        step_id="step-01-authentication",
        covers=["User authentication"],
        step_kind="code",
        title="Authentication foundation",
        summary="Create the first executable slice for sign-in and session bootstrapping.",
        related_artifacts=[".madspec/main/contracts/openapi.yaml"],
        size="medium",
        complexity="medium",
    )

    captured = capture_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.plan",
        plan_overview="Build thin vertical slices from authentication to profile settings.",
        planning_principles=[
            "Prefer executable vertical slices over layer-first decomposition.",
            "Keep each code step independently testable.",
        ],
        next_actions=["Plan session persistence after authentication foundation."],
        status="validated",
    )
    retrieved = retrieve_memory_context(memory_project.project_path, "main", "mvp.plan")
    retrieved_full = retrieve_memory_context(
        memory_project.project_path,
        "main",
        "mvp.plan",
        full_artifact=True,
    )
    checkpointed = checkpoint_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.plan",
        "Planning baseline ratified for implementation kickoff",
        evidence=[".madspec/main/implementation-plan.md"],
    )

    implementation_plan = (paths["branch_dir"] / "implementation-plan.md").read_text(encoding="utf-8")
    plan_state = json.loads(paths["plan_state"].read_text(encoding="utf-8"))

    assert captured["accepted"] is True
    assert retrieved["plan_status"]["is_complete"] is True
    assert retrieved["plan_status"]["counts"]["catalog_steps"] == 1
    assert retrieved_full["artifact_state"]["plan"]["planOverview"] == (
        "Build thin vertical slices from authentication to profile settings."
    )
    assert checkpointed["accepted"] is True
    assert "Authentication foundation" in implementation_plan
    assert "Planning baseline ratified for implementation kickoff" in implementation_plan
    assert plan_state["checkpointSummary"] == "Planning baseline ratified for implementation kickoff"


def test_ensure_memory_layout_migrates_plan_state_from_legacy_progress(memory_project) -> None:
    paths = memory_project.paths
    memory_project.write_mvp_concept()
    memory_project.create_step_artifacts("step-01-authentication")
    write_json(
        paths["progress"],
        {
            "currentImplementStep": None,
            "completedSteps": [],
            "plannedSteps": ["step-01-authentication"],
            "stepStatus": {"step-01-authentication": step_status(status="planned")},
            "stepMetadata": {"step-01-authentication": step_metadata("code", "required")},
            "coversFunctions": {"step-01-authentication": {"p1": ["User authentication"], "p2": [], "p3": []}},
            "planningMetadata": {
                "lastPlannedStep": "step-01-authentication",
                "planningPhase": "initial",
                "totalStepsEstimated": None,
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
    (paths["branch_dir"] / "implementation-plan.md").write_text(
        "# План реализации: Auth Demo\n\n## Обзор\nLegacy overview\n",
        encoding="utf-8",
    )
    paths["plan_state"].unlink()

    ensure_memory_layout(memory_project.project_path, "main")

    migrated = json.loads(paths["plan_state"].read_text(encoding="utf-8"))
    assert migrated["planOverview"] == "Legacy overview"
    assert migrated["stepCatalog"][0]["stepId"] == "step-01-authentication"
