from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from madspec_cli.features.git.infrastructure.operations import get_current_branch, is_git_repo
from madspec_cli.memory.shared.storage import get_memory_paths, now_iso, read_json, read_jsonl, write_json
from madspec_cli.shared.infra.subprocess_tools import run_subprocess

from ..domain.models import CHANGE_SCHEMA_VERSION, ChangeContext

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


def ensure_git_change_support(project_path: Path) -> None:
    if not is_git_repo(project_path):
        raise ValueError("change layer requires a git repository; initialize git first")


def resolve_default_base_branch(project_path: Path) -> str:
    ensure_git_change_support(project_path)
    try:
        remote_head = _run_git(project_path, ["symbolic-ref", "refs/remotes/origin/HEAD"])
        if remote_head.startswith("refs/remotes/origin/"):
            return remote_head.rsplit("/", 1)[-1]
    except ValueError:
        pass

    branches = set(_run_git(project_path, ["branch", "--format", "%(refname:short)"]).splitlines())
    for candidate in ("main", "master"):
        if candidate in branches:
            return candidate
    return "main"


def resolve_base_revision(project_path: Path, *, base_branch: str) -> str:
    ensure_git_change_support(project_path)
    current_revision = current_git_revision(project_path)
    if not base_branch:
        return current_revision
    try:
        return _run_git(project_path, ["merge-base", "HEAD", base_branch])
    except ValueError:
        return current_revision


def current_git_revision(project_path: Path) -> str:
    ensure_git_change_support(project_path)
    return _run_git(project_path, ["rev-parse", "HEAD"])


def current_git_branch(project_path: Path) -> str:
    return get_current_branch(project_path)


def load_change_state(project_path: Path, branch_name: str) -> dict[str, Any] | None:
    return read_json(get_change_paths(project_path, branch_name).state_file, None)


def save_change_state(project_path: Path, branch_name: str, state: dict[str, Any]) -> dict[str, Any]:
    paths = get_change_paths(project_path, branch_name)
    paths.change_dir.mkdir(parents=True, exist_ok=True)
    write_json(paths.state_file, state)
    if not paths.proposals_file.exists():
        paths.proposals_file.write_text("", encoding="utf-8")
    if not paths.history_file.exists():
        paths.history_file.write_text("", encoding="utf-8")
    paths.export_dir.mkdir(parents=True, exist_ok=True)
    return state


def list_change_proposals(project_path: Path, branch_name: str) -> list[dict[str, Any]]:
    return _read_jsonl(get_change_paths(project_path, branch_name).proposals_file)


def append_change_proposal(project_path: Path, branch_name: str, proposal: dict[str, Any]) -> None:
    _append_jsonl(get_change_paths(project_path, branch_name).proposals_file, [proposal])


def append_change_history(project_path: Path, branch_name: str, event: dict[str, Any]) -> None:
    _append_jsonl(get_change_paths(project_path, branch_name).history_file, [event])


def ensure_change_layout(
    project_path: Path,
    branch_name: str,
    *,
    base_branch: str,
    base_revision: str,
) -> tuple[dict[str, Any], list[str], list[Path]]:
    ensure_git_change_support(project_path)
    paths = get_change_paths(project_path, branch_name)
    created: list[Path] = []
    warnings: list[str] = []
    state = load_change_state(project_path, branch_name)
    if state is not None:
        if state.get("baseBranch") != base_branch or state.get("baseRevision") != base_revision:
            raise ValueError(
                "change store is already initialized with a different baseline; "
                "use the existing baseline or recreate the branch change store explicitly"
            )
        return state, warnings, created

    for path in (paths.branch_dir, paths.change_dir, paths.export_dir):
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(path)
    if not paths.proposals_file.exists():
        paths.proposals_file.write_text("", encoding="utf-8")
        created.append(paths.proposals_file)
    if not paths.history_file.exists():
        paths.history_file.write_text("", encoding="utf-8")
        created.append(paths.history_file)

    baseline, baseline_warnings = capture_branch_snapshot(project_path, base_branch)
    warnings.extend(baseline_warnings)
    bundle_id = f"chg-{uuid.uuid4().hex[:10]}"
    now = now_iso()
    state = {
        "schemaVersion": CHANGE_SCHEMA_VERSION,
        "branch": branch_name,
        "bundleId": bundle_id,
        "baseBranch": base_branch,
        "baseRevision": base_revision,
        "createdAt": now,
        "updatedAt": now,
        "revision": 0,
        "baseline": baseline,
        "activeBundle": None,
    }
    save_change_state(project_path, branch_name, state)
    append_change_history(
        project_path,
        branch_name,
        {
            "eventId": str(uuid.uuid4()),
            "eventType": "change_initialized",
            "bundleId": bundle_id,
            "ts": now,
            "summary": f"Initialized change store for branch {branch_name}",
            "payload": {"baseBranch": base_branch, "baseRevision": base_revision},
        },
    )
    created.append(paths.state_file)
    return state, warnings, created


