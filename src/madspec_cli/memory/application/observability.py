from __future__ import annotations
from pathlib import Path
from typing import Any

from ..shared.storage import get_memory_paths, read_json, read_jsonl
from ..shared.system_store.canonical_state import load_canonical_branch_state
from ..shared.system_store.constants import SYSTEM_SESSION_KEY
from ..shared.system_store.store import MemoryStore
from ..shared.validation import validate_branch_memory
from ..shared.validation_views import validate_generated_stage_views

_SNAPSHOT_KEY_TO_PATH = {
    "progress": "progress",
    "mvp.concept": "concept_state",
    "mvp.design": "design_state",
    "mvp.tech": "tech_state",
    "mvp.architecture": "architecture_state",
    "mvp.plan": "plan_state",
    "feature.init": "feature_init_state",
    "feature.plan": "feature_plan_state",
}

_STREAM_TO_PATH = {
    "decision_log": "decision_log",
    "events": "events",
    "facts": "facts",
    "decisions": "decisions",
    "contracts": "contracts",
}


def build_runtime_observability(
    project_path: Path,
    *,
    branch_name: str,
    session_key: str = SYSTEM_SESSION_KEY,
    stage: str | None = None,
    step_id: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    store = MemoryStore(project_path)
    canonical = load_canonical_branch_state(project_path, branch_name)
    branch_state = store.fetch_branch_runtime_state(branch_name)
    sessions = store.list_sessions(branch=branch_name)
    coordination = store.fetch_session_coordination(branch=branch_name, session_key=session_key)

    projection_health = _projection_health(
        project_path,
        branch_name=branch_name,
        canonical=canonical,
        sessions=sessions,
    )
    active_leases = _lease_state(store, branch_name=branch_name)
    proposal_state = _proposal_state(
        store,
        branch_name=branch_name,
        session_key=session_key,
        work_item_id=((coordination.get("work_item") or {}).get("work_item_id")),
        limit=limit,
    )
    conflict_state = _conflict_state(
        project_path,
        branch_name=branch_name,
        store=store,
        proposal_state=proposal_state,
        projection_health=projection_health,
        limit=limit,
    )
    orphan_sessions = _orphan_sessions(
        store,
        branch_name=branch_name,
        sessions=sessions,
    )
    current_session = _current_session_state(
        session_key=session_key,
        coordination=coordination,
        sessions=sessions,
    )
    shared_branch_state = {
        "branch": branch_name,
        "runtime_revision": canonical.runtime_revision,
        "runtime_updated_at": branch_state.get("updated_at"),
        "current_implement_step": canonical.progress.get("currentImplementStep"),
        "planned_steps_count": len(canonical.progress.get("plannedSteps", [])),
        "completed_steps_count": len(canonical.progress.get("completedSteps", [])),
        "snapshot_updated_at": {
            item["snapshot_key"]: item["updated_at"]
            for item in store.list_stage_snapshots(branch=branch_name, limit=32)
        },
        "projection_health": {
            "status": projection_health["status"],
            "stale_projection_count": len(projection_health["stale_projections"]),
            "revision_drift_count": len(projection_health["revision_drift"]),
        },
    }
    return {
        "shared_branch_state": shared_branch_state,
        "current_session_state": current_session,
        "active_leases": active_leases,
        "proposal_state": proposal_state,
        "conflict_state": conflict_state,
        "ownership_state": {
            "task": coordination.get("task"),
            "work_item": coordination.get("work_item"),
            "claim": coordination.get("claim"),
            "coordinator": coordination.get("coordinator"),
        },
        "projection_health": projection_health,
        "orphan_sessions": orphan_sessions,
        "summary": {
            "stage": stage,
            "step_id": step_id,
            "session_key": session_key,
            "has_active_claim": current_session["claim"] is not None,
            "active_lease_count": active_leases["active_count"],
            "stuck_lease_count": active_leases["stuck_count"],
            "pending_proposal_count": proposal_state["pending_count"],
            "unresolved_proposal_conflict_count": proposal_state["conflict_count"],
            "conflict_count": conflict_state["summary"]["total_conflicts"],
            "projection_status": projection_health["status"],
        },
    }


def _current_session_state(
    *,
    session_key: str,
    coordination: dict[str, Any],
    sessions: list[dict[str, Any]],
) -> dict[str, Any]:
    session_row = next((item for item in sessions if item["session_key"] == session_key), None)
    payload = dict((session_row or {}).get("payload") or {})
    return {
        "session_key": session_key,
        "updated_at": (session_row or {}).get("updated_at"),
        "payload": payload,
        "binding": coordination.get("session_binding"),
        "claim": coordination.get("claim"),
        "ownership": ((coordination.get("coordinator") or {}).get("ownership_state")),
        "readiness": ((coordination.get("coordinator") or {}).get("readiness")),
        "dependency_state": ((coordination.get("coordinator") or {}).get("dependency_state")),
        "scheduler_hints": ((coordination.get("coordinator") or {}).get("scheduler_hints")),
    }


def _lease_state(store: MemoryStore, *, branch_name: str) -> dict[str, Any]:
    leases = []
    for lease in store.list_writer_leases():
        if not _lease_matches_branch(lease.get("lease_name"), branch_name):
            continue
        stuck = bool(lease.get("expired")) or not _valid_lease_owner(lease.get("owner_id"))
        leases.append(
            {
                **lease,
                "scope": _lease_scope(lease.get("lease_name")),
                "affected_branch": branch_name,
                "stuck": stuck,
            }
        )
    active = [item for item in leases if not item.get("expired")]
    stuck = [item for item in leases if item.get("stuck")]
    return {
        "leases": leases,
        "active": active,
        "stuck": stuck,
        "active_count": len(active),
        "stuck_count": len(stuck),
    }


def _proposal_state(
    store: MemoryStore,
    *,
    branch_name: str,
    session_key: str,
    work_item_id: str | None,
    limit: int,
) -> dict[str, Any]:
    recent = store.list_runtime_proposals(branch=branch_name, limit=max(limit * 4, 20))
    session_recent = [item for item in recent if item.get("session_key") == session_key][:limit]
    work_item_recent = [item for item in recent if work_item_id and item.get("work_item_id") == work_item_id][:limit]
    unresolved = [item for item in recent if item.get("status") in {"pending", "conflict"}]
    latest = recent[0] if recent else None
    return {
        "recent": recent[:limit],
        "session_recent": session_recent,
        "work_item_recent": work_item_recent,
        "pending_count": len([item for item in recent if item.get("status") == "pending"]),
        "conflict_count": len([item for item in recent if item.get("status") == "conflict"]),
        "unresolved": unresolved[:limit],
        "latest": latest,
    }


def _conflict_state(
    project_path: Path,
    *,
    branch_name: str,
    store: MemoryStore,
    proposal_state: dict[str, Any],
    projection_health: dict[str, Any],
    limit: int,
) -> dict[str, Any]:
    record_conflicts = [
        _conflict_entry(
            kind="record_conflict",
            scope=item.get("scope") or "branch",
            summary=item.get("summary"),
            related_ids={"record_id": item.get("record_id"), "step_id": item.get("step_id")},
            probable_cause="Canonical record was marked as conflicted during runtime merge or validation.",
            repair_hint="Inspect the conflicted record, refresh runtime context, and resolve or replace the conflicting write.",
            status=item.get("status"),
        )
        for item in store.list_records(branch=branch_name, statuses=["conflicted"], limit=limit)
    ]
    proposal_conflicts = [
        _conflict_entry(
            kind="proposal_conflict",
            scope=((item.get("target_scope") or {}).get("scope") or "work-item"),
            summary=f"Proposal {item['proposal_id']} is {item['status']}",
            related_ids={
                "proposal_id": item.get("proposal_id"),
                "work_item_id": item.get("work_item_id"),
                "task_id": item.get("task_id"),
            },
            probable_cause=_proposal_conflict_cause(item),
            repair_hint="Review proposal preview, then publish a fresh proposal or resolve the conflicting ownership/runtime state.",
            status=item.get("status"),
        )
        for item in proposal_state["unresolved"][:limit]
    ]
    integrity_conflicts = [
        _conflict_entry(
            kind="integrity_conflict",
            scope="branch",
            summary=message,
            related_ids={},
            probable_cause="Branch memory projection or canonical stream is out of sync with expected invariants.",
            repair_hint="Run memory consolidate or inspect the affected projection file and rebuild it from canonical SQLite state.",
            status="error",
        )
        for message in validate_branch_memory(project_path, branch_name)[:limit]
    ]
    projection_conflicts = [
        _conflict_entry(
            kind="projection_conflict",
            scope="projection",
            summary=item["summary"],
            related_ids={"path": item.get("path")},
            probable_cause=item["probable_cause"],
            repair_hint=item["repair_hint"],
            status="error",
        )
        for item in projection_health["stale_projections"][:limit]
    ]
    coordinator_conflicts = []
    for issue in projection_health.get("coordinator_conflicts", [])[:limit]:
        coordinator_conflicts.append(
            _conflict_entry(
                kind=issue["kind"],
                scope="work-item",
                summary=issue["summary"],
                related_ids=issue.get("related_ids") or {},
                probable_cause=issue["probable_cause"],
                repair_hint=issue["repair_hint"],
                status=issue.get("status") or "error",
            )
        )
    all_conflicts = [
        *record_conflicts,
        *proposal_conflicts,
        *integrity_conflicts,
        *projection_conflicts,
        *coordinator_conflicts,
    ]
    return {
        "record_conflicts": record_conflicts,
        "proposal_conflicts": proposal_conflicts,
        "integrity_conflicts": integrity_conflicts,
        "projection_conflicts": projection_conflicts,
        "coordinator_conflicts": coordinator_conflicts,
        "summary": {
            "total_conflicts": len(all_conflicts),
            "record_conflicts": len(record_conflicts),
            "proposal_conflicts": len(proposal_conflicts),
            "integrity_conflicts": len(integrity_conflicts),
            "projection_conflicts": len(projection_conflicts),
            "coordinator_conflicts": len(coordinator_conflicts),
        },
    }


def _projection_health(
    project_path: Path,
    *,
    branch_name: str,
    canonical: Any,
    sessions: list[dict[str, Any]],
) -> dict[str, Any]:
    paths = get_memory_paths(project_path, branch_name)
    stale_projections: list[dict[str, Any]] = []
    revision_drift: list[dict[str, Any]] = []

    for snapshot_key, path_attr in _SNAPSHOT_KEY_TO_PATH.items():
        path = getattr(paths, path_attr)
        expected = canonical.snapshots.get(snapshot_key)
        if expected is None:
            continue
        actual = read_json(path, None)
        if actual != expected:
            stale_projections.append(
                {
                    "kind": "snapshot_projection_drift",
                    "path": str(path.relative_to(project_path)),
                    "summary": f"{snapshot_key} projection is stale",
                    "probable_cause": "Branch file projection no longer matches canonical SQLite snapshot state.",
                    "repair_hint": "Rebuild branch projections from canonical SQLite state with memory consolidate.",
                }
            )
            revision_drift.append(
                {
                    "path": str(path.relative_to(project_path)),
                    "summary": f"{snapshot_key} file projection does not reflect runtime revision {canonical.runtime_revision}",
                }
            )

    active_session = next((item for item in sessions if item["session_key"] == SYSTEM_SESSION_KEY), None)
    if read_json(paths.active_session, None) != (active_session or {}).get("payload", canonical.active_session):
        stale_projections.append(
            {
                "kind": "session_projection_drift",
                "path": str(paths.active_session.relative_to(project_path)),
                "summary": "Active session projection is stale",
                "probable_cause": "working/active-session.json does not reflect the canonical active session payload.",
                "repair_hint": "Refresh branch projections so the active session file is rebuilt from SQLite.",
            }
        )
        revision_drift.append(
            {
                "path": str(paths.active_session.relative_to(project_path)),
                "summary": f"Active session file projection does not reflect runtime revision {canonical.runtime_revision}",
            }
        )

    for stream_name, path_attr in _STREAM_TO_PATH.items():
        path = getattr(paths, path_attr)
        actual = read_jsonl(path)
        expected = canonical.record_streams.get(stream_name, [])
        if actual != expected:
            stale_projections.append(
                {
                    "kind": "record_stream_drift",
                    "path": str(path.relative_to(project_path)),
                    "summary": f"{stream_name} projection is stale",
                    "probable_cause": "Branch record stream projection no longer matches the canonical record stream.",
                    "repair_hint": "Rebuild branch memory projections from SQLite to restore the canonical record stream view.",
                }
            )

    generated_view_errors = validate_generated_stage_views(
        paths,
        project_path=project_path,
        branch_name=branch_name,
    )
    for message in generated_view_errors:
        stale_projections.append(
            {
                "kind": "generated_view_drift",
                "path": _path_from_validation_message(message),
                "summary": message,
                "probable_cause": "Generated markdown view is stale relative to canonical runtime state.",
                "repair_hint": "Run memory consolidate or regenerate the affected markdown view from SQLite projections.",
            }
        )

    coordinator_conflicts = _coordinator_conflict_entries(project_path, branch_name)
    status = "ok"
    if stale_projections:
        status = "error"
    elif revision_drift:
        status = "warn"
    return {
        "status": status,
        "stale_projections": stale_projections,
        "revision_drift": revision_drift,
        "generated_view_errors": generated_view_errors,
        "coordinator_conflicts": coordinator_conflicts,
    }


def _coordinator_conflict_entries(project_path: Path, branch_name: str) -> list[dict[str, Any]]:
    store = MemoryStore(project_path)
    work_items = store.list_work_items(branch=branch_name)
    work_items_by_id = {item["work_item_id"]: item for item in work_items}
    issues: list[dict[str, Any]] = []
    for edge in store.list_work_item_dependencies(branch=branch_name):
        if edge["work_item_id"] in work_items_by_id and edge["depends_on_work_item_id"] in work_items_by_id:
            continue
        issues.append(
            {
                "kind": "coordinator_dependency_conflict",
                "summary": f"Dangling dependency {edge['work_item_id']} -> {edge['depends_on_work_item_id']}",
                "related_ids": {
                    "work_item_id": edge["work_item_id"],
                    "depends_on_work_item_id": edge["depends_on_work_item_id"],
                },
                "probable_cause": "Coordinator dependency graph references a missing work item.",
                "repair_hint": "Repair or recreate the missing dependency target so coordinator readiness can be recomputed.",
                "status": "error",
            }
        )
    for item in work_items:
        claim = store.fetch_active_claim_for_work_item(work_item_id=item["work_item_id"])
        if claim is None:
            continue
        if item.get("session_key") == claim.get("session_key") and item.get("owner_id") == claim.get("owner_id"):
            continue
        issues.append(
            {
                "kind": "ownership_conflict",
                "summary": f"Claim for work item {item['work_item_id']} does not match work item ownership fields",
                "related_ids": {
                    "work_item_id": item["work_item_id"],
                    "claim_session_key": claim.get("session_key"),
                    "work_item_session_key": item.get("session_key"),
                },
                "probable_cause": "Coordinator claim and persisted work-item ownership diverged.",
                "repair_hint": "Release the stale claim or repair the work-item ownership binding so both sources agree.",
                "status": "error",
            }
        )
    return issues


def _orphan_sessions(
    store: MemoryStore,
    *,
    branch_name: str,
    sessions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in sessions:
        payload = dict(row.get("payload") or {})
        binding = {
            "task_id": payload.get("task_id"),
            "work_item_id": payload.get("work_item_id"),
            "subagent_id": payload.get("subagent_id"),
        }
        if not any(binding.values()):
            continue
        task = store.fetch_task(binding["task_id"]) if binding["task_id"] else None
        work_item = store.fetch_work_item(binding["work_item_id"]) if binding["work_item_id"] else None
        claim = store.fetch_active_claim_for_session(branch=branch_name, session_key=row["session_key"])
        problems = []
        if binding["task_id"] and task is None:
            problems.append("missing_task")
        if binding["work_item_id"] and work_item is None:
            problems.append("missing_work_item")
        if binding["work_item_id"] and claim is None:
            problems.append("binding_without_claim")
        if claim is not None and binding["work_item_id"] and claim.get("work_item_id") != binding["work_item_id"]:
            problems.append("claim_binding_mismatch")
        if problems:
            items.append(
                {
                    "session_key": row["session_key"],
                    "binding": binding,
                    "problems": problems,
                    "probable_cause": "Session-local binding refers to coordinator state that no longer exists or no longer matches the active claim.",
                    "repair_hint": "Reclaim the work item or clear the stale session binding before continuing shared work.",
                }
            )
    return items


def _conflict_entry(
    *,
    kind: str,
    scope: str,
    summary: str | None,
    related_ids: dict[str, Any],
    probable_cause: str,
    repair_hint: str,
    status: str | None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "scope": scope,
        "summary": summary,
        "related_ids": related_ids,
        "probable_cause": probable_cause,
        "repair_hint": repair_hint,
        "status": status,
    }


def _proposal_conflict_cause(proposal: dict[str, Any]) -> str:
    apply_summary = proposal.get("apply_summary") or {}
    reason = apply_summary.get("reason")
    if reason == "stale_revision":
        return "Proposal was published against an outdated runtime revision."
    if reason == "ownership_violation":
        return "Proposal owner no longer matches the active coordinator ownership binding."
    if reason == "readiness_blocked":
        return "Proposal targets a work item whose coordinator readiness is blocked."
    return "Proposal could not be applied cleanly in the current runtime state."


def _lease_matches_branch(lease_name: str | None, branch_name: str) -> bool:
    return bool(lease_name and lease_name.endswith(f":{branch_name}"))


def _lease_scope(lease_name: str | None) -> str:
    name = str(lease_name or "")
    return name.split(":", 1)[0] if ":" in name else name or "runtime"


def _valid_lease_owner(owner_id: Any) -> bool:
    value = str(owner_id or "")
    return value.startswith("runtime:") or value.startswith("work-item:")


def _path_from_validation_message(message: str) -> str | None:
    if "'" not in message:
        return None
    parts = message.split("'")
    if len(parts) < 2:
        return None
    return parts[1]
