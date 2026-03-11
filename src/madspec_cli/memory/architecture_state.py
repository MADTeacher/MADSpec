from __future__ import annotations

import re
from typing import Any

from .design_state import FLOW_DATA_KINDS, normalize_design_state
from .storage import now_iso, read_json, write_json

ARCHITECTURE_STAGE = "mvp.architecture"
ARCHITECTURE_SCHEMA_VERSION = 1
SUPPORTED_API_STYLE = "rest-openapi"
ENDPOINT_FIELD_SECTIONS = {"path", "query", "request"}


def _normalize_string(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _normalize_identifier(value: Any) -> str:
    normalized = _normalize_string(value).lower()
    if not normalized:
        return ""
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    return normalized.strip("-")


def _normalize_name_key(value: Any) -> str:
    normalized = _normalize_string(value).lower()
    if not normalized:
        return ""
    return re.sub(r"[^a-z0-9]+", "", normalized)


def _normalize_required_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = _normalize_string(value).lower()
    return normalized in {"required", "true", "yes", "1"}


def _normalize_string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for value in values:
        normalized = _normalize_string(value)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _normalize_path(value: Any) -> str:
    normalized = _normalize_string(value)
    return normalized.replace("\\", "/")


def _normalize_directory_list(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        normalized = {
            "path": _normalize_path(item.get("path", "")),
            "purpose": _normalize_string(item.get("purpose", "")),
        }
        if not all(normalized.values()):
            continue
        marker = tuple(normalized.values())
        if marker in seen:
            continue
        seen.add(marker)
        result.append(normalized)
    return result


def _normalize_entity_fields(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str, bool, str]] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        normalized = {
            "name": _normalize_string(item.get("name", "")),
            "type": _normalize_string(item.get("type", "")),
            "required": _normalize_required_flag(item.get("required", False)),
            "description": _normalize_string(item.get("description", "")),
        }
        if not normalized["name"] or not normalized["type"]:
            continue
        marker = (
            normalized["name"],
            normalized["type"],
            normalized["required"],
            normalized["description"],
        )
        if marker in seen:
            continue
        seen.add(marker)
        result.append(normalized)
    return result


def _normalize_entity_relationships(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        normalized = {
            "target": _normalize_string(item.get("target", "")),
            "kind": _normalize_string(item.get("kind", "")),
            "description": _normalize_string(item.get("description", "")),
        }
        if not all(normalized.values()):
            continue
        marker = tuple(normalized.values())
        if marker in seen:
            continue
        seen.add(marker)
        result.append(normalized)
    return result


def _normalize_entity_states(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        normalized = {
            "name": _normalize_string(item.get("name", "")),
            "description": _normalize_string(item.get("description", "")),
        }
        if not all(normalized.values()):
            continue
        marker = tuple(normalized.values())
        if marker in seen:
            continue
        seen.add(marker)
        result.append(normalized)
    return result


def _normalize_entities(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        normalized = {
            "name": _normalize_string(item.get("name", "")),
            "description": _normalize_string(item.get("description", "")),
            "fields": _normalize_entity_fields(item.get("fields", [])),
            "relationships": _normalize_entity_relationships(item.get("relationships", [])),
            "states": _normalize_entity_states(item.get("states", [])),
        }
        if not normalized["name"]:
            continue
        marker = _normalize_name_key(normalized["name"])
        if marker in seen:
            continue
        seen.add(marker)
        result.append(normalized)
    return result


def _normalize_endpoint_sections(value: Any) -> str:
    normalized = _normalize_string(value).lower()
    if normalized in ENDPOINT_FIELD_SECTIONS:
        return normalized
    if normalized.startswith("response:") and len(normalized) > len("response:"):
        return normalized
    return ""


def _normalize_endpoint_fields(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, bool, str]] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        normalized = {
            "section": _normalize_endpoint_sections(item.get("section", "")),
            "name": _normalize_string(item.get("name", "")),
            "type": _normalize_string(item.get("type", "")),
            "required": _normalize_required_flag(item.get("required", False)),
            "description": _normalize_string(item.get("description", "")),
        }
        if not normalized["section"] or not normalized["name"] or not normalized["type"]:
            continue
        marker = (
            normalized["section"],
            normalized["name"],
            normalized["type"],
            normalized["required"],
            normalized["description"],
        )
        if marker in seen:
            continue
        seen.add(marker)
        result.append(normalized)
    return result


def _normalize_endpoint_errors(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        normalized = {
            "status": _normalize_string(item.get("status", "")),
            "code": _normalize_string(item.get("code", "")),
            "description": _normalize_string(item.get("description", "")),
        }
        if not all(normalized.values()):
            continue
        marker = tuple(normalized.values())
        if marker in seen:
            continue
        seen.add(marker)
        result.append(normalized)
    return result


def _normalize_endpoints(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        normalized = {
            "operationId": _normalize_identifier(item.get("operationId", "")),
            "method": _normalize_string(item.get("method", "")).upper(),
            "path": _normalize_string(item.get("path", "")),
            "summary": _normalize_string(item.get("summary", "")),
            "screenIds": [_normalize_identifier(value) for value in item.get("screenIds", []) if _normalize_identifier(value)],
            "fields": _normalize_endpoint_fields(item.get("fields", [])),
            "errors": _normalize_endpoint_errors(item.get("errors", [])),
        }
        if not normalized["operationId"] or not normalized["method"] or not normalized["path"]:
            continue
        if normalized["operationId"] in seen:
            continue
        seen.add(normalized["operationId"])
        normalized["screenIds"] = list(dict.fromkeys(normalized["screenIds"]))
        result.append(normalized)
    return result


def _normalize_integrations(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        normalized = {
            "name": _normalize_string(item.get("name", "")),
            "kind": _normalize_string(item.get("kind", "")),
            "purpose": _normalize_string(item.get("purpose", "")),
            "touchpoints": _normalize_string_list(item.get("touchpoints", [])),
        }
        if not all([normalized["name"], normalized["kind"], normalized["purpose"]]):
            continue
        marker = (normalized["name"], normalized["kind"], normalized["purpose"])
        if marker in seen:
            continue
        seen.add(marker)
        result.append(normalized)
    return result


def _normalize_patterns(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        normalized = {
            "name": _normalize_string(item.get("name", "")),
            "rationale": _normalize_string(item.get("rationale", "")),
        }
        if not all(normalized.values()):
            continue
        marker = tuple(normalized.values())
        if marker in seen:
            continue
        seen.add(marker)
        result.append(normalized)
    return result


def default_architecture_state() -> dict[str, Any]:
    ts = now_iso()
    return {
        "schemaVersion": ARCHITECTURE_SCHEMA_VERSION,
        "revision": 0,
        "createdAt": ts,
        "updatedAt": ts,
        "ratifiedAt": None,
        "checkpointSummary": "",
        "architectureOverview": "",
        "projectStructure": {"strategy": "", "rationale": "", "directories": []},
        "dataModel": {"entities": []},
        "contracts": {"apiStyle": SUPPORTED_API_STYLE, "endpoints": []},
        "integrations": [],
        "codePrinciples": [],
        "patterns": [],
        "securityNotes": [],
        "performanceNotes": [],
        "nextActions": [],
    }


def normalize_architecture_state(state: Any) -> tuple[dict[str, Any], bool]:
    default_state = default_architecture_state()
    if not isinstance(state, dict):
        return default_state, True

    normalized = dict(default_state)
    changed = False

    normalized["schemaVersion"] = ARCHITECTURE_SCHEMA_VERSION
    if state.get("schemaVersion") != ARCHITECTURE_SCHEMA_VERSION:
        changed = True

    revision = state.get("revision", default_state["revision"])
    if not isinstance(revision, int) or revision < 0:
        revision = default_state["revision"]
        changed = True
    normalized["revision"] = revision
    if normalized["revision"] != state.get("revision"):
        changed = True

    for key in ("createdAt", "updatedAt", "checkpointSummary", "architectureOverview"):
        normalized[key] = _normalize_string(state.get(key, default_state[key]))
        if normalized[key] != state.get(key):
            changed = True

    ratified_at = state.get("ratifiedAt", default_state["ratifiedAt"])
    if ratified_at is not None and not isinstance(ratified_at, str):
        ratified_at = default_state["ratifiedAt"]
        changed = True
    normalized["ratifiedAt"] = _normalize_string(ratified_at) if isinstance(ratified_at, str) else None
    if normalized["ratifiedAt"] != state.get("ratifiedAt"):
        changed = True

    project_structure = state.get("projectStructure", {})
    if not isinstance(project_structure, dict):
        project_structure = {}
        changed = True
    normalized["projectStructure"] = {
        "strategy": _normalize_string(project_structure.get("strategy", "")),
        "rationale": _normalize_string(project_structure.get("rationale", "")),
        "directories": _normalize_directory_list(project_structure.get("directories", [])),
    }
    if normalized["projectStructure"] != state.get("projectStructure"):
        changed = True

    data_model = state.get("dataModel", {})
    if not isinstance(data_model, dict):
        data_model = {}
        changed = True
    normalized["dataModel"] = {"entities": _normalize_entities(data_model.get("entities", []))}
    if normalized["dataModel"] != state.get("dataModel"):
        changed = True

    contracts = state.get("contracts", {})
    if not isinstance(contracts, dict):
        contracts = {}
        changed = True
    normalized["contracts"] = {
        "apiStyle": SUPPORTED_API_STYLE,
        "endpoints": _normalize_endpoints(contracts.get("endpoints", [])),
    }
    if normalized["contracts"] != state.get("contracts"):
        changed = True

    normalized["integrations"] = _normalize_integrations(state.get("integrations", []))
    if normalized["integrations"] != state.get("integrations"):
        changed = True

    for key in ("codePrinciples", "securityNotes", "performanceNotes", "nextActions"):
        normalized[key] = _normalize_string_list(state.get(key, default_state[key]))
        if normalized[key] != state.get(key):
            changed = True

    normalized["patterns"] = _normalize_patterns(state.get("patterns", []))
    if normalized["patterns"] != state.get("patterns"):
        changed = True

    return normalized, changed


def load_architecture_state(path) -> dict[str, Any]:
    state = read_json(path, default_architecture_state())
    normalized, _ = normalize_architecture_state(state)
    return normalized


def save_architecture_state(path, state: dict[str, Any]) -> None:
    normalized, _ = normalize_architecture_state(state)
    write_json(path, normalized)


def append_unique_strings(target: list[str], values: list[str]) -> list[str]:
    result = list(target)
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _append_unique_dicts(
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


def is_empty_architecture_state(state: dict[str, Any]) -> bool:
    normalized, _ = normalize_architecture_state(state)
    return not any(
        [
            normalized["architectureOverview"],
            normalized["projectStructure"]["strategy"],
            normalized["projectStructure"]["rationale"],
            normalized["projectStructure"]["directories"],
            normalized["dataModel"]["entities"],
            normalized["contracts"]["endpoints"],
            normalized["integrations"],
            normalized["codePrinciples"],
            normalized["patterns"],
            normalized["securityNotes"],
            normalized["performanceNotes"],
            normalized["nextActions"],
            normalized["checkpointSummary"],
            normalized["revision"],
            normalized["ratifiedAt"],
        ]
    )


def parse_project_structure_value(value: str) -> dict[str, str] | None:
    parts = [segment.strip() for segment in value.split("::", 1)]
    if len(parts) != 2:
        return None
    normalized = {
        "strategy": _normalize_string(parts[0]),
        "rationale": _normalize_string(parts[1]),
    }
    if not all(normalized.values()):
        return None
    return normalized


def parse_directory_value(value: str) -> dict[str, str] | None:
    parts = [segment.strip() for segment in value.split("::", 1)]
    if len(parts) != 2:
        return None
    normalized = {"path": _normalize_path(parts[0]), "purpose": _normalize_string(parts[1])}
    if not all(normalized.values()):
        return None
    return normalized


def parse_entity_value(value: str) -> dict[str, str] | None:
    parts = [segment.strip() for segment in value.split("::", 1)]
    if len(parts) != 2:
        return None
    normalized = {"name": _normalize_string(parts[0]), "description": _normalize_string(parts[1])}
    if not all(normalized.values()):
        return None
    return normalized


def parse_entity_field_value(value: str) -> dict[str, Any] | None:
    parts = [segment.strip() for segment in value.split("::", 4)]
    if len(parts) != 5:
        return None
    entity_name = _normalize_string(parts[0])
    field_name = _normalize_string(parts[1])
    field_type = _normalize_string(parts[2])
    required_text = _normalize_string(parts[3]).lower()
    description = _normalize_string(parts[4])
    if required_text not in {"required", "optional"}:
        return None
    if not all([entity_name, field_name, field_type, description]):
        return None
    return {
        "entity": entity_name,
        "field": {
            "name": field_name,
            "type": field_type,
            "required": required_text == "required",
            "description": description,
        },
    }


def parse_entity_relationship_value(value: str) -> dict[str, Any] | None:
    parts = [segment.strip() for segment in value.split("::", 3)]
    if len(parts) != 4:
        return None
    entity_name = _normalize_string(parts[0])
    target = _normalize_string(parts[1])
    kind = _normalize_string(parts[2])
    description = _normalize_string(parts[3])
    if not all([entity_name, target, kind, description]):
        return None
    return {
        "entity": entity_name,
        "relationship": {"target": target, "kind": kind, "description": description},
    }


def parse_entity_state_value(value: str) -> dict[str, Any] | None:
    parts = [segment.strip() for segment in value.split("::", 2)]
    if len(parts) != 3:
        return None
    entity_name = _normalize_string(parts[0])
    state_name = _normalize_string(parts[1])
    description = _normalize_string(parts[2])
    if not all([entity_name, state_name, description]):
        return None
    return {
        "entity": entity_name,
        "state": {"name": state_name, "description": description},
    }


def parse_endpoint_value(value: str) -> dict[str, Any] | None:
    parts = [segment.strip() for segment in value.split("::", 3)]
    if len(parts) != 4:
        return None
    operation_id = _normalize_identifier(parts[0])
    method = _normalize_string(parts[1]).upper()
    path = _normalize_string(parts[2])
    summary = _normalize_string(parts[3])
    if not all([operation_id, method, path, summary]):
        return None
    return {
        "operationId": operation_id,
        "method": method,
        "path": path,
        "summary": summary,
        "screenIds": [],
        "fields": [],
        "errors": [],
    }


def parse_endpoint_screen_value(value: str) -> dict[str, str] | None:
    parts = [segment.strip() for segment in value.split("::", 1)]
    if len(parts) != 2:
        return None
    operation_id = _normalize_identifier(parts[0])
    screen_id = _normalize_identifier(parts[1])
    if not operation_id or not screen_id:
        return None
    return {"operationId": operation_id, "screenId": screen_id}


def parse_endpoint_field_value(value: str) -> dict[str, Any] | None:
    parts = [segment.strip() for segment in value.split("::", 5)]
    if len(parts) != 6:
        return None
    operation_id = _normalize_identifier(parts[0])
    section = _normalize_endpoint_sections(parts[1])
    name = _normalize_string(parts[2])
    field_type = _normalize_string(parts[3])
    required_text = _normalize_string(parts[4]).lower()
    description = _normalize_string(parts[5])
    if required_text not in {"required", "optional"}:
        return None
    if not all([operation_id, section, name, field_type, description]):
        return None
    return {
        "operationId": operation_id,
        "field": {
            "section": section,
            "name": name,
            "type": field_type,
            "required": required_text == "required",
            "description": description,
        },
    }


def parse_endpoint_error_value(value: str) -> dict[str, Any] | None:
    parts = [segment.strip() for segment in value.split("::", 3)]
    if len(parts) != 4:
        return None
    operation_id = _normalize_identifier(parts[0])
    status = _normalize_string(parts[1])
    code = _normalize_string(parts[2])
    description = _normalize_string(parts[3])
    if not all([operation_id, status, code, description]):
        return None
    return {
        "operationId": operation_id,
        "error": {"status": status, "code": code, "description": description},
    }


def parse_integration_value(value: str) -> dict[str, Any] | None:
    parts = [segment.strip() for segment in value.split("::", 3)]
    if len(parts) != 4:
        return None
    normalized = {
        "name": _normalize_string(parts[0]),
        "kind": _normalize_string(parts[1]),
        "purpose": _normalize_string(parts[2]),
        "touchpoints": [segment.strip() for segment in parts[3].split("|") if segment.strip()],
    }
    if not all([normalized["name"], normalized["kind"], normalized["purpose"]]):
        return None
    return normalized


def parse_pattern_value(value: str) -> dict[str, str] | None:
    parts = [segment.strip() for segment in value.split("::", 1)]
    if len(parts) != 2:
        return None
    normalized = {"name": _normalize_string(parts[0]), "rationale": _normalize_string(parts[1])}
    if not all(normalized.values()):
        return None
    return normalized


def _upsert_entity(
    target: list[dict[str, Any]],
    value: dict[str, Any],
) -> list[dict[str, Any]]:
    entity_name = _normalize_string(value.get("name", ""))
    if not entity_name:
        return target
    marker = _normalize_name_key(entity_name)
    result: list[dict[str, Any]] = []
    updated = False
    for item in target:
        if _normalize_name_key(item.get("name", "")) != marker:
            result.append(item)
            continue
        updated = True
        merged = {
            "name": entity_name,
            "description": value.get("description") or item.get("description", ""),
            "fields": _append_unique_dicts(
                item.get("fields", []),
                value.get("fields", []),
                marker_fields=("name", "type", "required", "description"),
            ),
            "relationships": _append_unique_dicts(
                item.get("relationships", []),
                value.get("relationships", []),
                marker_fields=("target", "kind", "description"),
            ),
            "states": _append_unique_dicts(
                item.get("states", []),
                value.get("states", []),
                marker_fields=("name", "description"),
            ),
        }
        result.append(merged)
    if not updated:
        result.append(
            {
                "name": entity_name,
                "description": value.get("description", ""),
                "fields": value.get("fields", []),
                "relationships": value.get("relationships", []),
                "states": value.get("states", []),
            }
        )
    return result


def _upsert_endpoint(target: list[dict[str, Any]], value: dict[str, Any]) -> list[dict[str, Any]]:
    operation_id = _normalize_identifier(value.get("operationId", ""))
    if not operation_id:
        return target
    result: list[dict[str, Any]] = []
    updated = False
    for item in target:
        if item.get("operationId") != operation_id:
            result.append(item)
            continue
        updated = True
        result.append(
            {
                "operationId": operation_id,
                "method": value.get("method") or item.get("method", ""),
                "path": value.get("path") or item.get("path", ""),
                "summary": value.get("summary") or item.get("summary", ""),
                "screenIds": append_unique_strings(item.get("screenIds", []), value.get("screenIds", [])),
                "fields": _append_unique_dicts(
                    item.get("fields", []),
                    value.get("fields", []),
                    marker_fields=("section", "name", "type", "required", "description"),
                ),
                "errors": _append_unique_dicts(
                    item.get("errors", []),
                    value.get("errors", []),
                    marker_fields=("status", "code", "description"),
                ),
            }
        )
    if not updated:
        result.append(
            {
                "operationId": operation_id,
                "method": value.get("method", ""),
                "path": value.get("path", ""),
                "summary": value.get("summary", ""),
                "screenIds": value.get("screenIds", []),
                "fields": value.get("fields", []),
                "errors": value.get("errors", []),
            }
        )
    return result


def update_architecture_state(
    state: dict[str, Any],
    *,
    architecture_overview: str | None = None,
    project_structure: dict[str, str] | None = None,
    directories: list[dict[str, str]] | None = None,
    entities: list[dict[str, str]] | None = None,
    entity_fields: list[dict[str, Any]] | None = None,
    entity_relationships: list[dict[str, Any]] | None = None,
    entity_states: list[dict[str, Any]] | None = None,
    endpoints: list[dict[str, Any]] | None = None,
    endpoint_screens: list[dict[str, str]] | None = None,
    endpoint_fields: list[dict[str, Any]] | None = None,
    endpoint_errors: list[dict[str, Any]] | None = None,
    integrations: list[dict[str, Any]] | None = None,
    code_principles: list[str] | None = None,
    patterns: list[dict[str, str]] | None = None,
    security_notes: list[str] | None = None,
    performance_notes: list[str] | None = None,
    next_actions: list[str] | None = None,
    checkpoint_summary: str | None = None,
    ratify: bool = False,
) -> dict[str, Any]:
    normalized, _ = normalize_architecture_state(state)

    if architecture_overview and architecture_overview.strip():
        normalized["architectureOverview"] = _normalize_string(architecture_overview)
    if project_structure is not None:
        if project_structure.get("strategy"):
            normalized["projectStructure"]["strategy"] = _normalize_string(project_structure.get("strategy"))
        if project_structure.get("rationale"):
            normalized["projectStructure"]["rationale"] = _normalize_string(project_structure.get("rationale"))
    normalized["projectStructure"]["directories"] = _append_unique_dicts(
        normalized["projectStructure"]["directories"],
        directories or [],
        marker_fields=("path", "purpose"),
    )

    for entity in entities or []:
        normalized["dataModel"]["entities"] = _upsert_entity(
            normalized["dataModel"]["entities"],
            {"name": entity.get("name", ""), "description": entity.get("description", ""), "fields": [], "relationships": [], "states": []},
        )
    for item in entity_fields or []:
        normalized["dataModel"]["entities"] = _upsert_entity(
            normalized["dataModel"]["entities"],
            {"name": item.get("entity", ""), "fields": [item.get("field", {})]},
        )
    for item in entity_relationships or []:
        normalized["dataModel"]["entities"] = _upsert_entity(
            normalized["dataModel"]["entities"],
            {"name": item.get("entity", ""), "relationships": [item.get("relationship", {})]},
        )
    for item in entity_states or []:
        normalized["dataModel"]["entities"] = _upsert_entity(
            normalized["dataModel"]["entities"],
            {"name": item.get("entity", ""), "states": [item.get("state", {})]},
        )

    for endpoint in endpoints or []:
        normalized["contracts"]["endpoints"] = _upsert_endpoint(normalized["contracts"]["endpoints"], endpoint)
    for item in endpoint_screens or []:
        normalized["contracts"]["endpoints"] = _upsert_endpoint(
            normalized["contracts"]["endpoints"],
            {"operationId": item.get("operationId", ""), "screenIds": [item.get("screenId", "")]},
        )
    for item in endpoint_fields or []:
        normalized["contracts"]["endpoints"] = _upsert_endpoint(
            normalized["contracts"]["endpoints"],
            {"operationId": item.get("operationId", ""), "fields": [item.get("field", {})]},
        )
    for item in endpoint_errors or []:
        normalized["contracts"]["endpoints"] = _upsert_endpoint(
            normalized["contracts"]["endpoints"],
            {"operationId": item.get("operationId", ""), "errors": [item.get("error", {})]},
        )

    normalized["integrations"] = _append_unique_dicts(
        normalized["integrations"],
        integrations or [],
        marker_fields=("name", "kind", "purpose"),
    )
    normalized["codePrinciples"] = append_unique_strings(normalized["codePrinciples"], code_principles or [])
    normalized["patterns"] = _append_unique_dicts(
        normalized["patterns"],
        patterns or [],
        marker_fields=("name", "rationale"),
    )
    normalized["securityNotes"] = append_unique_strings(normalized["securityNotes"], security_notes or [])
    normalized["performanceNotes"] = append_unique_strings(normalized["performanceNotes"], performance_notes or [])
    normalized["nextActions"] = append_unique_strings(normalized["nextActions"], next_actions or [])

    ts = now_iso()
    normalized["updatedAt"] = ts
    if checkpoint_summary is not None:
        normalized["checkpointSummary"] = _normalize_string(checkpoint_summary)
    if ratify:
        normalized["ratifiedAt"] = ts
        normalized["revision"] = int(normalized.get("revision", 0)) + 1
    return normalized


def _design_screen_ids(design_state: dict[str, Any]) -> set[str]:
    normalized_design, _ = normalize_design_state(design_state)
    return {screen.get("id", "") for screen in normalized_design.get("screens", []) if screen.get("id", "")}


def architecture_reference_errors(state: dict[str, Any], *, design_state: dict[str, Any]) -> list[str]:
    normalized, _ = normalize_architecture_state(state)
    normalized_design, _ = normalize_design_state(design_state)
    errors: list[str] = []
    screen_ids = _design_screen_ids(normalized_design)
    covered_screen_ids: set[str] = set()

    entity_names = {
        _normalize_name_key(entity.get("name", ""))
        for entity in normalized["dataModel"]["entities"]
        if entity.get("name", "")
    }
    for entity in normalized["dataModel"]["entities"]:
        for relationship in entity.get("relationships", []):
            if _normalize_name_key(relationship.get("target", "")) not in entity_names:
                errors.append(
                    f"architecture entity '{entity.get('name', '')}' references unknown target '{relationship.get('target', '')}'"
                )

    for endpoint in normalized["contracts"]["endpoints"]:
        operation_id = endpoint.get("operationId", "")
        if not endpoint.get("summary"):
            errors.append(f"architecture endpoint '{operation_id}' must include a summary")
        for screen_id in endpoint.get("screenIds", []):
            if screen_id not in screen_ids:
                errors.append(f"architecture endpoint '{operation_id}' references unknown screen '{screen_id}'")
            else:
                covered_screen_ids.add(screen_id)

    for screen in normalized_design.get("screens", []):
        screen_id = screen.get("id", "")
        if screen_id and screen_id not in covered_screen_ids:
            errors.append(f"architecture must link at least one endpoint to design screen '{screen_id}'")

    endpoint_map = {endpoint.get("operationId", ""): endpoint for endpoint in normalized["contracts"]["endpoints"]}
    for screen in normalized_design.get("screens", []):
        screen_id = screen.get("id", "")
        if not screen_id:
            continue
        linked = [endpoint for endpoint in endpoint_map.values() if screen_id in endpoint.get("screenIds", [])]
        if not linked:
            continue
        request_fields = {
            _normalize_name_key(field.get("name", ""))
            for endpoint in linked
            for field in endpoint.get("fields", [])
            if field.get("section", "") in ENDPOINT_FIELD_SECTIONS
        }
        response_fields = {
            _normalize_name_key(field.get("name", ""))
            for endpoint in linked
            for field in endpoint.get("fields", [])
            if str(field.get("section", "")).startswith("response:")
        }
        for data_kind in FLOW_DATA_KINDS:
            for name in screen.get("data", {}).get(data_kind, []):
                if data_kind == "input" and _normalize_name_key(name) not in request_fields:
                    errors.append(
                        f"architecture screen '{screen_id}' input '{name}' is missing from linked endpoint request fields"
                    )
                if data_kind == "displayed" and _normalize_name_key(name) not in response_fields:
                    errors.append(
                        f"architecture screen '{screen_id}' displayed field '{name}' is missing from linked endpoint response fields"
                    )

    return errors


def architecture_completeness_errors(state: dict[str, Any], *, design_state: dict[str, Any]) -> list[str]:
    normalized, _ = normalize_architecture_state(state)
    errors: list[str] = []
    if not normalized["architectureOverview"]:
        errors.append("architecture state must include an architecture overview before checkpoint")
    if not normalized["projectStructure"]["strategy"]:
        errors.append("architecture state must include a project structure strategy before checkpoint")
    if not normalized["projectStructure"]["rationale"]:
        errors.append("architecture state must include a project structure rationale before checkpoint")
    if not normalized["projectStructure"]["directories"]:
        errors.append("architecture state must include at least one directory before checkpoint")
    if not normalized["dataModel"]["entities"]:
        errors.append("architecture state must include at least one entity before checkpoint")
    elif not any(entity.get("fields") for entity in normalized["dataModel"]["entities"]):
        errors.append("architecture state must include at least one entity with fields before checkpoint")
    if not normalized["contracts"]["endpoints"]:
        errors.append("architecture state must include at least one endpoint before checkpoint")
    else:
        if not any(endpoint.get("screenIds") for endpoint in normalized["contracts"]["endpoints"]):
            errors.append("architecture state must include at least one endpoint linked to a screen before checkpoint")
        if not any(
            any(str(field.get("section", "")).startswith("response:") for field in endpoint.get("fields", []))
            for endpoint in normalized["contracts"]["endpoints"]
        ):
            errors.append("architecture state must include at least one response field before checkpoint")
    if not normalized["codePrinciples"] and not normalized["patterns"]:
        errors.append("architecture state must include at least one code principle or pattern before checkpoint")
    errors.extend(architecture_reference_errors(normalized, design_state=design_state))
    return errors


def architecture_schema_errors(state: Any) -> list[str]:
    if not isinstance(state, dict):
        return ["architecture state must be a JSON object"]
    normalized, _ = normalize_architecture_state(state)
    errors: list[str] = []
    if normalized["schemaVersion"] != ARCHITECTURE_SCHEMA_VERSION:
        errors.append(f"architecture state schemaVersion must equal {ARCHITECTURE_SCHEMA_VERSION}")
    if normalized["contracts"]["apiStyle"] != SUPPORTED_API_STYLE:
        errors.append(f"architecture contracts apiStyle must equal '{SUPPORTED_API_STYLE}'")
    return errors


def _render_list(values: list[str]) -> list[str]:
    if not values:
        return ["- Пока не зафиксировано."]
    return [f"- {value}" for value in values]


def render_architecture_markdown(
    state: dict[str, Any],
    *,
    branch_name: str,
    project_name: str = "",
) -> str:
    normalized, _ = normalize_architecture_state(state)
    project_label = project_name or "Не указано"
    lines = [
        f"# Архитектура проекта: {project_label}",
        "",
        (
            f"**Основано на**: `.madspec/{branch_name}/memory/stages/mvp.architecture.json`, "
            f"`.madspec/{branch_name}/concept.md`, `.madspec/{branch_name}/ui-design.md`, `.madspec/{branch_name}/tech-stack.md`"
        ),
        "",
        "## Обзор",
        "",
        normalized["architectureOverview"] or "Пока не зафиксировано.",
        "",
        "## Структура проекта",
        "",
        f"- **Стратегия**: {normalized['projectStructure']['strategy'] or 'Не указано'}",
        f"- **Обоснование**: {normalized['projectStructure']['rationale'] or 'Не указано'}",
        "",
        "### Директории",
        "",
    ]
    if normalized["projectStructure"]["directories"]:
        for item in normalized["projectStructure"]["directories"]:
            lines.append(f"- `{item['path']}`: {item['purpose']}")
    else:
        lines.append("- Пока не зафиксировано.")
    lines.extend(
        [
            "",
            "## Модель данных",
            "",
            f"**Детальная модель**: `.madspec/{branch_name}/data-model.md`",
            "",
        ]
    )
    for entity in normalized["dataModel"]["entities"]:
        lines.extend(
            [
                f"### {entity['name']}",
                "",
                entity.get("description") or "Без описания.",
                "",
                f"- Полей: {len(entity.get('fields', []))}",
                f"- Связей: {len(entity.get('relationships', []))}",
                f"- Состояний: {len(entity.get('states', []))}",
                "",
            ]
        )
    if not normalized["dataModel"]["entities"]:
        lines.extend(["Пока не зафиксировано.", ""])
    lines.extend(
        [
            "## API контракты",
            "",
            f"- **API style**: `{normalized['contracts']['apiStyle']}`",
            f"- **OpenAPI**: `.madspec/{branch_name}/contracts/openapi.yaml`",
            f"- **Endpoints**: {len(normalized['contracts']['endpoints'])}",
            "",
        ]
    )
    for endpoint in normalized["contracts"]["endpoints"]:
        lines.append(
            f"- `{endpoint['method']} {endpoint['path']}` (`{endpoint['operationId']}`) - {endpoint['summary']}"
        )
    if not normalized["contracts"]["endpoints"]:
        lines.append("- Пока не зафиксировано.")
    lines.extend(["", "## Внешние интеграции", ""])
    if normalized["integrations"]:
        for integration in normalized["integrations"]:
            touchpoints = ", ".join(integration.get("touchpoints", [])) or "Не указано"
            lines.append(
                f"- **{integration['name']}** ({integration['kind']}): {integration['purpose']} | Touchpoints: {touchpoints}"
            )
    else:
        lines.append("- Пока не зафиксировано.")
    lines.extend(["", "## Принципы организации кода", "", *_render_list(normalized["codePrinciples"]), ""])
    lines.extend(["## Архитектурные паттерны", ""])
    if normalized["patterns"]:
        for item in normalized["patterns"]:
            lines.append(f"- **{item['name']}**: {item['rationale']}")
        lines.append("")
    else:
        lines.extend(["- Пока не зафиксировано.", ""])
    lines.extend(["## Безопасность", "", *_render_list(normalized["securityNotes"]), ""])
    lines.extend(["## Производительность", "", *_render_list(normalized["performanceNotes"]), ""])
    lines.extend(["## Следующие шаги", "", *_render_list(normalized["nextActions"]), ""])
    lines.extend(
        [
            "## Checkpoint",
            "",
            normalized["checkpointSummary"] or "Пока не зафиксировано.",
            "",
            (
                f"Версия: {normalized['revision']} | "
                f"Ратифицирована: {normalized['ratifiedAt'] or 'Не указано'} | "
                f"Последнее изменение: {normalized['updatedAt'] or 'Не указано'}"
            ),
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def render_data_model_markdown(
    state: dict[str, Any],
    *,
    branch_name: str,
    project_name: str = "",
) -> str:
    normalized, _ = normalize_architecture_state(state)
    project_label = project_name or "Не указано"
    lines = [
        f"# Модель данных: {project_label}",
        "",
        f"**Основано на**: `.madspec/{branch_name}/memory/stages/mvp.architecture.json`",
        "",
    ]
    if not normalized["dataModel"]["entities"]:
        lines.extend(["Пока не зафиксировано.", ""])
        return "\n".join(lines) + "\n"
    for entity in normalized["dataModel"]["entities"]:
        lines.extend([f"## {entity['name']}", "", entity.get("description") or "Без описания.", "", "### Поля", ""])
        if entity.get("fields"):
            for field in entity["fields"]:
                required = "required" if field.get("required") else "optional"
                lines.append(
                    f"- **{field['name']}** `{field['type']}` ({required}) - {field.get('description') or 'Без описания'}"
                )
        else:
            lines.append("- Пока не зафиксировано.")
        lines.extend(["", "### Связи", ""])
        if entity.get("relationships"):
            for relation in entity["relationships"]:
                lines.append(
                    f"- **{relation['kind']}** -> `{relation['target']}`: {relation['description']}"
                )
        else:
            lines.append("- Пока не зафиксировано.")
        lines.extend(["", "### Состояния", ""])
        if entity.get("states"):
            for item in entity["states"]:
                lines.append(f"- **{item['name']}**: {item['description']}")
        else:
            lines.append("- Пока не зафиксировано.")
        lines.append("")
    return "\n".join(lines) + "\n"


def _yaml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _schema_name(operation_id: str, suffix: str) -> str:
    parts = [segment for segment in operation_id.split("-") if segment]
    stem = "".join(part.capitalize() for part in parts) or "Operation"
    return f"{stem}{suffix}"


def render_openapi_yaml(state: dict[str, Any], *, branch_name: str) -> str:
    normalized, _ = normalize_architecture_state(state)
    lines = [
        "openapi: 3.0.3",
        "info:",
        f"  title: {_yaml_quote(f'MADSpec {branch_name} Architecture API')}",
        '  version: "1.0.0"',
        "paths:",
    ]
    endpoints = sorted(
        normalized["contracts"]["endpoints"],
        key=lambda item: (item.get("path", ""), item.get("method", ""), item.get("operationId", "")),
    )
    if not endpoints:
        lines.append("  {}")
    else:
        for endpoint in endpoints:
            lines.append(f"  {endpoint['path']}:")
            lines.append(f"    {endpoint['method'].lower()}:")
            lines.append(f"      operationId: {endpoint['operationId']}")
            lines.append(f"      summary: {_yaml_quote(endpoint['summary'])}")
            if endpoint.get("screenIds"):
                lines.append("      tags:")
                for screen_id in endpoint["screenIds"]:
                    lines.append(f"        - {_yaml_quote(screen_id)}")
            parameter_fields = [field for field in endpoint.get("fields", []) if field.get("section") in {"path", "query"}]
            if parameter_fields:
                lines.append("      parameters:")
                for field in parameter_fields:
                    lines.extend(
                        [
                            f"        - name: {field['name']}",
                            f"          in: {field['section']}",
                            f"          required: {'true' if field.get('required') else 'false'}",
                            "          schema:",
                            f"            type: {_yaml_quote(field['type'])}",
                            f"          description: {_yaml_quote(field.get('description') or '')}",
                        ]
                    )
            request_fields = [field for field in endpoint.get("fields", []) if field.get("section") == "request"]
            if request_fields:
                request_schema = _schema_name(endpoint["operationId"], "Request")
                lines.extend(
                    [
                        "      requestBody:",
                        "        required: true",
                        "        content:",
                        "          application/json:",
                        "            schema:",
                        f"              $ref: '#/components/schemas/{request_schema}'",
                    ]
                )
            lines.append("      responses:")
            response_fields = [field for field in endpoint.get("fields", []) if str(field.get("section", "")).startswith("response:")]
            grouped_responses: dict[str, list[dict[str, Any]]] = {}
            for field in response_fields:
                status = field["section"].split(":", 1)[1]
                grouped_responses.setdefault(status, []).append(field)
            error_lookup = {error["status"]: error for error in endpoint.get("errors", [])}
            if not grouped_responses:
                lines.extend(
                    [
                        '        "200":',
                        "          description: OK",
                    ]
                )
            else:
                for status in sorted(grouped_responses):
                    response_schema = _schema_name(endpoint["operationId"], f"{status}Response")
                    description = error_lookup.get(status, {}).get("description", "Success")
                    lines.extend(
                        [
                            f'        "{status}":',
                            f"          description: {_yaml_quote(description)}",
                            "          content:",
                            "            application/json:",
                            "              schema:",
                            f"                $ref: '#/components/schemas/{response_schema}'",
                        ]
                    )
    lines.append("components:")
    lines.append("  schemas:")
    emitted_schemas = False
    for endpoint in endpoints:
        request_fields = [field for field in endpoint.get("fields", []) if field.get("section") == "request"]
        if request_fields:
            emitted_schemas = True
            request_schema = _schema_name(endpoint["operationId"], "Request")
            lines.extend(_render_object_schema(request_schema, request_fields, indent="    "))
        response_fields = [field for field in endpoint.get("fields", []) if str(field.get("section", "")).startswith("response:")]
        grouped_responses: dict[str, list[dict[str, Any]]] = {}
        for field in response_fields:
            status = field["section"].split(":", 1)[1]
            grouped_responses.setdefault(status, []).append(field)
        for status in sorted(grouped_responses):
            emitted_schemas = True
            response_schema = _schema_name(endpoint["operationId"], f"{status}Response")
            lines.extend(_render_object_schema(response_schema, grouped_responses[status], indent="    "))
    if not emitted_schemas:
        lines.append("    EmptyObject:")
        lines.append("      type: object")
        lines.append("      properties: {}")
    return "\n".join(lines) + "\n"


def _render_object_schema(name: str, fields: list[dict[str, Any]], *, indent: str) -> list[str]:
    lines = [f"{indent}{name}:", f"{indent}  type: object", f"{indent}  properties:"]
    required_names = [field["name"] for field in fields if field.get("required")]
    for field in fields:
        lines.extend(
            [
                f"{indent}    {field['name']}:",
                f"{indent}      type: {_yaml_quote(field['type'])}",
                f"{indent}      description: {_yaml_quote(field.get('description') or '')}",
            ]
        )
    if required_names:
        lines.append(f"{indent}  required:")
        for field_name in required_names:
            lines.append(f"{indent}    - {field_name}")
    return lines
