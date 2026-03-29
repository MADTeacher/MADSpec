from __future__ import annotations

import copy
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from madspec_cli.shared.kernel.result import PayloadResult

from .parallel_runtime import is_phase2_enabled
from .proposal_guard import guard_direct_runtime_write
from .proposals import PublishProposalRequest, publish
from ..domain.conflicts import PROJECT_MEMORY_BRANCH, project_record_id, semantic_fingerprint
from ..shared.records import make_record
from ..shared.storage import ensure_memory_layout, now_iso
from ..shared.system_store.canonical_state import load_canonical_branch_state, refresh_branch_projections
from ..shared.system_store.layout import get_system_memory_paths
from ..shared.system_store.store import MemoryStore
from ..shared.system_store.vector import VectorMemoryIndex
from ..shared.validation import validate_branch_memory

SemanticScope = Literal["branch", "project"]
SemanticCleanupMode = Literal["replace", "prune"]
SemanticKind = Literal["fact", "decision", "contract"]
SemanticRecordStatus = Literal["validated", "obsolete", "conflicted"]

SEMANTIC_KINDS: tuple[SemanticKind, ...] = ("fact", "decision", "contract")
SEMANTIC_STATUSES: tuple[SemanticRecordStatus, ...] = ("validated", "obsolete", "conflicted")
SEMANTIC_STREAMS: dict[SemanticKind, str] = {
    "fact": "facts",
    "decision": "decisions",
    "contract": "contracts",
}
MATCH_ALLOWED_FIELDS = {
    "id",
    "semantic_kind",
    "summary",
    "stage",
    "step_id",
    "scope",
    "status",
    "source",
    "metadata",
    "evidence",
}


@dataclass(frozen=True)
class RetrieveSemanticRequest:
    project_path: Path
    scope: SemanticScope
    branch_name: str | None = None
    include_obsolete: bool = False
    include_conflicted: bool = False


@dataclass(frozen=True)
class ReplaceSemanticRequest:
    project_path: Path
    scope: SemanticScope
    branch_name: str | None
    session_key: str
    expected_revision: int | None
    semantic: dict[str, Any]
    summary: str | None = None
    evidence: list[str] | None = None


@dataclass(frozen=True)
class PruneSemanticRequest:
    project_path: Path
    scope: SemanticScope
    branch_name: str | None
    session_key: str
    expected_revision: int | None
    operations: list[dict[str, Any]]
    summary: str | None = None
    evidence: list[str] | None = None


@dataclass(frozen=True)
class SemanticCleanupResult(PayloadResult):
    @property
    def accepted(self) -> bool:
        return bool(self.payload.get("accepted"))


def execute_retrieve(request: RetrieveSemanticRequest) -> SemanticCleanupResult:
    scope = _normalize_scope(request.scope)
    branch_name = _resolve_branch_for_scope(scope, request.branch_name)
    store = MemoryStore(request.project_path)
    runtime_revision = store.fetch_branch_revision(branch_name)
    statuses = _selected_semantic_statuses(
        include_obsolete=request.include_obsolete,
        include_conflicted=request.include_conflicted,
    )
    semantic = _load_semantic_artifact(
        store,
        scope=scope,
        branch_name=branch_name,
        statuses=statuses,
    )
    return SemanticCleanupResult(
        payload={
            "scope": scope,
            "branch": None if scope == "project" else branch_name,
            "runtime_revision": runtime_revision,
            "semantic": semantic,
            "counts": {key: len(value) for key, value in semantic.items()},
        }
    )


def execute_replace(request: ReplaceSemanticRequest) -> SemanticCleanupResult:
    return _execute_replace(
        request,
        allow_auto_publish=True,
        bypass_claimed_direct_guard=False,
    )


def execute_replace_from_proposal(request: ReplaceSemanticRequest) -> SemanticCleanupResult:
    return _execute_replace(
        request,
        allow_auto_publish=False,
        bypass_claimed_direct_guard=True,
    )


