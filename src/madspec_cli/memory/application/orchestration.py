from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from madspec_cli.features.agents.application.common import find_subagent
from madspec_cli.shared.kernel.result import PayloadResult

from ..domain.work_items import coordination_binding_from_session
from ..shared.system_store.sessions import read_runtime_session_payload, save_runtime_session
from ..shared.system_store.store import MemoryStore


@dataclass(frozen=True)
class CreateTaskRequest:
    project_path: Path
    branch_name: str
    title: str
    summary: str | None
    acceptance_note: str | None


@dataclass(frozen=True)
class ListTasksRequest:
    project_path: Path
    branch_name: str


@dataclass(frozen=True)
class CreateWorkItemRequest:
    project_path: Path
    branch_name: str
    task_id: str
    title: str
    work_item_type: str
    subagent_id: str
    step_id: str | None
    scope_descriptor: dict[str, Any]
    acceptance_note: str | None


@dataclass(frozen=True)
class ListWorkItemsRequest:
    project_path: Path
    branch_name: str
    task_id: str | None = None
    session_key: str | None = None


@dataclass(frozen=True)
class ClaimWorkItemRequest:
    project_path: Path
    branch_name: str
    work_item_id: str
    session_key: str
    subagent_id: str


@dataclass(frozen=True)
class ReleaseWorkItemRequest:
    project_path: Path
    branch_name: str
    work_item_id: str
    session_key: str


@dataclass(frozen=True)
class CoordinationContextRequest:
    project_path: Path
    branch_name: str
    session_key: str
    task_id: str | None = None
    work_item_id: str | None = None


@dataclass(frozen=True)
class CoordinationResult(PayloadResult):
    pass


def create_task(request: CreateTaskRequest) -> CoordinationResult:
    store = MemoryStore(request.project_path)
    task = store.create_task(
        branch=request.branch_name,
        title=request.title,
        summary=request.summary,
        acceptance_note=request.acceptance_note,
    )
    return CoordinationResult(payload={"task": task})


def list_tasks(request: ListTasksRequest) -> CoordinationResult:
    tasks = MemoryStore(request.project_path).list_tasks(branch=request.branch_name)
    return CoordinationResult(payload={"tasks": tasks})


def create_work_item(request: CreateWorkItemRequest) -> CoordinationResult:
    store = MemoryStore(request.project_path)
    task = store.fetch_task(request.task_id)
    if task is None or task["branch"] != request.branch_name:
        raise ValueError(f"task '{request.task_id}' was not found")
    if find_subagent(request.project_path, request.subagent_id) is None:
        raise ValueError(f"subagent '{request.subagent_id}' was not found")
    work_item = store.create_work_item(
        branch=request.branch_name,
        task_id=request.task_id,
        title=request.title,
        work_item_type=request.work_item_type,
        subagent_id=request.subagent_id,
        step_id=request.step_id,
        scope_descriptor=request.scope_descriptor,
        acceptance_note=request.acceptance_note,
    )
    return CoordinationResult(payload={"task": task, "work_item": work_item})


def list_work_items(request: ListWorkItemsRequest) -> CoordinationResult:
    work_items = MemoryStore(request.project_path).list_work_items(
        branch=request.branch_name,
        task_id=request.task_id,
        session_key=request.session_key,
    )
    return CoordinationResult(payload={"work_items": work_items})


def claim_work_item(request: ClaimWorkItemRequest) -> CoordinationResult:
    store = MemoryStore(request.project_path)
    if find_subagent(request.project_path, request.subagent_id) is None:
        raise ValueError(f"subagent '{request.subagent_id}' was not found")
    work_item = store.fetch_work_item(request.work_item_id)
    if work_item is None or work_item["branch"] != request.branch_name:
        raise ValueError(f"work item '{request.work_item_id}' was not found")
    claimed = store.claim_work_item(
        branch=request.branch_name,
        work_item_id=request.work_item_id,
        session_key=request.session_key,
        subagent_id=request.subagent_id,
    )
    session_payload = read_runtime_session_payload(
        request.project_path,
        branch_name=request.branch_name,
        session_key=request.session_key,
    )
    session_payload["task_id"] = claimed["task_id"]
    session_payload["work_item_id"] = claimed["work_item_id"]
    session_payload["subagent_id"] = request.subagent_id
    save_runtime_session(
        request.project_path,
        branch_name=request.branch_name,
        session_key=request.session_key,
        payload=session_payload,
    )
    return CoordinationResult(payload={"work_item": claimed, "session": session_payload})


def release_work_item(request: ReleaseWorkItemRequest) -> CoordinationResult:
    store = MemoryStore(request.project_path)
    released = store.release_work_item(
        branch=request.branch_name,
        work_item_id=request.work_item_id,
        session_key=request.session_key,
    )
    session_payload = read_runtime_session_payload(
        request.project_path,
        branch_name=request.branch_name,
        session_key=request.session_key,
    )
    binding = coordination_binding_from_session(session_payload)
    if binding["work_item_id"] == request.work_item_id:
        session_payload["task_id"] = None
        session_payload["work_item_id"] = None
        session_payload["subagent_id"] = None
        save_runtime_session(
            request.project_path,
            branch_name=request.branch_name,
            session_key=request.session_key,
            payload=session_payload,
        )
    return CoordinationResult(payload={"work_item": released, "session": session_payload})


def resolve_coordination_context(request: CoordinationContextRequest) -> CoordinationResult:
    store = MemoryStore(request.project_path)
    resolved = store.fetch_session_coordination(
        branch=request.branch_name,
        session_key=request.session_key,
    )
    task = resolved["task"]
    work_item = resolved["work_item"]
    claim = resolved["claim"]
    if request.task_id:
        task = store.fetch_task(request.task_id)
    if request.work_item_id:
        work_item = store.fetch_work_item(request.work_item_id)
        claim = store.fetch_active_claim_for_work_item(work_item_id=request.work_item_id)
        if work_item is not None and task is None:
            task = store.fetch_task(str(work_item["task_id"]))
    return CoordinationResult(
        payload={
            "task": task,
            "work_item": work_item,
            "claim": claim,
            "session_binding": resolved["session_binding"],
        }
    )
