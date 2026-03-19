from __future__ import annotations

from pathlib import Path

import typer

from madspec_cli.shared.cli.banners import console, show_banner
from madspec_cli.shared.cli.file_input import read_args_file
from madspec_cli.shared.cli.json_output import emit_json
from madspec_cli.shared.cli.presenters import emit_error

from .application.apply_profile import ApplyProfileRequest, execute as apply_profile
from .application.create_subagent import CreateSubagentRequest, execute as create_subagent
from .application.list_subagents import ListSubagentsRequest, execute as list_subagents
from .application.profile_agents import AgentProfileRequest, execute as profile_agents
from .application.propose_profile import ProposeProfileRequest, execute as propose_profile
from .application.recommend_agents import RecommendAgentsRequest, execute as recommend_agents
from .application.remove_subagent import RemoveSubagentRequest, execute as remove_subagent
from .application.show_subagent import ShowSubagentRequest, execute as show_subagent
from .application.subagent_context import SubagentContextRequest, execute as subagent_context
from .application.toggle_subagent import ToggleSubagentRequest, execute as toggle_subagent
from .application.update_subagent import UpdateSubagentRequest, execute as update_subagent


agents_app = typer.Typer(help="Subagent profiles, recommendations, and environment adapters")
subagents_app = typer.Typer(help="Subagent role state and role-scoped context")

SUBAGENT_FROM_FILE_ALLOWED_KEYS = {
    "title",
    "description",
    "purpose",
    "defaultStage",
    "executionModeHint",
    "dependencies",
    "toolPolicy",
    "outputContract",
}
SUBAGENT_FROM_FILE_ALIASES = {
    "default_stage": "defaultStage",
    "execution_mode_hint": "executionModeHint",
    "tool_policy": "toolPolicy",
    "output_contract": "outputContract",
}


