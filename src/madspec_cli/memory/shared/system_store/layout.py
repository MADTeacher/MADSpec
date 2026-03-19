from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .constants import DEFAULT_EMBEDDING_DIMENSION, SYSTEM_SCHEMA_VERSION


@dataclass(frozen=True)
class SystemMemoryPaths:
    system_dir: Path
    memory_dir: Path
    sqlite_file: Path
    lancedb_dir: Path
    schema_version: Path


def get_system_memory_paths(project_path: Path) -> SystemMemoryPaths:
    system_dir = project_path / ".madspec" / "system"
    memory_dir = system_dir / "memory"
    return SystemMemoryPaths(
        system_dir=system_dir,
        memory_dir=memory_dir,
        sqlite_file=memory_dir / "memory.sqlite",
        lancedb_dir=memory_dir / "lancedb",
        schema_version=memory_dir / "schema-version.json",
    )


def ensure_system_memory_layout(project_path: Path) -> list[Path]:
    from .store import MemoryStore
    from .vector import VectorMemoryIndex

    paths = get_system_memory_paths(project_path)
    created: list[Path] = []
    for path in (paths.system_dir, paths.memory_dir, paths.lancedb_dir):
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(path)

    store = MemoryStore(project_path)
    if not paths.sqlite_file.exists():
        created.append(paths.sqlite_file)
    store.ensure_schema()

    schema_payload = {
        "schemaVersion": SYSTEM_SCHEMA_VERSION,
        "sqlite": str(paths.sqlite_file.relative_to(project_path)),
        "vectorIndexDir": str(paths.lancedb_dir.relative_to(project_path)),
        "vectorBackend": VectorMemoryIndex(paths.lancedb_dir).backend_name,
        "embedding": {
            "provider": "local-hash",
            "dimension": DEFAULT_EMBEDDING_DIMENSION,
        },
    }
    existing_payload = None
    if paths.schema_version.exists():
        try:
            existing_payload = json.loads(paths.schema_version.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing_payload = None
    if existing_payload != schema_payload:
        paths.schema_version.write_text(
            json.dumps(schema_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if not existing_payload:
            created.append(paths.schema_version)
    return created
