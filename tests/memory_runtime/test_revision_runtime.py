from __future__ import annotations

from madspec_cli.memory.shared.storage import get_memory_paths
from madspec_cli.memory.shared.system_store import build_runtime_snapshot_specs, load_canonical_branch_state
from madspec_cli.memory.shared.system_store.runtime_mutations import RuntimeMutationPlan, commit_runtime_mutation
from madspec_cli.memory.shared.system_store.store import MemoryStore
from madspec_cli.memory.implementation import checkpoint_implementation_step, complete_implementation_step, start_implementation_step
from madspec_cli.memory.workflow.planning import (
    _build_register_step_plan,
    _detect_register_step_conflict,
    extract_function_catalog,
    register_planned_step,
)


def test_branch_runtime_revision_bootstraps_and_increments(memory_project) -> None:
    memory_project.write_mvp_concept(variant="auth_sessions")
    memory_project.create_step_artifacts("step-01-authentication")

    canonical = load_canonical_branch_state(memory_project.project_path, "main")
    assert canonical.runtime_revision == 0

    payload = register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        step_id="step-01-authentication",
        covers=["Authentication"],
        step_kind="code",
    )

    assert payload["accepted"] is True
    assert payload["runtime_revision_before"] == 0
    assert payload["runtime_revision_after"] == 1
    assert MemoryStore(memory_project.project_path).fetch_branch_revision("main") == 1


def test_compare_and_apply_allows_compatible_stale_register_step(memory_project) -> None:
    memory_project.write_mvp_concept(variant="auth_sessions")
    memory_project.create_step_artifacts("step-01-authentication")
    memory_project.create_step_artifacts("step-02-session-persistence")

    base_state = load_canonical_branch_state(memory_project.project_path, "main")
    known_functions = {
        item: priority
        for priority, items in extract_function_catalog(
            memory_project.project_path,
            "main",
            "mvp.plan",
        ).items()
        for item in items
    }

    first = register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        step_id="step-01-authentication",
        covers=["Authentication"],
        step_kind="code",
    )
    assert first["accepted"] is True

    payload = commit_runtime_mutation(
        memory_project.project_path,
        branch_name="main",
        stage="mvp.plan",
        mutation_kind="register-step",
        scope="plan-catalog",
        session_key="active",
        expected_revision=0,
        base_state=base_state,
        plan_builder=lambda latest_state: _build_register_step_plan(
            memory_project.project_path,
            "main",
            "mvp.plan",
            session_key="active",
            step_id="step-02-session-persistence",
            normalized_covers=["Sessions"],
            known_functions=known_functions,
            step_kind="code",
            effective_tdd_policy="required",
            waiver_reason=None,
            depends_on=["step-01-authentication"],
            summary="Register session persistence after authentication.",
            title=None,
            related_artifacts=[],
            size=None,
            complexity=None,
            canonical=latest_state,
        ),
        conflict_detector=lambda base, current: _detect_register_step_conflict(
            base,
            current,
            step_id="step-02-session-persistence",
        ),
    )

    assert payload["runtime_revision_before"] == 1
    assert payload["runtime_revision_after"] == 2
    refreshed = load_canonical_branch_state(memory_project.project_path, "main")
    assert refreshed.runtime_revision == 2
    assert "step-02-session-persistence" in refreshed.progress["plannedSteps"]


