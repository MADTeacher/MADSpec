from __future__ import annotations

from madspec_cli.config import AGENT_CONFIG

from ..domain.builtin_roles import role_catalog as builtin_role_catalog


def role_catalog(
    *, environment_id: str | None = None, supports_native_subagents: bool | None = None
) -> list[dict[str, object]]:
    resolved_supports_native_subagents = supports_native_subagents
    if environment_id is not None:
        try:
            environment_supports_native_subagents = AGENT_CONFIG[environment_id].supports_native_subagents
        except KeyError as exc:
            raise ValueError(f"Unknown agent environment: {environment_id}") from exc
        if resolved_supports_native_subagents not in (None, environment_supports_native_subagents):
            raise ValueError("Conflicting role_catalog arguments: environment_id and supports_native_subagents disagree")
        resolved_supports_native_subagents = environment_supports_native_subagents
    if resolved_supports_native_subagents is None:
        raise ValueError("role_catalog requires environment_id or supports_native_subagents")
    return builtin_role_catalog(supports_native_subagents=resolved_supports_native_subagents)
