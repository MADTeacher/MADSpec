from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .constants import DEFAULT_EMBEDDING_DIMENSION, SYSTEM_SCHEMA_VERSION


@dataclass(frozen=True)
class VectorNamespace:
    root_dir: Path
    namespace_dir: Path
    provider: str
    model: str
    revision: str
    dimension: int

    def relative_namespace(self, project_path: Path) -> str:
        return str(self.namespace_dir.relative_to(project_path))

    def to_payload(self, project_path: Path) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "revision": self.revision,
            "dimension": self.dimension,
            "path": self.relative_namespace(project_path),
        }


@dataclass(frozen=True)
class SystemMemoryPaths:
    system_dir: Path
    memory_dir: Path
    sqlite_file: Path
    vector_root_dir: Path
    lancedb_dir: Path
    active_vector_namespace: VectorNamespace
    active_vector_namespace_dir: Path
    schema_version: Path


def get_system_memory_paths(project_path: Path) -> SystemMemoryPaths:
    system_dir = project_path / ".madspec" / "system"
    memory_dir = system_dir / "memory"
    vector_root_dir = memory_dir / "lancedb"
    active_namespace = resolve_configured_vector_namespace(project_path, root_dir=vector_root_dir)
    return SystemMemoryPaths(
        system_dir=system_dir,
        memory_dir=memory_dir,
        sqlite_file=memory_dir / "memory.sqlite",
        vector_root_dir=vector_root_dir,
        lancedb_dir=vector_root_dir,
        active_vector_namespace=active_namespace,
        active_vector_namespace_dir=active_namespace.namespace_dir,
        schema_version=memory_dir / "schema-version.json",
    )


def resolve_vector_namespace(
    project_path: Path,
    *,
    provider: str,
    model: str | None,
    revision: str | None,
    dimension: int,
    root_dir: Path | None = None,
) -> VectorNamespace:
    vector_root_dir = root_dir or (project_path / ".madspec" / "system" / "memory" / "lancedb")
    model_segment = "default" if provider == "hash" else str(model or "").strip()
    if not model_segment:
        raise ValueError(f"Provider '{provider}' requires a non-empty model namespace")
    revision_segment = _normalize_namespace_segment(revision)
    dimension_segment = str(int(dimension))
    namespace_dir = vector_root_dir / provider / model_segment / revision_segment / dimension_segment
    return VectorNamespace(
        root_dir=vector_root_dir,
        namespace_dir=namespace_dir,
        provider=provider,
        model=model_segment,
        revision=revision_segment,
        dimension=int(dimension),
    )


def resolve_configured_vector_namespace(project_path: Path, *, root_dir: Path | None = None) -> VectorNamespace:
    from .provider_factory import resolve_configured_embeddings

    selection = resolve_configured_embeddings(project_path)
    return resolve_vector_namespace(
        project_path,
        provider=selection.provider,
        model=selection.model,
        revision=selection.revision,
        dimension=selection.dimension,
        root_dir=root_dir,
    )


def list_vector_namespaces(project_path: Path, *, root_dir: Path | None = None) -> list[VectorNamespace]:
    vector_root_dir = root_dir or (project_path / ".madspec" / "system" / "memory" / "lancedb")
    namespaces: list[VectorNamespace] = []
    if not vector_root_dir.exists():
        return namespaces
    for provider_dir in sorted(path for path in vector_root_dir.iterdir() if path.is_dir()):
        for model_dir in sorted(path for path in provider_dir.iterdir() if path.is_dir()):
            for revision_dir in sorted(path for path in model_dir.iterdir() if path.is_dir()):
                for dimension_dir in sorted(path for path in revision_dir.iterdir() if path.is_dir()):
                    try:
                        dimension = int(dimension_dir.name)
                    except ValueError:
                        continue
                    namespaces.append(
                        VectorNamespace(
                            root_dir=vector_root_dir,
                            namespace_dir=dimension_dir,
                            provider=provider_dir.name,
                            model=model_dir.name,
                            revision=revision_dir.name,
                            dimension=dimension,
                        )
                    )
    return namespaces


def has_legacy_flat_vector_layout(project_path: Path, *, root_dir: Path | None = None) -> bool:
    from .vector import VectorMemoryIndex

    vector_root_dir = root_dir or (project_path / ".madspec" / "system" / "memory" / "lancedb")
    if not vector_root_dir.exists():
        return False
    if any((vector_root_dir / name).exists() for name in ("memory_chunks.jsonl", "artifact_chunks.jsonl")):
        return True
    try:
        tables = set(VectorMemoryIndex(vector_root_dir, dimension=DEFAULT_EMBEDDING_DIMENSION).list_tables())
    except Exception:
        return False
    return bool({"memory_chunks", "artifact_chunks"} & tables)


