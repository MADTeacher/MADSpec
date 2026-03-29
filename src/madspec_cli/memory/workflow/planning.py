from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..domain.workflow_rules import validate_register_step_rules
from ..domain.progress import explain_next_executable_step

if TYPE_CHECKING:
    from madspec_cli.shared.kernel.ports import BranchPolicyEvaluator
from ..shared.progress_utils import (
    _compute_progress_metrics,
    extract_function_catalog,
)
from ..shared.records import make_record
from ..shared.storage import (
    _default_progress_state,
    _default_step_coverage,
    _default_step_metadata,
    _default_step_status,
    ensure_memory_layout,
    get_memory_paths,
    normalize_runtime_progress,
    normalize_progress_state,
    now_iso,
    read_json,
)
from ..shared.system_store.canonical_state import (
    CanonicalBranchState,
    build_runtime_snapshot_specs,
    load_canonical_branch_state,
    tag_records_for_stream,
)
from ..shared.system_store.constants import LEASE_TTL_SECONDS, SYSTEM_SESSION_KEY
from ..shared.system_store.leases import build_plan_catalog_lease
from ..shared.system_store.runtime_mutations import RuntimeMutationPlan, commit_runtime_mutation
from ..shared.system_store.sessions import read_runtime_session_payload
from ..stages.plan.state import load_plan_state, save_plan_state, upsert_step_catalog_entry
from ..stages.feature_plan.state import load_feature_plan_state, save_feature_plan_state


@dataclass(frozen=True)
class NextStepDecision:
    branch: str
    stage: str
    candidate_step: str | None
    dependencies: list[str]
    accepted: bool
    reason: str
    errors: list[str]
    selected_step: str | None = None
    executable_steps: list[str] | None = None

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "branch": self.branch,
            "stage": self.stage,
            "candidate_step": self.candidate_step,
            "dependencies": self.dependencies,
            "accepted": self.accepted,
            "errors": self.errors,
            "reason": self.reason,
        }
        if self.selected_step is not None:
            payload["selected_step"] = self.selected_step
        if self.executable_steps is not None:
            payload["executable_steps"] = self.executable_steps
        return payload


@dataclass(frozen=True)
class RegisterStepResult:
    accepted: bool
    step_id: str
    errors: list[str]
    depends_on: list[str] | None = None
    covers: dict[str, list[str]] | None = None
    step_metadata: dict[str, Any] | None = None
    progress_metrics: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "accepted": self.accepted,
            "step_id": self.step_id,
        }
        if self.errors:
            payload["errors"] = self.errors
        if self.depends_on is not None:
            payload["depends_on"] = self.depends_on
        if self.covers is not None:
            payload["covers"] = self.covers
        if self.step_metadata is not None:
            payload["stepMetadata"] = self.step_metadata
        if self.progress_metrics is not None:
            payload["progressMetrics"] = self.progress_metrics
        return payload


def _catalog_source_name(stage: str) -> str:
    return "feature.init.json" if "feature." in stage.lower() else "mvp.concept.json"


def determine_next_step(
    project_path: Path,
    branch_name: str,
    stage: str,
    *,
    candidate_step: str | None = None,
    candidate_dependencies: list[str] | None = None,
    allow_completed_dependencies: bool = True,
    _evaluate_branch_policies: BranchPolicyEvaluator | None = None,
) -> dict[str, Any]:
    progress = load_canonical_branch_state(project_path, branch_name).progress
    step_dependencies = progress.get("planningMetadata", {}).get("stepDependencies", {})

    if candidate_step:
        normalized_dependencies = candidate_dependencies or []
        report = validate_register_step_rules(
            progress=progress,
            step_id=candidate_step,
            step_kind="non-code",
            tdd_policy="not-applicable",
            waiver_reason=None,
            depends_on=normalized_dependencies,
            covers=[],
            catalog={},
            catalog_source="mvp.concept.json",
            allow_completed_dependencies=allow_completed_dependencies,
        )
        errors = list(report.errors)

        if _evaluate_branch_policies is None:
            from madspec_cli.features.policy.application.common import evaluate_branch_policies
            _evaluate_branch_policies = evaluate_branch_policies
        policy_payload = _evaluate_branch_policies(
            project_path,
            branch_name,
            stage=stage,
            operation="determine-next-step",
            step_id=candidate_step,
            overrides={},
            include_system_policies=False,
        )
        errors.extend(item["message"] for item in policy_payload["violations"])

        decision = NextStepDecision(
            branch=branch_name,
            stage=stage,
            candidate_step=candidate_step,
            dependencies=normalized_dependencies,
            accepted=not errors,
            errors=errors,
            reason="validated candidate" if not errors else "candidate rejected",
        )
        return decision.to_payload()

    analysis = explain_next_executable_step(progress)
    executable_steps = analysis["executable_steps"]
    selected_step = analysis["selected_step"]
    reason = analysis["reason"]

    decision = NextStepDecision(
        branch=branch_name,
        stage=stage,
        candidate_step=None,
        dependencies=step_dependencies.get(selected_step, []) if selected_step else [],
        accepted=selected_step is not None,
        selected_step=selected_step,
        errors=[] if selected_step else ["no executable step available"],
        reason=reason,
        executable_steps=executable_steps,
    )
    return decision.to_payload()


