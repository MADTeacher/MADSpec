from __future__ import annotations

from typing import Any

from madspec_cli.shared.cli.banners import console


def render_runtime_rejection(payload: dict[str, Any], *, fallback_title: str) -> None:
    if payload.get("kind") == "scope_busy":
        busy = payload.get("scope_busy", {})
        console.print("[red]Write scope is busy.[/red]")
        console.print(f"[cyan]Scope:[/cyan] {busy.get('scope') or 'unknown'}")
        console.print(f"[cyan]Lease:[/cyan] {busy.get('lease_name') or 'unknown'}")
        console.print(f"[cyan]Owner:[/cyan] {busy.get('owner_id') or 'unknown'}")
        console.print(f"[cyan]Expires At:[/cyan] {busy.get('expires_at') or 'unknown'}")
        console.print(f"[red]- {busy.get('retry_guidance') or 'Retry later.'}[/red]")
        return
    if payload.get("kind") == "conflict":
        conflict = payload.get("conflict", {})
        console.print("[red]Runtime conflict detected.[/red]")
        console.print(f"[cyan]Scope:[/cyan] {conflict.get('scope') or 'unknown'}")
        if conflict.get("step_id"):
            console.print(f"[cyan]Step:[/cyan] {conflict['step_id']}")
        console.print(
            f"[cyan]Revision:[/cyan] expected={conflict.get('expected_revision')} actual={conflict.get('actual_revision')}"
        )
        console.print(f"[red]- {conflict.get('retry_guidance') or 'Refresh runtime state and retry.'}[/red]")
        return

    console.print(f"[red]{fallback_title}[/red]")
    for error in payload.get("errors", []):
        console.print(f"[red]- {error}[/red]")
