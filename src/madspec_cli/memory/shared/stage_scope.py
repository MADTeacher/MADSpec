from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

STAGE_SNAPSHOT_PATH_ATTRS = {
    "mvp.concept": "concept_state",
    "mvp.design": "design_state",
    "mvp.tech": "tech_state",
    "deploy": "deploy_state",
    "mvp.architecture": "architecture_state",
    "mvp.plan": "plan_state",
    "feature.init": "feature_init_state",
    "feature.plan": "feature_plan_state",
}

VIEW_PATH_PARTS = {
    "concept": ("concept.md",),
    "ui-design": ("ui-design.md",),
    "tech-stack": ("tech-stack.md",),
    "deployment": ("deployment.md",),
    "architecture": ("architecture.md",),
    "data-model": ("data-model.md",),
    "openapi": ("contracts", "openapi.yaml"),
    "implementation-plan": ("implementation-plan.md",),
    "project-analysis": ("project-analysis.md",),
    "feature-context": ("feature-context.md",),
    "planning-cache": ("planning-context-cache.md",),
    "project-context": ("project-context.md",),
    "review": ("review.md",),
    "improvements": ("improvements.md",),
    "security-audit": ("security-audit.md",),
}

STAGE_SNAPSHOT_KEYS_BY_STAGE = {
    "mvp.concept": frozenset({"mvp.concept"}),
    "mvp.design": frozenset({"mvp.design"}),
    "mvp.tech": frozenset({"mvp.tech"}),
    "deploy": frozenset({"deploy"}),
    "mvp.architecture": frozenset({"mvp.architecture"}),
    "mvp.plan": frozenset({"mvp.plan"}),
    "feature.init": frozenset({"feature.init"}),
    "feature.plan": frozenset({"feature.plan"}),
    "mvp.implement": frozenset(),
    "feature.implement": frozenset(),
    "review": frozenset(),
    "security": frozenset(),
}

VIEW_KEYS_BY_STAGE = {
    "mvp.concept": frozenset({"concept", "planning-cache", "project-context"}),
    "mvp.design": frozenset({"ui-design", "project-context"}),
    "mvp.tech": frozenset({"tech-stack", "project-context"}),
    "deploy": frozenset({"deployment", "project-context"}),
    "mvp.architecture": frozenset({"architecture", "data-model", "openapi", "project-context"}),
    "mvp.plan": frozenset({"implementation-plan", "planning-cache", "project-context"}),
    "feature.init": frozenset(
        {"project-analysis", "feature-context", "tech-stack", "architecture", "project-context"}
    ),
    "feature.plan": frozenset({"implementation-plan", "planning-cache", "project-context"}),
    "mvp.implement": frozenset({"project-context"}),
    "feature.implement": frozenset({"project-context"}),
    "review": frozenset({"review", "improvements", "project-context"}),
    "security": frozenset({"security-audit", "project-context"}),
}

ALL_STAGE_SNAPSHOT_KEYS = frozenset(STAGE_SNAPSHOT_PATH_ATTRS)
ALL_VIEW_KEYS = frozenset(VIEW_PATH_PARTS)


@dataclass(frozen=True)
class MemoryStageScope:
    full: bool
    stage: str | None
    stage_snapshot_keys: frozenset[str]
    view_keys: frozenset[str]


def normalize_stage_name(stage: str | None) -> str | None:
    if stage is None:
        return None
    normalized = stage.strip().lower()
    return normalized or None


def resolve_stage_scope(stage: str | None = None, *, full: bool = False) -> MemoryStageScope:
    normalized_stage = normalize_stage_name(stage)
    if full or normalized_stage is None:
        return MemoryStageScope(
            full=True,
            stage=normalized_stage,
            stage_snapshot_keys=ALL_STAGE_SNAPSHOT_KEYS,
            view_keys=ALL_VIEW_KEYS,
        )
    return MemoryStageScope(
        full=False,
        stage=normalized_stage,
        stage_snapshot_keys=STAGE_SNAPSHOT_KEYS_BY_STAGE.get(normalized_stage, frozenset()),
        view_keys=VIEW_KEYS_BY_STAGE.get(normalized_stage, frozenset()),
    )


def view_path(branch_dir: Path, view_key: str) -> Path:
    return branch_dir.joinpath(*VIEW_PATH_PARTS[view_key])
