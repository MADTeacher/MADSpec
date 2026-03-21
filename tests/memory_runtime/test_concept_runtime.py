from __future__ import annotations

import json

from madspec_cli.memory import (
    capture_stage_memory,
    checkpoint_stage_memory,
    retrieve_memory_context,
    validate_branch_memory,
)
from madspec_cli.memory.stages.concept.state import load_concept_state, save_concept_state


def test_load_concept_state_repairs_char_split_pain_points(memory_project) -> None:
    paths = memory_project.paths
    broken_state = {
        "schemaVersion": 1,
        "projectName": "Repair Existing State",
        "systemOverview": "A concept state with broken pain points.",
        "createdAt": "2026-03-15T00:00:00+00:00",
        "ratifiedAt": None,
        "updatedAt": "2026-03-15T00:00:00+00:00",
        "revision": 0,
        "audiences": ["Developers"],
        "scenarios": ["Capture JSON payloads"],
        "painPoints": list("Manual setup is slow"),
        "features": {
            "p1": [{"name": "CLI Guardrail", "description": "Repair broken text lists"}],
            "p2": [],
            "p3": [],
        },
        "constraints": [],
        "assumptions": [],
        "nextActions": [],
        "checkpointSummary": "",
    }
    paths["concept_state"].write_text(json.dumps(broken_state, ensure_ascii=False) + "\n", encoding="utf-8")

    loaded = load_concept_state(paths["concept_state"])
    assert loaded["painPoints"] == ["Manual setup is slow"]

    save_concept_state(paths["concept_state"], loaded)
    persisted = json.loads(paths["concept_state"].read_text(encoding="utf-8"))
    assert persisted["painPoints"] == ["Manual setup is slow"]


def test_capture_stage_memory_accumulates_context_before_checkpoint(memory_project) -> None:
    paths = memory_project.paths

    captured = capture_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.concept",
        summary="Captured audience and pain points during discovery",
        project_name="MVP scheduling assistant",
        system_overview="System helps freelancers manage bookings and reminders from one interface.",
        audiences=["Freelancers scheduling appointments"],
        scenarios=["Create, move, and confirm appointments from one calendar"],
        pain_points=["Manual follow-ups lead to missed appointments"],
        feature_p1=["Booking workflow::Create bookings and send reminders"],
        assumptions=["Users already coordinate appointments in messengers or spreadsheets"],
        next_actions=["Proceed to mvp.design"],
        questions=["Do we need team scheduling in MVP?"],
        pending_actions=["Clarify notification constraints"],
        evidence=[".madspec/main/concept.md"],
        status="validated",
    )
    retrieved_before = retrieve_memory_context(memory_project.project_path, "main", "mvp.concept")
    checkpointed = checkpoint_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.concept",
        "Concept ratified after incremental discovery",
        evidence=[".madspec/main/concept.md"],
    )
    retrieved_after = retrieve_memory_context(memory_project.project_path, "main", "mvp.concept")
    retrieved_full_after = retrieve_memory_context(
        memory_project.project_path,
        "main",
        "mvp.concept",
        full_artifact=True,
        include_history=True,
    )

    assert captured["accepted"] is True
    assert retrieved_before["active_session"]["open_questions"] == ["Do we need team scheduling in MVP?"]
    assert retrieved_before["artifact_state"]["concept"] is None
    assert retrieved_before["concept_status"]["is_complete"] is True
    assert retrieved_before["concept_status"]["missing_required_fields"] == []
    assert retrieved_before["concept_status"]["counts"]["p1_features"] == 1
    assert retrieved_before["decision_log"] == []
    assert checkpointed["accepted"] is True
    assert checkpointed["used_existing_stage_memory"] is True
    assert retrieved_after["artifact_state"]["concept"] is None
    assert retrieved_after["concept_status"]["last_checkpoint_summary"] == "Concept ratified after incremental discovery"
    assert retrieved_after["concept_status"]["revision"] == 1
    assert retrieved_full_after["artifact_state"]["concept"]["checkpointSummary"] == "Concept ratified after incremental discovery"
    assert retrieved_full_after["artifact_state"]["concept"]["revision"] == 1
    assert retrieved_full_after["decision_log"] != []
    concept_text = (paths["branch_dir"] / "concept.md").read_text(encoding="utf-8")
    assert "## Общее описание системы" in concept_text
    assert "System helps freelancers manage bookings and reminders from one interface." in concept_text
    assert validate_branch_memory(memory_project.project_path, "main") == []


