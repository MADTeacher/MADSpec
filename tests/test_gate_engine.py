from __future__ import annotations

from madspec_cli.features.gates.application.common import _aggregate_status, _apply_waivers


def _gate(
    gate_id: str,
    *,
    status: str,
    blocking: bool = False,
    waivable: bool = True,
) -> dict[str, object]:
    return {
        "gateId": gate_id,
        "family": "policy_compliance",
        "scope": "stage",
        "subjectId": "review",
        "blocking": blocking,
        "waivable": waivable,
        "status": status,
        "message": gate_id,
        "sourceIds": [],
    }


def test_gate_aggregate_status_matrix() -> None:
    assert _aggregate_status([_gate("g1", status="passed")]) == "passed"
    assert _aggregate_status([_gate("g1", status="warning")]) == "warning"
    assert _aggregate_status([_gate("g1", status="pending")]) == "pending"
    assert _aggregate_status([_gate("g1", status="warning"), _gate("g2", status="pending")]) == "pending"
    assert _aggregate_status([_gate("g1", status="failed", blocking=True)]) == "blocked"
    assert _aggregate_status([_gate("g1", status="failed", blocking=True), _gate("g2", status="warning")]) == "blocked"


def test_gate_apply_waivers_changes_only_waivable_non_passed_gates() -> None:
    gates = [
        _gate("g-failed", status="failed", blocking=True, waivable=True),
        _gate("g-warning", status="warning", waivable=True),
        _gate("g-pending", status="pending", waivable=True),
        _gate("g-passed", status="passed", waivable=True),
        _gate("g-hard", status="failed", blocking=True, waivable=False),
    ]

    adjusted = _apply_waivers(
        gates,
        [
            {"gateId": "g-failed"},
            {"gateId": "g-warning"},
            {"gateId": "g-pending"},
            {"gateId": "g-passed"},
            {"gateId": "g-hard"},
        ],
    )
    adjusted_by_id = {item["gateId"]: item for item in adjusted}

    assert adjusted_by_id["g-failed"]["status"] == "waived"
    assert adjusted_by_id["g-warning"]["status"] == "waived"
    assert adjusted_by_id["g-pending"]["status"] == "waived"
    assert adjusted_by_id["g-passed"]["status"] == "passed"
    assert adjusted_by_id["g-hard"]["status"] == "failed"
