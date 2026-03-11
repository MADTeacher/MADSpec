from __future__ import annotations

from pathlib import Path

import typer

from ..memory.implementation import (
    IMPLEMENTATION_STAGES,
    checkpoint_implementation_step,
    complete_implementation_step,
    start_implementation_step,
)
from ..memory.stage_capture import CAPTURE_STAGES, capture_stage_memory
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
    stage: str = typer.Option(..., "--stage", help="Checkpoint stage: mvp.concept, mvp.design, mvp.tech, mvp.architecture, review, or security"),
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


def memory_capture(
    stage: str = typer.Option(..., "--stage", help="Stage to capture: mvp.concept, mvp.design, mvp.tech, mvp.architecture, review, or security"),
    summary: str = typer.Option(None, "--summary", help="Optional stage note summary"),
    fact: list[str] = typer.Option(None, "--fact", help="Fact to capture; repeat for multiple values"),
    decision: list[str] = typer.Option(None, "--decision", help="Decision to capture; repeat for multiple values"),
    contract: list[str] = typer.Option(None, "--contract", help="Contract/constraint to capture; repeat for multiple values"),
    evidence: list[str] = typer.Option(None, "--evidence", help="Supporting evidence path or note; repeat for multiple values"),
    question: list[str] = typer.Option(None, "--question", help="Open question to add to active session; repeat for multiple values"),
    pending_action: list[str] = typer.Option(None, "--pending-action", help="Pending action to add to active session; repeat for multiple values"),
    project_name: str = typer.Option(None, "--project-name", help="Concept-only: project name to store in canonical concept state"),
    system_overview: str = typer.Option(None, "--system-overview", help="Concept-only: short general description of the system"),
    audience: list[str] = typer.Option(None, "--audience", help="Concept-only: audience entry; repeat for multiple values"),
    scenario: list[str] = typer.Option(None, "--scenario", help="Concept-only: usage scenario; repeat for multiple values"),
    pain: list[str] = typer.Option(None, "--pain", help="Concept-only: pain point; repeat for multiple values"),
    feature_p1: list[str] = typer.Option(None, "--feature-p1", help="Concept-only: P1 feature in '<name>::<description>' format; repeat for multiple values"),
    feature_p2: list[str] = typer.Option(None, "--feature-p2", help="Concept-only: P2 feature in '<name>::<description>' format; repeat for multiple values"),
    feature_p3: list[str] = typer.Option(None, "--feature-p3", help="Concept-only: P3 feature in '<name>::<description>' format; repeat for multiple values"),
    constraint: list[str] = typer.Option(None, "--constraint", help="Concept-only: technical constraint; repeat for multiple values"),
    assumption: list[str] = typer.Option(None, "--assumption", help="Concept-only: assumption; repeat for multiple values"),
    next_action: list[str] = typer.Option(None, "--next-action", help="Concept/design/tech-only: canonical next action; repeat for multiple values"),
    design_overview: str = typer.Option(None, "--design-overview", help="Design-only: short summary of the UI/UX approach"),
    platform: list[str] = typer.Option(None, "--platform", help="Design-only: supported platform; repeat for multiple values"),
    zone: list[str] = typer.Option(None, "--zone", help="Design-only: zone in '<id>::<title>::<description>' format; repeat for multiple values"),
    screen: list[str] = typer.Option(None, "--screen", help="Design-only: screen in '<id>::<title>::<zone>::<prototype>::<purpose>' format; repeat for multiple values"),
    screen_feature: list[str] = typer.Option(None, "--screen-feature", help="Design-only: screen coverage in '<screen-id>::<priority>::<feature-name>' format; repeat for multiple values"),
    flow: list[str] = typer.Option(None, "--flow", help="Design-only: flow in '<id>::<title>::<goal>' format; repeat for multiple values"),
    flow_step: list[str] = typer.Option(None, "--flow-step", help="Design-only: flow step in '<flow-id>::<screen-id>::<action>::<result>' format; repeat for multiple values"),
    flow_alternative: list[str] = typer.Option(None, "--flow-alternative", help="Design-only: alternative path in '<flow-id>::<description>' format; repeat for multiple values"),
    nav: list[str] = typer.Option(None, "--nav", help="Design-only: navigation link in '<from-screen>::<to-screen>::<trigger>' format; repeat for multiple values"),
    platform_constraint: list[str] = typer.Option(None, "--platform-constraint", help="Design-only: platform or interaction constraint; repeat for multiple values"),
    screen_data: list[str] = typer.Option(None, "--screen-data", help="Design-only: screen data in '<screen-id>::<displayed|input>::<name>' format; repeat for multiple values"),
    stack_overview: str = typer.Option(None, "--stack-overview", help="Tech-only: short summary of the chosen stack"),
    project_type: str = typer.Option(None, "--project-type", help="Tech-only: project type, e.g. web, mobile, desktop, or API"),
    requirement: list[str] = typer.Option(None, "--requirement", help="Tech-only: technical requirement; repeat for multiple values"),
    preference: list[str] = typer.Option(None, "--preference", help="Tech-only: preferred technology or direction; repeat for multiple values"),
    tech_constraint: list[str] = typer.Option(None, "--tech-constraint", help="Tech-only: technical constraint; repeat for multiple values"),
    stack_component: list[str] = typer.Option(None, "--stack-component", help="Tech-only: component in '<slot>::<name>::<version>::<rationale>' format; repeat for multiple values"),
    library: list[str] = typer.Option(None, "--library", help="Tech-only: library in '<scope>::<name>::<version>::<purpose>' format; repeat for multiple values"),
    code_organization: str = typer.Option(None, "--code-organization", help="Tech-only: code organization in '<repo-strategy>::<source-layout>::<modularity>::<rationale>' format"),
    alternative: list[str] = typer.Option(None, "--alternative", help="Tech-only: rejected alternative in '<slot>::<option>::<reason-rejected>' format; repeat for multiple values"),
    status: str = typer.Option("validated", "--status", help="Memory record status: proposed, validated, conflicted, or obsolete"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to update"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Capture incremental non-iterative stage memory before final checkpoint."""
    project_path = Path.cwd()
    target_branch = resolve_branch_name(project_path, branch_name)
    payload = capture_stage_memory(
        project_path,
        target_branch,
        stage,
        summary=summary,
        facts=fact or [],
        decisions=decision or [],
        contracts=contract or [],
        evidence=evidence or [],
        questions=question or [],
        pending_actions=pending_action or [],
        project_name=project_name,
        system_overview=system_overview,
        audiences=audience or [],
        scenarios=scenario or [],
        pain_points=pain or [],
        feature_p1=feature_p1 or [],
        feature_p2=feature_p2 or [],
        feature_p3=feature_p3 or [],
        constraints=constraint or [],
        assumptions=assumption or [],
        next_actions=next_action or [],
        design_overview=design_overview,
        platforms=platform or [],
        zones=zone or [],
        screens=screen or [],
        screen_features=screen_feature or [],
        flows=flow or [],
        flow_steps=flow_step or [],
        flow_alternatives=flow_alternative or [],
        navigation=nav or [],
        platform_constraints=platform_constraint or [],
        screen_data=screen_data or [],
        stack_overview=stack_overview,
        project_type=project_type,
        requirements=requirement or [],
        preferences=preference or [],
        tech_constraints=tech_constraint or [],
        stack_components=stack_component or [],
        libraries=library or [],
        code_organization=code_organization,
        alternatives=alternative or [],
        status=status,
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
        console.print(f"[green]Captured stage memory:[/green] {stage}")
        console.print(
            "[cyan]Records:[/cyan] "
            f"notes={written['notes']} "
            f"facts={written['facts']} "
            f"decisions={written['decisions']} "
            f"contracts={written['contracts']} "
            f"questions={written['questions']} "
            f"pending_actions={written['pending_actions']}"
        )
        return

    console.print(
        "[red]Capture rejected.[/red] "
        f"Allowed stages: {', '.join(sorted(CAPTURE_STAGES))}"
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
    limit: int | None = typer.Option(
        None,
        "--limit",
        help="Max records per section (defaults to 3 for mvp.concept/mvp.design/mvp.tech and 5 for other stages)",
    ),
    include_obsolete: bool = typer.Option(False, "--include-obsolete", help="Include obsolete semantic records"),
    include_conflicted: bool = typer.Option(False, "--include-conflicted", help="Include conflicted semantic records"),
    full_artifact: bool = typer.Option(
        False,
        "--full-artifact",
        help="For mvp.concept, mvp.design, or mvp.tech return the full stage artifact state instead of summary-only context",
    ),
    include_history: bool = typer.Option(
        False,
        "--include-history",
        help="For mvp.concept, mvp.design, or mvp.tech include episodes and decision log in the response",
    ),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Retrieve minimal structured context for a stage."""
    project_path = Path.cwd()
    target_branch = resolve_branch_name(project_path, branch_name)
    ensure_memory_layout(project_path, target_branch)
    resolved_limit = limit if limit is not None else (3 if stage.strip().lower() in {"mvp.concept", "mvp.design", "mvp.tech"} else 5)
    payload = retrieve_memory_context(
        project_path,
        target_branch,
        stage,
        step_id=step_id,
        limit=resolved_limit,
        include_obsolete=include_obsolete,
        include_conflicted=include_conflicted,
        full_artifact=full_artifact,
        include_history=include_history,
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


def memory_start_step(
    stage: str = typer.Option(..., "--stage", help="Implementation stage: mvp.implement or feature.implement"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to update"),
    step_id: str = typer.Option(None, "--step-id", help="Optional step identifier; defaults to next executable step"),
    summary: str = typer.Option(None, "--summary", help="Optional active goal override"),
    evidence: list[str] = typer.Option(None, "--evidence", help="Supporting evidence path or note; repeat for multiple values"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Select and start an implementation step in structured memory."""
    project_path = Path.cwd()
    target_branch = resolve_branch_name(project_path, branch_name)
    ensure_memory_layout(project_path, target_branch)
    payload = start_implementation_step(
        project_path,
        target_branch,
        stage,
        step_id=step_id,
        summary=summary,
        evidence=evidence or [],
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
        console.print(f"[green]Started step:[/green] {payload['step_id']}")
        return

    console.print(
        "[red]Failed to start step.[/red] "
        f"Allowed stages: {', '.join(sorted(IMPLEMENTATION_STAGES))}"
    )
    for error in payload.get("errors", []):
        console.print(f"[red]- {error}[/red]")
    raise typer.Exit(1)


def memory_checkpoint_step(
    stage: str = typer.Option(..., "--stage", help="Implementation stage: mvp.implement or feature.implement"),
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
    project_path = Path.cwd()
    target_branch = resolve_branch_name(project_path, branch_name)
    ensure_memory_layout(project_path, target_branch)
    payload = checkpoint_implementation_step(
        project_path,
        target_branch,
        stage,
        step_id=step_id,
        summary=summary,
        tdd_phase=tdd_phase,
        red_evidence=red_evidence or [],
        green_evidence=green_evidence or [],
        refactor_note=refactor_note,
        evidence=evidence or [],
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
        console.print(f"[green]Checkpointed step:[/green] {payload['step_id']}")
        console.print(f"[cyan]TDD phase:[/cyan] {payload['tdd_phase']}")
        return

    for error in payload.get("errors", []):
        console.print(f"[red]- {error}[/red]")
    raise typer.Exit(1)


def memory_complete_step(
    stage: str = typer.Option(..., "--stage", help="Implementation stage: mvp.implement or feature.implement"),
    summary: str = typer.Option(..., "--summary", help="Completion summary for the implementation step"),
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
    project_path = Path.cwd()
    target_branch = resolve_branch_name(project_path, branch_name)
    ensure_memory_layout(project_path, target_branch)
    payload = complete_implementation_step(
        project_path,
        target_branch,
        stage,
        step_id=step_id,
        summary=summary,
        red_evidence=red_evidence or [],
        green_evidence=green_evidence or [],
        refactor_note=refactor_note,
        evidence=evidence or [],
        facts=fact or [],
        decisions=decision or [],
        contracts=contract or [],
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
        console.print(f"[green]Completed step:[/green] {payload['step_id']}")
        console.print(f"[cyan]Next step:[/cyan] {payload.get('next_step') or 'none'}")
        return

    for error in payload.get("errors", []):
        console.print(f"[red]- {error}[/red]")
    raise typer.Exit(1)


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
    memory_app.command("capture")(memory_capture)
    memory_app.command("checkpoint")(memory_checkpoint)
    memory_app.command("retrieve")(memory_retrieve)
    memory_app.command("start-step")(memory_start_step)
    memory_app.command("checkpoint-step")(memory_checkpoint_step)
    memory_app.command("complete-step")(memory_complete_step)
    memory_app.command("next-step")(memory_next_step)
    memory_app.command("register-step")(memory_register_step)
    memory_app.command("promote")(memory_promote)
    memory_app.command("learn")(memory_learn)
