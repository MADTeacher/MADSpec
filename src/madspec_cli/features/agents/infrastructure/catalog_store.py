from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from madspec_cli.config import AGENT_CONFIG
from madspec_cli.memory.shared.storage import append_jsonl, now_iso, read_json, read_jsonl, write_json

from ..domain.builtin_roles import DEFAULT_PROFILE_ID, DEFAULT_SUBAGENT_IDS, role_catalog
from ..domain.normalizers import (
    normalize_catalog_role,
    normalize_subagent_definition,
    unique_role_ids,
    validate_subagent_definition_dependencies,
    validate_subagent_id,
)
from .state_store import detect_agent_environment, get_agents_paths, load_agents_state


AGENTS_CATALOG_SCHEMA_VERSION = 1


def default_agents_catalog() -> dict[str, Any]:
    return {
        "schemaVersion": AGENTS_CATALOG_SCHEMA_VERSION,
        "updatedAt": now_iso(),
        "roles": [],
    }


def migrate_agents_catalog(catalog: dict[str, Any] | None) -> dict[str, Any]:
    normalized = dict(catalog or {})
    normalized["schemaVersion"] = int(normalized.get("schemaVersion") or AGENTS_CATALOG_SCHEMA_VERSION)
    normalized["updatedAt"] = normalized.get("updatedAt") or now_iso()
    roles = normalized.get("roles")
    if not isinstance(roles, list):
        normalized["roles"] = []
    else:
        normalized["roles"] = [normalize_catalog_role(item) for item in roles if isinstance(item, dict)]
    return normalized


def load_agents_catalog(project_path: Path, *, create_if_missing: bool = True) -> dict[str, Any]:
    paths = get_agents_paths(project_path)
    if create_if_missing and not paths.catalog_file.exists():
        paths.agents_dir.mkdir(parents=True, exist_ok=True)
        paths.bodies_dir.mkdir(parents=True, exist_ok=True)
        catalog = default_agents_catalog()
        write_json(paths.catalog_file, catalog)
        return catalog
    return migrate_agents_catalog(read_json(paths.catalog_file, {}))


def save_agents_catalog(project_path: Path, catalog: dict[str, Any]) -> dict[str, Any]:
    paths = get_agents_paths(project_path)
    paths.agents_dir.mkdir(parents=True, exist_ok=True)
    paths.bodies_dir.mkdir(parents=True, exist_ok=True)
    catalog = migrate_agents_catalog(catalog)
    catalog["updatedAt"] = now_iso()
    write_json(paths.catalog_file, catalog)
    return catalog


def list_agent_proposals(project_path: Path) -> list[dict[str, Any]]:
    return read_jsonl(get_agents_paths(project_path).proposals_file)


def append_agent_proposal(project_path: Path, proposal: dict[str, Any]) -> None:
    append_jsonl(get_agents_paths(project_path).proposals_file, [proposal])


def list_agent_history(project_path: Path) -> list[dict[str, Any]]:
    return read_jsonl(get_agents_paths(project_path).history_file)


def append_agent_history(project_path: Path, event: dict[str, Any]) -> None:
    append_jsonl(get_agents_paths(project_path).history_file, [event])


def build_agents_diff(before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, Any]:
    before = before or {}
    after = after or {}
    changes: list[dict[str, Any]] = []
    for key in sorted(set(before) | set(after)):
        if before.get(key) != after.get(key):
            changes.append({"field": key, "before": before.get(key), "after": after.get(key)})
    return {"changedFields": [item["field"] for item in changes], "changes": changes}


def project_body_relative_path(subagent_id: str) -> str:
    return f".madspec/system/agents/bodies/{subagent_id}.md"


def body_file_name(subagent_id: str) -> str:
    return f"{subagent_id}.md"


def body_file_path(project_path: Path, subagent_id: str) -> Path:
    return get_agents_paths(project_path).bodies_dir / body_file_name(subagent_id)


