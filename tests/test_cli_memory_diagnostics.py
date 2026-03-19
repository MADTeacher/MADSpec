from __future__ import annotations

import json

from madspec_cli.memory import append_jsonl, get_memory_paths, make_record, write_json

from tests.support import step_metadata, step_status


def _write_progress(paths, *, planned_steps: list[str], completed_steps: list[str]) -> None:
    write_json(
        paths.progress,
        {
            "currentImplementStep": None,
            "completedSteps": completed_steps,
            "plannedSteps": planned_steps,
            "stepStatus": {
                "step-01-bootstrap": step_status(
                    status="completed",
                    completed_at="2026-03-10T10:00:00+00:00",
                    tdd_phase="completed",
                    red=["uv run pytest tests/test_bootstrap.py -q"],
                    green=["uv run pytest tests/test_bootstrap.py -q"],
                    refactor_note="No refactor needed.",
                ),
                "step-02-auth-flow": step_status(status="planned"),
                "step-03-billing": step_status(status="planned"),
            },
            "stepMetadata": {
                "step-01-bootstrap": step_metadata("code", "required"),
                "step-02-auth-flow": step_metadata("code", "required"),
                "step-03-billing": step_metadata("code", "required"),
            },
            "coversFunctions": {
                "step-01-bootstrap": {"p1": ["Authentication"], "p2": [], "p3": []},
                "step-02-auth-flow": {"p1": ["Sessions"], "p2": [], "p3": []},
                "step-03-billing": {"p1": [], "p2": ["Billing"], "p3": []},
            },
            "planningMetadata": {
                "lastPlannedStep": "step-03-billing",
                "planningPhase": "initial",
                "totalStepsEstimated": 3,
                "stepDependencies": {
                    "step-02-auth-flow": ["step-01-bootstrap"],
                    "step-03-billing": ["step-02-auth-flow"],
                },
                "progressMetrics": {
                    "p1Coverage": {"covered": 2, "total": 2, "percentage": 100},
                    "p2Coverage": {"covered": 1, "total": 1, "percentage": 100},
                    "p3Coverage": {"covered": 0, "total": 0, "percentage": 0},
                    "overallProgress": 80,
                },
            },
        },
    )


def test_memory_why_next_step_and_explain_show_step_reasoning(init_memory_branch, invoke_cli) -> None:
    project_path = init_memory_branch(branch="main")
    paths = get_memory_paths(project_path, "main")
    _write_progress(
        paths,
        planned_steps=["step-01-bootstrap", "step-02-auth-flow", "step-03-billing"],
        completed_steps=["step-01-bootstrap"],
    )
    append_jsonl(
        paths.decisions,
        [
            make_record(
                "main",
                "mvp.plan",
                "agent",
                "Validated planning decision",
                status="validated",
                semantic_kind="decision",
                record_type="decision",
                evidence=["implementation-plan.md"],
            )
        ],
    )

    why_result = invoke_cli(
        ["memory", "why-next-step", "--branch", "main", "--stage", "mvp.implement", "--json-output"]
    )
    assert why_result.exit_code == 0, why_result.stdout
    why_payload = json.loads(why_result.stdout)
    assert why_payload["selected_step"] == "step-02-auth-flow"
    steps = {item["step_id"]: item for item in why_payload["steps"]}
    assert steps["step-01-bootstrap"]["state"] == "completed"
    assert steps["step-02-auth-flow"]["state"] == "ready"
    assert steps["step-03-billing"]["state"] == "blocked"
    assert steps["step-03-billing"]["missing_dependencies"] == ["step-02-auth-flow"]
    assert steps["step-02-auth-flow"]["gate_summary"]["overall_status"] in {"passed", "warning", "pending"}
    assert "gates" in steps["step-02-auth-flow"]["gate_summary"]

    explain_result = invoke_cli(
        [
            "memory",
            "explain",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--query",
            "Validated planning decision",
            "--json-output",
        ]
    )
    assert explain_result.exit_code == 0, explain_result.stdout
    explain_payload = json.loads(explain_result.stdout)
    assert explain_payload["summary"]["selected_step"] == "step-02-auth-flow"
    assert explain_payload["recall_explanation"]["resolved_query"] == "Validated planning decision"
    assert explain_payload["gate_summary"]["overall_status"] in {"passed", "warning", "pending"}
    assert explain_payload["context"]["gate_summary"]["overall_status"] == explain_payload["gate_summary"]["overall_status"]
    assert "explicit_query" in explain_payload["recall_explanation"]["triggers"]
    influence_kinds = {item["kind"] for item in explain_payload["influences"]}
    assert "semantic_decision" in influence_kinds
    assert "recall_match" in influence_kinds

    why_text_result = invoke_cli(["memory", "why-next-step", "--branch", "main", "--stage", "mvp.implement"])
    assert why_text_result.exit_code == 0, why_text_result.stdout
    assert "Selected step:" in why_text_result.stdout
    assert "gates=" in why_text_result.stdout


