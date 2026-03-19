from __future__ import annotations

from typing import Any

from ...stages.feature_init.state import (
    render_feature_architecture_markdown,
    render_feature_context_markdown,
    render_feature_tech_stack_markdown,
    render_project_analysis_markdown,
)
from ...stages.feature_plan.state import render_feature_implementation_plan_markdown


def render_tech_stack(feature_init_state: dict[str, Any], *, branch_name: str) -> str:
    return render_feature_tech_stack_markdown(feature_init_state, branch_name=branch_name)


def render_architecture(feature_init_state: dict[str, Any], *, branch_name: str) -> str:
    return render_feature_architecture_markdown(feature_init_state, branch_name=branch_name)


def render_project_analysis(feature_init_state: dict[str, Any]) -> str:
    return render_project_analysis_markdown(feature_init_state)


def render_feature_context(feature_init_state: dict[str, Any]) -> str:
    return render_feature_context_markdown(feature_init_state)


def render_implementation_plan(
    feature_plan_state: dict[str, Any],
    *,
    branch_name: str,
    progress: dict[str, Any],
    feature_goal: str,
) -> str:
    return render_feature_implementation_plan_markdown(
        feature_plan_state,
        branch_name=branch_name,
        progress=progress,
        feature_goal=feature_goal,
    )
