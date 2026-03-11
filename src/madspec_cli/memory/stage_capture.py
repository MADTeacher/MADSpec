from __future__ import annotations

from pathlib import Path
from typing import Any

from .concept_state import (
    CONCEPT_STAGE,
    load_concept_state,
    parse_feature_value,
    save_concept_state,
    update_concept_state,
)
from .records import make_record
from .storage import (
    _default_active_session,
    append_jsonl,
    ensure_memory_layout,
    get_memory_paths,
    now_iso,
    read_json,
    write_json,
)
from .validation import validate_branch_memory
from .views import consolidate_branch_memory

CAPTURE_STAGES = {
    "mvp.concept",
    "mvp.design",
    "mvp.tech",
    "mvp.architecture",
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


def _append_unique(existing: list[str], values: list[str]) -> list[str]:
    result = list(existing)
    for value in values:
        if value not in result:
            result.append(value)
    return result


def capture_stage_memory(
    project_path: Path,
    branch_name: str,
    stage: str,
    *,
    summary: str | None = None,
    facts: list[str] | None = None,
    decisions: list[str] | None = None,
    contracts: list[str] | None = None,
    evidence: list[str] | None = None,
    questions: list[str] | None = None,
    pending_actions: list[str] | None = None,
    project_name: str | None = None,
    system_overview: str | None = None,
    audiences: list[str] | None = None,
    scenarios: list[str] | None = None,
    pain_points: list[str] | None = None,
    feature_p1: list[str] | None = None,
    feature_p2: list[str] | None = None,
    feature_p3: list[str] | None = None,
    constraints: list[str] | None = None,
    assumptions: list[str] | None = None,
    next_actions: list[str] | None = None,
    status: str = "validated",
) -> dict[str, Any]:
    normalized_stage = stage.strip().lower()
    if normalized_stage not in CAPTURE_STAGES:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": ["stage must be one of: " + ", ".join(sorted(CAPTURE_STAGES))],
        }

    normalized_status = status.strip().lower()
    if normalized_status not in {"proposed", "validated", "conflicted", "obsolete"}:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": ["status must be one of: conflicted, obsolete, proposed, validated"],
        }

    normalized_summary = (summary or "").strip()
    normalized_facts = _normalize_text_list(facts)
    normalized_decisions = _normalize_text_list(decisions)
    normalized_contracts = _normalize_text_list(contracts)
    normalized_evidence = _normalize_text_list(evidence)
    normalized_questions = _normalize_text_list(questions)
    normalized_pending_actions = _normalize_text_list(pending_actions)
    normalized_audiences = _normalize_text_list(audiences)
    normalized_scenarios = _normalize_text_list(scenarios)
    normalized_pain_points = _normalize_text_list(pain_points)
    normalized_constraints = _normalize_text_list(constraints)
    normalized_assumptions = _normalize_text_list(assumptions)
    normalized_next_actions = _normalize_text_list(next_actions)
    normalized_project_name = (project_name or "").strip()
    normalized_system_overview = (system_overview or "").strip()
    concept_feature_updates: dict[str, list[dict[str, str]]] = {"p1": [], "p2": [], "p3": []}
    concept_feature_errors: list[str] = []
    for priority, values in {
        "p1": _normalize_text_list(feature_p1),
        "p2": _normalize_text_list(feature_p2),
        "p3": _normalize_text_list(feature_p3),
    }.items():
        for value in values:
            parsed = parse_feature_value(value)
            if parsed is None:
                concept_feature_errors.append(
                    f"{priority} feature must use '<name>::<description>' format: {value}"
                )
                continue
            concept_feature_updates[priority].append(parsed)

    used_concept_fields = any(
        [
            normalized_project_name,
            normalized_system_overview,
            normalized_audiences,
            normalized_scenarios,
            normalized_pain_points,
            concept_feature_updates["p1"],
            concept_feature_updates["p2"],
            concept_feature_updates["p3"],
            normalized_constraints,
            normalized_assumptions,
            normalized_next_actions,
        ]
    )
    if used_concept_fields and normalized_stage != CONCEPT_STAGE:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": ["concept-specific capture options are only supported for stage mvp.concept"],
        }
    if concept_feature_errors:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": concept_feature_errors,
        }
    normalized_pending_actions = _append_unique(normalized_pending_actions, normalized_next_actions)
    concept_fact_summaries = (
        ([f"Project name: {normalized_project_name}"] if normalized_project_name else [])
        + ([f"System overview: {normalized_system_overview}"] if normalized_system_overview else [])
        + normalized_audiences
        + normalized_scenarios
        + normalized_pain_points
        + normalized_assumptions
    )
    concept_decision_summaries = [
        f"{priority.upper()} feature: {feature['name']} - {feature['description']}"
        for priority in ("p1", "p2", "p3")
        for feature in concept_feature_updates[priority]
    ]
    concept_contract_summaries = normalized_constraints
    if not any(
        [
            normalized_summary,
            normalized_facts,
            normalized_decisions,
            normalized_contracts,
            normalized_questions,
            normalized_pending_actions,
            concept_fact_summaries,
            concept_decision_summaries,
            concept_contract_summaries,
        ]
    ):
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": ["capture payload must include summary, fact, decision, contract, question, or pending action"],
        }

    ensure_memory_layout(project_path, branch_name)
    paths = get_memory_paths(project_path, branch_name)
    snapshots = {
        paths.active_session: _snapshot_file(paths.active_session),
        paths.decision_log: _snapshot_file(paths.decision_log),
        paths.facts: _snapshot_file(paths.facts),
        paths.decisions: _snapshot_file(paths.decisions),
        paths.contracts: _snapshot_file(paths.contracts),
        paths.concept_state: _snapshot_file(paths.concept_state),
    }

    ts = now_iso()
    active_session = read_json(paths.active_session, _default_active_session(branch_name))
    active_session["branch"] = branch_name
    active_session["stage"] = normalized_stage
    if normalized_summary:
        active_session["active_goal"] = normalized_summary
    active_session["open_questions"] = _append_unique(
        active_session.get("open_questions", []),
        normalized_questions,
    )[:20]
    active_session["pending_actions"] = _append_unique(
        active_session.get("pending_actions", []),
        normalized_pending_actions,
    )[:20]
    active_session["current_hypotheses"] = _append_unique(
        active_session.get("current_hypotheses", []),
        concept_decision_summaries or normalized_decisions or concept_fact_summaries or normalized_facts,
    )[:20]
    active_session["last_checkpoint_at"] = ts
    active_session["updated_at"] = ts

    note_records = []
    if normalized_summary or normalized_questions or normalized_pending_actions:
        note_records.append(
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                normalized_summary or f"Captured stage update for {normalized_stage}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                record_type="stage_note",
                metadata={
                    "questions": normalized_questions,
                    "pendingActions": normalized_pending_actions,
                },
                ts=ts,
            )
        )

    concept_state = load_concept_state(paths.concept_state)
    if normalized_stage == CONCEPT_STAGE:
        concept_state = update_concept_state(
            concept_state,
            project_name=normalized_project_name or None,
            system_overview=normalized_system_overview or None,
            audiences=normalized_audiences,
            scenarios=normalized_scenarios,
            pain_points=normalized_pain_points,
            features=concept_feature_updates,
            constraints=normalized_constraints,
            assumptions=normalized_assumptions,
            next_actions=normalized_next_actions,
        )

    fact_records = [
        make_record(
            branch_name,
            normalized_stage,
            "memory.capture",
            item,
            status=normalized_status,
            evidence=normalized_evidence,
            scope="project",
            semantic_kind="fact",
            record_type="fact",
            ts=ts,
        )
        for item in normalized_facts
    ]
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"System overview: {normalized_system_overview}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "systemOverview"},
                ts=ts,
            )
        ]
        if normalized_system_overview and normalized_stage == CONCEPT_STAGE
        else []
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"Project name: {normalized_project_name}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "projectName"},
                ts=ts,
            )
        ]
        if normalized_project_name and normalized_stage == CONCEPT_STAGE
        else []
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                item,
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "audience"},
                ts=ts,
            )
            for item in normalized_audiences
        ]
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                item,
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "scenario"},
                ts=ts,
            )
            for item in normalized_scenarios
        ]
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                item,
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "painPoint"},
                ts=ts,
            )
            for item in normalized_pain_points
        ]
    )
    fact_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                item,
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="fact",
                record_type="fact",
                metadata={"slot": "assumption"},
                ts=ts,
            )
            for item in normalized_assumptions
        ]
    )
    decision_records = [
        make_record(
            branch_name,
            normalized_stage,
            "memory.capture",
            item,
            status=normalized_status,
            evidence=normalized_evidence,
            scope="project",
            semantic_kind="decision",
            record_type="decision",
            ts=ts,
        )
        for item in normalized_decisions
    ]
    decision_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                f"{priority.upper()} feature: {feature['name']} - {feature['description']}",
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="decision",
                record_type="decision",
                metadata={"slot": "feature", "priority": priority, **feature},
                ts=ts,
            )
            for priority in ("p1", "p2", "p3")
            for feature in concept_feature_updates[priority]
        ]
    )
    contract_records = [
        make_record(
            branch_name,
            normalized_stage,
            "memory.capture",
            item,
            status=normalized_status,
            evidence=normalized_evidence,
            scope="project",
            semantic_kind="contract",
            record_type="contract",
            ts=ts,
        )
        for item in normalized_contracts
    ]
    contract_records.extend(
        [
            make_record(
                branch_name,
                normalized_stage,
                "memory.capture",
                item,
                status=normalized_status,
                evidence=normalized_evidence,
                scope="project",
                semantic_kind="contract",
                record_type="contract",
                metadata={"slot": "constraint"},
                ts=ts,
            )
            for item in normalized_constraints
        ]
    )

    try:
        if normalized_stage == CONCEPT_STAGE:
            save_concept_state(paths.concept_state, concept_state)
        write_json(paths.active_session, active_session)
        append_jsonl(paths.decision_log, note_records)
        append_jsonl(paths.facts, fact_records)
        append_jsonl(paths.decisions, decision_records)
        append_jsonl(paths.contracts, contract_records)

        generated = consolidate_branch_memory(project_path, branch_name)
        ensure_memory_layout(project_path, branch_name)
        generated = consolidate_branch_memory(project_path, branch_name)
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
        "status": normalized_status,
        "written": {
            "notes": len(note_records),
            "facts": len(fact_records),
            "decisions": len(decision_records),
            "contracts": len(contract_records),
            "questions": len(normalized_questions),
            "pending_actions": len(normalized_pending_actions),
        },
        "generated_views": [str(path.relative_to(project_path)) for path in generated],
    }