def test_compare_and_apply_returns_conflict_for_same_step_stale_register(memory_project) -> None:
    memory_project.write_mvp_concept(variant="auth_sessions")
    memory_project.create_step_artifacts("step-01-authentication")

    base_state = load_canonical_branch_state(memory_project.project_path, "main")
    known_functions = {
        item: priority
        for priority, items in extract_function_catalog(
            memory_project.project_path,
            "main",
            "mvp.plan",
        ).items()
        for item in items
    }

    first = register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        step_id="step-01-authentication",
        covers=["Authentication"],
        step_kind="code",
    )
    assert first["accepted"] is True

    payload = commit_runtime_mutation(
        memory_project.project_path,
        branch_name="main",
        stage="mvp.plan",
        mutation_kind="register-step",
        scope="plan-catalog",
        session_key="active",
        expected_revision=0,
        base_state=base_state,
        plan_builder=lambda latest_state: _build_register_step_plan(
            memory_project.project_path,
            "main",
            "mvp.plan",
            session_key="active",
            step_id="step-01-authentication",
            normalized_covers=["Authentication"],
            known_functions=known_functions,
            step_kind="code",
            effective_tdd_policy="required",
            waiver_reason=None,
            depends_on=[],
            summary="Duplicate stale register should conflict.",
            title=None,
            related_artifacts=[],
            size=None,
            complexity=None,
            canonical=latest_state,
        ),
        conflict_detector=lambda base, current: _detect_register_step_conflict(
            base,
            current,
            step_id="step-01-authentication",
        ),
    )

    assert payload["accepted"] is False
    assert payload["kind"] == "conflict"
    assert payload["conflict"]["kind"] == "progress_conflict"
    assert payload["conflict"]["scope"] == "plan-catalog"
    assert payload["conflict"]["step_id"] == "step-01-authentication"
    assert payload["conflict"]["expected_revision"] == 0
    assert payload["conflict"]["actual_revision"] == 1


def test_runtime_mutation_recomputes_progress_derived_fields(memory_project) -> None:
    memory_project.write_mvp_concept(variant="auth_sessions")
    memory_project.create_step_artifacts("step-01-authentication")

    base_state = load_canonical_branch_state(memory_project.project_path, "main")
    paths = get_memory_paths(memory_project.project_path, "main")
    bad_progress = {
        "currentImplementStep": None,
        "completedSteps": [],
        "plannedSteps": ["step-01-authentication"],
        "stepStatus": {
            "step-01-authentication": {
                "status": "planned",
                "completedAt": None,
                "tddPhase": "not_started",
                "redEvidence": [],
                "greenEvidence": [],
                "refactorNote": None,
            }
        },
        "stepMetadata": {
            "step-01-authentication": {
                "kind": "code",
                "tddPolicy": "required",
                "waiverReason": None,
            }
        },
        "coversFunctions": {
            "step-01-authentication": {
                "p1": ["Authentication"],
                "p2": [],
                "p3": [],
            }
        },
        "planningMetadata": {
            "lastPlannedStep": "stale-step",
            "planningPhase": "stale-phase",
            "totalStepsEstimated": None,
            "stepDependencies": {"step-01-authentication": []},
            "progressMetrics": {
                "p1Coverage": {"covered": 0, "total": 0, "percentage": 0},
                "p2Coverage": {"covered": 0, "total": 0, "percentage": 0},
                "p3Coverage": {"covered": 0, "total": 0, "percentage": 0},
                "overallProgress": 0,
            },
        },
    }

    payload = commit_runtime_mutation(
        memory_project.project_path,
        branch_name="main",
        stage="mvp.plan",
        mutation_kind="test-progress",
        scope="plan-catalog",
        session_key="active",
        expected_revision=0,
        base_state=base_state,
        plan_builder=lambda _: RuntimeMutationPlan(
            stage_snapshots=build_runtime_snapshot_specs(
                memory_project.project_path,
                "main",
                {"progress": bad_progress},
            ),
            sessions=[],
            records=[],
        ),
        conflict_detector=lambda *_: None,
    )

    assert payload["runtime_revision_after"] == 1
    refreshed = load_canonical_branch_state(memory_project.project_path, "main")
    planning_metadata = refreshed.progress["planningMetadata"]
    assert planning_metadata["lastPlannedStep"] == "step-01-authentication"
    assert planning_metadata["planningPhase"] == "initial"
    assert planning_metadata["progressMetrics"]["p1Coverage"]["covered"] == 1
    assert planning_metadata["progressMetrics"]["overallProgress"] > 0
    assert refreshed.progress["stepStatus"]["step-01-authentication"]["status"] == "planned"
    assert str(paths.progress).endswith("progress.json")


