from __future__ import annotations

from pathlib import Path
from typing import Any

from madspec_cli.features.gates.application.common import SUPPORTED_GATE_STAGES, evaluate_gate_context
from madspec_cli.features.policy.application.common import evaluate_branch_policies
from madspec_cli.features.policy.infrastructure.storage import build_policy_context, load_policy_state, policy_summary


def build_materialization_summaries(
    project_path: Path,
    branch_name: str,
    *,
    active_session: dict[str, Any],
    progress: dict[str, Any],
    feature_mode: bool,
) -> dict[str, Any]:
    planning_stage = "feature.plan" if feature_mode else "mvp.plan"
    implementation_stage = "feature.implement" if feature_mode else "mvp.implement"
    current_gate_stage = str(active_session.get("stage", "")).strip().lower()
    if current_gate_stage not in SUPPORTED_GATE_STAGES:
        current_gate_stage = planning_stage
    current_step = active_session.get("current_step") or progress.get("currentImplementStep")
    return {
        "policy_summary": policy_summary(project_path),
        "planning_stage": planning_stage,
        "implementation_stage": implementation_stage,
        "current_gate_summary": evaluate_gate_context(
            project_path,
            branch_name,
            stage=current_gate_stage,
            operation="validate",
            step_id=current_step,
            overrides={},
            include_ratification=True,
            record_history=False,
        ),
        "review_gate_summary": evaluate_gate_context(
            project_path,
            branch_name,
            stage="review",
            operation="validate",
            overrides={},
            include_ratification=True,
            record_history=False,
        ),
        "security_gate_summary": evaluate_gate_context(
            project_path,
            branch_name,
            stage="security",
            operation="validate",
            overrides={},
            include_ratification=True,
            record_history=False,
        ),
    }


def build_step_gate_summary(
    project_path: Path,
    branch_name: str,
    *,
    stage: str,
    step_id: str,
) -> dict[str, Any]:
    return evaluate_gate_context(
        project_path,
        branch_name,
        stage=stage,
        operation="validate",
        step_id=step_id,
        overrides={},
        include_ratification=False,
        record_history=False,
    )


def build_retrieve_policy_context(
    project_path: Path,
    branch_name: str,
    *,
    stage: str,
    step_id: str | None,
    limit: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    context = build_policy_context(project_path, stage=stage)
    state = load_policy_state(project_path)
    validation = evaluate_branch_policies(
        project_path,
        branch_name,
        stage=stage,
        operation="retrieve",
        step_id=step_id,
        overrides={},
    )
    payload = {
        **context,
        "confirmations": validation["confirmations"][:limit],
        "violations": validation["violations"][:limit],
        "advisories": validation["advisories"][:limit],
    }
    return payload, state