def _build_register_step_plan(
    project_path: Path,
    branch_name: str,
    stage: str,
    *,
    session_key: str,
    step_id: str,
    normalized_covers: list[str],
    known_functions: dict[str, str],
    step_kind: str,
    effective_tdd_policy: str,
    waiver_reason: str | None,
    depends_on: list[str],
    summary: str | None,
    title: str | None,
    related_artifacts: list[str],
    size: str | None,
    complexity: str | None,
    canonical: CanonicalBranchState,
) -> RuntimeMutationPlan:
    paths = get_memory_paths(project_path, branch_name)
    progress = canonical.progress or _default_progress_state()
    if isinstance(progress, dict):
        progress, _ = normalize_progress_state(progress)

    planned_steps = progress.setdefault("plannedSteps", [])
    if step_id not in planned_steps:
        planned_steps.append(step_id)

    tdd_phase = "waived" if effective_tdd_policy in {"waived", "not-applicable"} else "not_started"
    progress.setdefault("stepStatus", {})[step_id] = _default_step_status(tdd_phase=tdd_phase)
    progress.setdefault("stepMetadata", {})[step_id] = _default_step_metadata(
        kind=step_kind,
        tdd_policy=effective_tdd_policy,
        waiver_reason=waiver_reason,
    )

    step_dependencies = progress.setdefault("planningMetadata", {}).setdefault(
        "stepDependencies", {}
    )
    step_dependencies[step_id] = list(depends_on)

    covers_functions = progress.setdefault("coversFunctions", {})
    covers_functions[step_id] = _default_step_coverage()
    for item in normalized_covers:
        covers_functions[step_id][known_functions[item]].append(item)

    progress, _ = normalize_runtime_progress(
        project_path,
        branch_name,
        progress,
    )

    if "feature." in stage.lower():
        plan_state = canonical.snapshots.get("feature.plan") or load_feature_plan_state(paths.feature_plan_state)
    else:
        plan_state = canonical.snapshots.get("mvp.plan") or load_plan_state(paths.plan_state)
    plan_state = upsert_step_catalog_entry(
        plan_state,
        step_id=step_id,
        title=title,
        summary=summary,
        step_kind=step_kind,
        tdd_policy=effective_tdd_policy,
        waiver_reason=waiver_reason,
        covers=covers_functions[step_id],
        depends_on=list(depends_on),
        related_artifacts=related_artifacts,
        size=size,
        complexity=complexity,
    )
    active_session = read_runtime_session_payload(
        project_path,
        branch_name=branch_name,
        session_key=session_key,
    )
    active_session["stage"] = stage
    active_session["current_step"] = step_id
    active_session["last_checkpoint_at"] = now_iso()
    active_session["updated_at"] = active_session["last_checkpoint_at"]

    snapshot_payloads = {
        "progress": progress,
        "feature.plan" if "feature." in stage.lower() else "mvp.plan": plan_state,
    }
    record_payloads = tag_records_for_stream(
        [
            make_record(
                branch_name,
                stage,
                "memory.register-step",
                summary or f"Registered planned step {step_id}",
                step_id=step_id,
                status="validated",
                evidence=[str(paths.progress.relative_to(project_path))],
                semantic_kind="decision",
                record_type="planned_step",
                metadata={
                    "depends_on": list(depends_on),
                    "covers": list(normalized_covers),
                    "step_kind": step_kind,
                    "tdd_policy": effective_tdd_policy,
                    "waiver_reason": waiver_reason,
                    "title": title,
                    "related_artifacts": related_artifacts,
                    "size": size,
                    "complexity": complexity,
                },
            )
        ],
        "decision_log",
    )
    return RuntimeMutationPlan(
        stage_snapshots=build_runtime_snapshot_specs(project_path, branch_name, snapshot_payloads),
        sessions=[{"session_key": session_key, "payload": active_session}],
        records=record_payloads,
        response_payload={
            "depends_on": list(depends_on),
            "covers": covers_functions[step_id],
            "stepMetadata": progress["stepMetadata"][step_id],
            "progressMetrics": progress["planningMetadata"]["progressMetrics"],
        },
    )


