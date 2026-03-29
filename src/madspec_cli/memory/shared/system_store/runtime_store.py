from __future__ import annotations

import json
import sqlite3
import time
import uuid
from typing import Any

from .db import LEASE_TTL_SECONDS, StoreComponent
from .jobs import acquire_lease, release_lease
from .leases import normalize_writer_lease_row
from .text import (
    _content_hash,
    _dump_json,
    _flatten_for_search,
    _normalized_optional_text,
    _now_iso,
    _record_search_text,
    _snapshot_stage,
    _snapshot_summary,
)

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


class RuntimeStore(StoreComponent):
    def upsert_record(self, record: dict[str, Any]) -> None:
        with self.connect() as conn:
            self._upsert_record(conn, record)

    def upsert_records_batch(
        self,
        records: list[dict[str, Any]],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        if not records:
            return
        if conn is not None:
            for record in records:
                self._upsert_record(conn, record)
            return
        with self.connect() as managed_conn:
            for record in records:
                self._upsert_record(managed_conn, record)

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
        return payload if isinstance(payload, dict) else None

    def list_sessions(self, *, branch: str) -> list[dict[str, Any]]:
        with self.connect_read_only() as conn:
            rows = conn.execute(
                """
                SELECT session_key, branch, stage, current_step, payload_json, updated_at, content_hash
                FROM sessions
                WHERE branch = ?
                ORDER BY updated_at DESC, session_key ASC
                """,
                (branch,),
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            if not isinstance(payload, dict):
                payload = {}
            items.append(
                {
                    "session_key": row["session_key"],
                    "branch": row["branch"],
                    "stage": row["stage"],
                    "current_step": row["current_step"],
                    "updated_at": row["updated_at"],
                    "content_hash": row["content_hash"],
                    "payload": payload,
                }
            )
        return items

    def fetch_branch_runtime_state(self, branch: str) -> dict[str, Any]:
        with self.connect_read_only() as conn:
            row = conn.execute(
                """
                SELECT branch, revision, updated_at
                FROM branch_runtime_state
                WHERE branch = ?
                """,
                (branch,),
            ).fetchone()
        if row is None:
            revision = self.fetch_branch_revision(branch)
            return {"branch": branch, "revision": revision, "updated_at": None}
        return {
            "branch": row["branch"],
            "revision": int(row["revision"]),
            "updated_at": row["updated_at"],
        }

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

    def delete_records(
        self,
        record_ids: list[str],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> int:
        normalized_ids = sorted({str(item) for item in record_ids if str(item)})
        if not normalized_ids:
            return 0
        if conn is not None:
            return self._delete_records(conn, normalized_ids)
        with self.connect() as managed_conn:
            return self._delete_records(managed_conn, normalized_ids)

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

    def list_semantic_record_details(
        self,
        *,
        branch: str,
        statuses: list[str] | None = None,
        limit: int = 10000,
    ) -> list[dict[str, Any]]:
        return [
            item
            for item in self.list_records(branch=branch, statuses=statuses, limit=limit)
            if item.get("semantic_kind") in {"fact", "decision", "contract"}
        ]

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

    def acquire_lease(
        self,
        lease_name: str,
        owner_id: str,
        *,
        ttl_seconds: int = LEASE_TTL_SECONDS,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        return acquire_lease(self, lease_name, owner_id, ttl_seconds=ttl_seconds, conn=conn)

    def release_lease(
        self,
        lease_name: str,
        owner_id: str,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> None:
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

    def _delete_records(self, conn: sqlite3.Connection, record_ids: list[str]) -> int:
        if not record_ids:
            return 0
        placeholders = ", ".join("?" for _ in record_ids)
        deleted = conn.execute(
            f"DELETE FROM records WHERE record_id IN ({placeholders})",
            record_ids,
        ).rowcount
        conn.execute(
            f"DELETE FROM index_jobs WHERE source_type = 'record' AND source_id IN ({placeholders})",
            record_ids,
        )
        if self._fts_exists(conn, "records_fts"):
            conn.execute(
                f"DELETE FROM records_fts WHERE record_id IN ({placeholders})",
                record_ids,
            )
        return int(deleted or 0)


__all__ = ["RuntimeStore"]
