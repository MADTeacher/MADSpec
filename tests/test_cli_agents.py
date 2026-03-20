from __future__ import annotations

import json

from madspec_cli.features.init.infrastructure import initializer_core


def test_agents_profile_bootstraps_state_from_init(tmp_path, monkeypatch, invoke_cli, fake_template_download) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(initializer_core, "download_and_extract_template", fake_template_download)

    result = invoke_cli(["init", "demo", "--ai", "cursor-agent", "--no-git"])

    assert result.exit_code == 0, result.stdout
    project_path = tmp_path / "demo"
    state_path = project_path / ".madspec" / "system" / "agents" / "state.json"
    catalog_path = project_path / ".madspec" / "system" / "agents" / "catalog.json"
    assert state_path.exists()
    assert catalog_path.exists()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["environmentId"] == "cursor-agent"
    assert set(state["enabledSubagentIds"]) == {
        "architecture",
        "developer",
        "contracts-data",
        "testing",
        "security",
        "research",
        "docs",
    }
    assert (project_path / ".cursor" / "agents" / "madspec-architecture.md").exists()
    assert (project_path / ".cursor" / "agents" / "madspec-developer.md").exists()
    assert (project_path / ".cursor" / "agents" / "madspec-contracts-data.md").exists()
    assert (project_path / ".cursor" / "agents" / "madspec-docs.md").exists()


def test_agents_profile_reports_current_environment(tmp_path, monkeypatch, invoke_cli, init_memory_branch) -> None:
    project_path = tmp_path / "demo"
    project_path.mkdir()
    monkeypatch.chdir(project_path)
    from tests.support import write_madspec_config

    write_madspec_config(project_path, branch="main", agent_environment="qwen")
    init_memory_branch(branch="main", project_path=project_path)

    result = invoke_cli(["agents", "profile", "--json-output"])

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["environment"]["environmentId"] == "qwen"
    assert payload["profile"]["environmentId"] == "qwen"
    assert payload["catalog_file"] == ".madspec/system/agents/catalog.json"


def test_agents_propose_and_apply_profile_renders_native_subagents(tmp_path, monkeypatch, invoke_cli, init_memory_branch) -> None:
    project_path = tmp_path / "demo"
    project_path.mkdir()
    monkeypatch.chdir(project_path)
    from tests.support import write_madspec_config

    write_madspec_config(project_path, branch="main", agent_environment="opencode")
    init_memory_branch(branch="main", project_path=project_path)

    propose = invoke_cli(
        [
            "agents",
            "propose-profile",
            "--profile-id",
            "quality-focused",
            "--subagent",
            "testing",
            "--subagent",
            "security",
            "--json-output",
        ]
    )
    assert propose.exit_code == 0, propose.stdout
    proposal = json.loads(propose.stdout)

    apply = invoke_cli(
        ["agents", "apply-profile", "--proposal-id", proposal["proposalId"], "--json-output"]
    )
    assert apply.exit_code == 0, apply.stdout
    payload = json.loads(apply.stdout)
    assert payload["profile"]["profileId"] == "quality-focused"
    assert set(payload["profile"]["enabledSubagentIds"]) == {"testing", "security"}
    assert (project_path / ".opencode" / "agents" / "madspec-testing.md").exists()
    assert (project_path / ".opencode" / "agents" / "madspec-security.md").exists()
    assert not (project_path / ".opencode" / "agents" / "madspec-architecture.md").exists()


def test_agents_enable_disable_updates_rendered_files(tmp_path, monkeypatch, invoke_cli, init_memory_branch) -> None:
    project_path = tmp_path / "demo"
    project_path.mkdir()
    monkeypatch.chdir(project_path)
    from tests.support import write_madspec_config

    write_madspec_config(project_path, branch="main", agent_environment="cursor-agent")
    init_memory_branch(branch="main", project_path=project_path)

    disable = invoke_cli(
        ["agents", "subagents", "disable", "--subagent-id", "research", "--json-output"]
    )
    assert disable.exit_code == 0, disable.stdout
    assert not (project_path / ".cursor" / "agents" / "madspec-research.md").exists()

    enable = invoke_cli(
        ["agents", "subagents", "enable", "--subagent-id", "research", "--json-output"]
    )
    assert enable.exit_code == 0, enable.stdout
    assert (project_path / ".cursor" / "agents" / "madspec-research.md").exists()


