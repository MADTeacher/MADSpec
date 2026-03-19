from __future__ import annotations

from typing import Any

from ...stages.architecture.state import render_architecture_markdown
from ...stages.plan.state import render_implementation_plan_markdown
from ...stages.tech.state import render_tech_stack_markdown


def render_tech_stack(
    tech_state: dict[str, Any],
    *,
    branch_name: str,
    project_name: str,
) -> str:
    return render_tech_stack_markdown(
        tech_state,
        branch_name=branch_name,
        project_name=project_name,
    )


def render_architecture(
    architecture_state: dict[str, Any],
    *,
    branch_name: str,
    project_name: str,
) -> str:
    return render_architecture_markdown(
        architecture_state,
        branch_name=branch_name,
        project_name=project_name,
    )


def render_implementation_plan(
    plan_state: dict[str, Any],
    *,
    branch_name: str,
    progress: dict[str, Any],
    project_name: str,
) -> str:
    return render_implementation_plan_markdown(
        plan_state,
        branch_name=branch_name,
        progress=progress,
        project_name=project_name,
    )
