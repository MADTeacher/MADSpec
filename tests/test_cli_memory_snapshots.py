from __future__ import annotations

import json

from madspec_cli.memory import capture_stage_memory, checkpoint_stage_memory, get_memory_paths, validate_branch_memory
from madspec_cli.memory.shared.system_store.store import MemoryStore

from tests.test_cli_memory_proposals import _create_claim, _setup_claimed_work_item


def test_memory_snapshots_prune_from_tmp_file_deletes_args_on_success(
    make_madspec_project,
    invoke_cli,
) -> None:
    project_path = make_madspec_project()
    _seed_architecture_with_duplicates(project_path, "main")

    tmp_dir = project_path / ".madspec" / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    args_file = tmp_dir / "architecture-prune.json"
    args_file.write_text(
        json.dumps(
            {
                "stage": "mvp.architecture",
                "summary": "Prune duplicate architecture entries",
                "operations": [
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
            }
        ),
        encoding="utf-8",
    )

    result = invoke_cli(
        [
            "memory",
            "snapshots",
            "prune",
            "--from-file",
            ".madspec/.tmp/architecture-prune.json",
            "--json-output",
        ]
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["accepted"] is True
    assert payload["details"]["removed_count"] == 3
    assert not args_file.exists()

    retrieve_result = invoke_cli(
        [
            "memory",
            "retrieve",
            "--stage",
            "mvp.architecture",
            "--full-artifact",
            "--json-output",
        ]
    )
    assert retrieve_result.exit_code == 0, retrieve_result.stdout
    retrieve_payload = json.loads(retrieve_result.stdout)
    architecture = retrieve_payload["artifact_state"]["architecture"]
    assert architecture["projectStructure"]["directories"] == [
        {"path": "cmd/server", "purpose": "Main HTTP entrypoint"},
        {"path": "internal/app", "purpose": "Gameplay orchestration"},
    ]
    assert architecture["codePrinciples"] == [
        "Keep handlers thin.",
        "Apply SOLID to service boundaries.",
    ]
    assert architecture["patterns"] == [{"name": "Repository", "rationale": "Persist matches"}]

    assert validate_branch_memory(project_path, "main", stage="mvp.architecture") == []


def test_memory_snapshots_replace_supports_from_file_and_preserves_projection(
    make_madspec_project,
    invoke_cli,
) -> None:
    project_path = make_madspec_project()
    _seed_architecture_with_duplicates(project_path, "main")

    retrieve_before = invoke_cli(
        [
            "memory",
            "retrieve",
            "--stage",
            "mvp.architecture",
            "--full-artifact",
            "--json-output",
        ]
    )
    assert retrieve_before.exit_code == 0, retrieve_before.stdout
    before_payload = json.loads(retrieve_before.stdout)
    before_snapshot = before_payload["artifact_state"]["architecture"]

    replacement = {
        **before_snapshot,
        "revision": 42,
        "ratifiedAt": "2099-01-01T00:00:00Z",
        "updatedAt": "2099-01-01T00:00:00Z",
        "projectStructure": {
            **before_snapshot["projectStructure"],
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

    tmp_dir = project_path / ".madspec" / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    args_file = tmp_dir / "architecture-replace.json"
    args_file.write_text(
        json.dumps(
            {
                "stage": "mvp.architecture",
                "summary": "Replace architecture snapshot with canonical copy",
                "snapshot": replacement,
            }
        ),
        encoding="utf-8",
    )

    result = invoke_cli(
        [
            "memory",
            "snapshots",
            "replace",
            "--from-file",
            ".madspec/.tmp/architecture-replace.json",
            "--json-output",
        ]
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["accepted"] is True
    assert not args_file.exists()

    retrieve_after = invoke_cli(
        [
            "memory",
            "retrieve",
            "--stage",
            "mvp.architecture",
            "--full-artifact",
            "--json-output",
        ]
    )
    assert retrieve_after.exit_code == 0, retrieve_after.stdout
    after_payload = json.loads(retrieve_after.stdout)
    after_snapshot = after_payload["artifact_state"]["architecture"]
    assert after_snapshot["ratifiedAt"] == before_snapshot["ratifiedAt"]
    assert after_snapshot["revision"] == before_snapshot["revision"] + 1
    assert after_snapshot["patterns"] == [{"name": "Repository", "rationale": "Persist matches"}]

    architecture_doc = (project_path / ".madspec" / "main" / "architecture.md").read_text(encoding="utf-8")
    assert "Keep persistence out of gameplay services" not in architecture_doc


def test_memory_snapshots_from_file_rejects_unknown_fields_and_keeps_args_file(
    make_madspec_project,
    invoke_cli,
) -> None:
    project_path = make_madspec_project()
    tmp_dir = project_path / ".madspec" / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    args_file = tmp_dir / "bad-prune.json"
    args_file.write_text(
        json.dumps(
            {
                "stage": "mvp.architecture",
                "operations": [],
                "mystery_field": "??",
            }
        ),
        encoding="utf-8",
    )

    result = invoke_cli(
        [
            "memory",
            "snapshots",
            "prune",
            "--from-file",
            ".madspec/.tmp/bad-prune.json",
        ]
    )

    assert result.exit_code != 0
    assert "Unsupported fields in args file: mystery_field" in (result.stdout + result.stderr)
    assert args_file.exists()


def test_claimed_session_snapshot_cleanup_is_blocked_without_proposal_guidance(
    tmp_path,
    monkeypatch,
    invoke_cli,
    init_memory_branch,
) -> None:
    project_path = _setup_claimed_work_item(tmp_path, monkeypatch, invoke_cli, init_memory_branch)
    _seed_architecture_with_duplicates(project_path, "main")
    _create_claim(
        invoke_cli,
        task_title="Coordinate cleanup",
        work_title="Cleanup architecture snapshot",
        subagent_id="developer",
        session_key="cleanup",
        step_id=None,
        path="cmd/server",
    )

    args_file = project_path / ".madspec" / ".tmp" / "claimed-prune.json"
    args_file.parent.mkdir(parents=True, exist_ok=True)
    args_file.write_text(
        json.dumps(
            {
                "stage": "mvp.architecture",
                "session_key": "cleanup",
                "operations": [
                    {
                        "path": "codePrinciples",
                        "equals": "Apply SOLID to application service boundaries.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = invoke_cli(
        [
            "memory",
            "snapshots",
            "prune",
            "--from-file",
            ".madspec/.tmp/claimed-prune.json",
            "--json-output",
        ]
    )

    assert result.exit_code == 1, result.stdout
    payload = json.loads(result.stdout)
    assert "cannot run direct snapshots prune writes" in payload["errors"][0]
    assert "proposal_required" not in payload
    assert args_file.exists()


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

    store = MemoryStore(project_path)
    snapshot = store.fetch_snapshot(branch_name, "mvp.architecture")
    assert snapshot is not None
