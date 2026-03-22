from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from madspec_cli.shared.kernel.result import PayloadResult

if TYPE_CHECKING:
    from madspec_cli.shared.kernel.ports import SubagentFinder


def _lazy_find_subagent():
    from madspec_cli.features.agents.application.common import find_subagent
    return find_subagent


from ..domain.work_items import coordination_binding_from_session
from ..shared.system_store.canonical_state import refresh_branch_file_projections
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
    acceptance_note: str | None = None
    depends_on_work_item_ids: list[str] | None = None


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
class ExplainCoordinatorRequest:
    project_path: Path
    branch_name: str
    session_key: str | None = None
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
    refresh_branch_file_projections(request.project_path, request.branch_name)
    return CoordinationResult(payload={"task": task})


def list_tasks(request: ListTasksRequest) -> CoordinationResult:
    tasks = MemoryStore(request.project_path).list_tasks(branch=request.branch_name)
    return CoordinationResult(payload={"tasks": tasks})


def create_work_item(
    request: CreateWorkItemRequest,
    *,
    _find_subagent: SubagentFinder | None = None,
) -> CoordinationResult:
    if _find_subagent is None:
        _find_subagent = _lazy_find_subagent()
    store = MemoryStore(request.project_path)
    task = store.fetch_task(request.task_id)
    if task is None or task["branch"] != request.branch_name:
        raise ValueError(f"task '{request.task_id}' was not found")
    subagent = _find_subagent(request.project_path, request.subagent_id)
    if subagent is None:
        raise ValueError(f"subagent '{request.subagent_id}' was not found")
    work_item = store.create_work_item(
        branch=request.branch_name,
        task_id=request.task_id,
        title=request.title,
        work_item_type=request.work_item_type,
        subagent_id=request.subagent_id,
        step_id=request.step_id,
        scope_descriptor=request.scope_descriptor,
        scheduling_hints={
            "default_stage": subagent.get("defaultStage"),
            "execution_mode_hint": subagent.get("executionModeHint"),
            "subagent_dependencies": list(subagent.get("dependencies") or []),
        },
        depends_on_work_item_ids=request.depends_on_work_item_ids,
        acceptance_note=request.acceptance_note,
    )
    coordinator = store.explain_work_item(
        branch=request.branch_name,
        work_item_id=work_item["work_item_id"],
        session_key=None,
    )
    refresh_branch_file_projections(request.project_path, request.branch_name)
    return CoordinationResult(payload={"task": task, "work_item": work_item, "coordinator": coordinator})


def list_work_items(request: ListWorkItemsRequest) -> CoordinationResult:
    store = MemoryStore(request.project_path)
    work_items = store.list_work_items(
        branch=request.branch_name,
        task_id=request.task_id,
        session_key=request.session_key,
    )
    enriched = [
        {
            **item,
            **(
                store.explain_work_item(
                    branch=request.branch_name,
                    work_item_id=item["work_item_id"],
                    session_key=request.session_key,
                )
                or {}
            ),
        }
        for item in work_items
    ]
    return CoordinationResult(payload={"work_items": enriched})


def claim_work_item(
    request: ClaimWorkItemRequest,
    *,
    _find_subagent: SubagentFinder | None = None,
) -> CoordinationResult:
    if _find_subagent is None:
        _find_subagent = _lazy_find_subagent()
    store = MemoryStore(request.project_path)
    if _find_subagent(request.project_path, request.subagent_id) is None:
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
    if claimed.get("accepted") is False:
        return CoordinationResult(
            payload={
                "accepted": False,
                "reason": claimed.get("reason"),
                "work_item": store.fetch_work_item(request.work_item_id),
                "readiness": claimed.get("readiness"),
                "dependency_state": claimed.get("dependency_state"),
                "ownership_state": claimed.get("ownership_state"),
                "related_proposals": claimed.get("related_proposals"),
                "scheduler_hints": claimed.get("scheduler_hints"),
            }
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
    coordinator = store.explain_work_item(
        branch=request.branch_name,
        work_item_id=claimed["work_item_id"],
        session_key=request.session_key,
    )
    refresh_branch_file_projections(request.project_path, request.branch_name)
    return CoordinationResult(payload={"accepted": True, "work_item": claimed, "session": session_payload, "coordinator": coordinator})


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
    coordinator = store.explain_work_item(
        branch=request.branch_name,
        work_item_id=released["work_item_id"],
        session_key=request.session_key,
    )
    refresh_branch_file_projections(request.project_path, request.branch_name)
    return CoordinationResult(payload={"work_item": released, "session": session_payload, "coordinator": coordinator})


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
    coordinator = None
    if work_item is not None:
        coordinator = store.explain_work_item(
            branch=request.branch_name,
            work_item_id=str(work_item["work_item_id"]),
            session_key=request.session_key,
        )
    return CoordinationResult(
        payload={
            "task": task,
            "work_item": work_item,
            "claim": claim,
            "session_binding": resolved["session_binding"],
            "proposal_summary": resolved.get("proposal_summary"),
            "coordinator": coordinator or resolved.get("coordinator"),
        }
    )


def explain_coordinator(request: ExplainCoordinatorRequest) -> CoordinationResult:
    store = MemoryStore(request.project_path)
    session_key = request.session_key
    task = store.fetch_task(request.task_id) if request.task_id else None
    work_item_id = request.work_item_id
    if work_item_id is None and session_key:
        resolved = store.fetch_session_coordination(branch=request.branch_name, session_key=session_key)
        work_item = resolved.get("work_item")
        if work_item is not None:
            work_item_id = str(work_item["work_item_id"])
        task = task or resolved.get("task")
    coordinator = None
    if work_item_id is not None:
        coordinator = store.explain_work_item(
            branch=request.branch_name,
            work_item_id=work_item_id,
            session_key=session_key,
        )
        if coordinator is not None and task is None:
            task = store.fetch_task(str(coordinator["task_id"]))
    task_work_items = []
    if task is not None:
        task_work_items = list_work_items(
            ListWorkItemsRequest(
                project_path=request.project_path,
                branch_name=request.branch_name,
                task_id=task["task_id"],
                session_key=session_key,
            )
        ).to_payload()["work_items"]
    return CoordinationResult(
        payload={
            "branch": request.branch_name,
            "session_key": session_key,
            "task": task,
            "work_item": coordinator["work_item"] if coordinator else None,
            "coordinator": coordinator,
            "work_items": task_work_items,
        }
    )
