from __future__ import annotations

import json
from pathlib import Path

from madspec_cli.memory import (
    checkpoint_stage_memory,
    append_jsonl,
    capture_stage_memory,
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
from madspec_cli.memory.implementation import (
    checkpoint_implementation_step,
    complete_implementation_step,
    start_implementation_step,
)


def _step_status(
    *,
    status: str,
    completed_at: str | None = None,
    tdd_phase: str = "not_started",
    red: list[str] | None = None,
    green: list[str] | None = None,
    refactor_note: str | None = None,
) -> dict[str, object]:
    return {
        "status": status,
        "completedAt": completed_at,
        "tddPhase": tdd_phase,
        "redEvidence": red or [],
        "greenEvidence": green or [],
        "refactorNote": refactor_note,
    }


def _step_metadata(kind: str, policy: str, waiver_reason: str | None = None) -> dict[str, object]:
    return {
        "kind": kind,
        "tddPolicy": policy,
        "waiverReason": waiver_reason,
    }


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
                "step-01-bootstrap": _step_status(status="planned")
            },
            "stepMetadata": {
                "step-01-bootstrap": _step_metadata("code", "required")
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
            "stepStatus": {
                "step-ghost": _step_status(
                    status="completed",
                    completed_at="2026-03-10",
                    tdd_phase="completed",
                    red=["uv run pytest tests/test_auth.py -q"],
                    green=["uv run pytest tests/test_auth.py -q"],
                    refactor_note="No refactor needed.",
                )
            },
            "stepMetadata": {
                "step-01-bootstrap": _step_metadata("code", "required")
            },
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
                "step-01-bootstrap": _step_status(
                    status="completed",
                    completed_at="2026-03-10",
                    tdd_phase="completed",
                    red=["uv run pytest tests/test_bootstrap.py -q"],
                    green=["uv run pytest tests/test_bootstrap.py -q"],
                    refactor_note="No refactor needed.",
                ),
                "step-02-api": _step_status(status="planned"),
                "step-03-ui": _step_status(status="planned", tdd_phase="waived"),
            },
            "stepMetadata": {
                "step-01-bootstrap": _step_metadata("code", "required"),
                "step-02-api": _step_metadata("code", "required"),
                "step-03-ui": _step_metadata("non-code", "waived", "UI polish step."),
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
        step_kind="code",
        summary="Plan authentication bootstrap",
    )
    second = register_planned_step(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.plan",
        step_id="step-02-session-persistence",
        covers=["Session persistence", "Profile customization"],
        step_kind="code",
        depends_on=["step-01-authentication"],
    )

    progress = json.loads(paths["progress"].read_text(encoding="utf-8"))

    assert first["accepted"] is True
    assert second["accepted"] is True
    assert first["stepMetadata"] == {
        "kind": "code",
        "tddPolicy": "required",
        "waiverReason": None,
    }
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
    assert progress["stepStatus"]["step-02-session-persistence"]["tddPhase"] == "not_started"
    assert progress["stepMetadata"]["step-02-session-persistence"]["tddPolicy"] == "required"
    assert progress["coversFunctions"]["step-02-session-persistence"]["p2"] == ["Profile customization"]
    assert validate_branch_memory(paths["branch_dir"].parents[1], "main") == []


def test_register_planned_step_supports_non_code_waiver(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)
    _write_mvp_concept(paths["branch_dir"])

    payload = register_planned_step(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.plan",
        step_id="step-01-design-polish",
        covers=["User authentication"],
        step_kind="non-code",
        tdd_policy="waived",
        waiver_reason="UI polish does not add executable product logic.",
    )

    progress = json.loads(paths["progress"].read_text(encoding="utf-8"))

    assert payload["accepted"] is True
    assert progress["stepMetadata"]["step-01-design-polish"] == {
        "kind": "non-code",
        "tddPolicy": "waived",
        "waiverReason": "UI polish does not add executable product logic.",
    }
    assert progress["stepStatus"]["step-01-design-polish"]["tddPhase"] == "waived"