def _execute_replace(
    request: ReplaceSemanticRequest,
    *,
    allow_auto_publish: bool,
    bypass_claimed_direct_guard: bool,
) -> SemanticCleanupResult:
    scope = _normalize_scope(request.scope)
    branch_name = _resolve_branch_for_scope(scope, request.branch_name)
    store = MemoryStore(request.project_path)
    if scope == "branch":
        ensure_memory_layout(request.project_path, branch_name, full=True)
    current = _load_semantic_artifact(
        store,
        scope=scope,
        branch_name=branch_name,
        statuses=SEMANTIC_STATUSES,
    )
    validation_errors = _validate_semantic_payload(request.semantic)
    if validation_errors:
        return SemanticCleanupResult(
            payload={
                "accepted": False,
                "scope": scope,
                "branch": None if scope == "project" else branch_name,
                "errors": validation_errors,
            }
        )
    summary = request.summary or _default_summary("replace", scope)
    if scope == "branch" and not bypass_claimed_direct_guard:
        proposal_payload = _maybe_autopublish_cleanup_proposal(
            project_path=request.project_path,
            branch_name=branch_name,
            session_key=request.session_key,
            expected_revision=request.expected_revision,
            cleanup_mode="replace",
            summary=summary,
            evidence=list(request.evidence or []),
            proposal_fields={"semantic": request.semantic},
            allow_auto_publish=allow_auto_publish,
        )
        if proposal_payload is not None:
            return SemanticCleanupResult(payload=proposal_payload)
        blocked = guard_direct_runtime_write(
            request.project_path,
            branch_name=branch_name,
            session_key=request.session_key,
            command_name="semantic replace",
            allow_proposal_guidance=False,
        )
        if blocked is not None:
            return SemanticCleanupResult(payload=blocked)
    candidate = _normalize_semantic_payload(
        request.semantic,
        scope=scope,
        branch_name=branch_name,
        cleanup_mode="replace",
    )
    payload = _commit_cleanup(
        project_path=request.project_path,
        scope=scope,
        branch_name=branch_name,
        session_key=request.session_key,
        expected_revision=request.expected_revision,
        current=current,
        candidate=candidate,
        summary=summary,
        evidence=list(request.evidence or []),
        cleanup_mode="replace",
    )
    return SemanticCleanupResult(payload=payload)


def execute_prune(request: PruneSemanticRequest) -> SemanticCleanupResult:
    return _execute_prune(
        request,
        allow_auto_publish=True,
        bypass_claimed_direct_guard=False,
    )


def execute_prune_from_proposal(request: PruneSemanticRequest) -> SemanticCleanupResult:
    return _execute_prune(
        request,
        allow_auto_publish=False,
        bypass_claimed_direct_guard=True,
    )


