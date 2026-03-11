from __future__ import annotations

from typing import Any

from .shared import (
    normalize_endpoint_sections,
    normalize_identifier,
    normalize_path,
    normalize_required_flag,
    normalize_string,
)


def parse_project_structure_value(value: str) -> dict[str, str] | None:
    parts = [segment.strip() for segment in value.split("::", 1)]
    if len(parts) != 2:
        return None
    normalized = {
        "strategy": normalize_string(parts[0]),
        "rationale": normalize_string(parts[1]),
    }
    if not all(normalized.values()):
        return None
    return normalized


def parse_directory_value(value: str) -> dict[str, str] | None:
    parts = [segment.strip() for segment in value.split("::", 1)]
    if len(parts) != 2:
        return None
    normalized = {"path": normalize_path(parts[0]), "purpose": normalize_string(parts[1])}
    if not all(normalized.values()):
        return None
    return normalized


def parse_entity_value(value: str) -> dict[str, str] | None:
    parts = [segment.strip() for segment in value.split("::", 1)]
    if len(parts) != 2:
        return None
    normalized = {"name": normalize_string(parts[0]), "description": normalize_string(parts[1])}
    if not all(normalized.values()):
        return None
    return normalized


def parse_entity_field_value(value: str) -> dict[str, Any] | None:
    parts = [segment.strip() for segment in value.split("::", 4)]
    if len(parts) != 5:
        return None
    entity_name = normalize_string(parts[0])
    field_name = normalize_string(parts[1])
    field_type = normalize_string(parts[2])
    required_text = normalize_string(parts[3]).lower()
    description = normalize_string(parts[4])
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
    entity_name = normalize_string(parts[0])
    target = normalize_string(parts[1])
    kind = normalize_string(parts[2])
    description = normalize_string(parts[3])
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
    entity_name = normalize_string(parts[0])
    state_name = normalize_string(parts[1])
    description = normalize_string(parts[2])
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
    operation_id = normalize_identifier(parts[0])
    method = normalize_string(parts[1]).upper()
    path = normalize_string(parts[2])
    summary = normalize_string(parts[3])
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
    operation_id = normalize_identifier(parts[0])
    screen_id = normalize_identifier(parts[1])
    if not operation_id or not screen_id:
        return None
    return {"operationId": operation_id, "screenId": screen_id}


def parse_endpoint_field_value(value: str) -> dict[str, Any] | None:
    parts = [segment.strip() for segment in value.split("::", 5)]
    if len(parts) != 6:
        return None
    operation_id = normalize_identifier(parts[0])
    section = normalize_endpoint_sections(parts[1])
    name = normalize_string(parts[2])
    field_type = normalize_string(parts[3])
    required_text = normalize_string(parts[4]).lower()
    description = normalize_string(parts[5])
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
    operation_id = normalize_identifier(parts[0])
    status = normalize_string(parts[1])
    code = normalize_string(parts[2])
    description = normalize_string(parts[3])
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
        "name": normalize_string(parts[0]),
        "kind": normalize_string(parts[1]),
        "purpose": normalize_string(parts[2]),
        "touchpoints": [segment.strip() for segment in parts[3].split("|") if segment.strip()],
    }
    if not all([normalized["name"], normalized["kind"], normalized["purpose"]]):
        return None
    return normalized


def parse_pattern_value(value: str) -> dict[str, str] | None:
    parts = [segment.strip() for segment in value.split("::", 1)]
    if len(parts) != 2:
        return None
    normalized = {"name": normalize_string(parts[0]), "rationale": normalize_string(parts[1])}
    if not all(normalized.values()):
        return None
    return normalized
