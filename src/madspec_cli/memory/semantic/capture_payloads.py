from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

from ..stages.architecture.state import ARCHITECTURE_STAGE
from ..stages.concept.state import CONCEPT_STAGE
from ..stages.deploy.state import DEPLOY_STAGE
from ..stages.design.state import DESIGN_STAGE
from ..stages.feature_init.state import FEATURE_INIT_STAGE
from ..stages.feature_plan.state import FEATURE_PLAN_STAGE
from ..stages.plan.state import PLAN_STAGE
from ..stages.tech.state import TECH_STAGE


@dataclass(frozen=True)
class BaseCapturePayload:
    summary: str | None = None
    facts: list[str] | None = None
    decisions: list[str] | None = None
    contracts: list[str] | None = None
    evidence: list[str] | None = None
    questions: list[str] | None = None
    pending_actions: list[str] | None = None
    next_actions: list[str] | None = None


@dataclass(frozen=True)
class ConceptCapturePayload(BaseCapturePayload):
    project_name: str | None = None
    system_overview: str | None = None
    audiences: list[str] | None = None
    scenarios: list[str] | None = None
    pain_points: list[str] | None = None
    feature_p1: list[str] | None = None
    feature_p2: list[str] | None = None
    feature_p3: list[str] | None = None
    constraints: list[str] | None = None
    assumptions: list[str] | None = None


@dataclass(frozen=True)
class DesignCapturePayload(BaseCapturePayload):
    design_overview: str | None = None
    platforms: list[str] | None = None
    zones: list[str] | None = None
    screens: list[str] | None = None
    screen_features: list[str] | None = None
    flows: list[str] | None = None
    flow_steps: list[str] | None = None
    flow_alternatives: list[str] | None = None
    navigation: list[str] | None = None
    platform_constraints: list[str] | None = None
    screen_data: list[str] | None = None


@dataclass(frozen=True)
class TechCapturePayload(BaseCapturePayload):
    stack_overview: str | None = None
    project_type: str | None = None
    framework: str | None = None
    requirements: list[str] | None = None
    structure_notes: list[str] | None = None
    preferences: list[str] | None = None
    tech_constraints: list[str] | None = None
    stack_components: list[str] | None = None
    libraries: list[str] | None = None
    code_organization: str | None = None
    alternatives: list[str] | None = None


@dataclass(frozen=True)
class ArchitectureCapturePayload(BaseCapturePayload):
    architecture_overview: str | None = None
    project_structure: str | None = None
    directories: list[str] | None = None
    entities: list[str] | None = None
    entity_fields: list[str] | None = None
    entity_relationships: list[str] | None = None
    entity_states: list[str] | None = None
    endpoints: list[str] | None = None
    endpoint_screens: list[str] | None = None
    endpoint_fields: list[str] | None = None
    endpoint_errors: list[str] | None = None
    integrations: list[str] | None = None
    code_principles: list[str] | None = None
    architecture_patterns: list[str] | None = None
    security_notes: list[str] | None = None
    performance_notes: list[str] | None = None


@dataclass(frozen=True)
class PlanCapturePayload(BaseCapturePayload):
    plan_overview: str | None = None
    planning_principles: list[str] | None = None


@dataclass(frozen=True)
class DeployCapturePayload(BaseCapturePayload):
    deploy_overview: str | None = None
    deploy_goals: list[str] | None = None
    environments: list[str] | None = None
    deployment_units: list[str] | None = None
    config_notes: list[str] | None = None
    secret_notes: list[str] | None = None
    cicd_triggers: list[str] | None = None
    cicd_steps: list[str] | None = None
    release_artifacts: list[str] | None = None
    migration_notes: list[str] | None = None
    backup_notes: list[str] | None = None
    recovery_checks: list[str] | None = None
    observability_notes: list[str] | None = None
    security_controls: list[str] | None = None
    release_strategy: str | None = None
    rollback_strategy: str | None = None


@dataclass(frozen=True)
class FeatureInitCapturePayload(BaseCapturePayload):
    project_type: str | None = None
    framework: str | None = None
    structure_notes: list[str] | None = None
    feature_goal: str | None = None
    problem: str | None = None
    expected_outcome: str | None = None
    feature_p1: list[str] | None = None
    feature_p2: list[str] | None = None
    feature_p3: list[str] | None = None
    existing_modules: list[str] | None = None
    modified_files: list[str] | None = None
    new_files: list[str] | None = None
    interface_contracts: list[str] | None = None
    dependencies: list[str] | None = None
    risks: list[str] | None = None
    recommendations: list[str] | None = None
    tech_notes: list[str] | None = None
    architecture_notes: list[str] | None = None


