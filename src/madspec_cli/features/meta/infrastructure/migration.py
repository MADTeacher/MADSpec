from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.features.git.infrastructure.operations import get_current_branch
from madspec_cli.memory import consolidate_branch_memory, ensure_memory_layout
from madspec_cli.project_state import create_madspec_config, ensure_branch_dir


@dataclass(frozen=True)
class LegacyLayoutScan:
    target_branch: str
    artifacts_in_root: list[Path]


@dataclass(frozen=True)
class LegacyLayoutMigration:
    target_branch: str
    moved: list[str]
    skipped: list[str]
    errors: list[dict[str, str]]


def scan_legacy_layout(project_path: Path) -> LegacyLayoutScan:
    target_branch = get_current_branch(project_path)
    madspec_dir = project_path / ".madspec"
    if not madspec_dir.exists():
        return LegacyLayoutScan(target_branch=target_branch, artifacts_in_root=[])

    exclude_dirs = {"templates", target_branch}
    artifacts_in_root = [
        item
        for item in madspec_dir.iterdir()
        if item.is_file() or (item.is_dir() and item.name not in exclude_dirs)
    ]
    return LegacyLayoutScan(target_branch=target_branch, artifacts_in_root=artifacts_in_root)


def migrate_legacy_layout(project_path: Path) -> LegacyLayoutMigration:
    scan = scan_legacy_layout(project_path)
    target_dir = ensure_branch_dir(project_path, scan.target_branch)
    moved: list[str] = []
    skipped: list[str] = []
    errors: list[dict[str, str]] = []

    for item in scan.artifacts_in_root:
        target_path = target_dir / item.name
        if target_path.exists():
            skipped.append(item.name)
            continue
        try:
            item.rename(target_path)
            moved.append(item.name)
        except Exception as exc:
            errors.append({"name": item.name, "message": str(exc)})

    create_madspec_config(project_path, scan.target_branch)
    ensure_memory_layout(project_path, scan.target_branch)
    consolidate_branch_memory(project_path, scan.target_branch)
    return LegacyLayoutMigration(
        target_branch=scan.target_branch,
        moved=moved,
        skipped=skipped,
        errors=errors,
    )
