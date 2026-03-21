from __future__ import annotations

from pathlib import Path

import typer

from madspec_cli.shared.cli.banners import console, show_banner
from madspec_cli.shared.cli.json_output import emit_json
from madspec_cli.shared.cli.toon_output import emit_toon, ensure_structured_output_mode

from ..application.conflicts import MemoryConflictsRequest, execute as list_conflicts
from ..application.doctor import MemoryDoctorRequest, execute as memory_doctor
from ..application.explain_state import ExplainStateRequest, execute as explain_state
from ..application.inspect_record import InspectRecordRequest, execute as inspect_record
from ..application.timeline import TimelineRequest, execute as memory_timeline
from ..application.why_next_step import WhyNextStepRequest, execute as explain_next_step
from ..domain.branch_layout import resolve_target_branch
from ..shared.system_store.constants import SYSTEM_SESSION_KEY


def doctor(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Run a read-only diagnostic sweep over branch memory and the project backend."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    result = memory_doctor(
        MemoryDoctorRequest(project_path=project_path, branch_name=target_branch)
    )
    payload = result.to_payload()
    if json_output:
        emit_json(payload)
        if result.has_errors:
            raise typer.Exit(1)
        return

    show_banner()
    console.print(f"[cyan]Branch:[/cyan] {target_branch}")
    console.print(f"[cyan]Overall status:[/cyan] {payload['status']}")
    for check in payload["checks"]:
        console.print(f"- [{check['status']}] {check['name']}: {check['summary']}")
        for detail in check.get("details", [])[:5]:
            console.print(f"  - {detail}")
        if check.get("probable_cause"):
            console.print(f"  probable cause: {check['probable_cause']}")
        if check.get("repair_hint"):
            console.print(f"  repair hint: {check['repair_hint']}")
    if result.has_errors:
        raise typer.Exit(1)


