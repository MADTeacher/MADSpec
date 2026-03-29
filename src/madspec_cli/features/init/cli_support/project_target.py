from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import typer
from rich.panel import Panel

from madspec_cli.shared.cli.banners import console


@dataclass(frozen=True)
class ResolvedProjectTarget:
    project_name: str
    project_path: Path
    here: bool


def resolve_project_target(
    *,
    project_name: str | None,
    here: bool,
    force: bool,
) -> ResolvedProjectTarget:
    if project_name == ".":
        here = True
        project_name = None

    if here and project_name:
        console.print("[red]Error:[/red] Cannot specify both project name and --here flag")
        raise typer.Exit(1)
    if not here and not project_name:
        console.print("[red]Error:[/red] Must specify either a project name, use '.' for current directory, or use --here flag")
        raise typer.Exit(1)

    if here:
        resolved_name = Path.cwd().name
        project_path = Path.cwd()
        existing_items = list(project_path.iterdir())
        if existing_items:
            console.print(f"[yellow]Warning:[/yellow] Current directory is not empty ({len(existing_items)} items)")
            console.print("[yellow]Template files will be merged with existing content and may overwrite existing files[/yellow]")
            if force:
                console.print("[cyan]--force supplied: skipping confirmation and proceeding with merge[/cyan]")
            elif not typer.confirm("Do you want to continue?"):
                console.print("[yellow]Operation cancelled[/yellow]")
                raise typer.Exit(0)
        return ResolvedProjectTarget(project_name=resolved_name, project_path=project_path, here=True)

    assert project_name is not None
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
    return ResolvedProjectTarget(project_name=project_name, project_path=project_path, here=False)


def print_setup_panel(target: ResolvedProjectTarget) -> None:
    current_dir = Path.cwd()
    setup_lines = [
        "[cyan]MADSpec Project Setup[/cyan]",
        "",
        f"{'Project':<15} [green]{target.project_path.name}[/green]",
        f"{'Working Path':<15} [dim]{current_dir}[/dim]",
    ]
    if not target.here:
        setup_lines.append(f"{'Target Path':<15} [dim]{target.project_path}[/dim]")
    console.print(Panel("\n".join(setup_lines), border_style="cyan", padding=(1, 2)))
