from __future__ import annotations

import json

from madspec_cli.memory import append_jsonl, get_memory_paths, make_record, read_jsonl, write_json

from tests.support import step_metadata, step_status


def _init_branch(invoke_cli, branch: str) -> None:
    result = invoke_cli(["memory", "init", "--branch", branch])
    assert result.exit_code == 0, result.stdout


def _write_progress(paths, *, dependencies: list[str], status: str) -> None:
    status_payload = (
        step_status(
            status="completed",
            completed_at="2026-03-16T10:00:00+00:00",
            tdd_phase="completed",
            red=["uv run pytest tests/test_billing.py -q"],
            green=["uv run pytest tests/test_billing.py -q"],
            refactor_note="Billing step merged cleanly.",
        )
        if status == "completed"
        else step_status(status=status)
    )
    write_json(
        paths.progress,
        {
            "currentImplementStep": None,
            "completedSteps": ["step-01-billing"] if status == "completed" else [],
            "plannedSteps": ["step-01-billing"],
            "stepStatus": {
                "step-01-billing": status_payload,
            },
            "stepMetadata": {
                "step-01-billing": step_metadata("code", "required"),
            },
            "coversFunctions": {
                "step-01-billing": {"p1": ["Billing"], "p2": [], "p3": []},
            },
            "planningMetadata": {
                "lastPlannedStep": "step-01-billing",
                "planningPhase": "initial",
                "totalStepsEstimated": 1,
                "stepDependencies": {
                    "step-01-billing": dependencies,
                },
                "progressMetrics": {
                    "p1Coverage": {"covered": 1, "total": 1, "percentage": 100},
                    "p2Coverage": {"covered": 0, "total": 0, "percentage": 0},
                    "p3Coverage": {"covered": 0, "total": 0, "percentage": 0},
                    "overallProgress": 50,
                },
            },
        },
    )


