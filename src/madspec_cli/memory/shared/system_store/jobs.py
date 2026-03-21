from __future__ import annotations

import os
import sqlite3
import time
import uuid
from typing import TYPE_CHECKING, Any

from .leases import normalize_writer_lease_row
from .text import _dump_json, _flatten_for_search, _now_iso, _record_search_text
from .vector import VectorMemoryIndex, _chunk_source_text

if TYPE_CHECKING:
    from .store import MemoryStore


def acquire_lease(
    store: MemoryStore,
    lease_name: str,
    owner_id: str,
    *,
    ttl_seconds: int,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    now = int(time.time())
    expires_at = now + ttl_seconds
    updated_at = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(now))
    if conn is None:
        with store.connect() as managed_conn:
            return acquire_lease(
                store,
                lease_name,
                owner_id,
                ttl_seconds=ttl_seconds,
                conn=managed_conn,
            )
    current = conn.execute(
        "SELECT owner_id, expires_at, updated_at FROM writer_leases WHERE lease_name = ?",
        (lease_name,),
    ).fetchone()
    if current and current["expires_at"] > now and current["owner_id"] != owner_id:
        return {
            "acquired": False,
            "lease": normalize_writer_lease_row(
                {
                    "lease_name": lease_name,
                    "owner_id": current["owner_id"],
                    "expires_at": current["expires_at"],
                    "updated_at": current["updated_at"],
                },
                now_epoch=now,
            ),
        }
    conn.execute(
        """
        INSERT INTO writer_leases (lease_name, owner_id, expires_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(lease_name) DO UPDATE SET
            owner_id=excluded.owner_id,
            expires_at=excluded.expires_at,
            updated_at=excluded.updated_at
        """,
        (lease_name, owner_id, expires_at, updated_at),
    )
    return {
        "acquired": True,
        "lease": normalize_writer_lease_row(
            {
                "lease_name": lease_name,
                "owner_id": owner_id,
                "expires_at": expires_at,
                "updated_at": updated_at,
            },
            now_epoch=now,
        ),
    }


def release_lease(
    store: MemoryStore,
    lease_name: str,
    owner_id: str,
    *,
    conn: sqlite3.Connection | None = None,
) -> None:
    if conn is None:
        with store.connect() as managed_conn:
            release_lease(store, lease_name, owner_id, conn=managed_conn)
        return
    conn.execute(
        "DELETE FROM writer_leases WHERE lease_name = ? AND owner_id = ?",
        (lease_name, owner_id),
    )


def process_pending_jobs(
    store: MemoryStore,
    *,
    branch: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    owner_id = f"{os.getpid()}-{uuid.uuid4()}"
    lease_result = acquire_lease(store, "indexer", owner_id, ttl_seconds=30)
    if not lease_result["acquired"]:
        return {"processed": 0, "failed": 0, "lease_acquired": False}
    index = VectorMemoryIndex(store.paths.lancedb_dir)
    index.ensure_layout()
    processed = 0
    failed = 0
    try:
        with store.connect() as conn:
            sql = "SELECT * FROM index_jobs WHERE status IN ('pending', 'failed')"
            params: list[Any] = []
            if branch:
                sql += " AND branch = ?"
                params.append(branch)
            sql += " ORDER BY updated_at ASC, job_id ASC LIMIT ?"
            params.append(limit)
            jobs = conn.execute(sql, params).fetchall()

        for job in jobs:
            try:
                _process_job(store, index, dict(job))
                processed += 1
            except Exception as exc:
                failed += 1
                with store.connect() as conn:
                    conn.execute(
                        """
                        UPDATE index_jobs
                        SET status = 'failed', error = ?, attempts = attempts + 1, updated_at = ?
                        WHERE job_id = ?
                        """,
                        (str(exc), _now_iso(), job["job_id"]),
                    )
    finally:
        release_lease(store, "indexer", owner_id)
    return {"processed": processed, "failed": failed, "lease_acquired": True}


def log_retrieval_run(
    store: MemoryStore,
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
    with store.connect() as conn:
        conn.execute(
            """
            INSERT INTO retrieval_runs (
                run_id, branch, stage, step_id, query, semantic_enabled, triggers_json,
                exact_count, lexical_count, semantic_count, merged_count, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                branch,
                stage,
                step_id,
                query,
                1 if semantic_enabled else 0,
                _dump_json(triggers),
                exact_count,
                lexical_count,
                semantic_count,
                merged_count,
                _now_iso(),
            ),
        )


def _process_job(store: MemoryStore, index: VectorMemoryIndex, job: dict[str, Any]) -> None:
    source_type = job["source_type"]
    source_id = job["source_id"]
    branch = job["branch"]
    stage = job["stage"]
    step_id = job["step_id"]
    if source_type == "record":
        record = store.fetch_record(source_id)
        if record is None:
            return
        chunks = _chunk_source_text(
            source_type="record",
            source_id=source_id,
            branch=branch,
            stage=stage,
            step_id=step_id,
            scope=record.get("scope"),
            status=record.get("status"),
            kind=record.get("semantic_kind") or record.get("record_type") or "event",
            content_hash=job["content_hash"],
            text=_record_search_text(record),
            provider=index.provider,
            table_name="memory_chunks",
        )
    elif source_type == "snapshot":
        snapshot_branch, snapshot_key = source_id.split(":", 1)
        snapshot = store.fetch_snapshot(snapshot_branch, snapshot_key)
        if snapshot is None:
            return
        chunks = _chunk_source_text(
            source_type="snapshot",
            source_id=source_id,
            branch=snapshot_branch,
            stage=snapshot.get("_stage") or stage,
            step_id=None,
            scope="branch",
            status="validated",
            kind="snapshot",
            content_hash=job["content_hash"],
            text=_flatten_for_search(snapshot),
            provider=index.provider,
            table_name="memory_chunks",
        )
    else:
        artifact = store.fetch_artifact(source_id)
        if artifact is None:
            return
        chunks = _chunk_source_text(
            source_type="artifact",
            source_id=source_id,
            branch=artifact["branch"],
            stage=artifact["stage"],
            step_id=None,
            scope="branch",
            status="validated",
            kind="artifact",
            content_hash=artifact["content_hash"],
            text=artifact["content"],
            provider=index.provider,
            table_name="artifact_chunks",
        )
    if chunks:
        index.upsert_chunks(chunks[0]["table_name"], chunks)
    with store.connect() as conn:
        conn.execute(
            """
            UPDATE index_jobs
            SET status = 'indexed', error = NULL, attempts = attempts + 1, updated_at = ?
            WHERE job_id = ?
            """,
            (_now_iso(), job["job_id"]),
        )
