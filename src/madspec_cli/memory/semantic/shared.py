from __future__ import annotations

from pathlib import Path

from ..shared.text_lists import normalize_plain_text_list


def normalize_text_list(values: list[str] | None) -> list[str]:
    return normalize_plain_text_list(values, normalize_item=lambda value: value.strip() if isinstance(value, str) else "")


def snapshot_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def restore_file(path: Path, content: str | None) -> None:
    if content is None:
        if path.exists():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def append_unique(existing: list[str], values: list[str]) -> list[str]:
    result = list(existing)
    for value in values:
        if value not in result:
            result.append(value)
    return result
