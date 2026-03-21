from __future__ import annotations

from pathlib import Path
from typing import Any

from ..stages.architecture.state import (
    ARCHITECTURE_STAGE,
    architecture_completeness_errors,
    load_architecture_state,
    update_architecture_state,
)
from ..stages.concept.state import (
    CONCEPT_STAGE,
    concept_completeness_errors,
    load_concept_state,
    update_concept_state,
)
from ..stages.design.state import (
    DESIGN_STAGE,
    design_completeness_errors,
    load_design_state,
    update_design_state,
)
from ..stages.feature_init.state import (
    FEATURE_INIT_STAGE,
    feature_init_completeness_errors,
    load_feature_init_state,
    update_feature_init_state,
)
from ..stages.feature_plan.state import (
    FEATURE_PLAN_STAGE,
    feature_plan_completeness_errors,
    load_feature_plan_state,
)
from ..stages.plan.state import (
    PLAN_STAGE,
    load_plan_state,
    plan_completeness_errors,
    update_plan_state,
)
from ..stages.tech.state import (
    TECH_STAGE,
    load_tech_state,
    tech_completeness_errors,
    update_tech_state,
)
from ..shared.records import make_record
from ..shared.storage import (
    ensure_memory_layout,
    get_memory_paths,
    normalize_runtime_progress,
    now_iso,
)
from ..shared.system_store.constants import SYSTEM_SESSION_KEY
from ..shared.system_store.canonical_state import (
    build_runtime_snapshot_specs,
    load_canonical_branch_state,
    tag_records_for_stream,
)
from ..shared.system_store.runtime_mutations import commit_runtime_mutation
from ..shared.system_store.sessions import load_runtime_session

CHECKPOINT_STAGES = {
    "mvp.concept",
    "mvp.design",
    "mvp.tech",
    "mvp.architecture",
    "mvp.plan",
    "feature.init",
    "feature.plan",
    "review",
    "security",
}


def _normalize_text_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    return [value.strip() for value in values if value and value.strip()]


