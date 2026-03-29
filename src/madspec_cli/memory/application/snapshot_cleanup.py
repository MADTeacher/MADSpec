from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from madspec_cli.shared.kernel.result import PayloadResult

from .proposal_guard import guard_direct_runtime_write
from ..shared.progress_utils import _compute_progress_metrics
from ..shared.records import make_record
from ..shared.storage import ensure_memory_layout, now_iso
from ..shared.system_store.canonical_state import (
    CanonicalBranchState,
    build_runtime_snapshot_specs,
    load_canonical_branch_state,
    tag_records_for_stream,
)
from ..shared.system_store.constants import SYSTEM_SESSION_KEY
from ..shared.system_store.runtime_mutations import RuntimeMutationPlan, commit_runtime_mutation
from ..stages.architecture.state import (
    architecture_completeness_errors,
    architecture_schema_errors,
    normalize_architecture_state,
)
from ..stages.concept.state import concept_completeness_errors, concept_schema_errors, normalize_concept_state
from ..stages.deploy.state import deploy_completeness_errors, deploy_schema_errors, normalize_deploy_state
from ..stages.design.state import (
    design_completeness_errors,
    design_schema_errors,
    normalize_design_state,
)
from ..stages.feature_init.state import (
    feature_init_completeness_errors,
    feature_init_schema_errors,
    normalize_feature_init_state,
)
from ..stages.feature_plan.state import (
    feature_plan_completeness_errors,
    feature_plan_reference_errors,
    feature_plan_schema_errors,
)
from ..stages.plan.state import (
    normalize_plan_state,
    plan_completeness_errors,
    plan_reference_errors,
    plan_schema_errors,
)
from ..stages.tech.state import normalize_tech_state, tech_completeness_errors, tech_schema_errors

SnapshotCleanupMode = Literal["replace", "prune"]

SUPPORTED_SNAPSHOT_STAGES = (
    "mvp.concept",
    "mvp.design",
    "mvp.tech",
    "deploy",
    "mvp.architecture",
    "mvp.plan",
    "feature.init",
    "feature.plan",
)


@dataclass(frozen=True)
class ReplaceSnapshotRequest:
    project_path: Path
    branch_name: str
    stage: str
    session_key: str
    expected_revision: int | None
    snapshot: dict[str, Any]
    summary: str | None = None
    evidence: list[str] | None = None


@dataclass(frozen=True)
class PruneSnapshotRequest:
    project_path: Path
    branch_name: str
    stage: str
    session_key: str
    expected_revision: int | None
    operations: list[dict[str, Any]]
    summary: str | None = None
    evidence: list[str] | None = None


@dataclass(frozen=True)
class SnapshotCleanupResult(PayloadResult):
    @property
    def accepted(self) -> bool:
        return bool(self.payload.get("accepted"))


