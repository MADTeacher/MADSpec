from __future__ import annotations

from pathlib import Path
from typing import Any

from .normalization import default_policy_state, normalize_policy_state, now_iso
from .paths import SYSTEM_POLICY_BRANCH, SYSTEM_POLICY_STAGE, get_policy_paths
from .rendering import render_policy_markdown
from .repository import (
    append_jsonl,
    list_policy_proposals,
    load_policy_state,
    read_json,
    write_json,
)
from .sync import (
    refresh_branch_policy_views,
    sync_policy_artifact,
    sync_policy_record,
    sync_policy_snapshot,
)


def ensure_policy_layout(project_path: Path) -> list[Path]:
    paths = get_policy_paths(project_path)
    created: list[Path] = []
    if not paths.system_dir.exists():
        paths.system_dir.mkdir(parents=True, exist_ok=True)
        created.append(paths.system_dir)
    if not paths.policy_dir.exists():
        paths.policy_dir.mkdir(parents=True, exist_ok=True)
        created.append(paths.policy_dir)

    if not paths.state_file.exists():
        write_json(paths.state_file, default_policy_state())
        created.append(paths.state_file)
    else:
        state = normalize_policy_state(read_json(paths.state_file, default_policy_state()))
        write_json(paths.state_file, state)

    for path in (paths.proposals_file, paths.history_file):
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
            created.append(path)

    export_policy_artifact(project_path, refresh_branches=False)
    return created


def save_policy_state(project_path: Path, state: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_policy_state(state)
    normalized["updatedAt"] = now_iso()
    write_json(get_policy_paths(project_path).state_file, normalized)
    sync_policy_snapshot(project_path, normalized)
    export_policy_artifact(project_path)
    return normalized


def append_policy_proposal(project_path: Path, proposal: dict[str, Any]) -> None:
    ensure_policy_layout(project_path)
    append_jsonl(get_policy_paths(project_path).proposals_file, proposal)
    sync_policy_record(
        project_path,
        {
            "id": proposal["proposalId"],
            "ts": proposal["requestedAt"],
            "branch": SYSTEM_POLICY_BRANCH,
            "stage": SYSTEM_POLICY_STAGE,
            "status": "validated" if proposal.get("status") == "applied" else "proposed",
            "source": "policy.proposal",
            "summary": proposal["summary"],
            "scope": "project",
            "record_type": "policy_proposal",
            "metadata": {
                "policyId": proposal["policyId"],
                "action": proposal["action"],
                "status": proposal["status"],
                "diff": proposal.get("diff", {}),
                "warnings": proposal.get("warnings", []),
            },
            "evidence": [],
        },
    )


def append_policy_history(project_path: Path, event: dict[str, Any]) -> None:
    ensure_policy_layout(project_path)
    append_jsonl(get_policy_paths(project_path).history_file, event)
    sync_policy_record(
        project_path,
        {
            "id": event["eventId"],
            "ts": event["ts"],
            "branch": SYSTEM_POLICY_BRANCH,
            "stage": SYSTEM_POLICY_STAGE,
            "status": "validated",
            "source": "policy.history",
            "summary": event["summary"],
            "scope": "project",
            "record_type": "policy_event",
            "metadata": {
                "eventType": event["eventType"],
                "policyId": event.get("policyId"),
                "proposalId": event.get("proposalId"),
                "payload": event.get("payload", {}),
            },
            "evidence": [],
        },
    )


def export_policy_artifact(project_path: Path, *, refresh_branches: bool = True) -> Path:
    paths = get_policy_paths(project_path)
    state = load_policy_state(project_path, create_if_missing=False)
    proposals = list_policy_proposals(project_path, create_if_missing=False)
    content = render_policy_markdown(state, proposals)
    paths.artifact_file.parent.mkdir(parents=True, exist_ok=True)
    paths.artifact_file.write_text(content, encoding="utf-8")
    sync_policy_snapshot(project_path, state)
    sync_policy_artifact(project_path, content)
    if refresh_branches:
        refresh_branch_policy_views(project_path)
    return paths.artifact_file


__all__ = [
    "append_policy_history",
    "append_policy_proposal",
    "ensure_policy_layout",
    "export_policy_artifact",
    "save_policy_state",
]