def test_subagent_context_returns_role_scoped_payload(tmp_path, monkeypatch, invoke_cli, init_memory_branch) -> None:
    project_path = tmp_path / "demo"
    project_path.mkdir()
    monkeypatch.chdir(project_path)
    from tests.support import write_madspec_config

    write_madspec_config(project_path, branch="main", agent_environment="copilot")
    init_memory_branch(branch="main", project_path=project_path)

    result = invoke_cli(
        [
            "agents",
            "subagents",
            "context",
            "--subagent-id",
            "security",
            "--json-output",
        ]
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["subagent"]["subagentId"] == "security"
    assert payload["stage"] == "security"
    assert "memory" in payload
    assert "policy" in payload
    assert "gates" in payload


def test_subagent_context_supports_toon_output(tmp_path, monkeypatch, invoke_cli, init_memory_branch) -> None:
    project_path = tmp_path / "demo"
    project_path.mkdir()
    monkeypatch.chdir(project_path)
    from tests.support import write_madspec_config

    write_madspec_config(project_path, branch="main", agent_environment="copilot")
    init_memory_branch(branch="main", project_path=project_path)

    result = invoke_cli(
        [
            "agents",
            "subagents",
            "context",
            "--subagent-id",
            "security",
            "--toon-output",
        ]
    )

    assert result.exit_code == 0, result.stdout
    assert "subagent:" in result.stdout
    assert "branch: main" in result.stdout
    assert "policy:" in result.stdout
    assert "gates:" in result.stdout


def test_agents_can_create_show_and_profile_custom_subagent(
    tmp_path,
    monkeypatch,
    invoke_cli,
    init_memory_branch,
    write_args_file,
) -> None:
    project_path = tmp_path / "demo"
    project_path.mkdir()
    monkeypatch.chdir(project_path)
    from tests.support import write_madspec_config

    write_madspec_config(project_path, branch="main", agent_environment="cursor-agent")
    init_memory_branch(branch="main", project_path=project_path)

    payload_file = write_args_file(
        "domain-expert.json",
        {
            "title": "Domain Expert",
            "description": "Understands product domain rules and business constraints for the current repository.",
            "purpose": "Capture domain-specific assumptions and contracts for the current product.",
            "defaultStage": "feature.plan",
            "executionModeHint": "parallel",
            "dependencies": ["architecture"],
            "toolPolicy": {"read": True, "search": True, "edit": False, "write": False, "bash": False},
            "outputContract": {"deliverable": "domain notes", "writeBack": "through canonical CLI only"},
        },
    )
    body_file = write_args_file(
        "domain-expert.md",
        "You are responsible for domain-specific constraints in the current product.\n",
    )

    create = invoke_cli(
        [
            "agents",
            "subagents",
            "create",
            "--subagent-id",
            "domain-expert",
            "--from-file",
            str(payload_file),
            "--body-file",
            str(body_file),
            "--json-output",
        ]
    )
    assert create.exit_code == 0, create.stdout

    show = invoke_cli(
        [
            "agents",
            "subagents",
            "show",
            "--subagent-id",
            "domain-expert",
            "--json-output",
        ]
    )
    assert show.exit_code == 0, show.stdout
    shown = json.loads(show.stdout)
    assert shown["origin"] == "project"
    assert shown["bodySource"] == ".madspec/system/agents/bodies/domain-expert.md"
    assert shown["enabled"] is False

    profile = invoke_cli(["agents", "profile", "--json-output"])
    payload = json.loads(profile.stdout)
    assert any(item["subagentId"] == "domain-expert" for item in payload["profile"]["subagents"])


def test_custom_subagent_can_be_applied_in_profile_and_rendered(
    tmp_path,
    monkeypatch,
    invoke_cli,
    init_memory_branch,
    write_args_file,
) -> None:
    project_path = tmp_path / "demo"
    project_path.mkdir()
    monkeypatch.chdir(project_path)
    from tests.support import write_madspec_config

    write_madspec_config(project_path, branch="main", agent_environment="qwen")
    init_memory_branch(branch="main", project_path=project_path)

    payload_file = write_args_file(
        "docs-auditor.json",
        {
            "title": "Docs Auditor",
            "description": "Reviews documentation consistency for the current repository.",
            "purpose": "Find mismatches between commands, docs, and generated artifacts.",
            "defaultStage": "review",
            "executionModeHint": "parallel",
            "dependencies": [],
            "toolPolicy": {"read": True, "search": True, "edit": False, "write": False, "bash": False},
            "outputContract": {"deliverable": "doc findings", "writeBack": "through canonical CLI only"},
        },
    )
    body_file = write_args_file("docs-auditor.md", "Audit project documentation for consistency.\n")
    create = invoke_cli(
        [
            "agents",
            "subagents",
            "create",
            "--subagent-id",
            "docs-auditor",
            "--from-file",
            str(payload_file),
            "--body-file",
            str(body_file),
            "--json-output",
        ]
    )
    assert create.exit_code == 0, create.stdout

    propose = invoke_cli(
        [
            "agents",
            "propose-profile",
            "--profile-id",
            "docs-profile",
            "--subagent",
            "architecture",
            "--subagent",
            "docs-auditor",
            "--json-output",
        ]
    )
    proposal = json.loads(propose.stdout)
    apply = invoke_cli(["agents", "apply-profile", "--proposal-id", proposal["proposalId"], "--json-output"])
    assert apply.exit_code == 0, apply.stdout

    payload = json.loads(apply.stdout)
    assert set(payload["profile"]["enabledSubagentIds"]) == {"architecture", "docs-auditor"}
    rendered_file = project_path / ".qwen" / "agents" / "madspec-docs-auditor.md"
    assert rendered_file.exists()
    assert "Audit project documentation for consistency." in rendered_file.read_text(encoding="utf-8")


def test_update_builtin_role_creates_override_and_remove_restores_builtin(
    tmp_path,
    monkeypatch,
    invoke_cli,
    init_memory_branch,
    write_args_file,
) -> None:
    project_path = tmp_path / "demo"
    project_path.mkdir()
    monkeypatch.chdir(project_path)
    from tests.support import write_madspec_config

    write_madspec_config(project_path, branch="main", agent_environment="cursor-agent")
    init_memory_branch(branch="main", project_path=project_path)

    payload_file = write_args_file(
        "architecture-override.json",
        {
            "title": "Architecture Steward",
            "description": "Owns repository architecture decisions for this project.",
            "purpose": "Review architecture decisions for this specific product.",
            "defaultStage": "mvp.architecture",
            "executionModeHint": "sequential",
            "dependencies": [],
            "toolPolicy": {"read": True, "search": True, "edit": False, "write": False, "bash": False},
            "outputContract": {"deliverable": "architecture notes", "writeBack": "through canonical CLI only"},
        },
    )
    body_file = write_args_file("architecture-override.md", "Project-specific architecture override body.\n")

    update = invoke_cli(
        [
            "agents",
            "subagents",
            "update",
            "--subagent-id",
            "architecture",
            "--from-file",
            str(payload_file),
            "--body-file",
            str(body_file),
            "--json-output",
        ]
    )
    assert update.exit_code == 0, update.stdout
    updated = json.loads(update.stdout)
    assert updated["subagent"]["origin"] == "override"

    rendered_file = project_path / ".cursor" / "agents" / "madspec-architecture.md"
    assert "Project-specific architecture override body." in rendered_file.read_text(encoding="utf-8")

    remove = invoke_cli(
        [
            "agents",
            "subagents",
            "remove",
            "--subagent-id",
            "architecture",
            "--json-output",
        ]
    )
    assert remove.exit_code == 0, remove.stdout

    show = invoke_cli(
        ["agents", "subagents", "show", "--subagent-id", "architecture", "--json-output"]
    )
    restored = json.loads(show.stdout)
    assert restored["origin"] == "builtin"
    assert restored["bodySource"] == "template:architecture"


def test_remove_enabled_project_subagent_requires_force(
    tmp_path,
    monkeypatch,
    invoke_cli,
    init_memory_branch,
    write_args_file,
) -> None:
    project_path = tmp_path / "demo"
    project_path.mkdir()
    monkeypatch.chdir(project_path)
    from tests.support import write_madspec_config

    write_madspec_config(project_path, branch="main", agent_environment="copilot")
    init_memory_branch(branch="main", project_path=project_path)

    payload_file = write_args_file(
        "api-auditor.json",
        {
            "title": "API Auditor",
            "description": "Reviews API consistency for the repository.",
            "purpose": "Track API contract mismatches.",
            "defaultStage": "review",
            "executionModeHint": "parallel",
            "dependencies": [],
            "toolPolicy": {"read": True, "search": True, "edit": False, "write": False, "bash": False},
            "outputContract": {"deliverable": "api findings", "writeBack": "through canonical CLI only"},
        },
    )
    body_file = write_args_file("api-auditor.md", "Audit API contracts.\n")
    create = invoke_cli(
        [
            "agents",
            "subagents",
            "create",
            "--subagent-id",
            "api-auditor",
            "--from-file",
            str(payload_file),
            "--body-file",
            str(body_file),
            "--json-output",
        ]
    )
    assert create.exit_code == 0, create.stdout
    enable = invoke_cli(
        ["agents", "subagents", "enable", "--subagent-id", "api-auditor", "--json-output"]
    )
    assert enable.exit_code == 0, enable.stdout

    remove = invoke_cli(
        ["agents", "subagents", "remove", "--subagent-id", "api-auditor", "--json-output"]
    )
    assert remove.exit_code == 1

    force_remove = invoke_cli(
        [
            "agents",
            "subagents",
            "remove",
            "--subagent-id",
            "api-auditor",
            "--force",
            "--json-output",
        ]
    )
    assert force_remove.exit_code == 0, force_remove.stdout
    payload = json.loads(force_remove.stdout)
    assert "api-auditor" not in payload["profile"]["enabledSubagentIds"]


def test_legacy_agents_state_migrates_to_enabled_ids_and_catalog(
    tmp_path,
    monkeypatch,
    invoke_cli,
) -> None:
    project_path = tmp_path / "demo"
    project_path.mkdir(parents=True)
    monkeypatch.chdir(project_path)
    from tests.support import write_madspec_config

    write_madspec_config(project_path, branch="main", agent_environment="cursor-agent")
    agents_dir = project_path / ".madspec" / "system" / "agents"
    agents_dir.mkdir(parents=True)
    legacy_state = {
        "schemaVersion": 1,
        "profileId": "legacy",
        "environmentId": "cursor-agent",
        "revision": 2,
        "createdAt": "2026-03-18T00:00:00Z",
        "updatedAt": "2026-03-18T00:00:00Z",
        "subagents": [
            {"subagentId": "architecture", "enabled": True},
            {"subagentId": "testing", "enabled": False},
            {"subagentId": "security", "enabled": True},
        ],
    }
    (agents_dir / "state.json").write_text(json.dumps(legacy_state), encoding="utf-8")

    profile = invoke_cli(["agents", "profile", "--json-output"])
    assert profile.exit_code == 0, profile.stdout
    payload = json.loads(profile.stdout)
    assert set(payload["profile"]["enabledSubagentIds"]) == {"architecture", "security"}
    assert (agents_dir / "catalog.json").exists()
