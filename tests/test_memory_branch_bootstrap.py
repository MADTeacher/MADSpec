from __future__ import annotations

from pathlib import Path

from madspec_cli.memory.application.branch_state import (
    BootstrapBranchStateRequest,
    bootstrap_branch_state,
)
from madspec_cli.memory.application.system_store_ops import build_db_status
from madspec_cli.memory.shared.storage import append_jsonl, ensure_memory_layout, get_memory_paths, write_json

from tests.support import write_madspec_config


def _progress_payload() -> dict[str, object]:
    return {
        "currentImplementStep": None,
        "completedSteps": [],
        "plannedSteps": [],
        "stepStatus": {},
        "stepMetadata": {},
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
    }


def test_memory_helpers_are_pure_file_io(tmp_path: Path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    write_madspec_config(project_path, "main")
    ensure_memory_layout(project_path, "main", full=True)
    paths = get_memory_paths(project_path, "main")
    before = build_db_status(project_path, "main")

    write_json(paths.progress, _progress_payload())
    append_jsonl(
        paths.facts,
        [
            {
                "record_id": "fact-1",
                "record_stream": "facts",
                "branch": "main",
                "summary": "fact",
            }
        ],
    )

    db_status = build_db_status(project_path, "main")
    assert db_status["stage_snapshots"] == before["stage_snapshots"]
    assert db_status["records"] == before["records"]


def test_bootstrap_branch_state_syncs_memory_and_generated_artifacts(tmp_path: Path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()

    result = bootstrap_branch_state(
        BootstrapBranchStateRequest(
            project_path=project_path,
            branch_name="main",
        )
    )

    assert result.config_path.exists()
    assert result.memory_dir.exists()
    assert (result.branch_dir / "project-context.md").exists()
    assert any(path.name == "progress.json" for path in result.created_paths)
    assert any(path.name == "project-context.md" for path in result.generated_paths)

    db_status = build_db_status(project_path, "main")
    assert db_status["stage_snapshots"] >= 1
    assert db_status["artifacts"] >= 1
