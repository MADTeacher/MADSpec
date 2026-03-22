from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..domain.conflicts import PROJECT_MEMORY_BRANCH, semantic_fingerprint

if TYPE_CHECKING:
    from madspec_cli.shared.kernel.ports import ChangeContextBuilder, ChangeStateLoader
from ..domain.progress import select_next_executable_step
from ..domain.step_resolution import resolve_runtime_step_id
from ..shared.system_store.canonical_state import load_canonical_branch_state
from ..shared.system_store.constants import SYSTEM_SESSION_KEY
from ..shared.storage import read_jsonl as _read_jsonl
from ..stages.design.state import load_design_state
from .context_loader import load_retrieve_projection_state
from .policy_gate_summary import build_retrieve_policy_context
from .projections import (
    build_architecture_status,
    build_concept_status,
    build_deploy_status,
    build_design_status,
    build_feature_init_status,
    build_feature_plan_status,
    build_plan_status,
    build_tech_status,
    filter_records_by_status,
)

read_jsonl = _read_jsonl


def _trim(records: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return sorted(
        records,
        key=lambda item: (item.get("ts", ""), item.get("id", "")),
        reverse=True,
    )[:limit]


def retrieve_memory_context(
    project_path: Path,
    branch_name: str,
    stage: str,
    *,
    session_key: str = SYSTEM_SESSION_KEY,
    step_id: str | None = None,
    limit: int | None = None,
    query: str | None = None,
    disable_semantic: bool = False,
    recall_limit: int | None = None,
    scope: str = "branch",
    include_obsolete: bool = False,
    include_conflicted: bool = False,
    full_artifact: bool = False,
    include_history: bool = False,
    include_coordination: bool = True,
    _build_change_context: ChangeContextBuilder | None = None,
    _load_change_state: ChangeStateLoader | None = None,
) -> dict[str, Any]:
    from ..shared.system_store import search_memory_store
    from ..shared.system_store.store import MemoryStore

    store = MemoryStore(project_path)
    stage_lower = stage.lower()
    is_stage_artifact = stage_lower in {
        "mvp.concept",
        "mvp.design",
        "mvp.tech",
        "deploy",
        "mvp.architecture",
        "mvp.plan",
        "feature.init",
        "feature.plan",
    }
    state = load_retrieve_projection_state(
        project_path,
        branch_name,
        stage_lower,
        session_key=session_key,
    )
    if _build_change_context is None or _load_change_state is None:
        from madspec_cli.features.change.infrastructure.storage import (
            build_change_context as _bcc,
            load_change_state as _lcs,
        )
        if _build_change_context is None:
            _build_change_context = _bcc
        if _load_change_state is None:
            _load_change_state = _lcs
    change_context = _build_change_context(project_path, branch_name)
    change_state = _load_change_state(project_path, branch_name)
    canonical = load_canonical_branch_state(project_path, branch_name)
    resolved_limit = 3 if limit is None or limit <= 0 else limit
    if not is_stage_artifact and (limit is None or limit <= 0):
        resolved_limit = 5
    include_history_records = include_history or not is_stage_artifact
    decision_log = list(canonical.record_streams["decision_log"]) if include_history_records else []
    events = list(canonical.record_streams["events"]) if include_history_records else []
    semantic_sets = {
        "validated": {
            "facts": filter_records_by_status(
                canonical.record_streams["facts"],
                include_obsolete=include_obsolete,
                include_conflicted=include_conflicted,
            ),
            "decisions": filter_records_by_status(
                canonical.record_streams["decisions"],
                include_obsolete=include_obsolete,
                include_conflicted=include_conflicted,
            ),
            "contracts": filter_records_by_status(
                canonical.record_streams["contracts"],
                include_obsolete=include_obsolete,
                include_conflicted=include_conflicted,
            ),
        },
        "stage": {
            "facts": filter_records_by_status(
                canonical.record_streams["facts"],
                include_obsolete=include_obsolete,
                include_conflicted=include_conflicted,
                include_proposed=True,
            ),
            "decisions": filter_records_by_status(
                canonical.record_streams["decisions"],
                include_obsolete=include_obsolete,
                include_conflicted=include_conflicted,
                include_proposed=True,
            ),
            "contracts": filter_records_by_status(
                canonical.record_streams["contracts"],
                include_obsolete=include_obsolete,
                include_conflicted=include_conflicted,
                include_proposed=True,
            ),
        },
    }
    if scope == "project":
        project_records = store.list_records(
            branch=PROJECT_MEMORY_BRANCH,
            statuses=["validated"],
            limit=500,
        )
        project_semantic = {"facts": [], "decisions": [], "contracts": []}
        for item in project_records:
            payload = item.get("payload", {})
            semantic_kind = payload.get("semantic_kind")
            if semantic_kind == "fact":
                project_semantic["facts"].append(payload)
            elif semantic_kind == "decision":
                project_semantic["decisions"].append(payload)
            elif semantic_kind == "contract":
                project_semantic["contracts"].append(payload)
        for semantic_key in ("facts", "decisions", "contracts"):
            branch_records = semantic_sets["validated"][semantic_key]
            merged_records: list[dict[str, Any]] = []
            seen: set[str] = set()
            for record in [*project_semantic[semantic_key], *branch_records]:
                fingerprint = semantic_fingerprint(record)
                if fingerprint in seen:
                    continue
                merged_records.append(record)
                seen.add(fingerprint)
            semantic_sets["validated"][semantic_key] = merged_records
            semantic_sets["stage"][semantic_key] = [*project_semantic[semantic_key], *semantic_sets["stage"][semantic_key]]

    semantic_facts = semantic_sets["validated"]["facts"]
    semantic_decisions = semantic_sets["validated"]["decisions"]
    semantic_contracts = semantic_sets["validated"]["contracts"]
    resolved_step_id = resolve_runtime_step_id(
        progress=state.progress,
        session_payload=state.active_session,
        stage=stage_lower,
        explicit_step_id=step_id,
    )

    stage_facts = [
        record
        for record in semantic_sets["stage"]["facts"]
        if stage_lower in str(record.get("stage", "")).lower()
        and (not resolved_step_id or record.get("step_id") == resolved_step_id)
    ]
    stage_decisions = [
        record
        for record in semantic_sets["stage"]["decisions"]
        if stage_lower in str(record.get("stage", "")).lower()
        and (not resolved_step_id or record.get("step_id") == resolved_step_id)
    ]
    stage_contracts = [
        record
        for record in semantic_sets["stage"]["contracts"]
        if stage_lower in str(record.get("stage", "")).lower()
        and (not resolved_step_id or record.get("step_id") == resolved_step_id)
    ]
    scoped_events = [
        record
        for record in events
        if (not resolved_step_id or record.get("step_id") == resolved_step_id)
        and stage_lower in str(record.get("stage", "")).lower()
    ]
    scoped_decisions = [
        record
        for record in decision_log
        if (not resolved_step_id or record.get("step_id") == resolved_step_id)
        and stage_lower in str(record.get("stage", "")).lower()
    ]

    if "plan" in stage_lower:
        relevant_facts = semantic_facts
        relevant_decisions = [
            record
            for record in semantic_decisions
            if "plan" in record.get("stage", "") or record.get("scope") == "project"
        ]
        relevant_contracts = semantic_contracts
    elif "implement" in stage_lower:
        relevant_facts = [
            record
            for record in semantic_facts
            if record.get("scope") in {"project", "branch", "step"}
        ]
        relevant_decisions = [
            record
            for record in semantic_decisions
            if "implement" in record.get("stage", "") or record.get("step_id") == step_id
        ]
        relevant_contracts = semantic_contracts
    else:
        relevant_facts = semantic_facts
        relevant_decisions = semantic_decisions
        relevant_contracts = semantic_contracts

    recall = search_memory_store(
        project_path,
        branch_name=branch_name,
        stage=stage,
        step_id=resolved_step_id,
        query=query,
        scope=scope,
        recall_limit=recall_limit or resolved_limit,
        disable_semantic=disable_semantic,
        include_obsolete=include_obsolete,
        include_conflicted=include_conflicted,
        active_session=state.active_session,
    )
    policy_context, policy_state = build_retrieve_policy_context(
        project_path,
        branch_name,
        stage=stage,
        step_id=resolved_step_id,
        limit=resolved_limit,
    )
    coordination = (
        store.fetch_session_coordination(
            branch=branch_name,
            session_key=session_key,
        )
        if include_coordination
        else {}
    )

    return {
        "branch": branch_name,
        "stage": stage,
        "runtime_revision": canonical.runtime_revision,
        "session_key": session_key,
        "step_id": resolved_step_id,
        "active_session": {
            "session_key": session_key,
            "active_goal": state.active_session.get("active_goal"),
            "stage": state.active_session.get("stage"),
            "current_step": state.active_session.get("current_step"),
            "open_questions": state.active_session.get("open_questions", [])[:resolved_limit],
            "current_hypotheses": state.active_session.get("current_hypotheses", [])[:resolved_limit],
        },
        "workflow": {
            "currentImplementStep": state.progress.get("currentImplementStep"),
            "plannedSteps": list(state.progress.get("plannedSteps", [])),
            "completedSteps": list(state.progress.get("completedSteps", [])),
            "stepDependencies": state.progress.get("planningMetadata", {}).get("stepDependencies", {}),
            "nextExecutableStep": select_next_executable_step(state.progress),
            "planningPhase": state.progress.get("planningMetadata", {}).get("planningPhase"),
            "lastPlannedStep": state.progress.get("planningMetadata", {}).get("lastPlannedStep"),
            "progressMetrics": state.progress.get("planningMetadata", {}).get("progressMetrics", {}),
        },
        "step": {
            "step_id": resolved_step_id,
            "metadata": state.progress.get("stepMetadata", {}).get(resolved_step_id, {}) if resolved_step_id else {},
            "status": state.progress.get("stepStatus", {}).get(resolved_step_id, {}) if resolved_step_id else {},
            "dependencies": state.progress.get("planningMetadata", {}).get("stepDependencies", {}).get(resolved_step_id, [])
            if resolved_step_id
            else [],
            "covers": state.progress.get("coversFunctions", {}).get(resolved_step_id, {}) if resolved_step_id else {},
        },
        "stage_memory": {
            "facts": _trim(stage_facts, resolved_limit),
            "decisions": _trim(stage_decisions, resolved_limit),
            "contracts": _trim(stage_contracts, resolved_limit),
            "notes": _trim(scoped_decisions + scoped_events, resolved_limit),
        },
        "semantic": {
            "facts": _trim(relevant_facts, resolved_limit),
            "decisions": _trim(relevant_decisions, resolved_limit),
            "contracts": _trim(relevant_contracts, resolved_limit),
        },
        "policy_context": policy_context,
        "coordination": {
            "task": coordination.get("task"),
            "work_item": coordination.get("work_item"),
            "claim": coordination.get("claim"),
            "session_binding": coordination.get("session_binding"),
            "proposal_summary": coordination.get("proposal_summary"),
            "coordinator": coordination.get("coordinator"),
            "task_id": ((coordination.get("session_binding") or {}).get("task_id")),
            "work_item_id": ((coordination.get("session_binding") or {}).get("work_item_id")),
            "session_key": session_key,
            "ownership": ((coordination.get("coordinator") or {}).get("ownership_state")),
            "readiness": ((coordination.get("coordinator") or {}).get("readiness")),
            "related_proposals": ((coordination.get("coordinator") or {}).get("related_proposals")),
            "scheduler_hints": ((coordination.get("coordinator") or {}).get("scheduler_hints")),
            "dependency_state": ((coordination.get("coordinator") or {}).get("dependency_state")),
        },
        "change_context": change_context,
        "concept_status": build_concept_status(state.concept_state) if stage_lower == "mvp.concept" else None,
        "design_status": (
            build_design_status(
                state.design_state,
                state.concept_state,
                project_path=project_path,
                branch_name=branch_name,
            )
            if stage_lower == "mvp.design" and state.design_state is not None
            else None
        ),
        "tech_status": (
            build_tech_status(state.tech_state)
            if stage_lower == "mvp.tech" and state.tech_state is not None
            else None
        ),
        "deploy_status": (
            build_deploy_status(state.deploy_state)
            if stage_lower == "deploy" and state.deploy_state is not None
            else None
        ),
        "architecture_status": (
            build_architecture_status(
                state.architecture_state,
                design_state=load_design_state(state.paths.design_state),
            )
            if stage_lower == "mvp.architecture" and state.architecture_state is not None
            else None
        ),
        "plan_status": (
            build_plan_status(state.plan_state, progress=state.progress)
            if stage_lower == "mvp.plan" and state.plan_state is not None
            else None
        ),
        "feature_init_status": (
            build_feature_init_status(state.feature_init_state)
            if stage_lower == "feature.init" and state.feature_init_state is not None
            else None
        ),
        "feature_plan_status": (
            build_feature_plan_status(state.feature_plan_state, progress=state.progress)
            if stage_lower == "feature.plan" and state.feature_plan_state is not None
            else None
        ),
        "episodes": _trim(scoped_events, resolved_limit) if include_history_records else [],
        "decision_log": _trim(scoped_decisions, resolved_limit) if include_history_records else [],
        "recall": recall,
        "artifact_state": {
            "concept": state.concept_state if (stage_lower == "mvp.concept" and full_artifact) else None,
            "design": state.design_state if (stage_lower == "mvp.design" and full_artifact) else None,
            "tech": state.tech_state if (stage_lower == "mvp.tech" and full_artifact) else None,
            "deploy": state.deploy_state if (stage_lower == "deploy" and full_artifact) else None,
            "architecture": state.architecture_state if (stage_lower == "mvp.architecture" and full_artifact) else None,
            "plan": (
                state.plan_state
                if (stage_lower == "mvp.plan" and full_artifact)
                else state.feature_plan_state
                if (stage_lower == "feature.plan" and full_artifact)
                else None
            ),
            "feature_init": state.feature_init_state if (stage_lower == "feature.init" and full_artifact) else None,
            "feature_plan": state.feature_plan_state if (stage_lower == "feature.plan" and full_artifact) else None,
            "policy": policy_state if full_artifact else None,
            "change": change_state if full_artifact else None,
        },
    }
