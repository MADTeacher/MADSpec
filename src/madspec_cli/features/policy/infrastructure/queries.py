from __future__ import annotations

from pathlib import Path
from typing import Any

from .normalization import policy_matches_scope
from .paths import get_policy_paths
from .repository import list_policy_proposals, load_policy_state


def effective_policies(
    project_path: Path,
    *,
    stage: str | None = None,
    operation: str | None = None,
    step_kind: str | None = None,
    create_if_missing: bool = True,
) -> list[dict[str, Any]]:
    state = load_policy_state(project_path, create_if_missing=create_if_missing)
    return [
        policy
        for policy in state.get("policies", [])
        if policy_matches_scope(policy, stage=stage, operation=operation, step_kind=step_kind)
    ]


def policy_summary(
    project_path: Path,
    *,
    stage: str | None = None,
    create_if_missing: bool = True,
) -> dict[str, Any]:
    state = load_policy_state(project_path, create_if_missing=create_if_missing)
    proposals = list_policy_proposals(project_path, create_if_missing=create_if_missing)
    effective = effective_policies(project_path, stage=stage, create_if_missing=create_if_missing)
    required = [item for item in effective if item.get("enforcement") == "required"]
    advisory = [item for item in effective if item.get("enforcement") == "advisory"]
    return {
        "revision": state.get("revision", 1),
        "activeCount": len([item for item in state.get("policies", []) if item.get("status") == "active"]),
        "deprecatedCount": len([item for item in state.get("policies", []) if item.get("status") == "deprecated"]),
        "pendingProposalsCount": len([item for item in proposals if item.get("status") == "pending"]),
        "required": required,
        "advisory": advisory,
    }


def build_policy_context(
    project_path: Path,
    *,
    stage: str | None = None,
    create_if_missing: bool = True,
) -> dict[str, Any]:
    summary = policy_summary(project_path, stage=stage, create_if_missing=create_if_missing)
    return {
        "revision": summary["revision"],
        "pending_proposals_count": summary["pendingProposalsCount"],
        "required": summary["required"],
        "advisory": summary["advisory"],
        "artifact": str(get_policy_paths(project_path).artifact_file.relative_to(project_path)),
    }


__all__ = ["build_policy_context", "effective_policies", "policy_summary"]
