from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from madspec_cli.shared.kernel.result import PayloadResult

from ..semantic.capture import capture_stage_memory
from ..semantic.checkpoint import checkpoint_stage_memory
from ..shared.storage import now_iso
from ..shared.system_store.canonical_state import load_canonical_branch_state
from ..shared.system_store.runtime_mutations import RuntimeMutationPlan, commit_runtime_mutation
from ..shared.system_store.store import MemoryStore
from ..workflow.implementation import (
    checkpoint_implementation_step,
    complete_implementation_step,
    start_implementation_step,
)
from ..workflow.planning import register_planned_step

PROPOSAL_TYPES = {
    "plan_change",
    "runtime_step_update",
    "semantic_update",
    "artifact_update",
}

PROPOSAL_STATUSES = {"pending", "applied", "conflict", "rejected"}


@dataclass(frozen=True)
class PublishProposalRequest:
    project_path: Path
    branch_name: str
    proposal_type: str
    session_key: str
    subagent_id: str
    base_revision: int
    payload: dict[str, Any]
    target_scope: dict[str, Any]
    conflict_hints: dict[str, Any]
    task_id: str | None = None
    work_item_id: str | None = None


@dataclass(frozen=True)
class ListProposalsRequest:
    project_path: Path
    branch_name: str
    task_id: str | None = None
    work_item_id: str | None = None
    session_key: str | None = None
    statuses: list[str] | None = None
    proposal_types: list[str] | None = None


@dataclass(frozen=True)
class PreviewProposalRequest:
    project_path: Path
    proposal_id: str


@dataclass(frozen=True)
class ApplyProposalRequest:
    project_path: Path
    proposal_id: str


@dataclass(frozen=True)
class ProposalResult(PayloadResult):
    pass


def publish(request: PublishProposalRequest) -> ProposalResult:
    normalized_type = _validate_proposal_type(request.proposal_type)
    store = MemoryStore(request.project_path)
    coordination = store.fetch_session_coordination(
        branch=request.branch_name,
        session_key=request.session_key,
    )
    bound = _require_claimed_binding(
        coordination,
        session_key=request.session_key,
        subagent_id=request.subagent_id,
        task_id=request.task_id,
        work_item_id=request.work_item_id,
    )
    _validate_publish_payload(normalized_type, request.payload)

    ts = now_iso()
    proposal = {
        "proposal_id": str(uuid.uuid4()),
        "branch": request.branch_name,
        "task_id": bound["task_id"],
        "work_item_id": bound["work_item_id"],
        "proposal_type": normalized_type,
        "status": "pending",
        "session_key": request.session_key,
        "subagent_id": request.subagent_id,
        "owner_id": bound["owner_id"],
        "base_revision": request.base_revision,
        "target_scope": dict(request.target_scope),
        "payload": dict(request.payload),
        "conflict_hints": dict(request.conflict_hints),
        "apply_summary": None,
        "created_at": ts,
        "updated_at": ts,
        "applied_at": None,
        "rejected_at": None,
    }
    store.upsert_runtime_proposal(proposal)
    _record_proposal_event(
        store,
        proposal,
        event_type="proposal.published",
        summary=f"Published {normalized_type} proposal",
        payload={"proposal_type": normalized_type, "target_scope": proposal["target_scope"]},
    )
    return ProposalResult(payload={"proposal": proposal})


def list_proposals(request: ListProposalsRequest) -> ProposalResult:
    proposals = MemoryStore(request.project_path).list_runtime_proposals(
        branch=request.branch_name,
        task_id=request.task_id,
        work_item_id=request.work_item_id,
        session_key=request.session_key,
        statuses=request.statuses,
        proposal_types=request.proposal_types,
        limit=100,
    )
    return ProposalResult(payload={"proposals": proposals})


def preview(request: PreviewProposalRequest) -> ProposalResult:
    store = MemoryStore(request.project_path)
    proposal = _require_proposal(store, request.proposal_id)
    coordination = store.fetch_session_coordination(
        branch=proposal["branch"],
        session_key=proposal["session_key"],
    )
    current_revision = store.fetch_branch_revision(proposal["branch"])
    ownership = _ownership_state(proposal, coordination)
    return ProposalResult(
        payload={
            "proposal": proposal,
            "current_revision": current_revision,
            "ownership": ownership,
            "events": store.list_runtime_proposal_events(proposal_id=proposal["proposal_id"], limit=20),
            "summary": _proposal_summary(proposal),
        }
    )


