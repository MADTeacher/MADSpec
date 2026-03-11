from __future__ import annotations

from pathlib import Path
from typing import Any

from ..stages.architecture.state import (
    ARCHITECTURE_STAGE,
    architecture_completeness_errors,
    load_architecture_state,
    save_architecture_state,
    update_architecture_state,
)
from ..stages.concept.state import (
    CONCEPT_STAGE,
    concept_completeness_errors,
    load_concept_state,
    save_concept_state,
    update_concept_state,
)
from ..stages.design.state import (
    DESIGN_STAGE,
    design_completeness_errors,
    load_design_state,
    save_design_state,
    update_design_state,
)
from ..stages.plan.state import (
    PLAN_STAGE,
    load_plan_state,
    plan_completeness_errors,
    save_plan_state,
    update_plan_state,
)
from ..stages.tech.state import (
    TECH_STAGE,
    load_tech_state,
    save_tech_state,
    tech_completeness_errors,
    update_tech_state,
)
from ..shared.records import make_record
from ..shared.storage import (
    _default_active_session,
    append_jsonl,
    ensure_memory_layout,
    get_memory_paths,
    now_iso,
    read_json,
    read_jsonl,
    write_json,
)
from ..shared.validation import validate_branch_memory
from ..views import consolidate_branch_memory

CHECKPOINT_STAGES = {
    "mvp.concept",
    "mvp.design",
    "mvp.tech",
    "mvp.architecture",
    "mvp.plan",
    "review",
    "security",
}


def _normalize_text_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    return [value.strip() for value in values if value and value.strip()]


def _snapshot_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _restore_file(path: Path, content: str | None) -> None:
    if content is None:
        if path.exists():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def checkpoint_stage_memory(
    project_path: Path,
    branch_name: str,
    stage: str,
    summary: str,
    *,
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
    ensure_memory_layout(project_path, branch_name)
    paths = get_memory_paths(project_path, branch_name)
    existing_stage_facts = [
        record
        for record in read_jsonl(paths.facts)
        if record.get("stage") == normalized_stage and record.get("status") == "validated"
    ]
    existing_stage_decisions = [
        record
        for record in read_jsonl(paths.decisions)
        if record.get("stage") == normalized_stage and record.get("status") == "validated"
    ]
    existing_stage_contracts = [
        record
        for record in read_jsonl(paths.contracts)
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

    snapshots = {
        paths.active_session: _snapshot_file(paths.active_session),
        paths.decision_log: _snapshot_file(paths.decision_log),
        paths.facts: _snapshot_file(paths.facts),
        paths.decisions: _snapshot_file(paths.decisions),
        paths.contracts: _snapshot_file(paths.contracts),
        paths.concept_state: _snapshot_file(paths.concept_state),
        paths.design_state: _snapshot_file(paths.design_state),
        paths.tech_state: _snapshot_file(paths.tech_state),
        paths.architecture_state: _snapshot_file(paths.architecture_state),
        paths.plan_state: _snapshot_file(paths.plan_state),
    }

    ts = now_iso()
    active_session = read_json(paths.active_session, _default_active_session(branch_name))
    active_session.update(
        {
            "branch": branch_name,
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
    concept_state = load_concept_state(paths.concept_state)
    design_state = load_design_state(paths.design_state)
    tech_state = load_tech_state(paths.tech_state)
    architecture_state = load_architecture_state(paths.architecture_state)
    plan_state = load_plan_state(paths.plan_state)
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

    try:
        if normalized_stage == CONCEPT_STAGE:
            save_concept_state(paths.concept_state, concept_state)
        elif normalized_stage == DESIGN_STAGE:
            save_design_state(paths.design_state, design_state)
        elif normalized_stage == TECH_STAGE:
            save_tech_state(paths.tech_state, tech_state)
        elif normalized_stage == ARCHITECTURE_STAGE:
            save_architecture_state(paths.architecture_state, architecture_state)
        elif normalized_stage == PLAN_STAGE:
            save_plan_state(paths.plan_state, plan_state)
        write_json(paths.active_session, active_session)
        append_jsonl(paths.decision_log, [checkpoint_record])
        append_jsonl(paths.facts, fact_records)
        append_jsonl(paths.decisions, decision_records)
        append_jsonl(paths.contracts, contract_records)

        generated = consolidate_branch_memory(project_path, branch_name)
        ensure_memory_layout(project_path, branch_name)
        validation_errors = validate_branch_memory(project_path, branch_name)
        if validation_errors:
            raise ValueError("; ".join(validation_errors))
    except Exception as exc:
        for path, content in snapshots.items():
            _restore_file(path, content)
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": [str(exc)],
        }

    return {
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
        "generated_views": [str(path.relative_to(project_path)) for path in generated],
    }
