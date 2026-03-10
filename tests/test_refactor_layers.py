from __future__ import annotations

import json
from pathlib import Path

import httpx

import madspec_cli
from madspec_cli.github_api import (
    ReleaseAsset,
    _format_rate_limit_error,
    _parse_rate_limit_headers,
    fetch_latest_release_asset,
)
from madspec_cli.initializer import merge_json_files
from madspec_cli.memory import (
    _compute_progress_metrics,
    consolidate_branch_memory,
    ensure_memory_layout,
    extract_function_catalog,
    get_memory_paths,
    validate_branch_memory,
    write_json,
)


def test_top_level_package_re_exports_app_and_main() -> None:
    assert callable(madspec_cli.main)
    assert madspec_cli.app.info.name == "madspec"


def test_memory_package_re_exports_compatibility_surface() -> None:
    from madspec_cli.memory import get_memory_paths as exported_get_memory_paths
    from madspec_cli.memory import register_planned_step as exported_register_planned_step

    assert callable(exported_get_memory_paths)
    assert callable(exported_register_planned_step)


def test_rate_limit_headers_are_parsed_and_formatted() -> None:
    headers = httpx.Headers(
        {
            "X-RateLimit-Limit": "60",
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": "1760000000",
            "Retry-After": "120",
        }
    )

    parsed = _parse_rate_limit_headers(headers)
    message = _format_rate_limit_error(403, headers, "https://api.github.com/demo")

    assert parsed["limit"] == "60"
    assert parsed["remaining"] == "0"
    assert parsed["retry_after_seconds"] == 120
    assert "Retry after: 120 seconds" in message


def test_release_asset_selection_uses_pattern_match() -> None:
    payload = {
        "tag_name": "v1.2.3",
        "assets": [
            {
                "name": "madspec-template-cursor-agent-v1.2.3.zip",
                "size": 1234,
                "browser_download_url": "https://example.com/ok.zip",
            },
            {
                "name": "other.zip",
                "size": 12,
                "browser_download_url": "https://example.com/other.zip",
            },
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    asset = fetch_latest_release_asset(
        "MADTeacher",
        "MADSpec",
        "madspec-template-cursor-agent",
        client=client,
    )

    assert asset == ReleaseAsset(
        filename="madspec-template-cursor-agent-v1.2.3.zip",
        size=1234,
        release="v1.2.3",
        asset_url="https://example.com/ok.zip",
    )


def test_merge_json_files_deep_merges_vscode_settings(tmp_path: Path) -> None:
    existing_path = tmp_path / "settings.json"
    existing_path.write_text(
        json.dumps(
            {
                "editor": {"tabSize": 2, "formatOnSave": False},
                "files.exclude": {"node_modules": True},
            }
        ),
        encoding="utf-8",
    )

    merged = merge_json_files(
        existing_path,
        {
            "editor": {"formatOnSave": True},
            "search.exclude": {"dist": True},
        },
    )

    assert merged == {
        "editor": {"tabSize": 2, "formatOnSave": True},
        "files.exclude": {"node_modules": True},
        "search.exclude": {"dist": True},
    }


def test_validate_branch_memory_is_read_only(tmp_path: Path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    (project_path / ".madspec").mkdir()
    (project_path / ".madspec" / "config.json").write_text(
        json.dumps({"currentBranch": "main", "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )
    ensure_memory_layout(project_path, "main")
    paths = get_memory_paths(project_path, "main")
    consolidate_branch_memory(project_path, "main")
    before = (paths.branch_dir / "project-context.md").read_text(encoding="utf-8")

    write_json(
        paths.progress,
        {
            "currentImplementStep": "missing-step",
            "completedSteps": [],
            "plannedSteps": [],
            "stepStatus": {},
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
        },
    )

    errors = validate_branch_memory(project_path, "main")
    after = (paths.branch_dir / "project-context.md").read_text(encoding="utf-8")

    assert errors
    assert before == after


def test_extract_function_catalog_and_progress_metrics(tmp_path: Path) -> None:
    project_path = tmp_path / "project"
    branch_dir = project_path / ".madspec" / "main"
    branch_dir.mkdir(parents=True)
    (project_path / ".madspec" / "config.json").write_text(
        json.dumps({"currentBranch": "main", "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )
    (branch_dir / "concept.md").write_text(
        """# Concept

### Приоритет 1
- Auth: user login
- Sessions: persistence

### Приоритет 2
- Profile: edit

### Приоритет 3
- Export: settings
""",
        encoding="utf-8",
    )

    catalog = extract_function_catalog(project_path, "main", "mvp.plan")
    metrics = _compute_progress_metrics(
        catalog,
        {
            "step-01-auth": {"p1": ["Auth"], "p2": [], "p3": []},
            "step-02-profile": {"p1": [], "p2": ["Profile"], "p3": []},
        },
    )

    assert catalog == {
        "p1": ["Auth", "Sessions"],
        "p2": ["Profile"],
        "p3": ["Export"],
    }
    assert metrics["p1Coverage"]["percentage"] == 50
    assert metrics["p2Coverage"]["percentage"] == 100
    assert metrics["overallProgress"] == 55
