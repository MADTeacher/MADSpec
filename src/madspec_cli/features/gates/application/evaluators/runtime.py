from __future__ import annotations

from pathlib import Path
from typing import Any

from madspec_cli.memory.shared.records import STEP_ID_PATTERN
from madspec_cli.memory.workflow.implementation_shared import (
    IMPLEMENTATION_STAGES,
    append_unique,
    normalize_text_list,
    step_dependencies,
)

from .shared import build_gate, known_function_samples, normalize_function_label


def collect_runtime_and_dependency_gates(
    *,
    project_path: Path,
    branch_name: str,
    progress: dict[str, Any],
    active_session: dict[str, Any],
    stage: str,
    operation: str,
    step_id: str | None,
    overrides: dict[str, Any],
) -> list[dict[str, Any]]:
    if operation == "register-step":
        return _collect_register_step_gates(
            project_path=project_path,
            branch_name=branch_name,
            progress=progress,
            stage=stage,
            step_id=step_id,
            overrides=overrides,
        )
    if stage in IMPLEMENTATION_STAGES:
        return _collect_implementation_gates(
            progress=progress,
            active_session=active_session,
            stage=stage,
            operation=operation,
            step_id=step_id,
            overrides=overrides,
        )
    return []


def _collect_register_step_gates(
    *,
    project_path: Path,
    branch_name: str,
    progress: dict[str, Any],
    stage: str,
    step_id: str | None,
    overrides: dict[str, Any],
) -> list[dict[str, Any]]:
    from madspec_cli.memory.workflow.planning import extract_function_catalog

    subject_id = step_id or "planned-step"
    planned_steps = [item for item in progress.get("plannedSteps", []) if isinstance(item, str)]
    completed_steps = {item for item in progress.get("completedSteps", []) if isinstance(item, str)}
    dependencies = overrides.get("depends_on", []) or []
    results: list[dict[str, Any]] = []

    if not step_id:
        results.append(
            build_gate(
                family="runtime_validity",
                scope="step",
                subject_id=subject_id,
                blocking=True,
                waivable=False,
                status="failed",
                message="step id is required for register-step",
                source_ids=["memory.progress"],
                stage=stage,
                operation="register-step",
            )
        )
        return results

    if not STEP_ID_PATTERN.match(step_id):
        results.append(
            build_gate(
                family="runtime_validity",
                scope="step",
                subject_id=subject_id,
                blocking=True,
                waivable=False,
                status="failed",
                message="candidate step id must match step-XX-kebab-case",
                source_ids=["memory.progress"],
                stage=stage,
                operation="register-step",
            )
        )
    if step_id in planned_steps:
        results.append(
            build_gate(
                family="runtime_validity",
                scope="step",
                subject_id=subject_id,
                blocking=True,
                waivable=False,
                status="failed",
                message="candidate step id already exists in plannedSteps",
                source_ids=["memory.progress"],
                stage=stage,
                operation="register-step",
            )
        )
    if len(set(dependencies)) != len(dependencies):
        results.append(
            build_gate(
                family="dependency_readiness",
                scope="step",
                subject_id=subject_id,
                blocking=True,
                waivable=False,
                status="failed",
                message="candidate dependencies must be unique",
                source_ids=["memory.progress"],
                stage=stage,
                operation="register-step",
            )
        )
    if step_id in dependencies:
        results.append(
            build_gate(
                family="dependency_readiness",
                scope="step",
                subject_id=subject_id,
                blocking=True,
                waivable=False,
                status="failed",
                message="candidate step cannot depend on itself",
                source_ids=["memory.progress"],
                stage=stage,
                operation="register-step",
            )
        )
    for dependency in dependencies:
        if dependency not in planned_steps:
            results.append(
                build_gate(
                    family="dependency_readiness",
                    scope="step",
                    subject_id=subject_id,
                    blocking=True,
                    waivable=False,
                    status="failed",
                    message=f"dependency '{dependency}' is not present in plannedSteps",
                    source_ids=["memory.progress"],
                    stage=stage,
                    operation="register-step",
                )
            )
        elif dependency in completed_steps:
            results.append(
                build_gate(
                    family="dependency_readiness",
                    scope="step",
                    subject_id=subject_id,
                    blocking=False,
                    waivable=False,
                    status="passed",
                    message=f"dependency '{dependency}' is already completed",
                    source_ids=["memory.progress"],
                    stage=stage,
                    operation="register-step",
                )
            )

    step_kind = overrides.get("step_kind")
    waiver_reason = overrides.get("waiver_reason")
    effective_tdd_policy = overrides.get("tdd_policy")
    if effective_tdd_policy is None:
        if step_kind == "code":
            effective_tdd_policy = "required"
        elif waiver_reason:
            effective_tdd_policy = "waived"
        else:
            effective_tdd_policy = "not-applicable"

    if step_kind not in {"code", "non-code"}:
        results.append(
            build_gate(
                family="runtime_validity",
                scope="step",
                subject_id=subject_id,
                blocking=True,
                waivable=False,
                status="failed",
                message="step kind must be one of: code, non-code",
                source_ids=["memory.progress"],
                stage=stage,
                operation="register-step",
            )
        )
        return results

    if effective_tdd_policy not in {"required", "waived", "not-applicable"}:
        results.append(
            build_gate(
                family="runtime_validity",
                scope="step",
                subject_id=subject_id,
                blocking=True,
                waivable=False,
                status="failed",
                message="tdd policy must be one of: required, waived, not-applicable",
                source_ids=["memory.progress"],
                stage=stage,
                operation="register-step",
            )
        )
        return results

    if step_kind == "code" and effective_tdd_policy != "required":
        results.append(
            build_gate(
                family="runtime_validity",
                scope="step",
                subject_id=subject_id,
                blocking=True,
                waivable=False,
                status="failed",
                message="code steps must use the required TDD policy",
                source_ids=["memory.progress"],
                stage=stage,
                operation="register-step",
            )
        )
    if step_kind == "non-code" and effective_tdd_policy == "required":
        results.append(
            build_gate(
                family="runtime_validity",
                scope="step",
                subject_id=subject_id,
                blocking=True,
                waivable=False,
                status="failed",
                message="non-code steps cannot use the required TDD policy",
                source_ids=["memory.progress"],
                stage=stage,
                operation="register-step",
            )
        )
    if effective_tdd_policy == "waived" and not waiver_reason:
        results.append(
            build_gate(
                family="runtime_validity",
                scope="step",
                subject_id=subject_id,
                blocking=True,
                waivable=False,
                status="failed",
                message="waiver reason is required when TDD policy is waived",
                source_ids=["memory.progress"],
                stage=stage,
                operation="register-step",
            )
        )
    if effective_tdd_policy != "waived" and waiver_reason is not None:
        results.append(
            build_gate(
                family="runtime_validity",
                scope="step",
                subject_id=subject_id,
                blocking=True,
                waivable=False,
                status="failed",
                message="waiver reason is only allowed when TDD policy is waived",
                source_ids=["memory.progress"],
                stage=stage,
                operation="register-step",
            )
        )

    normalized_covers = [normalize_function_label(item) for item in (overrides.get("covers", []) or [])]
    normalized_covers = [item for item in normalized_covers if item]
    if step_kind == "code" and not normalized_covers:
        results.append(
            build_gate(
                family="runtime_validity",
                scope="step",
                subject_id=subject_id,
                blocking=True,
                waivable=False,
                status="failed",
                message="code steps must declare at least one covered function",
                source_ids=["memory.progress"],
                stage=stage,
                operation="register-step",
            )
        )
    catalog = extract_function_catalog(project_path, branch_name, stage)
    known_functions = {item for items in catalog.values() for item in items}
    if not known_functions and normalized_covers:
        catalog_source = "feature.init.json" if "feature." in stage else "mvp.concept.json"
        results.append(
            build_gate(
                family="runtime_validity",
                scope="step",
                subject_id=subject_id,
                blocking=True,
                waivable=False,
                status="failed",
                message=f"no functions catalog found in {catalog_source} for the target stage",
                source_ids=[catalog_source],
                stage=stage,
                operation="register-step",
            )
        )
    unknown = [item for item in normalized_covers if item not in known_functions]
    if unknown:
        catalog_source = "feature.init.json" if "feature." in stage else "mvp.concept.json"
        choices = known_function_samples(catalog)
        suggestion = f" Known labels from {catalog_source}: {choices}" if choices else ""
        results.append(
            build_gate(
                family="runtime_validity",
                scope="step",
                subject_id=subject_id,
                blocking=True,
                waivable=False,
                status="failed",
                message=f"unknown covered functions in {catalog_source}: {', '.join(unknown)}.{suggestion}",
                source_ids=[catalog_source],
                stage=stage,
                operation="register-step",
            )
        )
    return results


