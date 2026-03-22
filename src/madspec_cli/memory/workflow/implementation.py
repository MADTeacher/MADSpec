from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..domain.progress import select_next_executable_step

if TYPE_CHECKING:
    from madspec_cli.shared.kernel.ports import BranchPolicyEvaluator, GateEvaluator, GateFailureExtractor


def _lazy_gate_imports() -> tuple:
    from madspec_cli.features.gates.application.common import evaluate_gate_context, gate_failure_messages
    return evaluate_gate_context, gate_failure_messages


def _lazy_policy_import():
    from madspec_cli.features.policy.application.common import evaluate_branch_policies
    return evaluate_branch_policies
from ..domain.step_resolution import resolve_runtime_step_id
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
    set_active_step,
    step_dependencies,
    validate_implementation_stage,
    validate_start_step,
)
from ..shared.storage import (
    ensure_memory_layout,
    get_memory_paths,
    now_iso,
)
from ..shared.system_store.constants import LEASE_TTL_SECONDS, SYSTEM_SESSION_KEY
from ..shared.system_store.canonical_state import CanonicalBranchState, build_runtime_snapshot_specs, load_canonical_branch_state, tag_records_for_stream
from ..shared.system_store.leases import build_implementation_step_lease
from ..shared.system_store.runtime_mutations import RuntimeMutationPlan, commit_runtime_mutation
from ..shared.system_store.sessions import read_runtime_session_payload
from ..shared.system_store.store import MemoryStore


def _step_runtime_signature(progress: dict[str, Any], step_id: str) -> str:
    payload = {
        "planned": step_id in progress.get("plannedSteps", []),
        "completed": step_id in progress.get("completedSteps", []),
        "status": progress.get("stepStatus", {}).get(step_id, {}),
        "metadata": progress.get("stepMetadata", {}).get(step_id, {}),
        "covers": progress.get("coversFunctions", {}).get(step_id, {}),
        "dependencies": progress.get("planningMetadata", {}).get("stepDependencies", {}).get(step_id, []),
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def _resolve_session_work_item(
    project_path: Path,
    branch_name: str,
    *,
    session_key: str,
) -> dict[str, Any] | None:
    coordination = MemoryStore(project_path).fetch_session_coordination(
        branch=branch_name,
        session_key=session_key,
    )
    work_item = coordination.get("work_item")
    if not work_item:
        return None
    claim = coordination.get("claim")
    if claim is None:
        return None
    return {
        "task": coordination.get("task"),
        "work_item": work_item,
        "claim": claim,
    }


def _validate_work_item_ownership(
    project_path: Path,
    branch_name: str,
    *,
    session_key: str,
    selected_step: str,
) -> dict[str, Any] | None:
    bound = _resolve_session_work_item(
        project_path,
        branch_name,
        session_key=session_key,
    )
    if bound is None:
        return None
    work_item = dict(bound["work_item"])
    scope_descriptor = dict(work_item.get("scope_descriptor") or {})
    expected_step_id = work_item.get("step_id") or scope_descriptor.get("step_id")
    if expected_step_id != selected_step:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": "mvp.implement",
            "step_id": selected_step,
            "errors": [
                f"session '{session_key}' is bound to work item '{work_item['work_item_id']}' for step '{expected_step_id}', not '{selected_step}'"
            ],
            "coordination": bound,
        }
    if not any(scope_descriptor.get(key) for key in ("paths", "artifacts", "concerns")):
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": "mvp.implement",
            "step_id": selected_step,
            "errors": [f"work item '{work_item['work_item_id']}' has no executable scope descriptor"],
            "coordination": bound,
        }
    return None


def _work_item_runtime_update(
    project_path: Path,
    branch_name: str,
    *,
    session_key: str,
    selected_step: str,
    next_status: str,
) -> list[dict[str, Any]]:
    bound = _resolve_session_work_item(
        project_path,
        branch_name,
        session_key=session_key,
    )
    if bound is None:
        return []
    work_item = dict(bound["work_item"])
    if work_item.get("step_id") != selected_step:
        return []
    if next_status == "in_progress" and work_item.get("status") in {"in_progress", "completed"}:
        return []
    if next_status == "completed" and work_item.get("status") == "completed":
        return []
    work_item["status"] = next_status
    work_item["updated_at"] = now_iso()
    return [work_item]


