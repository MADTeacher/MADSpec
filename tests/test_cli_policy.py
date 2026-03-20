from __future__ import annotations

import json

from madspec_cli.features.policy.infrastructure.storage import get_policy_paths
from madspec_cli.memory import ensure_memory_layout, get_memory_paths, write_json
from madspec_cli.memory.views import consolidate_branch_memory


def test_policy_init_creates_store_and_show_lists_builtins(make_madspec_project, invoke_cli) -> None:
    project_path = make_madspec_project()

    result = invoke_cli(["policy", "init", "--json-output"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    paths = get_policy_paths(project_path)

    assert paths.state_file.exists()
    assert paths.proposals_file.exists()
    assert paths.history_file.exists()
    assert paths.artifact_file.exists()
    assert payload["revision"] == 1

    show_result = invoke_cli(["policy", "show", "--json-output"])
    assert show_result.exit_code == 0, show_result.stdout
    show_payload = json.loads(show_result.stdout)
    policy_ids = {item["policyId"] for item in show_payload["policies"]}

    assert "code-steps-require-required-tdd" in policy_ids
    assert len(show_payload["policy_context"]["required"]) >= 4
    assert show_payload["policy_context"]["pending_proposals_count"] == 0


def test_policy_propose_apply_history_and_deprecate(make_madspec_project, invoke_cli) -> None:
    make_madspec_project()

    proposal_result = invoke_cli(
        [
            "policy",
            "propose",
            "--policy-id",
            "keep-http-handlers-thin",
            "--title",
            "Keep HTTP handlers thin",
            "--description",
            "Keep transport adapters thin and move orchestration into services.",
            "--applies-to-stage",
            "mvp.architecture",
            "--json-output",
        ]
    )
    assert proposal_result.exit_code == 0, proposal_result.stdout
    proposal_payload = json.loads(proposal_result.stdout)
    assert proposal_payload["status"] == "pending"

    apply_result = invoke_cli(
        ["policy", "apply", "--proposal-id", proposal_payload["proposalId"], "--json-output"]
    )
    assert apply_result.exit_code == 0, apply_result.stdout
    apply_payload = json.loads(apply_result.stdout)
    assert apply_payload["policy"]["policyId"] == "keep-http-handlers-thin"
    assert apply_payload["policy"]["status"] == "active"

    history_result = invoke_cli(
        ["policy", "history", "--policy-id", "keep-http-handlers-thin", "--json-output"]
    )
    assert history_result.exit_code == 0, history_result.stdout
    history_payload = json.loads(history_result.stdout)
    assert any(item["eventType"] == "policy_applied" for item in history_payload["events"])
    assert any(item["status"] == "applied" for item in history_payload["proposals"])

    explain_result = invoke_cli(
        ["policy", "explain", "--policy-id", "keep-http-handlers-thin", "--json-output"]
    )
    assert explain_result.exit_code == 0, explain_result.stdout
    explain_payload = json.loads(explain_result.stdout)
    assert explain_payload["policy"]["title"] == "Keep HTTP handlers thin"
    assert explain_payload["artifact"] == ".madspec/system/policy.md"

    deprecate_result = invoke_cli(
        ["policy", "deprecate", "--policy-id", "keep-http-handlers-thin", "--json-output"]
    )
    assert deprecate_result.exit_code == 0, deprecate_result.stdout

    show_deprecated = invoke_cli(["policy", "show", "--status", "deprecated", "--json-output"])
    assert show_deprecated.exit_code == 0, show_deprecated.stdout
    deprecated_payload = json.loads(show_deprecated.stdout)
    assert any(item["policyId"] == "keep-http-handlers-thin" for item in deprecated_payload["policies"])


def test_policy_validate_reports_required_system_rule_violations(make_madspec_project, invoke_cli) -> None:
    project_path = make_madspec_project()
    ensure_memory_layout(project_path, "main")
    paths = get_memory_paths(project_path, "main")
    write_json(
        paths.progress,
        {
            "currentImplementStep": None,
            "completedSteps": [],
            "plannedSteps": ["step-01-auth"],
            "stepStatus": {
                "step-01-auth": {
                    "status": "planned",
                    "completedAt": None,
                    "tddPhase": "not_started",
                    "redEvidence": [],
                    "greenEvidence": [],
                    "refactorNote": None,
                }
            },
            "stepMetadata": {
                "step-01-auth": {
                    "kind": "code",
                    "tddPolicy": "waived",
                    "waiverReason": "Legacy shortcut",
                }
            },
            "coversFunctions": {"step-01-auth": {"p1": [], "p2": [], "p3": []}},
            "planningMetadata": {
                "lastPlannedStep": "step-01-auth",
                "planningPhase": "initial",
                "totalStepsEstimated": 1,
                "stepDependencies": {},
                "progressMetrics": {
                    "p1Coverage": {"covered": 0, "total": 0, "percentage": 0},
                    "p2Coverage": {"covered": 0, "total": 0, "percentage": 0},
                    "p3Coverage": {"covered": 0, "total": 0, "percentage": 0},
                    "overallProgress": 0,
                },
            },
        },
    )

    result = invoke_cli(
        [
            "policy",
            "validate",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--operation",
            "validate",
            "--json-output",
        ]
    )
    assert result.exit_code == 1, result.stdout
    payload = json.loads(result.stdout)
    assert payload["valid"] is False
    assert any("must use tddPolicy='required'" in item["message"] for item in payload["violations"])


def test_policy_validate_supports_toon_output(make_madspec_project, invoke_cli) -> None:
    project_path = make_madspec_project()
    ensure_memory_layout(project_path, "main")
    paths = get_memory_paths(project_path, "main")
    write_json(
        paths.progress,
        {
            "currentImplementStep": None,
            "completedSteps": [],
            "plannedSteps": ["step-01-auth"],
            "stepStatus": {"step-01-auth": {"status": "planned"}},
            "stepMetadata": {"step-01-auth": {"kind": "code", "tddPolicy": "waived"}},
            "coversFunctions": {"step-01-auth": {"p1": [], "p2": [], "p3": []}},
            "planningMetadata": {
                "lastPlannedStep": "step-01-auth",
                "planningPhase": "initial",
                "totalStepsEstimated": 1,
                "stepDependencies": {},
                "progressMetrics": {
                    "p1Coverage": {"covered": 0, "total": 0, "percentage": 0},
                    "p2Coverage": {"covered": 0, "total": 0, "percentage": 0},
                    "p3Coverage": {"covered": 0, "total": 0, "percentage": 0},
                    "overallProgress": 0,
                },
            },
        },
    )

    result = invoke_cli(
        [
            "policy",
            "validate",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--operation",
            "validate",
            "--toon-output",
        ]
    )
    assert result.exit_code == 1, result.stdout
    assert "valid: false" in result.stdout
    assert "violations:" in result.stdout


def test_memory_retrieve_includes_policy_context_and_policy_artifact(make_madspec_project, invoke_cli) -> None:
    project_path = make_madspec_project()
    ensure_memory_layout(project_path, "main")
    consolidate_branch_memory(project_path, "main")

    set_result = invoke_cli(
        [
            "policy",
            "set",
            "--policy-id",
            "document-review-risks",
            "--title",
            "Document review risks",
            "--description",
            "Capture important review risks before checkpointing review.",
            "--applies-to-stage",
            "review",
            "--json-output",
        ]
    )
    assert set_result.exit_code == 0, set_result.stdout

    retrieve_result = invoke_cli(
        [
            "memory",
            "retrieve",
            "--branch",
            "main",
            "--stage",
            "review",
            "--full-artifact",
            "--json-output",
        ]
    )
    assert retrieve_result.exit_code == 0, retrieve_result.stdout
    payload = json.loads(retrieve_result.stdout)

    advisory_ids = {item["policyId"] for item in payload["policy_context"]["advisory"]}
    assert "document-review-risks" in advisory_ids
    assert payload["artifact_state"]["policy"]["revision"] >= 2
    project_context = (project_path / ".madspec" / "main" / "project-context.md").read_text(encoding="utf-8")
    assert "Global policy artifact: `.madspec/system/policy.md`" in project_context
