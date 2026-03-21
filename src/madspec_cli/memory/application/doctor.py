from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from madspec_cli.memory.shared.storage import get_memory_paths
from madspec_cli.memory.shared.system_store.layout import get_system_memory_paths
from madspec_cli.memory.shared.system_store.store import MemoryStore
from madspec_cli.memory.shared.validation import validate_branch_memory
from madspec_cli.memory.shared.validation_views import validate_generated_stage_views
from madspec_cli.shared.kernel.result import PayloadResult

from .diagnostics_shared import overall_status

REQUIRED_SQLITE_TABLES = {
    "artifacts",
    "branch_runtime_state",
    "index_jobs",
    "merge_history",
    "merge_proposals",
    "records",
    "retrieval_runs",
    "runtime_proposal_events",
    "runtime_proposals",
    "sessions",
    "stage_snapshots",
    "writer_leases",
}
RECOMMENDED_SQLITE_TABLES = {
    "artifacts_fts",
    "records_fts",
    "stage_snapshots_fts",
}
WRITER_LEASE_PREFIXES = (
    "plan-catalog:",
    "implement-step:",
    "artifact:",
    "review:",
    "security:",
)


@dataclass(frozen=True)
class MemoryDoctorRequest:
    project_path: Path
    branch_name: str


@dataclass(frozen=True)
class MemoryDoctorResult(PayloadResult):
    @property
    def has_errors(self) -> bool:
        return self.payload.get("status") == "error"


def execute(request: MemoryDoctorRequest) -> MemoryDoctorResult:
    paths = get_memory_paths(request.project_path, request.branch_name)
    system_paths = get_system_memory_paths(request.project_path)
    checks: list[dict[str, Any]] = []

    required_paths = {
        "branch_dir": paths.branch_dir,
        "memory_dir": paths.memory_dir,
        "progress": paths.progress,
        "active_session": paths.active_session,
        "decision_log": paths.decision_log,
        "events": paths.events,
        "facts": paths.facts,
        "decisions": paths.decisions,
        "contracts": paths.contracts,
        "sqlite_file": system_paths.sqlite_file,
        "vector_dir": system_paths.lancedb_dir,
        "schema_version": system_paths.schema_version,
    }
    missing_paths = [
        str(path.relative_to(request.project_path))
        for path in required_paths.values()
        if not path.exists()
    ]
    checks.append(
        _make_check(
            "branch_layout",
            "ok" if not missing_paths else "error",
            "branch memory layout is complete" if not missing_paths else "required memory files are missing",
            missing_paths,
        )
    )

    integrity_errors = validate_branch_memory(request.project_path, request.branch_name)
    checks.append(
        _make_check(
            "integrity",
            "ok" if not integrity_errors else "error",
            "branch memory passed validation"
            if not integrity_errors
            else "branch memory has integrity or validation errors",
            integrity_errors,
        )
    )

    db_payload, db_check = _db_diagnostics(request.project_path)
    checks.append(db_check)

    vector_payload, vector_check = _vector_diagnostics(request.project_path)
    checks.append(vector_check)

    indexing_payload, indexing_check = _indexing_diagnostics(request.project_path, request.branch_name)
    checks.append(indexing_check)

    lease_payload, lease_check = _lease_diagnostics(request.project_path, request.branch_name)
    checks.append(lease_check)

    proposal_payload, proposal_check = _proposal_diagnostics(request.project_path, request.branch_name)
    checks.append(proposal_check)

    generated_view_errors = validate_generated_stage_views(
        paths,
        project_path=request.project_path,
        branch_name=request.branch_name,
    )
    generated_views = {
        "status": "ok" if not generated_view_errors else "error",
        "errors": generated_view_errors,
    }
    checks.append(
        _make_check(
            "generated_views",
            generated_views["status"],
            "generated views are in sync"
            if not generated_view_errors
            else "generated views are missing or out of sync",
            generated_view_errors,
        )
    )

    return MemoryDoctorResult(
        payload={
            "branch": request.branch_name,
            "status": overall_status([item["status"] for item in checks]),
            "checks": checks,
            "db": db_payload,
            "vector": vector_payload,
            "generated_views": generated_views,
            "indexing": indexing_payload,
            "writer_leases": lease_payload,
            "runtime_proposals": proposal_payload,
        }
    )


