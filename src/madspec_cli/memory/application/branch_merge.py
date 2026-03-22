from __future__ import annotations

import copy
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from madspec_cli.shared.kernel.ports import BranchPolicyEvaluator

from madspec_cli.memory.domain.conflicts import (
    PROJECT_MEMORY_BRANCH,
    normalize_semantic_metadata,
    project_record_id,
    resolution_allowed,
    semantic_fingerprint,
)
from madspec_cli.memory.shared.storage import (
    _default_active_session,
    get_memory_paths,
    now_iso,
    read_json,
    read_jsonl,
    write_json,
)
from madspec_cli.memory.shared.system_store.store import MemoryStore
from madspec_cli.memory.shared.system_store.sync import sync_branch_memory_to_store
from madspec_cli.memory.semantic.shared import append_unique
from madspec_cli.shared.kernel.result import PayloadResult

from ..projection.materialize import consolidate_branch_memory
from ..shared.storage import ensure_memory_layout
from ..shared.validation import validate_branch_memory

from .branch_compare import (
    SEMANTIC_KIND_PATHS,
    compare_branch_memory,
    load_branch_memory_state,
    resolve_base_branch,
)


@dataclass(frozen=True)
class ProposeBranchMergeRequest:
    project_path: Path
    source_branch: str
    target_branch: str
    base_branch: str | None
    requested_by: str


@dataclass(frozen=True)
class PreviewBranchMergeRequest:
    project_path: Path
    proposal_id: str


@dataclass(frozen=True)
class ResolveBranchConflictRequest:
    project_path: Path
    proposal_id: str
    conflict_id: str
    resolution: str


@dataclass(frozen=True)
class MergeBranchesRequest:
    project_path: Path
    proposal_id: str


@dataclass(frozen=True)
class PromoteBranchKnowledgeRequest:
    project_path: Path
    source_branch: str
    record_ids: list[str]


@dataclass(frozen=True)
class BranchMergeResult(PayloadResult):
    pass


def propose_merge(request: ProposeBranchMergeRequest) -> BranchMergeResult:
    store = MemoryStore(request.project_path)
    base_branch = resolve_base_branch(
        request.project_path,
        source_branch=request.source_branch,
        target_branch=request.target_branch,
        explicit_base_branch=request.base_branch,
    )
    compare_payload = compare_branch_memory(
        request.project_path,
        source_branch=request.source_branch,
        target_branch=request.target_branch,
        base_branch=base_branch,
    )
    ts = now_iso()
    proposal = {
        "proposalId": str(uuid.uuid4()),
        "status": "pending",
        "sourceBranch": request.source_branch,
        "targetBranch": request.target_branch,
        "baseBranch": base_branch,
        "createdAt": ts,
        "updatedAt": ts,
        "requestedBy": request.requested_by,
        "summary": f"Merge memory from {request.source_branch} into {request.target_branch}",
        "compare": compare_payload,
        "autoActions": compare_payload["autoActions"],
        "conflicts": compare_payload["conflicts"],
        "warnings": compare_payload["warnings"],
        "appliedAt": None,
    }
    store.upsert_merge_proposal(proposal)
    store.append_merge_history(
        {
            "eventId": str(uuid.uuid4()),
            "proposalId": proposal["proposalId"],
            "sourceBranch": request.source_branch,
            "targetBranch": request.target_branch,
            "eventType": "merge_proposed",
            "summary": proposal["summary"],
            "payload": {
                "autoActionCount": len(proposal["autoActions"]),
                "conflictCount": len(proposal["conflicts"]),
            },
            "ts": ts,
        }
    )
    return BranchMergeResult(payload=_preview_payload(proposal))


def preview_merge(request: PreviewBranchMergeRequest) -> BranchMergeResult:
    proposal = _require_proposal(request.project_path, request.proposal_id)
    return BranchMergeResult(payload=_preview_payload(proposal))


