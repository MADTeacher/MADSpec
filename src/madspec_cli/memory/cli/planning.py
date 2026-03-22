from __future__ import annotations

from pathlib import Path

import typer

from madspec_cli.shared.cli.banners import console, show_banner
from madspec_cli.shared.cli.file_input import ArgsFileLifecycle, read_args_file
from madspec_cli.shared.cli.json_output import emit_json

from ..application.determine_next_step import DetermineNextStepRequest, execute as determine_next_step
from ..application.register_step import RegisterStepRequest, execute as register_step
from .runtime_feedback import render_runtime_rejection
from ..application.resolve_branch import resolve_branch
from ..shared import SYSTEM_SESSION_KEY


REGISTER_STEP_FROM_FILE_ALIASES = {
    "related_artifact": "related_artifacts",
}

REGISTER_STEP_FROM_FILE_ALLOWED_KEYS = {
    "stage",
    "session_key",
    "expected_revision",
    "step_id",
    "covers",
    "step_kind",
    "tdd_policy",
    "waiver_reason",
    "title",
    "branch",
    "depends_on",
    "summary",
    "related_artifacts",
    "size",
    "complexity",
    "json_output",
}


def memory_next_step(
    stage: str = typer.Option(..., "--stage", help="Target stage, e.g. mvp.plan or mvp.implement"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    candidate_step: str = typer.Option(None, "--candidate-step", help="Candidate step id to validate"),
    depends_on: list[str] = typer.Option(None, "--depends-on", help="Dependency step ids for candidate validation"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Select the next executable step or validate a new planning candidate."""
    project_path = Path.cwd()
    target_branch = resolve_branch(project_path, branch_name)
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
    from_file: str = typer.Option(None, "--from-file", help="Path to JSON file with all arguments (bypasses command-line length limits)"),
    stage: str = typer.Option(None, "--stage", help="Planning stage, e.g. mvp.plan or feature.plan"),
    session_key: str = typer.Option(SYSTEM_SESSION_KEY, "--session-key", help="Runtime session key; defaults to legacy active"),
    expected_revision: int | None = typer.Option(None, "--expected-revision", help="Expected branch runtime revision for optimistic concurrency"),
    step_id: str = typer.Option(None, "--step-id", help="New step identifier"),
    covers: list[str] = typer.Option(None, "--covers", help="Covered function ids/labels; repeat for multiple values."),
    step_kind: str = typer.Option(None, "--step-kind", help="Step kind: code or non-code"),
    tdd_policy: str = typer.Option(None, "--tdd-policy", help="TDD policy: required, waived, or not-applicable"),
    waiver_reason: str = typer.Option(None, "--waiver-reason", help="Reason for waiving TDD on non-code steps"),
    title: str = typer.Option(None, "--title", help="Optional human-readable step title for the generated implementation plan"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to update"),
    depends_on: list[str] = typer.Option(None, "--depends-on", help="Dependency step ids"),
    summary: str = typer.Option(None, "--summary", help="Optional summary for the decision log"),
    related_artifact: list[str] = typer.Option(None, "--related-artifact", help="Related artifact path; repeat for multiple values"),
    size: str = typer.Option(None, "--size", help="Step size: small, medium, large"),
    complexity: str = typer.Option(None, "--complexity", help="Step complexity: low, medium, high"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Register a planned step and update coverage metadata in progress.json."""
    args_file_lifecycle = ArgsFileLifecycle.from_path(from_file) if from_file else None
    if from_file:
        file_data = read_args_file(
            from_file,
            aliases=REGISTER_STEP_FROM_FILE_ALIASES,
            allowed_keys=REGISTER_STEP_FROM_FILE_ALLOWED_KEYS,
        )
        stage = file_data.pop("stage", stage)
        session_key = file_data.pop("session_key", session_key)
        expected_revision = file_data.pop("expected_revision", expected_revision)
        step_id = file_data.pop("step_id", step_id)
        covers = file_data.pop("covers", covers)
        step_kind = file_data.pop("step_kind", step_kind)
        tdd_policy = file_data.pop("tdd_policy", tdd_policy)
        waiver_reason = file_data.pop("waiver_reason", waiver_reason)
        title = file_data.pop("title", title)
        branch_name = file_data.pop("branch", branch_name)
        depends_on = file_data.pop("depends_on", depends_on)
        summary = file_data.pop("summary", summary)
        related_artifact = file_data.pop("related_artifacts", related_artifact)
        size = file_data.pop("size", size)
        complexity = file_data.pop("complexity", complexity)
        json_output = file_data.pop("json_output", json_output)

    if not stage:
        console.print("[red]--stage is required (pass it via CLI or inside the JSON file)[/red]")
        raise typer.Exit(1)
    if not step_id:
        console.print("[red]--step-id is required (pass it via CLI or inside the JSON file)[/red]")
        raise typer.Exit(1)
    if not step_kind:
        console.print("[red]--step-kind is required (pass it via CLI or inside the JSON file)[/red]")
        raise typer.Exit(1)

    project_path = Path.cwd()
    target_branch = resolve_branch(project_path, branch_name)
    result = register_step(
        RegisterStepRequest(
            project_path=project_path,
            branch_name=target_branch,
            stage=stage,
            session_key=session_key,
            expected_revision=expected_revision,
            step_id=step_id,
            covers=covers or [],
            step_kind=step_kind,
            tdd_policy=tdd_policy,
            waiver_reason=waiver_reason,
            depends_on=depends_on or [],
            summary=summary,
            title=title,
            related_artifacts=related_artifact or [],
            size=size,
            complexity=complexity,
        )
    )
    payload = result.to_payload()
    if json_output:
        emit_json(payload)
        if not result.accepted:
            raise typer.Exit(1)
        if args_file_lifecycle is not None:
            args_file_lifecycle.cleanup_after_success()
        return

    show_banner()
    console.print(f"[cyan]Branch:[/cyan] {target_branch}")
    console.print(f"[cyan]Stage:[/cyan] {stage}")
    console.print(f"[cyan]Step:[/cyan] {step_id}")
    if result.accepted:
        if args_file_lifecycle is not None:
            args_file_lifecycle.cleanup_after_success()
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

    render_runtime_rejection(payload, fallback_title="Register step rejected.")
    raise typer.Exit(1)


def register(memory_app: typer.Typer) -> None:
    memory_app.command("next-step")(memory_next_step)
    memory_app.command("register-step")(memory_register_step)
