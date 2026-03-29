from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..shared.progress_utils import _normalize_function_label
from ..shared.records import STEP_ID_PATTERN
from ..workflow.implementation_shared import append_unique, normalize_text_list, step_dependencies


@dataclass(frozen=True)
class WorkflowRuleFinding:
    family: str
    subject_id: str
    message: str
    source_ids: tuple[str, ...]
    status: str = "failed"
    blocking: bool = True
    scope: str = "step"
    waivable: bool = False


@dataclass(frozen=True)
class WorkflowRuleReport:
    findings: list[WorkflowRuleFinding] = field(default_factory=list)
    normalized: dict[str, Any] = field(default_factory=dict)

    @property
    def errors(self) -> list[str]:
        return [
            finding.message
            for finding in self.findings
            if finding.status == "failed" and finding.blocking
        ]


def validate_register_step_rules(
    *,
    progress: dict[str, Any],
    step_id: str | None,
    step_kind: str | None,
    tdd_policy: str | None,
    waiver_reason: str | None,
    depends_on: list[str] | None,
    covers: list[str] | None,
    catalog: dict[str, list[str]] | None,
    catalog_source: str,
    allow_completed_dependencies: bool = True,
    include_completed_dependency_findings: bool = False,
) -> WorkflowRuleReport:
    subject_id = step_id or "planned-step"
    findings: list[WorkflowRuleFinding] = []
    normalized: dict[str, Any] = {
        "effective_tdd_policy": None,
        "normalized_covers": [],
    }
    if not step_id:
        findings.append(
            _finding(
                family="runtime_validity",
                subject_id=subject_id,
                message="step id is required for register-step",
                source_ids=("memory.progress",),
            )
        )
        return WorkflowRuleReport(findings=findings, normalized=normalized)

    planned_steps = [item for item in progress.get("plannedSteps", []) if isinstance(item, str)]
    completed_steps = {item for item in progress.get("completedSteps", []) if isinstance(item, str)}
    dependencies = [item for item in (depends_on or []) if isinstance(item, str)]

    if not STEP_ID_PATTERN.match(step_id):
        findings.append(
            _finding(
                family="runtime_validity",
                subject_id=subject_id,
                message="candidate step id must match step-XX-kebab-case",
                source_ids=("memory.progress",),
            )
        )
    if step_id in planned_steps:
        findings.append(
            _finding(
                family="runtime_validity",
                subject_id=subject_id,
                message="candidate step id already exists in plannedSteps",
                source_ids=("memory.progress",),
            )
        )
    if len(set(dependencies)) != len(dependencies):
        findings.append(
            _finding(
                family="dependency_readiness",
                subject_id=subject_id,
                message="candidate dependencies must be unique",
                source_ids=("memory.progress",),
            )
        )
    if step_id in dependencies:
        findings.append(
            _finding(
                family="dependency_readiness",
                subject_id=subject_id,
                message="candidate step cannot depend on itself",
                source_ids=("memory.progress",),
            )
        )
    for dependency in dependencies:
        if dependency not in planned_steps:
            findings.append(
                _finding(
                    family="dependency_readiness",
                    subject_id=subject_id,
                    message=f"dependency '{dependency}' is not present in plannedSteps",
                    source_ids=("memory.progress",),
                )
            )
        elif dependency in completed_steps:
            if allow_completed_dependencies:
                if include_completed_dependency_findings:
                    findings.append(
                        _finding(
                            family="dependency_readiness",
                            subject_id=subject_id,
                            message=f"dependency '{dependency}' is already completed",
                            source_ids=("memory.progress",),
                            status="passed",
                            blocking=False,
                        )
                    )
            else:
                findings.append(
                    _finding(
                        family="dependency_readiness",
                        subject_id=subject_id,
                        message=(
                            f"dependency '{dependency}' is already completed and not allowed by current policy"
                        ),
                        source_ids=("memory.progress",),
                    )
                )

    if step_kind not in {"code", "non-code"}:
        findings.append(
            _finding(
                family="runtime_validity",
                subject_id=subject_id,
                message="step kind must be one of: code, non-code",
                source_ids=("memory.progress",),
            )
        )
        return WorkflowRuleReport(findings=findings, normalized=normalized)

    effective_tdd_policy = _effective_tdd_policy(
        step_kind=step_kind,
        tdd_policy=tdd_policy,
        waiver_reason=waiver_reason,
    )
    normalized["effective_tdd_policy"] = effective_tdd_policy

    if effective_tdd_policy not in {"required", "waived", "not-applicable"}:
        findings.append(
            _finding(
                family="runtime_validity",
                subject_id=subject_id,
                message="tdd policy must be one of: required, waived, not-applicable",
                source_ids=("memory.progress",),
            )
        )
        return WorkflowRuleReport(findings=findings, normalized=normalized)

    if step_kind == "code" and effective_tdd_policy != "required":
        findings.append(
            _finding(
                family="runtime_validity",
                subject_id=subject_id,
                message="code steps must use the required TDD policy",
                source_ids=("memory.progress",),
            )
        )
    if step_kind == "non-code" and effective_tdd_policy == "required":
        findings.append(
            _finding(
                family="runtime_validity",
                subject_id=subject_id,
                message="non-code steps cannot use the required TDD policy",
                source_ids=("memory.progress",),
            )
        )
    if effective_tdd_policy == "waived" and not waiver_reason:
        findings.append(
            _finding(
                family="runtime_validity",
                subject_id=subject_id,
                message="waiver reason is required when TDD policy is waived",
                source_ids=("memory.progress",),
            )
        )
    if effective_tdd_policy != "waived" and waiver_reason is not None:
        findings.append(
            _finding(
                family="runtime_validity",
                subject_id=subject_id,
                message="waiver reason is only allowed when TDD policy is waived",
                source_ids=("memory.progress",),
            )
        )

    normalized_covers = [_normalize_function_label(item) for item in (covers or [])]
    normalized_covers = [item for item in normalized_covers if item]
    normalized["normalized_covers"] = normalized_covers
    if step_kind == "code" and not normalized_covers:
        findings.append(
            _finding(
                family="runtime_validity",
                subject_id=subject_id,
                message="code steps must declare at least one covered function",
                source_ids=("memory.progress",),
            )
        )

    catalog = catalog or {}
    known_functions = {item for items in catalog.values() for item in items}
    if not known_functions and normalized_covers:
        findings.append(
            _finding(
                family="runtime_validity",
                subject_id=subject_id,
                message=f"no functions catalog found in {catalog_source} for the target stage",
                source_ids=(catalog_source,),
            )
        )

    unknown = [item for item in normalized_covers if item not in known_functions]
    if unknown:
        choices = _known_function_samples(catalog)
        suggestion = f" Known labels from {catalog_source}: {choices}" if choices else ""
        findings.append(
            _finding(
                family="runtime_validity",
                subject_id=subject_id,
                message=f"unknown covered functions in {catalog_source}: {', '.join(unknown)}.{suggestion}",
                source_ids=(catalog_source,),
            )
        )

    return WorkflowRuleReport(findings=findings, normalized=normalized)


