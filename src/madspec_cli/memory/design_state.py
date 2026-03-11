from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .storage import PRIORITIES, now_iso, read_json, write_json

DESIGN_STAGE = "mvp.design"
DESIGN_SCHEMA_VERSION = 1
FLOW_DATA_KINDS = {"displayed", "input"}


def _normalize_identifier(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    if not text:
        return ""
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _normalize_string(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _normalize_path(value: Any) -> str:
    normalized = _normalize_string(value)
    if not normalized:
        return ""
    return Path(normalized).as_posix()


def _normalize_string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for value in values:
        normalized = _normalize_string(value)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _default_screen_coverage() -> dict[str, list[str]]:
    return {priority: [] for priority in PRIORITIES}


def _default_screen_data() -> dict[str, list[str]]:
    return {"displayed": [], "input": []}


def default_design_state() -> dict[str, Any]:
    ts = now_iso()
    return {
        "schemaVersion": DESIGN_SCHEMA_VERSION,
        "designOverview": "",
        "createdAt": ts,
        "ratifiedAt": None,
        "updatedAt": ts,
        "revision": 0,
        "platforms": [],
        "zones": [],
        "screens": [],
        "flows": [],
        "navigation": [],
        "platformConstraints": [],
        "nextActions": [],
        "checkpointSummary": "",
    }


def _normalize_zone_list(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        zone_id = _normalize_identifier(item.get("id", ""))
        title = _normalize_string(item.get("title", ""))
        description = _normalize_string(item.get("description", ""))
        if not zone_id:
            zone_id = _normalize_identifier(title)
        if not zone_id and not title and not description:
            continue
        if zone_id in seen:
            continue
        seen.add(zone_id)
        result.append({"id": zone_id, "title": title, "description": description})
    return result


def _normalize_screen_list(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        screen_id = _normalize_identifier(item.get("id", ""))
        title = _normalize_string(item.get("title", ""))
        zone = _normalize_identifier(item.get("zone", ""))
        purpose = _normalize_string(item.get("purpose", ""))
        prototype = _normalize_path(item.get("prototype", ""))
        platforms = _normalize_string_list(item.get("platforms", []))
        covers = item.get("covers", {})
        data = item.get("data", {})
        if not isinstance(covers, dict):
            covers = {}
        if not isinstance(data, dict):
            data = {}
        if not screen_id:
            screen_id = _normalize_identifier(title or Path(prototype).stem)
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
                    priority: _normalize_string_list(covers.get(priority, []))
                    for priority in PRIORITIES
                },
                "data": {
                    "displayed": _normalize_string_list(data.get("displayed", [])),
                    "input": _normalize_string_list(data.get("input", [])),
                },
            }
        )
    return result


def _normalize_flow_steps(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        screen_id = _normalize_identifier(item.get("screenId", ""))
        action = _normalize_string(item.get("action", ""))
        result_text = _normalize_string(item.get("result", ""))
        if not any([screen_id, action, result_text]):
            continue
        marker = (screen_id, action, result_text)
        if marker in seen:
            continue
        seen.add(marker)
        result.append({"screenId": screen_id, "action": action, "result": result_text})
    return result


def _normalize_flow_list(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        flow_id = _normalize_identifier(item.get("id", ""))
        title = _normalize_string(item.get("title", ""))
        goal = _normalize_string(item.get("goal", ""))
        steps = _normalize_flow_steps(item.get("steps", []))
        alternatives = _normalize_string_list(item.get("alternatives", []))
        if not flow_id:
            flow_id = _normalize_identifier(title)
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


def _normalize_navigation_list(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        from_screen = _normalize_identifier(item.get("from", ""))
        to_screen = _normalize_identifier(item.get("to", ""))
        trigger = _normalize_string(item.get("trigger", ""))
        if not any([from_screen, to_screen, trigger]):
            continue
        marker = (from_screen, to_screen, trigger)
        if marker in seen:
            continue
        seen.add(marker)
        result.append({"from": from_screen, "to": to_screen, "trigger": trigger})
    return result


def normalize_design_state(state: Any) -> tuple[dict[str, Any], bool]:
    default_state = default_design_state()
    if not isinstance(state, dict):
        return default_state, True

    normalized = dict(default_state)
    changed = False

    normalized["schemaVersion"] = DESIGN_SCHEMA_VERSION
    if state.get("schemaVersion") != DESIGN_SCHEMA_VERSION:
        changed = True

    for key in ("designOverview", "createdAt", "checkpointSummary"):
        value = state.get(key, default_state[key])
        if not isinstance(value, str):
            value = default_state[key]
            changed = True
        normalized[key] = _normalize_string(value)
        if normalized[key] != state.get(key):
            changed = True

    for key in ("ratifiedAt", "updatedAt"):
        value = state.get(key, default_state[key])
        if value is not None and not isinstance(value, str):
            value = default_state[key]
            changed = True
        normalized[key] = _normalize_string(value) if isinstance(value, str) else value
        if normalized[key] != state.get(key):
            changed = True

    revision = state.get("revision", default_state["revision"])
    if not isinstance(revision, int) or revision < 0:
        revision = default_state["revision"]
        changed = True
    normalized["revision"] = revision
    if normalized["revision"] != state.get("revision"):
        changed = True

    normalized["platforms"] = _normalize_string_list(state.get("platforms", []))
    if normalized["platforms"] != state.get("platforms"):
        changed = True

    normalized["zones"] = _normalize_zone_list(state.get("zones", []))
    if normalized["zones"] != state.get("zones"):
        changed = True

    normalized["screens"] = _normalize_screen_list(state.get("screens", []))
    if normalized["screens"] != state.get("screens"):
        changed = True

    normalized["flows"] = _normalize_flow_list(state.get("flows", []))
    if normalized["flows"] != state.get("flows"):
        changed = True

    normalized["navigation"] = _normalize_navigation_list(state.get("navigation", []))
    if normalized["navigation"] != state.get("navigation"):
        changed = True

    for key in ("platformConstraints", "nextActions"):
        normalized[key] = _normalize_string_list(state.get(key, default_state[key]))
        if normalized[key] != state.get(key):
            changed = True

    return normalized, changed


def load_design_state(path: Path) -> dict[str, Any]:
    state = read_json(path, default_design_state())
    normalized, _ = normalize_design_state(state)
    return normalized


def save_design_state(path: Path, state: dict[str, Any]) -> None:
    normalized, _ = normalize_design_state(state)
    write_json(path, normalized)


def append_unique_strings(target: list[str], values: list[str]) -> list[str]:
    result = list(target)
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _upsert_zone(target: list[dict[str, str]], value: dict[str, str]) -> list[dict[str, str]]:
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


def _upsert_screen(target: list[dict[str, Any]], value: dict[str, Any]) -> list[dict[str, Any]]:
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


def _upsert_flow(target: list[dict[str, Any]], value: dict[str, Any]) -> list[dict[str, Any]]:
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
                "steps": _normalize_flow_steps((item.get("steps", []) or []) + (value.get("steps", []) or [])),
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
                "steps": _normalize_flow_steps(value.get("steps", [])),
                "alternatives": _normalize_string_list(value.get("alternatives", [])),
            }
        )
    return result


def _append_unique_navigation(
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


def update_design_state(
    state: dict[str, Any],
    *,
    design_overview: str | None = None,
    platforms: list[str] | None = None,
    zones: list[dict[str, str]] | None = None,
    screens: list[dict[str, Any]] | None = None,
    screen_feature_links: list[dict[str, str]] | None = None,
    flows: list[dict[str, Any]] | None = None,
    flow_steps: list[dict[str, str]] | None = None,
    flow_alternatives: list[dict[str, str]] | None = None,
    navigation: list[dict[str, str]] | None = None,
    platform_constraints: list[str] | None = None,
    screen_data_entries: list[dict[str, str]] | None = None,
    next_actions: list[str] | None = None,
    checkpoint_summary: str | None = None,
    ratify: bool = False,
) -> dict[str, Any]:
    normalized, _ = normalize_design_state(state)
    if design_overview and design_overview.strip():
        normalized["designOverview"] = _normalize_string(design_overview)

    normalized["platforms"] = append_unique_strings(normalized["platforms"], platforms or [])
    normalized["platformConstraints"] = append_unique_strings(
        normalized["platformConstraints"],
        platform_constraints or [],
    )
    normalized["nextActions"] = append_unique_strings(normalized["nextActions"], next_actions or [])

    for zone in zones or []:
        normalized["zones"] = _upsert_zone(normalized["zones"], zone)

    for screen in screens or []:
        normalized["screens"] = _upsert_screen(normalized["screens"], screen)

    for link in screen_feature_links or []:
        screen_id = _normalize_identifier(link.get("screenId", ""))
        priority = str(link.get("priority", "")).strip().lower()
        feature_name = _normalize_string(link.get("featureName", ""))
        if not screen_id or priority not in PRIORITIES or not feature_name:
            continue
        normalized["screens"] = _upsert_screen(
            normalized["screens"],
            {
                "id": screen_id,
                "covers": {priority: [feature_name]},
                "data": _default_screen_data(),
                "platforms": [],
            },
        )

    for entry in screen_data_entries or []:
        screen_id = _normalize_identifier(entry.get("screenId", ""))
        data_kind = _normalize_string(entry.get("dataKind", "")).lower()
        name = _normalize_string(entry.get("name", ""))
        if not screen_id or data_kind not in FLOW_DATA_KINDS or not name:
            continue
        normalized["screens"] = _upsert_screen(
            normalized["screens"],
            {
                "id": screen_id,
                "covers": _default_screen_coverage(),
                "data": {data_kind: [name]},
                "platforms": [],
            },
        )

    for flow in flows or []:
        normalized["flows"] = _upsert_flow(normalized["flows"], flow)

    for step in flow_steps or []:
        flow_id = _normalize_identifier(step.get("flowId", ""))
        if not flow_id:
            continue
        normalized["flows"] = _upsert_flow(
            normalized["flows"],
            {
                "id": flow_id,
                "steps": [
                    {
                        "screenId": step.get("screenId", ""),
                        "action": step.get("action", ""),
                        "result": step.get("result", ""),
                    }
                ],
            },
        )

    for item in flow_alternatives or []:
        flow_id = _normalize_identifier(item.get("flowId", ""))
        description = _normalize_string(item.get("description", ""))
        if not flow_id or not description:
            continue
        normalized["flows"] = _upsert_flow(
            normalized["flows"],
            {"id": flow_id, "alternatives": [description]},
        )

    normalized["navigation"] = _append_unique_navigation(
        normalized["navigation"],
        _normalize_navigation_list(navigation or []),
    )

    ts = now_iso()
    normalized["updatedAt"] = ts
    if checkpoint_summary is not None:
        normalized["checkpointSummary"] = _normalize_string(checkpoint_summary)
    if ratify:
        normalized["ratifiedAt"] = ts
        normalized["revision"] = int(normalized.get("revision", 0)) + 1
    return normalized


def is_empty_design_state(state: dict[str, Any]) -> bool:
    normalized, _ = normalize_design_state(state)
    return not any(
        [
            normalized["designOverview"],
            normalized["platforms"],
            normalized["zones"],
            normalized["screens"],
            normalized["flows"],
            normalized["navigation"],
            normalized["platformConstraints"],
            normalized["nextActions"],
            normalized["checkpointSummary"],
            normalized["revision"],
            normalized["ratifiedAt"],
        ]
    )


def parse_zone_value(value: str) -> dict[str, str] | None:
    parts = [segment.strip() for segment in value.split("::", 2)]
    if len(parts) != 3:
        return None
    zone_id = _normalize_identifier(parts[0])
    title = _normalize_string(parts[1])
    description = _normalize_string(parts[2])
    if not zone_id or not title or not description:
        return None
    return {"id": zone_id, "title": title, "description": description}


def parse_screen_value(value: str) -> dict[str, Any] | None:
    parts = [segment.strip() for segment in value.split("::", 4)]
    if len(parts) != 5:
        return None
    screen_id = _normalize_identifier(parts[0])
    title = _normalize_string(parts[1])
    zone = _normalize_identifier(parts[2])
    prototype = _normalize_path(parts[3])
    purpose = _normalize_string(parts[4])
    if not screen_id or not title or not prototype or not purpose:
        return None
    return {
        "id": screen_id,
        "title": title,
        "zone": zone,
        "prototype": prototype,
        "purpose": purpose,
        "platforms": [],
        "covers": _default_screen_coverage(),
        "data": _default_screen_data(),
    }


def parse_screen_feature_value(value: str) -> dict[str, str] | None:
    parts = [segment.strip() for segment in value.split("::", 2)]
    if len(parts) != 3:
        return None
    screen_id = _normalize_identifier(parts[0])
    priority = parts[1].lower()
    feature_name = _normalize_string(parts[2])
    if not screen_id or priority not in PRIORITIES or not feature_name:
        return None
    return {"screenId": screen_id, "priority": priority, "featureName": feature_name}


def parse_flow_value(value: str) -> dict[str, Any] | None:
    parts = [segment.strip() for segment in value.split("::", 2)]
    if len(parts) != 3:
        return None
    flow_id = _normalize_identifier(parts[0])
    title = _normalize_string(parts[1])
    goal = _normalize_string(parts[2])
    if not flow_id or not title or not goal:
        return None
    return {"id": flow_id, "title": title, "goal": goal, "steps": [], "alternatives": []}


def parse_flow_step_value(value: str) -> dict[str, str] | None:
    parts = [segment.strip() for segment in value.split("::", 3)]
    if len(parts) != 4:
        return None
    flow_id = _normalize_identifier(parts[0])
    screen_id = _normalize_identifier(parts[1])
    action = _normalize_string(parts[2])
    result_text = _normalize_string(parts[3])
    if not flow_id or not screen_id or not action or not result_text:
        return None
    return {"flowId": flow_id, "screenId": screen_id, "action": action, "result": result_text}


def parse_flow_alternative_value(value: str) -> dict[str, str] | None:
    parts = [segment.strip() for segment in value.split("::", 1)]
    if len(parts) != 2:
        return None
    flow_id = _normalize_identifier(parts[0])
    description = _normalize_string(parts[1])
    if not flow_id or not description:
        return None
    return {"flowId": flow_id, "description": description}


def parse_navigation_value(value: str) -> dict[str, str] | None:
    parts = [segment.strip() for segment in value.split("::", 2)]
    if len(parts) != 3:
        return None
    from_screen = _normalize_identifier(parts[0])
    to_screen = _normalize_identifier(parts[1])
    trigger = _normalize_string(parts[2])
    if not from_screen or not to_screen or not trigger:
        return None
    return {"from": from_screen, "to": to_screen, "trigger": trigger}


def parse_screen_data_value(value: str) -> dict[str, str] | None:
    parts = [segment.strip() for segment in value.split("::", 2)]
    if len(parts) != 3:
        return None
    screen_id = _normalize_identifier(parts[0])
    data_kind = parts[1].lower()
    name = _normalize_string(parts[2])
    if not screen_id or data_kind not in FLOW_DATA_KINDS or not name:
        return None
    return {"screenId": screen_id, "dataKind": data_kind, "name": name}


def design_main_prototype_path(branch_name: str) -> str:
    return Path(".madspec") / branch_name / "ui-prototype" / "index.html"


def extract_design_feature_coverage(state: dict[str, Any]) -> dict[str, list[str]]:
    normalized, _ = normalize_design_state(state)
    coverage = {priority: [] for priority in PRIORITIES}
    for screen in normalized["screens"]:
        for priority in PRIORITIES:
            coverage[priority] = append_unique_strings(
                coverage[priority],
                screen.get("covers", {}).get(priority, []),
            )
    return coverage


def uncovered_design_features(
    state: dict[str, Any],
    concept_state: dict[str, Any],
) -> dict[str, list[str]]:
    design_coverage = extract_design_feature_coverage(state)
    uncovered: dict[str, list[str]] = {}
    for priority in PRIORITIES:
        concept_features = [
            item.get("name", "").strip()
            for item in concept_state.get("features", {}).get(priority, [])
            if item.get("name", "").strip()
        ]
        uncovered[priority] = [
            feature_name for feature_name in concept_features if feature_name not in design_coverage[priority]
        ]
    return uncovered


def missing_prototype_files(
    state: dict[str, Any],
    project_path: Path,
    branch_name: str,
) -> list[str]:
    normalized, _ = normalize_design_state(state)
    missing: list[str] = []
    index_path = project_path / design_main_prototype_path(branch_name)
    if not index_path.exists():
        missing.append(design_main_prototype_path(branch_name).as_posix())
    for screen in normalized["screens"]:
        prototype = screen.get("prototype", "")
        if not prototype:
            continue
        if not (project_path / prototype).exists() and prototype not in missing:
            missing.append(prototype)
    return missing


def design_reference_errors(
    state: dict[str, Any],
    *,
    project_path: Path | None = None,
    branch_name: str | None = None,
) -> list[str]:
    normalized, _ = normalize_design_state(state)
    errors: list[str] = []
    zone_ids = {zone.get("id", "") for zone in normalized["zones"] if zone.get("id", "")}
    screen_ids = {screen.get("id", "") for screen in normalized["screens"] if screen.get("id", "")}

    for screen in normalized["screens"]:
        screen_id = screen.get("id", "")
        if screen.get("zone") and screen["zone"] not in zone_ids:
            errors.append(f"design screen '{screen_id}' references unknown zone '{screen['zone']}'")
        if not screen.get("prototype"):
            errors.append(f"design screen '{screen_id}' must include a prototype path")

    for flow in normalized["flows"]:
        flow_id = flow.get("id", "")
        steps = flow.get("steps", [])
        if not steps:
            errors.append(f"design flow '{flow_id}' must include at least one step")
        for step in steps:
            screen_id = step.get("screenId", "")
            if not screen_id:
                errors.append(f"design flow '{flow_id}' contains a step without screenId")
            elif screen_id not in screen_ids:
                errors.append(f"design flow '{flow_id}' references unknown screen '{screen_id}'")

    for item in normalized["navigation"]:
        if item.get("from") not in screen_ids:
            errors.append(f"design navigation references unknown screen '{item.get('from', '')}'")
        if item.get("to") not in screen_ids:
            errors.append(f"design navigation references unknown screen '{item.get('to', '')}'")

    if project_path is not None and branch_name is not None:
        for missing in missing_prototype_files(normalized, project_path, branch_name):
            errors.append(f"design references missing prototype file '{missing}'")

    return errors


def design_completeness_errors(
    state: dict[str, Any],
    *,
    concept_state: dict[str, Any],
    project_path: Path,
    branch_name: str,
) -> list[str]:
    normalized, _ = normalize_design_state(state)
    errors: list[str] = []
    if not normalized["designOverview"]:
        errors.append("design state must include a design overview before checkpoint")
    if not normalized["platforms"]:
        errors.append("design state must include at least one platform before checkpoint")
    if not normalized["screens"]:
        errors.append("design state must include at least one screen before checkpoint")
    if not normalized["flows"]:
        errors.append("design state must include at least one user flow before checkpoint")
    if not normalized["navigation"]:
        errors.append("design state must include navigation links before checkpoint")
    uncovered = uncovered_design_features(normalized, concept_state)
    for priority in PRIORITIES:
        if uncovered[priority]:
            errors.append(
                f"design state must cover all {priority.upper()} concept features before checkpoint: "
                + ", ".join(uncovered[priority])
            )
    errors.extend(
        design_reference_errors(
            normalized,
            project_path=project_path,
            branch_name=branch_name,
        )
    )
    return errors


def design_schema_errors(state: Any) -> list[str]:
    if not isinstance(state, dict):
        return ["design state must be a JSON object"]
    normalized, _ = normalize_design_state(state)
    errors: list[str] = []
    if normalized["schemaVersion"] != DESIGN_SCHEMA_VERSION:
        errors.append(f"design state schemaVersion must equal {DESIGN_SCHEMA_VERSION}")
    for key in ("designOverview", "createdAt", "checkpointSummary"):
        if not isinstance(normalized[key], str):
            errors.append(f"design state field '{key}' must be a string")
    for key in ("ratifiedAt", "updatedAt"):
        value = normalized[key]
        if value is not None and not isinstance(value, str):
            errors.append(f"design state field '{key}' must be a string or null")
    if not isinstance(normalized["revision"], int) or normalized["revision"] < 0:
        errors.append("design state field 'revision' must be a non-negative integer")
    for key in ("platforms", "zones", "screens", "flows", "navigation", "platformConstraints", "nextActions"):
        if not isinstance(normalized[key], list):
            errors.append(f"design state field '{key}' must be a list")
    return errors


def render_ui_design_markdown(
    state: dict[str, Any],
    *,
    branch_name: str,
    project_name: str = "",
) -> str:
    normalized, _ = normalize_design_state(state)
    main_prototype = design_main_prototype_path(branch_name).as_posix()
    project_label = project_name or "Без названия"
    zone_titles = {
        zone.get("id", ""): zone.get("title", "") or zone.get("id", "")
        for zone in normalized["zones"]
    }

    def render_list(values: list[str]) -> list[str]:
        if not values:
            return ["- Пока не зафиксировано."]
        return [f"- {value}" for value in values]

    def render_date(value: str | None) -> str:
        return value or "Не указано"

    lines = [
        f"# Дизайн пользовательского интерфейса: {project_label}",
        "",
        f"**Основано на**: `.madspec/{branch_name}/concept.md`",
        "",
        "## Обзор",
        "",
        normalized["designOverview"] or "Пока не зафиксировано.",
        "",
        "## Прототип интерфейса",
        "",
        f"**Главный файл прототипа**: `{main_prototype}`",
        "",
        "## Платформы",
        "",
        *render_list(normalized["platforms"]),
        "",
        "## Основные экраны",
        "",
    ]

    if not normalized["screens"]:
        lines.append("Пока не зафиксировано.")
        lines.append("")
    else:
        for screen in normalized["screens"]:
            lines.extend(
                [
                    f"### {screen.get('id', 'screen')}: {screen.get('title', 'Без названия')}",
                    "",
                    f"**Файл прототипа**: `{screen.get('prototype', 'Не указан')}`",
                    f"**Функциональная зона**: {zone_titles.get(screen.get('zone', ''), screen.get('zone', '') or 'Не указана')}",
                    f"**Назначение**: {screen.get('purpose', '') or 'Пока не зафиксировано.'}",
                    "",
                    "**Покрытие функций**:",
                    *(
                        [
                            f"- {priority.upper()}: "
                            + (", ".join(screen.get("covers", {}).get(priority, [])) or "Пока не зафиксировано.")
                            for priority in PRIORITIES
                        ]
                    ),
                    "",
                    "**Платформы**:",
                    *render_list(screen.get("platforms", [])),
                    "",
                    "**Данные на экране**:",
                    "- Отображаемые данные: "
                    + (", ".join(screen.get("data", {}).get("displayed", [])) or "Пока не зафиксировано."),
                    "- Вводимые данные: "
                    + (", ".join(screen.get("data", {}).get("input", [])) or "Пока не зафиксировано."),
                    "",
                ]
            )

    lines.extend(["## Пользовательские потоки", ""])
    if not normalized["flows"]:
        lines.append("Пока не зафиксировано.")
        lines.append("")
    else:
        for flow in normalized["flows"]:
            lines.extend(
                [
                    f"### {flow.get('id', 'flow')}: {flow.get('title', 'Без названия')}",
                    "",
                    f"**Цель пользователя**: {flow.get('goal', '') or 'Пока не зафиксировано.'}",
                    "",
                    "**Шаги**:",
                ]
            )
            if flow.get("steps"):
                lines.extend(
                    [
                        f"{index}. `{step.get('screenId', '')}` -> {step.get('action', '')} -> {step.get('result', '')}"
                        for index, step in enumerate(flow["steps"], start=1)
                    ]
                )
            else:
                lines.append("1. Пока не зафиксировано.")
            lines.extend(
                [
                    "",
                    "**Альтернативные пути**:",
                    *render_list(flow.get("alternatives", [])),
                    "",
                ]
            )

    lines.extend(["## Навигация", ""])
    if not normalized["navigation"]:
        lines.append("Пока не зафиксировано.")
    else:
        for item in normalized["navigation"]:
            lines.append(
                f"- `{item.get('from', '')}` -> `{item.get('to', '')}` через {item.get('trigger', '')}"
            )

    lines.extend(
        [
            "",
            "## Ограничения платформ",
            "",
            *render_list(normalized["platformConstraints"]),
            "",
            "## Следующие шаги",
            "",
            *render_list(normalized["nextActions"]),
            "",
            "---",
            (
                f"Версия: {normalized.get('revision', 0)} | "
                f"Ратифицирована: {render_date(normalized.get('ratifiedAt'))} | "
                f"Последнее изменение: {render_date(normalized.get('updatedAt'))}"
            ),
            "",
        ]
    )
    return "\n".join(lines)
