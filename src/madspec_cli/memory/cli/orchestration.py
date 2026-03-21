from __future__ import annotations

from pathlib import Path

import typer

from madspec_cli.shared.cli.banners import console, show_banner
from madspec_cli.shared.cli.json_output import emit_json
from madspec_cli.shared.cli.presenters import emit_error

from ..application.parallel_runtime import require_phase2_enabled
from ..application.orchestration import (
    ClaimWorkItemRequest,
    CoordinationContextRequest,
    CreateTaskRequest,
    CreateWorkItemRequest,
    ExplainCoordinatorRequest,
    ListTasksRequest,
    ListWorkItemsRequest,
    ReleaseWorkItemRequest,
    claim_work_item,
    create_task,
    create_work_item,
    explain_coordinator,
    list_tasks,
    list_work_items,
    release_work_item,
    resolve_coordination_context,
)
from ..domain.branch_layout import resolve_target_branch
from ..shared.system_store.constants import SYSTEM_SESSION_KEY


tasks_app = typer.Typer(help="Task coordination over shared branch runtime")
work_items_app = typer.Typer(help="Work items for subagent-scoped ownership")
coordinator_app = typer.Typer(help="Coordinator runtime explainability and orchestration diagnostics")


def _exit_if_phase2_disabled(*, project_path: Path, command_name: str, json_output: bool) -> None:
    payload = require_phase2_enabled(project_path, command_name=command_name)
    if payload is None:
        return
    if json_output:
        emit_json(payload)
    else:
        show_banner()
        console.print(f"[red]{payload['message']}[/red]")
        console.print(f"[cyan]Command:[/cyan] {command_name}")
        console.print(f"[cyan]Guidance:[/cyan] {payload['guidance']}")
    raise typer.Exit(1)