def apply(request: ApplyProposalRequest) -> ProposalResult:
    store = MemoryStore(request.project_path)
    proposal = _require_proposal(store, request.proposal_id)
    if proposal["status"] not in {"pending", "conflict"}:
        raise ValueError(f"proposal '{proposal['proposal_id']}' is already {proposal['status']}")
    coordination = store.fetch_session_coordination(
        branch=proposal["branch"],
        session_key=proposal["session_key"],
    )
    ownership = _ownership_state(proposal, coordination)
    if not ownership["valid"]:
        updated = _transition_proposal(
            proposal,
            status="rejected",
            apply_summary={
                "reason": "ownership_violation",
                "coordination": coordination,
            },
        )
        store.upsert_runtime_proposal(updated)
        _record_proposal_event(
            store,
            updated,
            event_type="proposal.rejected",
            summary="Rejected proposal because ownership binding is no longer valid",
            payload=updated["apply_summary"],
        )
        return ProposalResult(payload={"proposal": updated, "accepted": False})

    current_revision = store.fetch_branch_revision(proposal["branch"])
    if proposal["proposal_type"] in {"runtime_step_update", "artifact_update"} and current_revision != int(
        proposal["base_revision"]
    ):
        apply_payload = {
            "accepted": False,
            "kind": "conflict",
            "conflict": {
                "kind": proposal["proposal_type"],
                "scope": (proposal.get("target_scope") or {}).get("scope") or "work-item",
                "step_id": (proposal.get("target_scope") or {}).get("step_id"),
                "expected_revision": proposal["base_revision"],
                "actual_revision": current_revision,
                "retry_guidance": "Publish a fresh proposal from the latest runtime_revision before retrying this runtime step update.",
            },
        }
        updated = _transition_proposal(
            proposal,
            status="conflict",
            apply_summary={"result": apply_payload, "reason": "stale_revision"},
        )
        store.upsert_runtime_proposal(updated)
        _record_proposal_event(
            store,
            updated,
            event_type="proposal.conflict",
            summary="Conflict while applying proposal because base revision is stale",
            payload=updated["apply_summary"],
        )
        return ProposalResult(payload={"proposal": updated, "apply_result": apply_payload, "accepted": False})

    apply_payload = _apply_proposal_payload(request.project_path, proposal)
    if apply_payload.get("accepted", True):
        updated = _transition_proposal(
            proposal,
            status="applied",
            apply_summary={
                "result": apply_payload,
                "reason": "applied",
            },
            applied_at=now_iso(),
        )
        store.upsert_runtime_proposal(updated)
        _record_proposal_event(
            store,
            updated,
            event_type="proposal.applied",
            summary=f"Applied {proposal['proposal_type']} proposal",
            payload=updated["apply_summary"],
        )
        return ProposalResult(payload={"proposal": updated, "apply_result": apply_payload, "accepted": True})

    next_status = "conflict" if apply_payload.get("kind") in {"conflict", "scope_busy"} else "rejected"
    reason = _proposal_failure_reason(proposal, apply_payload)
    updated = _transition_proposal(
        proposal,
        status=next_status,
        apply_summary={
            "result": apply_payload,
            "reason": reason,
        },
        rejected_at=now_iso() if next_status == "rejected" else None,
    )
    store.upsert_runtime_proposal(updated)
    _record_proposal_event(
        store,
        updated,
        event_type=f"proposal.{next_status}",
        summary=f"{next_status.title()} proposal during apply",
        payload=updated["apply_summary"],
    )
    return ProposalResult(payload={"proposal": updated, "apply_result": apply_payload, "accepted": False})


