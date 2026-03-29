from __future__ import annotations

from madspec_cli.memory import capture_stage_memory, checkpoint_stage_memory, get_memory_paths
from madspec_cli.memory.application.snapshot_cleanup import (
    PruneSnapshotRequest,
    ReplaceSnapshotRequest,
    execute_prune,
    execute_replace,
    prune_snapshot_payload,
)
from madspec_cli.memory.shared.system_store.store import MemoryStore


def test_prune_snapshot_payload_removes_strings_and_objects() -> None:
    snapshot = {
        "codePrinciples": [
            "Keep handlers thin.",
            "Apply SOLID to service boundaries.",
            "Apply SOLID to application service boundaries.",
        ],
        "patterns": [
            {"name": "Repository", "rationale": "Persist matches"},
            {"name": "Repository", "rationale": "Keep persistence out of gameplay services"},
            {"name": "Service", "rationale": "Coordinate use cases"},
        ],
        "checkpointSummary": "Keep me",
    }

    pruned, errors, removed = prune_snapshot_payload(
        snapshot,
        [
            {
                "path": "codePrinciples",
                "equals": "Apply SOLID to application service boundaries.",
            },
            {
                "path": "patterns",
                "match": {
                    "name": "Repository",
                    "rationale": "Keep persistence out of gameplay services",
                },
            },
        ],
    )

    assert errors == []
    assert removed == 2
    assert pruned["codePrinciples"] == [
        "Keep handlers thin.",
        "Apply SOLID to service boundaries.",
    ]
    assert pruned["patterns"] == [
        {"name": "Repository", "rationale": "Persist matches"},
        {"name": "Service", "rationale": "Coordinate use cases"},
    ]
    assert pruned["checkpointSummary"] == "Keep me"


def test_snapshot_cleanup_prune_updates_canonical_snapshot_and_events(memory_project) -> None:
    _seed_architecture_with_duplicates(memory_project.project_path, memory_project.branch)

    result = execute_prune(
        PruneSnapshotRequest(
            project_path=memory_project.project_path,
            branch_name=memory_project.branch,
            stage="mvp.architecture",
            session_key="active",
            expected_revision=None,
            operations=[
                {
                    "path": "projectStructure.directories",
                    "match": {"path": "cmd/server", "purpose": "CLI and HTTP bootstrap"},
                },
                {
                    "path": "codePrinciples",
                    "equals": "Apply SOLID to application service boundaries.",
                },
                {
                    "path": "patterns",
                    "match": {
                        "name": "Repository",
                        "rationale": "Keep persistence out of gameplay services",
                    },
                },
            ],
            summary="Pruned architecture duplicates",
            evidence=[".madspec/main/memory/stages/mvp.architecture.json"],
        )
    )

    payload = result.to_payload()
    assert payload["accepted"] is True
    assert payload["details"]["removed_count"] == 3
    assert payload["written"] == {
        "stage_snapshots": 1,
        "events": 1,
    }

    store = MemoryStore(memory_project.project_path)
    snapshot = store.fetch_snapshot(memory_project.branch, "mvp.architecture")
    assert snapshot is not None
    assert snapshot["projectStructure"]["directories"] == [
        {"path": "cmd/server", "purpose": "Main HTTP entrypoint"},
        {"path": "internal/app", "purpose": "Gameplay orchestration"},
    ]
    assert snapshot["codePrinciples"] == [
        "Keep handlers thin.",
        "Apply SOLID to service boundaries.",
    ]
    assert snapshot["patterns"] == [
        {"name": "Repository", "rationale": "Persist matches"},
    ]

    stage_file = get_memory_paths(memory_project.project_path, memory_project.branch).architecture_state
    assert stage_file.exists()
    stage_text = stage_file.read_text(encoding="utf-8")
    assert "CLI and HTTP bootstrap" not in stage_text
    assert "Keep persistence out of gameplay services" not in stage_text

    events = store.list_records_by_stream(branch=memory_project.branch, record_stream="events", limit=20)
    assert any(
        item["summary"] == "Pruned architecture duplicates"
        and (item.get("metadata") or {}).get("cleanupMode") == "snapshot_prune"
        for item in events
    )


