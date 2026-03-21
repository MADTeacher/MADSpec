from __future__ import annotations

import json

from madspec_cli.memory import get_memory_paths
from madspec_cli.memory.shared.system_store.store import MemoryStore


def test_memory_register_step_updates_progress_and_views(
    make_madspec_project,
    invoke_cli,
    write_concept_markdown,
    create_step_artifacts,
) -> None:
    project_path = make_madspec_project()
    branch_dir = project_path / ".madspec" / "main"
    branch_dir.mkdir(parents=True, exist_ok=True)
    write_concept_markdown(branch_dir, variant="auth_profile_export")

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
            "--covers",
            "Profile",
            "--json-output",
        ]
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
    assert progress["stepMetadata"]["step-01-authentication"] == {
        "kind": "code",
        "tddPolicy": "required",
        "waiverReason": None,
    }
    assert progress["stepStatus"]["step-01-authentication"]["tddPhase"] == "not_started"
    assert progress["planningMetadata"]["progressMetrics"]["overallProgress"] == 55
    assert (project_path / ".madspec" / "main" / "project-context.md").exists()
    assert (project_path / ".madspec" / "main" / "planning-context-cache.md").exists()
    planning_context = (
        project_path / ".madspec" / "main" / "steps" / "step-01-authentication" / "planning-context.md"
    ).read_text(encoding="utf-8")
    assert "## Gate Summary" in planning_context


def test_memory_register_step_returns_scope_busy_payload_and_text(
    make_madspec_project,
    invoke_cli,
    write_concept_markdown,
    create_step_artifacts,
) -> None:
    project_path = make_madspec_project()
    branch_dir = project_path / ".madspec" / "main"
    branch_dir.mkdir(parents=True, exist_ok=True)
    write_concept_markdown(branch_dir, variant="auth_profile_export")

    init_result = invoke_cli(["memory", "init", "--branch", "main"])
    assert init_result.exit_code == 0, init_result.stdout
    create_step_artifacts(branch_dir, "step-01-authentication")

    store = MemoryStore(project_path)
    held = store.acquire_lease("plan-catalog:main", "planner-owner", ttl_seconds=30)
    assert held["acquired"] is True

    json_result = invoke_cli(
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
    assert json_result.exit_code == 1, json_result.stdout
    payload = json.loads(json_result.stdout)
    assert payload["kind"] == "scope_busy"
    assert payload["scope_busy"]["lease_name"] == "plan-catalog:main"

    text_result = invoke_cli(
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
        ]
    )
    assert text_result.exit_code == 1, text_result.stdout
    assert "Write scope is busy." in text_result.stdout
    assert "plan-catalog:main" in text_result.stdout


def test_memory_register_step_requires_waiver_reason_for_waived_policy(
    make_madspec_project,
    invoke_cli,
    write_concept_markdown,
    create_step_artifacts,
) -> None:
    project_path = make_madspec_project()
    branch_dir = project_path / ".madspec" / "main"
    branch_dir.mkdir(parents=True, exist_ok=True)
    write_concept_markdown(branch_dir, variant="auth")

    init_result = invoke_cli(["memory", "init", "--branch", "main"])
    assert init_result.exit_code == 0, init_result.stdout
    create_step_artifacts(branch_dir, "step-01-doc-refresh")

    result = invoke_cli(
        [
            "memory",
            "register-step",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--step-id",
            "step-01-ui-polish",
            "--step-kind",
            "non-code",
            "--tdd-policy",
            "waived",
            "--covers",
            "Authentication",
            "--json-output",
        ]
    )

    assert result.exit_code == 1, result.stdout
    payload = json.loads(result.stdout)
    assert "waiver reason is required" in result.stdout
    assert payload["gate_summary"]["overall_status"] == "blocked"


