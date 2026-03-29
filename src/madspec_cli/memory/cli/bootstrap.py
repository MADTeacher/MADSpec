from __future__ import annotations

from pathlib import Path

import typer

from madspec_cli.shared.cli.banners import console, show_banner
from madspec_cli.shared.cli.json_output import emit_json

from ..application.bootstrap_branch_memory import BootstrapBranchMemoryRequest, execute as bootstrap_memory
from ..application.consolidate_memory import ConsolidateMemoryRequest, execute as consolidate_memory
from ..application.validate_memory import ValidateMemoryRequest, execute as validate_memory
from ..application.resolve_branch import resolve_branch
from ..shared.storage import get_memory_paths, read_jsonl
from ..application.system_store_ops import bootstrap_configured_model, build_db_status, run_reindex


def memory_init(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to initialize"),
) -> None:
    """Initialize structured memory layout for the current project."""
    show_banner()
    project_path = Path.cwd()
    target_branch = resolve_branch(project_path, branch_name)
    result = bootstrap_memory(BootstrapBranchMemoryRequest(project_path=project_path, branch_name=target_branch))
    if result.errors:
        console.print("[red]Memory initialization completed with validation errors:[/red]")
        for error in result.errors:
            console.print(f"  - {error}")
        raise typer.Exit(1)

    console.print(f"[green]Structured memory initialized for branch:[/green] {target_branch}")
    console.print(f"[cyan]Created files:[/cyan] {result.created_count}")
    console.print(f"[cyan]Generated views:[/cyan] {result.generated_count}")