def execute_replace(request: ReplaceSnapshotRequest) -> SnapshotCleanupResult:
    ensure_memory_layout(request.project_path, request.branch_name, stage=request.stage)
    blocked = guard_direct_runtime_write(
        request.project_path,
        branch_name=request.branch_name,
        session_key=request.session_key,
        command_name="snapshots replace",
        allow_proposal_guidance=False,
        blocked_guidance=(
            "release the claim or use an unclaimed session; snapshot cleanup commands do not support proposal-based writes in Phase 2 yet"
        ),
    )
    if blocked is not None:
        return SnapshotCleanupResult(payload=blocked)

    normalized_stage = request.stage.strip().lower()
    if normalized_stage not in SUPPORTED_SNAPSHOT_STAGES:
        return SnapshotCleanupResult(
            payload={
                "accepted": False,
                "branch": request.branch_name,
                "stage": normalized_stage,
                "errors": ["stage must be one of: " + ", ".join(sorted(SUPPORTED_SNAPSHOT_STAGES))],
            }
        )
    if not isinstance(request.snapshot, dict):
        return SnapshotCleanupResult(
            payload={
                "accepted": False,
                "branch": request.branch_name,
                "stage": normalized_stage,
                "errors": ["snapshot must be a JSON object"],
            }
        )

    canonical = load_canonical_branch_state(request.project_path, request.branch_name)
    current_snapshot = copy.deepcopy(canonical.snapshots.get(normalized_stage) or {})
    errors = _snapshot_schema_errors(normalized_stage, request.snapshot)
    if errors:
        return SnapshotCleanupResult(
            payload={
                "accepted": False,
                "branch": request.branch_name,
                "stage": normalized_stage,
                "errors": errors,
            }
        )

    candidate = _normalize_snapshot_state(normalized_stage, request.snapshot)
    candidate = _merge_snapshot_system_fields(
        normalized_stage,
        current_snapshot=current_snapshot,
        candidate_snapshot=candidate,
    )
    validation_errors = _validate_cleanup_candidate(
        stage=normalized_stage,
        candidate_snapshot=candidate,
        canonical=canonical,
        project_path=request.project_path,
        branch_name=request.branch_name,
        was_ratified=bool(current_snapshot.get("ratifiedAt")),
    )
    if validation_errors:
        return SnapshotCleanupResult(
            payload={
                "accepted": False,
                "branch": request.branch_name,
                "stage": normalized_stage,
                "errors": validation_errors,
            }
        )

    summary = _cleanup_summary("replace", normalized_stage, request.summary)
    evidence = list(request.evidence or [])
    payload = _commit_snapshot_cleanup(
        project_path=request.project_path,
        branch_name=request.branch_name,
        stage=normalized_stage,
        session_key=request.session_key,
        expected_revision=request.expected_revision,
        canonical=canonical,
        candidate_snapshot=candidate,
        summary=summary,
        evidence=evidence,
        cleanup_mode="replace",
        details={"replaced": True},
    )
    return SnapshotCleanupResult(payload=payload)


def execute_prune(request: PruneSnapshotRequest) -> SnapshotCleanupResult:
    ensure_memory_layout(request.project_path, request.branch_name, stage=request.stage)
    blocked = guard_direct_runtime_write(
        request.project_path,
        branch_name=request.branch_name,
        session_key=request.session_key,
        command_name="snapshots prune",
        allow_proposal_guidance=False,
        blocked_guidance=(
            "release the claim or use an unclaimed session; snapshot cleanup commands do not support proposal-based writes in Phase 2 yet"
        ),
    )
    if blocked is not None:
        return SnapshotCleanupResult(payload=blocked)

    normalized_stage = request.stage.strip().lower()
    if normalized_stage not in SUPPORTED_SNAPSHOT_STAGES:
        return SnapshotCleanupResult(
            payload={
                "accepted": False,
                "branch": request.branch_name,
                "stage": normalized_stage,
                "errors": ["stage must be one of: " + ", ".join(sorted(SUPPORTED_SNAPSHOT_STAGES))],
            }
        )
    if not isinstance(request.operations, list) or not request.operations:
        return SnapshotCleanupResult(
            payload={
                "accepted": False,
                "branch": request.branch_name,
                "stage": normalized_stage,
                "errors": ["operations must be a non-empty list"],
            }
        )

    canonical = load_canonical_branch_state(request.project_path, request.branch_name)
    current_snapshot = copy.deepcopy(canonical.snapshots.get(normalized_stage) or {})
    candidate, prune_errors, removed_count = prune_snapshot_payload(
        copy.deepcopy(current_snapshot),
        request.operations,
    )
    if prune_errors:
        return SnapshotCleanupResult(
            payload={
                "accepted": False,
                "branch": request.branch_name,
                "stage": normalized_stage,
                "errors": prune_errors,
            }
        )

    candidate = _normalize_snapshot_state(normalized_stage, candidate)
    candidate = _merge_snapshot_system_fields(
        normalized_stage,
        current_snapshot=current_snapshot,
        candidate_snapshot=candidate,
    )
    validation_errors = _validate_cleanup_candidate(
        stage=normalized_stage,
        candidate_snapshot=candidate,
        canonical=canonical,
        project_path=request.project_path,
        branch_name=request.branch_name,
        was_ratified=bool(current_snapshot.get("ratifiedAt")),
    )
    if validation_errors:
        return SnapshotCleanupResult(
            payload={
                "accepted": False,
                "branch": request.branch_name,
                "stage": normalized_stage,
                "errors": validation_errors,
            }
        )

    summary = _cleanup_summary("prune", normalized_stage, request.summary)
    evidence = list(request.evidence or [])
    payload = _commit_snapshot_cleanup(
        project_path=request.project_path,
        branch_name=request.branch_name,
        stage=normalized_stage,
        session_key=request.session_key,
        expected_revision=request.expected_revision,
        canonical=canonical,
        candidate_snapshot=candidate,
        summary=summary,
        evidence=evidence,
        cleanup_mode="prune",
        details={
            "removed_count": removed_count,
            "operations": copy.deepcopy(request.operations),
        },
    )
    return SnapshotCleanupResult(payload=payload)