def test_scope_busy_does_not_replace_stale_revision_conflict(memory_project) -> None:
    memory_project.write_mvp_concept(variant="auth_sessions")
    memory_project.create_step_artifacts("step-01-authentication")
    memory_project.create_step_artifacts("step-02-session-persistence")

    base_state = load_canonical_branch_state(memory_project.project_path, "main")
    known_functions = {
        item: priority
        for priority, items in extract_function_catalog(
            memory_project.project_path,
            "main",
            "mvp.plan",
        ).items()
        for item in items
    }

    store = MemoryStore(memory_project.project_path)
    held = store.acquire_lease("plan-catalog:main", "external-owner", ttl_seconds=30)
    assert held["acquired"] is True

    busy = register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        step_id="step-01-authentication",
        covers=["Authentication"],
        step_kind="code",
    )
    assert busy["accepted"] is False
    assert busy["kind"] == "scope_busy"

    store.release_lease("plan-catalog:main", "external-owner")

    first = register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        step_id="step-01-authentication",
        covers=["Authentication"],
        step_kind="code",
    )
    assert first["accepted"] is True

    stale = commit_runtime_mutation(
        memory_project.project_path,
        branch_name="main",
        stage="mvp.plan",
        mutation_kind="register-step",
        scope="plan-catalog",
        session_key="active",
        expected_revision=0,
        base_state=base_state,
        plan_builder=lambda latest_state: _build_register_step_plan(
            memory_project.project_path,
            "main",
            "mvp.plan",
            session_key="active",
            step_id="step-02-session-persistence",
            normalized_covers=["Sessions"],
            known_functions=known_functions,
            step_kind="code",
            effective_tdd_policy="required",
            waiver_reason=None,
            depends_on=["step-01-authentication"],
            summary="Stale mutation should conflict after lease contention is resolved.",
            title=None,
            related_artifacts=[],
            size=None,
            complexity=None,
            canonical=latest_state,
        ),
        conflict_detector=lambda base, current: _detect_register_step_conflict(
            base,
            current,
            step_id="step-01-authentication",
        ),
    )
    assert stale["accepted"] is False
    assert stale["kind"] == "conflict"


def test_parallel_register_after_started_implementation_preserves_shared_execution_focus(memory_project) -> None:
    memory_project.write_mvp_concept(variant="auth_sessions")
    memory_project.create_step_artifacts("step-01-authentication")
    memory_project.create_step_artifacts("step-02-session-persistence")

    first = register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        session_key="planner",
        step_id="step-01-authentication",
        covers=["Authentication"],
        step_kind="code",
    )
    started = start_implementation_step(
        memory_project.project_path,
        "main",
        "mvp.implement",
        session_key="impl",
        step_id="step-01-authentication",
    )
    second = register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        session_key="planner",
        step_id="step-02-session-persistence",
        covers=["Sessions"],
        step_kind="code",
        depends_on=["step-01-authentication"],
        expected_revision=first["runtime_revision_after"],
    )

    assert first["accepted"] is True
    assert started["accepted"] is True
    assert second["accepted"] is True

    refreshed = load_canonical_branch_state(memory_project.project_path, "main")
    impl_session = MemoryStore(memory_project.project_path).fetch_session(branch="main", session_key="impl")
    planner_session = MemoryStore(memory_project.project_path).fetch_session(branch="main", session_key="planner")

    assert refreshed.progress["currentImplementStep"] == "step-01-authentication"
    assert refreshed.progress["stepStatus"]["step-01-authentication"]["status"] == "in_progress"
    assert refreshed.progress["plannedSteps"] == ["step-01-authentication", "step-02-session-persistence"]
    assert planner_session is not None and planner_session["current_step"] == "step-02-session-persistence"
    assert impl_session is not None and impl_session["current_step"] == "step-01-authentication"


