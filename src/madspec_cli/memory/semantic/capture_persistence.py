from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..domain.conflicts import semantic_fingerprint
from ..shared.storage import (
    ensure_memory_layout,
    get_memory_paths,
    normalize_runtime_progress,
    now_iso,
)
from ..shared.system_store.constants import SYSTEM_SESSION_KEY
from ..shared.system_store.canonical_state import (
    CanonicalBranchState,
    build_runtime_snapshot_specs,
    load_canonical_branch_state,
    tag_records_for_stream,
)
from ..shared.system_store.runtime_mutations import RuntimeMutationPlan, commit_runtime_mutation
from ..shared.system_store.sessions import read_runtime_session_payload
from ..stages.architecture.state import (
    ARCHITECTURE_STAGE,
    load_architecture_state,
)
from ..stages.concept.state import CONCEPT_STAGE, load_concept_state
from ..stages.design.state import DESIGN_STAGE, load_design_state
from ..stages.deploy.state import (
    DEPLOY_STAGE,
    load_deploy_state,
    update_deploy_state,
)
from ..stages.feature_init.state import FEATURE_INIT_STAGE, load_feature_init_state, update_feature_init_state
from ..stages.feature_plan.state import FEATURE_PLAN_STAGE, load_feature_plan_state
from ..stages.plan.state import PLAN_STAGE, load_plan_state, update_plan_state
from ..stages.tech.state import TECH_STAGE, load_tech_state
from .capture_models import PersistedCaptureResult, PreparedCapture
from .records import (
    RecordBuildContext,
    build_contract_records,
    build_decision_records,
    build_fact_records,
    build_note_records,
)
from .shared import append_unique
from .updates import apply_stage_state_update


def _capture_semantic_fingerprints(
    branch_name: str,
    prepared: PreparedCapture,
) -> set[str]:
    context = RecordBuildContext(
        branch_name=branch_name,
        ts="",
        inputs=prepared.inputs,
        parsed=prepared.parsed,
    )
    return {
        semantic_fingerprint(record)
        for record in (
            build_fact_records(context)
            + build_decision_records(context)
            + build_contract_records(context)
        )
    }


