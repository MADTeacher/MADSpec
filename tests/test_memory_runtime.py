from __future__ import annotations

import json
from pathlib import Path

import madspec_cli.memory.checkpoint as checkpoint_module
import madspec_cli.memory.stage_capture as stage_capture_module
import madspec_cli.memory.views as views_module
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
        """# Концепция проекта: Auth Demo

**Дата создания**: 2026-03-11

## Общее описание системы
Система помогает управлять аутентификацией пользователей и настройками их сессий.

## Основные функции разрабатываемого проекта

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


def _seed_concept_for_design(paths: dict[str, Path]) -> None:
    capture_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.concept",
        project_name="MVP scheduling assistant",
        system_overview="System helps freelancers manage bookings and reminders from one interface.",
        audiences=["Freelancers"],
        scenarios=["Book and reschedule client meetings"],
        pain_points=["Appointments are managed manually across chats and notes"],
        feature_p1=["Booking workflow::Capture booking details and send reminders"],
        feature_p2=["Profile studio::Customize the public-facing profile"],
        feature_p3=["Export hub::Download settings and summaries"],
        status="validated",
    )


def _write_design_prototypes(paths: dict[str, Path]) -> None:
    ui_dir = paths["branch_dir"] / "ui-prototype"
    ui_dir.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "schedule-board.html", "profile-studio.html", "export-hub.html"):
        (ui_dir / name).write_text(f"<html><body>{name}</body></html>\n", encoding="utf-8")


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

    captured = capture_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.tech",
        summary="Captured tech stack direction",
        project_type="Web application",
        stack_overview="A Python-first stack optimized for rapid MVP delivery and simple deployment.",
        requirements=["Need web delivery and fast iteration"],
        preferences=["Prefer a Python backend and server-rendered UI"],
        tech_constraints=["Python version must remain 3.13"],
        stack_components=[
            "language::Python::3.13::Primary language for backend and tooling",
            "frontend::HTMX::2.x::Keep frontend interactions server-driven and lightweight",
            "backend::FastAPI::0.115::Provide async HTTP APIs with strong typing",
            "database::PostgreSQL::16::Reliable relational storage for bookings and reminders",
            "unit-testing::pytest::8.x::Fast unit and integration test execution",
            "build::Docker::27.x::Standardize local and deployment builds",
        ],
        libraries=["backend::SQLAlchemy::2.x::ORM and SQL composition"],
        code_organization="monorepo::feature-first::modular service boundaries::Keep product slices close while preserving clear ownership",
        alternatives=["frontend::React SPA::Too much client complexity for the first MVP iteration"],
        evidence=[".madspec/main/tech-stack.md"],
        questions=["Do we need offline mode?"],
        pending_actions=["Proceed to mvp.architecture"],
        next_actions=["Proceed to mvp.architecture"],
    )
    assert captured["accepted"] is True

    payload = checkpoint_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.tech",
        "Tech stack approved for MVP",
        evidence=[".madspec/main/tech-stack.md"],
    )

    assert payload["accepted"] is True
    active_session = json.loads(paths["active_session"].read_text(encoding="utf-8"))
    assert active_session["stage"] == "mvp.tech"
    assert active_session["active_goal"] == "Tech stack approved for MVP"
    assert active_session["current_hypotheses"][0].startswith("Stack component language: Python 3.13")

    project_context = (paths["branch_dir"] / "project-context.md").read_text(encoding="utf-8")
    assert "Current stage: `mvp.tech`" in project_context
    assert "Active goal: `Tech stack approved for MVP`" in project_context
    assert "Tech checkpoint summary: `Tech stack approved for MVP`" in project_context

    retrieved = retrieve_memory_context(paths["branch_dir"].parents[1], "main", "mvp.tech", limit=10)
    assert retrieved["artifact_state"]["tech"] is None
    assert retrieved["tech_status"]["is_complete"] is True
    assert retrieved["tech_status"]["selected_slots"] == [
        "backend",
        "build",
        "database",
        "frontend",
        "language",
        "unit-testing",
    ]
    assert retrieved["decision_log"] == []
    fact_summaries = {item["summary"] for item in retrieved["semantic"]["facts"]}
    decision_summaries = {item["summary"] for item in retrieved["semantic"]["decisions"]}
    contract_summaries = {item["summary"] for item in retrieved["semantic"]["contracts"]}
    assert "Prefer a Python backend and server-rendered UI" in fact_summaries
    assert "Need web delivery and fast iteration" in fact_summaries
    assert any("FastAPI" in item for item in decision_summaries)
    assert "Python version must remain 3.13" in contract_summaries

    retrieved_full = retrieve_memory_context(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.tech",
        full_artifact=True,
        include_history=True,
    )
    assert retrieved_full["artifact_state"]["tech"]["checkpointSummary"] == "Tech stack approved for MVP"
    assert retrieved_full["artifact_state"]["tech"]["revision"] == 1
    tech_stack = (paths["branch_dir"] / "tech-stack.md").read_text(encoding="utf-8")
    assert "A Python-first stack optimized for rapid MVP delivery and simple deployment." in tech_stack
    assert "FastAPI" in tech_stack


def test_validate_reports_tech_stack_drift_and_consolidate_rewrites_it(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)

    capture_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.tech",
        project_type="API service",
        stack_overview="A compact backend-only stack for predictable service delivery.",
        stack_components=[
            "language::Python::3.13::Primary service language",
            "backend::FastAPI::0.115::HTTP service runtime",
            "unit-testing::pytest::8.x::Backend test runner",
            "build::Docker::27.x::Build and runtime packaging",
        ],
        code_organization="monorepo::layer-first::single service package::Keep service structure explicit for a small API",
        evidence=[".madspec/main/tech-stack.md"],
    )
    checkpoint_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.tech",
        "API stack ratified",
        evidence=[".madspec/main/tech-stack.md"],
    )

    tech_stack_path = paths["branch_dir"] / "tech-stack.md"
    original_text = tech_stack_path.read_text(encoding="utf-8")
    tech_stack_path.write_text("# Manual drift\n", encoding="utf-8")

    errors = validate_branch_memory(paths["branch_dir"].parents[1], "main")
    assert "tech-stack.md is out of sync with memory/stages/mvp.tech.json" in errors

    consolidate_branch_memory(paths["branch_dir"].parents[1], "main")
    rewritten_text = tech_stack_path.read_text(encoding="utf-8")
    assert rewritten_text == original_text


def test_capture_stage_memory_accumulates_context_before_checkpoint(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)

    captured = capture_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.concept",
        summary="Captured audience and pain points during discovery",
        project_name="MVP scheduling assistant",
        system_overview="System helps freelancers manage bookings and reminders from one interface.",
        audiences=["Freelancers scheduling appointments"],
        scenarios=["Create, move, and confirm appointments from one calendar"],
        pain_points=["Manual follow-ups lead to missed appointments"],
        feature_p1=["Booking workflow::Create bookings and send reminders"],
        assumptions=["Users already coordinate appointments in messengers or spreadsheets"],
        next_actions=["Proceed to mvp.design"],
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
    retrieved_full_after = retrieve_memory_context(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.concept",
        full_artifact=True,
        include_history=True,
    )

    assert captured["accepted"] is True
    assert retrieved_before["active_session"]["open_questions"] == ["Do we need team scheduling in MVP?"]
    assert retrieved_before["artifact_state"]["concept"] is None
    assert retrieved_before["concept_status"]["is_complete"] is True
    assert retrieved_before["concept_status"]["missing_required_fields"] == []
    assert retrieved_before["concept_status"]["counts"]["p1_features"] == 1
    assert retrieved_before["decision_log"] == []
    assert checkpointed["accepted"] is True
    assert checkpointed["used_existing_stage_memory"] is True
    assert retrieved_after["artifact_state"]["concept"] is None
    assert retrieved_after["concept_status"]["last_checkpoint_summary"] == "Concept ratified after incremental discovery"
    assert retrieved_after["concept_status"]["revision"] == 1
    assert retrieved_full_after["artifact_state"]["concept"]["checkpointSummary"] == "Concept ratified after incremental discovery"
    assert retrieved_full_after["artifact_state"]["concept"]["revision"] == 1
    assert retrieved_full_after["decision_log"] != []
    concept_text = (paths["branch_dir"] / "concept.md").read_text(encoding="utf-8")
    assert "## Общее описание системы" in concept_text
    assert "System helps freelancers manage bookings and reminders from one interface." in concept_text
    assert validate_branch_memory(paths["branch_dir"].parents[1], "main") == []


def test_retrieve_memory_context_returns_concept_status_for_partial_concept(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)

    capture_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.concept",
        project_name="MVP scheduling assistant",
        audiences=["Freelancers"],
        questions=["Q1", "Q2", "Q3", "Q4"],
        status="validated",
    )

    retrieved = retrieve_memory_context(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.concept",
    )

    assert retrieved["artifact_state"]["concept"] is None
    assert retrieved["concept_status"]["is_complete"] is False
    assert retrieved["concept_status"]["missing_required_fields"] == [
        "systemOverview",
        "scenarios",
        "painPoints",
        "features.p1",
    ]
    assert retrieved["concept_status"]["filled_fields"] == [
        "projectName",
        "audiences",
    ]
    assert retrieved["active_session"]["open_questions"] == ["Q1", "Q2", "Q3"]
    assert retrieved["concept_status"]["counts"] == {
        "audiences": 1,
        "scenarios": 0,
        "pain_points": 0,
        "p1_features": 0,
        "p2_features": 0,
        "p3_features": 0,
        "constraints": 0,
        "assumptions": 0,
        "next_actions": 0,
    }


def test_retrieve_memory_context_reads_semantic_files_once_and_skips_history_for_concept(tmp_path: Path, monkeypatch) -> None:
    paths = _bootstrap_project(tmp_path)

    capture_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.concept",
        project_name="MVP scheduling assistant",
        system_overview="System helps freelancers manage bookings.",
        audiences=["Freelancers"],
        scenarios=["Book client meetings"],
        pain_points=["Manual follow-ups are slow"],
        feature_p1=["Booking workflow::Create bookings and reminders"],
        questions=["Q1"],
        status="validated",
    )

    original_read_jsonl = views_module.read_jsonl
    calls: list[Path] = []

    def counting_read_jsonl(path: Path) -> list[dict[str, object]]:
        calls.append(path)
        return original_read_jsonl(path)

    monkeypatch.setattr(views_module, "read_jsonl", counting_read_jsonl)

    retrieved = retrieve_memory_context(paths["branch_dir"].parents[1], "main", "mvp.concept")

    assert retrieved["decision_log"] == []
    assert retrieved["episodes"] == []
    assert calls.count(paths["facts"]) == 1
    assert calls.count(paths["decisions"]) == 1
    assert calls.count(paths["contracts"]) == 1
    assert paths["decision_log"] not in calls
    assert paths["events"] not in calls


def test_retrieve_memory_context_reads_history_when_requested_for_concept(tmp_path: Path, monkeypatch) -> None:
    paths = _bootstrap_project(tmp_path)

    capture_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.concept",
        project_name="MVP scheduling assistant",
        system_overview="System helps freelancers manage bookings.",
        audiences=["Freelancers"],
        scenarios=["Book client meetings"],
        pain_points=["Manual follow-ups are slow"],
        feature_p1=["Booking workflow::Create bookings and reminders"],
        questions=["Q1"],
        status="validated",
    )

    original_read_jsonl = views_module.read_jsonl
    calls: list[Path] = []

    def counting_read_jsonl(path: Path) -> list[dict[str, object]]:
        calls.append(path)
        return original_read_jsonl(path)

    monkeypatch.setattr(views_module, "read_jsonl", counting_read_jsonl)

    retrieved = retrieve_memory_context(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.concept",
        include_history=True,
    )

    assert calls.count(paths["decision_log"]) == 1
    assert calls.count(paths["events"]) == 1
    assert len(retrieved["decision_log"]) == 1


def test_capture_stage_memory_consolidates_once(tmp_path: Path, monkeypatch) -> None:
    paths = _bootstrap_project(tmp_path)
    original_consolidate = stage_capture_module.consolidate_branch_memory
    calls: list[str] = []

    def counting_consolidate(project_path: Path, branch_name: str) -> list[Path]:
        calls.append(branch_name)
        return original_consolidate(project_path, branch_name)

    monkeypatch.setattr(stage_capture_module, "consolidate_branch_memory", counting_consolidate)

    captured = capture_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.concept",
        project_name="MVP scheduling assistant",
        system_overview="System helps freelancers manage bookings.",
        audiences=["Freelancers"],
        scenarios=["Book client meetings"],
        pain_points=["Manual follow-ups are slow"],
        feature_p1=["Booking workflow::Create bookings and reminders"],
        status="validated",
    )

    assert captured["accepted"] is True
    assert calls == ["main"]


def test_checkpoint_stage_memory_consolidates_once(tmp_path: Path, monkeypatch) -> None:
    paths = _bootstrap_project(tmp_path)
    capture_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.concept",
        project_name="MVP scheduling assistant",
        system_overview="System helps freelancers manage bookings.",
        audiences=["Freelancers"],
        scenarios=["Book client meetings"],
        pain_points=["Manual follow-ups are slow"],
        feature_p1=["Booking workflow::Create bookings and reminders"],
        status="validated",
    )

    original_consolidate = checkpoint_module.consolidate_branch_memory
    calls: list[str] = []

    def counting_consolidate(project_path: Path, branch_name: str) -> list[Path]:
        calls.append(branch_name)
        return original_consolidate(project_path, branch_name)

    monkeypatch.setattr(checkpoint_module, "consolidate_branch_memory", counting_consolidate)

    checkpointed = checkpoint_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.concept",
        "Concept ratified after incremental discovery",
        evidence=[".madspec/main/concept.md"],
    )

    assert checkpointed["accepted"] is True
    assert calls == ["main"]


def test_design_stage_retrieve_returns_design_status_and_full_artifact(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)
    _seed_concept_for_design(paths)
    _write_design_prototypes(paths)

    captured = capture_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.design",
        summary="Captured design iteration",
        design_overview="A workspace-first web UI with focused transitions between booking, profile tuning, and exports.",
        platforms=["Web"],
        zones=[
            "operations::Operations::Daily scheduling workspace",
            "settings::Settings::Profile and export configuration",
        ],
        screens=[
            "schedule-board::Schedule board::operations::.madspec/main/ui-prototype/schedule-board.html::Shows upcoming bookings and reminder actions",
            "profile-studio::Profile studio::settings::.madspec/main/ui-prototype/profile-studio.html::Lets the user customize profile details",
            "export-hub::Export hub::settings::.madspec/main/ui-prototype/export-hub.html::Lets the user export summaries and settings",
        ],
        screen_features=[
            "schedule-board::p1::Booking workflow",
            "profile-studio::p2::Profile studio",
            "export-hub::p3::Export hub",
        ],
        flows=["manage-booking::Manage booking::Create and review a booking flow from one workspace"],
        flow_steps=[
            "manage-booking::schedule-board::Create booking::Open booking details with reminders",
            "manage-booking::profile-studio::Review profile::Confirm public profile details",
        ],
        flow_alternatives=["manage-booking::Skip profile review when no changes are needed"],
        navigation=[
            "schedule-board::profile-studio::Profile settings shortcut",
            "profile-studio::export-hub::Export settings CTA",
        ],
        platform_constraints=["Primary interactions must remain usable on narrow laptop screens"],
        screen_data=[
            "schedule-board::displayed::Upcoming bookings with reminder state",
            "profile-studio::input::Public display name",
        ],
        next_actions=["Review the latest prototype with the user"],
        status="validated",
    )
    retrieved = retrieve_memory_context(paths["branch_dir"].parents[1], "main", "mvp.design")

    assert captured["accepted"] is True
    assert retrieved["artifact_state"]["design"] is None
    assert retrieved["design_status"]["is_complete"] is True
    assert retrieved["design_status"]["counts"] == {
        "platforms": 1,
        "zones": 2,
        "screens": 3,
        "flows": 1,
        "navigation_links": 2,
        "platform_constraints": 1,
    }
    assert retrieved["design_status"]["uncovered_features"] == {"p1": [], "p2": [], "p3": []}
    assert retrieved["design_status"]["missing_prototype_files"] == []
    assert retrieved["decision_log"] == []

    checkpointed = checkpoint_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.design",
        "Design ratified for prototype review",
        evidence=[".madspec/main/ui-design.md", ".madspec/main/ui-prototype/index.html"],
    )
    retrieved_full = retrieve_memory_context(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.design",
        full_artifact=True,
        include_history=True,
    )
    ui_design = (paths["branch_dir"] / "ui-design.md").read_text(encoding="utf-8")

    assert checkpointed["accepted"] is True
    assert retrieved_full["artifact_state"]["design"]["checkpointSummary"] == "Design ratified for prototype review"
    assert retrieved_full["artifact_state"]["design"]["revision"] == 1
    assert "Schedule board" in ui_design
    assert "Manage booking" in ui_design
    assert validate_branch_memory(paths["branch_dir"].parents[1], "main") == []


def test_design_checkpoint_can_be_repeated_and_increments_revision(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)
    _seed_concept_for_design(paths)
    _write_design_prototypes(paths)

    capture_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.design",
        design_overview="First design pass.",
        platforms=["Web"],
        zones=["operations::Operations::Daily scheduling workspace"],
        screens=[
            "schedule-board::Schedule board::operations::.madspec/main/ui-prototype/schedule-board.html::Shows upcoming bookings and reminder actions",
            "profile-studio::Profile studio::operations::.madspec/main/ui-prototype/profile-studio.html::Lets the user customize profile details",
            "export-hub::Export hub::operations::.madspec/main/ui-prototype/export-hub.html::Lets the user export summaries and settings",
        ],
        screen_features=[
            "schedule-board::p1::Booking workflow",
            "profile-studio::p2::Profile studio",
            "export-hub::p3::Export hub",
        ],
        flows=["manage-booking::Manage booking::Create and review a booking flow from one workspace"],
        flow_steps=["manage-booking::schedule-board::Create booking::Open booking details with reminders"],
        navigation=["schedule-board::profile-studio::Profile settings shortcut"],
        status="validated",
    )

    first_checkpoint = checkpoint_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.design",
        "Design version one",
        evidence=[".madspec/main/ui-design.md", ".madspec/main/ui-prototype/index.html"],
    )
    capture_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.design",
        design_overview="Second design pass with tighter information hierarchy.",
        navigation=["profile-studio::export-hub::Export settings CTA"],
        next_actions=["Validate export copy with the user"],
        status="validated",
    )
    second_checkpoint = checkpoint_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.design",
        "Design version two",
        evidence=[".madspec/main/ui-design.md", ".madspec/main/ui-prototype/index.html"],
    )
    retrieved_full = retrieve_memory_context(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.design",
        full_artifact=True,
    )

    assert first_checkpoint["accepted"] is True
    assert second_checkpoint["accepted"] is True
    assert retrieved_full["artifact_state"]["design"]["revision"] == 2
    assert retrieved_full["artifact_state"]["design"]["checkpointSummary"] == "Design version two"


def test_architecture_stage_retrieve_returns_status_and_full_artifact(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)
    _seed_concept_for_design(paths)
    _write_design_prototypes(paths)

    capture_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.design",
        design_overview="A workspace-first web UI with focused transitions between booking, profile tuning, and exports.",
        platforms=["Web"],
        zones=[
            "operations::Operations::Daily scheduling workspace",
            "settings::Settings::Profile and export configuration",
        ],
        screens=[
            "schedule-board::Schedule board::operations::.madspec/main/ui-prototype/schedule-board.html::Shows upcoming bookings and reminder actions",
            "profile-studio::Profile studio::settings::.madspec/main/ui-prototype/profile-studio.html::Lets the user customize profile details",
            "export-hub::Export hub::settings::.madspec/main/ui-prototype/export-hub.html::Lets the user export summaries and settings",
        ],
        screen_features=[
            "schedule-board::p1::Booking workflow",
            "profile-studio::p2::Profile studio",
            "export-hub::p3::Export hub",
        ],
        flows=["manage-booking::Manage booking::Create and review a booking flow from one workspace"],
        flow_steps=[
            "manage-booking::schedule-board::Create booking::Open booking details with reminders",
            "manage-booking::profile-studio::Review profile::Confirm public profile details",
            "manage-booking::export-hub::Export summary::Download account summary",
        ],
        navigation=[
            "schedule-board::profile-studio::Profile settings shortcut",
            "profile-studio::export-hub::Export settings CTA",
        ],
        screen_data=[
            "schedule-board::displayed::Upcoming bookings with reminder state",
            "schedule-board::input::Reminder lead time",
            "profile-studio::input::Public display name",
            "export-hub::displayed::Export download url",
        ],
        status="validated",
    )

    captured = capture_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.architecture",
        summary="Captured architecture iteration",
        architecture_overview="A modular web architecture centered on scheduling workflows and server-driven UI contracts.",
        project_structure="feature-first::Keep booking flows, profile tuning, and exports isolated by capability",
        directories=[
            "src/features/scheduling::Booking workflow handlers and orchestration",
            "src/features/profile::Profile editing logic",
            "src/features/exports::Export generation handlers",
        ],
        entities=[
            "Booking::Customer booking and reminder configuration",
            "Profile::Public profile settings",
            "ExportJob::Generated export package",
        ],
        entity_fields=[
            "Booking::id::uuid::required::Primary booking identifier",
            "Booking::reminder lead time::integer::required::Reminder lead time in minutes",
            "Profile::public display name::string::required::Display name shown to customers",
            "ExportJob::download url::string::required::Download location for generated export",
        ],
        entity_relationships=[
            "Booking::Profile::belongs-to::Bookings are owned by the freelancer profile",
        ],
        entity_states=["ExportJob::ready::Export package is ready for download"],
        endpoints=[
            "update-booking-reminder::PUT::/bookings/{id}/reminder::Update booking reminder configuration",
            "update-profile::PUT::/profile::Update freelancer profile settings",
            "download-export::GET::/exports/latest::Fetch the latest export package",
        ],
        endpoint_screens=[
            "update-booking-reminder::schedule-board",
            "update-profile::profile-studio",
            "download-export::export-hub",
        ],
        endpoint_fields=[
            "update-booking-reminder::path::id::uuid::required::Booking identifier",
            "update-booking-reminder::request::Reminder lead time::integer::required::Reminder lead time in minutes",
            "update-booking-reminder::response:200::Upcoming bookings with reminder state::array::required::Updated booking cards with reminder state",
            "update-profile::request::Public display name::string::required::Updated public display name",
            "update-profile::response:200::profile status::string::required::Profile save status",
            "download-export::response:200::Export download url::string::required::Download URL for latest export",
        ],
        endpoint_errors=["download-export::404::export_not_ready::Export package is not ready yet"],
        integrations=[
            "Email provider::external-api::Deliver reminders to customers::schedule-board|background worker",
        ],
        code_principles=[
            "Keep HTTP handlers thin and move workflow rules into feature services.",
        ],
        architecture_patterns=["Repository::Isolate persistence details from feature logic"],
        security_notes=[
            "Authorize profile and booking mutations against the current freelancer account.",
        ],
        performance_notes=[
            "Reuse precomputed export metadata to avoid rebuilding the package on every download request.",
        ],
        next_actions=["Proceed to mvp.plan"],
        status="validated",
    )
    retrieved = retrieve_memory_context(paths["branch_dir"].parents[1], "main", "mvp.architecture")

    assert captured["accepted"] is True
    assert retrieved["artifact_state"]["architecture"] is None
    assert retrieved["architecture_status"]["is_complete"] is True
    assert retrieved["architecture_status"]["counts"] == {
        "directories": 3,
        "entities": 3,
        "endpoints": 3,
        "integrations": 1,
        "code_principles": 1,
        "patterns": 1,
    }

    checkpointed = checkpoint_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.architecture",
        "Architecture ratified for implementation planning",
        evidence=[
            ".madspec/main/architecture.md",
            ".madspec/main/data-model.md",
            ".madspec/main/contracts/openapi.yaml",
        ],
    )
    retrieved_full = retrieve_memory_context(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.architecture",
        full_artifact=True,
        include_history=True,
    )

    assert checkpointed["accepted"] is True
    assert retrieved_full["artifact_state"]["architecture"]["checkpointSummary"] == "Architecture ratified for implementation planning"
    assert retrieved_full["artifact_state"]["architecture"]["revision"] == 1
    assert "A modular web architecture centered on scheduling workflows" in (paths["branch_dir"] / "architecture.md").read_text(encoding="utf-8")
    assert "Booking" in (paths["branch_dir"] / "data-model.md").read_text(encoding="utf-8")
    assert "update-booking-reminder" in (paths["branch_dir"] / "contracts" / "openapi.yaml").read_text(encoding="utf-8")
    assert validate_branch_memory(paths["branch_dir"].parents[1], "main") == []


def test_validate_detects_out_of_sync_generated_architecture_artifacts(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)
    _seed_concept_for_design(paths)
    _write_design_prototypes(paths)

    capture_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.design",
        design_overview="A workspace-first web UI with focused transitions between booking, profile tuning, and exports.",
        platforms=["Web"],
        zones=[
            "operations::Operations::Daily scheduling workspace",
            "settings::Settings::Profile and export configuration",
        ],
        screens=[
            "schedule-board::Schedule board::operations::.madspec/main/ui-prototype/schedule-board.html::Shows upcoming bookings and reminder actions",
            "profile-studio::Profile studio::settings::.madspec/main/ui-prototype/profile-studio.html::Lets the user customize profile details",
            "export-hub::Export hub::settings::.madspec/main/ui-prototype/export-hub.html::Lets the user export summaries and settings",
        ],
        screen_features=[
            "schedule-board::p1::Booking workflow",
            "profile-studio::p2::Profile studio",
            "export-hub::p3::Export hub",
        ],
        flows=["manage-booking::Manage booking::Create and review a booking flow from one workspace"],
        flow_steps=[
            "manage-booking::schedule-board::Create booking::Open booking details with reminders",
            "manage-booking::profile-studio::Review profile::Confirm public profile details",
            "manage-booking::export-hub::Export summary::Download account summary",
        ],
        navigation=[
            "schedule-board::profile-studio::Profile settings shortcut",
            "profile-studio::export-hub::Export settings CTA",
        ],
        screen_data=[
            "schedule-board::displayed::Upcoming bookings with reminder state",
            "schedule-board::input::Reminder lead time",
            "profile-studio::input::Public display name",
            "export-hub::displayed::Export download url",
        ],
        status="validated",
    )
    capture_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.architecture",
        architecture_overview="Architecture baseline.",
        project_structure="feature-first::Keep booking flows, profile tuning, and exports isolated by capability",
        directories=[
            "src/features/scheduling::Booking workflow handlers and orchestration",
            "src/features/profile::Profile editing logic",
            "src/features/exports::Export generation handlers",
        ],
        entities=[
            "Booking::Customer booking and reminder configuration",
            "Profile::Public profile settings",
            "ExportJob::Generated export package",
        ],
        entity_fields=[
            "Booking::id::uuid::required::Primary booking identifier",
            "Booking::reminder lead time::integer::required::Reminder lead time in minutes",
            "Profile::public display name::string::required::Display name shown to customers",
            "ExportJob::download url::string::required::Download location for generated export",
        ],
        endpoints=[
            "update-booking-reminder::PUT::/bookings/{id}/reminder::Update booking reminder configuration",
            "update-profile::PUT::/profile::Update freelancer profile settings",
            "download-export::GET::/exports/latest::Fetch the latest export package",
        ],
        endpoint_screens=[
            "update-booking-reminder::schedule-board",
            "update-profile::profile-studio",
            "download-export::export-hub",
        ],
        endpoint_fields=[
            "update-booking-reminder::path::id::uuid::required::Booking identifier",
            "update-booking-reminder::request::Reminder lead time::integer::required::Reminder lead time in minutes",
            "update-booking-reminder::response:200::Upcoming bookings with reminder state::array::required::Updated booking cards with reminder state",
            "update-profile::request::Public display name::string::required::Updated public display name",
            "update-profile::response:200::profile status::string::required::Profile save status",
            "download-export::response:200::Export download url::string::required::Download URL for latest export",
        ],
        code_principles=["Keep HTTP handlers thin and move workflow rules into feature services."],
        status="validated",
    )
    checkpoint_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.architecture",
        "Architecture version one",
        evidence=[
            ".madspec/main/architecture.md",
            ".madspec/main/data-model.md",
            ".madspec/main/contracts/openapi.yaml",
        ],
    )

    (paths["branch_dir"] / "architecture.md").write_text("# drift\n", encoding="utf-8")
    (paths["branch_dir"] / "data-model.md").write_text("# drift\n", encoding="utf-8")
    (paths["branch_dir"] / "contracts" / "openapi.yaml").write_text("openapi: drift\n", encoding="utf-8")

    errors = validate_branch_memory(paths["branch_dir"].parents[1], "main")

    assert "architecture.md is out of sync with memory/stages/mvp.architecture.json" in errors
    assert "data-model.md is out of sync with memory/stages/mvp.architecture.json" in errors
    assert "contracts/openapi.yaml is out of sync with memory/stages/mvp.architecture.json" in errors


def test_validate_detects_out_of_sync_generated_ui_design(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)
    _seed_concept_for_design(paths)
    _write_design_prototypes(paths)

    capture_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.design",
        design_overview="Design pass.",
        platforms=["Web"],
        zones=["operations::Operations::Daily scheduling workspace"],
        screens=[
            "schedule-board::Schedule board::operations::.madspec/main/ui-prototype/schedule-board.html::Shows upcoming bookings and reminder actions",
            "profile-studio::Profile studio::operations::.madspec/main/ui-prototype/profile-studio.html::Lets the user customize profile details",
            "export-hub::Export hub::operations::.madspec/main/ui-prototype/export-hub.html::Lets the user export summaries and settings",
        ],
        screen_features=[
            "schedule-board::p1::Booking workflow",
            "profile-studio::p2::Profile studio",
            "export-hub::p3::Export hub",
        ],
        flows=["manage-booking::Manage booking::Create and review a booking flow from one workspace"],
        flow_steps=["manage-booking::schedule-board::Create booking::Open booking details with reminders"],
        navigation=["schedule-board::profile-studio::Profile settings shortcut"],
        status="validated",
    )
    checkpoint_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.design",
        "Design ratified",
        evidence=[".madspec/main/ui-design.md", ".madspec/main/ui-prototype/index.html"],
    )

    design_path = paths["branch_dir"] / "ui-design.md"
    design_path.write_text("# manually edited\n", encoding="utf-8")

    errors = validate_branch_memory(paths["branch_dir"].parents[1], "main")

    assert any("ui-design.md is out of sync" in error for error in errors)


def test_validate_detects_missing_design_coverage_and_prototype_files(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)
    _seed_concept_for_design(paths)
    _write_design_prototypes(paths)

    captured = capture_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.design",
        design_overview="Incomplete design pass.",
        platforms=["Web"],
        zones=["operations::Operations::Daily scheduling workspace"],
        screens=[
            "schedule-board::Schedule board::operations::.madspec/main/ui-prototype/schedule-board.html::Shows upcoming bookings and reminder actions"
        ],
        screen_features=["schedule-board::p1::Booking workflow"],
        flows=["manage-booking::Manage booking::Create and review a booking flow from one workspace"],
        flow_steps=["manage-booking::schedule-board::Create booking::Open booking details with reminders"],
        navigation=["schedule-board::schedule-board::Refresh board"],
        status="proposed",
    )
    (paths["branch_dir"] / "ui-prototype" / "schedule-board.html").unlink()

    errors = validate_branch_memory(paths["branch_dir"].parents[1], "main")

    assert captured["accepted"] is True
    assert any("design references missing prototype file" in error for error in errors)
    assert any("design coverage missing P2 concept feature 'Profile studio'" in error for error in errors)


def test_validate_detects_out_of_sync_generated_concept(tmp_path: Path) -> None:
    paths = _bootstrap_project(tmp_path)

    capture_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.concept",
        project_name="MVP scheduling assistant",
        system_overview="System helps freelancers manage bookings and reminders from one interface.",
        audiences=["Freelancers"],
        scenarios=["Book and reschedule appointments"],
        pain_points=["Appointments are tracked manually"],
        feature_p1=["Booking workflow::Create bookings and reminders"],
        status="validated",
    )

    concept_path = paths["branch_dir"] / "concept.md"
    concept_path.write_text("# manually edited\n", encoding="utf-8")

    errors = validate_branch_memory(paths["branch_dir"].parents[1], "main")

    assert any("concept.md is out of sync" in error for error in errors)


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
