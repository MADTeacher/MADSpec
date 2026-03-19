from __future__ import annotations

from madspec_cli.memory import capture_stage_memory, checkpoint_stage_memory, retrieve_memory_context, validate_branch_memory


def test_design_stage_retrieve_returns_design_status_and_full_artifact(memory_project) -> None:
    paths = memory_project.paths
    memory_project.seed_concept_for_design()
    memory_project.write_design_prototypes()

    captured = capture_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.design",
        summary="Captured design iteration",
        design_overview="A workspace-first web UI with focused transitions between booking, profile tuning, and exports.",
        platforms=["Web"],
        zones=[
            "operations::Operations::Daily scheduling workspace",
            "settings::Settings::Profile and export configuration",
        ],
        screens=[
            "schedule-board::Schedule board::operations::.madspec/main/ui-prototype/schedule-board.html::Shows upcoming bookings and reminder actions",
            "profile-studio::Profile studio::settings::.madspec/main/ui-prototype/profile-studio.html::Lets the user customize profile details",
            "export-hub::Export hub::settings::.madspec/main/ui-prototype/export-hub.html::Lets the user export summaries and settings",
        ],
        screen_features=[
            "schedule-board::p1::Booking workflow",
            "profile-studio::p2::Profile studio",
            "export-hub::p3::Export hub",
        ],
        flows=["manage-booking::Manage booking::Create and review a booking flow from one workspace"],
        flow_steps=[
            "manage-booking::schedule-board::Create booking::Open booking details with reminders",
            "manage-booking::profile-studio::Review profile::Confirm public profile details",
        ],
        flow_alternatives=["manage-booking::Skip profile review when no changes are needed"],
        navigation=[
            "schedule-board::profile-studio::Profile settings shortcut",
            "profile-studio::export-hub::Export settings CTA",
        ],
        platform_constraints=["Primary interactions must remain usable on narrow laptop screens"],
        screen_data=[
            "schedule-board::displayed::Upcoming bookings with reminder state",
            "profile-studio::input::Public display name",
        ],
        next_actions=["Review the latest prototype with the user"],
        status="validated",
    )
    retrieved = retrieve_memory_context(memory_project.project_path, "main", "mvp.design")

    assert captured["accepted"] is True
    assert retrieved["artifact_state"]["design"] is None
    assert retrieved["design_status"]["is_complete"] is True
    assert retrieved["design_status"]["counts"] == {
        "platforms": 1,
        "zones": 2,
        "screens": 3,
        "flows": 1,
        "navigation_links": 2,
        "platform_constraints": 1,
    }
    assert retrieved["design_status"]["uncovered_features"] == {"p1": [], "p2": [], "p3": []}
    assert retrieved["design_status"]["missing_prototype_files"] == []
    assert retrieved["decision_log"] == []

    checkpointed = checkpoint_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.design",
        "Design ratified for prototype review",
        evidence=[".madspec/main/ui-design.md", ".madspec/main/ui-prototype/index.html"],
    )
    retrieved_full = retrieve_memory_context(
        memory_project.project_path,
        "main",
        "mvp.design",
        full_artifact=True,
        include_history=True,
    )
    ui_design = (paths["branch_dir"] / "ui-design.md").read_text(encoding="utf-8")

    assert checkpointed["accepted"] is True
    assert retrieved_full["artifact_state"]["design"]["checkpointSummary"] == "Design ratified for prototype review"
    assert retrieved_full["artifact_state"]["design"]["revision"] == 1
    assert "## Точка входа для review" in ui_design
    assert "## Review Journeys" in ui_design
    assert "Schedule board" in ui_design
    assert "Manage booking" in ui_design
    assert "Storyboard path" in ui_design
    assert "Покрытие функций" not in ui_design
    assert "- P1:" not in ui_design
    assert validate_branch_memory(memory_project.project_path, "main") == []


