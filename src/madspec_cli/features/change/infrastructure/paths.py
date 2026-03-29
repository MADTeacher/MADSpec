from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


STAGE_SNAPSHOT_FILES = {
    "mvp.concept": ("memory", "stages", "mvp.concept.json"),
    "mvp.design": ("memory", "stages", "mvp.design.json"),
    "mvp.tech": ("memory", "stages", "mvp.tech.json"),
    "mvp.architecture": ("memory", "stages", "mvp.architecture.json"),
    "mvp.plan": ("memory", "stages", "mvp.plan.json"),
    "feature.init": ("memory", "stages", "feature.init.json"),
    "feature.plan": ("memory", "stages", "feature.plan.json"),
}
SEMANTIC_FILES = {
    "facts": ("memory", "semantic", "facts.jsonl"),
    "decisions": ("memory", "semantic", "decisions.jsonl"),
    "contracts": ("memory", "semantic", "contracts.jsonl"),
}
EXPORT_FILES = ("bundle.json", "summary.md", "spec.md", "plan.md", "tasks.md")


@dataclass(frozen=True)
class ChangePaths:
    branch_dir: Path
    change_dir: Path
    state_file: Path
    proposals_file: Path
    history_file: Path
    export_dir: Path
    summary_artifact: Path


def get_change_paths(project_path: Path, branch_name: str) -> ChangePaths:
    branch_dir = project_path / ".madspec" / branch_name
    change_dir = branch_dir / "change"
    return ChangePaths(
        branch_dir=branch_dir,
        change_dir=change_dir,
        state_file=change_dir / "state.json",
        proposals_file=change_dir / "proposals.jsonl",
        history_file=change_dir / "history.jsonl",
        export_dir=change_dir / "export",
        summary_artifact=branch_dir / "change-summary.md",
    )


__all__ = [
    "ChangePaths",
    "EXPORT_FILES",
    "SEMANTIC_FILES",
    "STAGE_SNAPSHOT_FILES",
    "get_change_paths",
]
