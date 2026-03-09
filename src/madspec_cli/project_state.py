from __future__ import annotations

import json
from pathlib import Path

from .git_ops import get_current_branch
from .ui import console


def resolve_branch_name(project_path: Path, branch_name: str | None) -> str:
    return branch_name or get_current_branch(project_path)


def emit_json(payload: dict) -> None:
    console.print_json(json.dumps(payload, ensure_ascii=False))


def create_madspec_config(project_path: Path, branch_name: str) -> None:
    madspec_dir = project_path / ".madspec"
    madspec_dir.mkdir(exist_ok=True)
    config_file = madspec_dir / "config.json"
    config = {"currentBranch": branch_name, "version": "1.0.0"}
    config_file.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def ensure_branch_dir(project_path: Path, branch_name: str) -> Path:
    branch_dir = project_path / ".madspec" / branch_name
    branch_dir.mkdir(parents=True, exist_ok=True)
    return branch_dir
