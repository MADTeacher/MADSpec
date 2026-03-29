from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from madspec_cli.features.change.infrastructure.export import export_change_bundle
from madspec_cli.features.change.infrastructure.git_ops import current_git_revision
from madspec_cli.features.change.infrastructure.service import ensure_change_layout
from madspec_cli.features.change.infrastructure.snapshot import build_snapshot_diff, capture_branch_snapshot
from madspec_cli.features.policy.infrastructure.normalization import normalize_policy_payload
from madspec_cli.features.policy.infrastructure.queries import policy_summary
from madspec_cli.features.policy.infrastructure.rendering import render_policy_markdown
from madspec_cli.features.policy.infrastructure.repository import load_policy_state
from madspec_cli.features.policy.infrastructure.service import (
    append_policy_history,
    append_policy_proposal,
    save_policy_state,
)
from madspec_cli.memory.application.branch_state import (
    BootstrapBranchStateRequest,
    bootstrap_branch_state,
)
from madspec_cli.memory.shared.system_store.store import MemoryStore
from tests.support import bootstrap_project, git_identity_env


def _run_git(project_path: Path, *args: str) -> str:
    env = {**os.environ, **git_identity_env()}
    completed = subprocess.run(
        ["git", *args],
        cwd=project_path,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return completed.stdout.strip()


def _bootstrap_change_project(tmp_path: Path) -> Path:
    paths = bootstrap_project(tmp_path, branch="main")
    project_path = paths["branch_dir"].parents[1]
    (project_path / "README.md").write_text("# demo\n", encoding="utf-8")
    _run_git(project_path, "init")
    _run_git(project_path, "add", ".")
    _run_git(project_path, "commit", "-m", "bootstrap")
    _run_git(project_path, "checkout", "-b", "feature/auth")
    bootstrap_branch_state(
        BootstrapBranchStateRequest(project_path=project_path, branch_name="feature/auth")
    )
    return project_path


def test_policy_modules_keep_behavior_and_sync_system_store(tmp_path: Path) -> None:
    paths = bootstrap_project(tmp_path, branch="main")
    project_path = paths["branch_dir"].parents[1]

    original_state = load_policy_state(project_path)
    custom_policy, _ = normalize_policy_payload(
        {
            "policyId": "keep-handlers-thin",
            "title": "Keep handlers thin",
            "description": "Move orchestration into services.",
            "kind": "guideline",
            "enforcement": "advisory",
            "scope": {"stages": ["mvp.architecture"], "operations": ["validate"], "stepKinds": []},
            "source": "user",
            "status": "active",
            "revision": 1,
        }
    )
    updated_state = {
        **original_state,
        "policies": [*original_state["policies"], custom_policy],
        "revision": int(original_state["revision"]) + 1,
    }
    saved = save_policy_state(project_path, updated_state)

    proposal = {
        "proposalId": "proposal-1",
        "policyId": "keep-handlers-thin",
        "action": "set",
        "status": "pending",
        "summary": "Set policy keep-handlers-thin",
        "requestedAt": saved["updatedAt"],
        "requestedBy": "tester",
        "before": None,
        "after": custom_policy,
        "diff": {"changedFields": ["policyId"], "changes": []},
        "warnings": [],
        "appliedAt": None,
    }
    append_policy_proposal(project_path, proposal)
    append_policy_history(
        project_path,
        {
            "eventId": "event-1",
            "eventType": "policy_applied",
            "policyId": "keep-handlers-thin",
            "proposalId": "proposal-1",
            "ts": saved["updatedAt"],
            "summary": "Applied policy keep-handlers-thin",
            "payload": {"action": "set"},
        },
    )

    summary = policy_summary(project_path, stage="mvp.architecture")
    markdown = render_policy_markdown(saved, [proposal])
    store = MemoryStore(project_path)
    snapshot = store.fetch_snapshot("__system__", "policy")
    artifact = store.fetch_artifact(".madspec/system/policy.md")
    proposal_record = store.fetch_record("proposal-1")
    history_record = store.fetch_record("event-1")

    assert summary["revision"] == saved["revision"]
    assert any(item["policyId"] == "keep-handlers-thin" for item in summary["advisory"])
    assert "Keep handlers thin" in markdown
    assert snapshot is not None
    assert snapshot["revision"] == saved["revision"]
    assert artifact is not None
    assert "Keep handlers thin" in artifact["content"]
    assert proposal_record is not None
    assert history_record is not None


def test_change_snapshot_diff_export_and_layout_idempotency(tmp_path: Path) -> None:
    project_path = _bootstrap_change_project(tmp_path)

    baseline_state, warnings, created = ensure_change_layout(
        project_path,
        "feature/auth",
        base_branch="main",
        base_revision=current_git_revision(project_path),
    )
    repeated_state, repeated_warnings, repeated_created = ensure_change_layout(
        project_path,
        "feature/auth",
        base_branch="main",
        base_revision=current_git_revision(project_path),
    )

    assert warnings == []
    assert created
    assert repeated_state["bundleId"] == baseline_state["bundleId"]
    assert repeated_warnings == []
    assert repeated_created == []

    with pytest.raises(ValueError, match="different baseline"):
        ensure_change_layout(
            project_path,
            "feature/auth",
            base_branch="main",
            base_revision="deadbeef",
        )

    branch_dir = project_path / ".madspec" / "feature" / "auth"
    progress_path = branch_dir / "memory" / "progress.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    progress["plannedSteps"] = ["step-01-auth"]
    progress["currentImplementStep"] = "step-01-auth"
    progress_path.write_text(json.dumps(progress, indent=2) + "\n", encoding="utf-8")
    feature_init_path = branch_dir / "memory" / "stages" / "feature.init.json"
    feature_init_path.parent.mkdir(parents=True, exist_ok=True)
    feature_init_path.write_text(
        json.dumps(
            {
                "featureGoal": "Add auth flow",
                "projectAnalysis": {
                    "modifiedFiles": [{"path": "src/auth/api.py", "reason": "Extend API", "functionIds": ["F01"]}],
                    "newFiles": [{"path": "src/auth/service.py", "reason": "Add orchestration", "functionIds": ["F01"]}],
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (branch_dir / "steps" / "step-01-auth").mkdir(parents=True, exist_ok=True)
    (branch_dir / "steps" / "step-01-auth" / "tasks.md").write_text("- implement auth\n", encoding="utf-8")
    (branch_dir / "feature-context.md").write_text("# Feature context\n", encoding="utf-8")
    (branch_dir / "architecture.md").write_text("# Architecture\n", encoding="utf-8")
    (project_path / "src").mkdir(exist_ok=True)
    (project_path / "src" / "auth.py").write_text("print('auth')\n", encoding="utf-8")

    current_snapshot, snapshot_warnings = capture_branch_snapshot(project_path, "feature/auth")
    memory_diff, workflow_diff = build_snapshot_diff(baseline_state["baseline"], current_snapshot)
    bundle = {
        "bundleId": baseline_state["bundleId"],
        "branch": "feature/auth",
        "baseBranch": "main",
        "baseRevision": baseline_state["baseRevision"],
        "sourceRevision": current_git_revision(project_path),
        "title": "Feature auth bundle",
        "summary": "Bundle feature auth changes.",
        "workflowMode": current_snapshot["workflowMode"],
        "scope": {
            "stepIds": workflow_diff["impactedSteps"],
            "functionIds": ["F01"],
            "modifiedFiles": [{"path": "src/auth/api.py", "reason": "Extend API"}],
            "newFiles": [{"path": "src/auth/service.py", "reason": "Add orchestration"}],
        },
        "gitDiff": {
            "baseRevision": baseline_state["baseRevision"],
            "currentRevision": current_git_revision(project_path),
            "worktreeDirty": True,
            "summary": {"added": 1, "modified": 0, "deleted": 0, "renamed": 0, "untracked": 0},
            "files": [{"path": "src/auth.py", "status": "added", "additions": 1, "deletions": 0}],
            "untrackedFiles": [],
        },
        "memoryDiff": memory_diff,
        "workflowDiff": workflow_diff,
        "exportFiles": [],
        "contentHashes": {"bundle": None, "gitDiff": "x", "memoryDiff": "y", "workflowDiff": "z", "scope": "s"},
        "revision": 1,
        "createdAt": baseline_state["createdAt"],
        "updatedAt": baseline_state["updatedAt"],
        "appliedAt": None,
    }
    export_dir, exported = export_change_bundle(project_path, "feature/auth", bundle)

    assert snapshot_warnings == []
    assert current_snapshot["workflowMode"] == "feature"
    assert "feature.init" in memory_diff["changedStageSnapshots"]
    assert workflow_diff["impactedSteps"] == ["step-01-auth"]
    assert export_dir.exists()
    assert {Path(item["path"]).name for item in exported} == {
        "bundle.json",
        "summary.md",
        "spec.md",
        "plan.md",
        "tasks.md",
    }
