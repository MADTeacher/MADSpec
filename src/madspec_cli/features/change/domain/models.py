from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CHANGE_SCHEMA_VERSION = 1
CHANGE_PROPOSAL_STATUSES = {"pending", "applied"}
CHANGE_WORKFLOW_MODES = {"mvp", "feature"}


@dataclass(frozen=True)
class ChangeContext:
    initialized: bool
    branch: str
    base_branch: str | None
    base_revision: str | None
    bundle_id: str | None
    revision: int
    title: str | None
    summary: str | None
    workflow_mode: str | None
    impacted_steps: list[str]
    impacted_files: int
    export_files: list[str]
    summary_artifact: str | None

    def to_payload(self) -> dict[str, Any]:
        return {
            "initialized": self.initialized,
            "branch": self.branch,
            "base_branch": self.base_branch,
            "base_revision": self.base_revision,
            "bundle_id": self.bundle_id,
            "revision": self.revision,
            "title": self.title,
            "summary": self.summary,
            "workflow_mode": self.workflow_mode,
            "impacted_steps": self.impacted_steps,
            "impacted_files": self.impacted_files,
            "export_files": self.export_files,
            "summary_artifact": self.summary_artifact,
        }
