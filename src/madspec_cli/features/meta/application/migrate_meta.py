from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from ..infrastructure.migration import migrate_legacy_layout, scan_legacy_layout


@dataclass(frozen=True)
class PrepareMigrationRequest:
    project_path: Path


@dataclass(frozen=True)
class PrepareMigrationResult(PayloadResult):
    pass


@dataclass(frozen=True)
class ApplyMigrationRequest:
    project_path: Path


@dataclass(frozen=True)
class ApplyMigrationResult(PayloadResult):
    pass


def prepare(request: PrepareMigrationRequest) -> PrepareMigrationResult:
    madspec_dir = request.project_path / ".madspec"
    scan = scan_legacy_layout(request.project_path)
    if not madspec_dir.exists():
        status = "missing"
    elif not scan.artifacts_in_root:
        status = "noop"
    else:
        status = "pending"
    return PrepareMigrationResult(
        payload={
            "status": status,
            "target_branch": scan.target_branch,
            "artifact_count": len(scan.artifacts_in_root),
            "artifacts": [item.name for item in scan.artifacts_in_root],
        }
    )


def execute(request: ApplyMigrationRequest) -> ApplyMigrationResult:
    result = migrate_legacy_layout(request.project_path)
    return ApplyMigrationResult(
        payload={
            "target_branch": result.target_branch,
            "moved": result.moved,
            "skipped": result.skipped,
            "errors": result.errors,
            "moved_count": len(result.moved),
        }
    )
