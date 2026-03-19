from __future__ import annotations

from pathlib import Path
from typing import Any

from madspec_cli.features.policy.application.common import evaluate_branch_policies

from .shared import build_gate


def collect_policy_gates(
    *,
    project_path: Path,
    branch_name: str,
    stage: str,
    operation: str,
    step_id: str | None,
    overrides: dict[str, Any],
) -> list[dict[str, Any]]:
    payload = evaluate_branch_policies(
        project_path,
        branch_name,
        stage=stage,
        operation=operation,
        step_id=step_id,
        overrides=overrides,
        include_system_policies=False,
    )
    results: list[dict[str, Any]] = []
    subject_id = step_id or stage

    for item in payload.get("violations", []):
        results.append(
            build_gate(
                family="policy_compliance",
                scope="step" if step_id else "stage",
                subject_id=subject_id,
                blocking=True,
                waivable=True,
                status="failed",
                message=item["message"],
                source_ids=[f"policy:{item['policyId']}"],
                stage=stage,
                operation=operation,
            )
        )
    for item in payload.get("advisories", []):
        results.append(
            build_gate(
                family="policy_compliance",
                scope="step" if step_id else "stage",
                subject_id=subject_id,
                blocking=False,
                waivable=True,
                status="warning",
                message=item["message"],
                source_ids=[f"policy:{item['policyId']}"],
                stage=stage,
                operation=operation,
            )
        )
    for item in payload.get("confirmations", []):
        results.append(
            build_gate(
                family="policy_compliance",
                scope="step" if step_id else "stage",
                subject_id=subject_id,
                blocking=item.get("enforcement") == "required",
                waivable=True,
                status="passed",
                message=item["message"],
                source_ids=[f"policy:{item['policyId']}"],
                stage=stage,
                operation=operation,
            )
        )
    return results