def test_design_checkpoint_can_be_repeated_and_increments_revision(memory_project) -> None:
    memory_project.seed_concept_for_design()
    memory_project.write_design_prototypes()

    capture_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.design",
        design_overview="First design pass.",
        platforms=["Web"],
        zones=["operations::Operations::Daily scheduling workspace"],
        screens=[
            "schedule-board::Schedule board::operations::.madspec/main/ui-prototype/schedule-board.html::Shows upcoming bookings and reminder actions",
            "profile-studio::Profile studio::operations::.madspec/main/ui-prototype/profile-studio.html::Lets the user customize profile details",
            "export-hub::Export hub::operations::.madspec/main/ui-prototype/export-hub.html::Lets the user export summaries and settings",
        ],
        screen_features=[
            "schedule-board::p1::Booking workflow",
            "profile-studio::p2::Profile studio",
            "export-hub::p3::Export hub",
        ],
        flows=["manage-booking::Manage booking::Create and review a booking flow from one workspace"],
        flow_steps=["manage-booking::schedule-board::Create booking::Open booking details with reminders"],
        navigation=["schedule-board::profile-studio::Profile settings shortcut"],
        status="validated",
    )

    first_checkpoint = checkpoint_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.design",
        "Design version one",
        evidence=[".madspec/main/ui-design.md", ".madspec/main/ui-prototype/index.html"],
    )
    capture_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.design",
        design_overview="Second design pass with tighter information hierarchy.",
        navigation=["profile-studio::export-hub::Export settings CTA"],
        next_actions=["Validate export copy with the user"],
        status="validated",
    )
    second_checkpoint = checkpoint_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.design",
        "Design version two",
        evidence=[".madspec/main/ui-design.md", ".madspec/main/ui-prototype/index.html"],
    )
    retrieved_full = retrieve_memory_context(
        memory_project.project_path,
        "main",
        "mvp.design",
        full_artifact=True,
    )

    assert first_checkpoint["accepted"] is True
    assert second_checkpoint["accepted"] is True
    assert retrieved_full["artifact_state"]["design"]["revision"] == 2
    assert retrieved_full["artifact_state"]["design"]["checkpointSummary"] == "Design version two"


def test_validate_detects_out_of_sync_generated_ui_design(memory_project) -> None:
    paths = memory_project.paths
    memory_project.seed_concept_for_design()
    memory_project.write_design_prototypes()

    capture_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.design",
        design_overview="Design pass.",
        platforms=["Web"],
        zones=["operations::Operations::Daily scheduling workspace"],
        screens=[
            "schedule-board::Schedule board::operations::.madspec/main/ui-prototype/schedule-board.html::Shows upcoming bookings and reminder actions",
            "profile-studio::Profile studio::operations::.madspec/main/ui-prototype/profile-studio.html::Lets the user customize profile details",
            "export-hub::Export hub::operations::.madspec/main/ui-prototype/export-hub.html::Lets the user export summaries and settings",
        ],
        screen_features=[
            "schedule-board::p1::Booking workflow",
            "profile-studio::p2::Profile studio",
            "export-hub::p3::Export hub",
        ],
        flows=["manage-booking::Manage booking::Create and review a booking flow from one workspace"],
        flow_steps=["manage-booking::schedule-board::Create booking::Open booking details with reminders"],
        navigation=["schedule-board::profile-studio::Profile settings shortcut"],
        status="validated",
    )
    checkpoint_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.design",
        "Design ratified",
        evidence=[".madspec/main/ui-design.md", ".madspec/main/ui-prototype/index.html"],
    )

    design_path = paths["branch_dir"] / "ui-design.md"
    design_path.write_text("# manually edited\n", encoding="utf-8")

    errors = validate_branch_memory(memory_project.project_path, "main")

    assert any("ui-design.md is out of sync" in error for error in errors)


def test_validate_detects_missing_design_coverage_and_prototype_files(memory_project) -> None:
    paths = memory_project.paths
    memory_project.seed_concept_for_design()
    memory_project.write_design_prototypes()

    captured = capture_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.design",
        design_overview="Incomplete design pass.",
        platforms=["Web"],
        zones=["operations::Operations::Daily scheduling workspace"],
        screens=[
            "schedule-board::Schedule board::operations::.madspec/main/ui-prototype/schedule-board.html::Shows upcoming bookings and reminder actions"
        ],
        screen_features=["schedule-board::p1::Booking workflow"],
        flows=["manage-booking::Manage booking::Create and review a booking flow from one workspace"],
        flow_steps=["manage-booking::schedule-board::Create booking::Open booking details with reminders"],
        navigation=["schedule-board::schedule-board::Refresh board"],
        status="proposed",
    )
    (paths["branch_dir"] / "ui-prototype" / "schedule-board.html").unlink()

    errors = validate_branch_memory(memory_project.project_path, "main")

    assert captured["accepted"] is True
    assert any("design references missing prototype file" in error for error in errors)
    assert any("design coverage missing P2 concept feature 'Profile studio'" in error for error in errors)

