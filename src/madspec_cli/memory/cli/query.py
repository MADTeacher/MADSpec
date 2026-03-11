from __future__ import annotations

from pathlib import Path

import typer

from madspec_cli.shared.cli.banners import console, show_banner
from madspec_cli.shared.cli.json_output import emit_json

from ..application.retrieve_context import RetrieveMemoryContextRequest, execute as retrieve_context
from ..domain.branch_layout import resolve_target_branch


def memory_retrieve(
    stage: str = typer.Option(..., "--stage", help="Target stage, e.g. mvp.plan or review"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    step_id: str = typer.Option(None, "--step-id", help="Optional step identifier"),
    limit: int | None = typer.Option(None, "--limit", help="Max records per section"),
    include_obsolete: bool = typer.Option(False, "--include-obsolete", help="Include obsolete semantic records"),
    include_conflicted: bool = typer.Option(False, "--include-conflicted", help="Include conflicted semantic records"),
    full_artifact: bool = typer.Option(False, "--full-artifact", help="Return full stage artifact state instead of summary-only context"),
    include_history: bool = typer.Option(False, "--include-history", help="Include episodes and decision log in the response"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Retrieve minimal structured context for a stage."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    resolved_limit = limit if limit is not None else (3 if stage.strip().lower() in {"mvp.concept", "mvp.design", "mvp.tech", "mvp.architecture", "mvp.plan", "feature.init", "feature.plan"} else 5)
    result = retrieve_context(
        RetrieveMemoryContextRequest(
            project_path=project_path,
            branch_name=target_branch,
            stage=stage,
            step_id=step_id,
            limit=resolved_limit,
            include_obsolete=include_obsolete,
            include_conflicted=include_conflicted,
            full_artifact=full_artifact,
            include_history=include_history,
        )
    )
    payload = result.to_payload()
    if json_output:
        emit_json(payload)
        return

    show_banner()
    console.print(f"[cyan]Branch:[/cyan] {payload['branch']}")
    console.print(f"[cyan]Stage:[/cyan] {payload['stage']}")
    console.print(f"[cyan]Step:[/cyan] {payload['step_id'] or 'N/A'}")
    console.print(f"[cyan]Open questions:[/cyan] {len(payload['active_session']['open_questions'])}")
    console.print(f"[cyan]Facts:[/cyan] {len(payload['semantic']['facts'])}")
    console.print(f"[cyan]Decisions:[/cyan] {len(payload['semantic']['decisions'])}")
    console.print(f"[cyan]Contracts:[/cyan] {len(payload['semantic']['contracts'])}")
    console.print(f"[cyan]Episodes:[/cyan] {len(payload['episodes'])}")


def register(memory_app: typer.Typer) -> None:
    memory_app.command("retrieve")(memory_retrieve)
