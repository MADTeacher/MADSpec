from __future__ import annotations

import re
from typing import Any

SUPPORTED_API_STYLE = "rest-openapi"
ENDPOINT_FIELD_SECTIONS = {"path", "query", "request"}


def normalize_string(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()


def normalize_identifier(value: Any) -> str:
    normalized = normalize_string(value).lower()
    if not normalized:
        return ""
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    return normalized.strip("-")


def normalize_name_key(value: Any) -> str:
    normalized = normalize_string(value).lower()
    if not normalized:
        return ""
    return re.sub(r"[^a-z0-9]+", "", normalized)


def canonical_field_reference(value: Any) -> str:
    normalized = normalize_string(value)
    if not normalized:
        return ""
    canonical = normalized.split("::", 1)[0].strip().casefold()
    if not canonical:
        return ""
    return "".join(char for char in canonical if char.isalnum())


def normalize_required_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = normalize_string(value).lower()
    return normalized in {"required", "true", "yes", "1"}


def normalize_string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for value in values:
        normalized = normalize_string(value)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def normalize_path(value: Any) -> str:
    normalized = normalize_string(value)
    return normalized.replace("\\", "/")


def normalize_endpoint_sections(value: Any) -> str:
    normalized = normalize_string(value).lower()
    if normalized in ENDPOINT_FIELD_SECTIONS:
        return normalized
    if normalized == "response":
        return "response:200"
    if normalized.startswith("response:") and len(normalized) > len("response:"):
        return normalized
    return ""


def append_unique_strings(target: list[str], values: list[str]) -> list[str]:
    result = list(target)
    for value in values:
        if value not in result:
            result.append(value)
    return result


def append_unique_dicts(
    target: list[dict[str, Any]],
    values: list[dict[str, Any]],
    *,
    marker_fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    result = list(target)
    seen = {tuple(item.get(field, "") for field in marker_fields) for item in result}
    for value in values:
        marker = tuple(value.get(field, "") for field in marker_fields)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(value)
    return result
