from __future__ import annotations

from pathlib import Path
from typing import Any

from ..domain.models import ChangeContext
from .paths import get_change_paths
from .repository import load_change_state


def build_change_context(project_path: Path, branch_name: str) -> dict[str, Any]:
    state = load_change_state(project_path, branch_name)
    if state is None:
        return ChangeContext(
            initialized=False,
            branch=branch_name,
            base_branch=None,
            base_revision=None,
            bundle_id=None,
            revision=0,
            title=None,
            summary=None,
            workflow_mode=None,
            impacted_steps=[],
            impacted_files=0,
            export_files=[],
            summary_artifact=None,
        ).to_payload()

    active_bundle = state.get("activeBundle") or {}
    paths = get_change_paths(project_path, branch_name)
    return ChangeContext(
        initialized=True,
        branch=branch_name,
        base_branch=state.get("baseBranch"),
        base_revision=state.get("baseRevision"),
        bundle_id=state.get("bundleId"),
        revision=int(state.get("revision") or 0),
        title=active_bundle.get("title"),
        summary=active_bundle.get("summary"),
        workflow_mode=active_bundle.get("workflowMode"),
        impacted_steps=list(active_bundle.get("workflowDiff", {}).get("impactedSteps", [])),
        impacted_files=len(active_bundle.get("gitDiff", {}).get("files", [])),
        export_files=[
            item.get("path", "") for item in active_bundle.get("exportFiles", []) if item.get("path")
        ],
        summary_artifact=(
            str(paths.summary_artifact.relative_to(project_path))
            if paths.summary_artifact.exists()
            else None
        ),
    ).to_payload()


def render_change_summary_markdown(bundle: dict[str, Any]) -> str:
    files = bundle.get("gitDiff", {}).get("files", [])
    changed_snapshots = bundle.get("memoryDiff", {}).get("changedStageSnapshots", [])
    impacted_steps = bundle.get("workflowDiff", {}).get("impactedSteps", [])
    lines = [
        f"# Change Summary: {bundle.get('title') or bundle.get('bundleId')}",
        "",
        "> Generated from the canonical change bundle. Do not treat this file as the source of truth.",
        "",
        f"- Bundle ID: `{bundle.get('bundleId')}`",
        f"- Branch: `{bundle.get('branch')}`",
        f"- Base branch: `{bundle.get('baseBranch')}`",
        f"- Base revision: `{bundle.get('baseRevision')}`",
        f"- Source revision: `{bundle.get('sourceRevision')}`",
        f"- Workflow mode: `{bundle.get('workflowMode')}`",
        f"- Revision: `{bundle.get('revision')}`",
        "",
        "## Summary",
        bundle.get("summary") or "No summary recorded.",
        "",
        "## Impact",
        f"- Changed files: `{len(files)}`",
        f"- Impacted steps: `{len(impacted_steps)}`",
        f"- Changed stage snapshots: `{len(changed_snapshots)}`",
        "",
        "## Changed Files",
    ]
    if files:
        for item in files[:50]:
            lines.append(f"- `{item.get('status')}` `{item.get('path')}`")
    else:
        lines.append("- No git changes recorded.")
    lines.extend(["", "## Impacted Steps"])
    lines.extend([f"- `{step_id}`" for step_id in impacted_steps] or ["- No impacted steps detected."])
    lines.extend(["", "## Changed Stage Snapshots"])
    lines.extend(
        [f"- `{name}`" for name in changed_snapshots] or ["- No changed stage snapshots detected."]
    )
    return "\n".join(lines) + "\n"


def render_change_spec_markdown(project_path: Path, branch_name: str, bundle: dict[str, Any]) -> str:
    paths = get_change_paths(project_path, branch_name)
    feature_context = (
        (paths.branch_dir / "feature-context.md").read_text(encoding="utf-8")
        if (paths.branch_dir / "feature-context.md").exists()
        else ""
    )
    architecture = (
        (paths.branch_dir / "architecture.md").read_text(encoding="utf-8")
        if (paths.branch_dir / "architecture.md").exists()
        else ""
    )
    lines = [
        f"# Change Spec: {bundle.get('title') or bundle.get('bundleId')}",
        "",
        "> Generated from the canonical change bundle and branch artifacts.",
        "",
        f"- Branch: `{bundle.get('branch')}`",
        f"- Workflow mode: `{bundle.get('workflowMode')}`",
        "",
        "## Bundle Scope",
        bundle.get("summary") or "No summary recorded.",
        "",
        "## Feature Mapping",
    ]
    scope = bundle.get("scope", {})
    function_ids = scope.get("functionIds", [])
    lines.extend([f"- `{item}`" for item in function_ids] or ["- No feature function IDs recorded."])
    lines.extend(["", "## Integration Files"])
    for item in scope.get("modifiedFiles", []):
        lines.append(f"- modify `{item.get('path')}` — {item.get('reason') or 'No reason'}")
    for item in scope.get("newFiles", []):
        lines.append(f"- create `{item.get('path')}` — {item.get('reason') or 'No reason'}")
    if not scope.get("modifiedFiles") and not scope.get("newFiles"):
        lines.append("- No feature file mappings recorded.")
    if feature_context:
        lines.extend(["", "## Feature Context", "", feature_context.strip(), ""])
    if architecture:
        lines.extend(["", "## Architecture Context", "", architecture.strip(), ""])
    return "\n".join(lines).rstrip() + "\n"


def render_change_plan_markdown(project_path: Path, branch_name: str, bundle: dict[str, Any]) -> str:
    branch_dir = project_path / ".madspec" / branch_name
    implementation_plan = (
        (branch_dir / "implementation-plan.md").read_text(encoding="utf-8")
        if (branch_dir / "implementation-plan.md").exists()
        else ""
    )
    impacted_steps = bundle.get("workflowDiff", {}).get("impactedSteps", [])
    lines = [
        f"# Change Plan: {bundle.get('title') or bundle.get('bundleId')}",
        "",
        "> Generated from the canonical change bundle and current implementation plan.",
        "",
        "## Impacted Steps",
    ]
    lines.extend([f"- `{step_id}`" for step_id in impacted_steps] or ["- No impacted steps detected."])
    if implementation_plan:
        lines.extend(["", "## Current Implementation Plan", "", implementation_plan.strip(), ""])
    return "\n".join(lines).rstrip() + "\n"


def render_change_tasks_markdown(project_path: Path, branch_name: str, bundle: dict[str, Any]) -> str:
    branch_dir = project_path / ".madspec" / branch_name
    impacted_steps = bundle.get("workflowDiff", {}).get("impactedSteps", [])
    lines = [
        f"# Change Tasks: {bundle.get('title') or bundle.get('bundleId')}",
        "",
        "> Generated from step artifacts and the canonical change bundle.",
        "",
    ]
    if not impacted_steps:
        lines.append("- No impacted steps detected.")
        return "\n".join(lines) + "\n"

    for step_id in impacted_steps:
        task_file = branch_dir / "steps" / step_id / "tasks.md"
        lines.append(f"## {step_id}")
        lines.append("")
        if task_file.exists():
            lines.append(task_file.read_text(encoding="utf-8").strip())
        else:
            lines.append("- No step-specific tasks artifact found.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


__all__ = [
    "build_change_context",
    "render_change_plan_markdown",
    "render_change_spec_markdown",
    "render_change_summary_markdown",
    "render_change_tasks_markdown",
]
