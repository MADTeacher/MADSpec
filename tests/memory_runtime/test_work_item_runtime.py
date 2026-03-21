from __future__ import annotations

import json

import pytest

from madspec_cli.memory.application.orchestration import (
    ClaimWorkItemRequest,
    CreateTaskRequest,
    CreateWorkItemRequest,
    ReleaseWorkItemRequest,
    claim_work_item,
    create_task,
    create_work_item,
    release_work_item,
)
from madspec_cli.memory.implementation import complete_implementation_step, start_implementation_step
from madspec_cli.memory.shared.system_store.sessions import read_runtime_session_payload
from madspec_cli.memory.shared.system_store.store import MemoryStore
from madspec_cli.memory.workflow.planning import register_planned_step


def test_task_and_work_item_round_trip_with_scope_conflict(memory_project) -> None:
    store = MemoryStore(memory_project.project_path)
    task = store.create_task(
        branch="main",
        title="Auth coordination",
        summary="Coordinate auth work",
        acceptance_note=None,
    )

    first = store.create_work_item(
        branch="main",
        task_id=task["task_id"],
        title="Implement auth service",
        work_item_type="implementation",
        subagent_id="developer",
        step_id="step-01-authentication",
        scope_descriptor={
            "step_id": "step-01-authentication",
            "paths": ["src/auth/service.py"],
            "artifacts": [],
            "concerns": ["service"],
        },
        acceptance_note=None,
    )

    with pytest.raises(ValueError):
        store.create_work_item(
            branch="main",
            task_id=task["task_id"],
            title="Conflicting auth slice",
            work_item_type="testing",
            subagent_id="testing",
            step_id="step-01-authentication",
            scope_descriptor={
                "step_id": "step-01-authentication",
                "paths": ["src/auth/service.py"],
                "artifacts": [],
                "concerns": [],
            },
            acceptance_note=None,
        )

    second = store.create_work_item(
        branch="main",
        task_id=task["task_id"],
        title="Document auth flow",
        work_item_type="docs",
        subagent_id="docs",
        step_id="step-01-authentication",
        scope_descriptor={
            "step_id": "step-01-authentication",
            "paths": ["docs/auth.md"],
            "artifacts": [],
            "concerns": ["documentation"],
        },
        acceptance_note=None,
    )
    assert first["task_id"] == second["task_id"] == task["task_id"]

    claimed = store.claim_work_item(
        branch="main",
        work_item_id=first["work_item_id"],
        session_key="impl",
        subagent_id="developer",
    )
    assert claimed["status"] == "claimed"
    assert store.fetch_active_claim_for_session(branch="main", session_key="impl")["work_item_id"] == first["work_item_id"]

    released = store.release_work_item(
        branch="main",
        work_item_id=first["work_item_id"],
        session_key="impl",
    )
    assert released["status"] == "open"
    assert store.fetch_active_claim_for_session(branch="main", session_key="impl") is None


