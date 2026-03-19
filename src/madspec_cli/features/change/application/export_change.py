from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from madspec_cli.memory.shared.storage import now_iso
from madspec_cli.shared.kernel.result import PayloadResult

from ..infrastructure.storage import append_change_history, export_change_bundle, save_change_state
from .shared import refresh_bundle_content_hashes, require_change_state


@dataclass(frozen=True)
class ExportChangeRequest:
    project_path: Path
    branch_name: str


@dataclass(frozen=True)
class ExportChangeResult(PayloadResult):
    pass


def execute(request: ExportChangeRequest) -> ExportChangeResult:
    state = require_change_state(request.project_path, request.branch_name)
    bundle = state.get("activeBundle")
    if not isinstance(bundle, dict):
        raise ValueError("no active change bundle is applied; run 'madspec change apply' first")
    now = now_iso()
    export_dir, export_files = export_change_bundle(request.project_path, request.branch_name, bundle)
    bundle["exportFiles"] = export_files
    bundle["updatedAt"] = now
    refresh_bundle_content_hashes(bundle)
    state["activeBundle"] = bundle
    state["updatedAt"] = now
    save_change_state(request.project_path, request.branch_name, state)
    append_change_history(
        request.project_path,
        request.branch_name,
        {
            "eventId": str(uuid.uuid4()),
            "eventType": "change_exported",
            "bundleId": bundle["bundleId"],
            "ts": now,
            "summary": f"Exported change bundle {bundle['bundleId']}",
            "payload": {"exportDir": str(export_dir.relative_to(request.project_path))},
        },
    )
    return ExportChangeResult(
        payload={
            "bundleId": bundle["bundleId"],
            "revision": bundle["revision"],
            "export_dir": str(export_dir.relative_to(request.project_path)),
            "files": export_files,
        }
    )