def test_parallel_register_after_checkpoint_preserves_step_runtime_and_planning_derivatives(memory_project) -> None:
    memory_project.write_mvp_concept(variant="auth_sessions")
    memory_project.create_step_artifacts("step-01-authentication")
    memory_project.create_step_artifacts("step-02-session-persistence")

    register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        step_id="step-01-authentication",
        covers=["Authentication"],
        step_kind="code",
    )
    started = start_implementation_step(
        memory_project.project_path,
        "main",
        "mvp.implement",
        session_key="impl",
        step_id="step-01-authentication",
    )
    checkpointed = checkpoint_implementation_step(
        memory_project.project_path,
        "main",
        "mvp.implement",
        session_key="impl",
        step_id="step-01-authentication",
        summary="Auth tests red",
        tdd_phase="red",
        red_evidence=["uv run pytest tests/test_auth.py -q"],
    )
    second = register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        session_key="planner",
        step_id="step-02-session-persistence",
        covers=["Sessions"],
        step_kind="code",
        depends_on=["step-01-authentication"],
        expected_revision=started["runtime_revision_after"],
    )

    assert checkpointed["accepted"] is True
    assert second["accepted"] is True

    refreshed = load_canonical_branch_state(memory_project.project_path, "main")
    status = refreshed.progress["stepStatus"]["step-01-authentication"]
    planning = refreshed.progress["planningMetadata"]

    assert status["status"] == "in_progress"
    assert status["tddPhase"] == "red"
    assert status["redEvidence"] == ["uv run pytest tests/test_auth.py -q"]
    assert planning["lastPlannedStep"] == "step-02-session-persistence"
    assert planning["planningPhase"] == "incremental"
    assert planning["stepDependencies"]["step-02-session-persistence"] == ["step-01-authentication"]
    assert planning["progressMetrics"]["p1Coverage"]["covered"] == 2


def test_parallel_register_after_complete_preserves_completion_and_recomputed_next_step(memory_project) -> None:
    memory_project.write_mvp_concept(variant="auth_sessions")
    memory_project.create_step_artifacts("step-01-authentication")
    memory_project.create_step_artifacts("step-02-session-persistence")

    register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        step_id="step-01-authentication",
        covers=["Authentication"],
        step_kind="code",
    )
    started = start_implementation_step(
        memory_project.project_path,
        "main",
        "mvp.implement",
        session_key="impl",
        step_id="step-01-authentication",
    )
    checkpointed = checkpoint_implementation_step(
        memory_project.project_path,
        "main",
        "mvp.implement",
        session_key="impl",
        step_id="step-01-authentication",
        summary="Authentication tests green",
        tdd_phase="green",
        red_evidence=["uv run pytest tests/test_auth.py -q"],
        green_evidence=["uv run pytest tests/test_auth.py -q"],
        refactor_note="No refactor needed.",
    )
    completed = complete_implementation_step(
        memory_project.project_path,
        "main",
        "mvp.implement",
        session_key="impl",
        step_id="step-01-authentication",
        summary="Authentication complete",
        facts=["Authentication persists sessions"],
        evidence=["tests/test_auth.py"],
    )
    second = register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        session_key="planner",
        step_id="step-02-session-persistence",
        covers=["Sessions"],
        step_kind="code",
        depends_on=["step-01-authentication"],
        expected_revision=started["runtime_revision_after"],
    )

    assert checkpointed["accepted"] is True
    assert completed["accepted"] is True
    assert second["accepted"] is True

    refreshed = load_canonical_branch_state(memory_project.project_path, "main")
    planner_session = MemoryStore(memory_project.project_path).fetch_session(branch="main", session_key="planner")

    assert refreshed.progress["completedSteps"] == ["step-01-authentication"]
    assert refreshed.progress["stepStatus"]["step-01-authentication"]["status"] == "completed"
    assert refreshed.progress["currentImplementStep"] is None
    assert second["progressMetrics"]["p1Coverage"]["covered"] == 2
    assert refreshed.progress["planningMetadata"]["lastPlannedStep"] == "step-02-session-persistence"
    assert planner_session is not None and planner_session["current_step"] == "step-02-session-persistence"
