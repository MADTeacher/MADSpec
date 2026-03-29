from __future__ import annotations

from pathlib import Path

import typer

from madspec_cli.shared.cli.banners import console, show_banner
from madspec_cli.shared.cli.json_output import emit_json

from ..application.vector_namespace_gc import VectorNamespaceGcRequest, execute as vector_namespace_gc


gc_app = typer.Typer(help="Maintenance commands for derived memory storage")


@gc_app.command("vector-namespaces")
def gc_vector_namespaces(
    dry_run: bool = typer.Option(False, "--dry-run", help="Inspect inactive namespaces without deleting them"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    project_path = Path.cwd()
    payload = vector_namespace_gc(
        VectorNamespaceGcRequest(
            project_path=project_path,
            dry_run=dry_run,
        )
    ).to_payload()
    if json_output:
        emit_json(payload)
        return

    show_banner()
    console.print(f"[cyan]Active namespace:[/cyan] {payload['active_namespace']['path']}")
    console.print(f"[cyan]Mode:[/cyan] {'dry-run' if payload['dry_run'] else 'delete'}")
    console.print(f"[cyan]Candidates:[/cyan] {len(payload['candidates'])}")
    for item in payload["candidates"]:
        console.print(
            f"- {item['path']} "
            f"(provider={item['provider']}, model={item['model']}, revision={item['revision']}, "
            f"dimension={item['dimension']}, semantic_chunks={item['semantic_chunk_count']})"
        )
    if not payload["dry_run"]:
        console.print(f"[cyan]Deleted namespaces:[/cyan] {len(payload['deleted_namespaces'])}")
        console.print(f"[cyan]Deleted semantic chunks:[/cyan] {payload['deleted_chunk_count']}")
    for warning in payload.get("warnings") or []:
        console.print(f"[yellow]warning:[/yellow] {warning}")


def register(memory_app: typer.Typer) -> None:
    memory_app.add_typer(gc_app, name="gc")