def test_register_planned_step_supports_non_code_without_coverage(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)
    _write_mvp_concept(paths["branch_dir"])

    payload = register_planned_step(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.plan",
        step_id="step-01-project-setup",
        covers=[],
        step_kind="non-code",
        tdd_policy="not-applicable",
        summary="Bootstrap project structure before functional slices.",
    )

    progress = json.loads(paths["progress"].read_text(encoding="utf-8"))

    assert payload["accepted"] is True
    assert payload["covers"] == {"p1": [], "p2": [], "p3": []}
    assert progress["coversFunctions"]["step-01-project-setup"] == {"p1": [], "p2": [], "p3": []}
    assert progress["stepStatus"]["step-01-project-setup"]["tddPhase"] == "waived"


def test_register_planned_step_normalizes_markdown_catalog_labels(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)
    (paths["branch_dir"] / "concept.md").write_text(
        """# Concept

### Приоритет 1
- **Создание поста в CRM**
""",
        encoding="utf-8",
    )

    payload = register_planned_step(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.plan",
        step_id="step-01-posting-foundation",
        covers=["Создание поста в CRM"],
        step_kind="code",
    )

    progress = json.loads(paths["progress"].read_text(encoding="utf-8"))

    assert payload["accepted"] is True
    assert progress["coversFunctions"]["step-01-posting-foundation"] == {
        "p1": ["Создание поста в CRM"],
        "p2": [],
        "p3": [],
    }


def test_register_planned_step_reports_known_labels_for_unknown_cover(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)
    _write_mvp_concept(paths["branch_dir"])

    payload = register_planned_step(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.plan",
        step_id="step-01-authentication",
        covers=["Unknown capability"],
        step_kind="code",
    )

    assert payload["accepted"] is False
    assert "concept.md" in payload["errors"][0]
    assert "User authentication" in payload["errors"][0]


def test_implementation_lifecycle_updates_memory_incrementally(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)
    _write_mvp_concept(paths["branch_dir"])

    register_planned_step(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.plan",
        step_id="step-01-authentication",
        covers=["User authentication"],
        step_kind="code",
    )
    register_planned_step(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.plan",
        step_id="step-02-session-persistence",
        covers=["Session persistence"],
        step_kind="code",
        depends_on=["step-01-authentication"],
    )

    started = start_implementation_step(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.implement",
    )
    red = checkpoint_implementation_step(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.implement",
        step_id="step-01-authentication",
        summary="Focused auth test is red",
        tdd_phase="red",
        red_evidence=["uv run pytest tests/test_auth.py -q"],
    )
    green = checkpoint_implementation_step(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.implement",
        step_id="step-01-authentication",
        summary="Auth test is green",
        tdd_phase="green",
        green_evidence=["uv run pytest tests/test_auth.py -q"],
        refactor_note="No refactor needed.",
    )
    completed = complete_implementation_step(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.implement",
        step_id="step-01-authentication",
        summary="Authentication flow implemented and validated",
        facts=["Authentication now persists session cookies"],
        decisions=["Keep session middleware in the HTTP layer"],
        evidence=["tests/test_auth.py"],
    )

    progress = json.loads(paths["progress"].read_text(encoding="utf-8"))
    active_session = json.loads(paths["active_session"].read_text(encoding="utf-8"))
    retrieved = retrieve_memory_context(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.implement",
        step_id="step-01-authentication",
    )

    assert started["accepted"] is True
    assert started["step_id"] == "step-01-authentication"
    assert red["accepted"] is True
    assert green["accepted"] is True
    assert completed["accepted"] is True
    assert completed["next_step"] == "step-02-session-persistence"
    assert progress["completedSteps"] == ["step-01-authentication"]
    assert progress["currentImplementStep"] == "step-02-session-persistence"
    assert progress["stepStatus"]["step-01-authentication"]["status"] == "completed"
    assert progress["stepStatus"]["step-01-authentication"]["tddPhase"] == "completed"
    assert progress["stepStatus"]["step-01-authentication"]["redEvidence"] == [
        "uv run pytest tests/test_auth.py -q"
    ]
    assert progress["stepStatus"]["step-01-authentication"]["greenEvidence"] == [
        "uv run pytest tests/test_auth.py -q"
    ]
    assert active_session["current_step"] == "step-02-session-persistence"
    assert retrieved["step"]["status"]["status"] == "completed"
    assert retrieved["semantic"]["facts"][0]["summary"] == "Authentication now persists session cookies"
    assert retrieved["semantic"]["decisions"][0]["summary"] == "Keep session middleware in the HTTP layer"
    assert validate_branch_memory(paths["branch_dir"].parents[1], "main") == []


