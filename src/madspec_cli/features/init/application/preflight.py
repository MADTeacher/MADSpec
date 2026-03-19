from __future__ import annotations

from madspec_cli.config import AGENT_CONFIG, allowed_ai_values
from madspec_cli.shared.infra.system_tools import check_tool

from .contracts import InitializeProjectPreflightRequest, InitializeProjectPreflightResult


def execute(request: InitializeProjectPreflightRequest) -> InitializeProjectPreflightResult:
    if request.selected_ai not in AGENT_CONFIG:
        raise ValueError(
            f"Invalid AI assistant '{request.selected_ai}'. Choose from: {allowed_ai_values()}"
        )

    agent_config = AGENT_CONFIG[request.selected_ai]
    git_available = check_tool("git")
    should_init_git = False if request.no_git else git_available
    git_warning_message = None
    if not request.no_git and not git_available:
        git_warning_message = "Git not found - will skip repository initialization"

    missing_agent_tool = False
    if not request.ignore_agent_tools and agent_config.requires_cli:
        missing_agent_tool = not check_tool(request.selected_ai)

    return InitializeProjectPreflightResult(
        selected_ai=request.selected_ai,
        should_init_git=should_init_git,
        git_warning_message=git_warning_message,
        missing_agent_tool=missing_agent_tool,
        agent_install_url=agent_config.install_url,
        agent_display_name=agent_config.name,
    )
