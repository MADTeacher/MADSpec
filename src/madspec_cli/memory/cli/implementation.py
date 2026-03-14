from __future__ import annotations

from pathlib import Path

import typer

from madspec_cli.memory.workflow.implementation_shared import IMPLEMENTATION_STAGES
from madspec_cli.shared.cli.banners import console, show_banner
from madspec_cli.shared.cli.file_input import read_args_file
from madspec_cli.shared.cli.json_output import emit_json

from ..application.implementation_steps import (
    ImplementationStepRequest,
    checkpoint as checkpoint_step,
    complete as complete_step,
    start as start_step,
)
from ..domain.branch_layout import resolve_target_branch


START_STEP_FROM_FILE_ALLOWED_KEYS = {
    "stage",
    "branch",
    "step_id",
    "summary",
    "evidence",
    "json_output",
}

CHECKPOINT_STEP_FROM_FILE_ALLOWED_KEYS = {
    "stage",
    "branch",
    "step_id",
    "summary",
    "tdd_phase",
    "red_evidence",
    "green_evidence",
    "refactor_note",
    "evidence",
    "json_output",
}

COMPLETE_STEP_FROM_FILE_ALIASES = {
    "fact": "facts",
    "decision": "decisions",
    "contract": "contracts",
}

COMPLETE_STEP_FROM_FILE_ALLOWED_KEYS = {
    "stage",
    "summary",
    "branch",
    "step_id",
    "red_evidence",
    "green_evidence",
    "refactor_note",
    "evidence",
    "facts",
    "decisions",
    "contracts",
    "json_output",
}