def test_ensure_memory_layout_normalizes_legacy_tdd_fields(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)
    _write_mvp_concept(paths["branch_dir"])
    write_json(
        paths["progress"],
        {
            "currentImplementStep": None,
            "completedSteps": ["step-01-bootstrap"],
            "plannedSteps": ["step-01-bootstrap", "step-02-auth"],
            "stepStatus": {
                "step-01-bootstrap": {"status": "completed", "completedAt": "2026-03-10"},
                "step-02-auth": {"status": "planned", "completedAt": None},
            },
            "coversFunctions": {
                "step-01-bootstrap": {"p1": ["User authentication"], "p2": [], "p3": []},
                "step-02-auth": {"p1": ["Session persistence"], "p2": [], "p3": []},
            },
            "planningMetadata": {
                "lastPlannedStep": "step-02-auth",
                "planningPhase": "incremental",
                "totalStepsEstimated": 2,
                "stepDependencies": {"step-02-auth": ["step-01-bootstrap"]},
                "progressMetrics": {
                    "p1Coverage": {"covered": 1, "total": 2, "percentage": 50},
                    "p2Coverage": {"covered": 0, "total": 1, "percentage": 0},
                    "p3Coverage": {"covered": 0, "total": 1, "percentage": 0},
                    "overallProgress": 25,
                },
            },
        },
    )

    ensure_memory_layout(paths["branch_dir"].parents[1], "main")
    progress = json.loads(paths["progress"].read_text(encoding="utf-8"))

    assert progress["stepMetadata"]["step-01-bootstrap"] == {
        "kind": "non-code",
        "tddPolicy": "waived",
        "waiverReason": "Legacy step migrated without recorded TDD evidence.",
    }
    assert progress["stepMetadata"]["step-02-auth"] == {
        "kind": "code",
        "tddPolicy": "required",
        "waiverReason": None,
    }
    assert progress["stepStatus"]["step-01-bootstrap"]["tddPhase"] == "waived"
    assert progress["stepStatus"]["step-02-auth"]["tddPhase"] == "not_started"


def test_ensure_memory_layout_normalizes_legacy_coverage_shape(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)
    _write_mvp_concept(paths["branch_dir"])
    write_json(
        paths["progress"],
        {
            "currentImplementStep": None,
            "completedSteps": [],
            "plannedSteps": ["step-01-bootstrap"],
            "stepStatus": {
                "step-01-bootstrap": {"status": "planned", "tddPhase": "not_started"}
            },
            "stepMetadata": {
                "step-01-bootstrap": _step_metadata("non-code", "not-applicable")
            },
            "coversFunctions": {
                "step-01-bootstrap": []
            },
            "planningMetadata": {
                "lastPlannedStep": "step-01-bootstrap",
                "planningPhase": "initial",
                "totalStepsEstimated": 1,
                "stepDependencies": {},
                "progressMetrics": {
                    "p1Coverage": {"covered": 99, "total": 0, "percentage": 99},
                    "p2Coverage": {"covered": 99, "total": 0, "percentage": 99},
                    "p3Coverage": {"covered": 99, "total": 0, "percentage": 99},
                    "overallProgress": 99,
                },
            },
        },
    )

    ensure_memory_layout(paths["branch_dir"].parents[1], "main")
    consolidate_branch_memory(paths["branch_dir"].parents[1], "main")
    progress = json.loads(paths["progress"].read_text(encoding="utf-8"))

    assert progress["coversFunctions"]["step-01-bootstrap"] == {"p1": [], "p2": [], "p3": []}
    assert progress["planningMetadata"]["progressMetrics"] == {
        "p1Coverage": {"covered": 0, "total": 2, "percentage": 0},
        "p2Coverage": {"covered": 0, "total": 1, "percentage": 0},
        "p3Coverage": {"covered": 0, "total": 1, "percentage": 0},
        "overallProgress": 0,
    }
    assert validate_branch_memory(paths["branch_dir"].parents[1], "main") == []


