from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from .leases import normalize_writer_lease_row
from .constants import LEASE_TTL_SECONDS
from .layout import get_system_memory_paths
from .text import (
    _content_hash,
    _dump_json,
    _flatten_for_search,
    _matches_scope,
    _normalized_optional_text,
    _now_iso,
    _record_search_text,
    _snapshot_stage,
    _snapshot_summary,
    _snippet,
    _status_allowed,
    _tokenize,
)
from .vector import VectorMemoryIndex

_SEMANTIC_RECORD_STREAMS = {
    "fact": "facts",
    "decision": "decisions",
    "contract": "contracts",
}


def _infer_record_stream(record: dict[str, Any]) -> str:
    explicit = _normalized_optional_text(record.get("record_stream"))
    if explicit:
        return explicit

    semantic_kind = _normalized_optional_text(record.get("semantic_kind"))
    if semantic_kind in _SEMANTIC_RECORD_STREAMS:
        return _SEMANTIC_RECORD_STREAMS[semantic_kind]

    source = str(record.get("source") or "")
    if source.startswith("memory.start-step") or source.startswith("memory.checkpoint-step") or source.startswith("memory.complete-step"):
        return "events"
    return "decision_log"


class MemoryStore:
    def __init__(self, project_path: Path) -> None:
        self.project_path = project_path
        self.paths = get_system_memory_paths(project_path)

    def ensure_schema(self) -> None:
        self.paths.memory_dir.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS records (
                    record_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    semantic_kind TEXT,
                    record_stream TEXT,
                    scope TEXT,
                    branch TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    step_id TEXT,
                    status TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    summary TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    search_text TEXT NOT NULL,
                    source TEXT,
                    ts TEXT NOT NULL,
                    content_hash TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS stage_snapshots (
                    snapshot_key TEXT NOT NULL,
                    branch TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    summary TEXT,
                    payload_json TEXT NOT NULL,
                    search_text TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    PRIMARY KEY (snapshot_key, branch)
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    session_key TEXT NOT NULL,
                    branch TEXT NOT NULL,
                    stage TEXT,
                    current_step TEXT,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    PRIMARY KEY (session_key, branch)
                );

                CREATE TABLE IF NOT EXISTS branch_runtime_state (
                    branch TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    branch TEXT NOT NULL,
                    stage TEXT,
                    path TEXT NOT NULL,
                    content TEXT NOT NULL,
                    search_text TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    content_hash TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS index_jobs (
                    job_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    branch TEXT NOT NULL,
                    stage TEXT,
                    step_id TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    content_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (source_type, source_id, content_hash)
                );

                CREATE TABLE IF NOT EXISTS writer_leases (
                    lease_name TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    expires_at INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS retrieval_runs (
                    run_id TEXT PRIMARY KEY,
                    branch TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    step_id TEXT,
                    query TEXT,
                    semantic_enabled INTEGER NOT NULL,
                    triggers_json TEXT NOT NULL,
                    exact_count INTEGER NOT NULL,
                    lexical_count INTEGER NOT NULL,
                    semantic_count INTEGER NOT NULL,
                    merged_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS merge_proposals (
                    proposal_id TEXT PRIMARY KEY,
                    source_branch TEXT NOT NULL,
                    target_branch TEXT NOT NULL,
                    base_branch TEXT,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    applied_at TEXT
                );

                CREATE TABLE IF NOT EXISTS merge_history (
                    event_id TEXT PRIMARY KEY,
                    proposal_id TEXT,
                    source_branch TEXT NOT NULL,
                    target_branch TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    ts TEXT NOT NULL
                );
                """
            )
            self._ensure_schema_migrations(conn)
            self._ensure_fts_tables(conn)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.paths.sqlite_file)
        conn.row_factory = sqlite3.Row
        return conn

    def connect_read_only(self) -> sqlite3.Connection:
        if not self.paths.sqlite_file.exists():
            raise FileNotFoundError(self.paths.sqlite_file)
        conn = sqlite3.connect(f"file:{self.paths.sqlite_file}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def upsert_record(self, record: dict[str, Any]) -> None:
        with self.connect() as conn:
            self._upsert_record(conn, record)

    def ensure_branch_runtime_state(self, branch: str, *, conn: sqlite3.Connection | None = None) -> int:
        if conn is not None:
            return self._ensure_branch_runtime_state(conn, branch)
        with self.connect() as managed_conn:
            return self._ensure_branch_runtime_state(managed_conn, branch)

    def _ensure_branch_runtime_state(self, conn: sqlite3.Connection, branch: str) -> int:
        row = conn.execute(
            """
            SELECT revision
            FROM branch_runtime_state
            WHERE branch = ?
            """,
            (branch,),
        ).fetchone()
        if row is not None:
            return int(row["revision"])
        now = _now_iso()
        conn.execute(
            """
            INSERT INTO branch_runtime_state (branch, revision, updated_at)
            VALUES (?, 0, ?)
            """,
            (branch, now),
        )
        return 0

    def fetch_branch_revision(self, branch: str, *, conn: sqlite3.Connection | None = None) -> int:
        if conn is not None:
            return self._fetch_branch_revision(conn, branch)
        with self.connect() as managed_conn:
            return self._fetch_branch_revision(managed_conn, branch)

    def _fetch_branch_revision(self, conn: sqlite3.Connection, branch: str) -> int:
        return self._ensure_branch_runtime_state(conn, branch)

    def update_branch_revision(
        self,
        branch: str,
        *,
        revision: int,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        if conn is not None:
            self._update_branch_revision(conn, branch=branch, revision=revision)
            return
        with self.connect() as managed_conn:
            self._update_branch_revision(managed_conn, branch=branch, revision=revision)

    def _update_branch_revision(
        self,
        conn: sqlite3.Connection,
        *,
        branch: str,
        revision: int,
    ) -> None:
        self._ensure_branch_runtime_state(conn, branch)
        conn.execute(
            """
            UPDATE branch_runtime_state
            SET revision = ?, updated_at = ?
            WHERE branch = ?
            """,
            (revision, _now_iso(), branch),
        )

    def _upsert_record(self, conn: sqlite3.Connection, record: dict[str, Any]) -> None:
        payload_json = _dump_json(record)
        search_text = _record_search_text(record)
        content_hash = _content_hash(payload_json)
        kind = str(record.get("semantic_kind") or record.get("record_type") or "event")
        record_id = str(record.get("id") or uuid.uuid4())
        record_stream = _infer_record_stream(record)
        branch = str(record.get("branch") or "")
        stage = str(record.get("stage") or "")
        step_id = _normalized_optional_text(record.get("step_id"))
        status = str(record.get("status") or "proposed")
        scope = _normalized_optional_text(record.get("scope")) or "branch"
        ts = str(record.get("ts") or "")
        summary = str(record.get("summary") or "")
        source = _normalized_optional_text(record.get("source"))
        semantic_kind = _normalized_optional_text(record.get("semantic_kind"))
        conn.execute(
            """
            INSERT INTO records (
                record_id, kind, semantic_kind, record_stream, scope, branch, stage, step_id,
                status, version, summary, payload_json, search_text, source, ts, content_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(record_id) DO UPDATE SET
                kind=excluded.kind,
                semantic_kind=excluded.semantic_kind,
                record_stream=excluded.record_stream,
                scope=excluded.scope,
                branch=excluded.branch,
                stage=excluded.stage,
                step_id=excluded.step_id,
                status=excluded.status,
                summary=excluded.summary,
                payload_json=excluded.payload_json,
                search_text=excluded.search_text,
                source=excluded.source,
                ts=excluded.ts,
                content_hash=excluded.content_hash
            """,
            (
                record_id,
                kind,
                semantic_kind,
                record_stream,
                scope,
                branch,
                stage,
                step_id,
                status,
                int(record.get("version") or 1),
                summary,
                payload_json,
                search_text,
                source,
                ts,
                content_hash,
            ),
        )
        self._upsert_fts_row(
            conn,
            table_name="records_fts",
            columns=(
                "row_id",
                "record_id",
                "branch",
                "stage",
                "step_id",
                "scope",
                "status",
                "kind",
                "content",
            ),
            values=(
                record_id,
                record_id,
                branch,
                stage,
                step_id or "",
                scope,
                status,
                kind,
                search_text,
            ),
        )
        self._enqueue_index_job(
            conn,
            source_type="record",
            source_id=record_id,
            branch=branch,
            stage=stage,
            step_id=step_id,
            content_hash=content_hash,
        )

    def upsert_stage_snapshot(
        self,
        *,
        branch: str,
        snapshot_key: str,
        payload: dict[str, Any],
        source_path: str,
    ) -> None:
        with self.connect() as conn:
            self._upsert_stage_snapshot(
                conn,
                branch=branch,
                snapshot_key=snapshot_key,
                payload=payload,
                source_path=source_path,
            )

    def _upsert_stage_snapshot(
        self,
        conn: sqlite3.Connection,
        *,
        branch: str,
        snapshot_key: str,
        payload: dict[str, Any],
        source_path: str,
    ) -> None:
        payload_json = _dump_json(payload)
        search_text = _flatten_for_search(payload)
        content_hash = _content_hash(payload_json)
        summary = _snapshot_summary(snapshot_key, payload)
        updated_at = str(
            payload.get("updatedAt")
            or payload.get("ratifiedAt")
            or payload.get("updated_at")
            or ""
        )
        stage = _snapshot_stage(snapshot_key)
        conn.execute(
            """
            INSERT INTO stage_snapshots (
                snapshot_key, branch, stage, version, summary, payload_json, search_text,
                source_path, updated_at, content_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(snapshot_key, branch) DO UPDATE SET
                stage=excluded.stage,
                summary=excluded.summary,
                payload_json=excluded.payload_json,
                search_text=excluded.search_text,
                source_path=excluded.source_path,
                updated_at=excluded.updated_at,
                content_hash=excluded.content_hash
            """,
            (
                snapshot_key,
                branch,
                stage,
                int(payload.get("revision") or payload.get("version") or 1),
                summary,
                payload_json,
                search_text,
                source_path,
                updated_at,
                content_hash,
            ),
        )
        self._upsert_fts_row(
            conn,
            table_name="stage_snapshots_fts",
            columns=("row_id", "snapshot_key", "branch", "stage", "content"),
            values=(f"{branch}:{snapshot_key}", snapshot_key, branch, stage, search_text),
        )
        self._enqueue_index_job(
            conn,
            source_type="snapshot",
            source_id=f"{branch}:{snapshot_key}",
            branch=branch,
            stage=stage,
            step_id=None,
            content_hash=content_hash,
        )

    def upsert_session(self, *, branch: str, session_key: str, payload: dict[str, Any]) -> None:
        with self.connect() as conn:
            self._upsert_session(conn, branch=branch, session_key=session_key, payload=payload)

    def _upsert_session(
        self,
        conn: sqlite3.Connection,
        *,
        branch: str,
        session_key: str,
        payload: dict[str, Any],
    ) -> None:
        payload_json = _dump_json(payload)
        content_hash = _content_hash(payload_json)
        updated_at = str(payload.get("updated_at") or payload.get("last_checkpoint_at") or "")
        conn.execute(
            """
            INSERT INTO sessions (
                session_key, branch, stage, current_step, payload_json, updated_at, content_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_key, branch) DO UPDATE SET
                stage=excluded.stage,
                current_step=excluded.current_step,
                payload_json=excluded.payload_json,
                updated_at=excluded.updated_at,
                content_hash=excluded.content_hash
            """,
            (
                session_key,
                branch,
                _normalized_optional_text(payload.get("stage")),
                _normalized_optional_text(payload.get("current_step")),
                payload_json,
                updated_at,
                content_hash,
            ),
        )

    def fetch_session(self, *, branch: str, session_key: str) -> dict[str, Any] | None:
        with self.connect_read_only() as conn:
            row = conn.execute(
                """
                SELECT payload_json
                FROM sessions
                WHERE branch = ? AND session_key = ?
                """,
                (branch, session_key),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(row["payload_json"])
        if isinstance(payload, dict):
            return payload
        return None

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
        conn: sqlite3.Connection,
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

    def fetch_record(self, record_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM records WHERE record_id = ?",
                (record_id,),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(row["payload_json"])
        payload.setdefault("id", row["record_id"])
        payload.setdefault("kind", row["kind"])
        payload.setdefault("record_stream", row["record_stream"])
        payload.setdefault("content_hash", row["content_hash"])
        return payload

    def fetch_record_details(self, record_id: str) -> dict[str, Any] | None:
        with self.connect_read_only() as conn:
            row = conn.execute(
                "SELECT * FROM records WHERE record_id = ?",
                (record_id,),
            ).fetchone()
        if row is None:
            return None
        return self._record_details_from_row(dict(row))

    def fetch_snapshot(self, branch: str, snapshot_key: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM stage_snapshots WHERE branch = ? AND snapshot_key = ?",
                (branch, snapshot_key),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(row["payload_json"])
        payload["_snapshot_key"] = row["snapshot_key"]
        payload["_content_hash"] = row["content_hash"]
        payload["_stage"] = row["stage"]
        return payload

    def fetch_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    def branch_has_canonical_state(self, branch: str) -> bool:
        with self.connect_read_only() as conn:
            snapshot_count = conn.execute(
                "SELECT COUNT(*) FROM stage_snapshots WHERE branch = ?",
                (branch,),
            ).fetchone()[0]
            session_count = conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE branch = ?",
                (branch,),
            ).fetchone()[0]
            record_count = conn.execute(
                "SELECT COUNT(*) FROM records WHERE branch = ?",
                (branch,),
            ).fetchone()[0]
            artifact_count = conn.execute(
                "SELECT COUNT(*) FROM artifacts WHERE branch = ?",
                (branch,),
            ).fetchone()[0]
        return any((snapshot_count, session_count, record_count, artifact_count))

    def list_records(
        self,
        *,
        branch: str | None = None,
        stage: str | None = None,
        step_id: str | None = None,
        statuses: list[str] | None = None,
        record_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses = ["1 = 1"]
        params: list[Any] = []
        if record_id:
            clauses.append("record_id = ?")
            params.append(record_id)
        if branch is not None:
            clauses.append("branch = ?")
            params.append(branch)
        if stage is not None:
            clauses.append("stage = ?")
            params.append(stage)
        if step_id is not None:
            clauses.append("step_id = ?")
            params.append(step_id)
        if statuses:
            placeholders = ", ".join("?" for _ in statuses)
            clauses.append(f"status IN ({placeholders})")
            params.extend(statuses)
        with self.connect_read_only() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM records
                WHERE {' AND '.join(clauses)}
                ORDER BY ts DESC, record_id DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return [self._record_details_from_row(dict(row)) for row in rows]

    def list_records_by_stream(
        self,
        *,
        branch: str,
        record_stream: str,
        statuses: list[str] | None = None,
        stage: str | None = None,
        step_id: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        clauses = ["branch = ?", "record_stream = ?"]
        params: list[Any] = [branch, record_stream]
        if stage is not None:
            clauses.append("stage = ?")
            params.append(stage)
        if step_id is not None:
            clauses.append("step_id = ?")
            params.append(step_id)
        if statuses:
            placeholders = ", ".join("?" for _ in statuses)
            clauses.append(f"status IN ({placeholders})")
            params.extend(statuses)
        with self.connect_read_only() as conn:
            rows = conn.execute(
                f"""
                SELECT payload_json
                FROM records
                WHERE {' AND '.join(clauses)}
                ORDER BY ts ASC, record_id ASC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        payloads: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            if isinstance(payload, dict):
                payloads.append(payload)
        return payloads

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

    def commit_runtime_mutation(
        self,
        *,
        branch: str,
        stage_snapshots: list[dict[str, Any]],
        sessions: list[dict[str, Any]],
        records: list[dict[str, Any]],
        branch_revision_after: int,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        if conn is not None:
            self._commit_runtime_mutation(
                conn,
                branch=branch,
                stage_snapshots=stage_snapshots,
                sessions=sessions,
                records=records,
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
                branch_revision_after=branch_revision_after,
            )

    def _commit_runtime_mutation(
        self,
        conn: sqlite3.Connection,
        *,
        branch: str,
        stage_snapshots: list[dict[str, Any]],
        sessions: list[dict[str, Any]],
        records: list[dict[str, Any]],
        branch_revision_after: int,
    ) -> None:
        for snapshot in stage_snapshots:
            self._upsert_stage_snapshot(
                conn,
                branch=branch,
                snapshot_key=str(snapshot["snapshot_key"]),
                payload=dict(snapshot["payload"]),
                source_path=str(snapshot["source_path"]),
            )
        for session in sessions:
            self._upsert_session(
                conn,
                branch=branch,
                session_key=str(session["session_key"]),
                payload=dict(session["payload"]),
            )
        for record in records:
            self._upsert_record(conn, dict(record))
        self._update_branch_revision(conn, branch=branch, revision=branch_revision_after)

    def list_stage_snapshots(
        self,
        *,
        branch: str | None = None,
        stage: str | None = None,
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
        with self.connect_read_only() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM stage_snapshots
                WHERE {' AND '.join(clauses)}
                ORDER BY updated_at DESC, snapshot_key DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return [
            {
                "snapshot_key": row["snapshot_key"],
                "branch": row["branch"],
                "stage": row["stage"],
                "summary": row["summary"],
                "source_path": row["source_path"],
                "updated_at": row["updated_at"],
                "content_hash": row["content_hash"],
            }
            for row in rows
        ]

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

    def upsert_merge_proposal(self, proposal: dict[str, Any]) -> None:
        payload_json = _dump_json(proposal)
        content_hash = _content_hash(payload_json)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO merge_proposals (
                    proposal_id, source_branch, target_branch, base_branch, status,
                    payload_json, content_hash, created_at, updated_at, applied_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(proposal_id) DO UPDATE SET
                    source_branch=excluded.source_branch,
                    target_branch=excluded.target_branch,
                    base_branch=excluded.base_branch,
                    status=excluded.status,
                    payload_json=excluded.payload_json,
                    content_hash=excluded.content_hash,
                    created_at=excluded.created_at,
                    updated_at=excluded.updated_at,
                    applied_at=excluded.applied_at
                """,
                (
                    str(proposal.get("proposalId") or ""),
                    str(proposal.get("sourceBranch") or ""),
                    str(proposal.get("targetBranch") or ""),
                    _normalized_optional_text(proposal.get("baseBranch")),
                    str(proposal.get("status") or "pending"),
                    payload_json,
                    content_hash,
                    str(proposal.get("createdAt") or _now_iso()),
                    str(proposal.get("updatedAt") or _now_iso()),
                    _normalized_optional_text(proposal.get("appliedAt")),
                ),
            )

    def fetch_merge_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        with self.connect_read_only() as conn:
            row = conn.execute(
                "SELECT payload_json FROM merge_proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["payload_json"])

    def list_merge_proposals(
        self,
        *,
        source_branch: str | None = None,
        target_branch: str | None = None,
        statuses: list[str] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses = ["1 = 1"]
        params: list[Any] = []
        if source_branch is not None:
            clauses.append("source_branch = ?")
            params.append(source_branch)
        if target_branch is not None:
            clauses.append("target_branch = ?")
            params.append(target_branch)
        if statuses:
            placeholders = ", ".join("?" for _ in statuses)
            clauses.append(f"status IN ({placeholders})")
            params.extend(statuses)
        with self.connect_read_only() as conn:
            rows = conn.execute(
                f"""
                SELECT payload_json FROM merge_proposals
                WHERE {' AND '.join(clauses)}
                ORDER BY updated_at DESC, proposal_id DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def append_merge_history(self, event: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO merge_history (
                    event_id, proposal_id, source_branch, target_branch, event_type,
                    summary, payload_json, ts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(event.get("eventId") or ""),
                    _normalized_optional_text(event.get("proposalId")),
                    str(event.get("sourceBranch") or ""),
                    str(event.get("targetBranch") or ""),
                    str(event.get("eventType") or ""),
                    str(event.get("summary") or ""),
                    _dump_json(event.get("payload") or {}),
                    str(event.get("ts") or _now_iso()),
                ),
            )

    def list_merge_history(
        self,
        *,
        target_branch: str | None = None,
        proposal_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses = ["1 = 1"]
        params: list[Any] = []
        if target_branch is not None:
            clauses.append("target_branch = ?")
            params.append(target_branch)
        if proposal_id is not None:
            clauses.append("proposal_id = ?")
            params.append(proposal_id)
        with self.connect_read_only() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM merge_history
                WHERE {' AND '.join(clauses)}
                ORDER BY ts DESC, event_id DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            items.append(
                {
                    "eventId": row["event_id"],
                    "proposalId": row["proposal_id"],
                    "sourceBranch": row["source_branch"],
                    "targetBranch": row["target_branch"],
                    "eventType": row["event_type"],
                    "summary": row["summary"],
                    "payload": json.loads(row["payload_json"]),
                    "ts": row["ts"],
                }
            )
        return items

    def count_merge_events(self, *, target_branch: str, event_type: str | None = None) -> int:
        clauses = ["target_branch = ?"]
        params: list[Any] = [target_branch]
        if event_type is not None:
            clauses.append("event_type = ?")
            params.append(event_type)
        with self.connect_read_only() as conn:
            row = conn.execute(
                f"SELECT COUNT(*) AS count FROM merge_history WHERE {' AND '.join(clauses)}",
                params,
            ).fetchone()
        return int(row["count"]) if row is not None else 0

    def purge_branch(self, branch: str, *, include_artifacts: bool = True) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM records WHERE branch = ?", (branch,))
            conn.execute("DELETE FROM stage_snapshots WHERE branch = ?", (branch,))
            conn.execute("DELETE FROM sessions WHERE branch = ?", (branch,))
            conn.execute("DELETE FROM index_jobs WHERE branch = ?", (branch,))
            if include_artifacts:
                conn.execute("DELETE FROM artifacts WHERE branch = ?", (branch,))
            if self._fts_exists(conn, "records_fts"):
                conn.execute("DELETE FROM records_fts WHERE branch = ?", (branch,))
            if self._fts_exists(conn, "stage_snapshots_fts"):
                conn.execute("DELETE FROM stage_snapshots_fts WHERE branch = ?", (branch,))
            if include_artifacts and self._fts_exists(conn, "artifacts_fts"):
                conn.execute("DELETE FROM artifacts_fts WHERE branch = ?", (branch,))

    def list_tables(self) -> list[str]:
        with self.connect_read_only() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY name"
            ).fetchall()
        return [row["name"] for row in rows]

    def describe_vector_index(self) -> dict[str, Any]:
        index = VectorMemoryIndex(self.paths.lancedb_dir)
        description = index.describe()
        description["memory_chunk_count"] = index.count_chunks("memory_chunks")
        description["artifact_chunk_count"] = index.count_chunks("artifact_chunks")
        return description

    def describe_record_index(self, record_id: str) -> dict[str, Any]:
        jobs = self.list_index_jobs(source_type="record", source_id=record_id, limit=20)
        index = VectorMemoryIndex(self.paths.lancedb_dir)
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
            branch_revision = self._fetch_branch_revision(conn, branch) if branch else None
        return {
            "sqlite_path": str(self.paths.sqlite_file.relative_to(self.project_path)),
            "vector_dir": str(self.paths.lancedb_dir.relative_to(self.project_path)),
            "schema_version_path": str(self.paths.schema_version.relative_to(self.project_path)),
            "records": records_count,
            "stage_snapshots": snapshots_count,
            "sessions": sessions_count,
            "artifacts": artifacts_count,
            "pending_index_jobs": pending_jobs,
            "indexed_jobs": indexed_jobs,
            "vector_backend": VectorMemoryIndex(self.paths.lancedb_dir).backend_name,
            "runtime_revision": branch_revision,
        }

    def acquire_lease(
        self,
        lease_name: str,
        owner_id: str,
        *,
        ttl_seconds: int = LEASE_TTL_SECONDS,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        from .jobs import acquire_lease

        return acquire_lease(self, lease_name, owner_id, ttl_seconds=ttl_seconds, conn=conn)

    def release_lease(
        self,
        lease_name: str,
        owner_id: str,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        from .jobs import release_lease

        release_lease(self, lease_name, owner_id, conn=conn)

    def list_writer_leases(self) -> list[dict[str, Any]]:
        now = int(time.time())
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT lease_name, owner_id, expires_at, updated_at
                FROM writer_leases
                ORDER BY lease_name ASC
                """
            ).fetchall()
        return [normalize_writer_lease_row(dict(row), now_epoch=now) for row in rows]

    def process_pending_jobs(self, *, branch: str | None = None, limit: int = 100) -> dict[str, Any]:
        from .jobs import process_pending_jobs

        return process_pending_jobs(self, branch=branch, limit=limit)

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
    ) -> None:
        from .jobs import log_retrieval_run

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
        )

    def _ensure_fts_tables(self, conn: sqlite3.Connection) -> None:
        try:
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS records_fts USING fts5(
                    row_id UNINDEXED,
                    record_id UNINDEXED,
                    branch UNINDEXED,
                    stage UNINDEXED,
                    step_id UNINDEXED,
                    scope UNINDEXED,
                    status UNINDEXED,
                    kind UNINDEXED,
                    content
                )
                """
            )
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS stage_snapshots_fts USING fts5(
                    row_id UNINDEXED,
                    snapshot_key UNINDEXED,
                    branch UNINDEXED,
                    stage UNINDEXED,
                    content
                )
                """
            )
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS artifacts_fts USING fts5(
                    row_id UNINDEXED,
                    artifact_id UNINDEXED,
                    branch UNINDEXED,
                    stage UNINDEXED,
                    path UNINDEXED,
                    content
                )
                """
            )
        except sqlite3.OperationalError:
            return

    def _fts_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row is not None

    def _upsert_fts_row(
        self,
        conn: sqlite3.Connection,
        *,
        table_name: str,
        columns: tuple[str, ...],
        values: tuple[Any, ...],
    ) -> None:
        if not self._fts_exists(conn, table_name):
            return
        row_id = values[0]
        conn.execute(f"DELETE FROM {table_name} WHERE row_id = ?", (row_id,))
        placeholders = ", ".join("?" for _ in columns)
        conn.execute(
            f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )

    def _enqueue_index_job(
        self,
        conn: sqlite3.Connection,
        *,
        source_type: str,
        source_id: str,
        branch: str,
        stage: str | None,
        step_id: str | None,
        content_hash: str,
    ) -> None:
        now = _now_iso()
        conn.execute(
            """
            INSERT INTO index_jobs (
                source_type, source_id, branch, stage, step_id, status,
                attempts, error, content_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', 0, NULL, ?, ?, ?)
            ON CONFLICT(source_type, source_id, content_hash) DO NOTHING
            """,
            (
                source_type,
                source_id,
                branch,
                stage,
                step_id,
                content_hash,
                now,
                now,
            ),
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

    def _record_details_from_row(self, row: dict[str, Any]) -> dict[str, Any]:
        payload = json.loads(row["payload_json"])
        payload.setdefault("id", row["record_id"])
        payload.setdefault("kind", row["kind"])
        payload.setdefault("record_stream", row.get("record_stream"))
        payload.setdefault("content_hash", row["content_hash"])
        return {
            "record_id": row["record_id"],
            "kind": row["kind"],
            "semantic_kind": row.get("semantic_kind"),
            "record_stream": row.get("record_stream"),
            "scope": row.get("scope"),
            "branch": row.get("branch"),
            "stage": row.get("stage"),
            "step_id": row.get("step_id"),
            "status": row.get("status"),
            "version": row.get("version"),
            "summary": row.get("summary"),
            "payload": payload,
            "search_text": row.get("search_text"),
            "source": row.get("source"),
            "ts": row.get("ts"),
            "content_hash": row.get("content_hash"),
        }

    def _ensure_schema_migrations(self, conn: sqlite3.Connection) -> None:
        self._ensure_column(
            conn,
            table_name="records",
            column_name="record_stream",
            ddl="TEXT",
        )

    def _ensure_column(
        self,
        conn: sqlite3.Connection,
        *,
        table_name: str,
        column_name: str,
        ddl: str,
    ) -> None:
        columns = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name in columns:
            return
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")


def _dedupe_search_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for item in items:
        key = (item["source_type"], item["source_id"])
        if key not in unique:
            unique[key] = item
    return list(unique.values())