def prune_snapshot_payload(
    snapshot: dict[str, Any],
    operations: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[str], int]:
    working = copy.deepcopy(snapshot)
    errors: list[str] = []
    removed_total = 0

    for index, operation in enumerate(operations, start=1):
        label = f"operation {index}"
        if not isinstance(operation, dict):
            errors.append(f"{label}: operation must be a JSON object")
            continue
        path = operation.get("path")
        equals = operation.get("equals")
        match = operation.get("match")
        if not isinstance(path, str) or not path.strip():
            errors.append(f"{label}: path must be a non-empty string")
            continue
        has_equals = "equals" in operation
        has_match = "match" in operation
        if has_equals == has_match:
            errors.append(f"{label}: provide exactly one of 'equals' or 'match'")
            continue

        resolved = _resolve_path(working, path)
        if resolved is None:
            errors.append(f"{label}: path '{path}' does not exist")
            continue
        parent, key = resolved
        values = parent.get(key)
        if not isinstance(values, list):
            errors.append(f"{label}: path '{path}' must point to a list")
            continue
        if not values:
            errors.append(f"{label}: path '{path}' does not contain any items to prune")
            continue

        if has_equals:
            if not all(isinstance(item, str) for item in values):
                errors.append(f"{label}: 'equals' can only be used with a list of strings at '{path}'")
                continue
            removed_here = sum(1 for item in values if item == equals)
            if removed_here == 0:
                errors.append(f"{label}: no items matched equals='{equals}' at '{path}'")
                continue
            parent[key] = [item for item in values if item != equals]
            removed_total += removed_here
            continue

        if not isinstance(match, dict) or not match:
            errors.append(f"{label}: 'match' must be a non-empty object")
            continue
        if not all(isinstance(item, dict) for item in values):
            errors.append(f"{label}: 'match' can only be used with a list of objects at '{path}'")
            continue
        kept = [item for item in values if not _dict_matches(item, match)]
        removed_here = len(values) - len(kept)
        if removed_here == 0:
            errors.append(f"{label}: no items matched at '{path}'")
            continue
        parent[key] = kept
        removed_total += removed_here

    return working, errors, removed_total


def _cleanup_summary(mode: SnapshotCleanupMode, stage: str, summary: str | None) -> str:
    normalized = (summary or "").strip()
    if normalized:
        return normalized
    return (
        f"Snapshot prune cleanup for {stage}"
        if mode == "prune"
        else f"Snapshot replace cleanup for {stage}"
    )


def _commit_snapshot_cleanup(
    *,
    project_path: Path,
    branch_name: str,
    stage: str,
    session_key: str,
    expected_revision: int | None,
    canonical: CanonicalBranchState,
    candidate_snapshot: dict[str, Any],
    summary: str,
    evidence: list[str],
    cleanup_mode: SnapshotCleanupMode,
    details: dict[str, Any],
) -> dict[str, Any]:
    ts = now_iso()
    projection_meta = commit_runtime_mutation(
        project_path,
        branch_name=branch_name,
        stage=stage,
        mutation_kind=f"snapshot-{cleanup_mode}",
        scope="stage",
        session_key=session_key,
        expected_revision=expected_revision if expected_revision is not None else canonical.runtime_revision,
        base_state=canonical,
        plan_builder=lambda latest_state: _build_snapshot_cleanup_plan(
            project_path=project_path,
            branch_name=branch_name,
            stage=stage,
            session_key=session_key,
            candidate_snapshot=candidate_snapshot,
            summary=summary,
            evidence=evidence,
            cleanup_mode=cleanup_mode,
            details=details,
            ts=ts,
            canonical=latest_state,
        ),
        conflict_detector=lambda base, current: _detect_snapshot_cleanup_conflict(
            base,
            current,
            stage=stage,
        ),
    )
    if not projection_meta.get("accepted", True):
        return projection_meta
    return {
        "accepted": True,
        "branch": branch_name,
        "stage": stage,
        "operation": cleanup_mode,
        "summary": summary,
        "details": details,
        **projection_meta,
    }