def test_validate_requires_completed_code_step_to_finish_tdd_cycle(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)
    _write_mvp_concept(paths["branch_dir"])
    write_json(
        paths["progress"],
        {
            "currentImplementStep": None,
            "completedSteps": ["step-01-authentication"],
            "plannedSteps": ["step-01-authentication"],
            "stepStatus": {
                "step-01-authentication": _step_status(
                    status="completed",
                    completed_at="2026-03-10",
                    tdd_phase="green",
                    red=["uv run pytest tests/test_auth.py -q"],
                    green=["uv run pytest tests/test_auth.py -q"],
                    refactor_note="No refactor needed.",
                )
            },
            "stepMetadata": {
                "step-01-authentication": _step_metadata("code", "required")
            },
            "coversFunctions": {
                "step-01-authentication": {"p1": ["User authentication"], "p2": [], "p3": []}
            },
            "planningMetadata": {
                "lastPlannedStep": "step-01-authentication",
                "planningPhase": "incremental",
                "totalStepsEstimated": 1,
                "stepDependencies": {"step-01-authentication": []},
                "progressMetrics": {
                    "p1Coverage": {"covered": 1, "total": 2, "percentage": 50},
                    "p2Coverage": {"covered": 0, "total": 1, "percentage": 0},
                    "p3Coverage": {"covered": 0, "total": 1, "percentage": 0},
                    "overallProgress": 25,
                },
            },
        },
    )

    errors = validate_branch_memory(paths["branch_dir"].parents[1], "main")

    assert any("must have tddPhase='completed'" in error for error in errors)


def test_validate_requires_waiver_reason_for_waived_step(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)
    _write_mvp_concept(paths["branch_dir"])
    write_json(
        paths["progress"],
        {
            "currentImplementStep": None,
            "completedSteps": [],
            "plannedSteps": ["step-01-ui-polish"],
            "stepStatus": {
                "step-01-ui-polish": _step_status(
                    status="planned",
                    tdd_phase="waived",
                )
            },
            "stepMetadata": {
                "step-01-ui-polish": _step_metadata("non-code", "waived")
            },
            "coversFunctions": {
                "step-01-ui-polish": {"p1": ["User authentication"], "p2": [], "p3": []}
            },
            "planningMetadata": {
                "lastPlannedStep": "step-01-ui-polish",
                "planningPhase": "incremental",
                "totalStepsEstimated": 1,
                "stepDependencies": {"step-01-ui-polish": []},
                "progressMetrics": {
                    "p1Coverage": {"covered": 1, "total": 2, "percentage": 50},
                    "p2Coverage": {"covered": 0, "total": 1, "percentage": 0},
                    "p3Coverage": {"covered": 0, "total": 1, "percentage": 0},
                    "overallProgress": 25,
                },
            },
        },
    )

    errors = validate_branch_memory(paths["branch_dir"].parents[1], "main")

    assert any("waiverReason is required" in error for error in errors)