def resolve_conflict(request: ResolveBranchConflictRequest) -> BranchMergeResult:
    store = MemoryStore(request.project_path)
    proposal = _require_proposal(request.project_path, request.proposal_id)
    updated = False
    for item in proposal.get("conflicts", []):
        if item.get("conflictId") != request.conflict_id:
            continue
        allowed = list(item.get("allowedResolutions", []))
        if not resolution_allowed(request.resolution, allowed=allowed):
            raise ValueError(
                f"resolution '{request.resolution}' is not allowed for conflict '{request.conflict_id}'"
            )
        item["resolution"] = request.resolution
        updated = True
        break
    if not updated:
        raise ValueError(f"conflict '{request.conflict_id}' was not found")

    proposal["updatedAt"] = now_iso()
    store.upsert_merge_proposal(proposal)
    store.append_merge_history(
        {
            "eventId": str(uuid.uuid4()),
            "proposalId": proposal["proposalId"],
            "sourceBranch": proposal["sourceBranch"],
            "targetBranch": proposal["targetBranch"],
            "eventType": "merge_conflict_resolved",
            "summary": f"Resolved conflict {request.conflict_id}",
            "payload": {
                "conflictId": request.conflict_id,
                "resolution": request.resolution,
            },
            "ts": proposal["updatedAt"],
        }
    )
    return BranchMergeResult(payload=_preview_payload(proposal))


def merge_branches(
    request: MergeBranchesRequest,
    *,
    _evaluate_branch_policies: BranchPolicyEvaluator | None = None,
) -> BranchMergeResult:
    if _evaluate_branch_policies is None:
        from madspec_cli.features.policy.application.common import evaluate_branch_policies
        _evaluate_branch_policies = evaluate_branch_policies
    store = MemoryStore(request.project_path)
    proposal = _require_proposal(request.project_path, request.proposal_id)
    unresolved = [item for item in proposal.get("conflicts", []) if item.get("blocking") and not item.get("resolution")]
    if unresolved:
        return BranchMergeResult(
            payload={
                "applied": False,
                "proposalId": proposal["proposalId"],
                "sourceBranch": proposal["sourceBranch"],
                "targetBranch": proposal["targetBranch"],
                "error": "merge proposal still has unresolved blocking conflicts",
                "unresolvedConflicts": [item["conflictId"] for item in unresolved],
            }
        )

    target_branch = proposal["targetBranch"]
    ensure_memory_layout(request.project_path, target_branch)
    paths = get_memory_paths(request.project_path, target_branch)
    original_files = _snapshot_target_files(paths)
    try:
        applied_payload = _apply_proposal(request.project_path, proposal)
    except Exception:
        _restore_target_files(original_files)
        store.purge_branch(target_branch, include_artifacts=True)
        sync_branch_memory_to_store(request.project_path, target_branch)
        consolidate_branch_memory(request.project_path, target_branch)
        raise

    merge_policy_payload = _evaluate_branch_policies(
        request.project_path,
        target_branch,
        stage=None,
        operation="validate",
        include_system_policies=False,
        create_policy_if_missing=False,
    )
    validation_errors = validate_branch_memory(
        request.project_path, target_branch,
        policy_violations=merge_policy_payload["violations"],
    )
    if validation_errors:
        _restore_target_files(original_files)
        store.purge_branch(target_branch, include_artifacts=True)
        sync_branch_memory_to_store(request.project_path, target_branch)
        consolidate_branch_memory(request.project_path, target_branch)
        return BranchMergeResult(
            payload={
                "applied": False,
                "proposalId": proposal["proposalId"],
                "sourceBranch": proposal["sourceBranch"],
                "targetBranch": proposal["targetBranch"],
                "error": "merged memory failed validation and was rolled back",
                "validation": {"valid": False, "errors": validation_errors},
            }
        )

    revision = store.count_merge_events(target_branch=target_branch, event_type="merge_applied") + 1
    ts = now_iso()
    proposal["status"] = "applied"
    proposal["appliedAt"] = ts
    proposal["updatedAt"] = ts
    store.upsert_merge_proposal(proposal)
    store.append_merge_history(
        {
            "eventId": str(uuid.uuid4()),
            "proposalId": proposal["proposalId"],
            "sourceBranch": proposal["sourceBranch"],
            "targetBranch": proposal["targetBranch"],
            "eventType": "merge_applied",
            "summary": proposal["summary"],
            "payload": {
                "revision": revision,
                "autoActionCount": len(proposal.get("autoActions", [])),
                "conflictCount": len(proposal.get("conflicts", [])),
            },
            "ts": ts,
        }
    )
    return BranchMergeResult(
        payload={
            "applied": True,
            "proposalId": proposal["proposalId"],
            "sourceBranch": proposal["sourceBranch"],
            "targetBranch": proposal["targetBranch"],
            "revision": revision,
            "generated_artifacts": applied_payload["generated_artifacts"],
            "validation": {"valid": True, "errors": []},
        }
    )


