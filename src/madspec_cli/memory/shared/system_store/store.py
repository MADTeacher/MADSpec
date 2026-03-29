from __future__ import annotations

from pathlib import Path
from typing import Any

from .db import SystemStoreDB
from .index_store import IndexStore
from .layout import build_reindex_status, list_vector_namespaces
from .proposal_store import ProposalStore
from .runtime_store import RuntimeStore
from .task_store import TaskStore
from .vector import BaseEmbeddingProvider, VectorMemoryIndex


class MemoryStore:
    def __init__(self, project_path: Path) -> None:
        self.project_path = project_path
        self.db = SystemStoreDB(project_path)
        self._runtime: RuntimeStore | None = None
        self._proposals: ProposalStore | None = None
        self._tasks: TaskStore | None = None
        self._index: IndexStore | None = None

    @property
    def paths(self):
        return self.db.paths

    @property
    def runtime(self) -> RuntimeStore:
        if self._runtime is None:
            self._runtime = RuntimeStore(self.db)
        return self._runtime

    @property
    def proposals(self) -> ProposalStore:
        if self._proposals is None:
            self._proposals = ProposalStore(self.db)
        return self._proposals

    @property
    def tasks(self) -> TaskStore:
        if self._tasks is None:
            self._tasks = TaskStore(
                self.db,
                runtime_store=self.runtime,
                proposal_store=self.proposals,
            )
        return self._tasks

    @property
    def index(self) -> IndexStore:
        if self._index is None:
            self._index = IndexStore(self.db, runtime_store=self.runtime)
        return self._index

    def __getattr__(self, name: str) -> Any:
        for component in (self.runtime, self.tasks, self.proposals, self.index, self.db):
            if hasattr(component, name):
                return getattr(component, name)
        raise AttributeError(f"{type(self).__name__!s} has no attribute {name!r}")

    def commit_runtime_mutation(
        self,
        *,
        branch: str,
        stage_snapshots: list[dict[str, Any]],
        sessions: list[dict[str, Any]],
        records: list[dict[str, Any]],
        work_items: list[dict[str, Any]],
        artifacts: list[dict[str, Any]],
        branch_revision_after: int,
        conn=None,
    ) -> None:
        if conn is not None:
            self._commit_runtime_mutation(
                conn,
                branch=branch,
                stage_snapshots=stage_snapshots,
                sessions=sessions,
                records=records,
                work_items=work_items,
                artifacts=artifacts,
                branch_revision_after=branch_revision_after,
            )
            return
        with self.connect() as managed_conn:
            managed_conn.execute("BEGIN IMMEDIATE")
            self._commit_runtime_mutation(
                managed_conn,
                branch=branch,
                stage_snapshots=stage_snapshots,
                sessions=sessions,
                records=records,
                work_items=work_items,
                artifacts=artifacts,
                branch_revision_after=branch_revision_after,
            )

    def _commit_runtime_mutation(
        self,
        conn,
        *,
        branch: str,
        stage_snapshots: list[dict[str, Any]],
        sessions: list[dict[str, Any]],
        records: list[dict[str, Any]],
        work_items: list[dict[str, Any]],
        artifacts: list[dict[str, Any]],
        branch_revision_after: int,
    ) -> None:
        for snapshot in stage_snapshots:
            self.runtime._upsert_stage_snapshot(
                conn,
                branch=branch,
                snapshot_key=str(snapshot["snapshot_key"]),
                payload=dict(snapshot["payload"]),
                source_path=str(snapshot["source_path"]),
            )
        for session in sessions:
            self.runtime._upsert_session(
                conn,
                branch=branch,
                session_key=str(session["session_key"]),
                payload=dict(session["payload"]),
            )
        for artifact in artifacts:
            payload = dict(artifact)
            self.index._upsert_artifact(
                conn,
                artifact_id=str(payload["artifact_id"]),
                branch=branch,
                stage=payload.get("stage"),
                path=str(payload["path"]),
                content=str(payload["content"]),
                updated_at=str(payload["updated_at"]),
            )
        touched_tasks: set[str] = set()
        for work_item in work_items:
            payload = dict(work_item)
            self.tasks._upsert_work_item(conn, payload)
            touched_tasks.add(str(payload["task_id"]))
        for record in records:
            self.runtime._upsert_record(conn, dict(record))
        for task_id in touched_tasks:
            self.tasks._recompute_task_status(conn, task_id=task_id)
        self.runtime._update_branch_revision(conn, branch=branch, revision=branch_revision_after)

    def purge_branch(self, branch: str, *, include_artifacts: bool = True) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM records WHERE branch = ?", (branch,))
            conn.execute("DELETE FROM stage_snapshots WHERE branch = ?", (branch,))
            conn.execute("DELETE FROM sessions WHERE branch = ?", (branch,))
            conn.execute("DELETE FROM index_jobs WHERE branch = ?", (branch,))
            conn.execute("DELETE FROM runtime_proposal_events WHERE branch = ?", (branch,))
            conn.execute("DELETE FROM runtime_proposals WHERE branch = ?", (branch,))
            if include_artifacts:
                conn.execute("DELETE FROM artifacts WHERE branch = ?", (branch,))
            if self.db._fts_exists(conn, "records_fts"):
                conn.execute("DELETE FROM records_fts WHERE branch = ?", (branch,))
            if self.db._fts_exists(conn, "stage_snapshots_fts"):
                conn.execute("DELETE FROM stage_snapshots_fts WHERE branch = ?", (branch,))
            if include_artifacts and self.db._fts_exists(conn, "artifacts_fts"):
                conn.execute("DELETE FROM artifacts_fts WHERE branch = ?", (branch,))

    def list_tables(self) -> list[str]:
        with self.connect_read_only() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY name"
            ).fetchall()
        return [row["name"] for row in rows]

    def describe_status(self, branch: str | None = None) -> dict[str, Any]:
        filters = ""
        params: list[Any] = []
        if branch:
            filters = " WHERE branch = ?"
            params.append(branch)
        with self.connect() as conn:
            records_count = conn.execute(
                f"SELECT COUNT(*) FROM records{filters}",
                params,
            ).fetchone()[0]
            snapshots_count = conn.execute(
                f"SELECT COUNT(*) FROM stage_snapshots{filters}",
                params,
            ).fetchone()[0]
            sessions_count = conn.execute(
                f"SELECT COUNT(*) FROM sessions{filters}",
                params,
            ).fetchone()[0]
            artifacts_count = conn.execute(
                f"SELECT COUNT(*) FROM artifacts{filters}",
                params,
            ).fetchone()[0]
            pending_jobs = conn.execute(
                "SELECT COUNT(*) FROM index_jobs WHERE status IN ('pending', 'failed')"
                + (" AND branch = ?" if branch else ""),
                params,
            ).fetchone()[0]
            indexed_jobs = conn.execute(
                "SELECT COUNT(*) FROM index_jobs WHERE status = 'indexed'"
                + (" AND branch = ?" if branch else ""),
                params,
            ).fetchone()[0]
            branch_revision = self.runtime._fetch_branch_revision(conn, branch) if branch else None
        namespace = self.paths.active_vector_namespace
        known_namespaces = [
            item.to_payload(self.project_path)
            for item in list_vector_namespaces(self.project_path, root_dir=self.paths.vector_root_dir)
        ]
        index_state = build_reindex_status(self.project_path)
        return {
            "sqlite_path": str(self.paths.sqlite_file.relative_to(self.project_path)),
            "vector_dir": str(self.paths.active_vector_namespace_dir.relative_to(self.project_path)),
            "vector_root_dir": str(self.paths.vector_root_dir.relative_to(self.project_path)),
            "active_vector_namespace": namespace.relative_namespace(self.project_path),
            "active_vector_provider": namespace.provider,
            "active_vector_model": namespace.model,
            "active_vector_revision": namespace.revision,
            "active_vector_dimension": namespace.dimension,
            "known_vector_namespaces": known_namespaces,
            "schema_version_path": str(self.paths.schema_version.relative_to(self.project_path)),
            "records": records_count,
            "stage_snapshots": snapshots_count,
            "sessions": sessions_count,
            "artifacts": artifacts_count,
            "pending_index_jobs": pending_jobs,
            "indexed_jobs": indexed_jobs,
            "vector_backend": VectorMemoryIndex(
                self.paths.active_vector_namespace_dir,
                provider_kind=namespace.provider,
                model_key=namespace.model,
                revision=namespace.revision,
                dimension=namespace.dimension,
            ).backend_name,
            "runtime_revision": branch_revision,
            "index_state": index_state,
        }


__all__ = ["MemoryStore", "BaseEmbeddingProvider"]
