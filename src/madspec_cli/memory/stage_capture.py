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
    if not any(
        [
            normalized_summary,
            normalized_facts,
            normalized_decisions,
            normalized_contracts,
            normalized_questions,
            normalized_pending_actions,
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
        normalized_decisions or normalized_facts,
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

    try:
        write_json(paths.active_session, active_session)
        append_jsonl(paths.decision_log, note_records)
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
