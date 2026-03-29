from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .records import PROCEDURE_FILES
from .stage_scope import resolve_stage_scope

STEP_KINDS = {"code", "non-code"}
TDD_POLICIES = {"required", "waived", "not-applicable"}
TDD_PHASES = {"not_started", "red", "green", "refactor", "completed", "waived"}
PRIORITIES = ("p1", "p2", "p3")
LEGACY_TDD_WAIVER_REASON = "Legacy step migrated without recorded TDD evidence."


@dataclass(frozen=True)
class MemoryPaths:
    branch_dir: Path
    memory_dir: Path
    progress: Path
    stages_dir: Path
    concept_state: Path
    design_state: Path
    tech_state: Path
    deploy_state: Path
    architecture_state: Path
    plan_state: Path
    feature_init_state: Path
    feature_plan_state: Path
    working_dir: Path
    active_session: Path
    decision_log: Path
    episodes_dir: Path
    events: Path
    semantic_dir: Path
    facts: Path
    decisions: Path
    contracts: Path

    def __getitem__(self, key: str) -> Path:
        return getattr(self, key)

    def __iter__(self) -> Iterator[str]:
        return iter(self.as_dict())

    def as_dict(self) -> dict[str, Path]:
        return {
            "branch_dir": self.branch_dir,
            "memory_dir": self.memory_dir,
            "progress": self.progress,
            "stages_dir": self.stages_dir,
            "concept_state": self.concept_state,
            "design_state": self.design_state,
            "tech_state": self.tech_state,
            "deploy_state": self.deploy_state,
            "architecture_state": self.architecture_state,
            "plan_state": self.plan_state,
            "feature_init_state": self.feature_init_state,
            "feature_plan_state": self.feature_plan_state,
            "working_dir": self.working_dir,
            "active_session": self.active_session,
            "decision_log": self.decision_log,
            "episodes_dir": self.episodes_dir,
            "events": self.events,
            "semantic_dir": self.semantic_dir,
            "facts": self.facts,
            "decisions": self.decisions,
            "contracts": self.contracts,
        }


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _default_progress_state() -> dict[str, Any]:
    return {
        "currentImplementStep": None,
        "completedSteps": [],
        "plannedSteps": [],
        "stepStatus": {},
        "stepMetadata": {},
        "coversFunctions": {},
        "planningMetadata": {
            "lastPlannedStep": None,
            "planningPhase": "initial",
            "totalStepsEstimated": None,
            "stepDependencies": {},
            "progressMetrics": {
                "p1Coverage": {"covered": 0, "total": 0, "percentage": 0},
                "p2Coverage": {"covered": 0, "total": 0, "percentage": 0},
                "p3Coverage": {"covered": 0, "total": 0, "percentage": 0},
                "overallProgress": 0,
            },
        },
    }


def _default_step_status(*, tdd_phase: str = "not_started") -> dict[str, Any]:
    return {
        "status": "planned",
        "completedAt": None,
        "tddPhase": tdd_phase,
        "redEvidence": [],
        "greenEvidence": [],
        "refactorNote": None,
    }


def _default_step_metadata(
    *,
    kind: str = "code",
    tdd_policy: str = "required",
    waiver_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "tddPolicy": tdd_policy,
        "waiverReason": waiver_reason,
    }


def _default_step_coverage() -> dict[str, list[str]]:
    return {priority: [] for priority in PRIORITIES}


def _normalize_step_coverage(coverage: Any) -> dict[str, list[str]]:
    normalized = _default_step_coverage()
    if not isinstance(coverage, dict):
        return normalized

    for priority in PRIORITIES:
        values = coverage.get(priority, [])
        if isinstance(values, list):
            normalized[priority] = [item for item in values if isinstance(item, str)]
    return normalized