def memory_status(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Show structured memory status for the current branch."""
    project_path = Path.cwd()
    target_branch = resolve_branch(project_path, branch_name)
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
        "db": build_db_status(project_path, target_branch),
    }
    if json_output:
        emit_json(payload)
        return

    show_banner()
    console.print(f"[cyan]Branch:[/cyan] {target_branch}")
    console.print(f"[cyan]Progress:[/cyan] {'present' if payload['progress_exists'] else 'missing'}")
    console.print(f"[cyan]Active session:[/cyan] {'present' if payload['active_session_exists'] else 'missing'}")
    console.print(f"[cyan]Decision log records:[/cyan] {payload['decision_log_records']}")
    console.print(f"[cyan]Episode records:[/cyan] {payload['episode_records']}")
    console.print(
        "[cyan]Semantic records:[/cyan] "
        f"facts={payload['semantic_records']['facts']}, "
        f"decisions={payload['semantic_records']['decisions']}, "
        f"contracts={payload['semantic_records']['contracts']}"
    )
    embeddings = payload["db"].get("configured_embeddings") or {}
    index_state = payload["db"].get("index_state") or {}
    console.print(
        f"[cyan]Configured embeddings:[/cyan] {embeddings.get('provider')} "
        f"(model={embeddings.get('model') or 'n/a'}, status={embeddings.get('status')}, ready={embeddings.get('ready')})"
    )
    bootstrap = embeddings.get("bootstrap") or {}
    if isinstance(bootstrap, dict) and bootstrap.get("message"):
        console.print(f"[cyan]Embeddings cache:[/cyan] {bootstrap.get('message')}")
    console.print(
        f"[cyan]Active vector namespace:[/cyan] {payload['db'].get('active_vector_namespace') or 'n/a'} "
        f"(provider={payload['db'].get('active_vector_provider') or 'n/a'}, "
        f"model={payload['db'].get('active_vector_model') or 'n/a'}, "
        f"revision={payload['db'].get('active_vector_revision') or 'n/a'}, "
        f"dimension={payload['db'].get('active_vector_dimension') or 'n/a'})"
    )
    console.print(
        f"[cyan]Index state:[/cyan] ready={index_state.get('ready')} "
        f"reindex_required={index_state.get('reindexRequired')} "
        f"reason={index_state.get('reason') or 'n/a'}"
    )
    if index_state.get("message"):
        console.print(f"[cyan]Index guidance:[/cyan] {index_state.get('message')}")
    console.print(f"[cyan]SQLite records:[/cyan] {payload['db']['records']}")
    console.print(f"[cyan]Stage snapshots:[/cyan] {payload['db']['stage_snapshots']}")
    console.print(f"[cyan]Pending index jobs:[/cyan] {payload['db']['pending_index_jobs']}")


def memory_consolidate(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to consolidate"),
) -> None:
    """Generate markdown views from structured memory."""
    show_banner()
    project_path = Path.cwd()
    target_branch = resolve_branch(project_path, branch_name)
    result = consolidate_memory(ConsolidateMemoryRequest(project_path=project_path, branch_name=target_branch))
    console.print(f"[green]Consolidated branch:[/green] {target_branch}")
    for path in result.generated_paths:
        console.print(f"  - {path.relative_to(project_path)}")


def memory_validate(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to validate"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Validate structured memory and derived views."""
    project_path = Path.cwd()
    target_branch = resolve_branch(project_path, branch_name)
    result = validate_memory(ValidateMemoryRequest(project_path=project_path, branch_name=target_branch))
    if json_output:
        emit_json(result)
    else:
        show_banner()
        if result.errors:
            console.print(f"[red]Structured memory is invalid for branch:[/red] {target_branch}")
            for error in result.errors:
                console.print(f"  - {error}")
        else:
            console.print(f"[green]Structured memory is valid for branch:[/green] {target_branch}")

    if result.errors:
        raise typer.Exit(1)


def memory_db_status(
    branch_name: str = typer.Option(None, "--branch", help="Optional branch name to scope counts"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Show project-level SQLite/vector memory backend status."""
    project_path = Path.cwd()
    target_branch = resolve_branch(project_path, branch_name) if branch_name else None
    payload = build_db_status(project_path, target_branch)
    if json_output:
        emit_json(payload)
        return

    show_banner()
    if target_branch:
        console.print(f"[cyan]Branch:[/cyan] {target_branch}")
    console.print(f"[cyan]SQLite:[/cyan] {payload['sqlite_path']}")
    console.print(f"[cyan]Vector root:[/cyan] {payload['vector_root_dir']}")
    console.print(f"[cyan]Vector dir:[/cyan] {payload['vector_dir']}")
    console.print(f"[cyan]Vector backend:[/cyan] {payload['vector_backend']}")
    console.print(
        f"[cyan]Active vector namespace:[/cyan] {payload.get('active_vector_namespace') or 'n/a'} "
        f"(provider={payload.get('active_vector_provider') or 'n/a'}, "
        f"model={payload.get('active_vector_model') or 'n/a'}, "
        f"revision={payload.get('active_vector_revision') or 'n/a'}, "
        f"dimension={payload.get('active_vector_dimension') or 'n/a'})"
    )
    embeddings = payload.get("configured_embeddings") or {}
    index_state = payload.get("index_state") or {}
    console.print(
        f"[cyan]Configured embeddings:[/cyan] {embeddings.get('provider')} "
        f"(model={embeddings.get('model') or 'n/a'}, status={embeddings.get('status')}, ready={embeddings.get('ready')})"
    )
    bootstrap = embeddings.get("bootstrap") or {}
    if isinstance(bootstrap, dict) and bootstrap.get("message"):
        console.print(f"[cyan]Embeddings cache:[/cyan] {bootstrap.get('message')}")
    console.print(
        f"[cyan]Index state:[/cyan] ready={index_state.get('ready')} "
        f"reindex_required={index_state.get('reindexRequired')} "
        f"reason={index_state.get('reason') or 'n/a'}"
    )
    if index_state.get("message"):
        console.print(f"[cyan]Index guidance:[/cyan] {index_state.get('message')}")
    console.print(f"[cyan]Records:[/cyan] {payload['records']}")
    console.print(f"[cyan]Stage snapshots:[/cyan] {payload['stage_snapshots']}")
    console.print(f"[cyan]Sessions:[/cyan] {payload['sessions']}")
    console.print(f"[cyan]Artifacts:[/cyan] {payload['artifacts']}")
    console.print(f"[cyan]Pending index jobs:[/cyan] {payload['pending_index_jobs']}")
    console.print(f"[cyan]Indexed jobs:[/cyan] {payload['indexed_jobs']}")


def memory_reindex(
    branch_name: str = typer.Option(None, "--branch", help="Optional branch name to reindex"),
    limit: int = typer.Option(200, "--limit", help="Max index jobs to process"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Process pending index jobs for the project-local memory backend."""
    project_path = Path.cwd()
    target_branch = resolve_branch(project_path, branch_name) if branch_name else None
    payload = run_reindex(project_path, target_branch, limit=limit)
    if json_output:
        emit_json(payload)
        return

    show_banner()
    if target_branch:
        console.print(f"[cyan]Branch:[/cyan] {target_branch}")
    console.print(f"[cyan]Lease acquired:[/cyan] {'yes' if payload['lease_acquired'] else 'no'}")
    console.print(f"[cyan]Processed jobs:[/cyan] {payload['processed']}")
    console.print(f"[cyan]Failed jobs:[/cyan] {payload['failed']}")
    target_namespace = payload.get("target_namespace") or {}
    if target_namespace:
        console.print(
            f"[cyan]Target namespace:[/cyan] {target_namespace.get('path')} "
            f"(provider={target_namespace.get('provider')}, model={target_namespace.get('model')}, "
            f"revision={target_namespace.get('revision')}, dimension={target_namespace.get('dimension')})"
        )


def memory_bootstrap_model(
    force: bool = typer.Option(False, "--force", help="Rebuild a corrupted model cache root before downloading"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Prepare the configured dense model in the project-local cache."""
    project_path = Path.cwd()
    try:
        payload = bootstrap_configured_model(project_path, force=force)
    except (RuntimeError, ValueError) as exc:
        if json_output:
            emit_json(
                {
                    "status": "error",
                    "message": str(exc),
                }
            )
        else:
            show_banner()
            console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)

    if json_output:
        emit_json(payload)
        return

    show_banner()
    console.print(
        f"[cyan]Configured embeddings:[/cyan] {payload.get('provider')} "
        f"(model={payload.get('model') or 'n/a'}, status={payload.get('status')}, ready={payload.get('ready')})"
    )
    bootstrap = payload.get("bootstrap") or {}
    if isinstance(bootstrap, dict):
        if bootstrap.get("cacheRoot"):
            console.print(f"[cyan]Cache root:[/cyan] {bootstrap['cacheRoot']}")
        if bootstrap.get("manifestPath"):
            console.print(f"[cyan]Manifest:[/cyan] {bootstrap['manifestPath']}")
        if bootstrap.get("localPath"):
            console.print(f"[cyan]Local path:[/cyan] {bootstrap['localPath']}")
    if payload.get("message"):
        console.print(f"[green]{payload['message']}[/green]")
    console.print(f"[cyan]Downloaded:[/cyan] {'yes' if payload.get('downloaded') else 'no'}")
    next_action = payload.get("next_action")
    if next_action:
        console.print(f"[cyan]Next step:[/cyan] {next_action}")


def register(memory_app: typer.Typer) -> None:
    memory_app.command("init")(memory_init)
    memory_app.command("status")(memory_status)
    memory_app.command("db-status")(memory_db_status)
    memory_app.command("bootstrap-model")(memory_bootstrap_model)
    memory_app.command("reindex")(memory_reindex)
    memory_app.command("consolidate")(memory_consolidate)
    memory_app.command("validate")(memory_validate)
