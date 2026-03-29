from __future__ import annotations

import pytest

from madspec_cli.features.agents.infrastructure.frontmatter_profile_compat import translate_tool_policy
from madspec_cli.features.agents.infrastructure.render_workspace import render_native_subagent_file
from madspec_cli.features.agents.infrastructure.role_catalog_compat import role_catalog
from madspec_cli.features.agents.infrastructure.state_store import build_environment_profile


def _role(environment_id: str, subagent_id: str) -> dict[str, object]:
    return next(item for item in role_catalog(environment_id=environment_id) if item["subagentId"] == subagent_id)


def _frontmatter_block(text: str) -> str:
    assert text.startswith("---\n")
    frontmatter, separator, _body = text[4:].partition("\n---\n")
    assert separator == "\n---\n"
    return frontmatter


def test_environment_profile_exposes_explicit_frontmatter_profile() -> None:
    profile = build_environment_profile("copilot")

    assert profile["subagentFrontmatterProfile"] == {
        "profileId": "copilot-subagent-v1",
        "modelStrategy": "inherit",
        "modelField": "model",
        "toolsField": "tools",
        "toolTranslatorId": "copilot-tools-v1",
        "supportsExecutionModeHint": False,
        "supportsDependencies": False,
    }


def test_cursor_frontmatter_stays_minimal_and_role_specific() -> None:
    frontmatter = _frontmatter_block(render_native_subagent_file("cursor-agent", _role("cursor-agent", "testing")))

    assert frontmatter.splitlines() == [
        "description: Сосредоточен на пробелах в покрытии, проектировании тестов, стратегии проверки и подтверждении реализации.",
        "execution_mode_hint: parallel",
        'dependencies: ["architecture"]',
    ]


def test_opencode_frontmatter_uses_native_profile_and_strict_tool_map() -> None:
    frontmatter = _frontmatter_block(render_native_subagent_file("opencode", _role("opencode", "security")))

    assert frontmatter.splitlines() == [
        "name: Специалист по безопасности",
        "description: Проверяет безопасность, приватность, поверхность атаки, риски зависимостей и защитные меры.",
        "mode: subagent",
        "hidden: true",
        "tools:",
        "  edit: false",
        "  write: false",
        "  bash: true",
    ]


def test_qwen_frontmatter_uses_qwen_tool_names() -> None:
    frontmatter = _frontmatter_block(render_native_subagent_file("qwen", _role("qwen", "testing")))

    assert frontmatter.splitlines() == [
        "name: Специалист по тестированию",
        "description: Сосредоточен на пробелах в покрытии, проектировании тестов, стратегии проверки и подтверждении реализации.",
        'tools: ["read_file", "glob", "grep_search", "edit", "write_file", "run_shell_command"]',
    ]


def test_copilot_frontmatter_uses_copilot_specific_tool_names() -> None:
    frontmatter = _frontmatter_block(render_native_subagent_file("copilot", _role("copilot", "testing")))

    assert frontmatter.splitlines() == [
        "name: Специалист по тестированию",
        "description: Сосредоточен на пробелах в покрытии, проектировании тестов, стратегии проверки и подтверждении реализации.",
        "target: vscode",
        "user-invocable: false",
        'tools: ["read", "search", "edit", "terminal"]',
    ]


def test_copilot_frontmatter_for_developer_exposes_full_implementation_tools() -> None:
    frontmatter = _frontmatter_block(render_native_subagent_file("copilot", _role("copilot", "developer")))

    assert frontmatter.splitlines() == [
        "name: Специалист по разработке",
        "description: Реализует запланированные изменения в коде, встраивает решения и подтверждает шаги разработки в текущем репозитории.",
        "target: vscode",
        "user-invocable: false",
        'tools: ["read", "search", "edit", "terminal"]',
    ]


def test_tool_policy_translation_is_strict_about_unknown_keys() -> None:
    with pytest.raises(ValueError, match="Unsupported tool policy keys"):
        translate_tool_policy("copilot", {"read": True, "search": True, "deploy": True})


def test_role_catalog_accepts_supports_native_subagents_flag() -> None:
    native_roles = role_catalog(supports_native_subagents=True)
    fallback_roles = role_catalog(supports_native_subagents=False)

    assert native_roles[0]["renderMode"] == "native"
    assert fallback_roles[0]["renderMode"] == "fallback"


def test_role_catalog_rejects_conflicting_arguments() -> None:
    with pytest.raises(ValueError, match="Conflicting role_catalog arguments"):
        role_catalog(environment_id="cursor-agent", supports_native_subagents=False)


def test_qwen_tool_translation_returns_environment_specific_tools() -> None:
    translated = translate_tool_policy(
        "qwen",
        {"read": True, "search": True, "edit": False, "write": False, "bash": True},
    )

    assert translated == ["read_file", "glob", "grep_search", "run_shell_command"]


def test_tool_policy_translation_accepts_profile_id_directly() -> None:
    translated = translate_tool_policy(
        "copilot-subagent-v1",
        {"read": True, "search": True, "edit": True, "write": False, "bash": True},
    )

    assert translated == ["read", "search", "edit", "terminal"]


def test_tool_policy_translation_rejects_unknown_profile_or_environment() -> None:
    with pytest.raises(ValueError, match="Unknown subagent frontmatter profile"):
        translate_tool_policy("missing-environment", {"read": True})