def _build_capture_plan(
    *,
    project_path: Path,
    branch_name: str,
    session_key: str,
    prepared: PreparedCapture,
    canonical: CanonicalBranchState,
) -> RuntimeMutationPlan:
    paths = get_memory_paths(project_path, branch_name)
    inputs = prepared.inputs
    parsed = prepared.parsed
    bundles = prepared.bundles
    ts = now_iso()
    record_context = RecordBuildContext(
        branch_name=branch_name,
        ts=ts,
        inputs=inputs,
        parsed=parsed,
    )

    active_session = read_runtime_session_payload(
        project_path,
        branch_name=branch_name,
        session_key=session_key,
    )
    active_session["branch"] = branch_name
    active_session["session_key"] = session_key
    active_session["stage"] = inputs.stage
    if inputs.summary:
        active_session["active_goal"] = inputs.summary
    active_session["open_questions"] = append_unique(
        active_session.get("open_questions", []),
        inputs.questions,
    )[:20]
    active_session["pending_actions"] = append_unique(
        active_session.get("pending_actions", []),
        inputs.pending_actions,
    )[:20]
    active_session["current_hypotheses"] = append_unique(
        active_session.get("current_hypotheses", []),
        bundles.concept_decision_summaries
        or bundles.design_decision_summaries
        or bundles.tech_decision_summaries
        or bundles.architecture_decision_summaries
        or bundles.plan_decision_summaries
        or inputs.decisions
        or bundles.concept_fact_summaries
        or bundles.design_fact_summaries
        or bundles.tech_fact_summaries
        or bundles.architecture_fact_summaries
        or bundles.plan_fact_summaries
        or inputs.facts,
    )[:20]
    active_session["last_checkpoint_at"] = ts
    active_session["updated_at"] = ts

    note_records = build_note_records(record_context)

    concept_state = canonical.snapshots.get(CONCEPT_STAGE) or load_concept_state(paths.concept_state)
    design_state = canonical.snapshots.get(DESIGN_STAGE) or load_design_state(paths.design_state)
    tech_state = canonical.snapshots.get(TECH_STAGE) or load_tech_state(paths.tech_state)
    deploy_state = canonical.snapshots.get(DEPLOY_STAGE) or load_deploy_state(paths.deploy_state)
    architecture_state = canonical.snapshots.get(ARCHITECTURE_STAGE) or load_architecture_state(paths.architecture_state)
    plan_state = canonical.snapshots.get(PLAN_STAGE) or load_plan_state(paths.plan_state)
    feature_init_state = canonical.snapshots.get(FEATURE_INIT_STAGE) or load_feature_init_state(paths.feature_init_state)
    feature_plan_state = canonical.snapshots.get(FEATURE_PLAN_STAGE) or load_feature_plan_state(paths.feature_plan_state)
    concept_state, design_state, tech_state, architecture_state, plan_state = apply_stage_state_update(
        normalized_stage=inputs.stage,
        concept_state=concept_state,
        design_state=design_state,
        tech_state=tech_state,
        architecture_state=architecture_state,
        plan_state=plan_state,
        normalized_project_name=inputs.project_name,
        normalized_system_overview=inputs.system_overview,
        normalized_audiences=inputs.audiences,
        normalized_scenarios=inputs.scenarios,
        normalized_pain_points=inputs.pain_points,
        normalized_assumptions=inputs.assumptions,
        concept_feature_updates=parsed.concept_feature_updates,
        normalized_constraints=inputs.constraints,
        normalized_design_overview=inputs.design_overview,
        normalized_platforms=inputs.platforms,
        design_zone_updates=parsed.design_zone_updates,
        design_screen_updates=parsed.design_screen_updates,
        design_screen_feature_links=parsed.design_screen_feature_links,
        design_flow_updates=parsed.design_flow_updates,
        design_flow_step_updates=parsed.design_flow_step_updates,
        design_flow_alternative_updates=parsed.design_flow_alternative_updates,
        design_navigation_updates=parsed.design_navigation_updates,
        normalized_platform_constraints=inputs.platform_constraints,
        design_screen_data_updates=parsed.design_screen_data_updates,
        normalized_project_type=inputs.project_type,
        normalized_stack_overview=inputs.stack_overview,
        normalized_requirements=inputs.requirements,
        normalized_preferences=inputs.preferences,
        normalized_tech_constraints=inputs.tech_constraints,
        tech_component_updates=parsed.tech_component_updates,
        tech_library_updates=parsed.tech_library_updates,
        tech_code_organization=parsed.tech_code_organization,
        tech_alternative_updates=parsed.tech_alternative_updates,
        normalized_architecture_overview=inputs.architecture_overview,
        architecture_project_structure=parsed.architecture_project_structure,
        architecture_directory_updates=parsed.architecture_directory_updates,
        architecture_entity_updates=parsed.architecture_entity_updates,
        architecture_entity_field_updates=parsed.architecture_entity_field_updates,
        architecture_entity_relationship_updates=parsed.architecture_entity_relationship_updates,
        architecture_entity_state_updates=parsed.architecture_entity_state_updates,
        architecture_endpoint_updates=parsed.architecture_endpoint_updates,
        architecture_endpoint_screen_updates=parsed.architecture_endpoint_screen_updates,
        architecture_endpoint_field_updates=parsed.architecture_endpoint_field_updates,
        architecture_endpoint_error_updates=parsed.architecture_endpoint_error_updates,
        architecture_integration_updates=parsed.architecture_integration_updates,
        normalized_code_principles=inputs.code_principles,
        architecture_pattern_updates=parsed.architecture_pattern_updates,
        normalized_security_notes=inputs.security_notes,
        normalized_performance_notes=inputs.performance_notes,
        normalized_plan_overview=inputs.plan_overview,
        normalized_planning_principles=inputs.planning_principles,
        normalized_next_actions=inputs.next_actions,
    )
    if inputs.stage == FEATURE_INIT_STAGE:
        feature_init_state = update_feature_init_state(
            feature_init_state,
            feature_goal=inputs.feature_goal or None,
            problem=inputs.problem or None,
            expected_outcome=inputs.expected_outcome or None,
            project_type=inputs.project_type or None,
            framework=inputs.framework or None,
            structure_notes=inputs.structure_notes,
            existing_modules=parsed.feature_existing_modules,
            modified_files=parsed.feature_modified_files,
            new_files=parsed.feature_new_files,
            interface_contracts=inputs.interface_contracts,
            dependencies=parsed.feature_dependencies,
            risks=inputs.risks,
            recommendations=inputs.recommendations,
            tech_notes=inputs.tech_notes,
            architecture_notes=inputs.architecture_notes,
            features=parsed.feature_init_feature_updates,
            next_actions=inputs.next_actions,
        )
    elif inputs.stage == DEPLOY_STAGE:
        deploy_state = update_deploy_state(
            deploy_state,
            deploy_overview=inputs.deploy_overview or None,
            goals=inputs.deploy_goals,
            environments=parsed.deploy_environment_updates,
            deployment_units=parsed.deploy_unit_updates,
            config_notes=inputs.config_notes,
            secret_notes=inputs.secret_notes,
            cicd_triggers=inputs.cicd_triggers,
            cicd_steps=inputs.cicd_steps,
            release_artifacts=inputs.release_artifacts,
            migration_notes=inputs.migration_notes,
            backup_notes=inputs.backup_notes,
            recovery_checks=inputs.recovery_checks,
            observability_notes=inputs.observability_notes,
            security_controls=inputs.security_controls,
            constraints=inputs.contracts,
            release_strategy=inputs.release_strategy or None,
            rollback_strategy=inputs.rollback_strategy or None,
            next_actions=inputs.next_actions,
        )
    elif inputs.stage == FEATURE_PLAN_STAGE:
        feature_plan_state = update_plan_state(
            feature_plan_state,
            plan_overview=inputs.plan_overview or None,
            planning_principles=inputs.planning_principles,
            next_actions=inputs.next_actions,
        )

    fact_records = build_fact_records(record_context)
    decision_records = build_decision_records(record_context)
    contract_records = build_contract_records(record_context)

    snapshot_payloads: dict[str, dict[str, Any]] = {}
    if inputs.stage == CONCEPT_STAGE:
        snapshot_payloads[CONCEPT_STAGE] = concept_state
    elif inputs.stage == DESIGN_STAGE:
        snapshot_payloads[DESIGN_STAGE] = design_state
    elif inputs.stage == TECH_STAGE:
        snapshot_payloads[TECH_STAGE] = tech_state
    elif inputs.stage == DEPLOY_STAGE:
        snapshot_payloads[DEPLOY_STAGE] = deploy_state
    elif inputs.stage == ARCHITECTURE_STAGE:
        snapshot_payloads[ARCHITECTURE_STAGE] = architecture_state
    elif inputs.stage == PLAN_STAGE:
        snapshot_payloads[PLAN_STAGE] = plan_state
    elif inputs.stage == FEATURE_INIT_STAGE:
        snapshot_payloads[FEATURE_INIT_STAGE] = feature_init_state
    elif inputs.stage == FEATURE_PLAN_STAGE:
        snapshot_payloads[FEATURE_PLAN_STAGE] = feature_plan_state

    catalog_override: dict[str, list[str]] | None = None
    if inputs.stage == CONCEPT_STAGE:
        catalog_override = {
            priority: [
                item.get("name", "")
                for item in concept_state.get("features", {}).get(priority, [])
                if item.get("name", "")
            ]
            for priority in ("p1", "p2", "p3")
        }
    elif inputs.stage == FEATURE_INIT_STAGE:
        catalog_override = {
            priority: [
                item.get("id", "")
                for item in feature_init_state.get("features", {}).get(priority, [])
                if item.get("id", "")
            ]
            for priority in ("p1", "p2", "p3")
        }
    progress_state, _ = normalize_runtime_progress(
        project_path,
        branch_name,
        canonical.progress,
        catalog_override=catalog_override,
    )
    snapshot_payloads["progress"] = progress_state

    records: list[dict[str, Any]] = []
    records.extend(tag_records_for_stream(note_records, "decision_log"))
    records.extend(tag_records_for_stream(fact_records, "facts"))
    records.extend(tag_records_for_stream(decision_records, "decisions"))
    records.extend(tag_records_for_stream(contract_records, "contracts"))
    return RuntimeMutationPlan(
        stage_snapshots=build_runtime_snapshot_specs(project_path, branch_name, snapshot_payloads),
        sessions=[{"session_key": session_key, "payload": active_session}],
        records=records,
        response_payload={
            "written": {
                "notes": len(note_records),
                "facts": len(fact_records),
                "decisions": len(decision_records),
                "contracts": len(contract_records),
                "questions": len(inputs.questions),
                "pending_actions": len(inputs.pending_actions),
            },
        },
    )


