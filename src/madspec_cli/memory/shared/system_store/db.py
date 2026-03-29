from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .constants import LEASE_TTL_SECONDS
from .layout import get_system_memory_paths
from .text import _now_iso


class SystemStoreDB:
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
                    provider TEXT,
                    model TEXT,
                    revision TEXT,
                    dimension INTEGER,
                    namespace_path TEXT,
                    bootstrap_status TEXT,
                    semantic_outcome TEXT,
                    error_kind TEXT,
                    error_message TEXT,
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
        for column_name, ddl in (
            ("provider", "TEXT"),
            ("model", "TEXT"),
            ("revision", "TEXT"),
            ("dimension", "INTEGER"),
            ("namespace_path", "TEXT"),
            ("bootstrap_status", "TEXT"),
            ("semantic_outcome", "TEXT"),
            ("error_kind", "TEXT"),
            ("error_message", "TEXT"),
        ):
            self._ensure_column(
                conn,
                table_name="retrieval_runs",
                column_name=column_name,
                ddl=ddl,
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


class StoreComponent:
    def __init__(self, db: SystemStoreDB) -> None:
        self.db = db

    @property
    def project_path(self) -> Path:
        return self.db.project_path

    @property
    def paths(self):  # pragma: no cover - trivial proxy
        return self.db.paths

    def ensure_schema(self) -> None:
        self.db.ensure_schema()

    def connect(self) -> sqlite3.Connection:
        return self.db.connect()

    def connect_read_only(self) -> sqlite3.Connection:
        return self.db.connect_read_only()

    def _fts_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        return self.db._fts_exists(conn, table_name)

    def _upsert_fts_row(
        self,
        conn: sqlite3.Connection,
        *,
        table_name: str,
        columns: tuple[str, ...],
        values: tuple[Any, ...],
    ) -> None:
        self.db._upsert_fts_row(
            conn,
            table_name=table_name,
            columns=columns,
            values=values,
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
        self.db._enqueue_index_job(
            conn,
            source_type=source_type,
            source_id=source_id,
            branch=branch,
            stage=stage,
            step_id=step_id,
            content_hash=content_hash,
        )


__all__ = ["StoreComponent", "SystemStoreDB", "LEASE_TTL_SECONDS"]
