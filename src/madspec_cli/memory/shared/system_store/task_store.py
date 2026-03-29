from __future__ import annotations

import json
import sqlite3
import uuid
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
from .db import StoreComponent
from .text import _dump_json, _normalized_optional_text, _now_iso


class TaskStore(StoreComponent):
    def __init__(self, db, *, runtime_store, proposal_store) -> None:
        super().__init__(db)
        self.runtime = runtime_store
        self.proposals = proposal_store

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
        related_proposals = self.proposals.list_runtime_proposals(branch=branch, work_item_id=work_item_id, limit=20)
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
        session_payload = self.runtime.fetch_session(branch=branch, session_key=session_key) or {}
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
            proposal_summary = self.proposals.summarize_runtime_proposals(
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
        related_proposals = self.proposals.list_runtime_proposals(
            branch=str(work_item["branch"]),
            work_item_id=str(work_item["work_item_id"]),
            limit=20,
        )
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
        self.runtime._upsert_record(
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
        self.runtime._upsert_record(
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


__all__ = ["TaskStore"]