def _execute_prune(
    request: PruneSemanticRequest,
    *,
    allow_auto_publish: bool,
    bypass_claimed_direct_guard: bool,
) -> SemanticCleanupResult:
    scope = _normalize_scope(request.scope)
    branch_name = _resolve_branch_for_scope(scope, request.branch_name)
    if scope == "branch":
        ensure_memory_layout(request.project_path, branch_name, full=True)
    if not isinstance(request.operations, list) or not request.operations:
        return SemanticCleanupResult(
            payload={
                "accepted": False,
                "scope": scope,
                "branch": None if scope == "project" else branch_name,
                "errors": ["operations must be a non-empty list"],
            }
        )
    validation_errors = _validate_prune_operations(request.operations)
    if validation_errors:
        return SemanticCleanupResult(
            payload={
                "accepted": False,
                "scope": scope,
                "branch": None if scope == "project" else branch_name,
                "errors": validation_errors,
            }
        )
    summary = request.summary or _default_summary("prune", scope)
    if scope == "branch" and not bypass_claimed_direct_guard:
        proposal_payload = _maybe_autopublish_cleanup_proposal(
            project_path=request.project_path,
            branch_name=branch_name,
            session_key=request.session_key,
            expected_revision=request.expected_revision,
            cleanup_mode="prune",
            summary=summary,
            evidence=list(request.evidence or []),
            proposal_fields={"operations": request.operations},
            allow_auto_publish=allow_auto_publish,
        )
        if proposal_payload is not None:
            return SemanticCleanupResult(payload=proposal_payload)
        blocked = guard_direct_runtime_write(
            request.project_path,
            branch_name=branch_name,
            session_key=request.session_key,
            command_name="semantic prune",
            allow_proposal_guidance=False,
        )
        if blocked is not None:
            return SemanticCleanupResult(payload=blocked)
    store = MemoryStore(request.project_path)
    current = _load_semantic_artifact(
        store,
        scope=scope,
        branch_name=branch_name,
        statuses=SEMANTIC_STATUSES,
    )
    candidate, removed_count, errors = _apply_prune_operations(current, request.operations)
    if errors:
        return SemanticCleanupResult(
            payload={
                "accepted": False,
                "scope": scope,
                "branch": None if scope == "project" else branch_name,
                "errors": errors,
            }
        )
    payload = _commit_cleanup(
        project_path=request.project_path,
        scope=scope,
        branch_name=branch_name,
        session_key=request.session_key,
        expected_revision=request.expected_revision,
        current=current,
        candidate=candidate,
        summary=summary,
        evidence=list(request.evidence or []),
        cleanup_mode="prune",
        details={"removed_count": removed_count},
    )
    return SemanticCleanupResult(payload=payload)


def validate_semantic_cleanup_proposal_payload(payload: dict[str, Any]) -> None:
    scope = _normalize_scope(str(payload.get("scope") or ""))
    if scope != "branch":
        raise ValueError("semantic_cleanup proposals currently support only scope='branch'")
    operation = _normalize_cleanup_mode(str(payload.get("operation") or ""))
    evidence = payload.get("evidence")
    if evidence is not None:
        if not isinstance(evidence, list) or any(not isinstance(item, str) for item in evidence):
            raise ValueError("semantic_cleanup evidence must be a list of strings")
    summary = payload.get("summary")
    if summary is not None and not isinstance(summary, str):
        raise ValueError("semantic_cleanup summary must be a string")
    if operation == "replace":
        errors = _validate_semantic_payload(payload.get("semantic"))
    else:
        operations = payload.get("operations")
        if not isinstance(operations, list) or not operations:
            raise ValueError("semantic_cleanup prune proposals require a non-empty operations list")
        errors = _validate_prune_operations(operations)
    if errors:
        raise ValueError("; ".join(errors))


def apply_semantic_cleanup_proposal(project_path: Path, proposal: dict[str, Any]) -> dict[str, Any]:
    payload = dict(proposal.get("payload") or {})
    validate_semantic_cleanup_proposal_payload(payload)
    operation = _normalize_cleanup_mode(str(payload.get("operation") or ""))
    common_args = {
        "project_path": project_path,
        "scope": "branch",
        "branch_name": proposal["branch"],
        "session_key": proposal["session_key"],
        "expected_revision": int(proposal["base_revision"]),
        "summary": payload.get("summary"),
        "evidence": list(payload.get("evidence") or []),
    }
    if operation == "replace":
        return execute_replace_from_proposal(
            ReplaceSemanticRequest(
                semantic=dict(payload.get("semantic") or {}),
                **common_args,
            )
        ).to_payload()
    return execute_prune_from_proposal(
        PruneSemanticRequest(
            operations=list(payload.get("operations") or []),
            **common_args,
        )
    ).to_payload()