def _build_start_step_plan(
    project_path: Path,
    branch_name: str,
    normalized_stage: str,
    *,
    session_key: str,
    selected_step: str,
    normalized_summary: str,
    normalized_evidence: list[str],
    canonical: CanonicalBranchState,
) -> RuntimeMutationPlan:
    paths = get_memory_paths(project_path, branch_name)
    progress = dict(canonical.progress)
    active_session = read_runtime_session_payload(
        project_path,
        branch_name=branch_name,
        session_key=session_key,
    )

    ts = now_iso()
    set_active_step(progress, selected_step)
    active_session["stage"] = normalized_stage
    active_session["current_step"] = selected_step
    active_session["active_goal"] = normalized_summary or f"Implement {selected_step}"
    active_session["last_checkpoint_at"] = ts
    active_session["updated_at"] = ts
    return RuntimeMutationPlan(
        stage_snapshots=build_runtime_snapshot_specs(
            project_path,
            branch_name,
            {"progress": progress},
        ),
        sessions=[{"session_key": session_key, "payload": active_session}],
        work_items=_work_item_runtime_update(
            project_path,
            branch_name,
            session_key=session_key,
            selected_step=selected_step,
            next_status="in_progress",
        ),
        records=tag_records_for_stream(
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
            "events",
        ),
        response_payload={
            "step_id": selected_step,
            "status": progress.get("stepStatus", {}).get(selected_step, {}).get("status"),
        },
    )


def _build_checkpoint_step_plan(
    project_path: Path,
    branch_name: str,
    normalized_stage: str,
    *,
    session_key: str,
    selected_step: str,
    normalized_summary: str,
    normalized_phase: str | None,
    normalized_red: list[str],
    normalized_green: list[str],
    normalized_refactor_note: str | None,
    normalized_evidence: list[str],
    canonical: CanonicalBranchState,
) -> RuntimeMutationPlan:
    paths = get_memory_paths(project_path, branch_name)
    progress = dict(canonical.progress)
    active_session = read_runtime_session_payload(
        project_path,
        branch_name=branch_name,
        session_key=session_key,
    )

    ts = now_iso()
    set_active_step(progress, selected_step)
    status_info = progress.setdefault("stepStatus", {}).setdefault(selected_step, {})
    status_info["status"] = "in_progress"
    if normalized_phase:
        status_info["tddPhase"] = normalized_phase
    status_info["redEvidence"] = append_unique(status_info.get("redEvidence", []), normalized_red)
    status_info["greenEvidence"] = append_unique(status_info.get("greenEvidence", []), normalized_green)
    if normalized_refactor_note is not None:
        status_info["refactorNote"] = normalized_refactor_note

    active_session["stage"] = normalized_stage
    active_session["current_step"] = selected_step
    if normalized_summary:
        active_session["active_goal"] = normalized_summary
    active_session["last_checkpoint_at"] = ts
    active_session["updated_at"] = ts
    return RuntimeMutationPlan(
        stage_snapshots=build_runtime_snapshot_specs(
            project_path,
            branch_name,
            {"progress": progress},
        ),
        sessions=[{"session_key": session_key, "payload": active_session}],
        work_items=_work_item_runtime_update(
            project_path,
            branch_name,
            session_key=session_key,
            selected_step=selected_step,
            next_status="in_progress",
        ),
        records=tag_records_for_stream(
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
            "events",
        ),
        response_payload={
            "step_id": selected_step,
            "tdd_phase": status_info.get("tddPhase"),
        },
    )


