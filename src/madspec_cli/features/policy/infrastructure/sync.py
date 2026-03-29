from __future__ import annotations

from pathlib import Path
from typing import Any

from .normalization import now_iso
from .paths import SYSTEM_POLICY_BRANCH, SYSTEM_POLICY_STAGE, get_policy_paths


def sync_policy_snapshot(project_path: Path, state: dict[str, Any]) -> None:
    from madspec_cli.memory.shared.system_store.layout import ensure_system_memory_layout
    from madspec_cli.memory.shared.system_store.store import MemoryStore

    ensure_system_memory_layout(project_path)
    store = MemoryStore(project_path)
    paths = get_policy_paths(project_path)
    store.upsert_stage_snapshot(
        branch=SYSTEM_POLICY_BRANCH,
        snapshot_key="policy",
        payload=state,
        source_path=str(paths.state_file.relative_to(project_path)),
    )


def sync_policy_artifact(project_path: Path, content: str) -> None:
    from madspec_cli.memory.shared.system_store.layout import ensure_system_memory_layout
    from madspec_cli.memory.shared.system_store.store import MemoryStore

    ensure_system_memory_layout(project_path)
    store = MemoryStore(project_path)
    paths = get_policy_paths(project_path)
    store.upsert_artifact(
        artifact_id=str(paths.artifact_file.relative_to(project_path)),
        branch=SYSTEM_POLICY_BRANCH,
        stage=SYSTEM_POLICY_STAGE,
        path=str(paths.artifact_file.relative_to(project_path)),
        content=content,
        updated_at=now_iso(),
    )


def sync_policy_record(project_path: Path, record: dict[str, Any]) -> None:
    from madspec_cli.memory.shared.system_store.layout import ensure_system_memory_layout
    from madspec_cli.memory.shared.system_store.store import MemoryStore

    ensure_system_memory_layout(project_path)
    store = MemoryStore(project_path)
    store.upsert_record(record)


def refresh_branch_policy_views(project_path: Path) -> None:
    from madspec_cli.memory.views import consolidate_branch_memory

    madspec_dir = project_path / ".madspec"
    if not madspec_dir.exists():
        return
    for path in madspec_dir.iterdir():
        if not path.is_dir() or path.name == "system":
            continue
        consolidate_branch_memory(project_path, path.name)


__all__ = [
    "refresh_branch_policy_views",
    "sync_policy_artifact",
    "sync_policy_record",
    "sync_policy_snapshot",
]
