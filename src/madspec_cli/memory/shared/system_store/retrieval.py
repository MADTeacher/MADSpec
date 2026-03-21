from __future__ import annotations

from pathlib import Path
from typing import Any

from ...domain.conflicts import PROJECT_MEMORY_BRANCH
from .constants import SEARCH_SCOPES
from .layout import get_system_memory_paths
from .store import MemoryStore
from .text import (
    _flatten_for_search,
    _record_search_text,
    _snapshot_summary,
    _snippet,
    _status_allowed,
)
from .vector import VectorMemoryIndex


class RetrievalOrchestrator:
    def __init__(self, project_path: Path) -> None:
        self.project_path = project_path
        self.store = MemoryStore(project_path)
        self.index = VectorMemoryIndex(get_system_memory_paths(project_path).lancedb_dir)

    def search(
        self,
        *,
        branch: str,
        stage: str,
        step_id: str | None,
        query: str | None,
        scope: str = "branch",
        recall_limit: int = 5,
        disable_semantic: bool = False,
        include_obsolete: bool = False,
        include_conflicted: bool = False,
        active_session: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_scope = scope if scope in SEARCH_SCOPES else "branch"
        active_session = active_session or {}
        auto_query = _build_auto_query(
            stage=stage,
            step_id=step_id,
            active_session=active_session,
        )
        resolved_query = (query or auto_query).strip()
        triggers = _semantic_triggers(
            stage=stage,
            query=query,
            active_session=active_session,
            resolved_query=resolved_query,
        )
        if not resolved_query:
            return {
                "query": query,
                "resolved_query": None,
                "scope": normalized_scope,
                "runtime_revision": self.store.fetch_branch_revision(branch),
                "semantic_enabled": False,
                "triggers": triggers,
                "exact_matches": [],
                "lexical_matches": [],
                "semantic_matches": [],
                "merged": [],
            }

        exact = self.store.exact_search(
            resolved_query,
            branch=branch,
            stage=stage,
            step_id=step_id,
            scope=normalized_scope,
            limit=recall_limit,
            include_obsolete=include_obsolete,
            include_conflicted=include_conflicted,
        )
        lexical = self.store.lexical_search(
            resolved_query,
            branch=branch,
            stage=stage,
            step_id=step_id,
            scope=normalized_scope,
            limit=recall_limit,
            include_obsolete=include_obsolete,
            include_conflicted=include_conflicted,
        )
        if resolved_query and len(exact) + len(lexical) < recall_limit:
            triggers = [*triggers, "recall_gap"]
        semantic_enabled = bool(resolved_query and not disable_semantic and triggers)
        semantic: list[dict[str, Any]] = []
        if semantic_enabled:
            self.store.process_pending_jobs(branch=branch, limit=max(recall_limit * 4, 20))
            semantic = self._semantic_search(
                resolved_query,
                branch=branch,
                stage=stage,
                step_id=step_id,
                scope=normalized_scope,
                limit=recall_limit,
                include_obsolete=include_obsolete,
                include_conflicted=include_conflicted,
            )

        merged = _rerank_results(
            exact=exact,
            lexical=lexical,
            semantic=semantic,
            branch=branch,
            stage=stage,
            step_id=step_id,
            limit=recall_limit,
        )
        self.store.log_retrieval_run(
            branch=branch,
            stage=stage,
            step_id=step_id,
            query=query,
            semantic_enabled=semantic_enabled,
            triggers=triggers,
            exact_count=len(exact),
            lexical_count=len(lexical),
            semantic_count=len(semantic),
            merged_count=len(merged),
        )
        return {
            "query": query,
            "resolved_query": resolved_query,
            "scope": normalized_scope,
            "runtime_revision": self.store.fetch_branch_revision(branch),
            "semantic_enabled": semantic_enabled,
            "triggers": triggers,
            "exact_matches": exact,
            "lexical_matches": lexical,
            "semantic_matches": semantic,
            "merged": merged,
        }

    def _semantic_search(
        self,
        query: str,
        *,
        branch: str,
        stage: str,
        step_id: str | None,
        scope: str,
        limit: int,
        include_obsolete: bool,
        include_conflicted: bool,
    ) -> list[dict[str, Any]]:
        candidates = self.index.search(
            query,
            branch=branch,
            stage=stage,
            step_id=step_id,
            scope=scope,
            limit=limit * 4,
        )
        hydrated: list[dict[str, Any]] = []
        for candidate in candidates:
            item = self._rehydrate_candidate(
                candidate,
                include_obsolete=include_obsolete,
                include_conflicted=include_conflicted,
            )
            if item is None:
                continue
            item["match_type"] = "semantic"
            item["score"] = candidate["score"]
            hydrated.append(item)
        return _dedupe_search_items(hydrated)[:limit]

    def _rehydrate_candidate(
        self,
        candidate: dict[str, Any],
        *,
        include_obsolete: bool,
        include_conflicted: bool,
    ) -> dict[str, Any] | None:
        source_type = candidate["source_type"]
        if source_type == "record":
            record = self.store.fetch_record(candidate["source_id"])
            if record is None:
                return None
            if record.get("content_hash") and record.get("content_hash") != candidate.get("content_hash"):
                return None
            if not _status_allowed(
                record.get("status"),
                include_obsolete=include_obsolete,
                include_conflicted=include_conflicted,
            ):
                return None
            return {
                "source_type": "record",
                "source_id": candidate["source_id"],
                "branch": record.get("branch"),
                "stage": record.get("stage"),
                "step_id": record.get("step_id"),
                "scope": record.get("scope"),
                "status": record.get("status"),
                "kind": record.get("semantic_kind") or record.get("record_type"),
                "summary": record.get("summary"),
                "snippet": candidate.get("snippet") or _snippet(_record_search_text(record)),
                "content_hash": candidate.get("content_hash"),
                "ts": record.get("ts"),
            }
        if source_type == "snapshot":
            branch, snapshot_key = candidate["source_id"].split(":", 1)
            snapshot = self.store.fetch_snapshot(branch, snapshot_key)
            if snapshot is None:
                return None
            if snapshot.get("_content_hash") != candidate.get("content_hash"):
                return None
            return {
                "source_type": "snapshot",
                "source_id": candidate["source_id"],
                "branch": branch,
                "stage": snapshot.get("_stage"),
                "step_id": None,
                "scope": "branch",
                "status": "validated",
                "kind": "snapshot",
                "summary": _snapshot_summary(snapshot_key, snapshot) or snapshot_key,
                "snippet": candidate.get("snippet") or _snippet(_flatten_for_search(snapshot)),
                "content_hash": candidate.get("content_hash"),
                "ts": snapshot.get("updatedAt") or snapshot.get("ratifiedAt"),
            }
        artifact = self.store.fetch_artifact(candidate["source_id"])
        if artifact is None:
            return None
        if artifact["content_hash"] != candidate.get("content_hash"):
            return None
        return {
            "source_type": "artifact",
            "source_id": candidate["source_id"],
            "branch": artifact["branch"],
            "stage": artifact["stage"],
            "step_id": None,
            "scope": "branch",
            "status": "validated",
            "kind": "artifact",
            "summary": artifact["path"],
            "snippet": candidate.get("snippet") or _snippet(artifact["content"]),
            "content_hash": artifact["content_hash"],
            "ts": artifact["updated_at"],
        }


def _semantic_triggers(
    *,
    stage: str,
    query: str | None,
    active_session: dict[str, Any],
    resolved_query: str,
) -> list[str]:
    triggers: list[str] = []
    if query and query.strip():
        triggers.append("explicit_query")
    if "implement" in stage or stage in {"review", "security"}:
        triggers.append("stage_requires_recall")
    if active_session.get("open_questions"):
        triggers.append("open_questions")
    if active_session.get("current_hypotheses"):
        triggers.append("active_hypotheses")
    if active_session.get("stage") == "idle" and resolved_query:
        triggers.append("session_start")
    return triggers


def _build_auto_query(*, stage: str, step_id: str | None, active_session: dict[str, Any]) -> str:
    parts = [
        str(active_session.get("active_goal") or ""),
        str(step_id or ""),
        " ".join(str(item) for item in active_session.get("open_questions", [])[:3]),
        " ".join(str(item) for item in active_session.get("current_hypotheses", [])[:3]),
        stage,
    ]
    return " ".join(part for part in parts if part).strip()


def _rerank_results(
    *,
    exact: list[dict[str, Any]],
    lexical: list[dict[str, Any]],
    semantic: list[dict[str, Any]],
    branch: str,
    stage: str,
    step_id: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for base_score, items in ((90, exact), (70, lexical), (50, semantic)):
        for position, item in enumerate(items):
            key = (item["source_type"], item["source_id"])
            current = merged.get(key)
            relevance = _relevance_bonus(item, branch=branch, stage=stage, step_id=step_id)
            score = base_score - position + relevance + float(item.get("score") or 0)
            if current is None or score > current["_score"]:
                merged[key] = {**item, "_score": score}
    rows = sorted(merged.values(), key=lambda item: item["_score"], reverse=True)
    return [{key: value for key, value in row.items() if key != "_score"} for row in rows[:limit]]


def _relevance_bonus(item: dict[str, Any], *, branch: str, stage: str, step_id: str | None) -> float:
    bonus = 0.0
    if item.get("branch") == PROJECT_MEMORY_BRANCH:
        bonus += 12.0
    if item.get("branch") == branch:
        bonus += 8.0
    if item.get("stage") == stage:
        bonus += 5.0
    if step_id and item.get("step_id") == step_id:
        bonus += 4.0
    if item.get("status") == "validated":
        bonus += 2.0
    return bonus


def _dedupe_search_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for item in items:
        key = (item["source_type"], item["source_id"])
        if key not in unique:
            unique[key] = item
    return list(unique.values())
