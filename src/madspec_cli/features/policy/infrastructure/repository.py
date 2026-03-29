from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .normalization import default_policy_state, normalize_policy_state
from .paths import get_policy_paths


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def load_policy_state(project_path: Path, *, create_if_missing: bool = True) -> dict[str, Any]:
    if create_if_missing:
        from .service import ensure_policy_layout

        ensure_policy_layout(project_path)
    paths = get_policy_paths(project_path)
    return normalize_policy_state(read_json(paths.state_file, default_policy_state()))


def list_policy_proposals(
    project_path: Path,
    *,
    create_if_missing: bool = True,
) -> list[dict[str, Any]]:
    if create_if_missing:
        from .service import ensure_policy_layout

        ensure_policy_layout(project_path)
    proposals: dict[str, dict[str, Any]] = {}
    for item in read_jsonl(get_policy_paths(project_path).proposals_file):
        proposal_id = str(item.get("proposalId") or "").strip()
        if not proposal_id:
            continue
        proposals[proposal_id] = item
    return sorted(
        proposals.values(),
        key=lambda item: (item.get("requestedAt", ""), item.get("proposalId", "")),
        reverse=True,
    )


def list_policy_history(
    project_path: Path,
    *,
    create_if_missing: bool = True,
) -> list[dict[str, Any]]:
    if create_if_missing:
        from .service import ensure_policy_layout

        ensure_policy_layout(project_path)
    return sorted(
        read_jsonl(get_policy_paths(project_path).history_file),
        key=lambda item: (item.get("ts", ""), item.get("eventId", "")),
        reverse=True,
    )


__all__ = [
    "append_jsonl",
    "list_policy_history",
    "list_policy_proposals",
    "load_policy_state",
    "read_json",
    "read_jsonl",
    "write_json",
]
