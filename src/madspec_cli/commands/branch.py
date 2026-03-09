from __future__ import annotations

import json
from pathlib import Path

import typer

from ..git_ops import get_current_branch
from ..memory import consolidate_branch_memory, ensure_memory_layout
from ..project_state import create_madspec_config, ensure_branch_dir
from ..ui import console, show_banner


def branch(
    action: str = typer.Argument(..., help="Action: get, set, or list"),
    branch_name: str = typer.Argument(None, help="Branch name (required for 'set' action)"),
) -> None:
    """Manage MADSpec branch configuration."""
    show_banner()
    project_path = Path.cwd()
    config_file = project_path / ".madspec" / "config.json"

    if action == "get":
        current_branch = get_current_branch(project_path)
        console.print(f"[green]Current branch:[/green] {current_branch}")
        if config_file.exists():
            config = json.loads(config_file.read_text(encoding="utf-8"))
            if "currentBranch" in config:
                console.print(f"[dim]Configured in .madspec/config.json:[/dim] {config['currentBranch']}")
        return

    if action == "set":
        if not branch_name:
            console.print("[red]Error:[/red] Branch name is required for 'set' action")
            raise typer.Exit(1)
        create_madspec_config(project_path, branch_name)
        ensure_branch_dir(project_path, branch_name)
        ensure_memory_layout(project_path, branch_name)
        consolidate_branch_memory(project_path, branch_name)
        console.print(f"[green]Branch set to:[/green] {branch_name}")
        console.print(f"[dim]Branch directory created:[/dim] .madspec/{branch_name}/")
        return

    if action == "list":
        madspec_dir = project_path / ".madspec"
        if not madspec_dir.exists():
            console.print("[yellow]No .madspec directory found[/yellow]")
            return

        branches = []
        for item in madspec_dir.iterdir():
            if item.is_dir() and item.name not in ["templates", "scripts"]:
                branches.append(item.name)

        if branches:
            console.print("[cyan]Branches with artifacts:[/cyan]")
            for branch_name in sorted(branches):
                branch_dir = madspec_dir / branch_name
                artifact_count = sum(1 for item in branch_dir.rglob("*") if item.is_file())
                console.print(f"  • {branch_name} ({artifact_count} files)")
        else:
            console.print("[yellow]No branches with artifacts found[/yellow]")
        return

    console.print(f"[red]Error:[/red] Unknown action '{action}'. Use: get, set, or list")
    raise typer.Exit(1)


def register(app: typer.Typer) -> None:
    app.command()(branch)
