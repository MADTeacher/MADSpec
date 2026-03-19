from __future__ import annotations

from pathlib import Path

import typer

from madspec_cli.shared.cli.banners import console, show_banner
from madspec_cli.shared.cli.json_output import emit_json
from madspec_cli.shared.cli.presenters import emit_error

from ..application.branch_compare import CompareBranchesRequest, execute as compare_branch_memory
from ..application.branch_merge import (
    MergeBranchesRequest,
    PreviewBranchMergeRequest,
    PromoteBranchKnowledgeRequest,
    ProposeBranchMergeRequest,
    ResolveBranchConflictRequest,
    merge_branches,
    preview_merge,
    promote_branch_knowledge,
    propose_merge,
    resolve_conflict,
)
from ..domain.branch_layout import resolve_target_branch


def compare_branches(
    source_branch: str = typer.Option(..., "--source-branch", help="Branch to merge from"),
    target_branch: str = typer.Option(None, "--target-branch", help="Target branch; defaults to the current branch"),
    base_branch: str = typer.Option(None, "--base-branch", help="Optional common base branch"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Compare branch memory state before a merge."""
    project_path = Path.cwd()
    resolved_target = resolve_target_branch(project_path, target_branch)
    try:
        payload = compare_branch_memory(
            CompareBranchesRequest(
                project_path=project_path,
                source_branch=source_branch,
                target_branch=resolved_target,
                base_branch=base_branch,
            )
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return

    show_banner()
    console.print(f"[cyan]Source:[/cyan] {payload['sourceBranch']}")
    console.print(f"[cyan]Target:[/cyan] {payload['targetBranch']}")
    console.print(f"[cyan]Base:[/cyan] {payload['baseBranch'] or 'none'}")
    console.print(f"[cyan]Auto actions:[/cyan] {payload['summary']['autoActionCount']}")
    console.print(f"[cyan]Conflicts:[/cyan] {payload['summary']['conflictCount']}")


def propose_merge_command(
    source_branch: str = typer.Option(..., "--source-branch", help="Branch to merge from"),
    target_branch: str = typer.Option(None, "--target-branch", help="Target branch; defaults to the current branch"),
    base_branch: str = typer.Option(None, "--base-branch", help="Optional common base branch"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Create a merge proposal from one branch memory state into another."""
    project_path = Path.cwd()
    resolved_target = resolve_target_branch(project_path, target_branch)
    try:
        payload = propose_merge(
            ProposeBranchMergeRequest(
                project_path=project_path,
                source_branch=source_branch,
                target_branch=resolved_target,
                base_branch=base_branch,
                requested_by="memory.propose-merge",
            )
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return

    show_banner()
    console.print(f"[green]Created merge proposal:[/green] {payload['proposalId']}")
    console.print(f"[cyan]Can apply:[/cyan] {'yes' if payload['canApply'] else 'no'}")


def preview_merge_command(
    proposal_id: str = typer.Option(..., "--proposal-id", help="Merge proposal identifier"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Show a merge proposal preview without changing state."""
    project_path = Path.cwd()
    try:
        payload = preview_merge(
            PreviewBranchMergeRequest(project_path=project_path, proposal_id=proposal_id)
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return

    show_banner()
    console.print(f"[cyan]Proposal:[/cyan] {payload['proposalId']}")
    console.print(f"[cyan]Unresolved conflicts:[/cyan] {len(payload['unresolvedConflicts'])}")


def resolve_conflict_command(
    proposal_id: str = typer.Option(..., "--proposal-id", help="Merge proposal identifier"),
    conflict_id: str = typer.Option(..., "--conflict-id", help="Conflict identifier to resolve"),
    resolution: str = typer.Option(..., "--resolution", help="Resolution: keep_target, take_source, take_base, union"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Resolve a merge conflict inside a proposal."""
    project_path = Path.cwd()
    try:
        payload = resolve_conflict(
            ResolveBranchConflictRequest(
                project_path=project_path,
                proposal_id=proposal_id,
                conflict_id=conflict_id,
                resolution=resolution,
            )
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return

    show_banner()
    console.print(f"[green]Updated proposal:[/green] {payload['proposalId']}")
    console.print(f"[cyan]Unresolved conflicts:[/cyan] {len(payload['unresolvedConflicts'])}")


def merge_branches_command(
    proposal_id: str = typer.Option(..., "--proposal-id", help="Merge proposal identifier"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Apply a previously previewed merge proposal."""
    project_path = Path.cwd()
    payload = merge_branches(
        MergeBranchesRequest(project_path=project_path, proposal_id=proposal_id)
    ).to_payload()
    if json_output:
        emit_json(payload)
        if not payload.get("applied"):
            raise typer.Exit(1)
        return

    show_banner()
    if not payload.get("applied"):
        console.print(f"[red]{payload['error']}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]Applied merge proposal:[/green] {payload['proposalId']}")
    console.print(f"[cyan]Revision:[/cyan] {payload['revision']}")


def promote_branch_knowledge_command(
    source_branch: str = typer.Option(..., "--source-branch", help="Branch to promote validated knowledge from"),
    record_ids: list[str] = typer.Option(None, "--record-id", help="Optional validated record ids to promote"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Promote validated branch knowledge into project-level memory."""
    project_path = Path.cwd()
    try:
        payload = promote_branch_knowledge(
            PromoteBranchKnowledgeRequest(
                project_path=project_path,
                source_branch=source_branch,
                record_ids=record_ids or [],
            )
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return

    show_banner()
    console.print(f"[green]Promoted records:[/green] {len(payload['promoted'])}")
    console.print(f"[cyan]Skipped:[/cyan] {len(payload['skippedRecordIds'])}")


def register(memory_app: typer.Typer) -> None:
    memory_app.command("compare-branches")(compare_branches)
    memory_app.command("propose-merge")(propose_merge_command)
    memory_app.command("preview-merge")(preview_merge_command)
    memory_app.command("resolve-conflict")(resolve_conflict_command)
    memory_app.command("merge-branches")(merge_branches_command)
    memory_app.command("promote-branch-knowledge")(promote_branch_knowledge_command)
