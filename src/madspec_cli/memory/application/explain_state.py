from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from madspec_cli.features.gates.application.common import evaluate_gate_context
from madspec_cli.memory.shared.system_store.constants import SYSTEM_SESSION_KEY
from madspec_cli.shared.kernel.result import PayloadResult

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


def execute(request: ExplainStateRequest) -> ExplainStateResult:
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
    gate_summary = evaluate_gate_context(
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
    summary = {
        "stage": request.stage,
        "step_id": context.get("step_id"),
        "selected_step": (next_step_analysis or {}).get("selected_step"),
        "next_step_reason": (next_step_analysis or {}).get("reason"),
        "active_goal": context["active_session"].get("active_goal"),
        "open_questions_count": len(context["active_session"].get("open_questions", [])),
        "recall_match_count": len(context["recall"].get("merged", [])),
    }

    return ExplainStateResult(
        payload={
            "branch": request.branch_name,
            "stage": request.stage,
            "step_id": context.get("step_id"),
            "summary": summary,
            "context": {
                "active_session": context["active_session"],
                "workflow": context["workflow"],
                "step": context["step"],
                "stage_memory": context["stage_memory"],
                "semantic": context["semantic"],
                "change_context": context.get("change_context"),
                "status_views": status_views,
                "gate_summary": gate_summary,
            },
            "influences": influences,
            "gate_summary": gate_summary,
            "policy_effects": context["policy_context"],
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
