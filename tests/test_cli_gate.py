from __future__ import annotations

import json

from madspec_cli.features.gates.infrastructure.storage import get_gate_paths


def test_gate_status_run_explain_and_stage_aliases(init_memory_branch, invoke_cli) -> None:
    project_path = init_memory_branch(branch="main")

    status_result = invoke_cli(["gate", "status", "--branch", "main", "--stage", "review", "--json-output"])
    assert status_result.exit_code == 0, status_result.stdout
    status_payload = json.loads(status_result.stdout)

    assert status_payload["overall_status"] == "pending"
    assert status_payload["blocking_count"] == 0
    assert status_payload["pending_count"] == 1
    assert any(item["family"] == "stage_ratification" and item["status"] == "pending" for item in status_payload["gates"])

    review_status = invoke_cli(["review", "status", "--branch", "main", "--json-output"])
    assert review_status.exit_code == 0, review_status.stdout
    assert json.loads(review_status.stdout)["overall_status"] == "pending"

    security_status = invoke_cli(["security", "status", "--branch", "main", "--json-output"])
    assert security_status.exit_code == 0, security_status.stdout
    assert json.loads(security_status.stdout)["overall_status"] == "pending"

    run_result = invoke_cli(["gate", "run", "--branch", "main", "--stage", "review", "--json-output"])
    assert run_result.exit_code == 0, run_result.stdout
    run_payload = json.loads(run_result.stdout)
    assert run_payload["overall_status"] == "pending"

    history_records = get_gate_paths(project_path, "main").history_file.read_text(encoding="utf-8").splitlines()
    assert history_records
    assert any(json.loads(line)["eventType"] == "gate_run" for line in history_records)

    explain_result = invoke_cli(["gate", "explain", "--branch", "main", "--stage", "review", "--json-output"])
    assert explain_result.exit_code == 0, explain_result.stdout
    explain_payload = json.loads(explain_result.stdout)
    assert explain_payload["overall_status"] == "pending"
    assert explain_payload["history"]
    assert explain_payload["proposals"] == []


def test_gate_waiver_flow_marks_gate_as_waived(init_memory_branch, invoke_cli) -> None:
    init_memory_branch(branch="main")

    status_result = invoke_cli(["gate", "status", "--branch", "main", "--stage", "review", "--json-output"])
    assert status_result.exit_code == 0, status_result.stdout
    status_payload = json.loads(status_result.stdout)
    ratification_gate = next(item for item in status_payload["gates"] if item["family"] == "stage_ratification")

    propose_result = invoke_cli(
        [
            "gate",
            "propose-waiver",
            "--branch",
            "main",
            "--stage",
            "review",
            "--gate-id",
            ratification_gate["gateId"],
            "--reason",
            "Review checkpoint will be ratified later in a dedicated pass.",
            "--json-output",
        ]
    )
    assert propose_result.exit_code == 0, propose_result.stdout
    propose_payload = json.loads(propose_result.stdout)
    assert propose_payload["accepted"] is True
    assert propose_payload["status"] == "pending"
    assert propose_payload["gateId"] == ratification_gate["gateId"]

    apply_result = invoke_cli(
        [
            "gate",
            "apply-waiver",
            "--branch",
            "main",
            "--proposal-id",
            propose_payload["proposalId"],
            "--json-output",
        ]
    )
    assert apply_result.exit_code == 0, apply_result.stdout
    apply_payload = json.loads(apply_result.stdout)
    assert apply_payload["accepted"] is True
    assert apply_payload["proposal"]["status"] == "applied"

    waived_status = invoke_cli(["gate", "status", "--branch", "main", "--stage", "review", "--json-output"])
    assert waived_status.exit_code == 0, waived_status.stdout
    waived_payload = json.loads(waived_status.stdout)
    assert waived_payload["overall_status"] == "passed"
    assert len(waived_payload["active_waivers"]) == 1
    assert any(item["status"] == "waived" for item in waived_payload["gates"])


def test_gate_cli_rejects_empty_reason(init_memory_branch, invoke_cli) -> None:
    init_memory_branch(branch="main")

    status_result = invoke_cli(["gate", "status", "--branch", "main", "--stage", "review", "--json-output"])
    assert status_result.exit_code == 0, status_result.stdout
    status_payload = json.loads(status_result.stdout)
    ratification_gate = next(item for item in status_payload["gates"] if item["family"] == "stage_ratification")

    propose_result = invoke_cli(
        [
            "gate",
            "propose-waiver",
            "--branch",
            "main",
            "--stage",
            "review",
            "--gate-id",
            ratification_gate["gateId"],
            "--reason",
            "   ",
            "--json-output",
        ]
    )
    assert propose_result.exit_code == 1, propose_result.stdout
    payload = json.loads(propose_result.stdout)
    assert payload["accepted"] is False
    assert "must not be empty" in payload["error"]