def _detect_capture_conflict(
    base_state: CanonicalBranchState,
    current_state: CanonicalBranchState,
    *,
    stage: str,
) -> dict[str, Any] | None:
    if stage not in {
        CONCEPT_STAGE,
        DESIGN_STAGE,
        TECH_STAGE,
        DEPLOY_STAGE,
        ARCHITECTURE_STAGE,
        PLAN_STAGE,
        FEATURE_INIT_STAGE,
        FEATURE_PLAN_STAGE,
    }:
        return None
    base_snapshot = base_state.snapshots.get(stage)
    current_snapshot = current_state.snapshots.get(stage)
    if base_snapshot != current_snapshot:
        return {
            "kind": "snapshot_conflict",
            "scope": "stage",
            "conflicting_fields": [stage],
            "details": {"reason": "target stage snapshot changed while preparing capture"},
        }
    return None


def persist_capture(
    *,
    project_path: Path,
    branch_name: str,
    session_key: str = SYSTEM_SESSION_KEY,
    expected_revision: int | None = None,
    prepared: PreparedCapture,
    consolidate_fn: Callable[..., list[Path]],
) -> dict[str, Any]:
    ensure_memory_layout(project_path, branch_name, stage=prepared.inputs.stage)
    base_state = load_canonical_branch_state(project_path, branch_name)
    projection_meta = commit_runtime_mutation(
        project_path,
        branch_name=branch_name,
        stage=prepared.inputs.stage,
        mutation_kind="capture",
        scope="stage",
        session_key=session_key,
        expected_revision=expected_revision if expected_revision is not None else base_state.runtime_revision,
        base_state=base_state,
        plan_builder=lambda latest_state: _build_capture_plan(
            project_path=project_path,
            branch_name=branch_name,
            session_key=session_key,
            prepared=prepared,
            canonical=latest_state,
        ),
        conflict_detector=lambda base, current: _detect_capture_conflict(
            base,
            current,
            stage=prepared.inputs.stage,
        ),
    )
    if not projection_meta.get("accepted", True):
        return projection_meta

    result = PersistedCaptureResult(
        written=projection_meta["written"],
        generated_views=[],
    )
    payload = result.to_payload(
        project_path=project_path,
        branch_name=branch_name,
        stage=prepared.inputs.stage,
        status=prepared.inputs.status,
        warnings=prepared.inputs.warnings,
    )
    payload["generated_views"] = projection_meta["generated_views"]
    payload["projection_status"] = projection_meta["projection_status"]
    payload["projection_refresh_required"] = projection_meta["projection_refresh_required"]
    payload["warnings"] = [*payload.get("warnings", []), *projection_meta["warnings"]]
    return payload


def _filter_non_blocking_design_validation_errors(errors: list[str]) -> list[str]:
    non_blocking_prefixes = (
        "design coverage missing ",
        "design references missing prototype file ",
        "design screen ",
        "design flow ",
        "design navigation ",
    )
    return [error for error in errors if not error.startswith(non_blocking_prefixes)]


def _filter_non_blocking_architecture_validation_errors(errors: list[str]) -> list[str]:
    non_blocking_prefixes = (
        "architecture entity '",
        "architecture endpoint '",
        "architecture must link at least one endpoint to design screen ",
        "architecture screen '",
    )
    return [error for error in errors if not error.startswith(non_blocking_prefixes)]