def checkpoint_stage_memory(
    project_path: Path,
    branch_name: str,
    stage: str,
    summary: str,
    *,
    session_key: str = SYSTEM_SESSION_KEY,
    facts: list[str] | None = None,
    decisions: list[str] | None = None,
    contracts: list[str] | None = None,
    evidence: list[str] | None = None,
    questions: list[str] | None = None,
    pending_actions: list[str] | None = None,
) -> dict[str, Any]:
    normalized_stage = stage.strip().lower()
    normalized_summary = summary.strip()
    normalized_facts = _normalize_text_list(facts)
    normalized_decisions = _normalize_text_list(decisions)
    normalized_contracts = _normalize_text_list(contracts)
    normalized_evidence = _normalize_text_list(evidence)
    normalized_questions = _normalize_text_list(questions)
    normalized_pending_actions = _normalize_text_list(pending_actions)

    errors: list[str] = []
    if normalized_stage not in CHECKPOINT_STAGES:
        errors.append(
            "stage must be one of: "
            + ", ".join(sorted(CHECKPOINT_STAGES))
        )
    if not normalized_summary:
        errors.append("summary must not be empty")
    ensure_memory_layout(project_path, branch_name, stage=normalized_stage)
    paths = get_memory_paths(project_path, branch_name)
    canonical = load_canonical_branch_state(project_path, branch_name)
    existing_stage_facts = [
        record
        for record in canonical.record_streams["facts"]
        if record.get("stage") == normalized_stage and record.get("status") == "validated"
    ]
    existing_stage_decisions = [
        record
        for record in canonical.record_streams["decisions"]
        if record.get("stage") == normalized_stage and record.get("status") == "validated"
    ]
    existing_stage_contracts = [
        record
        for record in canonical.record_streams["contracts"]
        if record.get("stage") == normalized_stage and record.get("status") == "validated"
    ]
    has_existing_stage_memory = any(
        [existing_stage_facts, existing_stage_decisions, existing_stage_contracts]
    )
    if not any(
        [
            normalized_summary,
            normalized_facts,
            normalized_decisions,
            normalized_contracts,
            has_existing_stage_memory,
        ]
    ):
        errors.append(
            "checkpoint payload must include summary plus fact/decision/contract content or use previously captured validated stage memory"
        )
    if errors:
        return {"accepted": False, "branch": branch_name, "stage": normalized_stage, "errors": errors}

    ts = now_iso()
    active_session = load_runtime_session(
        project_path,
        branch_name=branch_name,
        session_key=session_key,
    )
    active_session.update(
        {
            "branch": branch_name,
            "session_key": session_key,
            "active_goal": normalized_summary,
            "stage": normalized_stage,
            "current_step": None,
            "pending_actions": normalized_pending_actions,
            "open_questions": normalized_questions,
            "current_hypotheses": (
                normalized_decisions
                or normalized_facts
                or active_session.get("current_hypotheses", [])
            )[:5],
            "last_checkpoint_at": ts,
            "updated_at": ts,
        }
    )

    checkpoint_record = make_record(
        branch_name,
        normalized_stage,
        "memory.checkpoint",
        normalized_summary,
        status="validated",
        evidence=normalized_evidence,
        scope="project",
        record_type="checkpoint",
        metadata={
            "questions": normalized_questions,
            "pendingActions": normalized_pending_actions,
        },
        ts=ts,
    )
    concept_state = canonical.snapshots.get(CONCEPT_STAGE) or load_concept_state(paths.concept_state)
    design_state = canonical.snapshots.get(DESIGN_STAGE) or load_design_state(paths.design_state)
    tech_state = canonical.snapshots.get(TECH_STAGE) or load_tech_state(paths.tech_state)
    architecture_state = canonical.snapshots.get(ARCHITECTURE_STAGE) or load_architecture_state(paths.architecture_state)
    plan_state = canonical.snapshots.get(PLAN_STAGE) or load_plan_state(paths.plan_state)
    feature_init_state = canonical.snapshots.get(FEATURE_INIT_STAGE) or load_feature_init_state(paths.feature_init_state)
    feature_plan_state = canonical.snapshots.get(FEATURE_PLAN_STAGE) or load_feature_plan_state(paths.feature_plan_state)
    if normalized_stage == CONCEPT_STAGE:
        concept_state = update_concept_state(
            concept_state,
            constraints=normalized_contracts,
            next_actions=normalized_pending_actions,
            checkpoint_summary=normalized_summary,
            ratify=True,
        )
        errors.extend(concept_completeness_errors(concept_state))
        if errors:
            return {"accepted": False, "branch": branch_name, "stage": normalized_stage, "errors": errors}
    elif normalized_stage == DESIGN_STAGE:
        design_state = update_design_state(
            design_state,
            next_actions=normalized_pending_actions,
            checkpoint_summary=normalized_summary,
            ratify=True,
        )
        errors.extend(
            design_completeness_errors(
                design_state,
                concept_state=concept_state,
                project_path=project_path,
                branch_name=branch_name,
            )
        )
        if errors:
            return {"accepted": False, "branch": branch_name, "stage": normalized_stage, "errors": errors}
    elif normalized_stage == TECH_STAGE:
        tech_state = update_tech_state(
            tech_state,
            constraints=normalized_contracts,
            next_actions=normalized_pending_actions,
            checkpoint_summary=normalized_summary,
            ratify=True,
        )
        errors.extend(tech_completeness_errors(tech_state))
        if errors:
            return {"accepted": False, "branch": branch_name, "stage": normalized_stage, "errors": errors}
    elif normalized_stage == ARCHITECTURE_STAGE:
        architecture_state = update_architecture_state(
            architecture_state,
            next_actions=normalized_pending_actions,
            checkpoint_summary=normalized_summary,
            ratify=True,
        )
        errors.extend(
            architecture_completeness_errors(
                architecture_state,
                design_state=design_state,
            )
        )
        if errors:
            return {"accepted": False, "branch": branch_name, "stage": normalized_stage, "errors": errors}
    elif normalized_stage == PLAN_STAGE:
        plan_state = update_plan_state(
            plan_state,
            next_actions=normalized_pending_actions,
            checkpoint_summary=normalized_summary,
            ratify=True,
        )
        errors.extend(plan_completeness_errors(plan_state))
        if errors:
            return {"accepted": False, "branch": branch_name, "stage": normalized_stage, "errors": errors}
    elif normalized_stage == FEATURE_INIT_STAGE:
        feature_init_state = update_feature_init_state(
            feature_init_state,
            next_actions=normalized_pending_actions,
            checkpoint_summary=normalized_summary,
            ratify=True,
        )
        errors.extend(feature_init_completeness_errors(feature_init_state))
        if errors:
            return {"accepted": False, "branch": branch_name, "stage": normalized_stage, "errors": errors}
    elif normalized_stage == FEATURE_PLAN_STAGE:
        feature_plan_state = update_plan_state(
            feature_plan_state,
            next_actions=normalized_pending_actions,
            checkpoint_summary=normalized_summary,
            ratify=True,
        )
        errors.extend(feature_plan_completeness_errors(feature_plan_state))
        if errors:
            return {"accepted": False, "branch": branch_name, "stage": normalized_stage, "errors": errors}

    fact_records = [
        make_record(
            branch_name,
            normalized_stage,
            "memory.checkpoint",
            item,
            status="validated",
            evidence=normalized_evidence,
            scope="project",
            semantic_kind="fact",
            record_type="fact",
            ts=ts,
        )
        for item in normalized_facts
    ]
    decision_records = [
        make_record(
            branch_name,
            normalized_stage,
            "memory.checkpoint",
            item,
            status="validated",
            evidence=normalized_evidence,
            scope="project",
            semantic_kind="decision",
            record_type="decision",
            ts=ts,
        )
        for item in normalized_decisions
    ]
    contract_records = [
        make_record(
            branch_name,
            normalized_stage,
            "memory.checkpoint",
            item,
            status="validated",
            evidence=normalized_evidence,
            scope="project",
            semantic_kind="contract",
            record_type="contract",
            ts=ts,
        )
        for item in normalized_contracts
    ]

    snapshot_payloads: dict[str, dict[str, Any]] = {}
    if normalized_stage == CONCEPT_STAGE:
        snapshot_payloads[CONCEPT_STAGE] = concept_state
    elif normalized_stage == DESIGN_STAGE:
        snapshot_payloads[DESIGN_STAGE] = design_state
    elif normalized_stage == TECH_STAGE:
        snapshot_payloads[TECH_STAGE] = tech_state
    elif normalized_stage == ARCHITECTURE_STAGE:
        snapshot_payloads[ARCHITECTURE_STAGE] = architecture_state
    elif normalized_stage == PLAN_STAGE:
        snapshot_payloads[PLAN_STAGE] = plan_state
    elif normalized_stage == FEATURE_INIT_STAGE:
        snapshot_payloads[FEATURE_INIT_STAGE] = feature_init_state
    elif normalized_stage == FEATURE_PLAN_STAGE:
        snapshot_payloads[FEATURE_PLAN_STAGE] = feature_plan_state

    catalog_override: dict[str, list[str]] | None = None
    if normalized_stage == CONCEPT_STAGE:
        catalog_override = {
            priority: [
                item.get("name", "")
                for item in concept_state.get("features", {}).get(priority, [])
                if item.get("name", "")
            ]
            for priority in ("p1", "p2", "p3")
        }
    elif normalized_stage == FEATURE_INIT_STAGE:
        catalog_override = {
            priority: [
                item.get("id", "")
                for item in feature_init_state.get("features", {}).get(priority, [])
                if item.get("id", "")
            ]
            for priority in ("p1", "p2", "p3")
        }
    progress_state, _ = normalize_runtime_progress(
        project_path,
        branch_name,
        canonical.progress,
        catalog_override=catalog_override,
    )
    snapshot_payloads["progress"] = progress_state

    records: list[dict[str, Any]] = []
    records.extend(tag_records_for_stream([checkpoint_record], "decision_log"))
    records.extend(tag_records_for_stream(fact_records, "facts"))
    records.extend(tag_records_for_stream(decision_records, "decisions"))
    records.extend(tag_records_for_stream(contract_records, "contracts"))
    projection_meta = commit_runtime_mutation(
        project_path,
        branch_name=branch_name,
        stage=normalized_stage,
        stage_snapshots=build_runtime_snapshot_specs(project_path, branch_name, snapshot_payloads),
        sessions=[{"session_key": session_key, "payload": active_session}],
        records=records,
    )

    payload = {
        "accepted": True,
        "branch": branch_name,
        "stage": normalized_stage,
        "summary": normalized_summary,
        "used_existing_stage_memory": has_existing_stage_memory and not any(
            [normalized_facts, normalized_decisions, normalized_contracts]
        ),
        "written": {
            "decision_log": 1,
            "facts": len(fact_records),
            "decisions": len(decision_records),
            "contracts": len(contract_records),
        },
    }
    payload.update(projection_meta)
    return payload
