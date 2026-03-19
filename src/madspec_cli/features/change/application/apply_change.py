from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from madspec_cli.memory import consolidate_branch_memory
from madspec_cli.memory.shared.storage import now_iso
from madspec_cli.shared.kernel.result import PayloadResult

from ..infrastructure.storage import (
    append_change_history,
    append_change_proposal,
    save_change_state,
    write_change_summary_artifact,
)
from .shared import build_change_bundle, find_proposal, refresh_bundle_content_hashes, require_change_state


@dataclass(frozen=True)
class ApplyChangeRequest:
    project_path: Path
    branch_name: str
    proposal_id: str


@dataclass(frozen=True)
class ApplyChangeResult(PayloadResult):
    pass


def execute(request: ApplyChangeRequest) -> ApplyChangeResult:
    state = require_change_state(request.project_path, request.branch_name)
    proposal = find_proposal(request.project_path, request.branch_name, request.proposal_id)
    if proposal is None:
        raise ValueError(f"proposal '{request.proposal_id}' was not found")
    if proposal.get("status") == "applied":
        raise ValueError(f"proposal '{request.proposal_id}' is already applied")

    bundle = dict(proposal["after"])
    now = now_iso()
    bundle["appliedAt"] = now
    bundle["updatedAt"] = now
    state["revision"] = int(state.get("revision") or 0) + 1
    bundle["revision"] = int(bundle.get("revision") or 0)
    state["updatedAt"] = now
    state["activeBundle"] = bundle
    save_change_state(request.project_path, request.branch_name, state)
    consolidated = consolidate_branch_memory(request.project_path, request.branch_name)
    rebuilt_bundle, _ = build_change_bundle(
        request.project_path,
        request.branch_name,
        title=bundle.get("title") or state["bundleId"],
        summary=bundle.get("summary") or "",
    )
    rebuilt_bundle["revision"] = bundle["revision"]
    rebuilt_bundle["appliedAt"] = now
    rebuilt_bundle["exportFiles"] = bundle.get("exportFiles", [])
    refresh_bundle_content_hashes(rebuilt_bundle)
    state["activeBundle"] = rebuilt_bundle
    state["updatedAt"] = now
    save_change_state(request.project_path, request.branch_name, state)
    generated_summary = write_change_summary_artifact(request.project_path, request.branch_name, rebuilt_bundle)

    applied = dict(proposal)
    applied["status"] = "applied"
    applied["appliedAt"] = now
    append_change_proposal(request.project_path, request.branch_name, applied)
    append_change_history(
        request.project_path,
        request.branch_name,
        {
            "eventId": str(uuid.uuid4()),
            "eventType": "change_applied",
            "bundleId": rebuilt_bundle["bundleId"],
            "proposalId": request.proposal_id,
            "ts": now,
            "summary": applied["summary"],
            "payload": {"revision": state["revision"]},
        },
    )
    return ApplyChangeResult(
        payload={
            "revision": state["revision"],
            "bundle": rebuilt_bundle,
            "proposal": applied,
            "generated_artifacts": [
                str(generated_summary.relative_to(request.project_path)),
                *[str(path.relative_to(request.project_path)) for path in consolidated],
            ],
        }
    )
