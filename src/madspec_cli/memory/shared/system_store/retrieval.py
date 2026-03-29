from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from ...domain.conflicts import PROJECT_MEMORY_BRANCH
from .constants import SEARCH_SCOPES
from .layout import VectorNamespace, get_system_memory_paths
from .provider_factory import (
    EmbeddingProviderRuntimeError,
    build_embedding_provider,
    resolve_configured_embeddings,
)
from .store import MemoryStore
from .text import (
    _flatten_for_search,
    _record_search_text,
    _snapshot_summary,
    _snippet,
    _status_allowed,
)
from .vector import BaseEmbeddingProvider, HashEmbeddingProvider, VectorMemoryIndex


class RetrievalEmbeddingProviderError(RuntimeError):
    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__(payload["message"])
        self.payload = payload


class RetrievalOrchestrator:
    def __init__(
        self,
        project_path: Path,
        *,
        provider: BaseEmbeddingProvider | None = None,
        provider_factory: Callable[[], BaseEmbeddingProvider] | None = None,
    ) -> None:
        self.project_path = project_path
        self.store = MemoryStore(project_path)
        self._provider = provider
        self._provider_factory = provider_factory or (
            lambda: build_embedding_provider(project_path, allow_bootstrap=True)
        )
        self._namespace: VectorNamespace | None = None
        self.index: VectorMemoryIndex | None = None
        if provider is not None:
            self.index = self._build_index(provider)

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
        configured_embeddings = resolve_configured_embeddings(self.project_path).to_status_payload(self.project_path)
        active_namespace = get_system_memory_paths(self.project_path).active_vector_namespace.to_payload(self.project_path)
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
        semantic_requested = bool(resolved_query and not disable_semantic and triggers)
        semantic_runtime = _build_semantic_runtime_payload(
            configured_embeddings=configured_embeddings,
            active_vector_namespace=active_namespace,
            semantic_requested=semantic_requested,
            semantic_used=False,
            semantic_outcome=_semantic_outcome(
                disable_semantic=disable_semantic,
                resolved_query=resolved_query,
                semantic_requested=semantic_requested,
            ),
        )
        if not resolved_query:
            return {
                "query": query,
                "resolved_query": None,
                "scope": normalized_scope,
                "runtime_revision": self.store.fetch_branch_revision(
                    PROJECT_MEMORY_BRANCH if normalized_scope == "project" else branch
                ),
                "semantic_enabled": False,
                "triggers": triggers,
                "semantic_runtime": semantic_runtime,
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
            semantic_requested = bool(resolved_query and not disable_semantic and triggers)
            semantic_runtime["semantic_requested"] = semantic_requested
            if semantic_runtime["semantic_outcome"] == "skipped":
                semantic_runtime["semantic_outcome"] = _semantic_outcome(
                    disable_semantic=disable_semantic,
                    resolved_query=resolved_query,
                    semantic_requested=semantic_requested,
                )
        semantic_enabled = semantic_requested
        semantic: list[dict[str, Any]] = []
        if semantic_enabled:
            try:
                provider, namespace = self._ensure_semantic_runtime()
            except EmbeddingProviderRuntimeError as exc:
                error_payload = _build_provider_error_payload(
                    exc=exc,
                    configured_embeddings=configured_embeddings,
                    active_vector_namespace=active_namespace,
                    branch=branch,
                    stage=stage,
                    step_id=step_id,
                    query=query,
                    resolved_query=resolved_query,
                    triggers=triggers,
                    exact_count=len(exact),
                    lexical_count=len(lexical),
                )
                semantic_runtime["semantic_outcome"] = "provider_error"
                semantic_runtime["provider_error"] = error_payload
                self.store.log_retrieval_run(
                    branch=branch,
                    stage=stage,
                    step_id=step_id,
                    query=query,
                    semantic_enabled=False,
                    triggers=triggers,
                    exact_count=len(exact),
                    lexical_count=len(lexical),
                    semantic_count=0,
                    merged_count=0,
                    provider=error_payload["provider"],
                    model=error_payload["model"],
                    revision=configured_embeddings.get("revision"),
                    dimension=configured_embeddings.get("dimension"),
                    namespace_path=active_namespace["path"],
                    bootstrap_status=error_payload["bootstrap"].get("status"),
                    semantic_outcome="provider_error",
                    error_kind=error_payload["kind"],
                    error_message=error_payload["message"],
                )
                raise RetrievalEmbeddingProviderError(error_payload) from exc
            semantic_runtime["semantic_used"] = True
            semantic_runtime["semantic_outcome"] = "used"
            semantic_runtime["runtime_provider"] = {
                "provider": provider.provider_kind,
                "model": provider.model_key,
                "revision": namespace.revision,
                "dimension": provider.dimension,
                "namespacePath": namespace.relative_namespace(self.project_path),
            }
            self.store.process_pending_jobs(
                branch=branch,
                limit=max(recall_limit * 4, 20),
                provider=provider,
                namespace=namespace,
            )
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
            semantic_enabled=semantic_runtime["semantic_used"],
            triggers=triggers,
            exact_count=len(exact),
            lexical_count=len(lexical),
            semantic_count=len(semantic),
            merged_count=len(merged),
            provider=((semantic_runtime.get("runtime_provider") or {}).get("provider") or configured_embeddings.get("provider")),
            model=((semantic_runtime.get("runtime_provider") or {}).get("model") or configured_embeddings.get("model")),
            revision=((semantic_runtime.get("runtime_provider") or {}).get("revision") or configured_embeddings.get("revision")),
            dimension=((semantic_runtime.get("runtime_provider") or {}).get("dimension") or configured_embeddings.get("dimension")),
            namespace_path=active_namespace["path"],
            bootstrap_status=((configured_embeddings.get("bootstrap") or {}).get("status") or configured_embeddings.get("status")),
            semantic_outcome=str(semantic_runtime["semantic_outcome"]),
            error_kind=None,
            error_message=None,
        )
        return {
            "query": query,
            "resolved_query": resolved_query,
            "scope": normalized_scope,
            "runtime_revision": self.store.fetch_branch_revision(
                PROJECT_MEMORY_BRANCH if normalized_scope == "project" else branch
            ),
            "semantic_enabled": semantic_runtime["semantic_used"],
            "triggers": triggers,
            "semantic_runtime": semantic_runtime,
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
        index = self._ensure_index()
        candidates = index.search(
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


    def _build_index(self, provider: BaseEmbeddingProvider) -> VectorMemoryIndex:
        namespace = get_system_memory_paths(self.project_path).active_vector_namespace
        self._namespace = namespace
        return VectorMemoryIndex(
            namespace.namespace_dir,
            provider=provider,
            provider_kind=namespace.provider,
            model_key=namespace.model,
            revision=namespace.revision,
            dimension=namespace.dimension,
        )

    def _ensure_semantic_runtime(self) -> tuple[BaseEmbeddingProvider, VectorNamespace]:
        if self._provider is None:
            self._provider = self._provider_factory()
        if self._namespace is None:
            self.index = self._build_index(self._provider)
        elif self.index is None:
            self.index = self._build_index(self._provider)
        return self._provider, self._namespace

    def _ensure_index(self) -> VectorMemoryIndex:
        if self.index is None:
            self._ensure_semantic_runtime()
        assert self.index is not None
        return self.index


def _build_semantic_runtime_payload(
    *,
    configured_embeddings: dict[str, Any],
    active_vector_namespace: dict[str, Any],
    semantic_requested: bool,
    semantic_used: bool,
    semantic_outcome: str,
) -> dict[str, Any]:
    return {
        "configured_embeddings": configured_embeddings,
        "active_vector_namespace": active_vector_namespace,
        "semantic_requested": semantic_requested,
        "semantic_used": semantic_used,
        "semantic_outcome": semantic_outcome,
        "runtime_provider": None,
        "provider_error": None,
    }


def _semantic_outcome(
    *,
    disable_semantic: bool,
    resolved_query: str | None,
    semantic_requested: bool,
) -> str:
    if disable_semantic:
        return "disabled"
    if not resolved_query or not semantic_requested:
        return "skipped"
    return "used"


def _build_provider_error_payload(
    *,
    exc: EmbeddingProviderRuntimeError,
    configured_embeddings: dict[str, Any],
    active_vector_namespace: dict[str, Any],
    branch: str,
    stage: str,
    step_id: str | None,
    query: str | None,
    resolved_query: str | None,
    triggers: list[str],
    exact_count: int,
    lexical_count: int,
) -> dict[str, Any]:
    bootstrap = (configured_embeddings.get("bootstrap") or {}).copy()
    return {
        "kind": "embedding_provider_error",
        "provider": exc.provider,
        "model": exc.model,
        "status": exc.status,
        "message": str(exc),
        "bootstrap": bootstrap,
        "branch": branch,
        "stage": stage,
        "step_id": step_id,
        "query": query,
        "resolved_query": resolved_query,
        "triggers": list(triggers),
        "exact_count": exact_count,
        "lexical_count": lexical_count,
        "active_vector_namespace": active_vector_namespace,
        "guidance": (
            "Run `madspec memory bootstrap-model`, then `madspec memory reindex`, "
            "or switch `.madspec/config.json` to a ready provider."
        ),
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