def _build_snapshot_cleanup_plan(
    *,
    project_path: Path,
    branch_name: str,
    stage: str,
    session_key: str,
    candidate_snapshot: dict[str, Any],
    summary: str,
    evidence: list[str],
    cleanup_mode: SnapshotCleanupMode,
    details: dict[str, Any],
    ts: str,
    canonical: CanonicalBranchState,
) -> RuntimeMutationPlan:
    snapshot_payloads = {stage: candidate_snapshot}
    event_record = make_record(
        branch_name,
        stage,
        f"memory.snapshots.{cleanup_mode}",
        summary,
        status="validated",
        evidence=evidence,
        scope="branch",
        record_type="event",
        ts=ts,
        metadata={
            "cleanupMode": f"snapshot_{cleanup_mode}",
            "sessionKey": session_key,
            **details,
        },
    )
    event_record["record_stream"] = "events"
    progress_metrics = _compute_progress_metrics(
        canonical.progress.get("functionCatalog", {}),
        canonical.progress.get("coversFunctions", {}),
    )
    return RuntimeMutationPlan(
        stage_snapshots=build_runtime_snapshot_specs(project_path, branch_name, snapshot_payloads),
        sessions=[],
        records=tag_records_for_stream([event_record], "events"),
        response_payload={
            "written": {
                "stage_snapshots": 1,
                "events": 1,
            },
            "progressMetrics": progress_metrics,
        },
    )


def _detect_snapshot_cleanup_conflict(
    base_state: CanonicalBranchState,
    current_state: CanonicalBranchState,
    *,
    stage: str,
) -> dict[str, Any] | None:
    if base_state.snapshots.get(stage) != current_state.snapshots.get(stage):
        return {
            "kind": "snapshot_conflict",
            "scope": "stage",
            "conflicting_fields": [stage],
            "details": {"reason": "target stage snapshot changed while preparing snapshot cleanup"},
        }
    return None


def _merge_snapshot_system_fields(
    stage: str,
    *,
    current_snapshot: dict[str, Any],
    candidate_snapshot: dict[str, Any],
) -> dict[str, Any]:
    del stage
    result = copy.deepcopy(candidate_snapshot)
    ts = _next_updated_at(current_snapshot.get("updatedAt"))
    if current_snapshot.get("createdAt"):
        result["createdAt"] = current_snapshot["createdAt"]
    result["updatedAt"] = ts
    result["ratifiedAt"] = current_snapshot.get("ratifiedAt")
    current_revision = int(current_snapshot.get("revision") or 0)
    result["revision"] = current_revision + 1 if current_snapshot.get("ratifiedAt") else current_revision
    if current_snapshot.get("ratifiedAt") and not result.get("checkpointSummary"):
        result["checkpointSummary"] = current_snapshot.get("checkpointSummary", "")
    return result


