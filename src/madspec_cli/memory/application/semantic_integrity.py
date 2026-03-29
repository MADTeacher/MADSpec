from __future__ import annotations

from pathlib import Path
from typing import Any

from .diagnostics_shared import overall_status
from ..domain.conflicts import PROJECT_MEMORY_BRANCH, project_record_id
from ..shared.storage import get_memory_paths, read_jsonl
from ..shared.system_store.layout import get_system_memory_paths, list_vector_namespaces
from ..shared.system_store.store import MemoryStore
from ..shared.system_store.vector import VectorMemoryIndex

SEMANTIC_KIND_TO_STREAM = {
    "fact": "facts",
    "decision": "decisions",
    "contract": "contracts",
}
SEMANTIC_KINDS = set(SEMANTIC_KIND_TO_STREAM)
BRANCH_ALLOWED_SCOPES = {"branch", "stage", "step"}


def build_semantic_integrity(
    project_path: Path,
    *,
    branch_name: str,
) -> dict[str, Any]:
    store = MemoryStore(project_path)
    branch_records = _list_semantic_records(store, branch=branch_name)
    project_records = _list_semantic_records(store, branch=PROJECT_MEMORY_BRANCH)
    branch_section = _branch_semantic_integrity(
        project_path,
        branch_name=branch_name,
        branch_records=branch_records,
    )
    project_section = _project_semantic_integrity(project_records)
    active_section = _active_namespace_integrity(
        project_path,
        branch_records=branch_records,
        project_records=project_records,
    )
    inactive_section = _inactive_namespace_integrity(project_path)
    statuses = [
        branch_section["status"],
        project_section["status"],
        active_section["status"],
        inactive_section["status"],
    ]
    all_issues = [
        *branch_section["issues"],
        *project_section["issues"],
        *active_section["issues"],
        *inactive_section["issues"],
    ]
    error_count = len([item for item in all_issues if item["status"] == "error"])
    warn_count = len([item for item in all_issues if item["status"] == "warn"])
    return {
        "status": overall_status(statuses),
        "summary": {
            "total_issue_count": len(all_issues),
            "error_count": error_count,
            "warn_count": warn_count,
            "branch_issue_count": len(branch_section["issues"]),
            "project_issue_count": len(project_section["issues"]),
            "active_namespace_issue_count": len(active_section["issues"]),
            "inactive_namespace_issue_count": len(inactive_section["issues"]),
        },
        "branch": branch_section,
        "project": project_section,
        "active_vector_namespace": active_section,
        "inactive_vector_namespaces": inactive_section,
    }


def semantic_integrity_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = dict(report.get("summary") or {})
    return {
        "semantic_integrity_status": report.get("status", "ok"),
        "semantic_integrity_error_count": int(summary.get("error_count") or 0),
        "semantic_integrity_warn_count": int(summary.get("warn_count") or 0),
        "semantic_integrity_branch_issue_count": int(summary.get("branch_issue_count") or 0),
        "semantic_integrity_project_issue_count": int(summary.get("project_issue_count") or 0),
        "project_scope_strict": True,
        "project_scope_mode": "project_only",
    }


def _branch_semantic_integrity(
    project_path: Path,
    *,
    branch_name: str,
    branch_records: list[dict[str, Any]],
) -> dict[str, Any]:
    paths = get_memory_paths(project_path, branch_name)
    expected_streams = _group_streams(branch_records)
    actual_streams = {
        "facts": read_jsonl(paths.facts),
        "decisions": read_jsonl(paths.decisions),
        "contracts": read_jsonl(paths.contracts),
    }
    issues: list[dict[str, Any]] = []
    for stream_name, path in (
        ("facts", paths.facts),
        ("decisions", paths.decisions),
        ("contracts", paths.contracts),
    ):
        if actual_streams[stream_name] != expected_streams[stream_name]:
            issues.append(
                _issue(
                    code="semantic_branch_projection_drift",
                    status="error",
                    scope="branch",
                    summary=f"{stream_name} semantic projection does not match canonical records",
                    details=[
                        f"path={path.relative_to(project_path)}",
                        f"expected_records={len(expected_streams[stream_name])}",
                        f"actual_records={len(actual_streams[stream_name])}",
                    ],
                    related_ids={"path": str(path.relative_to(project_path)), "branch": branch_name},
                    probable_cause="Branch semantic projection drifted from canonical validated records in SQLite.",
                    repair_hint="Rebuild projections from canonical SQLite state or use semantic cleanup to restore the intended canonical record set.",
                )
            )
    for record in branch_records:
        problems = _branch_record_shape_problems(record)
        if not problems:
            continue
        issues.append(
            _issue(
                code="semantic_branch_record_shape_mismatch",
                status="error",
                scope="branch",
                summary=f"Branch semantic record {record.get('id')} has an invalid shape",
                details=problems,
                related_ids={"record_id": record.get("id"), "branch": branch_name},
                probable_cause="Canonical branch semantic record contains fields that no longer match the semantic record contract.",
                repair_hint="Repair or replace the affected semantic record through supported cleanup commands so canonical records and projections agree again.",
            )
        )
    return {
        "status": overall_status([item["status"] for item in issues]),
        "validated_record_count": len(branch_records),
        "stream_counts": {key: len(value) for key, value in expected_streams.items()},
        "issues": issues,
    }


