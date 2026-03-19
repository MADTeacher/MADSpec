from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from madspec_cli.config import AGENT_CONFIG
from madspec_cli.memory.shared.storage import now_iso, read_json, write_json
from madspec_cli.project_state import (
    MADSPEC_AGENTS_SCHEMA_VERSION,
    create_madspec_config,
    read_madspec_config,
    update_madspec_config,
)

from ..domain.builtin_roles import DEFAULT_PROFILE_ID, DEFAULT_SUBAGENT_IDS
from ..domain.frontmatter_profiles import subagent_frontmatter_profile_for_environment
from ..domain.normalizers import unique_role_ids


AGENTS_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class AgentsPaths:
    system_dir: Path
    agents_dir: Path
    state_file: Path
    catalog_file: Path
    bodies_dir: Path
    proposals_file: Path
    history_file: Path
    artifact_file: Path


def get_agents_paths(project_path: Path) -> AgentsPaths:
    system_dir = project_path / ".madspec" / "system"
    agents_dir = system_dir / "agents"
    return AgentsPaths(
        system_dir=system_dir,
        agents_dir=agents_dir,
        state_file=agents_dir / "state.json",
        catalog_file=agents_dir / "catalog.json",
        bodies_dir=agents_dir / "bodies",
        proposals_file=agents_dir / "proposals.jsonl",
        history_file=agents_dir / "history.jsonl",
        artifact_file=system_dir / "agents.md",
    )


def detect_agent_environment(project_path: Path) -> str | None:
    detected: list[str] = []
    for environment_id, config in AGENT_CONFIG.items():
        if (project_path / config.folder).exists():
            detected.append(environment_id)
    if len(detected) == 1:
        return detected[0]
    return None


def build_environment_profile(environment_id: str) -> dict[str, Any]:
    config = AGENT_CONFIG[environment_id]
    frontmatter_profile = None
    if config.subagent_frontmatter_profile:
        frontmatter = subagent_frontmatter_profile_for_environment(environment_id)
        frontmatter_profile = {
            "profileId": frontmatter.profile_id,
            "modelStrategy": frontmatter.model_strategy,
            "modelField": frontmatter.model_field,
            "toolsField": frontmatter.tools_field,
            "toolTranslatorId": frontmatter.tool_translator_id,
            "supportsExecutionModeHint": frontmatter.include_execution_mode_hint,
            "supportsDependencies": frontmatter.include_dependencies,
        }
    return {
        "environmentId": environment_id,
        "displayName": config.name,
        "supportsNativeSubagents": config.supports_native_subagents,
        "commandDir": f"{config.folder}{config.commands_subdir}",
        "commandExtension": config.command_extension,
        "subagentsDir": f"{config.folder}{config.subagents_subdir}" if config.subagents_subdir else None,
        "subagentExtension": config.subagent_extension,
        "subagentFrontmatterProfile": frontmatter_profile,
        "fallbackStrategy": config.fallback_strategy,
    }


def default_agents_state(environment_id: str) -> dict[str, Any]:
    ts = now_iso()
    return {
        "schemaVersion": AGENTS_SCHEMA_VERSION,
        "profileId": DEFAULT_PROFILE_ID,
        "environmentId": environment_id,
        "revision": 1,
        "createdAt": ts,
        "updatedAt": ts,
        "enabledSubagentIds": list(DEFAULT_SUBAGENT_IDS),
    }


