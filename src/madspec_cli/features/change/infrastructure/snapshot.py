from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from madspec_cli.features.change.infrastructure.git_ops import _is_ignored_change_artifact
from madspec_cli.memory.shared.storage import get_memory_paths, read_json, read_jsonl
from .paths import SEMANTIC_FILES, STAGE_SNAPSHOT_FILES


def capture_branch_snapshot(project_path: Path, branch_name: str) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    branch_dir = project_path / ".madspec" / branch_name
    if not branch_dir.exists():
        warnings.append(
            f"baseline branch directory '.madspec/{branch_name}' is missing; memory diff will start empty"
        )
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
    feature_init_state = (
        read_json(paths.feature_init_state, {}) if paths.feature_init_state.exists() else {}
    )
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


def build_manifest_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def build_snapshot_diff(
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
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
        updated = sorted(
            record_id
            for record_id in set(after_records) & set(before_records)
            if after_records[record_id] != before_records[record_id]
        )
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


def _hash_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _hash_path(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = [
    "build_manifest_hash",
    "build_snapshot_diff",
    "capture_branch_snapshot",
]
