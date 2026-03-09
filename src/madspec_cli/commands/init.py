from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import typer
from rich.live import Live
from rich.panel import Panel

from ..config import AGENT_CONFIG, SCRIPT_TYPE_CHOICES, allowed_ai_values
from ..git_ops import check_tool
from ..initializer import initialize_project
from ..ui import StepTracker, console, select_with_arrows, show_banner


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
    script_type: str = typer.Option(
        None,
        "--script",
        help="Script type to use: sh or ps",
    ),
    ignore_agent_tools: bool = typer.Option(
        False,
        "--ignore-agent-tools",
        help="Skip checks for AI agent tools",
    ),
    no_git: bool = typer.Option(
        False,
        "--no-git",
        help="Skip git repository initialization",
    ),
    here: bool = typer.Option(
        False,
        "--here",
        help="Initialize project in the current directory instead of creating a new one",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Force merge/overwrite when using --here (skip confirmation)",
    ),
    skip_tls: bool = typer.Option(
        False,
        "--skip-tls",
        help="Skip SSL/TLS verification (not recommended)",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Show verbose diagnostic output for network and extraction failures",
    ),
    github_token: str = typer.Option(
        None,
        "--github-token",
        help="GitHub token to use for API requests (or set GH_TOKEN or GITHUB_TOKEN environment variable)",
    ),
) -> None:
    """Initialize a new MADSpec project from the latest template."""
    show_banner()

    if project_name == ".":
        here = True
        project_name = None

    if here and project_name:
        console.print("[red]Error:[/red] Cannot specify both project name and --here flag")
        raise typer.Exit(1)
    if not here and not project_name:
        console.print(
            "[red]Error:[/red] Must specify either a project name, use '.' for current directory, or use --here flag"
        )
        raise typer.Exit(1)

    if here:
        project_name = Path.cwd().name
        project_path = Path.cwd()
        existing_items = list(project_path.iterdir())
        if existing_items:
            console.print(
                f"[yellow]Warning:[/yellow] Current directory is not empty ({len(existing_items)} items)"
            )
            console.print(
                "[yellow]Template files will be merged with existing content and may overwrite existing files[/yellow]"
            )
            if force:
                console.print("[cyan]--force supplied: skipping confirmation and proceeding with merge[/cyan]")
            elif not typer.confirm("Do you want to continue?"):
                console.print("[yellow]Operation cancelled[/yellow]")
                raise typer.Exit(0)
    else:
        project_path = Path(project_name).resolve()
        if project_path.exists():
            console.print()
            console.print(
                Panel(
                    f"Directory '[cyan]{project_name}[/cyan]' already exists\n"
                    "Please choose a different project name or remove the existing directory.",
                    title="[red]Directory Conflict[/red]",
                    border_style="red",
                    padding=(1, 2),
                )
            )
            raise typer.Exit(1)

    current_dir = Path.cwd()
    setup_lines = [
        "[cyan]MADSpec Project Setup[/cyan]",
        "",
        f"{'Project':<15} [green]{project_path.name}[/green]",
        f"{'Working Path':<15} [dim]{current_dir}[/dim]",
    ]
    if not here:
        setup_lines.append(f"{'Target Path':<15} [dim]{project_path}[/dim]")
    console.print(Panel("\n".join(setup_lines), border_style="cyan", padding=(1, 2)))

    should_init_git = False
    if not no_git:
        should_init_git = check_tool("git")
        if not should_init_git:
            console.print("[yellow]Git not found - will skip repository initialization[/yellow]")

    if ai_assistant:
        if ai_assistant not in AGENT_CONFIG:
            console.print(
                f"[red]Error:[/red] Invalid AI assistant '{ai_assistant}'. Choose from: {allowed_ai_values()}"
            )
            raise typer.Exit(1)
        selected_ai = ai_assistant
    else:
        ai_choices = {key: config.name for key, config in AGENT_CONFIG.items()}
        selected_ai = select_with_arrows(
            ai_choices,
            "Choose your AI assistant:",
            "cursor-agent",
        )

    if not ignore_agent_tools:
        agent_config = AGENT_CONFIG[selected_ai]
        if agent_config.requires_cli and not check_tool(selected_ai):
            console.print()
            console.print(
                Panel(
                    f"[cyan]{selected_ai}[/cyan] not found\n"
                    f"Install from: [cyan]{agent_config.install_url}[/cyan]\n"
                    f"{agent_config.name} is required to continue with this project type.\n\n"
                    "Tip: Use [cyan]--ignore-agent-tools[/cyan] to skip this check",
                    title="[red]Agent Detection Error[/red]",
                    border_style="red",
                    padding=(1, 2),
                )
            )
            raise typer.Exit(1)

    if script_type:
        if script_type not in SCRIPT_TYPE_CHOICES:
            console.print(
                f"[red]Error:[/red] Invalid script type '{script_type}'. Choose from: {', '.join(SCRIPT_TYPE_CHOICES.keys())}"
            )
            raise typer.Exit(1)
        selected_script = script_type
    else:
        default_script = "ps" if os.name == "nt" else "sh"
        if sys.stdin.isatty():
            selected_script = select_with_arrows(
                SCRIPT_TYPE_CHOICES,
                "Choose script type (or press Enter)",
                default_script,
            )
        else:
            selected_script = default_script

    console.print(f"[cyan]Selected AI assistant:[/cyan] {selected_ai}")
    console.print(f"[cyan]Selected script type:[/cyan] {selected_script}")

    tracker = StepTracker("Initialize MADSpec Project")
    for key, label, detail in (
        ("precheck", "Check required tools", "ok"),
        ("ai-select", "Select AI assistant", selected_ai),
        ("script-select", "Select script type", selected_script),
    ):
        tracker.add(key, label)
        tracker.complete(key, detail)
    for key, label in (
        ("fetch", "Fetch latest release"),
        ("download", "Download template"),
        ("extract", "Extract template"),
        ("zip-list", "Archive contents"),
        ("extracted-summary", "Extraction summary"),
        ("flatten", "Flatten nested directory"),
        ("chmod", "Ensure scripts executable"),
        ("cleanup", "Cleanup"),
        ("git", "Initialize git repository"),
        ("final", "Finalize"),
    ):
        tracker.add(key, label)

    result = None
    with Live(tracker.render(), console=console, refresh_per_second=8, transient=True) as live:
        tracker.attach_refresh(lambda: live.update(tracker.render()))
        try:
            result = initialize_project(
                project_path,
                selected_ai=selected_ai,
                selected_script=selected_script,
                here=here,
                no_git=no_git,
                should_init_git=should_init_git,
                skip_tls=skip_tls,
                debug=debug,
                github_token=github_token,
                tracker=tracker,
            )
            tracker.complete("final", "project ready")
        except Exception as exc:
            tracker.error("final", str(exc))
            console.print(Panel(f"Initialization failed: {exc}", title="Failure", border_style="red"))
            if debug:
                env_lines = [
                    f"Python   → [bright_black]{sys.version.split()[0]}[/bright_black]",
                    f"Platform → [bright_black]{sys.platform}[/bright_black]",
                    f"CWD      → [bright_black]{Path.cwd()}[/bright_black]",
                ]
                console.print(
                    Panel(
                        "\n".join(env_lines),
                        title="Debug Environment",
                        border_style="magenta",
                    )
                )
            if not here and project_path.exists():
                shutil.rmtree(project_path)
            raise typer.Exit(1)

    console.print(tracker.render())
    console.print("\n[bold green]Project ready.[/bold green]")

    if result and result.git_error_message:
        console.print()
        console.print(
            Panel(
                f"[yellow]Warning:[/yellow] Git repository initialization failed\n\n"
                f"{result.git_error_message}\n\n"
                f"[dim]You can initialize git manually later with:[/dim]\n"
                f"[cyan]cd {project_path if not here else '.'}[/cyan]\n"
                f"[cyan]git init[/cyan]\n"
                f"[cyan]git add .[/cyan]\n"
                f'[cyan]git commit -m "Initial commit"[/cyan]',
                title="[red]Git Initialization Failed[/red]",
                border_style="red",
                padding=(1, 2),
            )
        )

    agent_config = AGENT_CONFIG[selected_ai]
    console.print()
    console.print(
        Panel(
            "Some agents may store credentials, auth tokens, or other identifying and private artifacts in the agent folder within your project.\n"
            f"Consider adding [cyan]{agent_config.folder}[/cyan] (or parts of it) to [cyan].gitignore[/cyan] to prevent accidental credential leakage.",
            title="[yellow]Agent Folder Security[/yellow]",
            border_style="yellow",
            padding=(1, 2),
        )
    )

    step_num = 2
    steps_lines = []
    if not here:
        steps_lines.append(f"1. Go to the project folder: [cyan]cd {project_name}[/cyan]")
    else:
        steps_lines.append("1. You're already in the project directory!")
    steps_lines.append(f"{step_num}. Start using MADSpec commands with your AI agent:")
    steps_lines.append("")
    steps_lines.append("   [bold]MVP режим (разработка с нуля):[/bold]")
    steps_lines.append("   2.1 [cyan]/madspec.mvp.concept[/] - Create project concept")
    steps_lines.append("   2.2 [cyan]/madspec.mvp.design[/] - Design UI with prototypes")
    steps_lines.append("   2.3 [cyan]/madspec.mvp.tech[/] - Choose technology stack")
    steps_lines.append("   2.4 [cyan]/madspec.mvp.architecture[/] - Design architecture")
    steps_lines.append("   2.5 [cyan]/madspec.mvp.plan[/] - Create implementation plan")
    steps_lines.append("   2.6 [cyan]/madspec.mvp.implement[/] - Execute implementation")
    steps_lines.append("")
    steps_lines.append("   [bold]Feature режим (добавление функциональности):[/bold]")
    steps_lines.append("   2.7 [cyan]/madspec.feature.init[/] - Initialize feature work")
    steps_lines.append("   2.8 [cyan]/madspec.feature.plan[/] - Plan feature implementation")
    steps_lines.append("   2.9 [cyan]/madspec.feature.implement[/] - Implement feature")
    steps_lines.append("")
    steps_lines.append("   [bold]Общие команды:[/bold]")
    steps_lines.append(
        "   2.10 [cyan]/madspec.deploy[/] - Plan deployment (environments, CI/CD, secrets, observability)"
    )
    console.print()
    console.print(Panel("\n".join(steps_lines), title="Next Steps", border_style="cyan", padding=(1, 2)))

    console.print()
    console.print(
        Panel(
            "\n".join(
                [
                    "Optional commands for enhanced learning [bright_black](educational features)[/bright_black]",
                    "",
                    "○ [cyan]/madspec.review[/] [bright_black](optional)[/bright_black] - Review and reflect on your implementation",
                ]
            ),
            title="Learning Enhancement Commands",
            border_style="cyan",
            padding=(1, 2),
        )
    )
    console.print()
    console.print(
        Panel(
            "\n".join(
                [
                    "Quality & safety commands [bright_black](recommended)[/bright_black]",
                    "",
                    "○ [cyan]/madspec.security[/] [bright_black](optional)[/bright_black] - Security audit (OWASP/privacy/dependencies/code)",
                ]
            ),
            title="Quality & Safety Commands",
            border_style="cyan",
            padding=(1, 2),
        )
    )


def register(app: typer.Typer) -> None:
    app.command()(init)
