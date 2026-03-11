from __future__ import annotations

from pathlib import Path
from typing import Any

from ...shared.storage import PRIORITIES
from .shared import normalize_identifier, normalize_path, normalize_string, normalize_string_list


def normalize_zone_list(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        zone_id = normalize_identifier(item.get("id", ""))
        title = normalize_string(item.get("title", ""))
        description = normalize_string(item.get("description", ""))
        if not zone_id:
            zone_id = normalize_identifier(title)
        if not zone_id and not title and not description:
            continue
        if zone_id in seen:
            continue
        seen.add(zone_id)
        result.append({"id": zone_id, "title": title, "description": description})
    return result


def normalize_screen_list(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        screen_id = normalize_identifier(item.get("id", ""))
        title = normalize_string(item.get("title", ""))
        zone = normalize_identifier(item.get("zone", ""))
        purpose = normalize_string(item.get("purpose", ""))
        prototype = normalize_path(item.get("prototype", ""))
        platforms = normalize_string_list(item.get("platforms", []))
        covers = item.get("covers", {})
        data = item.get("data", {})
        if not isinstance(covers, dict):
            covers = {}
        if not isinstance(data, dict):
            data = {}
        if not screen_id:
            screen_id = normalize_identifier(title or Path(prototype).stem)
        if not screen_id and not any([title, zone, purpose, prototype, platforms]):
            continue
        if screen_id in seen:
            continue
        seen.add(screen_id)
        result.append(
            {
                "id": screen_id,
                "title": title,
                "zone": zone,
                "purpose": purpose,
                "prototype": prototype,
                "platforms": platforms,
                "covers": {
                    priority: normalize_string_list(covers.get(priority, []))
                    for priority in PRIORITIES
                },
                "data": {
                    "displayed": normalize_string_list(data.get("displayed", [])),
                    "input": normalize_string_list(data.get("input", [])),
                },
            }
        )
    return result


def normalize_flow_steps(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        screen_id = normalize_identifier(item.get("screenId", ""))
        action = normalize_string(item.get("action", ""))
        result_text = normalize_string(item.get("result", ""))
        if not any([screen_id, action, result_text]):
            continue
        marker = (screen_id, action, result_text)
        if marker in seen:
            continue
        seen.add(marker)
        result.append({"screenId": screen_id, "action": action, "result": result_text})
    return result


def normalize_flow_list(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        flow_id = normalize_identifier(item.get("id", ""))
        title = normalize_string(item.get("title", ""))
        goal = normalize_string(item.get("goal", ""))
        steps = normalize_flow_steps(item.get("steps", []))
        alternatives = normalize_string_list(item.get("alternatives", []))
        if not flow_id:
            flow_id = normalize_identifier(title)
        if not flow_id and not any([title, goal, steps, alternatives]):
            continue
        if flow_id in seen:
            continue
        seen.add(flow_id)
        result.append(
            {
                "id": flow_id,
                "title": title,
                "goal": goal,
                "steps": steps,
                "alternatives": alternatives,
            }
        )
    return result


def normalize_navigation_list(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        from_screen = normalize_identifier(item.get("from", ""))
        to_screen = normalize_identifier(item.get("to", ""))
        trigger = normalize_string(item.get("trigger", ""))
        if not any([from_screen, to_screen, trigger]):
            continue
        marker = (from_screen, to_screen, trigger)
        if marker in seen:
            continue
        seen.add(marker)
        result.append({"from": from_screen, "to": to_screen, "trigger": trigger})
    return result
