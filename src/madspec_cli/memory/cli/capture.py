from __future__ import annotations

from pathlib import Path

import typer

from madspec_cli.memory.stage_capture import CAPTURE_STAGES
from madspec_cli.shared.cli.banners import console, show_banner
from madspec_cli.shared.cli.json_output import emit_json

from ..application.capture_stage import CaptureStageRequest, execute as capture_stage
from ..domain.branch_layout import resolve_target_branch


def memory_capture(
    stage: str = typer.Option(..., "--stage", help="Stage to capture: mvp.concept, mvp.design, mvp.tech, mvp.architecture, mvp.plan, feature.init, feature.plan, review, or security"),
    summary: str = typer.Option(None, "--summary", help="Optional stage note summary"),
    fact: list[str] = typer.Option(None, "--fact", help="Fact to capture; repeat for multiple values"),
    decision: list[str] = typer.Option(None, "--decision", help="Decision to capture; repeat for multiple values"),
    contract: list[str] = typer.Option(None, "--contract", help="Contract/constraint to capture; repeat for multiple values"),
    evidence: list[str] = typer.Option(None, "--evidence", help="Supporting evidence path or note; repeat for multiple values"),
    question: list[str] = typer.Option(None, "--question", help="Open question to add to active session; repeat for multiple values"),
    pending_action: list[str] = typer.Option(None, "--pending-action", help="Pending action to add to active session; repeat for multiple values"),
    project_name: str = typer.Option(None, "--project-name", help="Concept-only: project name to store in canonical concept state"),
    system_overview: str = typer.Option(None, "--system-overview", help="Concept-only: short general description of the system"),
    audience: list[str] = typer.Option(None, "--audience", help="Concept-only: audience entry; repeat for multiple values"),
    scenario: list[str] = typer.Option(None, "--scenario", help="Concept-only: usage scenario; repeat for multiple values"),
    pain: list[str] = typer.Option(None, "--pain", help="Concept-only: pain point; repeat for multiple values"),
    feature_p1: list[str] = typer.Option(None, "--feature-p1", help="Concept-only: P1 feature in '<name>::<description>' format; repeat for multiple values"),
    feature_p2: list[str] = typer.Option(None, "--feature-p2", help="Concept-only: P2 feature in '<name>::<description>' format; repeat for multiple values"),
    feature_p3: list[str] = typer.Option(None, "--feature-p3", help="Concept-only: P3 feature in '<name>::<description>' format; repeat for multiple values"),
    constraint: list[str] = typer.Option(None, "--constraint", help="Concept-only: technical constraint; repeat for multiple values"),
    assumption: list[str] = typer.Option(None, "--assumption", help="Concept-only: assumption; repeat for multiple values"),
    next_action: list[str] = typer.Option(None, "--next-action", help="Concept/design/tech/plan-only: canonical next action; repeat for multiple values"),
    design_overview: str = typer.Option(None, "--design-overview", help="Design-only: short summary of the UI/UX approach"),
    platform: list[str] = typer.Option(None, "--platform", help="Design-only: supported platform; repeat for multiple values"),
    zone: list[str] = typer.Option(None, "--zone", help="Design-only: zone in '<id>::<title>::<description>' format; repeat for multiple values"),
    screen: list[str] = typer.Option(None, "--screen", help="Design-only: screen in '<id>::<title>::<zone>::<prototype>::<purpose>' format; repeat for multiple values"),
    screen_feature: list[str] = typer.Option(None, "--screen-feature", help="Design-only: screen coverage in '<screen-id>::<priority>::<feature-name>' format; repeat for multiple values"),
    flow: list[str] = typer.Option(None, "--flow", help="Design-only: flow in '<id>::<title>::<goal>' format; repeat for multiple values"),
    flow_step: list[str] = typer.Option(None, "--flow-step", help="Design-only: flow step in '<flow-id>::<screen-id>::<action>::<result>' format; repeat for multiple values"),
    flow_alternative: list[str] = typer.Option(None, "--flow-alternative", help="Design-only: alternative path in '<flow-id>::<description>' format; repeat for multiple values"),
    nav: list[str] = typer.Option(None, "--nav", help="Design-only: navigation link in '<from-screen>::<to-screen>::<trigger>' format; repeat for multiple values"),
    platform_constraint: list[str] = typer.Option(None, "--platform-constraint", help="Design-only: platform or interaction constraint; repeat for multiple values"),
    screen_data: list[str] = typer.Option(None, "--screen-data", help="Design-only: screen data in '<screen-id>::<displayed|input>::<name>' format; repeat for multiple values"),
    stack_overview: str = typer.Option(None, "--stack-overview", help="Tech-only: short summary of the chosen stack"),
    project_type: str = typer.Option(None, "--project-type", help="Tech-only: project type, e.g. web, mobile, desktop, or API"),
    framework: str = typer.Option(None, "--framework", help="Feature-init-only: detected framework or platform stack"),
    requirement: list[str] = typer.Option(None, "--requirement", help="Tech-only: technical requirement; repeat for multiple values"),
    structure_note: list[str] = typer.Option(None, "--structure-note", help="Feature-init-only: project structure note; repeat for multiple values"),
    preference: list[str] = typer.Option(None, "--preference", help="Tech-only: preferred technology or direction; repeat for multiple values"),
    tech_constraint: list[str] = typer.Option(None, "--tech-constraint", help="Tech-only: technical constraint; repeat for multiple values"),
    stack_component: list[str] = typer.Option(None, "--stack-component", help="Tech-only: component in '<slot>::<name>::<version>::<rationale>' format; repeat for multiple values"),
    library: list[str] = typer.Option(None, "--library", help="Tech-only: library in '<scope>::<name>::<version>::<purpose>' format; repeat for multiple values"),
    code_organization: str = typer.Option(None, "--code-organization", help="Tech-only: code organization in '<repo-strategy>::<source-layout>::<modularity>::<rationale>' format"),
    alternative: list[str] = typer.Option(None, "--alternative", help="Tech-only: rejected alternative in '<slot>::<option>::<reason-rejected>' format; repeat for multiple values"),
    architecture_overview: str = typer.Option(None, "--architecture-overview", help="Architecture-only: short summary of the chosen architecture"),
    project_structure: str = typer.Option(None, "--project-structure", help="Architecture-only: project structure in '<strategy>::<rationale>' format"),
    directory: list[str] = typer.Option(None, "--directory", help="Architecture-only: directory in '<path>::<purpose>' format; repeat for multiple values"),
    entity: list[str] = typer.Option(None, "--entity", help="Architecture-only: entity in '<name>::<description>' format; repeat for multiple values"),
    entity_field: list[str] = typer.Option(None, "--entity-field", help="Architecture-only: entity field in '<entity>::<field>::<type>::<required|optional>::<description>' format; repeat for multiple values"),
    entity_relationship: list[str] = typer.Option(None, "--entity-relationship", help="Architecture-only: entity relationship in '<entity>::<target>::<kind>::<description>' format; repeat for multiple values"),
    entity_state: list[str] = typer.Option(None, "--entity-state", help="Architecture-only: entity state in '<entity>::<state>::<description>' format; repeat for multiple values"),
    endpoint: list[str] = typer.Option(None, "--endpoint", help="Architecture-only: endpoint in '<operation-id>::<METHOD>::</path>::<summary>' format; repeat for multiple values"),
    endpoint_screen: list[str] = typer.Option(None, "--endpoint-screen", help="Architecture-only: endpoint to screen link in '<operation-id>::<screen-id>' format; repeat for multiple values"),
    endpoint_field: list[str] = typer.Option(None, "--endpoint-field", help="Architecture-only: endpoint field in '<operation-id>::<section>::<name>::<type>::<required|optional>::<description>' format; repeat for multiple values"),
    endpoint_error: list[str] = typer.Option(None, "--endpoint-error", help="Architecture-only: endpoint error in '<operation-id>::<status>::<code>::<description>' format; repeat for multiple values"),
    integration: list[str] = typer.Option(None, "--integration", help="Architecture-only: integration in '<name>::<kind>::<purpose>::<touchpoints>' format; repeat for multiple values"),
    code_principle: list[str] = typer.Option(None, "--code-principle", help="Architecture-only: code principle; repeat for multiple values"),
    pattern: list[str] = typer.Option(None, "--pattern", help="Architecture-only: pattern in '<name>::<rationale>' format; repeat for multiple values"),
    security_note: list[str] = typer.Option(None, "--security-note", help="Architecture-only: security note; repeat for multiple values"),
    performance_note: list[str] = typer.Option(None, "--performance-note", help="Architecture-only: performance note; repeat for multiple values"),
    plan_overview: str = typer.Option(None, "--plan-overview", help="Plan-only: short summary of the implementation strategy"),
    planning_principle: list[str] = typer.Option(None, "--planning-principle", help="Plan-only: planning principle or invariant; repeat for multiple values"),
    feature_goal: str = typer.Option(None, "--feature-goal", help="Feature-init-only: concise statement of the feature goal"),
    problem: str = typer.Option(None, "--problem", help="Feature-init-only: problem the feature solves"),
    expected_outcome: str = typer.Option(None, "--expected-outcome", help="Feature-init-only: expected result after delivery"),
    existing_module: list[str] = typer.Option(None, "--existing-module", help="Feature-init-only: existing module in '<name>::<path>::<description>' format; repeat for multiple values"),
    modified_file: list[str] = typer.Option(None, "--modified-file", help="Feature-init-only: modified file in '<path>::<reason>::<function-id,...>' format; repeat for multiple values"),
    new_file: list[str] = typer.Option(None, "--new-file", help="Feature-init-only: new file in '<path>::<reason>::<function-id,...>' format; repeat for multiple values"),
    interface_contract: list[str] = typer.Option(None, "--interface-contract", help="Feature-init-only: interface or contract note; repeat for multiple values"),
    dependency: list[str] = typer.Option(None, "--dependency", help="Feature-init-only: dependency in '<scope>::<name>::<description>' format; repeat for multiple values"),
    risk: list[str] = typer.Option(None, "--risk", help="Feature-init-only: risk note; repeat for multiple values"),
    recommendation: list[str] = typer.Option(None, "--recommendation", help="Feature-init-only: integration recommendation; repeat for multiple values"),
    tech_note: list[str] = typer.Option(None, "--tech-note", help="Feature-init-only: tech context note; repeat for multiple values"),
    architecture_note: list[str] = typer.Option(None, "--architecture-note", help="Feature-init-only: architecture impact note; repeat for multiple values"),
    status: str = typer.Option("validated", "--status", help="Memory record status: proposed, validated, conflicted, or obsolete"),
    branch_name: str = typer.Option(None, "--branch", help="Branch name to update"),
    json_output: bool = typer.Option(False, "--json-output", help="Emit machine-readable JSON"),
) -> None:
    """Capture incremental non-iterative stage memory before final checkpoint."""
    project_path = Path.cwd()
    target_branch = resolve_target_branch(project_path, branch_name)
    result = capture_stage(
        CaptureStageRequest(
            project_path=project_path,
            branch_name=target_branch,
            stage=stage,
            options={
                "summary": summary,
                "facts": fact or [],
                "decisions": decision or [],
                "contracts": contract or [],
                "evidence": evidence or [],
                "questions": question or [],
                "pending_actions": pending_action or [],
                "project_name": project_name,
                "system_overview": system_overview,
                "audiences": audience or [],
                "scenarios": scenario or [],
                "pain_points": pain or [],
                "feature_p1": feature_p1 or [],
                "feature_p2": feature_p2 or [],
                "feature_p3": feature_p3 or [],
                "constraints": constraint or [],
                "assumptions": assumption or [],
                "next_actions": next_action or [],
                "design_overview": design_overview,
                "platforms": platform or [],
                "zones": zone or [],
                "screens": screen or [],
                "screen_features": screen_feature or [],
                "flows": flow or [],
                "flow_steps": flow_step or [],
                "flow_alternatives": flow_alternative or [],
                "navigation": nav or [],
                "platform_constraints": platform_constraint or [],
                "screen_data": screen_data or [],
                "stack_overview": stack_overview,
                "project_type": project_type,
                "framework": framework,
                "requirements": requirement or [],
                "structure_notes": structure_note or [],
                "preferences": preference or [],
                "tech_constraints": tech_constraint or [],
                "stack_components": stack_component or [],
                "libraries": library or [],
                "code_organization": code_organization,
                "alternatives": alternative or [],
                "architecture_overview": architecture_overview,
                "project_structure": project_structure,
                "directories": directory or [],
                "entities": entity or [],
                "entity_fields": entity_field or [],
                "entity_relationships": entity_relationship or [],
                "entity_states": entity_state or [],
                "endpoints": endpoint or [],
                "endpoint_screens": endpoint_screen or [],
                "endpoint_fields": endpoint_field or [],
                "endpoint_errors": endpoint_error or [],
                "integrations": integration or [],
                "code_principles": code_principle or [],
                "architecture_patterns": pattern or [],
                "security_notes": security_note or [],
                "performance_notes": performance_note or [],
                "plan_overview": plan_overview,
                "planning_principles": planning_principle or [],
                "feature_goal": feature_goal,
                "problem": problem,
                "expected_outcome": expected_outcome,
                "existing_modules": existing_module or [],
                "modified_files": modified_file or [],
                "new_files": new_file or [],
                "interface_contracts": interface_contract or [],
                "dependencies": dependency or [],
                "risks": risk or [],
                "recommendations": recommendation or [],
                "tech_notes": tech_note or [],
                "architecture_notes": architecture_note or [],
                "status": status,
            },
        )
    )

    payload = result.to_payload()
    if json_output:
        emit_json(payload)
        if not result.accepted:
            raise typer.Exit(1)
        return

    show_banner()
    console.print(f"[cyan]Branch:[/cyan] {target_branch}")
    console.print(f"[cyan]Stage:[/cyan] {stage}")
    if result.accepted:
        written = payload["written"]
        console.print(f"[green]Captured stage memory:[/green] {stage}")
        console.print(
            "[cyan]Records:[/cyan] "
            f"notes={written['notes']} "
            f"facts={written['facts']} "
            f"decisions={written['decisions']} "
            f"contracts={written['contracts']} "
            f"questions={written['questions']} "
            f"pending_actions={written['pending_actions']}"
        )
        return

    console.print("[red]Capture rejected.[/red] " f"Allowed stages: {', '.join(sorted(CAPTURE_STAGES))}")
    for error in payload.get("errors", []):
        console.print(f"[red]- {error}[/red]")
    raise typer.Exit(1)


def register(memory_app: typer.Typer) -> None:
    memory_app.command("capture")(memory_capture)
