from __future__ import annotations

from typing import Any

from madspec_cli.config import AGENT_CONFIG

from ..domain.frontmatter_profiles import (
    SubagentFrontmatterProfile,
    resolve_subagent_model as resolve_subagent_model_by_profile,
    subagent_frontmatter_profile_for_environment as subagent_frontmatter_profile_by_id,
)
from ..domain.tool_translation import translate_tool_policy as translate_tool_policy_by_profile


def resolve_subagent_frontmatter_profile_id(subagent_frontmatter_profile: str | None) -> str:
    if not subagent_frontmatter_profile:
        raise ValueError("No subagent frontmatter profile declared")
    if subagent_frontmatter_profile in AGENT_CONFIG:
        profile_id = AGENT_CONFIG[subagent_frontmatter_profile].subagent_frontmatter_profile
        if profile_id:
            return profile_id
    return subagent_frontmatter_profile


def subagent_frontmatter_profile_for_environment(subagent_frontmatter_profile: str | None) -> SubagentFrontmatterProfile:
    profile_id = resolve_subagent_frontmatter_profile_id(subagent_frontmatter_profile)
    return subagent_frontmatter_profile_by_id(profile_id)


def resolve_subagent_model(subagent_frontmatter_profile: str | None, role_id: str) -> str | None:
    profile_id = resolve_subagent_frontmatter_profile_id(subagent_frontmatter_profile)
    return resolve_subagent_model_by_profile(profile_id, role_id)


def translate_tool_policy(subagent_frontmatter_profile: str | None, tool_policy: dict[str, Any]) -> dict[str, bool] | list[str] | None:
    profile_id = resolve_subagent_frontmatter_profile_id(subagent_frontmatter_profile)
    return translate_tool_policy_by_profile(profile_id, tool_policy)
