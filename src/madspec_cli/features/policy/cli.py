from __future__ import annotations

from pathlib import Path

import typer

from madspec_cli.memory.domain.branch_layout import resolve_target_branch
from madspec_cli.shared.cli.banners import console, show_banner
from madspec_cli.shared.cli.json_output import emit_json

from .application.apply_policy import ApplyPolicyRequest, execute as apply_policy
from .application.deprecate_policy import DeprecatePolicyRequest, execute as deprecate_policy
from .application.explain_policy import ExplainPolicyRequest, execute as explain_policy
from .application.export_policy import ExportPolicyRequest, execute as export_policy
from .application.history_policy import HistoryPolicyRequest, execute as history_policy
from .application.init_policy import InitPolicyRequest, execute as init_policy
from .application.propose_policy import ProposePolicyRequest, execute as propose_policy
from .application.set_policy import SetPolicyRequest, execute as set_policy
from .application.show_policy import ShowPolicyRequest, execute as show_policy
from .application.validate_policy import ValidatePolicyRequest, execute as validate_policy


policy_app = typer.Typer(help="Project policy lifecycle, validation, and export")


def _emit_or_raise(payload: dict[str, object], *, json_output: bool, should_fail: bool = False) -> None:
    if json_output:
        emit_json(payload)
        if should_fail:
            raise typer.Exit(1)
        return


