from __future__ import annotations

from pathlib import Path

import typer

from madspec_cli.memory.domain.branch_layout import resolve_target_branch
from madspec_cli.shared.cli.banners import console, show_banner
from madspec_cli.shared.cli.json_output import emit_json
from madspec_cli.shared.cli.presenters import emit_error

from .application.apply_change import ApplyChangeRequest, execute as apply_change
from .application.diff_change import DiffChangeRequest, execute as diff_change
from .application.export_change import ExportChangeRequest, execute as export_change
from .application.init_change import InitChangeRequest, execute as init_change
from .application.preview_change import PreviewChangeRequest, execute as preview_change
from .application.propose_change import ProposeChangeRequest, execute as propose_change
from .application.summary_change import SummaryChangeRequest, execute as summary_change
from .application.verify_change import VerifyChangeRequest, execute as verify_change


change_app = typer.Typer(help="Canonical change bundle lifecycle for a branch")


@change_app.command("init")
def init(
    base_branch: str = typer.Option(None, "--base-branch", help="Optional base branch for the fixed bundle baseline"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to initialize"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Initialize the canonical change bundle store for the branch."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    try:
        payload = init_change(
            InitChangeRequest(project_path=project_path, branch_name=target_branch, base_branch=base_branch)
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Change store ready[/green] branch={payload['branch']}")
    console.print(f"[cyan]Base branch:[/cyan] {payload['base_branch']}")
    console.print(f"[cyan]Base revision:[/cyan] {payload['base_revision']}")
    console.print(f"[cyan]Bundle ID:[/cyan] {payload['bundle_id']}")


@change_app.command("propose")
def propose(
    title: str = typer.Option(..., "--title", help="Human-readable title for the bundle"),
    summary: str = typer.Option(..., "--summary", help="Narrative summary of the change"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Create a pending change bundle proposal."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    try:
        payload = propose_change(
            ProposeChangeRequest(
                project_path=project_path,
                branch_name=target_branch,
                title=title,
                summary=summary,
                requested_by="change.propose",
            )
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Created proposal:[/green] {payload['proposalId']}")
    console.print(f"[cyan]Bundle:[/cyan] {payload['bundleId']}")
    console.print(f"[cyan]Changed fields:[/cyan] {', '.join(payload['diff']['changedFields']) or 'none'}")


@change_app.command("diff")
def diff(
    proposal_id: str = typer.Option(None, "--proposal-id", help="Optional proposal identifier"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Show the computed delta against the fixed baseline."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    try:
        payload = diff_change(
            DiffChangeRequest(project_path=project_path, branch_name=target_branch, proposal_id=proposal_id)
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[cyan]Branch:[/cyan] {payload['branch']}")
    console.print(f"[cyan]Base branch:[/cyan] {payload['baseline']['base_branch']}")
    console.print(f"[cyan]Changed files:[/cyan] {len(payload['git_diff']['files'])}")
    console.print(f"[cyan]Changed snapshots:[/cyan] {len(payload['memory_diff']['changedStageSnapshots'])}")


@change_app.command("preview")
def preview(
    proposal_id: str = typer.Option(..., "--proposal-id", help="Pending proposal identifier"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Show the full proposal payload before apply."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    try:
        payload = preview_change(
            PreviewChangeRequest(project_path=project_path, branch_name=target_branch, proposal_id=proposal_id)
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[cyan]Proposal:[/cyan] {payload['proposalId']}")
    console.print(f"[cyan]Bundle:[/cyan] {payload['bundleId']}")
    console.print(f"[cyan]Warnings:[/cyan] {len(payload.get('warnings', []))}")


@change_app.command("apply")
def apply(
    proposal_id: str = typer.Option(..., "--proposal-id", help="Pending proposal identifier"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Apply a pending change bundle proposal."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    try:
        payload = apply_change(
            ApplyChangeRequest(project_path=project_path, branch_name=target_branch, proposal_id=proposal_id)
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Applied proposal:[/green] {proposal_id}")
    console.print(f"[cyan]Revision:[/cyan] {payload['revision']}")


@change_app.command("export")
def export(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to export"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Export the active change bundle into a portable package."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    try:
        payload = export_change(
            ExportChangeRequest(project_path=project_path, branch_name=target_branch)
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Exported bundle:[/green] {payload['bundleId']}")
    console.print(f"[cyan]Export dir:[/cyan] {payload['export_dir']}")


@change_app.command("verify")
def verify(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to verify"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Verify the active bundle against the current branch state."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    try:
        result = verify_change(
            VerifyChangeRequest(project_path=project_path, branch_name=target_branch)
        )
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    payload = result.to_payload()
    if json_output:
        emit_json(payload)
        if not result.valid:
            raise typer.Exit(1)
        return
    show_banner()
    console.print(f"[cyan]Valid:[/cyan] {'yes' if payload['valid'] else 'no'}")
    console.print(f"[cyan]Drift items:[/cyan] {len(payload['drift'])}")
    if not payload["valid"]:
        raise typer.Exit(1)


@change_app.command("summary")
def summary(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Show the applied change bundle and its high-level highlights."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    try:
        payload = summary_change(
            SummaryChangeRequest(project_path=project_path, branch_name=target_branch)
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    bundle = payload["bundle"]
    console.print(f"[cyan]Bundle:[/cyan] {bundle['bundleId']}")
    console.print(f"[cyan]Title:[/cyan] {bundle['title']}")
    console.print(f"[cyan]Changed files:[/cyan] {len(bundle['gitDiff']['files'])}")


def register(app: typer.Typer) -> None:
    app.add_typer(change_app, name="change")
