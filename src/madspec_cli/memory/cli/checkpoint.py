from __future__ import annotations

from pathlib import Path

import typer

from madspec_cli.memory.checkpoint import CHECKPOINT_STAGES
from madspec_cli.shared.cli.banners import console, show_banner
from madspec_cli.shared.cli.file_input import read_args_file
from madspec_cli.shared.cli.json_output import emit_json

from ..application.checkpoint_stage import CheckpointStageRequest, execute as checkpoint_stage
from ..domain.branch_layout import resolve_target_branch


CHECKPOINT_FROM_FILE_ALIASES = {
    "fact": "facts",
    "decision": "decisions",
    "contract": "contracts",
    "question": "questions",
    "pending_action": "pending_actions",
}

CHECKPOINT_FROM_FILE_ALLOWED_KEYS = {
    "stage",
    "summary",
    "branch",
    "json_output",
    "facts",
    "decisions",
    "contracts",
    "evidence",
    "questions",
    "pending_actions",
}


def memory_checkpoint(
    from_file: str = typer.Option(None, "--from-file", help="Path to JSON file with all arguments (bypasses command-line length limits)"),
    stage: str = typer.Option(None, "--stage", help="Checkpoint stage: mvp.concept, mvp.design, mvp.tech, mvp.architecture, mvp.plan, feature.init, feature.plan, review, or security"),
    summary: str = typer.Option(None, "--summary", help="Stage checkpoint summary"),
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
    if from_file:
        file_data = read_args_file(
            from_file,
            aliases=CHECKPOINT_FROM_FILE_ALIASES,
            allowed_keys=CHECKPOINT_FROM_FILE_ALLOWED_KEYS,
        )
        stage = file_data.pop("stage", stage)
        summary = file_data.pop("summary", summary)
        branch_name = file_data.pop("branch", branch_name)
        json_output = file_data.pop("json_output", json_output)
        options = {
            "facts": file_data.get("facts", []),
            "decisions": file_data.get("decisions", []),
            "contracts": file_data.get("contracts", []),
            "evidence": file_data.get("evidence", []),
            "questions": file_data.get("questions", []),
            "pending_actions": file_data.get("pending_actions", []),
        }
    else:
        options = {
            "facts": fact or [],
            "decisions": decision or [],
            "contracts": contract or [],
            "evidence": evidence or [],
            "questions": question or [],
            "pending_actions": pending_action or [],
        }

    if not stage:
        console.print("[red]--stage is required (pass it via CLI or inside the JSON file)[/red]")
        raise typer.Exit(1)
    if not summary:
        console.print("[red]--summary is required (pass it via CLI or inside the JSON file)[/red]")
        raise typer.Exit(1)

    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    result = checkpoint_stage(
        CheckpointStageRequest(
            project_path=project_path,
            branch_name=target_branch,
            stage=stage,
            summary=summary,
            options=options,
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

    errors = payload.get("errors", [])
    show_allowed_stages = any(error.startswith("stage must be one of:") for error in errors)
    if show_allowed_stages:
        console.print("[red]Checkpoint rejected.[/red] " f"Allowed stages: {', '.join(sorted(CHECKPOINT_STAGES))}")
    else:
        console.print("[red]Checkpoint rejected.[/red] Fix the validation errors below.")
    for error in errors:
        console.print(f"[red]- {error}[/red]")
    raise typer.Exit(1)


def register(memory_app: typer.Typer) -> None:
    memory_app.command("checkpoint")(memory_checkpoint)
