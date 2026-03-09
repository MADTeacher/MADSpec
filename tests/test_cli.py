from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

import madspec_cli as cli
from madspec_cli import initializer
from madspec_cli.memory import append_jsonl, get_memory_paths, make_record


runner = CliRunner()


def _fake_download(
    project_path: Path,
    ai_assistant: str,
    script_type: str,
    is_current_dir: bool,
    verbose: bool = False,
    tracker=None,
    client=None,
    debug: bool = False,
    github_token: str | None = None,
):
    project_path.mkdir(parents=True, exist_ok=True)
    (project_path / ".madspec" / "templates").mkdir(parents=True, exist_ok=True)
    (project_path / ".madspec" / "templates" / "project-context-template.md").write_text(
        "# template\n",
        encoding="utf-8",
    )
    (project_path / "README.md").write_text("# demo\n", encoding="utf-8")


def test_init_creates_structured_memory_layout(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(initializer, "download_and_extract_template", _fake_download)
    result = runner.invoke(
        cli.app,
        ["init", "demo", "--ai", "cursor-agent", "--script", "sh", "--no-git"],
    )

    assert result.exit_code == 0, result.stdout
    project_path = tmp_path / "demo"
    paths = get_memory_paths(project_path, "main")
    assert paths["progress"].exists()
    assert paths["active_session"].exists()
    assert (project_path / ".madspec" / "procedures" / "next-step-selection.md").exists()
    assert (project_path / ".madspec" / "main" / "project-context.md").exists()


def test_memory_commands_support_validation_and_retrieve_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    project_path = tmp_path
    (project_path / ".madspec").mkdir()
    (project_path / ".madspec" / "config.json").write_text(
        json.dumps({"currentBranch": "main", "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(cli.app, ["memory", "init", "--branch", "main"])
    assert result.exit_code == 0, result.stdout

    paths = get_memory_paths(project_path, "main")
    append_jsonl(
        paths["decision_log"],
        [
            make_record(
                "main",
                "mvp.plan",
                "agent",
                "Validated planning decision",
                status="validated",
                evidence=["README.md"],
                semantic_kind="decision",
                record_type="decision",
            )
        ],
    )

    promote_result = runner.invoke(
        cli.app,
        ["memory", "promote", "--branch", "main", "--json-output"],
    )
    assert promote_result.exit_code == 0, promote_result.stdout
    promoted_payload = json.loads(promote_result.stdout)
    assert promoted_payload["promoted"]["decision"] == 1

    validate_result = runner.invoke(
        cli.app,
        ["memory", "validate", "--branch", "main", "--json-output"],
    )
    assert validate_result.exit_code == 0, validate_result.stdout
    assert json.loads(validate_result.stdout)["valid"] is True

    retrieve_result = runner.invoke(
        cli.app,
        ["memory", "retrieve", "--branch", "main", "--stage", "mvp.plan", "--json-output"],
    )
    assert retrieve_result.exit_code == 0, retrieve_result.stdout
    payload = json.loads(retrieve_result.stdout)
    assert payload["semantic"]["decisions"][0]["summary"] == "Validated planning decision"

    next_step_candidate = runner.invoke(
        cli.app,
        [
            "memory",
            "next-step",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--candidate-step",
            "step-02-auth-flow",
            "--depends-on",
            "step-01-bootstrap",
            "--json-output",
        ],
    )
    assert next_step_candidate.exit_code == 1, next_step_candidate.stdout

    progress = json.loads(paths["progress"].read_text(encoding="utf-8"))
    progress["plannedSteps"] = ["step-01-bootstrap", "step-02-auth-flow"]
    progress["completedSteps"] = ["step-01-bootstrap"]
    progress["stepStatus"] = {
        "step-01-bootstrap": {"status": "completed", "completedAt": "2026-03-10"},
        "step-02-auth-flow": {"status": "planned", "completedAt": None},
    }
    progress["planningMetadata"]["stepDependencies"] = {"step-02-auth-flow": ["step-01-bootstrap"]}
    paths["progress"].write_text(json.dumps(progress, indent=2) + "\n", encoding="utf-8")

    next_step_select = runner.invoke(
        cli.app,
        ["memory", "next-step", "--branch", "main", "--stage", "mvp.implement", "--json-output"],
    )
    assert next_step_select.exit_code == 0, next_step_select.stdout
    next_step_payload = json.loads(next_step_select.stdout)
    assert next_step_payload["selected_step"] == "step-02-auth-flow"


def test_memory_register_step_updates_progress_and_views(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    project_path = tmp_path
    (project_path / ".madspec").mkdir()
    (project_path / ".madspec" / "config.json").write_text(
        json.dumps({"currentBranch": "main", "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )
    branch_dir = project_path / ".madspec" / "main"
    branch_dir.mkdir(parents=True, exist_ok=True)
    (branch_dir / "concept.md").write_text(
        """# Concept

### Приоритет 1
- Authentication: sign in users
- Sessions: keep users logged in

### Приоритет 2
- Profile: edit user profile

### Приоритет 3
- Export: download settings
""",
        encoding="utf-8",
    )

    init_result = runner.invoke(cli.app, ["memory", "init", "--branch", "main"])
    assert init_result.exit_code == 0, init_result.stdout

    register_result = runner.invoke(
        cli.app,
        [
            "memory",
            "register-step",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--step-id",
            "step-01-authentication",
            "--covers",
            "Authentication",
            "--covers",
            "Profile",
            "--json-output",
        ],
    )
    assert register_result.exit_code == 0, register_result.stdout
    payload = json.loads(register_result.stdout)
    paths = get_memory_paths(project_path, "main")
    progress = json.loads(paths["progress"].read_text(encoding="utf-8"))

    assert payload["accepted"] is True
    assert progress["plannedSteps"] == ["step-01-authentication"]
    assert progress["coversFunctions"]["step-01-authentication"] == {
        "p1": ["Authentication"],
        "p2": ["Profile"],
        "p3": [],
    }
    assert progress["planningMetadata"]["progressMetrics"]["overallProgress"] == 55
    assert (project_path / ".madspec" / "main" / "project-context.md").exists()
    assert (project_path / ".madspec" / "main" / "planning-context-cache.md").exists()
