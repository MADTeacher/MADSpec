from __future__ import annotations

from pathlib import Path
from typing import Any

from ..domain.models import PolicyValidationResult
from ..infrastructure.normalization import policy_matches_scope
from ..infrastructure.queries import effective_policies
from ..infrastructure.repository import load_policy_state


def _normalize_stage(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


def _normalize_operation(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


def load_branch_progress(project_path: Path, branch_name: str) -> dict[str, Any]:
    from madspec_cli.memory.shared.storage import _default_progress_state, get_memory_paths, read_json

    paths = get_memory_paths(project_path, branch_name)
    progress = read_json(paths.progress, _default_progress_state())
    if not isinstance(progress, dict):
        return _default_progress_state()
    return progress


def build_step_payload(
    progress: dict[str, Any],
    *,
    step_id: str | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    overrides = overrides or {}
    step_metadata = progress.get("stepMetadata", {})
    step_status = progress.get("stepStatus", {})
    resolved_step_id = step_id or overrides.get("step_id")
    metadata = dict(step_metadata.get(resolved_step_id, {})) if resolved_step_id else {}
    status_info = dict(step_status.get(resolved_step_id, {})) if resolved_step_id else {}

    payload = {
        "step_id": resolved_step_id,
        "step_kind": overrides.get("step_kind") or metadata.get("kind"),
        "tdd_policy": overrides.get("tdd_policy") or metadata.get("tddPolicy"),
        "waiver_reason": overrides.get("waiver_reason") if "waiver_reason" in overrides else metadata.get("waiverReason"),
        "tdd_phase": overrides.get("tdd_phase") or status_info.get("tddPhase"),
        "status": overrides.get("status") or status_info.get("status"),
        "red_evidence": overrides.get("red_evidence") if "red_evidence" in overrides else status_info.get("redEvidence", []),
        "green_evidence": overrides.get("green_evidence") if "green_evidence" in overrides else status_info.get("greenEvidence", []),
        "refactor_note": overrides.get("refactor_note") if "refactor_note" in overrides else status_info.get("refactorNote"),
    }
    return payload


def _step_message(prefix: str, step_id: str | None, generic: str) -> str:
    return f"{prefix} '{step_id}' {generic}" if step_id else generic


def evaluate_policy(
    policy: dict[str, Any],
    *,
    stage: str | None,
    operation: str | None,
    step_payload: dict[str, Any] | None = None,
) -> PolicyValidationResult | None:
    step_payload = step_payload or {}
    step_id = step_payload.get("step_id")
    step_kind = step_payload.get("step_kind")
    if not policy_matches_scope(policy, stage=stage, operation=operation, step_kind=step_kind):
        return None

    rule = policy.get("rule")
    if not isinstance(rule, dict):
        return PolicyValidationResult(
            policy_id=policy["policyId"],
            title=policy["title"],
            enforcement=policy["enforcement"],
            status="advisory",
            message=policy.get("description") or f"policy '{policy['policyId']}' applies to the current stage",
            stage=stage,
            operation=operation,
            details={"policyKind": policy.get("kind")},
        )

    rule_type = rule.get("ruleType")
    tdd_policy = step_payload.get("tdd_policy")
    tdd_phase = step_payload.get("tdd_phase")
    status = step_payload.get("status")
    red_evidence = step_payload.get("red_evidence") or []
    green_evidence = step_payload.get("green_evidence") or []
    refactor_note = step_payload.get("refactor_note")

    if rule_type == "code_steps_require_required_tdd":
        if step_kind == "code" and tdd_policy != "required":
            return PolicyValidationResult(
                policy_id=policy["policyId"],
                title=policy["title"],
                enforcement=policy["enforcement"],
                status="violated",
                message=_step_message("code step", step_id, "must use tddPolicy='required'"),
                stage=stage,
                operation=operation,
                details={"stepId": step_id, "actualTddPolicy": tdd_policy},
            )
        return PolicyValidationResult(
            policy_id=policy["policyId"],
            title=policy["title"],
            enforcement=policy["enforcement"],
            status="passed",
            message=policy["title"],
            stage=stage,
            operation=operation,
            details={"stepId": step_id},
        )

    if rule_type == "non_code_steps_forbid_required_tdd":
        if step_kind == "non-code" and tdd_policy == "required":
            return PolicyValidationResult(
                policy_id=policy["policyId"],
                title=policy["title"],
                enforcement=policy["enforcement"],
                status="violated",
                message=_step_message("non-code step", step_id, "cannot use tddPolicy='required'"),
                stage=stage,
                operation=operation,
                details={"stepId": step_id, "actualTddPolicy": tdd_policy},
            )
        return PolicyValidationResult(
            policy_id=policy["policyId"],
            title=policy["title"],
            enforcement=policy["enforcement"],
            status="passed",
            message=policy["title"],
            stage=stage,
            operation=operation,
            details={"stepId": step_id},
        )

    if rule_type == "non_required_tdd_requires_waived_phase":
        if tdd_policy in {"waived", "not-applicable"} and tdd_phase != "waived":
            return PolicyValidationResult(
                policy_id=policy["policyId"],
                title=policy["title"],
                enforcement=policy["enforcement"],
                status="violated",
                message=_step_message("step", step_id, "must use tddPhase='waived' for non-required TDD policy"),
                stage=stage,
                operation=operation,
                details={"stepId": step_id, "actualTddPhase": tdd_phase},
            )
        return PolicyValidationResult(
            policy_id=policy["policyId"],
            title=policy["title"],
            enforcement=policy["enforcement"],
            status="passed",
            message=policy["title"],
            stage=stage,
            operation=operation,
            details={"stepId": step_id},
        )

    if rule_type == "completed_code_steps_require_tdd_evidence":
        if step_kind == "code" and tdd_policy == "required" and status == "completed":
            if tdd_phase != "completed":
                return PolicyValidationResult(
                    policy_id=policy["policyId"],
                    title=policy["title"],
                    enforcement=policy["enforcement"],
                    status="violated",
                    message=_step_message("completed code step", step_id, "must have tddPhase='completed'"),
                    stage=stage,
                    operation=operation,
                    details={"stepId": step_id},
                )
            if not red_evidence:
                return PolicyValidationResult(
                    policy_id=policy["policyId"],
                    title=policy["title"],
                    enforcement=policy["enforcement"],
                    status="violated",
                    message=_step_message("completed code step", step_id, "must record redEvidence"),
                    stage=stage,
                    operation=operation,
                    details={"stepId": step_id},
                )
            if not green_evidence:
                return PolicyValidationResult(
                    policy_id=policy["policyId"],
                    title=policy["title"],
                    enforcement=policy["enforcement"],
                    status="violated",
                    message=_step_message("completed code step", step_id, "must record greenEvidence"),
                    stage=stage,
                    operation=operation,
                    details={"stepId": step_id},
                )
            if not isinstance(refactor_note, str) or not refactor_note.strip():
                return PolicyValidationResult(
                    policy_id=policy["policyId"],
                    title=policy["title"],
                    enforcement=policy["enforcement"],
                    status="violated",
                    message=_step_message("completed code step", step_id, "must record refactorNote"),
                    stage=stage,
                    operation=operation,
                    details={"stepId": step_id},
                )
        return PolicyValidationResult(
            policy_id=policy["policyId"],
            title=policy["title"],
            enforcement=policy["enforcement"],
            status="passed",
            message=policy["title"],
            stage=stage,
            operation=operation,
            details={"stepId": step_id},
        )

    return PolicyValidationResult(
        policy_id=policy["policyId"],
        title=policy["title"],
        enforcement=policy["enforcement"],
        status="advisory",
        message=policy.get("description") or policy["title"],
        stage=stage,
        operation=operation,
        details={"policyKind": policy.get("kind")},
    )


def evaluate_branch_policies(
    project_path: Path,
    branch_name: str,
    *,
    stage: str | None,
    operation: str | None,
    step_id: str | None = None,
    overrides: dict[str, Any] | None = None,
    include_system_policies: bool = True,
    policy_id: str | None = None,
    create_policy_if_missing: bool = True,
) -> dict[str, Any]:
    normalized_stage = _normalize_stage(stage)
    normalized_operation = _normalize_operation(operation)
    progress = load_branch_progress(project_path, branch_name)
    policies = effective_policies(
        project_path,
        stage=normalized_stage,
        operation=normalized_operation,
        step_kind=(overrides or {}).get("step_kind"),
        create_if_missing=create_policy_if_missing,
    )
    if not include_system_policies:
        policies = [item for item in policies if item.get("source") != "system"]
    if policy_id:
        policies = [item for item in policies if item.get("policyId") == policy_id]

    results: list[PolicyValidationResult] = []
    if step_id or overrides:
        payload = build_step_payload(progress, step_id=step_id, overrides=overrides)
        for policy in policies:
            result = evaluate_policy(policy, stage=normalized_stage, operation=normalized_operation, step_payload=payload)
            if result is not None:
                results.append(result)
    else:
        step_ids = progress.get("plannedSteps", []) or [None]
        if not step_ids:
            step_ids = [None]
        for policy in policies:
            if policy.get("kind") == "guideline":
                result = evaluate_policy(policy, stage=normalized_stage, operation=normalized_operation, step_payload={})
                if result is not None:
                    results.append(result)
                continue
            matched = False
            for current_step_id in step_ids:
                payload = build_step_payload(progress, step_id=current_step_id)
                result = evaluate_policy(policy, stage=normalized_stage, operation=normalized_operation, step_payload=payload)
                if result is None:
                    continue
                matched = True
                if result.status == "violated":
                    results.append(result)
            if not matched:
                result = evaluate_policy(policy, stage=normalized_stage, operation=normalized_operation, step_payload={})
                if result is not None and result.status != "violated":
                    results.append(result)

    unique_results: list[PolicyValidationResult] = []
    seen: set[tuple[str, str, str | None]] = set()
    for item in results:
        marker = (item.policy_id, item.message, item.details.get("stepId"))
        if marker in seen:
            continue
        seen.add(marker)
        unique_results.append(item)

    violations = [item.to_payload() for item in unique_results if item.status == "violated" and item.enforcement == "required"]
    advisories = [item.to_payload() for item in unique_results if item.enforcement == "advisory"]
    confirmations = [item.to_payload() for item in unique_results if item.status == "passed"]
    return {
        "policies": [
            item
            for item in load_policy_state(project_path, create_if_missing=create_policy_if_missing).get("policies", [])
            if any(item["policyId"] == result.policy_id for result in unique_results)
        ],
        "violations": violations,
        "advisories": advisories,
        "confirmations": confirmations,
    }
