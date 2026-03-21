from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .updates import StageSummaryBundles


@dataclass
class CaptureInputs:
    stage: str
    status: str
    summary: str
    warnings: list[dict[str, str]]
    facts: list[str]
    decisions: list[str]
    contracts: list[str]
    evidence: list[str]
    questions: list[str]
    pending_actions: list[str]
    project_name: str
    system_overview: str
    audiences: list[str]
    scenarios: list[str]
    pain_points: list[str]
    feature_p1: list[str]
    feature_p2: list[str]
    feature_p3: list[str]
    constraints: list[str]
    assumptions: list[str]
    next_actions: list[str]
    design_overview: str
    platforms: list[str]
    zones: list[str]
    screens: list[str]
    screen_features: list[str]
    flows: list[str]
    flow_steps: list[str]
    flow_alternatives: list[str]
    navigation: list[str]
    platform_constraints: list[str]
    screen_data: list[str]
    stack_overview: str
    project_type: str
    framework: str
    requirements: list[str]
    structure_notes: list[str]
    preferences: list[str]
    tech_constraints: list[str]
    stack_components: list[str]
    libraries: list[str]
    code_organization: str
    alternatives: list[str]
    architecture_overview: str
    project_structure: str
    directories: list[str]
    entities: list[str]
    entity_fields: list[str]
    entity_relationships: list[str]
    entity_states: list[str]
    endpoints: list[str]
    endpoint_screens: list[str]
    endpoint_fields: list[str]
    endpoint_errors: list[str]
    integrations: list[str]
    code_principles: list[str]
    architecture_patterns: list[str]
    security_notes: list[str]
    performance_notes: list[str]
    plan_overview: str
    planning_principles: list[str]
    deploy_overview: str
    deploy_goals: list[str]
    environments: list[str]
    deployment_units: list[str]
    config_notes: list[str]
    secret_notes: list[str]
    cicd_triggers: list[str]
    cicd_steps: list[str]
    release_artifacts: list[str]
    migration_notes: list[str]
    backup_notes: list[str]
    recovery_checks: list[str]
    observability_notes: list[str]
    security_controls: list[str]
    release_strategy: str
    rollback_strategy: str
    feature_goal: str
    problem: str
    expected_outcome: str
    existing_modules: list[str]
    modified_files: list[str]
    new_files: list[str]
    interface_contracts: list[str]
    dependencies: list[str]
    risks: list[str]
    recommendations: list[str]
    tech_notes: list[str]
    architecture_notes: list[str]


@dataclass(frozen=True)
class ParsedStageBundle:
    concept_feature_updates: dict[str, list[dict[str, str]]]
    concept_errors: list[str]
    feature_init_feature_updates: dict[str, list[dict[str, str]]]
    feature_existing_modules: list[dict[str, str]]
    feature_modified_files: list[dict[str, Any]]
    feature_new_files: list[dict[str, Any]]
    feature_dependencies: list[dict[str, str]]
    feature_init_errors: list[str]
    design_zone_updates: list[dict[str, str]]
    design_screen_updates: list[dict[str, Any]]
    design_screen_feature_links: list[dict[str, str]]
    design_flow_updates: list[dict[str, Any]]
    design_flow_step_updates: list[dict[str, str]]
    design_flow_alternative_updates: list[dict[str, str]]
    design_navigation_updates: list[dict[str, str]]
    design_screen_data_updates: list[dict[str, str]]
    design_errors: list[str]
    tech_component_updates: list[dict[str, str]]
    tech_library_updates: list[dict[str, str]]
    tech_alternative_updates: list[dict[str, str]]
    tech_code_organization: dict[str, str] | None
    tech_errors: list[str]
    deploy_environment_updates: list[dict[str, str]]
    deploy_unit_updates: list[dict[str, str]]
    deploy_errors: list[str]
    architecture_project_structure: dict[str, str] | None
    architecture_directory_updates: list[dict[str, str]]
    architecture_entity_updates: list[dict[str, str]]
    architecture_entity_field_updates: list[dict[str, Any]]
    architecture_entity_relationship_updates: list[dict[str, Any]]
    architecture_entity_state_updates: list[dict[str, Any]]
    architecture_endpoint_updates: list[dict[str, Any]]
    architecture_endpoint_screen_updates: list[dict[str, str]]
    architecture_endpoint_field_updates: list[dict[str, Any]]
    architecture_endpoint_error_updates: list[dict[str, Any]]
    architecture_integration_updates: list[dict[str, Any]]
    architecture_pattern_updates: list[dict[str, str]]
    architecture_errors: list[str]


@dataclass(frozen=True)
class PreparedCapture:
    inputs: CaptureInputs
    parsed: ParsedStageBundle
    bundles: StageSummaryBundles


@dataclass(frozen=True)
class PersistedCaptureResult:
    written: dict[str, int]
    generated_views: list[Path]

    def to_payload(
        self,
        *,
        project_path: Path,
        branch_name: str,
        stage: str,
        status: str,
        warnings: list[dict[str, str]],
    ) -> dict[str, Any]:
        return {
            "accepted": True,
            "branch": branch_name,
            "stage": stage,
            "status": status,
            "written": self.written,
            "generated_views": [str(path.relative_to(project_path)) for path in self.generated_views],
            "warnings": warnings,
        }
