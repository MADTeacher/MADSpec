from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from madspec_cli.memory.shared.storage import get_memory_paths

if TYPE_CHECKING:
    from madspec_cli.shared.kernel.ports import BranchPolicyEvaluator
from madspec_cli.memory.shared.system_store.layout import get_system_memory_paths
from madspec_cli.memory.shared.system_store.store import MemoryStore
from madspec_cli.memory.shared.validation import validate_branch_memory
from madspec_cli.memory.shared.validation_views import validate_generated_stage_views
from madspec_cli.shared.kernel.result import PayloadResult

from .diagnostics_shared import overall_status
from .observability import build_runtime_observability

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
    "work_item_dependencies",
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


def execute(
    request: MemoryDoctorRequest,
    *,
    _evaluate_branch_policies: BranchPolicyEvaluator | None = None,
) -> MemoryDoctorResult:
    if _evaluate_branch_policies is None:
        from madspec_cli.features.policy.application.common import evaluate_branch_policies
        _evaluate_branch_policies = evaluate_branch_policies

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

    doctor_policy_payload = _evaluate_branch_policies(
        request.project_path,
        request.branch_name,
        stage=None,
        operation="validate",
        include_system_policies=False,
        create_policy_if_missing=False,
    )
    integrity_errors = validate_branch_memory(
        request.project_path, request.branch_name,
        policy_violations=doctor_policy_payload["violations"],
    )
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
    coordinator_payload, coordinator_check = _coordinator_diagnostics(request.project_path, request.branch_name)
    checks.append(coordinator_check)

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
    observability = build_runtime_observability(
        request.project_path,
        branch_name=request.branch_name,
        limit=10,
    )
    projection_health = observability["projection_health"]
    stale_projection_details = [item["summary"] for item in projection_health["stale_projections"][:10]]
    checks.append(
        _make_check(
            "stale_projections",
            "error" if stale_projection_details else "ok",
            "branch and generated projections match canonical runtime state"
            if not stale_projection_details
            else "some branch or generated projections are stale",
            stale_projection_details,
            probable_cause=(
                None if not stale_projection_details else "Canonical SQLite state diverged from rebuildable file or markdown projections."
            ),
            repair_hint=(
                None if not stale_projection_details else "Run memory consolidate or rebuild projections from SQLite before continuing."
            ),
        )
    )
    orphan_sessions = observability["orphan_sessions"]
    checks.append(
        _make_check(
            "orphan_sessions",
            "error" if orphan_sessions else "ok",
            "all session bindings resolve cleanly"
            if not orphan_sessions
            else "some session bindings point at missing or mismatched coordinator state",
            [f"{item['session_key']}: {', '.join(item['problems'])}" for item in orphan_sessions[:10]],
            probable_cause=(
                None if not orphan_sessions else "Session-local bindings no longer match active claims or referenced task/work-item state."
            ),
            repair_hint=(
                None if not orphan_sessions else "Clear stale bindings or reclaim the intended work item to restore ownership consistency."
            ),
        )
    )
    stuck_leases = observability["active_leases"]["stuck"]
    checks.append(
        _make_check(
            "stuck_leases",
            "warn" if stuck_leases else "ok",
            "no stuck writer leases detected"
            if not stuck_leases
            else "some leases look expired or orphaned",
            [f"{item['lease_name']} owner={item.get('owner_id')}" for item in stuck_leases[:10]],
            probable_cause=(
                None if not stuck_leases else "A previous writer likely failed to release a hot-scope lease cleanly."
            ),
            repair_hint=(
                None if not stuck_leases else "Wait for TTL expiry or inspect the owning session/process before retrying the blocked write."
            ),
        )
    )
    unresolved_proposal_conflicts = observability["proposal_state"]["unresolved"]
    checks.append(
        _make_check(
            "unresolved_proposal_conflicts",
            "warn" if unresolved_proposal_conflicts else "ok",
            "proposal queue has no unresolved conflicts"
            if not unresolved_proposal_conflicts
            else "some proposals still require operator review",
            [
                f"{item['proposal_id']}: status={item['status']} work_item={item['work_item_id']}"
                for item in unresolved_proposal_conflicts[:10]
            ],
            probable_cause=(
                None if not unresolved_proposal_conflicts else "Pending or conflicted proposals are blocking clean shared progress."
            ),
            repair_hint=(
                None if not unresolved_proposal_conflicts else "Preview the proposal, then apply a fresh one or resolve the conflicting runtime state."
            ),
        )
    )
    revision_drift = projection_health["revision_drift"]
    checks.append(
        _make_check(
            "revision_drift",
            "warn" if revision_drift else "ok",
            "file projections reflect the latest runtime revision"
            if not revision_drift
            else "some file projections lag behind the latest runtime revision",
            [item["summary"] for item in revision_drift[:10]],
            probable_cause=(
                None if not revision_drift else "Runtime revision advanced, but one or more projections were not refreshed successfully."
            ),
            repair_hint=(
                None if not revision_drift else "Rebuild projections from SQLite and re-run doctor to confirm drift is cleared."
            ),
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
            "coordinator": coordinator_payload,
            "observability": observability,
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


def _coordinator_diagnostics(project_path: Path, branch_name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    store = MemoryStore(project_path)
    payload = {
        "dangling_dependencies": [],
        "inconsistent_claims": [],
        "blocked_without_reasons": [],
    }
    if not store.paths.sqlite_file.exists():
        return (
            payload,
            _make_check(
                "coordinator",
                "error",
                "coordinator state cannot be inspected because SQLite is missing",
                [str(store.paths.sqlite_file.relative_to(project_path))],
            ),
        )
    work_items = store.list_work_items(branch=branch_name)
    work_items_by_id = {item["work_item_id"]: item for item in work_items}
    for edge in store.list_work_item_dependencies(branch=branch_name):
        if edge["work_item_id"] not in work_items_by_id or edge["depends_on_work_item_id"] not in work_items_by_id:
            payload["dangling_dependencies"].append(edge)
    for item in work_items:
        claim = store.fetch_active_claim_for_work_item(work_item_id=item["work_item_id"])
        if claim is None:
            continue
        if item.get("session_key") != claim.get("session_key") or item.get("owner_id") != claim.get("owner_id"):
            payload["inconsistent_claims"].append(
                {
                    "work_item_id": item["work_item_id"],
                    "work_item_session_key": item.get("session_key"),
                    "claim_session_key": claim.get("session_key"),
                    "work_item_owner_id": item.get("owner_id"),
                    "claim_owner_id": claim.get("owner_id"),
                }
            )
    for item in work_items:
        explanation = store.explain_work_item(branch=branch_name, work_item_id=item["work_item_id"], session_key=item.get("session_key"))
        if explanation is None:
            continue
        readiness = explanation.get("readiness") or {}
        if readiness.get("status") == "blocked" and not readiness.get("blocked_reasons"):
            payload["blocked_without_reasons"].append({"work_item_id": item["work_item_id"]})
    details: list[str] = []
    status = "ok"
    if payload["dangling_dependencies"]:
        status = "error"
        details.extend(
            f"dangling dependency: {item['work_item_id']} -> {item['depends_on_work_item_id']}"
            for item in payload["dangling_dependencies"]
        )
    if payload["inconsistent_claims"]:
        status = "error"
        details.extend(
            f"inconsistent claim: {item['work_item_id']} work_item_session={item['work_item_session_key']} claim_session={item['claim_session_key']}"
            for item in payload["inconsistent_claims"]
        )
    if payload["blocked_without_reasons"]:
        status = "warn" if status != "error" else status
        details.extend(
            f"blocked work item without explanation: {item['work_item_id']}"
            for item in payload["blocked_without_reasons"]
        )
    summary = "coordinator state is healthy"
    if status == "warn":
        summary = "coordinator state requires explanation cleanup"
    elif status == "error":
        summary = "coordinator state has integrity problems"
    return payload, _make_check("coordinator", status, summary, details)


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


def _make_check(
    name: str,
    status: str,
    summary: str,
    details: list[str],
    *,
    probable_cause: str | None = None,
    repair_hint: str | None = None,
) -> dict[str, Any]:
    payload = {
        "name": name,
        "status": status,
        "summary": summary,
        "details": details,
    }
    if probable_cause is not None:
        payload["probable_cause"] = probable_cause
    if repair_hint is not None:
        payload["repair_hint"] = repair_hint
    return payload
