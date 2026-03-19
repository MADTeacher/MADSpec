from __future__ import annotations

from typing import Any

from madspec_cli.config import AGENT_CONFIG


DEFAULT_PROFILE_ID = "default"
DEFAULT_SUBAGENT_IDS = (
    "architecture",
    "developer",
    "contracts-data",
    "testing",
    "security",
    "research",
    "docs",
)
ROLE_METADATA_FIELDS = (
    "title",
    "description",
    "purpose",
    "defaultStage",
    "executionModeHint",
    "dependencies",
    "toolPolicy",
    "outputContract",
)

_ROLE_TITLES = {
    "architecture": "Architecture Specialist",
    "developer": "Developer Specialist",
    "contracts-data": "Contracts & Data Specialist",
    "testing": "Testing Specialist",
    "security": "Security Specialist",
    "research": "Research Specialist",
    "docs": "Documentation Specialist",
}

_ROLE_DESCRIPTIONS = {
    "architecture": "Designs architecture, boundaries, contracts, and tradeoffs for the current product and repository.",
    "developer": "Implements planned code changes, integrates solutions, and validates development steps in the current repository.",
    "contracts-data": "Owns API contracts, data structures, schema boundaries, and integration-facing data consistency.",
    "testing": "Focuses on coverage gaps, test design, validation strategy, and implementation verification.",
    "security": "Reviews security, privacy, threat surface, dependency risk, and defensive controls.",
    "research": "Explores repository context, unknowns, and supporting evidence for the current product and codebase.",
    "docs": "Maintains technical and workflow documentation so it stays aligned with the current repository and generated artifacts.",
}

_ROLE_PURPOSES = {
    "architecture": "Produce architecture-level decisions and constraints that fit the current product, repository, and project rules.",
    "developer": "Implement agreed changes in code and tests without drifting from the current step, plan, or project constraints.",
    "contracts-data": "Keep contracts, schemas, entities, and integration data models internally consistent and implementation-ready.",
    "testing": "Improve confidence through actionable test plans, new tests, and verification notes.",
    "security": "Identify meaningful security and privacy risks and suggest practical mitigations.",
    "research": "Gather context, compare options, and summarize findings to unblock downstream work.",
    "docs": "Keep user-facing and developer-facing documentation synchronized with the real workflow, codebase, and generated outputs.",
}

_ROLE_DEFAULT_STAGES = {
    "architecture": "mvp.architecture",
    "developer": "feature.implement",
    "contracts-data": "mvp.architecture",
    "testing": "feature.implement",
    "security": "security",
    "research": "feature.plan",
    "docs": "review",
}

_ROLE_EXECUTION_HINTS = {
    "architecture": "sequential",
    "developer": "parallel",
    "contracts-data": "sequential",
    "testing": "parallel",
    "security": "parallel",
    "research": "parallel",
    "docs": "parallel",
}

_ROLE_DEPENDENCIES = {
    "architecture": [],
    "developer": ["architecture"],
    "contracts-data": ["architecture"],
    "testing": ["architecture"],
    "security": [],
    "research": [],
    "docs": [],
}

_ROLE_TOOL_POLICY = {
    "architecture": {"read": True, "search": True, "edit": False, "write": False, "bash": False},
    "developer": {"read": True, "search": True, "edit": True, "write": True, "bash": True},
    "contracts-data": {"read": True, "search": True, "edit": False, "write": False, "bash": False},
    "testing": {"read": True, "search": True, "edit": True, "write": True, "bash": True},
    "security": {"read": True, "search": True, "edit": False, "write": False, "bash": True},
    "research": {"read": True, "search": True, "edit": False, "write": False, "bash": False},
    "docs": {"read": True, "search": True, "edit": True, "write": True, "bash": False},
}

_ROLE_OUTPUT_CONTRACT = {
    "architecture": {"deliverable": "decisions, constraints, interfaces", "writeBack": "through canonical CLI only"},
    "developer": {"deliverable": "code changes, tests, validation notes", "writeBack": "through canonical CLI only"},
    "contracts-data": {"deliverable": "contracts, schemas, entity decisions", "writeBack": "through canonical CLI only"},
    "testing": {"deliverable": "tests, validation notes, coverage recommendations", "writeBack": "through canonical CLI only"},
    "security": {"deliverable": "risks, mitigations, priority guidance", "writeBack": "through canonical CLI only"},
    "research": {"deliverable": "findings, options, evidence", "writeBack": "through canonical CLI only"},
    "docs": {"deliverable": "documentation updates, drift findings, clarification notes", "writeBack": "through canonical CLI only"},
}


def role_catalog(*, environment_id: str) -> list[dict[str, Any]]:
    config = AGENT_CONFIG[environment_id]
    render_mode = "native" if config.supports_native_subagents else "fallback"
    return [
        {
            "subagentId": role_id,
            "title": _ROLE_TITLES[role_id],
            "description": _ROLE_DESCRIPTIONS[role_id],
            "purpose": _ROLE_PURPOSES[role_id],
            "defaultStage": _ROLE_DEFAULT_STAGES[role_id],
            "executionModeHint": _ROLE_EXECUTION_HINTS[role_id],
            "dependencies": list(_ROLE_DEPENDENCIES[role_id]),
            "toolPolicy": dict(_ROLE_TOOL_POLICY[role_id]),
            "outputContract": dict(_ROLE_OUTPUT_CONTRACT[role_id]),
            "origin": "builtin",
            "bodySource": f"template:{role_id}",
            "enabled": role_id in DEFAULT_SUBAGENT_IDS,
            "renderMode": render_mode,
        }
        for role_id in DEFAULT_SUBAGENT_IDS
    ]
