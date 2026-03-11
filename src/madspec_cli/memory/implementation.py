from __future__ import annotations

from pathlib import Path
from typing import Any

from .records import make_record
from .storage import (
    _default_active_session,
    _default_progress_state,
    append_jsonl,
    ensure_memory_layout,
    get_memory_paths,
    now_iso,
    read_json,
    write_json,
)
from .validation import validate_branch_memory
from .views import consolidate_branch_memory

IMPLEMENTATION_STAGES = {"mvp.implement", "feature.implement"}


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


def _validate_implementation_stage(stage: str) -> str:
    normalized_stage = stage.strip().lower()
    if normalized_stage not in IMPLEMENTATION_STAGES:
        raise ValueError(
            "stage must be one of: " + ", ".join(sorted(IMPLEMENTATION_STAGES))
        )
    return normalized_stage


def _load_progress(project_path: Path, branch_name: str) -> tuple[Any, Any]:
    paths = get_memory_paths(project_path, branch_name)
    progress = read_json(paths.progress, _default_progress_state())
    active_session = read_json(paths.active_session, _default_active_session(branch_name))
    return progress, active_session


def _step_dependencies(progress: dict[str, Any], step_id: str) -> list[str]:
    return progress.get("planningMetadata", {}).get("stepDependencies", {}).get(step_id, [])


def _is_step_ready(progress: dict[str, Any], step_id: str) -> bool:
    completed_steps = set(progress.get("completedSteps", []))
    return all(dependency in completed_steps for dependency in _step_dependencies(progress, step_id))


def _select_next_executable_step(progress: dict[str, Any]) -> str | None:
    completed_steps = set(progress.get("completedSteps", []))
    step_status = progress.get("stepStatus", {})
    for step_id in progress.get("plannedSteps", []):
        if step_id in completed_steps:
            continue
        if step_status.get(step_id, {}).get("status") == "completed":
            continue
        if _is_step_ready(progress, step_id):
            return step_id
    return None


def _set_active_step(progress: dict[str, Any], step_id: str) -> None:
    for candidate, status_info in progress.get("stepStatus", {}).items():
        if not isinstance(status_info, dict):
            continue
        if candidate == step_id:
            status_info["status"] = "in_progress"
        elif status_info.get("status") == "in_progress":
            status_info["status"] = "planned"
    progress["currentImplementStep"] = step_id


