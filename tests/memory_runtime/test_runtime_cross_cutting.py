from __future__ import annotations

import json
from pathlib import Path

import madspec_cli.memory.shared.system_store.runtime_mutations as runtime_mutations_module
from madspec_cli.memory.application.consolidate_memory import ConsolidateMemoryRequest, execute as consolidate_memory
from madspec_cli.memory import (
    capture_stage_memory,
    checkpoint_stage_memory,
    consolidate_branch_memory,
    learn_from_outcomes,
    promote_validated_records,
    retrieve_memory_context,
    validate_branch_memory,
)
from madspec_cli.memory.shared.records import make_record
from madspec_cli.memory.shared.storage import append_jsonl, write_json
from madspec_cli.memory.shared.system_store.canonical_state import (
    bootstrap_branch_canonical_state,
    load_canonical_branch_state,
)
from madspec_cli.memory.shared.system_store.store import MemoryStore
from tests.memory_runtime.support import step_metadata, step_status


def test_consolidate_is_deterministic_for_same_memory_state(memory_project) -> None:
    paths = memory_project.paths
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
                "step-01-bootstrap": step_status(status="planned")
            },
            "stepMetadata": {
                "step-01-bootstrap": step_metadata("code", "required")
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
    memory_project.sync()

    first_run = consolidate_branch_memory(memory_project.project_path, "main")
    snapshot_a = {
        path.name: path.read_text(encoding="utf-8")
        for path in first_run
        if path.name in {"project-context.md", "planning-context-cache.md", "planning-context.md"}
    }
    second_run = consolidate_branch_memory(memory_project.project_path, "main")
    snapshot_b = {
        path.name: path.read_text(encoding="utf-8")
        for path in second_run
        if path.name in {"project-context.md", "planning-context-cache.md", "planning-context.md"}
    }

    assert snapshot_a == snapshot_b
    assert "Generated from structured memory" in snapshot_a["project-context.md"]
    assert "Bootstrap the project first" in snapshot_a["planning-context.md"]


def test_validate_reports_invalid_status_and_broken_step_reference(memory_project) -> None:
    paths = memory_project.paths
    write_json(
        paths["progress"],
        {
            "currentImplementStep": "step-99-missing",
            "completedSteps": ["step-01-bootstrap"],
            "plannedSteps": ["step-01-bootstrap"],
            "stepStatus": {
                "step-ghost": step_status(
                    status="completed",
                    completed_at="2026-03-10",
                    tdd_phase="completed",
                    red=["uv run pytest tests/test_auth.py -q"],
                    green=["uv run pytest tests/test_auth.py -q"],
                    refactor_note="No refactor needed.",
                )
            },
            "stepMetadata": {
                "step-01-bootstrap": step_metadata("code", "required")
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

    errors = validate_branch_memory(memory_project.project_path, "main")

    assert any("currentImplementStep must be null or reference a planned step" in error for error in errors)
    assert any("invalid status 'bad-status'" in error for error in errors)
    assert any("dependency 'step-02-missing'" in error for error in errors)


def test_promote_retrieve_and_learn_flow(memory_project) -> None:
    paths = memory_project.paths
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
    memory_project.sync()

    promoted = promote_validated_records(memory_project.project_path, "main")
    context = retrieve_memory_context(memory_project.project_path, "main", "mvp.plan")

    assert promoted == {"fact": 1, "decision": 0, "contract": 1}
    assert len(context["semantic"]["facts"]) == 1
    assert len(context["semantic"]["contracts"]) == 1

    learning_input = memory_project.project_path / "learning.json"
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

    learned = learn_from_outcomes(memory_project.project_path, "main", learning_input)

    assert learned["events"] == 2
    assert learned["semantic_candidates"] == 2


def test_capture_stage_memory_consolidates_once(memory_project, monkeypatch) -> None:
    original_refresh = runtime_mutations_module.refresh_branch_projections
    calls: list[str] = []

    def counting_refresh(project_path: Path, branch_name: str, **kwargs):
        calls.append(branch_name)
        return original_refresh(project_path, branch_name, **kwargs)

    monkeypatch.setattr(runtime_mutations_module, "refresh_branch_projections", counting_refresh)

    captured = capture_stage_memory(
        memory_project.project_path,
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


def test_checkpoint_stage_memory_consolidates_once(memory_project, monkeypatch) -> None:
    capture_stage_memory(
        memory_project.project_path,
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

    original_refresh = runtime_mutations_module.refresh_branch_projections
    calls: list[str] = []

    def counting_refresh(project_path: Path, branch_name: str, **kwargs):
        calls.append(branch_name)
        return original_refresh(project_path, branch_name, **kwargs)

    monkeypatch.setattr(runtime_mutations_module, "refresh_branch_projections", counting_refresh)

    checkpointed = checkpoint_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.concept",
        "Concept ratified after incremental discovery",
        evidence=[".madspec/main/concept.md"],
    )

    assert checkpointed["accepted"] is True
    assert calls == ["main"]


def test_security_checkpoint_generates_security_audit_view(memory_project) -> None:
    paths = memory_project.paths

    captured = capture_stage_memory(
        memory_project.project_path,
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
        memory_project.project_path,
        "main",
        "security",
        "Security audit ratified from accumulated findings",
        evidence=[".madspec/main/security-audit.md"],
    )

    security_audit = (paths["branch_dir"] / "security-audit.md").read_text(encoding="utf-8")
    retrieved = retrieve_memory_context(memory_project.project_path, "main", "security")

    assert captured["accepted"] is True
    assert checkpointed["accepted"] is True
    assert "Missing rate limiting on login endpoint" in security_audit
    assert "Add per-IP throttling before public release" in security_audit
    assert retrieved["stage_memory"]["contracts"][0]["summary"] == "Password reset tokens must expire within 15 minutes"


def test_checkpoint_stage_memory_is_atomic_on_invalid_payload(memory_project) -> None:
    paths = memory_project.paths
    original_decision_log = paths["decision_log"].read_text(encoding="utf-8")
    original_session = retrieve_memory_context(memory_project.project_path, "main", "mvp.plan")["active_session"]

    payload = checkpoint_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.plan",
        "",
    )

    assert payload["accepted"] is False
    assert paths["decision_log"].read_text(encoding="utf-8") == original_decision_log
    current_session = retrieve_memory_context(memory_project.project_path, "main", "mvp.plan")["active_session"]
    assert current_session == original_session


def test_consolidate_rebuilds_branch_memory_files_from_canonical_state(memory_project) -> None:
    capture_stage_memory(
        memory_project.project_path,
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
    branch_dir = memory_project.paths["branch_dir"]
    memory_project.paths["concept_state"].unlink()
    memory_project.paths["decision_log"].write_text("", encoding="utf-8")
    (branch_dir / "concept.md").unlink()

    retrieved = retrieve_memory_context(memory_project.project_path, "main", "mvp.concept", full_artifact=True)
    rebuilt = consolidate_memory(
        ConsolidateMemoryRequest(project_path=memory_project.project_path, branch_name="main")
    ).to_payload()

    assert retrieved["artifact_state"]["concept"]["projectName"] == "MVP scheduling assistant"
    assert memory_project.paths["concept_state"].exists()
    assert "MVP scheduling assistant" in memory_project.paths["concept_state"].read_text(encoding="utf-8")
    assert "MVP scheduling assistant" in (branch_dir / "concept.md").read_text(encoding="utf-8")
    assert rebuilt["generated_paths"]


def test_bootstrap_branch_canonical_state_imports_legacy_files_only_once(memory_project) -> None:
    store = MemoryStore(memory_project.project_path)
    store.purge_branch("main")

    legacy_progress = {
        "currentImplementStep": None,
        "completedSteps": [],
        "plannedSteps": ["step-01-bootstrap"],
        "stepStatus": {"step-01-bootstrap": step_status(status="planned")},
        "stepMetadata": {"step-01-bootstrap": step_metadata("code", "required")},
        "coversFunctions": {"step-01-bootstrap": {"p1": ["Booking workflow"], "p2": [], "p3": []}},
        "planningMetadata": {
            "lastPlannedStep": "step-01-bootstrap",
            "planningPhase": "initial",
            "totalStepsEstimated": 1,
            "stepDependencies": {"step-01-bootstrap": []},
            "progressMetrics": {
                "p1Coverage": {"covered": 1, "total": 1, "percentage": 100},
                "p2Coverage": {"covered": 0, "total": 0, "percentage": 0},
                "p3Coverage": {"covered": 0, "total": 0, "percentage": 0},
                "overallProgress": 50,
            },
        },
    }
    memory_project.paths["progress"].write_text(
        json.dumps(legacy_progress, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    memory_project.paths["decision_log"].write_text(
        json.dumps(
            make_record(
                "main",
                "mvp.plan",
                "memory.register-step",
                "Imported legacy planned step",
                step_id="step-01-bootstrap",
                status="validated",
            ),
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    assert bootstrap_branch_canonical_state(memory_project.project_path, "main") is True

    memory_project.paths["progress"].write_text(
        json.dumps({**legacy_progress, "plannedSteps": ["step-99-overwrite"]}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    assert bootstrap_branch_canonical_state(memory_project.project_path, "main") is False

    canonical = load_canonical_branch_state(memory_project.project_path, "main")
    assert canonical.progress["plannedSteps"] == ["step-01-bootstrap"]
    assert canonical.record_streams["decision_log"][0]["summary"] == "Imported legacy planned step"
