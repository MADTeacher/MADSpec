from __future__ import annotations

import json

from madspec_cli.memory import (
    append_jsonl,
    capture_stage_memory,
    checkpoint_stage_memory,
    consolidate_branch_memory,
    get_memory_paths,
    make_record,
    write_json,
)

from tests.support import step_metadata, step_status


def _bootstrap_change_repo(invoke_cli, git_identity_env, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("# demo\n", encoding="utf-8")

    init_result = invoke_cli(["git", "init", "--json-output"], env=git_identity_env)
    assert init_result.exit_code == 0, init_result.stdout

    current_result = invoke_cli(["git", "current-branch", "--json-output"])
    assert current_result.exit_code == 0, current_result.stdout
    current_branch = json.loads(current_result.stdout)["branch"]

    if current_branch == "main":
        main_result = invoke_cli(["git", "set-branch", "main", "--json-output"])
    else:
        main_result = invoke_cli(["git", "create-branch", "main", "--json-output"])
    assert main_result.exit_code == 0, main_result.stdout

    commit_result = invoke_cli(
        ["git", "commit", "--message", "chore: bootstrap main", "--json-output"],
        env=git_identity_env,
    )
    assert commit_result.exit_code == 0, commit_result.stdout

    feature_result = invoke_cli(["git", "create-branch", "feature/auth", "--json-output"])
    assert feature_result.exit_code == 0, feature_result.stdout


def _write_feature_branch_progress(project_path) -> None:
    paths = get_memory_paths(project_path, "feature/auth")
    write_json(
        paths.progress,
        {
            "currentImplementStep": "step-02-auth-flow",
            "completedSteps": [],
            "plannedSteps": ["step-01-bootstrap", "step-02-auth-flow"],
            "stepStatus": {
                "step-01-bootstrap": step_status(status="planned"),
                "step-02-auth-flow": step_status(status="planned"),
            },
            "stepMetadata": {
                "step-01-bootstrap": step_metadata("code", "required"),
                "step-02-auth-flow": step_metadata("code", "required"),
            },
            "coversFunctions": {
                "step-01-bootstrap": {"p1": ["Authentication"], "p2": [], "p3": []},
                "step-02-auth-flow": {"p1": ["Sessions"], "p2": [], "p3": []},
            },
            "planningMetadata": {
                "lastPlannedStep": "step-02-auth-flow",
                "planningPhase": "initial",
                "totalStepsEstimated": 2,
                "stepDependencies": {"step-02-auth-flow": ["step-01-bootstrap"]},
                "progressMetrics": {
                    "p1Coverage": {"covered": 2, "total": 2, "percentage": 100},
                    "p2Coverage": {"covered": 0, "total": 0, "percentage": 0},
                    "p3Coverage": {"covered": 0, "total": 0, "percentage": 0},
                    "overallProgress": 100,
                },
            },
        },
    )
    append_jsonl(
        paths.facts,
        [
            make_record(
                "feature/auth",
                "mvp.plan",
                "agent",
                "Auth flow bundle fact",
                status="validated",
                semantic_kind="fact",
                record_type="fact",
                step_id="step-02-auth-flow",
            )
        ],
    )
    consolidate_branch_memory(project_path, "feature/auth")


def test_change_init_requires_git_repo(make_madspec_project, invoke_cli) -> None:
    make_madspec_project()

    result = invoke_cli(["change", "init", "--json-output"])

    assert result.exit_code == 1, result.stdout
    payload = json.loads(result.stdout)
    assert "requires a git repository" in payload["error"]


def test_change_cli_happy_path_and_verify_drift(tmp_path, monkeypatch, invoke_cli, git_identity_env) -> None:
    _bootstrap_change_repo(invoke_cli, git_identity_env, tmp_path, monkeypatch)
    _write_feature_branch_progress(tmp_path)
    (tmp_path / "README.md").write_text("# demo\n\nfeature auth change\n", encoding="utf-8")

    init_result = invoke_cli(
        ["change", "init", "--branch", "feature/auth", "--base-branch", "main", "--json-output"]
    )
    assert init_result.exit_code == 0, init_result.stdout
    init_payload = json.loads(init_result.stdout)
    assert init_payload["branch"] == "feature/auth"
    assert init_payload["base_branch"] == "main"

    propose_result = invoke_cli(
        [
            "change",
            "propose",
            "--branch",
            "feature/auth",
            "--title",
            "Auth flow update",
            "--summary",
            "Bundle auth flow code and memory changes.",
            "--json-output",
        ]
    )
    assert propose_result.exit_code == 0, propose_result.stdout
    proposal_payload = json.loads(propose_result.stdout)
    assert proposal_payload["status"] == "pending"
    assert proposal_payload["after"]["bundleId"] == init_payload["bundle_id"]
    assert proposal_payload["after"]["gitDiff"]["files"]
    assert proposal_payload["after"]["workflowDiff"]["impactedSteps"]

    preview_result = invoke_cli(
        [
            "change",
            "preview",
            "--branch",
            "feature/auth",
            "--proposal-id",
            proposal_payload["proposalId"],
            "--json-output",
        ]
    )
    assert preview_result.exit_code == 0, preview_result.stdout
    assert json.loads(preview_result.stdout)["proposalId"] == proposal_payload["proposalId"]

    diff_result = invoke_cli(["change", "diff", "--branch", "feature/auth", "--json-output"])
    assert diff_result.exit_code == 0, diff_result.stdout
    diff_payload = json.loads(diff_result.stdout)
    assert diff_payload["baseline"]["base_branch"] == "main"
    assert diff_payload["workflow_diff"]["impactedSteps"]
    assert diff_payload["memory_diff"]["semanticRecords"]["facts"]["currentCount"] >= 1

    apply_result = invoke_cli(
        [
            "change",
            "apply",
            "--branch",
            "feature/auth",
            "--proposal-id",
            proposal_payload["proposalId"],
            "--json-output",
        ]
    )
    assert apply_result.exit_code == 0, apply_result.stdout
    apply_payload = json.loads(apply_result.stdout)
    assert apply_payload["revision"] == 1
    assert any(path.endswith("change-summary.md") for path in apply_payload["generated_artifacts"])

    export_result = invoke_cli(["change", "export", "--branch", "feature/auth", "--json-output"])
    assert export_result.exit_code == 0, export_result.stdout
    export_payload = json.loads(export_result.stdout)
    assert export_payload["files"]
    export_paths = {item["path"] for item in export_payload["files"]}
    assert any(path.endswith("/summary.md") for path in export_paths)
    assert any(path.endswith("/bundle.json") for path in export_paths)

    summary_result = invoke_cli(["change", "summary", "--branch", "feature/auth", "--json-output"])
    assert summary_result.exit_code == 0, summary_result.stdout
    summary_payload = json.loads(summary_result.stdout)
    assert summary_payload["bundle"]["title"] == "Auth flow update"

    verify_ok = invoke_cli(["change", "verify", "--branch", "feature/auth", "--json-output"])
    assert verify_ok.exit_code == 0, verify_ok.stdout
    assert json.loads(verify_ok.stdout)["valid"] is True

    (tmp_path / "README.md").write_text("# demo\n\nfeature auth change\n\nextra drift\n", encoding="utf-8")
    verify_drift = invoke_cli(["change", "verify", "--branch", "feature/auth", "--json-output"])
    assert verify_drift.exit_code == 1, verify_drift.stdout
    drift_payload = json.loads(verify_drift.stdout)
    assert drift_payload["valid"] is False
    assert any(item["kind"] == "git_diff" for item in drift_payload["drift"])


def test_change_feature_scope_and_review_security_context(
    tmp_path,
    monkeypatch,
    invoke_cli,
    git_identity_env,
) -> None:
    _bootstrap_change_repo(invoke_cli, git_identity_env, tmp_path, monkeypatch)
    capture_stage_memory(
        tmp_path,
        "feature/auth",
        "feature.init",
        summary="Analyze auth feature",
        feature_goal="Add auth flow",
        problem="Users cannot authenticate",
        expected_outcome="Users can sign in safely",
        project_type="web",
        framework="FastAPI + HTMX",
        feature_p1=["F01::Auth flow::Create and verify sign-in flow"],
        modified_files=["src/auth/api.py::Add sign-in endpoint::F01"],
        new_files=["src/auth/service.py::Auth orchestration::F01"],
        status="validated",
    )
    checkpoint_stage_memory(tmp_path, "feature/auth", "feature.init", "Feature init ratified")
    (tmp_path / "README.md").write_text("# demo\n\nauth feature flow\n", encoding="utf-8")

    init_result = invoke_cli(
        ["change", "init", "--branch", "feature/auth", "--base-branch", "main", "--json-output"]
    )
    assert init_result.exit_code == 0, init_result.stdout

    propose_result = invoke_cli(
        [
            "change",
            "propose",
            "--branch",
            "feature/auth",
            "--title",
            "Feature auth bundle",
            "--summary",
            "Bundle feature.init and auth integration work.",
            "--json-output",
        ]
    )
    assert propose_result.exit_code == 0, propose_result.stdout
    proposal_payload = json.loads(propose_result.stdout)
    assert proposal_payload["after"]["workflowMode"] == "feature"
    assert proposal_payload["after"]["scope"]["functionIds"] == ["F01"]
    assert proposal_payload["after"]["scope"]["modifiedFiles"][0]["path"] == "src/auth/api.py"
    assert proposal_payload["after"]["scope"]["newFiles"][0]["path"] == "src/auth/service.py"

    apply_result = invoke_cli(
        [
            "change",
            "apply",
            "--branch",
            "feature/auth",
            "--proposal-id",
            proposal_payload["proposalId"],
            "--json-output",
        ]
    )
    assert apply_result.exit_code == 0, apply_result.stdout

    review_retrieve = invoke_cli(
        ["memory", "retrieve", "--branch", "feature/auth", "--stage", "review", "--full-artifact", "--json-output"]
    )
    assert review_retrieve.exit_code == 0, review_retrieve.stdout
    review_payload = json.loads(review_retrieve.stdout)
    assert review_payload["change_context"]["initialized"] is True
    assert review_payload["change_context"]["title"] == "Feature auth bundle"
    assert review_payload["artifact_state"]["change"]["activeBundle"]["title"] == "Feature auth bundle"

    security_retrieve = invoke_cli(
        ["memory", "retrieve", "--branch", "feature/auth", "--stage", "security", "--json-output"]
    )
    assert security_retrieve.exit_code == 0, security_retrieve.stdout
    security_payload = json.loads(security_retrieve.stdout)
    assert security_payload["change_context"]["workflow_mode"] == "feature"

    review_md = (tmp_path / ".madspec" / "feature" / "auth" / "review.md").read_text(encoding="utf-8")
    security_md = (tmp_path / ".madspec" / "feature" / "auth" / "security-audit.md").read_text(encoding="utf-8")
    assert "## Active Change Bundle" in review_md
    assert "Feature auth bundle" in review_md
    assert "## Active Change Bundle" in security_md
