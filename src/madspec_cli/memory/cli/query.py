from __future__ import annotations

from pathlib import Path

import typer

from ..application.observability import build_runtime_observability
from madspec_cli.shared.cli.banners import console, show_banner
from madspec_cli.shared.cli.json_output import emit_json
from madspec_cli.shared.cli.toon_output import emit_toon, ensure_structured_output_mode

from ..application.retrieve_context import RetrieveMemoryContextRequest, execute as retrieve_context
from ..domain.branch_layout import resolve_target_branch
from ..shared.system_store.constants import SYSTEM_SESSION_KEY
from ..shared.system_store.sessions import load_runtime_session
from ..shared.system_store import search_memory_store


def memory_retrieve(
    stage: str = typer.Option(..., "--stage", help="Target stage, e.g. mvp.plan or review"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    session_key: str = typer.Option(SYSTEM_SESSION_KEY, "--session-key", help="Runtime session key; defaults to legacy active"),
    step_id: str = typer.Option(None, "--step-id", help="Optional step identifier"),
    limit: int | None = typer.Option(None, "--limit", help="Max records per section"),
    query: str | None = typer.Option(None, "--query", help="Optional recall query for hybrid search"),
    disable_semantic: bool = typer.Option(False, "--disable-semantic", help="Disable semantic recall and use SQLite exact/FTS only"),
    recall_limit: int | None = typer.Option(None, "--recall-limit", help="Max recall candidates to merge into working context"),
    scope: str = typer.Option("branch", "--scope", help="Recall scope: step, stage, branch, or project"),
    include_obsolete: bool = typer.Option(False, "--include-obsolete", help="Include obsolete semantic records"),
    include_conflicted: bool = typer.Option(False, "--include-conflicted", help="Include conflicted semantic records"),
    full_artifact: bool = typer.Option(False, "--full-artifact", help="Return full stage artifact state instead of summary-only context"),
    include_history: bool = typer.Option(False, "--include-history", help="Include episodes and decision log in the response"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
    toon_output: bool = typer.Option(False, "--toon-output", help="Emit TOON for agent-oriented structured context"),
) -> None:
    """Retrieve minimal structured context for a stage."""
    ensure_structured_output_mode(json_output=json_output, toon_output=toon_output)
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    resolved_limit = limit if limit is not None else (3 if stage.strip().lower() in {"mvp.concept", "mvp.design", "mvp.tech", "mvp.architecture", "mvp.plan", "feature.init", "feature.plan"} else 5)
    result = retrieve_context(
        RetrieveMemoryContextRequest(
            project_path=project_path,
            branch_name=target_branch,
            stage=stage,
            session_key=session_key,
            step_id=step_id,
            limit=resolved_limit,
            query=query,
            disable_semantic=disable_semantic,
            recall_limit=recall_limit if recall_limit is not None else resolved_limit,
            scope=scope,
            include_obsolete=include_obsolete,
            include_conflicted=include_conflicted,
            full_artifact=full_artifact,
            include_history=include_history,
        )
    )
    payload = result.to_payload()
    if json_output:
        emit_json(payload)
        return
    if toon_output:
        emit_toon(payload)
        return

    show_banner()
    console.print(f"[cyan]Branch:[/cyan] {payload['branch']}")
    console.print(f"[cyan]Stage:[/cyan] {payload['stage']}")
    console.print(f"[cyan]Step:[/cyan] {payload['step_id'] or 'N/A'}")
    console.print(f"[cyan]Open questions:[/cyan] {len(payload['active_session']['open_questions'])}")
    console.print(f"[cyan]Facts:[/cyan] {len(payload['semantic']['facts'])}")
    console.print(f"[cyan]Decisions:[/cyan] {len(payload['semantic']['decisions'])}")
    console.print(f"[cyan]Contracts:[/cyan] {len(payload['semantic']['contracts'])}")
    console.print(f"[cyan]Policies:[/cyan] required={len(payload['policy_context']['required'])} advisory={len(payload['policy_context']['advisory'])}")
    console.print(f"[cyan]Episodes:[/cyan] {len(payload['episodes'])}")
    console.print(f"[cyan]Recall matches:[/cyan] {len(payload['recall']['merged'])}")
    summary = (payload.get("observability") or {}).get("summary") or {}
    console.print(f"[cyan]Active leases:[/cyan] {summary.get('active_lease_count', 0)}")
    console.print(f"[cyan]Pending proposals:[/cyan] {summary.get('pending_proposal_count', 0)}")
    console.print(f"[cyan]Conflicts:[/cyan] {summary.get('conflict_count', 0)}")


def memory_search(
    stage: str = typer.Option(..., "--stage", help="Target stage, e.g. mvp.plan or review"),
    query: str = typer.Option(..., "--query", help="Search query for exact, lexical, and semantic recall"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    session_key: str = typer.Option(SYSTEM_SESSION_KEY, "--session-key", help="Runtime session key; defaults to legacy active"),
    step_id: str = typer.Option(None, "--step-id", help="Optional step identifier"),
    scope: str = typer.Option("branch", "--scope", help="Search scope: step, stage, branch, or project"),
    recall_limit: int = typer.Option(5, "--recall-limit", help="Max candidates per retrieval lane"),
    disable_semantic: bool = typer.Option(False, "--disable-semantic", help="Disable semantic recall and use SQLite exact/FTS only"),
    include_obsolete: bool = typer.Option(False, "--include-obsolete", help="Include obsolete records"),
    include_conflicted: bool = typer.Option(False, "--include-conflicted", help="Include conflicted records"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Inspect hybrid recall candidates without loading full stage context."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    active_session = load_runtime_session(
        project_path,
        branch_name=target_branch,
        session_key=session_key,
    )
    payload = search_memory_store(
        project_path,
        branch_name=target_branch,
        stage=stage,
        step_id=step_id,
        query=query,
        scope=scope,
        recall_limit=recall_limit,
        disable_semantic=disable_semantic,
        include_obsolete=include_obsolete,
        include_conflicted=include_conflicted,
        active_session=active_session,
    )
    payload["observability"] = build_runtime_observability(
        project_path,
        branch_name=target_branch,
        session_key=session_key,
        stage=stage,
        step_id=step_id,
        limit=recall_limit,
    )

    if json_output:
        emit_json(payload)
        return

    show_banner()
    console.print(f"[cyan]Branch:[/cyan] {target_branch}")
    console.print(f"[cyan]Stage:[/cyan] {stage}")
    console.print(f"[cyan]Query:[/cyan] {payload['resolved_query']}")
    console.print(f"[cyan]Scope:[/cyan] {payload['scope']}")
    console.print(f"[cyan]Triggers:[/cyan] {', '.join(payload['triggers']) if payload['triggers'] else 'none'}")
    console.print(f"[cyan]Exact:[/cyan] {len(payload['exact_matches'])}")
    console.print(f"[cyan]Lexical:[/cyan] {len(payload['lexical_matches'])}")
    console.print(f"[cyan]Semantic:[/cyan] {len(payload['semantic_matches'])}")
    console.print(f"[cyan]Merged:[/cyan] {len(payload['merged'])}")
    summary = (payload.get("observability") or {}).get("summary") or {}
    console.print(f"[cyan]Runtime summary:[/cyan] leases={summary.get('active_lease_count', 0)} proposals={summary.get('pending_proposal_count', 0)} conflicts={summary.get('conflict_count', 0)}")
    for item in payload["merged"]:
        console.print(
            f"- [{item['source_type']}] {item['summary']} "
            f"(stage={item.get('stage') or 'n/a'}, step={item.get('step_id') or 'n/a'}, status={item.get('status') or 'n/a'})"
        )


def register(memory_app: typer.Typer) -> None:
    memory_app.command("retrieve")(memory_retrieve)
    memory_app.command("search")(memory_search)