def _db_diagnostics(project_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    store = MemoryStore(project_path)
    payload = {
        "sqlite_path": str(store.paths.sqlite_file.relative_to(project_path)),
        "exists": store.paths.sqlite_file.exists(),
        "tables": [],
        "missing_tables": [],
        "missing_recommended_tables": [],
    }
    if not store.paths.sqlite_file.exists():
        return (
            payload,
            _make_check(
                "sqlite",
                "error",
                "SQLite memory database is missing",
                [payload["sqlite_path"]],
            ),
        )

    try:
        tables = set(store.list_tables())
    except Exception as exc:
        payload["error"] = str(exc)
        return (
            payload,
            _make_check("sqlite", "error", "failed to inspect SQLite memory database", [str(exc)]),
        )

    payload["tables"] = sorted(tables)
    payload["missing_tables"] = sorted(REQUIRED_SQLITE_TABLES.difference(tables))
    payload["missing_recommended_tables"] = sorted(RECOMMENDED_SQLITE_TABLES.difference(tables))
    status = "ok"
    details: list[str] = []
    if payload["missing_tables"]:
        status = "error"
        details.extend(f"missing table: {name}" for name in payload["missing_tables"])
    if payload["missing_recommended_tables"]:
        if status != "error":
            status = "warn"
        details.extend(
            f"missing recommended table: {name}"
            for name in payload["missing_recommended_tables"]
        )

    summary = "SQLite memory database is available"
    if status == "warn":
        summary = "SQLite memory database is available with degraded search capabilities"
    elif status == "error":
        summary = "SQLite memory database schema is incomplete"
    return payload, _make_check("sqlite", status, summary, details)


def _vector_diagnostics(project_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    store = MemoryStore(project_path)
    payload = store.describe_vector_index()
    payload["vector_dir"] = str(store.paths.lancedb_dir.relative_to(project_path))
    if not store.paths.lancedb_dir.exists():
        return (
            payload,
            _make_check(
                "vector",
                "error",
                "vector index directory is missing",
                [payload["vector_dir"]],
            ),
        )
    details: list[str] = []
    status = "ok"
    table_names = {item["name"] for item in payload.get("tables", [])}
    for required_table in ("memory_chunks", "artifact_chunks"):
        if required_table not in table_names:
            status = "warn"
            details.append(f"missing vector table: {required_table}")
    summary = "vector index backend is available"
    if status == "warn":
        summary = "vector index backend is available but some tables are missing"
    return payload, _make_check("vector", status, summary, details)


def _indexing_diagnostics(project_path: Path, branch_name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    store = MemoryStore(project_path)
    payload = {
        "pending_jobs": 0,
        "failed_jobs": 0,
        "jobs": [],
    }
    if not store.paths.sqlite_file.exists():
        return (
            payload,
            _make_check(
                "indexing",
                "error",
                "indexing cannot be inspected because SQLite is missing",
                [str(store.paths.sqlite_file.relative_to(project_path))],
            ),
        )
    jobs = store.list_index_jobs(branch=branch_name, statuses=["pending", "failed"], limit=20)
    payload["jobs"] = jobs
    payload["pending_jobs"] = len([item for item in jobs if item["status"] == "pending"])
    payload["failed_jobs"] = len([item for item in jobs if item["status"] == "failed"])
    details: list[str] = []
    status = "ok"
    if payload["failed_jobs"]:
        status = "warn"
        details.extend(
            f"failed job {item['job_id']}: {item.get('error') or 'unknown error'}"
            for item in jobs
            if item["status"] == "failed"
        )
    elif payload["pending_jobs"]:
        status = "warn"
        details.append(f"{payload['pending_jobs']} index job(s) are still pending")
    summary = "index queue is healthy"
    if status == "warn":
        summary = "index queue requires attention"
    return payload, _make_check("indexing", status, summary, details)


def _lease_diagnostics(project_path: Path, branch_name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    store = MemoryStore(project_path)
    payload = {
        "leases": [],
        "active": [],
        "expired": [],
    }
    if not store.paths.sqlite_file.exists():
        return (
            payload,
            _make_check(
                "writer_leases",
                "error",
                "writer leases cannot be inspected because SQLite is missing",
                [str(store.paths.sqlite_file.relative_to(project_path))],
            ),
        )
    all_leases = store.list_writer_leases()
    leases = [
        lease
        for lease in all_leases
        if lease["lease_name"].startswith(WRITER_LEASE_PREFIXES)
        and _lease_matches_branch(lease["lease_name"], branch_name)
    ]
    active = [lease for lease in leases if not lease["expired"]]
    expired = [lease for lease in leases if lease["expired"]]
    payload = {
        "leases": leases,
        "active": active,
        "expired": expired,
    }
    details: list[str] = []
    status = "ok"
    if active:
        details.extend(
            f"active lease: {lease['lease_name']} owner={lease['owner_id']}"
            for lease in active
        )
    if expired:
        status = "warn"
        details.extend(
            f"expired lease: {lease['lease_name']} owner={lease['owner_id']}"
            for lease in expired
        )
    summary = "writer lease state is healthy"
    if active:
        summary = "writer lease state includes active hot-scope locks"
    if expired:
        summary = "writer lease state includes expired hot-scope locks"
    return payload, _make_check("writer_leases", status, summary, details)


def _proposal_diagnostics(project_path: Path, branch_name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    store = MemoryStore(project_path)
    payload = {
        "pending_proposals": 0,
        "conflict_proposals": 0,
        "recent": [],
    }
    if not store.paths.sqlite_file.exists():
        return (
            payload,
            _make_check(
                "runtime_proposals",
                "error",
                "runtime proposals cannot be inspected because SQLite is missing",
                [str(store.paths.sqlite_file.relative_to(project_path))],
            ),
        )
    proposals = store.list_runtime_proposals(
        branch=branch_name,
        statuses=["pending", "conflict"],
        limit=20,
    )
    payload["recent"] = proposals
    payload["pending_proposals"] = len([item for item in proposals if item["status"] == "pending"])
    payload["conflict_proposals"] = len([item for item in proposals if item["status"] == "conflict"])
    details: list[str] = []
    status = "ok"
    if payload["conflict_proposals"]:
        status = "warn"
        details.append(f"{payload['conflict_proposals']} proposal(s) require conflict review")
    elif payload["pending_proposals"]:
        status = "warn"
        details.append(f"{payload['pending_proposals']} proposal(s) are pending apply")
    summary = "runtime proposals are healthy"
    if status == "warn":
        summary = "runtime proposals require operator attention"
    return payload, _make_check("runtime_proposals", status, summary, details)


def _lease_matches_branch(lease_name: str, branch_name: str) -> bool:
    if lease_name.startswith("plan-catalog:"):
        return lease_name == f"plan-catalog:{branch_name}"
    if lease_name.startswith(("implement-step:", "artifact:")):
        parts = lease_name.split(":", 2)
        return len(parts) == 3 and parts[1] == branch_name
    if lease_name.startswith("review:"):
        return lease_name == f"review:{branch_name}"
    if lease_name.startswith("security:"):
        return lease_name == f"security:{branch_name}"
    return False


def _make_check(name: str, status: str, summary: str, details: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "summary": summary,
        "details": details,
    }
