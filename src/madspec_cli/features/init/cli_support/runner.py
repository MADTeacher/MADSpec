from __future__ import annotations

import shutil
import sys
from pathlib import Path

import typer
from rich.panel import Panel

from madspec_cli.config import AGENT_CONFIG, allowed_ai_values
from madspec_cli.shared.cli.banners import console, select_with_arrows

from ..application.contracts import (
    InitializeProjectPreflightRequest,
    InitializeProjectRequest,
    InitializeProjectResult,
)
from ..application.initialize_project import execute
from ..application.preflight import execute as preflight_init
from .memory_selection import resolve_memory_selection
from .post_init_panels import (
    print_agent_folder_security_panel,
    print_dense_memory_panel,
    print_git_warning_panel,
    print_next_steps_panel,
    print_quality_commands_panel,
    print_review_commands_panel,
)
from .progress_reporting import TrackerProgressReporter, build_init_tracker, run_with_tracker
from .project_target import ResolvedProjectTarget, print_setup_panel, resolve_project_target


def run_init_command(
    *,
    project_name: str | None,
    ai_assistant: str | None,
    ignore_agent_tools: bool,
    no_git: bool,
    here: bool,
    force: bool,
    skip_tls: bool,
    debug: bool,
    github_token: str | None,
    memory_provider: str | None,
    memory_model: str | None,
    memory_download_policy: str | None,
) -> None:
    target = resolve_project_target(project_name=project_name, here=here, force=force)
    print_setup_panel(target)

    selected_ai = ai_assistant or select_with_arrows(
        {key: config.name for key, config in AGENT_CONFIG.items()},
        "Choose your AI assistant:",
        "cursor-agent",
    )
    preflight = _run_preflight(
        selected_ai=selected_ai,
        no_git=no_git,
        ignore_agent_tools=ignore_agent_tools,
    )

    if preflight.git_warning_message:
        console.print(f"[yellow]{preflight.git_warning_message}[/yellow]")

    if preflight.missing_agent_tool:
        console.print()
        console.print(
            Panel(
                f"[cyan]{selected_ai}[/cyan] not found\n"
                f"Install from: [cyan]{preflight.agent_install_url}[/cyan]\n"
                f"{preflight.agent_display_name} is required to continue with this project type.\n\n"
                "Tip: Use [cyan]--ignore-agent-tools[/cyan] to skip this check",
                title="[red]Agent Detection Error[/red]",
                border_style="red",
                padding=(1, 2),
            )
        )
        raise typer.Exit(1)

    console.print(f"[cyan]Selected AI assistant:[/cyan] {selected_ai}")

    try:
        memory_selection = resolve_memory_selection(
            provider=memory_provider,
            model=memory_model,
            download_policy=memory_download_policy,
        )
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    tracker = build_init_tracker(selected_ai=selected_ai, memory_selection=memory_selection)
    request = InitializeProjectRequest(
        project_path=target.project_path,
        selected_ai=selected_ai,
        memory_selection=memory_selection,
        here=target.here,
        no_git=no_git,
        should_init_git=preflight.should_init_git,
        skip_tls=skip_tls,
        debug=debug,
        github_token=github_token,
        progress_reporter=TrackerProgressReporter(tracker),
    )

    result = _execute_init(request=request, tracker=tracker, debug=debug, target=target)
    if result.config_error_message:
        console.print(tracker.render())
        console.print(
            Panel(
                f"Initialization failed: {result.config_error_message}",
                title="Failure",
                border_style="red",
            )
        )
        _cleanup_failed_target(target)
        raise typer.Exit(1)

    console.print(tracker.render())
    console.print("\n[bold green]Project ready.[/bold green]")
    print_dense_memory_panel(memory_selection=memory_selection, result=result)
    print_git_warning_panel(result=result, project_path=target.project_path, here=target.here)
    print_agent_folder_security_panel(selected_ai)
    print_next_steps_panel(project_name=target.project_name, here=target.here)
    print_review_commands_panel()
    print_quality_commands_panel()


def _run_preflight(
    *,
    selected_ai: str,
    no_git: bool,
    ignore_agent_tools: bool,
):
    try:
        return preflight_init(
            InitializeProjectPreflightRequest(
                selected_ai=selected_ai,
                no_git=no_git,
                ignore_agent_tools=ignore_agent_tools,
            )
        )
    except ValueError:
        console.print(f"[red]Error:[/red] Invalid AI assistant '{selected_ai}'. Choose from: {allowed_ai_values()}")
        raise typer.Exit(1) from None


def _execute_init(
    *,
    request: InitializeProjectRequest,
    tracker,
    debug: bool,
    target: ResolvedProjectTarget,
) -> InitializeProjectResult:
    def action() -> InitializeProjectResult:
        try:
            result = execute(request)
            tracker.complete("final", "project ready")
            return result
        except Exception as exc:
            tracker.error("final", str(exc))
            console.print(Panel(f"Initialization failed: {exc}", title="Failure", border_style="red"))
            if debug:
                env_lines = [
                    f"Python   → [bright_black]{sys.version.split()[0]}[/bright_black]",
                    f"Platform → [bright_black]{sys.platform}[/bright_black]",
                    f"CWD      → [bright_black]{Path.cwd()}[/bright_black]",
                ]
                console.print(Panel("\n".join(env_lines), title="Debug Environment", border_style="magenta"))
            _cleanup_failed_target(target)
            raise typer.Exit(1) from exc

    return run_with_tracker(tracker, action)


def _cleanup_failed_target(target: ResolvedProjectTarget) -> None:
    if not target.here and target.project_path.exists():
        shutil.rmtree(target.project_path)
