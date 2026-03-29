from __future__ import annotations

from pathlib import Path

import typer

from madspec_cli.shared.cli.banners import console, show_banner
from madspec_cli.shared.cli.file_input import ArgsFileLifecycle, read_args_file
from madspec_cli.shared.cli.json_output import emit_json

from .runtime_feedback import render_runtime_rejection
from ..application.resolve_branch import resolve_branch
from ..application.snapshot_cleanup import (
    PruneSnapshotRequest,
    ReplaceSnapshotRequest,
    execute_prune,
    execute_replace,
)
from ..shared.system_store.constants import SYSTEM_SESSION_KEY


snapshots_app = typer.Typer(help="Replace or prune canonical snapshot stage payloads")

SNAPSHOT_REPLACE_ALLOWED_KEYS = {
    "stage",
    "session_key",
    "expected_revision",
    "branch",
    "json_output",
    "summary",
    "evidence",
    "snapshot",
}

SNAPSHOT_PRUNE_ALLOWED_KEYS = {
    "stage",
    "session_key",
    "expected_revision",
    "branch",
    "json_output",
    "summary",
    "evidence",
    "operations",
}


@snapshots_app.command("replace")
def replace_snapshot_command(
    from_file: str = typer.Option(..., "--from-file", help="Path to JSON file with snapshot replacement payload"),
    stage: str = typer.Option(None, "--stage", help="Snapshot stage to replace"),
    session_key: str = typer.Option(SYSTEM_SESSION_KEY, "--session-key", help="Runtime session key; defaults to legacy active"),
    expected_revision: int | None = typer.Option(None, "--expected-revision", help="Expected branch runtime revision for optimistic concurrency"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to update"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    args_file_lifecycle = ArgsFileLifecycle.from_path(from_file)
    file_data = read_args_file(
        from_file,
        allowed_keys=SNAPSHOT_REPLACE_ALLOWED_KEYS,
    )
    stage = file_data.pop("stage", stage)
    session_key = file_data.pop("session_key", session_key)
    expected_revision = file_data.pop("expected_revision", expected_revision)
    branch_name = file_data.pop("branch", branch_name)
    json_output = file_data.pop("json_output", json_output)
    summary = file_data.pop("summary", None)
    evidence = file_data.pop("evidence", [])
    snapshot = file_data.pop("snapshot", None)

    if not stage:
        console.print("[red]--stage is required (pass it via CLI or inside the JSON file)[/red]")
        raise typer.Exit(1)
    if snapshot is None:
        console.print("[red]'snapshot' is required inside the JSON file[/red]")
        raise typer.Exit(1)

    project_path = Path.cwd()
    target_branch = resolve_branch(project_path, branch_name)
    result = execute_replace(
        ReplaceSnapshotRequest(
            project_path=project_path,
            branch_name=target_branch,
            stage=stage,
            session_key=session_key,
            expected_revision=expected_revision,
            snapshot=snapshot,
            summary=summary,
            evidence=list(evidence or []),
        )
    )
    _emit_result(
        result=result,
        args_file_lifecycle=args_file_lifecycle,
        branch_name=target_branch,
        stage=stage,
        json_output=json_output,
        success_title="Snapshot replaced.",
        failure_title="Snapshot replace rejected.",
    )


@snapshots_app.command("prune")
def prune_snapshot_command(
    from_file: str = typer.Option(..., "--from-file", help="Path to JSON file with snapshot prune payload"),
    stage: str = typer.Option(None, "--stage", help="Snapshot stage to prune"),
    session_key: str = typer.Option(SYSTEM_SESSION_KEY, "--session-key", help="Runtime session key; defaults to legacy active"),
    expected_revision: int | None = typer.Option(None, "--expected-revision", help="Expected branch runtime revision for optimistic concurrency"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to update"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    args_file_lifecycle = ArgsFileLifecycle.from_path(from_file)
    file_data = read_args_file(
        from_file,
        allowed_keys=SNAPSHOT_PRUNE_ALLOWED_KEYS,
    )
    stage = file_data.pop("stage", stage)
    session_key = file_data.pop("session_key", session_key)
    expected_revision = file_data.pop("expected_revision", expected_revision)
    branch_name = file_data.pop("branch", branch_name)
    json_output = file_data.pop("json_output", json_output)
    summary = file_data.pop("summary", None)
    evidence = file_data.pop("evidence", [])
    operations = file_data.pop("operations", None)

    if not stage:
        console.print("[red]--stage is required (pass it via CLI or inside the JSON file)[/red]")
        raise typer.Exit(1)
    if operations is None:
        console.print("[red]'operations' is required inside the JSON file[/red]")
        raise typer.Exit(1)

    project_path = Path.cwd()
    target_branch = resolve_branch(project_path, branch_name)
    result = execute_prune(
        PruneSnapshotRequest(
            project_path=project_path,
            branch_name=target_branch,
            stage=stage,
            session_key=session_key,
            expected_revision=expected_revision,
            operations=list(operations or []),
            summary=summary,
            evidence=list(evidence or []),
        )
    )
    _emit_result(
        result=result,
        args_file_lifecycle=args_file_lifecycle,
        branch_name=target_branch,
        stage=stage,
        json_output=json_output,
        success_title="Snapshot pruned.",
        failure_title="Snapshot prune rejected.",
    )


def register(memory_app: typer.Typer) -> None:
    memory_app.add_typer(snapshots_app, name="snapshots")


def _emit_result(
    *,
    result,
    args_file_lifecycle: ArgsFileLifecycle,
    branch_name: str,
    stage: str,
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
    console.print(f"[cyan]Branch:[/cyan] {branch_name}")
    console.print(f"[cyan]Stage:[/cyan] {stage}")
    if result.accepted:
        args_file_lifecycle.cleanup_after_success()
        details = payload.get("details") or {}
        console.print(f"[green]{success_title}[/green] {payload.get('summary')}")
        if details.get("removed_count") is not None:
            console.print(f"[cyan]Removed:[/cyan] {details['removed_count']}")
        return

    if payload.get("kind") in {"scope_busy", "conflict"}:
        render_runtime_rejection(payload, fallback_title=failure_title)
    else:
        console.print(f"[red]{failure_title}[/red] Fix the validation errors below.")
        for error in payload.get("errors", []):
            console.print(f"[red]- {error}[/red]")
    raise typer.Exit(1)