def test_memory_timeline_includes_progress_snapshot_and_retrieval_runs(init_memory_branch, invoke_cli) -> None:
    project_path = init_memory_branch(branch="main")
    paths = get_memory_paths(project_path, "main")
    _write_progress(
        paths,
        planned_steps=["step-01-bootstrap", "step-02-auth-flow", "step-03-billing"],
        completed_steps=["step-01-bootstrap"],
    )
    append_jsonl(
        paths.facts,
        [
            make_record(
                "main",
                "mvp.plan",
                "agent",
                "Billing dependencies captured",
                status="validated",
                semantic_kind="fact",
                record_type="fact",
            )
        ],
    )

    search_result = invoke_cli(
        [
            "memory",
            "search",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--query",
            "Billing dependencies captured",
            "--json-output",
        ]
    )
    assert search_result.exit_code == 0, search_result.stdout

    timeline_result = invoke_cli(
        ["memory", "timeline", "--branch", "main", "--stage", "mvp.plan", "--json-output"]
    )
    assert timeline_result.exit_code == 0, timeline_result.stdout
    payload = json.loads(timeline_result.stdout)
    assert any(item["source_type"] == "retrieval_run" for item in payload["items"])
    assert any(
        item["source_type"] == "snapshot" and item["stage"] == "runtime.progress"
        for item in payload["items"]
    )
    timestamps = [item["timestamp"] for item in payload["items"]]
    assert timestamps == sorted(timestamps, reverse=True)


def test_memory_inspect_record_and_conflicts_report_index_and_integrity(init_memory_branch, invoke_cli) -> None:
    project_path = init_memory_branch(branch="main")
    paths = get_memory_paths(project_path, "main")
    _write_progress(
        paths,
        planned_steps=["step-01-bootstrap", "step-02-auth-flow", "step-03-billing"],
        completed_steps=["step-01-bootstrap"],
    )
    inspected_record = make_record(
        "main",
        "mvp.plan",
        "agent",
        "Inspect me",
        status="validated",
        semantic_kind="decision",
        record_type="decision",
        evidence=["implementation-plan.md"],
    )
    conflicted_record = make_record(
        "main",
        "mvp.plan",
        "agent",
        "Conflicting billing note",
        status="conflicted",
        semantic_kind="fact",
        record_type="fact",
    )
    append_jsonl(paths.decisions, [inspected_record])
    append_jsonl(paths.facts, [conflicted_record])

    reindex_result = invoke_cli(["memory", "reindex", "--branch", "main", "--json-output"])
    assert reindex_result.exit_code == 0, reindex_result.stdout

    inspect_result = invoke_cli(
        [
            "memory",
            "inspect-record",
            "--branch",
            "main",
            "--id",
            inspected_record["id"],
            "--json-output",
        ]
    )
    assert inspect_result.exit_code == 0, inspect_result.stdout
    inspect_payload = json.loads(inspect_result.stdout)
    assert inspect_payload["found"] is True
    assert inspect_payload["record"]["payload"]["summary"] == "Inspect me"
    assert inspect_payload["source_file"].endswith("semantic/decisions.jsonl:1")
    assert inspect_payload["indexed"]["is_indexed"] is True

    (project_path / ".madspec" / "main" / "concept.md").write_text("# Drifted concept\n", encoding="utf-8")

    conflicts_result = invoke_cli(["memory", "conflicts", "--branch", "main", "--json-output"])
    assert conflicts_result.exit_code == 0, conflicts_result.stdout
    conflicts_payload = json.loads(conflicts_result.stdout)
    assert any(item["record_id"] == conflicted_record["id"] for item in conflicts_payload["record_conflicts"])
    assert conflicts_payload["integrity_conflicts"]

    missing_inspect = invoke_cli(
        ["memory", "inspect-record", "--branch", "main", "--id", "missing-record", "--json-output"]
    )
    assert missing_inspect.exit_code == 1, missing_inspect.stdout


def test_memory_doctor_reports_healthy_state_and_generated_view_drift(init_memory_branch, invoke_cli) -> None:
    project_path = init_memory_branch(branch="main")

    reindex_result = invoke_cli(["memory", "reindex", "--branch", "main", "--json-output"])
    assert reindex_result.exit_code == 0, reindex_result.stdout

    healthy_result = invoke_cli(["memory", "doctor", "--branch", "main", "--json-output"])
    assert healthy_result.exit_code == 0, healthy_result.stdout
    healthy_payload = json.loads(healthy_result.stdout)
    check_names = {item["name"] for item in healthy_payload["checks"]}
    assert {"branch_layout", "integrity", "sqlite", "vector", "indexing", "generated_views"} <= check_names
    assert healthy_payload["status"] in {"ok", "warn"}
    assert set(healthy_payload["db"]) >= {"exists", "sqlite_path", "tables"}
    assert set(healthy_payload["vector"]) >= {"backend", "memory_chunk_count", "artifact_chunk_count"}

    (project_path / ".madspec" / "main" / "concept.md").write_text("# Drifted concept\n", encoding="utf-8")

    drift_result = invoke_cli(["memory", "doctor", "--branch", "main", "--json-output"])
    assert drift_result.exit_code == 1, drift_result.stdout
    drift_payload = json.loads(drift_result.stdout)
    assert drift_payload["status"] == "error"
    assert drift_payload["generated_views"]["status"] == "error"

    doctor_text_result = invoke_cli(["memory", "doctor", "--branch", "main"])
    assert doctor_text_result.exit_code == 1, doctor_text_result.stdout
    assert "Overall status:" in doctor_text_result.stdout
