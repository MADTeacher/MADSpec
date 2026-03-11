from __future__ import annotations

from pathlib import Path

import typer

from madspec_cli.shared.cli.banners import console, show_banner
from madspec_cli.shared.cli.json_output import emit_json

from ..application.determine_next_step import DetermineNextStepRequest, execute as determine_next_step
from ..application.register_step import RegisterStepRequest, execute as register_step
from ..domain.branch_layout import resolve_target_branch


def memory_next_step(
    stage: str = typer.Option(..., "--stage", help="Target stage, e.g. mvp.plan or mvp.implement"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    candidate_step: str = typer.Option(None, "--candidate-step", help="Candidate step id to validate"),
    depends_on: list[str] = typer.Option(None, "--depends-on", help="Dependency step ids for candidate validation"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Select the next executable step or validate a new planning candidate."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    result = determine_next_step(
        DetermineNextStepRequest(
            project_path=project_path,
            branch_name=target_branch,
            stage=stage,
            candidate_step=candidate_step,
            depends_on=depends_on or [],
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
    if candidate_step:
        console.print(f"[cyan]Candidate:[/cyan] {candidate_step}")
    else:
        console.print(f"[cyan]Selected step:[/cyan] {payload.get('selected_step') or 'N/A'}")
    console.print(f"[cyan]Reason:[/cyan] {payload['reason']}")
    if payload["errors"]:
        for error in payload["errors"]:
            console.print(f"[red]- {error}[/red]")
        raise typer.Exit(1)


def memory_register_step(
    stage: str = typer.Option(..., "--stage", help="Planning stage, e.g. mvp.plan or feature.plan"),
    step_id: str = typer.Option(..., "--step-id", help="New step identifier"),
    covers: list[str] = typer.Option(None, "--covers", help="Covered function ids/labels; repeat for multiple values."),
    step_kind: str = typer.Option(..., "--step-kind", help="Step kind: code or non-code"),
    tdd_policy: str = typer.Option(None, "--tdd-policy", help="TDD policy: required, waived, or not-applicable"),
    waiver_reason: str = typer.Option(None, "--waiver-reason", help="Reason for waiving TDD on non-code steps"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to update"),
    depends_on: list[str] = typer.Option(None, "--depends-on", help="Dependency step ids"),
    summary: str = typer.Option(None, "--summary", help="Optional summary for the decision log"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Register a planned step and update coverage metadata in progress.json."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    result = register_step(
        RegisterStepRequest(
            project_path=project_path,
            branch_name=target_branch,
            stage=stage,
            step_id=step_id,
            covers=covers or [],
            step_kind=step_kind,
            tdd_policy=tdd_policy,
            waiver_reason=waiver_reason,
            depends_on=depends_on or [],
            summary=summary,
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
    console.print(f"[cyan]Step:[/cyan] {step_id}")
    if result.accepted:
        metrics = payload["progressMetrics"]
        console.print(f"[green]Registered step:[/green] {step_id}")
        console.print(
            "[cyan]Coverage:[/cyan] "
            f"P1={metrics['p1Coverage']['covered']}/{metrics['p1Coverage']['total']} "
            f"P2={metrics['p2Coverage']['covered']}/{metrics['p2Coverage']['total']} "
            f"P3={metrics['p3Coverage']['covered']}/{metrics['p3Coverage']['total']} "
            f"overall={metrics['overallProgress']}%"
        )
        metadata = payload.get("stepMetadata", {})
        console.print("[cyan]TDD:[/cyan] " f"kind={metadata.get('kind')} " f"policy={metadata.get('tddPolicy')}")
        return

    for error in payload.get("errors", []):
        console.print(f"[red]- {error}[/red]")
    raise typer.Exit(1)


def register(memory_app: typer.Typer) -> None:
    memory_app.command("next-step")(memory_next_step)
    memory_app.command("register-step")(memory_register_step)
