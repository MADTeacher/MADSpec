from __future__ import annotations

import json


def test_memory_tasks_and_work_items_cli_flow(tmp_path, monkeypatch, invoke_cli, init_memory_branch) -> None:
    project_path = tmp_path / "demo"
    project_path.mkdir()
    monkeypatch.chdir(project_path)
    from tests.support import write_madspec_config

    write_madspec_config(project_path, branch="main", agent_environment="cursor-agent", phase2_enabled=True)
    init_memory_branch(branch="main", project_path=project_path)

    task_result = invoke_cli(
        [
            "memory",
            "tasks",
            "create",
            "--branch",
            "main",
            "--title",
            "Coordinate auth implementation",
            "--summary",
            "Split work between subagents",
            "--json-output",
        ]
    )
    assert task_result.exit_code == 0, task_result.stdout
    task_payload = json.loads(task_result.stdout)

    work_item_result = invoke_cli(
        [
            "memory",
            "work-items",
            "create",
            "--branch",
            "main",
            "--task-id",
            task_payload["task"]["task_id"],
            "--title",
            "Developer auth slice",
            "--type",
            "implementation",
            "--subagent-id",
            "developer",
            "--step-id",
            "step-01-authentication",
            "--path",
            "src/auth/service.py",
            "--json-output",
        ]
    )
    assert work_item_result.exit_code == 0, work_item_result.stdout
    work_item_payload = json.loads(work_item_result.stdout)

    claim_result = invoke_cli(
        [
            "memory",
            "work-items",
            "claim",
            "--branch",
            "main",
            "--work-item-id",
            work_item_payload["work_item"]["work_item_id"],
            "--session-key",
            "impl",
            "--subagent-id",
            "developer",
            "--json-output",
        ]
    )
    assert claim_result.exit_code == 0, claim_result.stdout
    claim_payload = json.loads(claim_result.stdout)
    assert claim_payload["session"]["work_item_id"] == work_item_payload["work_item"]["work_item_id"]

    list_result = invoke_cli(
        [
            "memory",
            "work-items",
            "list",
            "--branch",
            "main",
            "--session-key",
            "impl",
            "--json-output",
        ]
    )
    assert list_result.exit_code == 0, list_result.stdout
    listed = json.loads(list_result.stdout)
    assert len(listed["work_items"]) == 1
    assert listed["work_items"][0]["status"] == "claimed"

    context_result = invoke_cli(
        [
            "agents",
            "subagents",
            "context",
            "--subagent-id",
            "developer",
            "--session-key",
            "impl",
            "--json-output",
        ]
    )
    assert context_result.exit_code == 0, context_result.stdout
    context_payload = json.loads(context_result.stdout)
    assert context_payload["coordination"]["task"]["task_id"] == task_payload["task"]["task_id"]
    assert context_payload["coordination"]["work_item"]["work_item_id"] == work_item_payload["work_item"]["work_item_id"]

    release_result = invoke_cli(
        [
            "memory",
            "work-items",
            "release",
            "--branch",
            "main",
            "--work-item-id",
            work_item_payload["work_item"]["work_item_id"],
            "--session-key",
            "impl",
            "--json-output",
        ]
    )
    assert release_result.exit_code == 0, release_result.stdout
    released = json.loads(release_result.stdout)
    assert released["session"]["work_item_id"] is None


def test_memory_work_item_dependency_blocks_claim_and_explain(tmp_path, monkeypatch, invoke_cli, init_memory_branch) -> None:
    project_path = tmp_path / "demo"
    project_path.mkdir()
    monkeypatch.chdir(project_path)
    from tests.support import write_madspec_config

    write_madspec_config(project_path, branch="main", agent_environment="cursor-agent", phase2_enabled=True)
    init_memory_branch(branch="main", project_path=project_path)

    task_result = invoke_cli(["memory", "tasks", "create", "--branch", "main", "--title", "Coordinate auth", "--json-output"])
    task_payload = json.loads(task_result.stdout)
    architecture_result = invoke_cli(
        [
            "memory",
            "work-items",
            "create",
            "--branch",
            "main",
            "--task-id",
            task_payload["task"]["task_id"],
            "--title",
            "Architecture slice",
            "--type",
            "architecture",
            "--subagent-id",
            "architecture",
            "--step-id",
            "step-01-authentication",
            "--path",
            "src/auth/contracts.py",
            "--json-output",
        ]
    )
    architecture_payload = json.loads(architecture_result.stdout)
    developer_result = invoke_cli(
        [
            "memory",
            "work-items",
            "create",
            "--branch",
            "main",
            "--task-id",
            task_payload["task"]["task_id"],
            "--title",
            "Developer slice",
            "--type",
            "implementation",
            "--subagent-id",
            "developer",
            "--step-id",
            "step-01-authentication",
            "--path",
            "src/auth/service.py",
            "--depends-on-work-item",
            architecture_payload["work_item"]["work_item_id"],
            "--json-output",
        ]
    )
    assert developer_result.exit_code == 0, developer_result.stdout
    developer_payload = json.loads(developer_result.stdout)
    assert developer_payload["coordinator"]["readiness"]["status"] == "blocked"

    claim_result = invoke_cli(
        [
            "memory",
            "work-items",
            "claim",
            "--branch",
            "main",
            "--work-item-id",
            developer_payload["work_item"]["work_item_id"],
            "--session-key",
            "impl",
            "--subagent-id",
            "developer",
            "--json-output",
        ]
    )
    assert claim_result.exit_code == 1, claim_result.stdout
    claim_payload = json.loads(claim_result.stdout)
    assert claim_payload["reason"] == "readiness_blocked"
    assert claim_payload["readiness"]["status"] == "blocked"

    explain_result = invoke_cli(
        [
            "memory",
            "coordinator",
            "explain",
            "--branch",
            "main",
            "--work-item-id",
            developer_payload["work_item"]["work_item_id"],
            "--session-key",
            "impl",
            "--json-output",
        ]
    )
    assert explain_result.exit_code == 0, explain_result.stdout
    explain_payload = json.loads(explain_result.stdout)
    assert explain_payload["coordinator"]["readiness"]["status"] == "blocked"


def test_phase2_cli_commands_are_opt_in_by_default(tmp_path, monkeypatch, invoke_cli, init_memory_branch) -> None:
    project_path = tmp_path / "demo"
    project_path.mkdir()
    monkeypatch.chdir(project_path)
    from tests.support import write_madspec_config

    write_madspec_config(project_path, branch="main", agent_environment="cursor-agent")
    init_memory_branch(branch="main", project_path=project_path)

    result = invoke_cli(
        [
            "memory",
            "tasks",
            "create",
            "--branch",
            "main",
            "--title",
            "Blocked by rollout",
            "--json-output",
        ]
    )

    assert result.exit_code == 1, result.stdout
    payload = json.loads(result.stdout)
    assert payload["reason"] == "phase2_disabled"
    assert payload["message"] == "Phase 2 coordinator runtime is opt-in"
    assert payload["parallel_runtime"]["phase1Enabled"] is True
    assert payload["parallel_runtime"]["phase2Enabled"] is False