def _commit_cleanup(
    *,
    project_path: Path,
    scope: SemanticScope,
    branch_name: str,
    session_key: str,
    expected_revision: int | None,
    current: dict[str, list[dict[str, Any]]],
    candidate: dict[str, list[dict[str, Any]]],
    summary: str,
    evidence: list[str],
    cleanup_mode: SemanticCleanupMode,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    details = dict(details or {})
    store = MemoryStore(project_path)
    current_revision = store.fetch_branch_revision(branch_name)
    removed_ids = _semantic_record_ids(current) - _semantic_record_ids(candidate)
    candidate_records = _flatten_semantic_artifact(candidate)
    ts = now_iso()
    target_revision = expected_revision if expected_revision is not None else current_revision

    try:
        with store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            latest_revision = store.fetch_branch_revision(branch_name, conn=conn)
            if latest_revision != target_revision:
                return {
                    "accepted": False,
                    "kind": "conflict",
                    "conflict": {
                        "kind": "semantic_conflict",
                        "scope": scope,
                        "expected_revision": target_revision,
                        "actual_revision": latest_revision,
                        "retry_guidance": "Refresh semantic context to get the latest runtime_revision, then retry the command.",
                        "details": {
                            "reason": "target semantic knowledge changed while preparing cleanup",
                        },
                    },
                }

            if removed_ids:
                store.delete_records(sorted(removed_ids), conn=conn)
            store.upsert_records_batch(candidate_records, conn=conn)
            if scope == "branch":
                audit_event = make_record(
                    branch_name,
                    "semantic.cleanup",
                    f"memory.semantic.{cleanup_mode}",
                    summary,
                    status="validated",
                    evidence=evidence,
                    scope="branch",
                    record_type="event",
                    ts=ts,
                    metadata={
                        "cleanupMode": f"semantic_{cleanup_mode}",
                        "cleanupScope": scope,
                        "sessionKey": session_key,
                        **details,
                    },
                )
                audit_event["record_stream"] = "events"
                store.upsert_records_batch([audit_event], conn=conn)
            store.update_branch_revision(branch_name, revision=latest_revision + 1, conn=conn)
    except sqlite3.Error as exc:
        return {
            "accepted": False,
            "scope": scope,
            "branch": None if scope == "project" else branch_name,
            "errors": [str(exc)],
        }

    vector_warning = _cleanup_active_vector_namespace(project_path, sorted(removed_ids))
    runtime_after = current_revision + 1

    if scope == "project":
        store.append_merge_history(
            {
                "eventId": str(uuid.uuid4()),
                "proposalId": None,
                "sourceBranch": branch_name,
                "targetBranch": PROJECT_MEMORY_BRANCH,
                "eventType": f"semantic_{cleanup_mode}",
                "summary": summary,
                "payload": {
                    "scope": scope,
                    "removedCount": len(removed_ids),
                    "recordCount": len(candidate_records),
                    **details,
                },
                "ts": ts,
            }
        )
        payload = {
            "accepted": True,
            "scope": scope,
            "branch": None,
            "operation": cleanup_mode,
            "summary": summary,
            "details": {
                **details,
                "record_count": len(candidate_records),
                "removed_count": len(removed_ids),
            },
            "runtime_revision_before": current_revision,
            "runtime_revision_after": runtime_after,
            "projection_status": "not_applicable",
            "projection_refresh_required": False,
            "generated_views": [],
            "warnings": [],
        }
        if vector_warning:
            payload["warnings"].append(vector_warning)
        return payload

    generated_views: list[str] = []
    warnings: list[str] = []
    projection_status = "synced"
    projection_refresh_required = False
    try:
        _, generated_paths = refresh_branch_projections(
            project_path,
            branch_name,
            stage=None,
            full=True,
        )
        generated_views = [str(path.relative_to(project_path)) for path in generated_paths]
        validation_errors = validate_branch_memory(project_path, branch_name, stage=None, policy_violations=[])
        if validation_errors:
            raise ValueError("; ".join(validation_errors))
    except Exception as exc:
        projection_status = "stale"
        projection_refresh_required = True
        warnings.append(f"projection refresh failed: {exc}")
    if vector_warning:
        warnings.append(vector_warning)
    return {
        "accepted": True,
        "scope": scope,
        "branch": branch_name,
        "operation": cleanup_mode,
        "summary": summary,
        "details": {
            **details,
            "record_count": len(candidate_records),
            "removed_count": len(removed_ids),
        },
        "runtime_revision_before": current_revision,
        "runtime_revision_after": runtime_after,
        "projection_status": projection_status,
        "projection_refresh_required": projection_refresh_required,
        "generated_views": generated_views,
        "warnings": warnings,
    }


def _maybe_autopublish_cleanup_proposal(
    *,
    project_path: Path,
    branch_name: str,
    session_key: str,
    expected_revision: int | None,
    cleanup_mode: SemanticCleanupMode,
    summary: str,
    evidence: list[str],
    proposal_fields: dict[str, Any],
    allow_auto_publish: bool,
) -> dict[str, Any] | None:
    if not is_phase2_enabled(project_path):
        return None
    store = MemoryStore(project_path)
    coordination = store.fetch_session_coordination(
        branch=branch_name,
        session_key=session_key,
    )
    claim = coordination.get("claim")
    work_item = coordination.get("work_item")
    task = coordination.get("task")
    if claim is None or work_item is None or task is None:
        return None
    if not allow_auto_publish:
        return None
    base_revision = expected_revision if expected_revision is not None else store.fetch_branch_revision(branch_name)
    proposal_result = publish(
        PublishProposalRequest(
            project_path=project_path,
            branch_name=branch_name,
            proposal_type="semantic_cleanup",
            session_key=session_key,
            subagent_id=str(work_item["subagent_id"]),
            base_revision=base_revision,
            payload={
                "scope": "branch",
                "operation": cleanup_mode,
                "summary": summary,
                "evidence": list(evidence),
                **proposal_fields,
            },
            target_scope={"scope": "semantic-knowledge"},
            conflict_hints={
                "kind": "semantic_cleanup",
                "operation": cleanup_mode,
                "scope": "semantic-knowledge",
            },
            task_id=str(task["task_id"]),
            work_item_id=str(work_item["work_item_id"]),
        )
    ).to_payload()
    return {
        "accepted": True,
        "proposal_mode": True,
        "apply_required": True,
        "scope": "branch",
        "branch": branch_name,
        "operation": cleanup_mode,
        "summary": summary,
        "runtime_revision_before": base_revision,
        "base_revision": base_revision,
        "proposal": proposal_result["proposal"],
    }


def _cleanup_active_vector_namespace(project_path: Path, record_ids: list[str]) -> str | None:
    if not record_ids:
        return None
    try:
        namespace = get_system_memory_paths(project_path).active_vector_namespace
        index = VectorMemoryIndex(
            namespace.namespace_dir,
            provider_kind=namespace.provider,
            model_key=namespace.model,
            revision=namespace.revision,
            dimension=namespace.dimension,
        )
        index.delete_source_chunks(
            "memory_chunks",
            source_type="record",
            source_ids=record_ids,
        )
    except Exception as exc:
        return f"active vector namespace cleanup failed: {exc}"
    return None


def _load_semantic_artifact(
    store: MemoryStore,
    *,
    scope: SemanticScope,
    branch_name: str,
    statuses: list[str] | tuple[str, ...],
) -> dict[str, list[dict[str, Any]]]:
    if scope == "branch":
        records = store.list_semantic_record_details(branch=branch_name, statuses=list(statuses), limit=10000)
    else:
        records = store.list_semantic_record_details(branch=PROJECT_MEMORY_BRANCH, statuses=list(statuses), limit=10000)
    grouped: dict[str, list[dict[str, Any]]] = {"facts": [], "decisions": [], "contracts": []}
    for item in records:
        payload = dict(item["payload"])
        semantic_kind = str(payload.get("semantic_kind") or item.get("semantic_kind") or "")
        if semantic_kind not in SEMANTIC_STREAMS:
            continue
        payload["semantic_kind"] = semantic_kind
        payload["record_stream"] = SEMANTIC_STREAMS[semantic_kind]
        payload["fingerprint"] = semantic_fingerprint(payload)
        grouped[SEMANTIC_STREAMS[semantic_kind]].append(payload)
    for key in grouped:
        grouped[key] = sorted(
            grouped[key],
            key=lambda item: (str(item.get("ts") or ""), str(item.get("id") or "")),
        )
    return grouped


def _validate_prune_operations(operations: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            errors.append(f"operations[{index}] must be an object")
            continue
        semantic_kind = str(operation.get("semantic_kind") or "").strip()
        if semantic_kind not in SEMANTIC_KINDS:
            errors.append(f"operations[{index}].semantic_kind must be one of: fact, decision, contract")
            continue
        selector_count = sum(
            1
            for key in ("record_id", "fingerprint", "match")
            if operation.get(key) is not None
        )
        if selector_count != 1:
            errors.append(f"operations[{index}] must include exactly one of: record_id, fingerprint, match")
            continue
        match_payload = operation.get("match")
        if match_payload is not None:
            if not isinstance(match_payload, dict) or not match_payload:
                errors.append(f"operations[{index}].match must be a non-empty object")
                continue
            unknown = sorted(key for key in match_payload if key not in MATCH_ALLOWED_FIELDS)
            if unknown:
                errors.append(
                    f"operations[{index}].match contains unsupported fields: {', '.join(unknown)}"
                )
    return errors


def _validate_semantic_payload(semantic: Any) -> list[str]:
    if not isinstance(semantic, dict):
        return ["semantic must be a JSON object with facts, decisions, and contracts arrays"]
    errors: list[str] = []
    for stream_name in ("facts", "decisions", "contracts"):
        if stream_name not in semantic:
            errors.append(f"semantic.{stream_name} is required")
            continue
        if not isinstance(semantic[stream_name], list):
            errors.append(f"semantic.{stream_name} must be a list")
            continue
        expected_kind = stream_name[:-1] if stream_name != "decisions" else "decision"
        for index, record in enumerate(semantic[stream_name]):
            if not isinstance(record, dict):
                errors.append(f"semantic.{stream_name}[{index}] must be an object")
                continue
            summary = str(record.get("summary") or "").strip()
            if not summary:
                errors.append(f"semantic.{stream_name}[{index}].summary is required")
            record_kind = str(record.get("semantic_kind") or expected_kind)
            if record_kind != expected_kind:
                errors.append(f"semantic.{stream_name}[{index}].semantic_kind must be '{expected_kind}'")
            status = str(record.get("status") or "validated").strip().lower()
            if status not in SEMANTIC_STATUSES:
                errors.append(
                    f"semantic.{stream_name}[{index}].status must be one of: conflicted, obsolete, validated"
                )
    return errors


def _normalize_semantic_payload(
    semantic: dict[str, Any],
    *,
    scope: SemanticScope,
    branch_name: str,
    cleanup_mode: SemanticCleanupMode,
) -> dict[str, list[dict[str, Any]]]:
    ts = now_iso()
    normalized: dict[str, list[dict[str, Any]]] = {"facts": [], "decisions": [], "contracts": []}
    for stream_name, semantic_kind in (("facts", "fact"), ("decisions", "decision"), ("contracts", "contract")):
        for raw_record in list(semantic.get(stream_name) or []):
            normalized[stream_name].append(
                _normalize_record(
                    dict(raw_record),
                    semantic_kind=semantic_kind,
                    stream_name=stream_name,
                    scope=scope,
                    branch_name=branch_name,
                    cleanup_mode=cleanup_mode,
                    fallback_ts=ts,
                )
            )
    return normalized


def _normalize_record(
    record: dict[str, Any],
    *,
    semantic_kind: SemanticKind,
    stream_name: str,
    scope: SemanticScope,
    branch_name: str,
    cleanup_mode: SemanticCleanupMode,
    fallback_ts: str,
) -> dict[str, Any]:
    normalized = copy.deepcopy(record)
    normalized.pop("content_hash", None)
    normalized.pop("fingerprint", None)
    normalized["semantic_kind"] = semantic_kind
    normalized["record_stream"] = stream_name
    normalized["status"] = _normalize_semantic_status(normalized.get("status"))
    normalized["branch"] = branch_name
    normalized["scope"] = "project" if scope == "project" else str(normalized.get("scope") or "branch")
    normalized["ts"] = str(normalized.get("ts") or fallback_ts)
    normalized["summary"] = str(normalized.get("summary") or "").strip()
    normalized["evidence"] = [str(item) for item in list(normalized.get("evidence") or [])]
    normalized["metadata"] = dict(normalized.get("metadata") or {})
    normalized["source"] = str(normalized.get("source") or f"memory.semantic.{cleanup_mode}")
    if scope == "project":
        normalized["id"] = project_record_id(normalized)
    else:
        normalized["id"] = str(normalized.get("id") or uuid.uuid4())
    return normalized


def _apply_prune_operations(
    current: dict[str, list[dict[str, Any]]],
    operations: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], int, list[str]]:
    errors = _validate_prune_operations(operations)
    if errors:
        return copy.deepcopy(current), 0, errors
    candidate = copy.deepcopy(current)
    removed_count = 0
    for index, operation in enumerate(operations):
        semantic_kind = str(operation.get("semantic_kind") or "").strip()
        stream_name = SEMANTIC_STREAMS[semantic_kind]
        retained: list[dict[str, Any]] = []
        for record in candidate[stream_name]:
            if _record_matches_operation(record, operation):
                removed_count += 1
                continue
            retained.append(record)
        candidate[stream_name] = retained
    return candidate, removed_count, errors


def _record_matches_operation(record: dict[str, Any], operation: dict[str, Any]) -> bool:
    record_id = operation.get("record_id")
    if record_id is not None:
        return str(record.get("id") or "") == str(record_id)
    fingerprint = operation.get("fingerprint")
    if fingerprint is not None:
        return semantic_fingerprint(record) == str(fingerprint)
    match_payload = operation.get("match") or {}
    for key, value in match_payload.items():
        if record.get(key) != value:
            return False
    return True


def _semantic_record_ids(semantic: dict[str, list[dict[str, Any]]]) -> set[str]:
    return {
        str(record.get("id"))
        for record in _flatten_semantic_artifact(semantic)
        if str(record.get("id") or "")
    }


def _flatten_semantic_artifact(semantic: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stream_name in ("facts", "decisions", "contracts"):
        rows.extend(copy.deepcopy(semantic.get(stream_name) or []))
    return rows


def _normalize_scope(scope: str) -> SemanticScope:
    value = str(scope or "").strip().lower()
    if value not in {"branch", "project"}:
        raise ValueError("scope must be 'branch' or 'project'")
    return value


def _normalize_cleanup_mode(mode: str) -> SemanticCleanupMode:
    value = str(mode or "").strip().lower()
    if value not in {"replace", "prune"}:
        raise ValueError("operation must be 'prune' or 'replace'")
    return value


def _resolve_branch_for_scope(scope: SemanticScope, branch_name: str | None) -> str:
    if scope == "project":
        if branch_name:
            raise ValueError("--branch is not supported when --scope=project")
        return PROJECT_MEMORY_BRANCH
    if not branch_name:
        raise ValueError("branch is required for branch semantic cleanup")
    return branch_name


def _default_summary(cleanup_mode: SemanticCleanupMode, scope: SemanticScope) -> str:
    if cleanup_mode == "replace":
        return "Replace semantic knowledge with canonical copy" if scope == "branch" else "Replace project semantic knowledge with canonical copy"
    return "Prune semantic knowledge entries" if scope == "branch" else "Prune project semantic knowledge entries"


def _selected_semantic_statuses(*, include_obsolete: bool, include_conflicted: bool) -> list[str]:
    statuses = ["validated"]
    if include_obsolete:
        statuses.append("obsolete")
    if include_conflicted:
        statuses.append("conflicted")
    return statuses


def _normalize_semantic_status(value: Any) -> SemanticRecordStatus:
    normalized = str(value or "validated").strip().lower()
    if normalized not in SEMANTIC_STATUSES:
        raise ValueError("status must be one of: conflicted, obsolete, validated")
    return normalized  # type: ignore[return-value]