def migrate_agents_state(state: dict[str, Any], *, environment_id: str) -> dict[str, Any]:
    normalized = dict(state)
    normalized["schemaVersion"] = int(normalized.get("schemaVersion") or AGENTS_SCHEMA_VERSION)
    normalized["profileId"] = normalized.get("profileId") or DEFAULT_PROFILE_ID
    normalized["environmentId"] = normalized.get("environmentId") or environment_id
    normalized["revision"] = int(normalized.get("revision") or 1)
    normalized["createdAt"] = normalized.get("createdAt") or now_iso()
    normalized["updatedAt"] = normalized.get("updatedAt") or normalized["createdAt"]
    enabled_ids = normalized.get("enabledSubagentIds")
    if isinstance(enabled_ids, list):
        normalized["enabledSubagentIds"] = unique_role_ids(enabled_ids)
    else:
        legacy_subagents = normalized.get("subagents")
        if isinstance(legacy_subagents, list) and legacy_subagents:
            migrated_enabled: list[str] = []
            for item in legacy_subagents:
                if not isinstance(item, dict):
                    continue
                role_id = str(item.get("subagentId") or "")
                if not role_id:
                    continue
                if bool(item.get("enabled", True)):
                    migrated_enabled.append(role_id)
            normalized["enabledSubagentIds"] = unique_role_ids(migrated_enabled or list(DEFAULT_SUBAGENT_IDS))
        else:
            normalized["enabledSubagentIds"] = list(DEFAULT_SUBAGENT_IDS)
    normalized.pop("subagents", None)
    return normalized


def ensure_agents_layout(project_path: Path, *, environment_id: str | None = None) -> tuple[dict[str, Any], list[Path]]:
    from .artifact_export import export_agents_artifact
    from .catalog_store import default_agents_catalog, migrate_agents_catalog

    paths = get_agents_paths(project_path)
    created: list[Path] = []
    if environment_id is None:
        config_payload = read_madspec_config(project_path)
        environment_id = config_payload.get("agentEnvironment") if isinstance(config_payload.get("agentEnvironment"), str) else None
    if environment_id is None:
        environment_id = detect_agent_environment(project_path) or "cursor-agent"

    for path in (paths.system_dir, paths.agents_dir, paths.bodies_dir):
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(path)

    state = read_json(paths.state_file, None)
    if not isinstance(state, dict):
        state = default_agents_state(environment_id)
        write_json(paths.state_file, state)
        created.append(paths.state_file)
    else:
        state = migrate_agents_state(state, environment_id=environment_id)
        write_json(paths.state_file, state)

    catalog = read_json(paths.catalog_file, None)
    if not isinstance(catalog, dict):
        catalog = default_agents_catalog()
        write_json(paths.catalog_file, catalog)
        created.append(paths.catalog_file)
    else:
        catalog = migrate_agents_catalog(catalog)
        write_json(paths.catalog_file, catalog)

    if not paths.proposals_file.exists():
        paths.proposals_file.write_text("", encoding="utf-8")
        created.append(paths.proposals_file)
    if not paths.history_file.exists():
        paths.history_file.write_text("", encoding="utf-8")
        created.append(paths.history_file)

    export_agents_artifact(project_path, state)
    create_madspec_config(
        project_path,
        read_madspec_config(project_path).get("currentBranch") or "main",
        agent_environment=environment_id,
    )
    update_madspec_config(
        project_path,
        agentEnvironment=environment_id,
        agentsSchemaVersion=MADSPEC_AGENTS_SCHEMA_VERSION,
        activeAgentsProfile=state.get("profileId", DEFAULT_PROFILE_ID),
    )
    return state, created


def load_agents_state(project_path: Path, *, create_if_missing: bool = True) -> dict[str, Any]:
    paths = get_agents_paths(project_path)
    if create_if_missing:
        state, _ = ensure_agents_layout(project_path)
        return state
    return migrate_agents_state(
        read_json(paths.state_file, {}),
        environment_id=read_madspec_config(project_path).get("agentEnvironment")
        or detect_agent_environment(project_path)
        or "cursor-agent",
    )


def save_agents_state(project_path: Path, state: dict[str, Any]) -> dict[str, Any]:
    from .artifact_export import export_agents_artifact

    paths = get_agents_paths(project_path)
    paths.agents_dir.mkdir(parents=True, exist_ok=True)
    state = migrate_agents_state(
        state,
        environment_id=state.get("environmentId") or detect_agent_environment(project_path) or "cursor-agent",
    )
    write_json(paths.state_file, state)
    export_agents_artifact(project_path, state)
    update_madspec_config(
        project_path,
        agentEnvironment=state.get("environmentId"),
        agentsSchemaVersion=MADSPEC_AGENTS_SCHEMA_VERSION,
        activeAgentsProfile=state.get("profileId", DEFAULT_PROFILE_ID),
    )
    return state
