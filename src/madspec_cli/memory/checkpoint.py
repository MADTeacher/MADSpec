from __future__ import annotations

from pathlib import Path
from typing import Any

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

CHECKPOINT_STAGES = {
    "mvp.concept",
    "mvp.design",
    "mvp.tech",
    "mvp.architecture",
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
    if not any(
        [
            normalized_summary,
            normalized_facts,
            normalized_decisions,
            normalized_contracts,
        ]
    ):
        errors.append("checkpoint payload must include summary, fact, decision, or contract content")
    if errors:
        return {"accepted": False, "branch": branch_name, "stage": normalized_stage, "errors": errors}

    ensure_memory_layout(project_path, branch_name)
    paths = get_memory_paths(project_path, branch_name)
    snapshots = {
        paths.active_session: _snapshot_file(paths.active_session),
        paths.decision_log: _snapshot_file(paths.decision_log),
        paths.facts: _snapshot_file(paths.facts),
        paths.decisions: _snapshot_file(paths.decisions),
        paths.contracts: _snapshot_file(paths.contracts),
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
            "current_hypotheses": (normalized_decisions or normalized_facts)[:5],
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
        write_json(paths.active_session, active_session)
        append_jsonl(paths.decision_log, [checkpoint_record])
        append_jsonl(paths.facts, fact_records)
        append_jsonl(paths.decisions, decision_records)
        append_jsonl(paths.contracts, contract_records)

        validation_errors = validate_branch_memory(project_path, branch_name)
        if validation_errors:
            raise ValueError("; ".join(validation_errors))

        generated = consolidate_branch_memory(project_path, branch_name)
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
        "written": {
            "decision_log": 1,
            "facts": len(fact_records),
            "decisions": len(decision_records),
            "contracts": len(contract_records),
        },
        "generated_views": [str(path.relative_to(project_path)) for path in generated],
    }