def validate_start_step_rules(
    *,
    progress: dict[str, Any],
    step_id: str | None,
    include_dependency_pass_finding: bool = False,
) -> WorkflowRuleReport:
    subject_id = step_id or "step"
    findings: list[WorkflowRuleFinding] = []
    if step_id is None:
        findings.append(
            _finding(
                family="runtime_validity",
                subject_id=subject_id,
                message="no executable implementation step found",
                source_ids=("memory.progress",),
            )
        )
        return WorkflowRuleReport(findings=findings, normalized={"selected_step": None})

    findings.extend(
        _validate_selected_step_state(
            progress=progress,
            step_id=step_id,
            require_dependencies=True,
            include_dependency_pass_finding=include_dependency_pass_finding,
        )
    )
    return WorkflowRuleReport(findings=findings, normalized={"selected_step": step_id})


def validate_checkpoint_step_rules(
    *,
    progress: dict[str, Any],
    step_id: str | None,
    summary: str | None,
    tdd_phase: str | None,
    red_evidence: list[str] | None,
    green_evidence: list[str] | None,
    refactor_note: str | None,
) -> WorkflowRuleReport:
    subject_id = step_id or "step"
    normalized_summary = (summary or "").strip()
    normalized_phase = (tdd_phase or "").strip().lower() or None
    normalized_red = normalize_text_list(red_evidence)
    normalized_green = normalize_text_list(green_evidence)
    normalized_refactor_note = (refactor_note or "").strip() or None
    normalized = {
        "selected_step": step_id,
        "summary": normalized_summary,
        "tdd_phase": normalized_phase,
        "red_evidence": normalized_red,
        "green_evidence": normalized_green,
        "refactor_note": normalized_refactor_note,
        "effective_tdd_policy": None,
        "allowed_phases": [],
    }
    findings: list[WorkflowRuleFinding] = []

    if step_id is None:
        findings.append(
            _finding(
                family="runtime_validity",
                subject_id=subject_id,
                message="step_id is required when there is no current implementation step",
                source_ids=("memory.progress", "memory.active_session"),
            )
        )
        return WorkflowRuleReport(findings=findings, normalized=normalized)

    findings.extend(
        _validate_selected_step_state(
            progress=progress,
            step_id=step_id,
            require_dependencies=False,
            include_dependency_pass_finding=False,
        )
    )
    metadata = progress.get("stepMetadata", {}).get(step_id, {})
    tdd_policy = metadata.get("tddPolicy")
    normalized["effective_tdd_policy"] = tdd_policy
    allowed_phases = (
        {"waived"}
        if tdd_policy in {"waived", "not-applicable"}
        else {"not_started", "red", "green", "refactor"}
    )
    normalized["allowed_phases"] = sorted(allowed_phases)

    if not any(
        [
            normalized_summary,
            normalized_phase,
            normalized_red,
            normalized_green,
            normalized_refactor_note,
        ]
    ):
        findings.append(
            _finding(
                family="runtime_validity",
                subject_id=subject_id,
                message="checkpoint must include summary, tdd phase, evidence, or refactor note",
                source_ids=("memory.progress",),
            )
        )
    if normalized_phase and normalized_phase not in allowed_phases:
        findings.append(
            _finding(
                family="runtime_validity",
                subject_id=subject_id,
                message="tdd phase must be one of: " + ", ".join(sorted(allowed_phases)),
                source_ids=("memory.progress",),
            )
        )

    return WorkflowRuleReport(findings=findings, normalized=normalized)