@policy_app.command("init")
def init(
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Initialize the project-global policy store."""
    payload = init_policy(InitPolicyRequest(project_path=Path.cwd())).to_payload()
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Policy store ready[/green] revision={payload['revision']}")
    console.print(f"[dim]State:[/dim] {payload['state_file']}")
    console.print(f"[dim]Artifact:[/dim] {payload['artifact_file']}")


@policy_app.command("show")
def show(
    stage: str = typer.Option(None, "--stage", help="Optional stage to filter effective policy context"),
    status: str = typer.Option("active", "--status", help="Policy status filter: active, deprecated, or all"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Show effective policies and pending proposals."""
    payload = show_policy(
        ShowPolicyRequest(project_path=Path.cwd(), stage=stage, status=status)
    ).to_payload()
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[cyan]Revision:[/cyan] {payload['revision']}")
    console.print(f"[cyan]Pending proposals:[/cyan] {len(payload['pending_proposals'])}")
    console.print(
        "[cyan]Effective context:[/cyan] "
        f"required={len(payload['policy_context']['required'])} "
        f"advisory={len(payload['policy_context']['advisory'])}"
    )
    for policy in payload["policies"]:
        console.print(
            f"- `{policy['policyId']}` [{policy['kind']}/{policy['enforcement']}/{policy['status']}] {policy['title']}"
        )


@policy_app.command("propose")
def propose(
    policy_id: str = typer.Option(..., "--policy-id", help="Stable policy identifier"),
    title: str = typer.Option(None, "--title", help="Human-readable title"),
    description: str = typer.Option("", "--description", help="Policy description"),
    kind: str = typer.Option("guideline", "--kind", help="Policy kind: guideline or rule"),
    enforcement: str = typer.Option("advisory", "--enforcement", help="Enforcement mode: advisory or required"),
    applies_to_stage: list[str] = typer.Option(None, "--applies-to-stage", help="Stage scope; repeat for multiple values"),
    applies_to_operation: list[str] = typer.Option(None, "--applies-to-operation", help="Operation scope; repeat for multiple values"),
    applies_to_step_kind: list[str] = typer.Option(None, "--applies-to-step-kind", help="Step kind scope; repeat for multiple values"),
    rule_type: str = typer.Option(None, "--rule-type", help="Optional supported rule type"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Create a pending policy proposal with normalized diff preview."""
    payload = propose_policy(
        ProposePolicyRequest(
            project_path=Path.cwd(),
            policy_id=policy_id,
            title=title or policy_id.replace("-", " ").title(),
            description=description,
            kind=kind,
            enforcement=enforcement,
            stages=applies_to_stage or [],
            operations=applies_to_operation or [],
            step_kinds=applies_to_step_kind or [],
            rule_type=rule_type,
            requested_by="policy.propose",
        )
    ).to_payload()
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Created proposal:[/green] {payload['proposalId']}")
    console.print(f"[cyan]Policy:[/cyan] {payload['policyId']}")
    if payload.get("warnings"):
        for warning in payload["warnings"]:
            console.print(f"[yellow]- {warning}[/yellow]")
    console.print(f"[cyan]Changed fields:[/cyan] {', '.join(payload['diff']['changedFields']) or 'none'}")


@policy_app.command("set")
def set_command(
    policy_id: str = typer.Option(..., "--policy-id", help="Stable policy identifier"),
    title: str = typer.Option(None, "--title", help="Human-readable title"),
    description: str = typer.Option("", "--description", help="Policy description"),
    kind: str = typer.Option("guideline", "--kind", help="Policy kind: guideline or rule"),
    enforcement: str = typer.Option("advisory", "--enforcement", help="Enforcement mode: advisory or required"),
    applies_to_stage: list[str] = typer.Option(None, "--applies-to-stage", help="Stage scope; repeat for multiple values"),
    applies_to_operation: list[str] = typer.Option(None, "--applies-to-operation", help="Operation scope; repeat for multiple values"),
    applies_to_step_kind: list[str] = typer.Option(None, "--applies-to-step-kind", help="Step kind scope; repeat for multiple values"),
    rule_type: str = typer.Option(None, "--rule-type", help="Optional supported rule type"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Create and immediately apply a policy proposal."""
    payload = set_policy(
        SetPolicyRequest(
            project_path=Path.cwd(),
            policy_id=policy_id,
            title=title or policy_id.replace("-", " ").title(),
            description=description,
            kind=kind,
            enforcement=enforcement,
            stages=applies_to_stage or [],
            operations=applies_to_operation or [],
            step_kinds=applies_to_step_kind or [],
            rule_type=rule_type,
            requested_by="policy.set",
        )
    ).to_payload()
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Applied policy:[/green] {policy_id}")
    console.print(f"[cyan]Proposal:[/cyan] {payload['proposal']['proposalId']}")
    console.print(f"[cyan]Revision:[/cyan] {payload['applied']['revision']}")


@policy_app.command("apply")
def apply(
    proposal_id: str = typer.Option(..., "--proposal-id", help="Pending proposal identifier"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Apply a pending proposal to the effective policy state."""
    payload = apply_policy(
        ApplyPolicyRequest(project_path=Path.cwd(), proposal_id=proposal_id)
    ).to_payload()
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Applied proposal:[/green] {proposal_id}")
    console.print(f"[cyan]Revision:[/cyan] {payload['revision']}")


@policy_app.command("deprecate")
def deprecate(
    policy_id: str = typer.Option(..., "--policy-id", help="Existing user policy identifier"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Deprecate an existing user policy through the proposal lifecycle."""
    payload = deprecate_policy(
        DeprecatePolicyRequest(project_path=Path.cwd(), policy_id=policy_id, requested_by="policy.deprecate")
    ).to_payload()
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Deprecated policy:[/green] {policy_id}")
    console.print(f"[cyan]Revision:[/cyan] {payload['revision']}")


@policy_app.command("validate")
def validate(
    stage: str = typer.Option(None, "--stage", help="Optional stage to evaluate against"),
    operation: str = typer.Option("validate", "--operation", help="Optional operation context"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    step_id: str = typer.Option(None, "--step-id", help="Optional step identifier"),
    step_kind: str = typer.Option(None, "--step-kind", help="Optional override for step kind"),
    tdd_policy: str = typer.Option(None, "--tdd-policy", help="Optional override for TDD policy"),
    tdd_phase: str = typer.Option(None, "--tdd-phase", help="Optional override for TDD phase"),
    status: str = typer.Option(None, "--status", help="Optional override for step status"),
    refactor_note: str = typer.Option(None, "--refactor-note", help="Optional override for refactor note"),
    red_evidence: list[str] = typer.Option(None, "--red-evidence", help="Optional override for red evidence"),
    green_evidence: list[str] = typer.Option(None, "--green-evidence", help="Optional override for green evidence"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Validate the current branch state against effective policies."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    payload = validate_policy(
        ValidatePolicyRequest(
            project_path=project_path,
            branch_name=target_branch,
            stage=stage,
            operation=operation,
            step_id=step_id,
            overrides={
                key: value
                for key, value in {
                    "step_kind": step_kind,
                    "tdd_policy": tdd_policy,
                    "tdd_phase": tdd_phase,
                    "status": status,
                    "refactor_note": refactor_note,
                    "red_evidence": red_evidence,
                    "green_evidence": green_evidence,
                }.items()
                if value is not None
            },
        )
    ).to_payload()
    if json_output:
        emit_json(payload)
        if not payload["valid"]:
            raise typer.Exit(1)
        return
    show_banner()
    console.print(f"[cyan]Branch:[/cyan] {target_branch}")
    console.print(f"[cyan]Violations:[/cyan] {len(payload['violations'])}")
    console.print(f"[cyan]Advisories:[/cyan] {len(payload['advisories'])}")
    console.print(f"[cyan]Confirmations:[/cyan] {len(payload['confirmations'])}")
    for violation in payload["violations"]:
        console.print(f"[red]- {violation['message']}[/red]")
    if payload["violations"]:
        raise typer.Exit(1)


@policy_app.command("history")
def history(
    policy_id: str = typer.Option(None, "--policy-id", help="Optional policy identifier filter"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Show policy proposals and applied history."""
    payload = history_policy(
        HistoryPolicyRequest(project_path=Path.cwd(), policy_id=policy_id)
    ).to_payload()
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[cyan]Events:[/cyan] {len(payload['events'])}")
    console.print(f"[cyan]Proposals:[/cyan] {len(payload['proposals'])}")
    for event in payload["events"][:10]:
        console.print(f"- [{event['eventType']}] {event['summary']}")


@policy_app.command("explain")
def explain(
    policy_id: str = typer.Option(None, "--policy-id", help="Policy identifier"),
    proposal_id: str = typer.Option(None, "--proposal-id", help="Proposal identifier"),
    stage: str = typer.Option(None, "--stage", help="Optional stage for validation context"),
    operation: str = typer.Option("validate", "--operation", help="Operation context"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to inspect"),
    step_id: str = typer.Option(None, "--step-id", help="Optional step identifier"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Explain a policy or proposal in the current branch context."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    payload = explain_policy(
        ExplainPolicyRequest(
            project_path=project_path,
            branch_name=target_branch,
            stage=stage,
            operation=operation,
            step_id=step_id,
            policy_id=policy_id,
            proposal_id=proposal_id,
        )
    ).to_payload()
    if json_output:
        emit_json(payload)
        return
    show_banner()
    policy = payload.get("policy") or {}
    console.print(f"[cyan]Policy:[/cyan] {policy.get('policyId') or payload.get('proposal', {}).get('policyId')}")
    console.print(f"[cyan]Artifact:[/cyan] {payload['artifact']}")
    for violation in payload["validation"]["violations"]:
        console.print(f"[red]- {violation['message']}[/red]")
    for advisory in payload["validation"]["advisories"]:
        console.print(f"[yellow]- {advisory['message']}[/yellow]")


@policy_app.command("export")
def export(
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Regenerate the project policy markdown artifact."""
    payload = export_policy(ExportPolicyRequest(project_path=Path.cwd())).to_payload()
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Exported:[/green] {payload['artifact_file']}")


def register(app: typer.Typer) -> None:
    app.add_typer(policy_app, name="policy")
