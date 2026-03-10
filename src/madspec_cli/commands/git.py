from __future__ import annotations

import json
from pathlib import Path

import typer

from ..git_ops import (
    GitOperationError,
    commit_all,
    create_branch,
    ensure_gitignore,
    get_current_branch_info,
    init_repo,
    list_madspec_branches,
    set_branch_config,
)
from ..ui import console, show_banner

git_app = typer.Typer(help="Git and branch management for MADSpec projects")


def _print_payload(payload: dict[str, object], json_output: bool) -> None:
    if json_output:
        console.print_json(json.dumps(payload, ensure_ascii=False))


def _emit_result(result, json_output: bool) -> None:
    payload = result.as_dict()
    _print_payload(payload, json_output)


def _emit_error(exc: Exception, json_output: bool) -> None:
    if json_output:
        console.print_json(json.dumps({"error": str(exc)}, ensure_ascii=False))
    else:
        show_banner()
        console.print(f"[red]Error:[/red] {exc}")


@git_app.command("current-branch")
def current_branch(
    json_output: bool = typer.Option(False, "--json-output", help="Emit JSON payload"),
) -> None:
    """Return the active git branch with MADSpec fallback."""
    info = get_current_branch_info(Path.cwd())
    if json_output:
        _emit_result(info, json_output=True)
        return
    show_banner()
    console.print(f"[green]Current branch:[/green] {info.branch}")
    console.print(f"[dim]Source:[/dim] {info.source}")


@git_app.command("list-branches")
def list_branches(
    json_output: bool = typer.Option(False, "--json-output", help="Emit JSON payload"),
) -> None:
    """List branches that already have MADSpec artifacts."""
    result = list_madspec_branches(Path.cwd())
    if json_output:
        _emit_result(result, json_output=True)
        return
    show_banner()
    if not result.branches:
        console.print("[yellow]No branches with artifacts found[/yellow]")
        return
    console.print("[cyan]Branches with artifacts:[/cyan]")
    for branch in result.branches:
        console.print(f"  • {branch['name']} ({branch['artifact_count']} files)")


@git_app.command("set-branch")
def set_branch(
    branch_name: str = typer.Argument(..., help="Branch name to use for MADSpec artifacts"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit JSON payload"),
) -> None:
    """Update MADSpec branch configuration and materialize its layout."""
    try:
        result = set_branch_config(Path.cwd(), branch_name)
    except Exception as exc:
        _emit_error(exc, json_output)
        raise typer.Exit(1) from exc
    if json_output:
        _emit_result(result, json_output=True)
        return
    show_banner()
    console.print(f"[green]Branch set to:[/green] {result.branch}")
    console.print(f"[dim]Config:[/dim] {result.config_path}")
    console.print(f"[dim]Branch directory:[/dim] {result.branch_dir}")


@git_app.command("ensure-gitignore")
def ensure_gitignore_command(
    json_output: bool = typer.Option(False, "--json-output", help="Emit JSON payload"),
) -> None:
    """Create or extend .gitignore with MADSpec defaults."""
    result = ensure_gitignore(Path.cwd())
    if json_output:
        _emit_result(result, json_output=True)
        return
    show_banner()
    if result.created:
        console.print(f"[green]Created:[/green] {result.path}")
    elif result.updated:
        console.print(f"[green]Updated:[/green] {result.path}")
    else:
        console.print(f"[yellow]No changes needed:[/yellow] {result.path}")
    console.print(f"[dim]Patterns added:[/dim] {result.added_patterns}")


@git_app.command("init")
def init(
    commit_message: str = typer.Option(
        "Initial commit from MADSpec template",
        "--commit-message",
        help="Commit message for the initial repository commit",
    ),
    json_output: bool = typer.Option(False, "--json-output", help="Emit JSON payload"),
) -> None:
    """Initialize a repository, ensure .gitignore, and create the initial commit."""
    try:
        result = init_repo(Path.cwd(), commit_message=commit_message)
    except (GitOperationError, OSError) as exc:
        _emit_error(exc, json_output)
        raise typer.Exit(1) from exc
    if json_output:
        _emit_result(result, json_output=True)
        return
    show_banner()
    if result.already_initialized:
        console.print("[yellow]Git repository already initialized[/yellow]")
    else:
        console.print("[green]Git repository initialized[/green]")
    console.print(f"[dim].gitignore:[/dim] {result.gitignore.path}")


@git_app.command("create-branch")
def create_branch_command(
    branch_name: str = typer.Argument(..., help="New git branch name"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit JSON payload"),
) -> None:
    """Create a git branch and sync MADSpec branch state."""
    try:
        result = create_branch(Path.cwd(), branch_name)
    except (GitOperationError, OSError) as exc:
        _emit_error(exc, json_output)
        raise typer.Exit(1) from exc
    if json_output:
        _emit_result(result, json_output=True)
        return
    show_banner()
    console.print(f"[green]Created branch:[/green] {result.branch}")
    console.print(f"[dim]Branch directory:[/dim] {result.sync.branch_dir}")


@git_app.command("commit")
def commit(
    message: str = typer.Option(..., "--message", help="Commit message"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit JSON payload"),
) -> None:
    """Stage all changes and create a commit."""
    try:
        result = commit_all(Path.cwd(), message)
    except (GitOperationError, OSError) as exc:
        _emit_error(exc, json_output)
        raise typer.Exit(1) from exc
    if json_output:
        _emit_result(result, json_output=True)
        return
    show_banner()
    console.print(f"[green]Created commit:[/green] {result.commit_hash}")
    console.print(f"[dim]Message:[/dim] {result.message}")


def register(app: typer.Typer) -> None:
    app.add_typer(git_app, name="git")
