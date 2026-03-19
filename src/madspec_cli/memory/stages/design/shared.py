from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ...shared.text_lists import normalize_plain_text_list
from ...shared.storage import PRIORITIES

FLOW_DATA_KINDS = {"displayed", "input"}


def normalize_identifier(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    if not text:
        return ""
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def normalize_string(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()


def normalize_path(value: Any) -> str:
    normalized = normalize_string(value)
    if not normalized:
        return ""
    return Path(normalized).as_posix()


def normalize_string_list(values: Any) -> list[str]:
    return normalize_plain_text_list(values, normalize_item=normalize_string)


def default_screen_coverage() -> dict[str, list[str]]:
    return {priority: [] for priority in PRIORITIES}


def default_screen_data() -> dict[str, list[str]]:
    return {"displayed": [], "input": []}


def append_unique_strings(target: list[str], values: list[str]) -> list[str]:
    result = list(target)
    for value in values:
        if value not in result:
            result.append(value)
    return result