@dataclass(frozen=True)
class LegacyCapturePayload(BaseCapturePayload):
    project_name: str | None = None
    system_overview: str | None = None
    audiences: list[str] | None = None
    scenarios: list[str] | None = None
    pain_points: list[str] | None = None
    feature_p1: list[str] | None = None
    feature_p2: list[str] | None = None
    feature_p3: list[str] | None = None
    constraints: list[str] | None = None
    assumptions: list[str] | None = None
    design_overview: str | None = None
    platforms: list[str] | None = None
    zones: list[str] | None = None
    screens: list[str] | None = None
    screen_features: list[str] | None = None
    flows: list[str] | None = None
    flow_steps: list[str] | None = None
    flow_alternatives: list[str] | None = None
    navigation: list[str] | None = None
    platform_constraints: list[str] | None = None
    screen_data: list[str] | None = None
    stack_overview: str | None = None
    project_type: str | None = None
    framework: str | None = None
    requirements: list[str] | None = None
    structure_notes: list[str] | None = None
    preferences: list[str] | None = None
    tech_constraints: list[str] | None = None
    stack_components: list[str] | None = None
    libraries: list[str] | None = None
    code_organization: str | None = None
    alternatives: list[str] | None = None
    architecture_overview: str | None = None
    project_structure: str | None = None
    directories: list[str] | None = None
    entities: list[str] | None = None
    entity_fields: list[str] | None = None
    entity_relationships: list[str] | None = None
    entity_states: list[str] | None = None
    endpoints: list[str] | None = None
    endpoint_screens: list[str] | None = None
    endpoint_fields: list[str] | None = None
    endpoint_errors: list[str] | None = None
    integrations: list[str] | None = None
    code_principles: list[str] | None = None
    architecture_patterns: list[str] | None = None
    security_notes: list[str] | None = None
    performance_notes: list[str] | None = None
    plan_overview: str | None = None
    planning_principles: list[str] | None = None
    deploy_overview: str | None = None
    deploy_goals: list[str] | None = None
    environments: list[str] | None = None
    deployment_units: list[str] | None = None
    config_notes: list[str] | None = None
    secret_notes: list[str] | None = None
    cicd_triggers: list[str] | None = None
    cicd_steps: list[str] | None = None
    release_artifacts: list[str] | None = None
    migration_notes: list[str] | None = None
    backup_notes: list[str] | None = None
    recovery_checks: list[str] | None = None
    observability_notes: list[str] | None = None
    security_controls: list[str] | None = None
    release_strategy: str | None = None
    rollback_strategy: str | None = None
    feature_goal: str | None = None
    problem: str | None = None
    expected_outcome: str | None = None
    existing_modules: list[str] | None = None
    modified_files: list[str] | None = None
    new_files: list[str] | None = None
    interface_contracts: list[str] | None = None
    dependencies: list[str] | None = None
    risks: list[str] | None = None
    recommendations: list[str] | None = None
    tech_notes: list[str] | None = None
    architecture_notes: list[str] | None = None


CapturePayload = (
    BaseCapturePayload
    | ConceptCapturePayload
    | DesignCapturePayload
    | TechCapturePayload
    | ArchitectureCapturePayload
    | PlanCapturePayload
    | DeployCapturePayload
    | FeatureInitCapturePayload
    | LegacyCapturePayload
)


_STAGE_PAYLOAD_TYPES = {
    CONCEPT_STAGE: ConceptCapturePayload,
    DESIGN_STAGE: DesignCapturePayload,
    TECH_STAGE: TechCapturePayload,
    ARCHITECTURE_STAGE: ArchitectureCapturePayload,
    PLAN_STAGE: PlanCapturePayload,
    FEATURE_PLAN_STAGE: PlanCapturePayload,
    DEPLOY_STAGE: DeployCapturePayload,
    FEATURE_INIT_STAGE: FeatureInitCapturePayload,
}


def build_stage_capture_payload(stage: str, **kwargs: Any) -> CapturePayload:
    payload_type = _STAGE_PAYLOAD_TYPES.get(stage, BaseCapturePayload)
    allowed = {field.name for field in fields(payload_type)}
    return payload_type(**{key: value for key, value in kwargs.items() if key in allowed})


def build_legacy_capture_payload(**kwargs: Any) -> LegacyCapturePayload:
    allowed = {field.name for field in fields(LegacyCapturePayload)}
    return LegacyCapturePayload(**{key: value for key, value in kwargs.items() if key in allowed})


__all__ = [
    "ArchitectureCapturePayload",
    "BaseCapturePayload",
    "CapturePayload",
    "ConceptCapturePayload",
    "DeployCapturePayload",
    "DesignCapturePayload",
    "FeatureInitCapturePayload",
    "LegacyCapturePayload",
    "PlanCapturePayload",
    "TechCapturePayload",
    "build_legacy_capture_payload",
    "build_stage_capture_payload",
]
