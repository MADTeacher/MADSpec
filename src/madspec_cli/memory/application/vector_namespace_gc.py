from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from madspec_cli.shared.kernel.result import PayloadResult

from ..shared.system_store.layout import get_system_memory_paths, list_vector_namespaces
from ..shared.system_store.vector import VectorMemoryIndex


@dataclass(frozen=True)
class VectorNamespaceGcRequest:
    project_path: Path
    dry_run: bool = False


@dataclass(frozen=True)
class VectorNamespaceGcResult(PayloadResult):
    pass


def execute(request: VectorNamespaceGcRequest) -> VectorNamespaceGcResult:
    paths = get_system_memory_paths(request.project_path)
    active_namespace = paths.active_vector_namespace
    inactive_items: list[dict[str, Any]] = []
    warnings: list[str] = []

    for namespace in list_vector_namespaces(request.project_path, root_dir=paths.vector_root_dir):
        if namespace.namespace_dir.resolve() == active_namespace.namespace_dir.resolve():
            continue
        item = _namespace_summary(request.project_path, namespace)
        inactive_items.append(item)

    inactive_items.sort(key=lambda item: str(item["path"]))
    deleted_namespaces: list[str] = []
    deleted_chunk_count = 0
    if not request.dry_run:
        for item in inactive_items:
            namespace_dir = request.project_path / str(item["path"])
            try:
                if namespace_dir.exists():
                    shutil.rmtree(namespace_dir)
                deleted_namespaces.append(str(item["path"]))
                deleted_chunk_count += int(item["semantic_chunk_count"])
            except Exception as exc:
                warnings.append(f"failed to remove {item['path']}: {exc}")

    payload = {
        "dry_run": request.dry_run,
        "active_namespace": active_namespace.to_payload(request.project_path),
        "candidates": inactive_items,
        "deleted_namespaces": deleted_namespaces,
        "deleted_chunk_count": deleted_chunk_count,
        "warnings": warnings,
    }
    return VectorNamespaceGcResult(payload=payload)


def _namespace_summary(project_path: Path, namespace) -> dict[str, Any]:
    index = VectorMemoryIndex(
        namespace.namespace_dir,
        provider_kind=namespace.provider,
        model_key=namespace.model,
        revision=namespace.revision,
        dimension=namespace.dimension,
    )
    semantic_sources = [
        item
        for item in index.list_chunk_sources("memory_chunks", source_type="record")
        if str(item.get("kind") or "") in {"fact", "decision", "contract"}
    ]
    semantic_chunk_count = sum(
        index.count_source_chunks("memory_chunks", source_type="record", source_id=str(item.get("source_id") or ""))
        for item in semantic_sources
        if str(item.get("source_id") or "")
    )
    return {
        **namespace.to_payload(project_path),
        "semantic_source_count": len(semantic_sources),
        "semantic_chunk_count": semantic_chunk_count,
    }