def load_effective_subagents(project_path: Path, *, state: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    state = state or load_agents_state(project_path)
    environment_id = state.get("environmentId") or detect_agent_environment(project_path) or "cursor-agent"
    effective: dict[str, dict[str, Any]] = {
        item["subagentId"]: dict(item) for item in role_catalog(environment_id=environment_id)
    }
    ordered_ids = [item["subagentId"] for item in role_catalog(environment_id=environment_id)]
    catalog = load_agents_catalog(project_path)
    for item in catalog.get("roles", []):
        subagent_id = str(item.get("subagentId") or "")
        if not subagent_id:
            continue
        merged = {
            "subagentId": subagent_id,
            "title": item.get("title"),
            "description": item.get("description"),
            "purpose": item.get("purpose"),
            "defaultStage": item.get("defaultStage"),
            "executionModeHint": item.get("executionModeHint"),
            "dependencies": list(item.get("dependencies") or []),
            "toolPolicy": dict(item.get("toolPolicy") or {}),
            "outputContract": dict(item.get("outputContract") or {}),
            "origin": item.get("kind"),
            "bodySource": project_body_relative_path(subagent_id) if item.get("bodyFile") else f"template:{subagent_id}",
            "enabled": False,
            "renderMode": "native" if AGENT_CONFIG[environment_id].supports_native_subagents else "fallback",
        }
        if subagent_id in effective:
            merged_effective = dict(effective[subagent_id])
            merged_effective.update(merged)
            merged_effective["origin"] = "override"
            effective[subagent_id] = merged_effective
        else:
            effective[subagent_id] = merged
            ordered_ids.append(subagent_id)
    enabled_set = set(unique_role_ids(list(state.get("enabledSubagentIds") or [])))
    return [
        {**effective[subagent_id], "enabled": subagent_id in enabled_set}
        for subagent_id in ordered_ids
        if subagent_id in effective
    ]


def find_effective_subagent(project_path: Path, subagent_id: str, *, state: dict[str, Any] | None = None) -> dict[str, Any] | None:
    for item in load_effective_subagents(project_path, state=state):
        if item.get("subagentId") == subagent_id:
            return item
    return None


def enabled_subagents_for_output(project_path: Path, state: dict[str, Any]) -> dict[str, Any]:
    effective_subagents = load_effective_subagents(project_path, state=state)
    return {
        **state,
        "enabledSubagentIds": unique_role_ids(list(state.get("enabledSubagentIds") or [])),
        "subagents": effective_subagents,
    }


def upsert_catalog_role(
    project_path: Path,
    *,
    subagent_id: str,
    payload: dict[str, Any],
    body_text: str | None,
    allow_create: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_id = validate_subagent_id(subagent_id)
    catalog = load_agents_catalog(project_path)
    existing_index = next(
        (index for index, item in enumerate(catalog.get("roles", [])) if item.get("subagentId") == normalized_id),
        None,
    )
    state = load_agents_state(project_path)
    builtin_ids = {item["subagentId"] for item in role_catalog(environment_id=state.get("environmentId") or "cursor-agent")}
    if existing_index is None and normalized_id in builtin_ids:
        if allow_create:
            raise ValueError(f"subagent '{normalized_id}' already exists as a built-in role; use update to override it")
        kind = "override"
    elif existing_index is None and not allow_create:
        raise ValueError(f"project-defined subagent '{normalized_id}' was not found; use create first")
    elif existing_index is None:
        kind = "project"
    else:
        kind = str(catalog["roles"][existing_index].get("kind") or "project")

    definition = normalize_subagent_definition(subagent_id=normalized_id, payload=payload, kind=kind)
    existing_ids = set(builtin_ids)
    for item in catalog.get("roles", []):
        role_id = str(item.get("subagentId") or "")
        if role_id and role_id != definition["subagentId"]:
            existing_ids.add(role_id)
    validate_subagent_definition_dependencies(definition, existing_ids=existing_ids)

    if existing_index is None and kind == "project" and not body_text:
        raise ValueError("body-file is required when creating a project-defined subagent")
    if body_text:
        definition["bodyFile"] = body_file_name(normalized_id)
    elif existing_index is not None:
        definition["bodyFile"] = catalog["roles"][existing_index].get("bodyFile")
    elif kind == "override":
        definition["bodyFile"] = None

    if existing_index is None:
        catalog.setdefault("roles", []).append(definition)
    else:
        catalog["roles"][existing_index] = definition
    saved_catalog = save_agents_catalog(project_path, catalog)
    if body_text is not None:
        body_file_path(project_path, normalized_id).write_text(body_text.strip() + "\n", encoding="utf-8")
    return saved_catalog, definition


def remove_catalog_role(project_path: Path, *, subagent_id: str, force: bool) -> tuple[dict[str, Any], dict[str, Any] | None]:
    normalized_id = validate_subagent_id(subagent_id)
    state = load_agents_state(project_path)
    enabled_ids = unique_role_ids(list(state.get("enabledSubagentIds") or []))
    catalog = load_agents_catalog(project_path)
    existing_index = next(
        (index for index, item in enumerate(catalog.get("roles", [])) if item.get("subagentId") == normalized_id),
        None,
    )
    if existing_index is None:
        raise ValueError(f"project-defined subagent '{normalized_id}' was not found")
    removed = catalog["roles"].pop(existing_index)
    builtin_ids = {item["subagentId"] for item in role_catalog(environment_id=state.get("environmentId") or "cursor-agent")}
    removing_override_only = removed.get("kind") == "override" and normalized_id in builtin_ids
    if normalized_id in enabled_ids and not force and not removing_override_only:
        raise ValueError(f"subagent '{normalized_id}' is enabled; use --force to remove it")
    saved_catalog = save_agents_catalog(project_path, catalog)
    body_path = body_file_path(project_path, normalized_id)
    if body_path.exists():
        body_path.unlink()
    if normalized_id in enabled_ids and not removing_override_only:
        state["enabledSubagentIds"] = [item for item in enabled_ids if item != normalized_id]
        state["revision"] = int(state.get("revision") or 0) + 1
        state["updatedAt"] = now_iso()
        from .state_store import save_agents_state

        save_agents_state(project_path, state)
    return saved_catalog, removed


def build_profile_payload(
    *,
    environment_id: str,
    profile_id: str = DEFAULT_PROFILE_ID,
    enabled_subagents: list[str] | None = None,
) -> dict[str, Any]:
    enabled_subagents = unique_role_ids(enabled_subagents or list(DEFAULT_SUBAGENT_IDS))
    from .state_store import default_agents_state

    state = default_agents_state(environment_id)
    state["profileId"] = profile_id
    state["enabledSubagentIds"] = enabled_subagents
    return state


def create_profile_proposal(
    *,
    current_state: dict[str, Any],
    environment_id: str,
    profile_id: str,
    enabled_subagents: list[str],
    requested_by: str,
) -> dict[str, Any]:
    next_state = build_profile_payload(
        environment_id=environment_id,
        profile_id=profile_id,
        enabled_subagents=enabled_subagents,
    )
    return {
        "proposalId": str(uuid.uuid4()),
        "profileId": profile_id,
        "environmentId": environment_id,
        "status": "pending",
        "requestedAt": now_iso(),
        "requestedBy": requested_by,
        "summary": f"Set subagent profile {profile_id} for {environment_id}",
        "before": current_state,
        "after": next_state,
        "diff": build_agents_diff(current_state, next_state),
        "appliedAt": None,
    }