def promote_branch_knowledge(request: PromoteBranchKnowledgeRequest) -> BranchMergeResult:
    store = MemoryStore(request.project_path)
    source_state = load_branch_memory_state(request.project_path, request.source_branch)
    source_records = _flatten_semantic_records(source_state)
    record_filter = set(request.record_ids)
    selected = [
        item["record"]
        for item in source_records
        if not record_filter or str(item["record"].get("id")) in record_filter
    ]
    existing_project = {
        record.get("record", {}).get("id"): record.get("record", {})
        for record in [
            {"record": item["payload"]}
            for item in store.list_records(branch=PROJECT_MEMORY_BRANCH, statuses=["validated"], limit=10000)
        ]
    }
    existing_fingerprints = {
        semantic_fingerprint(record): record
        for record in existing_project.values()
        if isinstance(record, dict)
    }

    promoted: list[dict[str, Any]] = []
    skipped: list[str] = []
    ts = now_iso()
    for record in selected:
        fingerprint = semantic_fingerprint(record)
        project_record = _make_project_record(record, source_branch=request.source_branch, promotion_ts=ts)
        existing = existing_fingerprints.get(fingerprint)
        if existing is not None and normalize_semantic_metadata(existing.get("metadata") or {}) == normalize_semantic_metadata(project_record.get("metadata") or {}) and existing.get("summary") == project_record.get("summary") and existing.get("evidence") == project_record.get("evidence"):
            skipped.append(str(record.get("id")))
            continue
        store.upsert_record(project_record)
        existing_fingerprints[fingerprint] = project_record
        promoted.append(
            {
                "recordId": project_record["id"],
                "originRecordId": record.get("id"),
                "semanticKind": project_record.get("semantic_kind"),
                "summary": project_record.get("summary"),
                "fingerprint": fingerprint,
            }
        )

    store.append_merge_history(
        {
            "eventId": str(uuid.uuid4()),
            "proposalId": None,
            "sourceBranch": request.source_branch,
            "targetBranch": PROJECT_MEMORY_BRANCH,
            "eventType": "knowledge_promoted",
            "summary": f"Promoted branch knowledge from {request.source_branch}",
            "payload": {"promotedCount": len(promoted), "skippedCount": len(skipped)},
            "ts": ts,
        }
    )
    return BranchMergeResult(
        payload={
            "sourceBranch": request.source_branch,
            "targetBranch": PROJECT_MEMORY_BRANCH,
            "promoted": promoted,
            "skippedRecordIds": skipped,
        }
    )