def capture_branch_snapshot(project_path: Path, branch_name: str) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    branch_dir = project_path / ".madspec" / branch_name
    if not branch_dir.exists():
        warnings.append(f"baseline branch directory '.madspec/{branch_name}' is missing; memory diff will start empty")
        return {
            "branch": branch_name,
            "available": False,
            "workflowMode": "mvp",
            "progress": {"plannedSteps": [], "completedSteps": [], "currentImplementStep": None},
            "stageSnapshots": {},
            "semanticRecords": {kind: {} for kind in SEMANTIC_FILES},
            "generatedArtifacts": {},
            "contentHashes": {
                "progress": None,
                "stageSnapshots": {},
                "semanticRecords": {kind: None for kind in SEMANTIC_FILES},
                "generatedArtifacts": {},
            },
        }, warnings

    paths = get_memory_paths(project_path, branch_name)
    progress = read_json(paths.progress, {}) if paths.progress.exists() else {}
    feature_init_state = read_json(paths.feature_init_state, {}) if paths.feature_init_state.exists() else {}
    workflow_mode = "feature" if _looks_like_feature_mode(feature_init_state) else "mvp"
    snapshot = {
        "branch": branch_name,
        "available": True,
        "workflowMode": workflow_mode,
        "progress": {
            "plannedSteps": list(progress.get("plannedSteps", [])) if isinstance(progress, dict) else [],
            "completedSteps": list(progress.get("completedSteps", [])) if isinstance(progress, dict) else [],
            "currentImplementStep": progress.get("currentImplementStep") if isinstance(progress, dict) else None,
            "stepDependencies": (
                dict(progress.get("planningMetadata", {}).get("stepDependencies", {}))
                if isinstance(progress, dict)
                else {}
            ),
        },
        "stageSnapshots": {},
        "semanticRecords": {},
        "generatedArtifacts": {},
        "contentHashes": {
            "progress": _hash_path(paths.progress),
            "stageSnapshots": {},
            "semanticRecords": {},
            "generatedArtifacts": {},
        },
    }

    for stage_name, relative_parts in STAGE_SNAPSHOT_FILES.items():
        path = branch_dir.joinpath(*relative_parts)
        payload = read_json(path, {}) if path.exists() else {}
        revision = payload.get("revision", 0) if isinstance(payload, dict) else 0
        snapshot["stageSnapshots"][stage_name] = {
            "revision": revision,
            "hash": _hash_path(path),
            "exists": path.exists(),
        }
        snapshot["contentHashes"]["stageSnapshots"][stage_name] = _hash_path(path)

    for kind, relative_parts in SEMANTIC_FILES.items():
        path = branch_dir.joinpath(*relative_parts)
        records = read_jsonl(path) if path.exists() else []
        validated = {
            str(item.get("id")): _hash_json(item)
            for item in records
            if isinstance(item, dict) and item.get("status") == "validated" and item.get("id")
        }
        snapshot["semanticRecords"][kind] = validated
        snapshot["contentHashes"]["semanticRecords"][kind] = _hash_path(path)

    for path in sorted(branch_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(branch_dir).as_posix()
        if relative == "change-summary.md" or relative.startswith("memory/") or relative.startswith("change/"):
            continue
        snapshot["generatedArtifacts"][relative] = _hash_path(path)
        snapshot["contentHashes"]["generatedArtifacts"][relative] = _hash_path(path)

    return snapshot, warnings


def build_git_diff(project_path: Path, *, base_revision: str) -> dict[str, Any]:
    ensure_git_change_support(project_path)
    current_branch = current_git_branch(project_path)
    name_lines = _run_git(project_path, ["diff", "--name-status", "-M", base_revision]).splitlines()
    stat_lines = _run_git(project_path, ["diff", "--numstat", "-M", base_revision]).splitlines()
    stat_map: dict[str, dict[str, int | None]] = {}
    for line in stat_lines:
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        additions = None if parts[0] == "-" else int(parts[0])
        deletions = None if parts[1] == "-" else int(parts[1])
        key = parts[-1]
        stat_map[key] = {"additions": additions, "deletions": deletions}

    files: list[dict[str, Any]] = []
    summary = {"added": 0, "modified": 0, "deleted": 0, "renamed": 0, "untracked": 0}
    for line in name_lines:
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith("R"):
            old_path = parts[1]
            new_path = parts[2]
            if _is_ignored_change_artifact(new_path, current_branch):
                continue
            summary["renamed"] += 1
            stats = stat_map.get(new_path, {})
            files.append(
                {
                    "path": new_path,
                    "status": "renamed",
                    "old_path": old_path,
                    "additions": stats.get("additions"),
                    "deletions": stats.get("deletions"),
                }
            )
            continue
        path = parts[1] if len(parts) > 1 else ""
        if _is_ignored_change_artifact(path, current_branch):
            continue
        normalized_status = {
            "A": "added",
            "M": "modified",
            "D": "deleted",
        }.get(status, "modified")
        summary[normalized_status] += 1
        stats = stat_map.get(path, {})
        files.append(
            {
                "path": path,
                "status": normalized_status,
                "additions": stats.get("additions"),
                "deletions": stats.get("deletions"),
            }
        )

    untracked = [
        line.strip()
        for line in _run_git(project_path, ["ls-files", "--others", "--exclude-standard"]).splitlines()
        if line.strip() and not _is_ignored_change_artifact(line.strip(), current_branch)
    ]
    for path in untracked:
        files.append({"path": path, "status": "untracked", "additions": None, "deletions": None})
    summary["untracked"] = len(untracked)
    return {
        "baseRevision": base_revision,
        "currentRevision": current_git_revision(project_path),
        "worktreeDirty": bool(files),
        "summary": summary,
        "files": files,
        "untrackedFiles": untracked,
    }


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
        export_files=[item.get("path", "") for item in active_bundle.get("exportFiles", []) if item.get("path")],
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
    lines.extend([f"- `{name}`" for name in changed_snapshots] or ["- No changed stage snapshots detected."])
    return "\n".join(lines) + "\n"


def render_change_spec_markdown(project_path: Path, branch_name: str, bundle: dict[str, Any]) -> str:
    paths = get_change_paths(project_path, branch_name)
    feature_context = (paths.branch_dir / "feature-context.md").read_text(encoding="utf-8") if (paths.branch_dir / "feature-context.md").exists() else ""
    architecture = (paths.branch_dir / "architecture.md").read_text(encoding="utf-8") if (paths.branch_dir / "architecture.md").exists() else ""
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
    implementation_plan = (branch_dir / "implementation-plan.md").read_text(encoding="utf-8") if (branch_dir / "implementation-plan.md").exists() else ""
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


def write_change_summary_artifact(project_path: Path, branch_name: str, bundle: dict[str, Any]) -> Path:
    paths = get_change_paths(project_path, branch_name)
    body = render_change_summary_markdown(bundle)
    paths.summary_artifact.write_text(body, encoding="utf-8")
    return paths.summary_artifact


def export_change_bundle(project_path: Path, branch_name: str, bundle: dict[str, Any]) -> tuple[Path, list[dict[str, str]]]:
    from madspec_cli.memory.shared.system_store import sync_generated_artifacts

    paths = get_change_paths(project_path, branch_name)
    export_dir = paths.export_dir / f"{bundle['bundleId']}-r{bundle['revision']}"
    export_dir.mkdir(parents=True, exist_ok=True)

    bundle_file = export_dir / "bundle.json"
    bundle_file.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary_file = export_dir / "summary.md"
    summary_file.write_text(render_change_summary_markdown(bundle), encoding="utf-8")
    spec_file = export_dir / "spec.md"
    spec_file.write_text(render_change_spec_markdown(project_path, branch_name, bundle), encoding="utf-8")
    plan_file = export_dir / "plan.md"
    plan_file.write_text(render_change_plan_markdown(project_path, branch_name, bundle), encoding="utf-8")
    tasks_file = export_dir / "tasks.md"
    tasks_file.write_text(render_change_tasks_markdown(project_path, branch_name, bundle), encoding="utf-8")

    exported = []
    for path in (bundle_file, summary_file, spec_file, plan_file, tasks_file):
        exported.append(
            {
                "path": str(path.relative_to(project_path)),
                "contentHash": _hash_path(path) or "",
            }
        )
    sync_generated_artifacts(project_path, branch_name)
    return export_dir, exported


def build_manifest_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def build_snapshot_diff(baseline: dict[str, Any], current: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    baseline_progress = baseline.get("progress", {})
    current_progress = current.get("progress", {})
    baseline_planned = set(baseline_progress.get("plannedSteps", []))
    current_planned = set(current_progress.get("plannedSteps", []))
    baseline_completed = set(baseline_progress.get("completedSteps", []))
    current_completed = set(current_progress.get("completedSteps", []))

    stage_diffs = {"added": [], "removed": [], "modified": []}
    changed_stage_snapshots: list[str] = []
    all_stages = sorted(set(baseline.get("stageSnapshots", {})) | set(current.get("stageSnapshots", {})))
    for stage_name in all_stages:
        before_hash = baseline.get("stageSnapshots", {}).get(stage_name, {}).get("hash")
        after_hash = current.get("stageSnapshots", {}).get(stage_name, {}).get("hash")
        if before_hash == after_hash:
            continue
        changed_stage_snapshots.append(stage_name)
        if before_hash and after_hash:
            stage_diffs["modified"].append(stage_name)
        elif after_hash:
            stage_diffs["added"].append(stage_name)
        else:
            stage_diffs["removed"].append(stage_name)

    semantic_diff: dict[str, Any] = {}
    impacted_steps: set[str] = set()
    for kind in SEMANTIC_FILES:
        before_records = baseline.get("semanticRecords", {}).get(kind, {})
        after_records = current.get("semanticRecords", {}).get(kind, {})
        added = sorted(set(after_records) - set(before_records))
        removed = sorted(set(before_records) - set(after_records))
        updated = sorted(record_id for record_id in set(after_records) & set(before_records) if after_records[record_id] != before_records[record_id])
        semantic_diff[kind] = {
            "added": added,
            "updated": updated,
            "removed": removed,
            "currentCount": len(after_records),
        }

    artifact_diff = {"added": [], "removed": [], "modified": []}
    all_artifacts = sorted(set(baseline.get("generatedArtifacts", {})) | set(current.get("generatedArtifacts", {})))
    for relative in all_artifacts:
        before_hash = baseline.get("generatedArtifacts", {}).get(relative)
        after_hash = current.get("generatedArtifacts", {}).get(relative)
        if before_hash == after_hash:
            continue
        if before_hash and after_hash:
            artifact_diff["modified"].append(relative)
        elif after_hash:
            artifact_diff["added"].append(relative)
        else:
            artifact_diff["removed"].append(relative)
        if relative.startswith("steps/"):
            impacted_steps.add(relative.split("/", 2)[1])

    impacted_steps.update(sorted(current_planned - baseline_planned))
    impacted_steps.update(sorted(current_completed - baseline_completed))
    current_step = current_progress.get("currentImplementStep")
    if current_step:
        impacted_steps.add(current_step)

    workflow_diff = {
        "workflowMode": current.get("workflowMode", "mvp"),
        "plannedStepsAdded": sorted(current_planned - baseline_planned),
        "plannedStepsRemoved": sorted(baseline_planned - current_planned),
        "completedStepsAdded": sorted(current_completed - baseline_completed),
        "currentImplementStep": current_step,
        "impactedSteps": sorted(item for item in impacted_steps if item),
    }
    memory_diff = {
        "changedStageSnapshots": changed_stage_snapshots,
        "stageSnapshots": stage_diffs,
        "semanticRecords": semantic_diff,
        "generatedArtifacts": artifact_diff,
    }
    return memory_diff, workflow_diff


def _looks_like_feature_mode(feature_init_state: dict[str, Any]) -> bool:
    if not isinstance(feature_init_state, dict):
        return False
    if feature_init_state.get("featureGoal"):
        return True
    features = feature_init_state.get("features", {})
    return any(features.get(priority) for priority in ("p1", "p2", "p3"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _hash_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _hash_path(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_git(project_path: Path, args: list[str]) -> str:
    try:
        result = run_subprocess(["git", *args], cwd=project_path)
    except Exception as exc:
        raise ValueError(str(exc)) from exc
    return result.stdout.strip()


def _is_ignored_change_artifact(path: str, branch_name: str) -> bool:
    normalized = path.strip()
    branch_prefix = f".madspec/{branch_name}/"
    return (
        normalized.startswith(".madspec/system/memory/")
        or normalized == f"{branch_prefix}change-summary.md"
        or normalized.startswith(f"{branch_prefix}change/")
    )
