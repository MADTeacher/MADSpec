from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from ..infrastructure.storage import list_policy_history, list_policy_proposals


@dataclass(frozen=True)
class HistoryPolicyRequest:
    project_path: Path
    policy_id: str | None


@dataclass(frozen=True)
class HistoryPolicyResult(PayloadResult):
    pass


def execute(request: HistoryPolicyRequest) -> HistoryPolicyResult:
    events = list_policy_history(request.project_path)
    proposals = list_policy_proposals(request.project_path)
    if request.policy_id:
        events = [item for item in events if item.get("policyId") == request.policy_id]
        proposals = [item for item in proposals if item.get("policyId") == request.policy_id]
    return HistoryPolicyResult(payload={"events": events, "proposals": proposals})
