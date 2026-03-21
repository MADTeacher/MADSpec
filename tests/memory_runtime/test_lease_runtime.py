from __future__ import annotations

from madspec_cli.memory import register_planned_step
from madspec_cli.memory.implementation import checkpoint_implementation_step, start_implementation_step
from madspec_cli.memory.shared.system_store.store import MemoryStore


def test_writer_lease_acquire_release_and_expiry(memory_project) -> None:
    store = MemoryStore(memory_project.project_path)

    first = store.acquire_lease("plan-catalog:main", "owner-a", ttl_seconds=30)
    assert first["acquired"] is True
    assert first["lease"]["lease_name"] == "plan-catalog:main"
    assert first["lease"]["expired"] is False

    blocked = store.acquire_lease("plan-catalog:main", "owner-b", ttl_seconds=30)
    assert blocked["acquired"] is False
    assert blocked["lease"]["owner_id"] == "owner-a"

    store.release_lease("plan-catalog:main", "owner-a")
    reacquired = store.acquire_lease("plan-catalog:main", "owner-b", ttl_seconds=30)
    assert reacquired["acquired"] is True

    expired = store.acquire_lease("implement-step:main:step-01-authentication", "owner-c", ttl_seconds=0)
    assert expired["acquired"] is True
    takeover = store.acquire_lease("implement-step:main:step-01-authentication", "owner-d", ttl_seconds=30)
    assert takeover["acquired"] is True
    assert takeover["lease"]["owner_id"] == "owner-d"


def test_register_step_returns_scope_busy_when_plan_catalog_lease_is_held(memory_project) -> None:
    memory_project.write_mvp_concept(variant="auth_sessions")
    memory_project.create_step_artifacts("step-01-authentication")

    store = MemoryStore(memory_project.project_path)
    held = store.acquire_lease("plan-catalog:main", "external-owner", ttl_seconds=30)
    assert held["acquired"] is True

    payload = register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        step_id="step-01-authentication",
        covers=["Authentication"],
        step_kind="code",
    )

    assert payload["accepted"] is False
    assert payload["kind"] == "scope_busy"
    assert payload["scope_busy"]["scope"] == "plan-catalog"
    assert payload["scope_busy"]["lease_name"] == "plan-catalog:main"
    assert payload["scope_busy"]["owner_id"] == "external-owner"


def test_checkpoint_step_returns_scope_busy_for_same_implementation_step(memory_project) -> None:
    memory_project.write_mvp_concept(variant="auth_sessions")
    memory_project.create_step_artifacts("step-01-authentication")

    register_payload = register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        step_id="step-01-authentication",
        covers=["Authentication"],
        step_kind="code",
    )
    assert register_payload["accepted"] is True

    started = start_implementation_step(
        memory_project.project_path,
        "main",
        "mvp.implement",
        step_id="step-01-authentication",
        session_key="impl",
    )
    assert started["accepted"] is True

    store = MemoryStore(memory_project.project_path)
    held = store.acquire_lease("implement-step:main:step-01-authentication", "external-owner", ttl_seconds=30)
    assert held["acquired"] is True

    payload = checkpoint_implementation_step(
        memory_project.project_path,
        "main",
        "mvp.implement",
        session_key="impl",
        step_id="step-01-authentication",
        summary="Checkpoint while another writer holds the step lease",
        tdd_phase="red",
        red_evidence=["pytest tests/test_auth.py -q"],
    )

    assert payload["accepted"] is False
    assert payload["kind"] == "scope_busy"
    assert payload["scope_busy"]["scope"] == "step"
    assert payload["scope_busy"]["lease_name"] == "implement-step:main:step-01-authentication"


def test_different_hot_scopes_do_not_contend(memory_project) -> None:
    memory_project.write_mvp_concept(variant="auth_sessions")
    memory_project.create_step_artifacts("step-01-authentication")
    memory_project.create_step_artifacts("step-02-session-persistence")

    first = register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        step_id="step-01-authentication",
        covers=["Authentication"],
        step_kind="code",
    )
    assert first["accepted"] is True
    second = register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        step_id="step-02-session-persistence",
        covers=["Sessions"],
        step_kind="code",
    )
    assert second["accepted"] is True

    store = MemoryStore(memory_project.project_path)
    held = store.acquire_lease("implement-step:main:step-01-authentication", "external-owner", ttl_seconds=30)
    assert held["acquired"] is True

    payload = start_implementation_step(
        memory_project.project_path,
        "main",
        "mvp.implement",
        session_key="impl",
        step_id="step-02-session-persistence",
    )

    assert payload["accepted"] is True
    assert payload["step_id"] == "step-02-session-persistence"