def test_claim_binds_session_and_complete_step_closes_work_item(memory_project) -> None:
    memory_project.write_mvp_concept(variant="auth_sessions")
    memory_project.create_step_artifacts("step-01-authentication")
    memory_project.create_step_artifacts("step-02-session-persistence")

    assert register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        session_key="planner",
        step_id="step-01-authentication",
        covers=["Authentication"],
        step_kind="code",
    )["accepted"] is True
    assert register_planned_step(
        memory_project.project_path,
        "main",
        "mvp.plan",
        session_key="planner",
        step_id="step-02-session-persistence",
        covers=["Sessions"],
        step_kind="code",
    )["accepted"] is True

    task = create_task(
        CreateTaskRequest(
            project_path=memory_project.project_path,
            branch_name="main",
            title="Implement auth step",
            summary=None,
            acceptance_note=None,
        )
    ).to_payload()["task"]
    work_item = create_work_item(
        CreateWorkItemRequest(
            project_path=memory_project.project_path,
            branch_name="main",
            task_id=task["task_id"],
            title="Developer auth slice",
            work_item_type="implementation",
            subagent_id="developer",
            step_id="step-01-authentication",
            scope_descriptor={
                "step_id": "step-01-authentication",
                "paths": ["src/auth/service.py"],
                "artifacts": [],
                "concerns": ["service"],
            },
            acceptance_note=None,
        )
    ).to_payload()["work_item"]
    claim_payload = claim_work_item(
        ClaimWorkItemRequest(
            project_path=memory_project.project_path,
            branch_name="main",
            work_item_id=work_item["work_item_id"],
            session_key="impl",
            subagent_id="developer",
        )
    ).to_payload()
    session_payload = read_runtime_session_payload(
        memory_project.project_path,
        branch_name="main",
        session_key="impl",
    )
    assert session_payload["work_item_id"] == work_item["work_item_id"]
    assert claim_payload["session"]["task_id"] == task["task_id"]

    rejected = start_implementation_step(
        memory_project.project_path,
        "main",
        "mvp.implement",
        session_key="impl",
        step_id="step-02-session-persistence",
    )
    assert rejected["accepted"] is False
    assert work_item["work_item_id"] in json.dumps(rejected, ensure_ascii=False)

    started = start_implementation_step(
        memory_project.project_path,
        "main",
        "mvp.implement",
        session_key="impl",
        step_id="step-01-authentication",
    )
    assert started["accepted"] is True
    store = MemoryStore(memory_project.project_path)
    assert store.fetch_work_item(work_item["work_item_id"])["status"] == "in_progress"

    completed = complete_implementation_step(
        memory_project.project_path,
        "main",
        "mvp.implement",
        session_key="impl",
        step_id="step-01-authentication",
        summary="Authentication done",
        red_evidence=["uv run pytest tests/test_auth.py -q"],
        green_evidence=["uv run pytest tests/test_auth.py -q"],
        refactor_note="No refactor needed.",
        facts=["Authentication persists session data"],
    )
    assert completed["accepted"] is True
    assert store.fetch_work_item(work_item["work_item_id"])["status"] == "completed"

    released = release_work_item(
        ReleaseWorkItemRequest(
            project_path=memory_project.project_path,
            branch_name="main",
            work_item_id=work_item["work_item_id"],
            session_key="impl",
        )
    ).to_payload()
    assert released["session"]["work_item_id"] is None


def test_work_item_dependencies_drive_readiness_and_task_status(memory_project) -> None:
    store = MemoryStore(memory_project.project_path)
    task = store.create_task(
        branch="main",
        title="Coordinator task",
        summary=None,
        acceptance_note=None,
    )
    first = store.create_work_item(
        branch="main",
        task_id=task["task_id"],
        title="Architecture slice",
        work_item_type="architecture",
        subagent_id="architecture",
        step_id="step-01-authentication",
        scope_descriptor={
            "step_id": "step-01-authentication",
            "paths": ["src/auth/contracts.py"],
            "artifacts": [],
            "concerns": ["architecture"],
        },
        acceptance_note=None,
    )
    second = store.create_work_item(
        branch="main",
        task_id=task["task_id"],
        title="Developer slice",
        work_item_type="implementation",
        subagent_id="developer",
        step_id="step-01-authentication",
        scope_descriptor={
            "step_id": "step-01-authentication",
            "paths": ["src/auth/service.py"],
            "artifacts": [],
            "concerns": ["implementation"],
        },
        acceptance_note=None,
        depends_on_work_item_ids=[first["work_item_id"]],
    )

    explained = store.explain_work_item(branch="main", work_item_id=second["work_item_id"], session_key="impl")
    assert explained is not None
    assert explained["readiness"]["status"] == "blocked"
    assert explained["dependency_state"]["unmet_dependencies"][0]["work_item_id"] == first["work_item_id"]
    assert store.fetch_task(task["task_id"])["status"] == "open"