def test_memory_register_step_accepts_non_code_not_applicable_policy(
    make_madspec_project,
    invoke_cli,
    write_concept_markdown,
    create_step_artifacts,
) -> None:
    project_path = make_madspec_project()
    branch_dir = project_path / ".madspec" / "main"
    branch_dir.mkdir(parents=True, exist_ok=True)
    write_concept_markdown(branch_dir, variant="auth")

    init_result = invoke_cli(["memory", "init", "--branch", "main"])
    assert init_result.exit_code == 0, init_result.stdout
    create_step_artifacts(branch_dir, "step-01-doc-refresh")

    result = invoke_cli(
        [
            "memory",
            "register-step",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--step-id",
            "step-01-doc-refresh",
            "--step-kind",
            "non-code",
            "--tdd-policy",
            "not-applicable",
            "--json-output",
        ]
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["stepMetadata"] == {
        "kind": "non-code",
        "tddPolicy": "not-applicable",
        "waiverReason": None,
    }
    assert payload["covers"] == {"p1": [], "p2": [], "p3": []}


def test_memory_register_step_requires_covers_for_code_steps(
    make_madspec_project,
    invoke_cli,
    write_concept_markdown,
) -> None:
    project_path = make_madspec_project()
    branch_dir = project_path / ".madspec" / "main"
    branch_dir.mkdir(parents=True, exist_ok=True)
    write_concept_markdown(branch_dir, variant="auth")

    init_result = invoke_cli(["memory", "init", "--branch", "main"])
    assert init_result.exit_code == 0, init_result.stdout

    result = invoke_cli(
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
            "--json-output",
        ]
    )

    assert result.exit_code == 1, result.stdout
    assert "code steps must declare at least one covered function" in result.stdout


def test_memory_register_step_rolls_back_when_step_artifacts_are_missing(
    make_madspec_project,
    invoke_cli,
    write_concept_markdown,
) -> None:
    project_path = make_madspec_project()
    branch_dir = project_path / ".madspec" / "main"
    branch_dir.mkdir(parents=True, exist_ok=True)
    write_concept_markdown(branch_dir, variant="auth")

    init_result = invoke_cli(["memory", "init", "--branch", "main"])
    assert init_result.exit_code == 0, init_result.stdout

    result = invoke_cli(
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

    paths = get_memory_paths(project_path, "main")
    progress = json.loads(paths["progress"].read_text(encoding="utf-8"))
    plan_state = json.loads(paths["plan_state"].read_text(encoding="utf-8"))
    payload = json.loads(result.stdout)

    assert result.exit_code == 0, result.stdout
    assert payload["accepted"] is True
    assert payload["projection_status"] == "stale"
    assert payload["projection_refresh_required"] is True
    assert "projection refresh failed:" in payload["warnings"][0]
    assert progress["plannedSteps"] == ["step-01-authentication"]
    assert plan_state["stepCatalog"][0]["stepId"] == "step-01-authentication"


def test_memory_register_step_rejects_invalid_step_kind_and_tdd_policy(
    make_madspec_project,
    invoke_cli,
    write_concept_markdown,
) -> None:
    project_path = make_madspec_project()
    branch_dir = project_path / ".madspec" / "main"
    branch_dir.mkdir(parents=True, exist_ok=True)
    write_concept_markdown(branch_dir, variant="auth")

    init_result = invoke_cli(["memory", "init", "--branch", "main"])
    assert init_result.exit_code == 0, init_result.stdout

    invalid_kind = invoke_cli(
        [
            "memory",
            "register-step",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--step-id",
            "step-01-auth",
            "--step-kind",
            "unknown",
            "--covers",
            "Authentication",
            "--json-output",
        ]
    )
    invalid_policy = invoke_cli(
        [
            "memory",
            "register-step",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--step-id",
            "step-01-auth",
            "--step-kind",
            "non-code",
            "--tdd-policy",
            "sometimes",
            "--covers",
            "Authentication",
            "--json-output",
        ]
    )

    assert invalid_kind.exit_code == 1, invalid_kind.stdout
    assert "step kind must be one of" in invalid_kind.stdout
    assert invalid_policy.exit_code == 1, invalid_policy.stdout
    assert "tdd policy must be one of" in invalid_policy.stdout
