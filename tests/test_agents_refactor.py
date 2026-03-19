from __future__ import annotations

import pytest

from madspec_cli.features.agents.domain.builtin_roles import DEFAULT_SUBAGENT_IDS
from madspec_cli.features.agents.domain.normalizers import (
    normalize_subagent_definition,
    validate_subagent_definition_dependencies,
)
from madspec_cli.features.agents.infrastructure.catalog_store import (
    load_agents_catalog,
    load_effective_subagents,
    save_agents_catalog,
)
from madspec_cli.features.agents.infrastructure.state_store import ensure_agents_layout, migrate_agents_state

from tests.support import write_madspec_config


def test_migrate_agents_state_legacy_subagents_to_enabled_ids() -> None:
    migrated = migrate_agents_state(
        {
            "subagents": [
                {"subagentId": "testing", "enabled": True},
                {"subagentId": "docs", "enabled": False},
                {"subagentId": "developer", "enabled": True},
                {"subagentId": "developer", "enabled": True},
            ]
        },
        environment_id="cursor-agent",
    )

    assert migrated["enabledSubagentIds"] == ["testing", "developer"]
    assert "subagents" not in migrated


def test_validate_subagent_definition_dependencies_uses_explicit_role_set() -> None:
    definition = normalize_subagent_definition(
        subagent_id="ops",
        kind="project",
        payload={
            "title": "Operations Specialist",
            "description": "Keeps operational workflows aligned.",
            "purpose": "Maintain deployment and runtime safety checks.",
            "defaultStage": "review",
            "executionModeHint": "parallel",
            "dependencies": ["architecture", "missing"],
            "toolPolicy": {"read": True, "search": True, "edit": False, "write": False, "bash": False},
            "outputContract": {"deliverable": "runbooks"},
        },
    )

    with pytest.raises(ValueError, match="missing"):
        validate_subagent_definition_dependencies(definition, existing_ids={"architecture", "developer"})


def test_load_effective_subagents_keeps_builtin_order_before_project_defined(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    write_madspec_config(project_path, agent_environment="copilot")
    state, _ = ensure_agents_layout(project_path, environment_id="copilot")
    catalog = load_agents_catalog(project_path)
    catalog["roles"].append(
        {
            "subagentId": "ops",
            "kind": "project",
            "title": "Operations Specialist",
            "description": "Owns deployment and runtime readiness.",
            "purpose": "Protect releases and operational health.",
            "defaultStage": "review",
            "executionModeHint": "parallel",
            "dependencies": ["security"],
            "toolPolicy": {"read": True, "search": True, "edit": False, "write": False, "bash": True},
            "outputContract": {"deliverable": "ops notes"},
            "bodyFile": "ops.md",
        }
    )
    save_agents_catalog(project_path, catalog)

    roles = load_effective_subagents(project_path, state=state)

    assert [item["subagentId"] for item in roles[: len(DEFAULT_SUBAGENT_IDS)]] == list(DEFAULT_SUBAGENT_IDS)
    assert roles[-1]["subagentId"] == "ops"