def _detect_register_step_conflict(
    base_state: CanonicalBranchState,
    current_state: CanonicalBranchState,
    *,
    step_id: str,
) -> dict[str, Any] | None:
    base_planned = set(base_state.progress.get("plannedSteps", []))
    current_planned = set(current_state.progress.get("plannedSteps", []))
    if step_id in current_planned and step_id not in base_planned:
        return {
            "kind": "progress_conflict",
            "scope": "plan-catalog",
            "step_id": step_id,
            "conflicting_fields": ["plannedSteps", "stepStatus", "stepMetadata", "coversFunctions"],
            "details": {"reason": "target step was registered by another writer"},
        }
    return None


def register_planned_step(
    project_path: Path,
    branch_name: str,
    stage: str,
    *,
    session_key: str = SYSTEM_SESSION_KEY,
    expected_revision: int | None = None,
    step_id: str,
    covers: list[str],
    step_kind: str,
    tdd_policy: str | None = None,
    waiver_reason: str | None = None,
    depends_on: list[str] | None = None,
    summary: str | None = None,
    title: str | None = None,
    related_artifacts: list[str] | None = None,
    size: str | None = None,
    complexity: str | None = None,
    _evaluate_branch_policies: BranchPolicyEvaluator | None = None,
) -> dict[str, Any]:
    ensure_memory_layout(project_path, branch_name, stage=stage)
    canonical = load_canonical_branch_state(project_path, branch_name)
    progress = canonical.progress
    if isinstance(progress, dict):
        progress, _ = normalize_progress_state(progress)
    decision = determine_next_step(
        project_path,
        branch_name,
        stage,
        candidate_step=step_id,
        candidate_dependencies=depends_on or [],
    )
    if not decision["accepted"]:
        return RegisterStepResult(
            accepted=False,
            step_id=step_id,
            errors=decision["errors"],
        ).to_payload()

    catalog = extract_function_catalog(project_path, branch_name, stage)
    catalog_source = _catalog_source_name(stage)
    rule_report = validate_register_step_rules(
        progress=progress,
        step_id=step_id,
        step_kind=step_kind,
        tdd_policy=tdd_policy,
        waiver_reason=waiver_reason,
        depends_on=depends_on,
        covers=covers,
        catalog=catalog,
        catalog_source=catalog_source,
    )
    if rule_report.errors:
        return RegisterStepResult(
            accepted=False,
            step_id=step_id,
            errors=rule_report.errors,
        ).to_payload()
    effective_tdd_policy = rule_report.normalized["effective_tdd_policy"]
    normalized_covers = rule_report.normalized["normalized_covers"]
    known_functions = {
        item: priority for priority, items in catalog.items() for item in items
    }

    if _evaluate_branch_policies is None:
        from madspec_cli.features.policy.application.common import evaluate_branch_policies
        _evaluate_branch_policies = evaluate_branch_policies
    policy_payload = _evaluate_branch_policies(
        project_path,
        branch_name,
        stage=stage,
        operation="register-step",
        step_id=step_id,
        overrides={
            "step_kind": step_kind,
            "tdd_policy": effective_tdd_policy,
            "waiver_reason": waiver_reason,
            "status": "planned",
        },
        include_system_policies=False,
    )
    if policy_payload["violations"]:
        return RegisterStepResult(
            accepted=False,
            step_id=step_id,
            errors=[item["message"] for item in policy_payload["violations"]],
        ).to_payload()

    projection_meta = commit_runtime_mutation(
        project_path,
        branch_name=branch_name,
        stage=stage,
        mutation_kind="register-step",
        scope="plan-catalog",
        session_key=session_key,
        expected_revision=expected_revision if expected_revision is not None else canonical.runtime_revision,
        base_state=canonical,
        plan_builder=lambda latest_state: _build_register_step_plan(
            project_path,
            branch_name,
            stage,
            session_key=session_key,
            step_id=step_id,
            normalized_covers=normalized_covers,
            known_functions=known_functions,
            step_kind=step_kind,
            effective_tdd_policy=effective_tdd_policy,
            waiver_reason=waiver_reason,
            depends_on=list(depends_on or []),
            summary=summary,
            title=title,
            related_artifacts=related_artifacts or [],
            size=size,
            complexity=complexity,
            canonical=latest_state,
        ),
        conflict_detector=lambda base, current: _detect_register_step_conflict(
            base,
            current,
            step_id=step_id,
        ),
        lease=build_plan_catalog_lease(
            branch_name=branch_name,
            mutation_kind="register-step",
            session_key=session_key,
            ttl_seconds=LEASE_TTL_SECONDS,
        ),
    )
    if not projection_meta.get("accepted", True):
        return projection_meta

    payload = RegisterStepResult(
        accepted=True,
        step_id=step_id,
        errors=[],
        depends_on=list(depends_on or []),
        covers=projection_meta.get("covers"),
        step_metadata=projection_meta.get("stepMetadata"),
        progress_metrics=projection_meta.get("progressMetrics"),
    ).to_payload()
    payload.update(projection_meta)
    return payload
