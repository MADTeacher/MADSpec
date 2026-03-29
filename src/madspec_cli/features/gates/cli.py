from __future__ import annotations

from pathlib import Path

import typer

from madspec_cli.memory.application.resolve_branch import resolve_branch
from madspec_cli.shared.cli.banners import console
from madspec_cli.shared.cli.command_runner import execute_cli_action
from madspec_cli.shared.cli.toon_output import ensure_structured_output_mode

from .application.apply_waiver import ApplyWaiverRequest, execute as apply_waiver
from .application.explain_gate import ExplainGateRequest, execute as explain_gate
from .application.propose_waiver import ProposeWaiverRequest, execute as propose_waiver
from .application.run_gate import RunGateRequest, execute as run_gate
from .application.status_gate import GateStatusRequest, execute as gate_status


gate_app = typer.Typer(help="Quality gate evaluation, state transitions, and waivers")
review_app = typer.Typer(help="Review-related quality gate status")
security_app = typer.Typer(help="Security-related quality gate status")


def _resolve_project_branch(branch_name: str | None) -> tuple[Path, str]:
    project_path = Path.cwd()
    return project_path, resolve_branch(project_path, branch_name)


def _print_gate_summary(payload: dict[str, object]) -> None:
    console.print(f"[cyan]Stage:[/cyan] {payload['stage']}")
    console.print(f"[cyan]Operation:[/cyan] {payload['operation']}")
    console.print(f"[cyan]Overall:[/cyan] {payload['overall_status']}")
    console.print(f"[cyan]Blocking:[/cyan] {payload['blocking_count']}")
    console.print(f"[cyan]Warnings:[/cyan] {payload['warning_count']}")
    console.print(f"[cyan]Pending:[/cyan] {payload['pending_count']}")
    console.print(f"[cyan]Active waivers:[/cyan] {len(payload.get('active_waivers', []))}")
    for gate in payload.get("gates", [])[:12]:
        console.print(f"- [{gate['status']}] {gate['family']} {gate['message']}")


def _print_status_payload(payload: dict[str, object], *, target_branch: str) -> None:
    console.print(f"[cyan]Branch:[/cyan] {target_branch}")
    _print_gate_summary(payload)


def _print_explain_payload(payload: dict[str, object], *, target_branch: str) -> None:
    console.print(f"[cyan]Branch:[/cyan] {target_branch}")
    _print_gate_summary(payload)
    console.print(f"[cyan]History events:[/cyan] {len(payload.get('history', []))}")
    console.print(f"[cyan]Related proposals:[/cyan] {len(payload.get('proposals', []))}")


def _print_waiver_payload(payload: dict[str, object]) -> None:
    if not payload.get("accepted"):
        console.print(f"[red]{payload['error']}[/red]")
        return
    console.print(f"[green]Created waiver proposal:[/green] {payload['proposalId']}")
    console.print(f"[cyan]Gate:[/cyan] {payload['gateId']}")
    console.print(f"[cyan]Reason:[/cyan] {payload['reason']}")


def _print_apply_waiver_payload(payload: dict[str, object], *, proposal_id: str) -> None:
    if not payload.get("accepted"):
        console.print(f"[red]{payload['error']}[/red]")
        return
    console.print(f"[green]Applied waiver proposal:[/green] {proposal_id}")
    console.print(f"[cyan]Revision:[/cyan] {payload['revision']}")


