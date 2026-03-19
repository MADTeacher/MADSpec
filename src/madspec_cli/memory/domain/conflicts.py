from __future__ import annotations

import hashlib
import json
from typing import Any

PROJECT_MEMORY_BRANCH = "__project__"

CONFLICT_KINDS = {
    "snapshot_conflict",
    "progress_conflict",
    "semantic_conflict",
}

MERGE_RESOLUTIONS = {
    "keep_target",
    "take_source",
    "take_base",
    "union",
}

VOLATILE_RECORD_KEYS = {
    "id",
    "ts",
    "branch",
    "source",
    "content_hash",
}

VOLATILE_METADATA_KEYS = {
    "fingerprint",
    "sourceBranch",
    "originRecordId",
    "promotionTs",
    "contentHash",
}


def normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().lower().split())


def normalize_semantic_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key in sorted(value):
            if key in VOLATILE_METADATA_KEYS:
                continue
            normalized[key] = normalize_semantic_metadata(value[key])
        return normalized
    if isinstance(value, list):
        return [normalize_semantic_metadata(item) for item in value]
    if isinstance(value, str):
        stripped = value.strip()
        return stripped
    return value


def semantic_fingerprint(record: dict[str, Any]) -> str:
    payload = {
        "semantic_kind": str(record.get("semantic_kind") or record.get("record_type") or ""),
        "stage": str(record.get("stage") or ""),
        "step_id": str(record.get("step_id") or ""),
        "summary": normalize_text(record.get("summary")),
        "metadata": normalize_semantic_metadata(record.get("metadata") or {}),
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def semantic_content_payload(record: dict[str, Any]) -> dict[str, Any]:
    payload = {
        key: value
        for key, value in record.items()
        if key not in VOLATILE_RECORD_KEYS
    }
    payload["summary"] = " ".join(str(payload.get("summary") or "").split())
    evidence = payload.get("evidence")
    if isinstance(evidence, list):
        payload["evidence"] = sorted({str(item).strip() for item in evidence if str(item).strip()})
    payload["metadata"] = normalize_semantic_metadata(payload.get("metadata") or {})
    return payload


def semantic_content_hash(record: dict[str, Any]) -> str:
    payload = semantic_content_payload(record)
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def project_record_id(record: dict[str, Any]) -> str:
    semantic_kind = str(record.get("semantic_kind") or record.get("record_type") or "record")
    return f"project:{semantic_kind}:{semantic_fingerprint(record)}"


def make_conflict_id(kind: str, section: str, subject: str) -> str:
    return f"{kind}:{section}:{subject}"


def resolution_allowed(resolution: str, *, allowed: list[str]) -> bool:
    return resolution in MERGE_RESOLUTIONS and resolution in allowed
