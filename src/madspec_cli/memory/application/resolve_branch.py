from __future__ import annotations

from pathlib import Path

from madspec_cli.features.git.infrastructure.operations import get_current_branch
from madspec_cli.memory.domain.branch_layout import resolve_target_branch


def resolve_branch(project_path: Path, branch_name: str | None) -> str:
    fallback = get_current_branch(project_path)
    return resolve_target_branch(branch_name, fallback_branch=fallback)