def test_checkpoint_stage_memory_updates_active_session_and_project_context(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)

    payload = checkpoint_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.tech",
        "Tech stack approved for MVP",
        facts=["Need web delivery and fast iteration"],
        decisions=["Use FastAPI for backend and HTMX for frontend"],
        contracts=["Python version must remain 3.13"],
        evidence=[".madspec/main/tech-stack.md"],
        questions=["Do we need offline mode?"],
        pending_actions=["Proceed to mvp.architecture"],
    )

    assert payload["accepted"] is True
    active_session = json.loads(paths["active_session"].read_text(encoding="utf-8"))
    assert active_session["stage"] == "mvp.tech"
    assert active_session["active_goal"] == "Tech stack approved for MVP"
    assert active_session["current_hypotheses"] == ["Use FastAPI for backend and HTMX for frontend"]

    project_context = (paths["branch_dir"] / "project-context.md").read_text(encoding="utf-8")
    assert "Current stage: `mvp.tech`" in project_context
    assert "Active goal: `Tech stack approved for MVP`" in project_context

    retrieved = retrieve_memory_context(paths["branch_dir"].parents[1], "main", "mvp.tech")
    assert retrieved["semantic"]["facts"][0]["summary"] == "Need web delivery and fast iteration"
    assert retrieved["semantic"]["decisions"][0]["summary"] == "Use FastAPI for backend and HTMX for frontend"
    assert retrieved["semantic"]["contracts"][0]["summary"] == "Python version must remain 3.13"


def test_capture_stage_memory_accumulates_context_before_checkpoint(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)

    captured = capture_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.concept",
        summary="Captured audience and pain points during discovery",
        facts=["Primary audience: freelancers"],
        decisions=["Prioritize booking workflow before analytics"],
        questions=["Do we need team scheduling in MVP?"],
        pending_actions=["Clarify notification constraints"],
        evidence=[".madspec/main/concept.md"],
        status="validated",
    )
    retrieved_before = retrieve_memory_context(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.concept",
    )
    checkpointed = checkpoint_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.concept",
        "Concept ratified after incremental discovery",
        evidence=[".madspec/main/concept.md"],
    )
    retrieved_after = retrieve_memory_context(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.concept",
    )

    assert captured["accepted"] is True
    assert retrieved_before["stage_memory"]["facts"][0]["summary"] == "Primary audience: freelancers"
    assert retrieved_before["stage_memory"]["decisions"][0]["summary"] == "Prioritize booking workflow before analytics"
    assert retrieved_before["active_session"]["open_questions"] == ["Do we need team scheduling in MVP?"]
    assert checkpointed["accepted"] is True
    assert checkpointed["used_existing_stage_memory"] is True
    assert retrieved_after["semantic"]["facts"][0]["summary"] == "Primary audience: freelancers"
    assert validate_branch_memory(paths["branch_dir"].parents[1], "main") == []


def test_security_checkpoint_generates_security_audit_view(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)

    captured = capture_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "security",
        summary="Captured initial OWASP findings",
        facts=["Missing rate limiting on login endpoint"],
        decisions=["Add per-IP throttling before public release"],
        contracts=["Password reset tokens must expire within 15 minutes"],
        evidence=["src/api/auth.py"],
        status="validated",
    )
    checkpointed = checkpoint_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "security",
        "Security audit ratified from accumulated findings",
        evidence=[".madspec/main/security-audit.md"],
    )

    security_audit = (paths["branch_dir"] / "security-audit.md").read_text(encoding="utf-8")
    retrieved = retrieve_memory_context(paths["branch_dir"].parents[1], "main", "security")

    assert captured["accepted"] is True
    assert checkpointed["accepted"] is True
    assert "Missing rate limiting on login endpoint" in security_audit
    assert "Add per-IP throttling before public release" in security_audit
    assert retrieved["stage_memory"]["contracts"][0]["summary"] == "Password reset tokens must expire within 15 minutes"


def test_checkpoint_stage_memory_is_atomic_on_invalid_payload(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)
    original_active_session = paths["active_session"].read_text(encoding="utf-8")
    original_decision_log = paths["decision_log"].read_text(encoding="utf-8")

    payload = checkpoint_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.plan",
        "",
    )

    assert payload["accepted"] is False
    assert paths["active_session"].read_text(encoding="utf-8") == original_active_session
    assert paths["decision_log"].read_text(encoding="utf-8") == original_decision_log