def test_snapshot_cleanup_replace_preserves_ratification_metadata(memory_project) -> None:
    _seed_architecture_with_duplicates(memory_project.project_path, memory_project.branch)
    store = MemoryStore(memory_project.project_path)
    before = store.fetch_snapshot(memory_project.branch, "mvp.architecture")
    assert before is not None

    replacement = {
        **before,
        "revision": 999,
        "ratifiedAt": "2099-01-01T00:00:00Z",
        "updatedAt": "2099-01-01T00:00:00Z",
        "projectStructure": {
            **before["projectStructure"],
            "directories": [
                {"path": "cmd/server", "purpose": "Main HTTP entrypoint"},
                {"path": "internal/app", "purpose": "Gameplay orchestration"},
            ],
        },
        "codePrinciples": [
            "Keep handlers thin.",
            "Apply SOLID to service boundaries.",
        ],
        "patterns": [
            {"name": "Repository", "rationale": "Persist matches"},
        ],
    }

    result = execute_replace(
        ReplaceSnapshotRequest(
            project_path=memory_project.project_path,
            branch_name=memory_project.branch,
            stage="mvp.architecture",
            session_key="active",
            expected_revision=None,
            snapshot=replacement,
            summary="Replaced architecture snapshot with canonical copy",
        )
    )

    payload = result.to_payload()
    assert payload["accepted"] is True

    after = store.fetch_snapshot(memory_project.branch, "mvp.architecture")
    assert after is not None
    assert after["ratifiedAt"] == before["ratifiedAt"]
    assert after["revision"] == before["revision"] + 1
    assert after["updatedAt"] != before["updatedAt"]
    assert after["projectStructure"]["directories"] == [
        {"path": "cmd/server", "purpose": "Main HTTP entrypoint"},
        {"path": "internal/app", "purpose": "Gameplay orchestration"},
    ]
    assert after["patterns"] == [{"name": "Repository", "rationale": "Persist matches"}]


def _seed_architecture_with_duplicates(project_path, branch_name: str) -> None:
    paths = get_memory_paths(project_path, branch_name)
    ui_dir = paths["branch_dir"] / "ui-prototype"
    ui_dir.mkdir(parents=True, exist_ok=True)
    (ui_dir / "index.html").write_text("<html><body>index</body></html>\n", encoding="utf-8")

    capture_stage_memory(
        project_path,
        branch_name,
        "mvp.concept",
        project_name="Match3",
        system_overview="Match3 service with a single gameplay screen.",
        audiences=["Players"],
        scenarios=["Play one match in the browser"],
        pain_points=["Prototype architecture accumulated duplicate notes"],
        feature_p1=["Gameplay::Play one match and submit moves"],
        status="validated",
    )
    capture_stage_memory(
        project_path,
        branch_name,
        "mvp.design",
        design_overview="Single-screen gameplay board.",
        platforms=["Web"],
        zones=["gameplay::Gameplay::Primary board"],
        screens=[
            "board::Board::gameplay::.madspec/main/ui-prototype/index.html::Shows the current board state",
        ],
        screen_features=["board::p1::Gameplay"],
        flows=["play::Play::Submit one move and inspect the result"],
        flow_steps=["play::board::Submit move::Refresh board state after the move"],
        navigation=["board::board::Replay from board header"],
        screen_data=[
            "board::displayed::board-state",
            "board::input::move-command",
        ],
        status="validated",
    )
    capture_stage_memory(
        project_path,
        branch_name,
        "mvp.architecture",
        architecture_overview="Go service split into entrypoint and application layers.",
        project_structure="feature-first::Keep gameplay logic isolated from the entrypoint",
        directories=[
            "cmd/server::Main HTTP entrypoint",
            "internal/app::Gameplay orchestration",
            "cmd/server::CLI and HTTP bootstrap",
        ],
        entities=[
            "Match::Current match state",
        ],
        entity_fields=[
            "Match::id::uuid::required::Primary match identifier",
            "Match::board-state::json::required::Current board layout",
        ],
        endpoints=[
            "submit-move::POST::/matches/{id}/moves::Submit a move",
        ],
        endpoint_screens=[
            "submit-move::board",
        ],
        endpoint_fields=[
            "submit-move::path::id::uuid::required::Match identifier",
            "submit-move::request::move-command::string::required::Move submitted by the player",
            "submit-move::response:200::board-state::json::required::Updated board state",
        ],
        code_principles=[
            "Keep handlers thin.",
            "Apply SOLID to service boundaries.",
            "Apply SOLID to application service boundaries.",
        ],
        architecture_patterns=[
            "Repository::Persist matches",
            "Repository::Keep persistence out of gameplay services",
        ],
        next_actions=["Proceed to mvp.plan"],
        status="validated",
    )
    checkpoint_stage_memory(
        project_path,
        branch_name,
        "mvp.architecture",
        "Architecture ratified with duplicates",
        evidence=[".madspec/main/architecture.md"],
    )