def _append_unique(existing: list[str], values: list[str]) -> list[str]:
    result = list(existing)
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _validate_start_step(progress: dict[str, Any], step_id: str) -> list[str]:
    errors: list[str] = []
    planned_steps = progress.get("plannedSteps", [])
    completed_steps = set(progress.get("completedSteps", []))
    if step_id not in planned_steps:
        errors.append(f"step '{step_id}' is not present in plannedSteps")
        return errors
    if step_id in completed_steps:
        errors.append(f"step '{step_id}' is already completed")
    if not _is_step_ready(progress, step_id):
        errors.append(
            f"step '{step_id}' has incomplete dependencies: {', '.join(_step_dependencies(progress, step_id))}"
        )
    return errors


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
        normalized_stage = _validate_implementation_stage(stage)
    except ValueError as exc:
        return {"accepted": False, "branch": branch_name, "stage": stage, "errors": [str(exc)]}

    normalized_summary = (summary or "").strip()
    normalized_evidence = _normalize_text_list(evidence)

    ensure_memory_layout(project_path, branch_name)
    paths = get_memory_paths(project_path, branch_name)
    snapshots = {
        paths.progress: _snapshot_file(paths.progress),
        paths.active_session: _snapshot_file(paths.active_session),
        paths.events: _snapshot_file(paths.events),
    }
    progress, active_session = _load_progress(project_path, branch_name)

    selected_step = step_id or _select_next_executable_step(progress)
    if not selected_step:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": ["no executable implementation step found"],
        }

    errors = _validate_start_step(progress, selected_step)
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
        _set_active_step(progress, selected_step)
        write_json(paths.progress, progress)

        active_session["stage"] = normalized_stage
        active_session["current_step"] = selected_step
        active_session["active_goal"] = normalized_summary or f"Implement {selected_step}"
        active_session["last_checkpoint_at"] = ts
        active_session["updated_at"] = ts
        write_json(paths.active_session, active_session)

        append_jsonl(
            paths.events,
            [
                make_record(
                    branch_name,
                    normalized_stage,
                    "memory.start-step",
                    normalized_summary or f"Started implementation step {selected_step}",
                    step_id=selected_step,
                    status="validated",
                    evidence=normalized_evidence or [str(paths.progress.relative_to(project_path))],
                    scope="step",
                    record_type="implementation_start",
                    metadata={
                        "dependencies": _step_dependencies(progress, selected_step),
                    },
                    ts=ts,
                )
            ],
        )

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
        normalized_stage = _validate_implementation_stage(stage)
    except ValueError as exc:
        return {"accepted": False, "branch": branch_name, "stage": stage, "errors": [str(exc)]}

    normalized_summary = (summary or "").strip()
    normalized_red = _normalize_text_list(red_evidence)
    normalized_green = _normalize_text_list(green_evidence)
    normalized_evidence = _normalize_text_list(evidence)
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
        paths.progress: _snapshot_file(paths.progress),
        paths.active_session: _snapshot_file(paths.active_session),
        paths.events: _snapshot_file(paths.events),
    }
    progress, active_session = _load_progress(project_path, branch_name)

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
        _set_active_step(progress, selected_step)
        status_info = progress.setdefault("stepStatus", {}).setdefault(selected_step, {})
        status_info["status"] = "in_progress"
        if normalized_phase:
            status_info["tddPhase"] = normalized_phase
        status_info["redEvidence"] = _append_unique(status_info.get("redEvidence", []), normalized_red)
        status_info["greenEvidence"] = _append_unique(status_info.get("greenEvidence", []), normalized_green)
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
            [
                make_record(
                    branch_name,
                    normalized_stage,
                    "memory.checkpoint-step",
                    normalized_summary or f"Checkpointed implementation step {selected_step}",
                    step_id=selected_step,
                    status="validated",
                    evidence=normalized_evidence
                    or normalized_red
                    or normalized_green
                    or [str(paths.progress.relative_to(project_path))],
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
            ],
        )

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
        normalized_stage = _validate_implementation_stage(stage)
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

    normalized_red = _normalize_text_list(red_evidence)
    normalized_green = _normalize_text_list(green_evidence)
    normalized_evidence = _normalize_text_list(evidence)
    normalized_facts = _normalize_text_list(facts)
    normalized_decisions = _normalize_text_list(decisions)
    normalized_contracts = _normalize_text_list(contracts)
    normalized_refactor_note = refactor_note.strip() if refactor_note else None

    ensure_memory_layout(project_path, branch_name)
    paths = get_memory_paths(project_path, branch_name)
    snapshots = {
        paths.progress: _snapshot_file(paths.progress),
        paths.active_session: _snapshot_file(paths.active_session),
        paths.events: _snapshot_file(paths.events),
        paths.facts: _snapshot_file(paths.facts),
        paths.decisions: _snapshot_file(paths.decisions),
        paths.contracts: _snapshot_file(paths.contracts),
    }
    progress, active_session = _load_progress(project_path, branch_name)

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
    if not _is_step_ready(progress, selected_step):
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "step_id": selected_step,
            "errors": [
                f"step '{selected_step}' has incomplete dependencies: {', '.join(_step_dependencies(progress, selected_step))}"
            ],
        }

    metadata = progress.get("stepMetadata", {}).get(selected_step, {})
    status_info = progress.setdefault("stepStatus", {}).setdefault(selected_step, {})
    ts = now_iso()
    completed_at = ts.split("T", 1)[0]
    try:
        status_info["redEvidence"] = _append_unique(status_info.get("redEvidence", []), normalized_red)
        status_info["greenEvidence"] = _append_unique(status_info.get("greenEvidence", []), normalized_green)
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

        next_step = _select_next_executable_step(progress)
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
            [
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
                    or [str(paths.progress.relative_to(project_path))],
                    scope="step",
                    record_type="implementation_completion",
                    metadata={
                        "next_step": next_step,
                        "completedAt": completed_at,
                    },
                    ts=ts,
                )
            ],
        )

        append_jsonl(
            paths.facts,
            [
                make_record(
                    branch_name,
                    normalized_stage,
                    "memory.complete-step",
                    item,
                    step_id=selected_step,
                    status="validated",
                    evidence=normalized_evidence,
                    scope="step",
                    semantic_kind="fact",
                    record_type="fact",
                    ts=ts,
                )
                for item in normalized_facts
            ],
        )
        append_jsonl(
            paths.decisions,
            [
                make_record(
                    branch_name,
                    normalized_stage,
                    "memory.complete-step",
                    item,
                    step_id=selected_step,
                    status="validated",
                    evidence=normalized_evidence,
                    scope="step",
                    semantic_kind="decision",
                    record_type="decision",
                    ts=ts,
                )
                for item in normalized_decisions
            ],
        )
        append_jsonl(
            paths.contracts,
            [
                make_record(
                    branch_name,
                    normalized_stage,
                    "memory.complete-step",
                    item,
                    step_id=selected_step,
                    status="validated",
                    evidence=normalized_evidence,
                    scope="step",
                    semantic_kind="contract",
                    record_type="contract",
                    ts=ts,
                )
                for item in normalized_contracts
            ],
        )

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
