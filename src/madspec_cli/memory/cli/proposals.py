from __future__ import annotations

import json
from pathlib import Path

import typer

from madspec_cli.shared.cli.banners import console, show_banner
from madspec_cli.shared.cli.json_output import emit_json

from ..application.proposals import (
    ApplyProposalRequest,
    ListProposalsRequest,
    PreviewProposalRequest,
    PublishProposalRequest,
    apply,
    list_proposals,
    preview,
    publish,
)
from ..domain.branch_layout import resolve_target_branch


proposals_app = typer.Typer(help="Proposal-based runtime commits for claimed work items")


@proposals_app.command("publish")
def publish_proposal_command(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to update"),
    proposal_type: str = typer.Option(..., "--type", help="Proposal type"),
    session_key: str = typer.Option(..., "--session-key", help="Claimed runtime session key"),
    subagent_id: str = typer.Option(..., "--subagent-id", help="Subagent identifier that owns the claim"),
    base_revision: int = typer.Option(..., "--base-revision", help="Runtime revision the proposal is based on"),
    payload_json: str = typer.Option(..., "--payload-json", help="JSON object describing the typed proposal payload"),
    target_scope_json: str = typer.Option("{}", "--target-scope-json", help="JSON object describing proposal scope"),
    conflict_hints_json: str = typer.Option("{}", "--conflict-hints-json", help="JSON object with conflict hints"),
    task_id: str = typer.Option(None, "--task-id", help="Optional task identifier override"),
    work_item_id: str = typer.Option(None, "--work-item-id", help="Optional work item identifier override"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    payload = publish(
        PublishProposalRequest(
            project_path=project_path,
            branch_name=target_branch,
            proposal_type=proposal_type,
            session_key=session_key,
            subagent_id=subagent_id,
            base_revision=base_revision,
            payload=_parse_json_object(payload_json, option_name="--payload-json"),
            target_scope=_parse_json_object(target_scope_json, option_name="--target-scope-json"),
            conflict_hints=_parse_json_object(conflict_hints_json, option_name="--conflict-hints-json"),
            task_id=task_id,
            work_item_id=work_item_id,
        )
    ).to_payload()
    if json_output:
        emit_json(payload)
        return
    proposal = payload["proposal"]
    show_banner()
    console.print(f"[green]Published proposal:[/green] {proposal['proposal_id']}")
    console.print(f"[cyan]Type:[/cyan] {proposal['proposal_type']}")
    console.print(f"[cyan]Work item:[/cyan] {proposal['work_item_id']}")


@proposals_app.command("list")
def list_proposals_command(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    task_id: str = typer.Option(None, "--task-id", help="Optional task filter"),
    work_item_id: str = typer.Option(None, "--work-item-id", help="Optional work item filter"),
    session_key: str = typer.Option(None, "--session-key", help="Optional session filter"),
    status: list[str] = typer.Option(None, "--status", help="Optional proposal status filter"),
    proposal_type: list[str] = typer.Option(None, "--type", help="Optional proposal type filter"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    payload = list_proposals(
        ListProposalsRequest(
            project_path=project_path,
            branch_name=target_branch,
            task_id=task_id,
            work_item_id=work_item_id,
            session_key=session_key,
            statuses=status or None,
            proposal_types=proposal_type or None,
        )
    ).to_payload()
    if json_output:
        emit_json(payload)
        return
    show_banner()
    for item in payload["proposals"]:
        console.print(
            f"- `{item['proposal_id']}` [{item['status']}] {item['proposal_type']} work-item={item['work_item_id']} revision={item['base_revision']}"
        )


@proposals_app.command("preview")
def preview_proposal_command(
    proposal_id: str = typer.Option(..., "--proposal-id", help="Proposal identifier"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    payload = preview(
        PreviewProposalRequest(project_path=Path.cwd(), proposal_id=proposal_id)
    ).to_payload()
    if json_output:
        emit_json(payload)
        return
    proposal = payload["proposal"]
    show_banner()
    console.print(f"[cyan]Proposal:[/cyan] {proposal['proposal_id']}")
    console.print(f"[cyan]Type:[/cyan] {proposal['proposal_type']}")
    console.print(f"[cyan]Status:[/cyan] {proposal['status']}")
    console.print(
        f"[cyan]Revision:[/cyan] base={proposal['base_revision']} current={payload['current_revision']}"
    )
    console.print(f"[cyan]Ownership valid:[/cyan] {payload['ownership']['valid']}")


@proposals_app.command("apply")
def apply_proposal_command(
    proposal_id: str = typer.Option(..., "--proposal-id", help="Proposal identifier"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    result = apply(
        ApplyProposalRequest(project_path=Path.cwd(), proposal_id=proposal_id)
    )
    payload = result.to_payload()
    if json_output:
        emit_json(payload)
        if not payload.get("accepted", False):
            raise typer.Exit(1)
        return
    proposal = payload["proposal"]
    show_banner()
    if payload.get("accepted"):
        console.print(f"[green]Applied proposal:[/green] {proposal['proposal_id']}")
        return
    console.print(f"[red]Proposal apply failed.[/red] {proposal['proposal_id']}")
    console.print(f"[cyan]Status:[/cyan] {proposal['status']}")
    apply_summary = proposal.get("apply_summary") or {}
    if apply_summary.get("reason"):
        console.print(f"[red]- {apply_summary['reason']}[/red]")
    raise typer.Exit(1)


def register(memory_app: typer.Typer) -> None:
    memory_app.add_typer(proposals_app, name="proposals")


def _parse_json_object(raw: str, *, option_name: str) -> dict[str, object]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"{option_name} must be valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise typer.BadParameter(f"{option_name} must decode to a JSON object")
    return payload