def _validate_proposal_type(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in PROPOSAL_TYPES:
        raise ValueError(f"proposal_type must be one of: {', '.join(sorted(PROPOSAL_TYPES))}")
    return normalized


def _require_claimed_binding(
    coordination: dict[str, Any],
    *,
    session_key: str,
    subagent_id: str,
    task_id: str | None,
    work_item_id: str | None,
) -> dict[str, Any]:
    claim = coordination.get("claim")
    work_item = coordination.get("work_item")
    task = coordination.get("task")
    if claim is None or work_item is None or task is None:
        raise ValueError(f"session '{session_key}' is not bound to a claimed work item")
    if work_item["subagent_id"] != subagent_id:
        raise ValueError(
            f"claimed work item '{work_item['work_item_id']}' belongs to subagent '{work_item['subagent_id']}', not '{subagent_id}'"
        )
    if task_id is not None and task_id != task["task_id"]:
        raise ValueError(f"session '{session_key}' is bound to task '{task['task_id']}', not '{task_id}'")
    if work_item_id is not None and work_item_id != work_item["work_item_id"]:
        raise ValueError(
            f"session '{session_key}' is bound to work item '{work_item['work_item_id']}', not '{work_item_id}'"
        )
    return {
        "task_id": task["task_id"],
        "work_item_id": work_item["work_item_id"],
        "owner_id": claim["owner_id"],
    }


def _validate_publish_payload(proposal_type: str, payload: dict[str, Any]) -> None:
    if proposal_type == "plan_change":
        required = {"stage", "step_id", "step_kind"}
    elif proposal_type == "runtime_step_update":
        required = {"stage", "operation"}
    elif proposal_type == "semantic_update":
        required = {"stage", "operation"}
    else:
        required = {"artifacts"}
    missing = sorted(key for key in required if key not in payload)
    if missing:
        raise ValueError(f"proposal payload is missing required keys: {', '.join(missing)}")


def _proposal_summary(proposal: dict[str, Any]) -> dict[str, Any]:
    payload = proposal.get("payload") or {}
    return {
        "proposal_id": proposal["proposal_id"],
        "proposal_type": proposal["proposal_type"],
        "status": proposal["status"],
        "base_revision": proposal["base_revision"],
        "branch": proposal["branch"],
        "task_id": proposal["task_id"],
        "work_item_id": proposal["work_item_id"],
        "step_id": payload.get("step_id"),
        "operation": payload.get("operation"),
        "stage": payload.get("stage"),
    }


def _ownership_state(proposal: dict[str, Any], coordination: dict[str, Any]) -> dict[str, Any]:
    claim = coordination.get("claim")
    work_item = coordination.get("work_item")
    valid = bool(
        claim
        and work_item
        and work_item.get("work_item_id") == proposal["work_item_id"]
        and claim.get("owner_id") == proposal["owner_id"]
        and work_item.get("subagent_id") == proposal["subagent_id"]
    )
    return {
        "valid": valid,
        "claim": claim,
        "work_item": work_item,
        "proposal_owner_id": proposal["owner_id"],
    }


def _transition_proposal(
    proposal: dict[str, Any],
    *,
    status: str,
    apply_summary: dict[str, Any],
    applied_at: str | None = None,
    rejected_at: str | None = None,
) -> dict[str, Any]:
    if status not in PROPOSAL_STATUSES:
        raise ValueError(f"unknown proposal status '{status}'")
    updated = dict(proposal)
    updated["status"] = status
    updated["updated_at"] = now_iso()
    updated["apply_summary"] = apply_summary
    updated["applied_at"] = applied_at
    updated["rejected_at"] = rejected_at
    return updated


def _proposal_failure_reason(proposal: dict[str, Any], apply_payload: dict[str, Any]) -> str:
    if apply_payload.get("kind") == "conflict":
        conflict = apply_payload.get("conflict") or {}
        if conflict.get("actual_revision") != conflict.get("expected_revision"):
            return "stale_revision"
        return "scope_conflict"
    if apply_payload.get("kind") == "scope_busy":
        return "scope_conflict"
    operation = (proposal.get("payload") or {}).get("operation")
    if proposal["proposal_type"] == "runtime_step_update" and operation in {
        "start-step",
        "checkpoint-step",
        "complete-step",
    }:
        return "invalid_state_transition"
    return "rejected"


def _require_proposal(store: MemoryStore, proposal_id: str) -> dict[str, Any]:
    proposal = store.fetch_runtime_proposal(proposal_id)
    if proposal is None:
        raise ValueError(f"proposal '{proposal_id}' was not found")
    return proposal


def _record_proposal_event(
    store: MemoryStore,
    proposal: dict[str, Any],
    *,
    event_type: str,
    summary: str,
    payload: dict[str, Any],
) -> None:
    ts = now_iso()
    event = {
        "event_id": str(uuid.uuid4()),
        "proposal_id": proposal["proposal_id"],
        "branch": proposal["branch"],
        "task_id": proposal["task_id"],
        "work_item_id": proposal["work_item_id"],
        "event_type": event_type,
        "summary": summary,
        "payload": payload,
        "ts": ts,
    }
    store.append_runtime_proposal_event(event)
    store.upsert_record(
        {
            "id": str(uuid.uuid4()),
            "record_type": "event",
            "record_stream": "events",
            "scope": "step" if (proposal.get("target_scope") or {}).get("step_id") else "branch",
            "branch": proposal["branch"],
            "stage": "coordination",
            "step_id": (proposal.get("target_scope") or {}).get("step_id"),
            "status": "validated",
            "summary": summary,
            "evidence": [],
            "payload": {
                "event_type": event_type,
                "proposal_id": proposal["proposal_id"],
                "proposal_type": proposal["proposal_type"],
                "step_id": (proposal.get("target_scope") or {}).get("step_id"),
                **payload,
            },
            "source": "memory.proposal",
            "ts": ts,
        }
    )


def _apply_proposal_payload(project_path: Path, proposal: dict[str, Any]) -> dict[str, Any]:
    payload = dict(proposal.get("payload") or {})
    proposal_type = proposal["proposal_type"]
    branch_name = proposal["branch"]
    session_key = proposal["session_key"]
    base_revision = int(proposal["base_revision"])

    if proposal_type == "plan_change":
        return register_planned_step(
            project_path,
            branch_name,
            str(payload["stage"]),
            session_key=session_key,
            expected_revision=base_revision,
            step_id=str(payload["step_id"]),
            covers=list(payload.get("covers") or []),
            step_kind=str(payload["step_kind"]),
            tdd_policy=payload.get("tdd_policy"),
            waiver_reason=payload.get("waiver_reason"),
            depends_on=list(payload.get("depends_on") or []),
            summary=payload.get("summary"),
            title=payload.get("title"),
            related_artifacts=list(payload.get("related_artifacts") or []),
            size=payload.get("size"),
            complexity=payload.get("complexity"),
        )

    if proposal_type == "runtime_step_update":
        operation = str(payload.get("operation") or "").strip().lower()
        common_options = {key: value for key, value in payload.items() if key not in {"stage", "operation"}}
        stage = str(payload["stage"])
        if operation == "start-step":
            return start_implementation_step(
                project_path,
                branch_name,
                stage,
                session_key=session_key,
                expected_revision=base_revision,
                **common_options,
            )
        if operation == "checkpoint-step":
            return checkpoint_implementation_step(
                project_path,
                branch_name,
                stage,
                session_key=session_key,
                expected_revision=base_revision,
                **common_options,
            )
        if operation == "complete-step":
            return complete_implementation_step(
                project_path,
                branch_name,
                stage,
                session_key=session_key,
                expected_revision=base_revision,
                **common_options,
            )
        raise ValueError("runtime_step_update operation must be start-step, checkpoint-step, or complete-step")

    if proposal_type == "semantic_update":
        operation = str(payload.get("operation") or "").strip().lower()
        stage = str(payload["stage"])
        semantic_options = {key: value for key, value in payload.items() if key not in {"stage", "operation"}}
        if operation == "capture":
            return capture_stage_memory(
                project_path,
                branch_name,
                stage,
                session_key=session_key,
                expected_revision=base_revision,
                **semantic_options,
            )
        if operation == "checkpoint":
            summary = semantic_options.pop("summary", None)
            if not summary:
                raise ValueError("semantic_update checkpoint proposal requires summary")
            return checkpoint_stage_memory(
                project_path,
                branch_name,
                stage,
                summary,
                session_key=session_key,
                expected_revision=base_revision,
                **semantic_options,
            )
        raise ValueError("semantic_update operation must be capture or checkpoint")

    return _apply_artifact_update(project_path, proposal)


def _apply_artifact_update(project_path: Path, proposal: dict[str, Any]) -> dict[str, Any]:
    payload = dict(proposal.get("payload") or {})
    artifacts = list(payload.get("artifacts") or [])
    if not artifacts:
        raise ValueError("artifact_update proposal requires at least one artifact")
    branch_name = proposal["branch"]
    canonical = load_canonical_branch_state(project_path, branch_name)
    stage = payload.get("stage")
    scope = proposal.get("target_scope") or {}
    projection_meta = commit_runtime_mutation(
        project_path,
        branch_name=branch_name,
        stage=str(stage) if stage else None,
        mutation_kind="artifact-update",
        scope=str(scope.get("scope") or "artifact"),
        session_key=proposal["session_key"],
        expected_revision=int(proposal["base_revision"]),
        base_state=canonical,
        plan_builder=lambda latest_state: RuntimeMutationPlan(
            stage_snapshots=[],
            sessions=[],
            records=[],
            artifacts=[
                {
                    "artifact_id": str(item.get("artifact_id") or item.get("path")),
                    "stage": item.get("stage") or stage,
                    "path": str(item["path"]),
                    "content": str(item["content"]),
                    "updated_at": str(item.get("updated_at") or now_iso()),
                }
                for item in artifacts
            ],
            response_payload={"artifacts_written": len(artifacts)},
        ),
        conflict_detector=lambda base, current: {
            "kind": "artifact-update",
            "scope": str(scope.get("scope") or "artifact"),
            "details": {"reason": "artifact_update requires a fresh base revision"},
        }
        if current.runtime_revision != base.runtime_revision
        else None,
        lease=None,
    )
    if not projection_meta.get("accepted", True):
        return projection_meta
    return {"accepted": True, **projection_meta}