def _apply_proposal(project_path: Path, proposal: dict[str, Any]) -> dict[str, Any]:
    source_branch = proposal["sourceBranch"]
    target_branch = proposal["targetBranch"]
    base_branch = proposal.get("baseBranch")
    source_state = load_branch_memory_state(project_path, source_branch)
    target_state = load_branch_memory_state(project_path, target_branch)
    base_state = load_branch_memory_state(project_path, base_branch) if base_branch else None
    paths = get_memory_paths(project_path, target_branch)

    merged_progress = copy.deepcopy(target_state["progress"])
    merged_snapshots = {
        stage_name: copy.deepcopy(item.get("payload") or {})
        for stage_name, item in target_state["stage_snapshots"].items()
    }
    semantic_replacements: dict[str, dict[str, dict[str, Any]]] = {
        semantic_kind: {}
        for semantic_kind in SEMANTIC_KIND_PATHS
    }
    operations = [*proposal.get("autoActions", []), *proposal.get("conflicts", [])]
    for item in operations:
        resolution = item.get("operation") or item.get("resolution") or "keep_target"
        if resolution == "keep_target":
            continue
        section = item.get("section")
        if section == "stageSnapshots":
            chosen = _select_snapshot_payload(item, source_state, base_state, resolution=resolution)
            if chosen is not None:
                merged_snapshots[str(item["subject"])] = chosen
            continue
        if section == "progress":
            if item.get("subject") == "currentImplementStep":
                merged_progress["currentImplementStep"] = _select_current_step_value(
                    item,
                    source_state,
                    target_state,
                    base_state,
                    resolution=resolution,
                )
            else:
                step_id = str(item["subject"])
                merged_step = _select_progress_step_state(
                    item,
                    step_id=step_id,
                    source_state=source_state,
                    target_state=target_state,
                    base_state=base_state,
                    resolution=resolution,
                )
                if merged_step is not None:
                    _apply_step_state(merged_progress, step_id, merged_step)
            continue
        if section == "semantic":
            semantic_kind = str(item.get("semanticKind") or "")
            fingerprint = str(item["subject"])
            merged_record = _select_semantic_record(
                item,
                semantic_kind=semantic_kind,
                fingerprint=fingerprint,
                source_state=source_state,
                target_state=target_state,
                base_state=base_state,
                target_branch=target_branch,
                proposal_id=str(proposal["proposalId"]),
            )
            if merged_record is not None:
                semantic_replacements[semantic_kind][fingerprint] = merged_record

    _finalize_progress(merged_progress, source_state["progress"], target_state["progress"])
    write_json(paths.progress, merged_progress)

    active_session = read_json(paths.active_session, _default_active_session(target_branch))
    if not isinstance(active_session, dict):
        active_session = _default_active_session(target_branch)
    active_session["branch"] = target_branch
    active_session["current_step"] = merged_progress.get("currentImplementStep")
    active_session["updated_at"] = now_iso()
    write_json(paths.active_session, active_session)

    snapshot_paths = {
        "mvp.concept": paths.concept_state,
        "mvp.design": paths.design_state,
        "mvp.tech": paths.tech_state,
        "deploy": paths.deploy_state,
        "mvp.architecture": paths.architecture_state,
        "mvp.plan": paths.plan_state,
        "feature.init": paths.feature_init_state,
        "feature.plan": paths.feature_plan_state,
    }
    for stage_name, path in snapshot_paths.items():
        write_json(path, merged_snapshots.get(stage_name, {}))

    for semantic_kind, path_attr in SEMANTIC_KIND_PATHS.items():
        path = getattr(paths, path_attr)
        existing_records = read_jsonl(path)
        merged_records = _merge_semantic_file_records(
            existing_records,
            semantic_replacements[semantic_kind],
        )
        _write_jsonl(path, merged_records)

    store = MemoryStore(project_path)
    store.purge_branch(target_branch, include_artifacts=True)
    sync_branch_memory_to_store(project_path, target_branch)
    generated = consolidate_branch_memory(project_path, target_branch)
    return {"generated_artifacts": [str(path.relative_to(project_path)) for path in generated]}


def _preview_payload(proposal: dict[str, Any]) -> dict[str, Any]:
    unresolved = [item["conflictId"] for item in proposal.get("conflicts", []) if item.get("blocking") and not item.get("resolution")]
    return {
        "proposalId": proposal["proposalId"],
        "status": proposal["status"],
        "sourceBranch": proposal["sourceBranch"],
        "targetBranch": proposal["targetBranch"],
        "baseBranch": proposal.get("baseBranch"),
        "summary": proposal.get("summary"),
        "compare": proposal.get("compare"),
        "autoActions": proposal.get("autoActions", []),
        "conflicts": proposal.get("conflicts", []),
        "warnings": proposal.get("warnings", []),
        "canApply": not unresolved,
        "unresolvedConflicts": unresolved,
        "createdAt": proposal.get("createdAt"),
        "updatedAt": proposal.get("updatedAt"),
        "appliedAt": proposal.get("appliedAt"),
    }


