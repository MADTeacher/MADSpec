from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from madspec_cli.memory.shared.storage import read_json, write_json

from .paths import get_change_paths


def load_change_state(project_path: Path, branch_name: str) -> dict[str, Any] | None:
    return read_json(get_change_paths(project_path, branch_name).state_file, None)


def save_change_state(project_path: Path, branch_name: str, state: dict[str, Any]) -> dict[str, Any]:
    paths = get_change_paths(project_path, branch_name)
    paths.change_dir.mkdir(parents=True, exist_ok=True)
    write_json(paths.state_file, state)
    if not paths.proposals_file.exists():
        paths.proposals_file.write_text("", encoding="utf-8")
    if not paths.history_file.exists():
        paths.history_file.write_text("", encoding="utf-8")
    paths.export_dir.mkdir(parents=True, exist_ok=True)
    return state


def list_change_proposals(project_path: Path, branch_name: str) -> list[dict[str, Any]]:
    return read_jsonl(get_change_paths(project_path, branch_name).proposals_file)


def append_change_proposal(project_path: Path, branch_name: str, proposal: dict[str, Any]) -> None:
    append_jsonl(get_change_paths(project_path, branch_name).proposals_file, [proposal])


def append_change_history(project_path: Path, branch_name: str, event: dict[str, Any]) -> None:
    append_jsonl(get_change_paths(project_path, branch_name).history_file, [event])


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


__all__ = [
    "append_change_history",
    "append_change_proposal",
    "list_change_proposals",
    "load_change_state",
    "save_change_state",
]
