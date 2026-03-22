from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from madspec_cli.memory.shared.system_store.constants import SYSTEM_SESSION_KEY
from madspec_cli.shared.kernel.result import PayloadResult

if TYPE_CHECKING:
    from madspec_cli.shared.kernel.ports import GateEvaluator

from .observability import build_runtime_observability
from .retrieve_context import RetrieveMemoryContextRequest, execute as retrieve_context
from .why_next_step import WhyNextStepRequest, execute as explain_next_step

STATUS_VIEW_KEYS = (
    "concept_status",
    "design_status",
    "tech_status",
    "architecture_status",
    "plan_status",
    "feature_init_status",
    "feature_plan_status",
)


@dataclass(frozen=True)
class ExplainStateRequest:
    project_path: Path
    branch_name: str
    stage: str
    step_id: str | None
    limit: int
    query: str | None
    disable_semantic: bool
    recall_limit: int
    scope: str
    include_obsolete: bool
    include_conflicted: bool
    include_history: bool
    session_key: str = SYSTEM_SESSION_KEY


@dataclass(frozen=True)
class ExplainStateResult(PayloadResult):
    pass


def execute(
    request: ExplainStateRequest,
    *,
    _evaluate_gate_context: GateEvaluator | None = None,
) -> ExplainStateResult:
    if _evaluate_gate_context is None:
        from madspec_cli.features.gates.application.common import evaluate_gate_context
        _evaluate_gate_context = evaluate_gate_context

    context = retrieve_context(
        RetrieveMemoryContextRequest(
            project_path=request.project_path,
            branch_name=request.branch_name,
            stage=request.stage,
            session_key=request.session_key,
            step_id=request.step_id,
            limit=request.limit,
            query=request.query,
            disable_semantic=request.disable_semantic,
            recall_limit=request.recall_limit,
            scope=request.scope,
            include_obsolete=request.include_obsolete,
            include_conflicted=request.include_conflicted,
            full_artifact=False,
            include_history=request.include_history,
        )
    ).to_payload()

    next_step_analysis = None
    if "plan" in request.stage.lower() or "implement" in request.stage.lower():
        next_step_analysis = explain_next_step(
            WhyNextStepRequest(
                project_path=request.project_path,
                branch_name=request.branch_name,
                stage=request.stage,
            )
        ).to_payload()

    influences = _build_influences(context, limit=request.limit)
    gate_summary = _evaluate_gate_context(
        request.project_path,
        request.branch_name,
        stage=request.stage,
        operation="validate",
        session_key=request.session_key,
        step_id=context.get("step_id"),
        overrides={},
        include_ratification=True,
        record_history=False,
    )
    status_views = {
        key: context[key]
        for key in STATUS_VIEW_KEYS
        if context.get(key) is not None
    }
    workflow = context["workflow"]
    active_session = context["active_session"]
    proposal_summary = ((context.get("coordination") or {}).get("proposal_summary")) or {}
    coordinator = ((context.get("coordination") or {}).get("coordinator")) or {}
    observability = context.get("observability") or build_runtime_observability(
        request.project_path,
        branch_name=request.branch_name,
        session_key=request.session_key,
        stage=request.stage,
        step_id=context.get("step_id"),
        limit=request.limit,
    )
    latest_runtime_outcome = _latest_runtime_outcome(observability)
    summary = {
        "stage": request.stage,
        "step_id": context.get("step_id"),
        "selected_step": (next_step_analysis or {}).get("selected_step"),
        "next_step_reason": (next_step_analysis or {}).get("reason"),
        "session_key": request.session_key,
        "session_current_step": active_session.get("current_step"),
        "shared_current_implement_step": workflow.get("currentImplementStep"),
        "next_executable_step": workflow.get("nextExecutableStep"),
        "last_planned_step": workflow.get("lastPlannedStep"),
        "planning_phase": workflow.get("planningPhase"),
        "progress_metrics": workflow.get("progressMetrics", {}),
        "active_goal": active_session.get("active_goal"),
        "open_questions_count": len(active_session.get("open_questions", [])),
        "recall_match_count": len(context["recall"].get("merged", [])),
        "task_id": (context.get("coordination") or {}).get("session_binding", {}).get("task_id"),
        "work_item_id": (context.get("coordination") or {}).get("session_binding", {}).get("work_item_id"),
        "pending_proposals_count": proposal_summary.get("pending_count", 0),
        "last_proposal_status": proposal_summary.get("last_proposal_status"),
        "related_proposal_ids": proposal_summary.get("related_proposal_ids", []),
        "coordinator_readiness": ((context.get("coordination") or {}).get("readiness") or {}).get("status"),
        "latest_runtime_outcome": latest_runtime_outcome,
    }

    return ExplainStateResult(
        payload={
            "branch": request.branch_name,
            "stage": request.stage,
            "runtime_revision": context.get("runtime_revision"),
            "step_id": context.get("step_id"),
            "summary": summary,
            "context": {
                "active_session": context["active_session"],
                "workflow": context["workflow"],
                "step": context["step"],
                "stage_memory": context["stage_memory"],
                "semantic": context["semantic"],
                "coordination": context.get("coordination"),
                "coordinator": coordinator,
                "change_context": context.get("change_context"),
                "status_views": status_views,
                "gate_summary": gate_summary,
                "observability": observability,
            },
            "influences": influences,
            "gate_summary": gate_summary,
            "policy_effects": context["policy_context"],
            "observability": observability,
            "latest_runtime_outcome": latest_runtime_outcome,
            "recall_explanation": {
                "query": context["recall"].get("query"),
                "resolved_query": context["recall"].get("resolved_query"),
                "semantic_enabled": context["recall"].get("semantic_enabled"),
                "triggers": context["recall"].get("triggers", []),
                "merged_count": len(context["recall"].get("merged", [])),
                "top_matches": context["recall"].get("merged", [])[: request.limit],
            },
        }
    )


