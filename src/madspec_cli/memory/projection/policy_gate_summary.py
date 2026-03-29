from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from madspec_cli.shared.kernel.ports import (
        BranchPolicyEvaluator,
        GateEvaluator,
        PolicyContextBuilder,
        PolicyStateLoader,
        PolicySummarizer,
    )


def _lazy_gate_imports() -> tuple:
    from madspec_cli.features.gates.application.common import (
        SUPPORTED_GATE_STAGES,
        evaluate_gate_context,
    )
    return SUPPORTED_GATE_STAGES, evaluate_gate_context


def _lazy_policy_imports() -> tuple:
    from madspec_cli.features.policy.application.common import evaluate_branch_policies
    from madspec_cli.features.policy.infrastructure.queries import (
        build_policy_context,
        policy_summary,
    )
    from madspec_cli.features.policy.infrastructure.repository import load_policy_state
    return evaluate_branch_policies, build_policy_context, load_policy_state, policy_summary


def build_materialization_summaries(
    project_path: Path,
    branch_name: str,
    *,
    active_session: dict[str, Any],
    progress: dict[str, Any],
    feature_mode: bool,
    _evaluate_gate_context: GateEvaluator | None = None,
    _policy_summary: PolicySummarizer | None = None,
    _supported_gate_stages: set[str] | None = None,
) -> dict[str, Any]:
    if _evaluate_gate_context is None or _supported_gate_stages is None:
        stages, egc = _lazy_gate_imports()
        if _supported_gate_stages is None:
            _supported_gate_stages = stages
        if _evaluate_gate_context is None:
            _evaluate_gate_context = egc
    if _policy_summary is None:
        _, _, _, _policy_summary = _lazy_policy_imports()

    planning_stage = "feature.plan" if feature_mode else "mvp.plan"
    implementation_stage = "feature.implement" if feature_mode else "mvp.implement"
    current_gate_stage = str(active_session.get("stage", "")).strip().lower()
    if current_gate_stage not in _supported_gate_stages:
        current_gate_stage = planning_stage
    current_step = active_session.get("current_step") or progress.get("currentImplementStep")
    return {
        "policy_summary": _policy_summary(project_path),
        "planning_stage": planning_stage,
        "implementation_stage": implementation_stage,
        "current_gate_summary": _evaluate_gate_context(
            project_path,
            branch_name,
            stage=current_gate_stage,
            operation="validate",
            step_id=current_step,
            overrides={},
            include_ratification=True,
            record_history=False,
        ),
        "review_gate_summary": _evaluate_gate_context(
            project_path,
            branch_name,
            stage="review",
            operation="validate",
            overrides={},
            include_ratification=True,
            record_history=False,
        ),
        "security_gate_summary": _evaluate_gate_context(
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
    _evaluate_gate_context: GateEvaluator | None = None,
) -> dict[str, Any]:
    if _evaluate_gate_context is None:
        _, _evaluate_gate_context = _lazy_gate_imports()
    return _evaluate_gate_context(
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
    _evaluate_branch_policies: BranchPolicyEvaluator | None = None,
    _build_policy_context: PolicyContextBuilder | None = None,
    _load_policy_state: PolicyStateLoader | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if _evaluate_branch_policies is None or _build_policy_context is None or _load_policy_state is None:
        ebp, bpc, lps, _ = _lazy_policy_imports()
        if _evaluate_branch_policies is None:
            _evaluate_branch_policies = ebp
        if _build_policy_context is None:
            _build_policy_context = bpc
        if _load_policy_state is None:
            _load_policy_state = lps
    context = _build_policy_context(project_path, stage=stage)
    state = _load_policy_state(project_path)
    validation = _evaluate_branch_policies(
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
