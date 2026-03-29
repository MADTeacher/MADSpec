from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConfig:
    name: str
    folder: str
    commands_subdir: str
    command_extension: str
    command_arguments_placeholder: str
    install_url: str | None
    requires_cli: bool
    skills_subdir: str = "skills"
    supports_native_subagents: bool = False
    subagents_subdir: str | None = None
    subagent_extension: str | None = None
    subagent_frontmatter_profile: str | None = None
    fallback_strategy: str = "commands"
    safe_agent_frontmatter: tuple[str, ...] = ("description",)


AGENT_CONFIG: dict[str, AgentConfig] = {
    "cursor-agent": AgentConfig(
        name="Cursor",
        folder=".cursor/",
        commands_subdir="commands",
        command_extension="md",
        command_arguments_placeholder="$ARGUMENTS",
        install_url=None,
        requires_cli=False,
        supports_native_subagents=True,
        subagents_subdir="agents",
        subagent_extension="md",
        subagent_frontmatter_profile="cursor-subagent-v1",
        fallback_strategy="native-subagents",
        safe_agent_frontmatter=("description",),
    ),
    "opencode": AgentConfig(
        name="opencode",
        folder=".opencode/",
        commands_subdir="commands",
        command_extension="md",
        command_arguments_placeholder="$ARGUMENTS",
        install_url="https://opencode.ai",
        requires_cli=True,
        supports_native_subagents=True,
        subagents_subdir="agents",
        subagent_extension="md",
        subagent_frontmatter_profile="opencode-subagent-v1",
        fallback_strategy="native-subagents",
        safe_agent_frontmatter=("description", "mode", "model", "temperature", "tools"),
    ),
    "kilocode": AgentConfig(
        name="Kilo Code",
        folder=".kilocode/",
        commands_subdir="rules",
        command_extension="md",
        command_arguments_placeholder="$ARGUMENTS",
        install_url=None,
        requires_cli=False,
        fallback_strategy="rules",
    ),
    "roo": AgentConfig(
        name="Roo Code",
        folder=".roo/",
        commands_subdir="rules",
        command_extension="md",
        command_arguments_placeholder="$ARGUMENTS",
        install_url=None,
        requires_cli=False,
        fallback_strategy="rules",
    ),
    "sourcecraft": AgentConfig(
        name="SourceCraft",
        folder=".codeassistant/",
        commands_subdir="commands",
        command_extension="md",
        command_arguments_placeholder="$ARGUMENTS",
        install_url=None,
        requires_cli=False,
        fallback_strategy="commands",
    ),
    "qwen": AgentConfig(
        name="Qwen Code",
        folder=".qwen/",
        commands_subdir="commands",
        command_extension="md",
        command_arguments_placeholder="{{args}}",
        install_url="https://github.com/QwenLM/qwen-code",
        requires_cli=True,
        supports_native_subagents=True,
        subagents_subdir="agents",
        subagent_extension="md",
        subagent_frontmatter_profile="qwen-subagent-v1",
        fallback_strategy="native-subagents",
        safe_agent_frontmatter=("description", "tools"),
    ),
    "copilot": AgentConfig(
        name="GitHub Copilot",
        folder=".github/",
        commands_subdir="agents",
        command_extension="agent.md",
        command_arguments_placeholder="$ARGUMENTS",
        install_url=None,
        requires_cli=False,
        supports_native_subagents=True,
        subagents_subdir="agents",
        subagent_extension="agent.md",
        subagent_frontmatter_profile="copilot-subagent-v1",
        fallback_strategy="native-subagents",
        safe_agent_frontmatter=("name", "description", "tools", "model", "target"),
    ),
}


MADSPEC_CONFIG_VERSION = "1.0.0"
MADSPEC_AGENTS_SCHEMA_VERSION = 1
DEFAULT_PARALLEL_RUNTIME_POLICY = {
    "phase1Enabled": True,
    "phase2Enabled": True,
}


def allowed_ai_values() -> str:
    return ", ".join(AGENT_CONFIG.keys())
