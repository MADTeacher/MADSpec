from __future__ import annotations

import json

from madspec_cli.memory import append_jsonl, get_memory_paths, make_record


def test_memory_commands_support_validation_and_retrieve_json(
    make_madspec_project,
    invoke_cli,
    write_concept_markdown,
    create_step_artifacts,
) -> None:
    project_path = make_madspec_project()
    branch_dir = project_path / ".madspec" / "main"
    branch_dir.mkdir(parents=True, exist_ok=True)
    write_concept_markdown(branch_dir, variant="auth_sessions")

    result = invoke_cli(["memory", "init", "--branch", "main"])
    assert result.exit_code == 0, result.stdout
    create_step_artifacts(branch_dir, "step-01-bootstrap")
    create_step_artifacts(branch_dir, "step-02-auth-flow")

    capture_result = invoke_cli(
        [
            "memory",
            "capture",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--decision",
            "Validated planning decision",
            "--evidence",
            "README.md",
            "--json-output",
        ]
    )
    assert capture_result.exit_code == 0, capture_result.stdout

    validate_result = invoke_cli(["memory", "validate", "--branch", "main", "--json-output"])
    assert validate_result.exit_code == 0, validate_result.stdout
    assert json.loads(validate_result.stdout)["valid"] is True

    db_status_result = invoke_cli(["memory", "db-status", "--branch", "main", "--json-output"])
    assert db_status_result.exit_code == 0, db_status_result.stdout
    db_status_payload = json.loads(db_status_result.stdout)
    assert db_status_payload["sqlite_path"] == ".madspec/system/memory/memory.sqlite"
    assert db_status_payload["stage_snapshots"] >= 1
    assert db_status_payload["vector_backend"] == "lancedb"

    reindex_result = invoke_cli(["memory", "reindex", "--branch", "main", "--json-output"])
    assert reindex_result.exit_code == 0, reindex_result.stdout
    reindex_payload = json.loads(reindex_result.stdout)
    assert reindex_payload["lease_acquired"] is True
    assert reindex_payload["processed"] >= 1

    retrieve_result = invoke_cli(
        [
            "memory",
            "retrieve",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--query",
            "Validated planning decision",
            "--disable-semantic",
            "--json-output",
        ]
    )
    assert retrieve_result.exit_code == 0, retrieve_result.stdout
    payload = json.loads(retrieve_result.stdout)
    assert payload["runtime_revision"] >= 0
    assert payload["semantic"]["decisions"][0]["summary"] == "Validated planning decision"
    assert payload["recall"]["resolved_query"] == "Validated planning decision"
    assert payload["recall"]["semantic_enabled"] is False
    assert payload["recall"]["merged"][0]["summary"] == "Validated planning decision"
    assert payload["observability"]["shared_branch_state"]["runtime_revision"] >= 0
    assert payload["observability"]["summary"]["projection_status"] in {"ok", "warn", "error"}

    search_result = invoke_cli(
        [
            "memory",
            "search",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--query",
            "Validated planning decision",
            "--json-output",
        ]
    )
    assert search_result.exit_code == 0, search_result.stdout
    search_payload = json.loads(search_result.stdout)
    assert search_payload["runtime_revision"] >= 0
    assert search_payload["exact_matches"]
    assert search_payload["merged"][0]["summary"] == "Validated planning decision"
    assert search_payload["observability"]["summary"]["pending_proposal_count"] >= 0
    assert "current_session_state" in search_payload["observability"]

    next_step_candidate = invoke_cli(
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
        ]
    )
    assert next_step_candidate.exit_code == 1, next_step_candidate.stdout

    register_first = invoke_cli(
        [
            "memory",
            "register-step",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--step-id",
            "step-01-bootstrap",
            "--step-kind",
            "code",
            "--covers",
            "Authentication",
            "--json-output",
        ]
    )
    assert register_first.exit_code == 0, register_first.stdout

    register_second = invoke_cli(
        [
            "memory",
            "register-step",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--step-id",
            "step-02-auth-flow",
            "--step-kind",
            "code",
            "--covers",
            "Sessions",
            "--depends-on",
            "step-01-bootstrap",
            "--json-output",
        ]
    )
    assert register_second.exit_code == 0, register_second.stdout

    start_result = invoke_cli(
        ["memory", "start-step", "--branch", "main", "--stage", "mvp.implement", "--json-output"]
    )
    assert start_result.exit_code == 0, start_result.stdout
    assert json.loads(start_result.stdout)["step_id"] == "step-01-bootstrap"

    checkpoint_result = invoke_cli(
        [
            "memory",
            "checkpoint-step",
            "--branch",
            "main",
            "--stage",
            "mvp.implement",
            "--step-id",
            "step-01-bootstrap",
            "--tdd-phase",
            "red",
            "--summary",
            "Bootstrap test is red",
            "--red-evidence",
            "uv run pytest tests/test_bootstrap.py -q",
            "--json-output",
        ]
    )
    assert checkpoint_result.exit_code == 0, checkpoint_result.stdout

    complete_result = invoke_cli(
        [
            "memory",
            "complete-step",
            "--branch",
            "main",
            "--stage",
            "mvp.implement",
            "--step-id",
            "step-01-bootstrap",
            "--summary",
            "Bootstrap completed",
            "--green-evidence",
            "uv run pytest tests/test_bootstrap.py -q",
            "--refactor-note",
            "No refactor needed.",
            "--json-output",
        ]
    )
    assert complete_result.exit_code == 0, complete_result.stdout

    next_step_select = invoke_cli(
        ["memory", "next-step", "--branch", "main", "--stage", "mvp.implement", "--json-output"]
    )
    assert next_step_select.exit_code == 0, next_step_select.stdout
    next_step_payload = json.loads(next_step_select.stdout)
    assert next_step_payload["selected_step"] == "step-02-auth-flow"


def test_memory_retrieve_and_explain_support_toon_output(make_madspec_project, invoke_cli) -> None:
    project_path = make_madspec_project()

    init_result = invoke_cli(["memory", "init", "--branch", "main"])
    assert init_result.exit_code == 0, init_result.stdout

    paths = get_memory_paths(project_path, "main")
    append_jsonl(
        paths["decision_log"],
        [
            make_record(
                "main",
                "mvp.plan",
                "agent",
                "Choose staged rollout",
                status="validated",
                evidence=["docs/cli/memory.md"],
                semantic_kind="decision",
                record_type="decision",
            )
        ],
    )

    retrieve_result = invoke_cli(
        ["memory", "retrieve", "--branch", "main", "--stage", "mvp.plan", "--toon-output"]
    )
    assert retrieve_result.exit_code == 0, retrieve_result.stdout
    assert "branch: main" in retrieve_result.stdout
    assert "policy_context:" in retrieve_result.stdout
    assert "semantic:" in retrieve_result.stdout

    explain_result = invoke_cli(
        ["memory", "explain", "--branch", "main", "--stage", "mvp.plan", "--toon-output"]
    )
    assert explain_result.exit_code == 0, explain_result.stdout
    assert "branch: main" in explain_result.stdout
    assert "runtime_revision:" in explain_result.stdout
    assert "summary:" in explain_result.stdout
    assert "gate_summary:" in explain_result.stdout
