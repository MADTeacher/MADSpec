from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from ..infrastructure.storage import build_policy_context, list_policy_proposals, load_policy_state


@dataclass(frozen=True)
class ShowPolicyRequest:
    project_path: Path
    stage: str | None
    status: str


@dataclass(frozen=True)
class ShowPolicyResult(PayloadResult):
    pass


def execute(request: ShowPolicyRequest) -> ShowPolicyResult:
    state = load_policy_state(request.project_path)
    policies = state.get("policies", [])
    if request.status != "all":
        policies = [item for item in policies if item.get("status") == request.status]
    context = build_policy_context(request.project_path, stage=request.stage)
    return ShowPolicyResult(
        payload={
            "revision": state.get("revision", 1),
            "policies": policies,
            "policy_context": context,
            "pending_proposals": [item for item in list_policy_proposals(request.project_path) if item.get("status") == "pending"],
        }
    )