def _build_influences(context: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
    influences: list[dict[str, Any]] = []

    for item in context["stage_memory"].get("facts", []):
        influences.append(_record_influence("stage_fact", item, "validated stage fact"))
    for item in context["stage_memory"].get("decisions", []):
        influences.append(_record_influence("stage_decision", item, "stage decision"))
    for item in context["stage_memory"].get("contracts", []):
        influences.append(_record_influence("stage_contract", item, "stage contract"))
    for item in context["stage_memory"].get("notes", []):
        influences.append(_record_influence("stage_note", item, "stage note or event"))

    for kind in ("facts", "decisions", "contracts"):
        for item in context["semantic"].get(kind, [])[:limit]:
            influences.append(
                _record_influence(
                    f"semantic_{kind[:-1]}",
                    item,
                    f"semantic {kind[:-1]} used in retrieval context",
                )
            )

    for item in context["policy_context"].get("violations", []):
        influences.append(
            {
                "kind": "policy_violation",
                "source_type": "policy",
                "source_id": item.get("policyId"),
                "summary": item.get("message"),
                "why": "policy violation affects the current stage context",
            }
        )
    for item in context["policy_context"].get("confirmations", []):
        influences.append(
            {
                "kind": "policy_confirmation",
                "source_type": "policy",
                "source_id": item.get("policyId"),
                "summary": item.get("message"),
                "why": "policy confirmation supports the current state",
            }
        )
    for item in context["recall"].get("merged", [])[:limit]:
        influences.append(
            {
                "kind": "recall_match",
                "source_type": item.get("source_type"),
                "source_id": item.get("source_id"),
                "summary": item.get("summary"),
                "why": "hybrid recall promoted this item into the working context",
            }
        )
    change_context = context.get("change_context") or {}
    if change_context.get("initialized") and change_context.get("title"):
        influences.append(
            {
                "kind": "change_bundle",
                "source_type": "change",
                "source_id": change_context.get("bundle_id"),
                "summary": change_context.get("summary") or change_context.get("title"),
                "why": "the active change bundle frames review/security context for the branch",
            }
        )

    return influences[: limit * 4]


def _record_influence(kind: str, item: dict[str, Any], why: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "source_type": "record",
        "source_id": item.get("id"),
        "summary": item.get("summary"),
        "why": why,
    }


def _latest_runtime_outcome(observability: dict[str, Any]) -> dict[str, Any] | None:
    proposal_state = observability.get("proposal_state") or {}
    latest = proposal_state.get("latest")
    if latest is not None:
        apply_summary = latest.get("apply_summary") or {}
        result = apply_summary.get("result") or {}
        kind = result.get("kind")
        if latest.get("status") == "applied":
            return {
                "outcome": "merged",
                "reason": apply_summary.get("reason") or "applied",
                "proposal_id": latest.get("proposal_id"),
            }
        if kind == "scope_busy":
            return {
                "outcome": "blocked_by_lease",
                "reason": apply_summary.get("reason") or "scope_conflict",
                "proposal_id": latest.get("proposal_id"),
            }
        if latest.get("status") == "conflict":
            return {
                "outcome": "conflict",
                "reason": apply_summary.get("reason") or "conflict",
                "proposal_id": latest.get("proposal_id"),
            }
        if latest.get("status") == "rejected":
            return {
                "outcome": "rejected",
                "reason": apply_summary.get("reason") or "rejected",
                "proposal_id": latest.get("proposal_id"),
            }

    stuck_leases = ((observability.get("active_leases") or {}).get("stuck")) or []
    if stuck_leases:
        lease = stuck_leases[0]
        return {
            "outcome": "blocked_by_lease",
            "reason": "stuck_lease",
            "lease_name": lease.get("lease_name"),
        }
    return None
