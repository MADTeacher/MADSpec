from __future__ import annotations

from pathlib import Path
from typing import Any

from ..domain.progress import select_next_executable_step
from .implementation_records import (
    build_checkpoint_event,
    build_completion_event,
    build_completion_semantic_records,
    build_start_event,
)
from .implementation_shared import (
    IMPLEMENTATION_STAGES,
    append_unique,
    is_step_ready,
    load_progress,
    normalize_text_list,
    restore_file,
    set_active_step,
    snapshot_file,
    step_dependencies,
    validate_implementation_stage,
    validate_start_step,
)
from ..shared.storage import (
    append_jsonl,
    ensure_memory_layout,
    get_memory_paths,
    now_iso,
    write_json,
)
from ..shared.validation import validate_branch_memory
from ..views import consolidate_branch_memory


def start_implementation_step(
    project_path: Path,
    branch_name: str,
    stage: str,
    *,
    step_id: str | None = None,
    summary: str | None = None,
    evidence: list[str] | None = None,
) -> dict[str, Any]:
    try:
        normalized_stage = validate_implementation_stage(stage)
    except ValueError as exc:
        return {"accepted": False, "branch": branch_name, "stage": stage, "errors": [str(exc)]}

    normalized_summary = (summary or "").strip()
    normalized_evidence = normalize_text_list(evidence)

    ensure_memory_layout(project_path, branch_name)
    paths = get_memory_paths(project_path, branch_name)
    snapshots = {
        paths.progress: snapshot_file(paths.progress),
        paths.active_session: snapshot_file(paths.active_session),
        paths.events: snapshot_file(paths.events),
    }
    progress, active_session = load_progress(project_path, branch_name)

    selected_step = step_id or select_next_executable_step(progress)
    if not selected_step:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": ["no executable implementation step found"],
        }

    errors = validate_start_step(progress, selected_step)
    if errors:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "step_id": selected_step,
            "errors": errors,
        }

    ts = now_iso()
    try:
        set_active_step(progress, selected_step)
        write_json(paths.progress, progress)

        active_session["stage"] = normalized_stage
        active_session["current_step"] = selected_step
        active_session["active_goal"] = normalized_summary or f"Implement {selected_step}"
        active_session["last_checkpoint_at"] = ts
        active_session["updated_at"] = ts
        write_json(paths.active_session, active_session)

        append_jsonl(
            paths.events,
            build_start_event(
                branch_name=branch_name,
                normalized_stage=normalized_stage,
                selected_step=selected_step,
                normalized_summary=normalized_summary,
                normalized_evidence=normalized_evidence,
                progress_path=str(paths.progress.relative_to(project_path)),
                dependencies=step_dependencies(progress, selected_step),
                ts=ts,
            ),
        )

        generated = consolidate_branch_memory(project_path, branch_name)
        validation_errors = validate_branch_memory(project_path, branch_name)
        if validation_errors:
            raise ValueError("; ".join(validation_errors))
    except Exception as exc:
        for path, content in snapshots.items():
            restore_file(path, content)
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "step_id": selected_step,
            "errors": [str(exc)],
        }

    return {
        "accepted": True,
        "branch": branch_name,
        "stage": normalized_stage,
        "step_id": selected_step,
        "status": progress.get("stepStatus", {}).get(selected_step, {}).get("status"),
        "generated_views": [str(path.relative_to(project_path)) for path in generated],
    }