def _require_proposal(project_path: Path, proposal_id: str) -> dict[str, Any]:
    proposal = MemoryStore(project_path).fetch_merge_proposal(proposal_id)
    if proposal is None:
        raise ValueError(f"merge proposal '{proposal_id}' was not found")
    return proposal


def _snapshot_target_files(paths) -> dict[Path, str | None]:
    return {
        path: path.read_text(encoding="utf-8") if path.exists() else None
        for path in (
            paths.progress,
            paths.active_session,
            paths.concept_state,
            paths.design_state,
            paths.tech_state,
            paths.deploy_state,
            paths.architecture_state,
            paths.plan_state,
            paths.feature_init_state,
            paths.feature_plan_state,
            paths.facts,
            paths.decisions,
            paths.contracts,
        )
    }


def _restore_target_files(snapshot: dict[Path, str | None]) -> None:
    for path, content in snapshot.items():
        if content is None:
            if path.exists():
                path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _select_snapshot_payload(
    item: dict[str, Any],
    source_state: dict[str, Any],
    base_state: dict[str, Any] | None,
    *,
    resolution: str,
) -> dict[str, Any] | None:
    stage_name = str(item["subject"])
    if resolution == "take_source":
        return copy.deepcopy(source_state["stage_snapshots"][stage_name]["payload"])
    if resolution == "take_base" and base_state is not None:
        return copy.deepcopy(base_state["stage_snapshots"][stage_name]["payload"])
    return None


def _select_current_step_value(
    item: dict[str, Any],
    source_state: dict[str, Any],
    target_state: dict[str, Any],
    base_state: dict[str, Any] | None,
    *,
    resolution: str,
) -> str | None:
    del item
    if resolution == "take_source":
        return source_state["progress"].get("currentImplementStep")
    if resolution == "take_base" and base_state is not None:
        return base_state["progress"].get("currentImplementStep")
    if resolution == "union":
        return (
            target_state["progress"].get("currentImplementStep")
            or source_state["progress"].get("currentImplementStep")
        )
    return target_state["progress"].get("currentImplementStep")


def _select_progress_step_state(
    item: dict[str, Any],
    *,
    step_id: str,
    source_state: dict[str, Any],
    target_state: dict[str, Any],
    base_state: dict[str, Any] | None,
    resolution: str,
) -> dict[str, Any] | None:
    source_step = item.get("sourceState") or {}
    target_step = item.get("targetState") or {}
    base_step = item.get("baseState") or {}
    if resolution == "take_source":
        return copy.deepcopy(source_step)
    if resolution == "take_base" and base_state is not None:
        return copy.deepcopy(base_step)
    if resolution == "union":
        return _union_progress_step_state(source_step, target_step)
    if resolution == "keep_target":
        return copy.deepcopy(target_step)
    del step_id, source_state, target_state
    return None


def _union_progress_step_state(source_step: dict[str, Any], target_step: dict[str, Any]) -> dict[str, Any]:
    status = dict(target_step.get("status") or {})
    if not status:
        status = dict(source_step.get("status") or {})
    metadata = dict(target_step.get("metadata") or {})
    if not metadata:
        metadata = dict(source_step.get("metadata") or {})
    covers = copy.deepcopy(target_step.get("covers") or {})
    source_covers = source_step.get("covers") or {}
    for priority, values in source_covers.items():
        current = list(covers.get(priority, [])) if isinstance(covers.get(priority), list) else []
        if isinstance(values, list):
            covers[priority] = append_unique(current, [str(item) for item in values if str(item)])
    dependencies = append_unique(
        list(target_step.get("dependencies") or []),
        [str(item) for item in source_step.get("dependencies") or [] if str(item)],
    )
    return {
        "planned": bool(target_step.get("planned") or source_step.get("planned")),
        "completed": bool(target_step.get("completed") or source_step.get("completed")),
        "status": status,
        "metadata": metadata,
        "covers": covers,
        "dependencies": dependencies,
    }


