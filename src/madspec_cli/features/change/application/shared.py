from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from madspec_cli.memory.shared.storage import now_iso, read_json
from madspec_cli.shared.kernel.result import serialize

from madspec_cli.features.change.infrastructure.git_ops import build_git_diff, current_git_revision
from ..infrastructure.paths import get_change_paths
from ..infrastructure.repository import append_change_proposal, list_change_proposals, load_change_state
from ..infrastructure.snapshot import build_manifest_hash, build_snapshot_diff, capture_branch_snapshot


def find_proposal(project_path: Path, branch_name: str, proposal_id: str) -> dict[str, Any] | None:
    for proposal in list_change_proposals(project_path, branch_name):
        if proposal.get("proposalId") == proposal_id:
            return proposal
    return None


def build_payload_diff(before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, Any]:
    before = before or {}
    after = after or {}
    changes: list[dict[str, Any]] = []
    for field in sorted(set(before) | set(after)):
        if before.get(field) != after.get(field):
            changes.append({"field": field, "before": serialize(before.get(field)), "after": serialize(after.get(field))})
    return {"changedFields": [item["field"] for item in changes], "changes": changes}


def refresh_bundle_content_hashes(bundle: dict[str, Any]) -> dict[str, Any]:
    bundle["contentHashes"] = {
        "bundle": None,
        "gitDiff": build_manifest_hash(bundle.get("gitDiff", {})),
        "memoryDiff": build_manifest_hash(bundle.get("memoryDiff", {})),
        "workflowDiff": build_manifest_hash(bundle.get("workflowDiff", {})),
        "scope": build_manifest_hash(bundle.get("scope", {})),
    }
    bundle["contentHashes"]["bundle"] = build_manifest_hash(bundle)
    return bundle


def require_change_state(project_path: Path, branch_name: str) -> dict[str, Any]:
    state = load_change_state(project_path, branch_name)
    if state is None:
        raise ValueError("change store is not initialized; run 'madspec change init' first")
    return state


def build_change_bundle(
    project_path: Path,
    branch_name: str,
    *,
    title: str,
    summary: str,
) -> tuple[dict[str, Any], list[str]]:
    state = require_change_state(project_path, branch_name)
    now = now_iso()
    current_snapshot, warnings = capture_branch_snapshot(project_path, branch_name)
    memory_diff, workflow_diff = build_snapshot_diff(state.get("baseline", {}), current_snapshot)
    git_diff = build_git_diff(project_path, base_revision=state["baseRevision"])

    feature_init_state = read_json(get_change_paths(project_path, branch_name).branch_dir / "memory" / "stages" / "feature.init.json", {})
    analysis = feature_init_state.get("projectAnalysis", {}) if isinstance(feature_init_state, dict) else {}
    scope = {
        "stepIds": workflow_diff.get("impactedSteps", []),
        "functionIds": sorted(
            {
                function_id
                for item in analysis.get("modifiedFiles", []) + analysis.get("newFiles", [])
                if isinstance(item, dict)
                for function_id in item.get("functionIds", [])
                if function_id
            }
        ),
        "modifiedFiles": analysis.get("modifiedFiles", []) if isinstance(analysis, dict) else [],
        "newFiles": analysis.get("newFiles", []) if isinstance(analysis, dict) else [],
    }
    revision = int((state.get("activeBundle") or {}).get("revision") or 0) + 1
    bundle = {
        "bundleId": state["bundleId"],
        "branch": branch_name,
        "baseBranch": state.get("baseBranch"),
        "baseRevision": state.get("baseRevision"),
        "sourceRevision": current_git_revision(project_path),
        "title": title,
        "summary": summary,
        "workflowMode": current_snapshot.get("workflowMode", "mvp"),
        "scope": scope,
        "gitDiff": git_diff,
        "memoryDiff": memory_diff,
        "workflowDiff": workflow_diff,
        "exportFiles": [],
        "contentHashes": {
            "bundle": None,
            "gitDiff": build_manifest_hash(git_diff),
            "memoryDiff": build_manifest_hash(memory_diff),
            "workflowDiff": build_manifest_hash(workflow_diff),
            "scope": build_manifest_hash(scope),
        },
        "revision": revision,
        "createdAt": (state.get("activeBundle") or {}).get("createdAt") or state.get("createdAt"),
        "updatedAt": now,
        "appliedAt": None,
    }
    refresh_bundle_content_hashes(bundle)
    if not git_diff["files"] and not memory_diff["changedStageSnapshots"] and not any(
        section["added"] or section["updated"] or section["removed"]
        for section in memory_diff["semanticRecords"].values()
    ):
        warnings.append("no code or structured-memory deltas were detected relative to the fixed baseline")
    return bundle, warnings


def create_change_proposal(
    project_path: Path,
    branch_name: str,
    *,
    title: str,
    summary: str,
    requested_by: str,
) -> dict[str, Any]:
    state = require_change_state(project_path, branch_name)
    after, warnings = build_change_bundle(project_path, branch_name, title=title, summary=summary)
    before = state.get("activeBundle")
    proposal = {
        "proposalId": str(uuid.uuid4()),
        "bundleId": state["bundleId"],
        "status": "pending",
        "summary": f"Update change bundle {state['bundleId']}",
        "requestedAt": after["updatedAt"],
        "requestedBy": requested_by,
        "before": before,
        "after": after,
        "diff": build_payload_diff(before, after),
        "warnings": warnings,
        "appliedAt": None,
    }
    append_change_proposal(project_path, branch_name, proposal)
    return proposal
