from __future__ import annotations


GATE_STATUSES = {"passed", "failed", "warning", "pending", "waived", "not_applicable"}
AGGREGATE_STATUSES = {"passed", "warning", "pending", "blocked"}


def dedupe_gates(gates: list[dict[str, object]]) -> list[dict[str, object]]:
    unique: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for gate in gates:
        marker = (str(gate["gateId"]), str(gate["status"]))
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(gate)
    return unique


def apply_waivers(gates: list[dict[str, object]], waivers: list[dict[str, object]]) -> list[dict[str, object]]:
    waiver_map = {item.get("gateId"): item for item in waivers if item.get("gateId")}
    adjusted: list[dict[str, object]] = []
    for gate in gates:
        waiver = waiver_map.get(gate["gateId"])
        updated = dict(gate)
        if waiver and gate["waivable"] and gate["status"] in {"failed", "warning", "pending"}:
            updated["status"] = "waived"
        adjusted.append(updated)
    return adjusted


def aggregate_status(gates: list[dict[str, object]]) -> str:
    if any(gate["status"] == "failed" and gate["blocking"] for gate in gates):
        return "blocked"
    if any(gate["status"] == "pending" for gate in gates):
        return "pending"
    if any(gate["status"] == "warning" for gate in gates):
        return "warning"
    return "passed"
