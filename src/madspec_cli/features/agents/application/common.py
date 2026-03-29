from __future__ import annotations

from typing import Any

from ..domain.builtin_roles import DEFAULT_PROFILE_ID, DEFAULT_SUBAGENT_IDS
from ..infrastructure.catalog_store import (
    create_profile_proposal,
    find_effective_subagent,
    list_agent_proposals,
    load_effective_subagents,
)
from ..infrastructure.state_store import build_environment_profile, load_agents_state


def find_subagent(project_path, subagent_id: str) -> dict[str, Any] | None:
    return find_effective_subagent(project_path, subagent_id)


def find_agent_proposal(project_path, proposal_id: str) -> dict[str, Any] | None:
    for item in list_agent_proposals(project_path):
        if item.get("proposalId") == proposal_id:
            return item
    return None


def default_recommendation(project_path) -> dict[str, Any]:
    state = load_agents_state(project_path)
    environment_id = state.get("environmentId")
    effective = {item["subagentId"]: item for item in load_effective_subagents(project_path, state=state)}
    recommended = []
    for subagent_id in DEFAULT_SUBAGENT_IDS:
        if subagent_id in effective:
            item = dict(effective[subagent_id])
            item["enabled"] = True
            recommended.append(item)
    return {
        "environment": build_environment_profile(environment_id),
        "profileId": state.get("profileId", DEFAULT_PROFILE_ID),
        "summary": "Рекомендуемый профиль по умолчанию включает встроенный начальный набор ролей поверх базового слоя памяти MADSpec.",
        "recommendedSubagents": recommended,
    }


def build_proposal(
    project_path,
    *,
    environment_id: str | None,
    profile_id: str,
    enabled_subagents: list[str] | None,
    requested_by: str,
) -> dict[str, Any]:
    current_state = load_agents_state(project_path)
    resolved_environment = environment_id or current_state.get("environmentId")
    effective_ids = {
        item.get("subagentId")
        for item in load_effective_subagents(project_path, state=current_state)
    }
    resolved_subagents = enabled_subagents or list(current_state.get("enabledSubagentIds") or [])
    unknown = [str(item) for item in resolved_subagents if str(item) not in effective_ids]
    if unknown:
        raise ValueError(f"unknown subagent ids in profile proposal: {', '.join(sorted(unknown))}")
    return create_profile_proposal(
        current_state=current_state,
        environment_id=resolved_environment,
        profile_id=profile_id,
        enabled_subagents=[str(item) for item in resolved_subagents],
        requested_by=requested_by,
    )
