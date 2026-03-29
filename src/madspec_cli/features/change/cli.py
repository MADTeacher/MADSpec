from __future__ import annotations

from pathlib import Path

import typer

from madspec_cli.memory.application.resolve_branch import resolve_branch
from madspec_cli.shared.cli.banners import console
from madspec_cli.shared.cli.command_runner import execute_cli_action

from .application.apply_change import ApplyChangeRequest, execute as apply_change
from .application.diff_change import DiffChangeRequest, execute as diff_change
from .application.export_change import ExportChangeRequest, execute as export_change
from .application.init_change import InitChangeRequest, execute as init_change
from .application.preview_change import PreviewChangeRequest, execute as preview_change
from .application.propose_change import ProposeChangeRequest, execute as propose_change
from .application.summary_change import SummaryChangeRequest, execute as summary_change
from .application.verify_change import VerifyChangeRequest, execute as verify_change


change_app = typer.Typer(help="Canonical change bundle lifecycle for a branch")


def _resolve_project_branch(branch_name: str | None) -> tuple[Path, str]:
    project_path = Path.cwd()
    return project_path, resolve_branch(project_path, branch_name)


def _print_init_payload(payload: dict[str, object]) -> None:
    console.print(f"[green]Change store ready[/green] branch={payload['branch']}")
    console.print(f"[cyan]Base branch:[/cyan] {payload['base_branch']}")
    console.print(f"[cyan]Base revision:[/cyan] {payload['base_revision']}")
    console.print(f"[cyan]Bundle ID:[/cyan] {payload['bundle_id']}")


def _print_propose_payload(payload: dict[str, object]) -> None:
    console.print(f"[green]Created proposal:[/green] {payload['proposalId']}")
    console.print(f"[cyan]Bundle:[/cyan] {payload['bundleId']}")
    console.print(f"[cyan]Changed fields:[/cyan] {', '.join(payload['diff']['changedFields']) or 'none'}")


def _print_diff_payload(payload: dict[str, object]) -> None:
    console.print(f"[cyan]Branch:[/cyan] {payload['branch']}")
    console.print(f"[cyan]Base branch:[/cyan] {payload['baseline']['base_branch']}")
    console.print(f"[cyan]Changed files:[/cyan] {len(payload['git_diff']['files'])}")
    console.print(f"[cyan]Changed snapshots:[/cyan] {len(payload['memory_diff']['changedStageSnapshots'])}")


def _print_preview_payload(payload: dict[str, object]) -> None:
    console.print(f"[cyan]Proposal:[/cyan] {payload['proposalId']}")
    console.print(f"[cyan]Bundle:[/cyan] {payload['bundleId']}")
    console.print(f"[cyan]Warnings:[/cyan] {len(payload.get('warnings', []))}")


def _print_apply_payload(payload: dict[str, object], proposal_id: str) -> None:
    console.print(f"[green]Applied proposal:[/green] {proposal_id}")
    console.print(f"[cyan]Revision:[/cyan] {payload['revision']}")


def _print_export_payload(payload: dict[str, object]) -> None:
    console.print(f"[green]Exported bundle:[/green] {payload['bundleId']}")
    console.print(f"[cyan]Export dir:[/cyan] {payload['export_dir']}")


def _print_verify_payload(payload: dict[str, object]) -> None:
    console.print(f"[cyan]Valid:[/cyan] {'yes' if payload['valid'] else 'no'}")
    console.print(f"[cyan]Drift items:[/cyan] {len(payload['drift'])}")


def _print_summary_payload(payload: dict[str, object]) -> None:
    bundle = payload["bundle"]
    console.print(f"[cyan]Bundle:[/cyan] {bundle['bundleId']}")
    console.print(f"[cyan]Title:[/cyan] {bundle['title']}")
    console.print(f"[cyan]Changed files:[/cyan] {len(bundle['gitDiff']['files'])}")


