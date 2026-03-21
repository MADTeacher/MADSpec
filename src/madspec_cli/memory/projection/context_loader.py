from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..shared.storage import (
    _default_progress_state,
    get_memory_paths,
    now_iso,
    read_json,
    read_jsonl,
)
from ..shared.system_store.sessions import load_runtime_session
from ..stages.architecture.state import load_architecture_state
from ..stages.concept.state import load_concept_state
from ..stages.design.state import load_design_state
from ..stages.feature_init.state import is_empty_feature_init_state, load_feature_init_state
from ..stages.feature_plan.state import load_feature_plan_state
from ..stages.plan.state import load_plan_state
from ..stages.tech.state import load_tech_state


@dataclass(frozen=True)
class BranchProjectionState:
    paths: Any
    progress: dict[str, Any]
    active_session: dict[str, Any]
    concept_state: dict[str, Any]
    design_state: dict[str, Any]
    tech_state: dict[str, Any]
    architecture_state: dict[str, Any]
    plan_state: dict[str, Any]
    feature_init_state: dict[str, Any]
    feature_plan_state: dict[str, Any]
    feature_mode: bool
    generated_at: str


@dataclass(frozen=True)
class MaterializationRecords:
    decision_log: list[dict[str, Any]]
    events: list[dict[str, Any]]
    facts: list[dict[str, Any]]
    decisions: list[dict[str, Any]]
    contracts: list[dict[str, Any]]


@dataclass(frozen=True)
class RetrieveProjectionState:
    paths: Any
    progress: dict[str, Any]
    active_session: dict[str, Any]
    concept_state: dict[str, Any]
    design_state: dict[str, Any] | None
    tech_state: dict[str, Any] | None
    architecture_state: dict[str, Any] | None
    plan_state: dict[str, Any] | None
    feature_init_state: dict[str, Any] | None
    feature_plan_state: dict[str, Any] | None


def load_branch_projection_state(project_path: Path, branch_name: str) -> BranchProjectionState:
    paths = get_memory_paths(project_path, branch_name)
    progress = read_json(paths.progress, _default_progress_state())
    active_session = load_runtime_session(project_path, branch_name=branch_name)
    concept_state = load_concept_state(paths.concept_state)
    design_state = load_design_state(paths.design_state)
    tech_state = load_tech_state(paths.tech_state)
    architecture_state = load_architecture_state(paths.architecture_state)
    plan_state = load_plan_state(paths.plan_state)
    feature_init_state = load_feature_init_state(paths.feature_init_state)
    feature_plan_state = load_feature_plan_state(paths.feature_plan_state)
    feature_mode = not is_empty_feature_init_state(feature_init_state)
    generated_at = active_session.get("updated_at") or active_session.get("last_checkpoint_at") or now_iso()
    return BranchProjectionState(
        paths=paths,
        progress=progress,
        active_session=active_session,
        concept_state=concept_state,
        design_state=design_state,
        tech_state=tech_state,
        architecture_state=architecture_state,
        plan_state=plan_state,
        feature_init_state=feature_init_state,
        feature_plan_state=feature_plan_state,
        feature_mode=feature_mode,
        generated_at=generated_at,
    )


def load_materialization_records(
    paths,
    *,
    read_records=read_jsonl,
) -> MaterializationRecords:
    decision_log = read_records(paths.decision_log)
    events = read_records(paths.events)
    facts = [record for record in read_records(paths.facts) if record.get("status") == "validated"]
    decisions = [record for record in read_records(paths.decisions) if record.get("status") == "validated"]
    contracts = [record for record in read_records(paths.contracts) if record.get("status") == "validated"]
    return MaterializationRecords(
        decision_log=decision_log,
        events=events,
        facts=facts,
        decisions=decisions,
        contracts=contracts,
    )


def load_retrieve_projection_state(
    project_path: Path,
    branch_name: str,
    stage_lower: str,
    *,
    session_key: str,
) -> RetrieveProjectionState:
    paths = get_memory_paths(project_path, branch_name)
    progress = read_json(paths.progress, _default_progress_state())
    active_session = load_runtime_session(
        project_path,
        branch_name=branch_name,
        session_key=session_key,
    )
    return RetrieveProjectionState(
        paths=paths,
        progress=progress,
        active_session=active_session,
        concept_state=load_concept_state(paths.concept_state),
        design_state=load_design_state(paths.design_state) if stage_lower == "mvp.design" else None,
        tech_state=load_tech_state(paths.tech_state) if stage_lower == "mvp.tech" else None,
        architecture_state=load_architecture_state(paths.architecture_state) if stage_lower == "mvp.architecture" else None,
        plan_state=load_plan_state(paths.plan_state) if stage_lower == "mvp.plan" else None,
        feature_init_state=load_feature_init_state(paths.feature_init_state) if stage_lower == "feature.init" else None,
        feature_plan_state=load_feature_plan_state(paths.feature_plan_state) if stage_lower == "feature.plan" else None,
    )
