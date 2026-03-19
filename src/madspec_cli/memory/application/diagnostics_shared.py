from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..shared.storage import get_memory_paths

STATUS_RANK = {"ok": 0, "warn": 1, "error": 2}


def overall_status(statuses: list[str]) -> str:
    if not statuses:
        return "ok"
    return max(statuses, key=lambda item: STATUS_RANK.get(item, 0))


def simplify_record(record: dict[str, Any]) -> dict[str, Any]:
    payload = record.get("payload", {})
    if not isinstance(payload, dict):
        payload = {}
    return {
        "record_id": record.get("record_id") or payload.get("id"),
        "summary": record.get("summary") or payload.get("summary"),
        "branch": record.get("branch") or payload.get("branch"),
        "stage": record.get("stage") or payload.get("stage"),
        "step_id": record.get("step_id") or payload.get("step_id"),
        "status": record.get("status") or payload.get("status"),
        "kind": record.get("kind") or payload.get("kind") or payload.get("record_type"),
        "semantic_kind": record.get("semantic_kind") or payload.get("semantic_kind"),
        "ts": record.get("ts") or payload.get("ts"),
    }


def record_source_paths(project_path: Path, branch_name: str) -> list[Path]:
    paths = get_memory_paths(project_path, branch_name)
    return [
        paths.decision_log,
        paths.events,
        paths.facts,
        paths.decisions,
        paths.contracts,
    ]


def locate_record_source(project_path: Path, branch_name: str, record_id: str) -> str | None:
    for path in record_source_paths(project_path, branch_name):
        if not path.exists():
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("id") == record_id:
                return f"{path.relative_to(project_path)}:{line_no}"
    return None
