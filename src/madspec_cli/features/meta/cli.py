from __future__ import annotations

from pathlib import Path

import typer
from rich.panel import Panel
from rich.table import Table

from madspec_cli.shared.cli.banners import StepTracker, console, show_banner

from .application.check_tools import execute as check_tools_use_case
from .application.migrate_meta import (
    ApplyMigrationRequest,
    PrepareMigrationRequest,
    execute as apply_migration_use_case,
    prepare as prepare_migration_use_case,
)
from .application.version_info import execute as version_info_use_case


def migrate() -> None:
    """Migrate existing project from .madspec/ to .madspec/<branch>/ structure."""
    show_banner()
    payload = prepare_migration_use_case(PrepareMigrationRequest(project_path=Path.cwd())).to_payload()
    if payload["status"] == "missing":
        console.print("[yellow]No .madspec directory found. Nothing to migrate.[/yellow]")
        return
    if payload["status"] == "noop":
        console.print(f"[green]No migration needed. Artifacts already in .madspec/{payload['target_branch']}/[/green]")
        return

    console.print(f"[cyan]Found {payload['artifact_count']} items in .madspec/ root[/cyan]")
    console.print(f"[cyan]Will migrate to: .madspec/{payload['target_branch']}/[/cyan]")
    if not typer.confirm("Do you want to proceed with migration?"):
        console.print("[yellow]Migration cancelled[/yellow]")
        return

    result = apply_migration_use_case(ApplyMigrationRequest(project_path=Path.cwd())).to_payload()
    for item in result["skipped"]:
        console.print(f"[yellow]Skipping {item} (already exists in target)[/yellow]")
    for error in result["errors"]:
        console.print(f"[red]Error moving {error['name']}: {error['message']}[/red]")
    console.print(
        f"[green]Migration complete:[/green] {result['moved_count']} items moved to .madspec/{result['target_branch']}/"
    )
    console.print("[dim]Config updated:[/dim] .madspec/config.json")


def check() -> None:
    """Check that all required tools are installed."""
    show_banner()
    console.print("[bold]Checking for installed tools...[/bold]\n")
    tracker = StepTracker("Check Available Tools")
    payload = check_tools_use_case().to_payload()
    for item in payload["items"]:
        tracker.add(item["id"], item["label"])
        if item["skipped"]:
            tracker.skip(item["id"], item["reason"])
        elif item["available"]:
            tracker.complete(item["id"], "available")
        else:
            tracker.error(item["id"], "not found")

    console.print(tracker.render())
    console.print("\n[bold green]MADSpec CLI is ready to use![/bold green]")
    if not payload["git_ok"]:
        console.print("[dim]Tip: Install git for repository management[/dim]")
    if not any(payload["agent_results"].values()):
        console.print("[dim]Tip: Install an AI assistant for the best experience[/dim]")
    _ = (payload["code_ok"], payload["code_insiders_ok"])


def version() -> None:
    """Display version and system information."""
    show_banner()
    info = version_info_use_case().to_payload()

    info_table = Table(show_header=False, box=None, padding=(0, 2))
    info_table.add_column("Key", style="cyan", justify="right")
    info_table.add_column("Value", style="white")
    info_table.add_row("CLI Version", info["cli_version"])
    info_table.add_row("Template Version", info["template_version"])
    info_table.add_row("Released", info["release_date"])
    info_table.add_row("", "")
    info_table.add_row("Python", info["python"])
    info_table.add_row("Platform", info["platform"])
    info_table.add_row("Architecture", info["architecture"])
    info_table.add_row("OS Version", info["os_version"])
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