def normalize_progress_state(progress: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    changed = False
    normalized = dict(progress)

    default_state = _default_progress_state()
    for key, value in default_state.items():
        if key not in normalized:
            normalized[key] = json.loads(json.dumps(value))
            changed = True

    completed_steps = normalized.get("completedSteps", [])
    planned_steps = normalized.get("plannedSteps", [])
    step_status = normalized.setdefault("stepStatus", {})
    step_metadata = normalized.setdefault("stepMetadata", {})
    covers_functions = normalized.setdefault("coversFunctions", {})

    if not isinstance(covers_functions, dict):
        covers_functions = {}
        normalized["coversFunctions"] = covers_functions
        changed = True

    for step_id, coverage in list(covers_functions.items()):
        normalized_coverage = _normalize_step_coverage(coverage)
        if coverage != normalized_coverage:
            covers_functions[step_id] = normalized_coverage
            changed = True

    for step_id in planned_steps:
        status_info = step_status.get(step_id)
        is_completed = step_id in completed_steps
        if not isinstance(status_info, dict):
            status_info = _default_step_status(
                tdd_phase="waived" if is_completed else "not_started"
            )
            status_info["status"] = "completed" if is_completed else "planned"
            status_info["completedAt"] = None
            step_status[step_id] = status_info
            changed = True

        metadata = step_metadata.get(step_id)
        if not isinstance(metadata, dict):
            if is_completed or status_info.get("status") == "completed":
                metadata = _default_step_metadata(
                    kind="non-code",
                    tdd_policy="waived",
                    waiver_reason=LEGACY_TDD_WAIVER_REASON,
                )
            else:
                metadata = _default_step_metadata()
            step_metadata[step_id] = metadata
            changed = True

        kind = metadata.get("kind")
        if kind not in STEP_KINDS:
            kind = "non-code" if is_completed or status_info.get("status") == "completed" else "code"
            metadata["kind"] = kind
            changed = True

        tdd_policy = metadata.get("tddPolicy")
        if tdd_policy not in TDD_POLICIES:
            if kind == "code":
                tdd_policy = "required"
            elif metadata.get("waiverReason"):
                tdd_policy = "waived"
            elif is_completed or status_info.get("status") == "completed":
                tdd_policy = "waived"
            else:
                tdd_policy = "not-applicable"
            metadata["tddPolicy"] = tdd_policy
            changed = True

        if tdd_policy == "waived" and not metadata.get("waiverReason"):
            metadata["waiverReason"] = LEGACY_TDD_WAIVER_REASON
            changed = True
        elif tdd_policy != "waived" and metadata.get("waiverReason") is not None:
            metadata["waiverReason"] = None
            changed = True

        default_tdd_phase = "waived" if tdd_policy in {"waived", "not-applicable"} else "not_started"
        if "status" not in status_info:
            status_info["status"] = "completed" if is_completed else "planned"
            changed = True
        if "completedAt" not in status_info:
            status_info["completedAt"] = None
            changed = True
        if status_info.get("tddPhase") not in TDD_PHASES:
            status_info["tddPhase"] = default_tdd_phase
            changed = True
        elif tdd_policy in {"waived", "not-applicable"} and status_info.get("tddPhase") != "waived":
            status_info["tddPhase"] = "waived"
            changed = True
        if "redEvidence" not in status_info or not isinstance(status_info.get("redEvidence"), list):
            status_info["redEvidence"] = []
            changed = True
        if "greenEvidence" not in status_info or not isinstance(status_info.get("greenEvidence"), list):
            status_info["greenEvidence"] = []
            changed = True
        if "refactorNote" not in status_info:
            status_info["refactorNote"] = None
            changed = True

        coverage = covers_functions.get(step_id)
        normalized_coverage = _normalize_step_coverage(coverage)
        if coverage != normalized_coverage:
            covers_functions[step_id] = normalized_coverage
            changed = True

    return normalized, changed


def normalize_runtime_progress(
    project_path: Path,
    branch_name: str,
    progress: dict[str, Any],
    *,
    catalog_override: dict[str, list[str]] | None = None,
) -> tuple[dict[str, Any], bool]:
    from .progress_utils import _compute_progress_metrics, extract_function_catalog

    normalized, changed = normalize_progress_state(progress)
    normalized, derived_changed = recompute_runtime_progress_fields(
        project_path,
        branch_name,
        normalized,
        catalog_override=catalog_override,
    )
    changed = changed or derived_changed
    return normalized, changed


def recompute_runtime_progress_fields(
    project_path: Path,
    branch_name: str,
    progress: dict[str, Any],
    *,
    catalog_override: dict[str, list[str]] | None = None,
) -> tuple[dict[str, Any], bool]:
    from .progress_utils import _compute_progress_metrics, extract_function_catalog

    normalized = dict(progress)
    changed = False

    planned_steps = list(normalized.get("plannedSteps", []))
    planning_metadata = normalized.setdefault("planningMetadata", {})
    expected_last_planned_step = planned_steps[-1] if planned_steps else None
    expected_planning_phase = "initial" if len(planned_steps) <= 1 else "incremental"
    if planning_metadata.get("lastPlannedStep") != expected_last_planned_step:
        planning_metadata["lastPlannedStep"] = expected_last_planned_step
        changed = True
    if planning_metadata.get("planningPhase") != expected_planning_phase:
        planning_metadata["planningPhase"] = expected_planning_phase
        changed = True

    catalog: dict[str, list[str]] = catalog_override or {}
    if not catalog:
        for stage_name in ("mvp.plan", "feature.plan"):
            stage_catalog = extract_function_catalog(project_path, branch_name, stage_name)
            if any(stage_catalog.values()):
                catalog = stage_catalog
                break
    if not catalog:
        return normalized, changed

    covers_functions = normalized.setdefault("coversFunctions", {})
    expected_metrics = _compute_progress_metrics(catalog, covers_functions)
    if planning_metadata.get("progressMetrics") != expected_metrics:
        planning_metadata["progressMetrics"] = expected_metrics
        changed = True
    return normalized, changed


def _default_active_session(branch_name: str) -> dict[str, Any]:
    ts = now_iso()
    return {
        "branch": branch_name,
        "active_goal": "",
        "stage": "idle",
        "current_step": None,
        "pending_actions": [],
        "open_questions": [],
        "current_hypotheses": [],
        "last_checkpoint_at": None,
        "updated_at": ts,
    }


def _memory_root(project_path: Path, branch_name: str) -> Path:
    return project_path / ".madspec" / branch_name / "memory"


def get_memory_paths(project_path: Path, branch_name: str) -> MemoryPaths:
    branch_dir = project_path / ".madspec" / branch_name
    memory_dir = _memory_root(project_path, branch_name)
    return MemoryPaths(
        branch_dir=branch_dir,
        memory_dir=memory_dir,
        progress=memory_dir / "progress.json",
        stages_dir=memory_dir / "stages",
        concept_state=memory_dir / "stages" / "mvp.concept.json",
        design_state=memory_dir / "stages" / "mvp.design.json",
        tech_state=memory_dir / "stages" / "mvp.tech.json",
        deploy_state=memory_dir / "stages" / "deploy.json",
        architecture_state=memory_dir / "stages" / "mvp.architecture.json",
        plan_state=memory_dir / "stages" / "mvp.plan.json",
        feature_init_state=memory_dir / "stages" / "feature.init.json",
        feature_plan_state=memory_dir / "stages" / "feature.plan.json",
        working_dir=memory_dir / "working",
        active_session=memory_dir / "working" / "active-session.json",
        decision_log=memory_dir / "working" / "decision-log.jsonl",
        episodes_dir=memory_dir / "episodes",
        events=memory_dir / "episodes" / "events.jsonl",
        semantic_dir=memory_dir / "semantic",
        facts=memory_dir / "semantic" / "facts.jsonl",
        decisions=memory_dir / "semantic" / "decisions.jsonl",
        contracts=memory_dir / "semantic" / "contracts.jsonl",
    )


def read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def append_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    if not records:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def ensure_procedures_layout(project_path: Path) -> list[Path]:
    procedures_dir = project_path / ".madspec" / "procedures"
    procedures_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    for relative_name, content in PROCEDURE_FILES.items():
        path = procedures_dir / relative_name
        if not path.exists():
            path.write_text(content, encoding="utf-8")
            created.append(path)
    return created


def ensure_memory_layout(
    project_path: Path,
    branch_name: str,
    *,
    stage: str | None = None,
    full: bool = False,
) -> list[Path]:
    from ..stages.concept.state import (
        default_concept_state,
        is_empty_concept_state,
        migrate_legacy_concept_markdown,
        save_concept_state,
    )
    from ..stages.design.state import default_design_state, save_design_state
    from ..stages.tech.state import default_tech_state, save_tech_state
    from ..stages.deploy.state import default_deploy_state, save_deploy_state
    from ..stages.architecture.state import (
        default_architecture_state,
        save_architecture_state,
    )
    from ..stages.plan.state import (
        default_plan_state,
        is_empty_plan_state,
        migrate_legacy_plan_state,
        save_plan_state,
    )
    from ..stages.feature_init.state import (
        default_feature_init_state,
        migrate_legacy_project_analysis_markdown,
        save_feature_init_state,
    )
    from ..stages.feature_plan.state import save_feature_plan_state

    paths = get_memory_paths(project_path, branch_name)
    scope = resolve_stage_scope(stage, full=full)
    created: list[Path] = []

    paths.branch_dir.mkdir(parents=True, exist_ok=True)
    paths.stages_dir.mkdir(parents=True, exist_ok=True)
    paths.working_dir.mkdir(parents=True, exist_ok=True)
    paths.episodes_dir.mkdir(parents=True, exist_ok=True)
    paths.semantic_dir.mkdir(parents=True, exist_ok=True)

    created.extend(ensure_procedures_layout(project_path))

    progress_exists = paths.progress.exists()
    progress = read_json(paths.progress, _default_progress_state())
    if not isinstance(progress, dict):
        progress = _default_progress_state()
    progress, progress_changed = normalize_runtime_progress(project_path, branch_name, progress)
    if (not progress_exists) or progress_changed:
        write_json(paths.progress, progress)
        if not progress_exists:
            created.append(paths.progress)
    elif read_json(paths.progress, None) != progress:
        write_json(paths.progress, progress)

    active_session_exists = paths.active_session.exists()
    if not active_session_exists:
        write_json(paths.active_session, _default_active_session(branch_name))
        created.append(paths.active_session)

    if "mvp.concept" in scope.stage_snapshot_keys:
        concept_exists = paths.concept_state.exists()
        concept_state = read_json(paths.concept_state, default_concept_state())
        if not isinstance(concept_state, dict):
            concept_state = default_concept_state()
        legacy_concept_path = paths.branch_dir / "concept.md"
        if legacy_concept_path.exists() and is_empty_concept_state(concept_state):
            concept_state = migrate_legacy_concept_markdown(legacy_concept_path)
        save_concept_state(paths.concept_state, concept_state)
        if not concept_exists and paths.concept_state.exists():
            created.append(paths.concept_state)

    if "mvp.design" in scope.stage_snapshot_keys:
        design_exists = paths.design_state.exists()
        design_state = read_json(paths.design_state, default_design_state())
        if not isinstance(design_state, dict):
            design_state = default_design_state()
        save_design_state(paths.design_state, design_state)
        if not design_exists and paths.design_state.exists():
            created.append(paths.design_state)

    if "mvp.tech" in scope.stage_snapshot_keys:
        tech_exists = paths.tech_state.exists()
        tech_state = read_json(paths.tech_state, default_tech_state())
        if not isinstance(tech_state, dict):
            tech_state = default_tech_state()
        save_tech_state(paths.tech_state, tech_state)
        if not tech_exists and paths.tech_state.exists():
            created.append(paths.tech_state)

    if "deploy" in scope.stage_snapshot_keys:
        deploy_exists = paths.deploy_state.exists()
        deploy_state = read_json(paths.deploy_state, default_deploy_state())
        if not isinstance(deploy_state, dict):
            deploy_state = default_deploy_state()
        save_deploy_state(paths.deploy_state, deploy_state)
        if not deploy_exists and paths.deploy_state.exists():
            created.append(paths.deploy_state)

    if "mvp.architecture" in scope.stage_snapshot_keys:
        architecture_exists = paths.architecture_state.exists()
        architecture_state = read_json(paths.architecture_state, default_architecture_state())
        if not isinstance(architecture_state, dict):
            architecture_state = default_architecture_state()
        save_architecture_state(paths.architecture_state, architecture_state)
        if not architecture_exists and paths.architecture_state.exists():
            created.append(paths.architecture_state)

    if "mvp.plan" in scope.stage_snapshot_keys:
        plan_exists = paths.plan_state.exists()
        should_migrate_plan = (
            not plan_exists
            and (
                (paths.branch_dir / "implementation-plan.md").exists()
                or any(progress.get("plannedSteps", []))
                or (paths.branch_dir / "steps").exists()
            )
        )
        if should_migrate_plan:
            plan_state = migrate_legacy_plan_state(
                progress=progress,
                implementation_plan_path=paths.branch_dir / "implementation-plan.md",
                steps_dir=paths.branch_dir / "steps",
            )
        else:
            plan_state = read_json(paths.plan_state, default_plan_state())
            if not isinstance(plan_state, dict):
                plan_state = default_plan_state()
        save_plan_state(paths.plan_state, plan_state)
        if not plan_exists and paths.plan_state.exists():
            created.append(paths.plan_state)

    if "feature.init" in scope.stage_snapshot_keys:
        feature_init_exists = paths.feature_init_state.exists()
        feature_init_state = read_json(paths.feature_init_state, default_feature_init_state())
        if not isinstance(feature_init_state, dict):
            feature_init_state = default_feature_init_state()
        legacy_analysis_path = paths.branch_dir / "project-analysis.md"
        if not feature_init_exists and legacy_analysis_path.exists():
            feature_init_state = migrate_legacy_project_analysis_markdown(legacy_analysis_path)
        save_feature_init_state(paths.feature_init_state, feature_init_state)
        if not feature_init_exists and paths.feature_init_state.exists():
            created.append(paths.feature_init_state)

    if "feature.plan" in scope.stage_snapshot_keys:
        feature_plan_exists = paths.feature_plan_state.exists()
        should_migrate_feature_plan = (
            not feature_plan_exists
            and (
                (paths.branch_dir / "implementation-plan.md").exists()
                or any(progress.get("plannedSteps", []))
                or (paths.branch_dir / "steps").exists()
            )
        )
        if should_migrate_feature_plan:
            feature_plan_state = migrate_legacy_plan_state(
                progress=progress,
                implementation_plan_path=paths.branch_dir / "implementation-plan.md",
                steps_dir=paths.branch_dir / "steps",
            )
        else:
            feature_plan_state = read_json(paths.feature_plan_state, default_plan_state())
            if not isinstance(feature_plan_state, dict):
                feature_plan_state = default_plan_state()
        save_feature_plan_state(paths.feature_plan_state, feature_plan_state)
        if not feature_plan_exists and paths.feature_plan_state.exists():
            created.append(paths.feature_plan_state)

    for path in (
        paths.decision_log,
        paths.events,
        paths.facts,
        paths.decisions,
        paths.contracts,
    ):
        if not path.exists():
            path.write_text("", encoding="utf-8")
            created.append(path)
    return created