def _build_complete_step_plan(
    project_path: Path,
    branch_name: str,
    normalized_stage: str,
    *,
    session_key: str,
    selected_step: str,
    normalized_summary: str,
    normalized_red: list[str],
    normalized_green: list[str],
    normalized_refactor_note: str | None,
    normalized_evidence: list[str],
    normalized_facts: list[str],
    normalized_decisions: list[str],
    normalized_contracts: list[str],
    canonical: CanonicalBranchState,
) -> RuntimeMutationPlan:
    paths = get_memory_paths(project_path, branch_name)
    progress = dict(canonical.progress)
    active_session = read_runtime_session_payload(
        project_path,
        branch_name=branch_name,
        session_key=session_key,
    )

    completed_steps = progress.setdefault("completedSteps", [])
    metadata = progress.get("stepMetadata", {}).get(selected_step, {})
    status_info = progress.setdefault("stepStatus", {}).setdefault(selected_step, {})
    ts = now_iso()
    completed_at = ts.split("T", 1)[0]
    status_info["redEvidence"] = append_unique(status_info.get("redEvidence", []), normalized_red)
    status_info["greenEvidence"] = append_unique(status_info.get("greenEvidence", []), normalized_green)
    if normalized_refactor_note is not None:
        status_info["refactorNote"] = normalized_refactor_note
    if metadata.get("tddPolicy") == "required":
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

    active_session["stage"] = normalized_stage
    active_session["current_step"] = next_step
    active_session["active_goal"] = (
        f"Implement {next_step}" if next_step else normalized_summary
    )
    active_session["last_checkpoint_at"] = ts
    active_session["updated_at"] = ts

    records: list[dict[str, Any]] = []
    records.extend(
        tag_records_for_stream(
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
            "events",
        )
    )
    records.extend(
        tag_records_for_stream(
            build_completion_semantic_records(
                branch_name=branch_name,
                normalized_stage=normalized_stage,
                selected_step=selected_step,
                normalized_evidence=normalized_evidence,
                values=normalized_facts,
                semantic_kind="fact",
                ts=ts,
            ),
            "facts",
        )
    )
    records.extend(
        tag_records_for_stream(
            build_completion_semantic_records(
                branch_name=branch_name,
                normalized_stage=normalized_stage,
                selected_step=selected_step,
                normalized_evidence=normalized_evidence,
                values=normalized_decisions,
                semantic_kind="decision",
                ts=ts,
            ),
            "decisions",
        )
    )
    records.extend(
        tag_records_for_stream(
            build_completion_semantic_records(
                branch_name=branch_name,
                normalized_stage=normalized_stage,
                selected_step=selected_step,
                normalized_evidence=normalized_evidence,
                values=normalized_contracts,
                semantic_kind="contract",
                ts=ts,
            ),
            "contracts",
        )
    )
    return RuntimeMutationPlan(
        stage_snapshots=build_runtime_snapshot_specs(
            project_path,
            branch_name,
            {"progress": progress},
        ),
        sessions=[{"session_key": session_key, "payload": active_session}],
        work_items=_work_item_runtime_update(
            project_path,
            branch_name,
            session_key=session_key,
            selected_step=selected_step,
            next_status="completed",
        ),
        records=records,
        response_payload={
            "step_id": selected_step,
            "next_step": progress.get("currentImplementStep"),
            "written": {
                "facts": len(normalized_facts),
                "decisions": len(normalized_decisions),
                "contracts": len(normalized_contracts),
            },
        },
    )


def _detect_implementation_conflict(
    project_path: Path,
    branch_name: str,
    *,
    session_key: str,
    stage: str,
    selected_step: str,
    explicit_step_id: str | None,
    base_state: CanonicalBranchState,
    current_state: CanonicalBranchState,
) -> dict[str, Any] | None:
    current_session = read_runtime_session_payload(
        project_path,
        branch_name=branch_name,
        session_key=session_key,
    )
    if explicit_step_id is None:
        resolved_step = resolve_runtime_step_id(
            progress=current_state.progress,
            session_payload=current_session,
            stage=stage,
            explicit_step_id=None,
            require_ready=False,
        )
        if resolved_step != selected_step:
            return {
                "kind": "progress_conflict",
                "scope": "step",
                "step_id": selected_step,
                "conflicting_fields": ["currentImplementStep"],
                "details": {"reason": "selected implementation step changed while preparing the mutation"},
            }

    if _step_runtime_signature(base_state.progress, selected_step) != _step_runtime_signature(current_state.progress, selected_step):
        return {
            "kind": "progress_conflict",
            "scope": "step",
            "step_id": selected_step,
            "conflicting_fields": ["stepStatus", "stepMetadata", "coversFunctions", "planningMetadata.stepDependencies"],
            "details": {"reason": "target implementation step was modified by another writer"},
        }

    return None


