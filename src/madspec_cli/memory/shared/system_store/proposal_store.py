from __future__ import annotations

import json
import sqlite3
from typing import Any

from .db import StoreComponent
from .text import _content_hash, _dump_json, _normalized_optional_text, _now_iso


class ProposalStore(StoreComponent):
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
        return [
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
            for row in rows
        ]

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


__all__ = ["ProposalStore"]
