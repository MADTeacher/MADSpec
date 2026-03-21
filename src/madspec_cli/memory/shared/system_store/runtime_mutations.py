from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..storage import normalize_runtime_progress
from .canonical_state import CanonicalBranchState, refresh_branch_projections
from .layout import ensure_system_memory_layout
from .sessions import normalize_session_payload
from .store import MemoryStore


@dataclass(frozen=True)
class RuntimeMutationPlan:
    stage_snapshots: list[dict[str, Any]]
    sessions: list[dict[str, Any]]
    records: list[dict[str, Any]]
    response_payload: dict[str, Any] = field(default_factory=dict)


def commit_runtime_mutation(
    project_path: Path,
    *,
    branch_name: str,
    stage: str | None,
    mutation_kind: str,
    scope: str,
    session_key: str | None,
    expected_revision: int,
    base_state: CanonicalBranchState,
    plan_builder: Callable[[CanonicalBranchState], RuntimeMutationPlan],
    conflict_detector: Callable[[CanonicalBranchState, CanonicalBranchState], dict[str, Any] | None],
    full: bool = False,
) -> dict[str, Any]:
    from .canonical_state import bootstrap_branch_canonical_state, load_canonical_branch_state

    ensure_system_memory_layout(project_path)
    bootstrap_branch_canonical_state(project_path, branch_name)
    store = MemoryStore(project_path)

    with store.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        current_revision = store.fetch_branch_revision(branch_name, conn=conn)
        current_state = base_state
        if current_revision != base_state.runtime_revision:
            current_state = load_canonical_branch_state(project_path, branch_name)

        if current_revision != expected_revision:
            conflict = conflict_detector(base_state, current_state)
            if conflict is not None:
                return _build_conflict_payload(
                    mutation_kind=mutation_kind,
                    scope=scope,
                    expected_revision=expected_revision,
                    actual_revision=current_revision,
                    conflict=conflict,
                )

        plan = plan_builder(current_state)
        normalized_plan = _normalize_runtime_mutation_plan(
            project_path,
            branch_name,
            plan,
        )
        branch_revision_after = current_revision + 1
        store.commit_runtime_mutation(
            branch=branch_name,
            stage_snapshots=normalized_plan.stage_snapshots,
            sessions=normalized_plan.sessions,
            records=normalized_plan.records,
            branch_revision_after=branch_revision_after,
            conn=conn,
        )

    generated_views: list[str] = []
    warnings: list[str] = []
    projection_status = "synced"
    projection_refresh_required = False
    try:
        _, generated_paths = refresh_branch_projections(
            project_path,
            branch_name,
            stage=stage,
            full=full,
        )
        generated_views = [str(path.relative_to(project_path)) for path in generated_paths]
        from ..validation import validate_branch_memory

        validation_errors = validate_branch_memory(project_path, branch_name, stage=stage)
        if validation_errors:
            raise ValueError("; ".join(validation_errors))
    except Exception as exc:
        projection_status = "stale"
        projection_refresh_required = True
        warnings.append(f"projection refresh failed: {exc}")

    return {
        **normalized_plan.response_payload,
        "generated_views": generated_views,
        "projection_status": projection_status,
        "projection_refresh_required": projection_refresh_required,
        "warnings": warnings,
        "runtime_revision_before": current_revision,
        "runtime_revision_after": branch_revision_after,
    }


def _normalize_runtime_mutation_plan(
    project_path: Path,
    branch_name: str,
    plan: RuntimeMutationPlan,
) -> RuntimeMutationPlan:
    snapshots: list[dict[str, Any]] = []
    for snapshot in plan.stage_snapshots:
        snapshot_key = str(snapshot["snapshot_key"])
        payload = dict(snapshot["payload"])
        if snapshot_key == "progress":
            payload, _ = normalize_runtime_progress(
                project_path,
                branch_name,
                payload,
            )
        snapshots.append(
            {
                "snapshot_key": snapshot_key,
                "payload": payload,
                "source_path": str(snapshot["source_path"]),
            }
        )

    sessions: list[dict[str, Any]] = []
    for item in plan.sessions:
        resolved_session_key = str(item["session_key"])
        payload = normalize_session_payload(
            dict(item["payload"]),
            branch_name=branch_name,
            session_key=resolved_session_key,
        )
        sessions.append(
            {
                "session_key": resolved_session_key,
                "payload": payload,
            }
        )

    return RuntimeMutationPlan(
        stage_snapshots=snapshots,
        sessions=sessions,
        records=[dict(record) for record in plan.records],
        response_payload=dict(plan.response_payload),
    )


def _build_conflict_payload(
    *,
    mutation_kind: str,
    scope: str,
    expected_revision: int,
    actual_revision: int,
    conflict: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "accepted": False,
        "kind": "conflict",
        "conflict": {
            "kind": conflict.get("kind") or mutation_kind,
            "scope": conflict.get("scope") or scope,
            "expected_revision": expected_revision,
            "actual_revision": actual_revision,
            "retry_guidance": conflict.get("retry_guidance")
            or "Refresh runtime context to get the latest runtime_revision, then retry the command.",
        },
    }
    if conflict.get("step_id") is not None:
        payload["conflict"]["step_id"] = conflict["step_id"]
    if conflict.get("conflicting_fields"):
        payload["conflict"]["conflicting_fields"] = list(conflict["conflicting_fields"])
    if conflict.get("details"):
        payload["conflict"]["details"] = conflict["details"]
    return payload
