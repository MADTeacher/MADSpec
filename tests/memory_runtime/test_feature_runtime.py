from __future__ import annotations

from tests.support import write_madspec_config

from madspec_cli.memory import capture_stage_memory, checkpoint_stage_memory, register_planned_step, retrieve_memory_context


def test_feature_init_retrieve_returns_feature_status_and_generated_views(memory_project) -> None:
    paths = memory_project.paths

    captured = capture_stage_memory(
        memory_project.project_path,
        "main",
        "feature.init",
        summary="Analyze Stripe payments integration",
        feature_goal="Add Stripe checkout flow",
        problem="Users cannot pay online",
        expected_outcome="Users can create a payment session and complete checkout",
        project_type="web",
        framework="FastAPI + React",
        structure_notes=["Monorepo with api and web packages"],
        feature_p1=["F01::Checkout session::Create and open Stripe checkout session"],
        existing_modules=["payments service::src/payments/service.py::Existing payment orchestration"],
        modified_files=["src/payments/api.py::Add checkout endpoint::F01"],
        new_files=["src/payments/stripe_client.py::Stripe gateway adapter::F01"],
        interface_contracts=["POST /api/payments/checkout returns checkout url"],
        dependencies=["external::stripe::Hosted checkout provider"],
        risks=["Webhook signature validation must be enforced"],
        recommendations=["Reuse existing billing service abstractions"],
        tech_notes=["Frontend already uses React Query"],
        architecture_notes=["Add provider adapter layer instead of inline SDK calls"],
        next_actions=["Proceed to feature.plan"],
        status="validated",
    )
    checkpointed = checkpoint_stage_memory(
        memory_project.project_path,
        "main",
        "feature.init",
        "Feature init ratified for Stripe checkout",
    )
    retrieved = retrieve_memory_context(memory_project.project_path, "main", "feature.init", full_artifact=True)

    assert captured["accepted"] is True
    assert checkpointed["accepted"] is True
    assert retrieved["feature_init_status"]["is_complete"] is True
    assert retrieved["feature_init_status"]["functions_by_priority"]["p1"] == ["F01"]
    assert retrieved["artifact_state"]["feature_init"]["featureGoal"] == "Add Stripe checkout flow"
    assert (paths["branch_dir"] / "project-analysis.md").exists()
    assert (paths["branch_dir"] / "feature-context.md").exists()


def test_register_step_updates_feature_plan_state(memory_project) -> None:
    capture_stage_memory(
        memory_project.project_path,
        "main",
        "feature.init",
        summary="Analyze profile settings feature",
        feature_goal="Add profile settings",
        problem="Users cannot edit profile settings",
        expected_outcome="Users can update profile fields safely",
        project_type="web",
        framework="Django",
        feature_p1=["F01::Profile settings::Update profile fields"],
        modified_files=["src/profile/views.py::Expose settings endpoint::F01"],
        new_files=["src/profile/service.py::Settings orchestration::F01"],
        status="validated",
    )
    checkpoint_stage_memory(
        memory_project.project_path,
        "main",
        "feature.init",
        "Feature init ratified for profile settings",
    )

    memory_project.create_step_artifacts("step-01-profile-settings")
    payload = register_planned_step(
        memory_project.project_path,
        "main",
        "feature.plan",
        step_id="step-01-profile-settings",
        covers=["F01"],
        step_kind="code",
        title="Profile settings endpoint",
        summary="Implement settings endpoint and service",
    )
    retrieved = retrieve_memory_context(memory_project.project_path, "main", "feature.plan", full_artifact=True)

    assert payload["accepted"] is True
    assert retrieved["feature_plan_status"]["planned_steps"] == 1
    assert retrieved["artifact_state"]["plan"]["stepCatalog"][0]["stepId"] == "step-01-profile-settings"


def test_feature_init_on_clean_branch_materializes_only_feature_minimum(tmp_path) -> None:
    project_path = tmp_path / "feature-minimum"
    project_path.mkdir()
    write_madspec_config(project_path, "main")

    captured = capture_stage_memory(
        project_path,
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

    assert captured["accepted"] is True

    branch_dir = project_path / ".madspec" / "main"
    stages_dir = branch_dir / "memory" / "stages"

    assert (stages_dir / "feature.init.json").exists()
    assert not (stages_dir / "mvp.concept.json").exists()
    assert not (stages_dir / "mvp.design.json").exists()
    assert not (stages_dir / "mvp.tech.json").exists()
    assert not (stages_dir / "mvp.architecture.json").exists()
    assert not (stages_dir / "mvp.plan.json").exists()
    assert not (stages_dir / "feature.plan.json").exists()

    assert (branch_dir / "project-analysis.md").exists()
    assert (branch_dir / "feature-context.md").exists()
    assert (branch_dir / "tech-stack.md").exists()
    assert (branch_dir / "architecture.md").exists()
    assert (branch_dir / "project-context.md").exists()

    assert not (branch_dir / "concept.md").exists()
    assert not (branch_dir / "ui-design.md").exists()
    assert not (branch_dir / "data-model.md").exists()
    assert not (branch_dir / "implementation-plan.md").exists()
    assert not (branch_dir / "planning-context-cache.md").exists()
    assert not (branch_dir / "review.md").exists()
    assert not (branch_dir / "improvements.md").exists()
    assert not (branch_dir / "security-audit.md").exists()
    assert not (branch_dir / "contracts" / "openapi.yaml").exists()


def test_feature_plan_materializes_plan_artifacts_lazily_after_feature_init(tmp_path) -> None:
    project_path = tmp_path / "feature-plan-lazy"
    project_path.mkdir()
    write_madspec_config(project_path, "main")

    capture_stage_memory(
        project_path,
        "main",
        "feature.init",
        summary="Analyze billing alerts feature",
        feature_goal="Add billing alerts",
        problem="Teams miss failed payment events",
        expected_outcome="Teams receive clear billing alerts",
        project_type="web",
        framework="Django + HTMX",
        feature_p1=["ALERT-1::Billing alerts::Notify on failed payment"],
        modified_files=["src/billing/views.py::Add alerts endpoint::ALERT-1"],
        new_files=["src/billing/alerts.py::Alert orchestration::ALERT-1"],
        status="validated",
    )
    checkpoint_stage_memory(
        project_path,
        "main",
        "feature.init",
        "Feature init ratified for billing alerts",
    )

    branch_dir = project_path / ".madspec" / "main"
    assert not (branch_dir / "memory" / "stages" / "feature.plan.json").exists()
    assert not (branch_dir / "implementation-plan.md").exists()
    assert not (branch_dir / "planning-context-cache.md").exists()

    payload = register_planned_step(
        project_path,
        "main",
        "feature.plan",
        step_id="step-01-billing-alerts",
        covers=["ALERT-1"],
        step_kind="code",
        title="Billing alerts delivery",
        summary="Register the first billing-alert implementation step",
    )

    assert payload["accepted"] is True
    assert (branch_dir / "memory" / "stages" / "feature.plan.json").exists()
    assert (branch_dir / "implementation-plan.md").exists()
    assert (branch_dir / "planning-context-cache.md").exists()
