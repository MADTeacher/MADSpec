from __future__ import annotations

import json

from madspec_cli.memory import register_planned_step, retrieve_memory_context
from madspec_cli.memory.implementation import start_implementation_step
from madspec_cli.memory.shared.system_store.sessions import load_runtime_session, save_runtime_session
from madspec_cli.memory.shared.system_store.store import MemoryStore


def test_runtime_sessions_persist_custom_keys_and_project_only_active(memory_project) -> None:
    planner_payload = save_runtime_session(
        memory_project.project_path,
        branch_name="main",
        session_key="planner",
        payload={
            "branch": "main",
            "stage": "mvp.plan",
            "current_step": "step-02-session-persistence",
            "active_goal": "Plan the next step",
            "open_questions": ["Should session storage be encrypted?"],
            "pending_actions": ["Add step-02 dependencies"],
            "current_hypotheses": ["Step-02 should stay independent from impl focus"],
        },
    )

    reloaded = load_runtime_session(
        memory_project.project_path,
        branch_name="main",
        session_key="planner",
    )
    projected_active = json.loads(memory_project.paths["active_session"].read_text(encoding="utf-8"))
    store_payload = MemoryStore(memory_project.project_path).fetch_session(
        branch="main",
        session_key="planner",
    )

    assert planner_payload["session_key"] == "planner"
    assert reloaded["current_step"] == "step-02-session-persistence"
    assert store_payload is not None
    assert store_payload["active_goal"] == "Plan the next step"
    assert projected_active["session_key"] == "active"
    assert projected_active["current_step"] is None


def test_load_runtime_session_imports_legacy_active_only_once(memory_project) -> None:
    store = MemoryStore(memory_project.project_path)
    with store.connect() as conn:
        conn.execute("DELETE FROM sessions WHERE branch = ?", ("main",))

    legacy_payload = {
        "branch": "main",
        "active_goal": "Resume legacy active focus",
        "stage": "mvp.implement",
        "current_step": "step-01-authentication",
        "pending_actions": ["Continue implementation"],
        "open_questions": ["Do we need another checkpoint?"],
        "current_hypotheses": ["Legacy projection should hydrate canonical active"],
        "last_checkpoint_at": "2026-03-10T00:00:00+00:00",
        "updated_at": "2026-03-10T00:00:00+00:00",
    }
    memory_project.paths["active_session"].write_text(
        json.dumps(legacy_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    imported = load_runtime_session(memory_project.project_path, branch_name="main")
    legacy_payload["active_goal"] = "Changed file should not override canonical session"
    memory_project.paths["active_session"].write_text(
        json.dumps(legacy_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    reloaded = load_runtime_session(memory_project.project_path, branch_name="main")

    assert imported["current_step"] == "step-01-authentication"
    assert reloaded["active_goal"] == "Resume legacy active focus"


def test_planner_and_impl_sessions_keep_independent_current_steps(memory_project) -> None:
    memory_project.write_mvp_concept(variant="auth_sessions")
    memory_project.create_step_artifacts("step-01-authentication")
    memory_project.create_step_artifacts("step-02-session-persistence")

    first_register = register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        session_key="planner",
        step_id="step-01-authentication",
        covers=["Authentication"],
        step_kind="code",
    )
    assert first_register["accepted"] is True
    started = start_implementation_step(
        memory_project.project_path,
        "main",
        "mvp.implement",
        session_key="impl",
        step_id="step-01-authentication",
    )
    assert started["accepted"] is True
    second_register = register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        session_key="planner",
        step_id="step-02-session-persistence",
        covers=["Sessions"],
        step_kind="code",
        depends_on=["step-01-authentication"],
    )
    assert second_register["accepted"] is True

    planner_context = retrieve_memory_context(
        memory_project.project_path,
        "main",
        "mvp.plan",
        session_key="planner",
    )
    impl_context = retrieve_memory_context(
        memory_project.project_path,
        "main",
        "mvp.implement",
        session_key="impl",
    )

    assert planner_context["session_key"] == "planner"
    assert planner_context["step_id"] == "step-02-session-persistence"
    assert planner_context["active_session"]["current_step"] == "step-02-session-persistence"
    assert impl_context["session_key"] == "impl"
    assert impl_context["step_id"] == "step-01-authentication"
    assert impl_context["active_session"]["current_step"] == "step-01-authentication"
    assert impl_context["workflow"]["currentImplementStep"] == "step-01-authentication"