def _collect_implementation_gates(
    *,
    progress: dict[str, Any],
    active_session: dict[str, Any],
    stage: str,
    operation: str,
    step_id: str | None,
    overrides: dict[str, Any],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    subject_id = step_id or "step"
    selected_step = step_id

    if operation == "start-step" and selected_step is None:
        results.append(
            build_gate(
                family="runtime_validity",
                scope="step",
                subject_id=subject_id,
                blocking=True,
                waivable=False,
                status="failed",
                message="no executable implementation step found",
                source_ids=["memory.progress"],
                stage=stage,
                operation=operation,
            )
        )
        return results
    if operation in {"checkpoint-step", "complete-step"} and selected_step is None:
        results.append(
            build_gate(
                family="runtime_validity",
                scope="step",
                subject_id=subject_id,
                blocking=True,
                waivable=False,
                status="failed",
                message="step_id is required when there is no current implementation step",
                source_ids=["memory.progress", "memory.active_session"],
                stage=stage,
                operation=operation,
            )
        )
        return results

    planned_steps = progress.get("plannedSteps", [])
    completed_steps = set(progress.get("completedSteps", []))
    if selected_step and selected_step not in planned_steps:
        results.append(
            build_gate(
                family="runtime_validity",
                scope="step",
                subject_id=subject_id,
                blocking=True,
                waivable=False,
                status="failed",
                message=f"step '{selected_step}' is not present in plannedSteps",
                source_ids=["memory.progress"],
                stage=stage,
                operation=operation,
            )
        )
        return results

    if selected_step and selected_step in completed_steps:
        results.append(
            build_gate(
                family="runtime_validity",
                scope="step",
                subject_id=subject_id,
                blocking=True,
                waivable=False,
                status="failed",
                message=f"step '{selected_step}' is already completed",
                source_ids=["memory.progress"],
                stage=stage,
                operation=operation,
            )
        )

    if selected_step:
        dependencies = step_dependencies(progress, selected_step)
        missing_dependencies = [dependency for dependency in dependencies if dependency not in completed_steps]
        if missing_dependencies and operation in {"start-step", "complete-step", "validate"}:
            results.append(
                build_gate(
                    family="dependency_readiness",
                    scope="step",
                    subject_id=subject_id,
                    blocking=True,
                    waivable=False,
                    status="failed",
                    message=f"step '{selected_step}' has incomplete dependencies: {', '.join(dependencies)}",
                    source_ids=["memory.progress"],
                    stage=stage,
                    operation=operation,
                )
            )
        elif operation in {"start-step", "complete-step", "validate"}:
            results.append(
                build_gate(
                    family="dependency_readiness",
                    scope="step",
                    subject_id=subject_id,
                    blocking=False,
                    waivable=False,
                    status="passed",
                    message="all step dependencies are satisfied",
                    source_ids=["memory.progress"],
                    stage=stage,
                    operation=operation,
                )
            )

    metadata = progress.get("stepMetadata", {}).get(selected_step, {}) if selected_step else {}
    status_info = progress.get("stepStatus", {}).get(selected_step, {}) if selected_step else {}
    if operation == "checkpoint-step":
        normalized_summary = (overrides.get("summary") or "").strip()
        normalized_phase = (overrides.get("tdd_phase") or "").strip().lower()
        normalized_red = normalize_text_list(overrides.get("red_evidence"))
        normalized_green = normalize_text_list(overrides.get("green_evidence"))
        normalized_refactor_note = (overrides.get("refactor_note") or "").strip()
        if not any([normalized_summary, normalized_phase, normalized_red, normalized_green, normalized_refactor_note]):
            results.append(
                build_gate(
                    family="runtime_validity",
                    scope="step",
                    subject_id=subject_id,
                    blocking=True,
                    waivable=False,
                    status="failed",
                    message="checkpoint must include summary, tdd phase, evidence, or refactor note",
                    source_ids=["memory.progress"],
                    stage=stage,
                    operation=operation,
                )
            )
        tdd_policy = metadata.get("tddPolicy")
        allowed_phases = {"waived"} if tdd_policy in {"waived", "not-applicable"} else {"not_started", "red", "green", "refactor"}
        if normalized_phase and normalized_phase not in allowed_phases:
            results.append(
                build_gate(
                    family="runtime_validity",
                    scope="step",
                    subject_id=subject_id,
                    blocking=True,
                    waivable=False,
                    status="failed",
                    message="tdd phase must be one of: " + ", ".join(sorted(allowed_phases)),
                    source_ids=["memory.progress"],
                    stage=stage,
                    operation=operation,
                )
            )

    if operation == "complete-step":
        normalized_summary = (overrides.get("summary") or "").strip()
        if not normalized_summary:
            results.append(
                build_gate(
                    family="runtime_validity",
                    scope="step",
                    subject_id=subject_id,
                    blocking=True,
                    waivable=False,
                    status="failed",
                    message="summary must not be empty",
                    source_ids=["memory.progress"],
                    stage=stage,
                    operation=operation,
                )
            )
        combined_red = append_unique(status_info.get("redEvidence", []), normalize_text_list(overrides.get("red_evidence")))
        combined_green = append_unique(status_info.get("greenEvidence", []), normalize_text_list(overrides.get("green_evidence")))
        refactor_note = (overrides.get("refactor_note") or "").strip() or status_info.get("refactorNote")
        if metadata.get("tddPolicy") == "required":
            if not combined_red:
                results.append(
                    build_gate(
                        family="runtime_validity",
                        scope="step",
                        subject_id=subject_id,
                        blocking=True,
                        waivable=False,
                        status="failed",
                        message=f"completed code step '{selected_step}' must record redEvidence",
                        source_ids=["memory.progress"],
                        stage=stage,
                        operation=operation,
                    )
                )
            if not combined_green:
                results.append(
                    build_gate(
                        family="runtime_validity",
                        scope="step",
                        subject_id=subject_id,
                        blocking=True,
                        waivable=False,
                        status="failed",
                        message=f"completed code step '{selected_step}' must record greenEvidence",
                        source_ids=["memory.progress"],
                        stage=stage,
                        operation=operation,
                    )
                )
            if not isinstance(refactor_note, str) or not refactor_note.strip():
                results.append(
                    build_gate(
                        family="runtime_validity",
                        scope="step",
                        subject_id=subject_id,
                        blocking=True,
                        waivable=False,
                        status="failed",
                        message=f"completed code step '{selected_step}' must record refactorNote",
                        source_ids=["memory.progress"],
                        stage=stage,
                        operation=operation,
                    )
                )
    return results
