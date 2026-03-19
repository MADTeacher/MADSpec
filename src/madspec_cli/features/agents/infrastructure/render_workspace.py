from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from madspec_cli.config import AGENT_CONFIG

from ..domain.frontmatter_profiles import resolve_subagent_model, subagent_frontmatter_profile_for_environment
from ..domain.tool_translation import translate_tool_policy
from .catalog_store import load_effective_subagents


MANAGED_FILE_PREFIX = "madspec-"


def managed_subagent_filename(environment_id: str, role_id: str) -> str:
    config = AGENT_CONFIG[environment_id]
    extension = config.subagent_extension or "md"
    return f"{MANAGED_FILE_PREFIX}{role_id}.{extension}"


def managed_role_id_from_path(filename: str) -> str:
    role = re.sub(r"\.(agent\.)?md$", "", filename)
    return role.removeprefix(MANAGED_FILE_PREFIX)


def load_subagent_template_body(subagent_id: str) -> str:
    repo_root = Path(__file__).resolve().parents[5]
    template_path = repo_root / "templates" / "subagents" / f"{subagent_id}.md"
    if template_path.exists():
        return template_path.read_text(encoding="utf-8").strip() + "\n"
    return (
        f"Ты отвечаешь за область `{subagent_id}` в текущем продукте и репозитории.\n\n"
        "Перед началом работы получи актуальный контекст для этой роли через "
        "`madspec agents subagents context --subagent-id "
        f"{subagent_id} --json-output`.\n"
    )


def load_subagent_body(project_path: Path | None, role: dict[str, Any]) -> str:
    body_source = str(role.get("bodySource") or "")
    if project_path is not None and body_source.startswith(".madspec/"):
        path = project_path / body_source
        if path.exists():
            return path.read_text(encoding="utf-8").strip() + "\n"
    subagent_id = str(role.get("subagentId") or "")
    return load_subagent_template_body(subagent_id)


def serialize_frontmatter(frontmatter: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in frontmatter.items():
        if isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
            continue
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for nested_key, nested_value in value.items():
                rendered = "true" if isinstance(nested_value, bool) and nested_value else "false" if isinstance(nested_value, bool) else str(nested_value)
                lines.append(f"  {nested_key}: {rendered}")
            continue
        if isinstance(value, list):
            rendered_items = ", ".join(_serialize_inline_yaml_scalar(item) for item in value)
            lines.append(f"{key}: [{rendered_items}]")
            continue
        lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def _serialize_inline_yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return f'"{value}"'


def render_native_subagent_file(environment_id: str, role: dict[str, Any], *, project_path: Path | None = None) -> str:
    body = load_subagent_body(project_path, role)
    profile = subagent_frontmatter_profile_for_environment(environment_id)
    frontmatter: dict[str, Any] = {}

    if profile.include_name:
        frontmatter["name"] = role["title"]
    if profile.include_description:
        frontmatter["description"] = role["description"]
    for key, value in profile.static_fields:
        frontmatter[key] = value

    model = resolve_subagent_model(environment_id, role["subagentId"])
    if profile.model_field and model:
        frontmatter[profile.model_field] = model

    translated_tools = translate_tool_policy(environment_id, role.get("toolPolicy", {}))
    if profile.tools_field and translated_tools:
        frontmatter[profile.tools_field] = translated_tools

    if profile.include_execution_mode_hint:
        frontmatter["execution_mode_hint"] = role.get("executionModeHint", "sequential")
    if profile.include_dependencies and role.get("dependencies"):
        frontmatter["dependencies"] = list(role["dependencies"])

    return serialize_frontmatter(frontmatter) + body


def render_fallback_guidance_file(environment_id: str, effective_roles: list[dict[str, Any]]) -> str:
    enabled = [item for item in effective_roles if item.get("enabled")]
    lines = [
        "# Подсказки по субагентам MADSpec",
        "",
        f"Активная среда: `{environment_id}`",
        "",
        "Эта среда сейчас использует запасной режим подсказок MADSpec вместо встроенных файлов субагентов.",
        "Используй `/madspec.agents`, чтобы посмотреть и скорректировать активный набор ролей.",
        "",
        "## Активные роли",
        "",
    ]
    for item in enabled:
        lines.append(f"- `{item['subagentId']}` ({item.get('origin')}): {item['description']}")
    lines.extend(
        [
            "",
            "## Канонический контекст",
            "",
            "Каждая роль должна получать свой контекст через `madspec agents subagents context --subagent-id <role>`.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_workspace_agents(project_path: Path, state: dict[str, Any]) -> dict[str, list[str]]:
    environment_id = state.get("environmentId") or "cursor-agent"
    config = AGENT_CONFIG[environment_id]
    created: list[str] = []
    removed: list[str] = []
    effective_roles = load_effective_subagents(project_path, state=state)

    if config.supports_native_subagents and config.subagents_subdir:
        target_dir = project_path / config.folder / config.subagents_subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        active_roles = [item for item in effective_roles if item.get("enabled")]
        active_ids = {str(item.get("subagentId")) for item in active_roles}
        for role in active_roles:
            role_id = str(role["subagentId"])
            file_path = target_dir / managed_subagent_filename(environment_id, role_id)
            file_path.write_text(
                render_native_subagent_file(environment_id, role, project_path=project_path),
                encoding="utf-8",
            )
            created.append(str(file_path.relative_to(project_path)))
        for stale_path in target_dir.glob(f"{MANAGED_FILE_PREFIX}*"):
            stale_role = managed_role_id_from_path(stale_path.name)
            if stale_role not in active_ids:
                stale_path.unlink()
                removed.append(str(stale_path.relative_to(project_path)))
    else:
        target_dir = project_path / config.folder / config.commands_subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / "madspec.subagents.md"
        file_path.write_text(render_fallback_guidance_file(environment_id, effective_roles), encoding="utf-8")
        created.append(str(file_path.relative_to(project_path)))
    return {"created": created, "removed": removed}
