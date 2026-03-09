from __future__ import annotations

import importlib.metadata
import platform
import tomllib
from pathlib import Path

import typer
from rich.panel import Panel
from rich.table import Table

from ..config import AGENT_CONFIG
from ..github_api import create_http_client, fetch_latest_release_info
from ..git_ops import check_tool, get_current_branch
from ..memory import consolidate_branch_memory, ensure_memory_layout
from ..project_state import create_madspec_config, ensure_branch_dir
from ..ui import StepTracker, console, show_banner


def migrate() -> None:
    """Migrate existing project from .madspec/ to .madspec/<branch>/ structure."""
    show_banner()
    project_path = Path.cwd()
    madspec_dir = project_path / ".madspec"
    if not madspec_dir.exists():
        console.print("[yellow]No .madspec directory found. Nothing to migrate.[/yellow]")
        return

    target_branch = get_current_branch(project_path)
    exclude_dirs = {"templates", "scripts", target_branch}
    artifacts_in_root = [
        item
        for item in madspec_dir.iterdir()
        if item.is_file() or (item.is_dir() and item.name not in exclude_dirs)
    ]
    if not artifacts_in_root:
        console.print(f"[green]No migration needed. Artifacts already in .madspec/{target_branch}/[/green]")
        return

    console.print(f"[cyan]Found {len(artifacts_in_root)} items in .madspec/ root[/cyan]")
    console.print(f"[cyan]Will migrate to: .madspec/{target_branch}/[/cyan]")
    if not typer.confirm("Do you want to proceed with migration?"):
        console.print("[yellow]Migration cancelled[/yellow]")
        return

    target_dir = ensure_branch_dir(project_path, target_branch)
    moved_count = 0
    for item in artifacts_in_root:
        try:
            target_path = target_dir / item.name
            if target_path.exists():
                console.print(f"[yellow]Skipping {item.name} (already exists in target)[/yellow]")
                continue
            item.rename(target_path)
            moved_count += 1
        except Exception as exc:
            console.print(f"[red]Error moving {item.name}: {exc}[/red]")

    create_madspec_config(project_path, target_branch)
    ensure_memory_layout(project_path, target_branch)
    consolidate_branch_memory(project_path, target_branch)
    console.print(f"[green]Migration complete:[/green] {moved_count} items moved to .madspec/{target_branch}/")
    console.print("[dim]Config updated:[/dim] .madspec/config.json")


def check() -> None:
    """Check that all required tools are installed."""
    show_banner()
    console.print("[bold]Checking for installed tools...[/bold]\n")
    tracker = StepTracker("Check Available Tools")

    tracker.add("git", "Git version control")
    git_ok = check_tool("git", tracker=tracker)

    agent_results = {}
    for agent_key, agent_config in AGENT_CONFIG.items():
        tracker.add(agent_key, agent_config.name)
        if agent_config.requires_cli:
            agent_results[agent_key] = check_tool(agent_key, tracker=tracker)
        else:
            tracker.skip(agent_key, "IDE-based, no CLI check")
            agent_results[agent_key] = False

    tracker.add("code", "Visual Studio Code")
    code_ok = check_tool("code", tracker=tracker)

    tracker.add("code-insiders", "Visual Studio Code Insiders")
    code_insiders_ok = check_tool("code-insiders", tracker=tracker)

    console.print(tracker.render())
    console.print("\n[bold green]MADSpec CLI is ready to use![/bold green]")
    if not git_ok:
        console.print("[dim]Tip: Install git for repository management[/dim]")
    if not any(agent_results.values()):
        console.print("[dim]Tip: Install an AI assistant for the best experience[/dim]")
    _ = (code_ok, code_insiders_ok)


def version() -> None:
    """Display version and system information."""
    show_banner()

    cli_version = "unknown"
    try:
        cli_version = importlib.metadata.version("madspec-cli")
    except Exception:
        pyproject_path = Path(__file__).parent.parent.parent.parent / "pyproject.toml"
        if pyproject_path.exists():
            data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
            cli_version = data.get("project", {}).get("version", "unknown")

    template_version = "unknown"
    release_date = "unknown"
    try:
        release_data = fetch_latest_release_info(
            "MADTeacher",
            "madspec",
            client=create_http_client(),
        )
        template_version = release_data.get("tag_name", "unknown")
        if template_version.startswith("v"):
            template_version = template_version[1:]
        release_date = release_data.get("published_at", "unknown")
        if release_date != "unknown":
            release_date = release_date.split("T", 1)[0]
    except Exception:
        pass

    info_table = Table(show_header=False, box=None, padding=(0, 2))
    info_table.add_column("Key", style="cyan", justify="right")
    info_table.add_column("Value", style="white")
    info_table.add_row("CLI Version", cli_version)
    info_table.add_row("Template Version", template_version)
    info_table.add_row("Released", release_date)
    info_table.add_row("", "")
    info_table.add_row("Python", platform.python_version())
    info_table.add_row("Platform", platform.system())
    info_table.add_row("Architecture", platform.machine())
    info_table.add_row("OS Version", platform.version())
    console.print(
        Panel(
            info_table,
            title="[bold cyan]MADSpec CLI Information[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )
    console.print()


def register(app: typer.Typer) -> None:
    app.command()(migrate)
    app.command()(check)
    app.command()(version)