@agents_app.command("profile")
def profile(
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    payload = profile_agents(AgentProfileRequest(project_path=Path.cwd())).to_payload()
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[cyan]Environment:[/cyan] {payload['environment']['environmentId']}")
    console.print(f"[cyan]Profile:[/cyan] {payload['profile']['profileId']}")
    console.print(f"[cyan]State:[/cyan] {payload['state_file']}")
    enabled = [item["subagentId"] for item in payload["profile"]["subagents"] if item.get("enabled")]
    console.print(f"[cyan]Enabled subagents:[/cyan] {', '.join(enabled) if enabled else 'none'}")


@agents_app.command("recommend")
def recommend(
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    payload = recommend_agents(RecommendAgentsRequest(project_path=Path.cwd())).to_payload()
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[cyan]Environment:[/cyan] {payload['environment']['environmentId']}")
    console.print(f"[cyan]Profile:[/cyan] {payload['profileId']}")
    console.print(payload["summary"])
    for item in payload["recommendedSubagents"]:
        console.print(f"- `{item['subagentId']}` [{item['renderMode']}] {item['description']}")


@agents_app.command("propose-profile")
def propose_profile_command(
    profile_id: str = typer.Option("default", "--profile-id", help="Profile identifier"),
    environment: str = typer.Option(None, "--environment", help="Optional environment override"),
    subagent: list[str] = typer.Option(None, "--subagent", help="Enable subagent in proposed profile; repeat for multiple values"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    payload = propose_profile(
        ProposeProfileRequest(
            project_path=Path.cwd(),
            environment_id=environment,
            profile_id=profile_id,
            enabled_subagents=subagent or None,
            requested_by="agents.propose-profile",
        )
    ).to_payload()
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Created proposal:[/green] {payload['proposalId']}")
    console.print(f"[cyan]Environment:[/cyan] {payload['environmentId']}")
    console.print(f"[cyan]Changed fields:[/cyan] {', '.join(payload['diff']['changedFields']) or 'none'}")


@agents_app.command("apply-profile")
def apply_profile_command(
    proposal_id: str = typer.Option(..., "--proposal-id", help="Pending proposal identifier"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    try:
        payload = apply_profile(
            ApplyProfileRequest(project_path=Path.cwd(), proposal_id=proposal_id)
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Applied proposal:[/green] {proposal_id}")
    console.print(f"[cyan]Rendered files:[/cyan] {len(payload['rendered']['created'])}")


@subagents_app.command("list")
def list_command(
    enabled_only: bool = typer.Option(False, "--enabled-only", help="Show only enabled subagents"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    payload = list_subagents(
        ListSubagentsRequest(project_path=Path.cwd(), enabled_only=enabled_only)
    ).to_payload()
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[cyan]Environment:[/cyan] {payload['environmentId']}")
    for item in payload["subagents"]:
        console.print(f"- `{item['subagentId']}` enabled={item['enabled']} [{item['renderMode']}] {item['description']}")


@subagents_app.command("show")
def show_command(
    subagent_id: str = typer.Option(..., "--subagent-id", help="Subagent identifier"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    try:
        payload = show_subagent(
            ShowSubagentRequest(project_path=Path.cwd(), subagent_id=subagent_id)
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[cyan]Subagent:[/cyan] {payload['subagentId']}")
    console.print(f"[cyan]Origin:[/cyan] {payload.get('origin')}")
    console.print(f"[cyan]Enabled:[/cyan] {payload.get('enabled')}")
    console.print(f"[cyan]Body source:[/cyan] {payload.get('bodySource')}")
    console.print(payload["description"])


@subagents_app.command("create")
def create_command(
    subagent_id: str = typer.Option(..., "--subagent-id", help="Subagent identifier"),
    from_file: str = typer.Option(..., "--from-file", help="Path to JSON file with subagent metadata"),
    body_file: str = typer.Option(..., "--body-file", help="Path to Markdown file with subagent body"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    try:
        payload_data = read_args_file(
            from_file,
            aliases=SUBAGENT_FROM_FILE_ALIASES,
            allowed_keys=SUBAGENT_FROM_FILE_ALLOWED_KEYS,
        )
        body_text = Path(body_file).read_text(encoding="utf-8")
        payload = create_subagent(
            CreateSubagentRequest(
                project_path=Path.cwd(),
                subagent_id=subagent_id,
                payload=payload_data,
                body_text=body_text,
            )
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Created subagent:[/green] {subagent_id}")


@subagents_app.command("update")
def update_command(
    subagent_id: str = typer.Option(..., "--subagent-id", help="Subagent identifier"),
    from_file: str = typer.Option(..., "--from-file", help="Path to JSON file with subagent metadata"),
    body_file: str = typer.Option(None, "--body-file", help="Optional Markdown file with subagent body"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    try:
        payload_data = read_args_file(
            from_file,
            aliases=SUBAGENT_FROM_FILE_ALIASES,
            allowed_keys=SUBAGENT_FROM_FILE_ALLOWED_KEYS,
        )
        body_text = Path(body_file).read_text(encoding="utf-8") if body_file else None
        payload = update_subagent(
            UpdateSubagentRequest(
                project_path=Path.cwd(),
                subagent_id=subagent_id,
                payload=payload_data,
                body_text=body_text,
            )
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Updated subagent:[/green] {subagent_id}")


@subagents_app.command("remove")
def remove_command(
    subagent_id: str = typer.Option(..., "--subagent-id", help="Subagent identifier"),
    force: bool = typer.Option(False, "--force", help="Remove even if the subagent is enabled"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    try:
        payload = remove_subagent(
            RemoveSubagentRequest(
                project_path=Path.cwd(),
                subagent_id=subagent_id,
                force=force,
            )
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Removed subagent:[/green] {subagent_id}")


@subagents_app.command("enable")
def enable_command(
    subagent_id: str = typer.Option(..., "--subagent-id", help="Subagent identifier"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    try:
        payload = toggle_subagent(
            ToggleSubagentRequest(project_path=Path.cwd(), subagent_id=subagent_id, enabled=True)
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Enabled subagent:[/green] {subagent_id}")


@subagents_app.command("disable")
def disable_command(
    subagent_id: str = typer.Option(..., "--subagent-id", help="Subagent identifier"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    try:
        payload = toggle_subagent(
            ToggleSubagentRequest(project_path=Path.cwd(), subagent_id=subagent_id, enabled=False)
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Disabled subagent:[/green] {subagent_id}")


@subagents_app.command("context")
def context_command(
    subagent_id: str = typer.Option(..., "--subagent-id", help="Subagent identifier"),
    branch_name: str = typer.Option(None, "--branch", help="Optional branch override"),
    stage: str = typer.Option(None, "--stage", help="Optional stage override"),
    step_id: str = typer.Option(None, "--step-id", help="Optional step identifier"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    try:
        payload = subagent_context(
            SubagentContextRequest(
                project_path=Path.cwd(),
                subagent_id=subagent_id,
                branch_name=branch_name,
                stage=stage,
                step_id=step_id,
            )
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[cyan]Subagent:[/cyan] {payload['subagent']['subagentId']}")
    console.print(f"[cyan]Branch:[/cyan] {payload['branch']}")
    console.print(f"[cyan]Stage:[/cyan] {payload['stage']}")
    console.print(f"[cyan]Policy confirmations:[/cyan] {len(payload['policy']['policy_context']['required'])}")
    console.print(f"[cyan]Gate status:[/cyan] {payload['gates']['overall_status']}")


def register(app: typer.Typer) -> None:
    agents_app.add_typer(subagents_app, name="subagents")
    app.add_typer(agents_app, name="agents")