def _apply_step_state(progress: dict[str, Any], step_id: str, step_state: dict[str, Any]) -> None:
    planned_steps = list(progress.get("plannedSteps", []))
    completed_steps = list(progress.get("completedSteps", []))
    if step_state.get("planned"):
        planned_steps = append_unique(planned_steps, [step_id])
    elif step_id in planned_steps:
        planned_steps = [item for item in planned_steps if item != step_id]
    if step_state.get("completed"):
        completed_steps = append_unique(completed_steps, [step_id])
        planned_steps = append_unique(planned_steps, [step_id])
    elif step_id in completed_steps:
        completed_steps = [item for item in completed_steps if item != step_id]

    progress["plannedSteps"] = planned_steps
    progress["completedSteps"] = completed_steps
    progress.setdefault("stepStatus", {})[step_id] = dict(step_state.get("status") or {})
    progress.setdefault("stepMetadata", {})[step_id] = dict(step_state.get("metadata") or {})
    progress.setdefault("coversFunctions", {})[step_id] = copy.deepcopy(step_state.get("covers") or {})
    planning_metadata = progress.setdefault("planningMetadata", {})
    planning_metadata.setdefault("stepDependencies", {})[step_id] = list(step_state.get("dependencies") or [])


def _finalize_progress(progress: dict[str, Any], source_progress: dict[str, Any], target_progress: dict[str, Any]) -> None:
    progress["plannedSteps"] = list(dict.fromkeys(progress.get("plannedSteps", [])))
    progress["completedSteps"] = [
        step_id
        for step_id in dict.fromkeys(progress.get("completedSteps", []))
        if step_id in progress["plannedSteps"]
    ]
    planning_metadata = progress.setdefault("planningMetadata", {})
    planning_metadata["lastPlannedStep"] = progress["plannedSteps"][-1] if progress["plannedSteps"] else None
    planning_metadata["planningPhase"] = (
        source_progress.get("planningMetadata", {}).get("planningPhase")
        or target_progress.get("planningMetadata", {}).get("planningPhase")
        or "initial"
    )
    planning_metadata["totalStepsEstimated"] = max(
        len(progress["plannedSteps"]),
        int(source_progress.get("planningMetadata", {}).get("totalStepsEstimated") or 0),
        int(target_progress.get("planningMetadata", {}).get("totalStepsEstimated") or 0),
    ) or None
    current_step = progress.get("currentImplementStep")
    if current_step and current_step not in progress["plannedSteps"]:
        progress["plannedSteps"] = append_unique(progress["plannedSteps"], [current_step])


def _select_semantic_record(
    item: dict[str, Any],
    *,
    semantic_kind: str,
    fingerprint: str,
    source_state: dict[str, Any],
    target_state: dict[str, Any],
    base_state: dict[str, Any] | None,
    target_branch: str,
    proposal_id: str,
) -> dict[str, Any] | None:
    source_record = (source_state["semantic"].get(semantic_kind) or {}).get(fingerprint, {}).get("record")
    target_record = (target_state["semantic"].get(semantic_kind) or {}).get(fingerprint, {}).get("record")
    base_record = (base_state or {}).get("semantic", {}).get(semantic_kind, {}).get(fingerprint, {}).get("record")
    resolution = item.get("operation") or item.get("resolution") or "keep_target"
    if resolution == "keep_target":
        return None
    if resolution == "take_source":
        return _clone_record_for_target(
            source_record,
            target_record=target_record,
            target_branch=target_branch,
            proposal_id=proposal_id,
            semantic_kind=semantic_kind,
        )
    if resolution == "take_base":
        return _clone_record_for_target(
            base_record,
            target_record=target_record,
            target_branch=target_branch,
            proposal_id=proposal_id,
            semantic_kind=semantic_kind,
        )
    if resolution == "union":
        if source_record is None and target_record is None:
            return None
        if source_record is None:
            return copy.deepcopy(target_record)
        if target_record is None:
            return _clone_record_for_target(
                source_record,
                target_record=None,
                target_branch=target_branch,
                proposal_id=proposal_id,
                semantic_kind=semantic_kind,
            )
        return _union_semantic_record(
            target_record,
            source_record,
            target_branch=target_branch,
            proposal_id=proposal_id,
            semantic_kind=semantic_kind,
        )
    return None


