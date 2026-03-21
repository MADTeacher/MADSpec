from __future__ import annotations

from typing import Any

from .records import MEMORY_STATUSES, SEMANTIC_KINDS


def validate_record(record: dict[str, Any], *, allow_semantic_kind: bool = True) -> list[str]:
    errors: list[str] = []
    for key in ("id", "ts", "branch", "stage", "status", "source", "summary", "evidence"):
        if key not in record:
            errors.append(f"missing field '{key}'")
    if "status" in record and record["status"] not in MEMORY_STATUSES:
        errors.append(f"invalid status '{record['status']}'")
    if "evidence" in record and not isinstance(record["evidence"], list):
        errors.append("evidence must be a list")
    if "step_id" in record and record["step_id"] is not None and not isinstance(record["step_id"], str):
        errors.append("step_id must be a string or null")
    if "scope" in record and record["scope"] not in {"project", "branch", "step", "feature", "work-item"}:
        errors.append(f"invalid scope '{record['scope']}'")
    if not allow_semantic_kind and "semantic_kind" in record:
        errors.append("semantic_kind is not allowed in this record set")
    if "semantic_kind" in record and record["semantic_kind"] not in SEMANTIC_KINDS:
        errors.append(f"invalid semantic_kind '{record['semantic_kind']}'")
    return errors
