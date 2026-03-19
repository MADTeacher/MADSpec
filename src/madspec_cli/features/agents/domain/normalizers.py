from __future__ import annotations

import re
from typing import Any

from .builtin_roles import ROLE_METADATA_FIELDS
from .tool_translation import TOOL_POLICY_KEYS


_SUBAGENT_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def unique_role_ids(role_ids: list[str]) -> list[str]:
    unique_ids: list[str] = []
    for item in role_ids:
        role_id = str(item or "").strip()
        if role_id and role_id not in unique_ids:
            unique_ids.append(role_id)
    return unique_ids


def validate_subagent_id(subagent_id: str) -> str:
    normalized = str(subagent_id or "").strip()
    if not _SUBAGENT_ID_RE.fullmatch(normalized):
        raise ValueError("subagentId must be a slug with lowercase letters, digits, and hyphens")
    return normalized


def _normalize_tool_policy(tool_policy: Any) -> dict[str, bool]:
    if not isinstance(tool_policy, dict):
        raise ValueError("toolPolicy must be an object")
    unknown_keys = sorted(set(tool_policy) - set(TOOL_POLICY_KEYS))
    if unknown_keys:
        raise ValueError(f"toolPolicy contains unsupported keys: {', '.join(unknown_keys)}")
    return {key: bool(tool_policy.get(key, False)) for key in TOOL_POLICY_KEYS}


def normalize_catalog_role(role: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {
        "subagentId": str(role.get("subagentId") or "").strip(),
        "kind": "override" if str(role.get("kind") or "project") == "override" else "project",
    }
    for key in ROLE_METADATA_FIELDS:
        value = role.get(key)
        if key == "dependencies":
            normalized[key] = [str(item) for item in value] if isinstance(value, list) else []
        elif key == "toolPolicy":
            normalized[key] = (
                {tool_key: bool(value.get(tool_key)) for tool_key in TOOL_POLICY_KEYS}
                if isinstance(value, dict)
                else {tool_key: False for tool_key in TOOL_POLICY_KEYS}
            )
        elif key == "outputContract":
            normalized[key] = dict(value) if isinstance(value, dict) else {}
        else:
            normalized[key] = value
    body_file = role.get("bodyFile")
    normalized["bodyFile"] = str(body_file) if body_file else None
    return normalized


def normalize_subagent_definition(
    *,
    subagent_id: str,
    payload: dict[str, Any],
    kind: str,
) -> dict[str, Any]:
    normalized_id = validate_subagent_id(subagent_id)
    if kind not in {"project", "override"}:
        raise ValueError("kind must be project or override")
    normalized: dict[str, Any] = {
        "subagentId": normalized_id,
        "kind": kind,
    }
    required_string_fields = ("title", "description", "purpose", "defaultStage", "executionModeHint")
    for key in required_string_fields:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} is required and must be a non-empty string")
        normalized[key] = value.strip()
    dependencies = payload.get("dependencies", [])
    if dependencies is None:
        dependencies = []
    if not isinstance(dependencies, list):
        raise ValueError("dependencies must be an array")
    normalized["dependencies"] = [validate_subagent_id(item) for item in dependencies]
    if normalized_id in normalized["dependencies"]:
        raise ValueError("dependencies cannot include the subagent itself")
    normalized["toolPolicy"] = _normalize_tool_policy(payload.get("toolPolicy"))
    output_contract = payload.get("outputContract", {})
    if not isinstance(output_contract, dict):
        raise ValueError("outputContract must be an object")
    normalized["outputContract"] = dict(output_contract)
    normalized["bodyFile"] = payload.get("bodyFile")
    return normalized


def validate_subagent_definition_dependencies(definition: dict[str, Any], *, existing_ids: set[str]) -> None:
    dependencies = list(definition.get("dependencies") or [])
    if not dependencies:
        return
    unknown_dependencies = [item for item in dependencies if item not in existing_ids]
    if unknown_dependencies:
        raise ValueError(f"dependencies reference unknown role ids: {', '.join(sorted(unknown_dependencies))}")