@change_app.command("init")
def init(
    base_branch: str = typer.Option(None, "--base-branch", help="Optional base branch for the fixed bundle baseline"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to initialize"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Initialize the canonical change bundle store for the branch."""
    project_path, target_branch = _resolve_project_branch(branch_name)
    execute_cli_action(
        lambda: init_change(
            InitChangeRequest(project_path=project_path, branch_name=target_branch, base_branch=base_branch)
        ).to_payload(),
        json_output=json_output,
        text_output=_print_init_payload,
    )


@change_app.command("propose")
def propose(
    title: str = typer.Option(..., "--title", help="Human-readable title for the bundle"),
    summary: str = typer.Option(..., "--summary", help="Narrative summary of the change"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Create a pending change bundle proposal."""
    project_path, target_branch = _resolve_project_branch(branch_name)
    execute_cli_action(
        lambda: propose_change(
            ProposeChangeRequest(
                project_path=project_path,
                branch_name=target_branch,
                title=title,
                summary=summary,
                requested_by="change.propose",
            )
        ).to_payload(),
        json_output=json_output,
        text_output=_print_propose_payload,
    )


@change_app.command("diff")
def diff(
    proposal_id: str = typer.Option(None, "--proposal-id", help="Optional proposal identifier"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Show the computed delta against the fixed baseline."""
    project_path, target_branch = _resolve_project_branch(branch_name)
    execute_cli_action(
        lambda: diff_change(
            DiffChangeRequest(project_path=project_path, branch_name=target_branch, proposal_id=proposal_id)
        ).to_payload(),
        json_output=json_output,
        text_output=_print_diff_payload,
    )


@change_app.command("preview")
def preview(
    proposal_id: str = typer.Option(..., "--proposal-id", help="Pending proposal identifier"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Show the full proposal payload before apply."""
    project_path, target_branch = _resolve_project_branch(branch_name)
    execute_cli_action(
        lambda: preview_change(
            PreviewChangeRequest(project_path=project_path, branch_name=target_branch, proposal_id=proposal_id)
        ).to_payload(),
        json_output=json_output,
        text_output=_print_preview_payload,
    )


@change_app.command("apply")
def apply(
    proposal_id: str = typer.Option(..., "--proposal-id", help="Pending proposal identifier"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Apply a pending change bundle proposal."""
    project_path, target_branch = _resolve_project_branch(branch_name)
    execute_cli_action(
        lambda: apply_change(
            ApplyChangeRequest(project_path=project_path, branch_name=target_branch, proposal_id=proposal_id)
        ).to_payload(),
        json_output=json_output,
        text_output=lambda payload: _print_apply_payload(payload, proposal_id),
    )


@change_app.command("export")
def export(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to export"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Export the active change bundle into a portable package."""
    project_path, target_branch = _resolve_project_branch(branch_name)
    execute_cli_action(
        lambda: export_change(
            ExportChangeRequest(project_path=project_path, branch_name=target_branch)
        ).to_payload(),
        json_output=json_output,
        text_output=_print_export_payload,
    )


@change_app.command("verify")
def verify(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to verify"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Verify the active bundle against the current branch state."""
    project_path, target_branch = _resolve_project_branch(branch_name)
    execute_cli_action(
        lambda: verify_change(
            VerifyChangeRequest(project_path=project_path, branch_name=target_branch)
        ).to_payload(),
        json_output=json_output,
        text_output=_print_verify_payload,
        should_fail=lambda payload: not payload["valid"],
    )


@change_app.command("summary")
def summary(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Show the applied change bundle and its high-level highlights."""
    project_path, target_branch = _resolve_project_branch(branch_name)
    execute_cli_action(
        lambda: summary_change(
            SummaryChangeRequest(project_path=project_path, branch_name=target_branch)
        ).to_payload(),
        json_output=json_output,
        text_output=_print_summary_payload,
    )


def register(app: typer.Typer) -> None:
    app.add_typer(change_app, name="change")
