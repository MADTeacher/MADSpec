from __future__ import annotations

import re
from typing import Any, Callable


TextNormalizer = Callable[[Any], str]


def default_normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()


def normalize_plain_text_list(
    values: Any,
    *,
    normalize_item: TextNormalizer | None = None,
) -> list[str]:
    normalized, _ = normalize_plain_text_list_with_repairs(values, normalize_item=normalize_item)
    return normalized


def normalize_plain_text_list_with_repairs(
    values: Any,
    *,
    field_name: str | None = None,
    normalize_item: TextNormalizer | None = None,
) -> tuple[list[str], list[dict[str, str]]]:
    normalizer = normalize_item or default_normalize_text
    if not isinstance(values, list):
        return [], []

    repaired_values = values
    warnings: list[dict[str, str]] = []
    if _looks_like_char_split_payload(values):
        joined = normalizer("".join(values))
        if joined:
            repaired_values = [joined]
            warnings.append(
                {
                    "field": field_name or "",
                    "code": "char_split_join",
                    "message": "Detected an array of single-character strings and joined it into one text item.",
                }
            )

    normalized: list[str] = []
    for value in repaired_values:
        item = normalizer(value)
        if item and item not in normalized:
            normalized.append(item)
    return normalized, warnings


def _looks_like_char_split_payload(values: list[Any]) -> bool:
    if len(values) < 8:
        return False
    if not all(isinstance(value, str) and len(value) <= 1 for value in values):
        return False

    non_whitespace_count = sum(1 for value in values if value.strip())
    if non_whitespace_count < 6:
        return False

    normalized_joined = default_normalize_text("".join(values))
    return len(normalized_joined) >= 4
