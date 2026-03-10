from __future__ import annotations

from pathlib import Path

import typer

from ..memory import (
    CHECKPOINT_STAGES,
    checkpoint_stage_memory,
    consolidate_branch_memory,
    ensure_memory_layout,
    get_memory_paths,
    learn_from_outcomes,
    promote_validated_records,
    read_jsonl,
    register_planned_step,
    retrieve_memory_context,
    determine_next_step,
    validate_branch_memory,
)
from ..project_state import create_madspec_config, emit_json, resolve_branch_name
from ..ui import console, show_banner


def memory_checkpoint(
    stage: str = typer.Option(..., "--stage", help="Checkpoint stage: mvp.concept, mvp.design, mvp.tech, or mvp.architecture"),
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
    target_branch = resolve_branch_name(project_path, branch_name)
    payload = checkpoint_stage_memory(
        project_path,
        target_branch,
        stage,
        summary,
        facts=fact or [],
        decisions=decision or [],
        contracts=contract or [],
        evidence=evidence or [],
        questions=question or [],
        pending_actions=pending_action or [],
    )

    if json_output:
        emit_json(payload)
        if not payload.get("accepted"):
            raise typer.Exit(1)
        return

    show_banner()
    console.print(f"[cyan]Branch:[/cyan] {target_branch}")
    console.print(f"[cyan]Stage:[/cyan] {stage}")
    if payload.get("accepted"):
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

    console.print(
        "[red]Checkpoint rejected.[/red] "
        f"Allowed stages: {', '.join(sorted(CHECKPOINT_STAGES))}"
    )
    for error in payload.get("errors", []):
        console.print(f"[red]- {error}[/red]")
    raise typer.Exit(1)


def memory_init(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to initialize"),
) -> None:
    """Initialize structured memory layout for the current project."""
    show_banner()
    project_path = Path.cwd()
    target_branch = resolve_branch_name(project_path, branch_name)
    create_madspec_config(project_path, target_branch)
    created = ensure_memory_layout(project_path, target_branch)
    generated = consolidate_branch_memory(project_path, target_branch)
    errors = validate_branch_memory(project_path, target_branch)
    if errors:
        console.print("[red]Memory initialization completed with validation errors:[/red]")
        for error in errors:
            console.print(f"  - {error}")
        raise typer.Exit(1)

    console.print(f"[green]Structured memory initialized for branch:[/green] {target_branch}")
    console.print(f"[cyan]Created files:[/cyan] {len(created)}")
    console.print(f"[cyan]Generated views:[/cyan] {len(generated)}")


def memory_status(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Show structured memory status for the current branch."""
    project_path = Path.cwd()
    target_branch = resolve_branch_name(project_path, branch_name)
    paths = get_memory_paths(project_path, target_branch)

    payload = {
        "branch": target_branch,
        "progress_exists": paths.progress.exists(),
        "active_session_exists": paths.active_session.exists(),
        "decision_log_records": len(read_jsonl(paths.decision_log)),
        "episode_records": len(read_jsonl(paths.events)),
        "semantic_records": {
            "facts": len(read_jsonl(paths.facts)),
            "decisions": len(read_jsonl(paths.decisions)),
            "contracts": len(read_jsonl(paths.contracts)),
        },
    }
    if json_output:
        emit_json(payload)
        return

    show_banner()
    console.print(f"[cyan]Branch:[/cyan] {target_branch}")
    console.print(f"[cyan]Progress:[/cyan] {'present' if payload['progress_exists'] else 'missing'}")
    console.print(
        f"[cyan]Active session:[/cyan] {'present' if payload['active_session_exists'] else 'missing'}"
    )
    console.print(f"[cyan]Decision log records:[/cyan] {payload['decision_log_records']}")
    console.print(f"[cyan]Episode records:[/cyan] {payload['episode_records']}")
    console.print(
        "[cyan]Semantic records:[/cyan] "
        f"facts={payload['semantic_records']['facts']}, "
        f"decisions={payload['semantic_records']['decisions']}, "
        f"contracts={payload['semantic_records']['contracts']}"
    )


def memory_consolidate(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to consolidate"),
) -> None:
    """Generate markdown views from structured memory."""
    show_banner()
    project_path = Path.cwd()
    target_branch = resolve_branch_name(project_path, branch_name)
    ensure_memory_layout(project_path, target_branch)
    generated = consolidate_branch_memory(project_path, target_branch)
    console.print(f"[green]Consolidated branch:[/green] {target_branch}")
    for path in generated:
        console.print(f"  - {path.relative_to(project_path)}")


def memory_validate(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to validate"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Validate structured memory and derived views."""
    project_path = Path.cwd()
    target_branch = resolve_branch_name(project_path, branch_name)
    ensure_memory_layout(project_path, target_branch)
    errors = validate_branch_memory(project_path, target_branch)
    payload = {"branch": target_branch, "valid": not errors, "errors": errors}

    if json_output:
        emit_json(payload)
    else:
        show_banner()
        if errors:
            console.print(f"[red]Structured memory is invalid for branch:[/red] {target_branch}")
            for error in errors:
                console.print(f"  - {error}")
        else:
            console.print(f"[green]Structured memory is valid for branch:[/green] {target_branch}")

    if errors:
        raise typer.Exit(1)


def memory_retrieve(
    stage: str = typer.Option(..., "--stage", help="Target stage, e.g. mvp.plan or review"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    step_id: str = typer.Option(None, "--step-id", help="Optional step identifier"),
    limit: int = typer.Option(5, "--limit", help="Max records per section"),
    include_obsolete: bool = typer.Option(False, "--include-obsolete", help="Include obsolete semantic records"),
    include_conflicted: bool = typer.Option(False, "--include-conflicted", help="Include conflicted semantic records"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Retrieve minimal structured context for a stage."""
    project_path = Path.cwd()
    target_branch = resolve_branch_name(project_path, branch_name)
    ensure_memory_layout(project_path, target_branch)
    payload = retrieve_memory_context(
        project_path,
        target_branch,
        stage,
        step_id=step_id,
        limit=limit,
        include_obsolete=include_obsolete,
        include_conflicted=include_conflicted,
    )
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


def memory_next_step(
    stage: str = typer.Option(..., "--stage", help="Target stage, e.g. mvp.plan or mvp.implement"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    candidate_step: str = typer.Option(None, "--candidate-step", help="Candidate step id to validate"),
    depends_on: list[str] = typer.Option(None, "--depends-on", help="Dependency step ids for candidate validation"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Select the next executable step or validate a new planning candidate."""
    project_path = Path.cwd()
    target_branch = resolve_branch_name(project_path, branch_name)
    ensure_memory_layout(project_path, target_branch)
    payload = determine_next_step(
        project_path,
        target_branch,
        stage,
        candidate_step=candidate_step,
        candidate_dependencies=depends_on or [],
    )

    if json_output:
        emit_json(payload)
        if not payload["accepted"]:
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
    covers: list[str] = typer.Option(
        None,
        "--covers",
        help="Covered function ids/labels; repeat for multiple values. Required for code steps, optional for non-code.",
    ),
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
    target_branch = resolve_branch_name(project_path, branch_name)
    ensure_memory_layout(project_path, target_branch)
    payload = register_planned_step(
        project_path,
        target_branch,
        stage,
        step_id=step_id,
        covers=covers or [],
        step_kind=step_kind,
        tdd_policy=tdd_policy,
        waiver_reason=waiver_reason,
        depends_on=depends_on or [],
        summary=summary,
    )
    if payload.get("accepted"):
        consolidate_branch_memory(project_path, target_branch)
        validation_errors = validate_branch_memory(project_path, target_branch)
        if validation_errors:
            payload = {"accepted": False, "step_id": step_id, "errors": validation_errors}

    if json_output:
        emit_json(payload)
        if not payload.get("accepted"):
            raise typer.Exit(1)
        return

    show_banner()
    console.print(f"[cyan]Branch:[/cyan] {target_branch}")
    console.print(f"[cyan]Stage:[/cyan] {stage}")
    console.print(f"[cyan]Step:[/cyan] {step_id}")
    if payload.get("accepted"):
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
        console.print(
            "[cyan]TDD:[/cyan] "
            f"kind={metadata.get('kind')} "
            f"policy={metadata.get('tddPolicy')}"
        )
        return

    for error in payload.get("errors", []):
        console.print(f"[red]- {error}[/red]")
    raise typer.Exit(1)


def memory_promote(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to promote"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Promote validated records into semantic memory."""
    project_path = Path.cwd()
    target_branch = resolve_branch_name(project_path, branch_name)
    ensure_memory_layout(project_path, target_branch)
    payload = promote_validated_records(project_path, target_branch)
    consolidate_branch_memory(project_path, target_branch)

    if json_output:
        emit_json({"branch": target_branch, "promoted": payload})
        return

    show_banner()
    console.print(f"[green]Promoted semantic records for branch:[/green] {target_branch}")
    console.print(
        f"[cyan]facts={payload['fact']} decisions={payload['decision']} contracts={payload['contract']}[/cyan]"
    )


def memory_learn(
    input_path: Path = typer.Option(..., "--input", exists=True, file_okay=True, dir_okay=False, readable=True, resolve_path=True, help="JSON or JSONL outcomes file"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to update"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Convert test/review outcomes into structured learning records."""
    project_path = Path.cwd()
    target_branch = resolve_branch_name(project_path, branch_name)
    ensure_memory_layout(project_path, target_branch)
    payload = learn_from_outcomes(project_path, target_branch, input_path)
    consolidate_branch_memory(project_path, target_branch)

    if json_output:
        emit_json({"branch": target_branch, **payload})
        return

    show_banner()
    console.print(f"[green]Learning records ingested for branch:[/green] {target_branch}")
    console.print(
        f"[cyan]events={payload['events']} semantic_candidates={payload['semantic_candidates']}[/cyan]"
    )


def register(memory_app: typer.Typer) -> None:
    memory_app.command("init")(memory_init)
    memory_app.command("status")(memory_status)
    memory_app.command("consolidate")(memory_consolidate)
    memory_app.command("validate")(memory_validate)
    memory_app.command("checkpoint")(memory_checkpoint)
    memory_app.command("retrieve")(memory_retrieve)
    memory_app.command("next-step")(memory_next_step)
    memory_app.command("register-step")(memory_register_step)
    memory_app.command("promote")(memory_promote)
    memory_app.command("learn")(memory_learn)
