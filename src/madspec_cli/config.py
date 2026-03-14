from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConfig:
    name: str
    folder: str
    commands_subdir: str
    install_url: str | None
    requires_cli: bool


AGENT_CONFIG: dict[str, AgentConfig] = {
    "cursor-agent": AgentConfig(
        name="Cursor",
        folder=".cursor/",
        commands_subdir="commands",
        install_url=None,
        requires_cli=False,
    ),
    "opencode": AgentConfig(
        name="opencode",
        folder=".opencode/",
        commands_subdir="command",
        install_url="https://opencode.ai",
        requires_cli=True,
    ),
    "kilocode": AgentConfig(
        name="Kilo Code",
        folder=".kilocode/",
        commands_subdir="rules",
        install_url=None,
        requires_cli=False,
    ),
    "roo": AgentConfig(
        name="Roo Code",
        folder=".roo/",
        commands_subdir="rules",
        install_url=None,
        requires_cli=False,
    ),
    "sourcecraft": AgentConfig(
        name="SourceCraft",
        folder=".codeassistant/",
        commands_subdir="commands",
        install_url=None,
        requires_cli=False,
    ),
    "qwen": AgentConfig(
        name="Qwen Code",
        folder=".qwen/",
        commands_subdir="commands",
        install_url="https://github.com/QwenLM/qwen-code",
        requires_cli=True,
    ),
    "copilot": AgentConfig(
        name="GitHub Copilot",
        folder=".github/",
        commands_subdir="agents",
        install_url=None,
        requires_cli=False,
    ),
}


def allowed_ai_values() -> str:
    return ", ".join(AGENT_CONFIG.keys())