def checkpoint_implementation_step(
    project_path: Path,
    branch_name: str,
    stage: str,
    *,
    step_id: str | None = None,
    summary: str | None = None,
    tdd_phase: str | None = None,
    red_evidence: list[str] | None = None,
    green_evidence: list[str] | None = None,
    refactor_note: str | None = None,
    evidence: list[str] | None = None,
) -> dict[str, Any]:
    try:
        normalized_stage = validate_implementation_stage(stage)
    except ValueError as exc:
        return {"accepted": False, "branch": branch_name, "stage": stage, "errors": [str(exc)]}

    normalized_summary = (summary or "").strip()
    normalized_red = normalize_text_list(red_evidence)
    normalized_green = normalize_text_list(green_evidence)
    normalized_evidence = normalize_text_list(evidence)
    normalized_refactor_note = refactor_note.strip() if refactor_note else None
    normalized_phase = tdd_phase.strip().lower() if tdd_phase else None

    if not any([normalized_summary, normalized_phase, normalized_red, normalized_green, normalized_refactor_note]):
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": ["checkpoint must include summary, tdd phase, evidence, or refactor note"],
        }

    ensure_memory_layout(project_path, branch_name)
    paths = get_memory_paths(project_path, branch_name)
    snapshots = {
        paths.progress: snapshot_file(paths.progress),
        paths.active_session: snapshot_file(paths.active_session),
        paths.events: snapshot_file(paths.events),
    }
    progress, active_session = load_progress(project_path, branch_name)

    selected_step = step_id or progress.get("currentImplementStep") or active_session.get("current_step")
    if not selected_step:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": ["step_id is required when there is no current implementation step"],
        }

    planned_steps = progress.get("plannedSteps", [])
    if selected_step not in planned_steps:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "step_id": selected_step,
            "errors": [f"step '{selected_step}' is not present in plannedSteps"],
        }

    metadata = progress.get("stepMetadata", {}).get(selected_step, {})
    status_info = progress.get("stepStatus", {}).get(selected_step, {})
    if status_info.get("status") == "completed":
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "step_id": selected_step,
            "errors": [f"step '{selected_step}' is already completed"],
        }

    tdd_policy = metadata.get("tddPolicy")
    allowed_phases = {"waived"} if tdd_policy in {"waived", "not-applicable"} else {"not_started", "red", "green", "refactor"}
    if normalized_phase and normalized_phase not in allowed_phases:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "step_id": selected_step,
            "errors": [
                "tdd phase must be one of: " + ", ".join(sorted(allowed_phases))
            ],
        }

    ts = now_iso()
    try:
        set_active_step(progress, selected_step)
        status_info = progress.setdefault("stepStatus", {}).setdefault(selected_step, {})
        status_info["status"] = "in_progress"
        if normalized_phase:
            status_info["tddPhase"] = normalized_phase
        status_info["redEvidence"] = append_unique(status_info.get("redEvidence", []), normalized_red)
        status_info["greenEvidence"] = append_unique(status_info.get("greenEvidence", []), normalized_green)
        if normalized_refactor_note is not None:
            status_info["refactorNote"] = normalized_refactor_note
        write_json(paths.progress, progress)

        active_session["stage"] = normalized_stage
        active_session["current_step"] = selected_step
        if normalized_summary:
            active_session["active_goal"] = normalized_summary
        active_session["last_checkpoint_at"] = ts
        active_session["updated_at"] = ts
        write_json(paths.active_session, active_session)

        append_jsonl(
            paths.events,
            build_checkpoint_event(
                branch_name=branch_name,
                normalized_stage=normalized_stage,
                selected_step=selected_step,
                normalized_summary=normalized_summary,
                normalized_evidence=normalized_evidence,
                normalized_red=normalized_red,
                normalized_green=normalized_green,
                progress_path=str(paths.progress.relative_to(project_path)),
                status_info=status_info,
                ts=ts,
            ),
        )

        generated = consolidate_branch_memory(project_path, branch_name)
        validation_errors = validate_branch_memory(project_path, branch_name)
        if validation_errors:
            raise ValueError("; ".join(validation_errors))
    except Exception as exc:
        for path, content in snapshots.items():
            restore_file(path, content)
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "step_id": selected_step,
            "errors": [str(exc)],
        }

    return {
        "accepted": True,
        "branch": branch_name,
        "stage": normalized_stage,
        "step_id": selected_step,
        "tdd_phase": status_info.get("tddPhase"),
        "generated_views": [str(path.relative_to(project_path)) for path in generated],
    }


