from __future__ import annotations

from pathlib import Path

import typer

from madspec_cli.memory.domain.branch_layout import resolve_target_branch
from madspec_cli.shared.cli.banners import console, show_banner
from madspec_cli.shared.cli.json_output import emit_json
from madspec_cli.shared.cli.presenters import emit_error

from .application.apply_waiver import ApplyWaiverRequest, execute as apply_waiver
from .application.explain_gate import ExplainGateRequest, execute as explain_gate
from .application.propose_waiver import ProposeWaiverRequest, execute as propose_waiver
from .application.run_gate import RunGateRequest, execute as run_gate
from .application.status_gate import GateStatusRequest, execute as gate_status


gate_app = typer.Typer(help="Quality gate evaluation, state transitions, and waivers")
review_app = typer.Typer(help="Review-related quality gate status")
security_app = typer.Typer(help="Security-related quality gate status")


def _print_gate_summary(payload: dict[str, object]) -> None:
    console.print(f"[cyan]Stage:[/cyan] {payload['stage']}")
    console.print(f"[cyan]Operation:[/cyan] {payload['operation']}")
    console.print(f"[cyan]Overall:[/cyan] {payload['overall_status']}")
    console.print(f"[cyan]Blocking:[/cyan] {payload['blocking_count']}")
    console.print(f"[cyan]Warnings:[/cyan] {payload['warning_count']}")
    console.print(f"[cyan]Pending:[/cyan] {payload['pending_count']}")
    console.print(f"[cyan]Active waivers:[/cyan] {len(payload.get('active_waivers', []))}")
    for gate in payload.get("gates", [])[:12]:
        console.print(
            f"- [{gate['status']}] {gate['family']} {gate['message']}"
        )


@gate_app.command("status")
def status(
    stage: str = typer.Option(None, "--stage", help="Target stage: mvp.plan, feature.plan, mvp.implement, feature.implement, review, or security"),
    operation: str = typer.Option("validate", "--operation", help="Transition or validation operation context"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    step_id: str = typer.Option(None, "--step-id", help="Optional step identifier"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Show the current quality gate status without changing state."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    try:
        payload = gate_status(
            GateStatusRequest(
                project_path=project_path,
                branch_name=target_branch,
                stage=stage,
                operation=operation,
                step_id=step_id,
                overrides={},
            )
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[cyan]Branch:[/cyan] {target_branch}")
    _print_gate_summary(payload)


@gate_app.command("run")
def run(
    stage: str = typer.Option(..., "--stage", help="Target stage: mvp.plan, feature.plan, mvp.implement, feature.implement, review, or security"),
    operation: str = typer.Option("validate", "--operation", help="Transition or validation operation context"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    step_id: str = typer.Option(None, "--step-id", help="Optional step identifier"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Evaluate gates for a specific transition context and record an audit event."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    try:
        payload = run_gate(
            RunGateRequest(
                project_path=project_path,
                branch_name=target_branch,
                stage=stage,
                operation=operation,
                step_id=step_id,
                overrides={},
            )
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        if payload["overall_status"] == "blocked":
            raise typer.Exit(1)
        return
    show_banner()
    console.print(f"[cyan]Branch:[/cyan] {target_branch}")
    _print_gate_summary(payload)
    if payload["overall_status"] == "blocked":
        raise typer.Exit(1)


@gate_app.command("explain")
def explain(
    stage: str = typer.Option(None, "--stage", help="Target stage"),
    operation: str = typer.Option("validate", "--operation", help="Transition or validation operation context"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    step_id: str = typer.Option(None, "--step-id", help="Optional step identifier"),
    gate_id: str = typer.Option(None, "--gate-id", help="Optional gate identifier to explain"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Explain gate results together with relevant waiver and history context."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    try:
        payload = explain_gate(
            ExplainGateRequest(
                project_path=project_path,
                branch_name=target_branch,
                stage=stage,
                operation=operation,
                step_id=step_id,
                gate_id=gate_id,
            )
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[cyan]Branch:[/cyan] {target_branch}")
    _print_gate_summary(payload)
    console.print(f"[cyan]History events:[/cyan] {len(payload.get('history', []))}")
    console.print(f"[cyan]Related proposals:[/cyan] {len(payload.get('proposals', []))}")


@gate_app.command("propose-waiver")
def propose_waiver_command(
    gate_id: str = typer.Option(..., "--gate-id", help="Gate identifier from gate status/explain output"),
    reason: str = typer.Option(..., "--reason", help="Human-readable justification for the waiver"),
    stage: str = typer.Option(None, "--stage", help="Target stage"),
    operation: str = typer.Option("validate", "--operation", help="Transition or validation operation context"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    step_id: str = typer.Option(None, "--step-id", help="Optional step identifier"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Create a pending waiver proposal for a waivable gate."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    try:
        payload = propose_waiver(
            ProposeWaiverRequest(
                project_path=project_path,
                branch_name=target_branch,
                stage=stage,
                operation=operation,
                step_id=step_id,
                gate_id=gate_id,
                reason=reason,
                requested_by="gate.propose-waiver",
            )
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        if not payload.get("accepted"):
            raise typer.Exit(1)
        return
    show_banner()
    if not payload.get("accepted"):
        console.print(f"[red]{payload['error']}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]Created waiver proposal:[/green] {payload['proposalId']}")
    console.print(f"[cyan]Gate:[/cyan] {payload['gateId']}")
    console.print(f"[cyan]Reason:[/cyan] {payload['reason']}")


@gate_app.command("apply-waiver")
def apply_waiver_command(
    proposal_id: str = typer.Option(..., "--proposal-id", help="Pending waiver proposal identifier"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Apply a pending waiver proposal."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    try:
        payload = apply_waiver(
            ApplyWaiverRequest(
                project_path=project_path,
                branch_name=target_branch,
                proposal_id=proposal_id,
            )
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        if not payload.get("accepted"):
            raise typer.Exit(1)
        return
    show_banner()
    if not payload.get("accepted"):
        console.print(f"[red]{payload['error']}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]Applied waiver proposal:[/green] {proposal_id}")
    console.print(f"[cyan]Revision:[/cyan] {payload['revision']}")


@review_app.command("status")
def review_status(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    operation: str = typer.Option("validate", "--operation", help="Transition or validation operation context"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Alias for `madspec gate status --stage review`."""
    status(stage="review", operation=operation, branch_name=branch_name, step_id=None, json_output=json_output)


@security_app.command("status")
def security_status(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    operation: str = typer.Option("validate", "--operation", help="Transition or validation operation context"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Alias for `madspec gate status --stage security`."""
    status(stage="security", operation=operation, branch_name=branch_name, step_id=None, json_output=json_output)


def register(app: typer.Typer) -> None:
    app.add_typer(gate_app, name="gate")
    app.add_typer(review_app, name="review")
    app.add_typer(security_app, name="security")