def test_memory_compare_branches_reports_source_only_semantic_delta(make_madspec_project, invoke_cli) -> None:
    project_path = make_madspec_project(branch="main")
    _init_branch(invoke_cli, "main")
    _init_branch(invoke_cli, "feature/source")

    source_paths = get_memory_paths(project_path, "feature/source")
    append_jsonl(
        source_paths.facts,
        [
            make_record(
                "feature/source",
                "mvp.plan",
                "agent",
                "Source-only validated fact",
                status="validated",
                semantic_kind="fact",
                record_type="fact",
            )
        ],
    )

    result = invoke_cli(
        [
            "memory",
            "compare-branches",
            "--source-branch",
            "feature/source",
            "--target-branch",
            "main",
            "--json-output",
        ]
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["summary"]["autoActionCount"] >= 1
    assert payload["summary"]["conflictCount"] == 0
    incoming = payload["differences"]["semantic"]["facts"]["incoming"]
    assert any(item["summary"] == "Source-only validated fact" for item in incoming)


def test_memory_compare_branches_three_way_avoids_false_conflicts(make_madspec_project, invoke_cli) -> None:
    project_path = make_madspec_project(branch="main")
    _init_branch(invoke_cli, "main")
    _init_branch(invoke_cli, "feature/source")
    _init_branch(invoke_cli, "feature/target")

    source_paths = get_memory_paths(project_path, "feature/source")
    append_jsonl(
        source_paths.decisions,
        [
            make_record(
                "feature/source",
                "mvp.plan",
                "agent",
                "Three-way merge decision",
                status="validated",
                semantic_kind="decision",
                record_type="decision",
            )
        ],
    )

    result = invoke_cli(
        [
            "memory",
            "compare-branches",
            "--source-branch",
            "feature/source",
            "--target-branch",
            "feature/target",
            "--base-branch",
            "main",
            "--json-output",
        ]
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["summary"]["conflictCount"] == 0
    assert any(
        item["summary"] == "Three-way merge decision"
        for item in payload["differences"]["semantic"]["decisions"]["incoming"]
    )


def test_memory_merge_flow_handles_conflicts_and_applies_resolved_merge(
    make_madspec_project,
    invoke_cli,
) -> None:
    project_path = make_madspec_project(branch="main")
    _init_branch(invoke_cli, "main")
    _init_branch(invoke_cli, "feature/source")
    _init_branch(invoke_cli, "feature/target")

    main_paths = get_memory_paths(project_path, "main")
    source_paths = get_memory_paths(project_path, "feature/source")
    target_paths = get_memory_paths(project_path, "feature/target")

    _write_progress(main_paths, dependencies=[], status="planned")
    _write_progress(source_paths, dependencies=[], status="completed")
    _write_progress(target_paths, dependencies=["step-99-legacy"], status="planned")

    append_jsonl(
        main_paths.decisions,
        [
            make_record(
                "main",
                "mvp.plan",
                "agent",
                "Billing knowledge",
                status="validated",
                semantic_kind="decision",
                record_type="decision",
                evidence=["base.md"],
            )
        ],
    )
    append_jsonl(
        source_paths.decisions,
        [
            make_record(
                "feature/source",
                "mvp.plan",
                "agent",
                "Billing knowledge",
                status="validated",
                semantic_kind="decision",
                record_type="decision",
                evidence=["source.md"],
            )
        ],
    )
    append_jsonl(
        target_paths.decisions,
        [
            make_record(
                "feature/target",
                "mvp.plan",
                "agent",
                "Billing knowledge",
                status="validated",
                semantic_kind="decision",
                record_type="decision",
                evidence=["target.md"],
            )
        ],
    )

    propose_result = invoke_cli(
        [
            "memory",
            "propose-merge",
            "--source-branch",
            "feature/source",
            "--target-branch",
            "feature/target",
            "--base-branch",
            "main",
            "--json-output",
        ]
    )
    assert propose_result.exit_code == 0, propose_result.stdout
    propose_payload = json.loads(propose_result.stdout)
    assert propose_payload["canApply"] is False
    conflict_ids = {item["conflictId"] for item in propose_payload["conflicts"]}
    assert any(item.startswith("progress_conflict") for item in conflict_ids)
    assert any(item.startswith("semantic_conflict") for item in conflict_ids)

    blocked_merge = invoke_cli(
        [
            "memory",
            "merge-branches",
            "--proposal-id",
            propose_payload["proposalId"],
            "--json-output",
        ]
    )
    assert blocked_merge.exit_code == 1, blocked_merge.stdout
    blocked_payload = json.loads(blocked_merge.stdout)
    assert blocked_payload["applied"] is False

    for conflict_id in conflict_ids:
        resolve_result = invoke_cli(
            [
                "memory",
                "resolve-conflict",
                "--proposal-id",
                propose_payload["proposalId"],
                "--conflict-id",
                conflict_id,
                "--resolution",
                "take_source",
                "--json-output",
            ]
        )
        assert resolve_result.exit_code == 0, resolve_result.stdout

    preview_result = invoke_cli(
        [
            "memory",
            "preview-merge",
            "--proposal-id",
            propose_payload["proposalId"],
            "--json-output",
        ]
    )
    assert preview_result.exit_code == 0, preview_result.stdout
    preview_payload = json.loads(preview_result.stdout)
    assert preview_payload["canApply"] is True

    merge_result = invoke_cli(
        [
            "memory",
            "merge-branches",
            "--proposal-id",
            propose_payload["proposalId"],
            "--json-output",
        ]
    )
    assert merge_result.exit_code == 0, merge_result.stdout
    merge_payload = json.loads(merge_result.stdout)
    assert merge_payload["applied"] is True
    assert merge_payload["validation"]["valid"] is True
    assert any(path.endswith("project-context.md") for path in merge_payload["generated_artifacts"])

    merged_progress = json.loads(target_paths.progress.read_text(encoding="utf-8"))
    assert merged_progress["completedSteps"] == ["step-01-billing"]
    assert merged_progress["planningMetadata"]["stepDependencies"]["step-01-billing"] == []

    merged_decisions = [row for row in read_jsonl(target_paths.decisions) if row.get("summary") == "Billing knowledge"]
    assert len(merged_decisions) == 1
    assert merged_decisions[0]["evidence"] == ["source.md"]


def test_memory_promote_branch_knowledge_populates_project_scope(make_madspec_project, invoke_cli) -> None:
    project_path = make_madspec_project(branch="main")
    _init_branch(invoke_cli, "main")
    _init_branch(invoke_cli, "feature/source")
    _init_branch(invoke_cli, "feature/target")

    source_paths = get_memory_paths(project_path, "feature/source")
    fact = make_record(
        "feature/source",
        "mvp.plan",
        "agent",
        "Promoted project fact",
        status="validated",
        semantic_kind="fact",
        record_type="fact",
        evidence=["source.md"],
    )
    append_jsonl(source_paths.facts, [fact])

    promote_result = invoke_cli(
        [
            "memory",
            "promote-branch-knowledge",
            "--source-branch",
            "feature/source",
            "--json-output",
        ]
    )
    assert promote_result.exit_code == 0, promote_result.stdout
    promote_payload = json.loads(promote_result.stdout)
    assert len(promote_payload["promoted"]) == 1

    promote_again = invoke_cli(
        [
            "memory",
            "promote-branch-knowledge",
            "--source-branch",
            "feature/source",
            "--json-output",
        ]
    )
    assert promote_again.exit_code == 0, promote_again.stdout
    assert json.loads(promote_again.stdout)["promoted"] == []

    search_result = invoke_cli(
        [
            "memory",
            "search",
            "--branch",
            "feature/target",
            "--stage",
            "mvp.plan",
            "--query",
            "Promoted project fact",
            "--scope",
            "project",
            "--json-output",
        ]
    )
    assert search_result.exit_code == 0, search_result.stdout
    search_payload = json.loads(search_result.stdout)
    assert search_payload["merged"][0]["branch"] == "__project__"

    retrieve_result = invoke_cli(
        [
            "memory",
            "retrieve",
            "--branch",
            "feature/target",
            "--stage",
            "mvp.plan",
            "--scope",
            "project",
            "--json-output",
        ]
    )
    assert retrieve_result.exit_code == 0, retrieve_result.stdout
    retrieve_payload = json.loads(retrieve_result.stdout)
    assert any(item["summary"] == "Promoted project fact" for item in retrieve_payload["semantic"]["facts"])