def ensure_system_memory_layout(project_path: Path) -> list[Path]:
    from .provider_factory import resolve_configured_embeddings
    from .store import MemoryStore
    from .vector import VectorMemoryIndex

    paths = get_system_memory_paths(project_path)
    created: list[Path] = []
    for path in (
        paths.system_dir,
        paths.memory_dir,
        paths.vector_root_dir,
        paths.active_vector_namespace_dir,
    ):
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(path)

    store = MemoryStore(project_path)
    if not paths.sqlite_file.exists():
        created.append(paths.sqlite_file)
    store.ensure_schema()

    configured = resolve_configured_embeddings(project_path)
    vector_index = VectorMemoryIndex(
        paths.active_vector_namespace_dir,
        provider_kind=paths.active_vector_namespace.provider,
        model_key=paths.active_vector_namespace.model,
        revision=paths.active_vector_namespace.revision,
        dimension=paths.active_vector_namespace.dimension,
    )
    schema_payload = {
        "schemaVersion": SYSTEM_SCHEMA_VERSION,
        "sqlite": str(paths.sqlite_file.relative_to(project_path)),
        "vectorRootDir": str(paths.vector_root_dir.relative_to(project_path)),
        "vectorIndexDir": str(paths.active_vector_namespace_dir.relative_to(project_path)),
        "vectorBackend": vector_index.backend_name,
        "activeVectorNamespace": paths.active_vector_namespace.to_payload(project_path),
        "configuredEmbeddings": configured.to_config_payload(),
        "embedding": {
            "provider": paths.active_vector_namespace.provider,
            "model": paths.active_vector_namespace.model,
            "revision": paths.active_vector_namespace.revision,
            "dimension": paths.active_vector_namespace.dimension,
        },
    }
    existing_payload = None
    if paths.schema_version.exists():
        try:
            existing_payload = json.loads(paths.schema_version.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing_payload = None
    reindex_state = _extract_reindex_state(existing_payload)
    schema_payload.update(reindex_state)
    if existing_payload != schema_payload:
        paths.schema_version.write_text(
            json.dumps(schema_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if not existing_payload:
            created.append(paths.schema_version)
    return created


def read_schema_version_payload(project_path: Path) -> dict[str, Any] | None:
    schema_path = get_system_memory_paths(project_path).schema_version
    if not schema_path.exists():
        return None
    try:
        payload = json.loads(schema_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def record_successful_reindex(
    project_path: Path,
    namespace: VectorNamespace,
) -> None:
    ensure_system_memory_layout(project_path)
    paths = get_system_memory_paths(project_path)
    payload = read_schema_version_payload(project_path) or {}
    payload["lastIndexedNamespace"] = namespace.to_payload(project_path)
    payload["lastIndexedAt"] = datetime.now(tz=UTC).isoformat()
    paths.schema_version.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def build_reindex_status(project_path: Path) -> dict[str, Any]:
    paths = get_system_memory_paths(project_path)
    schema_payload = read_schema_version_payload(project_path) or {}
    active_namespace = paths.active_vector_namespace.to_payload(project_path)
    last_indexed_namespace = _normalize_namespace_payload(schema_payload.get("lastIndexedNamespace"))
    last_indexed_at = schema_payload.get("lastIndexedAt")

    if last_indexed_namespace is None:
        return {
            "ready": False,
            "reindexRequired": True,
            "reason": "not_confirmed",
            "message": (
                "Активное пространство индекса еще не подтверждено успешной полной переиндексацией. "
                "Выполните `madspec memory reindex`."
            ),
            "lastIndexedNamespace": None,
            "lastIndexedAt": last_indexed_at if isinstance(last_indexed_at, str) else None,
            "nextAction": "Run `madspec memory reindex` to confirm the active vector namespace.",
        }

    namespace_matches = all(
        last_indexed_namespace.get(key) == active_namespace.get(key)
        for key in ("provider", "model", "revision", "dimension", "path")
    )
    if namespace_matches:
        return {
            "ready": True,
            "reindexRequired": False,
            "reason": "current",
            "message": "Активное пространство индекса соответствует последней успешной полной переиндексации.",
            "lastIndexedNamespace": last_indexed_namespace,
            "lastIndexedAt": last_indexed_at if isinstance(last_indexed_at, str) else None,
            "nextAction": None,
        }

    return {
        "ready": False,
        "reindexRequired": True,
        "reason": "namespace_mismatch",
        "message": (
            "Текущие настройки embeddings указывают на другое пространство индекса, чем последняя успешная "
            "полная переиндексация. Выполните `madspec memory reindex`."
        ),
        "lastIndexedNamespace": last_indexed_namespace,
        "lastIndexedAt": last_indexed_at if isinstance(last_indexed_at, str) else None,
        "nextAction": "Run `madspec memory reindex` to rebuild the active vector namespace.",
    }


def _normalize_namespace_segment(value: str | None) -> str:
    if value is None:
        return "current"
    safe = value.strip().replace("/", "__")
    return safe or "current"


def _extract_reindex_state(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"lastIndexedNamespace": None, "lastIndexedAt": None}
    return {
        "lastIndexedNamespace": _normalize_namespace_payload(payload.get("lastIndexedNamespace")),
        "lastIndexedAt": payload.get("lastIndexedAt") if isinstance(payload.get("lastIndexedAt"), str) else None,
    }


def _normalize_namespace_payload(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    path = payload.get("path")
    if not isinstance(path, str) or not path.strip():
        return None
    try:
        dimension = int(payload.get("dimension"))
    except (TypeError, ValueError):
        return None
    normalized = {
        "provider": str(payload.get("provider") or "").strip(),
        "model": str(payload.get("model") or "").strip(),
        "revision": str(payload.get("revision") or "").strip(),
        "dimension": dimension,
        "path": path.strip(),
    }
    if not normalized["provider"] or not normalized["model"] or not normalized["revision"]:
        return None
    return normalized