def _validate_cleanup_candidate(
    *,
    stage: str,
    candidate_snapshot: dict[str, Any],
    canonical: CanonicalBranchState,
    project_path: Path,
    branch_name: str,
    was_ratified: bool,
) -> list[str]:
    errors = _snapshot_schema_errors(stage, candidate_snapshot)
    if errors or not was_ratified:
        return errors

    concept_state = _snapshot_state(stage, "mvp.concept", candidate_snapshot, canonical)
    design_state = _snapshot_state(stage, "mvp.design", candidate_snapshot, canonical)
    tech_state = _snapshot_state(stage, "mvp.tech", candidate_snapshot, canonical)
    deploy_state = _snapshot_state(stage, "deploy", candidate_snapshot, canonical)
    architecture_state = _snapshot_state(stage, "mvp.architecture", candidate_snapshot, canonical)
    plan_state = _snapshot_state(stage, "mvp.plan", candidate_snapshot, canonical)
    feature_init_state = _snapshot_state(stage, "feature.init", candidate_snapshot, canonical)
    feature_plan_state = _snapshot_state(stage, "feature.plan", candidate_snapshot, canonical)

    if stage == "mvp.concept":
        errors.extend(concept_completeness_errors(concept_state))
    elif stage == "mvp.design":
        errors.extend(
            design_completeness_errors(
                design_state,
                concept_state=concept_state,
                project_path=project_path,
                branch_name=branch_name,
            )
        )
    elif stage == "mvp.tech":
        errors.extend(tech_completeness_errors(tech_state))
    elif stage == "deploy":
        errors.extend(deploy_completeness_errors(deploy_state))
    elif stage == "mvp.architecture":
        errors.extend(
            architecture_completeness_errors(
                architecture_state,
                design_state=design_state,
            )
        )
    elif stage == "mvp.plan":
        errors.extend(plan_completeness_errors(plan_state))
        errors.extend(
            plan_reference_errors(
                plan_state,
                project_path=project_path,
                branch_name=branch_name,
                progress=canonical.progress,
            )
        )
    elif stage == "feature.init":
        errors.extend(feature_init_completeness_errors(feature_init_state))
    elif stage == "feature.plan":
        errors.extend(feature_plan_completeness_errors(feature_plan_state))
        errors.extend(
            feature_plan_reference_errors(
                feature_plan_state,
                project_path=project_path,
                branch_name=branch_name,
                progress=canonical.progress,
            )
        )
    return errors


def _snapshot_state(
    target_stage: str,
    snapshot_stage: str,
    candidate_snapshot: dict[str, Any],
    canonical: CanonicalBranchState,
) -> dict[str, Any]:
    if target_stage == snapshot_stage:
        return candidate_snapshot
    return canonical.snapshots.get(snapshot_stage) or {}


def _snapshot_schema_errors(stage: str, payload: Any) -> list[str]:
    if stage == "mvp.concept":
        return concept_schema_errors(payload)
    if stage == "mvp.design":
        return design_schema_errors(payload)
    if stage == "mvp.tech":
        return tech_schema_errors(payload)
    if stage == "deploy":
        return deploy_schema_errors(payload)
    if stage == "mvp.architecture":
        return architecture_schema_errors(payload)
    if stage == "mvp.plan":
        return plan_schema_errors(payload)
    if stage == "feature.init":
        return feature_init_schema_errors(payload)
    if stage == "feature.plan":
        return feature_plan_schema_errors(payload)
    return [f"stage '{stage}' is not supported for snapshot cleanup"]


def _normalize_snapshot_state(stage: str, payload: Any) -> dict[str, Any]:
    if stage == "mvp.concept":
        return normalize_concept_state(payload)[0]
    if stage == "mvp.design":
        return normalize_design_state(payload)[0]
    if stage == "mvp.tech":
        return normalize_tech_state(payload)[0]
    if stage == "deploy":
        return normalize_deploy_state(payload)[0]
    if stage == "mvp.architecture":
        return normalize_architecture_state(payload)[0]
    if stage == "mvp.plan":
        return normalize_plan_state(payload)[0]
    if stage == "feature.init":
        return normalize_feature_init_state(payload)[0]
    if stage == "feature.plan":
        return normalize_plan_state(payload)[0]
    raise ValueError(f"stage '{stage}' is not supported for snapshot cleanup")


def _resolve_path(root: dict[str, Any], path: str) -> tuple[dict[str, Any], str] | None:
    current: dict[str, Any] = root
    segments = [segment.strip() for segment in path.split(".") if segment.strip()]
    if not segments:
        return None
    for segment in segments[:-1]:
        value = current.get(segment)
        if not isinstance(value, dict):
            return None
        current = value
    return current, segments[-1]


def _dict_matches(candidate: dict[str, Any], match: dict[str, Any]) -> bool:
    for key, expected in match.items():
        if candidate.get(key) != expected:
            return False
    return True


def _next_updated_at(current_value: Any) -> str:
    candidate = now_iso()
    if not isinstance(current_value, str) or not current_value:
        return candidate
    try:
        current_dt = datetime.fromisoformat(current_value)
        candidate_dt = datetime.fromisoformat(candidate)
    except ValueError:
        return candidate
    if candidate_dt <= current_dt:
        return (current_dt + timedelta(seconds=1)).isoformat()
    return candidate
