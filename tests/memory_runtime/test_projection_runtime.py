from __future__ import annotations

from madspec_cli.memory import capture_stage_memory, checkpoint_stage_memory, consolidate_branch_memory, retrieve_memory_context
from tests.support import write_madspec_config


def test_mvp_concept_on_clean_branch_materializes_only_concept_scope(tmp_path) -> None:
    project_path = tmp_path / "mvp-minimum"
    project_path.mkdir()
    write_madspec_config(project_path, "main")

    captured = capture_stage_memory(
        project_path,
        "main",
        "mvp.concept",
        project_name="Scheduler MVP",
        system_overview="Coordinate bookings from one place.",
        audiences=["Freelancers"],
        scenarios=["Create bookings"],
        pain_points=["Follow-ups are manual"],
        feature_p1=["Booking workflow::Create bookings and reminders"],
        status="validated",
    )

    assert captured["accepted"] is True

    branch_dir = project_path / ".madspec" / "main"
    assert (branch_dir / "concept.md").exists()
    assert (branch_dir / "planning-context-cache.md").exists()
    assert (branch_dir / "project-context.md").exists()
    assert not (branch_dir / "project-analysis.md").exists()
    assert not (branch_dir / "feature-context.md").exists()
    assert not (branch_dir / "implementation-plan.md").exists()
    assert not (branch_dir / "contracts" / "openapi.yaml").exists()


def test_full_consolidation_materializes_feature_and_mvp_artifacts(memory_project) -> None:
    memory_project.seed_concept_for_design()
    memory_project.write_design_prototypes()

    capture_stage_memory(
        memory_project.project_path,
        "main",
        "feature.init",
        summary="Analyze audit log feature",
        feature_goal="Add audit log timeline",
        problem="Users cannot inspect account activity",
        expected_outcome="Users can review important account events",
        project_type="web",
        framework="FastAPI + Vue",
        feature_p1=["AUD-1::Audit timeline::Show recent account activity"],
        modified_files=["src/api/audit.py::Expose audit timeline endpoint::AUD-1"],
        new_files=["src/services/audit_reader.py::Read audit events::AUD-1"],
        status="validated",
    )
    checkpoint_stage_memory(
        memory_project.project_path,
        "main",
        "feature.init",
        "Feature init ratified for audit log timeline",
    )

    generated = consolidate_branch_memory(memory_project.project_path, "main", full=True)

    assert generated
    assert (memory_project.branch_dir / "concept.md").exists()
    assert (memory_project.branch_dir / "project-analysis.md").exists()
    assert (memory_project.branch_dir / "feature-context.md").exists()
    assert (memory_project.branch_dir / "project-context.md").exists()


def test_retrieve_review_context_keeps_policy_context_and_history(memory_project) -> None:
    capture_stage_memory(
        memory_project.project_path,
        "main",
        "review",
        summary="Captured review findings",
        facts=["Naming is inconsistent across modules"],
        decisions=["Normalize terminology before checkpoint"],
        status="validated",
    )
    checkpoint_stage_memory(
        memory_project.project_path,
        "main",
        "review",
        "Review findings ratified",
    )

    payload = retrieve_memory_context(
        memory_project.project_path,
        "main",
        "review",
        include_history=True,
        full_artifact=True,
    )

    assert "required" in payload["policy_context"]
    assert payload["decision_log"]
    assert payload["artifact_state"]["policy"] is not None