def explain(
    stage: str = typer.Option(..., "--stage", help="Target stage, e.g. mvp.plan or mvp.implement"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    session_key: str = typer.Option(SYSTEM_SESSION_KEY, "--session-key", help="Runtime session key; defaults to legacy active"),
    step_id: str = typer.Option(None, "--step-id", help="Optional step identifier"),
    limit: int = typer.Option(5, "--limit", help="Max records per section"),
    query: str | None = typer.Option(None, "--query", help="Optional recall query"),
    disable_semantic: bool = typer.Option(False, "--disable-semantic", help="Disable semantic recall"),
    recall_limit: int = typer.Option(5, "--recall-limit", help="Max recall candidates to explain"),
    scope: str = typer.Option("branch", "--scope", help="Recall scope: step, stage, branch, or project"),
    include_obsolete: bool = typer.Option(False, "--include-obsolete", help="Include obsolete records"),
    include_conflicted: bool = typer.Option(False, "--include-conflicted", help="Include conflicted records"),
    include_history: bool = typer.Option(False, "--include-history", help="Include history layers in the explanation"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
    toon_output: bool = typer.Option(False, "--toon-output", help="Emit TOON for agent-oriented structured context"),
) -> None:
    """Explain the current stage context, policy effects, and recall influences."""
    ensure_structured_output_mode(json_output=json_output, toon_output=toon_output)
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    payload = explain_state(
        ExplainStateRequest(
            project_path=project_path,
            branch_name=target_branch,
            stage=stage,
            session_key=session_key,
            step_id=step_id,
            limit=limit,
            query=query,
            disable_semantic=disable_semantic,
            recall_limit=recall_limit,
            scope=scope,
            include_obsolete=include_obsolete,
            include_conflicted=include_conflicted,
            include_history=include_history,
        )
    ).to_payload()
    if json_output:
        emit_json(payload)
        return
    if toon_output:
        emit_toon(payload)
        return

    show_banner()
    console.print(f"[cyan]Branch:[/cyan] {target_branch}")
    console.print(f"[cyan]Stage:[/cyan] {stage}")
    console.print(f"[cyan]Session:[/cyan] {payload['summary'].get('session_key') or SYSTEM_SESSION_KEY}")
    console.print(f"[cyan]Step:[/cyan] {payload['step_id'] or 'N/A'}")
    console.print(f"[cyan]Session focus:[/cyan] {payload['summary'].get('session_current_step') or 'N/A'}")
    console.print(f"[cyan]Shared implementation focus:[/cyan] {payload['summary'].get('shared_current_implement_step') or 'N/A'}")
    console.print(f"[cyan]Selected step:[/cyan] {payload['summary'].get('selected_step') or 'N/A'}")
    console.print(f"[cyan]Reason:[/cyan] {payload['summary'].get('next_step_reason') or 'N/A'}")
    console.print(f"[cyan]Gate status:[/cyan] {payload['gate_summary']['overall_status']}")
    console.print(f"[cyan]Recall triggers:[/cyan] {', '.join(payload['recall_explanation']['triggers']) or 'none'}")
    console.print(f"[cyan]Influences:[/cyan] {len(payload['influences'])}")
    runtime_outcome = payload.get("latest_runtime_outcome")
    if runtime_outcome:
        console.print(
            f"[cyan]Latest runtime outcome:[/cyan] {runtime_outcome.get('outcome')} "
            f"({runtime_outcome.get('reason')})"
        )
    obs_summary = (payload.get("observability") or {}).get("summary") or {}
    console.print(
        f"[cyan]Observability:[/cyan] leases={obs_summary.get('active_lease_count', 0)} "
        f"pending_proposals={obs_summary.get('pending_proposal_count', 0)} "
        f"conflicts={obs_summary.get('conflict_count', 0)} "
        f"projection={obs_summary.get('projection_status', 'unknown')}"
    )
    for item in payload["influences"][:8]:
        console.print(f"- [{item['kind']}] {item['summary']}")


def timeline(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    stage: str = typer.Option(None, "--stage", help="Optional stage filter"),
    step_id: str = typer.Option(None, "--step-id", help="Optional step filter"),
    limit: int = typer.Option(20, "--limit", help="Max timeline items to return"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Show a merged timeline from canonical memory records, snapshots, and retrieval runs."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    payload = memory_timeline(
        TimelineRequest(
            project_path=project_path,
            branch_name=target_branch,
            stage=stage,
            step_id=step_id,
            limit=limit,
        )
    ).to_payload()
    if json_output:
        emit_json(payload)
        return

    show_banner()
    console.print(f"[cyan]Branch:[/cyan] {target_branch}")
    if stage:
        console.print(f"[cyan]Stage filter:[/cyan] {stage}")
    if step_id:
        console.print(f"[cyan]Step filter:[/cyan] {step_id}")
    for item in payload["items"]:
        console.print(
            f"- {item['timestamp']} [{item.get('category') or item['source_type']}] {item['summary']} "
            f"(event={item.get('event_type') or 'n/a'}, stage={item['stage'] or 'n/a'}, "
            f"step={item['step_id'] or 'n/a'}, status={item['status']}, reason={item.get('reason') or 'n/a'})"
        )


def why_next_step(
    stage: str = typer.Option(..., "--stage", help="Target stage, e.g. mvp.plan or mvp.implement"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Explain why a particular step is selected next and why others are blocked."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    payload = explain_next_step(
        WhyNextStepRequest(
            project_path=project_path,
            branch_name=target_branch,
            stage=stage,
        )
    ).to_payload()
    if json_output:
        emit_json(payload)
        return

    show_banner()
    console.print(f"[cyan]Branch:[/cyan] {target_branch}")
    console.print(f"[cyan]Stage:[/cyan] {stage}")
    console.print(f"[cyan]Selected step:[/cyan] {payload['selected_step'] or 'N/A'}")
    console.print(f"[cyan]Reason:[/cyan] {payload['reason']}")
    for item in payload["steps"]:
        line = (
            f"- {item['step_id']}: state={item['state']}, "
            f"missing={', '.join(item['missing_dependencies']) or 'none'}, "
            f"gates={item['gate_summary']['overall_status']}"
        )
        console.print(line)


def conflicts(
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    stage: str = typer.Option(None, "--stage", help="Optional stage filter"),
    step_id: str = typer.Option(None, "--step-id", help="Optional step filter"),
    limit: int = typer.Option(20, "--limit", help="Max conflicts to return per section"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """List explicit conflicted records and integrity conflicts for the branch."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    payload = list_conflicts(
        MemoryConflictsRequest(
            project_path=project_path,
            branch_name=target_branch,
            stage=stage,
            step_id=step_id,
            limit=limit,
        )
    ).to_payload()
    if json_output:
        emit_json(payload)
        return

    show_banner()
    console.print(f"[cyan]Branch:[/cyan] {target_branch}")
    console.print(f"[cyan]Record conflicts:[/cyan] {len(payload['record_conflicts'])}")
    console.print(f"[cyan]Integrity conflicts:[/cyan] {len(payload['integrity_conflicts'])}")
    dashboard = payload.get("conflict_dashboard") or {}
    console.print(
        f"[cyan]Conflict dashboard:[/cyan] proposals={len(dashboard.get('proposal_conflicts') or [])} "
        f"projection={len(dashboard.get('projection_conflicts') or [])} "
        f"coordinator={len(dashboard.get('coordinator_conflicts') or [])}"
    )
    for item in payload["record_conflicts"][:10]:
        console.print(f"- [record] {item['summary']} ({item['record_id']})")
    for item in payload["integrity_conflicts"][:10]:
        console.print(f"- [integrity] {item['message']}")
    for item in (dashboard.get("proposal_conflicts") or [])[:5]:
        console.print(f"- [proposal] {item['summary']} cause={item['probable_cause']}")


def inspect(
    record_id: str = typer.Option(..., "--id", help="Canonical record identifier to inspect"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    related_limit: int = typer.Option(5, "--related-limit", help="Max related records to return"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Inspect a canonical memory record together with its source and index state."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    result = inspect_record(
        InspectRecordRequest(
            project_path=project_path,
            branch_name=target_branch,
            record_id=record_id,
            related_limit=related_limit,
        )
    )
    payload = result.to_payload()
    if json_output:
        emit_json(payload)
        if not result.found:
            raise typer.Exit(1)
        return

    show_banner()
    if not result.found:
        console.print(f"[red]{payload['error']}[/red]")
        raise typer.Exit(1)
    console.print(f"[cyan]Record:[/cyan] {record_id}")
    console.print(f"[cyan]Source:[/cyan] {payload['source_file'] or 'unknown'}")
    console.print(f"[cyan]Indexed:[/cyan] {'yes' if payload['indexed']['is_indexed'] else 'no'}")
    console.print(f"[cyan]Summary:[/cyan] {payload['record']['summary']}")
    for item in payload["related"]:
        console.print(f"- {item['record_id']}: {item['summary']}")


def register(memory_app: typer.Typer) -> None:
    memory_app.command("doctor")(doctor)
    memory_app.command("explain")(explain)
    memory_app.command("timeline")(timeline)
    memory_app.command("why-next-step")(why_next_step)
    memory_app.command("conflicts")(conflicts)
    memory_app.command("inspect-record")(inspect)
