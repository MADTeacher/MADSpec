from __future__ import annotations

import json

from madspec_cli.memory.shared.system_store.store import MemoryStore


def test_memory_implementation_commands_drive_step_lifecycle(
    make_madspec_project,
    invoke_cli,
    write_concept_markdown,
    create_step_artifacts,
) -> None:
    project_path = make_madspec_project()
    branch_dir = project_path / ".madspec" / "main"
    branch_dir.mkdir(parents=True, exist_ok=True)
    write_concept_markdown(branch_dir, variant="auth_sessions")

    init_result = invoke_cli(["memory", "init", "--branch", "main"])
    assert init_result.exit_code == 0, init_result.stdout
    create_step_artifacts(branch_dir, "step-01-authentication")

    register_result = invoke_cli(
        [
            "memory",
            "register-step",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--step-id",
            "step-01-authentication",
            "--step-kind",
            "code",
            "--covers",
            "Authentication",
            "--json-output",
        ]
    )
    assert register_result.exit_code == 0, register_result.stdout

    start_result = invoke_cli(
        ["memory", "start-step", "--branch", "main", "--stage", "mvp.implement", "--json-output"]
    )
    assert start_result.exit_code == 0, start_result.stdout
    assert json.loads(start_result.stdout)["step_id"] == "step-01-authentication"

    red_result = invoke_cli(
        [
            "memory",
            "checkpoint-step",
            "--branch",
            "main",
            "--stage",
            "mvp.implement",
            "--step-id",
            "step-01-authentication",
            "--tdd-phase",
            "red",
            "--summary",
            "Auth test is red",
            "--red-evidence",
            "uv run pytest tests/test_auth.py -q",
            "--json-output",
        ]
    )
    assert red_result.exit_code == 0, red_result.stdout

    complete_result = invoke_cli(
        [
            "memory",
            "complete-step",
            "--branch",
            "main",
            "--stage",
            "mvp.implement",
            "--step-id",
            "step-01-authentication",
            "--summary",
            "Authentication implemented",
            "--green-evidence",
            "uv run pytest tests/test_auth.py -q",
            "--refactor-note",
            "No refactor needed.",
            "--fact",
            "Authentication persists session data",
            "--json-output",
        ]
    )
    assert complete_result.exit_code == 0, complete_result.stdout
    complete_payload = json.loads(complete_result.stdout)
    assert complete_payload["written"]["facts"] == 1

    retrieve_result = invoke_cli(
        [
            "memory",
            "retrieve",
            "--branch",
            "main",
            "--stage",
            "mvp.implement",
            "--step-id",
            "step-01-authentication",
            "--json-output",
        ]
    )
    assert retrieve_result.exit_code == 0, retrieve_result.stdout
    retrieve_payload = json.loads(retrieve_result.stdout)
    assert retrieve_payload["step"]["status"]["status"] == "completed"
    assert retrieve_payload["step"]["status"]["tddPhase"] == "completed"
    assert retrieve_payload["semantic"]["facts"][0]["summary"] == "Authentication persists session data"
    implementation_context = (
        project_path / ".madspec" / "main" / "steps" / "step-01-authentication" / "implementation-context.md"
    ).read_text(encoding="utf-8")
    assert "## Gate Summary" in implementation_context


def test_memory_complete_step_rejects_missing_tdd_evidence_with_gate_summary(
    make_madspec_project,
    invoke_cli,
    write_concept_markdown,
    create_step_artifacts,
) -> None:
    project_path = make_madspec_project()
    branch_dir = project_path / ".madspec" / "main"
    branch_dir.mkdir(parents=True, exist_ok=True)
    write_concept_markdown(branch_dir, variant="auth_sessions")

    init_result = invoke_cli(["memory", "init", "--branch", "main"])
    assert init_result.exit_code == 0, init_result.stdout
    create_step_artifacts(branch_dir, "step-01-authentication")

    register_result = invoke_cli(
        [
            "memory",
            "register-step",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--step-id",
            "step-01-authentication",
            "--step-kind",
            "code",
            "--covers",
            "Authentication",
            "--json-output",
        ]
    )
    assert register_result.exit_code == 0, register_result.stdout

    start_result = invoke_cli(
        ["memory", "start-step", "--branch", "main", "--stage", "mvp.implement", "--json-output"]
    )
    assert start_result.exit_code == 0, start_result.stdout

    failed_complete = invoke_cli(
        [
            "memory",
            "complete-step",
            "--branch",
            "main",
            "--stage",
            "mvp.implement",
            "--step-id",
            "step-01-authentication",
            "--summary",
            "Authentication implemented without green evidence",
            "--json-output",
        ]
    )
    assert failed_complete.exit_code == 1, failed_complete.stdout
    payload = json.loads(failed_complete.stdout)
    assert payload["accepted"] is False
    assert payload["gate_summary"]["overall_status"] == "blocked"
    assert any("must record redEvidence" in item or "must record greenEvidence" in item for item in payload["errors"])


def test_memory_checkpoint_step_returns_scope_busy_payload_and_text(
    make_madspec_project,
    invoke_cli,
    write_concept_markdown,
    create_step_artifacts,
) -> None:
    project_path = make_madspec_project()
    branch_dir = project_path / ".madspec" / "main"
    branch_dir.mkdir(parents=True, exist_ok=True)
    write_concept_markdown(branch_dir, variant="auth_sessions")

    init_result = invoke_cli(["memory", "init", "--branch", "main"])
    assert init_result.exit_code == 0, init_result.stdout
    create_step_artifacts(branch_dir, "step-01-authentication")

    register_result = invoke_cli(
        [
            "memory",
            "register-step",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--step-id",
            "step-01-authentication",
            "--step-kind",
            "code",
            "--covers",
            "Authentication",
            "--json-output",
        ]
    )
    assert register_result.exit_code == 0, register_result.stdout

    start_result = invoke_cli(
        [
            "memory",
            "start-step",
            "--branch",
            "main",
            "--stage",
            "mvp.implement",
            "--step-id",
            "step-01-authentication",
            "--json-output",
        ]
    )
    assert start_result.exit_code == 0, start_result.stdout

    store = MemoryStore(project_path)
    held = store.acquire_lease("implement-step:main:step-01-authentication", "impl-owner", ttl_seconds=30)
    assert held["acquired"] is True

    json_result = invoke_cli(
        [
            "memory",
            "checkpoint-step",
            "--branch",
            "main",
            "--stage",
            "mvp.implement",
            "--step-id",
            "step-01-authentication",
            "--tdd-phase",
            "red",
            "--summary",
            "Auth test is red",
            "--red-evidence",
            "uv run pytest tests/test_auth.py -q",
            "--json-output",
        ]
    )
    assert json_result.exit_code == 1, json_result.stdout
    payload = json.loads(json_result.stdout)
    assert payload["kind"] == "scope_busy"
    assert payload["scope_busy"]["lease_name"] == "implement-step:main:step-01-authentication"

    text_result = invoke_cli(
        [
            "memory",
            "checkpoint-step",
            "--branch",
            "main",
            "--stage",
            "mvp.implement",
            "--step-id",
            "step-01-authentication",
            "--tdd-phase",
            "red",
            "--summary",
            "Auth test is red",
            "--red-evidence",
            "uv run pytest tests/test_auth.py -q",
        ]
    )
    assert text_result.exit_code == 1, text_result.stdout
    assert "Write scope is busy." in text_result.stdout
    assert "implement-step:main:step-01-authentication" in text_result.stdout
