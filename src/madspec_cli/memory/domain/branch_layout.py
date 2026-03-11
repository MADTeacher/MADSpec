from __future__ import annotations

from pathlib import Path

from madspec_cli.project_state import resolve_branch_name


def resolve_target_branch(project_path: Path, branch_name: str | None) -> str:
    return resolve_branch_name(project_path, branch_name)
