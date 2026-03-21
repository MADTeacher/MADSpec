from __future__ import annotations

SYSTEM_SCHEMA_VERSION = 3
LEASE_TTL_SECONDS = 30
DEFAULT_EMBEDDING_DIMENSION = 64
SYSTEM_SESSION_KEY = "active"
RECORD_STATUSES = {"validated", "proposed", "obsolete", "conflicted"}
SEARCH_SCOPES = {"step", "stage", "branch", "project"}
ARTIFACT_STAGE_HINTS = {
    "concept.md": "mvp.concept",
    "ui-design.md": "mvp.design",
    "tech-stack.md": "mvp.tech",
    "architecture.md": "mvp.architecture",
    "data-model.md": "mvp.architecture",
    "openapi.yaml": "mvp.architecture",
    "implementation-plan.md": "mvp.plan",
    "project-analysis.md": "feature.init",
    "feature-context.md": "feature.init",
    "planning-context.md": "mvp.plan",
    "planning-context-cache.md": "mvp.plan",
    "implementation-context.md": "mvp.implement",
    "project-context.md": "mvp.implement",
    "review.md": "review",
    "improvements.md": "review",
    "security-audit.md": "security",
}
SEARCHABLE_ARTIFACT_SUFFIXES = {".md", ".txt", ".yaml", ".yml", ".html", ".json"}
