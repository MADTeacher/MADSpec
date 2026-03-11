from __future__ import annotations

from typing import Any

from ...shared.storage import PRIORITIES
from .normalizers import normalize_flow_steps
from .shared import FLOW_DATA_KINDS, append_unique_strings, normalize_string_list


def upsert_zone(target: list[dict[str, str]], value: dict[str, str]) -> list[dict[str, str]]:
    zone_id = value.get("id", "")
    if not zone_id:
        return target
    result = []
    updated = False
    for item in target:
        if item.get("id") != zone_id:
            result.append(item)
            continue
        updated = True
        result.append(
            {
                "id": zone_id,
                "title": value.get("title") or item.get("title", ""),
                "description": value.get("description") or item.get("description", ""),
            }
        )
    if not updated:
        result.append({"id": zone_id, "title": value.get("title", ""), "description": value.get("description", "")})
    return result


def upsert_screen(target: list[dict[str, Any]], value: dict[str, Any]) -> list[dict[str, Any]]:
    screen_id = value.get("id", "")
    if not screen_id:
        return target
    result = []
    updated = False
    for item in target:
        if item.get("id") != screen_id:
            result.append(item)
            continue
        updated = True
        merged = {
            "id": screen_id,
            "title": value.get("title") or item.get("title", ""),
            "zone": value.get("zone") or item.get("zone", ""),
            "purpose": value.get("purpose") or item.get("purpose", ""),
            "prototype": value.get("prototype") or item.get("prototype", ""),
            "platforms": append_unique_strings(item.get("platforms", []), value.get("platforms", [])),
            "covers": {
                priority: append_unique_strings(
                    item.get("covers", {}).get(priority, []),
                    value.get("covers", {}).get(priority, []),
                )
                for priority in PRIORITIES
            },
            "data": {
                kind: append_unique_strings(
                    item.get("data", {}).get(kind, []),
                    value.get("data", {}).get(kind, []),
                )
                for kind in FLOW_DATA_KINDS
            },
        }
        result.append(merged)
    if not updated:
        result.append(
            {
                "id": screen_id,
                "title": value.get("title", ""),
                "zone": value.get("zone", ""),
                "purpose": value.get("purpose", ""),
                "prototype": value.get("prototype", ""),
                "platforms": value.get("platforms", []),
                "covers": {
                    priority: list(value.get("covers", {}).get(priority, []))
                    for priority in PRIORITIES
                },
                "data": {
                    kind: list(value.get("data", {}).get(kind, []))
                    for kind in FLOW_DATA_KINDS
                },
            }
        )
    return result


def upsert_flow(target: list[dict[str, Any]], value: dict[str, Any]) -> list[dict[str, Any]]:
    flow_id = value.get("id", "")
    if not flow_id:
        return target
    result = []
    updated = False
    for item in target:
        if item.get("id") != flow_id:
            result.append(item)
            continue
        updated = True
        result.append(
            {
                "id": flow_id,
                "title": value.get("title") or item.get("title", ""),
                "goal": value.get("goal") or item.get("goal", ""),
                "steps": normalize_flow_steps((item.get("steps", []) or []) + (value.get("steps", []) or [])),
                "alternatives": append_unique_strings(
                    item.get("alternatives", []),
                    value.get("alternatives", []),
                ),
            }
        )
    if not updated:
        result.append(
            {
                "id": flow_id,
                "title": value.get("title", ""),
                "goal": value.get("goal", ""),
                "steps": normalize_flow_steps(value.get("steps", [])),
                "alternatives": normalize_string_list(value.get("alternatives", [])),
            }
        )
    return result


def append_unique_navigation(
    target: list[dict[str, str]],
    values: list[dict[str, str]],
) -> list[dict[str, str]]:
    result = list(target)
    seen = {(item.get("from", ""), item.get("to", ""), item.get("trigger", "")) for item in result}
    for value in values:
        marker = (value.get("from", ""), value.get("to", ""), value.get("trigger", ""))
        if marker in seen:
            continue
        seen.add(marker)
        result.append(value)
    return result