def start_implementation_step(
    project_path: Path,
    branch_name: str,
    stage: str,
    *,
    session_key: str = SYSTEM_SESSION_KEY,
    expected_revision: int | None = None,
    step_id: str | None = None,
    summary: str | None = None,
    evidence: list[str] | None = None,
    _evaluate_gate_context: GateEvaluator | None = None,
    _gate_failure_messages: GateFailureExtractor | None = None,
    _evaluate_branch_policies: BranchPolicyEvaluator | None = None,
) -> dict[str, Any]:
    if _evaluate_gate_context is None or _gate_failure_messages is None:
        egc, gfm = _lazy_gate_imports()
        if _evaluate_gate_context is None:
            _evaluate_gate_context = egc
        if _gate_failure_messages is None:
            _gate_failure_messages = gfm
    if _evaluate_branch_policies is None:
        _evaluate_branch_policies = _lazy_policy_import()

    try:
        normalized_stage = validate_implementation_stage(stage)
    except ValueError as exc:
        return {"accepted": False, "branch": branch_name, "stage": stage, "errors": [str(exc)]}

    normalized_summary = (summary or "").strip()
    normalized_evidence = normalize_text_list(evidence)

    ensure_memory_layout(project_path, branch_name, stage=normalized_stage)
    gate_payload = _evaluate_gate_context(
        project_path,
        branch_name,
        stage=normalized_stage,
        operation="start-step",
        session_key=session_key,
        step_id=step_id,
        overrides={"summary": normalized_summary, "evidence": normalized_evidence},
        include_ratification=False,
        record_history=False,
    )
    if gate_payload["overall_status"] == "blocked":
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "step_id": gate_payload.get("step_id"),
            "errors": _gate_failure_messages(gate_payload),
            "gate_summary": gate_payload,
        }
    progress, active_session = load_progress(
        project_path,
        branch_name,
        session_key=session_key,
    )

    selected_step = resolve_runtime_step_id(
        progress=progress,
        session_payload=active_session,
        stage=normalized_stage,
        explicit_step_id=step_id,
        require_ready=step_id is None,
    )
    if not selected_step:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": ["no executable implementation step found"],
        }

    ownership_error = _validate_work_item_ownership(
        project_path,
        branch_name,
        session_key=session_key,
        selected_step=selected_step,
    )
    if ownership_error is not None:
        ownership_error["stage"] = normalized_stage
        return ownership_error

    errors = validate_start_step(progress, selected_step)
    if errors:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "step_id": selected_step,
            "errors": errors,
        }

    policy_payload = _evaluate_branch_policies(
        project_path,
        branch_name,
        stage=normalized_stage,
        operation="start-step",
        step_id=selected_step,
        include_system_policies=False,
    )
    if policy_payload["violations"]:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "step_id": selected_step,
            "errors": [item["message"] for item in policy_payload["violations"]],
        }

    base_state = load_canonical_branch_state(project_path, branch_name)
    projection_meta = commit_runtime_mutation(
        project_path,
        branch_name=branch_name,
        stage=normalized_stage,
        mutation_kind="start-step",
        scope="step",
        session_key=session_key,
        expected_revision=expected_revision if expected_revision is not None else base_state.runtime_revision,
        base_state=base_state,
        plan_builder=lambda latest_state: _build_start_step_plan(
            project_path,
            branch_name,
            normalized_stage,
            session_key=session_key,
            selected_step=selected_step,
            normalized_summary=normalized_summary,
            normalized_evidence=normalized_evidence,
            canonical=latest_state,
        ),
        conflict_detector=lambda base, current: _detect_implementation_conflict(
            project_path,
            branch_name,
            session_key=session_key,
            stage=normalized_stage,
            selected_step=selected_step,
            explicit_step_id=step_id,
            base_state=base,
            current_state=current,
        ),
        lease=build_implementation_step_lease(
            branch_name=branch_name,
            step_id=selected_step,
            mutation_kind="start-step",
            session_key=session_key,
            ttl_seconds=LEASE_TTL_SECONDS,
        ),
    )
    if not projection_meta.get("accepted", True):
        return projection_meta

    payload = {
        "accepted": True,
        "branch": branch_name,
        "stage": normalized_stage,
        "step_id": projection_meta.get("step_id", selected_step),
        "status": projection_meta.get("status"),
    }
    payload.update(projection_meta)
    return payload