@tasks_app.command("create")
def create_task_command(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to update"),
    title: str = typer.Option(..., "--title", help="Task title"),
    summary: str = typer.Option(None, "--summary", help="Optional task summary"),
    acceptance_note: str = typer.Option(None, "--acceptance-note", help="Optional acceptance note"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    try:
        project_path = Path.cwd()
        _exit_if_phase2_disabled(
            project_path=project_path,
            command_name="madspec memory tasks create",
            json_output=json_output,
        )
        target_branch = resolve_target_branch(project_path, branch_name)
        payload = create_task(
            CreateTaskRequest(
                project_path=project_path,
                branch_name=target_branch,
                title=title,
                summary=summary,
                acceptance_note=acceptance_note,
            )
        ).to_payload()
    except typer.Exit:
        raise
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Created task:[/green] {payload['task']['task_id']}")
    console.print(f"[cyan]Title:[/cyan] {payload['task']['title']}")


@tasks_app.command("list")
def list_tasks_command(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    try:
        project_path = Path.cwd()
        _exit_if_phase2_disabled(
            project_path=project_path,
            command_name="madspec memory tasks list",
            json_output=json_output,
        )
        target_branch = resolve_target_branch(project_path, branch_name)
        payload = list_tasks(
            ListTasksRequest(project_path=project_path, branch_name=target_branch)
        ).to_payload()
    except typer.Exit:
        raise
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    for item in payload["tasks"]:
        console.print(f"- `{item['task_id']}` [{item['status']}] {item['title']}")


@work_items_app.command("create")
def create_work_item_command(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to update"),
    task_id: str = typer.Option(..., "--task-id", help="Task identifier"),
    title: str = typer.Option(..., "--title", help="Work item title"),
    work_item_type: str = typer.Option(..., "--type", help="Work item type"),
    subagent_id: str = typer.Option(..., "--subagent-id", help="Owning subagent"),
    step_id: str = typer.Option(None, "--step-id", help="Optional implementation step"),
    path: list[str] = typer.Option(None, "--path", help="Scoped repository path; repeat for multiple values"),
    artifact: list[str] = typer.Option(None, "--artifact", help="Scoped artifact path; repeat for multiple values"),
    concern: list[str] = typer.Option(None, "--concern", help="Scoped concern tag; repeat for multiple values"),
    depends_on_work_item: list[str] = typer.Option(None, "--depends-on-work-item", help="Explicit dependency work item id; repeat for multiple values"),
    acceptance_note: str = typer.Option(None, "--acceptance-note", help="Optional acceptance note"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    try:
        project_path = Path.cwd()
        _exit_if_phase2_disabled(
            project_path=project_path,
            command_name="madspec memory work-items create",
            json_output=json_output,
        )
        target_branch = resolve_target_branch(project_path, branch_name)
        payload = create_work_item(
            CreateWorkItemRequest(
                project_path=project_path,
                branch_name=target_branch,
                task_id=task_id,
                title=title,
                work_item_type=work_item_type,
                subagent_id=subagent_id,
                step_id=step_id,
                scope_descriptor={
                    "step_id": step_id,
                    "paths": path or [],
                    "artifacts": artifact or [],
                    "concerns": concern or [],
                },
                acceptance_note=acceptance_note,
                depends_on_work_item_ids=depends_on_work_item or [],
            )
        ).to_payload()
    except typer.Exit:
        raise
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Created work item:[/green] {payload['work_item']['work_item_id']}")
    console.print(f"[cyan]Task:[/cyan] {payload['work_item']['task_id']}")


@work_items_app.command("list")
def list_work_items_command(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    task_id: str = typer.Option(None, "--task-id", help="Optional task filter"),
    session_key: str = typer.Option(None, "--session-key", help="Optional session filter"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    try:
        project_path = Path.cwd()
        _exit_if_phase2_disabled(
            project_path=project_path,
            command_name="madspec memory work-items list",
            json_output=json_output,
        )
        target_branch = resolve_target_branch(project_path, branch_name)
        payload = list_work_items(
            ListWorkItemsRequest(
                project_path=project_path,
                branch_name=target_branch,
                task_id=task_id,
                session_key=session_key,
            )
        ).to_payload()
    except typer.Exit:
        raise
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    for item in payload["work_items"]:
        console.print(
            f"- `{item['work_item_id']}` [{item['status']}] readiness={((item.get('readiness') or {}).get('status') or 'n/a')} {item['title']} subagent={item['subagent_id']} session={item.get('session_key') or 'none'}"
        )


@work_items_app.command("claim")
def claim_work_item_command(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to update"),
    work_item_id: str = typer.Option(..., "--work-item-id", help="Work item identifier"),
    session_key: str = typer.Option(..., "--session-key", help="Session key to bind"),
    subagent_id: str = typer.Option(..., "--subagent-id", help="Subagent identifier"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    try:
        project_path = Path.cwd()
        _exit_if_phase2_disabled(
            project_path=project_path,
            command_name="madspec memory work-items claim",
            json_output=json_output,
        )
        target_branch = resolve_target_branch(project_path, branch_name)
        payload = claim_work_item(
            ClaimWorkItemRequest(
                project_path=project_path,
                branch_name=target_branch,
                work_item_id=work_item_id,
                session_key=session_key,
                subagent_id=subagent_id,
            )
        ).to_payload()
    except typer.Exit:
        raise
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        if payload.get("accepted") is False:
            raise typer.Exit(1)
        return
    if payload.get("accepted") is False:
        show_banner()
        console.print(f"[red]Claim rejected.[/red] {work_item_id}")
        for item in (payload.get("readiness") or {}).get("blocked_reasons", []):
            console.print(f"[red]- {item.get('code')}: {item.get('message')}[/red]")
        raise typer.Exit(1)
    show_banner()
    console.print(f"[green]Claimed work item:[/green] {payload['work_item']['work_item_id']}")
    console.print(f"[cyan]Session:[/cyan] {payload['session']['session_key']}")


@work_items_app.command("release")
def release_work_item_command(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to update"),
    work_item_id: str = typer.Option(..., "--work-item-id", help="Work item identifier"),
    session_key: str = typer.Option(SYSTEM_SESSION_KEY, "--session-key", help="Session key to release"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    try:
        project_path = Path.cwd()
        _exit_if_phase2_disabled(
            project_path=project_path,
            command_name="madspec memory work-items release",
            json_output=json_output,
        )
        target_branch = resolve_target_branch(project_path, branch_name)
        payload = release_work_item(
            ReleaseWorkItemRequest(
                project_path=project_path,
                branch_name=target_branch,
                work_item_id=work_item_id,
                session_key=session_key,
            )
        ).to_payload()
    except typer.Exit:
        raise
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Released work item:[/green] {payload['work_item']['work_item_id']}")


@coordinator_app.command("explain")
def explain_coordinator_command(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    task_id: str = typer.Option(None, "--task-id", help="Optional task identifier"),
    work_item_id: str = typer.Option(None, "--work-item-id", help="Optional work item identifier"),
    session_key: str = typer.Option(None, "--session-key", help="Optional session binding"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    try:
        project_path = Path.cwd()
        _exit_if_phase2_disabled(
            project_path=project_path,
            command_name="madspec memory coordinator explain",
            json_output=json_output,
        )
        target_branch = resolve_target_branch(project_path, branch_name)
        payload = explain_coordinator(
            ExplainCoordinatorRequest(
                project_path=project_path,
                branch_name=target_branch,
                session_key=session_key,
                task_id=task_id,
                work_item_id=work_item_id,
            )
        ).to_payload()
    except typer.Exit:
        raise
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[cyan]Branch:[/cyan] {payload['branch']}")
    console.print(f"[cyan]Session:[/cyan] {payload.get('session_key') or 'n/a'}")
    if payload.get("task"):
        console.print(f"[cyan]Task:[/cyan] {payload['task']['task_id']} [{payload['task']['status']}]")
    if payload.get("work_item"):
        console.print(f"[cyan]Work item:[/cyan] {payload['work_item']['work_item_id']}")
    coordinator = payload.get("coordinator") or {}
    readiness = coordinator.get("readiness") or {}
    console.print(f"[cyan]Readiness:[/cyan] {readiness.get('status') or 'n/a'}")
    for item in readiness.get("blocked_reasons", []):
        console.print(f"- {item.get('code')}: {item.get('message')}")


def register(memory_app: typer.Typer) -> None:
    memory_app.add_typer(tasks_app, name="tasks")
    memory_app.add_typer(work_items_app, name="work-items")
    memory_app.add_typer(coordinator_app, name="coordinator")
