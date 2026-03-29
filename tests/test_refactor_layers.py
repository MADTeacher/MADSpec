from __future__ import annotations

import json
import importlib
from pathlib import Path

import httpx

import madspec_cli
from madspec_cli.github_api import (
    ReleaseAsset,
    _format_rate_limit_error,
    _parse_rate_limit_headers,
    fetch_latest_release_asset,
)
from madspec_cli.features.init.infrastructure.initializer_core import merge_json_files
from madspec_cli.memory import (
    consolidate_branch_memory,
    ensure_memory_layout,
    get_memory_paths,
    validate_branch_memory,
)
from madspec_cli.memory.shared.storage import write_json
from madspec_cli.memory.workflow.planning import _compute_progress_metrics, extract_function_catalog


def test_top_level_package_re_exports_app_and_main() -> None:
    assert callable(madspec_cli.main)
    assert madspec_cli.app.info.name == "madspec"


def test_memory_package_re_exports_compatibility_surface() -> None:
    memory_module = importlib.import_module("madspec_cli.memory")

    assert callable(memory_module.get_memory_paths)
    assert callable(memory_module.register_planned_step)
    assert not hasattr(memory_module, "_compute_progress_metrics")
    assert not hasattr(memory_module, "extract_function_catalog")
    assert not hasattr(memory_module, "make_record")
    assert not hasattr(memory_module, "append_jsonl")
    assert not hasattr(memory_module, "read_jsonl")
    assert not hasattr(memory_module, "write_json")


def test_memory_internal_modules_do_not_import_memory_root() -> None:
    memory_dir = Path(__file__).resolve().parents[1] / "src" / "madspec_cli" / "memory"
    offenders: list[str] = []

    for path in sorted(memory_dir.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        content = path.read_text(encoding="utf-8")
        if "from madspec_cli.memory import" in content or "import madspec_cli.memory" in content:
            offenders.append(str(path.relative_to(memory_dir.parents[2])))

    assert offenders == []


def test_boundary_modules_do_not_depend_on_forbidden_layers(repo_root: Path) -> None:
    project_config = (
        repo_root / "src" / "madspec_cli" / "shared" / "infra" / "project_config.py"
    ).read_text(encoding="utf-8")
    memory_storage = (
        repo_root / "src" / "madspec_cli" / "memory" / "shared" / "storage.py"
    ).read_text(encoding="utf-8")
    git_operations = (
        repo_root / "src" / "madspec_cli" / "features" / "git" / "infrastructure" / "operations.py"
    ).read_text(encoding="utf-8")
    policy_storage = (
        repo_root / "src" / "madspec_cli" / "features" / "policy" / "infrastructure" / "storage.py"
    ).read_text(encoding="utf-8")
    change_storage = (
        repo_root / "src" / "madspec_cli" / "features" / "change" / "infrastructure" / "storage.py"
    ).read_text(encoding="utf-8")
    policy_repository = (
        repo_root / "src" / "madspec_cli" / "features" / "policy" / "infrastructure" / "repository.py"
    ).read_text(encoding="utf-8")
    change_repository = (
        repo_root / "src" / "madspec_cli" / "features" / "change" / "infrastructure" / "repository.py"
    ).read_text(encoding="utf-8")
    init_cli = (
        repo_root / "src" / "madspec_cli" / "features" / "init" / "cli.py"
    ).read_text(encoding="utf-8")
    agents_cli = (
        repo_root / "src" / "madspec_cli" / "features" / "agents" / "cli.py"
    ).read_text(encoding="utf-8")
    policy_cli = (
        repo_root / "src" / "madspec_cli" / "features" / "policy" / "cli.py"
    ).read_text(encoding="utf-8")
    change_cli = (
        repo_root / "src" / "madspec_cli" / "features" / "change" / "cli.py"
    ).read_text(encoding="utf-8")
    gates_cli = (
        repo_root / "src" / "madspec_cli" / "features" / "gates" / "cli.py"
    ).read_text(encoding="utf-8")
    features_init = (
        repo_root / "src" / "madspec_cli" / "features" / "__init__.py"
    ).read_text(encoding="utf-8")
    gates_init = (
        repo_root / "src" / "madspec_cli" / "features" / "gates" / "__init__.py"
    ).read_text(encoding="utf-8")
    git_init = (
        repo_root / "src" / "madspec_cli" / "features" / "git" / "__init__.py"
    ).read_text(encoding="utf-8")
    init_init = (
        repo_root / "src" / "madspec_cli" / "features" / "init" / "__init__.py"
    ).read_text(encoding="utf-8")
    meta_init = (
        repo_root / "src" / "madspec_cli" / "features" / "meta" / "__init__.py"
    ).read_text(encoding="utf-8")

    assert "features.git.infrastructure.operations" not in project_config
    assert ".system_store" not in memory_storage
    assert "madspec_cli.memory" not in git_operations
    assert "shared.infra.project_config" not in git_operations
    assert "MemoryStore" not in policy_storage
    assert "render_policy_markdown" not in policy_storage
    assert "normalize_policy_payload" not in policy_storage
    assert "run_subprocess" not in change_storage
    assert "build_git_diff" not in change_storage
    assert "render_change_summary_markdown" not in change_storage
    assert "MemoryStore" not in policy_repository
    assert "MemoryStore" not in change_repository
    assert "Live" not in init_cli
    assert "Panel" not in init_cli
    assert "shutil.rmtree" not in init_cli
    assert "StepTracker" not in init_cli
    assert "emit_error(" not in policy_cli
    assert "emit_error(" not in change_cli
    assert "emit_error(" not in gates_cli
    assert agents_cli.count("emit_error(") <= 2
    assert change_cli.count("raise typer.Exit(1)") == 0
    assert policy_cli.count("raise typer.Exit(1)") == 0
    assert gates_cli.count("raise typer.Exit(1)") == 0
    assert " import cli" not in features_init
    assert " import cli" not in gates_init
    assert " import cli" not in git_init
    assert " import cli" not in init_init
    assert " import cli" not in meta_init


def test_nested_agents_guides_exist_and_describe_stable_entry_points(repo_root: Path) -> None:
    expected = {
        repo_root / "src" / "madspec_cli" / "memory" / "AGENTS.md": ["Стабильные точки входа", "memory/__init__.py"],
        repo_root / "src" / "madspec_cli" / "memory" / "shared" / "system_store" / "AGENTS.md": ["store.py", "__init__.py"],
        repo_root / "src" / "madspec_cli" / "features" / "agents" / "AGENTS.md": ["infrastructure/storage.py", "application/"],
        repo_root / "src" / "madspec_cli" / "features" / "policy" / "AGENTS.md": ["infrastructure/storage.py", "service.py"],
        repo_root / "src" / "madspec_cli" / "features" / "change" / "AGENTS.md": ["infrastructure/storage.py", "service.py"],
    }

    for path, expected_snippets in expected.items():
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        for snippet in expected_snippets:
            assert snippet in content


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
