from __future__ import annotations

import json
from typing import Any

from .db import StoreComponent
from .jobs import log_retrieval_run, process_pending_jobs
from .layout import VectorNamespace
from .text import (
    _content_hash,
    _matches_scope,
    _normalized_optional_text,
    _snippet,
    _status_allowed,
    _tokenize,
)
from .vector import BaseEmbeddingProvider, VectorMemoryIndex


class IndexStore(StoreComponent):
    def __init__(self, db, *, runtime_store) -> None:
        super().__init__(db)
        self.runtime = runtime_store

    def fetch_record(self, record_id: str) -> dict[str, Any] | None:
        return self.runtime.fetch_record(record_id)

    def fetch_snapshot(self, branch: str, snapshot_key: str) -> dict[str, Any] | None:
        return self.runtime.fetch_snapshot(branch, snapshot_key)

    def upsert_artifact(
        self,
        *,
        artifact_id: str,
        branch: str,
        stage: str | None,
        path: str,
        content: str,
        updated_at: str,
    ) -> None:
        with self.connect() as conn:
            self._upsert_artifact(
                conn,
                artifact_id=artifact_id,
                branch=branch,
                stage=stage,
                path=path,
                content=content,
                updated_at=updated_at,
            )

    def _upsert_artifact(
        self,
        conn,
        *,
        artifact_id: str,
        branch: str,
        stage: str | None,
        path: str,
        content: str,
        updated_at: str,
    ) -> None:
        search_text = content
        content_hash = _content_hash(content)
        conn.execute(
            """
            INSERT INTO artifacts (
                artifact_id, branch, stage, path, content, search_text, updated_at, content_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(artifact_id) DO UPDATE SET
                branch=excluded.branch,
                stage=excluded.stage,
                path=excluded.path,
                content=excluded.content,
                search_text=excluded.search_text,
                updated_at=excluded.updated_at,
                content_hash=excluded.content_hash
            """,
            (
                artifact_id,
                branch,
                stage,
                path,
                content,
                search_text,
                updated_at,
                content_hash,
            ),
        )
        self._upsert_fts_row(
            conn,
            table_name="artifacts_fts",
            columns=("row_id", "artifact_id", "branch", "stage", "path", "content"),
            values=(artifact_id, artifact_id, branch, stage or "", path, search_text),
        )
        self._enqueue_index_job(
            conn,
            source_type="artifact",
            source_id=artifact_id,
            branch=branch,
            stage=stage,
            step_id=None,
            content_hash=content_hash,
        )

    def exact_search(
        self,
        query: str,
        *,
        branch: str,
        stage: str | None,
        step_id: str | None,
        scope: str,
        limit: int,
        include_obsolete: bool,
        include_conflicted: bool,
    ) -> list[dict[str, Any]]:
        like = f"%{query.lower()}%"
        results: list[dict[str, Any]] = []
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT 'record' AS source_type, record_id AS source_id, branch, stage, step_id,
                       scope, status, kind, summary, search_text, content_hash, ts
                FROM records
                WHERE lower(search_text) LIKE ?
                ORDER BY ts DESC
                LIMIT ?
                """,
                (like, limit * 4),
            ).fetchall()
            rows = list(rows) + conn.execute(
                """
                SELECT 'snapshot' AS source_type, branch || ':' || snapshot_key AS source_id, branch, stage,
                       NULL AS step_id, 'branch' AS scope, 'validated' AS status, 'snapshot' AS kind,
                       COALESCE(summary, snapshot_key) AS summary, search_text, content_hash, updated_at AS ts
                FROM stage_snapshots
                WHERE lower(search_text) LIKE ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (like, limit * 2),
            ).fetchall()
            rows = rows + conn.execute(
                """
                SELECT 'artifact' AS source_type, artifact_id AS source_id, branch, stage,
                       NULL AS step_id, 'branch' AS scope, 'validated' AS status, 'artifact' AS kind,
                       path AS summary, search_text, content_hash, updated_at AS ts
                FROM artifacts
                WHERE lower(search_text) LIKE ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (like, limit * 2),
            ).fetchall()
        for row in rows:
            item = self._search_item_from_row(dict(row))
            if not _matches_scope(
                row_branch=item["branch"],
                row_stage=item.get("stage"),
                row_step_id=item.get("step_id"),
                branch=branch,
                stage=stage,
                step_id=step_id,
                scope=scope,
            ):
                continue
            if not _status_allowed(
                item.get("status"),
                include_obsolete=include_obsolete,
                include_conflicted=include_conflicted,
            ):
                continue
            item["match_type"] = "exact"
            results.append(item)
        return _dedupe_search_items(results)[:limit]

    def lexical_search(
        self,
        query: str,
        *,
        branch: str,
        stage: str | None,
        step_id: str | None,
        scope: str,
        limit: int,
        include_obsolete: bool,
        include_conflicted: bool,
    ) -> list[dict[str, Any]]:
        sanitized = " OR ".join(_tokenize(query))
        if not sanitized:
            return []
        results: list[dict[str, Any]] = []
        with self.connect() as conn:
            tables = (
                (
                    "records_fts",
                    "SELECT record_id AS source_id, branch, stage, step_id, scope, status, kind, content FROM records_fts WHERE records_fts MATCH ? LIMIT ?",
                    "record",
                ),
                (
                    "stage_snapshots_fts",
                    "SELECT branch || ':' || snapshot_key AS source_id, branch, stage, NULL AS step_id, 'branch' AS scope, 'validated' AS status, 'snapshot' AS kind, content FROM stage_snapshots_fts WHERE stage_snapshots_fts MATCH ? LIMIT ?",
                    "snapshot",
                ),
                (
                    "artifacts_fts",
                    "SELECT artifact_id AS source_id, branch, stage, NULL AS step_id, 'branch' AS scope, 'validated' AS status, 'artifact' AS kind, content FROM artifacts_fts WHERE artifacts_fts MATCH ? LIMIT ?",
                    "artifact",
                ),
            )
            for table_name, sql, source_type in tables:
                if not self._fts_exists(conn, table_name):
                    continue
                for row in conn.execute(sql, (sanitized, limit * 3)).fetchall():
                    item = self._search_item_from_row({**dict(row), "source_type": source_type})
                    if not _matches_scope(
                        row_branch=item["branch"],
                        row_stage=item.get("stage"),
                        row_step_id=item.get("step_id"),
                        branch=branch,
                        stage=stage,
                        step_id=step_id,
                        scope=scope,
                    ):
                        continue
                    if not _status_allowed(
                        item.get("status"),
                        include_obsolete=include_obsolete,
                        include_conflicted=include_conflicted,
                    ):
                        continue
                    item["match_type"] = "lexical"
                    results.append(item)
        return _dedupe_search_items(results)[:limit]

    def fetch_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def upsert_artifacts_batch(self, *, branch: str, artifacts: list[dict[str, Any]]) -> None:
        if not artifacts:
            return
        with self.connect() as conn:
            for artifact in artifacts:
                self._upsert_artifact(
                    conn,
                    artifact_id=str(artifact["artifact_id"]),
                    branch=branch,
                    stage=_normalized_optional_text(artifact.get("stage")),
                    path=str(artifact["path"]),
                    content=str(artifact["content"]),
                    updated_at=str(artifact["updated_at"]),
                )

    def list_retrieval_runs(
        self,
        *,
        branch: str | None = None,
        stage: str | None = None,
        step_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses = ["1 = 1"]
        params: list[Any] = []
        if branch is not None:
            clauses.append("branch = ?")
            params.append(branch)
        if stage is not None:
            clauses.append("stage = ?")
            params.append(stage)
        if step_id is not None:
            clauses.append("step_id = ?")
            params.append(step_id)
        with self.connect_read_only() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM retrieval_runs
                WHERE {' AND '.join(clauses)}
                ORDER BY created_at DESC, run_id DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            triggers = json.loads(row["triggers_json"]) if row["triggers_json"] else []
            items.append(
                {
                    "run_id": row["run_id"],
                    "branch": row["branch"],
                    "stage": row["stage"],
                    "step_id": row["step_id"],
                    "query": row["query"],
                    "semantic_enabled": bool(row["semantic_enabled"]),
                    "triggers": triggers,
                    "exact_count": row["exact_count"],
                    "lexical_count": row["lexical_count"],
                    "semantic_count": row["semantic_count"],
                    "merged_count": row["merged_count"],
                    "provider": row["provider"] if "provider" in row.keys() else None,
                    "model": row["model"] if "model" in row.keys() else None,
                    "revision": row["revision"] if "revision" in row.keys() else None,
                    "dimension": row["dimension"] if "dimension" in row.keys() else None,
                    "namespace_path": row["namespace_path"] if "namespace_path" in row.keys() else None,
                    "bootstrap_status": row["bootstrap_status"] if "bootstrap_status" in row.keys() else None,
                    "semantic_outcome": row["semantic_outcome"] if "semantic_outcome" in row.keys() else None,
                    "error_kind": row["error_kind"] if "error_kind" in row.keys() else None,
                    "error_message": row["error_message"] if "error_message" in row.keys() else None,
                    "created_at": row["created_at"],
                }
            )
        return items

    def list_index_jobs(
        self,
        *,
        branch: str | None = None,
        source_type: str | None = None,
        source_id: str | None = None,
        statuses: list[str] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses = ["1 = 1"]
        params: list[Any] = []
        if branch is not None:
            clauses.append("branch = ?")
            params.append(branch)
        if source_type is not None:
            clauses.append("source_type = ?")
            params.append(source_type)
        if source_id is not None:
            clauses.append("source_id = ?")
            params.append(source_id)
        if statuses:
            placeholders = ", ".join("?" for _ in statuses)
            clauses.append(f"status IN ({placeholders})")
            params.extend(statuses)
        with self.connect_read_only() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM index_jobs
                WHERE {' AND '.join(clauses)}
                ORDER BY updated_at DESC, job_id DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def describe_vector_index(self, *, provider: BaseEmbeddingProvider | None = None) -> dict[str, Any]:
        namespace = self.paths.active_vector_namespace
        index = VectorMemoryIndex(
            namespace.namespace_dir,
            provider=provider,
            provider_kind=namespace.provider,
            model_key=namespace.model,
            revision=namespace.revision,
            dimension=namespace.dimension,
        )
        description = index.describe()
        description["vector_root_dir"] = str(self.paths.vector_root_dir.relative_to(self.project_path))
        description["active_vector_namespace"] = namespace.relative_namespace(self.project_path)
        description["memory_chunk_count"] = index.count_chunks("memory_chunks")
        description["artifact_chunk_count"] = index.count_chunks("artifact_chunks")
        return description

    def describe_record_index(
        self,
        record_id: str,
        *,
        provider: BaseEmbeddingProvider | None = None,
    ) -> dict[str, Any]:
        jobs = self.list_index_jobs(source_type="record", source_id=record_id, limit=20)
        namespace = self.paths.active_vector_namespace
        index = VectorMemoryIndex(
            namespace.namespace_dir,
            provider=provider,
            provider_kind=namespace.provider,
            model_key=namespace.model,
            revision=namespace.revision,
            dimension=namespace.dimension,
        )
        memory_chunks = index.count_source_chunks(
            "memory_chunks",
            source_type="record",
            source_id=record_id,
        )
        latest_job = jobs[0] if jobs else None
        return {
            "jobs": jobs,
            "memory_chunk_count": memory_chunks,
            "artifact_chunk_count": 0,
            "is_indexed": memory_chunks > 0 or bool(latest_job and latest_job["status"] == "indexed"),
            "latest_job": latest_job,
        }

    def process_pending_jobs(
        self,
        *,
        branch: str | None = None,
        limit: int = 100,
        provider: BaseEmbeddingProvider | None = None,
        namespace: VectorNamespace | None = None,
        rebuild: bool = False,
    ) -> dict[str, Any]:
        return process_pending_jobs(
            self,
            branch=branch,
            limit=limit,
            provider=provider,
            namespace=namespace,
            rebuild=rebuild,
        )

    def log_retrieval_run(
        self,
        *,
        branch: str,
        stage: str,
        step_id: str | None,
        query: str | None,
        semantic_enabled: bool,
        triggers: list[str],
        exact_count: int,
        lexical_count: int,
        semantic_count: int,
        merged_count: int,
        provider: str | None,
        model: str | None,
        revision: str | None,
        dimension: int | None,
        namespace_path: str | None,
        bootstrap_status: str | None,
        semantic_outcome: str | None,
        error_kind: str | None,
        error_message: str | None,
    ) -> None:
        log_retrieval_run(
            self,
            branch=branch,
            stage=stage,
            step_id=step_id,
            query=query,
            semantic_enabled=semantic_enabled,
            triggers=triggers,
            exact_count=exact_count,
            lexical_count=lexical_count,
            semantic_count=semantic_count,
            merged_count=merged_count,
            provider=provider,
            model=model,
            revision=revision,
            dimension=dimension,
            namespace_path=namespace_path,
            bootstrap_status=bootstrap_status,
            semantic_outcome=semantic_outcome,
            error_kind=error_kind,
            error_message=error_message,
        )

    def _search_item_from_row(self, row: dict[str, Any]) -> dict[str, Any]:
        text = row.get("search_text") or row.get("content") or row.get("summary") or ""
        summary = row.get("summary") or row.get("kind") or row.get("source_id")
        return {
            "source_type": row["source_type"],
            "source_id": row["source_id"],
            "branch": row.get("branch"),
            "stage": row.get("stage"),
            "step_id": row.get("step_id"),
            "scope": row.get("scope"),
            "status": row.get("status"),
            "kind": row.get("kind"),
            "summary": summary,
            "snippet": _snippet(text),
            "content_hash": row.get("content_hash"),
            "ts": row.get("ts"),
        }


def _dedupe_search_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for item in items:
        key = (item["source_type"], item["source_id"])
        if key not in unique:
            unique[key] = item
    return list(unique.values())


__all__ = ["IndexStore"]