def checkpoint_implementation_step(
    project_path: Path,
    branch_name: str,
    stage: str,
    *,
    session_key: str = SYSTEM_SESSION_KEY,
    expected_revision: int | None = None,
    step_id: str | None = None,
    summary: str | None = None,
    tdd_phase: str | None = None,
    red_evidence: list[str] | None = None,
    green_evidence: list[str] | None = None,
    refactor_note: str | None = None,
    evidence: list[str] | None = None,
    _evaluate_gate_context: GateEvaluator | None = None,
    _gate_failure_messages: GateFailureExtractor | None = None,
    _evaluate_branch_policies: BranchPolicyEvaluator | None = None,
) -> dict[str, Any]:
    if _evaluate_gate_context is None or _gate_failure_messages is None:
        egc, gfm = _lazy_gate_imports()
        if _evaluate_gate_context is None:
            _evaluate_gate_context = egc
        if _gate_failure_messages is None:
            _gate_failure_messages = gfm
    if _evaluate_branch_policies is None:
        _evaluate_branch_policies = _lazy_policy_import()

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
        gate_payload = _evaluate_gate_context(
            project_path,
            branch_name,
            stage=normalized_stage,
            operation="checkpoint-step",
            session_key=session_key,
            step_id=step_id,
            overrides={
                "summary": normalized_summary,
                "tdd_phase": normalized_phase,
                "red_evidence": normalized_red,
                "green_evidence": normalized_green,
                "refactor_note": normalized_refactor_note,
                "evidence": normalized_evidence,
            },
            include_ratification=False,
            record_history=False,
        )
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": _gate_failure_messages(gate_payload) or ["checkpoint must include summary, tdd phase, evidence, or refactor note"],
            "gate_summary": gate_payload,
        }

    ensure_memory_layout(project_path, branch_name, stage=normalized_stage)
    gate_payload = _evaluate_gate_context(
        project_path,
        branch_name,
        stage=normalized_stage,
        operation="checkpoint-step",
        session_key=session_key,
        step_id=step_id,
        overrides={
            "summary": normalized_summary,
            "tdd_phase": normalized_phase,
            "red_evidence": normalized_red,
            "green_evidence": normalized_green,
            "refactor_note": normalized_refactor_note,
            "evidence": normalized_evidence,
        },
        include_ratification=False,
        record_history=False,
    )
    if gate_payload["overall_status"] == "blocked":
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "step_id": gate_payload.get("step_id"),
            "errors": _gate_failure_messages(gate_payload),
            "gate_summary": gate_payload,
        }
    progress, active_session = load_progress(
        project_path,
        branch_name,
        session_key=session_key,
    )

    selected_step = resolve_runtime_step_id(
        progress=progress,
        session_payload=active_session,
        stage=normalized_stage,
        explicit_step_id=step_id,
    )
    if not selected_step:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": ["step_id is required when there is no current implementation step"],
        }

    ownership_error = _validate_work_item_ownership(
        project_path,
        branch_name,
        session_key=session_key,
        selected_step=selected_step,
    )
    if ownership_error is not None:
        ownership_error["stage"] = normalized_stage
        return ownership_error

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

    policy_payload = _evaluate_branch_policies(
        project_path,
        branch_name,
        stage=normalized_stage,
        operation="checkpoint-step",
        step_id=selected_step,
        overrides={
            "step_kind": metadata.get("kind"),
            "tdd_policy": tdd_policy,
            "tdd_phase": normalized_phase or status_info.get("tddPhase"),
            "status": "in_progress",
            "red_evidence": append_unique(status_info.get("redEvidence", []), normalized_red),
            "green_evidence": append_unique(status_info.get("greenEvidence", []), normalized_green),
            "refactor_note": normalized_refactor_note if normalized_refactor_note is not None else status_info.get("refactorNote"),
        },
        include_system_policies=False,
    )
    if policy_payload["violations"]:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "step_id": selected_step,
            "errors": [item["message"] for item in policy_payload["violations"]],
        }

    base_state = load_canonical_branch_state(project_path, branch_name)
    projection_meta = commit_runtime_mutation(
        project_path,
        branch_name=branch_name,
        stage=normalized_stage,
        mutation_kind="checkpoint-step",
        scope="step",
        session_key=session_key,
        expected_revision=expected_revision if expected_revision is not None else base_state.runtime_revision,
        base_state=base_state,
        plan_builder=lambda latest_state: _build_checkpoint_step_plan(
            project_path,
            branch_name,
            normalized_stage,
            session_key=session_key,
            selected_step=selected_step,
            normalized_summary=normalized_summary,
            normalized_phase=normalized_phase,
            normalized_red=normalized_red,
            normalized_green=normalized_green,
            normalized_refactor_note=normalized_refactor_note,
            normalized_evidence=normalized_evidence,
            canonical=latest_state,
        ),
        conflict_detector=lambda base, current: _detect_implementation_conflict(
            project_path,
            branch_name,
            session_key=session_key,
            stage=normalized_stage,
            selected_step=selected_step,
            explicit_step_id=step_id,
            base_state=base,
            current_state=current,
        ),
        lease=build_implementation_step_lease(
            branch_name=branch_name,
            step_id=selected_step,
            mutation_kind="checkpoint-step",
            session_key=session_key,
            ttl_seconds=LEASE_TTL_SECONDS,
        ),
    )
    if not projection_meta.get("accepted", True):
        return projection_meta

    payload = {
        "accepted": True,
        "branch": branch_name,
        "stage": normalized_stage,
        "step_id": projection_meta.get("step_id", selected_step),
        "tdd_phase": projection_meta.get("tdd_phase"),
    }
    payload.update(projection_meta)
    return payload