def memory_start_step(
    from_file: str = typer.Option(None, "--from-file", help="Path to JSON file with all arguments (bypasses command-line length limits)"),
    stage: str = typer.Option(None, "--stage", help="Implementation stage: mvp.implement or feature.implement"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to update"),
    step_id: str = typer.Option(None, "--step-id", help="Optional step identifier; defaults to next executable step"),
    summary: str = typer.Option(None, "--summary", help="Optional active goal override"),
    evidence: list[str] = typer.Option(None, "--evidence", help="Supporting evidence path or note; repeat for multiple values"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Select and start an implementation step in structured memory."""
    if from_file:
        file_data = read_args_file(from_file, allowed_keys=START_STEP_FROM_FILE_ALLOWED_KEYS)
        stage = file_data.pop("stage", stage)
        branch_name = file_data.pop("branch", branch_name)
        step_id = file_data.pop("step_id", step_id)
        summary = file_data.pop("summary", summary)
        evidence = file_data.pop("evidence", evidence)
        json_output = file_data.pop("json_output", json_output)

    if not stage:
        console.print("[red]--stage is required (pass it via CLI or inside the JSON file)[/red]")
        raise typer.Exit(1)

    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    result = start_step(
        ImplementationStepRequest(project_path=project_path, branch_name=target_branch, stage=stage, options={"step_id": step_id, "summary": summary, "evidence": evidence or []})
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
        console.print(f"[green]Started step:[/green] {payload['step_id']}")
        return

    console.print("[red]Failed to start step.[/red] " f"Allowed stages: {', '.join(sorted(IMPLEMENTATION_STAGES))}")
    for error in payload.get("errors", []):
        console.print(f"[red]- {error}[/red]")
    raise typer.Exit(1)


def memory_checkpoint_step(
    from_file: str = typer.Option(None, "--from-file", help="Path to JSON file with all arguments (bypasses command-line length limits)"),
    stage: str = typer.Option(None, "--stage", help="Implementation stage: mvp.implement or feature.implement"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to update"),
    step_id: str = typer.Option(None, "--step-id", help="Optional step identifier; defaults to current implementation step"),
    summary: str = typer.Option(None, "--summary", help="Optional checkpoint summary"),
    tdd_phase: str = typer.Option(None, "--tdd-phase", help="TDD phase checkpoint: not_started, red, green, refactor, or waived"),
    red_evidence: list[str] = typer.Option(None, "--red-evidence", help="Red-phase evidence; repeat for multiple values"),
    green_evidence: list[str] = typer.Option(None, "--green-evidence", help="Green-phase evidence; repeat for multiple values"),
    refactor_note: str = typer.Option(None, "--refactor-note", help="Refactor note for the current step"),
    evidence: list[str] = typer.Option(None, "--evidence", help="Supporting evidence path or note; repeat for multiple values"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Persist an in-progress implementation checkpoint into structured memory."""
    if from_file:
        file_data = read_args_file(from_file, allowed_keys=CHECKPOINT_STEP_FROM_FILE_ALLOWED_KEYS)
        stage = file_data.pop("stage", stage)
        branch_name = file_data.pop("branch", branch_name)
        json_output = file_data.pop("json_output", json_output)
        options = {
            "step_id": file_data.get("step_id", step_id),
            "summary": file_data.get("summary", summary),
            "tdd_phase": file_data.get("tdd_phase", tdd_phase),
            "red_evidence": file_data.get("red_evidence", red_evidence or []),
            "green_evidence": file_data.get("green_evidence", green_evidence or []),
            "refactor_note": file_data.get("refactor_note", refactor_note),
            "evidence": file_data.get("evidence", evidence or []),
        }
    else:
        options = {
            "step_id": step_id,
            "summary": summary,
            "tdd_phase": tdd_phase,
            "red_evidence": red_evidence or [],
            "green_evidence": green_evidence or [],
            "refactor_note": refactor_note,
            "evidence": evidence or [],
        }

    if not stage:
        console.print("[red]--stage is required (pass it via CLI or inside the JSON file)[/red]")
        raise typer.Exit(1)

    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    result = checkpoint_step(
        ImplementationStepRequest(
            project_path=project_path,
            branch_name=target_branch,
            stage=stage,
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
        console.print(f"[green]Checkpointed step:[/green] {payload['step_id']}")
        console.print(f"[cyan]TDD phase:[/cyan] {payload['tdd_phase']}")
        return

    for error in payload.get("errors", []):
        console.print(f"[red]- {error}[/red]")
    raise typer.Exit(1)


def memory_complete_step(
    from_file: str = typer.Option(None, "--from-file", help="Path to JSON file with all arguments (bypasses command-line length limits)"),
    stage: str = typer.Option(None, "--stage", help="Implementation stage: mvp.implement or feature.implement"),
    summary: str = typer.Option(None, "--summary", help="Completion summary for the implementation step"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to update"),
    step_id: str = typer.Option(None, "--step-id", help="Optional step identifier; defaults to current implementation step"),
    red_evidence: list[str] = typer.Option(None, "--red-evidence", help="Red-phase evidence; repeat for multiple values"),
    green_evidence: list[str] = typer.Option(None, "--green-evidence", help="Green-phase evidence; repeat for multiple values"),
    refactor_note: str = typer.Option(None, "--refactor-note", help="Refactor note for the current step"),
    evidence: list[str] = typer.Option(None, "--evidence", help="Supporting evidence path or note; repeat for multiple values"),
    fact: list[str] = typer.Option(None, "--fact", help="Validated fact to store for the completed step; repeat for multiple values"),
    decision: list[str] = typer.Option(None, "--decision", help="Validated decision to store for the completed step; repeat for multiple values"),
    contract: list[str] = typer.Option(None, "--contract", help="Validated contract to store for the completed step; repeat for multiple values"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Mark an implementation step complete and advance structured memory state."""
    if from_file:
        file_data = read_args_file(
            from_file,
            aliases=COMPLETE_STEP_FROM_FILE_ALIASES,
            allowed_keys=COMPLETE_STEP_FROM_FILE_ALLOWED_KEYS,
        )
        stage = file_data.pop("stage", stage)
        summary = file_data.pop("summary", summary)
        branch_name = file_data.pop("branch", branch_name)
        json_output = file_data.pop("json_output", json_output)
        options = {
            "step_id": file_data.get("step_id", step_id),
            "summary": summary,
            "red_evidence": file_data.get("red_evidence", red_evidence or []),
            "green_evidence": file_data.get("green_evidence", green_evidence or []),
            "refactor_note": file_data.get("refactor_note", refactor_note),
            "evidence": file_data.get("evidence", evidence or []),
            "facts": file_data.get("facts", fact or []),
            "decisions": file_data.get("decisions", decision or []),
            "contracts": file_data.get("contracts", contract or []),
        }
    else:
        options = {
            "step_id": step_id,
            "summary": summary,
            "red_evidence": red_evidence or [],
            "green_evidence": green_evidence or [],
            "refactor_note": refactor_note,
            "evidence": evidence or [],
            "facts": fact or [],
            "decisions": decision or [],
            "contracts": contract or [],
        }

    if not stage:
        console.print("[red]--stage is required (pass it via CLI or inside the JSON file)[/red]")
        raise typer.Exit(1)
    if not summary:
        console.print("[red]--summary is required (pass it via CLI or inside the JSON file)[/red]")
        raise typer.Exit(1)

    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    result = complete_step(
        ImplementationStepRequest(
            project_path=project_path,
            branch_name=target_branch,
            stage=stage,
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
        console.print(f"[green]Completed step:[/green] {payload['step_id']}")
        console.print(f"[cyan]Next step:[/cyan] {payload.get('next_step') or 'none'}")
        return

    for error in payload.get("errors", []):
        console.print(f"[red]- {error}[/red]")
    raise typer.Exit(1)


def register(memory_app: typer.Typer) -> None:
    memory_app.command("start-step")(memory_start_step)
    memory_app.command("checkpoint-step")(memory_checkpoint_step)
    memory_app.command("complete-step")(memory_complete_step)