def complete_implementation_step(
    project_path: Path,
    branch_name: str,
    stage: str,
    *,
    step_id: str | None = None,
    summary: str,
    red_evidence: list[str] | None = None,
    green_evidence: list[str] | None = None,
    refactor_note: str | None = None,
    evidence: list[str] | None = None,
    facts: list[str] | None = None,
    decisions: list[str] | None = None,
    contracts: list[str] | None = None,
) -> dict[str, Any]:
    try:
        normalized_stage = validate_implementation_stage(stage)
    except ValueError as exc:
        return {"accepted": False, "branch": branch_name, "stage": stage, "errors": [str(exc)]}

    normalized_summary = summary.strip()
    if not normalized_summary:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": ["summary must not be empty"],
        }

    normalized_red = normalize_text_list(red_evidence)
    normalized_green = normalize_text_list(green_evidence)
    normalized_evidence = normalize_text_list(evidence)
    normalized_facts = normalize_text_list(facts)
    normalized_decisions = normalize_text_list(decisions)
    normalized_contracts = normalize_text_list(contracts)
    normalized_refactor_note = refactor_note.strip() if refactor_note else None

    ensure_memory_layout(project_path, branch_name)
    paths = get_memory_paths(project_path, branch_name)
    snapshots = {
        paths.progress: snapshot_file(paths.progress),
        paths.active_session: snapshot_file(paths.active_session),
        paths.events: snapshot_file(paths.events),
        paths.facts: snapshot_file(paths.facts),
        paths.decisions: snapshot_file(paths.decisions),
        paths.contracts: snapshot_file(paths.contracts),
    }
    progress, active_session = load_progress(project_path, branch_name)

    selected_step = step_id or progress.get("currentImplementStep") or active_session.get("current_step")
    if not selected_step:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": ["step_id is required when there is no current implementation step"],
        }

    planned_steps = progress.get("plannedSteps", [])
    completed_steps = progress.setdefault("completedSteps", [])
    if selected_step not in planned_steps:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "step_id": selected_step,
            "errors": [f"step '{selected_step}' is not present in plannedSteps"],
        }
    if selected_step in completed_steps:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "step_id": selected_step,
            "errors": [f"step '{selected_step}' is already completed"],
        }
    if not is_step_ready(progress, selected_step):
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "step_id": selected_step,
            "errors": [
                f"step '{selected_step}' has incomplete dependencies: {', '.join(step_dependencies(progress, selected_step))}"
            ],
        }

    metadata = progress.get("stepMetadata", {}).get(selected_step, {})
    status_info = progress.setdefault("stepStatus", {}).setdefault(selected_step, {})
    ts = now_iso()
    completed_at = ts.split("T", 1)[0]
    try:
        status_info["redEvidence"] = append_unique(status_info.get("redEvidence", []), normalized_red)
        status_info["greenEvidence"] = append_unique(status_info.get("greenEvidence", []), normalized_green)
        if normalized_refactor_note is not None:
            status_info["refactorNote"] = normalized_refactor_note

        if metadata.get("tddPolicy") == "required":
            if not status_info.get("redEvidence"):
                raise ValueError(f"completed code step '{selected_step}' must record redEvidence")
            if not status_info.get("greenEvidence"):
                raise ValueError(f"completed code step '{selected_step}' must record greenEvidence")
            if not isinstance(status_info.get("refactorNote"), str) or not status_info.get("refactorNote", "").strip():
                raise ValueError(f"completed code step '{selected_step}' must record refactorNote")
            status_info["tddPhase"] = "completed"
        else:
            status_info["tddPhase"] = "waived"

        status_info["status"] = "completed"
        status_info["completedAt"] = completed_at
        if selected_step not in completed_steps:
            completed_steps.append(selected_step)

        next_step = select_next_executable_step(progress)
        progress["currentImplementStep"] = next_step
        if next_step:
            for candidate, candidate_status in progress.get("stepStatus", {}).items():
                if not isinstance(candidate_status, dict):
                    continue
                if candidate == next_step and candidate_status.get("status") == "in_progress":
                    continue
                if candidate != selected_step and candidate_status.get("status") == "in_progress":
                    candidate_status["status"] = "planned"

        write_json(paths.progress, progress)

        active_session["stage"] = normalized_stage
        active_session["current_step"] = next_step
        active_session["active_goal"] = (
            f"Implement {next_step}" if next_step else normalized_summary
        )
        active_session["last_checkpoint_at"] = ts
        active_session["updated_at"] = ts
        write_json(paths.active_session, active_session)

        append_jsonl(
            paths.events,
            build_completion_event(
                branch_name=branch_name,
                normalized_stage=normalized_stage,
                selected_step=selected_step,
                normalized_summary=normalized_summary,
                normalized_evidence=normalized_evidence,
                progress_path=str(paths.progress.relative_to(project_path)),
                status_info=status_info,
                next_step=next_step,
                completed_at=completed_at,
                ts=ts,
            ),
        )

        append_jsonl(
            paths.facts,
            build_completion_semantic_records(
                branch_name=branch_name,
                normalized_stage=normalized_stage,
                selected_step=selected_step,
                normalized_evidence=normalized_evidence,
                values=normalized_facts,
                semantic_kind="fact",
                ts=ts,
            ),
        )
        append_jsonl(
            paths.decisions,
            build_completion_semantic_records(
                branch_name=branch_name,
                normalized_stage=normalized_stage,
                selected_step=selected_step,
                normalized_evidence=normalized_evidence,
                values=normalized_decisions,
                semantic_kind="decision",
                ts=ts,
            ),
        )
        append_jsonl(
            paths.contracts,
            build_completion_semantic_records(
                branch_name=branch_name,
                normalized_stage=normalized_stage,
                selected_step=selected_step,
                normalized_evidence=normalized_evidence,
                values=normalized_contracts,
                semantic_kind="contract",
                ts=ts,
            ),
        )

        generated = consolidate_branch_memory(project_path, branch_name)
        validation_errors = validate_branch_memory(project_path, branch_name)
        if validation_errors:
            raise ValueError("; ".join(validation_errors))
    except Exception as exc:
        for path, content in snapshots.items():
            restore_file(path, content)
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "step_id": selected_step,
            "errors": [str(exc)],
        }

    return {
        "accepted": True,
        "branch": branch_name,
        "stage": normalized_stage,
        "step_id": selected_step,
        "next_step": progress.get("currentImplementStep"),
        "written": {
            "facts": len(normalized_facts),
            "decisions": len(normalized_decisions),
            "contracts": len(normalized_contracts),
        },
        "generated_views": [str(path.relative_to(project_path)) for path in generated],
    }
