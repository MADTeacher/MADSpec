from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from ...domain.work_items import (
    TASK_STATUSES,
    TERMINAL_WORK_ITEM_STATUSES,
    build_work_item_readiness,
    coordination_binding_from_session,
    make_work_item_owner_id,
    normalize_scheduling_hints,
    normalize_scope_descriptor,
    validate_work_item_status,
    validate_work_item_type,
)
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

                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    branch TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT,
                    acceptance_note TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS work_items (
                    work_item_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    branch TEXT NOT NULL,
                    title TEXT NOT NULL,
                    type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    subagent_id TEXT NOT NULL,
                    owner_id TEXT,
                    session_key TEXT,
                    step_id TEXT,
                    scope_descriptor_json TEXT NOT NULL,
                    scheduling_hints_json TEXT NOT NULL DEFAULT '{}',
                    acceptance_note TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
                );

                CREATE TABLE IF NOT EXISTS work_item_dependencies (
                    dependency_id TEXT PRIMARY KEY,
                    branch TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    work_item_id TEXT NOT NULL,
                    depends_on_work_item_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (work_item_id, depends_on_work_item_id),
                    FOREIGN KEY(work_item_id) REFERENCES work_items(work_item_id),
                    FOREIGN KEY(depends_on_work_item_id) REFERENCES work_items(work_item_id),
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
                );

                CREATE TABLE IF NOT EXISTS work_item_claims (
                    claim_id TEXT PRIMARY KEY,
                    work_item_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    branch TEXT NOT NULL,
                    session_key TEXT NOT NULL,
                    subagent_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    claimed_at TEXT NOT NULL,
                    released_at TEXT,
                    FOREIGN KEY(work_item_id) REFERENCES work_items(work_item_id),
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
                );

                CREATE TABLE IF NOT EXISTS runtime_proposals (
                    proposal_id TEXT PRIMARY KEY,
                    branch TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    work_item_id TEXT NOT NULL,
                    proposal_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    session_key TEXT NOT NULL,
                    subagent_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    base_revision INTEGER NOT NULL,
                    target_scope_json TEXT NOT NULL,
                    conflict_hints_json TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    apply_summary_json TEXT,
                    content_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    applied_at TEXT,
                    rejected_at TEXT
                );

                CREATE TABLE IF NOT EXISTS runtime_proposal_events (
                    event_id TEXT PRIMARY KEY,
                    proposal_id TEXT NOT NULL,
                    branch TEXT NOT NULL,
                    task_id TEXT,
                    work_item_id TEXT,
                    event_type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    FOREIGN KEY(proposal_id) REFERENCES runtime_proposals(proposal_id)
                );

                CREATE INDEX IF NOT EXISTS idx_tasks_branch ON tasks(branch, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_work_items_branch ON work_items(branch, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_work_items_task ON work_items(task_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_work_item_dependencies_task ON work_item_dependencies(task_id, work_item_id);
                CREATE INDEX IF NOT EXISTS idx_work_item_dependencies_target ON work_item_dependencies(depends_on_work_item_id, work_item_id);
                CREATE INDEX IF NOT EXISTS idx_runtime_proposals_branch ON runtime_proposals(branch, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_runtime_proposals_work_item ON runtime_proposals(work_item_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_runtime_proposal_events_branch ON runtime_proposal_events(branch, ts DESC);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_work_item_claims_active_work_item
                    ON work_item_claims(work_item_id)
                    WHERE released_at IS NULL;
                CREATE UNIQUE INDEX IF NOT EXISTS idx_work_item_claims_active_session
                    ON work_item_claims(branch, session_key)
                    WHERE released_at IS NULL;
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

    def create_task(
        self,
        *,
        branch: str,
        title: str,
        summary: str | None,
        acceptance_note: str | None,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        self.ensure_schema()
        task_id = str(uuid.uuid4())
        now = _now_iso()
        payload = {
            "task_id": task_id,
            "branch": branch,
            "title": title.strip(),
            "status": "open",
            "summary": _normalized_optional_text(summary),
            "acceptance_note": _normalized_optional_text(acceptance_note),
            "created_at": now,
            "updated_at": now,
        }
        if conn is not None:
            self._upsert_task(conn, payload)
            self._record_task_event(conn, payload=payload, event_type="task.created", summary=f"Created task {payload['title']}")
            return payload
        with self.connect() as managed_conn:
            managed_conn.execute("BEGIN IMMEDIATE")
            self._upsert_task(managed_conn, payload)
            self._record_task_event(
                managed_conn,
                payload=payload,
                event_type="task.created",
                summary=f"Created task {payload['title']}",
            )
        return payload

    def list_tasks(self, *, branch: str) -> list[dict[str, Any]]:
        self.ensure_schema()
        with self.connect_read_only() as conn:
            rows = conn.execute(
                """
                SELECT task_id, branch, title, status, summary, acceptance_note, created_at, updated_at
                FROM tasks
                WHERE branch = ?
                ORDER BY updated_at DESC, task_id DESC
                """,
                (branch,),
            ).fetchall()
        return [self._task_from_row(row) for row in rows]

    def fetch_task(self, task_id: str, *, conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        self.ensure_schema()
        if conn is not None:
            return self._fetch_task(conn, task_id)
        with self.connect_read_only() as managed_conn:
            return self._fetch_task(managed_conn, task_id)

    def create_work_item(
        self,
        *,
        branch: str,
        task_id: str,
        title: str,
        work_item_type: str,
        subagent_id: str,
        step_id: str | None,
        scope_descriptor: dict[str, Any] | None,
        scheduling_hints: dict[str, Any] | None = None,
        acceptance_note: str | None = None,
        depends_on_work_item_ids: list[str] | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        self.ensure_schema()
        normalized_scope = normalize_scope_descriptor(
            {**dict(scope_descriptor or {}), "step_id": step_id or dict(scope_descriptor or {}).get("step_id")}
        )
        normalized_hints = normalize_scheduling_hints(scheduling_hints)
        normalized_type = validate_work_item_type(work_item_type)
        work_item_id = str(uuid.uuid4())
        now = _now_iso()
        payload = {
            "work_item_id": work_item_id,
            "task_id": task_id,
            "branch": branch,
            "title": title.strip(),
            "type": normalized_type,
            "status": "open",
            "subagent_id": subagent_id.strip(),
            "owner_id": None,
            "session_key": None,
            "step_id": normalized_scope.get("step_id"),
            "scope_descriptor": normalized_scope,
            "scheduling_hints": normalized_hints,
            "acceptance_note": _normalized_optional_text(acceptance_note),
            "created_at": now,
            "updated_at": now,
        }
        dependency_ids = self._normalize_dependency_ids(depends_on_work_item_ids)
        if conn is not None:
            self._validate_work_item_scope_overlap(conn, payload)
            self._validate_work_item_dependencies(conn, payload=payload, depends_on_work_item_ids=dependency_ids)
            self._upsert_work_item(conn, payload)
            self._replace_work_item_dependencies(conn, payload=payload, depends_on_work_item_ids=dependency_ids)
            self._recompute_task_status(conn, task_id=task_id)
            self._record_work_item_event(
                conn,
                payload={**payload, "depends_on_work_item_ids": dependency_ids},
                event_type="work-item.created",
                summary=f"Created work item {payload['title']}",
            )
            return payload
        with self.connect() as managed_conn:
            managed_conn.execute("BEGIN IMMEDIATE")
            self._validate_work_item_scope_overlap(managed_conn, payload)
            self._validate_work_item_dependencies(
                managed_conn,
                payload=payload,
                depends_on_work_item_ids=dependency_ids,
            )
            self._upsert_work_item(managed_conn, payload)
            self._replace_work_item_dependencies(managed_conn, payload=payload, depends_on_work_item_ids=dependency_ids)
            self._recompute_task_status(managed_conn, task_id=task_id)
            self._record_work_item_event(
                managed_conn,
                payload={**payload, "depends_on_work_item_ids": dependency_ids},
                event_type="work-item.created",
                summary=f"Created work item {payload['title']}",
            )
        return payload

    def list_work_items(
        self,
        *,
        branch: str,
        task_id: str | None = None,
        session_key: str | None = None,
    ) -> list[dict[str, Any]]:
        self.ensure_schema()
        clauses = ["branch = ?"]
        params: list[Any] = [branch]
        if task_id is not None:
            clauses.append("task_id = ?")
            params.append(task_id)
        if session_key is not None:
            clauses.append("session_key = ?")
            params.append(session_key)
        with self.connect_read_only() as conn:
            rows = conn.execute(
                f"""
                SELECT work_item_id, task_id, branch, title, type, status, subagent_id, owner_id,
                       session_key, step_id, scope_descriptor_json, scheduling_hints_json,
                       acceptance_note, created_at, updated_at
                FROM work_items
                WHERE {' AND '.join(clauses)}
                ORDER BY updated_at DESC, work_item_id DESC
                """,
                params,
            ).fetchall()
        return [self._work_item_from_row(row) for row in rows]

    def fetch_work_item(
        self,
        work_item_id: str,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        self.ensure_schema()
        if conn is not None:
            return self._fetch_work_item(conn, work_item_id)
        with self.connect_read_only() as managed_conn:
            return self._fetch_work_item(managed_conn, work_item_id)

    def claim_work_item(
        self,
        *,
        branch: str,
        work_item_id: str,
        session_key: str,
        subagent_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        self.ensure_schema()
        if conn is not None:
            return self._claim_work_item(
                conn,
                branch=branch,
                work_item_id=work_item_id,
                session_key=session_key,
                subagent_id=subagent_id,
            )
        with self.connect() as managed_conn:
            managed_conn.execute("BEGIN IMMEDIATE")
            return self._claim_work_item(
                managed_conn,
                branch=branch,
                work_item_id=work_item_id,
                session_key=session_key,
                subagent_id=subagent_id,
            )

    def release_work_item(
        self,
        *,
        branch: str,
        work_item_id: str,
        session_key: str,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        self.ensure_schema()
        if conn is not None:
            return self._release_work_item(
                conn,
                branch=branch,
                work_item_id=work_item_id,
                session_key=session_key,
            )
        with self.connect() as managed_conn:
            managed_conn.execute("BEGIN IMMEDIATE")
            return self._release_work_item(
                managed_conn,
                branch=branch,
                work_item_id=work_item_id,
                session_key=session_key,
            )

    def fetch_active_claim_for_session(
        self,
        *,
        branch: str,
        session_key: str,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        self.ensure_schema()
        if conn is not None:
            return self._fetch_active_claim_for_session(conn, branch=branch, session_key=session_key)
        with self.connect_read_only() as managed_conn:
            return self._fetch_active_claim_for_session(managed_conn, branch=branch, session_key=session_key)

    def fetch_active_claim_for_work_item(
        self,
        *,
        work_item_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        self.ensure_schema()
        if conn is not None:
            return self._fetch_active_claim_for_work_item(conn, work_item_id=work_item_id)
        with self.connect_read_only() as managed_conn:
            return self._fetch_active_claim_for_work_item(managed_conn, work_item_id=work_item_id)

    def list_work_item_dependencies(
        self,
        *,
        task_id: str | None = None,
        work_item_id: str | None = None,
        branch: str | None = None,
    ) -> list[dict[str, Any]]:
        self.ensure_schema()
        clauses = ["1 = 1"]
        params: list[Any] = []
        if branch is not None:
            clauses.append("branch = ?")
            params.append(branch)
        if task_id is not None:
            clauses.append("task_id = ?")
            params.append(task_id)
        if work_item_id is not None:
            clauses.append("work_item_id = ?")
            params.append(work_item_id)
        with self.connect_read_only() as conn:
            rows = conn.execute(
                f"""
                SELECT dependency_id, branch, task_id, work_item_id, depends_on_work_item_id, created_at
                FROM work_item_dependencies
                WHERE {' AND '.join(clauses)}
                ORDER BY created_at ASC, dependency_id ASC
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def explain_work_item(
        self,
        *,
        branch: str,
        work_item_id: str,
        session_key: str | None = None,
    ) -> dict[str, Any] | None:
        self.ensure_schema()
        work_item = self.fetch_work_item(work_item_id)
        if work_item is None or work_item["branch"] != branch:
            return None
        active_claim = self.fetch_active_claim_for_work_item(work_item_id=work_item_id)
        dependency_edges = self.list_work_item_dependencies(task_id=work_item["task_id"], work_item_id=work_item_id)
        dependency_items = []
        for edge in dependency_edges:
            dependency = self.fetch_work_item(str(edge["depends_on_work_item_id"]))
            if dependency is not None:
                dependency_items.append(dependency)
        related_proposals = self.list_runtime_proposals(branch=branch, work_item_id=work_item_id, limit=20)
        readiness = build_work_item_readiness(
            work_item=work_item,
            dependencies=dependency_items,
            active_claim=active_claim,
            related_proposals=related_proposals,
        )
        ownership_state = {
            "has_claim": active_claim is not None,
            "claim": active_claim,
            "owner_id": work_item.get("owner_id"),
            "session_key": work_item.get("session_key"),
            "subagent_id": work_item.get("subagent_id"),
            "session_matches": bool(session_key and work_item.get("session_key") == session_key),
        }
        return {
            "task_id": work_item["task_id"],
            "work_item_id": work_item["work_item_id"],
            "session_key": session_key,
            "work_item": work_item,
            "readiness": {
                "status": readiness["readiness_status"],
                "blocked_reasons": readiness["blocked_reasons"],
            },
            "dependency_state": readiness["dependency_state"],
            "ownership_state": ownership_state,
            "related_proposals": readiness["related_proposals"],
            "scheduler_hints": readiness["scheduler_hints"],
        }

    def fetch_session_coordination(
        self,
        *,
        branch: str,
        session_key: str,
    ) -> dict[str, Any]:
        self.ensure_schema()
        session_payload = self.fetch_session(branch=branch, session_key=session_key) or {}
        binding = coordination_binding_from_session(session_payload)
        claim = self.fetch_active_claim_for_session(branch=branch, session_key=session_key)
        work_item = None
        task = None
        if binding["work_item_id"]:
            work_item = self.fetch_work_item(binding["work_item_id"])
        if work_item is None and claim is not None:
            work_item = self.fetch_work_item(str(claim["work_item_id"]))
        if binding["task_id"]:
            task = self.fetch_task(binding["task_id"])
        if task is None and work_item is not None:
            task = self.fetch_task(str(work_item["task_id"]))
        proposal_summary = None
        coordinator = None
        if work_item is not None:
            proposal_summary = self.summarize_runtime_proposals(
                branch=branch,
                work_item_id=str(work_item["work_item_id"]),
                session_key=session_key,
            )
            coordinator = self.explain_work_item(
                branch=branch,
                work_item_id=str(work_item["work_item_id"]),
                session_key=session_key,
            )
        return {
            "session_binding": binding,
            "claim": claim,
            "work_item": work_item,
            "task": task,
            "proposal_summary": proposal_summary,
            "coordinator": coordinator,
        }

    def _upsert_task(self, conn: sqlite3.Connection, payload: dict[str, Any]) -> None:
        status = str(payload.get("status") or "open")
        if status not in TASK_STATUSES:
            raise ValueError("task status is invalid")
        conn.execute(
            """
            INSERT INTO tasks (
                task_id, branch, title, status, summary, acceptance_note, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                branch=excluded.branch,
                title=excluded.title,
                status=excluded.status,
                summary=excluded.summary,
                acceptance_note=excluded.acceptance_note,
                updated_at=excluded.updated_at
            """,
            (
                str(payload["task_id"]),
                str(payload["branch"]),
                str(payload["title"]),
                status,
                _normalized_optional_text(payload.get("summary")),
                _normalized_optional_text(payload.get("acceptance_note")),
                str(payload["created_at"]),
                str(payload["updated_at"]),
            ),
        )

    def _fetch_task(self, conn: sqlite3.Connection, task_id: str) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT task_id, branch, title, status, summary, acceptance_note, created_at, updated_at
            FROM tasks
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()
        if row is None:
            return None
        return self._task_from_row(row)

    def _task_from_row(self, row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        return {
            "task_id": row["task_id"],
            "branch": row["branch"],
            "title": row["title"],
            "status": row["status"],
            "summary": row["summary"],
            "acceptance_note": row["acceptance_note"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _upsert_work_item(self, conn: sqlite3.Connection, payload: dict[str, Any]) -> None:
        normalized_scope = normalize_scope_descriptor(payload.get("scope_descriptor"))
        status = validate_work_item_status(str(payload.get("status") or "open"))
        conn.execute(
            """
            INSERT INTO work_items (
                work_item_id, task_id, branch, title, type, status, subagent_id, owner_id,
                session_key, step_id, scope_descriptor_json, scheduling_hints_json,
                acceptance_note, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(work_item_id) DO UPDATE SET
                task_id=excluded.task_id,
                branch=excluded.branch,
                title=excluded.title,
                type=excluded.type,
                status=excluded.status,
                subagent_id=excluded.subagent_id,
                owner_id=excluded.owner_id,
                session_key=excluded.session_key,
                step_id=excluded.step_id,
                scope_descriptor_json=excluded.scope_descriptor_json,
                scheduling_hints_json=excluded.scheduling_hints_json,
                acceptance_note=excluded.acceptance_note,
                updated_at=excluded.updated_at
            """,
            (
                str(payload["work_item_id"]),
                str(payload["task_id"]),
                str(payload["branch"]),
                str(payload["title"]),
                validate_work_item_type(str(payload["type"])),
                status,
                str(payload["subagent_id"]),
                _normalized_optional_text(payload.get("owner_id")),
                _normalized_optional_text(payload.get("session_key")),
                _normalized_optional_text(payload.get("step_id")) or _normalized_optional_text(normalized_scope.get("step_id")),
                _dump_json(normalized_scope),
                _dump_json(normalize_scheduling_hints(payload.get("scheduling_hints"))),
                _normalized_optional_text(payload.get("acceptance_note")),
                str(payload["created_at"]),
                str(payload["updated_at"]),
            ),
        )

    def _fetch_work_item(self, conn: sqlite3.Connection, work_item_id: str) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT work_item_id, task_id, branch, title, type, status, subagent_id, owner_id,
                   session_key, step_id, scope_descriptor_json, scheduling_hints_json,
                   acceptance_note, created_at, updated_at
            FROM work_items
            WHERE work_item_id = ?
            """,
            (work_item_id,),
        ).fetchone()
        if row is None:
            return None
        return self._work_item_from_row(row)

    def _work_item_from_row(self, row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        return {
            "work_item_id": row["work_item_id"],
            "task_id": row["task_id"],
            "branch": row["branch"],
            "title": row["title"],
            "type": row["type"],
            "status": row["status"],
            "subagent_id": row["subagent_id"],
            "owner_id": row["owner_id"],
            "session_key": row["session_key"],
            "step_id": row["step_id"],
            "scope_descriptor": normalize_scope_descriptor(json.loads(row["scope_descriptor_json"])),
            "scheduling_hints": normalize_scheduling_hints(json.loads(row["scheduling_hints_json"] or "{}")),
            "acceptance_note": row["acceptance_note"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _claim_work_item(
        self,
        conn: sqlite3.Connection,
        *,
        branch: str,
        work_item_id: str,
        session_key: str,
        subagent_id: str,
    ) -> dict[str, Any]:
        work_item = self._fetch_work_item(conn, work_item_id)
        if work_item is None or work_item["branch"] != branch:
            raise ValueError(f"work item '{work_item_id}' was not found")
        if work_item["subagent_id"] != subagent_id:
            raise ValueError(
                f"work item '{work_item_id}' is assigned to subagent '{work_item['subagent_id']}', not '{subagent_id}'"
            )
        active_for_work_item = self._fetch_active_claim_for_work_item(conn, work_item_id=work_item_id)
        active_for_session = self._fetch_active_claim_for_session(conn, branch=branch, session_key=session_key)
        if active_for_session is not None:
            raise ValueError(f"session '{session_key}' already claims work item '{active_for_session['work_item_id']}'")
        readiness = self._build_work_item_read_model(conn, work_item=work_item, session_key=session_key)
        if readiness["readiness"]["status"] == "blocked":
            return {
                **work_item,
                "accepted": False,
                "reason": "readiness_blocked",
                "readiness": readiness["readiness"],
                "dependency_state": readiness["dependency_state"],
                "ownership_state": readiness["ownership_state"],
                "related_proposals": readiness["related_proposals"],
                "scheduler_hints": readiness["scheduler_hints"],
            }
        if active_for_work_item is not None:
            raise ValueError(f"work item '{work_item_id}' is already claimed by session '{active_for_work_item['session_key']}'")

        owner_id = make_work_item_owner_id(subagent_id=subagent_id, session_key=session_key)
        claimed_at = _now_iso()
        claim = {
            "claim_id": str(uuid.uuid4()),
            "work_item_id": work_item_id,
            "task_id": str(work_item["task_id"]),
            "branch": branch,
            "session_key": session_key,
            "subagent_id": subagent_id,
            "owner_id": owner_id,
            "claimed_at": claimed_at,
            "released_at": None,
        }
        conn.execute(
            """
            INSERT INTO work_item_claims (
                claim_id, work_item_id, task_id, branch, session_key, subagent_id, owner_id, claimed_at, released_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                claim["claim_id"],
                claim["work_item_id"],
                claim["task_id"],
                claim["branch"],
                claim["session_key"],
                claim["subagent_id"],
                claim["owner_id"],
                claim["claimed_at"],
            ),
        )
        updated_work_item = {
            **work_item,
            "status": "claimed" if work_item["status"] == "open" else work_item["status"],
            "owner_id": owner_id,
            "session_key": session_key,
            "updated_at": claimed_at,
        }
        self._upsert_work_item(conn, updated_work_item)
        self._recompute_task_status(conn, task_id=str(work_item["task_id"]))
        self._record_work_item_event(
            conn,
            payload={**updated_work_item, "claim": claim},
            event_type="work-item.claimed",
            summary=f"Claimed work item {work_item['title']}",
        )
        return self._work_item_with_claim(updated_work_item, claim)

    def _release_work_item(
        self,
        conn: sqlite3.Connection,
        *,
        branch: str,
        work_item_id: str,
        session_key: str,
    ) -> dict[str, Any]:
        work_item = self._fetch_work_item(conn, work_item_id)
        if work_item is None or work_item["branch"] != branch:
            raise ValueError(f"work item '{work_item_id}' was not found")
        claim = self._fetch_active_claim_for_work_item(conn, work_item_id=work_item_id)
        if claim is None or claim["session_key"] != session_key:
            raise ValueError(f"session '{session_key}' does not hold work item '{work_item_id}'")

        released_at = _now_iso()
        conn.execute(
            """
            UPDATE work_item_claims
            SET released_at = ?
            WHERE claim_id = ?
            """,
            (released_at, claim["claim_id"]),
        )
        next_status = "open" if work_item["status"] == "claimed" else work_item["status"]
        updated_work_item = {
            **work_item,
            "status": next_status,
            "owner_id": None,
            "session_key": None,
            "updated_at": released_at,
        }
        self._upsert_work_item(conn, updated_work_item)
        self._recompute_task_status(conn, task_id=str(work_item["task_id"]))
        released_claim = {**claim, "released_at": released_at}
        self._record_work_item_event(
            conn,
            payload={**updated_work_item, "claim": released_claim},
            event_type="work-item.released",
            summary=f"Released work item {work_item['title']}",
        )
        return self._work_item_with_claim(updated_work_item, released_claim)

    def _fetch_active_claim_for_session(
        self,
        conn: sqlite3.Connection,
        *,
        branch: str,
        session_key: str,
    ) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT claim_id, work_item_id, task_id, branch, session_key, subagent_id, owner_id, claimed_at, released_at
            FROM work_item_claims
            WHERE branch = ? AND session_key = ? AND released_at IS NULL
            """,
            (branch, session_key),
        ).fetchone()
        if row is None:
            return None
        return self._claim_from_row(row)

    def _fetch_active_claim_for_work_item(
        self,
        conn: sqlite3.Connection,
        *,
        work_item_id: str,
    ) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT claim_id, work_item_id, task_id, branch, session_key, subagent_id, owner_id, claimed_at, released_at
            FROM work_item_claims
            WHERE work_item_id = ? AND released_at IS NULL
            """,
            (work_item_id,),
        ).fetchone()
        if row is None:
            return None
        return self._claim_from_row(row)

    def _claim_from_row(self, row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        return {
            "claim_id": row["claim_id"],
            "work_item_id": row["work_item_id"],
            "task_id": row["task_id"],
            "branch": row["branch"],
            "session_key": row["session_key"],
            "subagent_id": row["subagent_id"],
            "owner_id": row["owner_id"],
            "claimed_at": row["claimed_at"],
            "released_at": row["released_at"],
        }

    def _work_item_with_claim(self, work_item: dict[str, Any], claim: dict[str, Any] | None) -> dict[str, Any]:
        return {
            **work_item,
            "claim": claim,
        }

    def _recompute_task_status(self, conn: sqlite3.Connection, *, task_id: str) -> None:
        task = self._fetch_task(conn, task_id)
        if task is None:
            return
        rows = conn.execute(
            """
            SELECT work_item_id, task_id, branch, title, type, status, subagent_id, owner_id,
                   session_key, step_id, scope_descriptor_json, scheduling_hints_json,
                   acceptance_note, created_at, updated_at
            FROM work_items
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchall()
        work_items = [self._work_item_from_row(row) for row in rows]
        ready_count = 0
        if work_items:
            for item in work_items:
                read_model = self._build_work_item_read_model(conn, work_item=item, session_key=item.get("session_key"))
                if read_model["readiness"]["status"] == "ready":
                    ready_count += 1
        if work_items and all(item["status"] in TERMINAL_WORK_ITEM_STATUSES for item in work_items):
            status = "completed"
        elif any(item["status"] in {"claimed", "in_progress"} for item in work_items):
            status = "active"
        elif work_items and ready_count == 0:
            status = "blocked"
        else:
            status = "open"
        if status == task["status"]:
            return
        updated = {
            **task,
            "status": status,
            "updated_at": _now_iso(),
        }
        self._upsert_task(conn, updated)
        self._record_task_event(
            conn,
            payload=updated,
            event_type="task.status-changed",
            summary=f"Task {task['title']} status changed to {status}",
        )

    def _validate_work_item_scope_overlap(self, conn: sqlite3.Connection, payload: dict[str, Any]) -> None:
        step_id = _normalized_optional_text(payload.get("step_id"))
        if not step_id:
            return
        rows = conn.execute(
            """
            SELECT work_item_id, task_id, branch, title, type, status, subagent_id, owner_id,
                   session_key, step_id, scope_descriptor_json, scheduling_hints_json,
                   acceptance_note, created_at, updated_at
            FROM work_items
            WHERE branch = ? AND step_id = ? AND status != 'completed'
            """,
            (str(payload["branch"]), step_id),
        ).fetchall()
        current_scope = normalize_scope_descriptor(payload.get("scope_descriptor"))
        for row in rows:
            existing = self._work_item_from_row(row)
            if existing["work_item_id"] == payload.get("work_item_id"):
                continue
            for key in ("paths", "artifacts", "concerns"):
                if set(existing["scope_descriptor"].get(key, [])) & set(current_scope.get(key, [])):
                    raise ValueError(
                        f"work item scope overlaps with '{existing['work_item_id']}' on step '{step_id}' via {key}"
                    )

    def _normalize_dependency_ids(self, depends_on_work_item_ids: list[str] | None) -> list[str]:
        unique: list[str] = []
        seen: set[str] = set()
        for item in depends_on_work_item_ids or []:
            normalized = str(item or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique.append(normalized)
        return unique

    def _validate_work_item_dependencies(
        self,
        conn: sqlite3.Connection,
        *,
        payload: dict[str, Any],
        depends_on_work_item_ids: list[str],
    ) -> None:
        for dependency_id in depends_on_work_item_ids:
            if dependency_id == payload["work_item_id"]:
                raise ValueError("work item cannot depend on itself")
            dependency = self._fetch_work_item(conn, dependency_id)
            if dependency is None:
                raise ValueError(f"dependency work item '{dependency_id}' was not found")
            if dependency["task_id"] != payload["task_id"]:
                raise ValueError("work item dependencies must belong to the same task")
            if dependency["branch"] != payload["branch"]:
                raise ValueError("work item dependencies must belong to the same branch")

    def _replace_work_item_dependencies(
        self,
        conn: sqlite3.Connection,
        *,
        payload: dict[str, Any],
        depends_on_work_item_ids: list[str],
    ) -> None:
        conn.execute(
            "DELETE FROM work_item_dependencies WHERE work_item_id = ?",
            (str(payload["work_item_id"]),),
        )
        created_at = _now_iso()
        for dependency_id in depends_on_work_item_ids:
            conn.execute(
                """
                INSERT INTO work_item_dependencies (
                    dependency_id, branch, task_id, work_item_id, depends_on_work_item_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    str(payload["branch"]),
                    str(payload["task_id"]),
                    str(payload["work_item_id"]),
                    str(dependency_id),
                    created_at,
                ),
            )

    def _list_work_item_dependencies_for_conn(
        self,
        conn: sqlite3.Connection,
        *,
        task_id: str | None = None,
        work_item_id: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["1 = 1"]
        params: list[Any] = []
        if task_id is not None:
            clauses.append("task_id = ?")
            params.append(task_id)
        if work_item_id is not None:
            clauses.append("work_item_id = ?")
            params.append(work_item_id)
        rows = conn.execute(
            f"""
            SELECT dependency_id, branch, task_id, work_item_id, depends_on_work_item_id, created_at
            FROM work_item_dependencies
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at ASC, dependency_id ASC
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def _build_work_item_read_model(
        self,
        conn: sqlite3.Connection,
        *,
        work_item: dict[str, Any],
        session_key: str | None,
    ) -> dict[str, Any]:
        active_claim = self._fetch_active_claim_for_work_item(conn, work_item_id=str(work_item["work_item_id"]))
        dependency_edges = self._list_work_item_dependencies_for_conn(
            conn,
            task_id=str(work_item["task_id"]),
            work_item_id=str(work_item["work_item_id"]),
        )
        dependency_items = []
        for edge in dependency_edges:
            dependency = self._fetch_work_item(conn, str(edge["depends_on_work_item_id"]))
            if dependency is not None:
                dependency_items.append(dependency)
        related_proposals = [
            self._runtime_proposal_from_row(row)
            for row in conn.execute(
                """
                SELECT * FROM runtime_proposals
                WHERE branch = ? AND work_item_id = ?
                ORDER BY updated_at DESC, proposal_id DESC
                LIMIT 20
                """,
                (str(work_item["branch"]), str(work_item["work_item_id"])),
            ).fetchall()
        ]
        readiness = build_work_item_readiness(
            work_item=work_item,
            dependencies=dependency_items,
            active_claim=active_claim,
            related_proposals=related_proposals,
        )
        ownership_state = {
            "has_claim": active_claim is not None,
            "claim": active_claim,
            "owner_id": work_item.get("owner_id"),
            "session_key": work_item.get("session_key"),
            "subagent_id": work_item.get("subagent_id"),
            "session_matches": bool(session_key and work_item.get("session_key") == session_key),
        }
        return {
            "work_item": work_item,
            "readiness": {
                "status": readiness["readiness_status"],
                "blocked_reasons": readiness["blocked_reasons"],
            },
            "dependency_state": readiness["dependency_state"],
            "ownership_state": ownership_state,
            "related_proposals": readiness["related_proposals"],
            "scheduler_hints": readiness["scheduler_hints"],
        }

    def _record_task_event(
        self,
        conn: sqlite3.Connection,
        *,
        payload: dict[str, Any],
        event_type: str,
        summary: str,
    ) -> None:
        self._upsert_record(
            conn,
            {
                "id": str(uuid.uuid4()),
                "record_type": "event",
                "record_stream": "events",
                "scope": "work-item",
                "branch": str(payload["branch"]),
                "stage": "coordination",
                "status": "validated",
                "summary": summary,
                "evidence": [],
                "payload": {"event_type": event_type, "task": payload},
                "source": event_type,
                "ts": _now_iso(),
            },
        )

    def _record_work_item_event(
        self,
        conn: sqlite3.Connection,
        *,
        payload: dict[str, Any],
        event_type: str,
        summary: str,
    ) -> None:
        self._upsert_record(
            conn,
            {
                "id": str(uuid.uuid4()),
                "record_type": "event",
                "record_stream": "events",
                "scope": "work-item",
                "branch": str(payload["branch"]),
                "stage": "coordination",
                "step_id": _normalized_optional_text(payload.get("step_id")),
                "status": "validated",
                "summary": summary,
                "evidence": [],
                "payload": {"event_type": event_type, "work_item": payload},
                "source": event_type,
                "ts": _now_iso(),
            },
        )

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
        work_items: list[dict[str, Any]],
        artifacts: list[dict[str, Any]],
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
        conn: sqlite3.Connection,
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
        for artifact in artifacts:
            payload = dict(artifact)
            self._upsert_artifact(
                conn,
                artifact_id=str(payload["artifact_id"]),
                branch=branch,
                stage=_normalized_optional_text(payload.get("stage")),
                path=str(payload["path"]),
                content=str(payload["content"]),
                updated_at=str(payload["updated_at"]),
            )
        touched_tasks: set[str] = set()
        for work_item in work_items:
            payload = dict(work_item)
            self._upsert_work_item(conn, payload)
            touched_tasks.add(str(payload["task_id"]))
        for record in records:
            self._upsert_record(conn, dict(record))
        for task_id in touched_tasks:
            self._recompute_task_status(conn, task_id=task_id)
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

    def upsert_runtime_proposal(self, proposal: dict[str, Any]) -> None:
        self.ensure_schema()
        payload_json = _dump_json(proposal.get("payload") or {})
        target_scope_json = _dump_json(proposal.get("target_scope") or {})
        conflict_hints_json = _dump_json(proposal.get("conflict_hints") or {})
        apply_summary_json = (
            _dump_json(proposal.get("apply_summary") or {})
            if proposal.get("apply_summary") is not None
            else None
        )
        content_hash = _content_hash(
            _dump_json(
                {
                    "payload": proposal.get("payload") or {},
                    "target_scope": proposal.get("target_scope") or {},
                    "conflict_hints": proposal.get("conflict_hints") or {},
                    "status": proposal.get("status"),
                    "apply_summary": proposal.get("apply_summary"),
                }
            )
        )
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO runtime_proposals (
                    proposal_id, branch, task_id, work_item_id, proposal_type, status,
                    session_key, subagent_id, owner_id, base_revision, target_scope_json,
                    conflict_hints_json, payload_json, apply_summary_json, content_hash,
                    created_at, updated_at, applied_at, rejected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(proposal_id) DO UPDATE SET
                    branch=excluded.branch,
                    task_id=excluded.task_id,
                    work_item_id=excluded.work_item_id,
                    proposal_type=excluded.proposal_type,
                    status=excluded.status,
                    session_key=excluded.session_key,
                    subagent_id=excluded.subagent_id,
                    owner_id=excluded.owner_id,
                    base_revision=excluded.base_revision,
                    target_scope_json=excluded.target_scope_json,
                    conflict_hints_json=excluded.conflict_hints_json,
                    payload_json=excluded.payload_json,
                    apply_summary_json=excluded.apply_summary_json,
                    content_hash=excluded.content_hash,
                    created_at=excluded.created_at,
                    updated_at=excluded.updated_at,
                    applied_at=excluded.applied_at,
                    rejected_at=excluded.rejected_at
                """,
                (
                    str(proposal.get("proposal_id") or ""),
                    str(proposal.get("branch") or ""),
                    str(proposal.get("task_id") or ""),
                    str(proposal.get("work_item_id") or ""),
                    str(proposal.get("proposal_type") or ""),
                    str(proposal.get("status") or "pending"),
                    str(proposal.get("session_key") or ""),
                    str(proposal.get("subagent_id") or ""),
                    str(proposal.get("owner_id") or ""),
                    int(proposal.get("base_revision") or 0),
                    target_scope_json,
                    conflict_hints_json,
                    payload_json,
                    apply_summary_json,
                    content_hash,
                    str(proposal.get("created_at") or _now_iso()),
                    str(proposal.get("updated_at") or _now_iso()),
                    _normalized_optional_text(proposal.get("applied_at")),
                    _normalized_optional_text(proposal.get("rejected_at")),
                ),
            )

    def fetch_runtime_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        self.ensure_schema()
        with self.connect_read_only() as conn:
            row = conn.execute(
                "SELECT * FROM runtime_proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        if row is None:
            return None
        return self._runtime_proposal_from_row(row)

    def list_runtime_proposals(
        self,
        *,
        branch: str | None = None,
        task_id: str | None = None,
        work_item_id: str | None = None,
        session_key: str | None = None,
        statuses: list[str] | None = None,
        proposal_types: list[str] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        self.ensure_schema()
        clauses = ["1 = 1"]
        params: list[Any] = []
        if branch is not None:
            clauses.append("branch = ?")
            params.append(branch)
        if task_id is not None:
            clauses.append("task_id = ?")
            params.append(task_id)
        if work_item_id is not None:
            clauses.append("work_item_id = ?")
            params.append(work_item_id)
        if session_key is not None:
            clauses.append("session_key = ?")
            params.append(session_key)
        if statuses:
            placeholders = ", ".join("?" for _ in statuses)
            clauses.append(f"status IN ({placeholders})")
            params.extend(statuses)
        if proposal_types:
            placeholders = ", ".join("?" for _ in proposal_types)
            clauses.append(f"proposal_type IN ({placeholders})")
            params.extend(proposal_types)
        with self.connect_read_only() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM runtime_proposals
                WHERE {' AND '.join(clauses)}
                ORDER BY updated_at DESC, proposal_id DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return [self._runtime_proposal_from_row(row) for row in rows]

    def append_runtime_proposal_event(self, event: dict[str, Any]) -> None:
        self.ensure_schema()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO runtime_proposal_events (
                    event_id, proposal_id, branch, task_id, work_item_id, event_type,
                    summary, payload_json, ts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(event.get("event_id") or ""),
                    str(event.get("proposal_id") or ""),
                    str(event.get("branch") or ""),
                    _normalized_optional_text(event.get("task_id")),
                    _normalized_optional_text(event.get("work_item_id")),
                    str(event.get("event_type") or ""),
                    str(event.get("summary") or ""),
                    _dump_json(event.get("payload") or {}),
                    str(event.get("ts") or _now_iso()),
                ),
            )

    def list_runtime_proposal_events(
        self,
        *,
        branch: str | None = None,
        proposal_id: str | None = None,
        work_item_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        self.ensure_schema()
        clauses = ["1 = 1"]
        params: list[Any] = []
        if branch is not None:
            clauses.append("branch = ?")
            params.append(branch)
        if proposal_id is not None:
            clauses.append("proposal_id = ?")
            params.append(proposal_id)
        if work_item_id is not None:
            clauses.append("work_item_id = ?")
            params.append(work_item_id)
        with self.connect_read_only() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM runtime_proposal_events
                WHERE {' AND '.join(clauses)}
                ORDER BY ts DESC, event_id DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return [
            {
                "event_id": row["event_id"],
                "proposal_id": row["proposal_id"],
                "branch": row["branch"],
                "task_id": row["task_id"],
                "work_item_id": row["work_item_id"],
                "event_type": row["event_type"],
                "summary": row["summary"],
                "payload": json.loads(row["payload_json"]),
                "ts": row["ts"],
            }
            for row in rows
        ]

    def summarize_runtime_proposals(
        self,
        *,
        branch: str,
        work_item_id: str,
        session_key: str | None = None,
    ) -> dict[str, Any]:
        proposals = self.list_runtime_proposals(
            branch=branch,
            work_item_id=work_item_id,
            session_key=session_key,
            limit=20,
        )
        if not proposals:
            return {
                "pending_count": 0,
                "conflict_count": 0,
                "related_proposal_ids": [],
                "last_proposal_status": None,
                "last_proposal_id": None,
            }
        return {
            "pending_count": len([item for item in proposals if item.get("status") == "pending"]),
            "conflict_count": len([item for item in proposals if item.get("status") == "conflict"]),
            "related_proposal_ids": [item["proposal_id"] for item in proposals[:5]],
            "last_proposal_status": proposals[0].get("status"),
            "last_proposal_id": proposals[0].get("proposal_id"),
        }

    def _runtime_proposal_from_row(self, row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        apply_summary_json = row["apply_summary_json"] if isinstance(row, sqlite3.Row) else row.get("apply_summary_json")
        return {
            "proposal_id": row["proposal_id"],
            "branch": row["branch"],
            "task_id": row["task_id"],
            "work_item_id": row["work_item_id"],
            "proposal_type": row["proposal_type"],
            "status": row["status"],
            "session_key": row["session_key"],
            "subagent_id": row["subagent_id"],
            "owner_id": row["owner_id"],
            "base_revision": int(row["base_revision"]),
            "target_scope": json.loads(row["target_scope_json"]),
            "conflict_hints": json.loads(row["conflict_hints_json"]),
            "payload": json.loads(row["payload_json"]),
            "apply_summary": json.loads(apply_summary_json) if apply_summary_json else None,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "applied_at": row["applied_at"],
            "rejected_at": row["rejected_at"],
        }

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
        self._ensure_column(
            conn,
            table_name="work_items",
            column_name="scheduling_hints_json",
            ddl="TEXT NOT NULL DEFAULT '{}'",
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS work_item_dependencies (
                dependency_id TEXT PRIMARY KEY,
                branch TEXT NOT NULL,
                task_id TEXT NOT NULL,
                work_item_id TEXT NOT NULL,
                depends_on_work_item_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (work_item_id, depends_on_work_item_id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_work_item_dependencies_task ON work_item_dependencies(task_id, work_item_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_work_item_dependencies_target ON work_item_dependencies(depends_on_work_item_id, work_item_id)"
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
