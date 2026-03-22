from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from madspec_cli.memory.domain.branch_layout import resolve_target_branch

if TYPE_CHECKING:
    from madspec_cli.shared.kernel.ports import CurrentBranchResolver


def resolve_branch(
    project_path: Path,
    branch_name: str | None,
    *,
    _get_current_branch: CurrentBranchResolver | None = None,
) -> str:
    if _get_current_branch is None:
        from madspec_cli.features.git.infrastructure.operations import get_current_branch
        _get_current_branch = get_current_branch
    fallback = _get_current_branch(project_path)
    return resolve_target_branch(branch_name, fallback_branch=fallback)