@gate_app.command("status")
def status(
    stage: str = typer.Option(None, "--stage", help="Target stage: mvp.plan, feature.plan, mvp.implement, feature.implement, review, or security"),
    operation: str = typer.Option("validate", "--operation", help="Transition or validation operation context"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    step_id: str = typer.Option(None, "--step-id", help="Optional step identifier"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
    toon_output: bool = typer.Option(False, "--toon-output", help="Emit TOON for agent-oriented structured context"),
) -> None:
    """Show the current quality gate status without changing state."""
    ensure_structured_output_mode(json_output=json_output, toon_output=toon_output)
    project_path, target_branch = _resolve_project_branch(branch_name)
    execute_cli_action(
        lambda: gate_status(
            GateStatusRequest(
                project_path=project_path,
                branch_name=target_branch,
                stage=stage,
                operation=operation,
                step_id=step_id,
                overrides={},
            )
        ).to_payload(),
        json_output=json_output,
        toon_output=toon_output,
        text_output=lambda payload: _print_status_payload(payload, target_branch=target_branch),
    )


@gate_app.command("run")
def run(
    stage: str = typer.Option(..., "--stage", help="Target stage: mvp.plan, feature.plan, mvp.implement, feature.implement, review, or security"),
    operation: str = typer.Option("validate", "--operation", help="Transition or validation operation context"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    step_id: str = typer.Option(None, "--step-id", help="Optional step identifier"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Evaluate gates for a specific transition context and record an audit event."""
    project_path, target_branch = _resolve_project_branch(branch_name)
    execute_cli_action(
        lambda: run_gate(
            RunGateRequest(
                project_path=project_path,
                branch_name=target_branch,
                stage=stage,
                operation=operation,
                step_id=step_id,
                overrides={},
            )
        ).to_payload(),
        json_output=json_output,
        text_output=lambda payload: _print_status_payload(payload, target_branch=target_branch),
        should_fail=lambda payload: payload["overall_status"] == "blocked",
    )


@gate_app.command("explain")
def explain(
    stage: str = typer.Option(None, "--stage", help="Target stage"),
    operation: str = typer.Option("validate", "--operation", help="Transition or validation operation context"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    step_id: str = typer.Option(None, "--step-id", help="Optional step identifier"),
    gate_id: str = typer.Option(None, "--gate-id", help="Optional gate identifier to explain"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
    toon_output: bool = typer.Option(False, "--toon-output", help="Emit TOON for agent-oriented structured context"),
) -> None:
    """Explain gate results together with relevant waiver and history context."""
    ensure_structured_output_mode(json_output=json_output, toon_output=toon_output)
    project_path, target_branch = _resolve_project_branch(branch_name)
    execute_cli_action(
        lambda: explain_gate(
            ExplainGateRequest(
                project_path=project_path,
                branch_name=target_branch,
                stage=stage,
                operation=operation,
                step_id=step_id,
                gate_id=gate_id,
            )
        ).to_payload(),
        json_output=json_output,
        toon_output=toon_output,
        text_output=lambda payload: _print_explain_payload(payload, target_branch=target_branch),
    )


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
    project_path, target_branch = _resolve_project_branch(branch_name)
    execute_cli_action(
        lambda: propose_waiver(
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
        ).to_payload(),
        json_output=json_output,
        text_output=_print_waiver_payload,
        should_fail=lambda payload: not payload.get("accepted"),
    )


@gate_app.command("apply-waiver")
def apply_waiver_command(
    proposal_id: str = typer.Option(..., "--proposal-id", help="Pending waiver proposal identifier"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Apply a pending waiver proposal."""
    project_path, target_branch = _resolve_project_branch(branch_name)
    execute_cli_action(
        lambda: apply_waiver(
            ApplyWaiverRequest(
                project_path=project_path,
                branch_name=target_branch,
                proposal_id=proposal_id,
            )
        ).to_payload(),
        json_output=json_output,
        text_output=lambda payload: _print_apply_waiver_payload(payload, proposal_id=proposal_id),
        should_fail=lambda payload: not payload.get("accepted"),
    )


@review_app.command("status")
def review_status(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    operation: str = typer.Option("validate", "--operation", help="Transition or validation operation context"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
    toon_output: bool = typer.Option(False, "--toon-output", help="Emit TOON for agent-oriented structured context"),
) -> None:
    """Alias for `madspec gate status --stage review`."""
    status(
        stage="review",
        operation=operation,
        branch_name=branch_name,
        step_id=None,
        json_output=json_output,
        toon_output=toon_output,
    )


@security_app.command("status")
def security_status(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    operation: str = typer.Option("validate", "--operation", help="Transition or validation operation context"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
    toon_output: bool = typer.Option(False, "--toon-output", help="Emit TOON for agent-oriented structured context"),
) -> None:
    """Alias for `madspec gate status --stage security`."""
    status(
        stage="security",
        operation=operation,
        branch_name=branch_name,
        step_id=None,
        json_output=json_output,
        toon_output=toon_output,
    )


def register(app: typer.Typer) -> None:
    app.add_typer(gate_app, name="gate")
    app.add_typer(review_app, name="review")
    app.add_typer(security_app, name="security")
