from __future__ import annotations

import math
import re
from typing import Any

import typer

from .banners import console


_SAFE_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
_NUMBER_LIKE_RE = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$")
_RESERVED_SCALARS = {"null", "true", "false"}


def emit_toon(payload: Any) -> None:
    console.print(encode_toon(payload), markup=False, highlight=False)


def ensure_structured_output_mode(*, json_output: bool, toon_output: bool) -> None:
    if json_output and toon_output:
        raise typer.BadParameter("Use either --json-output or --toon-output, not both.")


def encode_toon(value: Any) -> str:
    return "\n".join(_encode_value(value, level=0)).rstrip() + "\n"


def _encode_value(value: Any, *, level: int) -> list[str]:
    if isinstance(value, dict):
        return _encode_object(value, level=level)
    if isinstance(value, list):
        return _encode_array(value, level=level)
    return [_indent(level) + _render_scalar(value)]


def _encode_object(value: dict[str, Any], *, level: int) -> list[str]:
    if not value:
        return [_indent(level) + "{}"]

    lines: list[str] = []
    for key, item in value.items():
        rendered_key = _render_key(str(key))
        if _is_scalar(item):
            lines.append(f"{_indent(level)}{rendered_key}: {_render_scalar(item)}")
            continue
        if isinstance(item, list):
            inline = _render_inline_array(item)
            if inline is not None:
                lines.append(f"{_indent(level)}{rendered_key}{inline}")
                continue
            tabular = _render_tabular_array(item, level=level, prefix=f"{rendered_key}")
            if tabular is not None:
                lines.extend(tabular)
                continue
        lines.append(f"{_indent(level)}{rendered_key}:")
        lines.extend(_encode_nested(item, level=level + 1))
    return lines


def _encode_array(value: list[Any], *, level: int) -> list[str]:
    inline = _render_inline_array(value)
    if inline is not None:
        return [_indent(level) + inline.lstrip()]

    tabular = _render_tabular_array(value, level=level, prefix="")
    if tabular is not None:
        return tabular

    lines = [f"{_indent(level)}[{len(value)}]:"]
    for item in value:
        if _is_scalar(item):
            lines.append(f"{_indent(level + 1)}- {_render_scalar(item)}")
            continue
        nested = _encode_nested(item, level=level + 1)
        first, *rest = nested
        lines.append(f"{_indent(level + 1)}- {first.strip()}")
        for line in rest:
            lines.append(f"{_indent(level + 2)}{line.strip()}")
    return lines


def _encode_nested(value: Any, *, level: int) -> list[str]:
    if isinstance(value, dict):
        return _encode_object(value, level=level)
    if isinstance(value, list):
        return _encode_array(value, level=level)
    return [_indent(level) + _render_scalar(value)]


def _render_inline_array(value: list[Any]) -> str | None:
    if not all(_is_scalar(item) for item in value):
        return None
    rendered = ",".join(_render_scalar(item) for item in value)
    return f"[{len(value)}]: {rendered}"


def _render_tabular_array(value: list[Any], *, level: int, prefix: str) -> list[str] | None:
    if not value:
        return None
    if not all(isinstance(item, dict) for item in value):
        return None

    rows = [item for item in value if isinstance(item, dict)]
    if not rows:
        return None

    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            key_str = str(key)
            if key_str not in seen:
                seen.add(key_str)
                columns.append(key_str)

    if not columns:
        return None
    if any(not all(_is_scalar(row.get(column)) for column in columns) for row in rows):
        return None

    header = ",".join(_render_key(column) for column in columns)
    line_prefix = _indent(level)
    if prefix:
        line_prefix += prefix
    lines = [f"{line_prefix}[{len(rows)},]{{{header}}}:"]
    for row in rows:
        rendered_row = ",".join(_render_scalar(row.get(column)) for column in columns)
        lines.append(f"{_indent(level + 1)}{rendered_row}")
    return lines


def _render_key(value: str) -> str:
    return value if _SAFE_KEY_RE.fullmatch(value) else _quote(value)


def _render_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return "null"
        return str(value).replace("-0.0", "0.0")
    if isinstance(value, str):
        return _render_string(value)
    return _quote(str(value))


def _render_string(value: str) -> str:
    if not value:
        return _quote(value)
    if value.strip() != value:
        return _quote(value)
    if value.lower() in _RESERVED_SCALARS:
        return _quote(value)
    if _NUMBER_LIKE_RE.fullmatch(value):
        return _quote(value)
    if any(char in value for char in (",", ":", "[", "]", "{", "}", "#", "\n", "\r", "\t", '"')):
        return _quote(value)
    return value


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return f'"{escaped}"'


def _indent(level: int) -> str:
    return "  " * level


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (bool, int, float, str))
