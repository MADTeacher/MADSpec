from __future__ import annotations

import json

from madspec_cli.memory import (
    capture_stage_memory,
    checkpoint_stage_memory,
    consolidate_branch_memory,
    retrieve_memory_context,
    validate_branch_memory,
)


def test_checkpoint_stage_memory_updates_active_session_and_project_context(memory_project) -> None:
    paths = memory_project.paths

    captured = capture_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.tech",
        summary="Captured tech stack direction",
        project_type="Web application",
        stack_overview="A Python-first stack optimized for rapid MVP delivery and simple deployment.",
        requirements=["Need web delivery and fast iteration"],
        preferences=["Prefer a Python backend and server-rendered UI"],
        tech_constraints=["Python version must remain 3.13"],
        stack_components=[
            "language::Python::3.13::Primary language for backend and tooling",
            "frontend::HTMX::2.x::Keep frontend interactions server-driven and lightweight",
            "backend::FastAPI::0.115::Provide async HTTP APIs with strong typing",
            "database::PostgreSQL::16::Reliable relational storage for bookings and reminders",
            "unit-testing::pytest::8.x::Fast unit and integration test execution",
            "build::Docker::27.x::Standardize local and deployment builds",
        ],
        libraries=["backend::SQLAlchemy::2.x::ORM and SQL composition"],
        code_organization="monorepo::feature-first::modular service boundaries::Keep product slices close while preserving clear ownership",
        alternatives=["frontend::React SPA::Too much client complexity for the first MVP iteration"],
        evidence=[".madspec/main/tech-stack.md"],
        questions=["Do we need offline mode?"],
        pending_actions=["Proceed to mvp.architecture"],
        next_actions=["Proceed to mvp.architecture"],
    )
    assert captured["accepted"] is True

    payload = checkpoint_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.tech",
        "Tech stack approved for MVP",
        evidence=[".madspec/main/tech-stack.md"],
    )

    assert payload["accepted"] is True
    active_session = json.loads(paths["active_session"].read_text(encoding="utf-8"))
    assert active_session["stage"] == "mvp.tech"
    assert active_session["active_goal"] == "Tech stack approved for MVP"
    assert active_session["current_hypotheses"][0].startswith("Stack component language: Python 3.13")

    project_context = (paths["branch_dir"] / "project-context.md").read_text(encoding="utf-8")
    assert "Current stage: `mvp.tech`" in project_context
    assert "Active goal: `Tech stack approved for MVP`" in project_context
    assert "Tech checkpoint summary: `Tech stack approved for MVP`" in project_context

    retrieved = retrieve_memory_context(memory_project.project_path, "main", "mvp.tech", limit=10)
    assert retrieved["artifact_state"]["tech"] is None
    assert retrieved["tech_status"]["is_complete"] is True
    assert retrieved["tech_status"]["selected_slots"] == [
        "backend",
        "build",
        "database",
        "frontend",
        "language",
        "unit-testing",
    ]
    assert retrieved["decision_log"] == []
    fact_summaries = {item["summary"] for item in retrieved["semantic"]["facts"]}
    decision_summaries = {item["summary"] for item in retrieved["semantic"]["decisions"]}
    contract_summaries = {item["summary"] for item in retrieved["semantic"]["contracts"]}
    assert "Prefer a Python backend and server-rendered UI" in fact_summaries
    assert "Need web delivery and fast iteration" in fact_summaries
    assert any("FastAPI" in item for item in decision_summaries)
    assert "Python version must remain 3.13" in contract_summaries

    retrieved_full = retrieve_memory_context(
        memory_project.project_path,
        "main",
        "mvp.tech",
        full_artifact=True,
        include_history=True,
    )
    assert retrieved_full["artifact_state"]["tech"]["checkpointSummary"] == "Tech stack approved for MVP"
    assert retrieved_full["artifact_state"]["tech"]["revision"] == 1
    tech_stack = (paths["branch_dir"] / "tech-stack.md").read_text(encoding="utf-8")
    assert "A Python-first stack optimized for rapid MVP delivery and simple deployment." in tech_stack
    assert "FastAPI" in tech_stack


def test_validate_reports_tech_stack_drift_and_consolidate_rewrites_it(memory_project) -> None:
    paths = memory_project.paths

    capture_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.tech",
        project_type="API service",
        stack_overview="A compact backend-only stack for predictable service delivery.",
        stack_components=[
            "language::Python::3.13::Primary service language",
            "backend::FastAPI::0.115::HTTP service runtime",
            "unit-testing::pytest::8.x::Backend test runner",
            "build::Docker::27.x::Build and runtime packaging",
        ],
        code_organization="monorepo::layer-first::single service package::Keep service structure explicit for a small API",
        evidence=[".madspec/main/tech-stack.md"],
    )
    checkpoint_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.tech",
        "API stack ratified",
        evidence=[".madspec/main/tech-stack.md"],
    )

    tech_stack_path = paths["branch_dir"] / "tech-stack.md"
    original_text = tech_stack_path.read_text(encoding="utf-8")
    tech_stack_path.write_text("# Manual drift\n", encoding="utf-8")

    errors = validate_branch_memory(memory_project.project_path, "main")
    assert "tech-stack.md is out of sync with memory/stages/mvp.tech.json" in errors

    consolidate_branch_memory(memory_project.project_path, "main")
    rewritten_text = tech_stack_path.read_text(encoding="utf-8")
    assert rewritten_text == original_text

