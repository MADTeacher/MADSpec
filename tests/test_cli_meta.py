from __future__ import annotations

from madspec_cli.features.meta import cli as meta_cli
from madspec_cli.features.meta.application.version_info import VersionInfoResult


def test_migrate_reports_when_no_madspec_dir(tmp_path, monkeypatch, invoke_cli) -> None:
    monkeypatch.chdir(tmp_path)

    result = invoke_cli(["migrate"])

    assert result.exit_code == 0, result.stdout
    assert "No .madspec directory found" in result.stdout


def test_migrate_reports_when_no_migration_needed(tmp_path, monkeypatch, invoke_cli) -> None:
    project_path = tmp_path
    monkeypatch.chdir(project_path)
    (project_path / ".madspec" / "main").mkdir(parents=True)

    result = invoke_cli(["migrate"])

    assert result.exit_code == 0, result.stdout
    assert "No migration needed" in result.stdout


def test_migrate_supports_cancel_path(tmp_path, monkeypatch, invoke_cli) -> None:
    project_path = tmp_path
    monkeypatch.chdir(project_path)
    (project_path / ".madspec").mkdir()
    (project_path / ".madspec" / "concept.md").write_text("# legacy\n", encoding="utf-8")

    result = invoke_cli(["migrate"], input="n\n")

    assert result.exit_code == 0, result.stdout
    assert "Migration cancelled" in result.stdout
    assert (project_path / ".madspec" / "concept.md").exists()


def test_migrate_moves_files_and_skips_existing_targets(tmp_path, monkeypatch, invoke_cli) -> None:
    project_path = tmp_path
    monkeypatch.chdir(project_path)
    branch_dir = project_path / ".madspec" / "main"
    branch_dir.mkdir(parents=True)
    (project_path / ".madspec" / "concept.md").write_text("# legacy concept\n", encoding="utf-8")
    (project_path / ".madspec" / "notes").mkdir()
    (project_path / ".madspec" / "notes" / "item.md").write_text("note\n", encoding="utf-8")
    (branch_dir / "design.md").write_text("# existing\n", encoding="utf-8")
    (project_path / ".madspec" / "design.md").write_text("# legacy design\n", encoding="utf-8")

    result = invoke_cli(["migrate"], input="y\n")

    assert result.exit_code == 0, result.stdout
    assert "Migration complete" in result.stdout
    assert "Skipping design.md" in result.stdout
    assert not (project_path / ".madspec" / "concept.md").exists()
    assert (branch_dir / "concept.md").exists()
    assert (branch_dir / "notes" / "item.md").exists()
    assert (branch_dir / "design.md").read_text(encoding="utf-8") == "# existing\n"


def test_check_runs_tool_inventory(monkeypatch, invoke_cli) -> None:
    monkeypatch.setattr("madspec_cli.features.meta.application.check_tools.check_tool", lambda tool: tool == "git")

    result = invoke_cli(["check"])

    assert result.exit_code == 0, result.stdout
    assert "Check Available Tools" in result.stdout
    assert "MADSpec CLI is ready to use!" in result.stdout
    assert "Install an AI assistant" in result.stdout


def test_version_renders_version_panel(monkeypatch, invoke_cli) -> None:
    monkeypatch.setattr(
        meta_cli,
        "version_info_use_case",
        lambda: VersionInfoResult(
            payload={
                "cli_version": "1.2.3",
                "template_version": "4.5.6",
                "release_date": "2026-03-19",
                "python": "3.13.0",
                "platform": "Darwin",
                "architecture": "arm64",
                "os_version": "test",
            }
        ),
    )

    result = invoke_cli(["version"])

    assert result.exit_code == 0, result.stdout
    assert "MADSpec CLI Information" in result.stdout
    assert "1.2.3" in result.stdout
    assert "4.5.6" in result.stdout
