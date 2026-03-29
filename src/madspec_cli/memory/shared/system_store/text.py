from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from ...domain.conflicts import PROJECT_MEMORY_BRANCH
from .constants import ARTIFACT_STAGE_HINTS, RECORD_STATUSES


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())


def _dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _tokenize(text: str) -> list[str]:
    normalized = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
    return [token for token in normalized.split() if token]


def _flatten_for_search(value: Any) -> str:
    parts: list[str] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            for key, item in node.items():
                parts.append(str(key))
                visit(item)
            return
        if isinstance(node, list):
            for item in node:
                visit(item)
            return
        if node is None:
            return
        parts.append(str(node))

    visit(value)
    return "\n".join(parts)


def _record_search_text(record: dict[str, Any]) -> str:
    parts = [
        str(record.get("summary") or ""),
        str(record.get("stage") or ""),
        str(record.get("step_id") or ""),
        str(record.get("source") or ""),
    ]
    evidence = record.get("evidence", [])
    if isinstance(evidence, list):
        parts.extend(str(item) for item in evidence if item)
    metadata = record.get("metadata")
    if metadata:
        parts.append(_flatten_for_search(metadata))
    return "\n".join(part for part in parts if part)


def _snapshot_summary(snapshot_key: str, payload: dict[str, Any]) -> str:
    for key in (
        "checkpointSummary",
        "planOverview",
        "stackOverview",
        "designOverview",
        "systemOverview",
        "featureGoal",
        "problem",
        "expectedOutcome",
        "active_goal",
    ):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return snapshot_key


def _snapshot_stage(snapshot_key: str) -> str:
    return "runtime.progress" if snapshot_key == "progress" else snapshot_key


def _artifact_stage(branch_name: str, path: Path) -> str | None:
    if path.name in ARTIFACT_STAGE_HINTS:
        return ARTIFACT_STAGE_HINTS[path.name]
    if "steps" in path.parts:
        return "mvp.implement" if branch_name else None
    return None


def _iso_from_mtime(path: Path) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(path.stat().st_mtime))


def _snippet(text: str, limit: int = 180) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def _matches_scope(
    *,
    row_branch: str | None,
    row_stage: str | None,
    row_step_id: str | None,
    branch: str,
    stage: str | None,
    step_id: str | None,
    scope: str,
) -> bool:
    if scope == "project":
        return row_branch == PROJECT_MEMORY_BRANCH
    if row_branch != branch:
        return False
    if scope == "branch":
        return True
    if scope == "stage":
        return row_stage == stage
    if scope == "step":
        return row_stage == stage and row_step_id == step_id
    return row_branch == branch


def _status_allowed(
    status: str | None,
    *,
    include_obsolete: bool,
    include_conflicted: bool,
) -> bool:
    if status == "obsolete" and not include_obsolete:
        return False
    if status == "conflicted" and not include_conflicted:
        return False
    return status in RECORD_STATUSES or status == "validated"


def _normalized_optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _sql_escape(value: str) -> str:
    return value.replace("'", "''")