def validate_complete_step_rules(
    *,
    progress: dict[str, Any],
    step_id: str | None,
    summary: str | None,
    red_evidence: list[str] | None,
    green_evidence: list[str] | None,
    refactor_note: str | None,
    include_dependency_pass_finding: bool = False,
) -> WorkflowRuleReport:
    subject_id = step_id or "step"
    normalized_summary = (summary or "").strip()
    normalized_red = normalize_text_list(red_evidence)
    normalized_green = normalize_text_list(green_evidence)
    normalized_refactor_note = (refactor_note or "").strip() or None
    normalized = {
        "selected_step": step_id,
        "summary": normalized_summary,
        "red_evidence": normalized_red,
        "green_evidence": normalized_green,
        "refactor_note": normalized_refactor_note,
        "combined_red_evidence": [],
        "combined_green_evidence": [],
        "effective_refactor_note": None,
        "effective_tdd_policy": None,
        "effective_tdd_phase": None,
    }
    findings: list[WorkflowRuleFinding] = []

    if step_id is None:
        findings.append(
            _finding(
                family="runtime_validity",
                subject_id=subject_id,
                message="step_id is required when there is no current implementation step",
                source_ids=("memory.progress", "memory.active_session"),
            )
        )
        return WorkflowRuleReport(findings=findings, normalized=normalized)

    findings.extend(
        _validate_selected_step_state(
            progress=progress,
            step_id=step_id,
            require_dependencies=True,
            include_dependency_pass_finding=include_dependency_pass_finding,
        )
    )
    if not normalized_summary:
        findings.append(
            _finding(
                family="runtime_validity",
                subject_id=subject_id,
                message="summary must not be empty",
                source_ids=("memory.progress",),
            )
        )

    metadata = progress.get("stepMetadata", {}).get(step_id, {})
    status_info = progress.get("stepStatus", {}).get(step_id, {})
    combined_red = append_unique(status_info.get("redEvidence", []), normalized_red)
    combined_green = append_unique(status_info.get("greenEvidence", []), normalized_green)
    effective_refactor_note = normalized_refactor_note or status_info.get("refactorNote")
    effective_tdd_policy = metadata.get("tddPolicy")
    normalized["combined_red_evidence"] = combined_red
    normalized["combined_green_evidence"] = combined_green
    normalized["effective_refactor_note"] = effective_refactor_note
    normalized["effective_tdd_policy"] = effective_tdd_policy
    normalized["effective_tdd_phase"] = (
        "completed" if effective_tdd_policy == "required" else "waived"
    )

    if effective_tdd_policy == "required":
        if not combined_red:
            findings.append(
                _finding(
                    family="runtime_validity",
                    subject_id=subject_id,
                    message=f"completed code step '{step_id}' must record redEvidence",
                    source_ids=("memory.progress",),
                )
            )
        if not combined_green:
            findings.append(
                _finding(
                    family="runtime_validity",
                    subject_id=subject_id,
                    message=f"completed code step '{step_id}' must record greenEvidence",
                    source_ids=("memory.progress",),
                )
            )
        if not isinstance(effective_refactor_note, str) or not effective_refactor_note.strip():
            findings.append(
                _finding(
                    family="runtime_validity",
                    subject_id=subject_id,
                    message=f"completed code step '{step_id}' must record refactorNote",
                    source_ids=("memory.progress",),
                )
            )

    return WorkflowRuleReport(findings=findings, normalized=normalized)


