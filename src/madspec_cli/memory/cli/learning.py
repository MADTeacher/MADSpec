from __future__ import annotations

from pathlib import Path

import typer

from madspec_cli.shared.cli.banners import console, show_banner
from madspec_cli.shared.cli.json_output import emit_json

from ..application.learning import LearnFromOutcomesRequest, PromoteMemoryRequest, learn as learn_from_outcomes, promote as promote_memory
from ..domain.branch_layout import resolve_target_branch


def memory_promote(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to promote"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Promote validated records into semantic memory."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    result = promote_memory(PromoteMemoryRequest(project_path=project_path, branch_name=target_branch))

    if json_output:
        emit_json(result)
        return

    payload = result.to_payload()
    show_banner()
    console.print(f"[green]Promoted semantic records for branch:[/green] {target_branch}")
    console.print(f"[cyan]facts={payload['promoted']['fact']} decisions={payload['promoted']['decision']} contracts={payload['promoted']['contract']}[/cyan]")


def memory_learn(
    input_path: Path = typer.Option(..., "--input", exists=True, file_okay=True, dir_okay=False, readable=True, resolve_path=True, help="JSON or JSONL outcomes file"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to update"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Convert test/review outcomes into structured learning records."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    result = learn_from_outcomes(LearnFromOutcomesRequest(project_path=project_path, branch_name=target_branch, input_path=input_path))

    if json_output:
        emit_json(result)
        return

    payload = result.to_payload()
    show_banner()
    console.print(f"[green]Learning records ingested for branch:[/green] {target_branch}")
    console.print(f"[cyan]events={payload['events']} semantic_candidates={payload['semantic_candidates']}[/cyan]")


def register(memory_app: typer.Typer) -> None:
    memory_app.command("promote")(memory_promote)
    memory_app.command("learn")(memory_learn)
