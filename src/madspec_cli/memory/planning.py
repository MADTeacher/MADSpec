from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .records import STEP_ID_PATTERN, make_record
from .storage import (
    _default_active_session,
    _default_progress_state,
    _default_step_coverage,
    _default_step_metadata,
    _default_step_status,
    append_jsonl,
    get_memory_paths,
    normalize_progress_state,
    read_json,
    now_iso,
    write_json,
)


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


def _extract_mvp_functions(concept_path: Path) -> dict[str, list[str]]:
    priorities = {"p1": [], "p2": [], "p3": []}
    if not concept_path.exists():
        return priorities

    current_priority: str | None = None
    for raw_line in concept_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("### Приоритет 1"):
            current_priority = "p1"
            continue
        if line.startswith("### Приоритет 2"):
            current_priority = "p2"
            continue
        if line.startswith("### Приоритет 3"):
            current_priority = "p3"
            continue
        if not current_priority or not line.startswith("- "):
            continue
        value = line[2:].strip()
        if ":" in value:
            value = value.split(":", 1)[0].strip()
        value = _normalize_function_label(value)
        if value:
            priorities[current_priority].append(value)
    return priorities


def _extract_feature_functions(analysis_path: Path) -> dict[str, list[str]]:
    priorities = {"p1": [], "p2": [], "p3": []}
    if not analysis_path.exists():
        return priorities

    current_priority: str | None = None
    for raw_line in analysis_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("### P1"):
            current_priority = "p1"
            continue
        if line.startswith("### P2"):
            current_priority = "p2"
            continue
        if line.startswith("### P3"):
            current_priority = "p3"
            continue
        if not current_priority or not line.startswith("- **"):
            continue
        match = re.match(r"- \*\*([^*]+)\*\*(?::|$)", line)
        if match:
            priorities[current_priority].append(_normalize_function_label(match.group(1)))
    return priorities


def _normalize_function_label(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value).strip()
    while normalized.startswith("**") and normalized.endswith("**") and len(normalized) >= 4:
        normalized = normalized[2:-2].strip()
    return normalized


def _catalog_source_name(stage: str) -> str:
    return "project-analysis.md" if "feature." in stage.lower() else "concept.md"


def _known_function_samples(catalog: dict[str, list[str]], limit: int = 5) -> str:
    values: list[str] = []
    for priority in ("p1", "p2", "p3"):
        for item in catalog.get(priority, []):
            if item not in values:
                values.append(item)
            if len(values) >= limit:
                return ", ".join(values)
    return ", ".join(values)


def extract_function_catalog(project_path: Path, branch_name: str, stage: str) -> dict[str, list[str]]:
    branch_dir = get_memory_paths(project_path, branch_name).branch_dir
    stage_lower = stage.lower()
    if "feature." in stage_lower:
        return _extract_feature_functions(branch_dir / "project-analysis.md")
    return _extract_mvp_functions(branch_dir / "concept.md")


def _compute_progress_metrics(
    catalog: dict[str, list[str]],
    covers_functions: dict[str, dict[str, list[str]]],
) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    weights = {"p1": 0.5, "p2": 0.3, "p3": 0.2}
    overall = 0.0
    for priority in ("p1", "p2", "p3"):
        total = len(catalog.get(priority, []))
        covered_names: set[str] = set()
        for step_coverage in covers_functions.values():
            if not isinstance(step_coverage, dict):
                continue
            values = step_coverage.get(priority, [])
            if isinstance(values, list):
                covered_names.update(item for item in values if isinstance(item, str))
        covered = len(covered_names.intersection(set(catalog.get(priority, []))))
        percentage = int(round((covered / total) * 100)) if total else 0
        metrics[f"{priority}Coverage"] = {
            "covered": covered,
            "total": total,
            "percentage": percentage,
        }
        overall += percentage * weights[priority]
    metrics["overallProgress"] = int(round(overall))
    return metrics


def determine_next_step(
    project_path: Path,
    branch_name: str,
    stage: str,
    *,
    candidate_step: str | None = None,
    candidate_dependencies: list[str] | None = None,
    allow_completed_dependencies: bool = True,
) -> dict[str, Any]:
    paths = get_memory_paths(project_path, branch_name)
    progress = read_json(paths.progress, _default_progress_state())
    planned_steps = progress.get("plannedSteps", [])
    completed_steps = set(progress.get("completedSteps", []))
    step_status = progress.get("stepStatus", {})
    step_dependencies = progress.get("planningMetadata", {}).get("stepDependencies", {})
    stage_lower = stage.lower()

    def _step_ready(step_id: str) -> bool:
        return all(dependency in completed_steps for dependency in step_dependencies.get(step_id, []))

    if candidate_step:
        errors: list[str] = []
        normalized_dependencies = candidate_dependencies or []
        if not STEP_ID_PATTERN.match(candidate_step):
            errors.append("candidate step id must match step-XX-kebab-case")
        if candidate_step in planned_steps:
            errors.append("candidate step id already exists in plannedSteps")
        if len(set(normalized_dependencies)) != len(normalized_dependencies):
            errors.append("candidate dependencies must be unique")
        for dependency in normalized_dependencies:
            if dependency not in planned_steps:
                errors.append(f"dependency '{dependency}' is not present in plannedSteps")
            elif not allow_completed_dependencies and dependency in completed_steps:
                errors.append(
                    f"dependency '{dependency}' is already completed and not allowed by current policy"
                )
        if candidate_step in normalized_dependencies:
            errors.append("candidate step cannot depend on itself")

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

    executable_steps = []
    for step_id in planned_steps:
        status = step_status.get(step_id, {}).get("status")
        if step_id in completed_steps or status == "completed":
            continue
        if _step_ready(step_id):
            executable_steps.append(step_id)

    selected_step = executable_steps[0] if executable_steps else None
    reason = (
        "next executable planned step for reference"
        if "plan" in stage_lower and selected_step
        else "next executable implementation step"
        if selected_step
        else "no executable planned step found"
        if "plan" in stage_lower
        else "no executable implementation step found"
    )

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