def _clone_record_for_target(
    record: dict[str, Any] | None,
    *,
    target_record: dict[str, Any] | None,
    target_branch: str,
    proposal_id: str,
    semantic_kind: str,
) -> dict[str, Any] | None:
    if record is None:
        return None
    cloned = copy.deepcopy(record)
    cloned["id"] = target_record.get("id") if target_record else str(uuid.uuid4())
    cloned["branch"] = target_branch
    cloned["status"] = "validated"
    cloned["semantic_kind"] = semantic_kind
    cloned.setdefault("metadata", {})
    cloned["metadata"] = {
        **dict(cloned.get("metadata") or {}),
        "mergedFromBranch": record.get("branch"),
        "originRecordId": record.get("id"),
        "mergeProposalId": proposal_id,
    }
    cloned["ts"] = now_iso()
    return cloned


def _union_semantic_record(
    target_record: dict[str, Any],
    source_record: dict[str, Any],
    *,
    target_branch: str,
    proposal_id: str,
    semantic_kind: str,
) -> dict[str, Any]:
    merged = _clone_record_for_target(
        target_record,
        target_record=target_record,
        target_branch=target_branch,
        proposal_id=proposal_id,
        semantic_kind=semantic_kind,
    )
    merged["summary"] = source_record.get("summary") or target_record.get("summary")
    merged["evidence"] = append_unique(
        list(target_record.get("evidence") or []),
        [str(item) for item in source_record.get("evidence") or [] if str(item)],
    )
    merged["metadata"] = _merge_metadata_dicts(
        dict(target_record.get("metadata") or {}),
        dict(source_record.get("metadata") or {}),
    )
    merged["metadata"]["mergedFromBranch"] = source_record.get("branch")
    merged["metadata"]["originRecordId"] = source_record.get("id")
    merged["metadata"]["mergeProposalId"] = proposal_id
    return merged


def _merge_metadata_dicts(target: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(target)
    for key, value in source.items():
        if key not in merged:
            merged[key] = copy.deepcopy(value)
            continue
        if isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _merge_metadata_dicts(merged[key], value)
            continue
        if isinstance(merged[key], list) and isinstance(value, list):
            merged[key] = append_unique(
                [str(item) for item in merged[key] if str(item)],
                [str(item) for item in value if str(item)],
            )
    return merged


def _merge_semantic_file_records(
    existing_records: list[dict[str, Any]],
    replacements: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    emitted: set[str] = set()
    merged_records: list[dict[str, Any]] = []
    for record in existing_records:
        if not isinstance(record, dict):
            continue
        if record.get("status") != "validated" or record.get("semantic_kind") not in {"fact", "decision", "contract"}:
            merged_records.append(record)
            continue
        fingerprint = semantic_fingerprint(record)
        replacement = replacements.get(fingerprint)
        if replacement is None:
            merged_records.append(record)
            continue
        if fingerprint in emitted:
            continue
        merged_records.append(replacement)
        emitted.add(fingerprint)
    for fingerprint, replacement in replacements.items():
        if fingerprint in emitted:
            continue
        merged_records.append(replacement)
    return merged_records


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text(content + ("\n" if content else ""), encoding="utf-8")


def _flatten_semantic_records(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for items in state.get("semantic", {}).values():
        rows.extend(items.values())
    return rows


def _make_project_record(record: dict[str, Any], *, source_branch: str, promotion_ts: str) -> dict[str, Any]:
    project_record = copy.deepcopy(record)
    project_record["id"] = project_record_id(record)
    project_record["branch"] = PROJECT_MEMORY_BRANCH
    project_record["scope"] = "project"
    project_record["source"] = "memory.promote-branch-knowledge"
    project_record["ts"] = promotion_ts
    project_record["metadata"] = {
        **dict(project_record.get("metadata") or {}),
        "sourceBranch": source_branch,
        "originRecordId": record.get("id"),
        "promotionTs": promotion_ts,
        "fingerprint": semantic_fingerprint(record),
    }
    return project_record
