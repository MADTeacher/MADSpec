from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from madspec_cli.shared.kernel.result import PayloadResult

from ..infrastructure.storage import (
    build_git_diff,
    build_manifest_hash,
    build_snapshot_diff,
    capture_branch_snapshot,
    get_change_paths,
    render_change_summary_markdown,
)
from .shared import build_change_bundle, require_change_state


@dataclass(frozen=True)
class VerifyChangeRequest:
    project_path: Path
    branch_name: str


@dataclass(frozen=True)
class VerifyChangeResult(PayloadResult):
    @property
    def valid(self) -> bool:
        return bool(self.payload.get("valid"))


def execute(request: VerifyChangeRequest) -> VerifyChangeResult:
    state = require_change_state(request.project_path, request.branch_name)
    active_bundle = state.get("activeBundle")
    if not isinstance(active_bundle, dict):
        raise ValueError("no active change bundle is applied; run 'madspec change apply' first")

    rebuilt_bundle, warnings = build_change_bundle(
        request.project_path,
        request.branch_name,
        title=active_bundle.get("title") or state["bundleId"],
        summary=active_bundle.get("summary") or "",
    )
    drift: list[dict[str, Any]] = []

    if build_manifest_hash(active_bundle.get("gitDiff", {})) != build_manifest_hash(rebuilt_bundle.get("gitDiff", {})):
        drift.append({"kind": "git_diff", "message": "git diff changed since the bundle was applied"})
    if build_manifest_hash(active_bundle.get("memoryDiff", {})) != build_manifest_hash(rebuilt_bundle.get("memoryDiff", {})):
        drift.append({"kind": "memory_diff", "message": "structured memory diff changed since the bundle was applied"})
    if build_manifest_hash(active_bundle.get("workflowDiff", {})) != build_manifest_hash(rebuilt_bundle.get("workflowDiff", {})):
        drift.append({"kind": "workflow_diff", "message": "workflow diff changed since the bundle was applied"})

    missing_exports = [
        item.get("path")
        for item in active_bundle.get("exportFiles", [])
        if item.get("path") and not (request.project_path / item["path"]).exists()
    ]
    if missing_exports:
        drift.append({"kind": "export_files", "message": "one or more exported files are missing"})

    paths = get_change_paths(request.project_path, request.branch_name)
    expected_summary_hash = build_manifest_hash(render_change_summary_markdown(active_bundle))
    if paths.summary_artifact.exists():
        actual_summary_hash = build_manifest_hash(paths.summary_artifact.read_text(encoding="utf-8"))
        if expected_summary_hash != actual_summary_hash:
            drift.append({"kind": "summary_artifact", "message": "change summary artifact is out of sync with the active bundle"})
    else:
        drift.append({"kind": "summary_artifact", "message": "change summary artifact is missing"})

    payload = {
        "valid": not drift and not missing_exports,
        "drift": drift,
        "missing_exports": missing_exports,
        "warnings": warnings,
    }
    return VerifyChangeResult(payload=payload)
