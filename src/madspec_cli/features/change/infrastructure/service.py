from __future__ import annotations

import uuid
from pathlib import Path

from madspec_cli.features.change.infrastructure.git_ops import ensure_git_change_support
from madspec_cli.memory.shared.storage import now_iso

from ..domain.models import CHANGE_SCHEMA_VERSION
from .paths import get_change_paths
from .repository import append_change_history, load_change_state, save_change_state
from .snapshot import capture_branch_snapshot


def ensure_change_layout(
    project_path: Path,
    branch_name: str,
    *,
    base_branch: str,
    base_revision: str,
) -> tuple[dict, list[str], list[Path]]:
    ensure_git_change_support(project_path)
    paths = get_change_paths(project_path, branch_name)
    created: list[Path] = []
    warnings: list[str] = []
    state = load_change_state(project_path, branch_name)
    if state is not None:
        if state.get("baseBranch") != base_branch or state.get("baseRevision") != base_revision:
            raise ValueError(
                "change store is already initialized with a different baseline; "
                "use the existing baseline or recreate the branch change store explicitly"
            )
        return state, warnings, created

    for path in (paths.branch_dir, paths.change_dir, paths.export_dir):
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(path)
    if not paths.proposals_file.exists():
        paths.proposals_file.write_text("", encoding="utf-8")
        created.append(paths.proposals_file)
    if not paths.history_file.exists():
        paths.history_file.write_text("", encoding="utf-8")
        created.append(paths.history_file)

    baseline, baseline_warnings = capture_branch_snapshot(project_path, base_branch)
    warnings.extend(baseline_warnings)
    bundle_id = f"chg-{uuid.uuid4().hex[:10]}"
    now = now_iso()
    state = {
        "schemaVersion": CHANGE_SCHEMA_VERSION,
        "branch": branch_name,
        "bundleId": bundle_id,
        "baseBranch": base_branch,
        "baseRevision": base_revision,
        "createdAt": now,
        "updatedAt": now,
        "revision": 0,
        "baseline": baseline,
        "activeBundle": None,
    }
    save_change_state(project_path, branch_name, state)
    append_change_history(
        project_path,
        branch_name,
        {
            "eventId": str(uuid.uuid4()),
            "eventType": "change_initialized",
            "bundleId": bundle_id,
            "ts": now,
            "summary": f"Initialized change store for branch {branch_name}",
            "payload": {"baseBranch": base_branch, "baseRevision": base_revision},
        },
    )
    created.append(paths.state_file)
    return state, warnings, created


__all__ = ["ensure_change_layout"]