def test_retrieve_memory_context_returns_concept_status_for_partial_concept(memory_project) -> None:
    capture_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.concept",
        project_name="MVP scheduling assistant",
        audiences=["Freelancers"],
        questions=["Q1", "Q2", "Q3", "Q4"],
        status="validated",
    )

    retrieved = retrieve_memory_context(memory_project.project_path, "main", "mvp.concept")

    assert retrieved["artifact_state"]["concept"] is None
    assert retrieved["concept_status"]["is_complete"] is False
    assert retrieved["concept_status"]["missing_required_fields"] == [
        "systemOverview",
        "scenarios",
        "painPoints",
        "features.p1",
    ]
    assert retrieved["concept_status"]["filled_fields"] == ["projectName", "audiences"]
    assert retrieved["active_session"]["open_questions"] == ["Q1", "Q2", "Q3"]
    assert retrieved["concept_status"]["counts"] == {
        "audiences": 1,
        "scenarios": 0,
        "pain_points": 0,
        "p1_features": 0,
        "p2_features": 0,
        "p3_features": 0,
        "constraints": 0,
        "assumptions": 0,
        "next_actions": 0,
    }


def test_retrieve_memory_context_skips_history_for_concept_by_default(memory_project) -> None:
    capture_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.concept",
        project_name="MVP scheduling assistant",
        system_overview="System helps freelancers manage bookings.",
        audiences=["Freelancers"],
        scenarios=["Book client meetings"],
        pain_points=["Manual follow-ups are slow"],
        feature_p1=["Booking workflow::Create bookings and reminders"],
        questions=["Q1"],
        status="validated",
    )

    retrieved = retrieve_memory_context(memory_project.project_path, "main", "mvp.concept")

    assert retrieved["decision_log"] == []
    assert retrieved["episodes"] == []
    assert len(retrieved["semantic"]["facts"]) >= 1
    assert retrieved["semantic"]["decisions"] != []


def test_retrieve_memory_context_includes_history_when_requested_for_concept(memory_project) -> None:
    capture_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.concept",
        project_name="MVP scheduling assistant",
        system_overview="System helps freelancers manage bookings.",
        audiences=["Freelancers"],
        scenarios=["Book client meetings"],
        pain_points=["Manual follow-ups are slow"],
        feature_p1=["Booking workflow::Create bookings and reminders"],
        questions=["Q1"],
        status="validated",
    )

    retrieved = retrieve_memory_context(
        memory_project.project_path,
        "main",
        "mvp.concept",
        include_history=True,
    )

    assert len(retrieved["decision_log"]) == 1
    assert retrieved["episodes"] == []


def test_validate_detects_out_of_sync_generated_concept(memory_project) -> None:
    capture_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.concept",
        project_name="MVP scheduling assistant",
        system_overview="System helps freelancers manage bookings and reminders from one interface.",
        audiences=["Freelancers"],
        scenarios=["Book and reschedule appointments"],
        pain_points=["Appointments are tracked manually"],
        feature_p1=["Booking workflow::Create bookings and reminders"],
        status="validated",
    )

    concept_path = memory_project.branch_dir / "concept.md"
    concept_path.write_text("# manually edited\n", encoding="utf-8")

    errors = validate_branch_memory(memory_project.project_path, "main")

    assert any("concept.md is out of sync" in error for error in errors)
