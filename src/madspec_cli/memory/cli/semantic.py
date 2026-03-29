from __future__ import annotations

from pathlib import Path

import typer

from madspec_cli.shared.cli.banners import console, show_banner
from madspec_cli.shared.cli.file_input import ArgsFileLifecycle, read_args_file
from madspec_cli.shared.cli.json_output import emit_json

from .runtime_feedback import render_runtime_rejection
from ..application.resolve_branch import resolve_branch
from ..application.semantic_cleanup import (
    PruneSemanticRequest,
    ReplaceSemanticRequest,
    RetrieveSemanticRequest,
    execute_prune,
    execute_replace,
    execute_retrieve,
)
from ..shared.system_store.constants import SYSTEM_SESSION_KEY


semantic_app = typer.Typer(help="Inspect or clean canonical semantic knowledge")

SEMANTIC_REPLACE_ALLOWED_KEYS = {
    "scope",
    "branch",
    "session_key",
    "expected_revision",
    "json_output",
    "summary",
    "evidence",
    "semantic",
}

SEMANTIC_PRUNE_ALLOWED_KEYS = {
    "scope",
    "branch",
    "session_key",
    "expected_revision",
    "json_output",
    "summary",
    "evidence",
    "operations",
}


@semantic_app.command("retrieve")
def retrieve_semantic_command(
    scope: str = typer.Option(..., "--scope", help="Semantic scope: branch or project"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name for branch-scoped semantic knowledge"),
    include_obsolete: bool = typer.Option(False, "--include-obsolete", help="Include obsolete semantic records"),
    include_conflicted: bool = typer.Option(False, "--include-conflicted", help="Include conflicted semantic records"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    project_path = Path.cwd()
    target_branch = resolve_branch(project_path, branch_name) if scope.strip().lower() == "branch" else branch_name
    try:
        payload = execute_retrieve(
            RetrieveSemanticRequest(
                project_path=project_path,
                scope=scope,
                branch_name=target_branch,
                include_obsolete=include_obsolete,
                include_conflicted=include_conflicted,
            )
        ).to_payload()
    except Exception as exc:
        if json_output:
            emit_json({"accepted": False, "errors": [str(exc)]})
        else:
            console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    if json_output:
        emit_json(payload)
        return

    show_banner()
    console.print(f"[cyan]Scope:[/cyan] {payload['scope']}")
    if payload.get("branch"):
        console.print(f"[cyan]Branch:[/cyan] {payload['branch']}")
    console.print(f"[cyan]Revision:[/cyan] {payload['runtime_revision']}")
    counts = payload.get("counts") or {}
    console.print(
        f"[cyan]Knowledge:[/cyan] facts={counts.get('facts', 0)}, "
        f"decisions={counts.get('decisions', 0)}, contracts={counts.get('contracts', 0)}"
    )


@semantic_app.command("replace")
def replace_semantic_command(
    from_file: str = typer.Option(..., "--from-file", help="Path to JSON file with semantic replacement payload"),
    scope: str = typer.Option(None, "--scope", help="Semantic scope: branch or project"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name for branch-scoped semantic cleanup"),
    session_key: str = typer.Option(SYSTEM_SESSION_KEY, "--session-key", help="Runtime session key for branch-scoped cleanup"),
    expected_revision: int | None = typer.Option(None, "--expected-revision", help="Expected runtime revision for optimistic concurrency"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    args_file_lifecycle = ArgsFileLifecycle.from_path(from_file)
    file_data = read_args_file(
        from_file,
        allowed_keys=SEMANTIC_REPLACE_ALLOWED_KEYS,
    )
    scope = file_data.pop("scope", scope)
    branch_name = file_data.pop("branch", branch_name)
    session_key = file_data.pop("session_key", session_key)
    expected_revision = file_data.pop("expected_revision", expected_revision)
    json_output = file_data.pop("json_output", json_output)
    summary = file_data.pop("summary", None)
    evidence = file_data.pop("evidence", [])
    semantic = file_data.pop("semantic", None)

    if not scope:
        console.print("[red]--scope is required (pass it via CLI or inside the JSON file)[/red]")
        raise typer.Exit(1)
    if semantic is None:
        console.print("[red]'semantic' is required inside the JSON file[/red]")
        raise typer.Exit(1)

    project_path = Path.cwd()
    target_branch = resolve_branch(project_path, branch_name) if scope.strip().lower() == "branch" else branch_name
    try:
        result = execute_replace(
            ReplaceSemanticRequest(
                project_path=project_path,
                scope=scope,
                branch_name=target_branch,
                session_key=session_key,
                expected_revision=expected_revision,
                semantic=semantic,
                summary=summary,
                evidence=list(evidence or []),
            )
        )
    except Exception as exc:
        if json_output:
            emit_json({"accepted": False, "errors": [str(exc)]})
        else:
            console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    _emit_result(
        result=result,
        args_file_lifecycle=args_file_lifecycle,
        scope=scope,
        branch_name=target_branch,
        json_output=json_output,
        success_title="Semantic knowledge replaced.",
        failure_title="Semantic replace rejected.",
    )


@semantic_app.command("prune")
def prune_semantic_command(
    from_file: str = typer.Option(..., "--from-file", help="Path to JSON file with semantic prune payload"),
    scope: str = typer.Option(None, "--scope", help="Semantic scope: branch or project"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name for branch-scoped semantic cleanup"),
    session_key: str = typer.Option(SYSTEM_SESSION_KEY, "--session-key", help="Runtime session key for branch-scoped cleanup"),
    expected_revision: int | None = typer.Option(None, "--expected-revision", help="Expected runtime revision for optimistic concurrency"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    args_file_lifecycle = ArgsFileLifecycle.from_path(from_file)
    file_data = read_args_file(
        from_file,
        allowed_keys=SEMANTIC_PRUNE_ALLOWED_KEYS,
    )
    scope = file_data.pop("scope", scope)
    branch_name = file_data.pop("branch", branch_name)
    session_key = file_data.pop("session_key", session_key)
    expected_revision = file_data.pop("expected_revision", expected_revision)
    json_output = file_data.pop("json_output", json_output)
    summary = file_data.pop("summary", None)
    evidence = file_data.pop("evidence", [])
    operations = file_data.pop("operations", None)

    if not scope:
        console.print("[red]--scope is required (pass it via CLI or inside the JSON file)[/red]")
        raise typer.Exit(1)
    if operations is None:
        console.print("[red]'operations' is required inside the JSON file[/red]")
        raise typer.Exit(1)

    project_path = Path.cwd()
    target_branch = resolve_branch(project_path, branch_name) if scope.strip().lower() == "branch" else branch_name
    try:
        result = execute_prune(
            PruneSemanticRequest(
                project_path=project_path,
                scope=scope,
                branch_name=target_branch,
                session_key=session_key,
                expected_revision=expected_revision,
                operations=list(operations or []),
                summary=summary,
                evidence=list(evidence or []),
            )
        )
    except Exception as exc:
        if json_output:
            emit_json({"accepted": False, "errors": [str(exc)]})
        else:
            console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    _emit_result(
        result=result,
        args_file_lifecycle=args_file_lifecycle,
        scope=scope,
        branch_name=target_branch,
        json_output=json_output,
        success_title="Semantic knowledge pruned.",
        failure_title="Semantic prune rejected.",
    )


def register(memory_app: typer.Typer) -> None:
    memory_app.add_typer(semantic_app, name="semantic")


def _emit_result(
    *,
    result,
    args_file_lifecycle: ArgsFileLifecycle,
    scope: str,
    branch_name: str | None,
    json_output: bool,
    success_title: str,
    failure_title: str,
) -> None:
    payload = result.to_payload()
    if json_output:
        emit_json(payload)
        if not result.accepted:
            raise typer.Exit(1)
        args_file_lifecycle.cleanup_after_success()
        return

    show_banner()
    console.print(f"[cyan]Scope:[/cyan] {payload.get('scope') or scope}")
    if branch_name:
        console.print(f"[cyan]Branch:[/cyan] {branch_name}")
    if result.accepted:
        args_file_lifecycle.cleanup_after_success()
        if payload.get("proposal_mode"):
            proposal = payload.get("proposal") or {}
            console.print("[green]Semantic cleanup proposal published.[/green]")
            console.print(f"[cyan]Proposal:[/cyan] {proposal.get('proposal_id')}")
            console.print(f"[cyan]Type:[/cyan] {proposal.get('proposal_type')}")
            console.print(f"[cyan]Base revision:[/cyan] {payload.get('base_revision')}")
            console.print(f"[cyan]Work item:[/cyan] {proposal.get('work_item_id')}")
            console.print(
                f"[cyan]Next step:[/cyan] madspec memory proposals apply --proposal-id {proposal.get('proposal_id')}"
            )
            return
        details = payload.get("details") or {}
        console.print(f"[green]{success_title}[/green] {payload.get('summary')}")
        console.print(f"[cyan]Records:[/cyan] {details.get('record_count', 0)}")
        console.print(f"[cyan]Removed:[/cyan] {details.get('removed_count', 0)}")
        return

    if payload.get("kind") in {"scope_busy", "conflict"}:
        render_runtime_rejection(payload, fallback_title=failure_title)
    else:
        console.print(f"[red]{failure_title}[/red] Fix the validation errors below.")
        for error in payload.get("errors", []):
            console.print(f"[red]- {error}[/red]")
    raise typer.Exit(1)
