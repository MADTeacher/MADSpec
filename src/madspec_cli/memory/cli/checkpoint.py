from __future__ import annotations

from pathlib import Path

import typer

from madspec_cli.memory.checkpoint import CHECKPOINT_STAGES
from madspec_cli.shared.cli.banners import console, show_banner
from madspec_cli.shared.cli.json_output import emit_json

from ..application.checkpoint_stage import CheckpointStageRequest, execute as checkpoint_stage
from ..domain.branch_layout import resolve_target_branch


def memory_checkpoint(
    stage: str = typer.Option(..., "--stage", help="Checkpoint stage: mvp.concept, mvp.design, mvp.tech, mvp.architecture, mvp.plan, feature.init, feature.plan, review, or security"),
    summary: str = typer.Option(..., "--summary", help="Stage checkpoint summary"),
    fact: list[str] = typer.Option(None, "--fact", help="Validated fact; repeat for multiple values"),
    decision: list[str] = typer.Option(None, "--decision", help="Validated decision; repeat for multiple values"),
    contract: list[str] = typer.Option(None, "--contract", help="Validated contract/constraint; repeat for multiple values"),
    evidence: list[str] = typer.Option(None, "--evidence", help="Supporting evidence path or note; repeat for multiple values"),
    question: list[str] = typer.Option(None, "--question", help="Open question to store in active session; repeat for multiple values"),
    pending_action: list[str] = typer.Option(None, "--pending-action", help="Pending action to store in active session; repeat for multiple values"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to update"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Persist a non-iterative stage checkpoint into structured memory."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    result = checkpoint_stage(
        CheckpointStageRequest(
            project_path=project_path,
            branch_name=target_branch,
            stage=stage,
            summary=summary,
            options={
                "facts": fact or [],
                "decisions": decision or [],
                "contracts": contract or [],
                "evidence": evidence or [],
                "questions": question or [],
                "pending_actions": pending_action or [],
            },
        )
    )

    payload = result.to_payload()
    if json_output:
        emit_json(payload)
        if not result.accepted:
            raise typer.Exit(1)
        return

    show_banner()
    console.print(f"[cyan]Branch:[/cyan] {target_branch}")
    console.print(f"[cyan]Stage:[/cyan] {stage}")
    if result.accepted:
        written = payload["written"]
        console.print(f"[green]Checkpoint saved for stage:[/green] {stage}")
        console.print(
            "[cyan]Records:[/cyan] "
            f"decision_log={written['decision_log']} "
            f"facts={written['facts']} "
            f"decisions={written['decisions']} "
            f"contracts={written['contracts']}"
        )
        return

    console.print("[red]Checkpoint rejected.[/red] " f"Allowed stages: {', '.join(sorted(CHECKPOINT_STAGES))}")
    for error in payload.get("errors", []):
        console.print(f"[red]- {error}[/red]")
    raise typer.Exit(1)


def register(memory_app: typer.Typer) -> None:
    memory_app.command("checkpoint")(memory_checkpoint)
