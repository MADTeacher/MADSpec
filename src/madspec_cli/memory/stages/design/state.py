from __future__ import annotations

from pathlib import Path
from typing import Any

from ...shared.storage import PRIORITIES, now_iso, read_json, write_json
from .normalizers import (
    normalize_flow_list as _normalize_flow_list,
    normalize_flow_steps as _normalize_flow_steps,
    normalize_navigation_list as _normalize_navigation_list,
    normalize_screen_list as _normalize_screen_list,
    normalize_zone_list as _normalize_zone_list,
)
from .parsers import (
    parse_flow_alternative_value,
    parse_flow_step_value,
    parse_flow_value,
    parse_navigation_value,
    parse_screen_data_value,
    parse_screen_feature_value,
    parse_screen_value,
    parse_zone_value,
)
from .renderers import render_ui_design_markdown
from .shared import (
    FLOW_DATA_KINDS,
    append_unique_strings,
    default_screen_coverage as _default_screen_coverage,
    default_screen_data as _default_screen_data,
    normalize_identifier as _normalize_identifier,
    normalize_path as _normalize_path,
    normalize_string as _normalize_string,
    normalize_string_list as _normalize_string_list,
)
from .updates import (
    append_unique_navigation as _append_unique_navigation,
    upsert_flow as _upsert_flow,
    upsert_screen as _upsert_screen,
    upsert_zone as _upsert_zone,
)
from .validators import (
    design_completeness_errors,
    design_main_prototype_path,
    design_reference_errors,
    design_schema_errors,
    extract_design_feature_coverage,
    missing_prototype_files,
    uncovered_design_features,
)

DESIGN_STAGE = "mvp.design"
DESIGN_SCHEMA_VERSION = 1


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