def register_planned_step(
    project_path: Path,
    branch_name: str,
    stage: str,
    *,
    step_id: str,
    covers: list[str],
    step_kind: str,
    tdd_policy: str | None = None,
    waiver_reason: str | None = None,
    depends_on: list[str] | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    paths = get_memory_paths(project_path, branch_name)
    progress = read_json(paths.progress, _default_progress_state())
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

    if step_kind not in {"code", "non-code"}:
        return RegisterStepResult(
            accepted=False,
            step_id=step_id,
            errors=["step kind must be one of: code, non-code"],
        ).to_payload()

    effective_tdd_policy = tdd_policy
    if effective_tdd_policy is None:
        if step_kind == "code":
            effective_tdd_policy = "required"
        elif waiver_reason:
            effective_tdd_policy = "waived"
        else:
            effective_tdd_policy = "not-applicable"

    if effective_tdd_policy not in {"required", "waived", "not-applicable"}:
        return RegisterStepResult(
            accepted=False,
            step_id=step_id,
            errors=["tdd policy must be one of: required, waived, not-applicable"],
        ).to_payload()

    if step_kind == "code" and effective_tdd_policy != "required":
        return RegisterStepResult(
            accepted=False,
            step_id=step_id,
            errors=["code steps must use the required TDD policy"],
        ).to_payload()

    if step_kind == "non-code" and effective_tdd_policy == "required":
        return RegisterStepResult(
            accepted=False,
            step_id=step_id,
            errors=["non-code steps cannot use the required TDD policy"],
        ).to_payload()

    if effective_tdd_policy == "waived" and not waiver_reason:
        return RegisterStepResult(
            accepted=False,
            step_id=step_id,
            errors=["waiver reason is required when TDD policy is waived"],
        ).to_payload()

    if effective_tdd_policy != "waived" and waiver_reason is not None:
        return RegisterStepResult(
            accepted=False,
            step_id=step_id,
            errors=["waiver reason is only allowed when TDD policy is waived"],
        ).to_payload()

    normalized_covers = [_normalize_function_label(item) for item in covers]
    normalized_covers = [item for item in normalized_covers if item]

    if step_kind == "code" and not normalized_covers:
        return RegisterStepResult(
            accepted=False,
            step_id=step_id,
            errors=["code steps must declare at least one covered function"],
        ).to_payload()

    catalog = extract_function_catalog(project_path, branch_name, stage)
    catalog_source = _catalog_source_name(stage)
    known_functions = {
        item: priority for priority, items in catalog.items() for item in items
    }
    if not known_functions and normalized_covers:
        return RegisterStepResult(
            accepted=False,
            step_id=step_id,
            errors=[f"no functions catalog found in {catalog_source} for the target stage"],
        ).to_payload()

    unknown = [item for item in normalized_covers if item not in known_functions]
    if unknown:
        choices = _known_function_samples(catalog)
        suggestion = f" Known labels from {catalog_source}: {choices}" if choices else ""
        return RegisterStepResult(
            accepted=False,
            step_id=step_id,
            errors=[
                f"unknown covered functions in {catalog_source}: {', '.join(unknown)}.{suggestion}"
            ],
        ).to_payload()

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
    step_dependencies[step_id] = list(depends_on or [])
    progress["planningMetadata"]["lastPlannedStep"] = step_id
    progress["planningMetadata"]["planningPhase"] = (
        "initial" if len(planned_steps) == 1 else "incremental"
    )

    covers_functions = progress.setdefault("coversFunctions", {})
    covers_functions[step_id] = _default_step_coverage()
    for item in normalized_covers:
        covers_functions[step_id][known_functions[item]].append(item)

    progress["planningMetadata"]["progressMetrics"] = _compute_progress_metrics(
        catalog,
        covers_functions,
    )
    write_json(paths.progress, progress)

    active_session = read_json(paths.active_session, _default_active_session(branch_name))
    active_session["stage"] = stage
    active_session["current_step"] = step_id
    active_session["last_checkpoint_at"] = now_iso()
    active_session["updated_at"] = active_session["last_checkpoint_at"]
    write_json(paths.active_session, active_session)

    append_jsonl(
        paths.decision_log,
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
                    "depends_on": list(depends_on or []),
                    "covers": list(normalized_covers),
                    "step_kind": step_kind,
                    "tdd_policy": effective_tdd_policy,
                    "waiver_reason": waiver_reason,
                },
            )
        ],
    )

    return RegisterStepResult(
        accepted=True,
        step_id=step_id,
        errors=[],
        depends_on=list(depends_on or []),
        covers=covers_functions[step_id],
        step_metadata=progress["stepMetadata"][step_id],
        progress_metrics=progress["planningMetadata"]["progressMetrics"],
    ).to_payload()
