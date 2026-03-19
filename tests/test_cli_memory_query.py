from __future__ import annotations

import json

from madspec_cli.memory import append_jsonl, get_memory_paths, make_record

from tests.support import step_metadata, step_status


def test_memory_commands_support_validation_and_retrieve_json(make_madspec_project, invoke_cli) -> None:
    project_path = make_madspec_project()

    result = invoke_cli(["memory", "init", "--branch", "main"])
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

    promote_result = invoke_cli(["memory", "promote", "--branch", "main", "--json-output"])
    assert promote_result.exit_code == 0, promote_result.stdout
    promoted_payload = json.loads(promote_result.stdout)
    assert promoted_payload["promoted"]["decision"] == 1

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
    assert payload["semantic"]["decisions"][0]["summary"] == "Validated planning decision"
    assert payload["recall"]["resolved_query"] == "Validated planning decision"
    assert payload["recall"]["semantic_enabled"] is False
    assert payload["recall"]["merged"][0]["summary"] == "Validated planning decision"

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
    assert search_payload["exact_matches"]
    assert search_payload["merged"][0]["summary"] == "Validated planning decision"

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

    progress = json.loads(paths["progress"].read_text(encoding="utf-8"))
    progress["plannedSteps"] = ["step-01-bootstrap", "step-02-auth-flow"]
    progress["completedSteps"] = ["step-01-bootstrap"]
    progress["stepStatus"] = {
        "step-01-bootstrap": step_status(
            status="completed",
            completed_at="2026-03-10",
            tdd_phase="completed",
            red=["uv run pytest tests/test_bootstrap.py -q"],
            green=["uv run pytest tests/test_bootstrap.py -q"],
            refactor_note="No refactor needed.",
        ),
        "step-02-auth-flow": step_status(status="planned"),
    }
    progress["stepMetadata"] = {
        "step-01-bootstrap": step_metadata("code", "required"),
        "step-02-auth-flow": step_metadata("code", "required"),
    }
    progress["planningMetadata"]["stepDependencies"] = {"step-02-auth-flow": ["step-01-bootstrap"]}
    paths["progress"].write_text(json.dumps(progress, indent=2) + "\n", encoding="utf-8")

    next_step_select = invoke_cli(
        ["memory", "next-step", "--branch", "main", "--stage", "mvp.implement", "--json-output"]
    )
    assert next_step_select.exit_code == 0, next_step_select.stdout
    next_step_payload = json.loads(next_step_select.stdout)
    assert next_step_payload["selected_step"] == "step-02-auth-flow"

