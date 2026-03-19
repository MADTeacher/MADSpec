from __future__ import annotations

import json

from madspec_cli.features.init.infrastructure import initializer_core
from madspec_cli.memory import get_memory_paths


def test_init_creates_structured_memory_layout(tmp_path, monkeypatch, invoke_cli, fake_template_download) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(initializer_core, "download_and_extract_template", fake_template_download)

    result = invoke_cli(["init", "demo", "--ai", "cursor-agent", "--no-git"])

    assert result.exit_code == 0, result.stdout
    project_path = tmp_path / "demo"
    paths = get_memory_paths(project_path, "main")
    assert paths["progress"].exists()
    assert paths["active_session"].exists()
    assert paths["design_state"].exists()
    assert paths["tech_state"].exists()
    assert paths["architecture_state"].exists()
    assert paths["plan_state"].exists()
    assert (project_path / ".madspec" / "procedures" / "next-step-selection.md").exists()
    assert (project_path / ".madspec" / "main" / "project-context.md").exists()
    assert (project_path / ".madspec" / "main" / "implementation-plan.md").exists()
    assert (project_path / ".madspec" / "system" / "memory" / "memory.sqlite").exists()
    assert (project_path / ".madspec" / "system" / "memory" / "schema-version.json").exists()
    assert (project_path / ".madspec" / "system" / "memory" / "lancedb").exists()
    config = json.loads((project_path / ".madspec" / "config.json").read_text(encoding="utf-8"))
    assert config["agentEnvironment"] == "cursor-agent"
    assert config["agentsSchemaVersion"] == 1
    assert (project_path / ".madspec" / "system" / "agents" / "state.json").exists()
    assert "/madspec.gate" in result.stdout


def test_init_accepts_qwen_agent(tmp_path, monkeypatch, invoke_cli, fake_template_download) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(initializer_core, "download_and_extract_template", fake_template_download)

    result = invoke_cli(["init", "demo", "--ai", "qwen", "--no-git", "--ignore-agent-tools"])

    assert result.exit_code == 0, result.stdout
    assert "Selected AI assistant:" in result.stdout
    assert "qwen" in result.stdout


def test_init_rejects_unknown_agent_and_lists_qwen(tmp_path, monkeypatch, invoke_cli) -> None:
    monkeypatch.chdir(tmp_path)

    result = invoke_cli(["init", "demo", "--ai", "unknown-agent", "--no-git"])

    assert result.exit_code == 1
    assert "Invalid AI assistant 'unknown-agent'" in result.stdout
    assert "qwen" in result.stdout


def test_init_here_cancel_keeps_existing_directory(tmp_path, monkeypatch, invoke_cli) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("# existing\n", encoding="utf-8")

    result = invoke_cli(["init", "--here", "--ai", "cursor-agent", "--no-git"], input="n\n")

    assert result.exit_code == 0, result.stdout
    assert "Operation cancelled" in result.stdout
    assert not (tmp_path / ".madspec").exists()


def test_init_warns_when_git_is_missing(tmp_path, monkeypatch, invoke_cli, fake_template_download) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(initializer_core, "download_and_extract_template", fake_template_download)
    monkeypatch.setattr("madspec_cli.features.init.application.preflight.check_tool", lambda tool: False)

    result = invoke_cli(["init", "demo", "--ai", "cursor-agent", "--ignore-agent-tools"])

    assert result.exit_code == 0, result.stdout
    assert "Git not found - will skip repository initialization" in result.stdout


def test_init_fails_when_required_agent_cli_is_missing(tmp_path, monkeypatch, invoke_cli) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_check_tool(tool: str) -> bool:
        return tool == "git"

    monkeypatch.setattr("madspec_cli.features.init.application.preflight.check_tool", fake_check_tool)

    result = invoke_cli(["init", "demo", "--ai", "qwen", "--no-git"])

    assert result.exit_code == 1, result.stdout
    assert "Agent Detection Error" in result.stdout
    assert "qwen" in result.stdout
