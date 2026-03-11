from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..domain.progress import select_next_executable_step
from ..stages.architecture.state import architecture_completeness_errors
from ..stages.concept.state import concept_completeness_errors
from ..stages.design.state import design_completeness_errors, missing_prototype_files, uncovered_design_features
from ..stages.feature_init.state import feature_init_completeness_errors
from ..stages.feature_plan.state import feature_plan_completeness_errors
from ..stages.tech.state import tech_completeness_errors
from ..stages.plan.state import plan_completeness_errors
from ..shared.storage import read_jsonl


def group_records_by_step(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        step_id = record.get("step_id")
        if not step_id:
            continue
        grouped.setdefault(step_id, []).append(record)
    return grouped


def format_record_lines(records: list[dict[str, Any]]) -> list[str]:
    if not records:
        return ["- Нет релевантных записей"]
    lines = []
    for record in sorted(records, key=lambda item: (item.get("ts", ""), item.get("id", ""))):
        status = record.get("status", "unknown")
        source = record.get("source", "unknown")
        summary = record.get("summary", "")
        lines.append(f"- `{status}` {summary} (source: `{source}`)")
    return lines


def _concept_missing_required_fields(concept_state: dict[str, Any]) -> list[str]:
    error_map = {
        "concept state must include a system overview before checkpoint": "systemOverview",
        "concept state must include at least one audience before checkpoint": "audiences",
        "concept state must include at least one scenario before checkpoint": "scenarios",
        "concept state must include at least one pain point before checkpoint": "painPoints",
        "concept state must include at least one P1 feature before checkpoint": "features.p1",
    }
    missing: list[str] = []
    for error in concept_completeness_errors(concept_state):
        field_name = error_map.get(error)
        if field_name and field_name not in missing:
            missing.append(field_name)
    return missing


def _concept_filled_fields(concept_state: dict[str, Any]) -> list[str]:
    field_checks = (
        ("projectName", bool(concept_state.get("projectName"))),
        ("systemOverview", bool(concept_state.get("systemOverview"))),
        ("audiences", bool(concept_state.get("audiences"))),
        ("scenarios", bool(concept_state.get("scenarios"))),
        ("painPoints", bool(concept_state.get("painPoints"))),
        ("features.p1", bool(concept_state.get("features", {}).get("p1"))),
        ("features.p2", bool(concept_state.get("features", {}).get("p2"))),
        ("features.p3", bool(concept_state.get("features", {}).get("p3"))),
        ("constraints", bool(concept_state.get("constraints"))),
        ("assumptions", bool(concept_state.get("assumptions"))),
        ("nextActions", bool(concept_state.get("nextActions"))),
        ("checkpointSummary", bool(concept_state.get("checkpointSummary"))),
    )
    return [field_name for field_name, is_filled in field_checks if is_filled]


def build_concept_status(concept_state: dict[str, Any]) -> dict[str, Any]:
    missing_required_fields = _concept_missing_required_fields(concept_state)
    return {
        "is_complete": not missing_required_fields,
        "missing_required_fields": missing_required_fields,
        "filled_fields": _concept_filled_fields(concept_state),
        "counts": {
            "audiences": len(concept_state.get("audiences", [])),
            "scenarios": len(concept_state.get("scenarios", [])),
            "pain_points": len(concept_state.get("painPoints", [])),
            "p1_features": len(concept_state.get("features", {}).get("p1", [])),
            "p2_features": len(concept_state.get("features", {}).get("p2", [])),
            "p3_features": len(concept_state.get("features", {}).get("p3", [])),
            "constraints": len(concept_state.get("constraints", [])),
            "assumptions": len(concept_state.get("assumptions", [])),
            "next_actions": len(concept_state.get("nextActions", [])),
        },
        "last_checkpoint_summary": concept_state.get("checkpointSummary") or None,
        "revision": concept_state.get("revision", 0),
        "ratified_at": concept_state.get("ratifiedAt"),
        "updated_at": concept_state.get("updatedAt"),
    }


def _design_missing_required_fields(
    design_state: dict[str, Any],
    concept_state: dict[str, Any],
    *,
    project_path: Path,
    branch_name: str,
) -> list[str]:
    error_map = {
        "design state must include a design overview before checkpoint": "designOverview",
        "design state must include at least one platform before checkpoint": "platforms",
        "design state must include at least one screen before checkpoint": "screens",
        "design state must include at least one user flow before checkpoint": "flows",
        "design state must include navigation links before checkpoint": "navigation",
    }
    missing: list[str] = []
    for error in design_completeness_errors(
        design_state,
        concept_state=concept_state,
        project_path=project_path,
        branch_name=branch_name,
    ):
        field_name = error_map.get(error)
        if field_name and field_name not in missing:
            missing.append(field_name)
    return missing


def _design_filled_fields(design_state: dict[str, Any]) -> list[str]:
    field_checks = (
        ("designOverview", bool(design_state.get("designOverview"))),
        ("platforms", bool(design_state.get("platforms"))),
        ("zones", bool(design_state.get("zones"))),
        ("screens", bool(design_state.get("screens"))),
        ("flows", bool(design_state.get("flows"))),
        ("navigation", bool(design_state.get("navigation"))),
        ("platformConstraints", bool(design_state.get("platformConstraints"))),
        ("nextActions", bool(design_state.get("nextActions"))),
        ("checkpointSummary", bool(design_state.get("checkpointSummary"))),
    )
    return [field_name for field_name, is_filled in field_checks if is_filled]


def build_design_status(
    design_state: dict[str, Any],
    concept_state: dict[str, Any],
    *,
    project_path: Path,
    branch_name: str,
) -> dict[str, Any]:
    missing_required_fields = _design_missing_required_fields(
        design_state,
        concept_state,
        project_path=project_path,
        branch_name=branch_name,
    )
    uncovered = uncovered_design_features(design_state, concept_state)
    missing_files = missing_prototype_files(design_state, project_path, branch_name)
    return {
        "is_complete": not missing_required_fields and not any(uncovered.values()) and not missing_files,
        "missing_required_fields": missing_required_fields,
        "filled_fields": _design_filled_fields(design_state),
        "uncovered_features": uncovered,
        "missing_prototype_files": missing_files,
        "counts": {
            "platforms": len(design_state.get("platforms", [])),
            "zones": len(design_state.get("zones", [])),
            "screens": len(design_state.get("screens", [])),
            "flows": len(design_state.get("flows", [])),
            "navigation_links": len(design_state.get("navigation", [])),
            "platform_constraints": len(design_state.get("platformConstraints", [])),
        },
        "last_checkpoint_summary": design_state.get("checkpointSummary") or None,
        "revision": design_state.get("revision", 0),
        "ratified_at": design_state.get("ratifiedAt"),
        "updated_at": design_state.get("updatedAt"),
    }


def _tech_missing_required_fields(tech_state: dict[str, Any]) -> list[str]:
    error_map = {
        "tech state must include a project type before checkpoint": "projectType",
        "tech state must include a stack overview before checkpoint": "stackOverview",
        "tech state must include at least one language component before checkpoint": "components.language",
        "tech state must include at least one build component before checkpoint": "components.build",
        "tech state must include at least one testing component before checkpoint": "components.testing",
        "tech state must include code organization before checkpoint": "codeOrganization",
    }
    missing: list[str] = []
    for error in tech_completeness_errors(tech_state):
        field_name = error_map.get(error)
        if field_name and field_name not in missing:
            missing.append(field_name)
    return missing


def _tech_filled_fields(tech_state: dict[str, Any]) -> list[str]:
    slots = {item.get("slot", "") for item in tech_state.get("components", [])}
    field_checks = (
        ("projectType", bool(tech_state.get("projectType"))),
        ("stackOverview", bool(tech_state.get("stackOverview"))),
        ("requirements", bool(tech_state.get("requirements"))),
        ("preferences", bool(tech_state.get("preferences"))),
        ("constraints", bool(tech_state.get("constraints"))),
        ("components", bool(tech_state.get("components"))),
        ("libraries", bool(tech_state.get("libraries"))),
        ("codeOrganization", bool(tech_state.get("codeOrganization"))),
        ("alternatives", bool(tech_state.get("alternatives"))),
        ("nextActions", bool(tech_state.get("nextActions"))),
        ("checkpointSummary", bool(tech_state.get("checkpointSummary"))),
        ("components.language", "language" in slots),
        ("components.build", "build" in slots),
        ("components.testing", any(slot in slots for slot in {"unit-testing", "integration-testing", "e2e-testing", "testing"})),
    )
    return [field_name for field_name, is_filled in field_checks if is_filled]


def build_tech_status(tech_state: dict[str, Any]) -> dict[str, Any]:
    missing_required_fields = _tech_missing_required_fields(tech_state)
    selected_slots = sorted({item.get("slot", "") for item in tech_state.get("components", []) if item.get("slot", "")})
    return {
        "is_complete": not missing_required_fields,
        "missing_required_fields": missing_required_fields,
        "filled_fields": _tech_filled_fields(tech_state),
        "counts": {
            "requirements": len(tech_state.get("requirements", [])),
            "preferences": len(tech_state.get("preferences", [])),
            "constraints": len(tech_state.get("constraints", [])),
            "components": len(tech_state.get("components", [])),
            "libraries": len(tech_state.get("libraries", [])),
            "alternatives": len(tech_state.get("alternatives", [])),
            "next_actions": len(tech_state.get("nextActions", [])),
        },
        "selected_slots": selected_slots,
        "last_checkpoint_summary": tech_state.get("checkpointSummary") or None,
        "revision": tech_state.get("revision", 0),
        "ratified_at": tech_state.get("ratifiedAt"),
        "updated_at": tech_state.get("updatedAt"),
    }


def _architecture_missing_required_fields(architecture_state: dict[str, Any], *, design_state: dict[str, Any]) -> list[str]:
    error_map = {
        "architecture state must include an architecture overview before checkpoint": "architectureOverview",
        "architecture state must include a project structure strategy before checkpoint": "projectStructure.strategy",
        "architecture state must include a project structure rationale before checkpoint": "projectStructure.rationale",
        "architecture state must include at least one directory before checkpoint": "projectStructure.directories",
        "architecture state must include at least one entity before checkpoint": "dataModel.entities",
        "architecture state must include at least one entity with fields before checkpoint": "dataModel.entities.fields",
        "architecture state must include at least one endpoint before checkpoint": "contracts.endpoints",
        "architecture state must include at least one endpoint linked to a screen before checkpoint": "contracts.endpoints.screenIds",
        "architecture state must include at least one response field before checkpoint": "contracts.endpoints.fields.response",
        "architecture state must include at least one code principle or pattern before checkpoint": "codePrinciples|patterns",
    }
    missing: list[str] = []
    for error in architecture_completeness_errors(architecture_state, design_state=design_state):
        field_name = error_map.get(error)
        if field_name and field_name not in missing:
            missing.append(field_name)
    return missing


def _architecture_filled_fields(architecture_state: dict[str, Any]) -> list[str]:
    field_checks = (
        ("architectureOverview", bool(architecture_state.get("architectureOverview"))),
        ("projectStructure.strategy", bool(architecture_state.get("projectStructure", {}).get("strategy"))),
        ("projectStructure.rationale", bool(architecture_state.get("projectStructure", {}).get("rationale"))),
        ("projectStructure.directories", bool(architecture_state.get("projectStructure", {}).get("directories"))),
        ("dataModel.entities", bool(architecture_state.get("dataModel", {}).get("entities"))),
        ("dataModel.entities.fields", any(entity.get("fields") for entity in architecture_state.get("dataModel", {}).get("entities", []))),
        ("contracts.endpoints", bool(architecture_state.get("contracts", {}).get("endpoints"))),
        ("integrations", bool(architecture_state.get("integrations"))),
        ("codePrinciples", bool(architecture_state.get("codePrinciples"))),
        ("patterns", bool(architecture_state.get("patterns"))),
        ("securityNotes", bool(architecture_state.get("securityNotes"))),
        ("performanceNotes", bool(architecture_state.get("performanceNotes"))),
        ("nextActions", bool(architecture_state.get("nextActions"))),
        ("checkpointSummary", bool(architecture_state.get("checkpointSummary"))),
    )
    return [field_name for field_name, is_filled in field_checks if is_filled]


def build_architecture_status(architecture_state: dict[str, Any], *, design_state: dict[str, Any]) -> dict[str, Any]:
    missing_required_fields = _architecture_missing_required_fields(architecture_state, design_state=design_state)
    reference_errors = [
        error
        for error in architecture_completeness_errors(architecture_state, design_state=design_state)
        if error
        not in {
            "architecture state must include an architecture overview before checkpoint",
            "architecture state must include a project structure strategy before checkpoint",
            "architecture state must include a project structure rationale before checkpoint",
            "architecture state must include at least one directory before checkpoint",
            "architecture state must include at least one entity before checkpoint",
            "architecture state must include at least one entity with fields before checkpoint",
            "architecture state must include at least one endpoint before checkpoint",
            "architecture state must include at least one endpoint linked to a screen before checkpoint",
            "architecture state must include at least one response field before checkpoint",
            "architecture state must include at least one code principle or pattern before checkpoint",
        }
    ]
    return {
        "is_complete": not missing_required_fields and not reference_errors,
        "missing_required_fields": missing_required_fields,
        "filled_fields": _architecture_filled_fields(architecture_state),
        "reference_errors": reference_errors,
        "counts": {
            "directories": len(architecture_state.get("projectStructure", {}).get("directories", [])),
            "entities": len(architecture_state.get("dataModel", {}).get("entities", [])),
            "endpoints": len(architecture_state.get("contracts", {}).get("endpoints", [])),
            "integrations": len(architecture_state.get("integrations", [])),
            "code_principles": len(architecture_state.get("codePrinciples", [])),
            "patterns": len(architecture_state.get("patterns", [])),
        },
        "last_checkpoint_summary": architecture_state.get("checkpointSummary") or None,
        "revision": architecture_state.get("revision", 0),
        "ratified_at": architecture_state.get("ratifiedAt"),
        "updated_at": architecture_state.get("updatedAt"),
    }


def _plan_filled_fields(plan_state: dict[str, Any]) -> list[str]:
    field_checks = (
        ("planOverview", bool(plan_state.get("planOverview"))),
        ("planningPrinciples", bool(plan_state.get("planningPrinciples"))),
        ("stepCatalog", bool(plan_state.get("stepCatalog"))),
        ("nextActions", bool(plan_state.get("nextActions"))),
        ("checkpointSummary", bool(plan_state.get("checkpointSummary"))),
    )
    return [field_name for field_name, is_filled in field_checks if is_filled]


def build_plan_status(plan_state: dict[str, Any], *, progress: dict[str, Any]) -> dict[str, Any]:
    missing_required_fields: list[str] = []
    error_map = {
        "plan state must include a plan overview before checkpoint": "planOverview",
        "plan state must include at least one step before checkpoint": "stepCatalog",
    }
    for error in plan_completeness_errors(plan_state):
        field_name = error_map.get(error)
        if field_name and field_name not in missing_required_fields:
            missing_required_fields.append(field_name)
    return {
        "is_complete": not missing_required_fields,
        "missing_required_fields": missing_required_fields,
        "filled_fields": _plan_filled_fields(plan_state),
        "counts": {
            "planned_steps": len(progress.get("plannedSteps", [])),
            "catalog_steps": len(plan_state.get("stepCatalog", [])),
            "completed_steps": len(progress.get("completedSteps", [])),
            "planning_principles": len(plan_state.get("planningPrinciples", [])),
            "next_actions": len(plan_state.get("nextActions", [])),
        },
        "coverage_snapshot": progress.get("planningMetadata", {}).get("progressMetrics", {}),
        "last_checkpoint_summary": plan_state.get("checkpointSummary") or None,
        "revision": plan_state.get("revision", 0),
        "ratified_at": plan_state.get("ratifiedAt"),
        "updated_at": plan_state.get("updatedAt"),
    }


def build_feature_init_status(feature_init_state: dict[str, Any]) -> dict[str, Any]:
    missing_required_fields: list[str] = []
    error_map = {
        "feature init state must include a feature goal before checkpoint": "featureGoal",
        "feature init state must include a problem before checkpoint": "problem",
        "feature init state must include an expected outcome before checkpoint": "expectedOutcome",
        "feature init state must include a framework before checkpoint": "projectAnalysis.framework",
        "feature init state must include at least one feature before checkpoint": "features",
        "feature init state must include integration file mappings before checkpoint": "projectAnalysis.integrationFiles",
    }
    for error in feature_init_completeness_errors(feature_init_state):
        field_name = error_map.get(error)
        if field_name and field_name not in missing_required_fields:
            missing_required_fields.append(field_name)
    analysis = feature_init_state.get("projectAnalysis", {})
    return {
        "is_complete": not missing_required_fields,
        "missing_required_fields": missing_required_fields,
        "counts": {
            "p1_features": len(feature_init_state.get("features", {}).get("p1", [])),
            "p2_features": len(feature_init_state.get("features", {}).get("p2", [])),
            "p3_features": len(feature_init_state.get("features", {}).get("p3", [])),
            "existing_modules": len(analysis.get("existingModules", [])),
            "modified_files": len(analysis.get("modifiedFiles", [])),
            "new_files": len(analysis.get("newFiles", [])),
        },
        "detected_stack": {
            "project_type": analysis.get("projectType") or None,
            "framework": analysis.get("framework") or None,
        },
        "integration_points_count": len(analysis.get("modifiedFiles", [])) + len(analysis.get("newFiles", [])),
        "functions_by_priority": {
            priority: [item.get("id", "") for item in feature_init_state.get("features", {}).get(priority, [])]
            for priority in ("p1", "p2", "p3")
        },
        "last_checkpoint_summary": feature_init_state.get("checkpointSummary") or None,
        "revision": feature_init_state.get("revision", 0),
        "ratified_at": feature_init_state.get("ratifiedAt"),
        "updated_at": feature_init_state.get("updatedAt"),
    }


def build_feature_plan_status(plan_state: dict[str, Any], *, progress: dict[str, Any]) -> dict[str, Any]:
    missing_required_fields: list[str] = []
    error_map = {
        "feature plan state must include a plan overview before checkpoint": "planOverview",
        "feature plan state must include at least one step before checkpoint": "stepCatalog",
    }
    for error in feature_plan_completeness_errors(plan_state):
        field_name = error_map.get(error)
        if field_name and field_name not in missing_required_fields:
            missing_required_fields.append(field_name)
    return {
        "is_complete": not missing_required_fields,
        "missing_required_fields": missing_required_fields,
        "planned_steps": len(progress.get("plannedSteps", [])),
        "completed_steps": len(progress.get("completedSteps", [])),
        "coverage": progress.get("planningMetadata", {}).get("progressMetrics", {}),
        "last_planned_step": progress.get("planningMetadata", {}).get("lastPlannedStep"),
        "next_executable_step": select_next_executable_step(progress),
        "last_checkpoint_summary": plan_state.get("checkpointSummary") or None,
        "revision": plan_state.get("revision", 0),
        "ratified_at": plan_state.get("ratifiedAt"),
        "updated_at": plan_state.get("updatedAt"),
    }


def filter_records_by_status(
    records: list[dict[str, Any]],
    *,
    include_obsolete: bool,
    include_conflicted: bool,
    include_proposed: bool = False,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for record in records:
        status = record.get("status")
        if status == "proposed" and not include_proposed:
            continue
        if status == "obsolete" and not include_obsolete:
            continue
        if status == "conflicted" and not include_conflicted:
            continue
        if status == "validated" or include_proposed or include_conflicted or include_obsolete:
            filtered.append(record)
    return filtered


def load_semantic_record_sets(
    paths,
    *,
    include_obsolete: bool,
    include_conflicted: bool,
    read_records: Callable[[Path], list[dict[str, Any]]] = read_jsonl,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    facts_records = read_records(paths.facts)
    decisions_records = read_records(paths.decisions)
    contracts_records = read_records(paths.contracts)
    return {
        "validated": {
            "facts": filter_records_by_status(facts_records, include_obsolete=include_obsolete, include_conflicted=include_conflicted),
            "decisions": filter_records_by_status(decisions_records, include_obsolete=include_obsolete, include_conflicted=include_conflicted),
            "contracts": filter_records_by_status(contracts_records, include_obsolete=include_obsolete, include_conflicted=include_conflicted),
        },
        "stage": {
            "facts": filter_records_by_status(facts_records, include_obsolete=include_obsolete, include_conflicted=include_conflicted, include_proposed=True),
            "decisions": filter_records_by_status(decisions_records, include_obsolete=include_obsolete, include_conflicted=include_conflicted, include_proposed=True),
            "contracts": filter_records_by_status(contracts_records, include_obsolete=include_obsolete, include_conflicted=include_conflicted, include_proposed=True),
        },
    }
