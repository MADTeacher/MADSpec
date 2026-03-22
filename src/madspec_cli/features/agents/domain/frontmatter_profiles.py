from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SubagentFrontmatterProfile:
    profile_id: str
    include_name: bool = False
    include_description: bool = True
    static_fields: tuple[tuple[str, Any], ...] = ()
    model_strategy: str = "inherit"
    model_field: str | None = None
    tools_field: str | None = None
    tool_translator_id: str | None = None
    include_execution_mode_hint: bool = False
    include_dependencies: bool = False
    role_models: dict[str, str] = field(default_factory=dict)


SUBAGENT_FRONTMATTER_PROFILES = {
    "cursor-subagent-v1": SubagentFrontmatterProfile(
        profile_id="cursor-subagent-v1",
        include_description=True,
        include_execution_mode_hint=True,
        include_dependencies=True,
    ),
    "opencode-subagent-v1": SubagentFrontmatterProfile(
        profile_id="opencode-subagent-v1",
        include_name=True,
        include_description=True,
        static_fields=(("mode", "subagent"), ("hidden", True)),
        model_strategy="inherit",
        model_field="model",
        tools_field="tools",
        tool_translator_id="opencode-tools-v1",
    ),
    "qwen-subagent-v1": SubagentFrontmatterProfile(
        profile_id="qwen-subagent-v1",
        include_name=True,
        include_description=True,
        model_strategy="inherit",
        tools_field="tools",
        tool_translator_id="qwen-tools-v1",
    ),
    "copilot-subagent-v1": SubagentFrontmatterProfile(
        profile_id="copilot-subagent-v1",
        include_name=True,
        include_description=True,
        static_fields=(("target", "vscode"), ("user-invocable", False)),
        model_strategy="inherit",
        model_field="model",
        tools_field="tools",
        tool_translator_id="copilot-tools-v1",
    ),
}


def subagent_frontmatter_profile_for_environment(subagent_frontmatter_profile: str | None) -> SubagentFrontmatterProfile:
    if not subagent_frontmatter_profile:
        raise ValueError("No subagent frontmatter profile declared")
    try:
        return SUBAGENT_FRONTMATTER_PROFILES[subagent_frontmatter_profile]
    except KeyError as exc:
        raise ValueError(f"Unknown subagent frontmatter profile: {subagent_frontmatter_profile}") from exc


def resolve_subagent_model(subagent_frontmatter_profile: str | None, role_id: str) -> str | None:
    profile = subagent_frontmatter_profile_for_environment(subagent_frontmatter_profile)
    if profile.model_field is None:
        return None
    return profile.role_models.get(role_id)
