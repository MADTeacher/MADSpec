from __future__ import annotations

import typer

from ...config import allowed_ai_values
from ...shared.cli.banners import show_banner
from .cli_support.memory_selection import (
    choose_memory_embeddings_interactively as _choose_memory_embeddings_interactively,
    resolve_memory_selection_from_flags as _resolve_memory_selection_from_flags,
)
from .cli_support.runner import run_init_command


def init(
    project_name: str = typer.Argument(
        None,
        help="Name for your new project directory (optional if using --here, or use '.' for current directory)",
    ),
    ai_assistant: str = typer.Option(
        None,
        "--ai",
        help=f"AI assistant to use: {allowed_ai_values()}",
    ),
    ignore_agent_tools: bool = typer.Option(False, "--ignore-agent-tools", help="Skip checks for AI agent tools"),
    no_git: bool = typer.Option(False, "--no-git", help="Skip git repository initialization"),
    here: bool = typer.Option(False, "--here", help="Initialize project in the current directory instead of creating a new one"),
    force: bool = typer.Option(False, "--force", help="Force merge/overwrite when using --here (skip confirmation)"),
    skip_tls: bool = typer.Option(False, "--skip-tls", help="Skip SSL/TLS verification (not recommended)"),
    debug: bool = typer.Option(False, "--debug", help="Show verbose diagnostic output for network and extraction failures"),
    github_token: str = typer.Option(None, "--github-token", help="GitHub token to use for API requests (or set GH_TOKEN or GITHUB_TOKEN environment variable)"),
    memory_provider: str = typer.Option(None, "--memory-provider", help="Memory embeddings provider to store in .madspec/config.json"),
    memory_model: str = typer.Option(None, "--memory-model", help="Memory embeddings model key for dense providers"),
    memory_download_policy: str = typer.Option(
        None,
        "--memory-download-policy",
        help="Memory model bootstrap policy: none, on-init, or on-first-use",
    ),
) -> None:
    """Initialize a new MADSpec project from the latest template."""
    show_banner()
    run_init_command(
        project_name=project_name,
        ai_assistant=ai_assistant,
        ignore_agent_tools=ignore_agent_tools,
        no_git=no_git,
        here=here,
        force=force,
        skip_tls=skip_tls,
        debug=debug,
        github_token=github_token,
        memory_provider=memory_provider,
        memory_model=memory_model,
        memory_download_policy=memory_download_policy,
    )


def register(app: typer.Typer) -> None:
    app.command()(init)
