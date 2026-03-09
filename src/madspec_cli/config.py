from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConfig:
    name: str
    folder: str
    install_url: str | None
    requires_cli: bool


AGENT_CONFIG: dict[str, AgentConfig] = {
    "cursor-agent": AgentConfig(
        name="Cursor",
        folder=".cursor/",
        install_url=None,
        requires_cli=False,
    ),
    "opencode": AgentConfig(
        name="opencode",
        folder=".opencode/",
        install_url="https://opencode.ai",
        requires_cli=True,
    ),
    "kilocode": AgentConfig(
        name="Kilo Code",
        folder=".kilocode/",
        install_url=None,
        requires_cli=False,
    ),
    "roo": AgentConfig(
        name="Roo Code",
        folder=".roo/",
        install_url=None,
        requires_cli=False,
    ),
    "sourcecraft": AgentConfig(
        name="SourceCraft",
        folder=".codeassistant/",
        install_url=None,
        requires_cli=False,
    ),
    "copilot": AgentConfig(
        name="GitHub Copilot",
        folder=".github/",
        install_url=None,
        requires_cli=False,
    ),
}

SCRIPT_TYPE_CHOICES = {"sh": "POSIX Shell (bash/zsh)", "ps": "PowerShell"}


def allowed_ai_values() -> str:
    return ", ".join(AGENT_CONFIG.keys())
