from __future__ import annotations

import json
from pathlib import Path

from madspec_cli.memory import (
    append_jsonl,
    consolidate_branch_memory,
    determine_next_step,
    ensure_memory_layout,
    get_memory_paths,
    learn_from_outcomes,
    make_record,
    promote_validated_records,
    register_planned_step,
    retrieve_memory_context,
    validate_branch_memory,
    write_json,
)


def _bootstrap_project(tmp_path: Path, branch: str = "main") -> dict[str, Path]:
    project_path = tmp_path / "project"
    project_path.mkdir()
    madspec_dir = project_path / ".madspec"
    madspec_dir.mkdir()
    (madspec_dir / "config.json").write_text(
        json.dumps({"currentBranch": branch, "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )
    ensure_memory_layout(project_path, branch)
    return get_memory_paths(project_path, branch)


def _write_mvp_concept(branch_dir: Path) -> None:
    (branch_dir / "concept.md").write_text(
        """# Concept

### Приоритет 1
- User authentication: sign in users
- Session persistence: keep users logged in

### Приоритет 2
- Profile customization: update display name

### Приоритет 3
- Export settings: download preferences
""",
        encoding="utf-8",
    )


def test_consolidate_is_deterministic_for_same_memory_state(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)
    step_dir = paths["branch_dir"] / "steps" / "step-01-bootstrap"
    step_dir.mkdir(parents=True)

    write_json(
        paths["active_session"],
        {
            "branch": "main",
            "active_goal": "Build memory-aware project",
            "stage": "mvp.plan",
            "current_step": "step-01-bootstrap",
            "pending_actions": ["plan first step"],
            "open_questions": ["Need API contract?"],
            "current_hypotheses": ["Bootstrap first"],
            "last_checkpoint_at": "2026-03-10T00:00:00+00:00",
            "updated_at": "2026-03-10T00:00:00+00:00",
        },
    )
    write_json(
        paths["progress"],
        {
            "currentImplementStep": "step-01-bootstrap",
            "completedSteps": [],
            "plannedSteps": ["step-01-bootstrap"],
            "stepStatus": {
                "step-01-bootstrap": {"status": "planned", "completedAt": None}
            },
            "coversFunctions": {
                "step-01-bootstrap": {"p1": ["User authentication"], "p2": [], "p3": []}
            },
            "planningMetadata": {
                "lastPlannedStep": "step-01-bootstrap",
                "planningPhase": "incremental",
                "totalStepsEstimated": 1,
                "stepDependencies": {"step-01-bootstrap": []},
                "progressMetrics": {
                    "p1Coverage": {"covered": 1, "total": 1, "percentage": 100},
                    "p2Coverage": {"covered": 0, "total": 0, "percentage": 0},
                    "p3Coverage": {"covered": 0, "total": 0, "percentage": 0},
                    "overallProgress": 100,
                },
            },
        },
    )
    append_jsonl(
        paths["decision_log"],
        [
            make_record(
                "main",
                "mvp.plan",
                "agent",
                "Bootstrap the project first",
                step_id="step-01-bootstrap",
                status="validated",
                evidence=[".madspec/main/concept.md"],
                semantic_kind="decision",
                record_type="decision",
            )
        ],
    )
    append_jsonl(
        paths["facts"],
        [
            make_record(
                "main",
                "architecture",
                "agent",
                "The project uses structured memory as source of truth",
                status="validated",
                evidence=["README.md"],
                semantic_kind="fact",
                record_type="fact",
            )
        ],
    )

    first_run = consolidate_branch_memory(paths["branch_dir"].parents[1], "main")
    snapshot_a = {
        path.name: path.read_text(encoding="utf-8")
        for path in first_run
        if path.name in {"project-context.md", "planning-context-cache.md", "planning-context.md"}
    }
    second_run = consolidate_branch_memory(paths["branch_dir"].parents[1], "main")
    snapshot_b = {
        path.name: path.read_text(encoding="utf-8")
        for path in second_run
        if path.name in {"project-context.md", "planning-context-cache.md", "planning-context.md"}
    }

    assert snapshot_a == snapshot_b
    assert "Generated from structured memory" in snapshot_a["project-context.md"]
    assert "Bootstrap the project first" in snapshot_a["planning-context.md"]


def test_validate_reports_invalid_status_and_broken_step_reference(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)
    write_json(
        paths["progress"],
        {
            "currentImplementStep": "step-99-missing",
            "completedSteps": ["step-01-bootstrap"],
            "plannedSteps": ["step-01-bootstrap"],
            "stepStatus": {"step-ghost": {"status": "completed", "completedAt": "2026-03-10"}},
            "coversFunctions": {},
            "planningMetadata": {
                "lastPlannedStep": "step-01-bootstrap",
                "planningPhase": "incremental",
                "totalStepsEstimated": 1,
                "stepDependencies": {"step-01-bootstrap": ["step-02-missing"]},
                "progressMetrics": {
                    "p1Coverage": {"covered": 0, "total": 0, "percentage": 0},
                    "p2Coverage": {"covered": 0, "total": 0, "percentage": 0},
                    "p3Coverage": {"covered": 0, "total": 0, "percentage": 0},
                    "overallProgress": 0,
                },
            },
        },
    )
    append_jsonl(
        paths["events"],
        [
            {
                "id": "evt-1",
                "ts": "2026-03-10T00:00:00+00:00",
                "branch": "main",
                "stage": "mvp.implement",
                "step_id": None,
                "status": "bad-status",
                "source": "test",
                "summary": "Broken event",
                "evidence": [],
                "scope": "branch",
            }
        ],
    )

    errors = validate_branch_memory(paths["branch_dir"].parents[1], "main")

    assert any("currentImplementStep must be null or reference a planned step" in error for error in errors)
    assert any("invalid status 'bad-status'" in error for error in errors)
    assert any("dependency 'step-02-missing'" in error for error in errors)


def test_promote_retrieve_and_learn_flow(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)
    append_jsonl(
        paths["decision_log"],
        [
            make_record(
                "main",
                "mvp.plan",
                "agent",
                "Need a validated architectural fact",
                status="validated",
                evidence=["README.md"],
                semantic_kind="fact",
                record_type="decision",
            ),
            make_record(
                "main",
                "mvp.plan",
                "agent",
                "Need an API contract",
                status="validated",
                evidence=["contracts/openapi.yaml"],
                semantic_kind="contract",
                record_type="decision",
            ),
        ],
    )

    promoted = promote_validated_records(paths["branch_dir"].parents[1], "main")
    context = retrieve_memory_context(paths["branch_dir"].parents[1], "main", "mvp.plan")

    assert promoted == {"fact": 1, "decision": 0, "contract": 1}
    assert len(context["semantic"]["facts"]) == 1
    assert len(context["semantic"]["contracts"]) == 1

    learning_input = paths["branch_dir"].parents[1] / "learning.json"
    learning_input.write_text(
        json.dumps(
            [
                {
                    "kind": "review_finding",
                    "stage": "review",
                    "summary": "Progress updates are easy to forget",
                    "evidence": ["tests.md"],
                    "source": "review",
                },
                {
                    "kind": "successful_workaround",
                    "stage": "mvp.implement",
                    "summary": "Running consolidate after each checkpoint keeps views in sync",
                    "evidence": ["README.md"],
                    "source": "dogfood",
                    "status": "validated",
                    "semantic_kind": "decision",
                },
            ]
        ),
        encoding="utf-8",
    )

    learned = learn_from_outcomes(paths["branch_dir"].parents[1], "main", learning_input)

    assert learned["events"] == 2
    assert learned["semantic_candidates"] == 2


def test_determine_next_step_validates_candidate_and_selects_ready_step(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)
    write_json(
        paths["progress"],
        {
            "currentImplementStep": None,
            "completedSteps": ["step-01-bootstrap"],
            "plannedSteps": ["step-01-bootstrap", "step-02-api", "step-03-ui"],
            "stepStatus": {
                "step-01-bootstrap": {"status": "completed", "completedAt": "2026-03-10"},
                "step-02-api": {"status": "planned", "completedAt": None},
                "step-03-ui": {"status": "planned", "completedAt": None},
            },
            "coversFunctions": {
                "step-01-bootstrap": {"p1": ["User authentication"], "p2": [], "p3": []},
                "step-02-api": {"p1": ["Session persistence"], "p2": [], "p3": []},
                "step-03-ui": {"p1": [], "p2": ["Profile customization"], "p3": []},
            },
            "planningMetadata": {
                "lastPlannedStep": "step-03-ui",
                "planningPhase": "incremental",
                "totalStepsEstimated": 3,
                "stepDependencies": {
                    "step-02-api": ["step-01-bootstrap"],
                    "step-03-ui": ["step-02-api"],
                },
                "progressMetrics": {
                    "p1Coverage": {"covered": 1, "total": 2, "percentage": 50},
                    "p2Coverage": {"covered": 0, "total": 1, "percentage": 0},
                    "p3Coverage": {"covered": 0, "total": 0, "percentage": 0},
                    "overallProgress": 40,
                },
            },
        },
    )

    candidate = determine_next_step(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.plan",
        candidate_step="step-04-auth-flow",
        candidate_dependencies=["step-02-api"],
    )
    invalid_candidate = determine_next_step(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.plan",
        candidate_step="bad-step-name",
        candidate_dependencies=["step-99-missing"],
    )
    selected = determine_next_step(paths["branch_dir"].parents[1], "main", "mvp.implement")

    assert candidate["accepted"] is True
    assert invalid_candidate["accepted"] is False
    assert any("must match step-XX-kebab-case" in error for error in invalid_candidate["errors"])
    assert selected["selected_step"] == "step-02-api"
    assert "step-03-ui" not in selected["executable_steps"]


def test_register_planned_step_updates_coverage_metrics(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)
    _write_mvp_concept(paths["branch_dir"])

    first = register_planned_step(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.plan",
        step_id="step-01-authentication",
        covers=["User authentication"],
        summary="Plan authentication bootstrap",
    )
    second = register_planned_step(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.plan",
        step_id="step-02-session-persistence",
        covers=["Session persistence", "Profile customization"],
        depends_on=["step-01-authentication"],
    )

    progress = json.loads(paths["progress"].read_text(encoding="utf-8"))

    assert first["accepted"] is True
    assert second["accepted"] is True
    assert progress["planningMetadata"]["lastPlannedStep"] == "step-02-session-persistence"
    assert progress["planningMetadata"]["progressMetrics"]["p1Coverage"] == {
        "covered": 2,
        "total": 2,
        "percentage": 100,
    }
    assert progress["planningMetadata"]["progressMetrics"]["p2Coverage"] == {
        "covered": 1,
        "total": 1,
        "percentage": 100,
    }
    assert progress["planningMetadata"]["progressMetrics"]["overallProgress"] == 80
    assert progress["coversFunctions"]["step-02-session-persistence"]["p2"] == ["Profile customization"]
    assert validate_branch_memory(paths["branch_dir"].parents[1], "main") == []
