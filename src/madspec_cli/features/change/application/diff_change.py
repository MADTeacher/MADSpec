from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from ..infrastructure.storage import build_git_diff, build_snapshot_diff, capture_branch_snapshot, load_change_state
from .shared import find_proposal, require_change_state


@dataclass(frozen=True)
class DiffChangeRequest:
    project_path: Path
    branch_name: str
    proposal_id: str | None


@dataclass(frozen=True)
class DiffChangeResult(PayloadResult):
    pass


def execute(request: DiffChangeRequest) -> DiffChangeResult:
    state = require_change_state(request.project_path, request.branch_name)
    if request.proposal_id:
        proposal = find_proposal(request.project_path, request.branch_name, request.proposal_id)
        if proposal is None:
            raise ValueError(f"proposal '{request.proposal_id}' was not found")
        bundle = proposal["after"]
        return DiffChangeResult(
            payload={
                "branch": request.branch_name,
                "bundleId": bundle["bundleId"],
                "baseline": {
                    "base_branch": state.get("baseBranch"),
                    "base_revision": state.get("baseRevision"),
                },
                "git_diff": bundle.get("gitDiff", {}),
                "memory_diff": bundle.get("memoryDiff", {}),
                "workflow_diff": bundle.get("workflowDiff", {}),
            }
        )

    current_snapshot, _ = capture_branch_snapshot(request.project_path, request.branch_name)
    memory_diff, workflow_diff = build_snapshot_diff(state.get("baseline", {}), current_snapshot)
    git_diff = build_git_diff(request.project_path, base_revision=state["baseRevision"])
    return DiffChangeResult(
        payload={
            "branch": request.branch_name,
            "bundleId": state["bundleId"],
            "baseline": {
                "base_branch": state.get("baseBranch"),
                "base_revision": state.get("baseRevision"),
            },
            "git_diff": git_diff,
            "memory_diff": memory_diff,
            "workflow_diff": workflow_diff,
        }
    )