def _effective_tdd_policy(
    *,
    step_kind: str | None,
    tdd_policy: str | None,
    waiver_reason: str | None,
) -> str | None:
    if tdd_policy is not None:
        return tdd_policy
    if step_kind == "code":
        return "required"
    if waiver_reason:
        return "waived"
    return "not-applicable"


def _validate_selected_step_state(
    *,
    progress: dict[str, Any],
    step_id: str,
    require_dependencies: bool,
    include_dependency_pass_finding: bool,
) -> list[WorkflowRuleFinding]:
    findings: list[WorkflowRuleFinding] = []
    planned_steps = progress.get("plannedSteps", [])
    completed_steps = set(progress.get("completedSteps", []))
    if step_id not in planned_steps:
        findings.append(
            _finding(
                family="runtime_validity",
                subject_id=step_id,
                message=f"step '{step_id}' is not present in plannedSteps",
                source_ids=("memory.progress",),
            )
        )
        return findings
    if step_id in completed_steps:
        findings.append(
            _finding(
                family="runtime_validity",
                subject_id=step_id,
                message=f"step '{step_id}' is already completed",
                source_ids=("memory.progress",),
            )
        )
    if require_dependencies:
        dependencies = step_dependencies(progress, step_id)
        missing_dependencies = [dependency for dependency in dependencies if dependency not in completed_steps]
        if missing_dependencies:
            findings.append(
                _finding(
                    family="dependency_readiness",
                    subject_id=step_id,
                    message=f"step '{step_id}' has incomplete dependencies: {', '.join(dependencies)}",
                    source_ids=("memory.progress",),
                )
            )
        elif include_dependency_pass_finding:
            findings.append(
                _finding(
                    family="dependency_readiness",
                    subject_id=step_id,
                    message="all step dependencies are satisfied",
                    source_ids=("memory.progress",),
                    status="passed",
                    blocking=False,
                )
            )
    return findings


def _known_function_samples(catalog: dict[str, list[str]], limit: int = 5) -> str:
    values: list[str] = []
    for priority in ("p1", "p2", "p3"):
        for item in catalog.get(priority, []):
            if item not in values:
                values.append(item)
            if len(values) >= limit:
                return ", ".join(values)
    return ", ".join(values)


def _finding(
    *,
    family: str,
    subject_id: str,
    message: str,
    source_ids: tuple[str, ...],
    status: str = "failed",
    blocking: bool = True,
) -> WorkflowRuleFinding:
    return WorkflowRuleFinding(
        family=family,
        subject_id=subject_id,
        message=message,
        source_ids=source_ids,
        status=status,
        blocking=blocking,
    )
