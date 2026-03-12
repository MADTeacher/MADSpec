from __future__ import annotations

from typing import Any

from ...shared.storage import PRIORITIES
from .shared import (
    FLOW_DATA_KINDS,
    default_screen_coverage,
    default_screen_data,
    normalize_identifier,
    normalize_path,
    normalize_string,
)


def parse_zone_value(value: str) -> dict[str, str] | None:
    parts = [segment.strip() for segment in value.split("::", 2)]
    if len(parts) != 3:
        return None
    zone_id = normalize_identifier(parts[0])
    title = normalize_string(parts[1])
    description = normalize_string(parts[2])
    if not zone_id or not title or not description:
        return None
    return {"id": zone_id, "title": title, "description": description}


def parse_screen_value(value: str) -> dict[str, Any] | None:
    parts = [segment.strip() for segment in value.split("::", 4)]
    if len(parts) != 5:
        return None
    screen_id = normalize_identifier(parts[0])
    title = normalize_string(parts[1])
    zone = normalize_identifier(parts[2])
    prototype = normalize_path(parts[3])
    purpose = normalize_string(parts[4])
    if not screen_id or not title or not prototype or not purpose:
        return None
    return {
        "id": screen_id,
        "title": title,
        "zone": zone,
        "prototype": prototype,
        "purpose": purpose,
        "platforms": [],
        "covers": default_screen_coverage(),
        "data": default_screen_data(),
    }


def parse_screen_feature_value(value: str) -> dict[str, str] | None:
    parts = [segment.strip() for segment in value.split("::", 2)]
    if len(parts) != 3:
        return None
    screen_id = normalize_identifier(parts[0])
    priority = parts[1].lower()
    feature_name = normalize_string(parts[2])
    if not screen_id or priority not in PRIORITIES or not feature_name:
        return None
    return {"screenId": screen_id, "priority": priority, "featureName": feature_name}


def parse_flow_value(value: str) -> dict[str, Any] | None:
    parts = [segment.strip() for segment in value.split("::", 2)]
    if len(parts) != 3:
        return None
    flow_id = normalize_identifier(parts[0])
    title = normalize_string(parts[1])
    goal = normalize_string(parts[2])
    if not flow_id or not title or not goal:
        return None
    return {"id": flow_id, "title": title, "goal": goal, "steps": [], "alternatives": []}


def parse_flow_step_value(value: str) -> dict[str, str] | None:
    parts = [segment.strip() for segment in value.split("::", 3)]
    if len(parts) != 4:
        return None
    flow_id = normalize_identifier(parts[0])
    screen_id = normalize_identifier(parts[1])
    action = normalize_string(parts[2])
    result_text = normalize_string(parts[3])
    if not flow_id or not screen_id or not action or not result_text:
        return None
    return {"flowId": flow_id, "screenId": screen_id, "action": action, "result": result_text}


def parse_flow_alternative_value(value: str) -> dict[str, str] | None:
    parts = [segment.strip() for segment in value.split("::", 1)]
    if len(parts) != 2:
        return None
    flow_id = normalize_identifier(parts[0])
    description = normalize_string(parts[1])
    if not flow_id or not description:
        return None
    return {"flowId": flow_id, "description": description}


def parse_navigation_value(value: str) -> dict[str, str] | None:
    parts = [segment.strip() for segment in value.split("::", 2)]
    if len(parts) != 3:
        return None
    from_screen = normalize_identifier(parts[0])
    to_screen = normalize_identifier(parts[1])
    trigger = normalize_string(parts[2])
    if not from_screen or not to_screen or not trigger:
        return None
    return {"from": from_screen, "to": to_screen, "trigger": trigger}


def parse_screen_data_value(value: str) -> dict[str, str] | None:
    parts = [segment.strip() for segment in value.split("::")]
    if len(parts) != 3:
        return None
    screen_id = normalize_identifier(parts[0])
    data_kind = parts[1].lower()
    name = normalize_string(parts[2])
    if not screen_id or data_kind not in FLOW_DATA_KINDS or not name:
        return None
    return {"screenId": screen_id, "dataKind": data_kind, "name": name}
