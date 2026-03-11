from __future__ import annotations

from typing import Any

from ..shared.records import make_record


def build_start_event(
    *,
    branch_name: str,
    normalized_stage: str,
    selected_step: str,
    normalized_summary: str,
    normalized_evidence: list[str],
    progress_path: str,
    dependencies: list[str],
    ts: str,
) -> list[dict[str, Any]]:
    return [
        make_record(
            branch_name,
            normalized_stage,
            "memory.start-step",
            normalized_summary or f"Started implementation step {selected_step}",
            step_id=selected_step,
            status="validated",
            evidence=normalized_evidence or [progress_path],
            scope="step",
            record_type="implementation_start",
            metadata={"dependencies": dependencies},
            ts=ts,
        )
    ]


def build_checkpoint_event(
    *,
    branch_name: str,
    normalized_stage: str,
    selected_step: str,
    normalized_summary: str,
    normalized_evidence: list[str],
    normalized_red: list[str],
    normalized_green: list[str],
    progress_path: str,
    status_info: dict[str, Any],
    ts: str,
) -> list[dict[str, Any]]:
    return [
        make_record(
            branch_name,
            normalized_stage,
            "memory.checkpoint-step",
            normalized_summary or f"Checkpointed implementation step {selected_step}",
            step_id=selected_step,
            status="validated",
            evidence=normalized_evidence or normalized_red or normalized_green or [progress_path],
            scope="step",
            record_type="implementation_checkpoint",
            metadata={
                "tdd_phase": status_info.get("tddPhase"),
                "redEvidenceCount": len(status_info.get("redEvidence", [])),
                "greenEvidenceCount": len(status_info.get("greenEvidence", [])),
                "refactorNote": status_info.get("refactorNote"),
            },
            ts=ts,
        )
    ]


def build_completion_event(
    *,
    branch_name: str,
    normalized_stage: str,
    selected_step: str,
    normalized_summary: str,
    normalized_evidence: list[str],
    progress_path: str,
    status_info: dict[str, Any],
    next_step: str | None,
    completed_at: str,
    ts: str,
) -> list[dict[str, Any]]:
    return [
        make_record(
            branch_name,
            normalized_stage,
            "memory.complete-step",
            normalized_summary,
            step_id=selected_step,
            status="validated",
            evidence=normalized_evidence
            or status_info.get("greenEvidence")
            or status_info.get("redEvidence")
            or [progress_path],
            scope="step",
            record_type="implementation_completion",
            metadata={
                "next_step": next_step,
                "completedAt": completed_at,
            },
            ts=ts,
        )
    ]


def build_completion_semantic_records(
    *,
    branch_name: str,
    normalized_stage: str,
    selected_step: str,
    normalized_evidence: list[str],
    values: list[str],
    semantic_kind: str,
    ts: str,
) -> list[dict[str, Any]]:
    return [
        make_record(
            branch_name,
            normalized_stage,
            "memory.complete-step",
            item,
            step_id=selected_step,
            status="validated",
            evidence=normalized_evidence,
            scope="step",
            semantic_kind=semantic_kind,
            record_type=semantic_kind,
            ts=ts,
        )
        for item in values
    ]