def _project_semantic_integrity(project_records: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    for record in project_records:
        expected_id = project_record_id(record)
        if str(record.get("id") or "") != expected_id:
            issues.append(
                _issue(
                    code="semantic_project_id_mismatch",
                    status="error",
                    scope="project",
                    summary=f"Project semantic record {record.get('id')} does not match canonical project id",
                    details=[f"expected_id={expected_id}"],
                    related_ids={"record_id": record.get("id"), "expected_record_id": expected_id},
                    probable_cause="Project-level semantic record was promoted or replaced with a non-canonical identifier.",
                    repair_hint="Replace the affected project semantic record through supported cleanup or promote flow so the canonical project id is recomputed.",
                )
            )
        if str(record.get("scope") or "") != "project":
            issues.append(
                _issue(
                    code="semantic_project_scope_mismatch",
                    status="error",
                    scope="project",
                    summary=f"Project semantic record {record.get('id')} has a non-project scope",
                    details=[f"scope={record.get('scope')!r}"],
                    related_ids={"record_id": record.get("id")},
                    probable_cause="Project-level semantic record payload does not reflect its canonical `__project__` placement.",
                    repair_hint="Replace or re-promote the affected record so its canonical scope becomes `project`.",
                )
            )
        problems = _project_record_shape_problems(record)
        if not problems:
            continue
        issues.append(
            _issue(
                code="semantic_project_record_shape_mismatch",
                status="error",
                scope="project",
                summary=f"Project semantic record {record.get('id')} has an invalid shape",
                details=problems,
                related_ids={"record_id": record.get("id")},
                probable_cause="Project-level semantic record no longer matches the canonical semantic knowledge contract.",
                repair_hint="Replace the affected project semantic knowledge so the canonical project record shape is restored.",
            )
        )
    return {
        "status": overall_status([item["status"] for item in issues]),
        "validated_record_count": len(project_records),
        "issues": issues,
    }


def _active_namespace_integrity(
    project_path: Path,
    *,
    branch_records: list[dict[str, Any]],
    project_records: list[dict[str, Any]],
) -> dict[str, Any]:
    paths = get_system_memory_paths(project_path)
    namespace = paths.active_vector_namespace
    index = VectorMemoryIndex(
        namespace.namespace_dir,
        provider_kind=namespace.provider,
        model_key=namespace.model,
        revision=namespace.revision,
        dimension=namespace.dimension,
    )
    sources = _semantic_chunk_sources(index)
    canonical_by_id = {
        str(record.get("id")): record
        for record in [*branch_records, *project_records]
        if str(record.get("id") or "")
    }
    issues: list[dict[str, Any]] = []
    for source in sources:
        source_id = str(source.get("source_id") or "")
        canonical = canonical_by_id.get(source_id)
        if canonical is None:
            issues.append(
                _issue(
                    code="semantic_active_chunk_orphan",
                    status="error",
                    scope="active_vector_namespace",
                    summary=f"Active semantic chunk source {source_id} no longer has a canonical semantic record",
                    details=[f"namespace={namespace.relative_namespace(project_path)}", f"kind={source.get('kind')}"],
                    related_ids={"source_id": source_id, "namespace": namespace.relative_namespace(project_path)},
                    probable_cause="Active vector namespace still contains semantic chunks for a removed or replaced canonical record.",
                    repair_hint="Run semantic cleanup or reindex so the active namespace reflects the current canonical semantic record set.",
                )
            )
            continue
        mismatch_details = _semantic_chunk_mismatch_details(source, canonical)
        if not mismatch_details:
            continue
        issues.append(
            _issue(
                code="semantic_active_chunk_scope_mismatch",
                status="error",
                scope="active_vector_namespace",
                summary=f"Active semantic chunk source {source_id} does not match canonical semantic record metadata",
                details=mismatch_details,
                related_ids={"source_id": source_id, "record_id": canonical.get("id")},
                probable_cause="Active vector namespace was indexed from an older semantic record shape or branch/project placement.",
                repair_hint="Rebuild the active semantic index or restore the canonical semantic record metadata so both views agree.",
            )
        )
    return {
        "status": overall_status([item["status"] for item in issues]),
        "namespace": namespace.to_payload(project_path),
        "semantic_source_count": len(sources),
        "issues": issues,
    }


def _inactive_namespace_integrity(project_path: Path) -> dict[str, Any]:
    paths = get_system_memory_paths(project_path)
    active_path = paths.active_vector_namespace.namespace_dir.resolve()
    namespace_items: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for namespace in list_vector_namespaces(project_path, root_dir=paths.vector_root_dir):
        if namespace.namespace_dir.resolve() == active_path:
            continue
        index = VectorMemoryIndex(
            namespace.namespace_dir,
            provider_kind=namespace.provider,
            model_key=namespace.model,
            revision=namespace.revision,
            dimension=namespace.dimension,
        )
        semantic_sources = _semantic_chunk_sources(index)
        item = {
            **namespace.to_payload(project_path),
            "semantic_source_count": len(semantic_sources),
            "status": "warn" if semantic_sources else "ok",
        }
        namespace_items.append(item)
        if not semantic_sources:
            continue
        issues.append(
            _issue(
                code="semantic_inactive_namespace_residue",
                status="warn",
                scope="inactive_vector_namespace",
                summary=f"Inactive namespace {item['path']} still contains semantic chunks",
                details=[f"semantic_source_count={len(semantic_sources)}"],
                related_ids={"namespace": item["path"]},
                probable_cause="An older vector namespace still retains semantic chunks from a previous active embedding layout.",
                repair_hint="If cleanup already succeeded and the active namespace is healthy, remove the residue with `madspec memory gc vector-namespaces`; use `madspec memory reindex` when you need a full rebuild of the active namespace.",
            )
        )
    return {
        "status": overall_status([item["status"] for item in issues]),
        "namespace_count": len(namespace_items),
        "namespaces": namespace_items,
        "issues": issues,
    }


def _list_semantic_records(store: MemoryStore, *, branch: str) -> list[dict[str, Any]]:
    records = store.list_semantic_record_details(branch=branch, statuses=["validated"], limit=10000)
    normalized: list[dict[str, Any]] = []
    for record in records:
        semantic_kind = str(record.get("semantic_kind") or "")
        if semantic_kind not in SEMANTIC_KINDS:
            continue
        normalized.append(record)
    normalized.sort(key=lambda item: (str(item.get("ts") or ""), str(item.get("id") or "")))
    return normalized


def _group_streams(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped = {"facts": [], "decisions": [], "contracts": []}
    for record in records:
        grouped[SEMANTIC_KIND_TO_STREAM[str(record["semantic_kind"])]].append(record)
    for value in grouped.values():
        value.sort(key=lambda item: (str(item.get("ts") or ""), str(item.get("id") or "")))
    return grouped


def _branch_record_shape_problems(record: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    semantic_kind = str(record.get("semantic_kind") or "")
    expected_stream = SEMANTIC_KIND_TO_STREAM.get(semantic_kind)
    if expected_stream is None:
        problems.append(f"unsupported semantic_kind={semantic_kind!r}")
    elif str(record.get("record_stream") or "") != expected_stream:
        problems.append(
            f"record_stream={record.get('record_stream')!r} does not match semantic_kind={semantic_kind!r}"
        )
    if not str(record.get("summary") or "").strip():
        problems.append("summary is empty")
    if str(record.get("scope") or "") not in BRANCH_ALLOWED_SCOPES:
        problems.append(f"scope={record.get('scope')!r} is not one of {sorted(BRANCH_ALLOWED_SCOPES)}")
    return problems


def _project_record_shape_problems(record: dict[str, Any]) -> list[str]:
    problems = _branch_record_shape_problems(record)
    if problems and any(item.startswith("scope=") for item in problems):
        problems = [item for item in problems if not item.startswith("scope=")]
    return problems


def _semantic_chunk_sources(index: VectorMemoryIndex) -> list[dict[str, Any]]:
    return [
        item
        for item in index.list_chunk_sources("memory_chunks", source_type="record")
        if str(item.get("kind") or "") in SEMANTIC_KINDS
    ]


def _semantic_chunk_mismatch_details(source: dict[str, Any], canonical: dict[str, Any]) -> list[str]:
    details: list[str] = []
    if str(source.get("kind") or "") != str(canonical.get("semantic_kind") or ""):
        details.append(
            f"kind={source.get('kind')!r} does not match semantic_kind={canonical.get('semantic_kind')!r}"
        )
    if str(source.get("branch") or "") != str(canonical.get("branch") or ""):
        details.append(
            f"branch={source.get('branch')!r} does not match canonical branch={canonical.get('branch')!r}"
        )
    if str(source.get("scope") or "") != str(canonical.get("scope") or ""):
        details.append(
            f"scope={source.get('scope')!r} does not match canonical scope={canonical.get('scope')!r}"
        )
    if str(source.get("status") or "") != str(canonical.get("status") or ""):
        details.append(
            f"status={source.get('status')!r} does not match canonical status={canonical.get('status')!r}"
        )
    return details


def _issue(
    *,
    code: str,
    status: str,
    scope: str,
    summary: str,
    details: list[str],
    related_ids: dict[str, Any],
    probable_cause: str,
    repair_hint: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "status": status,
        "scope": scope,
        "summary": summary,
        "details": details,
        "related_ids": related_ids,
        "probable_cause": probable_cause,
        "repair_hint": repair_hint,
    }