def complete_implementation_step(
    project_path: Path,
    branch_name: str,
    stage: str,
    *,
    session_key: str = SYSTEM_SESSION_KEY,
    expected_revision: int | None = None,
    step_id: str | None = None,
    summary: str,
    red_evidence: list[str] | None = None,
    green_evidence: list[str] | None = None,
    refactor_note: str | None = None,
    evidence: list[str] | None = None,
    facts: list[str] | None = None,
    decisions: list[str] | None = None,
    contracts: list[str] | None = None,
    _evaluate_gate_context: GateEvaluator | None = None,
    _gate_failure_messages: GateFailureExtractor | None = None,
    _evaluate_branch_policies: BranchPolicyEvaluator | None = None,
) -> dict[str, Any]:
    if _evaluate_gate_context is None or _gate_failure_messages is None:
        egc, gfm = _lazy_gate_imports()
        if _evaluate_gate_context is None:
            _evaluate_gate_context = egc
        if _gate_failure_messages is None:
            _gate_failure_messages = gfm
    if _evaluate_branch_policies is None:
        _evaluate_branch_policies = _lazy_policy_import()

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

    gate_payload = _evaluate_gate_context(
        project_path,
        branch_name,
        stage=normalized_stage,
        operation="complete-step",
        session_key=session_key,
        step_id=step_id,
        overrides={
            "summary": normalized_summary,
            "red_evidence": normalized_red,
            "green_evidence": normalized_green,
            "refactor_note": normalized_refactor_note,
            "evidence": normalized_evidence,
        },
        include_ratification=False,
        record_history=False,
    )
    if gate_payload["overall_status"] == "blocked":
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "step_id": gate_payload.get("step_id"),
            "errors": _gate_failure_messages(gate_payload),
            "gate_summary": gate_payload,
        }

    ensure_memory_layout(project_path, branch_name, stage=normalized_stage)
    progress, active_session = load_progress(
        project_path,
        branch_name,
        session_key=session_key,
    )

    selected_step = resolve_runtime_step_id(
        progress=progress,
        session_payload=active_session,
        stage=normalized_stage,
        explicit_step_id=step_id,
    )
    if not selected_step:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": ["step_id is required when there is no current implementation step"],
        }

    ownership_error = _validate_work_item_ownership(
        project_path,
        branch_name,
        session_key=session_key,
        selected_step=selected_step,
    )
    if ownership_error is not None:
        ownership_error["stage"] = normalized_stage
        return ownership_error

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
    status_info["redEvidence"] = append_unique(status_info.get("redEvidence", []), normalized_red)
    status_info["greenEvidence"] = append_unique(status_info.get("greenEvidence", []), normalized_green)
    if normalized_refactor_note is not None:
        status_info["refactorNote"] = normalized_refactor_note

    if metadata.get("tddPolicy") == "required":
        if not status_info.get("redEvidence"):
            return {
                "accepted": False,
                "branch": branch_name,
                "stage": normalized_stage,
                "step_id": selected_step,
                "errors": [f"completed code step '{selected_step}' must record redEvidence"],
            }
        if not status_info.get("greenEvidence"):
            return {
                "accepted": False,
                "branch": branch_name,
                "stage": normalized_stage,
                "step_id": selected_step,
                "errors": [f"completed code step '{selected_step}' must record greenEvidence"],
            }
        if not isinstance(status_info.get("refactorNote"), str) or not status_info.get("refactorNote", "").strip():
            return {
                "accepted": False,
                "branch": branch_name,
                "stage": normalized_stage,
                "step_id": selected_step,
                "errors": [f"completed code step '{selected_step}' must record refactorNote"],
            }
        status_info["tddPhase"] = "completed"
    else:
        status_info["tddPhase"] = "waived"

    policy_payload = _evaluate_branch_policies(
        project_path,
        branch_name,
        stage=normalized_stage,
        operation="complete-step",
        step_id=selected_step,
        overrides={
            "step_kind": metadata.get("kind"),
            "tdd_policy": metadata.get("tddPolicy"),
            "tdd_phase": status_info.get("tddPhase"),
            "status": "completed",
            "red_evidence": status_info.get("redEvidence", []),
            "green_evidence": status_info.get("greenEvidence", []),
            "refactor_note": status_info.get("refactorNote"),
        },
        include_system_policies=False,
    )
    if policy_payload["violations"]:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "step_id": selected_step,
            "errors": ["; ".join(item["message"] for item in policy_payload["violations"])],
        }

    base_state = load_canonical_branch_state(project_path, branch_name)
    projection_meta = commit_runtime_mutation(
        project_path,
        branch_name=branch_name,
        stage=normalized_stage,
        mutation_kind="complete-step",
        scope="step",
        session_key=session_key,
        expected_revision=expected_revision if expected_revision is not None else base_state.runtime_revision,
        base_state=base_state,
        plan_builder=lambda latest_state: _build_complete_step_plan(
            project_path,
            branch_name,
            normalized_stage,
            session_key=session_key,
            selected_step=selected_step,
            normalized_summary=normalized_summary,
            normalized_red=normalized_red,
            normalized_green=normalized_green,
            normalized_refactor_note=normalized_refactor_note,
            normalized_evidence=normalized_evidence,
            normalized_facts=normalized_facts,
            normalized_decisions=normalized_decisions,
            normalized_contracts=normalized_contracts,
            canonical=latest_state,
        ),
        conflict_detector=lambda base, current: _detect_implementation_conflict(
            project_path,
            branch_name,
            session_key=session_key,
            stage=normalized_stage,
            selected_step=selected_step,
            explicit_step_id=step_id,
            base_state=base,
            current_state=current,
        ),
        lease=build_implementation_step_lease(
            branch_name=branch_name,
            step_id=selected_step,
            mutation_kind="complete-step",
            session_key=session_key,
            ttl_seconds=LEASE_TTL_SECONDS,
        ),
    )
    if not projection_meta.get("accepted", True):
        return projection_meta

    payload = {
        "accepted": True,
        "branch": branch_name,
        "stage": normalized_stage,
        "step_id": projection_meta.get("step_id", selected_step),
        "next_step": projection_meta.get("next_step"),
        "written": projection_meta.get("written"),
    }
    payload.update(projection_meta)
    return payload
